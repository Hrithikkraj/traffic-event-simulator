# Flipkart Gridlock 2.0 — Event-Driven Congestion

Solution documentation for the **Flipkart Gridlock Hackathon 2.0 — Round 2** problem:
*Event-Driven Congestion (Planned & Unplanned).*

| Doc | What's inside |
|-----|---------------|
| [01 — Problem & Goal](01-problem-and-goal.md) | The problem statement, constraints, and what a winning solution must do |
| [02 — Data Analysis](02-data-analysis.md) | EDA findings on the ASTraM dataset — the insights that shape the approach |
| [03 — Solution Architecture](03-solution-architecture.md) | The 4-layer system (Forecast → Impact → Prescribe → Learn) + Event Impact Score |
| [04 — Build & Results](04-results.md) | The ML core: CV results, 20 techniques applied, leakage hunt, EIS validation |
| [05 — Full System & Demo](05-system-and-demo.md) | L1 forecasting (Poisson/Hawkes), L3 prescriptive + ILP optimization, the Streamlit demo |

**Code:** [src/](../src/) — build everything with `bash run.sh src/run_all.py`, then launch the dashboard with `bash run_app.sh`. Outputs land in `outputs/`.

**Dataset:** [`Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv`](../Astram%20event%20data_anonymized%20-%20Astram%20event%20data_anonymizedb40ac87.csv) — 8,173 rows × 46 cols, Bengaluru ASTraM traffic-management incident log (2023-11-09 → 2024-04-08).

> These docs mirror the persistent project memory in `~/.claude/projects/.../memory/`, which is auto-loaded into context each session.
