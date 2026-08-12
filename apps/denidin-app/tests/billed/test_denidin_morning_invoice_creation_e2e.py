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

import logging
import time

import pytest

from .denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _SEED_PHONE,
    _calls_for,
    _client_name_exact_match_found,
    _complete_add_client_flow,
    _fresh_nonexistent_client_name,
    _normalize_hebrew_geresh,
    _is_genuine_document_creation,
    _is_real_approval_prompt,
    _random_amount,
    _random_description,
    _random_seed_email,
    _seed_fresh_client,
    _send_turn,
    _send_turn_and_approve,
    _send_turn_and_decline,
    _unique_client_name,
)

logger = logging.getLogger(__name__)

# ============================================================================
# bugfix-039 (expanded 2026-08-11): permanent ground-truth clients for
# T1/T2 below. Seeded ONCE, out of band - not by this test file - and
# reused on every run instead of a fresh add_client conversation each time
# (user decision 2026-08-11: fewer OpenAI calls, no per-run collision risk).
# Full registry of every such permanent fixture this test suite depends on
# (including these two): GROUND_TRUTH_CLIENTS.md, alongside this file - read
# that file before wiping/resetting the sandbox, and re-run its documented
# one-time seed step afterward or these two tests will fail on a genuine
# "client not found" (not a regression).
# ============================================================================
GROUND_TRUTH_T1_CLIENT_NAME = "זהבית צור"
GROUND_TRUTH_T1_CLIENT_TYPED_VARIANT = "זהבית צורן"  # one letter added to the surname
GROUND_TRUTH_T2_CLIENT_NAME = "כרמלי דודי"
GROUND_TRUTH_T2_CLIENT_TYPED_VARIANT = "כרמלי דוד"  # one letter removed from the first name

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

    Feature 027: create_invoice now resolves client_name against a real
    client record before creating anything - the client must be seeded via
    a real add_client conversation first (see US1's happy-path test below
    for the dedicated, from-scratch version of this same flow).
    """
    amount = _random_amount()
    description = _random_description()
    client_name, _, _ = _seed_fresh_client(GODFATHER_CHAT_ID, id_prefix="E2E_CREATE")

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
    amount = _random_amount()
    description = _random_description()
    client_name, _, _ = _seed_fresh_client(GODFATHER_CHAT_ID, id_prefix="E2E_SMALLTALK")
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
    # Feature 027: "no error" alone isn't proof of real success anymore - a
    # "client not found" refusal is also a normal (error=None) tool return.
    # An actual link is airtight proof the document was really created.
    assert "http" in response, (
        f"Bot reply did not include an invoice link - possibly a silent "
        f"'client not found' refusal rather than a real success. Full reply: {response!r}"
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




# ============================================================================
# Feature 027: mandatory client reference for document creation
#
# create_invoice (and its Group A siblings) now resolve their client_name
# against a real Morning client record before creating anything - these
# tests drive the 7 flows the human explicitly asked to cover. "Verified via
# Morning" at this E2E layer means the real create_invoice/get_invoice_details
# mcp_call's own `output` (produced by a real call the morning-mcp-app server
# already made against the live Morning sandbox) - never a raw MorningClient
# call, per this module's app-wall (denidin-app never imports morning-mcp-app
# code or credentials).
# ============================================================================

@pytest.mark.billed
def test_create_document_for_existing_client_happy_path(denidin_app):
    """1. Happy path: client already exists under the given name -> the
    document is created attached to that real client, verified via a real
    follow-up get_invoice_details call, and the user is informed with a
    normal confirmation (a real invoice link)."""
    amount = _random_amount()
    description = _random_description()
    client_name, _, _ = _seed_fresh_client(GODFATHER_CHAT_ID, id_prefix="E2E_027_HAPPY")

    (ask_response, ask_ai_response), (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}",
        id_prefix="E2E_027_HAPPY",
    )

    assert not _calls_for(ask_ai_response, "create_invoice"), (
        f"create_invoice executed before approval: {ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )
    create_calls = _calls_for(ai_response, "create_invoice")
    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert create_calls and create_calls[0]["error"] is None, (
        f"create_invoice did not succeed for an existing client: {ai_response.mcp_calls!r}"
    )
    assert "http" in response, f"Bot reply did not include an invoice link: {response!r}"
    # Geresh-normalized: create_invoice's own arguments echo the CONFIRMED
    # exact name resolve_client_name disclosed (client-name-resolution
    # architecture, 2026-08-12), which is Morning's own normalized form - a
    # client_name containing a raw ASCII/typographic apostrophe (e.g.
    # "לוסי צ'ורנוב") won't match verbatim against that (e.g. "לוסי צ׳ורנוב").
    assert _normalize_hebrew_geresh(client_name) in (create_calls[0]["arguments"] or ""), (
        f"create_invoice was not called with {client_name!r}: {create_calls!r}"
    )

    # Verified via Morning: a real follow-up get_invoice_details call
    # independently confirms the document exists and names this client.
    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"מה הפרטים של החשבונית של {client_name}?",
        id_prefix="E2E_027_HAPPY_VERIFY",
    )
    details_calls = _calls_for(details_ai_response, "get_invoice_details") + _calls_for(
        details_ai_response, "list_invoices"
    )
    combined_output = "\n".join(c["output"] or "" for c in details_calls)
    assert _normalize_hebrew_geresh(client_name) in combined_output, (
        f"Follow-up real Morning lookup did not confirm the invoice for "
        f"{client_name!r}: {combined_output!r}. Bot reply: {details_response!r}"
    )


def _run_similarly_named_client_flow(real_name: str, typed_name: str, id_prefix: str):
    """Drive the bugfix-039 (expanded 2026-08-11) flow: ask for a document
    under a name that's only a non-exact match of a real, already-existing
    client, and follow the conversation with "כן" answers until either a
    real document is created or a bounded turn limit is hit.

    `real_name` must already exist as a real Morning client BEFORE this is
    called - see GROUND_TRUTH_CLIENTS.md for the permanent, one-time-seeded
    fixtures this is designed around (user decision, 2026-08-11: seed once,
    reuse forever, rather than a fresh add_client conversation - 2 OpenAI
    calls - on every single run). This helper itself does no seeding and
    has no opinion on where `real_name` came from.

    Returns (turns, amount, description) where `turns` is the ordered list
    of (response, ai_response) for every turn sent, so callers can assert on
    the *shape* of the conversation (no document created before a
    confirmation question naming the real client is shown), not just the
    final outcome.

    Bounded at 4 answer turns: per the real MCP approval mechanics
    (APPROVAL_REQUIRED_MCP_TOOLS - every create_invoice attempt, resolved or
    not, gets its own pending-approval gate), a non-exact match can take up
    to 2 full attempt+approve rounds (attempt with the typed name -> real
    tool resolution refuses with a confirmation question -> attempt again
    with the confirmed exact name -> real creation) - more turns than the
    bare 2-question exchange in isolation, since the pre-execution approval
    gate applies to each attempt independently of the confirmation
    question. This helper does not assume which shape occurs; it drives
    turns until settled and lets the caller check what actually happened.

    Real failure (2026-08-13): a blind "כן" every round doesn't work - a
    live run got an identity "did you mean X, or create new Y?" question,
    then several rewordings of a "pick 1 or 2" multi-choice, none of which
    "כן" can correctly answer (none are yes/no questions), so the loop never
    reached the real approval gate. Fixed: each round answers "כן" ONLY when
    the prior response is the real approval prompt (`_is_real_approval_prompt`
    - the "...לאישור... כן/לא?" gate); otherwise it answers with the exact
    `real_name`, which is always a valid, unambiguous answer to either
    question shape.
    """
    amount = _random_amount()
    description = _random_description()

    turns = [
        _send_turn(
            chat_id=GODFATHER_CHAT_ID,
            text=f"תפיק חשבונית חדשה עבור {typed_name} על סך {amount} שח עבור {description}",
            id_prefix=f"{id_prefix}_ASK",
        )
    ]
    for i in range(4):
        response, ai_response = turns[-1]
        if response is not None and any(
            _is_genuine_document_creation(call) for call in _calls_for(ai_response, "create_invoice")
        ):
            break
        answer = "כן" if _is_real_approval_prompt(response) else real_name
        turns.append(_send_turn(chat_id=GODFATHER_CHAT_ID, text=answer, id_prefix=f"{id_prefix}_YES{i}"))

    return turns, amount, description


def _assert_similarly_named_client_flow_succeeded(turns, real_name: str, typed_name: str):
    """Shared assertions for both T1/T2 cases below (bugfix-039, expanded
    2026-08-11): a document must eventually be created, attached to the
    REAL client - and no create_invoice call along the way may ever succeed
    for anything else (never a wrong/guessed client, never a duplicate under
    a different name).

    Deliberately does NOT assert the confirmation question is the mechanism
    that gets there: the seed step runs in the same live session immediately
    before the ask, so the model sometimes already has the real name in its
    own recent context and self-corrects before ever calling create_invoice
    with the wrong one (observed live, 2026-08-11) - a perfectly good
    outcome, not a bug, and not something a test should force a specific
    shape onto. The tool-level mechanism itself (refuse-and-ask on a
    non-exact match, never silently create) is already locked down
    unambiguously by test_morning_sandbox_create_invoice_client_resolution.py
    in apps/morning-mcp-app, which calls create_invoice directly with no
    surrounding conversation to leak context from. This test's job is only
    to confirm the full real conversational round-trip still ends up at the
    right place."""
    create_calls_by_turn = [_calls_for(ai_response, "create_invoice") for _, ai_response in turns]
    successful_calls = [
        call for calls in create_calls_by_turn for call in calls if _is_genuine_document_creation(call)
    ]

    assert successful_calls, (
        f"No document was ever created within the turn budget - full conversation: "
        f"{[(r, [c['name'] for c in calls]) for (r, _), calls in zip(turns, create_calls_by_turn)]!r}"
    )
    assert len(successful_calls) == 1, (
        f"Expected exactly one successful create_invoice call, got {len(successful_calls)}: {successful_calls!r}"
    )
    assert real_name in (successful_calls[0]["arguments"] or ""), (
        f"create_invoice must have been called with the REAL client name, never the raw typed "
        f"name left unresolved: {successful_calls[0]!r}"
    )


@pytest.mark.billed
def test_create_document_t1_single_letter_added_to_stored_name(denidin_app):
    """T1 (user-specified regression case, 2026-08-11): the real client's
    surname is missing a trailing letter relative to what's typed -
    "צור" (stored) vs "צורן" (typed), one letter added at the end, not the
    first letter.

    Uses GROUND_TRUTH_T1_CLIENT_NAME, a permanent, one-time-seeded sandbox
    fixture (see GROUND_TRUTH_CLIENTS.md) - not a fresh per-run seed, per
    user decision 2026-08-11 (fewer OpenAI calls; the old per-run
    add_client seed also risked colliding with sandbox residue, see
    docstring of _fresh_nonexistent_client_name and bugfix-039's own
    investigation, 2026-08-07/2026-08-11). Both of this fixture's name words
    are verified absent from _unique_client_name()'s random pool (see
    GROUND_TRUTH_CLIENTS.md), so no randomly-generated test client can ever
    collide with it."""
    typed_name = GROUND_TRUTH_T1_CLIENT_TYPED_VARIANT

    turns, _, _ = _run_similarly_named_client_flow(
        GROUND_TRUTH_T1_CLIENT_NAME, typed_name, id_prefix="E2E_039_T1"
    )

    _assert_similarly_named_client_flow_succeeded(turns, GROUND_TRUTH_T1_CLIENT_NAME, typed_name)


@pytest.mark.billed
def test_create_document_t2_single_letter_removed_from_stored_name(denidin_app):
    """T2 (user-specified regression case, 2026-08-11): the real client's
    first name has one extra trailing letter relative to what's typed -
    "דודי" (stored) vs "דוד" (typed), the exact shape of the live production
    incident this bugfix traces to.

    Uses GROUND_TRUTH_T2_CLIENT_NAME, a permanent, one-time-seeded sandbox
    fixture (see GROUND_TRUTH_CLIENTS.md) - same rationale as T1 above."""
    typed_name = GROUND_TRUTH_T2_CLIENT_TYPED_VARIANT

    turns, _, _ = _run_similarly_named_client_flow(
        GROUND_TRUTH_T2_CLIENT_NAME, typed_name, id_prefix="E2E_039_T2"
    )

    _assert_similarly_named_client_flow_succeeded(turns, GROUND_TRUTH_T2_CLIENT_NAME, typed_name)


@pytest.mark.billed
def test_create_document_for_new_client_full_flow_happy_path(denidin_app):
    """3. Extreme happy path: client does not exist yet -> godfather is
    asked whether to create it (via the tool's own "not found" refusal) ->
    provides full details (name/phone/email) up front -> client is created
    -> the original document request is retried and succeeds -> both the
    new client and the new document are verified via real Morning calls."""
    client_name = _fresh_nonexistent_client_name(GODFATHER_CHAT_ID, id_prefix="E2E_027_FULLFLOW")
    seed_email = _random_seed_email()
    amount = _random_amount()
    description = _random_description()
    request_text = f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}"

    # Turn 1/2: ask + approve create_invoice - the client doesn't exist yet.
    # The model may discover this either of two legitimate ways: by actually
    # calling create_invoice and reading its own "not found" refusal once
    # approved, OR by proactively checking existence first via the read-only
    # list_clients/get_client_details (no approval needed for those) before
    # ever proposing create_invoice at all - both correctly result in zero
    # documents created and the user being asked for phone/email; this test
    # doesn't prescribe which path the model takes, only the outcome.
    _, (not_found_response, not_found_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=request_text,
        id_prefix="E2E_027_FULLFLOW_ASK",
    )
    first_attempt_calls = _calls_for(not_found_ai_response, "create_invoice")
    if first_attempt_calls:
        assert first_attempt_calls[0]["error"] is None, (
            f"Expected a clean (non-error) 'not found' tool return, got: {not_found_ai_response.mcp_calls!r}"
        )
    assert "http" not in (not_found_response or ""), (
        f"No document should have been created yet for a nonexistent client: {not_found_response!r}"
    )

    # Turn 3: godfather provides the client's phone+email up front.
    _, (add_response, add_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"כן, תוסיף אותו. מייל {seed_email}, טלפון {_SEED_PHONE}",
        id_prefix="E2E_027_FULLFLOW_CREATE_CLIENT",
    )
    add_calls = _calls_for(add_ai_response, "add_client")
    assert add_calls and add_calls[0]["error"] is None, (
        f"add_client did not succeed: {add_ai_response.mcp_calls if add_ai_response else None!r}"
    )
    time.sleep(3)  # search-index lag (research.md Decision 8)

    # Turn 4/5: retry the original request explicitly - now it must succeed.
    (retry_ask_response, retry_ask_ai_response), (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=request_text,
        id_prefix="E2E_027_FULLFLOW_RETRY",
    )
    create_calls = _calls_for(ai_response, "create_invoice")
    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert create_calls and create_calls[0]["error"] is None, (
        f"Retried create_invoice did not succeed after client creation: {ai_response.mcp_calls!r}"
    )
    assert "http" in response, f"Bot reply did not include an invoice link: {response!r}"

    # Verified via Morning: both the new client and the new document, via
    # real follow-up lookups.
    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"פרטים על הלקוח {client_name}",
        id_prefix="E2E_027_FULLFLOW_VERIFY_CLIENT",
    )
    detail_calls = _calls_for(details_ai_response, "get_client_details")
    assert any("050-1234567" in (c["output"] or "") for c in detail_calls), (
        f"Follow-up real Morning lookup did not confirm the new client: "
        f"{detail_calls!r}. Bot reply: {details_response!r}"
    )
    invoice_details_response, invoice_details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"מה הפרטים של החשבונית של {client_name}?",
        id_prefix="E2E_027_FULLFLOW_VERIFY_INVOICE",
    )
    invoice_detail_calls = _calls_for(invoice_details_ai_response, "get_invoice_details") + _calls_for(
        invoice_details_ai_response, "list_invoices"
    )
    combined_output = "\n".join(c["output"] or "" for c in invoice_detail_calls)
    assert client_name in combined_output, (
        f"Follow-up real Morning lookup did not confirm the new invoice: "
        f"{combined_output!r}. Bot reply: {invoice_details_response!r}"
    )


@pytest.mark.billed
def test_create_document_for_new_client_declines_client_creation(denidin_app):
    """4. Negative case: client doesn't exist -> godfather is asked whether
    to create it -> declines -> neither the client nor the document is
    created, and the user is informed of both."""
    client_name = _fresh_nonexistent_client_name(GODFATHER_CHAT_ID, id_prefix="E2E_027_DECLINE")
    amount = _random_amount()
    description = _random_description()
    request_text = f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}"

    _send_turn_and_approve(chat_id=GODFATHER_CHAT_ID, text=request_text, id_prefix="E2E_027_DECLINE_ASK")

    # Godfather is asked for details; provides them, triggering add_client's
    # own pending approval - then explicitly declines it.
    decline_response, decline_ai_response = _send_turn_and_decline(
        chat_id=GODFATHER_CHAT_ID,
        text=f"כן, תוסיף אותו. מייל {_random_seed_email()}, טלפון {_SEED_PHONE}",
        id_prefix="E2E_027_DECLINE_CLIENT",
    )

    assert decline_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(decline_ai_response, "add_client"), (
        f"add_client executed despite an explicit decline: "
        f"{decline_ai_response.mcp_calls if decline_ai_response else None!r}"
    )
    assert "http" not in decline_response, (
        f"Bot reply looks like a fabricated document success despite the decline: {decline_response!r}"
    )

    # Verified via Morning: the client genuinely doesn't exist. An ambiguous
    # or non-exact resolve_client_name result does NOT mean it exists - only
    # a genuine EXACT match would (2026-08-12, user correction - a second,
    # unrelated ad-hoc copy of the already-fixed "not found" text check made
    # this exact mistake again; now routed through the one shared helper).
    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"פרטים על הלקוח {client_name}",
        id_prefix="E2E_027_DECLINE_VERIFY",
    )
    assert not _client_name_exact_match_found(details_ai_response), (
        f"Client should not exist after declining its creation, but resolve_client_name "
        f"reported a genuine exact match: {details_ai_response.mcp_calls if details_ai_response else None!r}. "
        f"Full reply: {details_response!r}"
    )


@pytest.mark.billed
def test_create_document_for_new_client_creates_client_but_declines_document(denidin_app):
    """5. Semi-negative case: same as scenario 3 up through client creation
    (godfather approves add_client), but then declines the retried
    document-creation request - the client IS created (verified via
    Morning), but the document is NOT, and the user is informed."""
    client_name = _fresh_nonexistent_client_name(GODFATHER_CHAT_ID, id_prefix="E2E_027_SEMINEG")
    seed_email = _random_seed_email()
    amount = _random_amount()
    description = _random_description()
    request_text = f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}"

    _send_turn_and_approve(chat_id=GODFATHER_CHAT_ID, text=request_text, id_prefix="E2E_027_SEMINEG_ASK")

    _, (add_response, add_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"כן, תוסיף אותו. מייל {seed_email}, טלפון {_SEED_PHONE}",
        id_prefix="E2E_027_SEMINEG_CREATE_CLIENT",
    )
    add_calls = _calls_for(add_ai_response, "add_client")
    assert add_calls and add_calls[0]["error"] is None, (
        f"add_client did not succeed: {add_ai_response.mcp_calls if add_ai_response else None!r}"
    )
    time.sleep(3)

    decline_response, decline_ai_response = _send_turn_and_decline(
        chat_id=GODFATHER_CHAT_ID,
        text=request_text,
        id_prefix="E2E_027_SEMINEG_RETRY",
    )
    assert decline_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(decline_ai_response, "create_invoice"), (
        f"create_invoice executed despite an explicit decline: "
        f"{decline_ai_response.mcp_calls if decline_ai_response else None!r}"
    )
    assert "http" not in decline_response, (
        f"Bot reply looks like a fabricated invoice success despite the decline: {decline_response!r}"
    )

    # Verified via Morning: the client DOES exist (created), the invoice does NOT.
    client_details_response, client_details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"פרטים על הלקוח {client_name}",
        id_prefix="E2E_027_SEMINEG_VERIFY_CLIENT",
    )
    assert "050-1234567" in client_details_response, (
        f"Client should exist (created earlier) but wasn't confirmed: {client_details_response!r}"
    )
    invoice_details_response, invoice_details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"מה הפרטים של החשבונית של {client_name}?",
        id_prefix="E2E_027_SEMINEG_VERIFY_INVOICE",
    )
    invoice_detail_calls = _calls_for(invoice_details_ai_response, "get_invoice_details") + _calls_for(
        invoice_details_ai_response, "list_invoices"
    )
    combined_output = "\n".join(c["output"] or "" for c in invoice_detail_calls)
    assert client_name not in combined_output, (
        f"No invoice should exist for this client after declining its creation: {combined_output!r}"
    )


@pytest.mark.billed
def test_create_document_for_new_client_asked_for_missing_info_then_provided(denidin_app):
    """6. Additional info required: godfather agrees to create the
    not-yet-existing client WITHOUT giving phone/email up front -> the model
    must ask for the missing info (runtime_constitution.md's `add_client`
    rule) rather than guessing or calling add_client incomplete -> godfather
    then provides it -> flow continues exactly like scenario 3 (client
    created, document created, both verified)."""
    client_name = _fresh_nonexistent_client_name(GODFATHER_CHAT_ID, id_prefix="E2E_027_ASKINFO")
    seed_email = _random_seed_email()
    amount = _random_amount()
    description = _random_description()
    request_text = f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}"

    _send_turn_and_approve(chat_id=GODFATHER_CHAT_ID, text=request_text, id_prefix="E2E_027_ASKINFO_ASK")

    # Bare "yes, add them" - no phone/email given yet.
    bare_yes_response, bare_yes_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="כן, תוסיף אותו",
        id_prefix="E2E_027_ASKINFO_BAREYES",
    )
    assert not _calls_for(bare_yes_ai_response, "add_client"), (
        f"add_client executed without phone/email - should have asked for "
        f"the missing fields instead: "
        f"{bare_yes_ai_response.mcp_calls if bare_yes_ai_response else None!r}"
    )
    assert bare_yes_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"

    # Now provide the missing info - _complete_add_client_flow drives this
    # through to a real add_client success under client_name specifically,
    # regardless of how many turns that takes (a plain approval, one extra
    # disambiguation "כן", or a forced "create new" turn for an ambiguous
    # candidates list) - this test only cares that a client was actually
    # created under the requested name, not the mechanics.
    add_response, add_ai_response = _complete_add_client_flow(
        chat_id=GODFATHER_CHAT_ID,
        text=f"מייל {seed_email}, טלפון {_SEED_PHONE}",
        client_name=client_name,
        id_prefix="E2E_027_ASKINFO",
        email=seed_email,
        phone=_SEED_PHONE,
    )
    add_calls = _calls_for(add_ai_response, "add_client")
    assert add_calls and add_calls[0]["error"] is None, (
        f"add_client did not succeed once the missing info was provided: "
        f"{add_ai_response.mcp_calls if add_ai_response else None!r}"
    )

    _, (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=request_text,
        id_prefix="E2E_027_ASKINFO_RETRY",
    )
    create_calls = _calls_for(ai_response, "create_invoice")
    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert create_calls and create_calls[0]["error"] is None, (
        f"Retried create_invoice did not succeed after client creation: {ai_response.mcp_calls!r}"
    )
    assert "http" in response, f"Bot reply did not include an invoice link: {response!r}"


@pytest.mark.billed
def test_create_document_for_new_client_missing_info_not_provided_stops_flow(denidin_app):
    """7. Additional info NOT provided: same as scenario 6 up to being asked
    for phone/email, but the godfather explicitly says he doesn't have
    it/won't provide it - the system must NOT create the client (add_client
    requires all three fields - runtime_constitution.md's rule, mirroring
    REQ-CLIENT-012) and must NOT create the document either. No pending
    add_client approval should ever appear."""
    client_name = _fresh_nonexistent_client_name(GODFATHER_CHAT_ID, id_prefix="E2E_027_NOINFO")
    amount = _random_amount()
    description = _random_description()
    request_text = f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}"

    _send_turn_and_approve(chat_id=GODFATHER_CHAT_ID, text=request_text, id_prefix="E2E_027_NOINFO_ASK")

    bare_yes_response, bare_yes_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="כן, תוסיף אותו",
        id_prefix="E2E_027_NOINFO_BAREYES",
    )
    assert not _calls_for(bare_yes_ai_response, "add_client"), (
        f"add_client executed without phone/email: "
        f"{bare_yes_ai_response.mcp_calls if bare_yes_ai_response else None!r}"
    )

    # Godfather explicitly has no phone/email to give.
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="אין לי את הטלפון או המייל שלו, אני לא יודע",
        id_prefix="E2E_027_NOINFO_REFUSE",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ai_response, "add_client"), (
        f"add_client must never be called without phone/email, even after "
        f"the user says they don't have it: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )
    assert "http" not in response, (
        f"No document should have been created without a real client: {response!r}"
    )

    # Verified via Morning: the client genuinely doesn't exist.
    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"פרטים על הלקוח {client_name}",
        id_prefix="E2E_027_NOINFO_VERIFY",
    )
    assert "לא נמצא" in details_response or "אין" in details_response, (
        f"Client should not exist since required info was never provided: {details_response!r}"
    )
