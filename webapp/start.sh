#!/usr/bin/env bash
# Quick-start: install deps and launch RecipeVault Studio at localhost:8765
set -e
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
# Single source of truth: install whatever's in requirements.txt.
# Previously this script kept its own hand-maintained PKGS list, which
# drifted (firebase-admin, stripe, etc. were missing) and produced silent
# "module not found" failures at runtime. Don't do that again.
REQS="$(dirname "$0")/requirements.txt"

echo "Installing webapp dependencies from $REQS ..."

# Try a sequence of pip install variants — different macOS / Linux Python
# installs need different flags. Use the first one that works.
install_ok=0
for flags in \
    "" \
    "--user" \
    "--break-system-packages" \
    "--user --break-system-packages"
do
    if $PYTHON -m pip install --quiet $flags -r "$REQS" 2>/dev/null; then
        echo "  -> installed with flags: '${flags:-default}'"
        install_ok=1
        break
    fi
done

if [ "$install_ok" -ne 1 ]; then
    echo
    echo "Plain pip install failed. Falling back to a local venv at ./.venv ..."
    $PYTHON -m venv .venv
    # shellcheck disable=SC1091
    source .venv/bin/activate
    pip install --quiet --upgrade pip
    pip install --quiet -r "$REQS"
    PYTHON=".venv/bin/python3"
fi

echo
echo "============================================================"
echo "  RecipeVault Studio -> http://localhost:8765"
echo "============================================================"
echo "  Press Ctrl+C to stop."
echo

# Open the browser after a short delay (mac default)
( sleep 1.5 && command -v open >/dev/null && open http://localhost:8765 ) &

exec $PYTHON server.py
