"""Interpretability (SHAP) + consolidated results summary + figures.

Run: bash run.sh src/report.py
"""
import warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import shap
import lightgbm as lgb

import config as C
import cv_utils as U


def shap_importance(pl, X, sample=1200, top=15):
    """Mean |SHAP| per feature for a fitted preprocessor+LGBM pipeline."""
    prep, model = pl.named_steps["prep"], pl.named_steps["model"]
    Xs = X.sample(min(sample, len(X)), random_state=C.SEED)
    Xt = prep.transform(Xs)
    names = list(prep.get_feature_names_out())
    sv = shap.TreeExplainer(model).shap_values(Xt)
    if isinstance(sv, list):
        sv = sv[1]
    imp = np.abs(sv).mean(axis=0)
    return (pd.Series(imp, index=names).sort_values(ascending=False).head(top))


def bar(series, title, path, color):
    plt.figure(figsize=(8, 5))
    series[::-1].plot.barh(color=color)
    plt.title(title)
    plt.xlabel("mean |SHAP| (impact on model output)")
    plt.tight_layout()
    plt.savefig(path, dpi=130)
    plt.close()


def main():
    df = pd.read_pickle(C.PROCESSED)

    # ---- SHAP: closure drivers
    print("=== SHAP — top drivers of ROAD-CLOSURE prediction ===")
    y = df["y_closure"].astype(int)
    spw = (1 - y.mean()) / y.mean()
    cl = U.pipe(lgb.LGBMClassifier(scale_pos_weight=spw, n_estimators=600, learning_rate=0.03,
                                   num_leaves=48, n_jobs=-1, random_state=C.SEED, verbose=-1))
    cl.fit(df[C.ALL_FEATS], y)
    imp_c = shap_importance(cl, df[C.ALL_FEATS])
    print(imp_c.round(4).to_string())
    bar(imp_c, "Road-closure: top SHAP drivers", C.FIG_DIR / "shap_closure.png", "#c0392b")

    # ---- SHAP: clearance drivers
    print("\n=== SHAP — top drivers of CLEARANCE-TIME prediction ===")
    lab = df["is_clear_label"] == 1
    rg = U.pipe(lgb.LGBMRegressor(n_estimators=600, learning_rate=0.03, num_leaves=48,
                                  n_jobs=-1, random_state=C.SEED, verbose=-1))
    rg.fit(df.loc[lab, C.ALL_FEATS], df.loc[lab, "y_clear_log"])
    imp_r = shap_importance(rg, df.loc[lab, C.ALL_FEATS])
    print(imp_r.round(4).to_string())
    bar(imp_r, "Clearance-time: top SHAP drivers", C.FIG_DIR / "shap_clearance.png", "#2980b9")

    # ---- EIS distribution figure
    if (C.DATA_DIR / "scored.pkl").exists():
        s = pd.read_pickle(C.DATA_DIR / "scored.pkl")
        plt.figure(figsize=(8, 4))
        order = ["Low", "Medium", "High", "Critical"]
        s["EIS_tier"].value_counts().reindex(order).plot.bar(
            color=["#27ae60", "#f39c12", "#e67e22", "#c0392b"])
        plt.title("Event Impact Score — tier distribution"); plt.ylabel("events")
        plt.tight_layout(); plt.savefig(C.FIG_DIR / "eis_tiers.png", dpi=130); plt.close()

    # ---- consolidated summary
    print("\n=== CONSOLIDATED RESULTS ===")
    lines = ["# Model Results Summary\n"]
    for task, file, head in [("Clearance regression", "clearance_cv.csv", "MAE_hours"),
                             ("Road-closure clf", "closure_cv.csv", "PR_AUC"),
                             ("Priority (intrinsic)", "priority_cv.csv", "ROC_AUC")]:
        p = C.METRIC_DIR / file
        if p.exists():
            t = pd.read_csv(p, index_col=0)
            best = t.index[0]
            print(f"  {task:24s} best={best:14s} {head}={t.iloc[0][head]:.3f}")
            lines.append(f"- **{task}**: best `{best}` — {head} = {t.iloc[0][head]:.3f}")
    with open(C.METRIC_DIR / "SUMMARY.md", "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nSaved figures -> outputs/figures/  |  summary -> outputs/metrics/SUMMARY.md")


if __name__ == "__main__":
    main()
