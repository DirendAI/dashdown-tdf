---
title: TDF 2026 × ML
subtitle: Live data & machine-learning predictions
description: >
  Tour de France 2026 dashboard — real standings and stage results so far,
  with ML predictions for the remaining stages, the final GC and the jersey
  competitions. Data refreshes daily during the race.
width: full
header: true
---

# 🚴 Tour de France 2026: The Machine Learning Grand Tour

*Real results through <Value data={race_overview} column="stages_completed" /> of 21 stages — and model predictions for everything still to come.*

```sql race_overview connector=main
SELECT * FROM race_overview
```

<Grid cols=4>
<Counter data={race_overview} column="stages_completed" label="Stages Completed" suffix=" / 21" />
<Counter data={race_overview} column="total_distance_km" format="number" label="Total Route" suffix=" km" />
<Counter data={race_overview} column="num_riders_active" label="Riders Still Racing" suffix=" of 184" />
<Counter data={race_overview} column="num_teams" label="Teams" />
</Grid>

<Grid cols=4>
<Counter data={race_overview} column="yellow_jersey" label="🟡 Yellow Jersey" color="primary" />
<Counter data={race_overview} column="green_jersey" label="🟢 Green Jersey" color="secondary" />
<Counter data={race_overview} column="polka_dot_jersey" label="🔴 Polka Dot" color="accent" />
<Counter data={race_overview} column="white_jersey" label="⚪ White Jersey" />
</Grid>

<sub>📊 **Data**: Wikipedia (cites letour.fr / Tissot timing), refreshed daily at 08:00 UTC | 🤖 **ML**: trained on 2020-2025 + this year's form | ✨ **AI commentary**: baked at build time</sub>

---

## 🏆 The Battle for Yellow — GC after Stage <Value data={race_overview} column="stages_completed" />

```sql gc_standings connector=live_2026
SELECT position, rider, team, nationality, age, time, gap
FROM gc_standings
ORDER BY position
```

```sql gc_gaps connector=live_2026
SELECT rider, gap_minutes
FROM gc_standings
ORDER BY position
```

<Grid cols=2>
<Table data={gc_standings}
       sort="position asc" title="General classification (top 10)" />

<BarChart data={gc_gaps} x="rider" y="gap_minutes" horizontal
          title="Minutes behind Tadej Pogačar"
          explain="Who is still within realistic striking distance of the yellow jersey, and who has already lost the Tour?" />
</Grid>

```sql gc_evolution connector=live_2026
SELECT e.stage,
       e.rider,
       ROUND(e.gap_seconds / 60.0, 2) AS minutes_behind
FROM gc_evolution e
WHERE e.rider IN (SELECT rider FROM gc_standings WHERE position <= 6)
ORDER BY e.stage, e.rider
```

<LineChart data={gc_evolution} x="stage" y="minutes_behind" series="rider"
           title="How the GC race has unfolded, stage by stage"
           explain="Where did the decisive time gaps open up? Stage 6 crossed the Col du Tourmalet." />

<Ask data={gc_standings,gc_evolution} inline
     ask="Summarise the state of the 2026 Tour GC battle in 3-4 sentences: who leads, by how much, where the race was decided so far (stage 1 was a team time trial in Barcelona, stage 3 finished at Les Angles, stage 6 crossed the Tourmalet to Gavarnie-Gèdre), and which riders are still in contention." />

---

## 📋 The Story So Far — Stage Results

```sql stage_winners connector=live_2026
SELECT stage,
       date,
       start_location || ' → ' || end_location AS course,
       stage_type,
       distance_km,
       winner,
       winner_team
FROM stages
WHERE completed
ORDER BY stage
```

<Table data={stage_winners}
       sort="stage asc" title="Completed stages" row_link="/stages/{stage}" />

```sql points_standings connector=live_2026
SELECT rank, rider, team, points
FROM classifications
WHERE classification = 'points' AND rank <= 10
ORDER BY rank
```

```sql kom_standings connector=live_2026
SELECT rank, rider, team, points
FROM classifications
WHERE classification = 'mountains' AND rank <= 10
ORDER BY rank
```

<Grid cols=2>
<BarChart data={points_standings} x="rider" y="points"
          title="🟢 Points classification (green jersey)"
          explain="Mads Pedersen leads on points — which sprinters are his closest threats?" />
<BarChart data={kom_standings} x="rider" y="points"
          title="🔴 Mountains classification (polka dot)"
          explain="How dominant is the mountains classification leader so far?" />
</Grid>

---

## 🔮 Next Up: Stage <Value data={next_stage_info} column="stage" /> — <Value data={next_stage_info} column="start_location" /> → <Value data={next_stage_info} column="end_location" />

```sql next_stage_info connector=predictions
SELECT DISTINCT stage, date, start_location, end_location, stage_type, distance_km
FROM stage_predictions
WHERE stage = (SELECT MIN(stage) FROM stage_predictions)
```

```sql next_stage_favorites connector=predictions
SELECT predicted_rank AS rank, rider, team, specialist,
       ROUND(win_probability * 100, 1)    AS win_pct,
       ROUND(podium_probability * 100, 1) AS podium_pct
FROM stage_predictions
WHERE stage = (SELECT MIN(stage) FROM stage_predictions)
ORDER BY predicted_rank
LIMIT 12
```

<Grid cols=3>
<Counter data={next_stage_info} column="date" label="Date" />
<Counter data={next_stage_info} column="stage_type" label="Stage Type" />
<Counter data={next_stage_info} column="distance_km" format="number" label="Distance" suffix=" km" />
</Grid>

<Grid cols=2>
<BarChart data={next_stage_favorites} x="rider" y="win_pct" horizontal
          format="percent"
          title="Model win probability — next stage"
          explain="Who does the model favour for this stage profile and why might that be?" />

<Table data={next_stage_favorites}
       format="win_pct=percent,podium_pct=percent"
       sort="rank asc" title="Top 12 picks" />
</Grid>

<Ask data={next_stage_favorites,next_stage_info} inline
     ask="Preview the next stage of the 2026 Tour using the model's favourites: name the top 3 picks, their specialist profiles, and what kind of finish the stage type suggests. 3-4 sentences." />

---

## 🎯 Stage-by-Stage Predictions for the Rest of the Tour

```sql prediction_heatmap connector=predictions
SELECT p.stage, p.rider, ROUND(p.win_probability * 100, 1) AS win_pct
FROM stage_predictions p
WHERE p.rider IN (
    SELECT rider FROM stage_predictions
    GROUP BY rider
    HAVING MAX(win_probability) >= 0.05
)
ORDER BY p.stage, p.win_probability DESC
```

<HeatmapChart data={prediction_heatmap} x="stage" y="rider" value="win_pct"
              title="Win probability (%) per rider per remaining stage"
              height="460"
              explain="Which riders' chances are concentrated on specific stages, and who is a threat everywhere?" />

```sql remaining_stage_picks connector=predictions
SELECT stage, date,
       start_location || ' → ' || end_location AS course,
       stage_type, distance_km,
       rider AS model_pick,
       ROUND(win_probability * 100, 1) AS win_pct
FROM stage_predictions
WHERE predicted_rank = 1
ORDER BY stage
```

<Table data={remaining_stage_picks}
       format="win_pct=percent"
       sort="stage asc" title="The model's pick for every remaining stage"
       row_link="/stages/{stage}" />

<sub>💡 Click any row for the full per-stage prediction breakdown.</sub>

---

## 👑 Final Podium Forecast

```sql gc_forecast connector=predictions
SELECT predicted_final_position AS predicted_final, rider, team,
       current_position, current_gap,
       ROUND(podium_probability * 100, 1) AS podium_pct
FROM gc_forecast
ORDER BY predicted_final_position
```

<Grid cols=2>
<Table data={gc_forecast}
       format="podium_pct=percent"
       sort="predicted_final asc" title="Predicted final GC (riders currently in the top 10)" />

<BarChart data={gc_forecast} x="rider" y="podium_pct" horizontal
          format="percent"
          title="Probability of finishing on the final podium in Paris"
          explain="Which riders outside the current top 3 does the model give a real podium chance, and who is expected to fade?" />
</Grid>

<sub>⚠️ **Honest caveat**: with only six Tours of training data, beating the "standings stay as they are" baseline on exact positions is genuinely hard — see the [methodology](/methodology) for the numbers. The podium probabilities are the more reliable signal.</sub>

---

## 👕 Jersey Projections — Who Wins in Paris?

```sql green_projection connector=predictions
SELECT projected_rank, rider, team, specialist,
       current_points, projected_additional_points, projected_total_points
FROM jersey_projections
WHERE classification = 'points' AND projected_rank <= 8
ORDER BY projected_rank
```

```sql polka_projection connector=predictions
SELECT projected_rank, rider, team, specialist,
       current_points, projected_additional_points, projected_total_points
FROM jersey_projections
WHERE classification = 'mountains' AND projected_rank <= 8
ORDER BY projected_rank
```

<Grid cols=2>
<BarChart data={green_projection} x="rider" y="current_points,projected_additional_points" stacked
          title="🟢 Green jersey: current + projected points"
          explain="The green jersey race is tight — who gains the most from the remaining sprint stages?" />

<BarChart data={polka_projection} x="rider" y="current_points,projected_additional_points" stacked
          title="🔴 Polka dot: current + projected points"
          explain="Can anyone realistically challenge for the mountains classification given the Alpe d'Huez double ahead?" />
</Grid>

<Ask data={green_projection,polka_projection} inline
     ask="In 3-4 sentences: who is projected to win the green and polka-dot jerseys of the 2026 Tour and how close are those races? Note that the projection adds expected finish points from the stage-winner model to the current standings." />

---

## 🔍 Rider Analysis — Form vs Expectation

```sql rider_analysis connector=predictions
SELECT rider, team, specialist,
       ROUND(AVG(win_probability) * 100, 2)    AS avg_win_pct,
       ROUND(MAX(win_probability) * 100, 1)    AS best_stage_pct,
       ROUND(AVG(podium_probability) * 100, 1) AS avg_podium_pct,
       COUNT(*) FILTER (WHERE predicted_rank <= 5) AS stages_in_top5_picks
FROM stage_predictions
GROUP BY rider, team, specialist
HAVING MAX(win_probability) >= 0.02
ORDER BY avg_win_pct DESC
LIMIT 25
```

<ScatterChart data={rider_analysis} x="best_stage_pct" y="avg_podium_pct"
              series="specialist"
              format="percent"
              title="Best single-stage win chance vs average podium chance"
              explain="Which riders are one-stage specialists versus consistent threats across many stages?" />

<Table data={rider_analysis}
       format="avg_win_pct=percent,best_stage_pct=percent,avg_podium_pct=percent"
       sort="avg_win_pct desc" page-size="10" title="Most dangerous riders for the remaining stages" />

---

## 📜 Historical Context (2020-2025)

```sql champions connector=historical
SELECT year,
       MAX(CASE WHEN classification = 'general'     THEN rider END) AS yellow,
       MAX(CASE WHEN classification = 'points'      THEN rider END) AS green,
       MAX(CASE WHEN classification = 'mountains'   THEN rider END) AS polka_dot,
       MAX(CASE WHEN classification = 'young rider' THEN rider END) AS white
FROM final_classifications
WHERE rank = 1
GROUP BY year
ORDER BY year DESC
```

<Table data={champions} sort="year desc" title="Jersey winners by year" />

```sql top_stage_winners connector=historical
SELECT rider, COUNT(*) AS stage_wins
FROM results
WHERE record = 'stage_result' AND position = 1
GROUP BY rider
ORDER BY stage_wins DESC
LIMIT 10
```

```sql stage_type_mix connector=historical
SELECT year, stage_type, COUNT(*) AS stages
FROM stages
GROUP BY year, stage_type
ORDER BY year, stage_type
```

<Grid cols=2>
<BarChart data={top_stage_winners} x="rider" y="stage_wins" horizontal
          title="Most stage wins, 2020-2025"
          explain="Pogačar's stage-win count towers over everyone — put it in context." />

<BarChart data={stage_type_mix} x="year" y="stages" series="stage_type" stacked
          title="Route composition by year"
          explain="How has the balance of flat, hilly, mountain and time-trial stages shifted across recent Tours?" />
</Grid>

<Ask data={champions,top_stage_winners} inline
     ask="Give 3 sentences of historical context for the 2026 Tour: the Pogačar-Vingegaard rivalry has decided the last six editions — what do the jersey winners and stage-win counts from 2020-2025 say about the era, and what would a 2026 Pogačar win mean (a record-tying 5th title)?" />

---

## 🎲 Model Scorecard — Honest Numbers

```sql model_performance connector=main
SELECT model_name, algorithm, target, headline
FROM model_performance
```

```sql winner_model_kpis connector=main
SELECT ROUND(top1_rate * 100, 1) AS top1_pct,
       ROUND(top3_rate * 100, 1) AS top3_pct,
       auc
FROM model_performance
WHERE model_name = 'Stage winner'
```

<Grid cols=3>
<Counter data={winner_model_kpis} column="top1_pct" format="percent" label="Winner picked correctly" />
<Counter data={winner_model_kpis} column="top3_pct" format="percent" label="Winner in model top-3" />
<Counter data={winner_model_kpis} column="auc" label="Ranking AUC" />
</Grid>

<Table data={model_performance}
       title="All models — leave-one-year-out cross-validation, scored on stages 9-21" />

<sub>🧪 Tour de France stages are genuinely hard to predict — long breakaways decide many of them. These numbers are cross-validated on held-out years, not cherry-picked. Full details on the [methodology page](/methodology).</sub>

---

## 📡 Data Freshness & Sources

```sql data_freshness connector=main
SELECT source, url, last_fetched, license
FROM data_freshness
```

<Table data={data_freshness} />

<sub>⏰ Last refreshed: <Value data={race_overview} column="last_refreshed" /> — pipeline: `scripts/fetch_tdf_data.py` (Wikipedia wikitext → Parquet) then `scripts/train_predictions.py` (train + predict). Built with [Dashdown](https://github.com/DirendAI/dashdown).</sub>
