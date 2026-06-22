"""Optuna hyperparameter optimization for the two real predictive tasks,
with a k-fold CV objective (Bayesian search via TPE). Reports lift over the
untuned LightGBM baseline and saves the best params.

Run: bash run.sh src/tune.py
"""
import json
import warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")
import optuna
optuna.logging.set_verbosity(optuna.logging.WARNING)

from sklearn.model_selection import KFold, StratifiedKFold, cross_val_score, cross_val_predict
from sklearn.metrics import average_precision_score
import lightgbm as lgb

import config as C
import cv_utils as U

N_TRIALS = 40
INNER_FOLDS = 3


def tune_clearance(df):
    lab = df["is_clear_label"] == 1
    X, y = df.loc[lab, C.ALL_FEATS], df.loc[lab, "y_clear_log"]
    cv = KFold(INNER_FOLDS, shuffle=True, random_state=C.SEED)

    def objective(t):
        params = dict(
            n_estimators=t.suggest_int("n_estimators", 300, 1200, step=100),
            learning_rate=t.suggest_float("learning_rate", 0.01, 0.1, log=True),
            num_leaves=t.suggest_int("num_leaves", 16, 128),
            min_child_samples=t.suggest_int("min_child_samples", 5, 80),
            subsample=t.suggest_float("subsample", 0.6, 1.0),
            colsample_bytree=t.suggest_float("colsample_bytree", 0.6, 1.0),
            reg_lambda=t.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
            reg_alpha=t.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
        )
        m = U.pipe(lgb.LGBMRegressor(n_jobs=-1, random_state=C.SEED, verbose=-1, **params))
        s = cross_val_score(m, X, y, cv=cv, scoring="neg_mean_absolute_error", n_jobs=1)
        return -s.mean()

    study = optuna.create_study(direction="minimize",
                                sampler=optuna.samplers.TPESampler(seed=C.SEED))
    study.optimize(objective, n_trials=N_TRIALS, timeout=240)

    # evaluate tuned model on full 5-fold (hours MAE) vs default
    tuned = U.pipe(lgb.LGBMRegressor(n_jobs=-1, random_state=C.SEED, verbose=-1, **study.best_params))
    p = cross_val_predict(tuned, X, y, cv=KFold(C.N_SPLITS, shuffle=True, random_state=C.SEED), n_jobs=1)
    m = U.reg_metrics(y, p)
    return study.best_params, m, study.best_value


def tune_closure(df):
    X, y = df[C.ALL_FEATS], df["y_closure"].astype(int)
    spw = (1 - y.mean()) / y.mean()
    cv = StratifiedKFold(INNER_FOLDS, shuffle=True, random_state=C.SEED)

    def objective(t):
        params = dict(
            n_estimators=t.suggest_int("n_estimators", 300, 1200, step=100),
            learning_rate=t.suggest_float("learning_rate", 0.01, 0.1, log=True),
            num_leaves=t.suggest_int("num_leaves", 16, 128),
            min_child_samples=t.suggest_int("min_child_samples", 5, 80),
            subsample=t.suggest_float("subsample", 0.6, 1.0),
            colsample_bytree=t.suggest_float("colsample_bytree", 0.6, 1.0),
            reg_lambda=t.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        )
        m = U.pipe(lgb.LGBMClassifier(scale_pos_weight=spw, n_jobs=-1, random_state=C.SEED,
                                      verbose=-1, **params))
        s = cross_val_score(m, X, y, cv=cv, scoring="average_precision", n_jobs=1)
        return s.mean()

    study = optuna.create_study(direction="maximize",
                                sampler=optuna.samplers.TPESampler(seed=C.SEED))
    study.optimize(objective, n_trials=N_TRIALS, timeout=240)

    tuned = U.pipe(lgb.LGBMClassifier(scale_pos_weight=spw, n_jobs=-1, random_state=C.SEED,
                                      verbose=-1, **study.best_params))
    p = cross_val_predict(tuned, X, y, cv=StratifiedKFold(C.N_SPLITS, shuffle=True, random_state=C.SEED),
                          method="predict_proba", n_jobs=1)[:, 1]
    return study.best_params, U.clf_metrics(y, p), average_precision_score(y, p)


def main():
    df = pd.read_pickle(C.PROCESSED)
    out = {}

    print("=== Optuna: CLEARANCE (LightGBM, minimize MAE_log) ===")
    bp, m, bv = tune_clearance(df)
    print(f"  tuned 5-fold MAE_hours={m['MAE_hours']:.3f}  R2_log={m['R2_log']:.3f}  (default was 2.964 / 0.383)")
    print(f"  best params: {bp}")
    out["clearance"] = {"params": bp, "metrics": m}

    print("\n=== Optuna: CLOSURE (LightGBM, maximize PR-AUC) ===")
    bp, m, bv = tune_closure(df)
    print(f"  tuned 5-fold PR-AUC={m['PR_AUC']:.3f}  ROC={m['ROC_AUC']:.3f}  (default was 0.465 / 0.811)")
    print(f"  best params: {bp}")
    out["closure"] = {"params": bp, "metrics": m}

    with open(C.METRIC_DIR / "tuned_params.json", "w") as f:
        json.dump(out, f, indent=2, default=float)
    print(f"\nSaved -> metrics/tuned_params.json")


if __name__ == "__main__":
    main()
