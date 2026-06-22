"""Inference bridge — score ANY event (real or hypothetical) at creation time.

Builds a full feature row from a handful of operator-known inputs, runs the
saved models (closure prob, clearance P50/P90) and maps to the Event Impact
Score using persisted artifacts. Powers the demo's event simulator.
"""
import numpy as np
import pandas as pd
import joblib
import config as C

_RUSH = {8, 9, 10, 11, 17, 18, 19, 20}
_NIGHT = {22, 23, 0, 1, 2, 3, 4, 5}

# cause/vehicle -> description keyword hints (so simulated events look realistic)
_CAUSE_KW = {
    "accident": "kw_accident", "tree_fall": "kw_tree", "water_logging": "kw_water",
    "pot_holes": "kw_pothole", "vip_movement": "kw_vip", "public_event": "kw_event",
    "procession": "kw_event", "protest": "kw_event", "congestion": "kw_signal",
}

_models = None


def _load():
    global _models
    if _models is None:
        _models = {
            "closure": joblib.load(C.MODEL_DIR / "closure_best.pkl"),
            "q50": joblib.load(C.MODEL_DIR / "clearance_q50.pkl"),
            "q90": joblib.load(C.MODEL_DIR / "clearance_q90.pkl"),
            "art": joblib.load(C.MODEL_DIR / "eis_artifacts.pkl"),
        }
    return _models


def time_weight(hour):
    if hour in _RUSH:
        return 2.0
    if hour in _NIGHT:
        return 0.4
    return 1.0


def build_feature_row(event_cause, corridor, hour, dow, veh_type="unknown",
                      event_type="unplanned", month=6, authenticated="yes",
                      zone="unknown", lat=None, lon=None):
    art = _load()["art"]
    if lat is None or lon is None:
        c = art["corridor_centroid"].get(corridor)
        lat, lon = (c["latitude"], c["longitude"]) if c else art["default_latlon"]

    row = {f: 0 for f in C.NUM_FEATS}
    row.update({
        "event_type": event_type, "event_cause": event_cause, "veh_type": veh_type,
        "corridor": corridor, "zone": zone, "authenticated": authenticated, "client_id": "1",
        "police_station": "unknown", "junction": "unknown", "spatial_cluster": "unknown",
        "latitude": lat, "longitude": lon, "hour": hour, "dow": dow, "month": month,
        "day_of_month": 15, "is_weekend": int(dow >= 5),
        "is_night": int(hour in _NIGHT), "is_rush": int(hour in _RUSH),
        "hour_sin": np.sin(2 * np.pi * hour / 24), "hour_cos": np.cos(2 * np.pi * hour / 24),
        "dow_sin": np.sin(2 * np.pi * dow / 7), "dow_cos": np.cos(2 * np.pi * dow / 7),
        "desc_len": 45, "desc_words": 8, "has_kannada": 0,
    })
    if event_cause in _CAUSE_KW:
        row[_CAUSE_KW[event_cause]] = 1
    if veh_type in ("bmtc_bus", "ksrtc_bus", "private_bus"):
        row["kw_bus"] = 1
    if veh_type in ("truck", "heavy_vehicle", "lcv"):
        row["kw_truck"] = 1
    return pd.DataFrame([row])[C.ALL_FEATS]


def score_event(event_cause, corridor, hour, dow, planned_duration_h=None, **kw):
    m = _load()
    art = m["art"]
    X = build_feature_row(event_cause, corridor, hour, dow,
                          event_type=("planned" if planned_duration_h else "unplanned"), **kw)

    closure_prob = float(m["closure"].predict_proba(X)[0, 1])
    p50 = float(np.expm1(m["q50"].predict(X)[0]))
    p90 = float(np.expm1(m["q90"].predict(X)[0]))
    duration = planned_duration_h if planned_duration_h else p50

    # effective congestion duration (chronic for persistent infra, else acute-capped)
    if event_cause in art["persistent_causes"]:
        eff = art["chronic_h"]
    else:
        eff = min(max(duration, 0.1), art["acute_cap"])

    cw = art["corridor_exposure"].get(corridor, 0.6)
    tw = time_weight(hour)
    eis_raw = eff * (1 + 2 * closure_prob) * cw * tw

    ref = art["eis_raw_reference"]
    eis = float(np.searchsorted(ref, eis_raw) / len(ref) * 100)
    tier = ("Critical" if eis >= 95 else "High" if eis >= 80
            else "Medium" if eis >= 50 else "Low")

    return {
        "EIS": round(eis, 1), "tier": tier,
        "closure_prob": round(closure_prob, 3),
        "clearance_p50_h": round(p50, 2), "clearance_p90_h": round(p90, 2),
        "duration_used_h": round(duration, 2),
        "corridor_exposure": round(cw, 2), "time_weight": tw,
    }


if __name__ == "__main__":
    print("Night breakdown (Tumkur Rd, 2am):",
          score_event("vehicle_breakdown", "Tumkur Road", 2, 2, veh_type="truck"))
    print("Rush breakdown (Hosur Rd, 9am):",
          score_event("vehicle_breakdown", "Hosur Road", 9, 2, veh_type="bmtc_bus"))
    print("VIP movement (Bellary Rd 1, 6pm):",
          score_event("vip_movement", "Bellary Road 1", 18, 4))
    print("Planned rally (CBD 1, 6pm, 4h):",
          score_event("public_event", "CBD 1", 18, 6, planned_duration_h=4.0))
