"""Feature 069 — Phase 11 acceptance (DOCX fee agreement routing), BILLED.

Real text-only OpenAI + real Morning sandbox. NO MOCKING.

US10: a `.docx` fee agreement arrives as a `documentMessage`. `DOCXExtractor`
classifies it `הסכם` (deterministic, no OpenAI call); the media path rewrites the
notification to a synthetic text turn carrying the verbatim stash; the shared
conversational path resolves the near-match client and records every fee
component post-turn. Two-hop fidelity (extraction lost nothing AND the detour
lost nothing). Recognition is text-only (`config.ai_model`) → billed, not expensive.

Split from the original `test_e2e_ledger_post_turn_capture.py` (2026-09-04). Its
own local HTTP server (port 8770) serves the docx to the media pipeline.

Run:
    scripts/run_single_test.sh "tests/billed/test_e2e_ledger_069_docx_billed.py::<node>"
"""
from __future__ import annotations

import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote

import pytest

from tests.billed.denidin_mcp_e2e_helpers import GODFATHER_CHAT_ID, _seed_client
from tests.billed._ledger_069_acceptance import (
    assert_event_matches_manifest,
    ledger_events_for_chat,
    load_manifest,
)
from tests.billed._ledger_069_post_turn_base import FIX_DIR, SENDER_DATA, logger
from tests.e2e_helpers import ClarificationAnswerBank, create_real_notification, get_response

_HTTP_PORT = 8770


@pytest.mark.billed
class TestLedgerPostTurnCaptureDocx:

    @pytest.fixture
    def docx_http_server(self):
        fixtures_dir = FIX_DIR

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=str(fixtures_dir), **kw)

            def translate_path(self, path):
                return super().translate_path(unquote(path))

            def log_message(self, *a):
                pass

        server = HTTPServer(("127.0.0.1", _HTTP_PORT), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        yield f"http://127.0.0.1:{_HTTP_PORT}"
        server.shutdown()

    def test_us10_docx_multi_component_agreement_two_hop(  # pylint: disable=too-many-locals
        self, denidin_app, docx_http_server
    ):
        docx_path = FIX_DIR / "agreement_doc_multi.docx"
        assert docx_path.exists(), (
            f"missing fixture {docx_path} — run "
            f"tests/fixtures/ledger_069/build_agreement_doc_multi.py"
        )
        manifest = load_manifest("agreement_doc_multi")
        res = manifest["client_resolution"]
        for seed in manifest.get("seed_clients", []):
            _seed_client(GODFATHER_CHAT_ID, seed["id_prefix"], name=seed["name"],
                         phone="0525550110")
            time.sleep(2)

        from denidin import handle_text_message
        import denidin as denidin_module

        notification = create_real_notification({
            "typeWebhook": "incomingMessageReceived",
            "timestamp": int(time.time()),
            "idMessage": "F069_US10_DOC",
            "instanceData": {"idInstance": 7103000000, "wid": "972501234567@c.us",
                             "typeInstance": "whatsapp"},
            "senderData": SENDER_DATA,
            "messageData": {
                "typeMessage": "documentMessage",
                "fileMessageData": {
                    "downloadUrl": f"{docx_http_server}/agreement_doc_multi.docx",
                    "fileName": "agreement_doc_multi.docx",
                    "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "caption": "ההסכם החתום, תרשום ביומן",
                },
            },
        })
        denidin_module._process_media_message(notification)  # media entry point
        first_reply = get_response(notification)
        logger.info("US10 media/synthetic-turn reply: %r", first_reply)

        events = ledger_events_for_chat(denidin_app, GODFATHER_CHAT_ID)
        bank = ClarificationAnswerBank(
            [{"topic": "near_match_confirm",
              "keywords": ["מצאתי", "האם הכוונה", "התכוונת", "דומה", "נכון"],
              "answer": f"כן, הכוונה ל{res['morning_name_after_resolution']}"}],
            fallback=f"כן, {res['morning_name_after_resolution']}",
        )
        turn = 0
        text = first_reply
        ts = int(time.time())
        while not events and turn < 4:
            turn += 1
            nxt, _ = bank.compose_answer(text or "")
            follow = create_real_notification({
                "typeWebhook": "incomingMessageReceived",
                "timestamp": ts + turn * 30,
                "idMessage": f"F069_US10_F{turn}",
                "instanceData": {"idInstance": 7103000000, "wid": "972501234567@c.us",
                                 "typeInstance": "whatsapp"},
                "senderData": SENDER_DATA,
                "messageData": {"typeMessage": "textMessage",
                                "textMessageData": {"textMessage": nxt}},
            })
            handle_text_message(follow)
            text = get_response(follow)
            events = ledger_events_for_chat(denidin_app, GODFATHER_CHAT_ID)

        assert events, "US10: no LedgerEvent after routing the docx agreement + detour"
        assert_event_matches_manifest(events, manifest)
