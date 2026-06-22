"""T2 - Road-closure classification (will this event need barricading/diversion?).

Target: requires_road_closure (8.3% positive -> imbalanced). All 8,173 rows.
Techniques: 10-model zoo + SMOTE variant, k-fold OOF, stacked ensemble,
probability calibration (for decision thresholds), temporal holdout.

Run: bash run.sh src/train_closure.py
"""
import numpy as np
import pandas as pd
import joblib
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import average_precision_score, brier_score_loss
from imblearn.pipeline import Pipeline as ImbPipeline
from imblearn.over_sampling import SMOTE
import lightgbm as lgb

import config as C
import cv_utils as U


def main():
    df = pd.read_pickle(C.PROCESSED)
    X = df[C.ALL_FEATS].reset_index(drop=True)
    y = df["y_closure"].reset_index(drop=True)
    pos = y.mean()
    spw = (1 - pos) / pos
    print(f"Closure classification: n={len(X)}  positives={int(y.sum())} ({pos*100:.1f}%)  "
          f"scale_pos_weight={spw:.1f}")

    base_pr = average_precision_score(y, np.full(len(y), pos))
    print(f"Baseline PR-AUC (prevalence) = {base_pr:.3f}")

    print(f"\n=== {C.N_SPLITS}-fold CV (classifiers, imbalance-weighted) ===")
    models = U.get_classifiers(scale_pos_weight=spw)

    # extra technique: SMOTE + LightGBM (resample minority inside CV folds)
    models["LGBM+SMOTE"] = ImbPipeline([
        ("prep", U.build_preprocessor(scale=False)),
        ("smote", SMOTE(random_state=C.SEED, k_neighbors=5)),
        ("model", lgb.LGBMClassifier(n_estimators=600, learning_rate=0.03, num_leaves=48,
                                     subsample=0.8, colsample_bytree=0.8, n_jobs=-1,
                                     random_state=C.SEED, verbose=-1)),
    ])

    table, oof = U.kfold_classification(models, X, y)

    # ---- stacked ensemble (logistic meta on OOF probabilities)
    oof_df = pd.DataFrame(oof)
    cv = StratifiedKFold(n_splits=C.N_SPLITS, shuffle=True, random_state=C.SEED)
    stack_oof = cross_val_predict(LogisticRegression(max_iter=2000), oof_df.values, y,
                                  cv=cv, method="predict_proba", n_jobs=1)[:, 1]
    sm = U.clf_metrics(y, stack_oof)
    sm["model"] = "STACK_logit"
    print(f"\n  STACK(logit)  ROC={sm['ROC_AUC']:.3f}  PR={sm['PR_AUC']:.3f}  F1*={sm['F1@best']:.3f}")
    table.loc["STACK_logit"] = {k: v for k, v in sm.items() if k != "model"}
    table = table.sort_values("PR_AUC", ascending=False)

    best_name = table.index[0]
    lift = (table["PR_AUC"].max() - base_pr) / base_pr * 100
    print(f"\nBest PR-AUC = {table['PR_AUC'].max():.3f} ({best_name})  "
          f"{lift:.0f}% over prevalence baseline")

    # ---- probability calibration (decisions depend on reliable probabilities)
    base_model = models.get(best_name, models["LightGBM"])
    raw_p = oof.get(best_name, oof["LightGBM"])
    cal = CalibratedClassifierCV(models["LightGBM"], method="isotonic", cv=3)
    cal_p = cross_val_predict(cal, X, y, cv=cv, method="predict_proba", n_jobs=1)[:, 1]
    print(f"\nCalibration (LightGBM): Brier raw={brier_score_loss(y, oof['LightGBM']):.4f} "
          f"-> isotonic={brier_score_loss(y, cal_p):.4f}")

    # ---- temporal holdout
    tr, te = U.time_split(df, pd.Series(True, index=range(len(X))))
    m = models["LightGBM"]
    m.fit(X[tr], y[tr])
    ts_p = m.predict_proba(X[te])[:, 1]
    ts = U.clf_metrics(y[te], ts_p)
    print(f"\n=== Temporal holdout (train<{C.TIME_SPLIT_DATE}, n_tr={tr.sum()}, n_te={te.sum()}) ===")
    print(f"  LightGBM: ROC={ts['ROC_AUC']:.3f}  PR={ts['PR_AUC']:.3f}")

    # ---- fit final + save
    final = models["LightGBM"]
    final.fit(X, y)
    joblib.dump(final, C.MODEL_DIR / "closure_best.pkl")
    table.to_csv(C.METRIC_DIR / "closure_cv.csv")
    np.save(C.PRED_DIR / "closure_oof.npy", oof["LightGBM"])
    print(f"\nSaved -> models/closure_best.pkl, metrics/closure_cv.csv")
    print("\n" + table.round(4).to_string())


if __name__ == "__main__":
    main()
