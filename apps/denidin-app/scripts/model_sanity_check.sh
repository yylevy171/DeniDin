#!/usr/bin/env bash
# Model sanity check — real BILLED OpenAI calls validating DeniDin's prompt design
# for a given model. Run whenever config.ai_model changes (or to evaluate a
# candidate). See scripts/model_sanity_check.py's docstring for what it checks.
#
#   scripts/model_sanity_check.sh --config config/config.dev.json
#   scripts/model_sanity_check.sh --config config/config.dev.json --model <candidate>
#   scripts/model_sanity_check.sh --config config/config.dev.json --with-mcp --json
#
# BILLED (~6 real responses.create calls). Never in CI. Needs its own fresh,
# explicit human go-ahead each run, same as any billed test.
#
# Full, untruncated output is teed to
#   logs/model_sanity_check/<model>_<timestamp>.txt
# (nothing upstream of that file filters it — read it there, do not re-run just
# to see more).
set -euo pipefail

APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_ROOT"

# Resolve THIS clone's own venv explicitly (never a bare `python3` — CLAUDE.md).
PY="$APP_ROOT/venv/bin/python3"
if [[ ! -x "$PY" ]]; then
  echo "ERROR: $PY not found — create this clone's venv first (python3 -m venv venv && pip install -r requirements.txt)" >&2
  exit 1
fi

# Best-effort model label for the log filename (parse --model, else read config).
MODEL_LABEL=""
CONFIG_PATH=""
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
  case "${args[$i]}" in
    --model) MODEL_LABEL="${args[$((i + 1))]:-}" ;;
    --config) CONFIG_PATH="${args[$((i + 1))]:-}" ;;
  esac
done
if [[ -z "$MODEL_LABEL" && -n "$CONFIG_PATH" && -f "$CONFIG_PATH" ]]; then
  MODEL_LABEL="$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('ai_model','model'))" "$CONFIG_PATH" 2>/dev/null || echo model)"
fi
MODEL_LABEL="${MODEL_LABEL//\//_}"
[[ -z "$MODEL_LABEL" ]] && MODEL_LABEL="model"

OUT_DIR="$APP_ROOT/logs/model_sanity_check"
mkdir -p "$OUT_DIR"
OUT_FILE="$OUT_DIR/${MODEL_LABEL}_$(date +%Y%m%d_%H%M%S).txt"

echo "→ writing full output to $OUT_FILE"
set +e
"$PY" "$APP_ROOT/scripts/model_sanity_check.py" "$@" 2>&1 | tee "$OUT_FILE"
rc="${PIPESTATUS[0]}"
set -e
echo "→ exit $rc  (full output: $OUT_FILE)"
exit "$rc"
