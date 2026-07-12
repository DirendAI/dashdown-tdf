# Data Pipeline

Two scripts turn public race data into the Parquet files the dashboard queries.

| Script | Purpose | Usage |
|--------|---------|-------|
| `fetch_tdf_data.py` | Fetch real TDF data (2026 live + 2020-2025 historical) | `python scripts/fetch_tdf_data.py --all --output data` |
| `train_predictions.py` | Train ML models, publish honest CV metrics, generate 2026 predictions | `python scripts/train_predictions.py --train --predict` |

## Data source

Both live and historical data are parsed from **Wikipedia wikitext** — the
Tour de France articles are updated within hours of each stage finish and
carry structured templates that are reliable to parse:

- `{{Cyclingresult}}` blocks → top-10 of every stage + GC after every stage
- *Stage characteristics* tables → route, dates, distances, stage types, winners
- Classification tables → GC / points / mountains / young rider / team standings
- The startlist article → all 184 riders with team, nationality, birth date, DNS/DNF status
- The `{{UCI team code}}` template is resolved to display names through the
  MediaWiki `expandtemplates` API

Wikipedia in turn cites the official timing (letour.fr / Tissot). The fetch
script cross-checks stage distances against the official race total and the
per-stage articles, and fails loudly on unknown stage types or suspicious row
counts rather than writing bad data.

Why not the sources the project originally named? `cqranking.com` has no
public JSON API, and `procyclingstats.com` returns HTTP 403 to scrapers.

## Outputs

```
data/
├── race_overview.parquet        # one-row summary (jerseys, stage count, ...)
├── model_performance.parquet    # honest leave-one-year-out CV metrics
├── data_freshness.parquet       # per-source refresh audit
├── metadata.json
├── live/                        # 2026: stages, stage_results, gc_standings,
│                                # gc_evolution, classifications, riders,
│                                # teams, rider_profiles
├── historical/                  # 2020-2025: results, stages,
│                                # final_classifications
└── predictions/                 # stage_predictions, gc_forecast,
                                 # jersey_projections
models/                          # trained models + model_selection.json (gitignored)
```

## The models

Trained on 2020-2025 (6 Tours, ~2,500 real result rows), features are built
only from information available *before* the stage being predicted (no
leakage). Evaluation is leave-one-year-out CV scored on stages 9-21 — the
regime the deployed model actually runs in (predicting the rest of the race
with a week of form data).

1. **Stage winner** — GradientBoostingClassifier over (rider × stage) rows.
   Features: stage type/distance, rider career + current-tour form, and
   explicit rider-x-stage-type interaction counts.
2. **Stage podium** — same features, P(top-3 on the stage).
3. **Stage ranker** — XGBRanker (LambdaMART) over the same features and tree
   budget, trained on graded finish positions (win › podium › top-10 › rest)
   with one ranking group per stage, so it learns the ordinal structure the
   binary targets discard. It competes with the stage-winner classifier in
   the same CV; whichever ranks held-out years better (top-1, then top-3 hit
   rate) supplies `predicted_rank` — the choice is written to
   `models/model_selection.json` and re-made on every retrain. Win/podium
   probabilities always come from the calibrated classifiers.
4. **Final GC position** — GradientBoostingRegressor for riders in the GC
   top 10 after stage 8. Also reports the "standings freeze" baseline —
   which is genuinely hard to beat with six years of data, and the dashboard
   says so.
5. **GC podium** — RandomForestClassifier, P(final podium).
6. **Jersey projections** — current green/polka-dot points plus expected
   podium points simulated from models 1-2 with the real UCI points scales,
   plus each rider's observed per-stage rate of the points those models
   can't see (intermediate sprints, finish places 4-15, breakaway KOM) —
   inferred as the residual between the rider's current total and their
   observed podium finishes, projected over the remaining stages.

Run `--train` to see the CV metrics; they are also published to the
dashboard's methodology page via `data/model_performance.parquet`.
