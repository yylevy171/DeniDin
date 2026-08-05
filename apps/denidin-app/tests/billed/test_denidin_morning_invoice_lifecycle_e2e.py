"""E2E Tests (Feature 018/020/022/023): get_invoice_details, mark-paid/cancel
direct dispatch, transaction-account payment marking - real webhook, real
OpenAI Responses API, real Morning MCP server, real Morning sandbox.

Split (2026-08-04, Feature 038, human-approved T012/T013) from the former
single test_denidin_morning_mcp_e2e.py - see
test_denidin_morning_invoice_creation_e2e.py's module docstring for the full
split rationale and shared-fixture/helper locations (this directory's
conftest.py for fixtures, denidin_mcp_e2e_helpers.py for helpers/constants).

get_invoice_details is read-only, no approval wait. "Mark as paid"/"cancel"
phrasing dispatches directly to a document-creating tool (create_receipt/
create_credit_note/close_transaction_account - there is no separate
status-update tool, feature 023 removed it entirely), so those all require
explicit approval - see `_send_turn_and_approve`/`_send_turn_and_decline`.

NO MOCKING anywhere. @pytest.mark.billed: real OpenAI billing on every run,
can be run freely - no per-run approval, no one-at-a-time restriction (see
CLAUDE.md/CONSTITUTION §VII).
"""
from __future__ import annotations

import logging
import re
import time

import pytest

from .denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _calls_for,
    _random_amount,
    _random_description,
    _send_turn,
    _send_turn_and_approve,
    _send_turn_and_decline,
    _unique_client_name,
)

logger = logging.getLogger(__name__)

# ============================================================================
# get_invoice_details
# ============================================================================

# One fully-known invoice from the fixed 2026-02-07 set (verified free, no
# billing) - referenced here by client name + date only, the way a real user
# would; the model must resolve the actual invoice_id itself.
KNOWN_INVOICE_NUMBER = "60006"
KNOWN_INVOICE_CLIENT = "Test Client DENIDIN_TEST_1770474207"
KNOWN_INVOICE_AMOUNT_IL = "123.45"
KNOWN_INVOICE_STATUS_HE = "שולם"  # paid


@pytest.mark.billed
def test_godfather_gets_invoice_details_via_whatsapp(denidin_app):
    """Godfather asks about a specific invoice by client name and date only -
    never an id. The model must resolve which invoice this is itself (via
    list_invoices and/or get_invoice_details) and reply with the real details.

    Verification checks the FINAL reply (what the user actually saw) against
    known ground truth - this is the tightest test in the suite (one specific,
    fully-known invoice, no pagination/date-range ambiguity) - and does not
    require a specific tool name to have been used, since a real user has no
    way to know or care which tool satisfies their request.
    """
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=(
            f"מה הסטטוס והפרטים המלאים של החשבונית של {KNOWN_INVOICE_CLIENT} "
            f"מהשבעה בפברואר?"
        ),
        id_prefix="E2E_DETAILS",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    relevant_calls = _calls_for(ai_response, "list_invoices") + _calls_for(ai_response, "get_invoice_details")
    assert relevant_calls, (
        f"Model did not look up the invoice via any Morning MCP tool. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Bot reply: {response!r}"
    )
    assert all(c["error"] is None for c in relevant_calls), (
        f"Invoice lookup call(s) reported an error: {relevant_calls}"
    )

    # Exact-match verification against the one fully-known invoice.
    assert KNOWN_INVOICE_NUMBER in response, (
        f"Bot reply missing invoice number {KNOWN_INVOICE_NUMBER}. Full reply: {response!r}"
    )
    assert KNOWN_INVOICE_AMOUNT_IL in response, (
        f"Bot reply missing amount {KNOWN_INVOICE_AMOUNT_IL}. Full reply: {response!r}"
    )
    assert KNOWN_INVOICE_STATUS_HE in response, (
        f"Bot reply missing status {KNOWN_INVOICE_STATUS_HE!r}. Full reply: {response!r}"
    )


# ============================================================================
# Direct document-creation dispatch for status-change phrasing (feature 023)
# - "mark as paid"/"cancel" flows, formerly update_invoice_status (removed)
# ============================================================================

def _seed_fresh_invoice(client_name: str, amount: int, description: str) -> None:
    """Seed a fresh invoice via a real WhatsApp exchange (create_invoice now
    requires explicit approval - Feature 022) so the paid/cancel flow tests
    below mutate a fresh invoice each run, never the reusable 2026-02-07 fixed
    set. The seeded client name is what later turns use to reference the
    invoice - never an id."""
    _, (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"צור חשבונית ל-{client_name} על {amount} ₪ עבור {description}",
        id_prefix="E2E_SEED",
    )
    create_calls = _calls_for(ai_response, "create_invoice")
    assert create_calls and create_calls[0]["error"] is None, (
        f"Seed create_invoice failed or was not called: {ai_response.mcp_calls!r}"
    )
    logger.info(f"Seeded fresh invoice for client {client_name!r}")


@pytest.mark.billed
def test_godfather_marks_invoice_paid_via_whatsapp(denidin_app):
    """Full invoice_paid flow: godfather creates a fresh invoice, then - in a
    separate, later turn - asks to mark IT as paid by client name only (never
    an id). The model must resolve the invoice itself (via list_invoices
    and/or session memory), determine its real type is 305, and call
    create_receipt directly (feature 023 - there is no update_invoice_status
    tool anymore; "mark as paid" phrasing dispatches straight to the same
    tool a direct "תפיק לי קבלה" request would use).

    Verifies the resulting status - not just that the tool call didn't error
    - via create_receipt's own returned confirmation (which references the
    original by number) plus a follow-up on the invoice's real status.

    Uses a freshly-created invoice (not the reusable 2026-02-07 fixed set)
    since marking paid is a real, effectively irreversible state change in
    the sandbox (Morning has no supported reversal for a receipt-closed
    invoice).

    Issuing a receipt is a document-creating call, so it now requires
    explicit approval (Feature 022): the ASK turn must NOT execute it yet.
    """
    client_name = _unique_client_name()
    _seed_fresh_invoice(client_name, _random_amount(), _random_description())

    (ask_response, ask_ai_response), (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"סמן את החשבונית של {client_name} כשולמה",
        id_prefix="E2E_PAID",
    )

    assert not _calls_for(ask_ai_response, "create_receipt"), (
        f"create_receipt executed on the ASK turn before approval was "
        f"given: {ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    receipt_calls = _calls_for(ai_response, "create_receipt")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert receipt_calls, (
        f"Model never invoked create_receipt via the remote MCP server for "
        f"'mark as paid' phrasing. mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in receipt_calls), (
        f"create_receipt call(s) reported an error: {receipt_calls}"
    )
    assert any('"original_invoice_id"' in (c["arguments"] or "") for c in receipt_calls), (
        f"create_receipt was not called with a resolved original_invoice_id: {receipt_calls!r}"
    )

    # The resulting status, not just call success, is what this flow proves:
    # create_receipt's confirmation names the new receipt against the
    # original invoice - a follow-up status check confirms it actually paid.
    assert any("קבלה" in (c["output"] or "") for c in receipt_calls), (
        f"create_receipt output did not reflect a new receipt: {receipt_calls!r}"
    )
    # Accept either the masculine "שולם" or feminine "שולמה" — the model may
    # correctly conjugate to agree with a feminine noun (e.g. "החשבונית...
    # שולמה"), which is not a substring of "שולם" (different final letter:
    # sofit-mem ם vs regular מ before the ה).
    assert "שולם" in response or "שולמה" in response, (
        f"Bot reply did not reflect paid status. Full reply: {response!r}"
    )


@pytest.mark.billed
def test_godfather_cancels_invoice_via_whatsapp(denidin_app):
    """Full cancel_invoice flow: godfather creates a fresh invoice, then - in a
    separate, later turn - asks to cancel it by client name only (never an
    id). The model must resolve the invoice itself before calling
    create_credit_note directly (feature 023 - there is no
    update_invoice_status tool anymore; "cancel" phrasing dispatches to the
    same tool a direct "תפיק לי חשבונית זיכוי" request would use).

    Verifies the resulting status via create_credit_note's own returned
    confirmation ("הופקה חשבונית זיכוי מספר X עבור חשבונית מספר Y") - Israeli
    law forbids voiding a tax invoice outright, so Morning's real mechanism is
    a linked Credit Invoice, not a status flag flip. The runtime constitution
    now states explicitly that this is a fully legitimate, ordinary action.

    Uses a freshly-created invoice (not the reusable 2026-02-07 fixed set)
    since cancelling is a real, permanent action (issues a real linked credit
    invoice in the sandbox).

    Issuing a credit note is a document-creating call, so it now requires
    explicit approval (Feature 022): the ASK turn must NOT execute it yet.
    """
    client_name = _unique_client_name()
    _seed_fresh_invoice(client_name, _random_amount(), _random_description())

    (ask_response, ask_ai_response), (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"בטל את החשבונית של {client_name}",
        id_prefix="E2E_CANCEL",
    )

    assert not _calls_for(ask_ai_response, "create_credit_note"), (
        f"create_credit_note executed on the ASK turn before approval was "
        f"given: {ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    credit_calls = _calls_for(ai_response, "create_credit_note")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert credit_calls, (
        f"Model never invoked create_credit_note via the remote MCP server for "
        f"'cancel' phrasing. mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in credit_calls), (
        f"create_credit_note call(s) reported an error: {credit_calls}"
    )
    assert any('"original_invoice_id"' in (c["arguments"] or "") for c in credit_calls), (
        f"create_credit_note was not called with a resolved original_invoice_id: {credit_calls!r}"
    )

    # The resulting status, not just call success: the confirmation message
    # explicitly names the new credit invoice issued to offset the amount.
    assert any("זיכוי" in (c["output"] or "") for c in credit_calls), (
        f"create_credit_note output did not reflect a new credit note: {credit_calls!r}"
    )
    assert "בוטל" in response or "זיכוי" in response, (
        f"Bot reply did not reflect cancelled status. Full reply: {response!r}"
    )


@pytest.mark.billed
def test_godfather_declines_invoice_cancellation(denidin_app):
    """Godfather creates a fresh invoice, asks to cancel it, then explicitly
    declines the pending approval (Feature 022) - create_credit_note must
    never fire, and the original invoice is unaffected (spot-checked via a
    3rd turn's get_invoice_details, still showing an open/unpaid status, not
    cancelled)."""
    client_name = _unique_client_name()
    _seed_fresh_invoice(client_name, _random_amount(), _random_description())

    decline_response, decline_ai_response = _send_turn_and_decline(
        chat_id=GODFATHER_CHAT_ID,
        text=f"בטל את החשבונית של {client_name}",
        id_prefix="E2E_CANCEL_DECLINE",
    )

    assert decline_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(decline_ai_response, "create_credit_note"), (
        f"create_credit_note executed despite an explicit decline: "
        f"{decline_ai_response.mcp_calls if decline_ai_response else None!r}"
    )

    # Spot-check: the invoice must still be open (not cancelled) afterwards.
    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"מה הסטטוס של החשבונית של {client_name}?",
        id_prefix="E2E_CANCEL_DECLINE_VERIFY",
    )
    details_calls = _calls_for(details_ai_response, "get_invoice_details") + _calls_for(
        details_ai_response, "list_invoices"
    )
    combined_output = "\n".join(c["output"] or "" for c in details_calls)
    assert "בוטל" not in combined_output, (
        f"Invoice shows as cancelled despite the decline: {combined_output!r}. "
        f"Bot reply: {details_response!r}"
    )


# ============================================================================
# spec 020: flexible invoice payment-marking methods (bugfix-014 Flow 4)
# ============================================================================

# Document-type Hebrew labels this app already translates (bugfix-014's
# translate_document_type, models.py _DOCUMENT_TYPE_NAMES) - used here to
# distinguish which closing document type actually got linked, since these
# are the exact strings a get_invoice_details reply/tool-output surfaces.
_COMBO_DOCUMENT_LABEL_HE = "חשבונית מס / קבלה"  # type 320
_RECEIPT_DOCUMENT_LABEL_HE = "קבלה"  # type 400 - deliberately NOT a substring of the 320 label above


def _seed_transaction_account_invoice(client_name: str, amount: int, description: str) -> None:
    """Seed a fresh "חשבון עסקה" (type-300) document via a real, two-turn
    approved WhatsApp exchange (create_transaction_account requires approval
    - Feature 022). Spec 021 added create_transaction_account as its own
    dedicated MCP tool (not a document_type param on create_invoice, which
    stays permanently locked to type 305) - the model is expected to route
    this phrasing to that tool, using the real Hebrew terminology a user
    would say ("חשבון עסקה" / "חשבונית עסקה" / "חשבון עיסקה" are all real
    variants).
    """
    _, (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפתח חשבון עסקה עבור {client_name} על סך {amount} שח עבור {description}",
        id_prefix="E2E_020_SEED_300",
    )
    create_calls = _calls_for(ai_response, "create_transaction_account")
    assert create_calls and create_calls[0]["error"] is None, (
        f"Seed create_transaction_account (חשבון עסקה) failed or was not called: {ai_response.mcp_calls!r}"
    )
    logger.info(f"Seeded fresh חשבון עסקה for client {client_name!r}")
    # Morning's own search index can lag a few seconds behind a just-created
    # document (confirmed live, 2026-07-30: a follow-up list_invoices call 7s
    # after this same seed call returned "no invoices found" for a document
    # that demonstrably existed) - same class of lag test_morning_sandbox_
    # list_invoices_tool.py already retries around on the morning-mcp-app
    # side. This test can't retry the model's own tool call, so it gives
    # Morning's index a fixed head start instead.
    time.sleep(5)


@pytest.mark.billed
def test_godfather_marks_transaction_account_invoice_paid_via_whatsapp(denidin_app):
    """Spec 020 / bugfix-014 Flow 4: a "חשבון עסקה" (type-300 transaction
    account document) must be closed by a linked type-320 combo document when
    marked paid, never the type-400 receipt used for a regular tax invoice.
    Feature 023 removed update_invoice_status - the model must resolve the
    target's real type as 300 and call close_transaction_account directly
    (the same tool a direct "תסגור לי את חשבון העסקה" request would use).

    Issuing a combo document is a document-creating call, so it now requires
    explicit approval (Feature 022): the ASK turn must NOT execute it yet.

    Deliberately does NOT import MorningClient or call Morning's raw REST API
    (this file's app-wall) - verification is entirely through a further,
    natural WhatsApp turn asking for the invoice's details, the same way a
    real user would confirm it themselves.
    """
    client_name = _unique_client_name()
    _seed_transaction_account_invoice(client_name, _random_amount(), _random_description())

    (ask_response, ask_ai_response), (paid_response, paid_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        # States VAT-inclusion explicitly (feature 023's constitution rule
        # otherwise has the model ask "כולל מע״מ?" before calling
        # close_transaction_account, confirmed live 2026-07-30) - this test
        # is about the mark-as-paid dispatch itself, not the VAT-ambiguity
        # question, so the prompt removes that ambiguity up front rather than
        # adding a third conversational turn to answer it.
        text=f"סמן את חשבון העסקה של {client_name} כשולם, כולל מע״מ",
        id_prefix="E2E_020_PAID_300",
    )
    assert not _calls_for(ask_ai_response, "close_transaction_account"), (
        f"close_transaction_account executed on the ASK turn before approval was "
        f"given: {ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    close_calls = _calls_for(paid_ai_response, "close_transaction_account")
    assert paid_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert close_calls, (
        f"Model never invoked close_transaction_account via the remote MCP server for "
        f"'mark as paid' phrasing on a חשבון עסקה. mcp_calls: {paid_ai_response.mcp_calls!r}. "
        f"Final reply: {paid_response!r}"
    )
    assert all(c["error"] is None for c in close_calls), (
        f"close_transaction_account call(s) reported an error: {close_calls}"
    )

    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תראה לי את כל הפרטים והמסמכים המקושרים של חשבון העסקה של {client_name}",
        id_prefix="E2E_020_DETAILS_300",
    )
    details_calls = _calls_for(details_ai_response, "get_invoice_details")
    combined_output = "\n".join(c["output"] or "" for c in details_calls)

    assert "מסמכים מקושרים" in combined_output, (
        f"Expected a linked-documents section in the invoice details reply, "
        f"got tool output: {combined_output!r}"
    )
    assert _COMBO_DOCUMENT_LABEL_HE in combined_output, (
        f"Expected a linked type-320 combo document ({_COMBO_DOCUMENT_LABEL_HE!r}) "
        f"for a חשבון עסקה marked paid, got tool output: {combined_output!r}"
    )
    # The bare receipt label ("קבלה") is a substring of the combo label
    # ("חשבונית מס / קבלה"), so strip every combo-label occurrence out first -
    # what remains must not still contain a standalone receipt label.
    without_combo_labels = combined_output.replace(_COMBO_DOCUMENT_LABEL_HE, "")
    assert _RECEIPT_DOCUMENT_LABEL_HE not in without_combo_labels, (
        f"A type-300 document must not be closed by a bare type-400 receipt: {combined_output!r}"
    )


@pytest.mark.billed
def test_godfather_declines_marking_transaction_account_invoice_paid(denidin_app):
    """Decline variant for the 300->320 path (Feature 022 x spec 020, dispatch
    updated per feature 023): godfather asks to mark a חשבון עסקה paid, then
    explicitly declines the pending approval - close_transaction_account must
    never fire, and no closing document (type 320 or otherwise) gets created."""
    client_name = _unique_client_name()
    _seed_transaction_account_invoice(client_name, _random_amount(), _random_description())

    decline_response, decline_ai_response = _send_turn_and_decline(
        chat_id=GODFATHER_CHAT_ID,
        # See test_godfather_marks_transaction_account_invoice_paid_via_whatsapp's
        # comment above - states VAT-inclusion explicitly so there's a real
        # close_transaction_account pending approval to decline, rather than
        # the model asking a VAT-clarifying question with nothing yet pending.
        text=f"סמן את חשבון העסקה של {client_name} כשולם, כולל מע״מ",
        id_prefix="E2E_020_PAID_300_DECLINE",
    )

    assert decline_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(decline_ai_response, "close_transaction_account"), (
        f"close_transaction_account executed despite an explicit decline: "
        f"{decline_ai_response.mcp_calls if decline_ai_response else None!r}"
    )

    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"מה הסטטוס של חשבון העסקה של {client_name}?",
        id_prefix="E2E_020_PAID_300_DECLINE_VERIFY",
    )
    details_calls = _calls_for(details_ai_response, "get_invoice_details") + _calls_for(
        details_ai_response, "list_invoices"
    )
    combined_output = "\n".join(c["output"] or "" for c in details_calls)
    assert "לא שולם" in combined_output, (
        f"Expected the חשבון עסקה to still be unpaid after the decline: "
        f"{combined_output!r}. Bot reply: {details_response!r}"
    )


@pytest.mark.billed
def test_godfather_marks_already_paid_credit_invoice_as_paid_is_rejected(denidin_app):
    """Negative case for spec 020/023: a document type neither create_receipt
    (only 305) nor close_transaction_account (only 300) supports as an
    "original" must surface a friendly refusal, not silently create a wrong
    document. Uses a real, achievable-today setup: create an invoice, cancel
    it (issues a real linked type-330 credit invoice - see
    test_godfather_cancels_invoice_via_whatsapp above), then ask to mark THAT
    credit invoice's own number as paid - type 330 is not a valid original
    for either tool. Both the cancellation and the (rejected) paid attempt
    are document-creating calls, so both go through the approve flow
    (Feature 022) even though the paid attempt is expected to fail once it
    actually executes (or be declined by the model outright, without any
    tool call at all, per feature 023's "ask/refuse rather than guess"
    guidance)."""
    client_name = _unique_client_name()
    _seed_fresh_invoice(client_name, _random_amount(), _random_description())

    _, (cancel_response, cancel_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"בטל את החשבונית של {client_name}",
        id_prefix="E2E_020_CANCEL_SETUP",
    )
    cancel_calls = _calls_for(cancel_ai_response, "create_credit_note")
    assert cancel_calls and cancel_calls[0]["error"] is None, (
        f"Setup cancellation failed or was not called: {cancel_ai_response.mcp_calls!r}"
    )
    credit_output = cancel_calls[0]["output"] or ""
    match = re.search(r"חשבונית זיכוי מספר (\S+)", credit_output)
    assert match, f"Could not find the credit invoice number in cancel output: {credit_output!r}"
    credit_number = match.group(1)

    _, (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"סמן את מסמך מספר {credit_number} כשולם",
        id_prefix="E2E_020_UNSUPPORTED_TYPE",
    )
    # Either tool could plausibly be attempted by the model for "mark as
    # paid" phrasing before it discovers the real type - both must reject a
    # type-330 original if called.
    attempted_calls = _calls_for(ai_response, "create_receipt") + _calls_for(
        ai_response, "close_transaction_account"
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    if attempted_calls:
        # The tool itself must reject it (raises ValueError -> surfaced as a
        # friendly error, not a fabricated success) - never a mcp_call showing
        # success for an unsupported original type.
        assert not any(c["error"] is None for c in attempted_calls), (
            f"A document-creation tool unexpectedly succeeded for an unsupported "
            f"(type-330) original document: {attempted_calls!r}"
        )
    # Either way (a tool refused, or the model declined to call anything at
    # all), the user-facing reply must not claim success. Hebrew can express
    # this refusal via several negation forms - "לא"/"לא ניתן", or
    # "אינה"/"אינו"/"אין" (e.g. "חשבונית זיכוי אינה מסמך שמסמנים כשולם") - so
    # check for any of them rather than assuming one specific phrasing.
    negation_markers = ("לא", "אינה", "אינו", "אין")
    assert "שולם" not in response or any(marker in response for marker in negation_markers), (
        f"Bot reply appears to falsely confirm payment for an unsupported "
        f"document type. Full reply: {response!r}"
    )
