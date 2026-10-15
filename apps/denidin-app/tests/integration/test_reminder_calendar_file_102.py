"""
Component-Integration Test: Calendar file alongside reminders (Feature 102, T007)

The full real path for each approved scenario: a real Green API notification -> denidin handlers ->
WhatsAppHandler -> Backbone -> real ReminderManager -> the model's confirmation, then the .ics file -
all real internal objects (CONSTITUTION SS V); only the OpenAI client (scripted) and the Green API bot
(FakeBot, which records every text/button/file in send order) are stood in for.

Proves the wiring and ORDER (confirmation text first, file second, only on success). Whether the model
makes the right calls on a real conversation belongs to tests/billed/test_reminder_calendar_file_102.py.
"""
from datetime import timedelta

import pytest

from src.services.reminder_delivery_service import _sweep_due_reminders
from src.utils.time_utils import now_local
from tests.routing_test_support import (
    build_routing_app, function_call, nothing_more, send_to_user, text_notification,
)

CHAT = "972501234567@c.us"
SENDER = "972501234567@c.us"


def _tap_notification(selected_id, stanza_id, msg_id="tap_1"):
    from whatsapp_chatbot_python import Notification
    notification = Notification.__new__(Notification)
    notification.event = {
        'typeWebhook': 'incomingMessageReceived', 'idMessage': msg_id, 'timestamp': 1755331200,
        'senderData': {'chatId': CHAT, 'sender': SENDER, 'senderName': "Test Godfather"},
        'messageData': {'typeMessage': 'interactiveButtonsResponse',
                        'interactiveButtonsResponse': {'selectedId': selected_id, 'stanzaId': stanza_id}},
    }
    notification.answer = lambda message: None
    return notification


@pytest.mark.integration
class TestCalendarFileAfterApprovedWrites:

    @pytest.fixture
    def app(self, tmp_path, monkeypatch):
        app = build_routing_app(tmp_path, monkeypatch)
        # An outstanding approval, as after the model's yes/no buttons: the next "כן" is an approved write.
        app.session_manager.set_active_capabilities(CHAT, ["cap_reminders_write"])
        app.session_manager.set_approval_message_id(CHAT, "BTN-OLD")
        yield app
        app.session_manager.close()

    def _answer(self, app, text, *calls):
        from denidin import handle_text_message
        app.ai_client.with_options.return_value.responses.create.side_effect = list(calls)
        handle_text_message(text_notification(CHAT, SENDER, "Test Godfather", text, f"msg_{text}_{len(calls)}"))

    def _create_args(self, text="להתקשר לרואה חשבון", hours=3):
        return {"message_text": text, "schedule_type": "one_time", "recurrence": None,
                "one_time_due_at": (now_local() + timedelta(hours=hours)).isoformat()}

    def test_one_time_create_sends_the_confirmation_then_one_file(self, app):
        self._answer(app, "כן", function_call("create_reminder", self._create_args(), rid="r1"),
                     send_to_user("✅ התזכורת נוצרה", rid="r2"), nothing_more("r3"))

        events = app.green_api_bot.events
        assert [kind for kind, _ in events] == ["text", "file"]  # the confirmation arrives BEFORE the file
        assert events[0][1] == "✅ התזכורת נוצרה"
        (chat, name, content), = app.green_api_bot.files
        assert chat == CHAT and name.endswith(".ics")
        assert b"METHOD:PUBLISH" in content and "דנידין תזכורת: להתקשר לרואה חשבון".encode() in content
        assert b"RRULE" not in content and b"VALARM" not in content
        (reminder,) = app.reminder_manager.list_active()
        assert f"UID:{reminder['reminder_id']}".encode() in content

    def test_recurring_create_sends_one_file_with_the_rule(self, app):
        first = (now_local() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        recurrence = {"interval": 1, "freq": "weekly", "weekdays": ["MO"], "month_day": None,
                      "month_nth_weekday": None, "first_occurrence_at": first.isoformat(),
                      "end_condition": "never", "end_count": None, "end_until": None}
        args = {"message_text": "ישיבת צוות", "schedule_type": "recurring", "one_time_due_at": None,
                "recurrence": recurrence}
        self._answer(app, "כן", function_call("create_reminder", args, rid="r1"),
                     send_to_user("✅ נוצרה תזכורת שבועית", rid="r2"), nothing_more("r3"))

        (_chat, _name, content), = app.green_api_bot.files
        assert b"RRULE:FREQ=WEEKLY" in content and "דנידין תזכורת: ישיבת צוות".encode() in content

    def test_a_failed_create_sends_no_file(self, app):
        args = self._create_args()
        args["one_time_due_at"] = (now_local() - timedelta(days=1)).isoformat()
        self._answer(app, "כן", function_call("create_reminder", args, rid="r1"),
                     send_to_user("⚠️ לא הצלחתי ליצור", rid="r2"), nothing_more("r3"))
        assert app.green_api_bot.files == [] and app.reminder_manager.list_active() == []

    def test_a_decline_sends_no_file(self, app):
        self._answer(app, "לא", send_to_user("בסדר, לא יצרתי. מה לשנות?", rid="r1"), nothing_more("r2"))
        assert app.green_api_bot.files == [] and app.reminder_manager.list_active() == []

    def test_a_button_tap_behaves_like_a_typed_yes(self, app):
        from denidin import handle_button_tap
        app.ai_client.with_options.return_value.responses.create.side_effect = [
            function_call("create_reminder", self._create_args(), rid="r1"),
            send_to_user("✅ התזכורת נוצרה", rid="r2"), nothing_more("r3")]
        handle_button_tap(_tap_notification("denidin_approve", "BTN-OLD"))
        assert [kind for kind, _ in app.green_api_bot.events] == ["text", "file"]

    def test_modify_sends_the_updated_file(self, app):
        reminder_id = app.reminder_manager.create_reminder(
            "ישן", "one_time", (now_local() + timedelta(days=2)).isoformat(), None, SENDER, "GODFATHER", CHAT
        )["reminder_id"]
        args = {"reminder_id": reminder_id, "scope": "whole_series", "new_message_text": "חדש",
                "new_due_at": None, "new_recurrence": None, "occurrence_date_hint": None}
        self._answer(app, "כן", function_call("modify_reminder", args, rid="r1"),
                     send_to_user("✅ עודכן", rid="r2"), nothing_more("r3"))
        (_chat, _name, content), = app.green_api_bot.files
        assert b"METHOD:PUBLISH" in content and "דנידין תזכורת: חדש".encode() in content
        assert f"UID:{reminder_id}".encode() in content

    def test_delete_sends_a_cancel_file(self, app):
        reminder_id = app.reminder_manager.create_reminder(
            "למחוק", "one_time", (now_local() + timedelta(days=2)).isoformat(), None, SENDER, "GODFATHER", CHAT
        )["reminder_id"]
        args = {"reminder_id": reminder_id, "scope": "whole_series", "occurrence_date_hint": None}
        self._answer(app, "כן", function_call("delete_reminder", args, rid="r1"),
                     send_to_user("✅ בוטל", rid="r2"), nothing_more("r3"))
        (_chat, _name, content), = app.green_api_bot.files
        assert b"METHOD:CANCEL" in content and b"STATUS:CANCELLED" in content
        assert f"UID:{reminder_id}".encode() in content


    def _daily(self, app):
        first = (now_local() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        recurrence = {"interval": 1, "freq": "daily", "weekdays": None, "month_day": None,
                      "month_nth_weekday": None, "first_occurrence_at": first.isoformat(),
                      "end_condition": "never", "end_count": None, "end_until": None}
        reminder_id = app.reminder_manager.create_reminder(
            "לשתות מים", "recurring", None, recurrence, SENDER, "GODFATHER", CHAT)["reminder_id"]
        return reminder_id, first

    def test_changing_one_occurrence_sends_the_master_plus_an_override(self, app):
        reminder_id, first = self._daily(app)
        args = {"reminder_id": reminder_id, "scope": "single_occurrence",
                "occurrence_date_hint": (first + timedelta(days=1)).date().isoformat(),
                "new_message_text": None, "new_due_at": (first + timedelta(days=1, hours=1)).isoformat(),
                "new_recurrence": None}
        self._answer(app, "כן", function_call("modify_reminder", args, rid="r1"),
                     send_to_user("✅ עודכן", rid="r2"), nothing_more("r3"))
        (_chat, _name, content), = app.green_api_bot.files
        assert content.count(b"BEGIN:VEVENT") == 2 and b"RECURRENCE-ID" in content and b"RRULE:FREQ=DAILY" in content

    def test_skipping_one_occurrence_sends_the_master_with_an_exdate(self, app):
        reminder_id, first = self._daily(app)
        args = {"reminder_id": reminder_id, "scope": "single_occurrence",
                "occurrence_date_hint": (first + timedelta(days=1)).date().isoformat()}
        self._answer(app, "כן", function_call("delete_reminder", args, rid="r1"),
                     send_to_user("✅ הדילוג נשמר", rid="r2"), nothing_more("r3"))
        (_chat, _name, content), = app.green_api_bot.files
        assert b"METHOD:PUBLISH" in content and b"EXDATE" in content and content.count(b"BEGIN:VEVENT") == 1

    def test_a_failed_file_send_keeps_the_reminder_and_tells_the_user(self, app):
        app.green_api_bot.file_error = ConnectionError("down")
        self._answer(app, "כן", function_call("create_reminder", self._create_args(), rid="r1"),
                     send_to_user("✅ התזכורת נוצרה", rid="r2"), nothing_more("r3"))
        assert len(app.reminder_manager.list_active()) == 1
        assert app.green_api_bot.files == []
        texts = [text for kind, text in app.green_api_bot.events if kind == "text"]
        assert texts[0] == "✅ התזכורת נוצרה" and "לא הצלחתי לשלוח את קובץ היומן" in texts[-1]


@pytest.mark.integration
class TestDeliveryNudgeIsUnchanged:

    def test_the_due_time_nudge_is_still_plain_text_with_no_file(self, tmp_path, monkeypatch):
        app = build_routing_app(tmp_path, monkeypatch)
        try:
            created = app.reminder_manager.create_reminder(
                "לשלם לספק", "one_time", (now_local() + timedelta(minutes=30)).isoformat(), None,
                SENDER, "GODFATHER", CHAT)
            from datetime import datetime
            due = datetime.fromisoformat(created["due_at"])

            _sweep_due_reminders(app, app.green_api_bot, now=due + timedelta(minutes=1))

            assert app.green_api_bot.files == []
            assert any("לשלם לספק" in text for kind, text in app.green_api_bot.events if kind == "text")
        finally:
            app.session_manager.close()
