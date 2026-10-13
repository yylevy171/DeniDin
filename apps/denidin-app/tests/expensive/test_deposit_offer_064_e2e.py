"""Feature 064 acceptance - after a bank-evidence image is recorded, the bot OFFERS (yes/no
buttons) to create a חשבונית מס / קבלה. Scenarios 64-1, 64-2, 64-4 (approved 2026-10-09).

Real vision OpenAI call + real Morning sandbox. NO MOCKING.

🚨 EXPENSIVE - each test needs its own fresh explicit human approval, every run, one at a time.

    scripts/run_single_test.sh "tests/expensive/test_deposit_offer_064_e2e.py::TestDepositOffer064E2E::<name>"
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

import pytest

from src.managers.pending_approval_manager import BUTTON_ID_APPROVE, BUTTON_ID_DECLINE
from tests.billed._ledger_069_acceptance import load_manifest
from tests.billed._ledger_069_post_turn_base import seed_scenario
from tests.billed.denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    NoMorningTunnelError,
    _calls_for,
    _send_button_tap,
    _send_turn,
    _track_approval_buttons,
    approval_buttons_on_screen,
    get_button_send,
    require_live_morning_tunnel,
)
from src.models.config import AppConfiguration
from tests.e2e_helpers import (
    assert_response_exists,
    create_real_notification,
    get_response,
    wipe_chat_messages_on_disk,
)

logger = logging.getLogger(__name__)

_MEDIA_DIR = Path(__file__).parent.parent / "fixtures" / "media" / "ledger_events"
_SENDER_DATA = {"chatId": GODFATHER_CHAT_ID, "sender": GODFATHER_CHAT_ID, "senderName": "E2E Godfather"}
_OFFER_WORDS = ("חשבונית מס", "קבלה")
_ARTIFACT_MANIFEST = "deposit_exact_match"  # payer is an existing Morning client; amount 1500


class DepositImageE2EBase:
    """Shared infrastructure (fixtures + image driver) for the deposit-image acceptance tests (064, 066)."""

    MEDIA_DIR = _MEDIA_DIR  # the folder the fake Green API file server serves; a subclass may point elsewhere

    @pytest.fixture(scope="class")
    def http_server(self):
        media_dir = self.MEDIA_DIR

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=str(media_dir), **kw)

            def translate_path(self, path):
                return super().translate_path(unquote(path))

            def log_message(self, *a):
                pass

        server = HTTPServer(("127.0.0.1", 8768), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        yield "http://127.0.0.1:8768"
        server.shutdown()

    @pytest.fixture(scope="class")
    def denidin_app(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
        if not config_path.exists():
            pytest.skip("config.test.json not found")
        from tests.e2e_helpers import sanity_worker_data_root

        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        root = sanity_worker_data_root()
        config.data_root = str(root)
        config.memory["session"]["storage_dir"] = str(root / "sessions")
        config.memory["longterm"]["storage_dir"] = str(root / "memory")
        config.godfather_phone = GODFATHER_CHAT_ID
        try:
            require_live_morning_tunnel(Path(config.mcp["morning_status_file"]),
                                        config.mcp.get("url_max_age_seconds", 0) or 0)
        except NoMorningTunnelError as exc:
            pytest.fail(str(exc), pytrace=False)

        import denidin

        denidin.denidin_app = denidin.initialize_app({
            k: getattr(config, k) for k in (
                "green_api_instance_id", "green_api_token", "ai_api_key", "ai_model", "ai_vision_model",
                "ai_embedding_model", "ai_reply_max_tokens", "log_level", "data_root", "feature_flags",
                "godfather_phone", "memory", "constitution_config", "user_roles", "mcp")
        })
        return denidin.denidin_app

    @pytest.fixture(autouse=True)
    def _clean(self, denidin_app):
        def _wipe():
            for f in Path(denidin_app.ledger_event_manager.storage_dir).glob("*.json"):
                f.unlink()
            if hasattr(denidin_app.ledger_event_manager, "_index"):
                denidin_app.ledger_event_manager._index = []
            wipe_chat_messages_on_disk(denidin_app.session_manager.storage_dir, GODFATHER_CHAT_ID)
        _wipe()
        yield
        _wipe()

    # ------------------------------------------------------------------ driver
    def _send_image(self, http_server, filename, id_prefix):
        from denidin import handle_image_message

        notification = create_real_notification({
            "typeWebhook": "incomingMessageReceived", "timestamp": int(time.time()),
            "idMessage": f"{id_prefix}_IMG",
            "instanceData": {"idInstance": 7103000000, "wid": "972501234567@c.us", "typeInstance": "whatsapp"},
            "senderData": _SENDER_DATA,
            "messageData": {"typeMessage": "imageMessage", "fileMessageData": {
                "downloadUrl": f"{http_server}/{filename}", "fileName": filename, "mimeType": "image/jpeg",
                "caption": "", "jpegThumbnail": "", "isForwarded": False, "forwardingScore": 0}},
        })
        handle_image_message(notification)
        reply = get_response(notification)
        assert_response_exists(reply)
        _track_approval_buttons(GODFATHER_CHAT_ID, notification)
        return reply, notification

    def _slip_to_offer(self, denidin_app, http_server, id_prefix):
        manifest = seed_scenario(denidin_app, _ARTIFACT_MANIFEST)
        reply, notification = self._send_image(
            http_server, manifest["source_file"], id_prefix)
        return manifest, reply, notification

    @staticmethod
    def _assert_is_the_offer(reply, notification, manifest):
        send = get_button_send(notification)
        assert send is not None, f"the offer must be sent as yes/no buttons: {reply!r}"
        assert [b.get("buttonId") or b.get("id") for b in send["buttons"]] and len(send["buttons"]) == 2
        assert any(w in reply for w in _OFFER_WORDS), f"the question must be about a חשבונית מס / קבלה: {reply!r}"
        client = manifest["resolution"]["name"]
        assert client not in reply, f"the offer must not name the client: {reply!r}"
        assert not re.search(r"\d{3,}", reply), f"the offer must carry no amount or number: {reply!r}"



@pytest.mark.expensive
class TestDepositOffer064E2E(DepositImageE2EBase):
    @pytest.mark.sanity
    def test_64_1_yes_starts_the_320_flow(self, denidin_app, http_server):
        manifest, reply, notification = self._slip_to_offer(denidin_app, http_server, "F064_1")
        assert denidin_app.ledger_event_manager is not None
        events = list(Path(denidin_app.ledger_event_manager.storage_dir).glob("*.json"))
        assert events, "the deposit must be recorded before the offer"
        self._assert_is_the_offer(reply, notification, manifest)

        reply, ai_response = _send_button_tap(GODFATHER_CHAT_ID, BUTTON_ID_APPROVE, "F064_1_YES")
        assert not _calls_for(ai_response, "create_combo_document"), "a 320 was created on 'yes' to the offer"
        assert manifest["resolution"]["name"] in reply, f"320 approval must show the client: {reply!r}"
        assert "1500" in reply.replace(",", ""), f"320 approval must show the slip amount: {reply!r}"
        assert approval_buttons_on_screen(GODFATHER_CHAT_ID), "the 320 approval must be a real approval prompt"

    def test_64_2_no_creates_nothing(self, denidin_app, http_server):
        manifest, reply, notification = self._slip_to_offer(denidin_app, http_server, "F064_2")
        self._assert_is_the_offer(reply, notification, manifest)
        reply, ai_response = _send_button_tap(GODFATHER_CHAT_ID, BUTTON_ID_DECLINE, "F064_2_NO")
        assert reply and len(reply) < 200, f"expected a short acknowledgement: {reply!r}"
        assert not _calls_for(ai_response, "create_combo_document")
        assert list(Path(denidin_app.ledger_event_manager.storage_dir).glob("*.json")), "the deposit must stay in the ledger"

    def test_64_4_new_client_offer_comes_after_add_client(self, denidin_app, http_server):
        from tests.billed._ledger_069_post_turn_base import drive_capture

        manifest = seed_scenario(denidin_app, "deposit_zero_matches")
        reply, notification = self._send_image(
            http_server, manifest["source_file"], "F064_4")
        events, transcript, _ = drive_capture(
            denidin_app, "deposit_zero_matches", image_reply=reply, base_ts=int(time.time()),
            id_prefix="F064_4", max_turns=7)
        assert events, "the deposit was never recorded"
        last = transcript[-1]["reply"] or ""
        assert any(w in last for w in _OFFER_WORDS), (
            f"after the new client was added and the turn completed, the offer must appear: {last!r}"
        )
