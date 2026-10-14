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
    _seed_client,
    _send_button_tap,
    _send_turn,
    approval_buttons_on_screen,
)
from tests.expensive.test_deposit_offer_064_e2e import DepositImageE2EBase

_MAX_CLARIFYING_TURNS = 10

# Invented contact details for the clients the slips belong to (Morning will not create a client without them).
_CONTACTS = {
    "ליאת חדד": ("liat.hadad.066@example.com", "0501066001"),
    "איציק בן שלוש": ("itzik.ben.shalush.066@example.com", "0501066002"),
    "שלמה ביטון": ("shlomo.biton.066@example.com", "0501066003"),
}


def _events(denidin_app):
    return [json.loads(f.read_text(encoding="utf-8"))
            for f in Path(denidin_app.ledger_event_manager.storage_dir).glob("*.json")]


def _payment_of_documents(ai_response) -> Optional[dict]:
    """The first document that carries a payment, from whichever read tool the model used
    to show the details (get_invoice_details returns one document, list_invoices a list)."""
    for tool in ("get_invoice_details", "list_invoices"):
        for call in _calls_for(ai_response, tool):
            try:
                out = json.loads(call.get("output") or "")
            except ValueError:
                continue
            docs = out.get("documents") or [out] if isinstance(out, dict) else []
            for doc in docs:
                if isinstance(doc, dict) and doc.get("payment"):
                    return doc
    return None


@pytest.mark.expensive
class TestDepositMethods066E2E(DepositImageE2EBase):
    # The Bit / PayBox / cheque images sit directly in fixtures/media (064's slip is in ledger_events/).
    MEDIA_DIR = Path(__file__).parent.parent / "fixtures" / "media"

    def _slip_to_stored_document(self, denidin_app, http_server, filename, prefix, client):
        """The client exists in Morning before the slip arrives (seeded once, idempotently - none of the amounts is
        above the ID threshold, so no ID is needed). `client` is the one the slip itself carries (Bit: the payer is דודו בכר but the client is the one in the payment's description; PayBox: the payer; cheque: the drawer printed top right); none of them exists
        in Morning, so the flow adds it before the 320. The test knows the right client and answers for it
        whichever way the model goes: a model that asks who the client is is told, a model that proposes a
        different client is corrected, a model that goes straight ahead is simply approved at each step."""
        email, phone = _CONTACTS[client]
        _seed_client(GODFATHER_CHAT_ID, f"{prefix}_SEED", name=client, email=email, phone=phone, ensure_exists=True)
        reply, _ = self._send_image(http_server, filename, prefix)
        ai_response = None
        created = []
        for i in range(_MAX_CLARIFYING_TURNS):
            if approval_buttons_on_screen(GODFATHER_CHAT_ID):
                if not _is_real_approval_prompt(reply):  # the 064 offer
                    reply, ai_response = _send_button_tap(GODFATHER_CHAT_ID, BUTTON_ID_APPROVE, f"{prefix}_OFFER_YES{i}")
                elif client in reply:  # add_client, then the 320 itself
                    reply, ai_response = _send_button_tap(GODFATHER_CHAT_ID, BUTTON_ID_APPROVE, f"{prefix}_APPROVE{i}")
                else:
                    reply, ai_response = _send_turn(
                        GODFATHER_CHAT_ID, f"לא, הלקוח הוא {client} - תרשום את ההפקדה עבורו",
                        id_prefix=f"{prefix}_CORRECT{i}")
            else:  # a question (who is the client, which of several, ...) or anything else but an approval
                reply, ai_response = _send_turn(
                    GODFATHER_CHAT_ID, f"הלקוח הוא {client} - תרשום את ההפקדה עבורו",
                    id_prefix=f"{prefix}_CLIENT{i}")
            created = _calls_for(ai_response, "create_combo_document") if ai_response else []
            if created:
                break
        assert created and created[0]["error"] is None, f"320 not created: {reply!r}"
        assert client in json.dumps(created[0], ensure_ascii=False), f"320 created for the wrong client: {created[0]!r}"

        _, ai_response = _send_turn(
            GODFATHER_CHAT_ID, f"תציג את הפרטים המלאים של חשבונית המס קבלה האחרונה של {client}",
            id_prefix=f"{prefix}_DETAILS")
        doc = _payment_of_documents(ai_response)
        assert doc is not None, f"no document with a payment in the details answer: {ai_response.mcp_calls!r}"
        return client, doc

    @staticmethod
    def _cancel_320(client, prefix):
        """Leave Morning as found, so the next run (same client, same date) is not blocked by this run's
        document: a 330 cancelling the 320, then the negative 400 (Feature 099 - two approvals)."""
        reply, ai_response = _send_turn(GODFATHER_CHAT_ID, f"בטל את החשבונית האחרונה של {client}", id_prefix=f"{prefix}_CANCEL")
        credit = receipt = None
        for i in range(4):
            credit = credit or (_calls_for(ai_response, "create_credit_note") or [None])[0]
            receipt = receipt or (_calls_for(ai_response, "create_receipt") or [None])[0]
            if credit and receipt:
                break
            reply, ai_response = _send_turn(GODFATHER_CHAT_ID, "כן", id_prefix=f"{prefix}_CANCEL_YES{i}")
        assert credit and credit["error"] is None, f"the 330 was not created, the test left its 320 behind: {reply!r}"
        assert receipt and receipt["error"] is None, f"the negative 400 was not created: {reply!r}"

    def test_66_1_bit_screenshot(self, denidin_app, http_server):
        client, doc = self._slip_to_stored_document(denidin_app, http_server, "bit1.jpeg", "F066_1", "ליאת חדד")
        try:
            event = [e for e in _events(denidin_app) if e["source_type"] == "הפקדה"]
            assert event and event[0]["event_subtype"] == "ביט" and float(event[0]["amount"]) == 2500, event
            assert "דודו בכר" in (event[0].get("payer_name") or ""), f"the Bit sender must be the ledger payer: {event[0]!r}"
            pay = doc["payment"]
            assert (pay["type"], pay["app_type"]) == (10, 1), f"payment method must be Bit: {pay!r}"
            assert pay["amount"] == pytest.approx(2500) and pay["date"] == "2026-10-08", pay
            assert doc.get("client_name") in (None, client) or client in json.dumps(doc, ensure_ascii=False)
        finally:
            self._cancel_320(client, "F066_1")

    def test_66_2_paybox_screenshot(self, denidin_app, http_server):
        client, doc = self._slip_to_stored_document(denidin_app, http_server, "paybox1.jpeg", "F066_2", "איציק בן שלוש")
        try:
            event = [e for e in _events(denidin_app) if e["source_type"] == "הפקדה"]
            assert event and event[0]["event_subtype"] == "פייבוקס" and float(event[0]["amount"]) == 3000, event
            pay = doc["payment"]
            assert (pay["type"], pay["app_type"]) == (10, 3), f"payment method must be PayBox: {pay!r}"
            assert pay["amount"] == pytest.approx(3000) and pay["date"] == "2026-09-23", pay
        finally:
            self._cancel_320(client, "F066_2")

    def test_66_3_cheque_image(self, denidin_app, http_server):
        client, doc = self._slip_to_stored_document(denidin_app, http_server, "cheque1.jpeg", "F066_3", "שלמה ביטון")
        try:
            event = [e for e in _events(denidin_app) if e["source_type"] == "הפקדה"]
            assert event and event[0]["event_subtype"] == "צ׳ק" and float(event[0]["amount"]) == 1500, event
            assert event[0]["check_number"] == "80000062", event
            pay = doc["payment"]
            assert pay["type"] == 2 and pay["cheque_number"] == "80000062", f"payment must be the cheque: {pay!r}"
            assert pay["amount"] == pytest.approx(1500), pay
            assert (str(pay["bank_number"]), str(pay["bank_branch"]), str(pay["bank_account"])) == ("11", "117", "121022"), pay
        finally:
            self._cancel_320(client, "F066_3")
