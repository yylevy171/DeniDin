"""E2E test (Feature 056, T010/T011): cancelling an open transaction account
creates no document - real webhook, real OpenAI Responses API, real Morning
MCP server, real Morning sandbox.

`cancel_transaction_account` is a document-mutating call (even though it
creates no document itself), so it requires explicit approval (Feature 022,
REQ-INV-023) - the ASK turn must not execute it.

Deliberately does NOT import MorningClient or call Morning's raw REST API
(this file's app-wall, per denidin_mcp_e2e_helpers.py's module docstring) -
verification is entirely through a further, natural WhatsApp turn asking
for the account's details, the same way a real user would confirm it
themselves.

NO MOCKING anywhere. @pytest.mark.billed: real OpenAI billing on every run,
can be run freely - no per-run approval, no one-at-a-time restriction (see
CLAUDE.md/CONSTITUTION §VII).
"""
from __future__ import annotations

import logging

import pytest

from .denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _calls_for,
    _random_amount,
    _random_description,
    _send_turn,
    _send_turn_and_approve,
)
from .test_denidin_morning_invoice_lifecycle_e2e import _seed_transaction_account_invoice

logger = logging.getLogger(__name__)


@pytest.mark.billed
def test_godfather_cancels_a_transaction_account_via_whatsapp(denidin_app):
    """Feature 056 (T010): a godfather has an open transaction account
    (חשבון עסקה) for a deal that fell through - no money changed hands,
    nothing should be recorded as income. DeniDin must resolve the real
    account, ask for approval, and on "כן" cancel it - with NO document of
    any kind created, and never claiming the account was "paid".

    REQ-INV-020 (no document), REQ-INV-023 (RBAC/approval-gate wiring),
    REQ-INV-026 (never "שולם"/paid wording) - all from the real user's
    perspective, not just T005a's unit-level formatter check.

    Reuses `_seed_transaction_account_invoice` (test_denidin_morning_
    invoice_lifecycle_e2e.py) - the same real, two-turn-approved seeding
    helper that file's own "mark as paid" tests already use, so a fresh
    open חשבון עסקה genuinely exists before this test's own turns begin.
    """
    client_name = _seed_transaction_account_invoice(_random_amount(), _random_description())

    (ask_response, ask_ai_response), (cancel_response, cancel_ai_response) = _send_turn_and_approve(
        chat_id=GODFATHER_CHAT_ID,
        text=f"בטל את חשבון העסקה של {client_name}, העסקה לא יצאה לפועל",
        id_prefix="E2E_056_CANCEL_300",
    )
    assert not _calls_for(ask_ai_response, "cancel_transaction_account"), (
        f"cancel_transaction_account executed on the ASK turn before approval was "
        f"given: {ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    # The approval PROMPT ITSELF must be specific, not the fully generic
    # "there's a pending action" text - found missing entirely during manual
    # QA (2026-08-20): _build_pending_approval_details had no branch for
    # cancel_transaction_account at all, so the ASK turn's reply named
    # nothing - no client, no account, not even that this was a
    # cancellation. This is the exact gap that let it ship unnoticed: every
    # earlier assertion in this test (below) checks the outcome, never the
    # prompt the godfather actually has to read before answering "כן".
    assert ask_response is not None, "CRITICAL: no approval prompt at all (silent drop)"
    assert "יש פעולה הממתינה לאישורך" not in ask_response, (
        f"Approval prompt fell back to the fully generic text, naming nothing: {ask_response!r}"
    )
    assert client_name in ask_response or "עסקה" in ask_response, (
        f"Approval prompt must name the account/action being cancelled: {ask_response!r}"
    )

    cancel_calls = _calls_for(cancel_ai_response, "cancel_transaction_account")
    assert cancel_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert cancel_calls and cancel_calls[0]["error"] is None, (
        f"Model never invoked cancel_transaction_account (or it errored) for a "
        f"cancellation request: {cancel_ai_response.mcp_calls if cancel_ai_response else None!r}. "
        f"Final reply: {cancel_response!r}"
    )
    assert "שולם" not in (cancel_calls[0]["output"] or ""), (
        f"cancel_transaction_account's own output must never say 'paid': {cancel_calls[0]!r}"
    )
    assert cancel_response and "שולם" not in cancel_response, (
        f"The final reply to the godfather must never say the account was 'paid': {cancel_response!r}"
    )

    # Verified via Morning: a real follow-up "what documents do I have with
    # this client" call independently confirms REQ-INV-020 - zero new
    # documents were created as a side effect of cancellation. This
    # deliberately does NOT assert on the follow-up reply's status WORDING
    # (e.g. "שולם"/"לא שולם") - a separate, later get_invoice_details lookup
    # goes through the shared, unmodified translate_status path, which maps
    # Morning's status code 2 to "paid" regardless of whether it was closed
    # by a real payment or by this feature's cancellation (Morning itself
    # cannot distinguish the two at the status-code level, and nothing
    # persists anywhere that records which one happened here). That's a
    # known, accepted, explicitly out-of-scope gap for this feature -
    # tracked separately as specs/backlog/058-morning-docs-calculation-nuances,
    # not something this test should pin one way or the other.
    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"אילו מסמכים יש לי אצל {client_name}?",
        id_prefix="E2E_056_CANCEL_300_VERIFY",
    )
    details_calls = _calls_for(details_ai_response, "list_invoices") + _calls_for(
        details_ai_response, "get_invoice_details"
    )
    combined_output = "\n".join(c["output"] or "" for c in details_calls)

    for other_document_label in ("קבלה", "חשבונית זיכוי", "חשבונית מס / קבלה", "חשבונית מס"):
        assert other_document_label not in combined_output, (
            f"Cancellation must create NO document of any kind - found "
            f"{other_document_label!r} in the client's document list: {combined_output!r}"
        )
