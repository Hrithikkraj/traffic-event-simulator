"""L3 - Prescriptive layer: turn an Event Impact Score into an ACTION plan, and
allocate a finite officer pool across many simultaneous events optimally.

Two capabilities:
 1. recommend(event)  -> manpower / barricades / diversion for one event
 2. allocate(events, budget) -> city-wide 0/1-knapsack (ILP via PuLP) that
    maximizes total mitigated impact under an officer-headcount constraint.
    Most teams stop at prediction; this is the "optimal deployment" deliverable.

Manpower data in ASTraM is too sparse (1.6%) to learn, so the per-event rule is
transparent and grounded in the validated EIS tier + closure probability.
"""
import math
import numpy as np
import pandas as pd
import joblib
import pulp
import config as C

TIER_BASE = {"Low": 1, "Medium": 2, "High": 4, "Critical": 8}
PLANNED_CAUSES = {"public_event", "procession", "vip_movement", "protest"}
_ART = None


def _art():
    global _ART
    if _ART is None:
        _ART = joblib.load(C.MODEL_DIR / "eis_artifacts.pkl")
    return _ART


def _haversine(a, b):
    R = 6371.0
    p = math.pi / 180
    dlat = (b[0] - a[0]) * p
    dlon = (b[1] - a[1]) * p
    h = (math.sin(dlat / 2) ** 2
         + math.cos(a[0] * p) * math.cos(b[0] * p) * math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(h))


def nearest_corridor(corridor):
    """Suggest a diversion target: the geographically nearest *other* arterial."""
    cents = _art()["corridor_centroid"]
    if corridor not in cents:
        return None
    here = (cents[corridor]["latitude"], cents[corridor]["longitude"])
    best, bestd = None, 1e9
    for c, v in cents.items():
        if c in (corridor, "Non-corridor", "unknown"):
            continue
        d = _haversine(here, (v["latitude"], v["longitude"]))
        if d < bestd:
            best, bestd = c, d
    return None if best is None else f"{best} ({bestd:.1f} km)"


def recommend(cause, corridor, eis, tier, closure_prob, duration_h, event_type="unplanned"):
    officers = TIER_BASE.get(tier, 1) + round(4 * closure_prob)
    if cause in PLANNED_CAUSES or event_type == "planned":
        officers = math.ceil(officers * 1.5)
    barricades = math.ceil(closure_prob * 6) if closure_prob > 0.3 else 0
    divert = closure_prob > 0.5 or tier == "Critical"
    alt = nearest_corridor(corridor) if divert else None

    actions = [f"Deploy {officers} field officer(s) to {corridor}"]
    if barricades:
        actions.append(f"Pre-position {barricades} barricade unit(s) (closure prob {closure_prob:.0%})")
    if divert:
        actions.append(f"Activate diversion → {alt}" if alt else "Activate diversion plan")
    if duration_h and duration_h > 3:
        actions.append(f"Stage for long event (~{duration_h:.1f} h); plan shift rotation")
    if tier in ("High", "Critical"):
        actions.append("Notify zone control room + traffic advisory broadcast")

    return {"officers_needed": int(officers), "barricades": int(barricades),
            "diversion": bool(divert), "diversion_target": alt, "actions": actions}


def allocate(events, budget, mode="priority"):
    """events: DataFrame ['id','EIS','officers_needed']. Two doctrines:
      - 'priority'  : cover the HIGHEST-impact events first (operational triage).
      - 'efficiency': ILP 0/1-knapsack maximizing total covered EIS (throughput).
    Under-resourcing is the norm here, so we also report the headcount deficit."""
    ev = events.reset_index(drop=True).copy()
    ev["EIS"] = ev["EIS"].astype(float)
    ev["officers_needed"] = ev["officers_needed"].astype(int).clip(lower=1)
    chosen = np.zeros(len(ev), dtype=int)

    if mode == "efficiency":
        prob = pulp.LpProblem("officer_allocation", pulp.LpMaximize)
        x = [pulp.LpVariable(f"x{i}", cat="Binary") for i in range(len(ev))]
        prob += pulp.lpSum(ev.loc[i, "EIS"] * x[i] for i in range(len(ev)))
        prob += pulp.lpSum(ev.loc[i, "officers_needed"] * x[i] for i in range(len(ev))) <= budget
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
        chosen = np.array([int(pulp.value(x[i]) or 0) for i in range(len(ev))])
        method = "ILP efficiency (CBC)"
    else:  # priority: worst-first greedy (a commander never skips a VIP for a pothole)
        used = 0
        for i in ev.sort_values("EIS", ascending=False).index:
            if used + ev.loc[i, "officers_needed"] <= budget:
                chosen[i] = 1
                used += ev.loc[i, "officers_needed"]
        method = "priority worst-first"

    ev["staffed"] = chosen
    covered, total = ev.loc[ev.staffed == 1, "EIS"].sum(), ev["EIS"].sum()
    need = int(ev["officers_needed"].sum())
    summary = {
        "method": method, "budget": budget,
        "officers_used": int((ev["officers_needed"] * ev["staffed"]).sum()),
        "officers_needed_total": need, "deficit": max(0, need - budget),
        "events_staffed": int(chosen.sum()), "events_total": len(ev),
        "impact_covered_pct": round(covered / total * 100, 1) if total else 0.0,
        "unmet_high_impact": ev[(ev.staffed == 0) & (ev.EIS >= 80)]["id"].tolist(),
    }
    return ev, summary


if __name__ == "__main__":
    import inference as I
    print("=== per-event recommendations ===")
    for cause, cor, hr, dur in [("vip_movement", "Bellary Road 1", 18, None),
                                ("vehicle_breakdown", "Hosur Road", 9, None),
                                ("public_event", "CBD 1", 18, 4.0)]:
        s = I.score_event(cause, cor, hr, 4, planned_duration_h=dur)
        r = recommend(cause, cor, s["EIS"], s["tier"], s["closure_prob"],
                      s["duration_used_h"], "planned" if dur else "unplanned")
        print(f"\n{cause} @ {cor} {hr}h  EIS={s['EIS']} ({s['tier']})")
        for a in r["actions"]:
            print("   -", a)

    print("\n=== city-wide allocation (surge: 12 events, 20 officers) ===")
    rng = list(range(12))
    rows = []
    scn = [("vip_movement", "Bellary Road 1", 18), ("public_event", "CBD 1", 18),
           ("accident", "Silk Board", 9), ("vehicle_breakdown", "Hosur Road", 9),
           ("protest", "CBD 2", 17), ("tree_fall", "Old Madras Road", 8),
           ("water_logging", "ORR East 1", 19), ("procession", "Mysore Road", 18),
           ("vehicle_breakdown", "Tumkur Road", 2), ("congestion", "ORR North 1", 10),
           ("accident", "Magadi Road", 20), ("pot_holes", "Bannerghata Road", 11)]
    for cause, cor, hr in scn:
        s = I.score_event(cause, cor, hr, 4)
        r = recommend(cause, cor, s["EIS"], s["tier"], s["closure_prob"], s["duration_used_h"])
        rows.append({"id": f"{cause}@{cor}", "EIS": s["EIS"], "officers_needed": r["officers_needed"]})
    ev = pd.DataFrame(rows)
    for mode in ("priority", "efficiency"):
        out, summ = allocate(ev, budget=20, mode=mode)
        print(f"\n--- {mode} ---")
        print(out.sort_values("EIS", ascending=False)[["id", "EIS", "officers_needed", "staffed"]].to_string(index=False))
        print("summary:", summ)
