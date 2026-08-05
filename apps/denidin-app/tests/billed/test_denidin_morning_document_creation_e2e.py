"""E2E Tests (Feature 021): godfather creates the new Morning document types
via natural WhatsApp conversation - real webhook, real OpenAI Responses API,
real Morning MCP server, real Morning sandbox.

Same entry point, fixtures, and non-technical-user conventions as this
directory's other Morning-MCP billed E2E test modules (feature 018 and
successors) - reuses shared fixtures/helpers rather than duplicating them
(denidin_app via conftest.py; _send_turn, _send_turn_and_approve,
_send_turn_and_decline, _calls_for, _unique_client_name, GODFATHER_CHAT_ID
via denidin_mcp_e2e_helpers.py). See
test_denidin_morning_invoice_creation_e2e.py's docstring for the full
rationale behind single-turn-only prompts for non-document-creating tools
and no test-only confirmation carve-out.

(2026-08-04, Feature 038: this import previously pointed at
test_denidin_morning_mcp_e2e.py, which was split by topic into 4 files -
see that feature's task list, T012/T013. Updated to import from the new
shared locations instead of any one of the resulting files.)

**Two-turn approval (Feature 022, merged after this file was first written;
tool list updated for features 023/026)**: create_transaction_account,
create_combo_document, create_credit_note, create_receipt, and
close_transaction_account all create a real Morning document, exactly like
create_invoice - so all of them are in ai_handler.APPROVAL_REQUIRED_MCP_TOOLS
(renamed from DOCUMENT_CREATING_MCP_TOOLS by Feature 026, which extended it
to also cover client-mutating tools) and require an explicit approval turn
before they execute. (update_invoice_status, which used to be one more tool
in this list, was removed entirely by feature 023.) Every test below is
genuinely two-turn (or more, when it also needs to seed a document first):
the ASK turn must NOT produce a real mcp_call, and the APPROVE turn is where
the actual creation happens - see _send_turn_and_approve/_send_turn_and_decline
in the 018 test module.

Amounts in this file are randomized 10-99 (all sandbox test amounts across
this app's E2E suites are kept strictly under 100) - plausible for the
short, cash-style phrasings used here ("X שילם 50 שח").

Credit-note/receipt requests reference the real, seeded invoice NUMBER
(Morning's human-visible document number, not the internal documentId GUID -
still a real thing a non-technical user would read off their own document/a
WhatsApp message, not an implementation detail) rather than "the invoice of
X" - this keeps each request unambiguous even though nothing here stops two
invoices existing for the same client name in the same sandbox.

NO MOCKING anywhere. @pytest.mark.billed: real OpenAI billing on every run.
"""
import random
import re
import time

import pytest

from tests.billed.denidin_mcp_e2e_helpers import (  # noqa: F401
    GODFATHER_CHAT_ID,
    _calls_for,
    _send_turn,
    _send_turn_and_approve,
    _send_turn_and_decline,
    _unique_client_name,
)

# `denidin_app`/`denidin_config`/`live_morning_tunnel` are no longer imported
# explicitly - they're pytest fixtures auto-discovered from this directory's
# conftest.py (Feature 038 split, T012/T013).


def _small_random_amount() -> int:
    """Amount range for this file's short, cash-style phrasings - see module
    docstring. Kept strictly under 100."""
    return random.randint(10, 99)


def _seed_fresh_invoice_and_get_number(client_name: str, amount: int, description: str) -> str:
    """Seed a fresh invoice via a real, two-turn approved WhatsApp exchange
    (create_invoice requires approval - Feature 022) and return its real,
    human-visible Morning invoice number (parsed from create_invoice's own
    Hebrew confirmation output, e.g. "חשבונית #60123") - so later turns in
    the same test can reference a specific, unambiguous real document."""
    _, (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"צור חשבונית ל-{client_name} על {amount} ₪ עבור {description}",
        id_prefix="E2E_021_SEED",
    )
    create_calls = _calls_for(ai_response, "create_invoice")
    assert create_calls and create_calls[0]["error"] is None, (
        f"Seed create_invoice failed or was not called: {ai_response.mcp_calls!r}"
    )
    output = create_calls[0]["output"] or ""
    match = re.search(r"#(\d+)", output)
    assert match, f"Could not extract invoice number from create_invoice output: {output!r}"
    time.sleep(3)  # search-index lag (research.md Decision 8) - a caller that immediately
    # list_invoices/get_invoice_details's for this just-seeded invoice would otherwise race
    # the sandbox's own indexing (a real, billed failure: 2026-07-31,
    # test_receipt_request_for_already_paid_invoice_handled_sensibly - the freshly-created
    # invoice was missing from list_invoices' results for the first ~10s after creation)
    return match.group(1)


_SEED_DESCRIPTIONS = ("ייעוץ", "עיצוב לוגו", "תחזוקת אתר", "צילום")


# ============================================================================
# create_transaction_account (type 300, "חשבון עסקה")
# ============================================================================

@pytest.mark.billed
def test_godfather_creates_transaction_account_via_whatsapp(denidin_app):
    """Godfather asks for a non-tax transaction account ("חשבון עסקה") the
    way a real, non-technical person would - client name, amount, what it's
    for, and the specific Hebrew document-type name (the one detail a real
    user would actually know/say to distinguish this from an ordinary tax
    invoice).

    Two-turn (Feature 022): the ASK turn must NOT execute
    create_transaction_account yet; the APPROVE turn is where it actually
    runs, with no error and the right client name in its arguments.
    """
    client_name = _unique_client_name()
    amount = _small_random_amount()
    description = random.choice(_SEED_DESCRIPTIONS)

    (ask_response, ask_ai_response), (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפיק חשבון עסקה עבור {client_name} על סך {amount} שח עבור {description}",
        id_prefix="E2E_TXN_ACCT",
    )
    assert not _calls_for(ask_ai_response, "create_transaction_account"), (
        f"create_transaction_account executed on the ASK turn before approval "
        f"was given: {ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    create_calls = _calls_for(ai_response, "create_transaction_account")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert create_calls, (
        f"Model never invoked create_transaction_account via the remote MCP "
        f"server. mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in create_calls), (
        f"create_transaction_account call(s) reported an error: {create_calls}"
    )
    assert any(client_name in (c["arguments"] or "") for c in create_calls), (
        f"create_transaction_account was not called with the client name "
        f"{client_name!r}: {create_calls!r}"
    )


# ============================================================================
# create_combo_document (type 320, "חשבונית מס / קבלה")
# ============================================================================

@pytest.mark.billed
def test_godfather_creates_combo_document_via_whatsapp(denidin_app):
    """Godfather reports payment already received and asks for the combo
    invoice+receipt document - the natural phrasing a real person uses right
    after a cash sale, not a request for payment later. Deliberately omits
    the description on the first turn (create_combo_document requires one),
    so this is genuinely three-turn: ASK (missing description, must not
    execute) -> DESCRIBE (now complete, triggers the pending approval, must
    still not execute - Feature 022) -> APPROVE (executes).
    """
    client_name = _unique_client_name()
    amount = _small_random_amount()
    description = random.choice(_SEED_DESCRIPTIONS)

    # Turn 1: no description given - create_combo_document requires one, so
    # the model is expected to ask for it (constitution's "ask for missing
    # required information" rule) rather than attempt the call.
    ask_response, ask_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"{client_name} שילם {amount} שח. תפיק חשבונית מס קבלה",
        id_prefix="E2E_COMBO_ASK",
    )
    assert not _calls_for(ask_ai_response, "create_combo_document"), (
        f"create_combo_document executed on the ASK turn before the "
        f"description was even given: {ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    # Turn 2: description supplied - now everything's present, so this turn
    # should trigger the pending approval (not execute yet - Feature 022).
    description_response, description_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"עבור {description}",
        id_prefix="E2E_COMBO_DESCRIBE",
    )
    assert not _calls_for(description_ai_response, "create_combo_document"), (
        f"create_combo_document executed before approval was given: "
        f"{description_ai_response.mcp_calls if description_ai_response else None!r}"
    )

    # Turn 3: approve.
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="כן",
        id_prefix="E2E_COMBO_APPROVE",
    )
    create_calls = _calls_for(ai_response, "create_combo_document")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert create_calls, (
        f"Model never invoked create_combo_document via the remote MCP "
        f"server. mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in create_calls), (
        f"create_combo_document call(s) reported an error: {create_calls}"
    )


# ============================================================================
# create_credit_note (type 330, "חשבונית זיכוי") - standalone
# ============================================================================

@pytest.mark.billed
def test_godfather_creates_credit_note_against_real_invoice(denidin_app):
    """Godfather explicitly asks for a credit note against a real, existing
    invoice by its real invoice number - exactly one such invoice exists
    (seeded fresh, this test's own number), so the request is unambiguous.
    Direct request for the document itself, per feature 021's resolved scope
    that documents are creatable directly. (Feature 023 removed
    update_invoice_status - "cancel" wording now routes to this same tool
    too, see test_denidin_morning_mcp_e2e.py's
    test_godfather_cancels_invoice_via_whatsapp, so this test's direct
    phrasing and that one's indirect phrasing now converge on one tool.)

    Two-turn (Feature 022): the ASK turn must NOT execute create_credit_note yet.
    """
    client_name = _unique_client_name()
    amount = _small_random_amount()
    invoice_number = _seed_fresh_invoice_and_get_number(client_name, amount, random.choice(_SEED_DESCRIPTIONS))

    (ask_response, ask_ai_response), (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפיק חשבונית זיכוי לחשבונית מספר {invoice_number}",
        id_prefix="E2E_CREDIT_NOTE",
    )
    assert not _calls_for(ask_ai_response, "create_credit_note"), (
        f"create_credit_note executed on the ASK turn before approval was "
        f"given: {ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    create_calls = _calls_for(ai_response, "create_credit_note")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert create_calls, (
        f"Model never invoked create_credit_note via the remote MCP server. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in create_calls), (
        f"create_credit_note call(s) reported an error: {create_calls}"
    )


@pytest.mark.billed
def test_credit_note_request_with_invalid_invoice_number_fails_gracefully(denidin_app):
    """Godfather asks for a credit note against an invoice number that does
    not exist. The invalid number is derived from a real, freshly seeded
    invoice's real number (offset far outside any plausible real range)
    rather than an arbitrary constant, so it has a realistic shape while
    still being guaranteed not to collide with any real document.

    Uses _send_turn_and_approve unconditionally (mirroring the equivalent
    "unsupported type" negative case in test_denidin_morning_mcp_e2e.py):
    if the model attempts the call at all, it comes back as a pending
    approval first: the tool must reject it once approved (never a
    fabricated success), and the model must never surface a raw stack
    trace/technical error either way.
    """
    client_name = _unique_client_name()
    amount = _small_random_amount()
    real_number = _seed_fresh_invoice_and_get_number(client_name, amount, random.choice(_SEED_DESCRIPTIONS))
    invalid_number = str(int(real_number) + 8_746_321)

    _, (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפיק חשבונית זיכוי לחשבונית מספר {invalid_number}",
        id_prefix="E2E_CREDIT_NOTE_BAD_ID",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    create_calls = _calls_for(ai_response, "create_credit_note")
    if create_calls:
        # If the model did attempt the call, it must have failed cleanly -
        # not silently claimed success.
        assert any(c["error"] is not None for c in create_calls), (
            f"create_credit_note against a nonexistent invoice reported no "
            f"error: {create_calls!r}"
        )
    # No raw technical detail (status codes, stack traces) leaked to the user.
    assert "Traceback" not in response
    assert "404" not in response


# ============================================================================
# create_receipt (type 400, "קבלה") - standalone
# ============================================================================

@pytest.mark.billed
def test_godfather_creates_receipt_against_unpaid_invoice(denidin_app):
    """Godfather explicitly asks for a receipt document against a real,
    existing unpaid invoice, referenced by its real invoice number (exactly
    one such invoice exists, freshly seeded) - a direct request for the
    document itself. (Feature 023 removed update_invoice_status - "mark it
    as paid" wording now routes to this same tool too, see
    test_denidin_morning_mcp_e2e.py's test_godfather_marks_invoice_paid_via_whatsapp,
    so this test's direct phrasing and that one's indirect phrasing now
    converge on one tool.)

    Two-turn (Feature 022): the ASK turn must NOT execute create_receipt yet.
    """
    client_name = _unique_client_name()
    amount = _small_random_amount()
    invoice_number = _seed_fresh_invoice_and_get_number(client_name, amount, random.choice(_SEED_DESCRIPTIONS))

    (ask_response, ask_ai_response), (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפיק קבלה עבור חשבונית מספר {invoice_number}",
        id_prefix="E2E_RECEIPT",
    )
    assert not _calls_for(ask_ai_response, "create_receipt"), (
        f"create_receipt executed on the ASK turn before approval was given: "
        f"{ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    create_calls = _calls_for(ai_response, "create_receipt")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert create_calls, (
        f"Model never invoked create_receipt via the remote MCP server. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in create_calls), (
        f"create_receipt call(s) reported an error: {create_calls}"
    )


@pytest.mark.billed
def test_receipt_request_with_exact_invoice_amount_resolves_correctly(denidin_app):
    """Godfather references the invoice by client name + the EXACT amount
    that was seeded on it (no invoice number mentioned at all) - a realistic
    "X paid me Y" phrasing that only disambiguates via the amount matching
    the real, single seeded invoice for that client.
    """
    client_name = _unique_client_name()
    amount = _small_random_amount()
    _seed_fresh_invoice_and_get_number(client_name, amount, random.choice(_SEED_DESCRIPTIONS))

    _, (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"{client_name} שילם {amount} שח. תפיק קבלה",
        id_prefix="E2E_RECEIPT_EXACT_AMOUNT",
    )
    create_calls = _calls_for(ai_response, "create_receipt")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert create_calls, (
        f"Model never invoked create_receipt via the remote MCP server. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in create_calls), (
        f"create_receipt call(s) reported an error: {create_calls}"
    )


@pytest.mark.billed
def test_receipt_request_for_already_paid_invoice_handled_sensibly(denidin_app):
    """Godfather asks for a receipt (by real invoice number) against an
    invoice that was already fully paid (via create_receipt in a prior,
    approved turn - feature 023 removed update_invoice_status, so "mark as
    paid" phrasing now dispatches directly to create_receipt itself) - edge
    case verifying the model/tool handles a second request sensibly. Since
    feature 023, create_receipt's own idempotency guard makes a repeated
    full-amount call against an already-paid invoice a deterministic no-op
    (not "whatever Morning does" - Morning itself does not reject a
    duplicate, confirmed live, so this guard is what actually prevents one)
    - this test mainly guards against crashing or fabricating a result if
    the model instead expresses this second request with an explicit amount
    (bypassing the no-op) or some other unanticipated phrasing.
    """
    client_name = _unique_client_name()
    amount = _small_random_amount()
    invoice_number = _seed_fresh_invoice_and_get_number(client_name, amount, random.choice(_SEED_DESCRIPTIONS))

    _, (paid_response, paid_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"סמן את חשבונית מספר {invoice_number} כשולמה",
        id_prefix="E2E_RECEIPT_PREPAY",
    )
    assert paid_response is not None
    status_calls = _calls_for(paid_ai_response, "create_receipt")
    assert status_calls and all(c["error"] is None for c in status_calls), (
        f"Setup step (marking invoice paid) failed: {paid_ai_response.mcp_calls!r}"
    )

    _, (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפיק קבלה נוספת עבור חשבונית מספר {invoice_number}",
        id_prefix="E2E_RECEIPT_DUPLICATE",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0
    # No raw technical detail leaked regardless of how Morning actually
    # handles a receipt against an already-paid document.
    assert "Traceback" not in response
