"""Feature 067 (REQ-RMH-010/015/020): no feature flag, no abort of a model call, no end-of-handling marker."""
import json
from pathlib import Path

APP = Path(__file__).resolve().parents[2]


def test_no_067_flag_in_config():
    example = json.loads((APP / "config" / "config.example.json").read_text(encoding="utf-8"))
    flags = example.get("feature_flags", {}) or {}
    assert not [k for k in flags if "message_handling" in k or "intake" in k or "dispatcher" in k]


def test_no_abort_or_end_of_handling_machinery_in_the_new_modules():
    sources = "\n".join((APP / rel).read_text(encoding="utf-8").lower() for rel in (
        "src/intake/intake_coordinator.py", "src/intake/denidin_dispatcher.py", "src/backbone/pending_messages.py"))
    for forbidden in ("responses.cancel", ".cancel(", "abort", "discard_and_merge", "end_of_turn", "debounce"):
        assert forbidden not in sources, forbidden
