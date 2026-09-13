#!/bin/bash

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "========================================"
echo "AIRFAREX DAILY API PIPELINE"
echo "========================================"

echo "[1/3] Fetching latest API data..."
/opt/anaconda3/bin/python3 scripts/fetch_friend_api.py

echo "[2/3] Running data pipeline..."
/opt/anaconda3/bin/python3 scripts/run_real_pipeline.py

echo "[3/3] Building airfare index..."
/opt/anaconda3/bin/python3 scripts/build_real_airfare_index.py

echo "========================================"
echo "AIRFAREX DAILY PIPELINE COMPLETE"
echo "========================================"
