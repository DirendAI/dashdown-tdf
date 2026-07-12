---
title: Stages
subtitle: All 21 stages — results so far, predictions for what's ahead
description: >
  Every stage of the 2026 Tour de France: official results for raced stages,
  ML win-probability picks for the upcoming ones. Click a stage for details.
sidebar_position: 2
icon: "🗺️"
header: true
---

# 🗺️ The 21 Stages of the 2026 Tour

```sql race_progress connector=live_2026
SELECT
    COUNT(*) FILTER (WHERE completed)                                  AS stages_raced,
    COUNT(*) FILTER (WHERE NOT completed)                              AS stages_to_go,
    COUNT(*) FILTER (WHERE stage_type = 'Mountain' AND NOT completed)  AS mountain_stages_left,
    ROUND(SUM(distance_km) FILTER (WHERE NOT completed), 1)            AS km_left
FROM stages
```

<Grid cols=4>
<Counter data={race_progress} column="stages_raced" label="Stages Raced" suffix=" / 21" />
<Counter data={race_progress} column="stages_to_go" label="Stages To Go" />
<Counter data={race_progress} column="mountain_stages_left" label="Mountain Stages Left" />
<Counter data={race_progress} column="km_left" format="number" label="Distance Left" suffix=" km" />
</Grid>

```sql route_profile connector=live_2026
SELECT stage, stage_type, distance_km
FROM stages
ORDER BY stage
```

<BarChart data={route_profile} x="stage" y="distance_km" series="stage_type" stacked
          title="The route at a glance — stage distance, coloured by type"
          explain="Where are the remaining mountain stages and the time trial in the final two weeks?" />

---

## ✅ Raced so far

*Click any row for the full result and post-stage GC.*

```sql completed_stages connector=live_2026
SELECT stage, date,
       start_location || ' → ' || end_location AS course,
       stage_type, distance_km, winner, winner_team
FROM stages
WHERE completed
ORDER BY stage
```

<Table data={completed_stages} sort="stage asc" row_link="/stages/{stage}" />

---

## 🔮 Still to come — the model's picks

*Click any row for the model's full ranking of every rider on that stage.*

```sql upcoming_stages connector=predictions
SELECT stage, date,
       start_location || ' → ' || end_location AS course,
       stage_type, distance_km,
       rider AS model_pick,
       ROUND(win_probability * 100, 1) AS win_pct
FROM stage_predictions
WHERE predicted_rank = 1
ORDER BY stage
```

<Table data={upcoming_stages} format="win_pct=percent"
       sort="stage asc" row_link="/stages/{stage}" />

<Ask data={completed_stages,upcoming_stages} inline
     ask="In 3-4 sentences, tell the story of this Tour so far from the completed stages (who has won what) and point out the biggest upcoming battlegrounds among the remaining stages — note the stage 16 time trial and the back-to-back Alpe d'Huez finishes on stages 19 and 20." />

---

[← Back to the dashboard](/)
