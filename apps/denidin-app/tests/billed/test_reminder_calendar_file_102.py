"""
End-to-End Billed Test: Calendar file (.ics) alongside reminders (Feature 102)

One test per approved acceptance scenario of specs/repo/features/102-calendar-reminders-as-whatsapp-events/
user-stories.md (UAT numbers are in the test names). Text-only real OpenAI calls (billed tier); everything
internal is real. The WhatsApp boundary is the shared RecordingBot (tests/e2e_helpers.py), which records every
text AND every uploaded .ics on the turn's notification (`_test_sent_files`) - nothing is delivered anywhere.

AUTHORED ONLY - NOT YET RUN. The first billed run of this feature needs the user's explicit permission
(CLAUDE.md), then each run is `scripts/run_single_test.sh <node_id>`.

Not covered here, by design:
- UAT 3.1 (device import, iOS/Android) is MANUAL - see quickstart.md "Manual device checks".
- UAT 3.2 (a client never gets a file): the backbone currently treats every non-godfather/admin role as out of
  scope (Backbone._resolve_role, explicit 2026-10-01 decision) - there is no client reminder path to test; this
  is flagged in the Feature 102 hand-off rather than asserted here.

Every generated .ics is also copied to apps/denidin-app/test_results/ (gitignored) for inspection.
"""
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from icalendar import Calendar

import src.services.reminder_delivery_service as delivery_service
from src.models.config import AppConfiguration
from src.utils.time_utils import now_local, to_local
from tests.billed.denidin_mcp_e2e_helpers import get_button_send
from tests.e2e_helpers import (
    RECORDING_BOT, create_real_notification, get_full_reply, sanity_worker_data_root,
    wipe_chat_messages_on_disk,
)

logger = logging.getLogger(__name__)

PREFIX = "דנידין תזכורת: "
EXPORT_QUESTION = "לייצא את התזכורות שלך לקובץ יומן (ics)?"
SEND_FAILED_NOTICE = "לא הצלחתי לשלוח את קובץ היומן"


@pytest.mark.billed
class TestReminderCalendarFileBilled:

    # ---- fixtures (same wiring as tests/billed/test_reminder_lifecycle_billed.py) ----------------

    @pytest.fixture
    def config(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
        if not config_path.exists():
            pytest.skip("config.test.json not found")
        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        root = sanity_worker_data_root()
        config.data_root = str(root)
        config.memory['session']['storage_dir'] = str(root / "sessions")
        config.memory['longterm']['storage_dir'] = str(root / "memory")
        return config

    @pytest.fixture(autouse=True)
    def _isolate(self, config):
        """Empty chats and no leftover active reminders before AND after every test, and the recording
        bot's forced-failure switch off - every scenario starts from a known, empty state."""
        self._wipe_every_chat(Path(config.memory['session']['storage_dir']))
        RECORDING_BOT.file_error = None
        yield
        RECORDING_BOT.file_error = None
        self._wipe_every_chat(Path(config.memory['session']['storage_dir']))

    @staticmethod
    def _wipe_every_chat(sessions_dir):
        index_db = sessions_dir / "chat_index.db"
        if not index_db.exists():
            return
        con = sqlite3.connect(str(index_db))
        try:
            chats = [row[0] for row in con.execute("SELECT chat FROM chat_sessions")]
        finally:
            con.close()
        for chat in chats:
            wipe_chat_messages_on_disk(sessions_dir, chat)

    @pytest.fixture
    def denidin_app(self, config):
        import denidin
        if denidin.denidin_app is None:
            denidin.denidin_app = denidin.initialize_app({
                'green_api_instance_id': config.green_api_instance_id, 'green_api_token': config.green_api_token,
                'ai_api_key': config.ai_api_key, 'ai_model': config.ai_model,
                'ai_vision_model': config.ai_vision_model, 'ai_embedding_model': config.ai_embedding_model,
                'ai_reply_max_tokens': config.ai_reply_max_tokens, 'log_level': config.log_level,
                'data_root': config.data_root, 'feature_flags': config.feature_flags,
                'godfather_phone': config.godfather_phone, 'memory': config.memory,
                'constitution_config': config.constitution_config, 'user_roles': config.user_roles,
                'mcp': config.mcp, 'reminders': {'max_active_reminders': 20},
            })
        app = denidin.denidin_app
        assert Path(app.reminder_manager.storage_dir).resolve().is_relative_to(Path(config.data_root).resolve()), \
            "ReminderManager is not under the isolated test data root - refusing to proceed"
        for reminder in app.reminder_manager.list_active():  # a known, empty starting point
            app.reminder_manager.delete_whole_series(reminder["reminder_id"])
        return app

    # ---- helpers -----------------------------------------------------------------------------

    @staticmethod
    def _godfather(config):
        phone = config.godfather_phone
        return phone, f"{phone}@c.us"

    @staticmethod
    def _event(chat_id, sender, text, msg_id):
        return {
            'typeWebhook': 'incomingMessageReceived', 'idMessage': msg_id,
            'timestamp': int(now_local().timestamp()),
            'senderData': {'chatId': chat_id, 'sender': sender, 'senderName': "Test Godfather"},
            'messageData': {'typeMessage': 'textMessage', 'textMessageData': {'textMessage': text}},
        }

    def _say(self, config, text, label):
        """The godfather sends `text`; returns the turn's notification (replies/buttons/files recorded on it)."""
        from denidin import handle_text_message
        phone, chat_id = self._godfather(config)
        notification = create_real_notification(
            self._event(chat_id, phone, text, f"billed102_{label}_{uuid.uuid4().hex[:8]}"))
        handle_text_message(notification)
        return notification

    def _create(self, denidin_app, config, request, label):
        """Request + approve a reminder through the real conversation; returns (reminder_id, confirmation turn)."""
        before = {r["reminder_id"] for r in denidin_app.reminder_manager.list_active()}
        proposal = self._say(config, request, f"{label}_ask")
        assert get_full_reply(proposal) and "לאישור" in get_full_reply(proposal)
        assert self._files(proposal) == [], "no file may exist before the user approves"
        approved = self._say(config, "כן", f"{label}_yes")
        new = {r["reminder_id"] for r in denidin_app.reminder_manager.list_active()} - before
        assert len(new) == 1, f"expected exactly one new reminder, got {new}"
        return new.pop(), approved

    @staticmethod
    def _files(notification):
        return notification._test_sent_files

    def _one_file(self, notification, label):
        files = self._files(notification)
        assert len(files) == 1, f"expected exactly one .ics, got {[f['file_name'] for f in files]}"
        self._keep(files[0], label)
        return files[0]

    @staticmethod
    def _keep(file_record, label):
        """Permanent copy for inspection (never lose a real generated file)."""
        results = Path(__file__).parent.parent.parent / "test_results"
        results.mkdir(exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        (results / f"reminder_ics_102_{label}_{stamp}.ics").write_bytes(file_record["content"])

    @staticmethod
    def _events(file_record):
        calendar = Calendar.from_ical(file_record["content"])
        return calendar, [c for c in calendar.walk() if c.name == "VEVENT"]

    def _assert_sent_after_the_text(self, notification, record):
        assert record["after_message_count"] == len(notification._test_sent_messages), \
            "the file must arrive AFTER the confirmation text, as the last thing sent"

    # ---- Story 1: a new reminder also arrives as a calendar file --------------------------------

    def test_uat_1_1_one_time_create_sends_a_valid_ics(self, denidin_app, config):
        reminder_id, approved = self._create(
            denidin_app, config, "תזכיר לי ביום שני הקרוב ב-11:00 דיון בבית המשפט", "uat11")
        record = self._one_file(approved, "uat11")
        calendar, events = self._events(record)

        assert str(calendar.get("METHOD")) == "PUBLISH"
        (event,) = events
        assert str(event["SUMMARY"]) == f"{PREFIX}דיון בבית המשפט"
        assert str(event["UID"]) == reminder_id and int(event["SEQUENCE"]) == 0
        start, end = to_local(event["DTSTART"].dt), to_local(event["DTEND"].dt)
        assert start == end, "a DeniDin reminder is a zero-length alarm"
        assert start.weekday() == 0 and (start.hour, start.minute) == (11, 0)
        assert "RRULE" not in event
        assert b"BEGIN:VALARM" not in record["content"], "no alert"
        assert b"BEGIN:VTIMEZONE" not in record["content"], "an embedded VTIMEZONE shifts updates on Android"
        assert b"TZID=Asia/Jerusalem" in record["content"]
        assert reminder_id in {r["reminder_id"] for r in denidin_app.reminder_manager.list_active()}
        self._assert_sent_after_the_text(approved, record)

    def test_uat_1_2_decline_sends_no_reminder_and_no_file(self, denidin_app, config):
        proposal = self._say(config, "תזכיר לי בעוד שעה לקנות חלב", "uat12_ask")
        assert "לאישור" in get_full_reply(proposal)
        declined = self._say(config, "לא", "uat12_no")
        assert self._files(proposal) == [] and self._files(declined) == []
        assert denidin_app.reminder_manager.list_active() == []

    def test_uat_1_3_recurring_create_carries_the_rrule(self, denidin_app, config):
        reminder_id, approved = self._create(
            denidin_app, config, "תזכיר לי כל יום ראשון ב-9:00 להגיש דוח שבועי", "uat13")
        _calendar, (event,) = self._events(self._one_file(approved, "uat13"))
        assert str(event["UID"]) == reminder_id
        rrule = event["RRULE"]
        assert rrule["FREQ"] == ["WEEKLY"] and rrule["BYDAY"] == ["SU"]
        assert (to_local(event["DTSTART"].dt).hour, to_local(event["DTSTART"].dt).minute) == (9, 0)
        assert denidin_app.reminder_manager.get_reminder(reminder_id)["rrule"], "stored as 054 stores it"

    def test_uat_1_4_the_due_time_text_nudge_is_still_delivered(self, denidin_app, config, monkeypatch):
        reminder_id, approved = self._create(
            denidin_app, config, "תזכיר לי בעוד שעתיים להתקשר לרואה חשבון", "uat14")
        self._one_file(approved, "uat14")
        row = denidin_app.reminder_manager.get_reminder(reminder_id)
        due_at = to_local(datetime.fromisoformat(row["dtstart"]))
        send = MagicMock(return_value="wamid.test")
        monkeypatch.setattr(delivery_service, "send_proactive_message", send)
        delivery_service._sweep_due_reminders(denidin_app, MagicMock(), now=due_at)  # pylint: disable=protected-access
        send.assert_called_once()
        assert send.call_args.args[2], "the 054 text nudge is delivered, unchanged"

    # ---- Story 2: modify / delete keeps the calendar honest -------------------------------------

    def test_uat_2_1_modify_time_sends_the_same_uid_with_a_higher_sequence(self, denidin_app, config):
        reminder_id, created = self._create(
            denidin_app, config, "תזכיר לי מחר ב-10:00 להתקשר לעורך הדין", "uat21_setup")
        first = self._one_file(created, "uat21_first")
        modified_turn = self._say(config, "תשנה את התזכורת של עורך הדין לשעה 14:00", "uat21_ask")
        assert "לאישור" in get_full_reply(modified_turn)
        done = self._say(config, "כן", "uat21_yes")
        second = self._one_file(done, "uat21_second")

        _c1, (before,) = self._events(first)
        _c2, (after,) = self._events(second)
        assert str(after["UID"]) == str(before["UID"]) == reminder_id
        assert int(after["SEQUENCE"]) == int(before["SEQUENCE"]) + 1
        assert to_local(after["DTSTART"].dt).hour == 14
        self._assert_sent_after_the_text(done, second)

    def test_uat_2_2_delete_sends_a_cancel_file(self, denidin_app, config):
        reminder_id, _created = self._create(
            denidin_app, config, "תזכיר לי בעוד שעתיים להוציא את הכביסה", "uat22_setup")
        asked = self._say(config, "תבטל את התזכורת של הכביסה", "uat22_ask")
        assert "לאישור" in get_full_reply(asked)
        done = self._say(config, "כן", "uat22_yes")
        record = self._one_file(done, "uat22")
        calendar, (event,) = self._events(record)
        assert str(calendar.get("METHOD")) == "CANCEL" and str(event["STATUS"]) == "CANCELLED"
        assert str(event["UID"]) == reminder_id and int(event["SEQUENCE"]) >= 1
        assert denidin_app.reminder_manager.get_reminder(reminder_id) is None

    def test_uat_2_3_one_occurrence_change_carries_master_plus_override(self, denidin_app, config):
        reminder_id, _created = self._create(
            denidin_app, config, "תזכיר לי כל יום בשעה 9:00 לשתות מים", "uat23_setup")
        asked = self._say(config, "תדחה רק את התזכורת של מחר לשעה 10:00, לא את כל הסדרה", "uat23_ask")
        assert "לאישור" in get_full_reply(asked)
        done = self._say(config, "כן", "uat23_yes")
        _calendar, events = self._events(self._one_file(done, "uat23"))
        masters = [e for e in events if "RECURRENCE-ID" not in e]
        overrides = [e for e in events if "RECURRENCE-ID" in e]
        assert len(masters) == 1 and len(overrides) == 1
        assert str(masters[0]["UID"]) == str(overrides[0]["UID"]) == reminder_id
        assert to_local(overrides[0]["DTSTART"].dt).strftime("%H:%M") == "10:00"

    def test_uat_2_4_skipping_one_occurrence_carries_an_exdate(self, denidin_app, config):
        reminder_id, _created = self._create(
            denidin_app, config, "תזכיר לי כל יום בשעה 8:00 להתעמל", "uat24_setup")
        asked = self._say(config, "תדלג על התזכורת של מחר להתעמלות, רק על מחר", "uat24_ask")
        assert "לאישור" in get_full_reply(asked)
        done = self._say(config, "כן", "uat24_yes")
        record = self._one_file(done, "uat24")
        _calendar, events = self._events(record)
        masters = [e for e in events if "RECURRENCE-ID" not in e]
        assert len(masters) == 1 and str(masters[0]["UID"]) == reminder_id
        assert b"EXDATE" in record["content"], "the skipped occurrence is an EXDATE on the master"

    def test_uat_2_5_deleting_the_whole_series_sends_a_cancel(self, denidin_app, config):
        reminder_id, _created = self._create(
            denidin_app, config, "תזכיר לי כל שבוע בימי רביעי בשעה 8:00 לשלוח דוח", "uat25_setup")
        asked = self._say(config, "תבטל לגמרי את התזכורת לשליחת הדוח, את כל הסדרה", "uat25_ask")
        assert get_full_reply(asked)
        done = self._say(config, "כן", "uat25_yes")
        calendar, (event,) = self._events(self._one_file(done, "uat25"))
        assert str(calendar.get("METHOD")) == "CANCEL" and str(event["UID"]) == reminder_id
        assert denidin_app.reminder_manager.get_reminder(reminder_id) is None

    # ---- Story 3: safety -------------------------------------------------------------------------

    def test_uat_3_3_a_failed_file_send_keeps_the_reminder_and_tells_the_user(self, denidin_app, config):
        proposal = self._say(config, "תזכיר לי בעוד שעה לשלם לספק", "uat33_ask")
        assert "לאישור" in get_full_reply(proposal)
        RECORDING_BOT.file_error = ConnectionError("forced file-send failure (UAT 3.3)")
        approved = self._say(config, "כן", "uat33_yes")
        assert len(denidin_app.reminder_manager.list_active()) == 1, "the reminder is still stored"
        assert self._files(approved) == []
        assert SEND_FAILED_NOTICE in get_full_reply(approved), "the user is told the calendar file failed"

    # ---- Story 4: asking for the file of an existing reminder -------------------------------------

    def _seed(self, denidin_app, config, text, days=3, hour=11):
        phone, chat_id = self._godfather(config)
        due = (now_local() + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)
        return denidin_app.reminder_manager.create_reminder(
            text, "one_time", due.isoformat(), None, phone, "GODFATHER", chat_id)["reminder_id"]

    def test_uat_4_1_asking_for_a_file_sends_it_without_an_approval_step(self, denidin_app, config):
        reminder_id = self._seed(denidin_app, config, "דיון בבית המשפט")
        turn = self._say(config, "תשלח לי קובץ יומן לתזכורת של הדיון", "uat41")
        record = self._one_file(turn, "uat41")
        _calendar, (event,) = self._events(record)
        assert str(event["UID"]) == reminder_id and str(event["SUMMARY"]) == f"{PREFIX}דיון בבית המשפט"
        assert "לאישור — כן/לא?" not in (get_full_reply(turn) or ""), "no approval step for a read-only send"
        assert get_button_send(turn) is None

    def test_uat_4_2_two_matches_ask_which_before_sending(self, denidin_app, config):
        self._seed(denidin_app, config, "דיון בבית המשפט בתל אביב", days=3)
        self._seed(denidin_app, config, "דיון בבית המשפט בחיפה", days=4)
        turn = self._say(config, "תשלח לי קובץ יומן לתזכורת של הדיון", "uat42")
        assert self._files(turn) == [], "nothing is sent until the user says which one"
        reply = get_full_reply(turn)
        assert reply and ("תל אביב" in reply and "חיפה" in reply)

    def test_uat_4_3_a_reminder_that_does_not_exist_sends_nothing(self, denidin_app, config):
        self._seed(denidin_app, config, "דיון בבית המשפט")
        turn = self._say(config, "תשלח לי קובץ יומן לתזכורת של הטיסה לאילת", "uat43")
        assert self._files(turn) == []
        assert get_full_reply(turn), "the user is told it was not found"

    # ---- Story 5: DeniDin offers the file when listing ---------------------------------------------

    def test_uat_5_1_listing_reminders_offers_the_file_and_sends_nothing(self, denidin_app, config):
        self._seed(denidin_app, config, "דיון בבית המשפט", days=3)
        self._seed(denidin_app, config, "פגישה עם רואה החשבון", days=4)
        turn = self._say(config, "אילו תזכורות יש לי?", "uat51")
        reply = get_full_reply(turn) or ""
        assert "דיון בבית המשפט" in reply and "פגישה עם רואה החשבון" in reply
        assert EXPORT_QUESTION in reply, "the offer is part of the same reply"
        assert self._files(turn) == []

    def test_uat_5_2_accepting_the_offer_sends_the_file(self, denidin_app, config):
        self._seed(denidin_app, config, "דיון בבית המשפט", days=3)
        self._seed(denidin_app, config, "פגישה עם רואה החשבון", days=4)
        self._say(config, "אילו תזכורות יש לי?", "uat52_list")
        accepted = self._say(config, "כן", "uat52_yes")
        _calendar, events = self._events(self._one_file(accepted, "uat52"))
        assert len(events) == 2

    def test_uat_5_3_declining_or_ignoring_the_offer_sends_nothing_and_does_not_nag(self, denidin_app, config):
        self._seed(denidin_app, config, "דיון בבית המשפט", days=3)
        self._say(config, "אילו תזכורות יש לי?", "uat53_list")
        declined = self._say(config, "לא", "uat53_no")
        assert self._files(declined) == []
        assert EXPORT_QUESTION not in (get_full_reply(declined) or ""), "no further prompt after a no"

    def test_uat_5_4_an_unrelated_question_gets_no_calendar_offer(self, denidin_app, config):
        self._seed(denidin_app, config, "דיון בבית המשפט")
        turn = self._say(config, "מה ההבדל בין חשבונית מס לקבלה?", "uat54")
        reply = get_full_reply(turn) or ""
        assert reply and "יומן" not in reply and "ics" not in reply.lower()
        assert self._files(turn) == []
