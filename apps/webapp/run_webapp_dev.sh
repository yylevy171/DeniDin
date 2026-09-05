#!/bin/bash
# Local dev launcher for Feature 068's Ledger Web UI — NOT the containerized dev/prod
# environment (that's Story 10: run_webapp.sh + docker-compose). This just starts the
# backend (uvicorn) and the Vite dev server on the host for quick viewing.
#
#   ./apps/webapp/run_webapp_dev.sh          # backend :8100, frontend :5173
#   open http://localhost:5173               # password: whatever is hashed in backend/auth/password.hash
#
# Ctrl-C stops both.
set -e
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

BACKEND_CONFIG="${1:-config/config.dev.json}"

cd "$HERE/backend"
[ -d venv ] || python3 -m venv venv
./venv/bin/pip -q install -r requirements.txt
PYTHONPATH=src ./venv/bin/python -m uvicorn webapp_backend.server:app_factory --factory \
  --host 127.0.0.1 --port 8100 &
BACKEND_PID=$!

cd "$HERE/frontend"
[ -d node_modules ] || npm install
npx vite --port 5173 &
FRONTEND_PID=$!

trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null' INT TERM EXIT
echo ""
echo "  backend : http://127.0.0.1:8100/health"
echo "  frontend: http://localhost:5173"
echo ""
wait
