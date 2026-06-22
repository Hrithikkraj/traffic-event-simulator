"""Master pipeline — runs every stage end to end.

Run: bash run.sh src/run_all.py          (full, includes Optuna ~8 min)
     bash run.sh src/run_all.py --fast    (skips Optuna tuning)
"""
import sys
import time
import data_prep, train_clearance, train_closure, train_priority, impact_score, forecast, report

STAGES = [
    ("L0  Data prep & features", data_prep.main),
    ("T1  Clearance regression", train_clearance.main),
    ("T2  Road-closure clf",     train_closure.main),
    ("T3  Priority clf (honest)", train_priority.main),
    ("EIS Event Impact Score",   impact_score.main),
    ("L1  Forecast + hotspots + Hawkes", forecast.main),
]
if "--fast" not in sys.argv:
    import tune
    STAGES.append(("OPT Optuna tuning", tune.main))
STAGES.append(("RPT SHAP + summary", report.main))


def main():
    t0 = time.time()
    for i, (name, fn) in enumerate(STAGES, 1):
        print("\n" + "=" * 70)
        print(f"[{i}/{len(STAGES)}] {name}")
        print("=" * 70)
        fn()
    print(f"\n✅ Pipeline complete in {time.time()-t0:.0f}s. See outputs/.")


if __name__ == "__main__":
    main()
