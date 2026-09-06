"""bugfix-038 (billed companion of tests/expensive/test_group_b_reference_approval_e2e.py)
- Group B document approvals (create_receipt/create_credit_note/
create_combo_document_as_reference) referencing an existing document must show the
user what they're actually approving, driven entirely through plain text -
no image/vision call involved, so this belongs in the free, no-approval-
needed `billed` tier rather than hiding behind an infrequent `expensive`
sweep (user, 2026-08-13: "make sure this is tested as billed tests and not
'wait' for expensives. There's no reason we need an image for this simple
test - the bug should have been caught earlier.").

Design confirmed live with the user 2026-08-13 (supersedes the original
"add display-only params to Group B tools" direction recorded in the spec):
Group B MCP tool signatures stay unchanged (thin - only `original_internal_morning_id`
plus their existing functional params). Instead, the model is required
(runtime_constitution.md) to call `get_invoice_details` on the original,
fresh, in the SAME turn, immediately before proposing any Group B call - and
`_build_pending_approval_details` correlates the pending call's
`original_internal_morning_id` against that same-turn `get_invoice_details` call's own
real output to build a two-part approval:
  - Part 1: the reference document's real data (client name, document date,
    amount at minimum - "bare minimum", user's own words; everything else
    get_invoice_details returns is shown too, EXCEPT the internal internal_morning_id
    line, which the constitution has always forbidden showing users).
  - Part 2: the actual request being approved (document type/amount/date/
    etc. - unchanged, already covered by the Group A approval-content tests
    in test_denidin_approval_content_and_vat_e2e.py).

RED as of 2026-08-13 - the fix isn't implemented yet. See
specs/bugfixes/bugfix-038-group-b-approval-missing-reference-data.md for the
full root-cause writeup.

NO MOCKING - real OpenAI API calls, real Morning MCP server, real Morning
sandbox. @pytest.mark.billed: can be run freely, no per-run approval needed.

Amounts stay under 100, per this suite's sandbox convention.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from tests.billed.denidin_mcp_e2e_helpers import (  # noqa: F401
    GODFATHER_CHAT_ID,
    _calls_for,
    _is_real_approval_prompt,
    _random_amount,
    _random_description,
    pick_existing_client,
    _send_turn,
    _send_turn_and_approve_capturing_approval,
)

logger = logging.getLogger(__name__)

pytestmark = pytest.mark.billed


def _today_il() -> str:
    """Today's real Israel-local calendar date, DD/MM/YYYY - the same format
    format_date_il uses, since these fixtures are always seeded and referenced
    "now" (no synthetic historical dates in this suite)."""
    return datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Jerusalem")).strftime("%d/%m/%Y")


def _seed_invoice_305(amount: int, description: str) -> tuple[str, str]:
    """Seed a fresh type-305 tax invoice via a real, approved WhatsApp
    exchange. Returns (client_name, invoice_number) - the real display number,
    extracted from create_invoice's own confirmation output, never a guess.

    Feature 059 item 5: only the invoice must be fresh - the client just has to
    exist, so it's drawn from the committed sandbox-client fixture rather than
    seeded conversationally (saves 2-3 billed turns + a sleep per test)."""
    from tests.billed.denidin_mcp_e2e_helpers import _send_turn_and_approve

    client_name = pick_existing_client()["name"]
    _, (_, seed_ai) = _send_turn_and_approve(
        GODFATHER_CHAT_ID,
        f"תפיק חשבונית מס ל{client_name} על סך {amount} ₪ כולל מע״מ, עבור {description}",
        id_prefix="B038_BILLED_SEED305",
    )
    seed_calls = _calls_for(seed_ai, "create_invoice")
    assert seed_calls and seed_calls[0]["error"] is None, (
        f"precondition failed - could not seed the type-305: "
        f"{seed_ai.mcp_calls if seed_ai else None!r}"
    )
    seeded_output = seed_calls[0]["output"] or ""
    invoice_number = next(
        (t for t in re.findall(r"\d{3,}", seeded_output) if t != str(amount)), None
    )
    assert invoice_number, f"could not read the seeded invoice number from {seeded_output!r}"
    return client_name, invoice_number


def _seed_transaction_account_300(amount: int, description: str) -> tuple[str, str]:
    """Seed a fresh type-300 חשבון עסקה for a brand-new client, VAT-inclusion
    stated explicitly up front (sidesteps the model's own mandatory VAT
    question - this test is about the approval's reference-data content, not
    that separate flow). Returns (client_name, document_number)."""
    client_name = pick_existing_client()["name"]  # Feature 059 item 5: any valid client works here
    _, ai_response = _send_turn(
        GODFATHER_CHAT_ID,
        f"תפתח חשבון עסקה עבור {client_name} על סך {amount} ₪ כולל מע״מ, עבור {description}",
        id_prefix="B038_BILLED_SEED300_ASK",
    )
    if not _calls_for(ai_response, "create_transaction_account"):
        _, ai_response = _send_turn(GODFATHER_CHAT_ID, "כן", id_prefix="B038_BILLED_SEED300_APPROVE")
    seed_calls = _calls_for(ai_response, "create_transaction_account")
    assert seed_calls and seed_calls[0]["error"] is None, (
        f"precondition failed - could not seed the type-300: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )
    seeded_output = seed_calls[0]["output"] or ""
    doc_number = next(
        (t for t in re.findall(r"\d{3,}", seeded_output) if t != str(amount)), None
    )
    assert doc_number, f"could not read the seeded document number from {seeded_output!r}"
    return client_name, doc_number


def _seed_transaction_account_300_with_real_id(amount: int, description: str) -> tuple[str, str, str]:
    """Like `_seed_transaction_account_300`, but also returns the REAL
    internal_morning_id (extracted from create_transaction_account's own
    confirmation output, which always includes it per format_invoice_
    confirmation) - needed to prove which id a later multi-turn call
    actually used. Returns (client_name, doc_number, real_internal_morning_id)."""
    client_name = pick_existing_client()["name"]  # Feature 059 item 5: any valid client works here
    _, ai_response = _send_turn(
        GODFATHER_CHAT_ID,
        f"תפתח חשבון עסקה עבור {client_name} על סך {amount} ₪ כולל מע״מ, עבור {description}",
        id_prefix="B038_BILLED_SEED300ID_ASK",
    )
    if not _calls_for(ai_response, "create_transaction_account"):
        _, ai_response = _send_turn(GODFATHER_CHAT_ID, "כן", id_prefix="B038_BILLED_SEED300ID_APPROVE")
    seed_calls = _calls_for(ai_response, "create_transaction_account")
    assert seed_calls and seed_calls[0]["error"] is None, (
        f"precondition failed - could not seed the type-300: "
        f"{ai_response.mcp_calls if ai_response else None!r}"
    )
    seeded_output = seed_calls[0]["output"] or ""
    doc_number = next(
        (t for t in re.findall(r"\d{3,}", seeded_output) if t != str(amount)), None
    )
    assert doc_number, f"could not read the seeded document number from {seeded_output!r}"
    id_match = re.search(r"מזהה פנימי \(internal_morning_id\): (\S+)", seeded_output)
    assert id_match, f"could not read the real internal_morning_id from {seeded_output!r}"
    return client_name, doc_number, id_match.group(1)


def _assert_reference_data_present(approval_text: str, *, client_name: str, doc_number: str, amount: int):
    """bugfix-038's core assertion: Part 1 of the approval (the reference
    document's own real data) must be present. User's own bare-minimum list
    (2026-08-13): client name, document date, amount - all as they are on the
    reference document. Document number is this test suite's own proxy for
    "which document" (the constitution forbids ever showing the internal
    Morning id - see this file's module docstring)."""
    missing = []
    if client_name.split()[0] not in approval_text:
        missing.append(f"client name ({client_name})")
    if _today_il() not in approval_text:
        missing.append(f"document date ({_today_il()})")
    if str(amount) not in approval_text:
        missing.append(f"amount ({amount})")
    if doc_number not in approval_text:
        missing.append(f"reference document number ({doc_number})")
    assert not missing, (
        f"the approval's reference-data section (Part 1) is missing {missing} - "
        f"the user cannot judge what they're approving. Approval text was: {approval_text!r}"
    )


def _assert_internal_id_never_leaked(approval_text: str, ai_response):
    """The constitution has always forbidden showing the internal Morning
    document id to the user - the reference-data block must not leak it, even
    though get_invoice_details' own raw output includes it (formatters.py's
    'מזהה פנימי (internal_morning_id)' line)."""
    lookup_calls = _calls_for(ai_response, "get_invoice_details")
    for call in lookup_calls:
        args = call.get("arguments") or ""
        match = re.search(r'"internal_morning_id"\s*:\s*"([^"]+)"', args)
        if match:
            leaked_id = match.group(1)
            assert leaked_id not in approval_text, (
                f"the internal Morning internal_morning_id {leaked_id!r} appeared in the "
                f"user-facing approval text - this must never be shown: {approval_text!r}"
            )


class TestGroupBReferenceApprovalBilled:
    """Text-only billed coverage for bugfix-038, one scenario per Group B
    tool - each proves the SAME core defect (blank/placeholder reference
    data) via the cheapest possible real reproduction."""

    @pytest.mark.sanity
    def test_receipt_against_existing_invoice_shows_reference_data(self, denidin_app):
        """create_receipt (400) closing an existing type-305 tax invoice."""
        amount = _random_amount()
        client_name, invoice_number = _seed_invoice_305(amount, _random_description())

        # Point at the freshly-seeded invoice as "the one I just issued"
        # (שהרגע הפקתי / האחרונה), not just "the invoice of {client}".
        # `pick_existing_client()` can (and does) land on a client that already
        # carries an unpaid invoice from an earlier run - then "the invoice of
        # X" is genuinely ambiguous and the model correctly asks which one,
        # which the one-clarifying-turn helper can't answer (seen 2026-09-04:
        # sandbox client מרסל אלמו still holding invoice #51816 from 2026-08-11,
        # on top of the one this test just seeded). "הרגע" is what a real user
        # says, uniquely picks the just-created invoice regardless of dates,
        # and doesn't leak the number.
        approval_text, approve_ai_response = _send_turn_and_approve_capturing_approval(
            GODFATHER_CHAT_ID,
            f"סמן את החשבונית האחרונה של {client_name}, זו שהרגע הפקתי, כשולמה - התשלום התקבל היום",
            id_prefix="B038_BILLED_RECEIPT",
            tool_name="create_receipt",
        )

        _assert_reference_data_present(
            approval_text, client_name=client_name, doc_number=invoice_number, amount=amount
        )
        receipt_calls = _calls_for(approve_ai_response, "create_receipt")
        assert receipt_calls and receipt_calls[0]["error"] is None, (
            f"create_receipt did not fire/succeed after approval: "
            f"{approve_ai_response.mcp_calls if approve_ai_response else None!r}"
        )
        _assert_internal_id_never_leaked(approval_text, approve_ai_response)

    def test_credit_note_against_existing_invoice_shows_reference_data(self, denidin_app):
        """create_credit_note (330) cancelling an existing type-305 tax invoice."""
        amount = _random_amount()
        client_name, invoice_number = _seed_invoice_305(amount, _random_description())

        approval_text, approve_ai_response = _send_turn_and_approve_capturing_approval(
            GODFATHER_CHAT_ID,
            f"בטל את החשבונית של {client_name}",
            id_prefix="B038_BILLED_CREDIT",
            tool_name="create_credit_note",
        )

        _assert_reference_data_present(
            approval_text, client_name=client_name, doc_number=invoice_number, amount=amount
        )
        credit_calls = _calls_for(approve_ai_response, "create_credit_note")
        assert credit_calls and credit_calls[0]["error"] is None, (
            f"create_credit_note did not fire/succeed after approval: "
            f"{approve_ai_response.mcp_calls if approve_ai_response else None!r}"
        )
        _assert_internal_id_never_leaked(approval_text, approve_ai_response)

    @pytest.mark.sanity
    def test_combo_document_against_existing_transaction_account_shows_reference_data(self, denidin_app):
        """create_combo_document_as_reference (320) closing an existing type-300 חשבון
        עסקה. Uses today's tool name - will be updated to
        create_combo_document_as_reference by this bugfix's rename task."""
        amount = _random_amount()
        client_name, doc_number = _seed_transaction_account_300(amount, _random_description())

        approval_text, approve_ai_response = _send_turn_and_approve_capturing_approval(
            GODFATHER_CHAT_ID,
            f"סמן את חשבון העסקה של {client_name} כשולם, כולל מע״מ, התשלום התקבל היום",
            id_prefix="B038_BILLED_COMBOREF",
            tool_name="create_combo_document_as_reference",
        )

        _assert_reference_data_present(
            approval_text, client_name=client_name, doc_number=doc_number, amount=amount
        )
        close_calls = _calls_for(approve_ai_response, "create_combo_document_as_reference")
        assert close_calls and close_calls[0]["error"] is None, (
            f"create_combo_document_as_reference did not fire/succeed after approval: "
            f"{approve_ai_response.mcp_calls if approve_ai_response else None!r}"
        )
        _assert_internal_id_never_leaked(approval_text, approve_ai_response)

    def test_multi_turn_clarification_uses_the_real_internal_id_not_the_display_number(self, denidin_app):
        """Regression test for a real production incident (manual testing,
        2026-08-13): a multi-turn "mark as paid" exchange - find the document,
        ask for the payment date, ask separately whether VAT is included,
        THEN approve - triggered the model to pass the document's DISPLAY
        NUMBER as `internal_morning_id` on a fresh get_invoice_details call,
        instead of the real internal id it had already correctly resolved
        twice earlier in the very same conversation. Root cause: the model's
        own immediately-preceding reply had just said "חשבון עסקה #40280" -
        it appears to have copied that visible number instead of pulling the
        real id from an earlier tool result. Morning rejected the malformed
        id outright and the whole request silently failed with no approval
        ever shown.

        Confirmed live as RED before the fix (this exact log trace, chat
        972522968679@c.us, 2026-08-13 13:52-13:53): `get_invoice_details`
        called with `internal_morning_id="40280"` - the bare display number.
        Fixed by (a) renaming `invoice_id`/`original_invoice_id` to
        `internal_morning_id`/`original_internal_morning_id` and the
        `list_invoices` `number` filter to `document_display_number`
        (structural distinction in the tool schema itself, not just prose),
        and (b) runtime_constitution.md's new "Two distinct identifiers
        exist for every document" section stating the rule explicitly and
        unconditionally.

        Deliberately does NOT state date/VAT inline in the opening message -
        the whole point is to force the same multi-turn shape (separate
        clarifying turns, with the model's own reply naming the display
        number in between) that produced the real failure. Bounded to 4
        clarifying turns so a genuine regression fails loudly rather than
        hanging."""
        amount = _random_amount()
        client_name, doc_number, real_id = _seed_transaction_account_300_with_real_id(
            amount, _random_description()
        )

        response, ai_response = _send_turn(
            GODFATHER_CHAT_ID, f"סמן את חשבון העסקה של {client_name} כשולם",
            id_prefix="B038_MULTITURN_ASK",
        )
        assert not _calls_for(ai_response, "create_combo_document_as_reference"), (
            f"executed before any approval was given: {ai_response.mcp_calls if ai_response else None!r}"
        )

        for i in range(4):
            if _is_real_approval_prompt(response):
                break
            answer = "כן" if "מע" in (response or "") else "היום"
            response, ai_response = _send_turn(
                GODFATHER_CHAT_ID, answer, id_prefix=f"B038_MULTITURN_CLARIFY_{i}"
            )
            assert not _calls_for(ai_response, "create_combo_document_as_reference"), (
                f"executed before the actual approval turn: "
                f"{ai_response.mcp_calls if ai_response else None!r}"
            )

        assert _is_real_approval_prompt(response), (
            f"never reached a real pending-approval prompt after 4 clarifying turns: {response!r}"
        )

        _, final_ai_response = _send_turn(GODFATHER_CHAT_ID, "כן", id_prefix="B038_MULTITURN_APPROVE")

        id_shaped_calls = (
            _calls_for(final_ai_response, "get_invoice_details")
            + _calls_for(final_ai_response, "create_combo_document_as_reference")
        )
        assert id_shaped_calls, (
            f"no id-shaped tool call fired on the approval turn: "
            f"{final_ai_response.mcp_calls if final_ai_response else None!r}"
        )
        for call in id_shaped_calls:
            try:
                args = json.loads(call.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            # The bug is the DISPLAY number landing in an id-shaped field. Assert
            # on those fields specifically - a whole-blob substring scan also
            # trips on a legitimate mention of the display number in the
            # free-text `description` ("...חשבון עסקה מספר 40445...", which is
            # correct and natural), which is NOT the bug (2026-09-03, Feature 059
            # triage: original_internal_morning_id was the correct GUID and the
            # call succeeded). Stricter, too: the id field must be exactly the
            # real resolved id, not merely "not the display number".
            for id_field in ("internal_morning_id", "original_internal_morning_id"):
                if args.get(id_field) is not None:
                    assert args[id_field] == real_id, (
                        f"{id_field} was {args[id_field]!r}, not the real resolved id "
                        f"{real_id!r} (the display number is {doc_number}) - this is the "
                        f"exact bug: {call!r}"
                    )
            assert call["error"] is None, (
                f"tool call failed - likely used a wrong/malformed id: {call!r}"
            )
        close_calls = _calls_for(final_ai_response, "create_combo_document_as_reference")
        assert close_calls and close_calls[0]["error"] is None, (
            f"create_combo_document_as_reference never actually succeeded: "
            f"{final_ai_response.mcp_calls if final_ai_response else None!r}"
        )
