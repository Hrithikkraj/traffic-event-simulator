"""Hunt for leakage behind the suspiciously-high closure AUC."""
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
import config as C

df = pd.read_pickle(C.PROCESSED)
y = df["y_closure"].values

print("=== single-feature ROC-AUC (numeric) ===")
res = []
for f in C.NUM_FEATS:
    v = df[f].values.astype(float)
    if np.unique(v).size < 2:
        continue
    a = roc_auc_score(y, v)
    res.append((f, max(a, 1 - a)))
for f, a in sorted(res, key=lambda x: -x[1])[:12]:
    print(f"  {f:14s} {a:.3f}")

print("\n=== categorical closure-rate spread ===")
for f in ["event_type", "event_cause", "corridor", "zone", "veh_type", "authenticated", "client_id"]:
    g = df.groupby(f)["y_closure"].agg(["mean", "size"])
    print(f"  {f:13s} range[{g['mean'].min():.2f},{g['mean'].max():.2f}] nuniq={len(g)}")

print("\n=== description literally contains closure words? ===")
d = df["description"].fillna("").str.lower()
for w in ["clos", "divert", "barricad", "block", "no entry", "one way", "restrict"]:
    m = d.str.contains(w, regex=False)
    if m.sum():
        print(f"  '{w}': n={m.sum()}  closure-rate={df.loc[m,'y_closure'].mean():.2f} (overall {y.mean():.2f})")

print("\n=== junction / cluster purity (target-encoding memorization risk) ===")
for f in ["junction", "spatial_cluster", "police_station"]:
    g = df.groupby(f)["y_closure"].agg(["mean", "size"])
    big = g[g["size"] >= 5]
    pure = big[(big["mean"] == 0) | (big["mean"] == 1)]
    print(f"  {f:14s}: {len(pure)}/{len(big)} categories(>=5 ev) are 100% pure 0 or 1")

print("\n=== map_file / status / authenticated cross-tab with closure ===")
for f in ["status", "authenticated"]:
    print(f"  {f}:")
    print(df.groupby(f)["y_closure"].agg(["mean", "size"]).to_string())
