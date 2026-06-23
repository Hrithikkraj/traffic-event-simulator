# Gridlock — Hackathon Submission

**Team TrafficSolvers** · Flipkart Gridlock Hackathon 2.0 — Round 2
Ryan Bhan (Lead, IIIT-D) · Kanan Mittal (IGDTUW) · Aditya Rawat (IIIT-D) · Hrithik Raj (IIIT-D)

---

## Title
**Gridlock — Event-Driven Congestion Intelligence**

## One-line
Forecast event-related traffic impact, quantify it, prescribe the optimal manpower/barricade/diversion plan, and learn after every event — built on the Bengaluru ASTraM incident dataset.

## Description (paste into the platform)
Political rallies, festivals, sports, construction and sudden gatherings cause localized traffic breakdowns, yet impact is never quantified in advance, deployment is experience-driven, and there is no post-event learning. The ASTraM data is an **incident log with no congestion field** — so we *engineer* the missing target: a validated **Event Impact Score** (expected vehicle-hours of delay; Spearman 0.70 vs observed severity). Around it we built a 4-layer system: **L1 Forecast** (LightGBM-Poisson event counts +16.7% over baseline, empirical-Bayes hotspots, Hawkes self-excitation), **L2 Impact** (clearance-time quantile regression + a road-closure classifier, PR-AUC 0.471 = +469% over baseline, 10-model zoo with k-fold CV, stacking, Optuna, and an explicit leakage hunt), **L3 Prescribe** (per-event plan + city-wide officer optimization via ILP that exposes the resource deficit), and **L4 Learn** (predicted-vs-actual playbook with drift detection). A live Streamlit dashboard ties it together: simulator, risk map, surge-day replay, forecast, and learning loop.

## Key results
| Component | Result |
|---|---|
| Event Impact Score | Spearman **0.70**, AUC **0.89** (flags top-10% impact) |
| Road-closure classifier | PR-AUC **0.471** (+469% over prevalence baseline) |
| Clearance-time regression | MAE **2.88 h** (blended, 10-model k-fold) |
| Event-count forecast | **+16.7%** over lag-7 baseline (temporal split) |
| Accident self-excitation | Hawkes branching ratio **0.31** |

## Links
- **GitHub repo:** https://github.com/Hrithikkraj/traffic-event-simulator/tree/kanan-dev
- **Pitch deck (PDF):** https://github.com/Hrithikkraj/traffic-event-simulator/blob/kanan-dev/Gridlock_Pitch_Deck.pdf
- **Pitch deck (PPTX):** https://github.com/Hrithikkraj/traffic-event-simulator/blob/kanan-dev/Gridlock_Pitch_Deck.pptx
- **Demo video:** https://github.com/Hrithikkraj/traffic-event-simulator/blob/kanan-dev/Gridlock_Demo.mp4
  *(plays inline on GitHub; for a clean embeddable URL, also upload to YouTube → Unlisted)*
- **Live app:** deploy in 2 minutes (below), then paste the `…streamlit.app` URL here: `__________`

## Deploy the live app (Streamlit Community Cloud — free)
1. Go to https://share.streamlit.io → **New app**.
2. Repo `Hrithikkraj/traffic-event-simulator`, branch `kanan-dev`, main file `src/app.py`.
3. **Advanced settings → Python 3.12** (the committed model pickles require it).
4. Deploy. `requirements.txt` + `packages.txt` are already set; pre-built model artifacts are committed, so it boots without retraining.

## Run locally
```bash
pip install -r requirements-dev.txt        # full pipeline + tooling
brew install libomp                          # macOS only (LightGBM/XGBoost)
python src/run_all.py                        # build models/EIS/forecasts (~14 min)
bash run_app.sh                              # launch the dashboard
```

## Docs
`docs/` — problem, data analysis, architecture, results, branch comparison & merge.
