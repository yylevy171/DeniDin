#!/usr/bin/env bash
# Seeds the deterministic fixture and starts BOTH fixture backends (full :8130, empty :8131).
# Foreground — Playwright's webServer owns the lifecycle and kills the process group on teardown.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$HERE/../backend"

python3 "$HERE/seed_fixture.py"

cd "$BACKEND"
PY="$BACKEND/venv/bin/python"
[ -x "$PY" ] || { echo "backend venv missing — run: python3 -m venv $BACKEND/venv && $BACKEND/venv/bin/pip install -r $BACKEND/requirements.txt" >&2; exit 1; }

PYTHONPATH=src "$PY" -m webapp_backend.server "$HERE/.fixture/config.full.json" &
PID_FULL=$!
PYTHONPATH=src "$PY" -m webapp_backend.server "$HERE/.fixture/config.empty.json" &
PID_EMPTY=$!

trap 'kill $PID_FULL $PID_EMPTY 2>/dev/null || true' INT TERM EXIT
wait
