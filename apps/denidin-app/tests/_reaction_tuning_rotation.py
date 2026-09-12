"""
Feature 084 (WhatsApp reactions) - rotation-state selection logic for the reaction-
judgment tuning harness (contracts/reaction-judgment-tuning.md). Pure functions, no I/O
side effects beyond the two explicit load/save helpers - mirrors sanity_state.tsv's own
plain-TSV pattern (apps/denidin-app/logs/test_logs/sanity_state.tsv).

Underscore-prefixed (not `test_*.py`) so pytest never collects this as a test module -
it's imported by tests/unit/test_reaction_tuning_harness.py and by
scripts/run_reaction_tuning.sh's own Python entry point.
"""
from pathlib import Path
from typing import Dict, List


def load_rotation_state(path: Path) -> Dict[str, str]:
    """name -> last-run ISO timestamp. A missing file, or a name never seen before,
    means "never run" - selection treats that as the highest priority to run next."""
    if not path.exists():
        return {}
    state: Dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            name, last_run = line.split("\t", 1)
            state[name] = last_run
    return state


def save_rotation_state(path: Path, state: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for name in sorted(state):
            f.write(f"{name}\t{state[name]}\n")


def select_subset(pool_names: List[str], state: Dict[str, str], subset_size: int) -> List[str]:
    """Selects up to `subset_size` names from `pool_names`, preferring never-run names
    first, then the least-recently-run ones - so repeated rounds build broad coverage
    over time rather than re-exercising the same handful of examples. Stable for names
    tied on recency (falls back to `pool_names`' own order)."""
    def sort_key(indexed_name):
        index, name = indexed_name
        never_run = name not in state
        return (not never_run, state.get(name, ""), index)

    ordered = [
        name for _, name in sorted(enumerate(pool_names), key=sort_key)
    ]
    return ordered[:subset_size]


def record_run(state: Dict[str, str], names: List[str], timestamp: str) -> Dict[str, str]:
    """Returns a NEW state dict with `names` stamped at `timestamp` - never mutates the
    input dict, so a caller can compare before/after if needed."""
    updated = dict(state)
    for name in names:
        updated[name] = timestamp
    return updated
