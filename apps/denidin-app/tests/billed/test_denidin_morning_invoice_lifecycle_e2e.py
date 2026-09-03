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
create_credit_note/create_combo_document_as_reference - there is no separate
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
    _seed_client,
    pick_existing_client,
    _send_turn,
    _send_turn_and_approve,
    _send_turn_and_approve_receipt,
    _send_turn_and_decline,
)

logger = logging.getLogger(__name__)

# ============================================================================
# get_invoice_details
# ============================================================================

# One fully-known, permanent ground-truth invoice (see GROUND_TRUTH_CLIENTS.md)
# - referenced here by client name + date only, the way a real user would;
# the model must resolve the actual internal_morning_id itself.
#
# Re-seeded 2026-08-12: the original fixture ("Test Client
# DENIDIN_TEST_1770474207", invoice #60006, seeded 2026-02-07) was never
# deleted (confirmed live via a direct list_invoices(number=...) lookup - the
# document and its embedded client name are both still there) - but its
# client was created before Feature 027 required documents to reference a
# real, resolvable Client record: it's a bare name+phone object with no
# Morning client_id at all (`'self': False`, no `id` key), so
# `resolve_client_name`'s mandatory-first search (2026-08-12 architecture)
# can never find it - `search_clients` searches real Client records, and
# this one was never saved as one. Not a data-loss bug; an architecture
# mismatch with a 2026-02-07 fixture that predates it. Replaced with a
# properly-seeded fixture via the same real-`add_client` mechanism as
# `זהבית צור`/`כרמלי דודי` (see GROUND_TRUTH_CLIENTS.md) - has a real
# client_id, genuinely resolvable.
KNOWN_INVOICE_NUMBER = "52046"
KNOWN_INVOICE_CLIENT = "רימונה כהן"
KNOWN_INVOICE_AMOUNT_IL = "156.75"
KNOWN_INVOICE_STATUS_HE = "שולם"  # paid


@pytest.mark.billed
@pytest.mark.sanity
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
            f"מהשנים עשר באוגוסט?"
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

def _seed_fresh_invoice(amount: int, description: str) -> str:
    """Seed a fresh invoice via a real WhatsApp exchange (create_invoice now
    requires explicit approval - Feature 022) so the paid/cancel flow tests
    below mutate a fresh invoice each run, never the reusable 2026-02-07 fixed
    set. Returns the client name actually used - never an id - for later turns
    to reference the invoice.

    Only asserts on the end state (a fresh invoice genuinely exists before
    the real test begins), never on the seeding turns themselves.

    Feature 059 item 5: the *invoice* must be fresh (marking it paid / cancelling
    it is effectively irreversible in the sandbox), but the *client* need not be
    - so this picks an existing sandbox client rather than paying 2-3 billed
    turns + a sleep to seed a throwaway one (`pick_existing_client`)."""
    client_name = pick_existing_client()["name"]
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
    return client_name


def _seed_fresh_invoice_for_a_fresh_client(amount: int, description: str) -> str:
    """Like `_seed_fresh_invoice`, but the invoice is created for a BRAND-NEW
    client (so that client owns exactly one invoice and a later
    "cancel the invoice of X" is unambiguous), and VAT treatment is stated
    explicitly in the seed text so the mandatory "כולל מע\"מ?" question
    (`runtime_constitution.md`) never interrupts the fixed ask->approve
    seeding turns.

    Feature 059 N1 fix (2026-09-03): `_seed_fresh_invoice` was changed on this
    branch (commit 77868e6) from a fresh client to `pick_existing_client()`,
    which made "בטל את החשבונית של {client}" ambiguous whenever the reused
    client already owned another open invoice - the model then (correctly)
    asks which one, and the 2-turn `_send_turn_and_approve` helper cannot
    answer. Seeding a fresh client removes that ambiguity at the source.
    VAT is stated as NOT included here purely to exercise that branch."""
    client_name, _, _ = _seed_client(GODFATHER_CHAT_ID, id_prefix="E2E_CANCEL_SEED")
    _, (response, ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"צור חשבונית ל-{client_name} על {amount} ₪ לא כולל מע\"מ עבור {description}",
        id_prefix="E2E_CANCEL_SEED_INV",
    )
    create_calls = _calls_for(ai_response, "create_invoice")
    assert create_calls and create_calls[0]["error"] is None, (
        f"N1 seed create_invoice failed or was not called: "
        f"{ai_response.mcp_calls if ai_response else None!r}. Reply: {response!r}"
    )
    logger.info(f"Seeded fresh invoice for a fresh client {client_name!r}")
    return client_name


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

    `create_receipt`'s `payment_date` is mandatory (2026-08-12) - the ASK
    turn deliberately gives no date, so the model must ask for one rather
    than silently assuming "today" (it may legitimately land on "today" as
    the actual answer once asked - a verbal "mark as paid" often does mean
    today - but never without asking). Handles both legitimate shapes: the
    model may ask an open question first (answered here with "היום"), or it
    may go straight to the pending create_receipt approval already showing
    a date for the user to confirm/correct - either way, only the FINAL
    "כן" may ever actually execute create_receipt.
    """
    client_name = _seed_fresh_invoice(_random_amount(), _random_description())

    (ask_response, ask_ai_response), (response, ai_response) = _send_turn_and_approve_receipt(
        chat_id=GODFATHER_CHAT_ID,
        text=f"סמן את החשבונית של {client_name} כשולמה",
        id_prefix="E2E_PAID",
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
    assert any('"original_internal_morning_id"' in (c["arguments"] or "") for c in receipt_calls), (
        f"create_receipt was not called with a resolved original_internal_morning_id: {receipt_calls!r}"
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
    # sofit-mem ם vs regular מ before the ה). Also accept phrasing that
    # substantively confirms paid status without the literal word "paid" -
    # a receipt being issued and payment being received are themselves proof
    # of paid status (found live, 2026-08-12: a real reply said "הופקה קבלה
    # ... התשלום התקבל היום" - receipt issued, payment received today -
    # which is correct and complete but never says "שולם"/"שולמה" outright).
    paid_status_markers = ("שולם", "שולמה", "הופקה", "הופק", "התקבל", "התקבלה")
    assert any(marker in response for marker in paid_status_markers), (
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
    client_name = _seed_fresh_invoice_for_a_fresh_client(
        _random_amount(), _random_description()
    )

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
    assert any('"original_internal_morning_id"' in (c["arguments"] or "") for c in credit_calls), (
        f"create_credit_note was not called with a resolved original_internal_morning_id: {credit_calls!r}"
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
    client_name = _seed_fresh_invoice(_random_amount(), _random_description())

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


def _seed_transaction_account_invoice(amount: int, description: str) -> str:
    """Seed a fresh "חשבון עסקה" (type-300) document via a real, two-turn
    approved WhatsApp exchange (create_transaction_account requires approval -
    Feature 022). Spec 021 added create_transaction_account as its own dedicated
    MCP tool (not a document_type param on create_invoice, which stays
    permanently locked to type 305) - the model is expected to route this
    phrasing to that tool, using the real Hebrew terminology a user would say
    ("חשבון עסקה" / "חשבונית עסקה" / "חשבון עיסקה" are all real variants).
    Returns the client name actually used.

    Only asserts on the end state (a fresh חשבון עסקה genuinely exists before
    the real test begins), never on the seeding turns themselves.

    Feature 059 item 5: same as `_seed_fresh_invoice` above - the *document*
    must be fresh (its paid/cancel state change is effectively irreversible in
    the sandbox), the *client* need not be, so this picks an existing sandbox
    client (`pick_existing_client`) rather than seeding a throwaway one.

    This phrasing never states VAT inclusion, so the model deterministically
    asks about it first (same mandatory rule as create_transaction_account's
    own direct test - found live, 2026-08-12, when this shared seed helper
    hit the exact same gap). Answered here with "לא" (not VAT-included) - a
    real, deliberately different answer from the "כן"/explicit-VAT-stated
    phrasing used elsewhere in this file, to also exercise that branch.
    """
    client_name = pick_existing_client()["name"]
    ask_response, ask_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפתח חשבון עסקה עבור {client_name} על סך {amount} שח עבור {description}",
        id_prefix="E2E_020_SEED_300_ASK",
    )
    assert not _calls_for(ask_ai_response, "create_transaction_account"), (
        f"create_transaction_account executed on the ASK turn before approval "
        f"was given: {ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    # Answer the mandatory VAT-inclusion question - "לא" (not included).
    vat_response, vat_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID, text="לא", id_prefix="E2E_020_SEED_300_VAT"
    )
    assert not _calls_for(vat_ai_response, "create_transaction_account"), (
        f"create_transaction_account executed before the actual approval turn: "
        f"{vat_ai_response.mcp_calls if vat_ai_response else None!r}"
    )

    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID, text="כן", id_prefix="E2E_020_SEED_300_APPROVE"
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
    return client_name


def _seed_transaction_account_invoice_for_a_fresh_client(amount: int, description: str) -> str:
    """Like `_seed_transaction_account_invoice`, but the חשבון עסקה is opened
    for a BRAND-NEW client, so that client owns exactly one type-300 and a
    later "סמן את חשבון העסקה של X כשולם" is unambiguous.

    Feature 059 N2 fix (2026-09-03): `_seed_transaction_account_invoice` was
    changed on this branch (commit 77868e6) from a fresh client to
    `pick_existing_client()` - same regression as `_seed_fresh_invoice` (see
    `_seed_fresh_invoice_for_a_fresh_client`). The VAT-inclusion question is
    still answered here with "לא" mid-seed exactly as the shared helper does."""
    client_name, _, _ = _seed_client(GODFATHER_CHAT_ID, id_prefix="E2E_020_SEED_300")
    _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפתח חשבון עסקה עבור {client_name} על סך {amount} שח עבור {description}",
        id_prefix="E2E_020_SEED_300F_ASK",
    )
    _send_turn(chat_id=GODFATHER_CHAT_ID, text="לא", id_prefix="E2E_020_SEED_300F_VAT")
    _, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID, text="כן", id_prefix="E2E_020_SEED_300F_APPROVE"
    )
    create_calls = _calls_for(ai_response, "create_transaction_account")
    assert create_calls and create_calls[0]["error"] is None, (
        f"N2 seed create_transaction_account (חשבון עסקה) failed or was not called: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )
    logger.info(f"Seeded fresh חשבון עסקה for a fresh client {client_name!r}")
    time.sleep(5)  # Morning search-index lag - see _seed_transaction_account_invoice
    return client_name


@pytest.mark.billed
def test_godfather_marks_transaction_account_invoice_paid_via_whatsapp(denidin_app):
    """Spec 020 / bugfix-014 Flow 4: a "חשבון עסקה" (type-300 transaction
    account document) must be closed by a linked type-320 combo document when
    marked paid, never the type-400 receipt used for a regular tax invoice.
    Feature 023 removed update_invoice_status - the model must resolve the
    target's real type as 300 and call create_combo_document_as_reference directly
    (the same tool a direct "תסגור לי את חשבון העסקה" request would use).

    Issuing a combo document is a document-creating call, so it now requires
    explicit approval (Feature 022): the ASK turn must NOT execute it yet.

    Deliberately does NOT import MorningClient or call Morning's raw REST API
    (this file's app-wall) - verification is entirely through a further,
    natural WhatsApp turn asking for the invoice's details, the same way a
    real user would confirm it themselves.
    """
    client_name = _seed_transaction_account_invoice_for_a_fresh_client(
        _random_amount(), _random_description()
    )

    (ask_response, ask_ai_response), (paid_response, paid_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        # States VAT-inclusion AND the payment date explicitly. Feature 023's
        # constitution rules otherwise have the model ask "כולל מע״מ?" and
        # "האם התשלום התקבל היום?" (both confirmed live - VAT 2026-07-30, the
        # payment_date question 2026-09-02) before calling
        # create_combo_document_as_reference. This test is about the
        # mark-as-paid dispatch itself, not those clarifications, so the prompt
        # removes both up front rather than adding conversational turns the
        # fixed ask->approve helper cannot answer.
        text=f"סמן את חשבון העסקה של {client_name} כשולם היום, כולל מע״מ",
        id_prefix="E2E_020_PAID_300",
    )
    assert not _calls_for(ask_ai_response, "create_combo_document_as_reference"), (
        f"create_combo_document_as_reference executed on the ASK turn before approval was "
        f"given: {ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    close_calls = _calls_for(paid_ai_response, "create_combo_document_as_reference")
    assert paid_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert close_calls, (
        f"Model never invoked create_combo_document_as_reference via the remote MCP server for "
        f"'mark as paid' phrasing on a חשבון עסקה. mcp_calls: {paid_ai_response.mcp_calls!r}. "
        f"Final reply: {paid_response!r}"
    )
    assert all(c["error"] is None for c in close_calls), (
        f"create_combo_document_as_reference call(s) reported an error: {close_calls}"
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
    explicitly declines the pending approval - create_combo_document_as_reference must
    never fire, and no closing document (type 320 or otherwise) gets created."""
    client_name = _seed_transaction_account_invoice(_random_amount(), _random_description())

    decline_response, decline_ai_response = _send_turn_and_decline(
        chat_id=GODFATHER_CHAT_ID,
        # See test_godfather_marks_transaction_account_invoice_paid_via_whatsapp's
        # comment above - states VAT-inclusion explicitly so there's a real
        # create_combo_document_as_reference pending approval to decline, rather than
        # the model asking a VAT-clarifying question with nothing yet pending.
        text=f"סמן את חשבון העסקה של {client_name} כשולם, כולל מע״מ",
        id_prefix="E2E_020_PAID_300_DECLINE",
    )

    assert decline_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(decline_ai_response, "create_combo_document_as_reference"), (
        f"create_combo_document_as_reference executed despite an explicit decline: "
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
    (only 305) nor create_combo_document_as_reference (only 300) supports as an
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
    client_name = _seed_fresh_invoice(_random_amount(), _random_description())

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
        ai_response, "create_combo_document_as_reference"
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
