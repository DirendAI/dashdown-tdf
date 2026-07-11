# 🚧 TDF 2026 × ML - Dashboard Template

**Template for a Tour de France 2026 Dashboard with Machine Learning Predictions & AI Commentary**

[![CI](https://github.com/DirendAI/dashdown-tdf/actions/workflows/deploy.yml/badge.svg)](https://github.com/DirendAI/dashdown-tdf/actions/workflows/deploy.yml)
[![Dashdown](https://img.shields.io/badge/built%20with-Dashdown-000000.svg)](https://github.com/DirendAI/dashdown)
[![License](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue.svg)](LICENSE)

---

**⚠️ NOTE**: This is a **template/demo project** that demonstrates Dashdown's capabilities. 
**It does not currently have real live data.** To use it with real data, you need to:

1. Set up API access to data sources (CQ Ranking, ProCyclingStats, etc.)
2. Run `python scripts/fetch_tdf_data.py` to fetch real data
3. Configure the data connectors in `sources.yaml`

---

## 📋 What This Template Shows

This repository demonstrates how to build an **interactive analytics dashboard** for the Tour de France that would combine:

- **Live race data** - GC standings, stage results, rider info
- **ML-powered predictions** - Stage winners, GC contenders, jersey specialists  
- **AI-generated commentary** - Mistral-powered insights baked at build time
- **Historical analysis** - Compare current year to previous years
- **Interactive visualizations** - Charts, tables, and filters

All built with **[Dashdown](https://github.com/DirendAI/dashdown)** — a tool that turns Markdown + SQL into interactive dashboards.

---

## 🚀 Quick Start (With Real Data)

### Prerequisites

1. **API Access**: You need access to cycling data APIs:
   - [CQ Ranking API](https://cqranking.com/api/) (free, but check current endpoints)
   - [ProCyclingStats](https://www.procyclingstats.com) (may require permission)
   - [Cycling Archives](https://www.cyclingarchives.com)

2. **Update the fetch script**: The `scripts/fetch_tdf_data.py` script needs to be updated with current API endpoints.

### Setup

```bash
# Clone the repository
git clone https://github.com/DirendAI/dashdown-tdf.git
cd dashdown-tdf

# Install dependencies
pip install -r requirements.txt

# Fetch real data (after updating the script with working API endpoints)
python scripts/fetch_tdf_data.py --year 2026 --output data

# Or fetch historical data for testing
python scripts/fetch_tdf_data.py --historical --output data

# Run the dashboard locally
dashdown serve .
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## 📊 Dashboard Features (When Data is Available)

### Pages

- **Home** (`pages/index.md`) - Main dashboard with GC standings, predictions, and analysis
- **Methodology** (`pages/methodology.md`) - ML model explanations and performance metrics
- **Stage Details** (`pages/stages/_template.md`) - Template for individual stage pages

### Data Model

The dashboard expects data in Parquet format under `data/`:

```
data/
├── live/
│   ├── gc_standings.parquet      # Current GC standings
│   ├── stage_results.parquet     # Stage results
│   ├── riders.parquet            # Rider information
│   ├── teams.parquet             # Team information
│   └── stages.parquet            # Stage profiles
├── predictions/
│   ├── all_stage_predictions.parquet  # All predictions
│   └── stage_*.parquet           # Per-stage predictions
├── historical/
│   └── results.parquet          # Historical results (2020-2025)
└── metadata.json                # Data freshness info
```

### ML Models

The template includes placeholders for 5 ML models:
- Stage winner prediction (Random Forest)
- GC position prediction (Gradient Boosting)
- Time gap prediction (Random Forest)
- Points jersey contender prediction (Random Forest)
- Mountains jersey contender prediction (Random Forest)

---

## 🔧 Configuration

### Data Connectors (`sources.yaml`)

```yaml
default: main

main:
  type: parquet
  directory: data

live_2026:
  type: parquet
  directory: data/live

predictions:
  type: parquet
  directory: data/predictions

historical:
  type: parquet
  directory: data/historical
```

### Dashdown Config (`dashdown.yaml`)

```yaml
title: "TDF 2026 Analytics Dashboard"
description: "Live Tour de France 2026 dashboard with ML predictions"
agents: [mistral]

# Mistral API for AI commentary
llm:
  provider: mistral
  model: mistral-medium-latest
  api_key: ${MISTRAL_API_KEY}

palette:
  primary: '#FFD700'    # Yellow jersey
  secondary: '#00A651'  # Green jersey
  accent: '#EF3340'     # Red (Points jersey)
```

---

## 🤖 AI Commentary

The dashboard uses Mistral AI to generate insights. Set the API key:

```bash
export MISTRAL_API_KEY="your-api-key"
dashdown build . --out dist
```

Without an API key, `<Ask>` components will show placeholder messages.

---

## 📚 Project Structure

```
dashdown-tdf/
├── pages/                    # Dashboard pages (Markdown + SQL)
│   ├── index.md             # Main dashboard
│   ├── methodology.md       # ML methodology
│   └── stages/              # Stage detail pages
│       └── _template.md     # Stage template
├── scripts/                 # Data pipeline
│   ├── fetch_tdf_data.py    # Fetch real data (needs API updates)
│   ├── train_predictions.py # Train ML models
│   └── generate_sample_data.py # Generate test data
├── data/                    # Data files (Parquet)
├── dashdown.yaml            # Dashdown configuration
├── sources.yaml             # Data source configuration
└── .vibe/                   # Mistral/Vibe agent support
```

---

## 🎯 Next Steps to Make This Real

1. **Update `scripts/fetch_tdf_data.py`** with current API endpoints
2. **Get API keys/access** for cycling data sources
3. **Run the fetch script** to populate `data/` with real data
4. **Train the ML models** with historical data
5. **Generate predictions** for the current race
6. **Deploy** to GitHub Pages or your own hosting

---

## 📄 License

AGPL-3.0-or-later — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- [Dashdown](https://github.com/DirendAI/dashdown) - The framework
- [CQ Ranking](https://cqranking.com) - Primary data source (API needs updating)
- [Mistral AI](https://mistral.ai) - AI commentary
- [scikit-learn](https://scikit-learn.org) - ML library
