"""E2E Tests (Feature 018): create_invoice approval flow + add_client
(Feature 026) - real webhook, real OpenAI Responses API, real Morning MCP
server, real Morning sandbox.

Split (2026-08-04, Feature 038, human-approved T012/T013) from the former
single test_denidin_morning_mcp_e2e.py (2094 lines, ~40 tests) into this
file plus test_denidin_morning_client_management_e2e.py,
test_denidin_morning_list_invoices_e2e.py, and
test_denidin_morning_invoice_lifecycle_e2e.py - pure reorganization, no test
logic changed. Shared fixtures (`denidin_app`, `denidin_config`,
`live_morning_tunnel`) live in this directory's conftest.py (auto-discovered,
no import needed); shared helpers/constants
(`_send_turn`/`_send_turn_and_approve`/`_send_turn_and_decline`/`_calls_for`/
`_unique_client_name`/`_random_amount`/`_random_description`/
`_random_seed_email`/`_SEED_PHONE`/`GODFATHER_CHAT_ID`) live in
denidin_mcp_e2e_helpers.py.

Flow (entry point is the real Green API webhook, dispatched through the
actual @bot.router.message-decorated `handle_text_message` - CONSTITUTION
§V):

    Green API textMessage webhook (godfather sender)
      -> handle_text_message (real router handler, not a direct internal call)
      -> WhatsAppHandler.process_notification
      -> AIHandler.get_response
           -> client.responses.create (real OpenAI Responses API call)
              with the real Morning MCP server registered as a remote tool
              (reached over its already-open ngrok tunnel, bearer-authenticated)
      -> bot replies in Hebrew

**Prompts portray a real, non-technical user (2026-07-14 decision)**: the
user never knows about tools, parameter names, or internal ids (Morning
documentId GUIDs) - only casual references a person would actually use.

**Two-tier turn behavior (Feature 022/023/026)**: every document-creating
tool (create_invoice, create_transaction_account, create_combo_document,
create_credit_note, create_receipt, close_transaction_account), plus
add_client/update_client (Feature 026), requires explicit human approval
before it executes - see `_send_turn_and_approve`/`_send_turn_and_decline`
in denidin_mcp_e2e_helpers.py. Read-only tools (list_invoices,
get_invoice_details, get_financial_summary, download_invoice_pdf,
list_clients, get_client_details) remain single-turn.

NO MOCKING anywhere. @pytest.mark.billed: real OpenAI billing on every run,
can be run freely - no per-run approval, no one-at-a-time restriction (see
CLAUDE.md/CONSTITUTION §VII).
"""
from __future__ import annotations

import pytest

from .denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _SEED_PHONE,
    _calls_for,
    _random_amount,
    _random_description,
    _random_seed_email,
    _send_turn,
    _send_turn_and_approve,
    _send_turn_and_decline,
    _unique_client_name,
)

# ============================================================================
# create_invoice
# ============================================================================

@pytest.mark.billed
def test_godfather_creates_invoice_via_whatsapp(denidin_app):
    """Godfather asks for a new invoice the way a real, non-technical person
    would - client name, amount, and what it's for, all in one message.
    Since create_invoice creates a document, it now requires explicit
    approval (Feature 022): the ASK turn must NOT execute it yet, and only
    the APPROVE turn (an explicit Hebrew "כן") actually calls the tool.

    Verification (independent signals, not the model's unverified claim alone):
    1. ASK turn: no create_invoice call yet.
    2. APPROVE turn: mcp_calls shows a create_invoice call with no error.
    3. The final reply contains an invoice link - the runtime constitution
       says create_invoice confirmations must always include one, unprompted,
       so this isn't a special ask in the test prompt.

    Uses a fresh unique client per run (2026-07-28) - this test used to
    create a new real invoice under the fixed "יוסי שמואלי" ground-truth
    client (see bugfix-014 tests below) on every single run, which is
    exactly what caused that client to organically grow from 6 to 14
    documents over time and break those other tests' pagination
    assumptions. Never hardcode a shared ground-truth client name here.
    """
    client_name = _unique_client_name()
    amount = _random_amount()
    description = _random_description()

    (ask_response, ask_ai_response), (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}",
        id_prefix="E2E_CREATE",
    )

    assert not _calls_for(ask_ai_response, "create_invoice"), (
        f"create_invoice executed on the ASK turn before approval was given: "
        f"{ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    create_calls = _calls_for(ai_response, "create_invoice")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert create_calls, (
        f"Model never invoked create_invoice via the remote MCP server, even "
        f"after approving. mcp_calls: {ai_response.mcp_calls!r}. "
        f"Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in create_calls), (
        f"create_invoice call(s) reported an error: {create_calls}"
    )
    assert any(client_name in (c["arguments"] or "") for c in create_calls), (
        f"create_invoice was not called with the client name {client_name!r}: {create_calls!r}"
    )

    # The reply must actually carry a link, not just confirm success in the abstract.
    assert "http" in response, (
        f"Bot reply did not include an invoice link. Full reply: {response!r}"
    )


@pytest.mark.billed
def test_godfather_declines_invoice_creation(denidin_app):
    """Godfather asks for a new invoice, then explicitly declines the pending
    approval (Feature 022) - create_invoice must never fire, and the bot's
    reply should read like an acknowledgment of the decline, not a fabricated
    success."""
    client_name = "דנה כהן"
    amount = _random_amount()
    description = _random_description()

    response, ai_response = _send_turn_and_decline(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}",
        id_prefix="E2E_CREATE_DECLINE",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ai_response, "create_invoice"), (
        f"create_invoice executed despite an explicit decline: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )
    assert "http" not in response, (
        f"Bot reply looks like a fabricated success (contains a link) despite "
        f"the decline. Full reply: {response!r}"
    )


@pytest.mark.billed
def test_godfather_ignores_pending_approval_with_unrelated_message(denidin_app):
    """Godfather triggers a pending create_invoice approval, then sends an
    unrelated message instead of yes/no (Feature 022). This must be treated
    as an implicit decline: create_invoice never fires, and the unrelated
    message gets a normal, on-topic reply (proves fall-through to a fresh
    turn works, and that the app doesn't get stuck)."""
    client_name = "משה לוי"
    amount = _random_amount()
    description = _random_description()

    _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}",
        id_prefix="E2E_CREATE_UNRELATED_ASK",
    )
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="מה השעה עכשיו?",
        id_prefix="E2E_CREATE_UNRELATED_FOLLOWUP",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ai_response, "create_invoice"), (
        f"create_invoice executed despite an unrelated follow-up message: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )


@pytest.mark.billed
def test_godfather_approval_survives_intervening_small_talk(denidin_app):
    """An implicitly-declined pending approval (Feature 022) must not leave
    the app stuck: after unrelated small talk clears the pending request,
    the user can simply re-ask and complete the approval flow normally."""
    client_name = "רותי אברהם"
    amount = _random_amount()
    description = _random_description()
    request_text = f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}"

    _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=request_text,
        id_prefix="E2E_SMALLTALK_ASK1",
    )
    _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="איזה מזג אוויר יש היום?",
        id_prefix="E2E_SMALLTALK_INTERRUPT",
    )

    # Re-issue the original request and approve normally this time.
    _, (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=request_text,
        id_prefix="E2E_SMALLTALK_RETRY",
    )
    create_calls = _calls_for(ai_response, "create_invoice")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert create_calls and create_calls[0]["error"] is None, (
        f"Re-issued create_invoice request did not succeed after an "
        f"intervening, implicitly-declined pending approval: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )


@pytest.mark.billed
def test_godfather_add_client_requires_approval(denidin_app):
    """🚨 CONSTITUTION §VIII flagged exception (spec.md Clarifications round 1,
    explicitly human-approved): replaces test_godfather_add_client_still_
    single_turn's regression guard. add_client now creates a real, persisted
    client record - Feature 026 moves it into APPROVAL_REQUIRED_MCP_TOOLS,
    reversing its prior single-turn behavior.

    Verification (independent signals, not the model's unverified claim
    alone):
    1. ASK turn: add_client must NOT execute yet.
    2. APPROVE turn: mcp_calls shows an add_client call with no error.
    3. A follow-up get_client_details turn (same test, real WhatsApp
       round-trip) confirms the client was actually created and its phone
       number persisted in normalized Israeli dashed format
       (REQ-CLIENT-016/017), same standard as the sandbox-level
       test_add_client_tool_normalizes_and_persists_phone test.
    """
    client_name = _unique_client_name()
    seed_email = _random_seed_email()
    raw_phone = "+972501234567"  # international input - must normalize on read-back

    (ask_response, ask_ai_response), (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {client_name}, מייל {seed_email}, טלפון {raw_phone}",
        id_prefix="E2E_ADD_CLIENT_APPROVE",
    )

    assert not _calls_for(ask_ai_response, "add_client"), (
        f"add_client executed on the ASK turn before approval was given: "
        f"{ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )
    add_calls = _calls_for(ai_response, "add_client")
    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert add_calls and add_calls[0]["error"] is None, (
        f"add_client did not succeed on the APPROVE turn: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )

    # Search-index lag (research.md Decision 8) - cost-free local sleep,
    # cheaper than retrying a whole billed conversational turn.
    time.sleep(3)

    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"פרטים על הלקוח {client_name}",
        id_prefix="E2E_ADD_CLIENT_VERIFY",
    )
    detail_calls = _calls_for(details_ai_response, "get_client_details")

    # Asserts the FINAL user-facing reply is correct and meaningful - NOT
    # that every intermediate get_client_details attempt succeeded. A real
    # run (2026-08-03) showed the model can genuinely recover from its own
    # mistakes within one turn (e.g. a wrong argument casing on one attempt)
    # via a retry or list_clients fallback - exactly the resilience you want
    # from a real assistant, not a bug. What actually matters - and what
    # this checks, deterministically - is whether the user got the client's
    # REAL data back: the normalized phone number appearing in the reply is
    # airtight proof of a genuinely correct answer, since a generic "not
    # found"/failure reply could never accidentally contain it.
    if detail_calls and any(c["error"] is not None for c in detail_calls):
        logger.warning(
            f"get_client_details had at least one failed attempt this turn "
            f"before the final reply was produced - model self-corrected, "
            f"not asserted on here, but worth eyeballing if this recurs: "
            f"{detail_calls!r}"
        )
    assert detail_calls, (
        f"Model never invoked get_client_details when verifying the newly "
        f"created client: "
        f"{details_ai_response.mcp_calls if details_ai_response else None!r}"
    )
    assert "050-1234567" in details_response, (
        f"Expected the normalized Israeli phone format in the follow-up "
        f"details reply, got: {details_response!r}"
    )


@pytest.mark.billed
def test_godfather_add_client_missing_field_is_asked_for(denidin_app):
    """Omitting email or phone must make the model ask for it, never call
    add_client with a guessed/blank value (runtime_constitution.md's
    "add_client needs name, email, AND phone" guidance, added by Feature
    026's T015)."""
    client_name = _unique_client_name()

    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {client_name}",
        id_prefix="E2E_ADD_CLIENT_MISSING",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ai_response, "add_client"), (
        f"add_client executed despite missing email/phone - should have "
        f"asked for the missing field(s) instead: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )


@pytest.mark.billed
def test_godfather_add_client_rejects_malformed_email(denidin_app):
    """A malformed email must never result in a fabricated success. Two
    acceptable outcomes (asserted on whichever actually happens, not assumed
    in advance): either the model recognizes the malformed address itself
    and asks for a valid one without ever calling add_client (no pending
    approval at all), or it calls add_client anyway, the pending approval is
    granted, and the tool's own _validate_email rejection (ValueError ->
    friendly error, tools.py) surfaces as a real error on that mcp_call - not
    a fabricated "created" confirmation."""
    client_name = _unique_client_name()

    ask_response, ask_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {client_name}, מייל not-an-email, טלפון {_SEED_PHONE}",
        id_prefix="E2E_ADD_CLIENT_BADEMAIL_ASK",
    )
    ask_add_calls = _calls_for(ask_ai_response, "add_client")

    assert ask_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"

    if not ask_add_calls:
        # Model itself declined to call the tool with an invalid email - no
        # pending approval was ever created, nothing further to check.
        return

    # Model called add_client anyway (approval gate fires on tool name only,
    # not argument validity - research.md Decision 7) - approve it and
    # confirm the malformed email surfaces as a real error.
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="כן",
        id_prefix="E2E_ADD_CLIENT_BADEMAIL_APPROVE",
    )
    add_calls = _calls_for(ai_response, "add_client")
    assert add_calls, (
        f"Pending add_client approval never resolved into an actual "
        f"mcp_call after approving. "
        f"mcp_calls: {ai_response.mcp_calls if ai_response else None!r}"
    )
    assert any(c["error"] is not None for c in add_calls), (
        f"Expected the malformed email to surface as an error on the "
        f"add_client call, got: {add_calls}"
    )


@pytest.mark.billed
def test_godfather_declines_add_client(denidin_app):
    """Godfather asks to add a client, then explicitly declines the pending
    approval - add_client must never fire, and the bot's reply should read
    like an acknowledgment of the decline, not a fabricated success (mirrors
    test_godfather_declines_invoice_creation's pattern)."""
    client_name = _unique_client_name()
    seed_email = _random_seed_email()

    response, ai_response = _send_turn_and_decline(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תוסיף לקוח חדש בשם {client_name}, מייל {seed_email}, טלפון {_SEED_PHONE}",
        id_prefix="E2E_ADD_CLIENT_DECLINE",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ai_response, "add_client"), (
        f"add_client executed despite an explicit decline: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )


