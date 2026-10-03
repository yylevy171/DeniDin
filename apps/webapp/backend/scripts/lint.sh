#!/usr/bin/env bash
# Lint + type-check the webapp backend with this app's own venv (pip install -r
# requirements-dev.txt), using denidin-app's .pylintrc / mypy.ini so both apps share one standard.
# Same pylint gate as `make lint` (--fail-under=7.0).
set -euo pipefail
BACKEND="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RULES="$BACKEND/../../denidin-app"
PY="$BACKEND/venv/bin/python"
cd "$BACKEND"
export PYTHONPATH="$BACKEND/src:$RULES/src:$BACKEND/../../morning-mcp-app/src"
"$PY" -m pylint src/webapp_backend scripts/*.py --rcfile="$RULES/.pylintrc" --fail-under=7.0
"$PY" -m mypy src/webapp_backend --config-file="$RULES/mypy.ini"
