#!/usr/bin/env bash
set -uo pipefail

# ============================================================================
# Feature 075 - the PARALLEL sanity sweep.
#
# A fast "is the whole billed sanity subset green?" pass. This is a SEPARATE
# entrypoint from scripts/run_sanity.sh - not a mode of it. run_sanity.sh keeps
# its whole contract unchanged (one test per process, live
# `>>> SANITY [k/N] PASSED|FAILED` sound-off, stop-on-first-failure, resumable
# sanity_state.tsv) because that contract is inherently sequential and was
# shaped by explicit user incidents. This script trades all of that for wall
# time: it runs the denidin-app billed sanity tests concurrently with
# pytest-xdist, file-level (`--dist loadfile` - every test FILE pinned to one
# worker, so the deliberate within-file "one long shared chat" ordering is
# preserved; different files run in parallel).
#
# What makes this safe (see specs/backlog/075-parallelize-test-suite/spec.md):
#   - Each xdist worker gets its own test_data/<worker>/ subtree
#     (tests/e2e_helpers.py::sanity_worker_data_root, keyed off PYTEST_XDIST_WORKER)
#     so ChromaDB / ledger-event JSON / reminders.db / sessions never collide,
#     and tests/billed/conftest.py's autouse before-AND-after cleanup fixtures
#     only ever touch their own worker's state.
#   - The Morning MCP server is plain HTTP (concurrent requests fine); billed
#     tests seed fresh unique clients per run. Count/summary-sensitive tests on
#     fixed ground-truth clients are the known risk - see spec.md's audit list.
#
# Retry rounds (Feature 075): the single shared ngrok free-tier tunnel is the
# real concurrency ceiling - under load it can brown out for ~60-90s, during
# which every in-flight MCP call fails (OpenAI reports mcp_network_error /
# "Connection failed." / a 424 "Failed Dependency" on the tool-list fetch). That
# is harness-induced infra, not a product defect, so after the initial round the
# sweep re-runs ONLY the failures whose traceback carries such a signature
# (scripts/_sanity_retryable_failures.py). Real assertion failures and model
# nondeterminism are terminal - never re-run. Defaults: one initial round + one
# retry round, retry starts immediately (delay 0). Override with
# --retry-max-rounds / --retry-delay / --retry-factor, or --no-retry.
#
# Precondition (same as run_sanity.sh): apps/morning-mcp-app must already be
# running for its env (./run_morning_mcp.sh dev). This script starts NO
# containers.
#
# Usage:
#   ./scripts/run_sanity_parallel.sh            # gate (serial) + all billed sanity at -n 6
#   ./scripts/run_sanity_parallel.sh -n 12      # bump worker count
#   ./scripts/run_sanity_parallel.sh --no-gate  # skip the morning-mcp gate test
#   ./scripts/run_sanity_parallel.sh --gate     # force the gate on (default when a
#                                               # subset is given, the gate is OFF)
#   ./scripts/run_sanity_parallel.sh --no-retry # single pass, no retry round
#   ./scripts/run_sanity_parallel.sh --retry-max-rounds 3 --retry-delay 5 --retry-factor 1.5
#
#   # SUBSET: pass explicit sanity node ids as trailing args - runs just those,
#   # one parallel round. -n defaults to the number of distinct FILES among them
#   # (so each file gets its own worker), capped by an explicit -n if given.
#   # A subset that names tests/expensive/ node ids opts INTO expensive (the
#   # caller has taken on the per-test approval each still needs - CLAUDE.md).
#   ./scripts/run_sanity_parallel.sh \
#       tests/billed/test_group_etiquette_billed.py::TestGroupEtiquetteBilled::test_case1_default_address_gets_substantive_reply \
#       tests/billed/test_simple_text_e2e.py::TestSimpleTextE2E::test_e2e_simple_text_message_hebrew
#   ./scripts/run_sanity_parallel.sh -n 8 <node_id> <node_id> ...   # exactly 8 workers
#
# Exit 0 = every gate + sanity test passed (possibly after the retry round).
# Exit 1 = at least one terminal failure, OR an infra-signature failure that was
# still red after the retry round (both listed, separately, at the end). Exit 2
# = bad args / missing venv. Exit 3 = the morning-mcp gate test failed (a
# broken tunnel fails everything downstream - nothing else is run).
#
# EXPENSIVE sanity tests are not run by the FULL sweep - same rule as
# run_sanity.sh (CLAUDE.md: fresh explicit approval for EVERY expensive test).
# A subset MAY name them (see above). `./scripts/run_sanity.sh --status` shows
# what the serial runner still owes.
# ============================================================================

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEN_DIR="${ROOT}/apps/denidin-app"
MM_SINGLE="${ROOT}/apps/morning-mcp-app/scripts/run_single_test.sh"
VENV_PY="${DEN_DIR}/venv/bin/python3"
RESULTS_DIR="${DEN_DIR}/logs/test_logs/pytest_results"

GATE_NODE="tests/billed/test_openai_invokes_mcp_e2e.py::test_openai_invokes_create_invoice_via_remote_mcp"

NPROCS=""            # empty => auto (6 for the full run; #files for a subset)
GATE_FLAG=""         # "", "on", "off"
RETRY=1              # 0 via --no-retry
RETRY_MAX_ROUNDS=2   # initial round + (RETRY_MAX_ROUNDS - 1) retry rounds
RETRY_DELAY=0        # seconds before the FIRST retry round
RETRY_FACTOR="1.5"   # each further retry round multiplies the delay by this
NODE_IDS=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    -n)                NPROCS="${2:-}"; shift 2 ;;
    -n*)               NPROCS="${1#-n}"; shift ;;
    --no-gate)         GATE_FLAG="off"; shift ;;
    --gate)            GATE_FLAG="on"; shift ;;
    --no-retry)        RETRY=0; shift ;;
    --retry-max-rounds) RETRY_MAX_ROUNDS="${2:-}"; shift 2 ;;
    --retry-delay)     RETRY_DELAY="${2:-}"; shift 2 ;;
    --retry-factor)    RETRY_FACTOR="${2:-}"; shift 2 ;;
    -h|--help)         sed -n '1,72p' "$0"; exit 0 ;;
    -*)                echo "unknown flag: $1 (see --help)" >&2; exit 2 ;;
    *)                 NODE_IDS+=("$1"); shift ;;
  esac
done
case "$RETRY_MAX_ROUNDS" in ''|*[!0-9]*|0) echo "ERROR: --retry-max-rounds needs a positive integer" >&2; exit 2 ;; esac
case "$RETRY_DELAY" in ''|*[!0-9]*) echo "ERROR: --retry-delay needs a non-negative integer" >&2; exit 2 ;; esac
CLASSIFIER="${ROOT}/scripts/_sanity_retryable_failures.py"

SUBSET=0
[ "${#NODE_IDS[@]}" -gt 0 ] && SUBSET=1

# Gate: on by default for a full run, off by default for a subset; --gate/--no-gate override.
if [ -n "$GATE_FLAG" ]; then
  [ "$GATE_FLAG" = "on" ] && RUN_GATE=1 || RUN_GATE=0
else
  [ "$SUBSET" -eq 1 ] && RUN_GATE=0 || RUN_GATE=1
fi

# Resolve worker count.
if [ -z "$NPROCS" ]; then
  if [ "$SUBSET" -eq 1 ]; then
    NPROCS="$(printf '%s\n' "${NODE_IDS[@]}" | sed 's/::.*//' | sort -u | grep -c .)"
  else
    NPROCS=6   # one shared ngrok free-tier tunnel is the concurrency ceiling,
               # not OpenAI/sandbox: -n 8 dropped a create_receipt mid-request
               # (2026-09-04, tunnel connection reset under load). 6 is the
               # tested-safe default; bump with -n only if a run has headroom.
  fi
fi
case "$NPROCS" in
  ''|*[!0-9]*|0) echo "ERROR: -n needs a positive integer, got '$NPROCS'" >&2; exit 2 ;;
esac

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

if [ "$SUBSET" -eq 1 ]; then
  SCOPE="SUBSET: ${#NODE_IDS[@]} node id(s)"
else
  SCOPE="FULL: 41 billed sanity tests"
fi
echo "############################################################"
echo "# PARALLEL SANITY SWEEP   (${SCOPE}; -n ${NPROCS}, --dist loadfile)"
echo "# interpreter: $("$VENV_PY" -c 'import sys; print(sys.executable)')"
echo "############################################################"

# --- 1. morning-mcp gate (serial, first) ------------------------------------
if [ "$RUN_GATE" -eq 1 ]; then
  echo
  echo ">>> GATE (morning-mcp-app, serial): ${GATE_NODE}"
  if [ ! -x "$MM_SINGLE" ]; then
    echo "ERROR: missing/broken gate runner: $MM_SINGLE" >&2
    exit 2
  fi
  if ! "$MM_SINGLE" "$GATE_NODE"; then
    echo
    echo "############################################################"
    echo "# GATE FAILED - the Morning tunnel / remote-MCP / sandbox path is"
    echo "# broken, so every downstream billed test would fail too. Stopping."
    echo "############################################################"
    exit 3
  fi
  echo ">>> GATE PASSED"
else
  echo
  echo ">>> GATE SKIPPED (--no-gate)"
fi

# --- 2. denidin-app sanity subset (parallel, with one retry round) ---------
mkdir -p "$RESULTS_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
RESULTS_FILE="${RESULTS_DIR}/_sanity_parallel_${TS}.txt"

# Clear any stale per-worker roots from an earlier parallel run (gitignored,
# worker-only - never the canonical test_data/ itself).
rm -rf "${DEN_DIR}/test_data/gw"* "${DEN_DIR}/test_data/master" 2>/dev/null || true

echo
echo ">>> SANITY ($SCOPE)  ->  ${RESULTS_FILE#$ROOT/}"
echo "    (per-test '>>> TEST [k/N]' sound-off streams live from conftest.py — relay each line)"

# The FULL sweep is billed-only. A subset naming tests/expensive/ node ids opts
# INTO expensive - the caller has taken on the per-test approval each still
# requires (CLAUDE.md); this script does not grant it.
MARKER='sanity and not expensive'
if [ "$SUBSET" -eq 1 ]; then
  BASE_TARGET=( "${NODE_IDS[@]}" )
  for _n in "${NODE_IDS[@]}"; do
    case "$_n" in tests/expensive/*) MARKER='sanity'; echo ">>> NOTE: expensive sanity tests included (caller-approved)"; break ;; esac
  done
else
  BASE_TARGET=( tests/billed/ )
fi

# Run one pytest round; append everything to $RESULTS_FILE. $1 = header label,
# $2 = -n value, rest = pytest targets. Sets ROUND_EXIT.
run_round() {
  local label="$1" nproc="$2"; shift 2
  {
    echo
    echo "############################################################"
    echo "### ${label}   (-n ${nproc}, --dist loadfile)"
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
run_round "ROUND 1 / ${RETRY_MAX_ROUNDS}" "$NPROCS" "${BASE_TARGET[@]}"
EXIT_CODE="$ROUND_EXIT"

ROUND=1
DELAY="$RETRY_DELAY"
RETRY_STATUS=""   # human note for the final banner
STILL_RED_INFRA=""

while [ "$EXIT_CODE" -ne 0 ] && [ "$RETRY" -eq 1 ] && [ "$ROUND" -lt "$RETRY_MAX_ROUNDS" ]; do
  RETRYABLE=()
  while IFS= read -r _line; do
    [ -n "$_line" ] && RETRYABLE+=("$_line")
  done < <("$VENV_PY" "$CLASSIFIER" "$RESULTS_FILE")

  if [ "${#RETRYABLE[@]}" -eq 0 ]; then
    RETRY_STATUS="no infra-signature failures - nothing retried"
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

  # escalate the delay for any further round (0 stays 0 - immediate, by design)
  DELAY=$(awk -v d="$DELAY" -v f="$RETRY_FACTOR" 'BEGIN{ if(d<=0){print 0}else{printf "%.0f", d*f} }')

  if [ "$EXIT_CODE" -ne 0 ]; then
    STILL_RED_INFRA=$(printf '%s\n' "${RETRYABLE[@]}")
    RETRY_STATUS="retried ${#RETRYABLE[@]}; still red after round ${ROUND}"
  else
    RETRY_STATUS="retried ${#RETRYABLE[@]}; all green on round ${ROUND}"
  fi
done

# --- 3. final report ------------------------------------------------------
echo
echo "############################################################"
GATE_NOTE="gate skipped"; [ "$RUN_GATE" -eq 1 ] && GATE_NOTE="gate passed"
if [ "$EXIT_CODE" -eq 0 ]; then
  echo "# PARALLEL SANITY: ALL PASSED (${GATE_NOTE}; ${SCOPE}, -n ${NPROCS})"
  [ -n "$RETRY_STATUS" ] && echo "#   retry: ${RETRY_STATUS}"
else
  ALL_FAILED=$(grep -hE "^(FAILED|ERROR) " "$RESULTS_FILE" | awk '{print $2}' | sort -u)
  INFRA_RED=$(printf '%s\n' "$STILL_RED_INFRA" | sed '/^$/d' | sort -u)
  TERMINAL=$(comm -23 <(printf '%s\n' "$ALL_FAILED") <(printf '%s\n' "$INFRA_RED") 2>/dev/null || printf '%s\n' "$ALL_FAILED")

  echo "# PARALLEL SANITY: FAILURES (${GATE_NOTE}; ${SCOPE}, -n ${NPROCS})"
  [ -n "$RETRY_STATUS" ] && echo "#   retry: ${RETRY_STATUS}"
  if [ -n "$(printf '%s' "$TERMINAL" | tr -d '[:space:]')" ]; then
    echo "#"
    echo "#   TERMINAL failures (real - assertion / model, NOT retried):"
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
echo "#   expensive   : ./scripts/run_sanity.sh --status"
echo "############################################################"

exit "$EXIT_CODE"
