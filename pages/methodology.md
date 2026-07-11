---
title: Methodology
subtitle: Where the data comes from and how the models work
description: >
  Data lineage, feature engineering, model design and honest cross-validated
  performance numbers for the TDF 2026 ML dashboard.
sidebar_position: 3
icon: "🧪"
header: true
---

# 🧪 Methodology

*Every number on this dashboard is either parsed from public race records or
produced by a model whose cross-validated accuracy is published below.*

---

## 📡 Data: real, and where it comes from

All race data is parsed from **Wikipedia's Tour de France articles**, which are
updated within hours of each stage finishing and cite the official timing
(letour.fr / Tissot) for every table. The fetch pipeline
(`scripts/fetch_tdf_data.py`) parses the underlying wikitext templates —
`{{Cyclingresult}}` blocks, stage characteristics tables, classification
tables and the startlist — rather than scraping rendered HTML, which makes it
fast and robust.

| Dataset | Contents |
|---------|----------|
| `live/` | 2026 route, stage results, GC after every stage, all four classifications, the full 184-rider startlist with DNS/DNF status |
| `historical/` | 2020-2025: top-10 of all 126 stages, GC after every stage, final classifications (~2,500 rows) |
| `predictions/` | model outputs for every remaining 2026 stage, the final GC and jersey projections — regenerated daily |

Why not the sources this project originally named? `cqranking.com` exposes no
public JSON API and `procyclingstats.com` blocks automated clients (HTTP 403).
Wikipedia is reliable, licensed CC BY-SA, and independently cites official
timing.

The pipeline **validates before writing**: 21 stages per year or it fails,
unknown stage types fail loudly, and stage distances are cross-checked against
the official race total (that check caught a real typo — the route table
listed stage 9 as 155.5 km where letour.fr says 185.5 km).

```sql data_freshness connector=main
SELECT source, url, last_fetched, license FROM data_freshness
```

<Table data={data_freshness} title="Sources & freshness" />

---

## 🤖 The models

Four scikit-learn models plus one simulation, all trained by
`scripts/train_predictions.py` on the 2020-2025 results. Features are built
**only from information available before the stage being predicted** — a
rider's career record in previous Tours and their form in the current Tour up
to that morning. No leakage.

```sql model_performance connector=main
SELECT model_name, algorithm, target,
       ROUND(top1_rate * 100, 1) AS top1_pct,
       ROUND(top3_rate * 100, 1) AS top3_pct,
       auc, mae_places, baseline_mae_places, n_train
FROM model_performance
```

<Table data={model_performance}
       format="top1_pct=percent,top3_pct=percent"
       title="Leave-one-year-out cross-validation (scored on stages 9-21 of the held-out year)" />

### 1. Stage winner — `GradientBoostingClassifier`

One row per (rider × stage): **~10,600 training rows, 126 actual winners.**
Features:

- **Stage**: type (flat / hilly / mountain / ITT), distance, race progress
- **Career** (previous Tours in the dataset): stage wins, podiums, top-10s split by stage type, best final GC
- **Form** (this Tour, before the stage): wins, podiums, top-10s by type, current GC position
- **Interactions**: the rider's wins/podiums/top-10s *on this stage type* — the single strongest signal (sprinters win flat stages, climbers win mountains)

Raw probabilities are normalised per stage so exactly one winner's worth of
probability is distributed across the peloton.

### 2. Stage podium — same features, target = top-3

Feeds the jersey projections (a rider doesn't need to win to score points).

### 3. Final GC position — `GradientBoostingRegressor`

For riders in the GC top 10 after stage 8: predict their final position in
Paris. Features: current gap and position, what remains of the route
(mountain stages, ITT km), career GC pedigree and mountain form. Riders who
crashed out or faded from the top 10 are censored at rank 12.

**Honesty required**: its cross-validated error is
<Value data={gc_mae} column="mae_places" /> places versus
<Value data={gc_mae} column="baseline_mae_places" /> for simply freezing the
standings — with six Tours of history, the freeze baseline is genuinely hard
to beat. We show the model's ordering because it encodes *who typically
fades* (breakaway survivors) and *who climbs* (GC pedigree riders), but treat
the podium probabilities below as the more meaningful output.

```sql gc_mae connector=main
SELECT mae_places, baseline_mae_places FROM model_performance
WHERE model_name = 'Final GC position'
```

### 4. GC podium — `RandomForestClassifier`

Same inputs, binary target *finishes on the final podium*. Class-weight
balanced; this is the headline GC prediction on the dashboard.

### 5. Jersey projections — expected-points simulation

No black box: projected points = current points + expected finish points over
the remaining stages, where the expectation combines the two stage models with
the **real UCI points scales** (flat wins pay 50 green-jersey points, hilly
30, mountain/ITT 20; mountain-stage winners typically bag ~18 KOM points at
summit finishes). Intermediate-sprint and breakaway KOM points are *not*
modelled — the projection is a documented floor, not gospel.

---

## 🏷️ Rider "specialist" labels

The specialist tags (Sprinter, Climber, GC contender, Puncheur, Time
trialist, Stage hunter, Domestique) are **derived from the data**, not typed
in: each rider's top-10 finishes from 2020 through this morning are split by
stage type and a simple documented rule assigns the label (e.g. mostly flat
top-10s → Sprinter; GC top-10 plus repeated mountain top-10s → GC contender).
Riders with no top-10 in the dataset are labelled Domestique.

```sql specialist_mix connector=live_2026
SELECT specialist, COUNT(*) AS riders
FROM rider_profiles
GROUP BY specialist
ORDER BY riders DESC
```

<PieChart data={specialist_mix} x="specialist" y="riders" title="The 2026 peloton by derived specialty" />

---

## ⚠️ Limitations — read before betting

```sql winner_rate connector=main
SELECT ROUND(top1_rate * 100, 1) AS top1_pct
FROM model_performance WHERE model_name = 'Stage winner'
```

- **Breakaways**: many Tour stages are won from long-range breakaways that no
  rider-profile model predicts. That is why the honest top-1 hit rate is
  <Value data={winner_rate} column="top1_pct" format="percent" />, not 85%.
- **Six years of history** is a small sample for GC dynamics; the position
  regressor does not beat the standings-freeze baseline and the page says so.
- **Top-10 depth**: historical training data covers each stage's top 10, not
  the full finish order.
- **No exogenous factors**: crashes, illness, weather, team tactics and
  abandons (like Torstein Træen's exit while in yellow after stage 6) are
  unmodelled.
- **TTT excluded**: stage 1 was a team event; rider-level models skip it.

---

## 🔁 Reproduce it

```bash
pip install -r requirements.txt
python scripts/fetch_tdf_data.py --all --output data     # real data → parquet
python scripts/train_predictions.py --train --predict    # models + predictions
dashdown serve .                                         # this dashboard
```

Every model, metric and prediction on this site regenerates from those three
commands. During the race a GitHub Action runs them daily at 08:00 UTC.
