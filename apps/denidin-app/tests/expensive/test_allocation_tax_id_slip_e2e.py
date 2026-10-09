"""Feature 098 acceptance T3.7 - a bank slip above the allocation threshold, EXPENSIVE.

Real **vision** OpenAI call (the slip image) + real text OpenAI calls + the real
Morning MCP server over its live dev tunnel + the real Morning sandbox. NO MOCKING.

The operator sends a bank slip for 7,000 ₪ (`bank_deposit_7k.jpeg`: a transfer
from Lux Clean for attorney fees) and asks for a tax invoice/receipt (320) for it,
naming a client that has no ID. 7,000 ₪ including VAT is 5,932 ₪ before VAT, above
the 5,000 ₪ threshold, so DeniDin must read the amount off the slip, ask for the
client's ID first, save it (its own approval), then issue the 320 (its own
approval) for the slip's amount.

App-wall: this file never imports morning-mcp-app code and never calls Morning's
REST API; every Morning check is a further natural WhatsApp turn.

🚨 EXPENSIVE - needs its own fresh explicit human approval for every run, one at a
time. Read `logs/test_logs/` (and the run's `pytest_results/` file) before re-running.

    scripts/run_single_test.sh \\
      "tests/expensive/test_allocation_tax_id_slip_e2e.py::TestAllocationTaxIdSlipE2E::test_slip_above_threshold_asks_for_id_then_issues_320"
"""
from __future__ import annotations

import logging
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

import pytest

from src.managers.pending_approval_manager import BUTTON_ID_APPROVE
from tests.billed.conftest import denidin_app, denidin_config, live_morning_tunnel  # noqa: F401 - fixtures
from tests.billed.denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    VALID_TAX_ID,
    _calls_for,
    _seed_client,
    _send_button_tap,
    _send_turn,
)
from tests.billed.test_allocation_tax_id_billed import (
    QUALIFYING_TOOLS,
    _assert_buttons_for,
    _assert_document_issued_on_tap,
    _assert_nothing_issued,
    _assert_plain_text_no_buttons,
    _asks_for_an_id,
    _digits,
    _gives_the_allocation_reason,
    _morning_documents,
    _morning_tax_id,
    _of_type,
)
from tests.e2e_helpers import create_real_notification, get_response

logger = logging.getLogger(__name__)

_MEDIA_DIR = Path(__file__).parent.parent / "fixtures" / "media"
_SLIP = "bank_deposit_7k.jpeg"
_SLIP_AMOUNT = 7000
_SLIP_PAYER = 'לוקס קלין בע"מ'  # the payer named on the slip: the client the 320 is for
CHAT = GODFATHER_CHAT_ID


@pytest.mark.expensive
class TestAllocationTaxIdSlipE2E:

    @pytest.fixture(scope="class")
    def http_server(self):
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=str(_MEDIA_DIR), **kw)

            def translate_path(self, path):
                return super().translate_path(unquote(path))

            def log_message(self, *a):
                pass

        server = HTTPServer(("127.0.0.1", 8768), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        yield "http://127.0.0.1:8768"
        server.shutdown()

    def _send_slip(self, http_server: str, caption: str, id_prefix: str):
        """The slip arrives as a real `imageMessage` through the real handler."""
        from denidin import handle_image_message
        import denidin

        notification = create_real_notification({
            "typeWebhook": "incomingMessageReceived",
            "timestamp": int(time.time()),
            "idMessage": f"{id_prefix}_IMG",
            "instanceData": {"idInstance": 7103000000, "wid": "972501234567@c.us",
                             "typeInstance": "whatsapp"},
            "senderData": {"chatId": CHAT, "sender": CHAT, "senderName": "E2E Godfather"},
            "messageData": {
                "typeMessage": "imageMessage",
                "fileMessageData": {
                    "downloadUrl": f"{http_server}/{_SLIP}",
                    "fileName": _SLIP,
                    "mimeType": "image/jpeg",
                    "caption": caption,
                    "jpegThumbnail": "",
                    "isForwarded": False,
                    "forwardingScore": 0,
                },
            },
        })
        handle_image_message(notification)
        return get_response(notification), denidin.denidin_app.last_response

    @staticmethod
    def _retire_client(client_name: str) -> None:
        """update_client cannot clear an ID, so rename the client instead: the payer's name is then
        free, and the next run seeds a fresh client with no ID."""
        retired = f'{client_name} (בדיקה {int(time.time())})'
        _send_turn(CHAT, f'שנה את שם הלקוח {client_name} ל{retired}', id_prefix="E2E_098_T37_RETIRE")
        _send_button_tap(CHAT, BUTTON_ID_APPROVE, id_prefix="E2E_098_T37_RETIRE_TAP")

    def test_slip_above_threshold_asks_for_id_then_issues_320(self, denidin_app, http_server):
        """T3.7 - slip (7,000 ₪) + "issue a tax invoice/receipt" for a client with no ID:
        the slip is read, the ID is asked for (plain text, nothing issued), saved on its
        own approval, then the 320 for 7,000 ₪ is issued on its own approval."""
        # The slip's own payer is the client, so DeniDin has no payer/client mismatch to ask
        # about. A fixed name that must have no ID: a client left with one by an earlier run is renamed away first.
        client_name = _seed_client(CHAT, "E2E_098_T37", name=_SLIP_PAYER, ensure_exists=True)[0]
        if _morning_tax_id(client_name, "E2E_098_T37_PRE") is not None:  # left by an earlier run
            self._retire_client(client_name)
            client_name = _seed_client(CHAT, "E2E_098_T37B", name=_SLIP_PAYER, ensure_exists=True)[0]
            assert _morning_tax_id(client_name, "E2E_098_T37_PRE2") is None, "no fresh client without an ID"

        id_saved = False
        try:
            # The slip arrives with no caption; the request comes as the next message.
            self._send_slip(http_server, "", "E2E_098_T37")
            response, ai_response = _send_turn(
                CHAT, 'תפיק חשבונית מס קבלה על ההפקדה הזו, עבור ייעוץ משפטי',
                id_prefix="E2E_098_T37_ASK",
            )

            # The slip's amount was read and the ID asked for, with the allocation number as the reason.
            _assert_nothing_issued(ai_response)
            _assert_plain_text_no_buttons(response)
            assert _asks_for_an_id(response), f"does not ask for the client's ID: {response!r}"
            assert _gives_the_allocation_reason(response), f"no allocation-number reason: {response!r}"
            assert str(_SLIP_AMOUNT) in _digits(response), f"slip amount not stated: {response!r}"

            # The ID -> approval to save it; tap -> saved, and the 320's own approval follows.
            response, ai_response = _send_turn(CHAT, VALID_TAX_ID, id_prefix="E2E_098_T37_ID")
            _assert_nothing_issued(ai_response)
            _assert_buttons_for("update_client")
            response, ai_response = _send_button_tap(CHAT, BUTTON_ID_APPROVE, id_prefix="E2E_098_T37_TAP_ID")
            update_calls = _calls_for(ai_response, "update_client")
            assert update_calls and update_calls[0]["error"] is None, (
                f"update_client did not run cleanly: {ai_response.mcp_calls if ai_response else None!r}"
            )
            id_saved = True
            assert not any(_calls_for(ai_response, t) for t in QUALIFYING_TOOLS), (
                "document issued without its own approval"
            )

            document = _assert_document_issued_on_tap("create_combo_document", "E2E_098_T37_DOC")
            assert document.get("amount") == _SLIP_AMOUNT, f"wrong amount: {document!r}"

            assert _morning_tax_id(client_name, "E2E_098_T37") == VALID_TAX_ID
            combos = _of_type(_morning_documents(client_name, "E2E_098_T37"), 320)
            assert len(combos) == 1 and combos[0].get("amount") == _SLIP_AMOUNT, (
                f"expected one {_SLIP_AMOUNT} ₪ 320: {combos!r}"
            )
        finally:
            if id_saved:
                self._retire_client(client_name)
