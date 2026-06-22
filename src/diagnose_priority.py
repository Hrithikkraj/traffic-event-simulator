"""Find what perfectly separates priority (1.000 AUC is suspicious)."""
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score
import config as C

df = pd.read_pickle(C.PROCESSED).copy()
m = df["y_priority"].notna()
df = df[m]
y = df["y_priority"].astype(int).values

print("=== single-feature ROC-AUC for priority (numeric) ===")
res = []
for f in C.NUM_FEATS:
    v = df[f].values.astype(float)
    if np.unique(v).size < 2:
        continue
    a = roc_auc_score(y, v)
    res.append((f, max(a, 1 - a)))
for f, a in sorted(res, key=lambda x: -x[1])[:12]:
    print(f"  {f:14s} {a:.3f}")

print("\n=== categorical: High-rate spread (mean y per category) ===")
for f in C.LOWCARD_CATS + C.HIGHCARD_CATS:
    g = df.groupby(f)["y_priority"].agg(["mean", "size"])
    pure = g[(g["size"] >= 5) & ((g["mean"] == 0) | (g["mean"] == 1))]
    print(f"  {f:15s} range[{g['mean'].min():.2f},{g['mean'].max():.2f}] nuniq={len(g)} "
          f"pure(>=5)={len(pure)}")

# Is priority a deterministic function of event_cause?
print("\n=== priority High-rate by event_cause ===")
print(df.groupby("event_cause")["y_priority"].agg(["mean", "size"]).round(3).to_string())

# Cause x veh_type combos pure?
print("\n=== does (event_cause) alone classify perfectly? check overlap ===")
g = df.groupby("event_cause")["y_priority"].mean()
mixed = g[(g > 0.02) & (g < 0.98)]
print(f"  causes with MIXED priority (not near-pure): {list(mixed.index)}")
