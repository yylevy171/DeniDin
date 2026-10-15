"""Feature 102 (T005A/T006A): the reminders write handler QUEUES a calendar file on the backbone for each
successful create/modify/delete; the backbone FLUSHES the queue after the conversation ends (so the file
arrives after the model's confirmation text).

Real Backbone + real ReminderManager + real DeniDin/WhatsAppHandler; only the Green API bot (FakeBot) and the
OpenAI client are stand-ins."""
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from src.capabilities.reminders.handler import dispatch_direct_tool_call
from src.capabilities.reminders.calendar_file import NOTICE_SEND_FAILED
from src.models.config import AppConfiguration
from src.utils.time_utils import now_local
from tests.backbone_test_support import FakeBot, make_backbone, make_session_manager
from tests.denidin_test_support import make_reminder_manager

CHAT = "972500000000@c.us"
CONTEXT = {"chat_id": CHAT, "user_phone": "972500000000", "role": "godfather"}


@pytest.fixture
def backbone(tmp_path):
    config = AppConfiguration(green_api_instance_id="x", green_api_token="y", ai_api_key="z")
    manager = make_reminder_manager(storage_dir=str(tmp_path / "data" / "reminders"))
    bb = make_backbone(MagicMock(), config, reminder_manager=manager, session_manager=make_session_manager())
    bb.denidin.green_api_bot = FakeBot()
    return bb


def _due(days=2):
    return (now_local() + timedelta(days=days)).replace(hour=9, minute=0, second=0, microsecond=0).isoformat()


def _create(backbone, text="לשלם לספק", days=2):
    args = {"message_text": text, "schedule_type": "one_time", "one_time_due_at": _due(days), "recurrence": None}
    result = dispatch_direct_tool_call(backbone, "create_reminder", args, CONTEXT)
    assert result.startswith("✅"), result
    return backbone.reminder_manager.list_active()[-1]["reminder_id"]


def _queue(backbone):
    return dict(backbone._turn_reminder_calendar_queue)


class TestQueueing:
    def test_create_queues_a_publish(self, backbone):
        reminder_id = _create(backbone)
        assert _queue(backbone) == {reminder_id: "PUBLISH"}

    def test_whole_series_modify_queues_a_publish(self, backbone):
        reminder_id = _create(backbone)
        backbone._turn_reminder_calendar_queue.clear()
        args = {"reminder_id": reminder_id, "scope": "whole_series", "new_message_text": "חדש",
                "new_due_at": None, "new_recurrence": None, "occurrence_date_hint": None}
        assert dispatch_direct_tool_call(backbone, "modify_reminder", args, CONTEXT).startswith("✅")
        assert _queue(backbone) == {reminder_id: "PUBLISH"}

    def test_whole_series_delete_queues_a_cancel(self, backbone):
        reminder_id = _create(backbone)
        backbone._turn_reminder_calendar_queue.clear()
        args = {"reminder_id": reminder_id, "scope": "whole_series", "occurrence_date_hint": None}
        assert dispatch_direct_tool_call(backbone, "delete_reminder", args, CONTEXT).startswith("✅")
        assert _queue(backbone) == {reminder_id: "CANCEL"}

    def test_a_failed_create_queues_nothing(self, backbone):
        args = {"message_text": "x", "schedule_type": "one_time",
                "one_time_due_at": (now_local() - timedelta(days=1)).isoformat(), "recurrence": None}
        assert dispatch_direct_tool_call(backbone, "create_reminder", args, CONTEXT).startswith("⚠️")
        assert _queue(backbone) == {}

    def test_an_unknown_reminder_modify_queues_nothing(self, backbone):
        args = {"reminder_id": "nope", "scope": "whole_series", "new_message_text": "x",
                "new_due_at": None, "new_recurrence": None, "occurrence_date_hint": None}
        dispatch_direct_tool_call(backbone, "modify_reminder", args, CONTEXT)
        assert _queue(backbone) == {}

    def test_a_no_op_modify_queues_nothing(self, backbone):
        reminder_id = _create(backbone)
        backbone._turn_reminder_calendar_queue.clear()
        args = {"reminder_id": reminder_id, "scope": "whole_series", "new_message_text": None,
                "new_due_at": None, "new_recurrence": None, "occurrence_date_hint": None}
        dispatch_direct_tool_call(backbone, "modify_reminder", args, CONTEXT)
        assert _queue(backbone) == {}

    def test_delete_after_create_in_one_turn_keeps_the_last_operation(self, backbone):
        reminder_id = _create(backbone)
        args = {"reminder_id": reminder_id, "scope": "whole_series", "occurrence_date_hint": None}
        dispatch_direct_tool_call(backbone, "delete_reminder", args, CONTEXT)
        assert _queue(backbone) == {reminder_id: "CANCEL"}


class TestFlush:
    def test_one_created_reminder_sends_one_publish_file(self, backbone):
        _create(backbone)
        backbone._flush_reminder_calendar_files(CHAT)
        (chat, name, content), = backbone.denidin.green_api_bot.files
        assert chat == CHAT and name.startswith("reminder_") and name.endswith(".ics")
        assert b"METHOD:PUBLISH" in content and "דנידין תזכורת: לשלם לספק".encode() in content
        assert b"SEQUENCE:0" in content
        assert _queue(backbone) == {}  # cleared after flushing

    def test_several_creates_are_one_combined_file(self, backbone):
        _create(backbone, "א"), _create(backbone, "ב")
        backbone._flush_reminder_calendar_files(CHAT)
        (_chat, name, content), = backbone.denidin.green_api_bot.files
        assert name.startswith("reminders_") and content.count(b"BEGIN:VEVENT") == 2

    def test_a_cancel_is_its_own_file(self, backbone):
        keep = _create(backbone, "נשאר")
        gone = _create(backbone, "נמחק")
        backbone._turn_reminder_calendar_queue.clear()
        backbone.queue_reminder_calendar_file(keep, "PUBLISH")
        backbone.reminder_manager.delete_whole_series(gone)
        backbone.queue_reminder_calendar_file(gone, "CANCEL")
        backbone._flush_reminder_calendar_files(CHAT)
        contents = [content for _c, _n, content in backbone.denidin.green_api_bot.files]
        assert len(contents) == 2
        assert sum(b"METHOD:CANCEL" in c for c in contents) == 1 and sum(b"METHOD:PUBLISH" in c for c in contents) == 1

    def test_sequence_rises_on_every_file_for_the_same_reminder(self, backbone):
        reminder_id = _create(backbone)
        for _ in range(2):
            backbone.queue_reminder_calendar_file(reminder_id, "PUBLISH")
            backbone._flush_reminder_calendar_files(CHAT)
        first, second = (c for _c, _n, c in backbone.denidin.green_api_bot.files[-2:])
        assert b"SEQUENCE:0" in first and b"SEQUENCE:1" in second

    def test_empty_queue_sends_nothing(self, backbone):
        backbone._flush_reminder_calendar_files(CHAT)
        assert backbone.denidin.green_api_bot.files == []

    def test_send_failure_sends_the_notice_and_never_raises(self, backbone):
        _create(backbone)
        backbone.denidin.green_api_bot.file_error = ConnectionError("down")
        backbone._flush_reminder_calendar_files(CHAT)
        assert backbone.denidin.green_api_bot.files == []
        assert NOTICE_SEND_FAILED in backbone.denidin.green_api_bot.sent_texts
        assert _queue(backbone) == {}

    def test_an_unknown_queued_id_is_skipped_without_raising(self, backbone):
        backbone.queue_reminder_calendar_file("vanished", "PUBLISH")
        backbone._flush_reminder_calendar_files(CHAT)
        assert backbone.denidin.green_api_bot.files == []

    def test_no_reminder_manager_does_not_raise(self, backbone):
        backbone.queue_reminder_calendar_file("x", "PUBLISH")
        backbone.denidin.reminder_manager = None
        backbone._flush_reminder_calendar_files(CHAT)
