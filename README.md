# 🚦 Gridlock — Event-Driven Congestion Intelligence

Solution for **Flipkart Gridlock Hackathon 2.0 — Round 2**: *Event-Driven Congestion (Planned & Unplanned).*
Built on the Bengaluru **ASTraM** incident dataset (8,173 events × 46 cols).

A 4-layer decision-support system:

> **FORECAST** (where/when/how many) → **QUANTIFY IMPACT** (Event Impact Score) → **PRESCRIBE** (manpower, barricades, diversions) → **LEARN**

## Quickstart
```bash
# 1. install deps (LightGBM/XGBoost need libomp: `brew install libomp` on macOS)
pip install -r requirements.txt

# 2. build everything — models, Event Impact Score, forecasts (~10 min)
bash run.sh src/run_all.py

# 3. launch the dashboard
bash run_app.sh
```
`run.sh` / `run_app.sh` set `DYLD_LIBRARY_PATH` so LightGBM/XGBoost find libomp on macOS.

## What's inside
| Layer | Module | Highlights |
|-------|--------|-----------|
| L0 Data | [src/data_prep.py](src/data_prep.py) | cleaning, leakage-safe feature engineering, EN+Kannada text features |
| L1 Forecast | [src/forecast.py](src/forecast.py) | LightGBM-Poisson corridor counts (16.7% over baseline), EB hotspot surface, Hawkes self-excitation |
| L2 Impact | [src/impact_score.py](src/impact_score.py) | **Event Impact Score** validated vs observed severity (Spearman 0.70, AUC 0.89) |
| L2 Models | [src/train_*.py](src/) | clearance-time quantile regression, road-closure classifier — many models, k-fold CV |
| L3 Prescribe | [src/prescribe.py](src/prescribe.py) | per-event plan + city-wide officer optimization (ILP knapsack + priority triage) |
| Inference | [src/inference.py](src/inference.py) | score any hypothetical event at creation time |
| Demo | [src/app.py](src/app.py) | Streamlit + pydeck: simulator, risk map, surge-day replay, forecast |

## Docs
Full write-up in [docs/](docs/) — problem, data analysis, architecture, results, and the demo script.

## Data
`Astram event data_anonymized - ...csv` is the anonymized competition dataset. Generated models/figures land in `outputs/` (git-ignored; rebuild with `run_all.py`).
