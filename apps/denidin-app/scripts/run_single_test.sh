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
#   scripts/run_single_test.sh <pytest_node_id> [marker]
#
# Examples:
#   scripts/run_single_test.sh \
#     "tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_modify_whole_series_pattern"
#   scripts/run_single_test.sh \
#     "tests/expensive/test_pdf_extraction.py::test_something" expensive
#
# Exits with pytest's own exit code (0 = passed, 1 = failed, etc.) - the
# calling agent/human can check $? without parsing any text.
#
# 🚨 This script does not grant approval to run anything - every invocation
# (billed or expensive alike) still needs its own explicit human go-ahead
# per this project's standing rules, exactly as before this script existed.
# expensive tests keep ALL of their extra discipline on top of this (one at
# a time only, never re-run once it's actually reached OpenAI without a
# fresh explicit approval, read existing logs before re-running anything) -
# this script only fixes HOW output is captured, not any approval gate.

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: $0 <pytest_node_id> [marker]" >&2
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

RESULTS_DIR="logs/test_logs/pytest_results"
mkdir -p "$RESULTS_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
SAFE_NAME="$(printf '%s' "$NODE_ID" | tr -c 'A-Za-z0-9_.' '_')"
RESULTS_FILE="${RESULTS_DIR}/${SAFE_NAME}_${TIMESTAMP}.txt"

echo "Running: $NODE_ID (marker: $MARKER)"
echo "Full pytest output will be written to: $RESULTS_FILE"
echo "(app's own per-test-file log, unaffected by this script: logs/test_logs/<test_file>.log)"
echo

# The ENTIRE pytest run - stdout and stderr both - goes straight to the
# results file. No intermediate tail/grep/head in this pipeline; whatever
# pytest produces, all of it lands on disk before this script does anything
# else with it.
set +e
python3 -m pytest "$NODE_ID" -v -m "$MARKER" --tb=long >"$RESULTS_FILE" 2>&1
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
