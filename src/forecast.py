"""L1 - Spatiotemporal forecasting (WHERE / WHEN / HOW MANY events).

Three components:
 1. Corridor x day event-count forecast  -> LightGBM Poisson on lag/calendar feats
 2. Hotspot risk surface (corridor x hour) -> empirical-Bayes smoothed rates
 3. Hawkes self-exciting process on accidents -> quantifies incident "contagion"

Run: bash run.sh src/forecast.py
"""
import numpy as np
import pandas as pd
import joblib
from scipy.optimize import minimize
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, mean_poisson_deviance
import config as C


# ---------------------------------------------------------------- 1) panel
def build_panel(df):
    t = pd.to_datetime(df["event_time"]).dt.tz_localize(None)
    d = df.assign(date=t.dt.normalize())
    g = d.groupby(["corridor", "date"]).size().rename("count").reset_index()
    corridors = d["corridor"].dropna().unique()
    dates = pd.date_range(d["date"].min(), d["date"].max(), freq="D")
    full = (pd.MultiIndex.from_product([corridors, dates], names=["corridor", "date"])
            .to_frame(index=False))
    p = full.merge(g, on=["corridor", "date"], how="left").fillna({"count": 0})
    p = p.sort_values(["corridor", "date"]).reset_index(drop=True)
    p["dow"] = p.date.dt.dayofweek
    p["month"] = p.date.dt.month
    p["day"] = p.date.dt.day
    p["is_weekend"] = (p["dow"] >= 5).astype(int)
    grp = p.groupby("corridor")["count"]
    p["lag1"] = grp.shift(1)
    p["lag7"] = grp.shift(7)
    p["roll7"] = grp.transform(lambda s: s.shift(1).rolling(7, min_periods=3).mean())
    p["roll30"] = grp.transform(lambda s: s.shift(1).rolling(30, min_periods=7).mean())
    return p.dropna(subset=["lag7", "roll7", "roll30"]).reset_index(drop=True)


def forecast_counts(df):
    p = build_panel(df)
    feats = ["dow", "month", "day", "is_weekend", "lag1", "lag7", "roll7", "roll30"]
    X = pd.concat([p[feats], pd.get_dummies(p["corridor"], prefix="cor")], axis=1)
    y = p["count"].values

    cut = p["date"].quantile(0.8)
    tr, te = (p["date"] <= cut).values, (p["date"] > cut).values
    model = lgb.LGBMRegressor(objective="poisson", n_estimators=600, learning_rate=0.03,
                              num_leaves=48, subsample=0.8, colsample_bytree=0.8,
                              n_jobs=-1, random_state=C.SEED, verbose=-1)
    model.fit(X[tr], y[tr])
    pred = np.clip(model.predict(X[te]), 1e-6, None)

    mae = mean_absolute_error(y[te], pred)
    dev = mean_poisson_deviance(y[te], pred)
    base_lag7 = mean_absolute_error(y[te], np.clip(p.loc[te, "lag7"], 1e-6, None))
    base_mean = mean_absolute_error(y[te], np.full(te.sum(), y[tr].mean()))
    print("=== 1) Corridor x day count forecast (temporal split) ===")
    print(f"  LightGBM-Poisson  MAE={mae:.3f}  PoissonDev={dev:.3f}")
    print(f"  baseline lag7     MAE={base_lag7:.3f}   baseline global-mean MAE={base_mean:.3f}")
    print(f"  lift over lag7 baseline: {(base_lag7-mae)/base_lag7*100:.1f}%")
    joblib.dump(model, C.MODEL_DIR / "forecast_counts.pkl")
    return p


# ---------------------------------------------------------------- 2) hotspot
def hotspot_surface(df):
    t = pd.to_datetime(df["event_time"]).dt.tz_localize(None)
    d = df.assign(date=t.dt.normalize(), hr=df["hour"])
    n_days = d["date"].nunique()
    # empirical-Bayes smoothed expected events per corridor x hour per day
    grand = len(d) / (n_days * 24)
    tab = d.groupby(["corridor", "hr"]).size().rename("n").reset_index()
    tab["rate_per_day"] = (tab["n"] + 2 * grand) / (n_days + 2)   # EB shrink to grand mean
    tab = tab.sort_values("rate_per_day", ascending=False)
    tab.to_csv(C.PRED_DIR / "hotspot_corridor_hour.csv", index=False)
    print("\n=== 2) Hotspot risk surface (corridor x hour) — top 8 ===")
    print(tab.head(8).to_string(index=False))
    return tab


# ---------------------------------------------------------------- 3) Hawkes
def hawkes_fit(times, T):
    """Univariate exp-kernel Hawkes MLE via the Ogata recursion (bounded L-BFGS-B)."""
    times = np.sort(times)

    def neg_ll(p):
        mu, alpha, beta = p
        A = 0.0
        ll = 0.0
        prev = times[0]
        for i, ti in enumerate(times):
            if i > 0:
                A = np.exp(-beta * (ti - prev)) * (1 + A)
                prev = ti
            ll += np.log(mu + alpha * A + 1e-12)
        comp = mu * T + (alpha / beta) * np.sum(1 - np.exp(-beta * (T - times)))
        return -(ll - comp)

    # beta bounded so the decay half-life stays interpretable (>= ~7 min)
    res = minimize(neg_ll, [len(times) / T, 0.3, 0.5], method="L-BFGS-B",
                   bounds=[(1e-4, 5.0), (1e-4, 10.0), (0.05, 6.0)])
    return tuple(res.x)


def hawkes_contagion(df):
    a = df[df["event_cause"] == "accident"].copy()
    t = pd.to_datetime(a["event_time"]).dt.tz_localize(None).dropna().sort_values()
    hrs = (t - t.min()).dt.total_seconds().values / 3600.0
    hrs = hrs[hrs >= 0]
    T = hrs.max() + 1
    mu, alpha, beta = hawkes_fit(hrs, T)
    branching = alpha / beta
    half_life = np.log(2) / beta
    print("\n=== 3) Hawkes self-excitation on ACCIDENTS (n={}) ===".format(len(hrs)))
    print(f"  background mu={mu:.4f}/h  alpha={alpha:.3f}  beta={beta:.3f}/h")
    print(f"  branching ratio (alpha/beta) = {branching:.3f}  "
          f"-> {branching*100:.0f}% of accidents trigger follow-on incidents")
    print(f"  excitation half-life = {half_life:.2f} h")
    joblib.dump({"mu": mu, "alpha": alpha, "beta": beta, "branching": branching,
                 "half_life_h": half_life}, C.MODEL_DIR / "hawkes_accident.pkl")


def main():
    df = pd.read_pickle(C.PROCESSED)
    forecast_counts(df)
    hotspot_surface(df)
    hawkes_contagion(df)
    print("\nSaved -> models/forecast_counts.pkl, models/hawkes_accident.pkl, "
          "predictions/hotspot_corridor_hour.csv")


if __name__ == "__main__":
    main()
