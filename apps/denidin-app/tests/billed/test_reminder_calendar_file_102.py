"""
End-to-End Billed Test: the calendar-file OFFER (Feature 102)

Only what needs the real model is billed here: whether it offers the calendar-file export after a question
about reminders, sends the right file on a yes, does not nag after a no, and does not offer on unrelated
questions. The .ics itself (content, order after the confirmation text, create/modify/delete/CANCEL, single
occurrences, failures) is deterministic and is covered by tests/integration/test_reminder_calendar_file_102.py
and, on the real-model path, by assertions added to tests/billed/test_reminder_lifecycle_billed.py.

AUTHORED ONLY - NOT YET RUN. The first billed run of this feature needs the user's explicit permission
(CLAUDE.md); then `scripts/run_single_test.sh <node_id>`.
"""
import sqlite3
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from icalendar import Calendar

from src.models.config import AppConfiguration
from src.utils.time_utils import now_local
from tests.billed.denidin_mcp_e2e_helpers import get_button_send
from tests.e2e_helpers import (
    RECORDING_BOT, create_real_notification, get_full_reply, sanity_worker_data_root,
    wipe_chat_messages_on_disk,
)



def _offer_buttons(turn):
    """The yes/no buttons message of the turn, if any. The wording is the model's (it adapts singular/plural),
    so the offer is recognised by being a buttons message that is about a calendar file (יומן / ics)."""
    sent = get_button_send(turn)
    return sent if sent and ("יומן" in sent["body"] or "ics" in sent["body"].lower()) else None


@pytest.mark.billed
class TestReminderCalendarOfferBilled:

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
        """Empty chats before AND after every test (same as the lifecycle billed file)."""
        self._wipe_every_chat(Path(config.memory['session']['storage_dir']))
        RECORDING_BOT.file_error = None
        yield
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

    def _say(self, config, text, label):
        from denidin import handle_text_message
        phone = config.godfather_phone
        chat_id = f"{phone}@c.us"
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived', 'idMessage': f"billed102_{label}_{uuid.uuid4().hex[:8]}",
            'timestamp': int(now_local().timestamp()),
            'senderData': {'chatId': chat_id, 'sender': phone, 'senderName': "Test Godfather"},
            'messageData': {'typeMessage': 'textMessage', 'textMessageData': {'textMessage': text}},
        })
        handle_text_message(notification)
        return notification

    @staticmethod
    def _seed(denidin_app, config, text, days):
        phone = config.godfather_phone
        due = (now_local() + timedelta(days=days)).replace(hour=11, minute=0, second=0, microsecond=0)
        return denidin_app.reminder_manager.create_reminder(
            text, "one_time", due.isoformat(), None, phone, "GODFATHER", f"{phone}@c.us")["reminder_id"]

    def test_listing_reminders_offers_the_file_and_sends_nothing(self, denidin_app, config):
        self._seed(denidin_app, config, "דיון בבית המשפט", 3)
        self._seed(denidin_app, config, "פגישה עם רואה החשבון", 4)
        turn = self._say(config, "אילו תזכורות יש לי?", "list")
        reply = get_full_reply(turn) or ""
        assert "דיון בבית המשפט" in reply and "פגישה עם רואה החשבון" in reply
        assert _offer_buttons(turn) is not None, "the offer is yes/no buttons, in the same turn as the list"
        assert turn._test_sent_files == []

    def test_a_question_about_reminders_also_offers_the_file(self, denidin_app, config):
        self._seed(denidin_app, config, "דיון בבית המשפט", 1)
        turn = self._say(config, "מה יש לי מחר ביומן התזכורות?", "question")
        assert _offer_buttons(turn) is not None, "expected yes/no buttons offering the calendar file"
        assert turn._test_sent_files == []

    def test_accepting_the_offer_sends_one_file_with_the_listed_reminders(self, denidin_app, config):
        ids = {self._seed(denidin_app, config, "דיון בבית המשפט", 3),
               self._seed(denidin_app, config, "פגישה עם רואה החשבון", 4)}
        self._say(config, "אילו תזכורות יש לי?", "accept_list")
        accepted = self._say(config, "כן", "accept_yes")
        (record,) = accepted._test_sent_files
        events = [c for c in Calendar.from_ical(record["content"]).walk() if c.name == "VEVENT"]
        assert {str(e["UID"]) for e in events} == ids

    def test_declining_the_offer_sends_nothing_and_does_not_nag(self, denidin_app, config):
        self._seed(denidin_app, config, "דיון בבית המשפט", 3)
        self._say(config, "אילו תזכורות יש לי?", "decline_list")
        declined = self._say(config, "לא", "decline_no")
        assert declined._test_sent_files == []
        assert get_button_send(declined) is None, "no further prompt after a no"

    def test_an_unrelated_question_gets_no_calendar_offer(self, denidin_app, config):
        self._seed(denidin_app, config, "דיון בבית המשפט", 3)
        turn = self._say(config, "מה ההבדל בין חשבונית מס לקבלה?", "unrelated")
        reply = get_full_reply(turn) or ""
        assert reply and "יומן" not in reply and "ics" not in reply.lower()
        assert get_button_send(turn) is None and turn._test_sent_files == []
