"""Generate DARK-THEME, transparent-background figures for the pitch deck.

Transparent PNGs with light text → they sit cleanly on the dark slides.
Run: /opt/anaconda3/bin/python src/make_figures.py  -> outputs/figures/ppt/*.png
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import config as C

FIG = C.FIG_DIR / "ppt"; FIG.mkdir(parents=True, exist_ok=True)
BLUE, YELLOW = "#5AA0FF", "#FFE11B"
LIGHT, MUTED = "#EAF0FA", "#9AA7B8"
TIER = {"Low": "#2ECC71", "Medium": "#F4B740", "High": "#E67E22", "Critical": "#FF5A5F"}
plt.rcParams.update({
    "font.size": 13.5, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 16, "axes.titleweight": "bold", "figure.dpi": 150,
    "text.color": LIGHT, "axes.labelcolor": LIGHT, "axes.titlecolor": LIGHT,
    "xtick.color": LIGHT, "ytick.color": LIGHT, "axes.edgecolor": MUTED,
    "figure.facecolor": "none", "axes.facecolor": "none", "savefig.transparent": True,
})


def save(name):
    plt.tight_layout(); plt.savefig(FIG / name, dpi=150, bbox_inches="tight", transparent=True); plt.close()


df = pd.read_pickle(C.DATA_DIR / "scored.pkl")
t = pd.to_datetime(df["event_time"]).dt.tz_localize(None)

# 1) Events by hour — the 2 AM hook
by_hr = df.groupby("hour").size()
plt.figure(figsize=(9, 5.0))
plt.bar(by_hr.index, by_hr.values, color=[YELLOW if h == 2 else BLUE for h in by_hr.index])
plt.annotate("Peak at 2 AM —\nfreight breakdowns,\nNOT rush hour", xy=(2, by_hr.max()),
             xytext=(6, by_hr.max()*0.86), fontsize=13, color=YELLOW, fontweight="bold",
             arrowprops=dict(arrowstyle="->", color=YELLOW, lw=2))
plt.xlabel("Hour of day"); plt.ylabel("Events"); plt.title("Events peak at 2 AM, not rush hour")
plt.xticks(range(0, 24, 2)); save("events_by_hour.png")

# 2) Mean EIS by cause — face validity
mc = df.groupby("event_cause")["EIS"].mean().sort_values()
plt.figure(figsize=(8.5, 5.6))
plt.barh(mc.index, mc.values, color=[TIER["Critical"] if v >= 80 else TIER["High"] if v >= 60
         else TIER["Medium"] if v >= 40 else TIER["Low"] for v in mc.values])
plt.xlabel("Mean Event Impact Score (0–100)")
plt.title("EIS ranks disruptive events high (face validity)")
save("eis_by_cause.png")

# 3) Road-closure leaderboard (k-fold PR-AUC)
cv = pd.read_csv(C.METRIC_DIR / "closure_cv.csv").sort_values("PR_AUC")
plt.figure(figsize=(8.5, 5.4))
plt.barh(cv["model"], cv["PR_AUC"], color=[YELLOW if m == "STACK_logit" else BLUE for m in cv["model"]])
plt.axvline(0.083, color=TIER["Critical"], ls="--", lw=2)
plt.text(0.088, 0.2, "prevalence\nbaseline 0.083", color=TIER["Critical"], fontsize=11)
plt.xlabel("PR-AUC (5-fold CV)"); plt.title("Road-closure: 10-model zoo + stacked ensemble")
save("closure_leaderboard.png")

# 4) Daily volume with surge days annotated
daily = df.assign(d=t.dt.date).groupby("d").size()
plt.figure(figsize=(9.5, 4.9))
plt.plot(daily.index, daily.values, color=BLUE, lw=1.8)
plt.axhline(daily.median(), color=MUTED, ls=":", lw=1.5, label=f"median {daily.median():.0f}/day")
for d, v in daily.sort_values(ascending=False).head(2).items():
    plt.annotate(f"{v} events", xy=(d, v), xytext=(d, v+14), fontsize=12, color=TIER["Critical"],
                 ha="center", fontweight="bold", arrowprops=dict(arrowstyle="->", color=TIER["Critical"]))
plt.ylabel("Events per day"); plt.title("Demand spikes are real — and forecastable")
plt.legend(facecolor="none", edgecolor=MUTED, labelcolor=LIGHT); save("daily_volume.png")

# 5) Learning-loop bias by cause (L4)
pb = pd.read_csv(C.PRED_DIR / "learning_playbook_by_cause.csv").sort_values("model_bias_hrs")
plt.figure(figsize=(8.5, 5.6))
plt.barh(pb["event_cause"], pb["model_bias_hrs"],
         color=[TIER["Critical"] if b > 1 else TIER["High"] if b > 0 else BLUE for b in pb["model_bias_hrs"]])
plt.axvline(0, color=LIGHT, lw=1.2)
plt.xlabel("Model bias: actual − predicted (hours)")
plt.title("L4 learning loop flags where the model drifts")
save("learning_bias.png")

print(f"Saved 5 dark figures -> {FIG}")
