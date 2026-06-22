#!/bin/bash
# Wrapper so LightGBM/XGBoost find libomp (OpenMP runtime) on macOS.
# Usage: bash run.sh src/data_prep.py
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/libomp/lib:$DYLD_LIBRARY_PATH"
export PYTHONWARNINGS="ignore"
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-4}"
exec python3 "$@"
