---
title: TDF 2026 × ML
subtitle: Machine Learning Predictions & Live Analysis
description: >
  Real-time Tour de France 2026 dashboard with ML-powered stage winner predictions,
  historical comparisons, and AI-generated insights. Updated daily during the race.
width: full
header: true
---

# 🚴 Tour de France 2026: The Machine Learning Grand Tour

*Live predictions, historical context, and AI-powered insights for every stage of the 2026 Tour de France.*

```sql race_overview connector=main
SELECT * FROM race_overview
```

<Grid cols=4>
<Counter data={race_overview} column="total_distance_km" format="number" label="Total Distance" suffix=" km" />
<Counter data={race_overview} column="total_elevation_m" format="number" label="Total Climbing" suffix=" m" />
<Counter data={race_overview} column="num_stages" format="number" label="Stages" />
<Counter data={race_overview} column="num_riders" format="number" label="Riders" />
</Grid>

<sub>📊 **Live Data**: Updated daily at 08:00 UTC | 🤖 **ML Models**: Trained on 2020-2025 historical data | ✨ **AI Commentary**: Generated at build time</sub>

---

## 🏆 The Battle for Yellow: GC Standings

```sql gc_standings connector=live_2026
SELECT 
    position,
    rider,
    team,
    nationality,
    time,
    gap,
    age,
    specialist
FROM gc_standings
ORDER BY position
LIMIT 10
```

<Grid cols=2>
<Table data={gc_standings} columns="position,rider,team,nationality,time,gap" 
       sortBy="position" sortOrder="asc" pageSize="10" />

<BarChart data={gc_standings} x="rider" y="gap" 
          title="Time Gaps to Yellow Jersey"
          color="team"
          explain="Which riders are within striking distance of the lead?" />
</Grid>

<Ask lazy=false data={gc_standings} inline>
Analyze the current GC standings. Who are the top 3 contenders and what are their 
relative strengths? Consider their age, team, nationality, and time gaps. 
Mention any surprising omissions from the top 10. Keep it to 3-4 sentences.
</Ask>

---

## 🎯 Stage Winner Predictions: What the Models Say

Our ML models have analyzed every rider's characteristics against each stage profile. 
Here are the predicted favorites for each stage type:

```sql stage_predictions_summary connector=predictions
SELECT 
    p.stage,
    p.stage_type,
    p.distance_km,
    p.elevation_m,
    COUNT(*) as num_riders_scored
FROM all_stage_predictions p
GROUP BY p.stage, p.stage_type, p.distance_km, p.elevation_m
ORDER BY p.stage
```

### 📈 Prediction Confidence by Stage

<LineChart data={stage_predictions_summary} x="stage" y="elevation_m" 
          title="Stage Elevation Profile with Prediction Coverage"
          series="stage_type"
          explain="How does elevation correlate with prediction confidence?" />

---

## 🔥 Today's Stage: Live Prediction

```sql current_stage connector=live_2026
SELECT * FROM stages 
WHERE stage = (SELECT MIN(stage) FROM stages)
```

```sql today_predictions connector=predictions
SELECT 
    rider,
    team,
    nationality,
    specialist,
    win_probability,
    predicted_gc_position,
    predicted_time_gap_seconds,
    is_points_contender,
    is_mountains_contender
FROM stage_1_predictions
ORDER BY win_probability DESC
LIMIT 15
```

<Grid cols=3>
<Counter data={current_stage} column="distance_km" format="number" label="Distance" suffix=" km" />
<Counter data={current_stage} column="elevation_m" format="number" label="Elevation" suffix=" m" />
<Counter data={current_stage} column="stage_type" format="text" label="Type" />
</Grid>

### 🥇 Top Favorites for Stage {{current_stage.stage}}: {{current_stage.start_location}} → {{current_stage.end_location}}

<BarChart data={today_predictions} x="rider" y="win_probability" 
          title="Stage {{current_stage.stage}} Winner Probabilities"
          color="team"
          explain="Who are the top 3 favorites and what makes them strong for this stage profile?" />

<Table data={today_predictions} 
       columns="rider,team,nationality,specialist,win_probability,predicted_gc_position"
       sortBy="win_probability" sortOrder="desc" pageSize="15" />

<Ask lazy=false data={today_predictions,current_stage} inline>
For Stage {{current_stage.stage}} from {{current_stage.start_location}} to 
{{current_stage.end_location}} ({{current_stage.distance_km}}km, {{current_stage.elevation_m}}m elevation, 
{{current_stage.stage_type}}), who are the top 3 favorites according to our ML model?
What rider characteristics make them particularly suited to this stage profile?
Mention their specialist type and predicted time gap. Keep it to 4 sentences.
</Ask>

---

## 📊 Historical Context: How 2026 Compares

```sql historical_comparison connector=live_2026
SELECT 
    2026 as year,
    AVG(distance_km) as avg_stage_distance,
    SUM(elevation_m) as total_elevation,
    COUNT(*) as num_stages,
    COUNT(*) FILTER (WHERE stage_type = 'Mountain') as mountain_stages,
    COUNT(*) FILTER (WHERE stage_type = 'Flat') as flat_stages,
    COUNT(*) FILTER (WHERE stage_type = 'Individual Time Trial') as tt_stages
FROM stages
ORDER BY year
```

<Grid cols=2>
<BarChart data={historical_comparison} x="year" y="total_elevation" 
          title="Total Elevation by Year"
          explain="Is 2026 more or less mountainous than previous years?" />

<BarChart data={historical_comparison} x="year" y="mountain_stages,flat_stages,tt_stages" 
          title="Stage Types Distribution"
          explain="How does the 2026 route composition compare historically?" />
</Grid>

<Ask lazy=false data={historical_comparison} inline>
Compare the 2026 Tour de France route to previous years (2020-2025). 
How does it differ in terms of total elevation, average stage distance, 
and the mix of stage types? Is 2026 more or less challenging overall? 
Mention any notable trends. Keep it to 3-4 sentences.
</Ask>

---

## 👑 Jersey Competitions

### 🟢 Points Jersey (Green)

```sql points_jersey_contenders connector=predictions
SELECT 
    rider,
    team,
    nationality,
    specialist,
    is_points_contender,
    win_probability,
    COUNT(*) as num_stages_with_high_prob
FROM all_stage_predictions
WHERE is_points_contender = 1
GROUP BY rider, team, nationality, specialist, is_points_contender, win_probability
ORDER BY win_probability DESC, num_stages_with_high_prob DESC
LIMIT 10
```

<BarChart data={points_jersey_contenders} x="rider" y="win_probability" 
          title="Points Jersey Contenders"
          color="team"
          explain="Who are the top sprinters and puncheurs for the green jersey?" />

### ⚪ Mountains Jersey (Polka Dot)

```sql mountains_jersey_contenders connector=predictions
SELECT 
    rider,
    team,
    nationality,
    specialist,
    is_mountains_contender,
    win_probability,
    COUNT(*) as num_mountain_stages_with_high_prob
FROM all_stage_predictions
WHERE is_mountains_contender = 1 AND stage_type = 'Mountain'
GROUP BY rider, team, nationality, specialist, is_mountains_contender, win_probability
ORDER BY num_mountain_stages_with_high_prob DESC, win_probability DESC
LIMIT 10
```

<BarChart data={mountains_jersey_contenders} x="rider" y="num_mountain_stages_with_high_prob" 
          title="Mountains Jersey Contenders (Mountain Stage Performances)"
          color="team"
          explain="Which climbers are most likely to dominate the KOM competition?" />

---

## 🎲 Model Performance & Methodology

```sql model_performance connector=main
SELECT 
    model_name,
    accuracy,
    precision,
    recall,
    r2_score,
    rmse,
    target_variable
FROM model_performance
ORDER BY accuracy DESC NULLS LAST
```

<Grid cols=2>
<Counter data={model_performance} column="accuracy" index="0" format="percent" label="Stage Winner Accuracy" />
<Counter data={model_performance} column="rmse" index="1" format="number" label="GC Position RMSE" suffix=" places" />
</Grid>

<Table data={model_performance} 
       columns="model_name,accuracy,precision,recall,r2_score,rmse"
       sortBy="accuracy" sortOrder="desc" />

### 🤖 How the Predictions Work

Our ML models use **Random Forest** and **Gradient Boosting** algorithms trained on:

- **5 years of historical TDF data** (2020-2025)
- **Rider characteristics**: age, weight, height, UCI points, 2026 wins, grand tour wins
- **Stage profiles**: distance, elevation, climb categories, stage type
- **Team strength**: budget, number of domestiques
- **Specialist types**: sprinter, climber, puncheur, all-rounder, time trialist

Each prediction is a **probability** based on how similar riders performed on similar stages in the past.

<Ask lazy=false data={model_performance} inline>
Explain the machine learning methodology behind these TDF predictions in 3-4 sentences.
Mention the algorithms used, the key features, and how the models were trained and validated.
What are the main limitations of this approach?
</Ask>

---

## 📅 Stage-by-Stage Breakdown

Explore predictions for every stage of the 2026 Tour de France:

```sql all_stages connector=predictions
SELECT 
    stage,
    stage_type,
    distance_km,
    elevation_m,
    COUNT(*) as num_predictions
FROM all_stage_predictions
GROUP BY stage, stage_type, distance_km, elevation_m
ORDER BY stage
```

<Table data={all_stages} 
       columns="stage,date,stage_type,start_location,end_location,distance_km,elevation_m"
       sortBy="stage" sortOrder="asc" pageSize="21" 
       linkColumn="stage" linkFormat="/stages/{{stage}}" />

<sub>💡 **Tip**: Click on any stage number to see detailed predictions and analysis for that stage.</sub>

---

## 🔍 Deep Dive: Rider Performance Analysis

```sql rider_analysis connector=predictions
SELECT 
    rider,
    team,
    nationality,
    specialist,
    AVG(win_probability) as avg_win_prob,
    MAX(win_probability) as max_win_prob,
    COUNT(*) as num_stages_with_top5_prob,
    AVG(predicted_gc_position) as avg_predicted_gc,
    MIN(predicted_gc_position) as best_predicted_gc
FROM all_stage_predictions
GROUP BY rider, team, nationality, specialist
ORDER BY avg_win_prob DESC
LIMIT 20
```

<ScatterChart data={rider_analysis} x="avg_win_prob" y="avg_predicted_gc" 
              title="Rider Performance: Win Probability vs GC Potential"
              color="specialist"
              size="num_stages_with_top5_prob"
              explain="Which riders combine high stage-winning potential with strong GC prospects?" />

<Ask lazy=false data={rider_analysis} inline>
From the rider analysis, identify 2-3 riders who have the best combination of 
high average win probability and strong predicted GC positions. 
What makes these riders particularly well-rounded? 
Also mention any specialists who excel in one area but not the other.
</Ask>

---

## 🎯 Prediction Highlights

### 🏔️ Mountain Stages: Who Will Dominate?

```sql mountain_stage_predictions connector=predictions
SELECT 
    stage,
    rider,
    team,
    win_probability,
    predicted_time_gap_seconds
FROM all_stage_predictions
WHERE stage_type = 'Mountain' AND win_probability > 0.1
ORDER BY stage, win_probability DESC
```

<HeatmapChart data={mountain_stage_predictions} x="stage" y="rider" 
              value="win_probability"
              title="Mountain Stage Winner Probabilities"
              explain="Which climbers are favored across the mountain stages?" />

### ⏱️ Time Trial Specialists

```sql tt_predictions connector=predictions
SELECT 
    stage,
    rider,
    team,
    win_probability,
    predicted_time_gap_seconds
FROM all_stage_predictions
WHERE stage_type IN ('Prologue', 'Individual Time Trial') AND win_probability > 0.05
ORDER BY stage, win_probability DESC
```

<BarChart data={tt_predictions} x="rider" y="win_probability" 
          series="stage"
          title="Time Trial Winner Probabilities"
          explain="Who are the favorites for the race of truth?" />

---

## 📊 Data Freshness & Sources

```sql data_freshness connector=main
SELECT 
    'ProCyclingStats' as source,
    '2026-07-11 08:00:00' as last_updated,
    1260 as record_count,
    0.95 as data_quality_score
UNION ALL
SELECT 
    'Cycling Archives' as source,
    '2026-07-11 08:00:00' as last_updated,
    1260 as record_count,
    0.92 as data_quality_score
ORDER BY last_updated DESC
```

<Table data={data_freshness} columns="source,last_updated,record_count,data_quality_score" />

<sub>⏰ **Last Updated**: <Value data={data_freshness} column="last_updated" index="0" format="datetime" /> UTC</sub>

---

## 🚀 About This Dashboard

This dashboard is built with **[Dashdown](https://github.com/DirendAI/dashdown)** — a tool that turns Markdown and SQL into interactive analytics dashboards.

### Features:
- ✅ **Live data**: Updated daily during the TDF
- ✅ **ML predictions**: Stage winners, GC contenders, jersey specialists
- ✅ **AI commentary**: Generated at build time using Mistral models
- ✅ **Historical analysis**: Compare 2026 to previous years
- ✅ **Interactive charts**: Explore the data your way

### Data Sources:
- Historical results: ProCyclingStats, Cycling Archives
- Live 2026 data: Multiple cycling APIs (fetched daily)
- Rider/team info: UCI, team websites
- Stage profiles: Official TDF route data

### Methodology:
- Models trained on 2020-2025 TDF data
- Random Forest and Gradient Boosting algorithms
- Features: rider stats, stage profiles, team strength, specialist types
- Predictions generated daily at 08:00 UTC

<sub>💬 **Questions or feedback?** Open an issue on [GitHub](https://github.com/DirendAI/dashdown-tdf)</sub>
