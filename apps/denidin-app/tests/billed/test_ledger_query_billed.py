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
import json
import logging
import uuid
from datetime import datetime
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
              percent=None, message_id="seed", timestamp=None,
              description="תיאור", reference_hint=None, trigger_condition=None,
              component_label="בסיס"):
        return denidin_app.ai_handler.ledger_event_manager.add_ledger_event(
            session_id="s", event={
                "source_type": source_type, "event_subtype": event_subtype,
                "client_name": client_name, "payer_name": payer_name,
                "description": description, "amount": amount,
                # percent is stored verbatim (no _normalize_amount-style parsing,
                # unlike amount) - pass a plain number STRING, no "%" sign, so
                # it stays numeric-matchable (_try_parse_number) for anything
                # that needs to read it back as a real number (T018).
                "percent": percent, "percent_base": None, "hours": hours,
                "hourly_rate": None, "txn_date": txn_date,
                "vat_status": "כולל" if source_type == "בנק" else "לא צוין",
                "reference_hint": reference_hint,
                "trigger_condition": trigger_condition,
                "agreement_label": "תיק" if source_type == "הסכם" else None,
                "component_label": component_label if source_type == "הסכם" else None,
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

    def _seed_accounting_document(
        self, denidin_app, client_name, *, doc_type, type_name, amount,
        status="unpaid", status_code=0, status_label="פתוח",
        description="שירותים", display_number=None,
        linked_document=None, timestamp=None,
    ):
        """Seeds a source_type=חשבונית ledger event via the REAL
        _expand_accounting_document_json code path (a fake but structurally
        real Morning document JSON blob, exactly as the reconciliation sweep
        would receive it) - never hand-populates the derived
        accounting_document_*/event_datetime fields directly, same discipline
        as test_ledger_event_manager.py's own _accounting_event/_json_event
        helpers. status="unpaid"/"paid" maps via LedgerEventManager's own
        _STATUS_HE to "לא שולם"/"שולם".

        doc_type/type_name pairs used by this file's new owed/received tests:
        (300, "חשבון עסקה"), (305, "חשבונית מס"), (320, "חשבונית מס/קבלה"),
        (400, "קבלה"), (330, "חשבונית זיכוי").
        """
        ts = timestamp or _this_month_timestamp()
        display_number = display_number or f"D{uuid.uuid4().hex[:8]}"
        creation_iso = datetime.fromtimestamp(ts, tz=now_local().tzinfo).isoformat()
        doc = {
            "display_number": display_number,
            "internal_morning_id": str(uuid.uuid4()),
            "type": doc_type, "type_name": type_name,
            "status": status, "status_code": status_code, "status_label": status_label,
            "client_name": client_name, "description": description,
            "amount": amount, "amount_excl_vat": amount, "vat_amount": 0, "vat_rate": 0,
            "currency": "ILS",
            "document_date": _this_month_date_str(),
            "due_date": None,
            "creation_date": creation_iso,
            "payment": None,
            "linked_document": linked_document,
        }
        return denidin_app.ai_handler.ledger_event_manager.add_ledger_event(
            session_id="accounting-reconciliation",
            event={
                "source_type": "חשבונית", "event_subtype": "הפקה",
                "accounting_document_json": json.dumps(doc, ensure_ascii=False),
            },
            message_id=None, message_timestamp=ts,
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
            chat_id, phone, "Test Godfather", "כמה חייבים לנו ממגדל?", "t008_payer",
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

    # T013 (20-item display cap) removed 2026-08-26 (user directive): the
    # constitution no longer specifies a fixed numeric cap on how many events
    # a reply may enumerate - it now just directs the model to keep replies
    # readable for a WhatsApp conversation, using its own judgment. The real,
    # strictly-enforced limit is the reply's own output-token budget, which
    # this test can't meaningfully probe by seeding a specific event count.

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

    # ------------------------------------------------------------------
    # T017-T020 (2026-08-24 query-engine redesign addendum) - OR, NOT +
    # numeric threshold, broad-category + threshold, and cross-category
    # retrieval - scenarios the OLD 8-structured-filter design could not
    # have answered correctly even if these tests had existed sooner. See
    # research.md's "2026-08-24 Redesign" section for the full trail.
    # ------------------------------------------------------------------

    def test_or_across_two_identities_single_turn(self, denidin_app, config):
        """T017: explicit OR across two distinct, unambiguous identities named
        up front in ONE request (distinct from T009's ambiguity-then-"both/
        all" two-turn flow - no ambiguity here at all, just a direct OR)."""
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't017_or')
        self._seed_noise(denidin_app, count=6, label="t017_noise")
        self._seed(
            denidin_app, "אלי אבירם", source_type="בנק", event_subtype="הפקדה",
            amount="100₪", message_id="t017_a", timestamp=_this_month_timestamp(day=6),
        )
        self._seed(
            denidin_app, "דוד כרמון", source_type="בנק", event_subtype="הפקדה",
            amount="100₪", message_id="t017_b", timestamp=_this_month_timestamp(day=12),
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather",
            "האם קיבלנו תשלום של 100 שקל מאלי אבירם או מדוד כרמון?", "t017_or",
        ))
        assert reply is not None
        assert "אלי אבירם" in reply and "דוד כרמון" in reply, (
            f"expected BOTH names' payments reflected in reply, not just one: {reply!r}"
        )

    def test_exclusion_with_percent_threshold(self, denidin_app, config):
        """T018: NOT/exclusion combined with a numeric threshold, over a field
        never exercised by any earlier scenario (percent). Real exclusion
        reasoning, not just threshold filtering: קרן שלו's own agreement IS
        genuinely above 50%, so a correct reply must actively exclude her by
        name, not merely apply the threshold."""
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't018_percent')
        self._seed_noise(denidin_app, count=6, label="t018_noise")
        self._seed(
            denidin_app, "קרן שלו", amount=None, percent="60",
            message_id="t018_keren", timestamp=_this_month_timestamp(day=4),
        )
        self._seed(
            denidin_app, "אורי ששון", amount=None, percent="70",
            message_id="t018_ori", timestamp=_this_month_timestamp(day=9),
        )
        self._seed(
            denidin_app, "מאיה זיו", amount=None, percent="55",
            message_id="t018_maya", timestamp=_this_month_timestamp(day=15),
        )
        # Negative control - below the 50% threshold, must be excluded
        # regardless of the "except קרן שלו" clause.
        self._seed(
            denidin_app, "רן אלפסי", amount=None, percent="45",
            message_id="t018_ran", timestamp=_this_month_timestamp(day=20),
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather",
            "מי, חוץ מקרן שלו, הסכים על אחוזים מעל 50%?", "t018_percent",
        ))
        assert reply is not None
        assert "אורי ששון" in reply and "מאיה זיו" in reply, (
            f"expected the other above-50% clients named in reply: {reply!r}"
        )
        assert "רן אלפסי" not in reply, (
            f"the below-threshold negative control leaked into the reply: {reply!r}"
        )

    def test_broad_threshold_who_owes_above_amount(self, denidin_app, config):
        """T019: the original "who owes above 100 shekel" example from the
        redesign discussion - broad-category retrieval (no name given at
        all) plus numeric-threshold reasoning, with a real already-paid
        control (above-threshold but NOT still owed) alongside real
        at-or-below-threshold negative controls."""
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't019_owed')
        self._seed_noise(denidin_app, count=6, label="t019_noise")
        # Above threshold, genuinely still owed (no payment on file):
        self._seed(
            denidin_app, "תמר כרמי", amount="150₪",
            message_id="t019_tamar", timestamp=_this_month_timestamp(day=3),
        )
        self._seed(
            denidin_app, "עומר לביא", amount="220₪",
            message_id="t019_omer", timestamp=_this_month_timestamp(day=8),
        )
        # Above threshold but ALREADY PAID (a separate בנק/הפקדה event, same
        # period) - must be excluded from "still owed," not just "agreed
        # above 100."
        self._seed(
            denidin_app, "שני אור", amount="180₪",
            message_id="t019_shani_agreement", timestamp=_this_month_timestamp(day=5),
        )
        self._seed(
            denidin_app, "שני אור", source_type="בנק", event_subtype="הפקדה",
            amount="180₪", message_id="t019_shani_payment",
            timestamp=_this_month_timestamp(day=11),
        )
        # At-or-below threshold, real negative controls (absence, not just
        # silence, is the point):
        self._seed(
            denidin_app, "בר אילן", amount="90₪",
            message_id="t019_bar", timestamp=_this_month_timestamp(day=14),
        )
        self._seed(
            denidin_app, "יובל שדה", amount="100₪",
            message_id="t019_yuval", timestamp=_this_month_timestamp(day=17),
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather",
            "מי כל הלקוחות שחייבים לי מעל 100 שקל?", "t019_owed",
        ))
        assert reply is not None
        assert "תמר כרמי" in reply and "עומר לביא" in reply, (
            f"expected both genuinely-still-owed above-threshold clients in reply: {reply!r}"
        )
        # 2026-08-26 (user correction): שני אור being NAMED in the reply is fine -
        # the model is allowed to (and often should) explain a close call rather
        # than stay silent about it. What must never happen is her being LISTED
        # as owing (the same "- name — amount" bullet shape used for the two
        # genuinely-owed clients above) - a paid-off agreement must not be
        # counted, whether or not it's mentioned.
        assert "- שני אור —" not in reply and "- שני אור-" not in reply, (
            f"שני אור already paid and must not be LISTED as still owed (mentioning "
            f"her to explain why she's excluded is fine): {reply!r}"
        )
        assert "בר אילן" not in reply and "יובל שדה" not in reply, (
            f"at-or-below-threshold clients leaked into the reply: {reply!r}"
        )

    def test_cross_category_two_figures_for_one_identity(self, denidin_app, config):
        """T020: cross-category retrieval for ONE identity in a single turn -
        two DIFFERENT facts from two different event categories (agreed vs.
        paid-to-date), reported side by side. Distinct from T010's owed-
        balance scenario (which needs a computed subtraction) - this only
        needs both raw numbers stated correctly, without conflating them."""
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't020_two_figures')
        self._seed_noise(denidin_app, count=6, label="t020_noise")
        self._seed(
            denidin_app, "משה כהן", amount="45₪",
            message_id="t020_agreed", timestamp=_this_month_timestamp(day=4),
        )
        self._seed(
            denidin_app, "משה כהן", source_type="בנק", event_subtype="הפקדה",
            amount="20₪", message_id="t020_paid", timestamp=_this_month_timestamp(day=12),
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather",
            "כמה משה כהן הסכים לשלם, וכמה הוא שילם עד היום?", "t020_two_figures",
        ))
        assert reply is not None
        assert _reply_contains_amount(reply, 45), (
            f"expected the agreed amount (45) in reply: {reply!r}"
        )
        assert _reply_contains_amount(reply, 20), (
            f"expected the paid-so-far amount (20) in reply: {reply!r}"
        )

    # ------------------------------------------------------------------
    # T021-T026 (2026-08-26 addendum) - "What counts as owed vs. received"
    # (runtime_constitution.md), covering every event type/kind the user
    # specified: הסכם (created + modified), חשבון עסקה (300), חשבונית מס
    # (305), בנק/הפקדה, קבלה/type-320-400 receipts, חשבונית זיכוי (330
    # credit note), plus a genuine same-turn multi-round search. Each uses
    # a real bought-and-paid-for SUM proof (like T014's exclusion test)
    # rather than asserting on the ABSENCE of a name/number, since a correct
    # model may legitimately narrate the paid-off/cancelled events too.
    # ------------------------------------------------------------------

    def test_owed_via_transaction_account_no_agreement_at_all(self, denidin_app, config):
        """T021: a pure Morning-sourced owed signal - a type-300 חשבון עסקה
        with no corresponding הסכם ledger event whatsoever. Proves the owed
        model recognizes Morning-only debt, not just fee-agreement debt."""
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't021_txn_account')
        self._seed_noise(denidin_app, count=6, label="t021_noise")
        self._seed_accounting_document(
            denidin_app, "לירז אבני", doc_type=300, type_name="חשבון עסקה",
            amount=250, status="unpaid", status_code=0, status_label="פתוח",
            timestamp=_this_month_timestamp(day=6),
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather", "כמה לירז אבני חייבת לי?", "t021_txn_account",
        ))
        assert reply is not None
        assert _reply_contains_amount(reply, 250), (
            f"expected the open transaction-account amount (250) in reply: {reply!r}"
        )

    def test_tax_invoice_closed_by_receipt_excluded_from_owed_sum(self, denidin_app, config):
        """T022: a type-305 חשבונית מס fully closed by a matching type-400
        קבלה must be excluded from an owed total, proven via a two-client SUM
        (the only way the total comes out right is if the paid-off client's
        amount was correctly netted to zero, not just narrated)."""
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't022_closed_invoice')
        self._seed_noise(denidin_app, count=6, label="t022_noise")
        self._seed_accounting_document(
            denidin_app, "בועז נחמיאס", doc_type=305, type_name="חשבונית מס",
            amount=400, status="unpaid", status_code=0, status_label="פתוח",
            display_number="D022A", timestamp=_this_month_timestamp(day=3),
        )
        self._seed_accounting_document(
            denidin_app, "בועז נחמיאס", doc_type=400, type_name="קבלה",
            amount=400, status="paid", status_code=1, status_label="מסמך סגור",
            linked_document={"type_name": "חשבונית מס", "number": "D022A"},
            timestamp=_this_month_timestamp(day=10),
        )
        self._seed_accounting_document(
            denidin_app, "שירה בכר", doc_type=305, type_name="חשבונית מס",
            amount=150, status="unpaid", status_code=0, status_label="פתוח",
            timestamp=_this_month_timestamp(day=14),
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather",
            "כמה כסף חייבים לי בסך הכל מבועז נחמיאס ומשירה בכר?", "t022_closed_invoice",
        ))
        assert reply is not None
        assert _reply_contains_amount(reply, 150), (
            f"expected the correct total (150, בועז's 400 fully paid and excluded) "
            f"in reply: {reply!r}"
        )

    def test_credit_note_reverses_a_receipt_so_invoice_stays_owed(self, denidin_app, config):
        """T023: a type-330 חשבונית זיכוי issued against a type-400 קבלה
        reverses that receipt - the underlying invoice must STILL count as
        owed, not be wrongly netted to zero. Proven via the same two-client
        SUM technique as T022 (correct total = 420 only if מאיה's invoice is
        still counted despite having a receipt on file)."""
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't023_credit_note')
        self._seed_noise(denidin_app, count=6, label="t023_noise")
        self._seed_accounting_document(
            denidin_app, "מאיה פלד", doc_type=305, type_name="חשבונית מס",
            amount=300, status="unpaid", status_code=0, status_label="פתוח",
            display_number="D023A", timestamp=_this_month_timestamp(day=2),
        )
        self._seed_accounting_document(
            denidin_app, "מאיה פלד", doc_type=400, type_name="קבלה",
            amount=300, status="paid", status_code=1, status_label="מסמך סגור",
            display_number="D023A_R",
            linked_document={"type_name": "חשבונית מס", "number": "D023A"},
            timestamp=_this_month_timestamp(day=6),
        )
        self._seed_accounting_document(
            denidin_app, "מאיה פלד", doc_type=330, type_name="חשבונית זיכוי",
            amount=300, status="paid", status_code=1, status_label="מסמך סגור",
            description="ביטול קבלה שהופקה בטעות",
            linked_document={"type_name": "קבלה", "number": "D023A_R"},
            timestamp=_this_month_timestamp(day=9),
        )
        self._seed_accounting_document(
            denidin_app, "רועי אבן", doc_type=305, type_name="חשבונית מס",
            amount=120, status="unpaid", status_code=0, status_label="פתוח",
            timestamp=_this_month_timestamp(day=17),
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather",
            "כמה כסף חייבים לי בסך הכל ממאיה פלד ומרועי אבן?", "t023_credit_note",
        ))
        assert reply is not None
        assert _reply_contains_amount(reply, 420), (
            f"expected the correct total (420 = 300 + 120 - מאיה's receipt was "
            f"reversed by the credit note, so her invoice is STILL owed) in "
            f"reply: {reply!r}"
        )

    def test_agreement_modification_reports_the_latest_state(self, denidin_app, config):
        """T024: a client with TWO הסכם events over time (a fee increase) -
        'what was eventually agreed' must reflect the LATEST state (350),
        never the original (200) alone or the naive sum (550)."""
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't024_modified_agreement')
        self._seed_noise(denidin_app, count=6, label="t024_noise")
        self._seed(
            denidin_app, "שלומית ברגר", amount="200₪",
            message_id="t024_original", timestamp=_this_month_timestamp(day=3),
        )
        self._seed(
            denidin_app, "שלומית ברגר", amount="350₪",
            message_id="t024_updated", timestamp=_this_month_timestamp(day=20),
            reference_hint="מעדכן את ההסכם הקודם - העלאת שכר טרחה ל-350",
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather",
            "כמה סוכם בסופו של דבר עם שלומית ברגר?", "t024_modified_agreement",
        ))
        assert reply is not None
        assert _reply_contains_amount(reply, 350), (
            f"expected the LATEST agreed amount (350) in reply: {reply!r}"
        )
        assert not _reply_contains_amount(reply, 550), (
            f"550 (200+350, the naive un-superseded sum) must not appear as the "
            f"final agreed figure: {reply!r}"
        )

    def test_total_paid_dedups_matching_deposit_and_receipt(self, denidin_app, config):
        """T025: 'total paid', not 'owed' - one payment shows up as BOTH a
        בנק/הפקדה event AND a separate matching קבלה (same client, same
        amount = the same real payment, per runtime_constitution.md) and
        must be counted ONCE; a second, genuinely different-amount deposit
        is a real additional payment and must be added. Correct total = 300
        (200 deduped once + 100), never 400 (200+200 double-counted) or 500
        (the agreed amount, not what's been paid)."""
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't025_total_paid')
        self._seed_noise(denidin_app, count=6, label="t025_noise")
        self._seed(
            denidin_app, "דנה עמית", amount="500₪",
            message_id="t025_agreement", timestamp=_this_month_timestamp(day=2),
        )
        self._seed(
            denidin_app, "דנה עמית", source_type="בנק", event_subtype="הפקדה",
            amount="200₪", message_id="t025_deposit",
            timestamp=_this_month_timestamp(day=9),
        )
        self._seed_accounting_document(
            denidin_app, "דנה עמית", doc_type=400, type_name="קבלה",
            amount=200, status="paid", status_code=1, status_label="מסמך סגור",
            timestamp=_this_month_timestamp(day=9),
        )
        self._seed(
            denidin_app, "דנה עמית", source_type="בנק", event_subtype="הפקדה",
            amount="100₪", message_id="t025_second_deposit",
            timestamp=_this_month_timestamp(day=21),
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather",
            "כמה דנה עמית שילמה עד היום בסך הכל?", "t025_total_paid",
        ))
        assert reply is not None
        assert _reply_contains_amount(reply, 300), (
            f"expected the correctly-deduped total paid (300 = 200 deduped once + "
            f"100) in reply: {reply!r}"
        )
        assert not _reply_contains_amount(reply, 400), (
            f"400 (200+200, double-counting the same payment's deposit AND "
            f"receipt) must not appear as the total paid: {reply!r}"
        )

    def test_combined_owed_across_two_clients_requires_multiple_search_rounds(
        self, denidin_app, config
    ):
        """T026: a genuine same-turn multi-round search, not just narration -
        two distinct, unrelated clients each with their own agreement; no
        single query_ledger_events call's fuzzy text can match both distinct
        names at once (unlike T011's four-way OR, this asks for one COMBINED
        number, proving the model actually retrieved and summed both rather
        than just listing names). Correct total = 300 (130 + 170)."""
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't026_multi_round')
        self._seed_noise(denidin_app, count=6, label="t026_noise")
        self._seed(
            denidin_app, "ג'ינג'י בלס", amount="130₪",
            message_id="t026_gingi", timestamp=_this_month_timestamp(day=5),
        )
        self._seed(
            denidin_app, "פאפי טריטי", amount="170₪",
            message_id="t026_pappy", timestamp=_this_month_timestamp(day=13),
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather",
            "כמה ג'ינג'י בלס ופאפי טריטי חייבים לי ביחד?", "t026_multi_round",
        ))
        assert reply is not None
        assert _reply_contains_amount(reply, 300), (
            f"expected the combined total (300 = 130 + 170, requiring a real search "
            f"round per client) in reply: {reply!r}"
        )

    # ------------------------------------------------------------------
    # T027-T029 (2026-08-26 addendum, user-specified rich edge cases)
    # ------------------------------------------------------------------

    def test_conditional_component_status_stays_uncertain_not_guessed(
        self, denidin_app, config
    ):
        """T027: a two-component agreement - component 1 (80, unconditional)
        and component 2 (100, conditional on an "ערעור"/appeal materializing,
        via trigger_condition). A matching bank deposit (80) AND a matching
        combo-320 receipt (80) - the SAME real payment (dedup rule) - closes
        component 1 exactly. Nothing in the ledger says whether the appeal
        happened, so component 2's status is genuinely UNKNOWN, not owed and
        not paid. A correct reply engages with that conditionality rather
        than confidently asserting a firm total (180 owed, or fully settled)."""
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't027_conditional')
        self._seed_noise(denidin_app, count=6, label="t027_noise")
        self._seed(
            denidin_app, "חווה יערי", amount="80₪", component_label="רכיב 1",
            message_id="t027_comp1", timestamp=_this_month_timestamp(day=2),
        )
        self._seed(
            denidin_app, "חווה יערי", amount="100₪", component_label="רכיב 2",
            trigger_condition="ערעור", message_id="t027_comp2",
            timestamp=_this_month_timestamp(day=2),
        )
        self._seed(
            denidin_app, "חווה יערי", source_type="בנק", event_subtype="הפקדה",
            amount="80₪", message_id="t027_deposit",
            timestamp=_this_month_timestamp(day=9),
        )
        self._seed_accounting_document(
            denidin_app, "חווה יערי", doc_type=320, type_name="חשבונית מס/קבלה",
            amount=80, status="paid", status_code=1, status_label="מסמך סגור",
            timestamp=_this_month_timestamp(day=9),
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather",
            "האם חווה יערי עוד חייבת כסף?", "t027_conditional",
        ))
        assert reply is not None
        assert "ערעור" in reply, (
            f"expected the reply to engage with component 2's own trigger "
            f"condition (ערעור) rather than silently ignore it: {reply!r}"
        )
        assert not _reply_contains_amount(reply, 180), (
            f"180 (80+100, treating the conditional component as a confirmed "
            f"current debt) must never appear as a confident total owed: {reply!r}"
        )

    def test_payment_under_a_different_payer_name_still_resolves(self, denidin_app, config):
        """T028: the agreement is with עוזי לנדאו, but one of the closing
        signals is a bank deposit under a DIFFERENT name (בני לנדאו) whose
        own description explicitly links it back to עוזי - there is no
        separate payer_name field for a בנק event (see LEDGER_EVENT_TOOL's
        own docs), so free text is the only place this link can live. A
        separate combo-320 receipt under עוזי's own name independently closes
        the same agreement.

        2026-08-26: the shared surname (לנדאו) that makes this scenario
        realistic ALSO fuzzy-collides above the app's own
        _NAME_MATCH_THRESHOLD (WRatio("עוזי לנדאו", "בני לנדאו") = 74 >= 70),
        so a search for "עוזי לנדאו" legitimately comes back as an
        identity-ambiguity candidates response, not a direct answer -
        confirmed live, this is the correct, working-as-designed behavior,
        not a bug. The test now handles both real outcomes: if the model
        answers directly, it must say כן; if it asks which of the two names
        was meant (matching this file's own established T009
        ask-then-confirm pattern), the user's own clarification is supplied
        verbatim on the second turn, and THAT reply must say כן."""
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't028_different_payer')
        self._seed_noise(denidin_app, count=6, label="t028_noise")
        self._seed(
            denidin_app, "עוזי לנדאו", amount="100₪",
            message_id="t028_agreement", timestamp=_this_month_timestamp(day=3),
        )
        self._seed(
            denidin_app, "בני לנדאו", source_type="בנק", event_subtype="הפקדה",
            amount="100₪", description="מקושר ללקוח עוזי לנדאו",
            message_id="t028_deposit", timestamp=_this_month_timestamp(day=10),
        )
        self._seed_accounting_document(
            denidin_app, "עוזי לנדאו", doc_type=320, type_name="חשבונית מס/קבלה",
            amount=100, status="paid", status_code=1, status_label="מסמך סגור",
            timestamp=_this_month_timestamp(day=10),
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather",
            "האם עוזי לנדאו שילם הכל?", "t028_different_payer",
        ))
        assert reply is not None
        if "?" in reply:
            reply = self._get_response(self._send_text(
                chat_id, phone, "Test Godfather",
                "בני הוא אח של עוזי שרק שילם בשבילו. עוזי הוא הלקוח. "
                "תשייך לעוזי גם את מה ששילם בני.",
                "t028_clarification",
            ))
            assert reply is not None
        assert "כן" in reply, (
            f"expected an affirmative (כן) - he's paid in full via the combo-320 "
            f"receipt alone, regardless of the differently-named deposit: {reply!r}"
        )

    def test_typo_variant_name_resolved_or_clarified_never_silently_dropped(
        self, denidin_app, config
    ):
        """T029: two bank deposits for the same real person, one with a
        single-character typo in the client_name (יוסי אביאל vs יןסי אביאל -
        ו/ן swapped). Two acceptable outcomes: the model resolves the typo'd
        entry as obviously the same person and sums both (150), or it asks a
        clarifying question naming the discrepancy - either is fine. What's
        NOT acceptable is silently answering from only one of the two events
        (100 alone) with no acknowledgement the second exists."""
        phone = config.godfather_phone
        chat_id = self._fresh_chat_id(config, 't029_typo')
        self._seed_noise(denidin_app, count=6, label="t029_noise")
        self._seed(
            denidin_app, "יוסי אביאל", source_type="בנק", event_subtype="הפקדה",
            amount="100₪", message_id="t029_correct",
            timestamp=_this_month_timestamp(day=4),
        )
        self._seed(
            denidin_app, "יןסי אביאל", source_type="בנק", event_subtype="הפקדה",
            amount="50₪", message_id="t029_typo",
            timestamp=_this_month_timestamp(day=11),
        )

        reply = self._get_response(self._send_text(
            chat_id, phone, "Test Godfather", "כמה שילם יוסי אביאל", "t029_typo",
        ))
        assert reply is not None
        resolved_full_sum = _reply_contains_amount(reply, 150)
        asked_clarifying_question = "?" in reply
        assert resolved_full_sum or asked_clarifying_question, (
            f"expected either a resolved total of 150 (typo recognized as the "
            f"same person) or a clarifying question about the second, "
            f"differently-spelled entry - got neither: {reply!r}"
        )
