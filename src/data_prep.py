"""L0 — Data cleaning & feature engineering.

Produces outputs/data/processed.pkl with engineered features + the three
supervised targets (clearance time, road closure, priority) and the raw
fields needed for the Event Impact Score.

Run:  bash run.sh src/data_prep.py
"""
import re
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

import config as C


# ---------------------------------------------------------------- helpers
def parse_dt(s):
    """Parse to tz-aware IST timestamps."""
    return pd.to_datetime(s, errors="coerce", utc=True).dt.tz_convert("Asia/Kolkata")


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p = np.pi / 180.0
    dlat = (lat2 - lat1) * p
    dlon = (lon2 - lon1) * p
    a = (np.sin(dlat / 2.0) ** 2
         + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin(dlon / 2.0) ** 2)
    return 2 * R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


KANNADA = re.compile(r"[ಀ-೿]")
KEYWORDS = {
    "kw_bus": r"\bbus\b|bmtc|ksrtc|ಬಸ್",
    "kw_truck": r"truck|lorry|heavy|container|ಲಾರಿ",
    "kw_accident": r"accident|collision|hit|ಅಪಘಾತ",
    "kw_signal": r"signal|junction|circle|cross",
    "kw_tree": r"tree|branch|ಮರ",
    "kw_water": r"water|flood|rain|logging|ಮಳೆ",
    "kw_pothole": r"pot.?hole|road damage|ಗುಂಡಿ",
    "kw_vip": r"\bvip\b|minister|cm |governor|president",
    "kw_event": r"event|match|rally|procession|festival|protest|stadium",
}


# ---------------------------------------------------------------- pipeline
def load():
    df = pd.read_csv(C.CSV, low_memory=False)
    print(f"Loaded {df.shape[0]} rows x {df.shape[1]} cols")
    return df


def clean(df):
    df = df.copy()

    # Standardize categorical text (fix Debris/debris etc.)
    df["event_cause"] = df["event_cause"].astype(str).str.strip().str.lower()
    df["event_type"] = df["event_type"].astype(str).str.strip().str.lower()
    df["veh_type"] = df["veh_type"].fillna("unknown").astype(str).str.strip().str.lower()
    df["corridor"] = df["corridor"].fillna("unknown").astype(str).str.strip()
    df["zone"] = df["zone"].fillna("unknown").astype(str).str.strip()
    df["police_station"] = df["police_station"].fillna("unknown").astype(str).str.strip()
    df["junction"] = df["junction"].fillna("unknown").astype(str).str.strip()
    df["authenticated"] = df["authenticated"].fillna("unknown").astype(str).str.strip().str.lower()
    df["priority"] = df["priority"].astype(str).str.strip().str.title()

    # Datetimes
    for c in ["start_datetime", "closed_datetime", "end_datetime",
              "created_date", "modified_datetime", "resolved_datetime"]:
        df[c + "_dt"] = parse_dt(df[c])

    # Use start time; fall back to created_date when start missing
    df["event_time"] = df["start_datetime_dt"].fillna(df["created_date_dt"])

    # Durations (hours)
    df["clearance_h"] = (df["closed_datetime_dt"] - df["start_datetime_dt"]).dt.total_seconds() / 3600.0
    df["planned_dur_h"] = (df["end_datetime_dt"] - df["start_datetime_dt"]).dt.total_seconds() / 3600.0

    return df


def add_features(df):
    df = df.copy()
    t = df["event_time"]

    # Temporal
    df["hour"] = t.dt.hour
    df["dow"] = t.dt.dayofweek
    df["month"] = t.dt.month
    df["day_of_month"] = t.dt.day
    df["is_weekend"] = (df["dow"] >= 5).astype(int)
    df["is_night"] = df["hour"].isin([22, 23, 0, 1, 2, 3, 4, 5, 6]).astype(int)
    df["is_rush"] = df["hour"].isin([8, 9, 10, 11, 17, 18, 19, 20]).astype(int)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["dow_sin"] = np.sin(2 * np.pi * df["dow"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["dow"] / 7)

    # Spatial
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["has_endpoint"] = df["endlatitude"].notna().astype(int)
    df["segment_km"] = haversine_km(df["latitude"], df["longitude"],
                                    pd.to_numeric(df["endlatitude"], errors="coerce"),
                                    pd.to_numeric(df["endlongitude"], errors="coerce"))
    df["segment_km"] = df["segment_km"].fillna(0.0).clip(0, 50)

    # KMeans spatial clusters (unsupervised on coords -> low leakage risk)
    coords = df[["latitude", "longitude"]].copy()
    med = coords.median()
    coords = coords.fillna(med)
    km = KMeans(n_clusters=40, random_state=C.SEED, n_init=10)
    df["spatial_cluster"] = km.fit_predict(coords).astype(str)
    df["latitude"] = df["latitude"].fillna(med["latitude"])
    df["longitude"] = df["longitude"].fillna(med["longitude"])

    # Text features from description
    desc = df["description"].fillna("").astype(str)
    df["desc_len"] = desc.str.len()
    df["desc_words"] = desc.str.split().apply(len)
    df["has_kannada"] = desc.apply(lambda s: int(bool(KANNADA.search(s))))
    low = desc.str.lower()
    for col, pat in KEYWORDS.items():
        df[col] = low.str.contains(pat, regex=True, na=False).astype(int)

    df["client_id"] = df["client_id"].astype(str)
    return df


def add_targets(df):
    df = df.copy()
    # T1: clearance time (unplanned, valid & sane). Live-congestion regime <= 72h.
    valid = (df["event_type"] == "unplanned") & df["clearance_h"].notna()
    df["clear_target_h"] = np.where(valid, df["clearance_h"], np.nan)
    # keep strictly positive, drop absurd; cap heavy tail for the live regime
    df.loc[df["clear_target_h"] <= 0, "clear_target_h"] = np.nan
    df["is_clear_label"] = (df["clear_target_h"].notna() & (df["clear_target_h"] <= 72)).astype(int)
    df["y_clear_log"] = np.log1p(df["clear_target_h"].where(df["is_clear_label"] == 1))

    # T2: road closure (all rows)
    df["y_closure"] = df["requires_road_closure"].astype(int)

    # T3: priority High vs Low (rows with a valid label)
    df["y_priority"] = np.where(df["priority"] == "High", 1,
                                np.where(df["priority"] == "Low", 0, np.nan))

    # regime flag: transient (live) vs persistent (infra ticket)
    persistent_causes = {"pot_holes", "road_conditions", "construction", "water_logging", "debris"}
    df["is_persistent"] = df["event_cause"].isin(persistent_causes).astype(int)
    return df


def main():
    df = load()
    df = clean(df)
    df = add_features(df)
    df = add_targets(df)

    # impute any residual nulls in numeric features (e.g. 2 rows w/ no timestamp)
    for f in C.NUM_FEATS:
        if f in df.columns and df[f].isna().any():
            df[f] = df[f].fillna(df[f].median())

    # sanity report
    print("\n=== TARGET AVAILABILITY ===")
    print(f"  clearance labels (unplanned, 0<h<=72): {int(df['is_clear_label'].sum())}")
    print(f"  closure positives: {int(df['y_closure'].sum())} / {len(df)} "
          f"({df['y_closure'].mean()*100:.1f}%)")
    print(f"  priority labels: {int(df['y_priority'].notna().sum())}, "
          f"High rate: {df['y_priority'].mean()*100:.1f}%")

    print("\n=== FEATURE NULL CHECK (engineered) ===")
    feats = [f for f in C.ALL_FEATS if f in df.columns]
    nulls = df[feats].isna().sum()
    print(nulls[nulls > 0].to_string() if nulls.sum() else "  no nulls in engineered features ✔")

    missing = [f for f in C.ALL_FEATS if f not in df.columns]
    if missing:
        print("  MISSING FEATURE COLUMNS:", missing)

    df.to_pickle(C.PROCESSED)
    print(f"\nSaved processed dataset -> {C.PROCESSED}  shape={df.shape}")


if __name__ == "__main__":
    main()
