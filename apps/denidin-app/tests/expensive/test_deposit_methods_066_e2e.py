"""Feature 066 acceptance - Bit / PayBox / cheque deposit images, from the slip to the Morning document.

The admin sends the image, accepts the 064 offer, approves the 320, then asks for the document's details;
the check is on what Morning stored (via get_invoice_details), plus the ledger event.

Real vision OpenAI calls + real Morning sandbox. NO MOCKING.

🚨 EXPENSIVE - each test needs its own fresh explicit human approval, every run, one at a time.

    scripts/run_single_test.sh "tests/expensive/test_deposit_methods_066_e2e.py::TestDepositMethods066E2E::<name>"
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pytest

from src.managers.pending_approval_manager import BUTTON_ID_APPROVE
from tests.billed.denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _calls_for,
    _is_real_approval_prompt,
    _send_button_tap,
    _send_turn,
    approval_buttons_on_screen,
    pick_existing_client,
)
from tests.expensive.test_deposit_offer_064_e2e import DepositImageE2EBase

_MAX_CLARIFYING_TURNS = 3


def _events(denidin_app):
    return [json.loads(f.read_text(encoding="utf-8"))
            for f in Path(denidin_app.ledger_event_manager.storage_dir).glob("*.json")]


def _payment_of_documents(ai_response) -> Optional[dict]:
    for call in _calls_for(ai_response, "get_invoice_details"):
        try:
            doc = json.loads(call.get("output") or "")
        except ValueError:
            continue
        if isinstance(doc, dict) and doc.get("payment"):
            return doc
    return None


@pytest.mark.expensive
class TestDepositMethods066E2E(DepositImageE2EBase):

    def _slip_to_stored_document(self, denidin_app, http_server, filename, prefix):
        client = pick_existing_client()["name"]
        reply, _ = self._send_image(http_server, filename, f"הפקדה מהלקוח {client}, תרשום ביומן", prefix)
        assert approval_buttons_on_screen(GODFATHER_CHAT_ID), f"no offer after the slip: {reply!r}"

        reply, ai_response = _send_button_tap(GODFATHER_CHAT_ID, BUTTON_ID_APPROVE, f"{prefix}_OFFER_YES")
        for i in range(_MAX_CLARIFYING_TURNS):
            if _is_real_approval_prompt(reply):
                break
            reply, ai_response = _send_turn(GODFATHER_CHAT_ID, "כן", id_prefix=f"{prefix}_CLARIFY{i}")
        assert _is_real_approval_prompt(reply), f"never reached the 320 approval: {reply!r}"
        assert not _calls_for(ai_response, "create_combo_document"), "the 320 ran before its approval"

        _, ai_response = _send_button_tap(GODFATHER_CHAT_ID, BUTTON_ID_APPROVE, f"{prefix}_320_YES")
        created = _calls_for(ai_response, "create_combo_document")
        assert created and created[0]["error"] is None, f"320 not created: {ai_response.mcp_calls!r}"

        _, ai_response = _send_turn(
            GODFATHER_CHAT_ID, f"תציג את הפרטים המלאים של חשבונית המס קבלה האחרונה של {client}",
            id_prefix=f"{prefix}_DETAILS")
        doc = _payment_of_documents(ai_response)
        assert doc is not None, f"no get_invoice_details result with a payment: {ai_response.mcp_calls!r}"
        return client, doc

    def test_66_1_bit_screenshot(self, denidin_app, http_server):
        client, doc = self._slip_to_stored_document(denidin_app, http_server, "bit1.jpeg", "F066_1")
        event = [e for e in _events(denidin_app) if e["source_type"] == "הפקדה"]
        assert event and event[0]["event_subtype"] == "ביט" and float(event[0]["amount"]) == 2500, event
        pay = doc["payment"]
        assert (pay["type"], pay["app_type"]) == (10, 1), f"payment method must be Bit: {pay!r}"
        assert pay["amount"] == pytest.approx(2500) and pay["date"] == "2026-10-08", pay
        assert doc.get("client_name") in (None, client) or client in json.dumps(doc, ensure_ascii=False)

    def test_66_2_paybox_screenshot(self, denidin_app, http_server):
        client, doc = self._slip_to_stored_document(denidin_app, http_server, "paybox1.jpeg", "F066_2")
        event = [e for e in _events(denidin_app) if e["source_type"] == "הפקדה"]
        assert event and event[0]["event_subtype"] == "פייבוקס" and float(event[0]["amount"]) == 3000, event
        pay = doc["payment"]
        assert (pay["type"], pay["app_type"]) == (10, 3), f"payment method must be PayBox: {pay!r}"
        assert pay["amount"] == pytest.approx(3000) and pay["date"] == "2026-09-23", pay

    def test_66_3_cheque_image(self, denidin_app, http_server):
        client, doc = self._slip_to_stored_document(denidin_app, http_server, "cheque1.jpeg", "F066_3")
        event = [e for e in _events(denidin_app) if e["source_type"] == "הפקדה"]
        assert event and event[0]["event_subtype"] == "צ׳ק" and float(event[0]["amount"]) == 1500, event
        assert event[0]["check_number"] == "80000062", event
        pay = doc["payment"]
        assert pay["type"] == 2 and pay["cheque_number"] == "80000062", f"payment must be the cheque: {pay!r}"
        assert pay["amount"] == pytest.approx(1500), pay
        assert (str(pay["bank_number"]), str(pay["bank_branch"]), str(pay["bank_account"])) == ("11", "117", "121022"), pay
