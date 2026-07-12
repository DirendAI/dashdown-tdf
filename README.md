# 🚴 TDF 2026 × ML — Live Dashboard

**Tour de France 2026 dashboard with real race data and machine-learning predictions**

[![CI](https://github.com/DirendAI/dashdown-tdf/actions/workflows/deploy.yml/badge.svg)](https://github.com/DirendAI/dashdown-tdf/actions/workflows/deploy.yml)
[![Dashdown](https://img.shields.io/badge/built%20with-Dashdown-000000.svg)](https://github.com/DirendAI/dashdown)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Real standings and results for the 2026 Tour (currently mid-race), historical
data for 2020-2025, and ML predictions for the remaining stages, the final GC
and the jersey competitions — all regenerated several times a day while the
race runs.

---

## 📊 What's on the dashboard

- **Live 2026 race state** — GC standings, stage results, all four jersey
  classifications, and how the GC race has evolved stage by stage
- **ML predictions** — win probability for every rider on every remaining
  stage, final-podium probabilities, green/polka-dot jersey projections
- **Per-stage pages** — `/stages/1` … `/stages/21`: official result for raced
  stages, model picks for upcoming ones
- **Historical context** — champions, stage-win counts and route composition
  for 2020-2025
- **Honest model scorecard** — leave-one-year-out cross-validation numbers,
  including where the model does *not* beat a naive baseline
- **AI commentary** (optional) — Mistral-generated read-outs baked at build
  time when `MISTRAL_API_KEY` is set

## 📡 Where the data comes from

Everything is parsed from **Wikipedia's Tour de France articles** (which cite
the official letour.fr / Tissot timing and are updated within hours of each
stage). The pipeline parses wikitext templates — results blocks, stage tables,
classification tables, the startlist — and validates before writing: row
counts, stage counts, unknown stage types, and stage distances cross-checked
against the official race total.

> Historical note: this project originally pointed at a "CQ Ranking API"
> (which doesn't exist publicly) and ProCyclingStats (which blocks scrapers,
> HTTP 403) — that's why the repo used to ship with no real data. The current
> pipeline has no API keys, no scraping arms-race, and real data.

## 🚀 Quick start

```bash
git clone https://github.com/DirendAI/dashdown-tdf.git
cd dashdown-tdf
pip install -r requirements.txt

# Refresh the data (parquet files are also committed, so this is optional)
python scripts/fetch_tdf_data.py --all --output data

# Retrain models + regenerate predictions
python scripts/train_predictions.py --train --predict

# Serve locally
dashdown serve .          # → http://localhost:8080
```

Build the static site (with optional AI commentary):

```bash
export MISTRAL_API_KEY=your_key   # optional — Ask cards degrade gracefully
dashdown build . --out dist
```

## 🗂️ Data model

```
data/
├── race_overview.parquet        # one-row race state (jerseys, progress, ...)
├── model_performance.parquet    # honest LOYO-CV metrics
├── data_freshness.parquet       # source audit
├── live/                        # 2026: stages, stage_results, gc_standings,
│                                #   gc_evolution, classifications, riders,
│                                #   teams, rider_profiles
├── historical/                  # 2020-2025: results (stage top-10s + GC
│                                #   evolution), stages, final_classifications
└── predictions/                 # stage_predictions, gc_forecast,
                                 #   jersey_projections
```

Connectors are defined in `sources.yaml` (`main`, `live_2026`, `historical`,
`predictions`) — each parquet file is a SQL table named after the file.

## 🤖 The ML

Trained on the 2020-2025 Tours (~2,500 real result rows), features built only
from information available before each predicted stage (career record +
current-tour form + rider-×-stage-type interactions). Evaluated with
**leave-one-year-out cross-validation scored on stages 9-21** — the same
regime the deployed model runs in. The honest numbers (winner top-1/top-3 hit
rate, AUC, GC MAE vs the standings-freeze baseline) are published on the
[methodology page](pages/methodology.md) and in
`data/model_performance.parquet`. Details in [scripts/README.md](scripts/README.md).

## 🔄 CI/CD

- **daily-refresh.yml** — at 08:00, 16:00, 18:00 and 20:00 UTC during the
  race: fetch → retrain → predict → commit → deploy (evening passes catch the
  day's result; no-change runs skip commit and deploy)
- **deploy.yml** — build & deploy to **Cloudflare Pages**
  (https://dashdown-tdf.pages.dev) on push to `main`, with quality gates
  (baked Ask answers, charts actually draw)

Repository secrets used by CI:

| Secret | Purpose |
|--------|---------|
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare account for Pages deploys |
| `CLOUDFLARE_API_TOKEN` | API token with the *Cloudflare Pages — Edit* permission |
| `MISTRAL_API_KEY` | Bakes AI commentary into the build (optional) |

## 📄 License

MIT — see [LICENSE](LICENSE).

## 🙏 Acknowledgments

- [Dashdown](https://github.com/DirendAI/dashdown) — the framework
- [Wikipedia](https://en.wikipedia.org/wiki/2026_Tour_de_France) & the
  cycling editors who keep it current (CC BY-SA 4.0)
- [ASO / letour.fr](https://www.letour.fr) — the underlying official timing
- [scikit-learn](https://scikit-learn.org) — ML
- [Mistral AI](https://mistral.ai) — commentary
