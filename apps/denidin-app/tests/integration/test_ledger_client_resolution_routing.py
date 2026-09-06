"""
Component-Integration Tests: post-turn ledger recognition through the real router
(Feature 069 — the mechanism move + mandatory client resolution).

A real Green API notification → `bot.router` → `handle_text_message` →
`_process_conversational_message` → `AIHandler.get_response` (normal reply) → **the
post-turn recognition call** → the zero-AI ledgerer → `LedgerEvent` file(s) on disk,
back-linked from the completing `Message`.

All real internal objects and real router dispatch (CONSTITUTION §V); the ONLY
stand-in is `ai_handler.client.responses.create`, scripted per turn via
`_ledger_069_harness.ScriptedOpenAI` (real model judgement is `tests/billed/`,
Phase 11).

Covers, by phase:
  - T007a  — the enabler slice (exact-match `הסכם`, post-turn, back-linked)
  - US1    — decoupling: the reply is produced independently of recognition (SC-009)
  - US3    — regression guard: a read-back / a mid-flow field-fill capture nothing
  - US2    — a Morning `create_*` that succeeds in-conversation → one `חשבונית`
             event that turn, from the tool result (not the prose), deduped against
             Feature 025's cache
  - US4    — new-client `הסכם`: nothing persists until the client is created; then
             every extracted field reaches the record; `event_datetime` = the
             original agreement message's timestamp; declined approval → nothing
  - US5    — ambiguous client name: candidates listed, nothing captured until a
             pick; a re-ask once then abandonment; a later correction reuses the
             resolved name
  - US8    — won't provide email/phone → single closed store-anyway question →
             store-anyway (marker in description, no Morning client) OR don't-store
             (`declined` verdict, one breadcrumb, nothing persisted); proactive
             election honoured with no "are you sure" turn
"""
import json
import logging
from pathlib import Path

import pytest

from src.handlers.ai_handler import AIHandler, LEDGER_EVENT_TOOL
from src.models.config import AppConfiguration

from tests.e2e_helpers import event_datetime_for_message_ts
from tests.integration import _ledger_069_harness as h
from tests.integration._ledger_069_harness import (
    ScriptedOpenAI, GODFATHER_CHAT_ID, GODFATHER_SENDER, RECOGNITION_TOOL_NAME,
)

TRIGGER_MSG_ID = "integration_069_recognition_msg_1"
OPERATOR_REPLY = "רשמתי את הסכם שכר הטרחה עם דנה כהן."


@pytest.mark.integration
class TestLedgerClientResolutionRouting:

    # ------------------------------------------------------------------ #
    # fixtures / helpers
    # ------------------------------------------------------------------ #

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
        # The background session-cleanup thread makes its own OpenAI calls to
        # summarize expired sessions - left running it races the scripted client
        # and mutates session state mid-turn. Stop it for the duration.
        if getattr(app, "cleanup_thread", None) is not None:
            app.cleanup_thread.stop()
            app.cleanup_thread = None
        return app

    @pytest.fixture(autouse=True)
    def _clean_state(self, denidin_app):
        def _wipe():
            manager = denidin_app.ai_handler.ledger_event_manager
            manager._index = []
            manager._accounting_document_cache = None
            for path in manager.storage_dir.glob("*.json"):
                path.unlink()
            denidin_app.ai_handler.session_manager.clear_session(GODFATHER_CHAT_ID)
            denidin_app.ai_handler.pending_approval_manager._pending.clear()
        _wipe()
        yield
        _wipe()

    def _create_notification(self, text: str, msg_id: str):
        from whatsapp_chatbot_python import Notification

        notification = Notification.__new__(Notification)
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'idMessage': msg_id,
            'timestamp': 1755331200,
            'senderData': {
                'chatId': GODFATHER_CHAT_ID,
                'sender': GODFATHER_SENDER,
                'senderName': 'Test Godfather',
            },
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': text},
            },
        }
        notification._test_sent_messages = []
        notification.answer = notification._test_sent_messages.append
        return notification

    def _install(self, denidin_app, monkeypatch, script: ScriptedOpenAI) -> ScriptedOpenAI:
        monkeypatch.setattr(denidin_app.ai_handler.client.responses, 'create', script)
        return script

    def _send(self, text: str, msg_id: str = "u"):
        notification = self._create_notification(text, msg_id)
        from denidin import handle_text_message
        handle_text_message(notification)
        return notification

    def _events(self, denidin_app):
        mgr = denidin_app.ai_handler.ledger_event_manager
        return [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(mgr.storage_dir.glob("*.json"))]

    def _session(self, denidin_app):
        return denidin_app.ai_handler.session_manager.get_session(GODFATHER_CHAT_ID)

    def _first_message_id(self, denidin_app):
        return self._session(denidin_app).message_ids[0]

    def _messages_by_role(self, denidin_app):
        sm = denidin_app.ai_handler.session_manager
        session = sm.get_session(GODFATHER_CHAT_ID)
        messages_dir = Path(sm.storage_dir) / session.session_id / "messages"
        by_role = {}
        for mid in session.message_ids:
            data = json.loads((messages_dir / f"{mid}.json").read_text(encoding="utf-8"))
            by_role.setdefault(data["role"], []).append(data)
        return by_role

    def _crumbs(self, caplog):
        return [r.getMessage() for r in caplog.records if r.getMessage().startswith("[069]")]

    def _recognize_verdict_for_trigger(self, denidin_app, ev: dict):
        """Deferred: resolve the real trigger message id at call time (message ids
        are fresh uuids, never the webhook idMessage)."""
        return lambda: h.recognition_verdict(
            h.complete(self._first_message_id(denidin_app), ev))

    # ================================================================== #
    # T007a — the enabler slice
    # ================================================================== #

    def test_followup_api_is_gone(self):
        assert not hasattr(AIHandler, "_call_openai_ledger_followup_api")

    def test_exact_match_agreement_captured_post_turn_and_back_linked(
        self, denidin_app, monkeypatch, caplog
    ):
        caplog.set_level(logging.INFO)
        script = ScriptedOpenAI().queue_turn(
            h.reply(OPERATOR_REPLY),
            self._recognize_verdict_for_trigger(
                denidin_app,
                h.agreement_event(client_name="דנה כהן",
                                  components=[{"amount": "4000", "description": "ריטיינר חודשי"}])),
        )
        self._install(denidin_app, monkeypatch, script)

        notification = self._send(
            "חתמנו הסכם שכר טרחה עם דנה כהן, ריטיינר 4000 בחודש", TRIGGER_MSG_ID)

        assert notification._test_sent_messages == [OPERATOR_REPLY]

        events = self._events(denidin_app)
        assert len(events) == 1
        assert events[0]["source_type"] == "הסכם"
        assert events[0]["client_name"] == "דנה כהן"
        event_id = events[0]["event_id"]

        by_role = self._messages_by_role(denidin_app)
        assert by_role["assistant"][-1]["ledger_event_ids"] == [event_id]
        trigger_msg = next(d for role, ms in by_role.items() if role != "assistant" for d in ms)
        assert trigger_msg["ledger_event_ids"] == []

        crumbs = self._crumbs(caplog)
        assert any(c.startswith("[069] ledger capture recognized:") for c in crumbs)
        assert any(c.startswith("[069] ledger event written:") and event_id in c for c in crumbs)

    # ================================================================== #
    # Amendment linking — a later "adds/corrects" turn writes a SECOND
    # יצירה record whose `reference` points at the first event's id (the
    # model reads that id off the `[✓ captured as <ids>]` window marker).
    # ================================================================== #

    def test_amendment_second_record_references_first_event_id(
        self, denidin_app, monkeypatch
    ):
        script = ScriptedOpenAI()
        # turn A - a plain agreement for an existing client
        script.queue_turn(
            h.reply("רשמתי הסכם עם דנה לולו, 1500."),
            self._recognize_verdict_for_trigger(
                denidin_app,
                h.agreement_event(client_name="דנה לולו",
                                  components=[{"amount": "1500", "description": "שכר טרחה"}])),
        )
        # turn B - "they settled on 15% of the amount" -> a second record that
        # references event A (id resolved at call time off the window marker).
        def _verdict_b():
            first_id = self._events(denidin_app)[0]["event_id"]
            return h.recognition_verdict(h.complete(
                self._session(denidin_app).message_ids[-1],
                h.agreement_event(
                    client_name="דנה לולו", reference=first_id,
                    components=[
                        {"amount": "1500", "description": "שכר טרחה"},
                        {"percent": "15", "percent_base": "הסכום", "description": "הסדר"},
                    ])))
        script.queue_turn(h.reply("עדכנתי - נוסף 15% אם יגיעו להסדר."), _verdict_b)
        self._install(denidin_app, monkeypatch, script)

        self._send("דנה לולו 1500", "u1")
        events_after_a = self._events(denidin_app)
        assert len(events_after_a) == 1
        first_id = events_after_a[0]["event_id"]

        self._send("אם הגיעו להסדר, 15% מהסכום", "u2")
        events = self._events(denidin_app)
        # event A + the 2 components of record B, all הסכם
        new_events = [e for e in events if e["event_id"] != first_id]
        assert new_events, "amendment record B was not persisted"
        assert all(e["source_type"] == "הסכם" for e in events)
        assert all(e["reference"] == first_id for e in new_events)

    # ================================================================== #
    # Phase 3 — US1: the reply is produced independently of recognition
    # ================================================================== #

    def test_us1_reply_unchanged_when_recognition_raises(self, denidin_app, monkeypatch):
        """SC-009: recognition blowing up must not change the operator's reply by
        one byte, and must not crash the turn."""
        self._install(denidin_app, monkeypatch,
                      ScriptedOpenAI().queue_turn(h.reply("רשמתי את ההסכם.")))

        def boom(*a, **k):
            raise RuntimeError("recognition exploded")

        monkeypatch.setattr(denidin_app.ai_handler, "recognize_ledger_event", boom)

        notification = self._send("חתמנו הסכם עם דנה כהן, ריטיינר 4000", "u1")

        assert notification._test_sent_messages == ["רשמתי את ההסכם."]
        assert self._events(denidin_app) == []

    def test_us1_main_turn_has_query_but_not_capture_tool(self, denidin_app, monkeypatch):
        script = self._install(denidin_app, monkeypatch,
                               ScriptedOpenAI().queue_turn(h.reply("טוב.")))
        self._send("מה שלומך?", "u1")

        main_tools = script.main_calls[0].get("tools") or []
        names = {t.get("name") for t in main_tools if isinstance(t, dict)}
        assert "query_ledger_events" in names
        assert LEDGER_EVENT_TOOL["name"] not in names
        assert "capture_ledger_event" not in names

    def test_us1_exact_match_multi_component_agreement_one_file_per_component(
        self, denidin_app, monkeypatch, caplog
    ):
        caplog.set_level(logging.INFO)
        script = ScriptedOpenAI().queue_turn(
            h.reply("רשמתי את הסכם שכר הטרחה עם דנה כהן."),
            self._recognize_verdict_for_trigger(denidin_app, h.agreement_event()),
        )
        self._install(denidin_app, monkeypatch, script)

        self._send("חתמנו הסכם עם דנה כהן: ריטיינר 4000, 12% הצלחה, 750 לכל דיון", "u1")

        events = self._events(denidin_app)
        assert len(events) == 3
        assert {e["client_name"] for e in events} == {"דנה כהן"}
        assert len({e["agreement_id"] for e in events}) == 1
        assert len({e["component_id"] for e in events}) == 3
        assert {e["payer_name"] for e in events} == {"איגוד העובדים"}
        assert sum(c.startswith("[069] ledger event written:") for c in self._crumbs(caplog)) == 3

    # ================================================================== #
    # Phase 4 — US3: regression guard (no spurious capture, no lost reply)
    # ================================================================== #

    def test_us3_list_invoices_readback_captures_nothing(self, denidin_app, monkeypatch):
        """2026-07-28 shape: the model reads a list_invoices result back to the
        operator - a read-only Morning question, never a ledger event."""
        readback = "יש לך 3 חשבוניות פתוחות: 1001, 1002, 1003."
        script = ScriptedOpenAI().queue_turn(
            h.reply_with_calls(readback, [{
                "type": "mcp_call", "name": "list_invoices",
                "arguments": json.dumps({"client_name": "דנה כהן"}),
                "output": json.dumps({"invoices": [{"number": "1001"}, {"number": "1002"}]}),
            }]),
            h.recognition_none(),
        )
        self._install(denidin_app, monkeypatch, script)

        notification = self._send("אילו חשבוניות פתוחות יש לדנה כהן?", "u1")

        assert notification._test_sent_messages == [readback]
        assert self._events(denidin_app) == []

    def test_us3_midflow_field_fill_reply_captures_nothing(self, denidin_app, monkeypatch):
        """2026-08-02 shape: a two-word field-filling reply mid-approval
        ("עבור ייעוץ") - an incomplete event, recognition returns none."""
        script = ScriptedOpenAI().queue_turn(
            h.reply("קיבלתי, אעדכן את פרטי המסמך."),
            h.recognition_none(),
        )
        self._install(denidin_app, monkeypatch, script)

        notification = self._send("עבור ייעוץ", "u1")

        assert notification._test_sent_messages == ["קיבלתי, אעדכן את פרטי המסמך."]
        assert self._events(denidin_app) == []

    def test_us3_recognition_call_is_text_only_for_morning(self, denidin_app, monkeypatch):
        script = ScriptedOpenAI().queue_turn(h.reply("טוב."), h.recognition_none())
        self._install(denidin_app, monkeypatch, script)
        self._send("סתם הודעה", "u1")

        assert script.recognition_calls, "the post-turn recognition call must fire"
        rec_tools = script.recognition_calls[0].get("tools") or []
        # No Morning MCP / hosted tool. query_ledger_events (a local, read-only,
        # in-memory function tool - no tunnel) IS attached by design (decision #5).
        assert not any(isinstance(t, dict) and t.get("type") == "mcp" for t in rec_tools)
        names = {t.get("name") for t in rec_tools if isinstance(t, dict)}
        assert names == {RECOGNITION_TOOL_NAME, "query_ledger_events"}

    # ================================================================== #
    # Phase 5 — US2: Morning create_* captured synchronously
    # ================================================================== #

    def test_us2_morning_create_captured_that_turn_from_tool_result(
        self, denidin_app, monkeypatch, caplog
    ):
        caplog.set_level(logging.INFO)
        morning_response = {
            "status": "success", "document_number": "1042", "document_type": 320,
            "amount": 4000, "creation_date": "2026-07-15", "client_name": "דנה כהן",
        }
        # prose deliberately disagrees with the real response (wrong number/amount)
        prose = "יצרתי עסקה משולבת מספר 9999 על סך 12,000."
        invoice_ev = h.invoice_event(
            accounting_document_display_number="1042", amount="4000",
            txn_date="2026-07-15", event_subtype="חשבונית מס/קבלה", vat_status="כולל",
        )
        script = ScriptedOpenAI().queue_turn(
            h.reply_with_calls(prose, [{
                "type": "mcp_call", "name": "create_combo_document",
                "arguments": json.dumps({"client_name": "דנה כהן", "amount": 4000}),
                "output": json.dumps(morning_response),
            }]),
            self._recognize_verdict_for_trigger(denidin_app, invoice_ev),
        )
        self._install(denidin_app, monkeypatch, script)

        self._send("תוציא לדנה כהן עסקה משולבת על 4000 כולל מע\"מ", "u1")

        events = self._events(denidin_app)
        assert len(events) == 1
        rec = events[0]
        assert rec["source_type"] == "חשבונית"
        assert rec["accounting_document_display_number"] == "1042"   # from the response
        assert rec["amount"] == 4000
        assert rec["event_subtype"] == "חשבונית מס/קבלה"
        assert rec["vat_status"] == "כולל"

        # Feature 025 dedup: the display number is now in the cache, so the
        # reconciliation sweep re-seeing it that same day is a no-op.
        mgr = denidin_app.ai_handler.ledger_event_manager
        again = mgr.add_ledger_events_from_call(
            session_id="accounting-reconciliation",
            call_arguments={
                "source_type": "חשבונית", "event_subtype": "הפקה",
                "accounting_document_json": json.dumps({
                    "display_number": "1042", "type_name": "חשבונית מס/קבלה",
                    "creation_date": "2026-07-15T10:00:00", "amount": 4000,
                    "client_name": "דנה כהן", "description": "עסקה משולבת",
                    "status": 0, "payment": {},
                }),
                "component_count": 0, "components": [],
            },
            message_id=None, message_timestamp=None,
        )
        assert again == []
        assert len(self._events(denidin_app)) == 1

    # ================================================================== #
    # Phase 6 — US4: new-client fee agreement (nothing until add_client)
    # ================================================================== #

    def test_us4_new_client_agreement_nothing_until_client_created(
        self, denidin_app, monkeypatch, caplog
    ):
        caplog.set_level(logging.INFO)
        script = ScriptedOpenAI()
        # turn 1: operator states the agreement; DeniDin asks for full name+email+phone
        script.queue_turn(
            h.reply_with_calls(
                "לא מצאתי את הלקוח במורנינג. מה השם המלא, האימייל והטלפון?",
                [{"type": "mcp_call", "name": "resolve_client_name",
                  "arguments": json.dumps({"name": "רון לוי"}),
                  "output": json.dumps({"matches": []})}]),
            h.recognition_none(),
        )
        # turn 2: operator gives the three details -> add_client proposed (pending approval)
        script.queue_turn(
            h.reply_with_calls(
                "📋 לאישור — הוספת לקוח: רון לוי. אישור — כן/לא?",
                [{"type": "function_call", "name": "add_client",
                  "arguments": json.dumps({"name": "רון לוי", "email": "ron@example.com",
                                           "phone": "0521112222"})}]),
            h.recognition_none(),
        )
        # turn 3: "כן" -> add_client resolves; the completing turn recognizes the event
        agreement = h.agreement_event(client_name="רון לוי", payer_name="איגוד העובדים")
        script.queue_turn(
            h.reply("הלקוח נוסף והסכם שכר הטרחה נרשם."),
            self._recognize_verdict_for_trigger(denidin_app, agreement),
        )
        self._install(denidin_app, monkeypatch, script)

        self._send("חתמנו הסכם שכר טרחה עם רון לוי: ריטיינר 4000, 12% הצלחה, 750 לדיון", "u1")
        assert self._events(denidin_app) == []          # unresolved client -> nothing

        self._send("רון לוי, ron@example.com, 0521112222", "u2")
        assert self._events(denidin_app) == []          # still just a pending approval

        self._send("כן", "u3")
        events = self._events(denidin_app)
        assert len(events) == 3
        assert {e["client_name"] for e in events} == {"רון לוי"}
        assert {e["payer_name"] for e in events} == {"איגוד העובדים"}
        # Feature 069 decision #10: event_datetime is the COMPLETING message's
        # OWN persisted timestamp. Every webhook in this test carries the same
        # fixed epoch, so this is also the original agreement message's time -
        # never "now".
        messages_dir = (Path(denidin_app.ai_handler.session_manager.storage_dir)
                        / self._session(denidin_app).session_id / "messages")
        for e in events:
            completing = json.loads(
                (messages_dir / f"{e['message_id']}.json").read_text(encoding="utf-8")
            )
            assert e["event_datetime"] == event_datetime_for_message_ts(completing["timestamp"])

        # back-link on the turn-3 completing assistant message
        by_role = self._messages_by_role(denidin_app)
        assert sorted(by_role["assistant"][-1]["ledger_event_ids"]) == sorted(
            e["event_id"] for e in events)

    def test_us4_declined_approval_writes_nothing(self, denidin_app, monkeypatch):
        script = ScriptedOpenAI()
        script.queue_turn(
            h.reply_with_calls("מה השם המלא, האימייל והטלפון?",
                               [{"type": "mcp_call", "name": "resolve_client_name",
                                 "arguments": "{}", "output": json.dumps({"matches": []})}]),
            h.recognition_none())
        script.queue_turn(
            h.reply_with_calls("📋 לאישור — הוספת לקוח. כן/לא?",
                               [{"type": "function_call", "name": "add_client",
                                 "arguments": json.dumps({"name": "רון לוי",
                                                          "email": "r@e.com", "phone": "05200"})}]),
            h.recognition_none())
        script.queue_turn(h.reply("בוטל."), h.recognition_none())
        self._install(denidin_app, monkeypatch, script)

        self._send("הסכם שכר טרחה עם רון לוי, ריטיינר 4000", "u1")
        self._send("רון לוי, r@e.com, 05200", "u2")
        self._send("לא", "u3")

        assert self._events(denidin_app) == []

    # ================================================================== #
    # Phase 7 — US5: ambiguous client name
    # ================================================================== #

    def test_us5_one_candidate_listed_then_pick_captures(self, denidin_app, monkeypatch):
        script = ScriptedOpenAI()
        script.queue_turn(
            h.reply_with_calls(
                "מצאתי לקוח דומה: דנה כהן-לוי. להשתמש בו, או ליצור לקוח חדש?",
                [{"type": "mcp_call", "name": "resolve_client_name",
                  "arguments": json.dumps({"name": "דנה"}),
                  "output": json.dumps({"matches": [{"name": "דנה כהן-לוי"}]})}]),
            h.recognition_none())
        script.queue_turn(
            h.reply("מצוין, רשמתי מול דנה כהן-לוי."),
            self._recognize_verdict_for_trigger(
                denidin_app, h.agreement_event(client_name="דנה כהן-לוי")))
        self._install(denidin_app, monkeypatch, script)

        self._send("הסכם עם דנה, ריטיינר 4000 ו-12% הצלחה ו-750 לדיון", "u1")
        assert self._events(denidin_app) == []

        self._send("כן, דנה כהן-לוי", "u2")
        events = self._events(denidin_app)
        assert len(events) == 3
        assert {e["client_name"] for e in events} == {"דנה כהן-לוי"}

    def test_us5_ambiguous_disambiguation_then_abandonment(self, denidin_app, monkeypatch):
        script = ScriptedOpenAI()
        script.queue_turn(
            h.reply("מצאתי כמה: דנה כהן, דנה כהן-לוי. באיזו להשתמש, או ליצור חדש?"),
            h.recognition_none())
        script.queue_turn(h.reply("לא הבנתי — דנה כהן, דנה כהן-לוי, או חדש?"),
                          h.recognition_none())   # re-ask once
        script.queue_turn(h.reply("נחזור לזה בהמשך."), h.recognition_none())  # abandon
        self._install(denidin_app, monkeypatch, script)

        self._send("הסכם עם דנה, ריטיינר 4000", "u1")
        self._send("כן", "u2")
        self._send("לא משנה", "u3")

        assert self._events(denidin_app) == []

    # ================================================================== #
    # Phase 8 — US8: won't provide email/phone
    # ================================================================== #

    def test_us8_store_anyway_marks_description_and_creates_no_client(
        self, denidin_app, monkeypatch
    ):
        script = ScriptedOpenAI()
        script.queue_turn(h.reply("צריך אימייל וטלפון כדי להוסיף את הלקוח למורנינג."),
                          h.recognition_none())
        # operator declines -> single closed store-anyway question
        script.queue_turn(
            h.reply("לרשום את האירוע בלי שהלקוח מאומת במורנינג, או לא לרשום?"),
            h.recognition_none())
        # "store anyway": client_name is the operator's free text; the marker
        # phrase goes into the persisted description.
        marked = h.bank_event(
            client_name="רון מהשוק",
            description="הפקדה בנקאית [לקוח לא אומת במורנינג]")
        script.queue_turn(h.reply("נרשם."),
                          self._recognize_verdict_for_trigger(denidin_app, marked))
        self._install(denidin_app, monkeypatch, script)

        self._send("רון מהשוק העביר 5000 לחשבון", "u1")
        self._send("אין לי אימייל וטלפון שלו", "u2")
        self._send("תרשום בכל זאת", "u3")

        events = self._events(denidin_app)
        assert len(events) == 1
        assert "[לקוח לא אומת במורנינג]" in events[0]["description"]
        assert events[0]["client_name"] == "רון מהשוק"
        # no add_client approval prompt was ever emitted in the transcript
        assert not any("add_client" in json.dumps(kw.get("input") or [], ensure_ascii=False,
                                                  default=str)
                       for kw in script.main_calls)

    def test_us8_dont_store_emits_declined_breadcrumb_and_persists_nothing(
        self, denidin_app, monkeypatch, caplog
    ):
        caplog.set_level(logging.INFO)
        script = ScriptedOpenAI()
        script.queue_turn(h.reply("צריך אימייל וטלפון."), h.recognition_none())
        script.queue_turn(h.reply("לרשום בלי אימות, או לא?"), h.recognition_none())
        script.queue_turn(h.reply("בסדר, לא רושם."),
                          h.recognition_verdict(h.declined("הסכם", "רון מהשוק")))
        self._install(denidin_app, monkeypatch, script)

        self._send("הסכם עם רון מהשוק, ריטיינר 4000", "u1")
        self._send("אין לי", "u2")
        self._send("אל תרשום", "u3")

        assert self._events(denidin_app) == []
        declined_lines = [c for c in self._crumbs(caplog)
                          if c.startswith("[069] ledger capture declined by operator:")]
        assert len(declined_lines) == 1
        assert "reason=declined_by_operator" in declined_lines[0]
        assert "name='רון מהשוק'" in declined_lines[0]

    def test_us8_proactive_election_no_are_you_sure_turn(self, denidin_app, monkeypatch):
        marked = h.bank_event(
            client_name="רון מהשוק",
            description="הפקדה בנקאית [לקוח לא אומת במורנינג]")
        script = ScriptedOpenAI().queue_turn(
            h.reply("נרשם בלי אימות מול מורנינג."),
            self._recognize_verdict_for_trigger(denidin_app, marked))
        self._install(denidin_app, monkeypatch, script)

        notification = self._send(
            "רון מהשוק העביר 5000, תרשום גם בלי אימייל וטלפון", "u1")

        # honoured directly - exactly one turn, no "בטוח?" round-trip
        assert len(notification._test_sent_messages) == 1
        events = self._events(denidin_app)
        assert len(events) == 1
        assert "[לקוח לא אומת במורנינג]" in events[0]["description"]

    # ================================================================== #
    # Phase 9 — T025a: a recognised bank-deposit IMAGE routes through the
    # real router as a synthetic conversational turn → client resolution →
    # exactly one LedgerEvent (never persisted by MediaHandler itself).
    # ================================================================== #

    def _send_image(self, monkeypatch, denidin_app, extractor_result, msg_id="img1"):
        from whatsapp_chatbot_python import Notification
        media = denidin_app.whatsapp_handler.media_handler
        monkeypatch.setattr(media.image_extractor, "analyze_media",
                            lambda *a, **k: extractor_result)
        mfm = media.media_file_manager
        monkeypatch.setattr(mfm, "download_file", lambda *a, **k: (b"data", True))
        monkeypatch.setattr(mfm, "validate_file_size", lambda *a, **k: None)
        monkeypatch.setattr(mfm, "validate_format", lambda *a, **k: "image")
        import tempfile
        d = Path(tempfile.mkdtemp())
        monkeypatch.setattr(mfm, "create_storage_path", lambda *a, **k: d)
        monkeypatch.setattr(mfm, "save_file", lambda *a, **k: d / "DD-x.jpg")

        notification = Notification.__new__(Notification)
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'idMessage': msg_id,
            'timestamp': 1755331200,
            'senderData': {'chatId': GODFATHER_CHAT_ID, 'sender': GODFATHER_SENDER,
                           'senderName': 'Test Godfather'},
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {'downloadUrl': 'https://example.com/bank.jpg',
                                    'fileName': 'bank.jpg', 'mimeType': 'image/jpeg',
                                    'caption': ''},
            },
        }
        notification._test_sent_messages = []
        notification.answer = notification._test_sent_messages.append
        from denidin import handle_image_message
        handle_image_message(notification)
        return notification

    def test_bank_image_routes_synthetic_turn_and_persists_one_event(
        self, denidin_app, monkeypatch, caplog
    ):
        caplog.set_level(logging.INFO)
        script = ScriptedOpenAI().queue_turn(
            h.reply("רשמתי את ההפקדה של דנה כהן."),
            self._recognize_verdict_for_trigger(
                denidin_app, h.bank_event(client_name="דנה כהן", amount="9440")),
        )
        self._install(denidin_app, monkeypatch, script)

        extractor_result = {
            "raw_response": "בנק - הפקדה 9,440 ₪",
            "extracted_text": "אישור העברה בנקאית\nסכום: 9,440 ₪\nמוטב: דנה כהן",
            "ledger_events": [{
                "source_type": "בנק", "event_subtype": "הפקדה",
                "client_name": "דנה כהן", "amount": "9,440₪", "txn_date": None,
                "components": [],
            }],
        }
        notification = self._send_image(monkeypatch, denidin_app, extractor_result)

        # the operator saw the synthetic turn's reply, NOT the plain media summary
        assert notification._test_sent_messages == ["רשמתי את ההפקדה של דנה כהן."]

        events = self._events(denidin_app)
        assert len(events) == 1
        assert events[0]["source_type"] == "בנק"
        assert events[0]["client_name"] == "דנה כהן"

        # the stash text really did carry the verbatim extracted text into the turn
        assert any("אישור העברה בנקאית" in json.dumps(kw.get("input") or [],
                                                      ensure_ascii=False, default=str)
                   for kw in script.main_calls)

    def test_agreement_docx_routes_synthetic_turn_and_persists_one_event(
        self, denidin_app, monkeypatch
    ):
        """T028a (Phase 10): a fee-agreement DOCX → deterministic type signal →
        synthetic conversational turn → one הסכם LedgerEvent, never persisted by
        MediaHandler itself."""
        from whatsapp_chatbot_python import Notification
        media = denidin_app.whatsapp_handler.media_handler
        monkeypatch.setattr(media.docx_extractor, "analyze_media", lambda *a, **k: {
            "raw_response": "מסמך הסכם שכר טרחה עם רון לוי.",
            "extracted_text": "הסכם שכר טרחה בין עו\"ד לבין רון לוי. ריטיינר 1,500 ש\"ח.",
            "document_analysis": {"document_type": "הסכם", "summary": "", "key_points": []},
            "extraction_quality": "high", "warnings": [], "model_used": "python-docx",
        })
        mfm = media.media_file_manager
        monkeypatch.setattr(mfm, "download_file", lambda *a, **k: (b"data", True))
        monkeypatch.setattr(mfm, "validate_file_size", lambda *a, **k: None)
        monkeypatch.setattr(mfm, "validate_format", lambda *a, **k: "docx")
        import tempfile
        d = Path(tempfile.mkdtemp())
        monkeypatch.setattr(mfm, "create_storage_path", lambda *a, **k: d)
        monkeypatch.setattr(mfm, "save_file", lambda *a, **k: d / "DD-a.docx")

        script = ScriptedOpenAI().queue_turn(
            h.reply("רשמתי את ההסכם עם רון לוי."),
            self._recognize_verdict_for_trigger(
                denidin_app,
                h.agreement_event(client_name="רון לוי",
                                  components=[{"amount": "1500", "description": "ריטיינר"}])),
        )
        self._install(denidin_app, monkeypatch, script)

        notification = Notification.__new__(Notification)
        notification.event = {
            'typeWebhook': 'incomingMessageReceived', 'idMessage': 'doc1',
            'timestamp': 1755331200,
            'senderData': {'chatId': GODFATHER_CHAT_ID, 'sender': GODFATHER_SENDER,
                           'senderName': 'Test Godfather'},
            'messageData': {
                'typeMessage': 'documentMessage',
                'fileMessageData': {'downloadUrl': 'https://example.com/a.docx',
                                    'fileName': 'a.docx',
                                    'mimeType': 'application/vnd.openxmlformats-'
                                                'officedocument.wordprocessingml.document',
                                    'caption': ''},
            },
        }
        notification._test_sent_messages = []
        notification.answer = notification._test_sent_messages.append
        from denidin import handle_document_message
        handle_document_message(notification)

        assert notification._test_sent_messages == ["רשמתי את ההסכם עם רון לוי."]
        events = self._events(denidin_app)
        assert len(events) >= 1
        assert all(e["source_type"] == "הסכם" for e in events)
        assert events[0]["client_name"] == "רון לוי"
