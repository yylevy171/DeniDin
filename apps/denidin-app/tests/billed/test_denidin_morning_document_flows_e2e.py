"""E2E Tests (Feature 027): mandatory client-reference resolution for
document creation - the 8 `create_document_*` flows plus the T1/T2
similarly-named-client variants.

Split out of test_denidin_morning_invoice_creation_e2e.py (2026-09-03,
Feature 075) - pure reorganization, no test logic changed. The parent file
had grown to hold 7 @pytest.mark.sanity tests, making it the long pole of
the parallel sanity sweep (scripts/run_sanity_parallel.sh, `--dist
loadfile`); moving this self-contained Feature 027 block into its own file
lets the two halves run on separate xdist workers. Shared fixtures
(`denidin_app`, `denidin_config`, `live_morning_tunnel`) live in this
directory's conftest.py (auto-discovered); shared helpers/constants live in
denidin_mcp_e2e_helpers.py.

NO MOCKING anywhere. @pytest.mark.billed: real OpenAI billing on every run,
can be run freely - no per-run approval (see CLAUDE.md/CONSTITUTION §VII).
"""
from __future__ import annotations

import logging
import time

import pytest

from .denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
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
    _send_turn,
    _send_turn_and_approve,
    _send_turn_and_decline,
)

logger = logging.getLogger(__name__)

# Permanent ground-truth clients for the T1/T2 tests below - seeded ONCE, out
# of band (see GROUND_TRUTH_CLIENTS.md). Copied here with the tests that use
# them when this file was split from test_denidin_morning_invoice_creation_e2e.py.
GROUND_TRUTH_T1_CLIENT_NAME = "זהבית צור"
GROUND_TRUTH_T1_CLIENT_TYPED_VARIANT = "זהבית צורן"
GROUND_TRUTH_T2_CLIENT_NAME = "כרמלי דודי"
GROUND_TRUTH_T2_CLIENT_TYPED_VARIANT = "כרמלי דוד"

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
@pytest.mark.sanity
def test_create_document_for_existing_client_happy_path(denidin_app):
    """1. Happy path: client already exists under the given name -> the
    document is created attached to that real client, verified via a real
    follow-up get_invoice_details call, and the user is informed with a
    normal confirmation (a real invoice link)."""
    amount = _random_amount()
    description = _random_description()
    client_name = pick_existing_client()["name"]  # Feature 059 item 5: any existing client works

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
    the _seed_client(create=False) docstring and bugfix-039's own
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
@pytest.mark.sanity
def test_create_document_for_new_client_full_flow_happy_path(denidin_app):
    """3. Extreme happy path: client does not exist yet -> godfather is
    asked whether to create it (via the tool's own "not found" refusal) ->
    provides full details (name/phone/email) up front -> client is created
    -> the original document request is retried and succeeds -> both the
    new client and the new document are verified via real Morning calls."""
    client_name, _, _ = _seed_client(GODFATHER_CHAT_ID, "E2E_027_FULLFLOW", create=False)
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
    client_name, _, _ = _seed_client(GODFATHER_CHAT_ID, "E2E_027_DECLINE", create=False)
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
    assert not _resolve_client_name(
        initial_result=(details_response, details_ai_response), drive=False
    ).exists, (
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
    client_name, _, _ = _seed_client(GODFATHER_CHAT_ID, "E2E_027_SEMINEG", create=False)
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
@pytest.mark.sanity
def test_create_document_for_new_client_asked_for_missing_info_then_provided(denidin_app):
    """6. Additional info required: godfather agrees to create the
    not-yet-existing client WITHOUT giving phone/email up front -> the model
    must ask for the missing info (runtime_constitution.md's `add_client`
    rule) rather than guessing or calling add_client incomplete -> godfather
    then provides it -> flow continues exactly like scenario 3 (client
    created, document created, both verified)."""
    client_name, _, _ = _seed_client(GODFATHER_CHAT_ID, "E2E_027_ASKINFO", create=False)
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

    # Now provide the missing info - _seed_client (specific-name variant with
    # an explicit first turn) drives this through to a real add_client success
    # under client_name specifically, regardless of how many turns that takes
    # (a plain approval, one extra disambiguation "כן", or a forced "create
    # new" turn for an ambiguous candidates list) - this test only cares that
    # a client was actually created under the requested name, not the mechanics.
    _, _, add_ai_response = _seed_client(
        GODFATHER_CHAT_ID,
        "E2E_027_ASKINFO",
        name=client_name,
        text=f"מייל {seed_email}, טלפון {_SEED_PHONE}",
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
    client_name, _, _ = _seed_client(GODFATHER_CHAT_ID, "E2E_027_NOINFO", create=False)
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
    resolved = _resolve_client_name(
        initial_result=(details_response, details_ai_response), drive=False
    )
    assert resolved.outcome in (
        ResolveOutcome.SINGLE_CANDIDATE,
        ResolveOutcome.MULTI_CANDIDATE,
        ResolveOutcome.NONE,
    ), (
        f"Client should not exist since required info was never provided; "
        f"resolve outcome was {resolved.outcome}: {details_response!r}"
    )
