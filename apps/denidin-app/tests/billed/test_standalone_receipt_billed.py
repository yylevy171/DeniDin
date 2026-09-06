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
import re

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
    # itself: the standalone branch announces a receipt only ("קבלה"), whereas
    # every linked/combo variant announces "חשבונית מס/קבלה". Scanning the
    # client's whole document history for "חשבונית מס" instead is unreliable -
    # an existing client (pick_existing_client is random) routinely already
    # owns unrelated tax invoices from prior sandbox runs.
    receipt_output = receipt_calls[0]["output"] or ""
    assert "קבלה" in receipt_output and "חשבונית מס" not in receipt_output, (
        f"Standalone create_receipt should announce a receipt only, no tax document, "
        f"got: {receipt_output!r}"
    )

    # And a real follow-up turn independently confirms THIS receipt persisted
    # for the client (by the number Morning assigned it).
    receipt_number_match = re.search(r"מספר (\d+)", receipt_output)
    assert receipt_number_match, f"Could not read the receipt number from: {receipt_output!r}"
    receipt_number = receipt_number_match.group(1)

    details_response, details_ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"מה כל המסמכים שיש לי אצל {client_name}?",
        id_prefix="E2E_056_STANDALONE_VERIFY",
    )
    details_calls = _calls_for(details_ai_response, "list_invoices") + _calls_for(
        details_ai_response, "get_invoice_details"
    )
    combined_output = "\n".join(c["output"] or "" for c in details_calls)

    assert f"#{receipt_number}" in combined_output, (
        f"Standalone receipt #{receipt_number} did not show up in {client_name!r}'s "
        f"document list: {combined_output!r}"
    )
