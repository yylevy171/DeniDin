#!/usr/bin/env bash
set -uo pipefail

# Runs unit/integration tests (the tiers with no per-run cost or approval
# gate) through a sanctioned wrapper, exactly as run_single_test.sh /
# run_multiple_billed_tests.sh / run_sanity*.sh already do for
# billed/expensive. Written 2026-09-24 per CONSTITUTION.md §XIX /
# METHODOLOGY.md §XXIII ("AI Agents: No Bare `pytest` Invocations, Ever -
# Scripts Only") - that rule is absolute and carries NO tier exception, so
# unit/integration needed its own wrapper rather than being left to a bare
# `pytest`/`make test` invocation.
#
# 🚨 MUST BE RUN WITH LIVE SOUND-OFF - same requirement as every other test
# runner in this repo (CLAUDE.md's "INDIVIDUAL PER-TEST SOUND-OFF" banner).
# This script streams pytest's output live via `tee` (not buffered-then-
# printed like run_single_test.sh, which only ever runs ONE test at a time) -
# relay each `>>> TEST [k/N]` line the instant it appears, never launch this
# in the background and read the results only once it exits.
#
# What this gives you that a bare `pytest` invocation doesn't:
#   - Pinned interpreter: always THIS clone's own venv/bin/python3, never a
#     bare `python3` off the caller's PATH (see run_single_test.sh's own
#     comment on why - a stray Python 3.14 with no pytest installed once
#     produced a misleading "FAILED" for a test that never actually ran).
#   - Full untruncated capture: `tee` writes everything to a results file on
#     disk AND to stdout - nothing is ever discarded by an intermediate
#     tail/grep/head, and the file survives after the terminal scrollback
#     doesn't.
#
# Usage:
#   scripts/run_unit_integration_tests.sh [<pytest target/arg> ...]
#
# With no arguments, runs the full suite as CLAUDE.md documents it
# ("tests/ -v --tb=short") - pytest.ini's own addopts already excludes
# billed/expensive by default, so this naturally stays within
# unit/integration (and any other non-billed/non-expensive marker) even
# with no explicit tier restriction.
#
# Examples:
#   scripts/run_unit_integration_tests.sh
#   scripts/run_unit_integration_tests.sh tests/unit/
#   scripts/run_unit_integration_tests.sh tests/integration/
#   scripts/run_unit_integration_tests.sh \
#     tests/unit/test_session_manager.py::test_function -xvs
#
# Exits with pytest's own exit code (0 = passed, 1+ = failures/errors) -
# check $? without parsing any text. Exit code 3 is reserved for "this
# clone's venv is missing or has no pytest" (a setup problem, never a test
# result), matching run_single_test.sh's convention.

# Always run from the app root, regardless of the caller's cwd.
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- Interpreter resolution (same convention as run_single_test.sh) --------
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

TARGETS=("$@")
if [ "${#TARGETS[@]}" -eq 0 ]; then
  TARGETS=("tests/" "-v" "--tb=short")
fi

RESULTS_DIR="logs/test_logs/pytest_results"
mkdir -p "$RESULTS_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
SAFE_NAME="$(printf '%s' "${TARGETS[*]}" | tr -c 'A-Za-z0-9_.' '_' | cut -c1-120)"
RESULTS_FILE="${RESULTS_DIR}/unit_integration_${SAFE_NAME}_${TIMESTAMP}.txt"

echo "Running: ${TARGETS[*]}"
echo "Full pytest output streamed live AND written to: $RESULTS_FILE"
echo "(app's own per-test-file log, unaffected by this script: logs/test_logs/<test_file>.log)"
echo

# Live-streamed via tee: the caller sees every >>> TEST sound-off line the
# instant it's emitted, AND the complete output lands on disk untouched -
# same "nothing discarded" guarantee as run_single_test.sh, but not
# buffered-then-printed, since this can run far more than one test.
set -o pipefail
"$VENV_PY" -m pytest "${TARGETS[@]}" 2>&1 | tee "$RESULTS_FILE"
EXIT_CODE=$?

echo "------------------------------------------------------------------"
if [ "$EXIT_CODE" -eq 0 ]; then
  echo "RESULT: PASSED"
else
  echo "RESULT: FAILED (exit code $EXIT_CODE)"
fi
echo "Full untruncated output: $RESULTS_FILE"

exit "$EXIT_CODE"
