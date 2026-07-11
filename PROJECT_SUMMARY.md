# 🚴 TDF 2026 × ML — Project Summary

A Tour de France 2026 analytics dashboard built with
[Dashdown](https://github.com/DirendAI/dashdown), running on **real data**.

## What it does

- Parses live 2026 race data and 2020-2025 historical results from
  Wikipedia's structured wikitext (which cites official letour.fr / Tissot
  timing) into Parquet files.
- Trains four scikit-learn models (stage winner, stage podium, final GC
  position, GC podium) plus an expected-points jersey simulation, using only
  leak-free features derived from the results themselves.
- Publishes honest leave-one-year-out cross-validation metrics next to every
  prediction — including where the model fails to beat a naive baseline.
- Renders it all as an interactive dashboard: main page, methodology page,
  and 21 per-stage detail pages.

## Layout

| Path | Purpose |
|------|---------|
| `pages/index.md` | Main dashboard (standings, predictions, projections, history) |
| `pages/methodology.md` | Data lineage, model design, honest metrics, limitations |
| `pages/stages/[stage].md` | Per-stage result / prediction detail pages |
| `scripts/fetch_tdf_data.py` | Wikipedia wikitext → Parquet (validating parser) |
| `scripts/train_predictions.py` | Train, cross-validate, predict |
| `data/` | Committed Parquet data (live / historical / predictions) |
| `.github/workflows/` | Daily refresh during the race + deploy to Cloudflare Pages |

## Daily loop during the race

```
fetch_tdf_data.py --all        # latest results from Wikipedia
train_predictions.py --train --predict
git commit data/ && deploy     # GitHub Action, 08:00 UTC
```

See [README.md](README.md) for setup and [scripts/README.md](scripts/README.md)
for pipeline details.
