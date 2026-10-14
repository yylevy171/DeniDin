"""Feature 071 acceptance (71-1 / 71-2, ledger side) - a PDF now goes through the same single-call
extraction as an image, so a fee-agreement PDF is recorded in the ledger and any other PDF is not.

The existing PDF tests in test_media_e2e.py (reply + persisted text) are unchanged; this file adds the
ledger assertions the approved scenarios call for.

Real OpenAI (the PDF goes to the model as one input_file) + real Morning sandbox. NO MOCKING.

🚨 EXPENSIVE - each test needs its own fresh explicit human approval, every run, one at a time.

    scripts/run_single_test.sh "tests/expensive/test_pdf_ledger_071_e2e.py::TestPdfLedger071E2E::<name>"
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import quote

import pytest

from tests.billed._ledger_069_post_turn_base import drive_capture, seed_scenario
from tests.billed.denidin_mcp_e2e_helpers import GODFATHER_CHAT_ID
from tests.e2e_helpers import assert_response_exists, create_real_notification, get_full_reply
from tests.expensive.test_deposit_offer_064_e2e import DepositImageE2EBase, _SENDER_DATA

_PDF_DIR = Path(__file__).parent.parent / "fixtures" / "media"


def _events(denidin_app):
    return [json.loads(f.read_text(encoding="utf-8"))
            for f in Path(denidin_app.ledger_event_manager.storage_dir).glob("*.json")]


@pytest.mark.expensive
class TestPdfLedger071E2E(DepositImageE2EBase):

    @pytest.fixture(scope="class")
    def http_server(self):
        import threading
        from http.server import HTTPServer, SimpleHTTPRequestHandler
        from urllib.parse import unquote

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=str(_PDF_DIR), **kw)

            def translate_path(self, path):
                return super().translate_path(unquote(path))

            def log_message(self, *a):
                pass

        server = HTTPServer(("127.0.0.1", 8769), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        yield "http://127.0.0.1:8769"
        server.shutdown()

    def _send_pdf(self, http_server, filename, id_prefix, caption=""):
        from denidin import handle_document_message

        trigger_epoch = int(time.time())
        notification = create_real_notification({
            "typeWebhook": "incomingMessageReceived", "timestamp": trigger_epoch, "idMessage": f"{id_prefix}_PDF",
            "instanceData": {"idInstance": 7103000000, "wid": "972501234567@c.us", "typeInstance": "whatsapp"},
            "senderData": _SENDER_DATA,
            "messageData": {"typeMessage": "documentMessage", "fileMessageData": {
                "downloadUrl": f"{http_server}/{quote(filename)}", "fileName": filename,
                "mimeType": "application/pdf", "caption": caption, "jpegThumbnail": ""}},
        })
        handle_document_message(notification)
        reply = get_full_reply(notification)
        assert_response_exists(reply)
        return reply, trigger_epoch

    def test_71_1_fee_proposal_pdf_is_recorded_as_an_agreement(self, denidin_app, http_server):
        manifest = seed_scenario(denidin_app, "agreement_pdf_roei")
        reply, epoch = self._send_pdf(http_server, manifest["source_file"], "F071_1", caption="ההסכם, תרשום ביומן")
        events, transcript, _ = drive_capture(
            denidin_app, "agreement_pdf_roei", image_reply=reply, base_ts=epoch, id_prefix="F071_1", max_turns=5)
        assert events, f"the agreement in the PDF was never recorded; turns: {[t['sent'] for t in transcript]!r}"
        for event in events:
            assert event["source_type"] == "הסכם", event
            assert event["client_name"] == manifest["resolution"]["name"], event

    def test_71_2_non_agreement_pdf_records_nothing(self, denidin_app, http_server):
        reply, _ = self._send_pdf(http_server, "מודול 4.pdf", "F071_2")
        assert reply, "no summary reply"
        assert _events(denidin_app) == [], f"a non-agreement PDF must record nothing: {_events(denidin_app)!r}"
