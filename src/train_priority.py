"""T3 - Priority classification (High vs Low), done HONESTLY.

Diagnostic finding: `priority` is ~95% determined by corridor/junction -> it is
effectively a STATIC LOCATION DESIGNATION in ASTraM, not an event-severity label.
"Predicting" it with location features is circular (AUC ~ 1.0 even for a linear
model, even on a temporal holdout).

So we run TWO models and report both:
  (A) location-based  -> documents the circularity (NOT a real result)
  (B) intrinsic-only  -> the honest question: how much is priority predictable
                          from event characteristics (cause, vehicle, time) ALONE?

Run: bash run.sh src/train_priority.py
"""
import numpy as np
import pandas as pd
import joblib
import config as C
import cv_utils as U


def main():
    df = pd.read_pickle(C.PROCESSED)
    mask = df["y_priority"].notna()
    y = df.loc[mask, "y_priority"].astype(int).reset_index(drop=True)
    print(f"Priority: n={int(mask.sum())}  High-rate={y.mean()*100:.1f}%\n")

    # (A) location-based — circular, for documentation only
    Xa = df.loc[mask, C.ALL_FEATS].reset_index(drop=True)
    print("=== (A) WITH location features  [expected circular ~1.0] ===")
    ta, _ = U.kfold_classification({k: U.get_classifiers()[k]
                                    for k in ["Logistic", "LightGBM"]}, Xa, y)

    # (B) intrinsic-only — the honest model
    Xb = df.loc[mask, C.INTRINSIC_FEATS].reset_index(drop=True)
    print("\n=== (B) INTRINSIC features only (no location)  [the real result] ===")
    models = U.get_classifiers(scale_pos_weight=1.0, lowcard=C.INTRINSIC_LOWCARD,
                               highcard=[], num=C.INTRINSIC_NUM)
    tb, oof = U.kfold_classification(models, Xb, y)

    # temporal holdout for the intrinsic model
    tr, te = U.time_split(df.loc[mask].reset_index(drop=True),
                          pd.Series(True, index=range(len(Xb))))
    m = models["LightGBM"]
    m.fit(Xb[tr], y[tr])
    ts = U.clf_metrics(y[te], m.predict_proba(Xb[te])[:, 1])
    print(f"\n=== Temporal holdout (intrinsic, n_tr={tr.sum()}, n_te={te.sum()}) ===")
    print(f"  LightGBM: ROC={ts['ROC_AUC']:.3f}  PR={ts['PR_AUC']:.3f}")

    best = tb.index[0]
    print(f"\nIntrinsic best ROC-AUC = {tb['ROC_AUC'].max():.3f} ({best}) "
          f"-> priority is only partly event-driven; the rest is location.")

    final = models["LightGBM"]
    final.fit(Xb, y)
    joblib.dump(final, C.MODEL_DIR / "priority_intrinsic.pkl")
    tb.to_csv(C.METRIC_DIR / "priority_cv.csv")
    np.save(C.PRED_DIR / "priority_oof.npy", oof["LightGBM"])
    print(f"\nSaved -> models/priority_intrinsic.pkl, metrics/priority_cv.csv")
    print("\n(A) location-based:\n" + ta.round(4).to_string())
    print("\n(B) intrinsic-only:\n" + tb.round(4).to_string())


if __name__ == "__main__":
    main()
