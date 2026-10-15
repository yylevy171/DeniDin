"""
Component-Integration Test: Ledger Event Querying Conversation Routing
(Feature 044, T007a; updated for the no-turn redesign - Feature 067)

Verifies the full real path for querying ledger events: a real textMessage-shaped Green API
notification -> handle_text_message -> WhatsAppHandler -> Backbone -> the model loads
cap_ledger_query and calls query_ledger_events -> a real LedgerEventManager.query_events call
-> the result is handed back to the model, whose send_to_user reaches the (faked) Green API
bot. All real internal objects (CONSTITUTION SS V); only the OpenAI client and the Green API
bot are stood in for.

Does NOT exercise real conversational accuracy (whether the model decides to call
query_ledger_events at the right time, with sensible arguments) - that needs the real OpenAI
API and belongs in tests/billed/. What this DOES prove: given a scripted model that calls
query_ledger_events one or more times, the real wiring genuinely executes them against real
ledger data and hands back the real result. (Client-role gating is not tested here: the
backbone treats clients as out of scope for now - see Backbone._resolve_role.)

The app is built fresh per test on a throwaway data root, so no test data needs wiping.
"""
import json

import pytest

from tests.routing_test_support import (
    build_routing_app, function_call, nothing_more, send_to_user, text_notification,
)

GODFATHER_CHAT_ID = "972501234567@c.us"
GODFATHER_SENDER = "972501234567@c.us"


def _criteria_args(*pairs):
    """A query_ledger_events call's arguments from (text, hint) pairs - the 2026-08-24
    redesign's `criteria` shape (see src/managers/ledger_event_manager.py's _HINT_GROUPS)."""
    return {"criteria": [{"text": text, "hint": hint} for text, hint in pairs]}


def _multi_query(calls_args, rid="r2"):
    """One model response carrying SEVERAL query_ledger_events calls at once - the real shape
    of a multi-criterion question (research.md Decision 10)."""
    response = function_call("query_ledger_events", calls_args[0], call_id="call_0", rid=rid)
    for i, args in enumerate(calls_args[1:], start=1):
        extra = function_call("query_ledger_events", args, call_id=f"call_{i}").output[0]
        response.output.append(extra)
    return response


@pytest.mark.integration
class TestLedgerQueryRouting:

    @pytest.fixture
    def denidin_app(self, tmp_path, monkeypatch):
        app = build_routing_app(tmp_path, monkeypatch)
        yield app
        app.session_manager.close()

    def _seed(self, denidin_app, client_name, payer_name=None, source_type="הסכם",
              event_subtype="יצירה", amount="1,000₪", message_id="seed",
              timestamp=1786784400):  # 2026-08-15 local, unless overridden
        return denidin_app.ledger_event_manager.add_ledger_event(
            session_id="s", event={
                "source_type": source_type, "event_subtype": event_subtype,
                "client_name": client_name, "payer_name": payer_name,
                "description": "תיאור", "amount": amount,
                "percent": None, "percent_base": None, "hours": None,
                "hourly_rate": None, "txn_date": None,
                "vat_status": "כולל" if source_type == "הפקדה" else "לא צוין",
                "trigger_condition": None, "reference_hint": None,
                "agreement_label": "תיק" if source_type == "הסכם" else None,
                "component_label": "בסיס" if source_type == "הסכם" else None,
            },
            message_id=message_id, message_timestamp=timestamp,
        )

    def _ask(self, denidin_app, text, msg_id, *query_responses, reply="נמצא"):
        """Scripts the model: load the capability, run the given query response(s), send
        `reply`, pause - then delivers `text` through the real router entry. Returns the
        outputs handed back to the model for the queries (one list per query response)."""
        responses = [function_call("load_capabilities", {"capabilities": ["cap_ledger_query"]}, rid="r1")]
        responses += list(query_responses)
        responses += [send_to_user(reply, rid="r-send"), nothing_more()]
        denidin_app.ai_client.responses.create.side_effect = responses
        from denidin import handle_text_message
        handle_text_message(text_notification(GODFATHER_CHAT_ID, GODFATHER_SENDER, "Test Godfather", text, msg_id))
        calls = denidin_app.ai_client.responses.create.call_args_list
        return [calls[2 + i].kwargs["input"] for i in range(len(query_responses))]

    def test_query_ledger_events_call_dispatches_and_the_reply_is_sent(self, denidin_app):
        """Godfather asks about a past agreement; the model calls query_ledger_events against
        a real pre-seeded event, then sends its reply."""
        self._seed(denidin_app, "תומר אלוני", amount="5,000₪", message_id="seed_m1")
        query = function_call("query_ledger_events", _criteria_args(("תומר אלוני", "identity")), rid="r2")

        (handed_back,) = self._ask(denidin_app, "כמה סוכם עם תומר אלוני?", "integration_ledger_query_msg_1",
                                   query, reply="נמצא סכום 5,000")

        payload = json.loads(handed_back[0]["output"])
        assert payload["count"] == 1 and payload["matches"][0]["client_name"] == "תומר אלוני"
        assert denidin_app.green_api_bot.sent == [(GODFATHER_CHAT_ID, "נמצא סכום 5,000")]

    def test_payer_name_search_dispatches_correctly_over_the_real_route(self, denidin_app):
        """Payer-name search (T008 scenario 4), mechanics-only: finds an event by its
        payer_name (not client_name) end-to-end. payer_name is a real insurer proper noun
        ("מגדל"), matching this codebase's own real data convention."""
        self._seed(denidin_app, "דניאל פרץ", payer_name="מגדל", amount="3,000₪", message_id="seed_payer_m1")
        query = function_call("query_ledger_events", _criteria_args(("מגדל", "identity")), rid="r2")

        (handed_back,) = self._ask(denidin_app, "האם קיבלנו תשלום ממגדל?", "integration_ledger_query_payer_1", query)

        payload = json.loads(handed_back[0]["output"])
        assert payload["count"] == 1
        assert payload["matches"][0]["payer_name"] == "מגדל"

    def test_both_confirmed_candidates_issues_two_calls_and_merges_over_the_real_route(self, denidin_app):
        """The 'both/all' follow-up after disambiguation (T009 scenario 2), mechanics-only:
        TWO query_ledger_events calls in one response are both executed and each answered
        under its own call_id."""
        self._seed(denidin_app, "מיכל רוזן", amount="1,000₪", message_id="seed_both_m1")
        self._seed(denidin_app, "בני אשכנזי", amount="2,000₪", message_id="seed_both_m2")
        queries = _multi_query([_criteria_args(("מיכל רוזן", "identity")),
                                _criteria_args(("בני אשכנזי", "identity"))])

        (handed_back,) = self._ask(denidin_app, "גם וגם", "integration_ledger_query_both_1", queries)

        assert len(handed_back) == 2
        by_call_id = {item["call_id"]: json.loads(item["output"]) for item in handed_back}
        names_found = {item["matches"][0]["client_name"] for item in by_call_id.values() if item.get("count") == 1}
        assert names_found == {"מיכל רוזן", "בני אשכנזי"}

    def test_monthly_income_aggregation_date_only_query_over_the_real_route(self, denidin_app):
        """Monthly income aggregation (T010 scenario 3), mechanics-only: a broad, client-less,
        category-only query (research.md Decision 11 - "income" means received, not agreed)
        includes only the deposit event and excludes an agreed-but-unpaid one. The model
        itself keeps only the right month (a model-reasoning concern - see tests/billed/)."""
        self._seed(denidin_app, "דנה פלד", source_type="הפקדה", event_subtype="בנק",
                   amount="4,000₪", message_id="seed_income_m1", timestamp=1785920400)
        self._seed(denidin_app, "אלון שני", amount="9,000₪", message_id="seed_income_m2", timestamp=1785920400)
        query = function_call("query_ledger_events", _criteria_args(("בנק", "event_type")), rid="r2")

        (handed_back,) = self._ask(denidin_app, "כמה הכנסות היו לי באוגוסט?", "integration_ledger_query_income_1",
                                   query, reply='סה"כ הכנסות: 4,000')

        payload = json.loads(handed_back[0]["output"])
        assert payload["count"] == 1
        assert payload["matches"][0]["source_type"] == "הפקדה"
        assert payload["matches"][0]["amount"] == 4000

    def test_four_way_multi_criterion_with_date_range_issues_four_calls_over_the_real_route(self, denidin_app):
        """A genuine multi-criterion request (T011), mechanics-only: N criteria, unbounded -
        FOUR separately-named clients, each call ALSO carrying a date criterion (identity AND
        date at once; "date" is just another ANDed {text, hint} criterion, not a range filter)."""
        clients = [("נועה שדה", "2,000₪"), ("אבי גולן", "3,000₪"), ("שירה מזרחי", "4,000₪"), ("אלעד ברק", "5,000₪")]
        for i, (name, amount) in enumerate(clients):
            self._seed(denidin_app, name, amount=amount, message_id=f"seed_four_m{i}", timestamp=1786784400)
        queries = _multi_query([_criteria_args((name, "identity"), ("08/2026", "date")) for name, _ in clients])

        (handed_back,) = self._ask(
            denidin_app, "מה סוכם באוגוסט עם נועה שדה, אבי גולן, שירה מזרחי או אלעד ברק?",
            "integration_ledger_query_four_1", queries)

        assert len(handed_back) == 4
        amounts_by_client = {}
        for item in handed_back:
            payload = json.loads(item["output"])
            if payload.get("count") == 1:
                amounts_by_client[payload["matches"][0]["client_name"]] = payload["matches"][0]["amount"]
        assert amounts_by_client == {"נועה שדה": 2000, "אבי גולן": 3000, "שירה מזרחי": 4000, "אלעד ברק": 5000}
