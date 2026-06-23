# 06 — Branch Comparison & Merge (best of both)

Two solutions were built independently for this problem:
- **`main`** (teammate) and **`kanan-dev`** (this branch). Both converged on the same 4-layer
  architecture (clean → EIS → clearance model → ILP allocation → Streamlit map), which validates the design.

## Where each branch led

| Dimension | `main` | `kanan-dev` (before merge) |
|---|---|---|
| Clearance model | 1 LightGBM, fixed params, single 80/20 split | model zoo + **k-fold CV** + stacking + Optuna |
| EIS normalization | MinMaxScaler (outlier-fragile) | **percentile rank** (robust) |
| EIS validation | none | **Spearman 0.70**, AUC 0.89 vs observed severity |
| Simulator | `random.uniform()` severity | **runs trained models** (EIS 17@2am vs 78@9am) |
| Clearance output | point estimate | **P50 / P90** quantiles |
| Forecasting (L1) | ❌ | ✅ Poisson counts + hotspots + Hawkes |
| Learning loop (L4) | ✅ implemented | ❌ (described only) |
| Spatial unit | ✅ H3 hexagons | corridor + KMeans |
| Diversion routing | ✅ real routes (Mappls) | centroid-nearest heuristic |
| Leakage discipline | unchecked | **leakage hunt** (dropped end-coords @ AUC 0.976) |
| Secrets | ⚠️ hard-coded API key | none |

## What was merged INTO `kanan-dev`
We kept our stronger ML core and ported the three real wins from `main` — each done better:

1. **L4 learning loop** ([src/learn.py](../src/learn.py)) — predicted-vs-actual playbook keyed by
   `cause × H3 hex`, with model-bias and drift→retrain flags. **Upgrade:** predictions are leak-free
   **out-of-fold** (not in-sample like main), so the measured bias is honest. It surfaced that the
   clearance model systematically under-predicts infrastructure events (potholes **+8.0 h**,
   water-logging **+7.1 h** bias) while breakdowns are well-calibrated (+0.06 h) — a real, actionable
   finding. Outputs `predictions/learning_playbook.csv`.

2. **H3 hexagonal binning** ([src/data_prep.py](../src/data_prep.py)) — `hex_id` at resolution 8
   (~0.7 km), 661 occupied cells. Used as the spatial key for the playbook and hotspots.

3. **Real diversion routing** ([src/route_diversion.py](../src/route_diversion.py)) — actual
   road-network routes drawn on the simulator map. **De-risked:** uses the **keyless** public OSRM
   server (no committed secret, unlike main's hard-coded key), reads an `OSRM_URL` override from env,
   and degrades gracefully to the corridor heuristic when offline.

All three are wired into the dashboard: a new **🔁 Learning Loop** tab and a live diversion-route map
in the **🎯 Event Simulator**. The orchestrator now runs 9 stages incl. `L4 Learning loop`.

## Net result
The merged branch has, in one solution: k-fold model zoo, validated+robust EIS, real-ML simulator,
forecasting, **the learning loop**, **H3 spatial granularity**, and **real routing without a leaked
key** — strictly dominating either branch alone.
