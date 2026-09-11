"""Feature 069 — Phase 11 acceptance (DOCX fee-agreement routing), BILLED.

Real text-only OpenAI + real Morning sandbox. NO MOCKING.

US10: a `.docx` fee agreement arrives as a `documentMessage`. `DOCXExtractor`
classifies it `הסכם` (deterministic, no OpenAI call); the media path rewrites the
notification to a synthetic text turn carrying the verbatim stash; the shared
conversational path resolves the **near-match** client (Morning has 'מרים בן שחר';
the document says 'מרים בן שעיה') — the operator picks the existing candidate, so
no client is created and the fixture is repeatable — and records every fee
component post-turn. Two-hop fidelity is automatic (`source_kind: document`).
Recognition is text-only (`config.ai_model`) → billed, not expensive.

Seed / drive / assert, same as every Feature 069 acceptance test — the only
scenario-specific step is sending the `documentMessage` itself.

Run:
    scripts/run_single_test.sh "tests/billed/test_e2e_ledger_069_docx_billed.py::<node>"
"""
from __future__ import annotations

import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote

import pytest

from tests.billed.denidin_mcp_e2e_helpers import GODFATHER_CHAT_ID
from tests.billed._ledger_069_acceptance import assert_ledger_event_matches_manifest
from tests.billed._ledger_069_post_turn_base import (
    FIX_DIR,
    SENDER_DATA,
    drive_capture,
    logger,
    seed_scenario,
    clean_069_chat_history,  # noqa: F401 - autouse fixture, registers in this module
)
from tests.e2e_helpers import create_real_notification, get_response

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

    def test_us10_docx_multi_component_agreement_two_hop(self, denidin_app, docx_http_server):
        manifest = seed_scenario(denidin_app, "agreement_doc_multi")
        docx_name = manifest["source_file"]
        assert (FIX_DIR / docx_name).exists(), (
            f"missing fixture {FIX_DIR / docx_name} — run "
            f"tests/fixtures/ledger_069/build_agreement_doc_multi.py"
        )

        import denidin as denidin_module

        trigger_epoch = int(time.time())
        notification = create_real_notification({
            "typeWebhook": "incomingMessageReceived",
            "timestamp": trigger_epoch,
            "idMessage": "F069_US10_DOC",
            "instanceData": {"idInstance": 7103000000, "wid": "972501234567@c.us",
                             "typeInstance": "whatsapp"},
            "senderData": SENDER_DATA,
            "messageData": {
                "typeMessage": "documentMessage",
                "fileMessageData": {
                    "downloadUrl": f"{docx_http_server}/{docx_name}",
                    "fileName": docx_name,
                    "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "caption": "ההסכם החתום, תרשום ביומן",
                },
            },
        })
        denidin_module._process_media_message(notification)  # media entry point
        first_reply = get_response(notification)
        logger.info("US10 media/synthetic-turn reply: %r", first_reply)

        events, _, completing_epoch = drive_capture(
            denidin_app, "agreement_doc_multi", id_prefix="F069_US10",
            image_reply=first_reply, base_ts=trigger_epoch, max_turns=5,
        )
        assert events, "US10: no LedgerEvent after routing the docx agreement + detour"
        assert_ledger_event_matches_manifest(
            denidin_app, events, "agreement_doc_multi", completing_epoch,
        )
