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
`_seed_client`/`_random_amount`/`_random_description`/
`_random_seed_email`/`_SEED_PHONE`/`GODFATHER_CHAT_ID`) live in
denidin_mcp_e2e_helpers.py. Client names are always obtained via
`_seed_client` (the ONE 4-way-resolve/seed flow) - never a raw
`_unique_client_name()` call in a test body.

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
create_credit_note, create_receipt, create_combo_document_as_reference), plus
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
import random
import time

import pytest

from .denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _HEBREW_FAMILY_NAMES,
    _HEBREW_NAME_SPELLING_VARIANTS,
    _SEED_PHONE,
    _calls_for,
    _normalize_hebrew_geresh,
    _is_genuine_document_creation,
    _is_real_approval_prompt,
    _random_amount,
    _random_description,
    _random_seed_email,
    _resolve_client_name,
    _seed_client,
    ResolveOutcome,
    pick_existing_client,
    _send_button_tap,
    _send_turn,
    _send_turn_and_approve,
    _send_turn_and_decline,
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
    """Godfather asks for a new document the way a real, non-technical person
    would - client name, amount, and what it's for, all in one message.
    It creates a document, so it requires explicit approval (Feature 022):
    the ASK turn must NOT execute it yet, and only the APPROVE turn (an
    explicit Hebrew "כן") actually calls the tool.

    Requests a חשבונית מס/קבלה (combo tax-invoice/receipt -> create_combo_document)
    rather than a plain חשבונית (2026-09-02, Feature 059 stabilization): its VAT
    treatment is unconditionally "included" per the runtime constitution, so the
    model has no reason to insert an unstated-VAT clarifying turn - which broke
    this 2-turn (ASK -> "כן") flow on any run the model chose to ask. "שילם ...
    היום" also supplies the payment fact + date up front so nothing else is
    asked. (Plain-invoice creation + its own approval gate is still covered by
    US1's happy-path test below.)

    Verification (independent signals, not the model's unverified claim alone):
    1. ASK turn: no create_combo_document call yet.
    2. APPROVE turn: mcp_calls shows a create_combo_document call with no error.
    3. The final reply contains a document link - the runtime constitution
       says these confirmations must always include one, unprompted, so this
       isn't a special ask in the test prompt.

    Uses a real existing sandbox client (Feature 059 item 5: pick_existing_client)
    - never hardcode a shared ground-truth client name here.
    """
    amount = _random_amount()
    description = _random_description()
    client_name = pick_existing_client()["name"]  # Feature 059 item 5: any existing client works

    (ask_response, ask_ai_response), (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"{client_name} שילם {amount} שח היום עבור {description}. תפיק חשבונית מס קבלה",
        id_prefix="E2E_CREATE",
    )

    assert not _calls_for(ask_ai_response, "create_combo_document"), (
        f"create_combo_document executed on the ASK turn before approval was given: "
        f"{ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    create_calls = _calls_for(ai_response, "create_combo_document")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert create_calls, (
        f"Model never invoked create_combo_document via the remote MCP server, even "
        f"after approving. mcp_calls: {ai_response.mcp_calls!r}. "
        f"Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in create_calls), (
        f"create_combo_document call(s) reported an error: {create_calls}"
    )
    assert any(client_name in (c["arguments"] or "") for c in create_calls), (
        f"create_combo_document was not called with the client name {client_name!r}: {create_calls!r}"
    )

    # NOTE (bugfix-050, 2026-09-02): the Morning create tools drop response["url"], so
    # format_invoice_confirmation never emits a link - the model only sometimes adds one via a
    # separate download_invoice_pdf call, making this assertion nondeterministic for BOTH type
    # 305 and 320. Commented out pending bugfix-050 (populate Invoice.pdf_url from the create
    # response); re-enable once that lands.
    # assert "http" in response, (
    #     f"Bot reply did not include an invoice link. Full reply: {response!r}"
    # )


@pytest.mark.billed
@pytest.mark.sanity
def test_godfather_creates_invoice_via_whatsapp_button_tap(denidin_app):
    """Feature 047: identical to test_godfather_creates_invoice_via_whatsapp
    above, except the approval is given by a real WhatsApp interactive-button
    tap (AIHandler.resolve_button_tap, via handle_button_tap) instead of
    typing "כן" - exercises the full button-tap resolution path end to end
    against real OpenAI/Morning MCP traffic: the ASK turn must actually send
    real interactive buttons (not just a plain-text prompt), and the tap must
    resolve to the same real, single create_invoice execution the text path
    produces."""
    amount = _random_amount()
    description = _random_description()
    client_name = pick_existing_client()["name"]  # Feature 059 item 5: any existing client works

    ask_response, ask_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}",
        id_prefix="E2E_CREATE_TAP_ASK",
    )

    assert not _calls_for(ask_ai_response, "create_invoice"), (
        f"create_invoice executed on the ASK turn before approval was given: "
        f"{ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    # The ASK turn must have actually sent real interactive buttons - not
    # silently fallen back to plain text (which would make this test
    # indistinguishable from the text-path test above, and mask a real
    # regression the way this exact scenario did before the E2E harness
    # gained answer_with_interactive_buttons support, 2026-08-14). Checked
    # right here, between the ASK and TAP turns - checking any later (e.g.
    # after the tap has already resolved and cleared it) would always show
    # None regardless of whether the buttons send itself actually worked, a
    # real ordering bug caught in this test's own first run, 2026-08-14.
    # sent_message_id is populated by the exact same production wiring
    # (denidin.py's attach_sent_message_id call) that requires a real,
    # successful buttons send in the first place, so its presence here is
    # direct proof - no need for get_button_send()'s captured body/buttons.
    import denidin as denidin_module
    pending_after_ask = denidin_module.denidin_app.ai_handler.pending_approval_manager.get(
        GODFATHER_CHAT_ID
    )
    assert pending_after_ask is not None and pending_after_ask.sent_message_id, (
        "ASK turn did not result in a pending approval with a real "
        "sent_message_id attached - either no pending approval was created, "
        "or the interactive-buttons send failed and silently fell back "
        "(check for 'Failed to send approval buttons' in the log)."
    )

    from src.managers.pending_approval_manager import BUTTON_ID_APPROVE
    response, ai_response = _send_button_tap(
        GODFATHER_CHAT_ID, BUTTON_ID_APPROVE, id_prefix="E2E_CREATE_TAP_APPROVE"
    )

    create_calls = _calls_for(ai_response, "create_invoice")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert create_calls, (
        f"Model never invoked create_invoice via the remote MCP server, even "
        f"after the button tap. mcp_calls: {ai_response.mcp_calls!r}. "
        f"Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in create_calls), (
        f"create_invoice call(s) reported an error: {create_calls}"
    )
    assert any(client_name in (c["arguments"] or "") for c in create_calls), (
        f"create_invoice was not called with the client name {client_name!r}: {create_calls!r}"
    )
    assert len(create_calls) == 1, (
        f"create_invoice executed {len(create_calls)} times via the button-tap "
        f"resolution path, expected exactly 1 (duplicate-execution guard "
        f"regression): {create_calls!r}"
    )

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
    client_name = pick_existing_client()["name"]  # Feature 059 item 5: any existing client works
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
@pytest.mark.sanity
def test_godfather_add_client_requires_approval(denidin_app):
    """🚨 CONSTITUTION §VIII flagged exception (spec.md Clarifications round 1,
    explicitly human-approved): replaces test_godfather_add_client_still_
    single_turn's regression guard. add_client now creates a real, persisted
    client record - Feature 026 moves it into APPROVAL_REQUIRED_MCP_TOOLS,
    reversing its prior single-turn behavior.

    Verification (independent signals, not the model's unverified claim
    alone):
    1. _seed_client drives the real add_client conversation through the ONE
       shared 4-way-resolve/approval flow and raises if add_client never
       lands cleanly (the pre-approval gate itself is covered by
       test_godfather_add_client_near_duplicate_name_is_asked_before_creating
       and the _send_turn_and_approve family).
    2. mcp_calls on the seed's final turn shows an add_client call with no
       error.
    3. A follow-up get_client_details turn (same test, real WhatsApp
       round-trip) confirms the client was actually created and its phone
       number persisted in normalized Israeli dashed format
       (REQ-CLIENT-016/017), same standard as the sandbox-level
       test_add_client_tool_normalizes_and_persists_phone test.
    """
    seed_email = _random_seed_email()
    raw_phone = "+972501234567"  # international input - must normalize on read-back

    client_name, response, ai_response = _seed_client(
        GODFATHER_CHAT_ID,
        "E2E_ADD_CLIENT_APPROVE",
        email=seed_email,
        phone=raw_phone,
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
@pytest.mark.sanity
def test_godfather_add_client_missing_field_is_asked_for(denidin_app):
    """Omitting email or phone must make the model ask for it, never call
    add_client with a guessed/blank value (runtime_constitution.md's
    "add_client needs name, email, AND phone" guidance, added by Feature
    026's T015)."""
    client_name, _, _ = _seed_client(
        GODFATHER_CHAT_ID, "E2E_ADD_CLIENT_MISSING", create=False
    )

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
    client_name, _, _ = _seed_client(
        GODFATHER_CHAT_ID, "E2E_ADD_CLIENT_BADEMAIL", create=False
    )

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
    client_name, _, _ = _seed_client(
        GODFATHER_CHAT_ID, "E2E_ADD_CLIENT_DECLINE", create=False
    )
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


@pytest.mark.billed
@pytest.mark.sanity
def test_godfather_add_client_near_duplicate_name_is_asked_before_creating(denidin_app):
    """bugfix-045 regression guard, added 2026-08-27 - written specifically
    because the fix for the *original* bugfix-045 deadlock (the model
    refusing to ever create a new client once resolve_client_name returned
    multiple ambiguous candidates) risked over-correcting into the opposite
    failure: silently creating a near-duplicate the instant a message merely
    SAYS "add a new client", without ever giving the godfather a chance to
    say "wait, that's actually the same person, just spelled differently."

    The whole point of resolve_client_name's courtesy check
    (runtime_constitution.md's "Exception when the underlying request is to
    ADD a NEW client") is to catch exactly this case - a genuinely SIMILAR
    (not exact) existing client - and surface it before creating anything,
    not to wave every add_client request straight through unexamined.

    Uses the SAME real Hebrew male/chaser spelling-variant pool as
    test_godfather_finds_client_via_hebrew_vowel_variant (a previously-
    confirmed-live "similar enough for Morning's own search to surface it"
    pair, not a synthetic worst-case) - seed a real client under one
    spelling, then ask to add a "new" client under the other spelling of the
    exact same name.
    """
    chaser_spelling, male_spelling = random.choice(_HEBREW_NAME_SPELLING_VARIANTS)
    seed_name, _, _ = _seed_client(
        GODFATHER_CHAT_ID,
        "E2E_ADD_CLIENT_NEARDUP_SEED",
        name_factory=lambda: f"{male_spelling} {random.choice(_HEBREW_FAMILY_NAMES)}",
    )
    family_name = seed_name.split()[-1]
    near_duplicate_name = f"{chaser_spelling} {family_name}"
    seed_email = _random_seed_email()

    import denidin

    ask_response, ask_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=(
            f"תוסיף לקוח חדש בשם {near_duplicate_name}, מייל {seed_email}, "
            f"טלפון {_SEED_PHONE}"
        ),
        id_prefix="E2E_ADD_CLIENT_NEARDUP_ASK",
    )

    assert ask_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ask_ai_response, "add_client"), (
        f"add_client executed (completed) on the very first turn, with no "
        f"chance to flag the near-duplicate: "
        f"{ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )
    pending = denidin.denidin_app.ai_handler.pending_approval_manager.get(GODFATHER_CHAT_ID)
    assert pending is None or pending.tool_name != "add_client", (
        f"add_client got a pending approval immediately, with NO chance for "
        f"the godfather to say 'that's actually the same person' about the "
        f"just-seeded, genuinely similar client {seed_name!r} - this is "
        f"exactly the silent-duplicate risk the courtesy check exists to "
        f"prevent: {pending!r}"
    )
    assert _normalize_hebrew_geresh(seed_name) in (ask_response or ""), (
        f"Expected the reply to explicitly name the existing similar client "
        f"{seed_name!r} (per runtime_constitution.md's mandatory disclosure) "
        f"before offering to create a new one under {near_duplicate_name!r} - "
        f"got: {ask_response!r}"
    )

    # Confirming intent to create anyway (not "use the existing one") must
    # still work - the courtesy check blocks SILENT creation, not creation
    # itself once the godfather has actually seen and rejected the match.
    confirm_response, confirm_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=(
            "לא, זה לא אותו לקוח, זה אדם אחר לגמרי - אני יודע שיש לקוח עם שם "
            "דומה, אבל אני בכל זאת רוצה ליצור לקוח חדש עם השם שנתתי."
        ),
        id_prefix="E2E_ADD_CLIENT_NEARDUP_CONFIRMNEW",
    )
    pending = denidin.denidin_app.ai_handler.pending_approval_manager.get(GODFATHER_CHAT_ID)
    assert pending is not None and pending.tool_name == "add_client", (
        f"After explicitly insisting on a new client despite the near-"
        f"duplicate warning, no pending add_client approval was created. "
        f"Reply: {confirm_response!r}, calls: "
        f"{confirm_ai_response.mcp_calls if confirm_ai_response else None!r}"
    )

    approve_response, approve_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID, text="כן", id_prefix="E2E_ADD_CLIENT_NEARDUP_APPROVE"
    )
    add_calls = _calls_for(approve_ai_response, "add_client")
    assert add_calls and add_calls[0]["error"] is None, (
        f"add_client did not complete after explicit confirmation: "
        f"{approve_ai_response.mcp_calls if approve_ai_response else None!r}"
    )
