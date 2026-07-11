# AGENTS.md — Tour de France 2026 Dashboard

> **Tool-agnostic guide for coding agents working on this project.**
> Read this first. Then follow links to topic-specific references as needed.

---

## 🎯 Project Overview

**dashdown-tdf** is an interactive analytics dashboard for the **2026 Tour de France** with:

- **Live data**: Daily updates during the race (July 5-27, 2026)
- **ML predictions**: Stage winners, GC contenders, jersey specialists
- **AI commentary**: Mistral-powered insights baked at build time
- **Historical analysis**: Compare 2026 to 2020-2025

Built with **[Dashdown](https://github.com/DirendAI/dashdown)** — Markdown + SQL → interactive dashboards.

---

## 🚀 Quick Start

### Local Development

```bash
# Clone and setup
git clone https://github.com/DirendAI/dashdown-tdf.git
cd dashdown-tdf

# Install dependencies
pip install -r requirements.txt

# Fetch data and generate predictions
python scripts/fetch_tdf_data.py --all --output data
python scripts/train_predictions.py --train
python scripts/train_predictions.py --predict-all

# Run the dev server
dashdown serve .
# → http://localhost:8000
```

### Build for Production

```bash
# Set Mistral API key for AI commentary
MISTRAL_API_KEY=your_key dashdown build . --out dist

# Or without AI (Ask cards show muted notices)
dashdown build . --out dist
```

---

## 📁 Project Structure

```
dashdown-tdf/
├── pages/                    # Dashboard pages (Markdown + SQL)
│   ├── index.md             # Main dashboard with overview, predictions, analysis
│   ├── methodology.md        # ML methodology explanation
│   └── stages/              # Per-stage detail pages (template-based)
│       └── _template.md     # Template for stage-specific pages
│
├── data/                    # Data files (Parquet format)
│   ├── historical/          # 2020-2025 historical results
│   │   └── results.parquet
│   ├── live/                # 2026 live data (refreshed daily)
│   │   ├── gc_standings.parquet
│   │   ├── stage_results.parquet
│   │   ├── riders.parquet
│   │   ├── teams.parquet
│   │   └── stages.parquet
│   └── predictions/         # ML-generated predictions
│       ├── all_stage_predictions.parquet
│       ├── stage_1_predictions.parquet
│       └── ...
│
├── models/                  # Trained ML models (joblib format)
│   ├── stage_winner_model.pkl
│   ├── gc_position_model.pkl
│   └── ...
│
├── scripts/                 # Data pipeline and ML scripts
│   ├── fetch_tdf_data.py    # Fetch data from APIs
│   ├── train_predictions.py # Train ML models and generate predictions
│   └── README.md           # Scripts documentation
│
├── .github/workflows/      # GitHub Actions workflows
│   ├── daily-refresh.yml    # Daily data refresh + predictions (08:00 UTC)
│   └── deploy.yml          # Build and deploy dashboard
│
├── dashdown.yaml           # Dashdown configuration
├── sources.yaml            # Data source configuration
├── requirements.txt         # Python dependencies
└── AGENTS.md               # This file
```

---

## 🎨 Dashboard Architecture

### Pages

| Page | Purpose | Key Components |
|------|---------|----------------|
| `index.md` | Main dashboard | GC standings, stage predictions, historical comparison, rider analysis |
| `methodology.md` | ML explanation | Model performance, feature importance, data sources, limitations |
| `stages/_template.md` | Stage detail | Stage profile, predictions, historical comparison |

### Data Flow

```
APIs (CQ Ranking, ProCyclingStats, Cycling Archives)
    ↓
scripts/fetch_tdf_data.py
    ↓
data/live/*.parquet
    ↓
scripts/train_predictions.py
    ↓
data/predictions/*.parquet + models/*.pkl
    ↓
Dashdown SQL queries (in .md files)
    ↓
Interactive dashboard
```

---

## 📊 Data Model

### Core Tables

| Table | Source | Grain | Key Columns |
|-------|--------|-------|--------------|
| `live_2026/gc_standings` | API | 1 row per rider | position, rider, team, time, gap, age, nationality |
| `live_2026/stage_results` | API | 1 row per rider-stage | stage, position, rider, team, time, gap |
| `live_2026/riders` | API | 1 row per rider | rider_id, name, team, nationality, age, height, weight, specialist |
| `live_2026/teams` | API | 1 row per team | team_id, name, country, budget |
| `live_2026/stages` | API | 1 row per stage | stage, date, start/end_location, distance, elevation, stage_type, climbs |
| `historical/results` | API | 1 row per rider-stage (2020-2025) | year, stage, position, rider, team, time, gap |
| `predictions/all_stage_predictions` | ML | 1 row per rider-stage | stage, rider, win_probability, predicted_gc_position, time_gap |
| `predictions/stage_N_predictions` | ML | 1 row per rider | rider, team, win_probability, predicted_gc_position, ... |

### Key Metrics

- **win_probability**: ML-predicted probability of winning the stage (0-1)
- **predicted_gc_position**: ML-predicted overall GC position (1-N)
- **predicted_time_gap_seconds**: ML-predicted time gap to stage winner
- **is_points_contender**: Binary flag for green jersey contenders
- **is_mountains_contender**: Binary flag for polka dot jersey contenders

---

## 🤖 ML Models

### Model Types

| Model | Type | Target | Algorithm | Use Case |
|-------|------|--------|-----------|----------|
| `stage_winner` | Classification | won_stage (0/1) | RandomForest | Predict stage winners |
| `gc_position` | Regression | gc_position (1-N) | GradientBoosting | Predict overall GC |
| `time_gap` | Regression | time_gap_seconds | RandomForest | Predict time differences |
| `points_jersey` | Classification | is_points_contender (0/1) | RandomForest | Predict green jersey contenders |
| `mountains_jersey` | Classification | is_mountains_contender (0/1) | RandomForest | Predict KOM jersey contenders |

### Feature Categories

**Rider Features (15+):**
- Physical: age, height_m, weight_kg, bmi
- Performance: uci_points, 2026_wins, grand_tour_wins
- Type: specialist (Sprinter, Climber, Puncheur, All-Rounder, Time Trialist)

**Stage Features (7+):**
- Profile: distance_km, elevation_m, stage_type
- Climbs: num_climbs_hc, num_climbs_cat1, num_climbs_cat2
- Flags: is_mountain_stage, is_tt

**Team Features (1+):**
- Resources: team_budget_million

---

## 🔧 Common Tasks

### Adding a New Page

1. Create a new `.md` file in `pages/`
2. Add frontmatter with title and description
3. Write SQL queries with ```sql blocks
4. Add Dashdown components: `<Counter>`, `<BarChart>`, `<Table>`, `<Ask>`, etc.
5. Reference data: `data={query_name}` where `query_name` matches the SQL block label

Example:
```markdown
---
title: New Analysis
---

# My Analysis

```sql my_data connector=main
SELECT * FROM live_2026/gc_standings LIMIT 10
```

<BarChart data={my_data} x="rider" y="gap" title="GC Gaps" />
```

### Adding a New Data Source

1. Add connector configuration to `sources.yaml`
2. Create a script in `scripts/` to fetch/transform the data
3. Save output to `data/` as Parquet files
4. Reference in SQL queries using the connector name

### Adding a New ML Model

1. Add model definition to `scripts/train_predictions.py`
2. Add feature engineering for the new target variable
3. Train and save the model in `models/`
4. Generate predictions and save to `data/predictions/`
5. Add visualization to a dashboard page

### Updating Data Daily

The `daily-refresh.yml` workflow:
- Runs at 08:00 UTC during TDF (July 5-27, 2026)
- Fetches latest 2026 data
- Regenerates all predictions
- Commits changes to `data/`
- Triggers dashboard rebuild and deploy

To manually trigger:
```bash
# On GitHub: Actions → Daily TDF Data Refresh → Run workflow
# Or via CLI:
gh workflow run daily-refresh.yml
```

---

## 📝 Dashdown Component Reference

### Charts

| Component | Purpose | Key Props |
|-----------|---------|-----------|
| `<LineChart>` | Time series, trends | x, y, title, series |
| `<BarChart>` | Categorical comparison | x, y, title, color, series |
| `<PieChart>` | Proportions | x, y, title |
| `<ScatterChart>` | Correlation | x, y, title, color, size |
| `<HeatmapChart>` | Matrix visualization | x, y, value, title |
| `<GaugeChart>` | Single metric | column, min, max, title |

### Tables & Counters

| Component | Purpose | Key Props |
|-----------|---------|-----------|
| `<Table>` | Tabular data | columns, sortBy, sortOrder, pageSize |
| `<Counter>` | Big number | column, label, format, suffix |
| `<Value>` | Inline value | column, label, format, index |

### AI & Special

| Component | Purpose | Key Props |
|-----------|---------|-----------|
| `<Ask>` | LLM commentary | data, ask, inline, lazy |
| `explain` | Chart explanation | (attribute on chart components) |

### Layout

| Component | Purpose | Key Props |
|-----------|---------|-----------|
| `<Grid>` | Multi-column layout | cols, gap |
| `<Tabs>` | Tabbed interface | labels, active |

---

## 🎨 Styling & Formatting

### Colors

TDF-themed palette defined in `dashdown.yaml`:
- `#FFD700` — Yellow (Maillot Jaune)
- `#00A651` — Green (Points Jersey)
- `#EF3340` — Red (Polka Dot Jersey)
- `#FFFFFF` — White (Best Young Rider)
- `#0052A5` — Blue
- `#8B4513` — Brown

Use `color="team"` to color charts by team.

### Number Formatting

```markdown
<Counter format="number" />        <!-- 1234 -->
<Counter format="compact" />       <!-- 1.2K -->
<Counter format="currency" />      <!-- €1,234 -->
<Counter format="percent" />       <!-- 45.6% -->
<Counter format="date" />         <!-- Jul 5, 2026 -->
<Counter format="datetime" />      <!-- Jul 5, 2026 08:00 -->
```

---

## 🔍 Querying Data

### SQL Syntax

Dashdown uses **DuckDB SQL** with some extensions:

```sql
-- Basic query
SELECT rider, team, win_probability 
FROM predictions/all_stage_predictions 
WHERE stage = 15 
ORDER BY win_probability DESC
LIMIT 10

-- Aggregation
SELECT 
    specialist,
    COUNT(*) as num_riders,
    AVG(win_probability) as avg_prob
FROM predictions/all_stage_predictions
GROUP BY specialist
ORDER BY avg_prob DESC

-- Filtering
SELECT * 
FROM live_2026/stages 
WHERE stage_type = 'Mountain' 
  AND elevation_m > 3000

-- Date functions
SELECT * 
FROM live_2026/stages 
WHERE date >= current_date()
```

### Parameterized Queries

Use `${param}` syntax for dynamic values:

```sql
SELECT * FROM predictions/stage_${stage}_predictions
```

In page templates, use `{{variable}}` syntax (Dashdown templating).

---

## 🧪 Testing & Validation

### Verify Build

```bash
# Check all pages render
dashdown check

# Verify SQL queries
dashdown query "SELECT COUNT(*) FROM live_2026/gc_standings"

# Take screenshot to verify charts draw
dashdown screenshot / --full-page -o test.png
```

### Verify Data

```bash
# Check Parquet files
python -c "import pandas as pd; print(pd.read_parquet('data/live/gc_standings.parquet').head())"

# Query with DuckDB
python -c "import duckdb; print(duckdb.sql('SELECT COUNT(*) FROM \"data/live/*.parquet\"').fetchall())"
```

---

## 🚀 Deployment

### GitHub Pages

The dashboard auto-deploys to GitHub Pages:
- **Trigger**: Push to main, or daily refresh workflow
- **URL**: `https://direndai.github.io/dashdown-tdf/`
- **Workflow**: `.github/workflows/deploy.yml`

### Manual Deploy

```bash
# Build locally
MISTRAL_API_KEY=your_key dashdown build . --out dist

# Or via GitHub Actions
gh workflow run deploy.yml
```

---

## 📚 References

### Dashdown Documentation

- [Official Docs](https://direndai.github.io/dashdown/)
- [Components Reference](https://direndai.github.io/dashdown/pages/components/)
- [SQL Reference](https://duckdb.org/docs/sql/introduction)

### Project-Specific

- [Methodology](/pages/methodology.md) — How the ML models work
- [Data Pipeline](scripts/README.md) — Data collection and processing
- [ML Models](scripts/train_predictions.py) — Prediction logic

### External Resources

- [CQ Ranking API](https://cqranking.com/api/) — Primary data source
- [ProCyclingStats](https://www.procyclingstats.com) — Race data
- [Cycling Archives](https://www.cyclingarchives.com) — Historical results
- [UCI](https://www.uci.org) — Rider/team information
- [Tour de France Official](https://www.letour.fr) — Route and stage details

---

## ❓ FAQ

**Q: How do I add a new chart?**
A: Add a SQL query block, then reference it in a component: `<BarChart data={my_query} x="col1" y="col2" />`

**Q: How do I use the ML models?**
A: Models are pre-trained. Use `scripts/train_predictions.py --predict-all` to generate predictions.

**Q: How do I add AI commentary?**
A: Add `<Ask data={query} ask="Your question here" />` to any page. Requires `MISTRAL_API_KEY`.

**Q: Why are predictions only updated daily?**
A: To balance freshness with stability. The TDF moves fast, but daily updates capture the key changes.

**Q: Can I run this without Mistral API key?**
A: Yes! The dashboard builds without it — `<Ask>` components just show muted notices instead of answers.

**Q: How do I test locally?**
A: Run `dashdown serve .` and open `http://localhost:8000`. No API key needed for local testing.

---

## 🎯 Best Practices

1. **Small commits**: Each change should be focused and reviewable
2. **Test locally**: Always run `dashdown check` before committing
3. **Document queries**: Add comments to complex SQL
4. **Use semantic names**: `gc_standings`, not `q1` or `data`
5. **Keep data small**: Commit only aggregates, not raw data
6. **Validate predictions**: Check model outputs make sense
7. **Update references**: If you add new patterns, update this file

---

*Last updated: 2026-07-11*
*Maintainer: Dirend AI*
