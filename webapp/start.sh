#!/usr/bin/env bash
# Quick-start: install deps and launch RecipeVault Studio at localhost:8765
set -e
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
REQS="requirements.txt"

# Prefer a project venv (required on Homebrew Python / PEP 668).
if [ -x ".venv/bin/python3" ]; then
    PYTHON=".venv/bin/python3"
else
    echo "Creating virtualenv at webapp/.venv ..."
    $PYTHON -m venv .venv
    PYTHON=".venv/bin/python3"
fi

echo "Installing webapp dependencies from $REQS ..."
$PYTHON -m pip install --quiet --upgrade pip
$PYTHON -m pip install --quiet -r "$REQS"

echo
echo "============================================================"
echo "  RecipeVault Studio -> http://localhost:8765"
echo "============================================================"
echo "  Press Ctrl+C to stop."
echo

# Open the browser after a short delay (mac default)
( sleep 1.5 && command -v open >/dev/null && open http://localhost:8765 ) &

exec $PYTHON server.py
