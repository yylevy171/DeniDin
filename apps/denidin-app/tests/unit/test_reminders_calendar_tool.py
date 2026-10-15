"""Feature 102 (T008A): the read-only `send_reminders_calendar_file(reminder_ids)` tool - attached with
cap_reminders_read, sends ONE .ics for the given active reminders on request. Real Backbone/ReminderManager/
DeniDin; only the Green API bot (FakeBot) and OpenAI client are stand-ins."""
import json
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from src.backbone.capability_tags import CapabilityTag
from src.capabilities.reminders.handler import dispatch_direct_tool_call
from src.capabilities.toolsets import WRITE_TOOL_NAMES, build_capability_tools
from src.models.config import AppConfiguration
from src.tool_actions.tool_schemas import SEND_REMINDERS_CALENDAR_FILE_TOOL
from src.utils.time_utils import now_local
from tests.backbone_test_support import FakeBot, make_backbone, make_session_manager
from tests.denidin_test_support import make_reminder_manager

CHAT = "972500000000@c.us"
CONTEXT = {"chat_id": CHAT, "user_phone": "972500000000", "role": "godfather"}
TOOL = "send_reminders_calendar_file"


@pytest.fixture
def backbone(tmp_path):
    config = AppConfiguration(green_api_instance_id="x", green_api_token="y", ai_api_key="z")
    manager = make_reminder_manager(storage_dir=str(tmp_path / "data" / "reminders"))
    bb = make_backbone(MagicMock(), config, reminder_manager=manager, session_manager=make_session_manager())
    bb.denidin.green_api_bot = FakeBot()
    return bb


def _new(backbone, text, days=2):
    due = (now_local() + timedelta(days=days)).replace(hour=9, minute=0, second=0, microsecond=0)
    return backbone.reminder_manager.create_reminder(
        text, "one_time", due.isoformat(), None, "972500000000", "GODFATHER", CHAT)["reminder_id"]


def _call(backbone, ids):
    return dispatch_direct_tool_call(backbone, TOOL, {"reminder_ids": ids}, CONTEXT)


class TestSchemaAndAttachment:
    def test_schema_is_strict_with_a_non_empty_id_array(self):
        tool = SEND_REMINDERS_CALENDAR_FILE_TOOL
        assert tool["type"] == "function" and tool["name"] == TOOL and tool["strict"] is True
        ids = tool["parameters"]["properties"]["reminder_ids"]
        assert ids["type"] == "array" and ids["minItems"] == 1 and ids["items"] == {"type": "string"}
        assert tool["parameters"]["required"] == ["reminder_ids"]
        assert tool["parameters"]["additionalProperties"] is False

    def test_attached_with_reminders_read_only(self, backbone):
        read = [t["name"] for t in build_capability_tools(backbone, [CapabilityTag.REMINDERS_READ], CONTEXT)]
        write = [t["name"] for t in build_capability_tools(backbone, [CapabilityTag.REMINDERS_WRITE], CONTEXT)]
        assert TOOL in read and TOOL not in write

    def test_is_not_a_write_tool(self):
        assert TOOL not in WRITE_TOOL_NAMES


class TestDispatch:
    def test_sends_one_file_for_several_reminders(self, backbone):
        first, second = _new(backbone, "א"), _new(backbone, "ב")
        result = json.loads(_call(backbone, [first, second]))
        assert result["sent"] is True and result["reminders"] == 2
        (chat, name, content), = backbone.denidin.green_api_bot.files
        assert chat == CHAT and name == result["file_name"] and name.startswith("reminders_")
        assert content.count(b"BEGIN:VEVENT") == 2 and b"METHOD:PUBLISH" in content

    def test_single_reminder_file_name(self, backbone):
        rid = _new(backbone, "לשלם")
        result = json.loads(_call(backbone, [rid]))
        assert result["file_name"].startswith("reminder_") and result["reminders"] == 1

    def test_duplicate_ids_are_sent_once(self, backbone):
        rid = _new(backbone, "לשלם")
        result = json.loads(_call(backbone, [rid, rid]))
        assert result["reminders"] == 1
        assert backbone.denidin.green_api_bot.files[0][2].count(b"BEGIN:VEVENT") == 1

    def test_an_unknown_id_sends_nothing(self, backbone):
        rid = _new(backbone, "לשלם")
        result = _call(backbone, [rid, "no-such-id"])
        assert result.startswith("⚠️ לא נמצאה תזכורת פעילה עם המזהה") and "no-such-id" in result
        assert backbone.denidin.green_api_bot.files == []

    def test_a_cancelled_reminder_is_treated_as_unknown(self, backbone):
        rid = _new(backbone, "לשלם")
        backbone.reminder_manager.delete_whole_series(rid)
        assert _call(backbone, [rid]).startswith("⚠️ לא נמצאה תזכורת פעילה")
        assert backbone.denidin.green_api_bot.files == []

    def test_each_request_carries_a_higher_sequence(self, backbone):
        rid = _new(backbone, "לשלם")
        _call(backbone, [rid])
        _call(backbone, [rid])
        first, second = (c for _c, _n, c in backbone.denidin.green_api_bot.files)
        assert b"SEQUENCE:0" in first and b"SEQUENCE:1" in second

    def test_no_reminder_manager(self, backbone):
        backbone.denidin.reminder_manager = None
        assert _call(backbone, ["x"]) == "⚠️ שירות התזכורות אינו זמין כרגע."

    def test_send_failure_is_reported(self, backbone):
        rid = _new(backbone, "לשלם")
        backbone.denidin.green_api_bot.file_error = ConnectionError("down")
        assert _call(backbone, [rid]) == "⚠️ לא הצלחתי לשלוח את קובץ היומן."

    def test_does_not_queue_an_automatic_file(self, backbone):
        rid = _new(backbone, "לשלם")
        _call(backbone, [rid])
        assert backbone._turn_reminder_calendar_queue == {}
