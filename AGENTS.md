# AGENTS.md — Tour de France 2026 Dashboard

> **Tool-agnostic guide for coding agents working on this project.**
> Read this first. Then follow links to topic-specific references as needed.

---

## 🎯 Project Overview

**dashdown-tdf** is an interactive analytics dashboard for the **2026 Tour de France** with:

- **Live data**: Daily updates during the race (July 4-26, 2026)
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
python scripts/train_predictions.py --train --predict

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
│   ├── methodology.md        # Data lineage, models, honest CV metrics
│   └── stages/              # Per-stage detail pages (dynamic route)
│       └── [stage].md       # /stages/1 … /stages/21 (static_paths export)
│
├── data/                    # Data files (Parquet format, committed)
│   ├── race_overview.parquet     # one-row race state (main connector)
│   ├── model_performance.parquet # honest CV metrics (main connector)
│   ├── data_freshness.parquet    # source audit (main connector)
│   ├── historical/          # 2020-2025: results, stages, final_classifications
│   ├── live/                # 2026: stages, stage_results, gc_standings,
│   │                        # gc_evolution, classifications, riders, teams,
│   │                        # rider_profiles (refreshed daily)
│   └── predictions/         # stage_predictions, gc_forecast, jersey_projections
│
├── models/                  # Trained ML models (joblib, gitignored)
│
├── scripts/                 # Data pipeline and ML scripts
│   ├── fetch_tdf_data.py    # Parse Wikipedia wikitext → parquet
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
| `index.md` | Main dashboard | GC standings, stage predictions, jersey projections, historical context |
| `methodology.md` | ML explanation | Model performance (honest CV), data lineage, limitations |
| `stages/[stage].md` | Stage detail | Result (if raced), GC after the stage, model prediction |

### Data Flow

```
Wikipedia wikitext (cites letour.fr / Tissot timing)
    ↓
scripts/fetch_tdf_data.py        # {{Cyclingresult}} blocks, stage tables,
    ↓                            # classifications, startlist → parquet
data/live/ + data/historical/ + data/race_overview.parquet
    ↓
scripts/train_predictions.py     # LOYO-CV metrics + trained models
    ↓
data/predictions/*.parquet + data/model_performance.parquet + models/*.pkl
    ↓
Dashdown SQL queries (in .md files)
    ↓
Interactive dashboard
```

---

## 📊 Data Model

### Core Tables

Connector in parentheses; table name = parquet file stem.

| Table (connector) | Grain | Key Columns |
|-------------------|-------|--------------|
| `gc_standings` (live_2026) | 1 row per GC top-10 rider | position, rider, team, nationality, age, time, gap, gap_minutes, gap_seconds |
| `gc_evolution` (live_2026) | GC top-10 after every completed stage | stage, position, rider, team, gap_seconds |
| `stage_results` (live_2026) | top-10 per completed stage | stage, position, rider, team, time_raw, gap_seconds, stage_type, distance_km |
| `stages` (live_2026) | 1 row per stage (all 21) | stage, date, start/end_location, distance_km, stage_type, winner, completed, climbs_* |
| `classifications` (live_2026) | top-10 of points/mountains/young rider/team | classification, rank, rider, team, points, value |
| `riders` (live_2026) | full startlist | number, rider, team, country, age, birth_date, status (active/DNS-n/DNF-n) |
| `rider_profiles` (live_2026) | 1 row per rider | specialist (derived), career_stage_wins, top10_flat/hilly/mountain/individual |
| `results` (historical) | stage top-10s + GC-after-stage, 2020-2025 | year, stage, record ('stage_result'/'gc_after_stage'), position, rider, team, stage_type |
| `final_classifications` (historical) | final top-10s per year | year, classification, rank, rider, team, points/gap_seconds |
| `stage_predictions` (predictions) | 1 row per (remaining stage × active rider) | stage, rider, team, specialist, win_probability, podium_probability, predicted_rank |
| `gc_forecast` (predictions) | current GC top 10 | rider, current_position, current_gap, predicted_final_position, podium_probability |
| `jersey_projections` (predictions) | top-30 per jersey | classification, rider, current_points, projected_podium_points, projected_other_points, projected_additional_points, projected_total_points, projected_rank |
| `race_overview` / `model_performance` / `data_freshness` (main) | one-row/state tables | see files |

### Key Metrics

- **win_probability**: normalised per stage so each stage's probabilities sum to 1
- **podium_probability**: P(top-3 on the stage) — raw classifier output
- **predicted_rank**: per-stage ordering from whichever of ranker/classifier
  won the CV duel (currently the ranker) — can disagree with win_probability
- **predicted_final_position**: rank of the GC position regressor's scores
- **projected_total_points**: current jersey points + expected podium points
  (stage models) + the rider's observed rate of intermediate-sprint /
  minor-placing / breakaway points (the part of their current total the
  observed podiums can't explain, projected forward)

---

## 🤖 ML Models

### Model Types

| Model | Type | Target | Algorithm |
|-------|------|--------|-----------|
| `stage_winner` | Classification | won_stage (0/1) | GradientBoosting |
| `stage_podium` | Classification | top3_stage (0/1) | GradientBoosting |
| `stage_ranker` | Learning-to-rank | graded finish position per stage group | XGBRanker (LambdaMART) |
| `gc_position` | Regression | final GC rank of top-10-after-8 | GradientBoosting |
| `gc_podium` | Classification | final podium (0/1) | RandomForest |
| jersey projections | Simulation | expected points | models 1+2 × UCI points scales |

The stage ranker and stage-winner classifier compete in the same LOYO CV;
the better ranker of held-out years (top-1, then top-3 hit rate) supplies
`predicted_rank` (recorded in `models/model_selection.json`, re-decided every
retrain). Probabilities always come from the calibrated classifiers.

Honest leave-one-year-out CV metrics live in `data/model_performance.parquet`
and are shown on the dashboard — do not replace them with aspirational numbers.

### Feature Categories

All features derive from the results data itself (no hand-typed rider stats):

**Career (previous Tours in dataset):** wins, podiums, top-10s by stage type,
best final GC, plus same-type interaction counts.

**Form (current Tour, before the predicted stage):** wins, podiums, top-10s by
type, current GC position, same-type interaction counts.

**Stage:** type one-hots, distance_km, race progress.

**GC models:** current gap/position, remaining mountain stages & ITT km,
career GC pedigree, mountain form so far.

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

```sql my_data connector=live_2026
SELECT * FROM gc_standings LIMIT 10
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

Dashdown uses **DuckDB SQL**. The connector is chosen in the query's info
string (` ```sql name connector=predictions `), and each parquet file in that
connector's directory is a table named after the file stem:

````markdown
```sql stage15_favorites connector=predictions
SELECT rider, team, win_probability
FROM stage_predictions
WHERE stage = 15
ORDER BY win_probability DESC
LIMIT 10
```
````

```sql
-- Aggregation (connector=predictions)
SELECT specialist,
       COUNT(*) AS num_riders,
       AVG(win_probability) AS avg_prob
FROM stage_predictions
GROUP BY specialist
ORDER BY avg_prob DESC

-- Filtering (connector=live_2026)
SELECT *
FROM stages
WHERE stage_type = 'Mountain' AND completed
```

Cross-connector joins are not possible — each connector is its own DuckDB.
The prediction parquets are denormalised (they carry team/specialist/age) for
exactly this reason.

### Parameterized Queries

Route params from dynamic pages (`pages/stages/[stage].md`) reach SQL as
`${stage}`. Values are substituted as quoted string literals (injection-safe),
so cast explicitly for numeric comparisons:

```sql
SELECT * FROM stage_predictions
WHERE stage = CAST('${stage}' AS INTEGER)
```

Page **prose is not templated** — to show a value in a sentence, use
`<Value data={query} column="col" />`, never `{{...}}` placeholders.

**Never put `<Ask>` on a `[param]` page.** Static builds bake ONE answer per
ask id for the whole template (generated with the first static path's data),
so all 21 stage pages would show the same — wrong — commentary. Ask belongs
on regular pages only.

---

## 🧪 Testing & Validation

### Verify Build

```bash
# Check all pages render
dashdown check

# Verify SQL queries
dashdown query "SELECT COUNT(*) FROM gc_standings" --connector live_2026

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

### Cloudflare Pages

The dashboard auto-deploys to Cloudflare Pages:
- **Trigger**: Push to main, or daily refresh workflow
- **URL**: `https://dashdown-tdf.pages.dev`
- **Workflow**: `.github/workflows/deploy.yml` (wrangler `pages deploy dist`)
- **Secrets**: `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN` (Pages — Edit),
  optional `MISTRAL_API_KEY`

The site is served from the domain root, so keep links root-relative
(`/stages/9`) and do not reintroduce a sub-path prefix.

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

- [Wikipedia: 2026 Tour de France](https://en.wikipedia.org/wiki/2026_Tour_de_France) — primary data source (parsed wikitext)
- [Tour de France Official](https://www.letour.fr) — the timing Wikipedia cites
- [UCI](https://www.uci.org) — rider/team information

Note: `cqranking.com` has no public JSON API and `procyclingstats.com` blocks
automated clients (HTTP 403) — do not point the fetch script back at them.

---

## ❓ FAQ

**Q: How do I add a new chart?**
A: Add a SQL query block, then reference it in a component: `<BarChart data={my_query} x="col1" y="col2" />`

**Q: How do I use the ML models?**
A: Models are pre-trained. Run `python scripts/train_predictions.py --train --predict` to retrain and regenerate predictions.

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
