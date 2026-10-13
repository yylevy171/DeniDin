"""Feature 066, scenario 66-4 - a cash deposit stated in text, from the message to the Morning document.

"קיבלתי 500 במזומן מ<client>": the ledger records a cash deposit of 500 with no confirmation question; the
admin then has the 320 created, and Morning shows payment method cash and the amount.

Real OpenAI + real Morning sandbox. NO MOCKING. @pytest.mark.billed.

    scripts/run_single_test.sh "tests/billed/test_cash_deposit_066_billed.py::test_66_4_cash_deposit_from_text"
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.billed.denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _calls_for,
    _is_real_approval_prompt,
    _send_turn,
    pick_existing_client,
)

pytestmark = pytest.mark.billed

_MAX_CLARIFYING_TURNS = 3


def _cash_events(denidin_app, client):
    found = []
    for f in Path(denidin_app.ledger_event_manager.storage_dir).glob("*.json"):
        event = json.loads(f.read_text(encoding="utf-8"))
        if event.get("source_type") == "הפקדה" and event.get("client_name") == client:
            found.append(event)
    return found


def test_66_4_cash_deposit_from_text(denidin_app):
    client = pick_existing_client()["name"]
    before = len(_cash_events(denidin_app, client))

    reply, ai_response = _send_turn(GODFATHER_CHAT_ID, f"קיבלתי 500 במזומן מ{client}", id_prefix="E2E_066_4_CASH")
    events = _cash_events(denidin_app, client)
    assert len(events) == before + 1, f"the cash deposit was not recorded: {reply!r}"
    event = events[-1]
    assert event["event_subtype"] == "מזומן" and float(event["amount"]) == 500, event
    assert not _is_real_approval_prompt(reply), f"recording a deposit must not ask for confirmation: {reply!r}"

    reply, ai_response = _send_turn(GODFATHER_CHAT_ID, f"תפיק חשבונית מס קבלה על ההפקדה של {client}", id_prefix="E2E_066_4_320")
    for i in range(_MAX_CLARIFYING_TURNS):
        if _is_real_approval_prompt(reply):
            break
        reply, ai_response = _send_turn(GODFATHER_CHAT_ID, "כן, היום", id_prefix=f"E2E_066_4_CLARIFY{i}")
    assert _is_real_approval_prompt(reply), f"never reached the 320 approval: {reply!r}"
    assert not _calls_for(ai_response, "create_combo_document"), "the 320 ran before its approval"

    _, ai_response = _send_turn(GODFATHER_CHAT_ID, "כן", id_prefix="E2E_066_4_APPROVE")
    created = _calls_for(ai_response, "create_combo_document")
    assert created and created[0]["error"] is None, f"320 not created: {ai_response.mcp_calls!r}"

    _, ai_response = _send_turn(
        GODFATHER_CHAT_ID, f"תציג את הפרטים המלאים של חשבונית המס קבלה האחרונה של {client}", id_prefix="E2E_066_4_DETAILS")
    docs = []
    for tool in ("get_invoice_details", "list_invoices"):
        for call in _calls_for(ai_response, tool):
            try:
                out = json.loads(call.get("output") or "")
            except ValueError:
                continue
            docs.extend(out.get("documents") or [out] if isinstance(out, dict) else [])
    doc = next((d for d in docs if isinstance(d, dict) and d.get("payment")), None)
    assert doc is not None, f"no document with a payment in the details lookup: {ai_response.mcp_calls!r}"
    assert doc["payment"]["type"] == 1, f"payment method must be cash: {doc['payment']!r}"
    assert doc["payment"]["amount"] == pytest.approx(500), doc["payment"]
