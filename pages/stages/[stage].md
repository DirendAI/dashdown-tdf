---
title: Stage detail
description: Result or ML prediction for a single stage of the 2026 Tour de France.
header: true
static_paths:
  query: SELECT range::INT AS stage FROM range(1, 22)
---

# 🚴 Stage <Value data={stage_info} column="stage" />: <Value data={stage_info} column="start_location" /> → <Value data={stage_info} column="end_location" />

```sql stage_info connector=live_2026
SELECT stage, date, start_location, end_location, distance_km, stage_type,
       winner, winner_team, completed,
       climbs_hc, climbs_cat1, climbs_cat2, climbs_cat3, climbs_cat4
FROM stages
WHERE stage = CAST('${stage}' AS INTEGER)
```

<Grid cols=4>
<Counter data={stage_info} column="date" label="Date" />
<Counter data={stage_info} column="stage_type" label="Type" />
<Counter data={stage_info} column="distance_km" format="number" label="Distance" suffix=" km" />
<Counter data={stage_info} column="winner" label="Winner" />
</Grid>

<sub>Climbs mentioned in the roadbook summary — HC: <Value data={stage_info} column="climbs_hc" />, Cat 1: <Value data={stage_info} column="climbs_cat1" />, Cat 2: <Value data={stage_info} column="climbs_cat2" />, Cat 3: <Value data={stage_info} column="climbs_cat3" />, Cat 4: <Value data={stage_info} column="climbs_cat4" /></sub>

---

## 🏁 Result

```sql stage_result connector=live_2026
SELECT position, rider, team, nationality, time_raw AS time
FROM stage_results
WHERE stage = CAST('${stage}' AS INTEGER)
ORDER BY position
```

<Table data={stage_result}
       sort="position asc" title="Official top 10"
       empty_message="This stage hasn't been raced yet — see the model's predictions below." />

```sql gc_after connector=live_2026
SELECT position, rider, team,
       ROUND(gap_seconds / 60.0, 2) AS minutes_behind
FROM gc_evolution
WHERE stage = CAST('${stage}' AS INTEGER)
ORDER BY position
```

<BarChart data={gc_after} x="rider" y="minutes_behind" horizontal
          title="GC after this stage — minutes behind yellow"
          empty_message="No GC standings yet for this stage." />

---

## 🔮 Model Prediction

```sql stage_prediction connector=predictions
SELECT predicted_rank AS rank, rider, team, specialist,
       ROUND(win_probability * 100, 1)    AS win_pct,
       ROUND(podium_probability * 100, 1) AS podium_pct
FROM stage_predictions
WHERE stage = CAST('${stage}' AS INTEGER)
ORDER BY predicted_rank
LIMIT 15
```

<Grid cols=2>
<BarChart data={stage_prediction} x="rider" y="win_pct" horizontal
          format="percent"
          title="Win probability (top 15)"
          empty_message="No prediction for this stage — it was already raced before the model's cutoff, or it is the team time trial." />

<Table data={stage_prediction}
       format="win_pct=percent,podium_pct=percent"
       sort="rank asc" title="The model's picks"
       empty_message="No prediction for this stage." />
</Grid>

<Ask data={stage_prediction,stage_info} inline
     ask="If this stage has prediction rows, preview it in 2-3 sentences (top picks and why the stage type suits them). If the prediction table is empty but there is a winner in the stage info, recap who won instead. Be concrete." />

---

[← Back to the dashboard](/)
