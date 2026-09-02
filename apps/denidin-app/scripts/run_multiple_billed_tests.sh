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
# 🚨 AI AGENTS DRIVING THIS SCRIPT: SOUND OFF ON EACH TEST RESULT AS IT
# COMES IN, NOT ONLY AFTER THE WHOLE RUN FINISHES - unless the user has
# explicitly said otherwise for this run. This script already announces
# each test's PASSED/FAILED individually (see above) specifically so a
# human watching along gets live progress - don't defeat that by capturing
# the whole run's output in one shot and reporting it only at the end.
# Real incident (2026-08-26): an agent ran this via a backgrounded shell
# call piped through `| tail -150`, which buffers the ENTIRE pipeline's
# output until the process exits - so nothing streamed anywhere until the
# full 23-test sweep had already finished, several minutes later, with the
# user seeing silence the whole time and having to demand a status
# ("SOUND OFF GODDAMNIT!!!") before getting anything. Don't pipe this
# script's output through anything that buffers until EOF (`tail`, `head`,
# a variable capture like `$(...)`, etc.) when a human is waiting on
# progress. Instead: run it via a backgrounded call with NO buffering pipe
# on the command itself, then poll its output file (or use Monitor) at a
# short interval and relay each newly-completed `[N/TOTAL] PASSED/FAILED:`
# line to the user as soon as it appears - polling/Monitor is explicitly
# fine here, whichever is more convenient, the point is live per-test
# results, not a single report at the end.
#
# Usage:
#   scripts/run_multiple_billed_tests.sh <pytest_node_id> [<pytest_node_id> ...]
#   (agents: poll the output file or use Monitor and relay each
#   `[N/TOTAL] PASSED/FAILED:` line to the user as it appears - see the
#   sound-off note above; don't wait for the whole run to finish before
#   reporting anything, unless the user has said otherwise.)
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

  if [ "$RESULT" -eq 3 ]; then
    # Setup problem (missing/incomplete venv) reported by run_single_test.sh -
    # NOT a test failure. No test in this sweep actually ran; don't record it
    # as a FAILED test result, just stop and surface the setup error.
    echo "[$INDEX/$TOTAL] SETUP ERROR (not a test result): $NODE_ID" >&2
    echo "Aborting the sweep - fix the venv (see the error above) and re-run." >&2
    exit 3
  fi

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
