"""Shared cross-validation engine, model zoo, preprocessing and metrics.

Design choices that matter for a competition:
- Fold-safe target encoding: high-cardinality cats are target-encoded *inside*
  the pipeline, so the encoder only ever sees training-fold labels (no leakage).
- Out-of-fold (OOF) predictions for every model -> honest k-fold scores and a
  clean substrate for stacking.
- Both k-fold (random) AND temporal holdout are reported, because the data is a
  time series and random CV alone is optimistic.
"""
import warnings
import numpy as np
import pandas as pd
warnings.filterwarnings("ignore")

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, TargetEncoder
from sklearn.model_selection import StratifiedKFold, KFold, cross_val_predict
from sklearn.linear_model import Ridge, ElasticNet, LogisticRegression
from sklearn.ensemble import (RandomForestRegressor, RandomForestClassifier,
                              ExtraTreesRegressor, ExtraTreesClassifier,
                              HistGradientBoostingRegressor, HistGradientBoostingClassifier)
from sklearn.neighbors import KNeighborsRegressor, KNeighborsClassifier
from sklearn.neural_network import MLPRegressor, MLPClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import (mean_absolute_error, mean_squared_error, r2_score,
                             roc_auc_score, average_precision_score, f1_score,
                             balanced_accuracy_score, brier_score_loss)
import lightgbm as lgb
import xgboost as xgb
from catboost import CatBoostRegressor, CatBoostClassifier

import config as C
SEED = C.SEED


# ----------------------------------------------------------- preprocessing
def build_preprocessor(scale=False, lowcard=None, highcard=None, num=None):
    lowcard = C.LOWCARD_CATS if lowcard is None else lowcard
    highcard = C.HIGHCARD_CATS if highcard is None else highcard
    num = C.NUM_FEATS if num is None else num
    num_step = StandardScaler() if scale else "passthrough"
    transformers = []
    if lowcard:
        transformers.append(("ohe", OneHotEncoder(handle_unknown="ignore", sparse_output=False), lowcard))
    if highcard:
        transformers.append(("te", TargetEncoder(smooth="auto", random_state=SEED), highcard))
    if num:
        transformers.append(("num", num_step, num))
    return ColumnTransformer(transformers=transformers, remainder="drop")


def pipe(model, scale=False, lowcard=None, highcard=None, num=None):
    return Pipeline([("prep", build_preprocessor(scale, lowcard, highcard, num)),
                     ("model", model)])


# ----------------------------------------------------------- model zoos
def get_regressors(lowcard=None, highcard=None, num=None):
    def P(model, scale=False):
        return pipe(model, scale, lowcard, highcard, num)
    return {
        "Ridge":        P(Ridge(alpha=1.0, random_state=SEED), scale=True),
        "ElasticNet":   P(ElasticNet(alpha=0.01, l1_ratio=0.5, random_state=SEED), scale=True),
        "KNN":          P(KNeighborsRegressor(n_neighbors=15, weights="distance"), scale=True),
        "MLP":          P(MLPRegressor(hidden_layer_sizes=(128, 64), alpha=1e-3,
                                       max_iter=400, early_stopping=True, random_state=SEED), scale=True),
        "RandomForest": P(RandomForestRegressor(n_estimators=400, min_samples_leaf=3,
                                                n_jobs=-1, random_state=SEED)),
        "ExtraTrees":   P(ExtraTreesRegressor(n_estimators=500, min_samples_leaf=3,
                                              n_jobs=-1, random_state=SEED)),
        "HistGBM":      P(HistGradientBoostingRegressor(max_iter=500, learning_rate=0.05,
                                                        max_depth=None, l2_regularization=1.0,
                                                        random_state=SEED)),
        "LightGBM":     P(lgb.LGBMRegressor(n_estimators=700, learning_rate=0.03, num_leaves=48,
                                            subsample=0.8, colsample_bytree=0.8, reg_lambda=2.0,
                                            n_jobs=-1, random_state=SEED, verbose=-1)),
        "XGBoost":      P(xgb.XGBRegressor(n_estimators=700, learning_rate=0.03, max_depth=6,
                                           subsample=0.8, colsample_bytree=0.8, reg_lambda=2.0,
                                           n_jobs=-1, random_state=SEED, verbosity=0)),
        "CatBoost":     P(CatBoostRegressor(iterations=700, learning_rate=0.03, depth=6,
                                            l2_leaf_reg=3.0, random_seed=SEED, verbose=0)),
    }


def get_classifiers(scale_pos_weight=1.0, lowcard=None, highcard=None, num=None):
    spw = scale_pos_weight
    def P(model, scale=False):
        return pipe(model, scale, lowcard, highcard, num)
    return {
        "Logistic":     P(LogisticRegression(C=1.0, class_weight="balanced",
                                             max_iter=2000, random_state=SEED), scale=True),
        "GaussianNB":   P(GaussianNB(), scale=True),
        "KNN":          P(KNeighborsClassifier(n_neighbors=25, weights="distance"), scale=True),
        "MLP":          P(MLPClassifier(hidden_layer_sizes=(128, 64), alpha=1e-3, max_iter=400,
                                        early_stopping=True, random_state=SEED), scale=True),
        "RandomForest": P(RandomForestClassifier(n_estimators=500, min_samples_leaf=2,
                                                 class_weight="balanced_subsample",
                                                 n_jobs=-1, random_state=SEED)),
        "ExtraTrees":   P(ExtraTreesClassifier(n_estimators=600, min_samples_leaf=2,
                                               class_weight="balanced_subsample",
                                               n_jobs=-1, random_state=SEED)),
        "HistGBM":      P(HistGradientBoostingClassifier(max_iter=500, learning_rate=0.05,
                                                         l2_regularization=1.0,
                                                         class_weight="balanced", random_state=SEED)),
        "LightGBM":     P(lgb.LGBMClassifier(n_estimators=700, learning_rate=0.03, num_leaves=48,
                                             subsample=0.8, colsample_bytree=0.8, reg_lambda=2.0,
                                             scale_pos_weight=spw, n_jobs=-1, random_state=SEED,
                                             verbose=-1)),
        "XGBoost":      P(xgb.XGBClassifier(n_estimators=700, learning_rate=0.03, max_depth=6,
                                            subsample=0.8, colsample_bytree=0.8, reg_lambda=2.0,
                                            scale_pos_weight=spw, n_jobs=-1, random_state=SEED,
                                            verbosity=0, eval_metric="logloss")),
        "CatBoost":     P(CatBoostClassifier(iterations=700, learning_rate=0.03, depth=6,
                                             l2_leaf_reg=3.0, random_seed=SEED, verbose=0,
                                             auto_class_weights="Balanced")),
    }


# ----------------------------------------------------------- metrics
def reg_metrics(y_log, pred_log):
    """y is log1p(hours). Report on log scale and back-transformed hours."""
    y_h, p_h = np.expm1(y_log), np.expm1(np.clip(pred_log, None, 12))
    return {
        "MAE_log": mean_absolute_error(y_log, pred_log),
        "RMSE_log": mean_squared_error(y_log, pred_log) ** 0.5,
        "R2_log": r2_score(y_log, pred_log),
        "MAE_hours": mean_absolute_error(y_h, p_h),
        "MedAE_hours": float(np.median(np.abs(y_h - p_h))),
    }


def clf_metrics(y, proba):
    pred = (proba >= 0.5).astype(int)
    # best-F1 threshold
    ts = np.linspace(0.05, 0.95, 19)
    best_t = max(ts, key=lambda t: f1_score(y, (proba >= t).astype(int), zero_division=0))
    return {
        "ROC_AUC": roc_auc_score(y, proba),
        "PR_AUC": average_precision_score(y, proba),
        "F1@0.5": f1_score(y, pred, zero_division=0),
        "F1@best": f1_score(y, (proba >= best_t).astype(int), zero_division=0),
        "best_thr": float(best_t),
        "BalAcc": balanced_accuracy_score(y, pred),
        "Brier": brier_score_loss(y, proba),
    }


# ----------------------------------------------------------- OOF runners
def kfold_regression(models, X, y, n_splits=C.N_SPLITS):
    cv = KFold(n_splits=n_splits, shuffle=True, random_state=SEED)
    rows, oof = [], {}
    for name, model in models.items():
        try:
            p = cross_val_predict(model, X, y, cv=cv, n_jobs=1)
            m = reg_metrics(y, p)
            m["model"] = name
            rows.append(m)
            oof[name] = p
            print(f"  {name:13s} MAE_h={m['MAE_hours']:.3f}  MedAE_h={m['MedAE_hours']:.3f}  R2_log={m['R2_log']:.3f}")
        except Exception as e:
            print(f"  {name:13s} FAILED: {str(e)[:90]}")
    if not rows:
        raise RuntimeError("All regressors failed")
    return pd.DataFrame(rows).set_index("model").sort_values("MAE_hours"), oof


def kfold_classification(models, X, y, n_splits=C.N_SPLITS):
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=SEED)
    rows, oof = [], {}
    for name, model in models.items():
        try:
            p = cross_val_predict(model, X, y, cv=cv, method="predict_proba", n_jobs=1)[:, 1]
            m = clf_metrics(y, p)
            m["model"] = name
            rows.append(m)
            oof[name] = p
            print(f"  {name:13s} ROC={m['ROC_AUC']:.3f}  PR={m['PR_AUC']:.3f}  F1*={m['F1@best']:.3f}")
        except Exception as e:
            print(f"  {name:13s} FAILED: {str(e)[:90]}")
    return pd.DataFrame(rows).set_index("model").sort_values("PR_AUC", ascending=False), oof


# ----------------------------------------------------------- temporal holdout
def time_split(df, mask, time_col="event_time", date=C.TIME_SPLIT_DATE):
    t = pd.to_datetime(df[time_col]).dt.tz_localize(None)
    cut = pd.Timestamp(date)
    tr = mask & (t < cut)
    te = mask & (t >= cut)
    return tr.values, te.values
