"""L4 - Post-event learning loop (merged & upgraded from the main-branch playbook).

After events close, compare what the model PREDICTED against what actually
happened, and distil it into an operational playbook keyed by (cause x H3 hex):
  - historical_avg_hrs : ground-truth clearance time for that cause+place
  - model_bias_hrs     : mean (actual - predicted) -> are we systematically off?
  - drift flag         : |bias| over threshold with enough samples -> retrain

Upgrade vs. main: predictions are leak-free **out-of-fold** (k-fold) estimates,
not in-sample, so the measured bias is honest.

Run: bash run.sh src/learn.py
"""
import numpy as np
import pandas as pd
import config as C
import cv_utils as U

DRIFT_HRS = 1.0      # systematic error that warrants attention
MIN_N = 5            # minimum closed events before we trust a cell's signal


def main():
    df = pd.read_pickle(C.PROCESSED)
    mask = df["is_clear_label"] == 1
    X = df.loc[mask, C.ALL_FEATS]
    y = df.loc[mask, "y_clear_log"].values
    print(f"Learning from {int(mask.sum())} closed unplanned events (leak-free OOF)...")

    # leak-free out-of-fold predicted clearance
    _, oof = U.kfold_regression({"LightGBM": U.get_regressors()["LightGBM"]}, X, y)
    pred_h = np.expm1(np.clip(oof["LightGBM"], None, 12))
    actual_h = np.expm1(y)

    lab = df.loc[mask, ["event_cause", "hex_id", "corridor", "zone"]].copy()
    lab["actual_h"] = actual_h
    lab["pred_h"] = pred_h
    lab["resid_h"] = actual_h - pred_h          # +ve => model UNDER-predicts (worse than expected)

    print(f"  overall OOF MAE = {np.mean(np.abs(lab['resid_h'])):.3f} h")

    # ---- playbook keyed by cause x hex
    pb = (lab.groupby(["event_cause", "hex_id"])
          .agg(n=("actual_h", "size"),
               historical_avg_hrs=("actual_h", "mean"),
               model_bias_hrs=("resid_h", "mean"),
               mae_hrs=("resid_h", lambda s: s.abs().mean()),
               corridor=("corridor", "first"))
          .reset_index())
    pb["retrain_flag"] = ((pb["model_bias_hrs"].abs() > DRIFT_HRS) & (pb["n"] >= MIN_N)).astype(int)
    pb = pb.sort_values(["retrain_flag", "n"], ascending=False)
    pb.to_csv(C.PRED_DIR / "learning_playbook.csv", index=False)

    # ---- coarse cause-level summary (interpretable for ops)
    cause_pb = (lab.groupby("event_cause")
                .agg(n=("actual_h", "size"),
                     historical_avg_hrs=("actual_h", "mean"),
                     model_bias_hrs=("resid_h", "mean"))
                .sort_values("n", ascending=False))
    cause_pb.to_csv(C.PRED_DIR / "learning_playbook_by_cause.csv")

    drift = pb[pb["retrain_flag"] == 1]
    print(f"  playbook cells: {len(pb)}  |  with >={MIN_N} events: {(pb['n']>=MIN_N).sum()}  "
          f"|  DRIFT (retrain) cells: {len(drift)}")
    print("\n  Top model-bias by cause (h, +ve = under-predicted):")
    print(cause_pb[["n", "historical_avg_hrs", "model_bias_hrs"]].round(2).to_string())
    if len(drift):
        print("\n  🚨 Highest-drift cells flagged for retraining:")
        print(drift.head(6)[["event_cause", "corridor", "n", "historical_avg_hrs",
                             "model_bias_hrs"]].round(2).to_string(index=False))
    print(f"\nSaved -> predictions/learning_playbook.csv (+ _by_cause.csv)")


if __name__ == "__main__":
    main()
