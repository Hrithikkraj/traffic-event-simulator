# 05 — Full System (L1 + L3) & Demo

The complete 4-layer system is now built: **Forecast (L1) → Impact (L2/EIS) → Prescribe (L3) → Demo**.

## Run it
```bash
bash run.sh src/run_all.py     # build everything (models, EIS, forecasts) ~10 min
bash run_app.sh                # launch the dashboard
```

## L1 — Spatiotemporal forecasting (`src/forecast.py`)
| Component | Method | Result |
|-----------|--------|--------|
| Corridor × day event-count forecast | LightGBM **Poisson** on lag (1, 7) + rolling (7, 30) + calendar | MAE **1.85**, **16.7%** better than the lag-7 baseline (temporal split) |
| Hotspot risk surface | Empirical-Bayes-smoothed corridor × hour rates | `predictions/hotspot_corridor_hour.csv` |
| Accident **self-excitation** | Univariate exp-kernel **Hawkes** (MLE, Ogata recursion) | branching ratio **0.31**, ~7-min half-life → short-burst clustering (secondary incidents / co-reporting) |

*Honest note:* the Hawkes β pins at its bound — accidents cluster on a very short timescale, so the **hotspot + Poisson** models carry the real spatial forecasting; Hawkes is reported as an exploratory contagion measure.

## L3 — Prescriptive layer (`src/prescribe.py`)
**Per-event plan** (`recommend`): officers, barricade units, diversion (→ nearest alternate arterial by centroid distance), and an action checklist — driven by the validated EIS tier + closure probability. *Manpower data is too sparse (1.6%) to learn, so this rule is transparent and defensible rather than a black box.*

**City-wide optimization** (`allocate`) — the deliverable most teams never reach:
- **Priority doctrine** — cover highest-impact events first (operational triage).
- **Efficiency doctrine** — ILP 0/1-knapsack (PuLP/CBC) maximizing total mitigated impact.
- Reports the **officer deficit** — e.g. the March-7-2024 surge (214 events) needs ~1,096 officers; at 120 you cover ~7% and 9 high-impact events go unmet. *This quantifies the under-resourcing the problem statement names.*

The two doctrines deliberately disagree (priority covers the VIP for 15% total impact; efficiency covers 41% but skips 6 Critical events) — showing the triage trade-off explicitly is itself the insight.

## Inference bridge (`src/inference.py`)
`score_event(cause, corridor, hour, dow, …)` builds a full feature row from operator-known inputs, runs the saved closure + clearance-quantile models, and maps to EIS via persisted artifacts. Powers the simulator. Demonstration:

| Scenario | EIS | Tier |
|----------|-----|------|
| Vehicle breakdown, Tumkur Rd, **2 AM** | 17 | Low |
| Same breakdown, Hosur Rd, **9 AM rush** | 78 | Medium |
| VIP movement, Bellary Rd, 6 PM | 99.7 | Critical |
| Planned rally, CBD, 6 PM (4 h) | 99.6 | Critical |

## The demo (`src/app.py`, Streamlit + pydeck + Plotly)
Four tabs:
1. **🎯 Event Simulator** — inputs → EIS gauge, clearance P50/P90, closure %, full deployment plan. *The "what-if a rally on Sunday 6 PM" moment.*
2. **🗺️ City Risk Map** — all 8,173 events on a Bengaluru pydeck map, colored by tier, filterable.
3. **📅 Surge-Day Replay** — pick a real day (e.g. 2024-03-07), set an officer budget + doctrine → live allocation, deficit, unmet-events warning.
4. **📈 Forecast & Hotspots** — corridor × hour risk heatmap, Hawkes contagion stat, the 2-AM-peak explainer.

Boots clean (verified via health check + full tab-logic smoke test).

## Demo script (4 min, in order)
1. Open Tab 4 → "Why do events peak at 2 AM?" (the freight-night insight).
2. Tab 1 → score a night breakdown (Low) then flip to 9 AM rush (jumps to High) — *impact is contextual*.
3. Tab 1 → simulate a VIP rally → instant Critical + officers + barricades + diversion.
4. Tab 3 → replay 2024-03-07 (214 events) → show the 976-officer deficit and the triage.
5. Close: "Forecast → quantify → prescribe → learn — and it caught its own data leakage." (see [04](04-results.md)).
