#!/usr/bin/env bash
# Idempotent installer for dev-os. Safe to re-run.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv"

echo "== dev-os bootstrap =="

echo
echo "-- Checking dependencies --"
if ! python3 "$REPO_ROOT/bootstrap/checks.py"; then
    echo
    echo "Bootstrap aborted: install the missing dependencies above and re-run."
    exit 1
fi

echo
echo "-- Setting up virtualenv --"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
    echo "Created venv at $VENV_DIR"
else
    echo "venv already exists at $VENV_DIR"
fi

echo
echo "-- Installing devos (editable) --"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -e "$REPO_ROOT"

echo
echo "-- Verifying stub CLI --"
"$VENV_DIR/bin/devos" --version

echo
echo "Bootstrap complete."
echo "Activate the venv with: source $VENV_DIR/bin/activate"
echo "Then run: devos --version"
