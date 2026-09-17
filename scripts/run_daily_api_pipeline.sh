#!/bin/bash

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "========================================"
echo "AIRFAREX DAILY API PIPELINE"
echo "========================================"

echo "[1/3] Fetching latest API data..."
set +e
python3 scripts/fetch_friend_api.py
FETCH_RC=$?
set -e

if [ "$FETCH_RC" -eq 2 ]; then
    echo "No new API records. Skipping pipeline + index rebuild."
    SKIP_PIPELINE=1
elif [ "$FETCH_RC" -ne 0 ]; then
    echo "ERROR: fetch_friend_api.py failed with exit code $FETCH_RC"
    exit "$FETCH_RC"
else
    SKIP_PIPELINE=0
fi

if [ "$SKIP_PIPELINE" -eq 0 ]; then
    echo "[2/3] Running data pipeline..."
    python3 scripts/run_real_pipeline.py

    echo "[3/3] Building airfare index..."
    python3 scripts/build_real_airfare_index.py
else
    echo "[2/3] Skipped (no new records)."
    echo "[3/3] Skipped (no new records)."
fi


echo "[4/4] Syncing artifacts to GitHub..."
echo "----------------------------------------"

# Only stage tracked artifacts. Raw JSON is untracked and
# must not be pushed (196MB, exceeds GitHub limits).
git add -u
git add .gitignore

if git diff --cached --quiet; then
    echo "No artifact changes to commit. Skipping push."
else
    COMMIT_DATE="$(date '+%Y-%m-%d %H:%M')"
    git commit -m "chore: daily airfare pipeline refresh ${COMMIT_DATE}" \
        --no-verify > /dev/null
    echo "Commit created."

    if git push origin main 2>&1; then
        echo "Push succeeded. Render will auto-deploy."
    else
        echo "WARNING: git push failed. Local commit retained."
        echo "         Investigate when convenient; pipeline output is intact."
    fi
fi

echo "========================================"
echo "AIRFAREX DAILY PIPELINE COMPLETE"
echo "========================================"
