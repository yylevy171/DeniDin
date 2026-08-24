"""
End-to-End Billed Test: Ledger Event Querying via AI (Feature 044, tasks.md T008-T011/
T013/T014)

Tests the real OpenAI function-calling mechanism end-to-end for `query_ledger_events` -
NOT unit/integration-testable, since what's under test is whether the real model (a)
decides to call the tool at all from a natural Hebrew question, (b) extracts correct
arguments (a name, a date range, an amount range) from conversational phrasing, (c)
composes MULTIPLE calls unprompted for a multi-criterion question (research.md Decision
10), and (d) reasons correctly over the raw returned events in its own reply (sums,
exclusions, disambiguation). Every one of these is real model judgment - a stubbed
response (see tests/integration/test_ledger_query_conversation_routing.py) can prove
"if the model calls it this way, everything downstream works," never "the model actually
decides to call it this way." All billed (cheap, text-only), none expensive.

**Data seeding vs. the test itself** (user directive, 2026-08-23): every scenario's
ledger data is seeded directly via `LedgerEventManager.add_ledger_event` - real internal
code, never a simulated capture conversation just to get data in place. Apart from that
seeding step, the OpenAI client is NEVER mocked/stubbed anywhere in this file - every
model call is real, same as every other file in tests/billed/.

**Seeding convention** (user directive, 2026-08-23): every scenario seeds MORE than the
minimum needed - real distractor/noise events (other clients, other dates/months, other
amounts) alongside the actual target data, never a suspiciously minimal dataset
containing only what the question needs. Closer to a real ledger's shape, and a
materially stronger proof: the difference between "the model can find the answer when
it's the only thing there" and "the model can find the answer among noise."

**Dates are relative to whenever this file actually runs** (`now_local()`-anchored "this
month"/"last month" helpers below), never a hardcoded calendar month - a test file that
only works correctly in August 2026 would silently go stale the first time it's rerun
later. Prompts use "החודש"/"החודש שעבר" (this month/last month) rather than a specific
month name for the same reason.

NO MOCKING beyond data seeding - real OpenAI API calls, real ledger storage.
"""
import calendar
import logging
import uuid
from pathlib import Path

import pytest

from src.models.config import AppConfiguration
from src.utils.time_utils import now_local

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

GODFATHER_CHAT_ID_TEMPLATE = "{phone}@c.us"


def _this_month_timestamp(day=5, hour=9):
    """Real Unix epoch for a given day/hour in the CURRENT local month - never a
    hardcoded calendar month, so this file doesn't go stale whenever it's re-run."""
    now = now_local()
    last_day = calendar.monthrange(now.year, now.month)[1]
    dt = now.replace(day=min(day, last_day), hour=hour, minute=0, second=0, microsecond=0)
    return int(dt.timestamp())


def _last_month_timestamp(day=5, hour=9):
    """Same as _this_month_timestamp, one calendar month back - for negative-control
    events that must NOT match a "this month" query."""
    now = now_local()
    year, month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
    last_day = calendar.monthrange(year, month)[1]
    dt = now.replace(year=year, month=month, day=min(day, last_day), hour=hour, minute=0, second=0, microsecond=0)
    return int(dt.timestamp())


def _this_month_date_str(day=5):
    """ISO YYYY-MM-DD for a given day in the CURRENT local month - for txn_date,
    which needs a date string, never an epoch int."""
    now = now_local()
    last_day = calendar.monthrange(now.year, now.month)[1]
    return now.replace(day=min(day, last_day)).strftime("%Y-%m-%d")


def _last_month_date_str(day=5):
    """Same as _this_month_date_str, one calendar month back."""
    now = now_local()
    year, month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
    last_day = calendar.monthrange(year, month)[1]
    return now.replace(year=year, month=month, day=min(day, last_day)).strftime("%Y-%m-%d")


def _amount_variants(amount: int):
    """The common ways a real reply might format an amount - checked as
    "any of these substrings appears", never an exact-string match (real model
    phrasing varies: with/without a thousands comma, with/without a currency
    symbol/word)."""
    return {str(amount), f"{amount:,}"}


def _reply_contains_amount(reply: str, amount: int) -> bool:
    return any(variant in reply for variant in _amount_variants(amount))


@pytest.mark.billed
class TestLedgerQueryBilled:
    """Given/When/Then E2E coverage for query_ledger_events across explicit and
    implicit natural-language ledger questions."""

    @pytest.fixture
    def config(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
        if not config_path.exists():
            pytest.skip("config.test.json not found")
        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        test_data_root = Path(__file__).parent.parent.parent / "test_data"
        config.data_root = str(test_data_root)
        config.memory['session']['storage_dir'] = str(test_data_root / "sessions")
        config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")
        return config

    @pytest.fixture
    def denidin_app(self, config):
        import denidin

        if denidin.denidin_app is None:
            config_dict = {
                'green_api_instance_id': config.green_api_instance_id,
                'green_api_token': config.green_api_token,
                'ai_api_key': config.ai_api_key,
                'ai_model': config.ai_model,
                'ai_vision_model': config.ai_vision_model,
                'ai_embedding_model': config.ai_embedding_model,
                'ai_reply_max_tokens': config.ai_reply_max_tokens,
                'log_level': config.log_level,
                'data_root': config.data_root,
                'feature_flags': config.feature_flags,
                'godfather_phone': config.godfather_phone,
                'memory': config.memory,
                'constitution_config': config.constitution_config,
                'user_roles': config.user_roles,
                'mcp': config.mcp,
            }
            denidin.denidin_app = denidin.initialize_app(config_dict)

        # Safety guard (mirrors test_ledger_event_capture_billed.py's precedent):
        # LedgerEventManager.storage_dir MUST resolve under this test's isolated
        # data_root, never real production/dev data.
        actual_events_dir = Path(denidin.denidin_app.ai_handler.ledger_event_manager.storage_dir).resolve()
        expected_root = Path(config.data_root).resolve()
        assert actual_events_dir.is_relative_to(expected_root), (
            f"LedgerEventManager.storage_dir={actual_events_dir} is NOT under this "
            f"test's isolated data_root={expected_root} - refusing to proceed"
        )
        return denidin.denidin_app

    def _godfather(self, config):
        phone = config.godfather_phone
        return phone, GODFATHER_CHAT_ID_TEMPLATE.format(phone=phone)

    @staticmethod
    def _create_notification(chat_id, sender, sender_name, text, msg_id):
        from whatsapp_chatbot_python import Notification

        notification = Notification.__new__(Notification)
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'idMessage': msg_id,
            'timestamp': int(now_local().timestamp()),
            'senderData': {'chatId': chat_id, 'sender': sender, 'senderName': sender_name},
            'messageData': {'typeMessage': 'textMessage', 'textMessageData': {'textMessage': text}},
        }
        notification._test_sent_messages = []

        def track_answer(message):
            notification._test_sent_messages.append(message)
            logger.info(f"Would send to user: {message}")

        notification.answer = track_answer
        return notification

    @staticmethod
    def _get_response(notification):
        return notification._test_sent_messages[0] if notification._test_sent_messages else None

    def _send_text(self, chat_id, sender, sender_name, text, label):
        from denidin import handle_text_message
        msg_id = f"billed_lq_{label}_{uuid.uuid4().hex[:8]}"
        notification = self._create_notification(chat_id, sender, sender_name, text, msg_id)
        handle_text_message(notification)
        return notification

    @staticmethod
    def _fresh_chat_id(config, label: str) -> str:
        """A unique-per-test chat_id (godfather's own phone, distinguished only
        by session isolation via a fresh session - mirrors
        test_ledger_event_capture_billed.py's precedent, adapted since our
        RBAC-gated tool needs the REAL godfather phone, not an arbitrary one).
        Reusing the same phone number across tests is fine since each test's
        session is independent (a fresh chat_id string still resolves to the
        same godfather ROLE, which is all RBAC cares about)."""
        return f"{config.godfather_phone}_{label}_{uuid.uuid4().hex[:6]}@c.us"

    def _seed(self, denidin_app, client_name, *, payer_name=None, source_type="הסכם",
              event_subtype="יצירה", amount="10₪", hours=None, txn_date=None,
              message_id="seed", timestamp=None):
        return denidin_app.ai_handler.ledger_event_manager.add_ledger_event(
            session_id="s", event={
                "source_type": source_type, "event_subtype": event_subtype,
                "client_name": client_name, "payer_name": payer_name,
                "description": "תיאור", "amount": amount,
                "percent": None, "percent_base": None, "hours": hours,
                "hourly_rate": None, "txn_date": txn_date,
                "vat_status": "כולל" if source_type == "בנק" else "לא צוין",
                "trigger_condition": None, "reference_hint": None,
                "agreement_label": "תיק" if source_type == "הסכם" else None,
                "component_label": "בסיס" if source_type == "הסכם" else None,
            },
            message_id=message_id, message_timestamp=timestamp or _this_month_timestamp(),
        )

    def _seed_noise(self, denidin_app, count=5, label="noise"):
        """Distractor events for a scenario's OWN test to seed alongside its
        real target data - other clients, other months, other amounts. Never
        asserted on directly; just makes the dataset non-trivially small."""
        noise_names = [
            "רותם שגיא", "עידן ברק", "ליאור אשד", "טל ורדי", "אורית כרמי",
            "אלה שני", "גיא רימון", "נעם דגן",
        ]
        for i in range(count):
            self._seed(
                denidin_app, noise_names[i % len(noise_names)],
                amount=f"{20 + i * 10}₪",
                message_id=f"{label}_{i}",
                timestamp=_last_month_timestamp(day=(i % 27) + 1),
            )

    # ------------------------------------------------------------------
    # T008 - core lookups
    # ------------------------------------------------------------------

    def test_explicit_amount_lookup(self, denidin_app, config):
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't008_amount')
        self._seed_noise(denidin_app, count=6, label="t008_amount_noise")
        self._seed(denidin_app, "תומר אלוני", amount="45₪", message_id="t008_amount_target")

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather", "כמה סוכם עם תומר אלוני?", "t008_amount",
        ))
        assert reply is not None
        assert _reply_contains_amount(reply, 45), f"expected 45 in reply: {reply!r}"

    def test_explicit_date_lookup(self, denidin_app, config):
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't008_date')
        self._seed_noise(denidin_app, count=6, label="t008_date_noise")
        target_ts = _this_month_timestamp(day=17, hour=10)
        self._seed(
            denidin_app, "נועה שדה", amount="42₪",
            message_id="t008_date_target", timestamp=target_ts,
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather", "מתי נועה שדה התחילה את ההסכם?", "t008_date",
        ))
        assert reply is not None
        assert "17" in reply, f"expected the 17th to appear in the date reply: {reply!r}"

    def test_no_match_never_fabricates(self, denidin_app, config):
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't008_nomatch')
        self._seed_noise(denidin_app, count=6, label="t008_nomatch_noise")

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather", "כמה סוכם עם אביגיל טרבלסי?", "t008_nomatch",
        ))
        assert reply is not None
        no_finding_markers = ("לא נמצא", "אין מידע", "לא מצאתי", "אין רישום", "לא קיים", "לא מוכר")
        assert any(marker in reply for marker in no_finding_markers), (
            f"expected a plain 'nothing found' reply, got: {reply!r}"
        )

    def test_payer_name_search(self, denidin_app, config):
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't008_payer')
        self._seed_noise(denidin_app, count=6, label="t008_payer_noise")
        self._seed(
            denidin_app, "דניאל פרץ", payer_name="מגדל", amount="38₪",
            message_id="t008_payer_target",
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather", "האם קיבלנו תשלום ממגדל?", "t008_payer",
        ))
        assert reply is not None
        assert _reply_contains_amount(reply, 38), f"expected 38 in reply: {reply!r}"

    # ------------------------------------------------------------------
    # T009 - ambiguity + "both/all" follow-up
    # ------------------------------------------------------------------

    def test_ambiguous_name_asks_then_both_confirmed_merges(self, denidin_app, config):
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't009_both')
        self._seed_noise(denidin_app, count=6, label="t009_noise")
        self._seed(denidin_app, "דוד כהן", amount="15₪", message_id="t009_a")
        self._seed(denidin_app, "דוד לוי", amount="27₪", message_id="t009_b")

        first = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather", "כמה סוכם עם דוד?", "t009_ambiguous",
        ))
        assert first is not None
        assert "?" in first, f"expected a clarifying question, got: {first!r}"
        assert "דוד כהן" in first and "דוד לוי" in first, (
            f"expected both candidate names listed, got: {first!r}"
        )

        both = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather", "גם וגם", "t009_both",
        ))
        assert both is not None
        assert _reply_contains_amount(both, 15) and _reply_contains_amount(both, 27), (
            f"expected BOTH amounts reflected after confirming both, got: {both!r}"
        )

    # ------------------------------------------------------------------
    # T010 - aggregation
    # ------------------------------------------------------------------

    def test_hours_by_client_this_month(self, denidin_app, config):
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't010_hours_client')
        self._seed_noise(denidin_app, count=6, label="t010_hours_client_noise")
        self._seed(
            denidin_app, "מיכל רוזן", amount=None, hours="3",
            txn_date=_this_month_date_str(day=3),
            message_id="t010_hc_1", timestamp=_this_month_timestamp(day=3),
        )
        self._seed(
            denidin_app, "מיכל רוזן", amount=None, hours="4",
            txn_date=_this_month_date_str(day=10),
            message_id="t010_hc_2", timestamp=_this_month_timestamp(day=10),
        )
        # Negative control - same client, LAST month, must not be included.
        self._seed(
            denidin_app, "מיכל רוזן", amount=None, hours="99",
            txn_date=_last_month_date_str(day=5),
            message_id="t010_hc_decoy", timestamp=_last_month_timestamp(day=5),
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather",
            "כמה שעות אני צריך לחייב את מיכל רוזן החודש?", "t010_hours_client",
        ))
        assert reply is not None
        assert "7" in reply, f"expected the correct sum (3+4=7) in reply: {reply!r}"
        assert "99" not in reply, f"last month's decoy hours leaked into the reply: {reply!r}"

    def test_hours_by_payer_this_month(self, denidin_app, config):
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't010_hours_payer')
        self._seed_noise(denidin_app, count=6, label="t010_hours_payer_noise")
        self._seed(
            denidin_app, "בני אשכנזי", payer_name="מגדל", amount=None, hours="2",
            txn_date=_this_month_date_str(day=6),
            message_id="t010_hp_1", timestamp=_this_month_timestamp(day=6),
        )
        self._seed(
            denidin_app, "בני אשכנזי", payer_name="מגדל", amount=None, hours="5",
            txn_date=_this_month_date_str(day=12),
            message_id="t010_hp_2", timestamp=_this_month_timestamp(day=12),
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather",
            "כמה שעות אני צריך לחייב עבור מגדל החודש?", "t010_hours_payer",
        ))
        assert reply is not None
        assert "7" in reply, f"expected the correct sum (2+5=7) in reply: {reply!r}"

    def test_monthly_income_aggregation(self, denidin_app, config):
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't010_income')
        self._seed_noise(denidin_app, count=6, label="t010_income_noise")
        self._seed(
            denidin_app, "דנה פלד", source_type="בנק", event_subtype="הפקדה",
            amount="40₪", message_id="t010_income_1", timestamp=_this_month_timestamp(day=4),
        )
        self._seed(
            denidin_app, "אלון שני", source_type="בנק", event_subtype="הפקדה",
            amount="22₪", message_id="t010_income_2", timestamp=_this_month_timestamp(day=14),
        )
        # Negative control - agreed but NOT paid, same month - must be excluded from "income".
        self._seed(
            denidin_app, "אלעד ברק", amount="80₪",
            message_id="t010_income_decoy", timestamp=_this_month_timestamp(day=20),
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather", "כמה הכנסות היו לי החודש?", "t010_income",
        ))
        assert reply is not None
        assert _reply_contains_amount(reply, 62), (
            f"expected the deposit-only sum (40+22=62) in reply: {reply!r}"
        )
        assert "80" not in reply, (
            f"the agreed-but-unpaid decoy amount leaked into the income reply: {reply!r}"
        )

    # ------------------------------------------------------------------
    # T011 - four-way multi-criterion, name + date combined
    # ------------------------------------------------------------------

    def test_four_way_multi_criterion_with_date_range(self, denidin_app, config):
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't011_four_way')
        self._seed_noise(denidin_app, count=6, label="t011_noise")
        clients = [
            ("שירה מזרחי", 20, 2), ("אבי גולן", 33, 9),
            ("טליה נבון", 47, 16), ("רועי הראל", 61, 23),
        ]
        for name, amount, day in clients:
            self._seed(
                denidin_app, name, amount=f"{amount}₪",
                message_id=f"t011_{name}", timestamp=_this_month_timestamp(day=day),
            )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather",
            "מה סוכם החודש עם שירה מזרחי, אבי גולן, טליה נבון או רועי הראל?", "t011_four_way",
        ))
        assert reply is not None
        for name, amount, _day in clients:
            assert _reply_contains_amount(reply, amount), (
                f"expected {name}'s amount ({amount}) reflected in reply: {reply!r}"
            )

    # ------------------------------------------------------------------
    # T013 - 20-item display cap
    # ------------------------------------------------------------------

    def test_twenty_item_display_cap(self, denidin_app, config):
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't013_cap')
        distinct_names = [f"לקוח מספר {i:02d}" for i in range(25)]
        for i, name in enumerate(distinct_names):
            self._seed(
                denidin_app, name, amount=f"{10 + i}₪",
                message_id=f"t013_{i}", timestamp=_this_month_timestamp(day=(i % 27) + 1),
            )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather", "מה כל האירועים מהחודש האחרון?", "t013_cap",
        ))
        assert reply is not None
        named_count = sum(1 for name in distinct_names if name in reply)
        assert named_count <= 20, (
            f"reply enumerated {named_count} individual events verbatim (>20) - "
            f"should summarize/group/ask to narrow instead: {reply!r}"
        )

    # ------------------------------------------------------------------
    # T014 - natural-language exclusion (a fact the user states, not in the ledger)
    # ------------------------------------------------------------------

    def test_natural_language_exclusion(self, denidin_app, config):
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't014_exclusion')
        self._seed_noise(denidin_app, count=6, label="t014_noise")
        # Yossi's agreement has NO corresponding payment event on file - matches
        # the user's own example ("except Yossi who I know already paid").
        self._seed(
            denidin_app, "יוסי ברנע", amount="55₪",
            message_id="t014_yossi", timestamp=_this_month_timestamp(day=8),
        )
        self._seed(
            denidin_app, "קרן אביטל", amount="33₪",
            message_id="t014_other", timestamp=_this_month_timestamp(day=15),
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather",
            "כמה כסף חייבים לי עדיין החודש חוץ מיוסי ברנע שאני יודע ששילם כבר?",
            "t014_exclusion",
        ))
        assert reply is not None
        assert _reply_contains_amount(reply, 33), (
            f"expected the correctly-excluded total (33, Yossi's 55 excluded) "
            f"in reply: {reply!r}"
        )
