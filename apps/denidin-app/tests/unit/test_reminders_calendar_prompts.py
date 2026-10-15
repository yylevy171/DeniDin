"""Feature 102 (T009A): the prompts define the calendar-file behavior and its boundaries in BOTH directions
(CLAUDE.md: every new tool-bearing feature needs explicit constitution boundaries) - the reminder prompts say
when the file applies / does not apply / that ambiguity is resolved by asking, and every other tool-bearing
capability prompt (plus the backbone) says calendar files belong only to the reminders capabilities."""
from pathlib import Path

import pytest

from src.backbone.flow_tags import FLOW_INFO, FlowTag

CONFIG = Path(__file__).resolve().parents[2] / "config" / "prompts"
EXPORT_QUESTION = "לייצא את התזכורות שלך לקובץ יומן (ics)?"
OTHER_TOOL_BEARING = [
    "cap_agreements_read", "cap_agreements_write", "cap_client_read", "cap_client_write", "cap_docx_write",
    "cap_invoicing_read", "cap_invoicing_write", "cap_ledger_capture", "cap_ledger_query", "cap_media_analysis",
]
BOUNDARY_PHRASE = "calendar files (.ics) belong only to the reminders capabilities"


def _text(*parts):
    return (CONFIG.joinpath(*parts)).read_text(encoding="utf-8")


class TestReminderReadCapability:
    @pytest.fixture(scope="class")
    def text(self):
        return _text("capabilities", "cap_reminders_read.md")

    def test_documents_the_tool(self, text):
        assert "send_reminders_calendar_file" in text

    def test_states_when_it_applies(self, text):
        assert "asks for" in text and "calendar file" in text
        assert "approval_with_yes_no_buttons" in text and EXPORT_QUESTION in text

    def test_states_when_it_does_not_apply(self, text):
        for phrase in ("never for invoices", "ledger", "agreements", "never to answer a confirmation reply"):
            assert phrase in text.lower() or phrase in text

    def test_ambiguity_is_resolved_by_asking(self, text):
        assert "ask" in text.lower() and "never guess" in text.lower()

    def test_nothing_is_sent_before_a_yes(self, text):
        assert "until" in text and "yes" in text.lower()

    def test_points_back_to_the_general_short_reply_rule(self, text):
        assert "Contexts of Operation" in text


class TestReminderWriteSide:
    @pytest.mark.parametrize("path", [
        ("capabilities", "cap_reminders_write.md"), ("flows", "flow_create_reminder.md"),
        ("flows", "flow_modify_reminder.md"),
    ])
    def test_says_the_file_is_automatic_and_never_requested(self, path):
        text = _text(*path)
        assert "calendar" in text and "automatically" in text
        assert "never" in text.lower()


class TestCalendarFileFlow:
    def test_flow_tag_and_catalog_entry(self):
        assert FlowTag.REMINDERS_CALENDAR_FILE.value == "flow_reminders_calendar_file"
        info = next(i for i in FLOW_INFO if i.tag == FlowTag.REMINDERS_CALENDAR_FILE)
        assert info.description.count(".") >= 2 and "calendar" in info.description

    def test_flow_steps(self):
        text = _text("flows", "flow_reminders_calendar_file.md")
        assert "cap_reminders_read" in text and "cap_approval_with_buttons" in text
        assert EXPORT_QUESTION in text and "send_reminders_calendar_file" in text
        assert "no" in text.lower() and "do nothing" in text.lower()

    def test_flow_unloads_what_it_loaded(self):
        assert "unload" in _text("flows", "flow_reminders_calendar_file.md")


class TestBoundariesInTheOtherDirection:
    @pytest.mark.parametrize("name", OTHER_TOOL_BEARING)
    def test_every_other_tool_bearing_capability_excludes_calendar_files(self, name):
        assert BOUNDARY_PHRASE in _text("capabilities", f"{name}.md")

    def test_backbone_lists_the_boundary(self):
        assert BOUNDARY_PHRASE in _text("backbone.md")
