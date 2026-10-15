#!/usr/bin/env bash
# Feature 089 - seeds the Agreements fixture, then starts the REAL denidin-app Agreements API
# (:8310) and the REAL webapp backend (:8133) wired to it. Foreground - Playwright's webServer
# owns the lifecycle; the API is stopped when this script exits.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DENIDIN="$HERE/../../denidin-app"
BACKEND="$HERE/../backend"
DPY="$DENIDIN/venv/bin/python3"
BPY="$BACKEND/venv/bin/python"
[ -x "$DPY" ] || { echo "denidin-app venv missing: $DPY" >&2; exit 1; }
[ -x "$BPY" ] || { echo "webapp backend venv missing: $BPY" >&2; exit 1; }
ROOT="$HERE/.fixture/agreements"

( cd "$DENIDIN" && "$DPY" "$HERE/seed_agreements_fixture.py" )

( cd "$DENIDIN" && exec "$DPY" -m src.services.agreements_api --config "$ROOT/config.denidin.json" --port 8310 ) &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT

for _ in $(seq 1 60); do
  curl -sf "http://127.0.0.1:8310/is_alive" >/dev/null && break
  sleep 0.5
done
curl -sf "http://127.0.0.1:8310/is_alive" >/dev/null || { echo "Agreements API did not come up" >&2; exit 1; }

cd "$BACKEND"
"$BPY" "$HERE/agreements_backend.py" "$ROOT/config.backend.json" "$ROOT/manifest.json"
