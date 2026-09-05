"""E2E test (Feature 056, T009/T011): recording a deposit as a standalone
receipt - real webhook, real OpenAI Responses API, real Morning MCP server,
real Morning sandbox.

`create_receipt`'s standalone branch (no `original_internal_morning_id`) is
a document-creating call, so it requires explicit approval (Feature 022) -
the ASK turn must not execute it. `payment_date` is mandatory (bugfix-028
A3), so this uses `_send_turn_and_approve_receipt`, same as every other
create_receipt E2E test in this suite.

Deliberately does NOT import MorningClient or call Morning's raw REST API
(this file's app-wall, per denidin_mcp_e2e_helpers.py's module docstring) -
verification is entirely through a further, natural WhatsApp turn asking
for the receipt's details, the same way a real user would confirm it
themselves.

NO MOCKING anywhere. @pytest.mark.billed: real OpenAI billing on every run,
can be run freely - no per-run approval, no one-at-a-time restriction (see
CLAUDE.md/CONSTITUTION §VII).
"""
from __future__ import annotations

import json
import logging

import pytest

from .denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _calls_for,
    _random_amount,
    _random_description,
    pick_existing_client,
    _send_turn,
    _send_turn_and_approve_receipt,
)

logger = logging.getLogger(__name__)


@pytest.mark.billed
@pytest.mark.sanity
def test_godfather_records_a_deposit_as_a_standalone_receipt(denidin_app):
    """Feature 056 (T009): a godfather tells DeniDin about a refundable
    deposit just received from a known, existing client - money that isn't
    business income and has no invoice behind it at all. DeniDin must
    resolve the real client, ask for approval, and on "כן" create a
    standalone receipt - with no invoice ever created or implied.

    REQ-INV-014/015/018: standalone creation, required fields (client,
    amount, description, payment_date), free-text description (no
    structured reason code - the specific wording here, "פיקדון", is just
    one plausible example, not a distinct code path).
    """
    client_name = pick_existing_client()["name"]  # Feature 059 item 5: any existing client works
    amount = _random_amount()
    description = _random_description()

    (ask_response, ask_ai_response), (approve_response, approve_ai_response) = (
        _send_turn_and_approve_receipt(
            chat_id=GODFATHER_CHAT_ID,
            text=(
                f"קיבלתי פיקדון של {amount} שקל מ{client_name}, זה לא הכנסה, "
                f"תוציא לי קבלה על זה. התשלום התקבל היום."
            ),
            id_prefix="E2E_056_STANDALONE",
        )
    )
    assert not _calls_for(ask_ai_response, "create_receipt"), (
        f"create_receipt executed on the ASK turn before approval was given: "
        f"{ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )

    receipt_calls = _calls_for(approve_ai_response, "create_receipt")
    assert approve_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert receipt_calls and receipt_calls[0]["error"] is None, (
        f"Model never invoked create_receipt (or it errored) for a standalone-deposit "
        f"request: {approve_ai_response.mcp_calls if approve_ai_response else None!r}. "
        f"Final reply: {approve_response!r}"
    )
    # The standalone branch fires on original_internal_morning_id being None -
    # the model may express that either by omitting the key or by passing it
    # explicitly as null; both deserialize to None and hit the same server
    # branch. Assert on the VALUE, not the key's textual presence in the JSON
    # (a real UUID here would mean the model wrongly linked an invoice).
    receipt_args = json.loads(receipt_calls[0]["arguments"] or "{}")
    assert receipt_args.get("original_internal_morning_id") is None, (
        f"Expected the STANDALONE branch (original_internal_morning_id None/absent) to fire, "
        f"got arguments: {receipt_calls[0]['arguments']!r}"
    )

    # "no tax document created/attached" is proven by the create_receipt result
    # itself: the standalone branch produces a plain receipt (type 400, "קבלה"),
    # whereas every linked/combo variant is a "חשבונית מס / קבלה" document.
    # Scanning the client's whole document history for "חשבונית מס" instead is
    # unreliable - an existing client (pick_existing_client is random) routinely
    # already owns unrelated tax invoices from prior sandbox runs.
    receipt_output = receipt_calls[0]["output"] or ""
    receipt_doc = json.loads(receipt_output) if receipt_output else {}
    assert receipt_doc.get("type") == 400 and "חשבונית מס" not in (receipt_doc.get("type_name") or ""), (
        f"Standalone create_receipt should be a plain receipt (type 400, קבלה), not a "
        f"tax-linked/combo document, got: {receipt_output!r}"
    )

    # And a real follow-up turn independently confirms THIS receipt persisted
    # for the client (by the number Morning assigned it).
    receipt_number = receipt_doc.get("display_number")
    assert receipt_number, f"Could not read the receipt number from: {receipt_output!r}"
    receipt_number = str(receipt_number)

    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=(
            "תביא את הפרטים של הקבלה האחרונה מתוך מערכת החשבוניות ישירות. "
            "אני רוצה לוודא שלא נפלה טעות."
        ),
        id_prefix="E2E_056_STANDALONE_VERIFY",
    )
    # "מתוך מערכת החשבוניות ישירות" forces a live Morning read
    # (list_invoices / get_invoice_details), not an answer from the local
    # ledger-event cache (query_ledger_events).
    details_calls = _calls_for(details_ai_response, "list_invoices") + _calls_for(
        details_ai_response, "get_invoice_details"
    )
    assert details_calls, (
        f"follow-up turn did not query Morning directly - no list_invoices/"
        f"get_invoice_details call: "
        f"{details_ai_response.mcp_calls if details_ai_response else None!r}"
    )
    combined_output = "\n".join(c["output"] or "" for c in details_calls)
    payloads = [json.loads(c["output"]) for c in details_calls if c["output"]]
    # list_invoices returns a {"total_matched", "shown", "documents": [...]} wrapper;
    # get_invoice_details returns a bare document. Flatten both shapes.
    docs = [p for p in payloads if "documents" not in p] + [
        d for p in payloads for d in p.get("documents", [])
    ]

    # A real follow-up turn must re-query Morning and surface THIS receipt by
    # the number Morning assigned it - independent confirmation that the
    # standalone receipt actually persisted server-side.
    assert any(
        str(d.get("display_number")) == receipt_number and d.get("type") == 400
        for d in docs
    ), (
        f"the receipt fetched live from Morning is not the standalone receipt "
        f"#{receipt_number} (type 400) just created: {combined_output!r}"
    )
