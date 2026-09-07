"""Feature 069 — Phase 11 acceptance (DOCX fee-agreement routing), BILLED.

Real text-only OpenAI + real Morning sandbox. NO MOCKING.

US10: a `.docx` fee agreement arrives as a `documentMessage`. `DOCXExtractor`
classifies it `הסכם` (deterministic, no OpenAI call); the media path rewrites the
notification to a synthetic text turn carrying the verbatim stash; the shared
conversational path resolves the **near-match** client (Morning has 'מרים בן שחר';
the document says 'מרים בן שעיה') — the operator picks the existing candidate, so
no client is created and the fixture is repeatable — and records every fee
component post-turn. Two-hop fidelity (extraction lost nothing AND the detour
lost nothing), exhaustive per-field manifest. Recognition is text-only
(`config.ai_model`) → billed, not expensive.

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
    assert_ledger_event_matches_manifest_two_hop,
    ledger_events_for_chat,
    load_manifest,
    session_id_for_chat,
)
from tests.billed._ledger_069_post_turn_base import (
    FIX_DIR,
    SENDER_DATA,
    logger,
    reset_069_chat,  # noqa: F401 - autouse fixture, imported to register in this module
)
from tests.e2e_helpers import (
    ClarificationAnswerBank,
    create_real_notification,
    get_response,
)

_HTTP_PORT = 8770


def _docx_stash_text_for_chat(denidin_app, chat_id: str) -> str:
    """The synthetic media turn's verbatim stash, pulled from session history.

    The DOCX media path rewrites the `documentMessage` into a synthetic *text*
    turn whose `Message.content` is the stash frame (verbatim extracted text +
    rendered structured fields) — it does NOT populate `Message.extracted_text`
    for a routed-agreement docx, so `assert_extracted_text_persisted` does not
    apply here. The stash frame always contains `שחולץ מה` (mirrors
    `test_e2e_media_client_resolution._extractor_output_for_chat`)."""
    sm = denidin_app.ai_handler.session_manager
    session = sm.get_session(chat_id)
    for mid in session.message_ids:
        msg = sm.load_message(session, mid)
        if msg is None:
            continue
        content = getattr(msg, "content", None) or ""
        if getattr(msg, "ai_required_role", None) == "user" and "שחולץ מה" in content:
            return content
    return ""


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
                         phone="0525550110",
                         ensure_exists=bool(seed.get("ensure_exists")))
            time.sleep(2)

        from denidin import handle_text_message
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

        extractor_text = _docx_stash_text_for_chat(denidin_app, GODFATHER_CHAT_ID)
        assert extractor_text, (
            "US10: the synthetic docx media turn's verbatim stash was not found in "
            "session history (expected a user turn whose content contains 'שחולץ מה')"
        )
        extractor_output = {"extracted_text": extractor_text, "ledger_events": []}

        events = ledger_events_for_chat(denidin_app, GODFATHER_CHAT_ID)
        bank = ClarificationAnswerBank(
            [{"topic": "near_match_confirm",
              "keywords": ["מצאתי", "האם הכוונה", "התכוונת", "דומה", "נכון", "קיים", "חדש", "ליצור"],
              "answer": f"כן, הכוונה ללקוח הקיים {res['operator_picks']}, אל תיצור לקוח חדש"}],
            fallback=f"כן, הלקוח הקיים {res['operator_picks']}, אל תיצור חדש",
        )
        turn = 0
        text = first_reply
        ts = trigger_epoch
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
        # data-model.md §3 #10: event_datetime dates from the COMPLETING turn.
        # turn 0 = the synthetic media turn itself (ts=trigger_epoch); each detour
        # follow-up is ts + turn*30. `turn` now holds the turn that captured.
        completing_epoch = trigger_epoch + turn * 30
        assert_ledger_event_matches_manifest_two_hop(
            extractor_output, events, manifest,
            trigger_epoch=completing_epoch,
            session_id=session_id_for_chat(denidin_app, GODFATHER_CHAT_ID),
        )
