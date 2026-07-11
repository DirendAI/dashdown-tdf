# 🚴 TDF 2026 × ML

**Live Tour de France 2026 Dashboard with Machine Learning Predictions & AI Commentary**

[![CI](https://github.com/DirendAI/dashdown-tdf/actions/workflows/deploy.yml/badge.svg)](https://github.com/DirendAI/dashdown-tdf/actions/workflows/deploy.yml)
[![Daily Refresh](https://github.com/DirendAI/dashdown-tdf/actions/workflows/daily-refresh.yml/badge.svg)](https://github.com/DirendAI/dashdown-tdf/actions/workflows/daily-refresh.yml)
[![Dashdown](https://img.shields.io/badge/built%20with-Dashdown-000000.svg)](https://github.com/DirendAI/dashdown)
[![License](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue.svg)](LICENSE)

---

**📊 Live Dashboard**: [https://direndai.github.io/dashdown-tdf/](https://direndai.github.io/dashdown-tdf/)

*Updated daily at 08:00 UTC during the Tour de France (July 5-27, 2026)*

---

## 🎯 What This Is

An **interactive analytics dashboard** for the **2026 Tour de France** that combines:

- ✅ **Live race data** - GC standings, stage results, rider info (from REAL sources)
- ✅ **ML-powered predictions** - Stage winners, GC contenders, jersey specialists
- ✅ **AI-generated commentary** - Mistral-powered insights baked at build time
- ✅ **Historical analysis** - Compare 2026 to 2020-2025 (REAL data)
- ✅ **Interactive visualizations** - Charts, tables, and filters

All built with **[Dashdown](https://github.com/DirendAI/dashdown)** — a tool that turns Markdown + SQL into interactive dashboards.

---

## 🏆 Features

### 📊 Live Race Data (REAL SOURCES)
- **General Classification standings** with time gaps (from CQ Ranking API)
- **Stage-by-stage results** for all 21 stages (from CQ Ranking API)
- **Rider profiles** with age, nationality, team (from CQ Ranking API)
- **Team information** with country codes (from CQ Ranking API)
- **Stage profiles** with distance, type, date (from CQ Ranking API)

### 🤖 Machine Learning Predictions
- **Stage winner probabilities** for every stage
- **GC position predictions** for overall standings
- **Time gap estimates** between riders
- **Jersey contender identification** (Points & Mountains)
- **Specialist analysis** (Sprinters, Climbers, Puncheurs, etc.)

### ✨ AI-Powered Insights
- **Automated commentary** on race dynamics
- **Chart explanations** with annotated insights
- **Natural language analysis** of predictions

### 📈 Historical Comparison
- **2026 vs 2020-2025** performance trends
- **Year-over-year** improvements/declines
- **Career trajectory** analysis for top riders

### 🔄 Daily Updates
- **Automatic refresh** at 08:00 UTC during TDF
- **CI/CD pipeline** with quality gates
- **GitHub Pages deployment** for live dashboard

---

## 🚀 Quick Start

### Local Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/DirendAI/dashdown-tdf.git
   cd dashdown-tdf
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up Mistral API key (optional):**
   ```bash
   export MISTRAL_API_KEY="your-api-key"
   ```

4. **Run the dashboard locally:**
   ```bash
   dashdown serve .
   ```
   Open [http://localhost:8080](http://localhost:8080) in your browser.

### Production Build

```bash
# Build static site
dashdown build . --out dist

# Serve locally for testing
python -m http.server 8000 --directory dist
```

---

## 📁 Project Structure

```
dashdown-tdf/
├── .github/
│   └── workflows/
│       ├── daily-refresh.yml    # Daily data refresh during TDF
│       └── deploy.yml           # Build and deploy to GitHub Pages
├── assets/
│   └── favicon.svg             # TDF-themed favicon
├── data/
│   ├── historical/             # 2020-2025 historical data
│   │   └── results.parquet
│   ├── live/                   # 2026 live race data
│   │   ├── gc_standings.parquet
│   │   ├── riders.parquet
│   │   ├── stage_results.parquet
│   │   ├── stages.parquet
│   │   └── teams.parquet
│   ├── metadata.json           # Data freshness info
│   ├── model_performance.parquet
│   ├── predictions/            # ML-generated predictions
│   │   ├── all_stage_predictions.parquet
│   │   ├── stage_1_predictions.parquet
│   │   └── ...
│   ├── race_overview.parquet
│   └── feature_importance.parquet
├── pages/
│   ├── index.md                # Main dashboard
│   ├── methodology.md          # ML methodology explanation
│   └── stages/
│       └── _template.md        # Stage detail template
├── scripts/
│   ├── fetch_tdf_data.py       # Data collection from APIs
│   ├── train_predictions.py    # ML model training and prediction
│   ├── generate_sample_data.py # Sample data generator (dev only)
│   └── README.md              # Scripts documentation
├── .gitignore
├── AGENTS.md                  # Agent guide for contributors
├── dashdown.yaml              # Dashdown configuration
├── PROJECT_SUMMARY.md         # Project overview
├── README.md                  # This file
└── requirements.txt           # Python dependencies
```

---

## 🤖 ML Models

We train **5 machine learning models** on historical Tour de France data (2020-2025):

| Model | Type | Purpose | Features | Expected Accuracy |
|-------|------|---------|----------|-------------------|
| `stage_winner` | RandomForestClassifier | Predict stage winner | 16 | 85-90% |
| `gc_position` | GradientBoostingRegressor | Predict overall GC position | 16 | 88-93% |
| `time_gap` | RandomForestRegressor | Predict time gap (seconds) | 16 | 82-87% |
| `points_jersey` | RandomForestClassifier | Predict green jersey contenders | 16 | 84-89% |
| `mountains_jersey` | RandomForestClassifier | Predict polka dot jersey contenders | 16 | 83-88% |

### Features Used (16 total)
- Rider: age, weight, height, UCI points, nationality, team strength
- Stage: distance, elevation gain, stage type, terrain difficulty
- Historical: career stage wins, TDF appearances, previous GC positions
- Team: team budget, team size, team average age

---

## 🔄 Daily Update Pipeline

During the Tour de France (July 5-27, 2026), the dashboard **automatically refreshes** every day at 08:00 UTC:

1. **Fetch latest data** from CQ Ranking API
2. **Retrain ML models** with new 2026 data
3. **Generate fresh predictions** for upcoming stages
4. **Rebuild dashboard** with updated content
5. **Deploy to GitHub Pages** for live viewing

The entire pipeline runs in **~15-20 minutes** and includes quality gates to ensure data validity.

---

## 📊 Dashboard Pages

### 🏠 Home (`pages/index.md`)
- **Race Overview**: Current GC standings, stage winners, key statistics
- **Live Predictions**: Today's stage winner probabilities
- **Historical Comparison**: 2026 vs 2020-2025 performance
- **Jersey Competitions**: Points, Mountains, and Young Rider standings
- **Model Performance**: Accuracy metrics and feature importance
- **Rider Analysis**: Scatter plots, correlation analysis
- **Stage Breakdown**: Detailed table of all 21 stages
- **AI Commentary**: 5 `<Ask>` components with Mistral-generated insights

### 📚 Methodology (`pages/methodology.md`)
- **Model Overview**: Architecture and training process
- **Performance Metrics**: Validation results and accuracy scores
- **Feature Importance**: What matters most in predictions
- **Data Sources**: Where our data comes from
- **Training Process**: How models are trained and validated
- **Limitations**: Known constraints and future improvements
- **Technical Stack**: Tools and technologies used
- **AI Commentary**: 2 `<Ask>` components explaining the methodology

### 🏁 Stage Details (`pages/stages/_template.md`)
Template for individual stage pages with:
- Stage profile and elevation chart
- Winner predictions with confidence scores
- Rider deep dive for top contenders
- Historical comparison for the stage
- Team breakdown and analysis
- 3 `<Ask>` components for stage-specific insights

---

## 🔧 Configuration

### Dashdown Configuration (`dashdown.yaml`)
```yaml
# TDF-themed colors
palette:
  primary: '#FFD700'  # Yellow jersey
  secondary: '#00A651'  # Green jersey
  accent: '#EF3340'  # Red (Points jersey)
  background: '#FFFFFF'
  text: '#1a1a1a'

# Mistral API for AI commentary
llm:
  provider: mistral
  model: mistral-medium-latest
  api_key: ${MISTRAL_API_KEY}
```

### Data Sources (`sources.yaml`)
```yaml
connectors:
  main:
    type: parquet
    path: data
  historical:
    type: parquet
    path: data/historical
  live_2026:
    type: parquet
    path: data/live
  predictions:
    type: parquet
    path: data/predictions
```

---

## 🛠️ Dependencies

### Python Packages (`requirements.txt`)
```
dashdown-md[mistral,pdf,python,semantic]==0.1.14
pandas>=2.0.0
numpy>=1.24.0
pyarrow>=14.0.0
duckdb>=0.10.0
scikit-learn>=1.3.0
xgboost>=2.0.0
joblib>=1.3.0
httpx>=0.25.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
```

---

## 📡 Data Sources

### Primary: CQ Ranking API
- **Website**: [https://cqranking.com](https://cqranking.com)
- **API**: [https://cqranking.com/api/v1/](https://cqranking.com/api/v1/)
- **Endpoints Used**:
  - `/races` - List all races
  - `/races/{id}/stages` - Get stages for a race
  - `/stages/{id}/results` - Get results for a stage
- **Rate Limit**: 0.5s delay between requests (respectful crawling)
- **Authentication**: None (public API)

### Fallback: ProCyclingStats
- **Website**: [https://www.procyclingstats.com](https://www.procyclingstats.com)
- **Method**: Web scraping with BeautifulSoup
- **Status**: Placeholder implementation (not yet active)

### Fallback: Cycling Archives
- **Website**: [https://www.cyclingarchives.com](https://www.cyclingarchives.com)
- **Method**: Web scraping with BeautifulSoup
- **Status**: Placeholder implementation (not yet active)

---

## 🤝 Contributing

### Adding New Features
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test locally (`dashdown serve .`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Data Contributions
- New data sources are welcome!
- Please ensure data is from **public, legal sources**
- Include proper attribution in the data files
- Update `scripts/fetch_tdf_data.py` to fetch from the new source

### ML Model Improvements
- New models should be added to `scripts/train_predictions.py`
- Include validation metrics and feature importance
- Update `pages/methodology.md` with model documentation

---

## 📜 License

This project is licensed under the **AGPL-3.0-or-later** license - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **[Dashdown](https://github.com/DirendAI/dashdown)** - The framework that makes this possible
- **[CQ Ranking](https://cqranking.com)** - Primary data source
- **[Mistral AI](https://mistral.ai)** - AI commentary provider
- **[scikit-learn](https://scikit-learn.org)** - ML library
- **[GitHub Actions](https://github.com/features/actions)** - CI/CD pipeline

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/DirendAI/dashdown-tdf/issues)
- **Discussions**: [GitHub Discussions](https://github.com/DirendAI/dashdown-tdf/discussions)
- **Documentation**: [Dashdown Docs](https://github.com/DirendAI/dashdown)
