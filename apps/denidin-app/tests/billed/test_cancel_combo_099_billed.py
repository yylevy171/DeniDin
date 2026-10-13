"""Feature 099 acceptance - cancelling a 320 (חשבונית מס / קבלה) takes two documents:
a credit note (330) and a negative receipt (400) that reverses the cash side.

Real webhook -> real OpenAI Responses API -> real Morning MCP server -> real Morning
sandbox. NO MOCKING. @pytest.mark.billed. Scenarios 99-1..99-4 (approved 2026-10-09).

Run one at a time:
    scripts/run_single_test.sh "tests/billed/test_cancel_combo_099_billed.py::<test>"
"""
from __future__ import annotations

import json
from typing import Tuple

import pytest

from tests.billed.denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _calls_for,
    _is_real_approval_prompt,
    _random_description,
    _send_turn,
    pick_existing_client,
)
from tests.billed.test_bugfix_071_vat_rules_billed import _drive_to_approval, _created, _seed_document

pytestmark = pytest.mark.billed

AMOUNT = 50


def _seed_combo(id_prefix: str) -> Tuple[str, str]:
    """A fresh 320 of AMOUNT paid by bank transfer, through the real conversation."""
    client_name = pick_existing_client()["name"]
    _, _, ai_response = _drive_to_approval(
        f'תפיק חשבונית מס קבלה ללקוח {client_name} על סך {AMOUNT} ₪ כולל מע"מ, '
        f"עבור {_random_description()}, שולם היום בהעברה בנקאית",
        "create_combo_document", id_prefix,
    )
    call = _created(ai_response, "create_combo_document")
    return client_name, str(json.loads(call["output"])["display_number"])


def _cancel_request(client_name: str) -> str:
    return f"בטל את החשבונית האחרונה של {client_name}"


def _ask_cancel(client_name: str, id_prefix: str):
    reply, ai_response = _send_turn(GODFATHER_CHAT_ID, _cancel_request(client_name), id_prefix=f"{id_prefix}_ASK")
    assert not _calls_for(ai_response, "create_credit_note"), "330 ran before approval"
    assert _is_real_approval_prompt(reply), f"no approval prompt for the 330: {reply!r}"
    return reply


def _approve_330(client_name: str, id_prefix: str):
    """Ask to cancel, approve the 330, and return (the next reply, its AIResponse)."""
    _ask_cancel(client_name, id_prefix)
    reply, ai_response = _send_turn(GODFATHER_CHAT_ID, "כן", id_prefix=f"{id_prefix}_APPROVE_330")
    call = _calls_for(ai_response, "create_credit_note")
    assert call and call[0]["error"] is None, f"330 not created: {ai_response.mcp_calls!r}"
    return reply, ai_response


@pytest.mark.sanity
def test_99_1_cancel_320_creates_330_then_negative_400(denidin_app):
    client_name, number = _seed_combo("E2E_099_1_SEED")
    reply, ai_response = _approve_330(client_name, "E2E_099_1")
    assert not _calls_for(ai_response, "create_receipt"), "the 400 ran before its own approval"
    assert _is_real_approval_prompt(reply), f"the 330 was done but no approval was asked for the 400: {reply!r}"
    reply, ai_response = _send_turn(GODFATHER_CHAT_ID, "כן", id_prefix="E2E_099_1_APPROVE_400")
    calls = _calls_for(ai_response, "create_receipt")
    assert calls and calls[0]["error"] is None, f"400 not created: {ai_response.mcp_calls!r}"
    doc = json.loads(calls[0]["output"])
    assert (doc.get("amount") or 0) < 0, f"the 400 must be negative: {doc!r}"
    assert abs(doc["amount"]) == pytest.approx(AMOUNT, abs=0.02), doc
    assert reply, "no final reply"


def test_99_2_declining_the_400_leaves_cash_unreversed(denidin_app):
    client_name, _ = _seed_combo("E2E_099_2_SEED")
    reply, _ = _approve_330(client_name, "E2E_099_2")
    assert _is_real_approval_prompt(reply), f"no approval asked for the 400: {reply!r}"
    reply, ai_response = _send_turn(GODFATHER_CHAT_ID, "לא", id_prefix="E2E_099_2_DECLINE_400")
    assert not _calls_for(ai_response, "create_receipt"), "the 400 was created after being declined"
    assert reply and any(w in reply for w in ("כסף", "תשלום", "קבלה", "מזומן", "הצד")), (
        f"the bot must say the cash side is still not reversed: {reply!r}"
    )


def test_99_3_already_cancelled_320_is_refused(denidin_app):
    client_name, _ = _seed_combo("E2E_099_3_SEED")
    _approve_330(client_name, "E2E_099_3_FIRST")
    _send_turn(GODFATHER_CHAT_ID, "לא", id_prefix="E2E_099_3_SKIP_400")
    reply, ai_response = _send_turn(GODFATHER_CHAT_ID, _cancel_request(client_name), id_prefix="E2E_099_3_AGAIN")
    assert not _calls_for(ai_response, "create_credit_note"), "a second 330 was attempted"
    assert not _calls_for(ai_response, "create_receipt"), "a 400 was attempted on a cancelled 320"
    assert reply and "בוטל" in reply, f"the bot must say it is already cancelled: {reply!r}"


def test_99_4_cancelling_a_305_creates_only_a_330(denidin_app):
    client_name, _ = _seed_document("חשבונית מס", 'כולל מע"מ', "E2E_099_4_SEED")
    reply, ai_response = _approve_330(client_name, "E2E_099_4")
    assert not _calls_for(ai_response, "create_receipt"), "a 305 cancellation must not create a 400"
    assert not (reply and _is_real_approval_prompt(reply)), f"no second approval expected: {reply!r}"
