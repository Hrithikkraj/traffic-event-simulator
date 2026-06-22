"""THE SPINE - Event Impact Score (EIS).

The dataset has NO congestion/flow measurement, so "impact" must be engineered.
We frame it as expected vehicle-hours of delay (a transport-engineering unit):

    EIS_raw = Duration  x  ClosureFactor  x  CorridorExposure  x  TimeWeight

  - Duration        : predicted clearance hours (unplanned) or planned duration
  - ClosureFactor   : 1 + 2*P(road_closure)   (a closure multiplies lanes lost)
  - CorridorExposure: busier arterial -> more vehicles exposed (historical proxy)
  - TimeWeight      : same blockage hurts far more in rush hour than at 2am

EIS is the 0-100 percentile rank of EIS_raw, tiered Low/Medium/High/Critical.

VALIDATION (no ground truth exists, so we prove it estimates realized impact):
We build EIS from components known/predicted AT EVENT CREATION (out-of-fold, no
leakage) and correlate it with an OBSERVED impact built from ACTUAL outcomes.

Run: bash run.sh src/impact_score.py
"""
import numpy as np
import pandas as pd
import joblib
from scipy.stats import spearmanr
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score
import config as C
import cv_utils as U

# EIS effective-duration constants (shared with inference)
CHRONIC_H, ACUTE_CAP = 1.5, 12.0


def time_weight(hour):
    rush = hour.isin([8, 9, 10, 11, 17, 18, 19, 20])
    night = hour.isin([22, 23, 0, 1, 2, 3, 4, 5])
    w = pd.Series(1.0, index=hour.index)
    w[rush] = 2.0
    w[night] = 0.4
    return w


def corridor_exposure_map(df):
    cnt = df["corridor"].value_counts()
    w = np.log1p(cnt) / np.log1p(cnt.max())          # 0..1
    w = 0.5 + 1.5 * w                                  # 0.5..2.0
    if "Non-corridor" in w.index:
        w["Non-corridor"] = 0.6
    return w


def corridor_exposure(df, wmap=None):
    w = corridor_exposure_map(df) if wmap is None else wmap
    return df["corridor"].map(w).fillna(0.6).values


def main():
    df = pd.read_pickle(C.PROCESSED).reset_index(drop=True)
    n = len(df)
    print(f"Scoring {n} events.\n")

    # ---- shared structural weights
    tw = time_weight(df["hour"]).values
    cw = corridor_exposure(df)

    # ---- closure probability, OUT-OF-FOLD (honest, no leakage)
    Xc = df[C.ALL_FEATS]
    yc = df["y_closure"].astype(int)
    spw = (1 - yc.mean()) / yc.mean()
    closure_clf = U.get_classifiers(scale_pos_weight=spw)["LightGBM"]
    cv = StratifiedKFold(n_splits=C.N_SPLITS, shuffle=True, random_state=C.SEED)
    closure_oof = cross_val_predict(closure_clf, Xc, yc, cv=cv,
                                    method="predict_proba", n_jobs=1)[:, 1]

    # ---- clearance hours: OOF for labelled unplanned; planned uses known schedule
    lab = df["is_clear_label"] == 1
    Xr = df.loc[lab, C.ALL_FEATS]
    yr = df.loc[lab, "y_clear_log"]
    reg = U.get_regressors()["ExtraTrees"]
    clear_oof_log = cross_val_predict(reg, Xr, yr,
                                      cv=KFold(C.N_SPLITS, shuffle=True, random_state=C.SEED), n_jobs=1)
    dur_pred = pd.Series(np.nan, index=df.index)
    dur_pred[lab] = np.expm1(clear_oof_log)
    # planned events: use known planned duration
    planned = (df["event_type"] == "planned") & df["planned_dur_h"].notna()
    dur_pred[planned] = df.loc[planned, "planned_dur_h"].clip(0.1, 72)
    # remaining (unplanned, unlabelled): fill with cause-median of predicted
    cause_med = dur_pred.groupby(df["event_cause"]).transform("median")
    dur_pred = dur_pred.fillna(cause_med).fillna(dur_pred.median()).clip(0.1, 72)

    # EFFECTIVE congestion duration != ticket-open duration.
    # Persistent infra defects (potholes/construction/water-logging) stay "open"
    # for days but do NOT block traffic continuously -> model as a chronic, low-
    # grade recurring impact. Acute events are capped at a continuous-block ceiling.
    eff_dur = dur_pred.copy()
    eff_dur[df["is_persistent"] == 1] = CHRONIC_H
    eff_dur = eff_dur.clip(0.1, ACUTE_CAP)

    # ---- EIS (predicted, from creation-time info)
    closure_factor = 1 + 2 * closure_oof
    eis_raw = eff_dur.values * closure_factor * cw * tw
    eis = pd.Series(eis_raw).rank(pct=True).values * 100
    tier = pd.cut(eis, [-1, 50, 80, 95, 101], labels=["Low", "Medium", "High", "Critical"])

    df["closure_prob"] = closure_oof
    df["pred_duration_h"] = dur_pred.values
    df["EIS"] = eis
    df["EIS_tier"] = tier

    # ===================== VALIDATION =====================
    print("=== VALIDATION 1: EIS vs OBSERVED impact (labelled unplanned) ===")
    L = df[lab].copy()
    # observed effective duration uses the same chronic/acute treatment
    obs_dur = L["clear_target_h"].copy()
    obs_dur[L["is_persistent"] == 1] = CHRONIC_H
    obs_dur = obs_dur.clip(0.1, ACUTE_CAP)
    obs_impact = (obs_dur.values
                  * (1 + 2 * df.loc[lab, "y_closure"].values)
                  * cw[lab.values] * tw[lab.values])
    rho, _ = spearmanr(L["EIS"].values, obs_impact)
    print(f"  Spearman(EIS_predicted, observed_impact) = {rho:.3f}  (n={len(L)})")
    # does high EIS flag the worst 10% of realized impact?
    top = (obs_impact >= np.quantile(obs_impact, 0.90)).astype(int)
    print(f"  AUC(EIS flags top-10% impact events)      = {roc_auc_score(top, L['EIS'].values):.3f}")

    print("\n=== VALIDATION 2: EIS vs requires_road_closure (all rows) ===")
    print(f"  AUC(EIS ranks closure events)             = {roc_auc_score(df['y_closure'], df['EIS']):.3f}")

    print("\n=== FACE VALIDITY: mean EIS by cause (should rank disruptive causes high) ===")
    fv = df.groupby("event_cause")["EIS"].mean().sort_values(ascending=False)
    print(fv.round(1).to_string())

    print("\n=== TIER DISTRIBUTION ===")
    print(df["EIS_tier"].value_counts().sort_index().to_string())
    print("\n  mean EIS: planned={:.1f}  unplanned={:.1f}".format(
        df.loc[df.event_type == "planned", "EIS"].mean(),
        df.loc[df.event_type == "unplanned", "EIS"].mean()))

    df.to_pickle(C.DATA_DIR / "scored.pkl")
    keep = ["id", "event_type", "event_cause", "corridor", "zone", "hour",
            "closure_prob", "pred_duration_h", "EIS", "EIS_tier"]
    df[keep].to_csv(C.PRED_DIR / "event_impact_scores.csv", index=False)

    # ---- persist artifacts so ANY new event can be scored at inference time
    artifacts = {
        "corridor_exposure": corridor_exposure_map(df).to_dict(),
        "corridor_centroid": df.groupby("corridor")[["latitude", "longitude"]].median().to_dict("index"),
        "cause_median_dur": dur_pred.groupby(df["event_cause"]).median().to_dict(),
        "eis_raw_reference": np.sort(eis_raw),       # map a new raw score -> percentile
        "chronic_h": CHRONIC_H, "acute_cap": ACUTE_CAP,
        "persistent_causes": sorted(df.loc[df.is_persistent == 1, "event_cause"].unique().tolist()),
        "default_latlon": [float(df.latitude.median()), float(df.longitude.median())],
    }
    joblib.dump(artifacts, C.MODEL_DIR / "eis_artifacts.pkl")
    print(f"\nSaved -> data/scored.pkl, predictions/event_impact_scores.csv, models/eis_artifacts.pkl")


if __name__ == "__main__":
    main()
