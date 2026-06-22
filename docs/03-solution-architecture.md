# 03 — Solution Architecture

Grounded in [02 — Data Analysis](02-data-analysis.md). Solves [01 — Problem & Goal](01-problem-and-goal.md).

## The reframe
This is **not** congestion prediction — it's a 3-stage decision-support system plus a learning loop:

> **FORECAST → QUANTIFY IMPACT → PRESCRIBE → LEARN**

Differentiator vs the field: most teams only *predict*. We *prescribe under constraints* and *learn post-event*.

## The spine — Event Impact Score (EIS)
The target doesn't exist in the data, so engineer it as **expected vehicle-hours of delay** (a transport-engineering unit judges trust):

```
EIS ≈ Clearance_Duration × Spatial_Reach × Baseline_Flow(corridor, hour, dow) × Closure_Severity
```

- Normalize to 0–100; tier into **Low / Medium / High / Critical**.
- **Validate** by correlating EIS with observed proxies (closure rate, priority, duration) on a held-out period.
- **Lock the EIS definition first — everything hangs on it.**

## System diagram

```
HISTORICAL LOG ─┐
REAL-TIME FEED ─┤→ L0 FOUNDATION (clean • spatial-join zone/ward • H3+corridor bins • calendar • weather)
EXTERNAL CAL/WX ┘        │
                ┌────────┴────────┐
                ▼                 ▼
        L1 FORECAST          L2 IMPACT
        where/when/what  →   clearance qreg + closure clf + priority clf
                                  │ → Event Impact Score
                                  ▼
                           L3 PRESCRIBE
                           manpower • barricades • diversions
                           + city-wide resource OPTIMIZATION
                                  ▼
                           L4 LEARN (predicted vs actual → retrain → update playbook)
                                  ▼
                  DASHBOARD: risk map • event simulator • deployment plans
```

## Layers

**L0 — Foundation.** Clean/dedupe, spatial-join zone/ward, bin into H3 (~500m) + corridor, join calendar + weather.

**L1 — Forecast.**
- *Unplanned:* LightGBM **Poisson** regressor on spatiotemporal features + **Hawkes self-exciting process** for accident clustering/aftershocks.
- *Planned:* calendar-prior model mining recurring venues/festivals/VIP routes.

**L2 — Impact.**
- Clearance-time **quantile** regressor (P50/P90; target `log(closed − start)`).
- Road-closure binary classifier (optimize **PR-AUC**; ~8% positive).
- Priority classifier → combine into **EIS**.

**L3 — Prescribe.**
- Manpower / barricade / diversion rules from EIS tier + closure prediction.
- Diversions on the real OSM road graph (OSMnx / networkx / OSRM).
- **Killer feature — city-wide resource optimization:** ILP / greedy knapsack that allocates a finite officer pool to **maximize mitigated impact** across simultaneous events.

**L4 — Learn.** After each close, log predicted-vs-actual → periodic retrain → update a living **cause × location → action playbook**. Closes the brief's "no post-event learning" gap.

## Rigor (the credibility moat)
- **Leakage control:** exclude post-event fields (see [02 leakage warning](02-data-analysis.md#-leakage-warning)).
- **Time-split CV:** train Nov 2023–Feb 2024, validate Mar–Apr 2024. Never random.
- **Spatial holdout** to prove hotspot generalization.
- **Beat baselines:** report lift over "historical average by cause × corridor × hour."
- **Metrics:** pinball/MAE (clearance), PR-AUC (closure), Poisson deviance (forecast) + one business metric (% of high-impact events pre-positioned).

## Stack & demo
- **Stack:** Python · LightGBM · statsmodels · H3 · OSMnx/networkx/OSRM · PuLP/OR-Tools · FastAPI · Streamlit + pydeck/kepler.gl.
- **Demo (4 min):** hook with the 2 AM insight → live risk map → replay the 2024-03-07 surge (214 events) → **event simulator** (rally → instant EIS + deployment plan + diversion map drawn on real roads) → show the learning loop updating the playbook.

## Open next steps
1. **EIS deep-dive** — precise formula, full feature list, validation plan *(recommended first)*.
2. **L1 forecasting** — spatiotemporal feature set + time-split CV scheme.
3. **Optimization layer** — objective, constraints, solver.
