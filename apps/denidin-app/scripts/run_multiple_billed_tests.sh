#!/usr/bin/env bash
set -uo pipefail

# Runs multiple BILLED tests ONE AT A TIME via run_single_test.sh, stopping
# immediately on the first failure - the -x/"stop on fail" behavior, but at
# the granularity of one full test per pytest invocation (never a bare
# `pytest -m billed` sweep across many tests in one process - each test gets
# its own clean process, matching how these tests have been run throughout
# this project's history).
#
# 🚨 BILLED ONLY - never expensive. CLAUDE.md requires per-run approval for
# EVERY expensive test individually, one at a time, with no batching - a
# multi-test sequence runner is structurally incompatible with that rule
# for the expensive tier. Use run_single_test.sh directly for an expensive
# test, one invocation, one fresh approval, every time.
#
# Each test's result is announced (PASSED/FAILED) as soon as it's known -
# "sound off on each one by one" - before moving to the next. On a failure,
# this script stops and does NOT run any remaining tests; it exits non-zero
# so a human/agent driving it can see failure without reading output.
#
# Usage:
#   scripts/run_multiple_billed_tests.sh <pytest_node_id> [<pytest_node_id> ...]
#
# Example:
#   scripts/run_multiple_billed_tests.sh \
#     "tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_delete_one_time_reminder" \
#     "tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_delete_whole_series" \
#     "tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_client_role_denied_reminder_tools"
#
# Each individual test's full pytest output lands in its own file under
# logs/test_logs/pytest_results/ (see run_single_test.sh) - nothing here
# re-truncates or re-pipes that output, it's just announced by name.

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <pytest_node_id> [<pytest_node_id> ...]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SINGLE_RUNNER="${SCRIPT_DIR}/run_single_test.sh"

if [ ! -x "$SINGLE_RUNNER" ]; then
  echo "ERROR: expected executable at $SINGLE_RUNNER" >&2
  exit 2
fi

TOTAL="$#"
INDEX=0
PASSED_COUNT=0

for NODE_ID in "$@"; do
  INDEX=$((INDEX + 1))
  echo "===================================================================="
  echo "[$INDEX/$TOTAL] $NODE_ID"
  echo "===================================================================="

  "$SINGLE_RUNNER" "$NODE_ID"
  RESULT=$?

  if [ "$RESULT" -eq 0 ]; then
    PASSED_COUNT=$((PASSED_COUNT + 1))
    echo "[$INDEX/$TOTAL] PASSED: $NODE_ID"
    echo
  else
    echo "[$INDEX/$TOTAL] FAILED: $NODE_ID"
    echo
    echo "Stopping (stop-on-fail) - $PASSED_COUNT/$TOTAL passed before this failure."
    exit 1
  fi
done

echo "All $TOTAL test(s) passed."
exit 0
