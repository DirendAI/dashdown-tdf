---
title: Stage {{stage_number}} - {{stage_name}}
description: Detailed analysis and predictions for Stage {{stage_number}} of Tour de France 2026
---

# 🏁 Stage {{stage_number}}: {{stage_name}}

<Counter
  query="SELECT COUNT(*) as total FROM stage_{{stage_number}}_predictions"
  label="Predicted Riders"
  color="#FFD700"
/>

<Counter
  query="SELECT AVG(prediction_score) as avg_score FROM stage_{{stage_number}}_predictions"
  label="Avg Confidence"
  color="#00A651"
  format="%.1f%%"
/>

---

## 📊 Stage Profile

<BarChart
  query="""SELECT
    stage_number,
    distance_km,
    elevation_gain_m,
    stage_type,
    start_location,
    end_location
  FROM stages_2026
  WHERE stage_number = {{stage_number}}"""
  x=stage_number
  y="['distance_km', 'elevation_gain_m']"
  title="Stage {{stage_number}} - Distance & Elevation"
  color="#FFD700"
/>

<Value
  query="SELECT distance_km FROM stages_2026 WHERE stage_number = {{stage_number}}"
  label="Distance"
  suffix=" km"
/>

<Value
  query="SELECT elevation_gain_m FROM stages_2026 WHERE stage_number = {{stage_number}}"
  label="Elevation Gain"
  suffix=" m"
/>

<Value
  query="SELECT stage_type FROM stages_2026 WHERE stage_number = {{stage_number}}"
  label="Stage Type"
/>

---

## 🎯 Winner Predictions

<BarChart
  query="""SELECT
    rider_name,
    prediction_score * 100 as confidence,
    predicted_position
  FROM stage_{{stage_number}}_predictions
  ORDER BY prediction_score DESC
  LIMIT 10"""
  x=rider_name
  y=confidence
  title="Top 10 Predicted Winners - Stage {{stage_number}}"
  color="#FFD700"
  series="predicted_position"
/>

<Table
  query="""SELECT
    predicted_position as '#',
    rider_name as 'Rider',
    team_name as 'Team',
    prediction_score * 100 as 'Confidence %',
    rider_specialty as 'Specialty',
    historical_stage_wins as 'Career Stage Wins'
  FROM stage_{{stage_number}}_predictions
  ORDER BY prediction_score DESC
  LIMIT 15"""
/>

---

## 👥 Rider Deep Dive

### Top Contender: {{top_rider}}

<BigValue
  query="SELECT prediction_score * 100 FROM stage_{{stage_number}}_predictions WHERE rider_name = '{{top_rider}}'"
  label="{{top_rider}} Win Probability"
  suffix="%"
  color="#FFD700"
/>

<Table
  query="""SELECT
    'Age' as metric, age as value,
    'Weight' as metric, weight_kg as value,
    'Height' as metric, height_cm as value,
    'Nationality' as metric, nationality as value,
    'UCI Points' as metric, uci_points as value
  FROM riders_2026
  WHERE rider_name = '{{top_rider}}'
  UNPIVOT(value FOR metric IN (age, weight_kg, height_cm, nationality, uci_points))"""
  title="{{top_rider}} - Rider Profile"
/>

<BarChart
  query="""SELECT
    stage_type,
    COUNT(*) as stage_wins,
    AVG(finish_time_seconds) as avg_time
  FROM historical_results
  WHERE rider_name = '{{top_rider}}' AND finish_position = 1
  GROUP BY stage_type"""
  x=stage_type
  y="['stage_wins', 'avg_time']"
  title="{{top_rider}} - Historical Stage Wins by Type"
  color="#00A651"
/>

### Team Breakdown

<PieChart
  query="""SELECT
    team_name,
    COUNT(*) as rider_count
  FROM stage_{{stage_number}}_predictions
  GROUP BY team_name
  ORDER BY rider_count DESC"""
  title="Team Representation in Top Predictions"
  color="#FFD700"
/>

---

## 📈 Historical Comparison

<LineChart
  query="""SELECT
    year,
    AVG(finish_time_seconds) as avg_time
  FROM historical_results
  WHERE stage_number = {{stage_number}}
  GROUP BY year
  ORDER BY year"""
  x=year
  y=avg_time
  title="Average Finish Time - Stage {{stage_number}} (Historical)"
  color="#00A651"
/>

<Table
  query="""SELECT
    year,
    winner_name as 'Winner',
    winner_team as 'Team',
    finish_time as 'Time',
    avg_speed_kmh as 'Avg Speed (km/h)'
  FROM historical_results
  WHERE stage_number = {{stage_number}} AND finish_position = 1
  ORDER BY year DESC"""
  title="Previous Winners - Stage {{stage_number}}"
/>

---

## 🤖 Prediction Insights

<Gauge
  query="SELECT AVG(prediction_score) * 100 as avg_confidence FROM stage_{{stage_number}}_predictions"
  label="Model Confidence"
  min=0
  max=100
  color="#FFD700"
/>

<Ask lazy=false>
What makes Stage {{stage_number}} particularly challenging based on the elevation profile and distance?
Explain the key factors that will determine the winner of this stage.
</Ask>

<Ask lazy=false>
Who are the top 3 favorites for Stage {{stage_number}} and what are their strengths?
Compare their historical performance in similar stage types.
</Ask>

<Ask lazy=false>
How does the predicted winner's profile match the demands of Stage {{stage_number}}?
Analyze the fit between rider specialty and stage characteristics.
</Ask>

---

## 📝 Stage Details

<Table
  query="""SELECT
    'Start' as detail, start_location as value,
    'End' as detail, end_location as value,
    'Date' as detail, stage_date as value,
    'Type' as detail, stage_type as value,
    'Distance' as detail, CONCAT(distance_km, ' km') as value,
    'Elevation' as detail, CONCAT(elevation_gain_m, ' m') as value
  FROM stages_2026
  WHERE stage_number = {{stage_number}}
  UNPIVOT(value FOR detail IN (start_location, end_location, stage_date, stage_type, distance_km, elevation_gain_m))"""
  title="Stage {{stage_number}} - Details"
/>

---

*Predictions generated: {{prediction_date}}*
*Model version: {{model_version}}*
