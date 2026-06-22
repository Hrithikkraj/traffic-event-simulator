"""Central paths, constants, and feature definitions for the Gridlock pipeline."""
import os
from pathlib import Path

# Make LightGBM/XGBoost find libomp even if run.sh wasn't used.
os.environ.setdefault("DYLD_LIBRARY_PATH", "/opt/homebrew/opt/libomp/lib")

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "Astram event data_anonymized - Astram event data_anonymizedb40ac87.csv"
OUT = ROOT / "outputs"
DATA_DIR = OUT / "data"
MODEL_DIR = OUT / "models"
METRIC_DIR = OUT / "metrics"
FIG_DIR = OUT / "figures"
PRED_DIR = OUT / "predictions"
for d in (DATA_DIR, MODEL_DIR, METRIC_DIR, FIG_DIR, PRED_DIR):
    d.mkdir(parents=True, exist_ok=True)

PROCESSED = DATA_DIR / "processed.pkl"

SEED = 42
N_SPLITS = 5            # k for k-fold cross-validation
TIME_SPLIT_DATE = "2024-03-01"   # train < this, validate >= this (temporal holdout)

# Bengaluru bounding box (data-derived) for spatial sanity checks
BLR_BOUNDS = dict(lat_min=12.70, lat_max=13.35, lon_min=77.25, lon_max=77.85)

# Feature groups (filled/validated in data_prep)
LOWCARD_CATS = ["event_type", "event_cause", "veh_type", "corridor",
                "zone", "authenticated", "client_id"]
HIGHCARD_CATS = ["police_station", "junction", "spatial_cluster"]
# NOTE: has_endpoint & segment_km were DROPPED — they derive from end-coordinates
# that are only populated once a road stretch/diversion is defined (a closure
# *outcome*, not a pre-event input). Single-feature AUC 0.976 = textbook leakage.
NUM_FEATS = ["latitude", "longitude", "hour", "dow", "month", "day_of_month",
             "is_weekend", "is_night", "is_rush", "hour_sin", "hour_cos",
             "dow_sin", "dow_cos",
             "desc_len", "desc_words", "has_kannada",
             "kw_bus", "kw_truck", "kw_accident", "kw_signal", "kw_tree",
             "kw_water", "kw_pothole", "kw_vip", "kw_event"]

ALL_FEATS = LOWCARD_CATS + HIGHCARD_CATS + NUM_FEATS

# Event-INTRINSIC features only (NO location). Used to test whether a target is
# genuinely event-driven vs. a static location/source designation. Diagnostics
# showed `priority` is ~95% determined by corridor/junction (a location label),
# so location-based "prediction" of it is circular.
INTRINSIC_LOWCARD = ["event_type", "event_cause", "veh_type", "authenticated"]
INTRINSIC_NUM = ["hour", "dow", "month", "day_of_month", "is_weekend", "is_night",
                 "is_rush", "hour_sin", "hour_cos", "dow_sin", "dow_cos",
                 "desc_len", "desc_words", "has_kannada",
                 "kw_bus", "kw_truck", "kw_accident", "kw_signal", "kw_tree",
                 "kw_water", "kw_pothole", "kw_vip", "kw_event"]
INTRINSIC_FEATS = INTRINSIC_LOWCARD + INTRINSIC_NUM
