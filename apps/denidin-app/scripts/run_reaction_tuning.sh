#!/usr/bin/env bash
set -uo pipefail

# ============================================================================
# Feature 084 - the reaction-judgment tuning harness's rotation runner
# (contracts/reaction-judgment-tuning.md, tasks.md T011).
#
# Selects a least-recently-run subset of tests/billed/reaction_judgment_pool.py's
# scenarios (and, with --include-expensive, a subset of
# tests/expensive/reaction_judgment_pool.py's), runs each - billed scenarios
# freely, one at a time via scripts/run_single_test.sh (never batched, per
# CLAUDE.md); expensive scenarios only ever printed as a checklist for the human
# to run themselves, one at a time, with fresh approval every single run - and
# records the round in logs/reaction_tuning/rotation_state.tsv.
#
# This is PLUMBING for the AI-run tuning loop (T012) - it does not itself judge
# emoji choice, and the hard-assertion test (tests/billed/test_reaction_judgment_
# tuning.py) is the only thing that ever fails this script; the rest is just
# selection/state bookkeeping mirroring scripts/run_sanity.sh's own pattern.
#
# Usage:
#   ./scripts/run_reaction_tuning.sh                       # default: 4 billed scenarios
#   ./scripts/run_reaction_tuning.sh --billed-only          # same as default (explicit)
#   ./scripts/run_reaction_tuning.sh --subset-size 6        # pick a different subset size
#   ./scripts/run_reaction_tuning.sh --include-expensive 2  # ALSO print 2 expensive scenarios
#                                                            # as a checklist (never auto-run)
# ============================================================================

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

SINGLE_TEST="${ROOT}/scripts/run_single_test.sh"
STATE_FILE="${ROOT}/logs/reaction_tuning/rotation_state.tsv"
SUBSET_SIZE=4
INCLUDE_EXPENSIVE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --billed-only)
      INCLUDE_EXPENSIVE=0
      shift
      ;;
    --include-expensive)
      INCLUDE_EXPENSIVE="${2:?--include-expensive requires a count}"
      shift 2
      ;;
    --subset-size)
      SUBSET_SIZE="${2:?--subset-size requires a count}"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

# --- selection (delegates to tests/_reaction_tuning_rotation.py's pure functions) ---
SELECTION_JSON="$(venv/bin/python3 - "$STATE_FILE" "$SUBSET_SIZE" "$INCLUDE_EXPENSIVE" <<'PYEOF'
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from tests._reaction_tuning_rotation import load_rotation_state, select_subset
from tests.billed.reaction_judgment_pool import BILLED_REACTION_SCENARIOS
from tests.expensive.reaction_judgment_pool import EXPENSIVE_REACTION_SCENARIOS

state_file = Path(sys.argv[1])
subset_size = int(sys.argv[2])
include_expensive = int(sys.argv[3])

state = load_rotation_state(state_file)
billed_names = [s["name"] for s in BILLED_REACTION_SCENARIOS]
billed_selected = select_subset(billed_names, state, subset_size)

expensive_selected = []
if include_expensive > 0:
    expensive_names = [s["name"] for s in EXPENSIVE_REACTION_SCENARIOS]
    expensive_selected = select_subset(expensive_names, state, include_expensive)

print(json.dumps({"billed": billed_selected, "expensive": expensive_selected}))
PYEOF
)"

BILLED_SELECTED=($(echo "$SELECTION_JSON" | venv/bin/python3 -c "import json,sys; print(' '.join(json.load(sys.stdin)['billed']))"))
EXPENSIVE_SELECTED=($(echo "$SELECTION_JSON" | venv/bin/python3 -c "import json,sys; print(' '.join(json.load(sys.stdin)['expensive']))"))

echo "Reaction-judgment tuning round: $(date -u +%Y%m%dT%H%M%SZ)"
echo "Billed scenarios this round: ${BILLED_SELECTED[*]:-none}"

RUN_TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TOTAL=${#BILLED_SELECTED[@]}
COUNT=0
RUN_NAMES=()

for name in "${BILLED_SELECTED[@]:-}"; do
  [[ -z "$name" ]] && continue
  COUNT=$((COUNT + 1))
  echo ">>> TUNING [$COUNT/$TOTAL] running billed scenario: $name"
  # The hard-assertion test file exercises the 3 scenarios with a fixed
  # hard-assertion outcome; other pool scenarios are judgment-only and have no
  # dedicated node id yet (that's the AI-run loop's job, T012 - out of scope here).
  case "$name" in
    ambient_group_chatter_lunch)
      "$SINGLE_TEST" "tests/billed/test_reaction_judgment_tuning.py::TestReactionJudgmentTuningHardAssertions::test_ambient_group_chatter_lunch_makes_zero_reaction_calls" || exit 1
      ;;
    ambient_group_chatter_debate)
      "$SINGLE_TEST" "tests/billed/test_reaction_judgment_tuning.py::TestReactionJudgmentTuningHardAssertions::test_ambient_group_chatter_debate_makes_zero_reaction_calls" || exit 1
      ;;
    react_flip_earlier_message)
      "$SINGLE_TEST" "tests/billed/test_reaction_judgment_tuning.py::TestReactionJudgmentTuningHardAssertions::test_flip_earlier_message_targets_the_same_id_message" || exit 1
      ;;
    *)
      echo "    (no dedicated hard-assertion test for '$name' yet - judgment-only scenario, part of the AI-run tuning loop T012, not run by this script)"
      ;;
  esac
  RUN_NAMES+=("$name")
done

if [[ ${#RUN_NAMES[@]} -gt 0 ]]; then
  venv/bin/python3 - "$STATE_FILE" "$RUN_TIMESTAMP" "${RUN_NAMES[@]}" <<'PYEOF'
import sys
from pathlib import Path

sys.path.insert(0, ".")
from tests._reaction_tuning_rotation import load_rotation_state, record_run, save_rotation_state

state_file = Path(sys.argv[1])
timestamp = sys.argv[2]
names = sys.argv[3:]

state = load_rotation_state(state_file)
state = record_run(state, names, timestamp)
save_rotation_state(state_file, state)
PYEOF
  echo "Rotation state updated: $STATE_FILE"
fi

if [[ "$INCLUDE_EXPENSIVE" -gt 0 ]]; then
  echo ""
  echo "Expensive scenarios selected this round (NEVER auto-run - copy/paste one at a time,"
  echo "each needs its own fresh, explicit human approval per CLAUDE.md):"
  for name in "${EXPENSIVE_SELECTED[@]:-}"; do
    [[ -z "$name" ]] && continue
    echo "  - $name  (see tests/expensive/reaction_judgment_pool.py)"
  done
fi

echo ""
echo "Done. This script only runs the harness's hard-assertion plumbing test(s) - the"
echo "actual AI-run judgment-tuning loop (T012, reading judgment logs and deciding"
echo "whether emoji choice looks right) is a separate, deliberate activity, not a test."
