"""
Component-Integration Test: Ledger Event Querying Conversation Routing
(Feature 044, T007a)

Verifies the full real router-dispatch path for querying ledger events: a
real textMessage-shaped Green API notification -> bot.router ->
handle_text_message -> WhatsAppHandler -> AIHandler.get_response ->
_finalize_response -> _handle_query_ledger_events -> a real
LedgerEventManager.query_events call -> a real follow-up round-trip whose
reply is what actually gets sent - all real internal objects and real router
dispatch (CONSTITUTION SS V), only the OpenAI client's responses.create is
stood in for (the genuine external boundary), same convention as
tests/integration/test_reminder_conversation_routing.py.

Does NOT exercise real conversational accuracy (whether the model decides to
call query_ledger_events at the right time, with sensible arguments, or
incorporates a free-text fact like "except X who already paid" into its own
reasoning) - that needs the real OpenAI API and belongs in tests/billed/.
What this DOES prove: given a response that already contains one or more
query_ledger_events calls, the real routing/handler/manager wiring genuinely
executes them against real ledger data and the reply reflects the real
result - AND that the RBAC gate genuinely keeps the tool off a client-role
turn through the real pipeline, not just at the unit level (already covered
by tests/unit/test_ai_handler_ledger_query.py).

**Test-data hygiene (user directive, 2026-08-23)**: `denidin_app` is a
process-global singleton reused across test files within one pytest session
(see the fixture below), and its `ledger_event_manager` is backed by the
real, ON-DISK, persistent `test_data/` root - NOT a fresh tmp_path per test.
Every test in this file wipes `test_data/events/` (files + the in-memory
index) BEFORE and AFTER itself via the autouse `_clean_ledger_events` fixture
below - this is unit/integration-tier data, safe to clear unconditionally
(unlike prod data). This is a stronger guarantee than "clean up what you
seeded": earlier drafts of these tests instead tried to track and delete only
their own seeded event_ids, and still hit a real fuzzy-match collision from
UNRELATED leftover data (two similar-sounding names tripping the
entity-ambiguity check against each other - research.md Decision 4 working
exactly as designed, just against noise neither test caused). A full wipe
removes that whole class of flakiness rather than trying to out-clever it.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.models.config import AppConfiguration


GODFATHER_CHAT_ID = "972501234567@c.us"
GODFATHER_SENDER = "972501234567@c.us"


def _is_post_turn_recognition_call(kwargs) -> bool:
    """Feature 069: every godfather/admin turn now ends with a text-only
    `recognize_ledger_event` call (tools=[report_ledger_recognition]). These tests
    exercise the `query_ledger_events` main-turn route, not recognition - let each
    stub short-circuit that trailing call to an inert `none` verdict so it neither
    advances the stub's own call counter nor clobbers a captured-kwargs slot."""
    return any(
        isinstance(t, dict) and t.get("name") == "report_ledger_recognition"
        for t in (kwargs.get("tools") or [])
    )


_RECOGNITION_NOOP = SimpleNamespace(
    id="resp_recognition_noop", output=[], output_text="", model="gpt-5.6-luna",
    usage=SimpleNamespace(total_tokens=1, input_tokens=1, output_tokens=0),
)


@pytest.mark.integration
class TestLedgerQueryRouting:

    @pytest.fixture
    def denidin_app(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
        if not config_path.exists():
            pytest.skip("config.test.json not found")

        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        test_data_root = Path(__file__).parent.parent.parent / "test_data"
        config.data_root = str(test_data_root)
        config.memory['session']['storage_dir'] = str(test_data_root / "sessions")
        config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")

        import denidin as denidin_module
        if denidin_module.denidin_app is None:
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
                'reminders': {'max_active_reminders': 20},
            }
            denidin_module.denidin_app = denidin_module.initialize_app(config_dict)

        app = denidin_module.denidin_app
        # Stop the background session-cleanup thread: it makes its own
        # client.responses.create calls (session summarization) that race these
        # tests' stubbed OpenAI client and desync their call counters.
        if getattr(app, "cleanup_thread", None) is not None:
            app.cleanup_thread.stop()
            app.cleanup_thread = None
        return app

    def _wipe_events(self, denidin_app):
        manager = denidin_app.ai_handler.ledger_event_manager
        manager._index = []
        for path in manager.storage_dir.glob("*.json"):
            path.unlink()

    @pytest.fixture(autouse=True)
    def _clean_ledger_events(self, denidin_app):
        """Wipes test_data/events/ (disk + in-memory index) before AND after
        every test in this class - see the module docstring's "Test-data
        hygiene" note for why a full wipe, not selective cleanup."""
        self._wipe_events(denidin_app)
        yield
        self._wipe_events(denidin_app)

    def _seed(self, denidin_app, client_name, payer_name=None, source_type="הסכם",
              event_subtype="יצירה", amount="1,000₪", message_id="seed",
              timestamp=1786784400):  # 2026-08-15 local, unless overridden
        return denidin_app.ai_handler.ledger_event_manager.add_ledger_event(
            session_id="s", event={
                "source_type": source_type, "event_subtype": event_subtype,
                "client_name": client_name, "payer_name": payer_name,
                "description": "תיאור", "amount": amount,
                "percent": None, "percent_base": None, "hours": None,
                "hourly_rate": None, "txn_date": None,
                "vat_status": "כולל" if source_type == "בנק" else "לא צוין",
                "trigger_condition": None, "reference_hint": None,
                "agreement_label": "תיק" if source_type == "הסכם" else None,
                "component_label": "בסיס" if source_type == "הסכם" else None,
            },
            message_id=message_id, message_timestamp=timestamp,
        )

    def _create_notification(self, chat_id: str, sender: str, sender_name: str, text: str, msg_id: str):
        from whatsapp_chatbot_python import Notification

        notification = Notification.__new__(Notification)
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'idMessage': msg_id,
            'timestamp': 1755331200,
            'senderData': {
                'chatId': chat_id,
                'sender': sender,
                'senderName': sender_name,
            },
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': text},
            },
        }
        notification._test_sent_messages = []

        def track_answer(message):
            notification._test_sent_messages.append(message)

        notification.answer = track_answer
        return notification

    def _stub_query_ledger_events_response(self, denidin_app, monkeypatch, args: dict,
                                            followup_text: str = "נמצא סכום 5,000"):
        """Stand in for the one genuine external boundary (OpenAI) - the first
        call returns a query_ledger_events function_call, the follow-up
        (chained via previous_response_id) returns the real reply text."""
        first_response = SimpleNamespace(
            id="resp_integration_ledger_query_1",
            output=[SimpleNamespace(
                type="function_call", name="query_ledger_events",
                arguments=json.dumps(args), call_id="call_integration_ledger_query_1",
            )],
            output_text="",
            model="gpt-5.6-luna",
            usage=SimpleNamespace(total_tokens=8, input_tokens=6, output_tokens=2),
        )
        followup_response = SimpleNamespace(
            id="resp_integration_ledger_query_followup_1",
            output=[], output_text=followup_text,
            model="gpt-5.6-luna",
            usage=SimpleNamespace(total_tokens=6, input_tokens=4, output_tokens=2),
        )
        calls = {"n": 0}

        def fake_create(**kwargs):
            if _is_post_turn_recognition_call(kwargs):
                return _RECOGNITION_NOOP
            calls["n"] += 1
            return first_response if calls["n"] == 1 else followup_response

        monkeypatch.setattr(denidin_app.ai_handler.client.responses, 'create', fake_create)

    def _stub_multi_call_response(self, denidin_app, monkeypatch, calls_args: list,
                                   followup_text: str = "התוצאות נמצאו"):
        """Same as _stub_query_ledger_events_response, but the first (stubbed)
        response contains SEVERAL query_ledger_events calls at once - the
        real shape a genuine multi-criterion question ("client A, B, C, or D,
        within a date range") produces (research.md Decision 10). Captures
        the real follow-up's `input` kwarg so tests can inspect exactly what
        was reported back per call_id. Not limited to two calls - the whole
        point of Decision 10 is that this scales to however many distinct
        criteria the user's own question implies."""
        first_response = SimpleNamespace(
            id="resp_integration_ledger_query_multi_1",
            output=[
                SimpleNamespace(
                    type="function_call", name="query_ledger_events",
                    arguments=json.dumps(args), call_id=f"call_multi_{i}",
                )
                for i, args in enumerate(calls_args)
            ],
            output_text="",
            model="gpt-5.6-luna",
            usage=SimpleNamespace(total_tokens=8, input_tokens=6, output_tokens=2),
        )
        followup_response = SimpleNamespace(
            id="resp_integration_ledger_query_multi_followup_1",
            output=[], output_text=followup_text,
            model="gpt-5.6-luna",
            usage=SimpleNamespace(total_tokens=6, input_tokens=4, output_tokens=2),
        )
        captured = {}
        calls = {"n": 0}

        def fake_create(**kwargs):
            if _is_post_turn_recognition_call(kwargs):
                return _RECOGNITION_NOOP
            calls["n"] += 1
            if calls["n"] == 1:
                return first_response
            captured.update(kwargs)
            return followup_response

        monkeypatch.setattr(denidin_app.ai_handler.client.responses, 'create', fake_create)
        return captured

    NO_FILTER_ARGS = {"criteria": []}

    @staticmethod
    def _criteria_args(*pairs):
        """Build a query_ledger_events call's arguments from (text, hint)
        pairs - the 2026-08-24 redesign's `criteria` shape (see
        src/managers/ledger_event_manager.py's module-level _HINT_GROUPS
        comment)."""
        return {"criteria": [{"text": text, "hint": hint} for text, hint in pairs]}

    def test_query_ledger_events_call_dispatches_and_reply_reflects_real_result(
        self, denidin_app, monkeypatch
    ):
        """
        **Scenario**: Godfather asks about a past agreement; the model calls
        query_ledger_events.

        Given: a real, pre-seeded ledger event and a real textMessage
               notification from the godfather's own chat
        When: dispatched through the real handle_text_message router entry
        Then: query_ledger_events genuinely executes against the real
              LedgerEventManager, and the sent reply is the follow-up call's
              real text - proving the tool is genuinely attached AND
              genuinely reachable through the real pipeline.
        """
        self._seed(denidin_app, "תומר אלוני", amount="5,000₪", message_id="seed_m1")
        self._stub_query_ledger_events_response(
            denidin_app, monkeypatch,
            self._criteria_args(("תומר אלוני", "identity")),
        )

        notification = self._create_notification(
            GODFATHER_CHAT_ID, GODFATHER_SENDER, "Test Godfather",
            "כמה סוכם עם תומר אלוני?", "integration_ledger_query_msg_1",
        )

        from denidin import handle_text_message
        handle_text_message(notification)

        assert notification._test_sent_messages, "expected a reply to have been sent"
        assert notification._test_sent_messages[0] == "נמצא סכום 5,000"

    def test_client_role_never_receives_query_ledger_events_tool_over_the_real_route(
        self, denidin_app, monkeypatch
    ):
        """RBAC gate (US3/FR-004), exercised through the real router/handler/
        RBAC-resolution path rather than calling _build_ledger_query_tools
        directly (already covered at the unit tier) - captures what `tools`
        the REAL _assemble_tools call actually handed to the (stubbed) OpenAI
        request for a genuine CLIENT-role dispatch, and confirms
        query_ledger_events is structurally absent, not just "not called this
        time"."""
        client_chat_id = "972500009998@c.us"
        captured_kwargs = {}

        def capture_and_respond(**kwargs):
            if _is_post_turn_recognition_call(kwargs):
                return _RECOGNITION_NOOP
            captured_kwargs.update(kwargs)
            return SimpleNamespace(
                id="resp_client_ledger_query_1", output=[], output_text="בסדר",
                model="gpt-5.6-luna",
                usage=SimpleNamespace(total_tokens=4, input_tokens=3, output_tokens=1),
            )

        monkeypatch.setattr(denidin_app.ai_handler.client.responses, 'create', capture_and_respond)

        notification = self._create_notification(
            client_chat_id, client_chat_id, "Test Client",
            "כמה סוכם עם לקוח כלשהו?", "integration_ledger_query_msg_2",
        )
        from denidin import handle_text_message
        handle_text_message(notification)

        tool_names = [t.get("name") for t in (captured_kwargs.get("tools") or [])]
        assert "query_ledger_events" not in tool_names

    def test_payer_name_search_dispatches_correctly_over_the_real_route(
        self, denidin_app, monkeypatch
    ):
        """T008 scenario 4 (payer-name search), mechanics-only: proves the
        real router/handler/manager wiring finds an event by its payer_name
        (not client_name) end-to-end - the fuzzy-matching logic itself is
        already unit-tested (test_ledger_event_manager.py), this closes the
        real-pipeline gap for THIS specific argument shape. payer_name here
        is a real insurer proper noun ("מגדל"), matching this codebase's own
        real historical data convention (e.g. "הראל" as a real payer_name) -
        never a generic "חברת X" placeholder, and never itself the client."""
        self._seed(
            denidin_app, "דניאל פרץ", payer_name="מגדל",
            amount="3,000₪", message_id="seed_payer_m1",
        )
        captured = {}
        calls = {"n": 0}

        def fake_create(**kwargs):
            if _is_post_turn_recognition_call(kwargs):
                return _RECOGNITION_NOOP
            calls["n"] += 1
            if calls["n"] == 1:
                return SimpleNamespace(
                    id="resp_payer_1",
                    output=[SimpleNamespace(
                        type="function_call", name="query_ledger_events",
                        arguments=json.dumps(self._criteria_args(("מגדל", "identity"))),
                        call_id="call_payer_1",
                    )],
                    output_text="", model="gpt-5.6-luna",
                    usage=SimpleNamespace(total_tokens=8, input_tokens=6, output_tokens=2),
                )
            captured.update(kwargs)
            return SimpleNamespace(
                id="resp_payer_followup_1", output=[], output_text="נמצא",
                model="gpt-5.6-luna",
                usage=SimpleNamespace(total_tokens=6, input_tokens=4, output_tokens=2),
            )

        monkeypatch.setattr(denidin_app.ai_handler.client.responses, 'create', fake_create)

        notification = self._create_notification(
            GODFATHER_CHAT_ID, GODFATHER_SENDER, "Test Godfather",
            "האם קיבלנו תשלום ממגדל?", "integration_ledger_query_payer_1",
        )
        from denidin import handle_text_message
        handle_text_message(notification)

        payload = json.loads(captured["input"][0]["output"])
        assert payload["count"] == 1
        assert payload["matches"][0]["payer_name"] == "מגדל"

    def test_both_confirmed_candidates_issues_two_calls_and_merges_over_the_real_route(
        self, denidin_app, monkeypatch
    ):
        """T009 scenario 2 (the 'both/all' follow-up after disambiguation),
        mechanics-only: proves the real router/handler/manager wiring
        correctly executes and merges TWO query_ledger_events calls in one
        turn - the multi-call dispatch logic itself is already unit-tested
        (test_ai_handler_ledger_query.py), this closes the real-pipeline gap.
        (The disambiguation turn itself - the model recognizing ambiguity
        and asking - is real model judgment, not simulated here; this test
        starts from the point where the user has already confirmed both
        candidates by their exact names.)"""
        self._seed(denidin_app, "מיכל רוזן", amount="1,000₪", message_id="seed_both_m1")
        self._seed(denidin_app, "בני אשכנזי", amount="2,000₪", message_id="seed_both_m2")

        captured = self._stub_multi_call_response(denidin_app, monkeypatch, [
            self._criteria_args(("מיכל רוזן", "identity")),
            self._criteria_args(("בני אשכנזי", "identity")),
        ])

        notification = self._create_notification(
            GODFATHER_CHAT_ID, GODFATHER_SENDER, "Test Godfather",
            "גם וגם", "integration_ledger_query_both_1",
        )
        from denidin import handle_text_message
        handle_text_message(notification)

        assert len(captured["input"]) == 2
        by_call_id = {item["call_id"]: json.loads(item["output"]) for item in captured["input"]}
        names_found = {
            item["matches"][0]["client_name"]
            for item in by_call_id.values() if item.get("count") == 1
        }
        assert names_found == {"מיכל רוזן", "בני אשכנזי"}

    def test_monthly_income_aggregation_date_only_query_over_the_real_route(
        self, denidin_app, monkeypatch
    ):
        """T010 scenario 3 (monthly income aggregation), mechanics-only:
        proves a broad, client-less, category-only query (research.md
        Decision 11 - "income" means received, not agreed) correctly
        includes only the deposit event and excludes an agreed-but-unpaid
        event, through the real pipeline, including the vague-query guard
        NOT blocking a client-less single-criterion query. Post-2026-08-24
        redesign, there is no dedicated date-range filter any more - a
        real "how much income in August" question is answered by a broad
        category='בנק' retrieval (this test's own concern) plus the model
        itself reasoning over each returned event's own date field to keep
        only the right month (a model-reasoning concern, not exercised
        here - see tests/billed/ for the real conversational scenario)."""
        self._seed(denidin_app, "דנה פלד", source_type="בנק", event_subtype="הפקדה",
                    amount="4,000₪", message_id="seed_income_m1", timestamp=1785920400)
        self._seed(denidin_app, "אלון שני", amount="9,000₪",
                    message_id="seed_income_m2", timestamp=1785920400)

        captured = {}
        calls = {"n": 0}

        def fake_create(**kwargs):
            if _is_post_turn_recognition_call(kwargs):
                return _RECOGNITION_NOOP
            calls["n"] += 1
            if calls["n"] == 1:
                return SimpleNamespace(
                    id="resp_income_1",
                    output=[SimpleNamespace(
                        type="function_call", name="query_ledger_events",
                        arguments=json.dumps(self._criteria_args(("בנק", "event_type"))),
                        call_id="call_income_1",
                    )],
                    output_text="", model="gpt-5.6-luna",
                    usage=SimpleNamespace(total_tokens=8, input_tokens=6, output_tokens=2),
                )
            captured.update(kwargs)
            return SimpleNamespace(
                id="resp_income_followup_1", output=[], output_text="סה\"כ הכנסות: 4,000",
                model="gpt-5.6-luna",
                usage=SimpleNamespace(total_tokens=6, input_tokens=4, output_tokens=2),
            )

        monkeypatch.setattr(denidin_app.ai_handler.client.responses, 'create', fake_create)

        notification = self._create_notification(
            GODFATHER_CHAT_ID, GODFATHER_SENDER, "Test Godfather",
            "כמה הכנסות היו לי באוגוסט?", "integration_ledger_query_income_1",
        )
        from denidin import handle_text_message
        handle_text_message(notification)

        payload = json.loads(captured["input"][0]["output"])
        assert payload["count"] == 1
        assert payload["matches"][0]["source_type"] == "בנק"
        assert payload["matches"][0]["amount"] == 4000

    def test_four_way_multi_criterion_with_date_range_issues_four_calls_over_the_real_route(
        self, denidin_app, monkeypatch
    ):
        """T011 (genuine multi-criterion request), mechanics-only, strengthened
        2026-08-23 per user note - "A or B" was only an illustrative example;
        the real requirement is N criteria, unbounded (research.md Decision
        10 already supports this - no schema change, just N calls in one
        turn). Proves the real pipeline correctly executes and merges FOUR
        separately-named, already-known-distinct clients, each call ALSO
        carrying a second (date) criterion - i.e. each of the four calls
        combines two dimensions at once (identity AND date), not just one.
        Post-2026-08-24 redesign, "date" is just another ANDed {text, hint}
        criterion (fuzzy text match against date-bearing fields), not a
        dedicated range filter - the date text here matches every seeded
        event's own event_datetime month/year substring."""
        clients = [
            ("נועה שדה", "2,000₪"),
            ("אבי גולן", "3,000₪"),
            ("שירה מזרחי", "4,000₪"),
            ("אלעד ברק", "5,000₪"),
        ]
        for i, (name, amount) in enumerate(clients):
            self._seed(denidin_app, name, amount=amount, message_id=f"seed_four_m{i}",
                       timestamp=1786784400)  # 2026-08-15 local

        captured = self._stub_multi_call_response(denidin_app, monkeypatch, [
            self._criteria_args((name, "identity"), ("08/2026", "date"))
            for name, _ in clients
        ])

        notification = self._create_notification(
            GODFATHER_CHAT_ID, GODFATHER_SENDER, "Test Godfather",
            "מה סוכם באוגוסט עם נועה שדה, אבי גולן, שירה מזרחי או אלעד ברק?",
            "integration_ledger_query_four_1",
        )
        from denidin import handle_text_message
        handle_text_message(notification)

        assert len(captured["input"]) == 4
        amounts_by_client = {}
        for item in captured["input"]:
            payload = json.loads(item["output"])
            if payload.get("count") == 1:
                amounts_by_client[payload["matches"][0]["client_name"]] = payload["matches"][0]["amount"]
        assert amounts_by_client == {
            "נועה שדה": 2000, "אבי גולן": 3000, "שירה מזרחי": 4000, "אלעד ברק": 5000,
        }
