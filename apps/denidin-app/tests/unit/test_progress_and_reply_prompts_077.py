"""bugfix-077: progress updates and replies are two distinct tools, each unaware of the other.

Pins the PM's decided behavior (specs/repo/bugfixes/bugfix-077-progress-updates-and-typing-dots.md):
the progress tool describes what the model is about to do, the reply tool is the official answer or
summary, neither one's prompt or tool description mentions the other, the backbone says when to use
which, and every flow tells the model it may send progress updates between its steps.
"""
from pathlib import Path

import pytest

from src.backbone.resolution_tools import SEND_TO_USER_TOOL
from src.tool_actions.tool_schemas import SEND_PROGRESS_UPDATE_TOOL

PROMPTS = Path(__file__).resolve().parents[2] / "config" / "prompts"
FLOWS = sorted((PROMPTS / "flows").glob("flow_*.md"))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestTheTwoToolsAreUnawareOfEachOther:
    def test_progress_capability_prompt_does_not_mention_send_to_user_or_a_final_answer(self):
        text = _read(PROMPTS / "capabilities" / "cap_send_progress_update.md").lower()
        for banned in ("send_to_user", "final reply", "final answer", "end_turn"):
            assert banned not in text, f"cap_send_progress_update.md still mentions {banned!r}"

    def test_progress_capability_prompt_does_not_demand_an_update_on_every_tool_call(self):
        text = _read(PROMPTS / "capabilities" / "cap_send_progress_update.md").lower()
        for banned in ("every single time", "never skip it", "any tool or capability"):
            assert banned not in text, f"cap_send_progress_update.md still demands an update on every tool call: {banned!r}"

    def test_progress_tool_description_does_not_mention_a_final_answer_or_restrain_use(self):
        text = SEND_PROGRESS_UPDATE_TOOL["description"].lower()
        for banned in ("final answer", "send_to_user", "only on a turn you already know", "never on an ordinary"):
            assert banned not in text, f"progress tool description still contains {banned!r}"

    def test_send_to_user_capability_prompt_does_not_mention_progress_updates(self):
        text = _read(PROMPTS / "capabilities" / "cap_send_to_user.md").lower()
        for banned in ("progress", "status message", "wrap-up"):
            assert banned not in text, f"cap_send_to_user.md still mentions {banned!r}"

    def test_send_to_user_tool_description_does_not_mention_progress(self):
        assert "progress" not in SEND_TO_USER_TOOL["description"].lower()


class TestBackboneDefinesWhenToUseWhich:
    def test_backbone_has_a_section_telling_when_to_send_a_progress_update_and_when_a_reply(self):
        text = _read(PROMPTS / "backbone.md")
        assert "## Progress updates and replies" in text
        section = text.split("## Progress updates and replies", 1)[1].split("\n## ", 1)[0]
        assert "send_progress_update" in section and "send_to_user" in section

    def test_backbone_no_longer_discourages_interim_messages(self):
        text = _read(PROMPTS / "backbone.md")
        assert "Do not follow it with a" not in text
        assert "status or wrap-up message" not in text


@pytest.mark.parametrize("flow", FLOWS, ids=lambda p: p.name)
def test_every_flow_mentions_progress_updates_between_its_steps_at_the_top(flow):
    top = "\n".join(_read(flow).splitlines()[:12])
    assert "cap_send_progress_update" in top, f"{flow.name}: no progress-update line in the first lines"
