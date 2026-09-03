"""
Shared harness for the Feature 069 post-turn ledger-recognition integration tests
(`test_ledger_client_resolution_routing.py`).

Everything here is component-integration infrastructure (CONSTITUTION §V): the real
router, real `AIHandler` / `SessionManager` / `LedgerEventManager` /
`PendingApprovalManager`, real `denidin.py` dispatch. The ONLY stand-in is the
OpenAI client's `responses.create` - scripted per turn so a test can drive a
multi-turn client-resolution detour deterministically without a real model call
(real model judgement is `tests/billed/`, Phase 11).

Not collected by pytest (leading underscore); imported by the test module.
"""
import json
from collections import deque
from types import SimpleNamespace

RECOGNITION_TOOL_NAME = "report_ledger_recognition"

GODFATHER_CHAT_ID = "972501234567@c.us"
GODFATHER_SENDER = "972501234567@c.us"


# --------------------------------------------------------------------------- #
# Response builders - Responses-API-shaped SimpleNamespaces
# --------------------------------------------------------------------------- #

def _usage():
    return SimpleNamespace(total_tokens=8, input_tokens=6, output_tokens=2)


def reply(text: str, *, resp_id: str = "resp_main"):
    """A plain conversational reply (no tool calls)."""
    return SimpleNamespace(id=resp_id, output=[], output_text=text,
                           model="gpt-5.6-luna", usage=_usage())


def reply_with_calls(text: str, calls, *, resp_id: str = "resp_main_calls"):
    """A conversational turn that also emitted one or more items.

    `calls` is a list of dicts: {"type": "function_call"|"mcp_call", "name", ...}.
    function_call → {"name", "arguments" (json str), "call_id"}.
    mcp_call      → {"name", "arguments", "output", "error"}.
    """
    output = []
    for c in calls:
        if c["type"] == "mcp_call":
            output.append(SimpleNamespace(
                type="mcp_call", name=c["name"], error=c.get("error"),
                arguments=c.get("arguments", "{}"), output=c.get("output", ""),
            ))
        else:
            output.append(SimpleNamespace(
                type="function_call", name=c["name"],
                arguments=c.get("arguments", "{}"),
                call_id=c.get("call_id", f"call_{c['name']}"),
            ))
    return SimpleNamespace(id=resp_id, output=output, output_text=text,
                           model="gpt-5.6-luna", usage=_usage())


def recognition_verdict(payload: dict, *, resp_id: str = "resp_recognition"):
    """A `report_ledger_recognition` function-call carrying `payload`."""
    return SimpleNamespace(
        id=resp_id, output_text="", model="gpt-5.6-luna", usage=_usage(),
        output=[SimpleNamespace(
            type="function_call", name=RECOGNITION_TOOL_NAME,
            arguments=json.dumps(payload, ensure_ascii=False),
            call_id="call_recognition",
        )],
    )


def recognition_none(*, resp_id: str = "resp_recognition_none"):
    """The recognition call deliberately reported verdict='none' (the model DID
    call the tool - an empty output would instead look like a parse failure and
    burn the one-shot retry)."""
    return recognition_verdict({"verdict": "none"}, resp_id=resp_id)


def recognition_silent(*, resp_id: str = "resp_recognition_silent"):
    """The recognition call emitted nothing at all → one-shot retry, then
    normalized to {"verdict": "none"}."""
    return SimpleNamespace(id=resp_id, output=[], output_text="",
                           model="gpt-5.6-luna", usage=_usage())


# --------------------------------------------------------------------------- #
# Scripted OpenAI client
# --------------------------------------------------------------------------- #

class ScriptedOpenAI:
    """Stands in for `ai_handler.client.responses.create`.

    Two independent FIFO queues: `main` (conversational + approval-resolution
    turns) and `recognition` (the post-turn `report_ledger_recognition` call,
    identified by its tool). An exhausted queue falls back to a benign default
    (a bland reply / a `none` verdict) so an unexpected extra call never blows
    up a test for the wrong reason. Every call's kwargs are recorded.
    """

    def __init__(self):
        self.main = deque()
        self.recognition = deque()
        self.main_calls = []
        self.recognition_calls = []
        self._default_reply = "בסדר"

    def queue_turn(self, main_response, recognition_response=None):
        """Queue one operator turn: its main reply and (optionally) its
        post-turn recognition verdict."""
        self.main.append(main_response)
        if recognition_response is not None:
            self.recognition.append(recognition_response)
        return self

    def queue_recognition(self, recognition_response):
        self.recognition.append(recognition_response)
        return self

    @staticmethod
    def _is_recognition(kwargs) -> bool:
        return any(
            isinstance(t, dict) and t.get("name") == RECOGNITION_TOOL_NAME
            for t in (kwargs.get("tools") or [])
        )

    @staticmethod
    def _resolve(item):
        """A queued item may be a callable (deferred until the call actually
        happens - e.g. so a recognition verdict can name a trigger message id
        that only exists once the turn has persisted its messages)."""
        return item() if callable(item) else item

    def __call__(self, **kwargs):
        if self._is_recognition(kwargs):
            self.recognition_calls.append(kwargs)
            if self.recognition:
                return self._resolve(self.recognition.popleft())
            return recognition_none()
        self.main_calls.append(kwargs)
        if self.main:
            return self._resolve(self.main.popleft())
        return reply(self._default_reply)


# --------------------------------------------------------------------------- #
# Verdict / event payload builders
# --------------------------------------------------------------------------- #

_EVENT_DEFAULTS = {
    "source_type": None, "event_subtype": None, "client_name": None,
    "description": None, "vat_status": None, "payer_name": None,
    "amount": None, "txn_date": None, "components": [], "component_count": 0,
    "bank_number": None, "bank_branch": None, "bank_account": None,
    "accounting_document_display_number": None, "reference": None,
    "reference_hint": None,
}


def event(**overrides) -> dict:
    e = dict(_EVENT_DEFAULTS)
    e.update(overrides)
    if e["components"] and not e["component_count"]:
        e["component_count"] = len(e["components"])
    return e


def complete(trigger_message_id: str, ev: dict) -> dict:
    return {"verdict": "complete", "trigger_message_id": trigger_message_id, "event": ev}


def declined(source_type: str, client_name_stated: str) -> dict:
    return {"verdict": "declined", "source_type": source_type,
            "client_name_stated": client_name_stated, "reason": "declined_by_operator"}


def none_verdict() -> dict:
    return {"verdict": "none"}


def agreement_event(**overrides) -> dict:
    base = dict(
        source_type="הסכם", event_subtype="יצירה", client_name="דנה כהן",
        description="הסכם שכר טרחה", payer_name="איגוד העובדים",
        components=[
            {"amount": "4000", "percent": None, "percent_base": None,
             "trigger_condition": None, "hours": None, "hourly_rate": None,
             "description": "ריטיינר חודשי"},
            {"amount": None, "percent": "12", "percent_base": "פיצוי",
             "trigger_condition": "עם קבלת פיצוי", "hours": None, "hourly_rate": None,
             "description": "בונוס הצלחה"},
            {"amount": "750", "percent": None, "percent_base": None,
             "trigger_condition": "לכל דיון", "hours": None, "hourly_rate": None,
             "description": "תשלום לדיון"},
        ],
    )
    base.update(overrides)
    return event(**base)


def bank_event(**overrides) -> dict:
    base = dict(
        source_type="בנק", event_subtype="הפקדה", client_name="דנה כהן",
        description="הפקדה בנקאית מהלקוחה", amount="5000", txn_date="2026-07-15",
        bank_number="12", bank_branch="345", bank_account="678901",
    )
    base.update(overrides)
    return event(**base)


def invoice_event(**overrides) -> dict:
    base = dict(
        source_type="חשבונית", event_subtype="חשבונית מס/קבלה", client_name="דנה כהן",
        description="עסקה משולבת", amount="4000", txn_date="2026-07-15",
        vat_status="כולל", accounting_document_display_number="1042",
        components=[{}],
    )
    base.update(overrides)
    return event(**base)
