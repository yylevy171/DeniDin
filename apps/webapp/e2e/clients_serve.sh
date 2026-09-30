#!/usr/bin/env bash
# Feature 087 — seeds the Clients fixture and starts ONE real backend (:8132) wired to the
# Morning sandbox. Foreground - Playwright's webServer owns the lifecycle.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$HERE/../backend"
PY="$BACKEND/venv/bin/python"
[ -x "$PY" ] || { echo "backend venv missing - run: python3 -m venv $BACKEND/venv && $BACKEND/venv/bin/pip install -r $BACKEND/requirements.txt" >&2; exit 1; }

"$PY" "$HERE/seed_clients_fixture.py"

cd "$BACKEND"
PYTHONPATH=src exec "$PY" -m webapp_backend.server "$HERE/.fixture/clients/config.clients.json"
