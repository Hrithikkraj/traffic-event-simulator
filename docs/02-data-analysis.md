# 02 — Data Analysis (ASTraM event dataset)

**Source:** [`Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv`](../Astram%20event%20data_anonymized%20-%20Astram%20event%20data_anonymizedb40ac87.csv)
**Shape:** 8,173 rows × 46 columns · **Span:** 2023-11-09 → 2024-04-08 (~53 events/day) · **City:** Bengaluru (lat 12.80–13.27, lon 77.31–77.77)

These findings are the competitive edge — most teams will misread the dataset.

## The 8 insights that shape the approach

1. **No congestion measurement exists.** No speed / volume / delay / queue field. This is an **operational incident log**, not traffic-flow data. → The impact target must be *engineered* (this is the crux — see [03](03-solution-architecture.md)).

2. **Events peak at 2 AM, collapse 5–9 PM** — the opposite of rush hour. Cause: 60% of events are `vehicle_breakdown`, dominated by night-time freight movement (trucks restricted to enter the city at night). → Strong pitch hook that proves deep data understanding.

3. **Planned (467) vs Unplanned (7,706) have different schemas.**
   - Planned: `end_datetime` populated 99.8% — the end is *known in advance*.
   - Unplanned: `veh_type` 63%, `closed_datetime` 40% — clearance time is the predictable target.
   - → Build **two pipelines**: planned = proactive scheduling, unplanned = real-time triage. Maps 1:1 to "Planned & Unplanned."

4. **`corridor` is the best spatial unit** — 99.8% populated, 22 values = real arterials: Mysore Rd, Bellary Rd (airport), Tumkur Rd, Hosur Rd, ORR N/E/W segments, Old Madras Rd, Magadi Rd, Bannerghatta Rd (`Non-corridor` = 3,124). Matches how traffic police organize.

5. **Closure rate varies sharply by cause** — direct signal for the barricade/diversion recommender:

   | Cause | Road-closure rate |
   |-------|------|
   | vip_movement | 80% |
   | public_event | 46% |
   | protest | 40% |
   | tree_fall | 39% |
   | construction | 26% · procession 26% |
   | vehicle_breakdown | 4% |

6. **Clearance time is predictable.** `bmtc_bus` & trucks ~0.8h vs cars ~0.49h. Causes split into **transient** (<1h: accident, procession, breakdown) vs **persistent infra tickets** (days–weeks: potholes, construction). → Must separate these two regimes.

7. **`description` is bilingual English + Kannada** free text (e.g. "Cricket Match at M Chinnaswamy Stadium"; "ಬಿಎಂಟಿಸಿ ಬಸ್ ಕೆಟ್ಟು ನಿಂತಿದೆ"). → A multilingual NLP layer is a genuine differentiator.

8. **Real demand spikes:** 214 events on 2024-03-07, 200 on 2023-12-16 vs median 49/day. → Use a spike day as the demo centerpiece.

## Data quality to fix (shows rigor)
- Case-duplicate causes: `Debris` / `debris`.
- 3 negative durations; 143 events open >30 days (infra tickets, not live congestion).
- `zone` 58% missing → impute via spatial join to BBMP ward shapefile.
- Near-empty columns to drop: `direction`, `map_file`, `comment`, `meta_data`.

## ⚠️ Leakage warning
These fields are only known **after** an event and must be excluded from impact-at-creation models:
`closed_datetime`, `resolved_*`, `closed_by_id`, `status`, `modified_datetime`.
