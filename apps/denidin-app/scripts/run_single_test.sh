#!/usr/bin/env bash
set -euo pipefail

# Runs exactly ONE billed or expensive test and captures pytest's COMPLETE
# output to a dedicated results file on disk - never piped through
# tail/grep/head at capture time, so nothing is ever discarded before it's
# written down. This is the mandated way to run a single billed/expensive
# test in this project (CLAUDE.md, CONSTITUTION.md, METHODOLOGY.md) -
# written 2026-08-18 after repeated incidents where an ad-hoc
# `pytest ... | tail -N` discarded the actual assertion/traceback before it
# was ever seen.
#
# Two separate, non-overlapping outputs, matching how this project's logging
# already works:
#   1. The APP's own per-test-file log (logs/test_logs/{test_file}.log) -
#      written automatically by conftest.py's pytest_runtest_setup hook,
#      exactly as it always has been. This script never touches, redirects,
#      or otherwise interferes with that file - it is read-only from this
#      script's point of view.
#   2. PYTEST's own report (pass/fail, assertion diffs, tracebacks) - this
#      does NOT go through the app's logger at all (confirmed 2026-08-18: a
#      pytest AssertionError never appears in logs/test_logs/*.log), so it
#      needs its own destination. This script lets pytest write its full,
#      untruncated output straight to a results file - nothing upstream of
#      that file ever filters/truncates it.
#
# Marker (billed vs expensive) is auto-detected from the node id's path
# (tests/billed/... -> -m billed, tests/expensive/... -> -m expensive) so
# the common case needs no extra flag; override with an explicit 2nd arg
# if a node id ever lives somewhere that doesn't match either pattern.
#
# Usage:
#   scripts/run_single_test.sh <pytest_node_id> [marker] [--{config_key}={value} ...]
#
# --{config_key}={value} (2026-09-15, Feature 063 follow-up, generalized same
# day): overrides feature_flags.<config_key> to <value> for this run only -
# any current or future feature_flags key, not hardcoded to one. The literal
# config key, the literal config value, nothing else - forwarded to pytest as
# `--config-override <config_key>=<value>` (conftest.py's pytest_addoption),
# which a session-scoped fixture applies to the in-memory AppConfiguration
# object every test file's own `config` fixture returns. No config JSON file
# on disk is ever read from, written to, or otherwise touched - this is a
# purely in-memory, test-run-scoped override. Omit it for no override at all,
# byte-for-byte unchanged from before this option existed. Multiple
# --{config_key}={value} args may be given at once. This is the ONLY
# sanctioned way to set it - never invoke pytest's own --config-override
# directly.
#
# Examples:
#   scripts/run_single_test.sh \
#     "tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_modify_whole_series_pattern"
#   scripts/run_single_test.sh \
#     "tests/expensive/test_pdf_extraction.py::test_something" expensive
#   scripts/run_single_test.sh \
#     "tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_hours_by_client_last_month" billed --enable_capability_backbone=true
#
# Exits with pytest's own exit code (0 = passed, 1 = failed, etc.) - the
# calling agent/human can check $? without parsing any text. Exit code 3 is
# reserved for "this clone's venv is missing or has no pytest" (see the
# interpreter-resolution block below) - a setup problem, never a test result.
#
# 🚨 This script does not grant approval to run anything - every invocation
# (billed or expensive alike) still needs its own explicit human go-ahead
# per this project's standing rules, exactly as before this script existed.
# expensive tests keep ALL of their extra discipline on top of this (one at
# a time only, never re-run once it's actually reached OpenAI without a
# fresh explicit approval, read existing logs before re-running anything) -
# this script only fixes HOW output is captured, not any approval gate.

# Parse args: NODE_ID (positional), optional MARKER (positional), any number
# of --{config_key}={value} overrides (may appear anywhere after the node
# id) - each is a literal feature_flags key/value pair, not a fixed set.
CONFIG_OVERRIDES=()
POSITIONAL=()
for arg in "$@"; do
  case "$arg" in
    --*=*)
      CONFIG_OVERRIDES+=("${arg#--}")
      ;;
    *)
      POSITIONAL+=("$arg")
      ;;
  esac
done
if [ "${#POSITIONAL[@]}" -gt 0 ]; then set -- "${POSITIONAL[@]}"; else set --; fi

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: $0 <pytest_node_id> [marker] [--{config_key}={value} ...]" >&2
  echo "Example: $0 \"tests/billed/test_foo.py::TestClass::test_method\"" >&2
  exit 2
fi

NODE_ID="$1"

if [ "$#" -eq 2 ]; then
  MARKER="$2"
elif [[ "$NODE_ID" == tests/expensive/* ]]; then
  MARKER="expensive"
else
  MARKER="billed"
fi

# Always run from the app root, regardless of the caller's cwd.
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Each --{config_key}={value} becomes a `--config-override key=value` pytest
# arg (conftest.py) - built up here, appended to the pytest invocation below.
PYTEST_CONFIG_OVERRIDE_ARGS=()
for override in "${CONFIG_OVERRIDES[@]:-}"; do
  [ -n "$override" ] || continue
  PYTEST_CONFIG_OVERRIDE_ARGS+=(--config-override "$override")
done

# --- Interpreter resolution (added 2026-09-02) -------------------------------
# NEVER run pytest through a bare `python3` off the caller's PATH. On this
# machine bare `python3` resolves to a standalone Python 3.14 with no pytest
# installed, so a bare invocation produced a misleading "RESULT: FAILED"
# (exit 1, "No module named pytest") for a test that never actually ran -
# indistinguishable at a glance from a real test failure. Per CLAUDE.md
# ("always resolve/activate your own clone's own venv explicitly ... verify
# rather than assume"), this script now pins the interpreter to THIS clone's
# own venv, unconditionally, and fails loudly with its own distinct exit
# code (3) if that venv is missing or incomplete - it must never silently
# fall back to whatever `python3` happens to be first on PATH.
VENV_PY="venv/bin/python3"

if [ ! -x "$VENV_PY" ]; then
  echo "ERROR: no usable venv interpreter at $(pwd)/$VENV_PY" >&2
  echo "       Create this clone's own venv first:" >&2
  echo "         cd $(pwd) && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt" >&2
  exit 3
fi

if ! "$VENV_PY" -c "import pytest" >/dev/null 2>&1; then
  echo "ERROR: $(pwd)/$VENV_PY exists but pytest is not installed in it." >&2
  echo "       Install this clone's test dependencies:" >&2
  echo "         cd $(pwd) && ./venv/bin/pip install -r requirements.txt" >&2
  exit 3
fi

echo "Interpreter: $("$VENV_PY" -c 'import sys; print(sys.executable)') ($("$VENV_PY" --version 2>&1))"

RESULTS_DIR="logs/test_logs/pytest_results"
mkdir -p "$RESULTS_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
SAFE_NAME="$(printf '%s' "$NODE_ID" | tr -c 'A-Za-z0-9_.' '_')"
RESULTS_FILE="${RESULTS_DIR}/${SAFE_NAME}_${TIMESTAMP}.txt"

CONFIG_OVERRIDES_NOTE="none"
[ "${#CONFIG_OVERRIDES[@]}" -gt 0 ] && CONFIG_OVERRIDES_NOTE="${CONFIG_OVERRIDES[*]}"
echo "Running: $NODE_ID (marker: $MARKER, config overrides: $CONFIG_OVERRIDES_NOTE)"
echo "Full pytest output will be written to: $RESULTS_FILE"
echo "(app's own per-test-file log, unaffected by this script: logs/test_logs/<test_file>.log)"
echo

# The ENTIRE pytest run - stdout and stderr both - goes straight to the
# results file. No intermediate tail/grep/head in this pipeline; whatever
# pytest produces, all of it lands on disk before this script does anything
# else with it.
set +e
if [ "${#PYTEST_CONFIG_OVERRIDE_ARGS[@]}" -gt 0 ]; then
  "$VENV_PY" -m pytest "$NODE_ID" -v -m "$MARKER" --tb=long "${PYTEST_CONFIG_OVERRIDE_ARGS[@]}" >"$RESULTS_FILE" 2>&1
else
  "$VENV_PY" -m pytest "$NODE_ID" -v -m "$MARKER" --tb=long >"$RESULTS_FILE" 2>&1
fi
EXIT_CODE=$?
set -e

echo "----- last 15 lines of $RESULTS_FILE (full file has everything) -----"
tail -n 15 "$RESULTS_FILE"
echo "------------------------------------------------------------------"

if [ "$EXIT_CODE" -eq 0 ]; then
  echo "RESULT: PASSED"
else
  echo "RESULT: FAILED (exit code $EXIT_CODE)"
fi
echo "Full untruncated output: $RESULTS_FILE"

exit "$EXIT_CODE"
