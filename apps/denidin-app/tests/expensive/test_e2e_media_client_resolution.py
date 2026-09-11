"""Feature 069 — Phase 11 acceptance tier (photographed / imaged sources), EXPENSIVE.

Real **vision** OpenAI calls (the image pipeline) + real Morning sandbox. NO MOCKING.

What these prove that the billed text tests cannot: a `בנק` deposit slip or a
photographed `הסכם` fee agreement, arriving as a real `imageMessage`, is
**routed through the conversational pipeline as a synthetic turn** (never
persisted directly off the OCR anymore — FR-069-045), so the mandatory
client-resolution detour runs, and the post-turn recognition call then records
the event against an EXACT Morning client name.

Two-hop fidelity is automatic — every manifest here is `source_kind: image`, so
`assert_ledger_event_matches_manifest` runs Hop 1 (the vision extractor already
carried every manifest field) before Hop 2 (the persisted event matches).

Every test is seed / send-image / drive / assert — the client-resolution answers
live in the driver, keyed by each manifest's `resolution.mode`.

🚨 EXPENSIVE — each test needs its own fresh explicit human approval, every run,
one at a time. STOP at every failure for a full report. Read `logs/test_logs/`
(and this run's `pytest_results/` file) before re-running.

    scripts/run_single_test.sh \\
      "tests/expensive/test_e2e_media_client_resolution.py::TestMediaClientResolutionE2E::<name>"
"""
from __future__ import annotations

import logging
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

import pytest

from src.models.config import AppConfiguration
from tests.billed.denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    NoMorningTunnelError,
    require_live_morning_tunnel,
)
from tests.billed._ledger_069_acceptance import assert_ledger_event_matches_manifest
from tests.billed._ledger_069_post_turn_base import drive_capture, seed_scenario
from tests.e2e_helpers import (
    create_real_notification,
    get_response,
    assert_response_exists,
    wipe_chat_messages_on_disk,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

_MEDIA_DIR = Path(__file__).parent.parent / "fixtures" / "media" / "ledger_events"
_SENDER_DATA = {
    "chatId": GODFATHER_CHAT_ID,
    "sender": GODFATHER_CHAT_ID,
    "senderName": "E2E Godfather",
}


@pytest.mark.expensive
class TestMediaClientResolutionE2E:

    # ------------------------------------------------------------------ infra
    @pytest.fixture(scope="class")
    def http_server(self):
        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *a, **kw):
                super().__init__(*a, directory=str(_MEDIA_DIR), **kw)

            def translate_path(self, path):
                return super().translate_path(unquote(path))

            def log_message(self, *a):
                pass

        server = HTTPServer(("127.0.0.1", 8767), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logger.info("media HTTP server on http://127.0.0.1:8767 serving %s", _MEDIA_DIR)
        yield "http://127.0.0.1:8767"
        server.shutdown()

    @pytest.fixture(scope="class")
    def config(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
        if not config_path.exists():
            pytest.skip("config.test.json not found")
        from tests.e2e_helpers import sanity_worker_data_root

        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        test_data_root = sanity_worker_data_root()  # per-xdist-worker isolation (Feature 075)
        config.data_root = str(test_data_root)
        config.memory["session"]["storage_dir"] = str(test_data_root / "sessions")
        config.memory["longterm"]["storage_dir"] = str(test_data_root / "memory")
        config.godfather_phone = GODFATHER_CHAT_ID
        return config

    @pytest.fixture(scope="class")
    def denidin_app(self, config):
        # Feature 069 media resolution goes through the live Morning tunnel — fail
        # loudly (not skip) if it isn't up, same contract as tests/billed/conftest.py.
        status_file_path = Path(config.mcp["morning_status_file"])
        max_age = config.mcp.get("url_max_age_seconds", 0) or 0
        try:
            require_live_morning_tunnel(status_file_path, max_age)
        except NoMorningTunnelError as exc:
            pytest.fail(str(exc), pytrace=False)

        import denidin

        config_dict = {
            "green_api_instance_id": config.green_api_instance_id,
            "green_api_token": config.green_api_token,
            "ai_api_key": config.ai_api_key,
            "ai_model": config.ai_model,
            "ai_vision_model": config.ai_vision_model,
            "ai_embedding_model": config.ai_embedding_model,
            "ai_reply_max_tokens": config.ai_reply_max_tokens,
            "log_level": config.log_level,
            "data_root": config.data_root,
            "feature_flags": config.feature_flags,
            "godfather_phone": config.godfather_phone,
            "memory": config.memory,
            "constitution_config": config.constitution_config,
            "user_roles": config.user_roles,
            "mcp": config.mcp,
        }
        denidin.denidin_app = denidin.initialize_app(config_dict)

        events_dir = Path(denidin.denidin_app.ai_handler.ledger_event_manager.storage_dir).resolve()
        assert events_dir.is_relative_to(Path(config.data_root).resolve()), (
            f"LedgerEventManager.storage_dir={events_dir} not under test data_root — refusing"
        )
        return denidin.denidin_app

    @pytest.fixture(autouse=True)
    def _clean_ledger(self, denidin_app):
        events_dir = Path(denidin_app.ai_handler.ledger_event_manager.storage_dir)

        def _wipe():
            if events_dir.exists():
                for f in events_dir.glob("*.json"):
                    f.unlink()
            mgr = denidin_app.ai_handler.ledger_event_manager
            if hasattr(mgr, "_index"):
                mgr._index = []  # keep the in-memory index consistent with disk
            wipe_chat_messages_on_disk(
                denidin_app.ai_handler.session_manager.storage_dir, GODFATHER_CHAT_ID)

        _wipe()
        yield
        _wipe()

    # ------------------------------------------------------------------ driver
    def _send_image(self, http_server, filename, caption, id_prefix):
        """Returns `(reply, trigger_epoch)` — `trigger_epoch` is the image
        message's Green API timestamp, which every persisted event's
        `event_datetime` must equal (the 'hard pointer', even after the detour)."""
        from denidin import handle_image_message

        trigger_epoch = int(time.time())
        notification = create_real_notification({
            "typeWebhook": "incomingMessageReceived",
            "timestamp": trigger_epoch,
            "idMessage": f"{id_prefix}_IMG",
            "instanceData": {"idInstance": 7103000000, "wid": "972501234567@c.us",
                             "typeInstance": "whatsapp"},
            "senderData": _SENDER_DATA,
            "messageData": {
                "typeMessage": "imageMessage",
                "fileMessageData": {
                    "downloadUrl": f"{http_server}/{filename}",
                    "fileName": filename,
                    "mimeType": "image/jpeg",
                    "caption": caption,
                    "jpegThumbnail": "",
                    "isForwarded": False,
                    "forwardingScore": 0,
                },
            },
        })
        handle_image_message(notification)
        reply = get_response(notification)
        assert_response_exists(reply)
        return reply, trigger_epoch

    def _run(self, denidin_app, http_server, manifest_name, caption, id_prefix, *, max_turns=7):
        manifest = seed_scenario(denidin_app, manifest_name)
        first, trigger_epoch = self._send_image(
            http_server, manifest["source_file"], caption, id_prefix)
        events, transcript, event_epoch = drive_capture(
            denidin_app, manifest_name, image_reply=first, base_ts=trigger_epoch,
            id_prefix=id_prefix, max_turns=max_turns)
        return manifest, events, transcript, event_epoch

    # ==================================================================== US7
    @pytest.mark.sanity
    def test_us7a_deposit_image_zero_matches_new_client(self, denidin_app, http_server):
        """US7a — deposit slip whose payer has ZERO Morning matches. The detour
        collects full name + email + phone, `add_client` runs, and the deposit is
        recorded against the new exact Morning name."""
        _, events, _, epoch = self._run(
            denidin_app, http_server, "deposit_zero_matches",
            "הפקדה שנכנסה היום, תרשום ביומן", "F069_US7A")
        assert events, "US7a: deposit never recorded"
        assert_ledger_event_matches_manifest(denidin_app, events, "deposit_zero_matches", epoch)

    def test_us7b_deposit_image_one_partial_match(self, denidin_app, http_server):
        """US7b — the deposit slip's payer (`גרינפלד אורלי`) has ONE partial
        (non-exact) Morning match. The routed turn asks to confirm; the operator
        confirms → the deposit is recorded against that exact Morning name."""
        _, events, _, epoch = self._run(
            denidin_app, http_server, "deposit_one_partial",
            "הפקדה שנכנסה, תרשום ביומן", "F069_US7B")
        assert events, "US7b: deposit never recorded"
        assert_ledger_event_matches_manifest(denidin_app, events, "deposit_one_partial", epoch)

    def test_us7c_deposit_image_two_plus_matches(self, denidin_app, http_server):
        """US7c — the payer (`גרינפלד אורלי`) has 2+ partial matches; operator
        picks one → capture against that exact Morning name."""
        _, events, _, epoch = self._run(
            denidin_app, http_server, "deposit_two_plus",
            "הפקדה, תרשום ביומן", "F069_US7C")
        assert events, "US7c: deposit never recorded"
        assert_ledger_event_matches_manifest(denidin_app, events, "deposit_two_plus", epoch)

    @pytest.mark.sanity
    def test_us7d_deposit_image_exact_match_no_question(self, denidin_app, http_server):
        """US7d — the deposit slip's payer is an EXACT existing Morning client.
        NO disambiguation question, NO `add_client` (the no-detour assertion lives
        in `drive_capture`) — the deposit is recorded directly against the
        existing client, on the routed turn."""
        _, events, _, epoch = self._run(
            denidin_app, http_server, "deposit_exact_match",
            "הפקדה שנכנסה, תרשום ביומן", "F069_US7D", max_turns=3)
        assert events, "US7d: exact-match deposit not recorded"
        assert_ledger_event_matches_manifest(denidin_app, events, "deposit_exact_match", epoch)

    # ==================================================================== US9
    @pytest.mark.sanity
    def test_us9_photographed_multi_component_agreement(self, denidin_app, http_server):
        """US9 — a photographed multi-tier fee agreement (`agreement_idan_shabtai.jpg`).
        Client not in Morning → detour → `add_client` → every fee tier recorded
        against the new exact Morning name. Two-hop fidelity."""
        _, events, _, epoch = self._run(
            denidin_app, http_server, "agreement_photo_multi",
            "ההסכם החתום, תרשום ביומן", "F069_US9")
        assert events, "US9: photographed agreement never recorded"
        for e in events:
            assert e["source_type"] == "הסכם"
        assert_ledger_event_matches_manifest(denidin_app, events, "agreement_photo_multi", epoch)
