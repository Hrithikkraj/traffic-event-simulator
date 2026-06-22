#!/bin/bash
# Launch the Gridlock dashboard (sets libomp env so LightGBM models load).
export DYLD_LIBRARY_PATH="/opt/homebrew/opt/libomp/lib:$DYLD_LIBRARY_PATH"
export PYTHONWARNINGS="ignore"
DIR="$(cd "$(dirname "$0")" && pwd)"
exec streamlit run "$DIR/src/app.py" "$@"
