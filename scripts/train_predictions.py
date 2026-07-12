#!/usr/bin/env python3
"""
Train ML models on real Tour de France results (2020-2025) and generate
predictions for the remaining stages of the 2026 race.

Everything here is derived from the data written by fetch_tdf_data.py — no
hand-typed rider stats. Models are evaluated with leave-one-year-out cross
validation and the honest scores are published to the dashboard
(data/model_performance.parquet).

Models
------
1. stage_winner   GradientBoostingClassifier  P(rider wins a given stage)
2. stage_podium   GradientBoostingClassifier  P(rider finishes top-3 on stage)
3. stage_ranker   XGBRanker (LambdaMART)      per-stage ordering of all riders,
                                              trained on graded finish positions
                                              (win > podium > top-10 > rest) so
                                              the ordinal structure is learned
                                              directly instead of via binary
                                              targets
4. gc_position    GradientBoostingRegressor   final GC position for riders
                                              in the GC top 10 after stage 8
5. gc_podium      RandomForestClassifier      P(final GC podium) same input
6. green/polka    projection                  expected remaining finish points
                                              from models 1+2, added to current
                                              standings

The classifier and the ranker compete in the same leave-one-year-out CV on
identical features; whichever ranks stages better (top-1, then top-3 hit rate)
supplies `predicted_rank` in the published predictions. Win/podium
probabilities always come from the classifiers — a LambdaMART score is not a
probability. The choice is data-driven and re-made on every retrain; both
scores are published to the dashboard.

Usage
-----
    python scripts/train_predictions.py --train --predict
    python scripts/train_predictions.py --train            # models + metrics
    python scripts/train_predictions.py --predict          # needs models/
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
)
from sklearn.metrics import (
    log_loss,
    mean_absolute_error,
    r2_score,
    roc_auc_score,
)
from xgboost import XGBRanker

RANDOM_STATE = 42
CURRENT_YEAR = 2026
PIVOT_STAGE = 8  # stage after which the GC models are anchored

STAGE_TYPES = ["Flat", "Hilly", "Mountain", "Individual time trial"]

# Real UCI points scales for the Tour de France points classification
FINISH_POINTS = {
    "Flat":                  [50, 30, 20, 18, 16, 14, 12, 10, 8, 7, 6, 5, 4, 3, 2],
    "Hilly":                 [30, 25, 22, 19, 17, 15, 13, 11, 9, 7, 6, 5, 4, 3, 2],
    "Mountain":              [20, 17, 15, 13, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
    "Individual time trial": [20, 17, 15, 13, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
}
# Rough KOM points available to the winner of a mountain stage (summit finishes
# at HC/Cat-1 climbs award 20/10 to the first rider over)
KOM_WIN_POINTS = {"Mountain": 18.0, "Hilly": 4.0}


# ----------------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------------

class TDFData:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        hist = pd.read_parquet(data_dir / "historical" / "results.parquet")
        self.hist_results = hist[hist["record"] == "stage_result"].copy()
        self.hist_gc = hist[hist["record"] == "gc_after_stage"].copy()
        self.hist_stages = pd.read_parquet(data_dir / "historical" / "stages.parquet")
        self.hist_finals = pd.read_parquet(
            data_dir / "historical" / "final_classifications.parquet")

        live = data_dir / "live"
        self.stages = pd.read_parquet(live / "stages.parquet")
        self.results = pd.read_parquet(live / "stage_results.parquet")
        self.gc_evo = pd.read_parquet(live / "gc_evolution.parquet")
        self.riders = pd.read_parquet(live / "riders.parquet")
        self.classifications = pd.read_parquet(live / "classifications.parquet")

        # unified view of per-stage results across all years incl. 2026
        cur = self.results.copy()
        cur["year"] = CURRENT_YEAR
        keep = ["year", "stage", "position", "rider", "nationality",
                "team", "stage_type", "distance_km"]
        self.all_results = pd.concat(
            [self.hist_results[keep], cur[keep]], ignore_index=True)
        self.all_results = self.all_results.dropna(subset=["rider"])

        cur_stages = self.stages.copy()
        cur_stages["year"] = CURRENT_YEAR
        self.all_stages = pd.concat(
            [self.hist_stages[["year", "stage", "stage_type", "distance_km"]],
             cur_stages[["year", "stage", "stage_type", "distance_km"]]],
            ignore_index=True)


# ----------------------------------------------------------------------------
# Feature engineering — stage winner / podium models
# ----------------------------------------------------------------------------

def _count_by_type(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    """Pivot top-10 appearances into per-stage-type count columns."""
    if df.empty:
        return pd.DataFrame(columns=[f"{prefix}_{t.split()[0].lower()}"
                                     for t in STAGE_TYPES])
    pv = (df.assign(n=1)
            .pivot_table(index="rider", columns="stage_type", values="n",
                         aggfunc="sum", fill_value=0))
    pv.columns = [f"{prefix}_{str(c).split()[0].lower()}" for c in pv.columns]
    return pv


FEATURE_COLS = [
    "distance_km", "race_progress",
    "type_flat", "type_hilly", "type_mountain", "type_itt",
    # career (previous years in dataset)
    "career_wins", "career_podiums",
    "career_top10_flat", "career_top10_hilly", "career_top10_mountain",
    "career_top10_individual",
    "career_best_final_gc",
    # current-tour form (stages before the one being predicted)
    "tour_wins", "tour_podiums",
    "tour_top10_flat", "tour_top10_hilly", "tour_top10_mountain",
    "tour_top10_individual",
    "tour_gc_position",
    # explicit rider-x-stage-type interactions (the strongest signal:
    # sprinters win flat stages, climbers win mountain stages)
    "career_wins_same_type", "career_top10_same_type",
    "tour_wins_same_type", "tour_podiums_same_type", "tour_top10_same_type",
]


def build_stage_matrix(data: TDFData, year: int, upto_stage: int | None = None,
                       pool: pd.Series | None = None) -> pd.DataFrame:
    """One row per (stage, rider) for `year`.

    For training years all stages are emitted (with form features computed
    from earlier stages of the same tour only — no leakage). For 2026,
    `upto_stage` limits form features and `pool` supplies the startlist.
    """
    results = data.all_results
    year_stages = data.all_stages[data.all_stages["year"] == year]
    year_results = results[results["year"] == year]

    career = results[results["year"] < year]
    career_top10 = _count_by_type(career, "career_top10")
    career_wins_t = _count_by_type(career[career["position"] == 1], "career_wins")
    career_wins = career[career["position"] == 1].groupby("rider").size()
    career_podiums = career[career["position"] <= 3].groupby("rider").size()

    finals_gc = data.hist_finals.query(
        "classification == 'general' and year < @year")
    career_best_gc = finals_gc.groupby("rider")["rank"].min()

    if pool is None:
        pool_riders = pd.Index(year_results["rider"].unique())
    else:
        pool_riders = pd.Index(pool.unique())

    if year == CURRENT_YEAR:
        gc_source = data.gc_evo
    else:
        gc_source = data.hist_gc[data.hist_gc["year"] == year]

    rows = []
    stage_list = year_stages.sort_values("stage")
    for _, st in stage_list.iterrows():
        s_no, s_type = int(st["stage"]), st["stage_type"]
        if s_type == "Team time trial":
            continue  # team event: no rider-level winner
        if upto_stage is not None and s_no <= upto_stage:
            continue
        # form = everything earlier in this tour
        before = year_results[year_results["stage"] < s_no]
        form_top10 = _count_by_type(before, "tour_top10")
        form_wins_t = _count_by_type(before[before["position"] == 1], "tour_wins")
        form_pod_t = _count_by_type(before[before["position"] <= 3], "tour_podiums")
        form_wins = before[before["position"] == 1].groupby("rider").size()
        form_podiums = before[before["position"] <= 3].groupby("rider").size()
        type_key = s_type.split()[0].lower()
        gc_before = gc_source[gc_source["stage"] < s_no]
        if not gc_before.empty:
            last_gc = gc_before[gc_before["stage"] == gc_before["stage"].max()]
            gc_pos = last_gc.set_index("rider")["position"]
        else:
            gc_pos = pd.Series(dtype=float)

        stage_winners = set(
            year_results.query("stage == @s_no and position == 1")["rider"])
        stage_podium = set(
            year_results.query("stage == @s_no and position <= 3")["rider"])
        stage_positions = (year_results.query("stage == @s_no")
                           .set_index("rider")["position"].to_dict())

        for rider in pool_riders:
            rows.append({
                "year": year, "stage": s_no, "rider": rider,
                "stage_type": s_type,
                "distance_km": st["distance_km"],
                "race_progress": s_no / 21,
                "type_flat": int(s_type == "Flat"),
                "type_hilly": int(s_type == "Hilly"),
                "type_mountain": int(s_type == "Mountain"),
                "type_itt": int(s_type == "Individual time trial"),
                "career_wins": int(career_wins.get(rider, 0)),
                "career_podiums": int(career_podiums.get(rider, 0)),
                "career_top10_flat": int(career_top10.get("career_top10_flat", pd.Series()).get(rider, 0)),
                "career_top10_hilly": int(career_top10.get("career_top10_hilly", pd.Series()).get(rider, 0)),
                "career_top10_mountain": int(career_top10.get("career_top10_mountain", pd.Series()).get(rider, 0)),
                "career_top10_individual": int(career_top10.get("career_top10_individual", pd.Series()).get(rider, 0)),
                "career_best_final_gc": float(career_best_gc.get(rider, 60)),
                "tour_wins": int(form_wins.get(rider, 0)),
                "tour_podiums": int(form_podiums.get(rider, 0)),
                "tour_top10_flat": int(form_top10.get("tour_top10_flat", pd.Series()).get(rider, 0)),
                "tour_top10_hilly": int(form_top10.get("tour_top10_hilly", pd.Series()).get(rider, 0)),
                "tour_top10_mountain": int(form_top10.get("tour_top10_mountain", pd.Series()).get(rider, 0)),
                "tour_top10_individual": int(form_top10.get("tour_top10_individual", pd.Series()).get(rider, 0)),
                "tour_gc_position": float(gc_pos.get(rider, 60)),
                "career_wins_same_type": int(career_wins_t.get(f"career_wins_{type_key}", pd.Series()).get(rider, 0)),
                "career_top10_same_type": int(career_top10.get(f"career_top10_{type_key}", pd.Series()).get(rider, 0)),
                "tour_wins_same_type": int(form_wins_t.get(f"tour_wins_{type_key}", pd.Series()).get(rider, 0)),
                "tour_podiums_same_type": int(form_pod_t.get(f"tour_podiums_{type_key}", pd.Series()).get(rider, 0)),
                "tour_top10_same_type": int(form_top10.get(f"tour_top10_{type_key}", pd.Series()).get(rider, 0)),
                "won_stage": int(rider in stage_winners),
                "top3_stage": int(rider in stage_podium),
                # graded relevance for the ranker: the ordinal target the
                # binary classifiers cannot see (win > podium > top-10 > rest;
                # results data covers each stage's top 10)
                "rank_grade": rank_grade(stage_positions.get(rider)),
            })
    return pd.DataFrame(rows)


def rank_grade(position: float | None) -> int:
    """Ordinal relevance grade for LambdaMART from a stage finish position."""
    if position is None or pd.isna(position):
        return 0
    if position == 1:
        return 3
    if position <= 3:
        return 2
    if position <= 10:
        return 1
    return 0


# ----------------------------------------------------------------------------
# Feature engineering — GC models
# ----------------------------------------------------------------------------

GC_FEATURE_COLS = [
    "gap_after8_seconds", "position_after8",
    "remaining_mountain_stages", "remaining_itt_km", "remaining_km",
    "career_best_final_gc", "tour_wins_so_far", "tour_top10_mountain_so_far",
]


def remaining_route_features(stages: pd.DataFrame, after_stage: int) -> dict:
    rem = stages[stages["stage"] > after_stage]
    itt = rem[rem["stage_type"] == "Individual time trial"]
    return {
        "remaining_mountain_stages": int((rem["stage_type"] == "Mountain").sum()),
        "remaining_itt_km": float(itt["distance_km"].sum()),
        "remaining_km": float(rem["distance_km"].sum()),
    }


def build_gc_matrix(data: TDFData) -> pd.DataFrame:
    """Training rows: GC top-10 after stage 8, one per (year, rider)."""
    rows = []
    for year in sorted(data.hist_gc["year"].unique()):
        gc8 = data.hist_gc.query("year == @year and stage == @PIVOT_STAGE")
        finals = data.hist_finals.query(
            "classification == 'general' and year == @year")
        final_gap = finals.set_index("rider")["gap_seconds"]
        final_rank = finals.set_index("rider")["rank"]
        stages_y = data.hist_stages[data.hist_stages["year"] == year]
        route = remaining_route_features(stages_y, PIVOT_STAGE)
        res_y = data.hist_results.query("year == @year and stage <= @PIVOT_STAGE")
        wins8 = res_y[res_y["position"] == 1].groupby("rider").size()
        mtn8 = res_y[(res_y["position"] <= 10)
                     & (res_y["stage_type"] == "Mountain")].groupby("rider").size()
        career_gc = data.hist_finals.query(
            "classification == 'general' and year < @year")
        career_best = career_gc.groupby("rider")["rank"].min()
        for _, r in gc8.iterrows():
            rider = r["rider"]
            rows.append({
                "year": year, "rider": rider,
                "gap_after8_seconds": r["gap_seconds"],
                "position_after8": r["position"],
                **route,
                "career_best_final_gc": float(career_best.get(rider, 60)),
                "tour_wins_so_far": int(wins8.get(rider, 0)),
                "tour_top10_mountain_so_far": int(mtn8.get(rider, 0)),
                "final_gap_seconds": float(final_gap.get(rider, np.nan)),
                # riders who fell out of the final top 10 (crash, blow-up,
                # abandon) get a censored rank of 12
                "final_rank": float(final_rank.get(rider, 12)),
                "final_podium": int(final_rank.get(rider, 99) <= 3),
            })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# Training + honest evaluation (leave-one-year-out)
# ----------------------------------------------------------------------------

def make_stage_model() -> GradientBoostingClassifier:
    return GradientBoostingClassifier(
        n_estimators=200, max_depth=3, learning_rate=0.05,
        subsample=0.9, random_state=RANDOM_STATE)


def evaluate_stage_model(matrix: pd.DataFrame, target: str) -> dict:
    """Leave-one-year-out CV, scored on stages 9-21 of the held-out year —
    the regime the deployed model runs in (predicting the rest of the race
    with a week of form data), so the published numbers match reality."""
    years = sorted(matrix["year"].unique())
    top1_hits, top3_hits, n_stages = 0, 0, 0
    all_proba, all_true = [], []
    for held in years:
        train = matrix[matrix["year"] != held]
        test = matrix[(matrix["year"] == held) & (matrix["stage"] > PIVOT_STAGE)]
        model = make_stage_model()
        model.fit(train[FEATURE_COLS], train[target])
        proba = model.predict_proba(test[FEATURE_COLS])[:, 1]
        test = test.assign(proba=proba)
        all_proba.extend(proba)
        all_true.extend(test[target])
        for s_no, grp in test.groupby("stage"):
            actual = set(grp.loc[grp["won_stage"] == 1, "rider"])
            if not actual:
                continue
            ranked = grp.sort_values("proba", ascending=False)["rider"].tolist()
            n_stages += 1
            top1_hits += int(ranked[0] in actual)
            top3_hits += int(bool(actual & set(ranked[:3])))
    return {
        "cv_top1_rate": top1_hits / n_stages,
        "cv_top3_rate": top3_hits / n_stages,
        "cv_auc": roc_auc_score(all_true, all_proba),
        "cv_log_loss": log_loss(all_true, all_proba),
        "n_eval_stages": n_stages,
    }


def make_stage_ranker() -> XGBRanker:
    """LambdaMART over the same features, learning the per-stage ordering from
    graded finish positions instead of a binary won/lost label. Tree budget
    mirrors make_stage_model so the CV comparison is model-class against
    model-class, not a tuning contest."""
    return XGBRanker(
        objective="rank:ndcg",
        n_estimators=200, max_depth=3, learning_rate=0.05,
        subsample=0.9, random_state=RANDOM_STATE)


def _stage_qid(frame: pd.DataFrame) -> pd.Series:
    """One ranking group per (year, stage); monotone when sorted by both."""
    return frame["year"] * 100 + frame["stage"]


def evaluate_stage_ranker(matrix: pd.DataFrame) -> dict:
    """Same LOYO regime as evaluate_stage_model — held-out year, scored on
    stages 9-21 — but the candidate is a ranker: one score per (stage, rider)
    and top-1/top-3 read straight off the ordering. AUC of the scores against
    the actual winners is rank-based and scale-free, so it is comparable with
    the classifiers'; log loss is undefined for scores (not probabilities)."""
    years = sorted(matrix["year"].unique())
    top1_hits, top3_hits, n_stages = 0, 0, 0
    all_scores, all_true = [], []
    for held in years:
        train = matrix[matrix["year"] != held].sort_values(["year", "stage"])
        test = matrix[(matrix["year"] == held) & (matrix["stage"] > PIVOT_STAGE)]
        model = make_stage_ranker()
        model.fit(train[FEATURE_COLS], train["rank_grade"], qid=_stage_qid(train))
        scores = model.predict(test[FEATURE_COLS])
        test = test.assign(score=scores)
        all_scores.extend(scores)
        all_true.extend(test["won_stage"])
        for s_no, grp in test.groupby("stage"):
            actual = set(grp.loc[grp["won_stage"] == 1, "rider"])
            if not actual:
                continue
            ranked = grp.sort_values("score", ascending=False)["rider"].tolist()
            n_stages += 1
            top1_hits += int(ranked[0] in actual)
            top3_hits += int(bool(actual & set(ranked[:3])))
    return {
        "cv_top1_rate": top1_hits / n_stages,
        "cv_top3_rate": top3_hits / n_stages,
        "cv_auc": roc_auc_score(all_true, all_scores),
        "n_eval_stages": n_stages,
    }


def make_gc_regressor() -> GradientBoostingRegressor:
    return GradientBoostingRegressor(
        n_estimators=80, max_depth=2, learning_rate=0.05, loss="huber",
        min_samples_leaf=5, random_state=RANDOM_STATE)


def evaluate_gc_models(gc: pd.DataFrame) -> tuple[dict, dict]:
    """The regressor predicts each rider's FINAL GC position (riders who
    dropped out of the top 10 are censored at 12). Also reports the
    'no change' baseline (final position = position after stage 8)."""
    years = sorted(gc["year"].unique())
    reg_pred, reg_true, base_pred = [], [], []
    cls_proba, cls_true = [], []
    for held in years:
        train, test = gc[gc["year"] != held], gc[gc["year"] == held]
        reg = make_gc_regressor()
        reg.fit(train[GC_FEATURE_COLS], train["final_rank"])
        reg_pred.extend(reg.predict(test[GC_FEATURE_COLS]))
        reg_true.extend(test["final_rank"])
        base_pred.extend(test["position_after8"])
        cls = RandomForestClassifier(
            n_estimators=300, max_depth=4, random_state=RANDOM_STATE,
            class_weight="balanced")
        cls.fit(train[GC_FEATURE_COLS], train["final_podium"])
        cls_proba.extend(cls.predict_proba(test[GC_FEATURE_COLS])[:, 1])
        cls_true.extend(test["final_podium"])
    reg_metrics = {
        "cv_mae_places": mean_absolute_error(reg_true, reg_pred),
        "cv_r2": r2_score(reg_true, reg_pred),
        "baseline_mae_places": mean_absolute_error(reg_true, base_pred),
        "n_rows": len(reg_true),
    }
    cls_metrics = {
        "cv_auc": roc_auc_score(cls_true, cls_proba),
        "cv_log_loss": log_loss(cls_true, cls_proba),
        "n_rows": len(cls_true),
    }
    return reg_metrics, cls_metrics


# ----------------------------------------------------------------------------
# Rider profiles (data-derived specialities — used for display & analysis)
# ----------------------------------------------------------------------------

def build_rider_profiles(data: TDFData) -> pd.DataFrame:
    res = data.all_results
    top10 = _count_by_type(res[res["position"] <= 10], "top10")
    wins = res[res["position"] == 1].groupby("rider").size().rename("career_stage_wins")
    podiums = res[res["position"] <= 3].groupby("rider").size().rename("career_podiums")
    gc_top10 = pd.concat([
        data.hist_finals.query("classification == 'general' and rank <= 10")["rider"],
        data.gc_evo.query("stage == @PIVOT_STAGE and position <= 10")["rider"],
    ]).value_counts().rename("gc_top10_years")

    prof = data.riders[["rider", "team", "country", "age", "status"]].copy()
    prof = (prof.set_index("rider")
            .join([top10, wins, podiums, gc_top10]).fillna(0).reset_index())
    for c in ["top10_flat", "top10_hilly", "top10_mountain", "top10_individual"]:
        if c not in prof.columns:
            prof[c] = 0

    def classify(r) -> str:
        total = r.top10_flat + r.top10_hilly + r.top10_mountain + r.top10_individual
        if r.gc_top10_years > 0 and r.top10_mountain >= 2:
            return "GC contender"
        if total == 0:
            return "Domestique"
        if r.top10_flat >= max(r.top10_mountain, r.top10_hilly) and r.top10_flat >= 2:
            return "Sprinter"
        if r.top10_mountain > max(r.top10_flat, r.top10_hilly):
            return "Climber"
        if r.top10_individual >= 2 and r.top10_individual >= r.top10_mountain:
            return "Time trialist"
        if r.top10_hilly >= 2:
            return "Puncheur"
        return "Stage hunter"

    prof["specialist"] = prof.apply(classify, axis=1)
    int_cols = ["career_stage_wins", "career_podiums", "gc_top10_years",
                "top10_flat", "top10_hilly", "top10_mountain", "top10_individual"]
    prof[int_cols] = prof[int_cols].astype(int)
    return prof


# ----------------------------------------------------------------------------
# Prediction
# ----------------------------------------------------------------------------

def predict_2026(data: TDFData, models_dir: Path, out_dir: Path,
                 profiles: pd.DataFrame) -> None:
    stage_winner = joblib.load(models_dir / "stage_winner_model.pkl")
    stage_podium = joblib.load(models_dir / "stage_podium_model.pkl")
    gc_reg = joblib.load(models_dir / "gc_position_model.pkl")
    gc_cls = joblib.load(models_dir / "gc_podium_model.pkl")

    # which model won the CV ranking contest at train time (see main)
    selection_file = models_dir / "model_selection.json"
    rank_source = "classifier"
    if selection_file.exists():
        rank_source = json.loads(selection_file.read_text()).get(
            "stage_rank_source", "classifier")

    active = data.riders.query("status == 'active'")["rider"]
    matrix = build_stage_matrix(
        data, CURRENT_YEAR, upto_stage=PIVOT_STAGE, pool=active)

    matrix["win_probability_raw"] = stage_winner.predict_proba(
        matrix[FEATURE_COLS])[:, 1]
    matrix["podium_probability"] = stage_podium.predict_proba(
        matrix[FEATURE_COLS])[:, 1]
    # exactly one rider wins each stage: normalise per stage
    matrix["win_probability"] = matrix.groupby("stage")[
        "win_probability_raw"].transform(lambda p: p / p.sum())
    if rank_source == "ranker":
        # ordering from LambdaMART; win/podium probabilities stay with the
        # calibrated classifiers (a ranking score is not a probability)
        ranker = joblib.load(models_dir / "stage_ranker_model.pkl")
        matrix["rank_score"] = ranker.predict(matrix[FEATURE_COLS])
        matrix["predicted_rank"] = matrix.groupby("stage")[
            "rank_score"].rank(ascending=False, method="first").astype(int)
    else:
        matrix["predicted_rank"] = matrix.groupby("stage")[
            "win_probability"].rank(ascending=False, method="first").astype(int)
    print(f"  predicted_rank source: {rank_source}")

    stage_meta = data.stages[[
        "stage", "date", "start_location", "end_location"]].copy()
    preds = matrix.merge(stage_meta, on="stage", how="left").merge(
        profiles[["rider", "team", "country", "age", "specialist"]],
        on="rider", how="left")
    cols = ["stage", "date", "start_location", "end_location", "stage_type",
            "distance_km", "rider", "team", "country", "age", "specialist",
            "win_probability", "podium_probability", "predicted_rank"]
    preds = preds[cols].sort_values(["stage", "predicted_rank"])
    out_dir.mkdir(parents=True, exist_ok=True)
    preds.to_parquet(out_dir / "stage_predictions.parquet", index=False)
    print(f"  predictions/stage_predictions: {len(preds)} rows "
          f"({preds['stage'].nunique()} stages x {preds['rider'].nunique()} riders)")

    # ---- final GC forecast ------------------------------------------------
    gc_now = data.gc_evo.query("stage == @PIVOT_STAGE").copy()
    route = remaining_route_features(data.stages, PIVOT_STAGE)
    res8 = data.results.query("stage <= @PIVOT_STAGE")
    wins8 = res8[res8["position"] == 1].groupby("rider").size()
    mtn8 = res8[(res8["position"] <= 10)
                & (res8["stage_type"] == "Mountain")].groupby("rider").size()
    career_gc = data.hist_finals.query("classification == 'general'")
    career_best = career_gc.groupby("rider")["rank"].min()
    gc_rows = []
    for _, r in gc_now.iterrows():
        gc_rows.append({
            "rider": r["rider"], "team": r["team"],
            "current_position": r["position"],
            "current_gap_seconds": r["gap_seconds"],
            "gap_after8_seconds": r["gap_seconds"],
            "position_after8": r["position"],
            **route,
            "career_best_final_gc": float(career_best.get(r["rider"], 60)),
            "tour_wins_so_far": int(wins8.get(r["rider"], 0)),
            "tour_top10_mountain_so_far": int(mtn8.get(r["rider"], 0)),
        })
    gc_pred = pd.DataFrame(gc_rows)
    gc_pred["predicted_position_score"] = gc_reg.predict(
        gc_pred[GC_FEATURE_COLS]).round(1)
    gc_pred["podium_probability"] = gc_cls.predict_proba(
        gc_pred[GC_FEATURE_COLS])[:, 1].round(3)
    gc_pred["predicted_final_position"] = gc_pred[
        "predicted_position_score"].rank(method="first").astype(int)
    gc_pred["current_gap"] = gc_pred["current_gap_seconds"].map(
        lambda s: "—" if s == 0 else f"+ {int(s // 60)}' {int(s % 60):02d}\"")
    keep = ["rider", "team", "current_position", "current_gap",
            "current_gap_seconds", "predicted_final_position",
            "predicted_position_score", "podium_probability"]
    gc_pred[keep].sort_values("predicted_final_position").to_parquet(
        out_dir / "gc_forecast.parquet", index=False)
    print(f"  predictions/gc_forecast: {len(gc_pred)} riders")

    # ---- jersey projections ------------------------------------------------
    def expected_finish_points(row) -> float:
        pts = FINISH_POINTS[row["stage_type"]]
        p_win = row["win_probability"]
        p_pod = max(row["podium_probability"] - p_win, 0)
        return p_win * pts[0] + p_pod * (pts[1] + pts[2]) / 2

    preds_p = matrix.merge(data.stages[["stage"]], on="stage")
    preds_p = matrix.copy()
    preds_p["exp_points"] = preds_p.apply(expected_finish_points, axis=1)
    exp_green = preds_p.groupby("rider")["exp_points"].sum()

    kom = preds_p[preds_p["stage_type"].isin(KOM_WIN_POINTS)].copy()
    kom["exp_kom"] = kom.apply(
        lambda r: r["win_probability"] * KOM_WIN_POINTS[r["stage_type"]]
        + max(r["podium_probability"] - r["win_probability"], 0)
        * KOM_WIN_POINTS[r["stage_type"]] * 0.4, axis=1)
    exp_kom = kom.groupby("rider")["exp_kom"].sum()

    jerseys = []
    for cls_name, expected in (("points", exp_green), ("mountains", exp_kom)):
        current = data.classifications.query(
            "classification == @cls_name").set_index("rider")["points"]
        riders_union = current.index.union(expected.index)
        proj = pd.DataFrame({
            "classification": cls_name,
            "rider": riders_union,
            "current_points": [float(current.get(r, 0) or 0) for r in riders_union],
            "projected_additional_points":
                [round(float(expected.get(r, 0)), 1) for r in riders_union],
        })
        proj["projected_total_points"] = (
            proj["current_points"] + proj["projected_additional_points"]).round(1)
        proj["current_rank"] = (proj["current_points"]
                                .rank(ascending=False, method="min").astype(int))
        proj["projected_rank"] = (proj["projected_total_points"]
                                  .rank(ascending=False, method="first").astype(int))
        jerseys.append(proj.sort_values("projected_rank").head(30))
    jersey_df = pd.concat(jerseys, ignore_index=True).merge(
        profiles[["rider", "team", "specialist"]], on="rider", how="left")
    jersey_df.to_parquet(out_dir / "jersey_projections.parquet", index=False)
    print(f"  predictions/jersey_projections: {len(jersey_df)} rows")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Train TDF models / predict 2026")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--predict", action="store_true")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--models-dir", default="models")
    args = parser.parse_args()
    if not (args.train or args.predict):
        parser.print_help()
        return 1

    data_dir, models_dir = Path(args.data_dir), Path(args.models_dir)
    out_dir = data_dir / "predictions"
    data = TDFData(data_dir)
    profiles = build_rider_profiles(data)
    profiles.to_parquet(data_dir / "live" / "rider_profiles.parquet", index=False)
    print(f"rider_profiles: {len(profiles)} riders "
          f"({profiles['specialist'].value_counts().to_dict()})")

    if args.train:
        print("Building training matrices from 2020-2025 results...")
        matrices = [build_stage_matrix(data, y)
                    for y in sorted(data.hist_results["year"].unique())]
        matrix = pd.concat(matrices, ignore_index=True)
        print(f"  stage matrix: {len(matrix)} rider-stage rows, "
              f"{matrix['won_stage'].sum()} winners")
        gc_matrix = build_gc_matrix(data)
        print(f"  GC matrix: {len(gc_matrix)} rows")

        print("Cross-validating (leave-one-year-out)...")
        winner_metrics = evaluate_stage_model(matrix, "won_stage")
        podium_metrics = evaluate_stage_model(matrix, "top3_stage")
        ranker_metrics = evaluate_stage_ranker(matrix)
        gc_reg_metrics, gc_cls_metrics = evaluate_gc_models(gc_matrix)
        print(f"  stage winner: top1 {winner_metrics['cv_top1_rate']:.0%}, "
              f"top3 {winner_metrics['cv_top3_rate']:.0%}, "
              f"AUC {winner_metrics['cv_auc']:.3f}")
        print(f"  stage ranker: top1 {ranker_metrics['cv_top1_rate']:.0%}, "
              f"top3 {ranker_metrics['cv_top3_rate']:.0%}, "
              f"AUC {ranker_metrics['cv_auc']:.3f}")
        # The published stage ordering goes to whichever model class ranks the
        # held-out years better: top-1 hit rate first, top-3 breaks the tie.
        # A full tie keeps the incumbent classifier (its probabilities are the
        # calibrated output the rest of the pipeline consumes anyway).
        use_ranker = (
            (ranker_metrics["cv_top1_rate"], ranker_metrics["cv_top3_rate"])
            > (winner_metrics["cv_top1_rate"], winner_metrics["cv_top3_rate"]))
        rank_source = "ranker" if use_ranker else "classifier"
        print(f"  → published stage ranking comes from the {rank_source}")
        print(f"  GC position: MAE {gc_reg_metrics['cv_mae_places']:.2f} places "
              f"(no-change baseline {gc_reg_metrics['baseline_mae_places']:.2f}), "
              f"R2 {gc_reg_metrics['cv_r2']:.2f}")

        print("Fitting final models on all years...")
        models_dir.mkdir(parents=True, exist_ok=True)
        m_win = make_stage_model().fit(matrix[FEATURE_COLS], matrix["won_stage"])
        m_pod = make_stage_model().fit(matrix[FEATURE_COLS], matrix["top3_stage"])
        sorted_matrix = matrix.sort_values(["year", "stage"])
        m_rank = make_stage_ranker().fit(
            sorted_matrix[FEATURE_COLS], sorted_matrix["rank_grade"],
            qid=_stage_qid(sorted_matrix))
        m_gc = make_gc_regressor().fit(
            gc_matrix[GC_FEATURE_COLS], gc_matrix["final_rank"])
        m_gcp = RandomForestClassifier(
            n_estimators=300, max_depth=4, random_state=RANDOM_STATE,
            class_weight="balanced").fit(
            gc_matrix[GC_FEATURE_COLS], gc_matrix["final_podium"])
        joblib.dump(m_win, models_dir / "stage_winner_model.pkl")
        joblib.dump(m_pod, models_dir / "stage_podium_model.pkl")
        joblib.dump(m_rank, models_dir / "stage_ranker_model.pkl")
        joblib.dump(m_gc, models_dir / "gc_position_model.pkl")
        joblib.dump(m_gcp, models_dir / "gc_podium_model.pkl")
        # --predict (possibly a separate invocation) reads this to know which
        # model supplies predicted_rank; the CV numbers make the file auditable
        (models_dir / "model_selection.json").write_text(json.dumps({
            "stage_rank_source": rank_source,
            "classifier_cv": {k: round(v, 4) for k, v in winner_metrics.items()},
            "ranker_cv": {k: round(v, 4) for k, v in ranker_metrics.items()},
        }, indent=2))

        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        perf = pd.DataFrame([
            {"model_name": "Stage winner", "algorithm": "GradientBoostingClassifier",
             "target": "P(rider wins stage)",
             "top1_rate": round(winner_metrics["cv_top1_rate"], 3),
             "top3_rate": round(winner_metrics["cv_top3_rate"], 3),
             "auc": round(winner_metrics["cv_auc"], 3),
             "log_loss": round(winner_metrics["cv_log_loss"], 4),
             "mae_places": None, "baseline_mae_places": None, "r2": None,
             "n_train": int(len(matrix)),
             "provides_stage_ranking": not use_ranker,
             "headline": f"picks the actual winner {winner_metrics['cv_top1_rate']:.0%} of stages; winner in model top-3 {winner_metrics['cv_top3_rate']:.0%}"},
            {"model_name": "Stage podium", "algorithm": "GradientBoostingClassifier",
             "target": "P(rider finishes top 3)",
             "top1_rate": round(podium_metrics["cv_top1_rate"], 3),
             "top3_rate": round(podium_metrics["cv_top3_rate"], 3),
             "auc": round(podium_metrics["cv_auc"], 3),
             "log_loss": round(podium_metrics["cv_log_loss"], 4),
             "mae_places": None, "baseline_mae_places": None, "r2": None,
             "n_train": int(len(matrix)),
             "provides_stage_ranking": False,
             "headline": f"AUC {podium_metrics['cv_auc']:.2f} ranking top-3 finishers"},
            {"model_name": "Stage ranker", "algorithm": "XGBRanker (LambdaMART)",
             "target": "per-stage ordering (graded win/podium/top-10)",
             "top1_rate": round(ranker_metrics["cv_top1_rate"], 3),
             "top3_rate": round(ranker_metrics["cv_top3_rate"], 3),
             "auc": round(ranker_metrics["cv_auc"], 3),
             "log_loss": None,
             "mae_places": None, "baseline_mae_places": None, "r2": None,
             "n_train": int(len(matrix)),
             "provides_stage_ranking": use_ranker,
             "headline": (
                 f"ordinal-aware challenger: top-1 {ranker_metrics['cv_top1_rate']:.0%} "
                 f"vs classifier {winner_metrics['cv_top1_rate']:.0%} — "
                 + ("supplies the published stage ranking"
                    if use_ranker else
                    "classifier keeps the published ranking"))},
            {"model_name": "Final GC position", "provides_stage_ranking": False, "algorithm": "GradientBoostingRegressor",
             "target": "final GC position of top-10 after stage 8",
             "top1_rate": None, "top3_rate": None,
             "auc": None, "log_loss": None,
             "mae_places": round(gc_reg_metrics["cv_mae_places"], 2),
             "baseline_mae_places": round(gc_reg_metrics["baseline_mae_places"], 2),
             "r2": round(gc_reg_metrics["cv_r2"], 3),
             "n_train": int(gc_reg_metrics["n_rows"]),
             "headline": f"average error {gc_reg_metrics['cv_mae_places']:.1f} places "
                         f"(baseline: standings freeze at {gc_reg_metrics['baseline_mae_places']:.1f})"},
            {"model_name": "GC podium", "provides_stage_ranking": False, "algorithm": "RandomForestClassifier",
             "target": "P(final GC podium)",
             "top1_rate": None, "top3_rate": None,
             "auc": round(gc_cls_metrics["cv_auc"], 3),
             "log_loss": round(gc_cls_metrics["cv_log_loss"], 4),
             "mae_places": None, "baseline_mae_places": None, "r2": None,
             "n_train": int(gc_cls_metrics["n_rows"]),
             "headline": f"AUC {gc_cls_metrics['cv_auc']:.2f} identifying final podium riders"},
            {"model_name": "Jersey projections", "provides_stage_ranking": False, "algorithm": "Expected-points simulation",
             "target": "green/polka-dot points at Paris",
             "top1_rate": None, "top3_rate": None, "auc": None, "log_loss": None,
             "mae_places": None, "baseline_mae_places": None, "r2": None,
             "n_train": None,
             "headline": "current points + expected finish points from the two stage models"},
        ])
        perf["cv_scheme"] = "leave-one-year-out CV, 2020-2025"
        perf["trained_at"] = now
        perf.to_parquet(data_dir / "model_performance.parquet", index=False)
        print("  model_performance.parquet written")

    if args.predict:
        print("Generating 2026 predictions...")
        predict_2026(data, models_dir, out_dir, profiles)

    print("✓ Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
