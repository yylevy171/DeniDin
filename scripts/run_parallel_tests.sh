#!/usr/bin/env bash
set -uo pipefail

# ============================================================================
# General-purpose PARALLEL runner for denidin-app billed / expensive tests.
#
# This is the NON-sanity sibling of scripts/run_sanity_parallel.sh (Feature 075).
# Same engine — pytest-xdist, `--dist loadfile`, per-worker `test_data/<worker>/`
# isolation, an infra-signature retry round — but it runs an ARBITRARY set of
# tests you name, with no `-m sanity` filter and no morning-mcp gate by default.
#
# Built for Feature 069's acceptance suite (many billed E2E files that are
# independent and slow), but works for any billed/expensive subset.
#
# WHY `--dist loadfile` (not `--dist load`): every test FILE is pinned to ONE
# worker, so a file that deliberately builds up one long shared WhatsApp
# conversation across its tests keeps its ordering. Parallelism therefore comes
# from spreading DISTINCT FILES across workers — a single-file target runs
# effectively serially. Split a big file into per-class/per-story files to
# parallelize it (Feature 069 did this: tests/billed/test_e2e_ledger_069_*_billed.py).
#
# WHAT MAKES IT SAFE:
#   - tests/e2e_helpers.py::sanity_worker_data_root() keys the data root off
#     PYTEST_XDIST_WORKER (NOT off any sanity flag), and tests/billed/conftest.py
#     already routes denidin_config.data_root + its autouse ledger/reminder
#     cleanup through it — so ChromaDB / ledger-event JSON / reminders.db /
#     sessions never collide between workers, on ANY `-n` run.
#   - The Morning MCP server is plain HTTP (concurrent requests fine); billed
#     tests seed fresh unique clients per run.
#   - The single shared ngrok free-tier tunnel is the real concurrency ceiling
#     (not OpenAI/sandbox). Under load it can brown out for ~60-90s; every
#     in-flight MCP call then fails with a transport signature. Those — and only
#     those — are re-run once (scripts/_sanity_retryable_failures.py). Real
#     assertion failures and model nondeterminism are terminal, never re-run.
#
# 🚨 EXPENSIVE: CLAUDE.md requires a fresh explicit human approval for EVERY
# expensive test, one at a time. This script does NOT grant that. Passing
# `-m expensive` / expensive node ids is YOU asserting you have taken that on
# for this exact invocation (same stance as run_sanity_parallel.sh's subset
# mode). Prefer scripts/run_single_test.sh for expensive.
#
# PRECONDITION: apps/morning-mcp-app must already be running for its env
# (./run_morning_mcp.sh dev). This script starts NO containers.
#
# Usage:
#   scripts/run_parallel_tests.sh <target> [<target> ...]
#   scripts/run_parallel_tests.sh -n 6 -m "billed" tests/billed/test_e2e_ledger_069_*_billed.py
#   scripts/run_parallel_tests.sh tests/billed/test_foo.py::TestX::test_a tests/billed/test_bar.py::TestY::test_b
#   scripts/run_parallel_tests.sh --gate tests/billed/...        # run the morning-mcp gate first
#   scripts/run_parallel_tests.sh --no-retry -n 4 tests/billed/...
#
#   <target>  a pytest node id, file, or directory, relative to apps/denidin-app/
#             (globs are expanded by your shell before the script sees them).
#
# Options:
#   -n N                   worker count. Default: number of distinct FILES among
#                          the targets (so each file gets its own worker), min 1,
#                          capped at 6 unless you pass a higher -n explicitly.
#   -m EXPR                pytest -m expression. Default: "billed". Use
#                          "expensive" or "billed or expensive" as needed.
#   --gate / --no-gate     run (or skip) the morning-mcp-app gate test first.
#                          Default: skip.
#   --no-retry             single pass, no infra retry round.
#   --retry-max-rounds N   initial round + (N-1) retry rounds. Default 2.
#   --retry-delay S        seconds before the first retry round. Default 0.
#   --retry-factor F       multiply the delay by F each further round. Default 1.5.
#   -h | --help
#
# Exit 0 = every named test (+ gate if run) passed, possibly after the retry
# round. Exit 1 = >=1 terminal failure, or an infra failure still red after the
# last retry round (both listed separately at the end). Exit 2 = bad args /
# missing venv / missing xdist. Exit 3 = the gate test failed (nothing else run).
# ============================================================================

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEN_DIR="${ROOT}/apps/denidin-app"
MM_SINGLE="${ROOT}/apps/morning-mcp-app/scripts/run_single_test.sh"
VENV_PY="${DEN_DIR}/venv/bin/python3"
RESULTS_DIR="${DEN_DIR}/logs/test_logs/pytest_results"
CLASSIFIER="${ROOT}/scripts/_sanity_retryable_failures.py"
GATE_NODE="tests/billed/test_openai_invokes_mcp_e2e.py::test_openai_invokes_create_invoice_via_remote_mcp"

NPROCS=""
NPROCS_EXPLICIT=0
MARKER="billed"
RUN_GATE=0
RETRY=1
RETRY_MAX_ROUNDS=2
RETRY_DELAY=0
RETRY_FACTOR="1.5"
TARGETS=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    -n)                 NPROCS="${2:-}"; NPROCS_EXPLICIT=1; shift 2 ;;
    -n*)                NPROCS="${1#-n}"; NPROCS_EXPLICIT=1; shift ;;
    -m)                 MARKER="${2:-}"; shift 2 ;;
    -m*)                MARKER="${1#-m}"; shift ;;
    --gate)             RUN_GATE=1; shift ;;
    --no-gate)          RUN_GATE=0; shift ;;
    --no-retry)         RETRY=0; shift ;;
    --retry-max-rounds) RETRY_MAX_ROUNDS="${2:-}"; shift 2 ;;
    --retry-delay)      RETRY_DELAY="${2:-}"; shift 2 ;;
    --retry-factor)     RETRY_FACTOR="${2:-}"; shift 2 ;;
    -h|--help)          sed -n '1,96p' "$0"; exit 0 ;;
    -*)                 echo "unknown flag: $1 (see --help)" >&2; exit 2 ;;
    *)                  TARGETS+=("$1"); shift ;;
  esac
done

if [ "${#TARGETS[@]}" -eq 0 ]; then
  echo "ERROR: name at least one test target (node id / file / dir). See --help." >&2
  exit 2
fi
case "$RETRY_MAX_ROUNDS" in ''|*[!0-9]*|0) echo "ERROR: --retry-max-rounds needs a positive integer" >&2; exit 2 ;; esac
case "$RETRY_DELAY" in ''|*[!0-9]*) echo "ERROR: --retry-delay needs a non-negative integer" >&2; exit 2 ;; esac

# Resolve worker count: default = #distinct files among the targets, capped at 6.
if [ "$NPROCS_EXPLICIT" -eq 0 ]; then
  NPROCS="$(printf '%s\n' "${TARGETS[@]}" | sed 's/::.*//' | sort -u | grep -c .)"
  [ "$NPROCS" -gt 6 ] && NPROCS=6
fi
case "$NPROCS" in ''|*[!0-9]*|0) echo "ERROR: -n needs a positive integer, got '$NPROCS'" >&2; exit 2 ;; esac

if [ ! -x "$VENV_PY" ]; then
  echo "ERROR: no usable venv interpreter at $VENV_PY" >&2
  echo "       cd $DEN_DIR && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt" >&2
  exit 2
fi
if ! "$VENV_PY" -c "import xdist" >/dev/null 2>&1; then
  echo "ERROR: pytest-xdist is not installed in this clone's venv." >&2
  echo "       cd $DEN_DIR && ./venv/bin/pip install -r requirements.txt" >&2
  exit 2
fi

case " $MARKER " in
  *expensive*) echo ">>> NOTE: -m '${MARKER}' includes EXPENSIVE — you are asserting per-test approval for this run (CLAUDE.md)." ;;
esac

echo "############################################################"
echo "# PARALLEL TEST RUN   (${#TARGETS[@]} target(s); -n ${NPROCS}, --dist loadfile, -m '${MARKER}')"
echo "# interpreter: $("$VENV_PY" -c 'import sys; print(sys.executable)')"
echo "############################################################"

# --- 1. optional morning-mcp gate (serial, first) --------------------------
if [ "$RUN_GATE" -eq 1 ]; then
  echo
  echo ">>> GATE (morning-mcp-app, serial): ${GATE_NODE}"
  if [ ! -x "$MM_SINGLE" ]; then echo "ERROR: missing/broken gate runner: $MM_SINGLE" >&2; exit 2; fi
  if ! "$MM_SINGLE" "$GATE_NODE"; then
    echo
    echo "############################################################"
    echo "# GATE FAILED — the Morning tunnel / remote-MCP / sandbox path is broken."
    echo "# Every downstream billed test would fail too. Stopping."
    echo "############################################################"
    exit 3
  fi
  echo ">>> GATE PASSED"
fi

# --- 2. the parallel round(s) --------------------------------------------
mkdir -p "$RESULTS_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
RESULTS_FILE="${RESULTS_DIR}/_parallel_${TS}.txt"

# Clear stale per-worker roots from an earlier parallel run (gitignored,
# worker-only — never the canonical test_data/ itself).
rm -rf "${DEN_DIR}/test_data/gw"* "${DEN_DIR}/test_data/master" 2>/dev/null || true

echo
echo ">>> RUN  ->  ${RESULTS_FILE#$ROOT/}"
echo "    (streams little while workers run; the file has everything)"

run_round() {
  local label="$1" nproc="$2"; shift 2
  {
    echo
    echo "############################################################"
    echo "### ${label}   (-n ${nproc}, --dist loadfile, -m '${MARKER}')"
    echo "############################################################"
  } | tee -a "$RESULTS_FILE"
  ( cd "$DEN_DIR" && SANITY_PARALLEL_SOUNDOFF=1 "$VENV_PY" -m pytest "$@" \
      -m "$MARKER" \
      -n "$nproc" --dist loadfile \
      -p "no:cacheprovider" \
      --durations=25 --durations-min=1.0 \
      --tb=short -ra -v ) 2>&1 | tee -a "$RESULTS_FILE"
  ROUND_EXIT="${PIPESTATUS[0]}"
}

: > "$RESULTS_FILE"
run_round "ROUND 1 / ${RETRY_MAX_ROUNDS}" "$NPROCS" "${TARGETS[@]}"
EXIT_CODE="$ROUND_EXIT"

ROUND=1
DELAY="$RETRY_DELAY"
RETRY_STATUS=""
STILL_RED_INFRA=""

while [ "$EXIT_CODE" -ne 0 ] && [ "$RETRY" -eq 1 ] && [ "$ROUND" -lt "$RETRY_MAX_ROUNDS" ]; do
  RETRYABLE=()
  while IFS= read -r _line; do
    [ -n "$_line" ] && RETRYABLE+=("$_line")
  done < <("$VENV_PY" "$CLASSIFIER" "$RESULTS_FILE")

  if [ "${#RETRYABLE[@]}" -eq 0 ]; then
    RETRY_STATUS="no infra-signature failures — nothing retried"
    break
  fi

  ROUND=$((ROUND + 1))
  echo
  echo ">>> RETRY ROUND ${ROUND}/${RETRY_MAX_ROUNDS}: ${#RETRYABLE[@]} infra-signature failure(s); delay ${DELAY}s"
  printf '      %s\n' "${RETRYABLE[@]}"
  if [ "$DELAY" -gt 0 ] 2>/dev/null; then sleep "$DELAY"; fi

  rfiles=$(printf '%s\n' "${RETRYABLE[@]}" | sed 's/::.*//' | sort -u | grep -c .)
  rn=$NPROCS; [ "$rfiles" -lt "$NPROCS" ] && rn=$rfiles
  run_round "RETRY ROUND ${ROUND} / ${RETRY_MAX_ROUNDS} (delay was ${DELAY}s)" "$rn" "${RETRYABLE[@]}"
  EXIT_CODE="$ROUND_EXIT"

  DELAY=$(awk -v d="$DELAY" -v f="$RETRY_FACTOR" 'BEGIN{ if(d<=0){print 0}else{printf "%.0f", d*f} }')

  if [ "$EXIT_CODE" -ne 0 ]; then
    STILL_RED_INFRA=$(printf '%s\n' "${RETRYABLE[@]}")
    RETRY_STATUS="retried ${#RETRYABLE[@]}; still red after round ${ROUND}"
  else
    RETRY_STATUS="retried ${#RETRYABLE[@]}; all green on round ${ROUND}"
  fi
done

# --- 3. final report ----------------------------------------------------
echo
echo "############################################################"
if [ "$EXIT_CODE" -eq 0 ]; then
  echo "# PARALLEL TEST RUN: ALL PASSED  (${#TARGETS[@]} target(s), -n ${NPROCS}, -m '${MARKER}')"
  [ -n "$RETRY_STATUS" ] && echo "#   retry: ${RETRY_STATUS}"
else
  ALL_FAILED=$(grep -hE "^(FAILED|ERROR) " "$RESULTS_FILE" | awk '{print $2}' | sort -u)
  INFRA_RED=$(printf '%s\n' "$STILL_RED_INFRA" | sed '/^$/d' | sort -u)
  TERMINAL=$(comm -23 <(printf '%s\n' "$ALL_FAILED") <(printf '%s\n' "$INFRA_RED") 2>/dev/null || printf '%s\n' "$ALL_FAILED")

  echo "# PARALLEL TEST RUN: FAILURES  (${#TARGETS[@]} target(s), -n ${NPROCS}, -m '${MARKER}')"
  [ -n "$RETRY_STATUS" ] && echo "#   retry: ${RETRY_STATUS}"
  if [ -n "$(printf '%s' "$TERMINAL" | tr -d '[:space:]')" ]; then
    echo "#"
    echo "#   TERMINAL failures (real — assertion / model, NOT retried):"
    printf '%s\n' "$TERMINAL" | sed '/^$/d;s/^/#     /'
  fi
  if [ -n "$(printf '%s' "$INFRA_RED" | tr -d '[:space:]')" ]; then
    echo "#"
    echo "#   INFRA-signature failures still red after ${ROUND} round(s):"
    printf '%s\n' "$INFRA_RED" | sed '/^$/d;s/^/#     /'
  fi
fi
echo "#"
echo "#   full output : ${RESULTS_FILE#$ROOT/}"
echo "############################################################"

exit "$EXIT_CODE"
