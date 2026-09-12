"""
Feature 084 (WhatsApp reactions) - the reaction-judgment tuning harness's capture
mechanism (contracts/reaction-judgment-tuning.md). `send_reaction()` is stubbed at the
Green API boundary ONLY (permitted per CONSTITUTION SS V - external services may be
mocked in tests; internal components may not) - everything else in a scenario run
(AIHandler, tool dispatch, session persistence) is real.

The deterministic keyword-based fast-path hook in denidin.py has been removed
(2026-09-12, explicit user instruction: "get rid of the fast in code. Fast should
happen IN THE AI") - the only real send_reaction call site left is ai_handler.py's
react_to_message tool. The model is now expected to produce its own fast initial
reaction+ack itself (as its very first tool call in a turn), then do the rest of the
work, then react again on resolution - not a separate non-AI heuristic. The
"fast_path" source label is kept in CapturedReaction/the judgment log shape for
backward-compatible log format only; it is never actually recorded anymore since
nothing patches denidin.py's now-nonexistent send_reaction reference.

Underscore-prefixed (not `test_*.py`) so pytest never collects this as a test module -
imported by tests/unit/test_reaction_tuning_harness.py and by the actual billed/expensive
reaction-judgment test files.
"""
import json
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List
from unittest.mock import patch

from src.utils.time_utils import now_local


@dataclass
class CapturedReaction:
    """One send_reaction call observed during a scenario run."""
    source: str  # "fast_path" (denidin.py's hook) or "react_to_message" (the AI tool)
    chat_id: str
    id_message: str
    reaction: str


class ReactionCaptureStub:
    """Records every send_reaction call made during a scenario run. The only real call
    site left is ai_handler.py's react_to_message tool (denidin.py's deterministic
    fast-path hook was removed 2026-09-12 - the model's own first tool call in a turn
    is now the "fast" reaction). A scenario that makes zero calls is a valid, loggable
    outcome - `self.calls` simply stays empty, never treated as an error by this class
    itself."""

    def __init__(self) -> None:
        self.calls: List[CapturedReaction] = []

    def _recorder(self, source: str):
        def _stub(bot, chat_id, id_message, reaction):  # pylint: disable=unused-argument
            self.calls.append(CapturedReaction(source, chat_id, id_message, reaction))
            return True
        return _stub

    @contextmanager
    def installed(self):
        """Patches send_reaction at its one real import site for the duration of the
        `with` block. Each scenario run should use a FRESH ReactionCaptureStub instance
        (never reused across scenarios) so `self.calls` reflects exactly one scenario's
        outcome."""
        with patch("src.handlers.ai_handler.send_reaction", side_effect=self._recorder("react_to_message")):
            yield self


class ReactionTuningJudgmentLog:
    """One JSON file per rotation round (`logs/reaction_tuning/<timestamp>.json`), one
    array entry appended per scenario run within that round - contracts/
    reaction-judgment-tuning.md's capture-mechanism shape."""

    def __init__(self, log_dir: Path, round_timestamp: str) -> None:
        self.log_dir = log_dir
        self.round_timestamp = round_timestamp
        self.path = log_dir / f"{round_timestamp}.json"
        self._entries: List[dict] = []
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                self._entries = json.load(f)

    def append(self, scenario_name: str, calls: List[CapturedReaction], *, reply_text: str = "") -> None:
        self._entries.append({
            "scenario": scenario_name,
            "recorded_at": now_local().isoformat(),
            "reply_text": reply_text,
            "reactions": [asdict(c) for c in calls],
        })
        self.log_dir.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._entries, f, indent=2, ensure_ascii=False)

    @property
    def entries(self) -> List[dict]:
        return list(self._entries)
