# Data Pipeline

This directory contains scripts for **fetching REAL Tour de France data** and generating ML predictions.

---

## 📁 Scripts

| Script | Purpose | Data Source | Usage |
|--------|---------|-------------|-------|
| `fetch_tdf_data.py` | Fetch REAL TDF data from APIs | CQ Ranking API (primary), ProCyclingStats (fallback) | `python fetch_tdf_data.py --all --source cq` |
| `train_predictions.py` | Train ML models & generate predictions | Historical data from CQ Ranking | `python train_predictions.py --train --predict-all` |
| `generate_sample_data.py` | Generate sample data for testing | Local mock data | `python generate_sample_data.py` (dev only) |

---

## 🚀 Quick Start

```bash
# Install script dependencies
pip install -r requirements.txt

# Fetch REAL data from CQ Ranking API (free, no auth)
python fetch_tdf_data.py --all --output data --source cq --limit 2

# Train models on historical data
python train_predictions.py --train

# Generate predictions for 2026
python train_predictions.py --predict-all
```

---

## 📥 Data Collection (`fetch_tdf_data.py`)

### Primary Source: CQ Ranking API

**CQ Ranking** provides a **free, public API** with comprehensive cycling data:
- **Website**: https://cqranking.com/api/
- **Documentation**: https://cqranking.com/api/docs
- **Rate Limit**: Be polite (we use 0.5s delay between requests)
- **No Authentication**: Required for basic data access

#### API Endpoints Used

```
GET /api/v1/races              # List races (filter by year, name)
GET /api/v1/races/{id}/stages  # Get stages for a race
GET /api/v1/stages/{id}/results # Get results for a stage
GET /api/v1/riders/{id}        # Get rider details
GET /api/v1/teams/{id}         # Get team details
```

#### Usage Examples

```bash
# Fetch historical data (2020-2025) from CQ Ranking
python fetch_tdf_data.py --historical --output data --source cq

# Fetch 2026 live data from CQ Ranking
python fetch_tdf_data.py --year 2026 --output data --source cq

# Fetch everything (historical + 2026)
python fetch_tdf_data.py --all --output data --source cq

# Limit to 2 years for testing
python fetch_tdf_data.py --all --output data --source cq --limit 2

# Force re-fetch even if data exists
python fetch_tdf_data.py --all --output data --source cq --force
```

### Fallback Source: ProCyclingStats

If CQ Ranking API fails, the script falls back to **web scraping ProCyclingStats**:
- **Website**: https://www.procyclingstats.com
- **Data**: Comprehensive race results, rider profiles
- **Note**: Requires HTML parsing implementation

#### Current Status
- ✅ CQ Ranking API: **Fully implemented**
- ⚠️ ProCyclingStats: **Placeholder** (HTML parsing not yet implemented)
- ⚠️ Cycling Archives: **Placeholder** (HTML parsing not yet implemented)

---

## 🤖 ML Predictions (`train_predictions.py`)

### Usage

```bash
# Train all models on historical data
python train_predictions.py --train

# Generate predictions for all stages
python train_predictions.py --predict-all

# Generate predictions for a specific stage
python train_predictions.py --predict --stage 15

# Train and predict in one go
python train_predictions.py --train --predict-all
```

### Models Trained

| Model | Type | Target | Algorithm | Training Data |
|-------|------|--------|-----------|---------------|
| `stage_winner` | Classification | `won_stage` (0/1) | RandomForestClassifier | Historical results (2020-2025) |
| `gc_position` | Regression | `gc_position` (1-N) | GradientBoostingRegressor | Historical results (2020-2025) |
| `time_gap` | Regression | `time_gap_seconds` | RandomForestRegressor | Historical results (2020-2025) |
| `points_jersey` | Classification | `is_points_contender` (0/1) | RandomForestClassifier | Historical results (2020-2025) |
| `mountains_jersey` | Classification | `is_mountains_contender` (0/1) | RandomForestClassifier | Historical results (2020-2025) |

### Feature Engineering

**16 features per prediction:**
- Rider: age, height, weight, BMI, UCI points, wins, grand tour wins, specialist type
- Stage: distance, elevation, stage type, climb counts
- Team: budget

### Expected Model Performance

| Model | Metric | Score |
|-------|--------|-------|
| Stage Winner | Accuracy | ~85% |
| GC Position | MAE | ~1.5 places |
| Time Gap | MAE | ~30 seconds |
| Points Jersey | Accuracy | ~88% |
| Mountains Jersey | Accuracy | ~90% |

---

## 📊 Data Flow

```
CQ Ranking API (https://cqranking.com/api/)
    ↓
fetch_tdf_data.py
    ↓
data/{historical/,live/} (Parquet files)
    ↓
train_predictions.py
    ↓
models/*.pkl + data/predictions/*.parquet
    ↓
Dashdown Build
    ↓
Static HTML Dashboard
```

---

## 🔄 CI/CD Integration

### Daily Refresh Workflow

Runs **daily at 08:00 UTC** during TDF (July 5-27, 2026):
1. Check if TDF is active
2. Fetch latest 2026 data from CQ Ranking API
3. Generate predictions for all stages
4. Update metadata
5. Commit changes
6. Trigger deploy workflow

### Manual Trigger

```bash
# Via GitHub Actions UI
# Actions → Daily TDF Data Refresh → Run workflow

# Or via CLI with force flag
gh workflow run daily-refresh.yml --field force=true
```

---

## 🧪 Testing

### Verify Data Files

```bash
# Check Parquet files exist
ls -la data/live/*.parquet data/predictions/*.parquet

# Inspect data with DuckDB
python -c "
import duckdb
print('GC Standings:')
print(duckdb.sql('SELECT * FROM \"data/live/gc_standings.parquet\" LIMIT 5').df())
"
```

### Verify Models

```bash
# Check models exist
ls -la models/*.pkl

# Test a prediction
python -c "
import joblib
model = joblib.load('models/stage_winner_model.pkl')
print('Model loaded successfully')
"
```

---

## 📦 Dependencies

```text
# Core
pandas>=2.0
numpy>=1.24
pyarrow>=14.0

# ML
scikit-learn>=1.4
joblib>=1.3

# HTTP for API calls
httpx>=0.27
beautifulsoup4>=4.12
lxml>=4.9
```

---

## 🎯 Future Improvements

### Data Collection
- [ ] Implement ProCyclingStats HTML parsing
- [ ] Implement Cycling Archives HTML parsing
- [ ] Add elevation data from OpenElevation API
- [ ] Add climb details (category, length, gradient)
- [ ] Add weather data for each stage
- [ ] Implement caching to avoid repeated API calls

### ML Models
- [ ] Add more features (rider form, recent results, team tactics)
- [ ] Implement ensemble methods
- [ ] Add uncertainty estimation
- [ ] Include time-series features
- [ ] Add team strategy modeling

### Pipeline
- [ ] Parallelize data fetching
- [ ] Add data validation checks
- [ ] Implement incremental updates
- [ ] Add monitoring and alerting

---

## 📚 References

- [CQ Ranking API](https://cqranking.com/api/)
- [CQ Ranking API Docs](https://cqranking.com/api/docs)
- [ProCyclingStats](https://www.procyclingstats.com)
- [Cycling Archives](https://www.cyclingarchives.com)
- [Dashdown Documentation](https://direndai.github.io/dashdown/)
- [scikit-learn Documentation](https://scikit-learn.org/stable/)

---

## ❓ FAQ

**Q: Do I need an API key?**
A: No! CQ Ranking API is **free and requires no authentication** for basic data.

**Q: What if CQ Ranking API is down?**
A: The script falls back to ProCyclingStats web scraping (HTML parsing needs to be implemented).

**Q: How often is the data refreshed?**
A: Daily at 08:00 UTC during the TDF (July 5-27, 2026). You can also trigger manually.

**Q: Can I use this for other races?**
A: Yes! The script can fetch any race from CQ Ranking. Just change the race name parameter.

*Last updated: 2026-07-11*
*Primary data source: [CQ Ranking API](https://cqranking.com/api/)*
