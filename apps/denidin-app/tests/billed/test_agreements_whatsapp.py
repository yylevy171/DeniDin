"""
Billed E2E: WhatsApp agreement conversations (Feature 089, US5, UAT 5.1-5.6; the bot halves of
4.2 / 4.3). Real webhook dispatch through denidin.py with the backbone flag ON and real OpenAI
calls; the Agreements DB and ledger are real files under an isolated test data root.

What is asserted is the OUTCOME in the Agreements DB / ledger (deterministic) plus loose
properties of the reply - never the model's exact Hebrew wording. Each test seeds its own
agreement(s) through the real AgreementsManager (actor "webapp") so it starts from a known state.

Known coverage limit, stated plainly: UAT 5.1's first detour (two Morning clients answering to
"Israel") needs two such clients in the Morning sandbox, which this suite does not control; the
test gives the exact stored client name and covers the second detour (two agreements -> which one?)
and the short-reply rule.
"""
import json
import logging
import sqlite3
import uuid
from pathlib import Path

import pytest

from src.models.config import AppConfiguration
from src.utils.time_utils import now_local
from tests.e2e_helpers import create_real_notification, get_response, sanity_worker_data_root, wipe_chat_messages_on_disk

logger = logging.getLogger(__name__)

# A real client of the Morning sandbox (tests/fixtures/morning_sandbox_clients.json): the flow resolves
# the client in Morning before reading the Agreements DB, so an invented name is "not found".
CLIENT = "אדיר זריהון"
APPEAL = "ייצוג בבית הדין הארצי"
DAMAGES = "תביעת נזיקין"


@pytest.mark.billed
class TestAgreementsWhatsAppBilled:

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
                'agreements_api': {'port': 0, 'auth_token': 'unused'},
            })
        app = denidin.denidin_app
        assert app.agreements_manager is not None, "the app was built without an AgreementsManager"
        assert Path(app.agreements_manager.db_path).resolve().is_relative_to(Path(config.data_root).resolve()), \
            "AgreementsManager must live under this test's isolated data_root"
        return app

    @pytest.fixture(autouse=True)
    def _clean(self, config):
        """A fresh Agreements DB and empty chats around every test."""
        sessions_dir = Path(config.memory['session']['storage_dir'])
        self._wipe(config, sessions_dir)
        yield
        self._wipe(config, sessions_dir)

    @staticmethod
    def _wipe(config, sessions_dir):
        db = Path(config.data_root) / "agreements" / "agreements.db"
        if db.exists():
            con = sqlite3.connect(str(db))
            try:
                for table in ("components", "agreements"):
                    con.execute(f"DELETE FROM {table}")
                con.commit()
            finally:
                con.close()
        index_db = sessions_dir / "chat_index.db"
        if index_db.exists():
            con = sqlite3.connect(str(index_db))
            try:
                chats = [row[0] for row in con.execute("SELECT chat FROM chat_sessions")]
            finally:
                con.close()
            for chat in chats:
                wipe_chat_messages_on_disk(sessions_dir, chat)

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _godfather(config):
        return config.godfather_phone, f"{config.godfather_phone}@c.us"

    @staticmethod
    def _say(chat_id, phone, text, label):
        from denidin import handle_text_message
        event = {
            'typeWebhook': 'incomingMessageReceived', 'idMessage': f"billed_{label}_{uuid.uuid4().hex[:8]}",
            'timestamp': int(now_local().timestamp()),
            'senderData': {'chatId': chat_id, 'sender': phone, 'senderName': "Test Godfather"},
            'messageData': {'typeMessage': 'textMessage', 'textMessageData': {'textMessage': text}},
        }
        notification = create_real_notification(event)
        handle_text_message(notification)
        return get_response(notification)

    @staticmethod
    def _seed(app, title=APPEAL, components=None):
        agreement, _ = app.agreements_manager.create_agreement(
            client_name=CLIENT, title=title, actor="webapp",
            components=components or [
                {"label": "ריטיינר", "amount": 5000, "vat_status": "לא כולל מע״מ"},
                {"label": "שכר טרחה באחוזים", "percent": 20, "percent_base": "סכום הזכייה"},
            ])
        return agreement

    @staticmethod
    def _component(app, agreement_id, label):
        agreement = app.agreements_manager.get_agreement(agreement_id)
        return next(c for c in agreement["components"] if c["label"] == label)

    @staticmethod
    def _agreement_events(config, agreement_id):
        out = []
        for path in sorted((Path(config.data_root) / "events").glob("*.json")):
            event = json.loads(path.read_text(encoding="utf-8"))
            if event.get("agreement_id") == agreement_id and event.get("source_type") == "הסכם":
                out.append(event)
        return out

    # ------------------------------------------------------------------ tests

    def test_uat_5_1_query_with_agreement_ambiguity(self, denidin_app, config):
        phone, chat = self._godfather(config)
        appeal = self._seed(denidin_app, APPEAL)
        self._seed(denidin_app, DAMAGES, [{"label": "ריטיינר", "amount": 1000}])
        state_before = denidin_app.agreements_manager.get_agreement(appeal["agreement_id"])

        ask = self._say(chat, phone, f"מה ההסכם שלנו עם {CLIENT}?", "q1")
        assert ask and "ארצי" in ask and "נזיק" in ask, f"expected a which-agreement question naming both: {ask!r}"

        answer = self._say(chat, phone, "לארצי", "q2")
        assert answer and "ריטיינר" in answer
        assert "5,000" in answer or "5000" in answer
        assert "20%" in answer or "20" in answer
        assert "1,000" not in answer  # the other agreement's component never leaks in

        assert denidin_app.agreements_manager.get_agreement(appeal["agreement_id"]) == state_before  # a read changes nothing
        assert len(self._agreement_events(config, appeal["agreement_id"])) == 2  # only the seed's events

    def test_uat_5_2_edit_component_amount(self, denidin_app, config):
        phone, chat = self._godfather(config)
        agreement = self._seed(denidin_app)
        agreement_id = agreement["agreement_id"]
        events_before = len(self._agreement_events(config, agreement_id))

        proposal = self._say(chat, phone, f"סיכמנו עם {CLIENT} בערעור להעלות את הריטיינר ל-6,000 ש״ח", "e1")
        assert proposal
        assert self._component(denidin_app, agreement_id, "ריטיינר")["amount"] == 5000, "wrote before approval"

        confirmation = self._say(chat, phone, "כן", "e1_yes")
        assert confirmation
        assert self._component(denidin_app, agreement_id, "ריטיינר")["amount"] == 6000
        assert self._component(denidin_app, agreement_id, "שכר טרחה באחוזים")["percent"] == 20
        assert len(self._agreement_events(config, agreement_id)) == events_before + 1

    def test_uat_5_3_edit_payer_and_partner(self, denidin_app, config):
        phone, chat = self._godfather(config)
        agreement = self._seed(denidin_app)
        agreement_id = agreement["agreement_id"]
        events_before = len(self._agreement_events(config, agreement_id))

        self._say(chat, phone, f"בערעור של {CLIENT} תוסיף את עו״ד כהן כשותף ב-25%, "
                                "והמשלם הוא בעצם ההסתדרות ולא אדיר", "t1")
        assert denidin_app.agreements_manager.get_agreement(agreement_id)["partner_name"] is None, "wrote before approval"

        self._say(chat, phone, "כן", "t1_yes")
        after = denidin_app.agreements_manager.get_agreement(agreement_id)
        assert "הסתדרות" in (after["payer_name"] or "")
        assert "כהן" in (after["partner_name"] or "")
        assert after["partner_percent"] == 25
        assert len(self._agreement_events(config, agreement_id)) == events_before + 2  # one per component

    def test_uat_5_4_add_component_starts_pending(self, denidin_app, config):
        phone, chat = self._godfather(config)
        agreement = self._seed(denidin_app)
        agreement_id = agreement["agreement_id"]

        self._say(chat, phone, f"תוסיף רכיב חדש להסכם הערעור של {CLIENT}: 1,500 ש״ח כולל מע״מ על כל דיון נוסף "
                                "מעבר לקבוע מראש", "a1")
        assert len(denidin_app.agreements_manager.get_agreement(agreement_id)["components"]) == 2, "wrote before approval"

        self._say(chat, phone, "כן", "a1_yes")
        components = denidin_app.agreements_manager.get_agreement(agreement_id)["components"]
        assert len(components) == 3
        added = next(c for c in components if c["label"] not in ("ריטיינר", "שכר טרחה באחוזים"))
        assert added["amount"] == 1500
        assert added["trigger_condition"], "the per-hearing condition must be stored as the trigger"
        assert added["status"] == "Pending"
        assert added["vat_status"] and "לא" not in added["vat_status"], "the stated VAT (included) must be stored"

    def test_uat_5_5a_complete_single_component(self, denidin_app, config):
        phone, chat = self._godfather(config)
        agreement = self._seed(denidin_app)
        agreement_id = agreement["agreement_id"]

        self._say(chat, phone, f"{CLIENT} שילם את הריטיינר של הערעור", "c1")
        assert self._component(denidin_app, agreement_id, "ריטיינר")["status"] == "Active", "wrote before approval"

        self._say(chat, phone, "כן", "c1_yes")
        assert self._component(denidin_app, agreement_id, "ריטיינר")["status"] == "Completed"
        assert self._component(denidin_app, agreement_id, "שכר טרחה באחוזים")["status"] == "Active"
        assert denidin_app.agreements_manager.get_agreement(agreement_id)["status"] == "Active"

    def test_uat_5_5b_complete_whole_agreement_cascades(self, denidin_app, config):
        phone, chat = self._godfather(config)
        agreement = self._seed(denidin_app, components=[
            {"label": "ריטיינר", "amount": 5000},
            {"label": "שכר הצלחה", "percent": 20, "trigger_condition": "אם נזכה בתיק"},
        ])
        agreement_id = agreement["agreement_id"]
        events_before = len(self._agreement_events(config, agreement_id))

        self._say(chat, phone, f"תסגור את הסכם הערעור של {CLIENT}, התיק הסתיים לגמרי", "k1")
        assert denidin_app.agreements_manager.get_agreement(agreement_id)["status"] == "Active", "wrote before approval"

        reply = self._say(chat, phone, "כן", "k1_yes")
        after = denidin_app.agreements_manager.get_agreement(agreement_id)
        assert after["status"] == "Completed"
        assert {c["label"]: c["status"] for c in after["components"]} == {"ריטיינר": "Completed", "שכר הצלחה": "Cancelled"}
        assert len(self._agreement_events(config, agreement_id)) == events_before + 2
        assert reply and "בוטל" in reply, f"the reply must mention the Pending component being cancelled: {reply!r}"

    def test_uat_5_6_ambiguous_short_reply_changes_nothing(self, denidin_app, config):
        phone, chat = self._godfather(config)
        agreement = self._seed(denidin_app)
        agreement_id = agreement["agreement_id"]
        state_before = denidin_app.agreements_manager.get_agreement(agreement_id)
        reminders_before = len(denidin_app.reminder_manager.list_active())

        reply = self._say(chat, phone, "כן", "s1")
        assert reply, "an ambiguous reply must be answered (a clarifying question), not ignored"
        assert denidin_app.agreements_manager.get_agreement(agreement_id) == state_before
        assert len(denidin_app.reminder_manager.list_active()) == reminders_before
