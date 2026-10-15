#!/usr/bin/env bash
# Feature 087 — seeds the Clients fixture and starts ONE real backend (:8132) wired to the
# Morning sandbox. Foreground - Playwright's webServer owns the lifecycle.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$HERE/../backend"
PY="$BACKEND/venv/bin/python"
[ -x "$PY" ] || { echo "backend venv missing - run: python3 -m venv $BACKEND/venv && $BACKEND/venv/bin/pip install -r $BACKEND/requirements.txt" >&2; exit 1; }

"$PY" "$HERE/seed_clients_fixture.py"

# Feature 089: the agreed total comes from the Agreements DB, so give the ledger-seeded agreements a
# real DB and run the REAL denidin-app Agreements API on it (:8311) for the backend to call.
DENIDIN="$HERE/../../denidin-app"
DPY="$DENIDIN/venv/bin/python3"
[ -x "$DPY" ] || { echo "denidin-app venv missing: $DPY" >&2; exit 1; }
ROOT="$HERE/.fixture/clients"
( cd "$DENIDIN" && "$DPY" "$HERE/agreements_db_import.py" "$ROOT" 8311 e2e-clients-agreements-token )
( cd "$DENIDIN" && exec "$DPY" -m src.services.agreements_api --config "$ROOT/config.denidin.json" --port 8311 ) &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT
for _ in $(seq 1 60); do
  curl -sf "http://127.0.0.1:8311/is_alive" >/dev/null && break
  sleep 0.5
done
curl -sf "http://127.0.0.1:8311/is_alive" >/dev/null || { echo "Agreements API did not come up" >&2; exit 1; }

cd "$BACKEND"
PYTHONPATH=src "$PY" -m webapp_backend.server "$HERE/.fixture/clients/config.clients.json"
