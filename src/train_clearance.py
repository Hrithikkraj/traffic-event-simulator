"""T1 - Clearance-time regression (how long until an unplanned event clears).

Target: log1p(hours) for unplanned events with 0 < clearance <= 72h.
Techniques: 10-model zoo, k-fold OOF, stacked ensemble, temporal holdout,
quantile regression (P50/P90) for "likely vs worst-case" clearance.

Run: bash run.sh src/train_clearance.py
"""
import numpy as np
import pandas as pd
import joblib
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.metrics import mean_pinball_loss, mean_absolute_error
import lightgbm as lgb

import config as C
import cv_utils as U


def main():
    df = pd.read_pickle(C.PROCESSED)
    mask = df["is_clear_label"] == 1
    X = df.loc[mask, C.ALL_FEATS].reset_index(drop=True)
    y = df.loc[mask, "y_clear_log"].reset_index(drop=True)
    print(f"Clearance regression: n={len(X)}  median={np.expm1(y).median():.2f}h  "
          f"mean={np.expm1(y).mean():.2f}h")

    # ---- baseline: predict global median (log)
    base_pred = np.full(len(y), y.median())
    base_mae_h = mean_absolute_error(np.expm1(y), np.expm1(base_pred))
    print(f"\nBaseline (median) MAE_hours = {base_mae_h:.3f}")

    # ---- k-fold across the model zoo
    print(f"\n=== {C.N_SPLITS}-fold CV (regressors) ===")
    table, oof = U.kfold_regression(U.get_regressors(), X, y)

    # ---- stacked ensemble (Ridge meta on OOF preds, itself k-folded)
    oof_df = pd.DataFrame(oof)
    cv = KFold(n_splits=C.N_SPLITS, shuffle=True, random_state=C.SEED)
    stack_oof = cross_val_predict(Ridge(alpha=1.0), oof_df.values, y, cv=cv, n_jobs=1)
    sm = U.reg_metrics(y, stack_oof)
    print(f"\n  STACK(Ridge)  MAE_h={sm['MAE_hours']:.3f}  MedAE_h={sm['MedAE_hours']:.3f}  R2_log={sm['R2_log']:.3f}")

    # ---- simple blend of top-3 by MAE
    top3 = table.head(3).index.tolist()
    blend = oof_df[top3].mean(axis=1).values
    bm = U.reg_metrics(y, blend)
    print(f"  BLEND top3 {top3}  MAE_h={bm['MAE_hours']:.3f}")

    # add ensembles to table
    table.loc["STACK_ridge"] = {**sm}
    table.loc["BLEND_top3"] = {**bm}
    table = table.sort_values("MAE_hours")
    lift = (base_mae_h - table["MAE_hours"].min()) / base_mae_h * 100
    print(f"\nBest MAE_hours = {table['MAE_hours'].min():.3f}  "
          f"({lift:.1f}% better than baseline)")

    # ---- temporal holdout (train past -> predict future)
    tr, te = U.time_split(df.loc[mask].reset_index(drop=True),
                          pd.Series(True, index=range(len(X))))
    best_name = table.index[0] if table.index[0] not in ("STACK_ridge", "BLEND_top3") else table.index[2]
    best_model = U.get_regressors()[best_name]
    best_model.fit(X[tr], y[tr])
    ts_pred = best_model.predict(X[te])
    ts = U.reg_metrics(y[te], ts_pred)
    print(f"\n=== Temporal holdout (train<{C.TIME_SPLIT_DATE}, n_tr={tr.sum()}, n_te={te.sum()}) ===")
    print(f"  {best_name}: MAE_hours={ts['MAE_hours']:.3f}  R2_log={ts['R2_log']:.3f}")

    # ---- quantile regression: P50 (likely) and P90 (worst-case)
    print("\n=== Quantile regression (pinball loss, k-fold) ===")
    quant = {}
    for a in (0.5, 0.9):
        qm = U.pipe(lgb.LGBMRegressor(objective="quantile", alpha=a, n_estimators=500,
                                      learning_rate=0.03, num_leaves=48, subsample=0.8,
                                      colsample_bytree=0.8, n_jobs=-1, random_state=C.SEED,
                                      verbose=-1))
        qp = cross_val_predict(qm, X, y, cv=cv, n_jobs=1)
        pin = mean_pinball_loss(y, qp, alpha=a)
        quant[a] = qp
        print(f"  P{int(a*100)}: pinball={pin:.4f}  median_pred={np.expm1(np.median(qp)):.2f}h")
    cover = np.mean(np.expm1(y) <= np.expm1(quant[0.9]))
    print(f"  P90 empirical coverage = {cover*100:.1f}% (target ~90%)")

    # ---- fit & save P50/P90 quantile models (for "likely vs worst-case" at inference)
    for a, tag in [(0.5, "q50"), (0.9, "q90")]:
        qm = U.pipe(lgb.LGBMRegressor(objective="quantile", alpha=a, n_estimators=500,
                                      learning_rate=0.03, num_leaves=48, subsample=0.8,
                                      colsample_bytree=0.8, n_jobs=-1, random_state=C.SEED,
                                      verbose=-1))
        qm.fit(X, y)
        joblib.dump(qm, C.MODEL_DIR / f"clearance_{tag}.pkl")

    # ---- fit final model on all data, save
    final = U.get_regressors()[best_name]
    final.fit(X, y)
    joblib.dump(final, C.MODEL_DIR / "clearance_best.pkl")
    table.to_csv(C.METRIC_DIR / "clearance_cv.csv")
    np.save(C.PRED_DIR / "clearance_oof.npy", oof_df.values)
    print(f"\nSaved -> models/clearance_best.pkl ({best_name}), metrics/clearance_cv.csv")
    print("\n" + table.round(4).to_string())


if __name__ == "__main__":
    main()
