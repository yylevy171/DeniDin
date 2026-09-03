"""Feature 069 — Phase 11 acceptance tier (photographed / imaged sources), EXPENSIVE.

Real **vision** OpenAI calls (the image pipeline) + real Morning sandbox. NO MOCKING.

What these prove that the billed text tests cannot: a `בנק` deposit slip or a
photographed `הסכם` fee agreement, arriving as a real `imageMessage`, is
**routed through the conversational pipeline as a synthetic turn** (never
persisted directly off the OCR anymore — FR-069-045), so the mandatory
client-resolution detour runs, and the post-turn recognition call then records
the event against an EXACT Morning client name.

Two-hop fidelity (`_ledger_069_acceptance.assert_event_matches_manifest_two_hop`):
  Hop 1 — the vision extractor already carried every manifest field (no OCR loss)
  Hop 2 — the persisted event matches the manifest (no loss in the detour)

🚨 EXPENSIVE — each test needs its own fresh explicit human approval, every run,
one at a time. STOP at every failure for a full report. Read `logs/test_logs/`
(and this run's `pytest_results/` file) before re-running.

    scripts/run_single_test.sh \\
      "tests/expensive/test_e2e_media_client_resolution.py::TestMediaClientResolutionE2E::<name>"

Morning sandbox roster
----------------------
* US7d: `עטיה רועי מאיר` — seeded idempotently in-test
  (`_seed_client(ensure_exists=True)`); also on `pull_sandbox_clients.py`'s
  denylist (expensive bank-deposit payer).
* US7a / US9: the payer/client (`קהילת צעיר` / `עידן שבתאי`) is NOT in the sandbox —
  the run creates it via the detour.
* US7b / US7c: both drive off `bank_transfer_grinfeld.jpg` (payer `גרינפלד אורלי`,
  ₪800, 23/08/2026). The tests seed non-exact partial-match clients
  (`_seed_client(ensure_exists=True)`) per each manifest's `seed_clients`; they
  assert only the final resolved `client_name`, not the candidate count (they
  share one image, so a prior run of the other leaves its partials behind).
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
    _seed_client,
    require_live_morning_tunnel,
)
from tests.billed._ledger_069_acceptance import (
    assert_event_matches_manifest_two_hop,
    ledger_events_for_chat,
    load_manifest,
    resolution_answer_bank,
)
from tests.e2e_helpers import (
    ClarificationAnswerBank,
    create_real_notification,
    get_response,
    assert_response_exists,
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
        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        test_data_root = Path(__file__).parent.parent.parent / "test_data"
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
            if hasattr(mgr, "_events_index"):
                mgr._events_index.clear()  # keep in-memory index consistent with disk

        _wipe()
        yield
        _wipe()

    # ------------------------------------------------------------------ driver
    def _send_image(self, http_server, filename, caption, id_prefix):
        from denidin import handle_image_message

        notification = create_real_notification({
            "typeWebhook": "incomingMessageReceived",
            "timestamp": int(time.time()),
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
        return reply

    def _run_detour_until_captured(  # pylint: disable=too-many-locals
        self, denidin_app, first_reply, answer_bank, id_prefix, max_turns=6
    ):
        from denidin import handle_text_message

        events = ledger_events_for_chat(denidin_app, GODFATHER_CHAT_ID)
        text = first_reply
        ts = int(time.time())
        transcript = [{"turn": 0, "sent": "<image>", "reply": first_reply}]
        turn = 0
        while not events and turn < max_turns:
            turn += 1
            nxt, matched = answer_bank.compose_answer(text or "")
            notification = create_real_notification({
                "typeWebhook": "incomingMessageReceived",
                "timestamp": ts + turn * 30,
                "idMessage": f"{id_prefix}_F{turn}",
                "instanceData": {"idInstance": 7103000000, "wid": "972501234567@c.us",
                                 "typeInstance": "whatsapp"},
                "senderData": _SENDER_DATA,
                "messageData": {"typeMessage": "textMessage",
                                "textMessageData": {"textMessage": nxt}},
            })
            handle_text_message(notification)
            text = get_response(notification)
            transcript.append({"turn": turn, "sent": nxt, "reply": text, "matched": matched})
            events = ledger_events_for_chat(denidin_app, GODFATHER_CHAT_ID)
        for e in transcript:
            logger.info("TURN %s | sent=%r | reply=%r", e["turn"], e["sent"], e["reply"])
        return events, transcript

    def _extractor_output_for_chat(self, denidin_app):
        """Best-effort Hop-1 payload: the synthetic media turn's stashed user
        message text (verbatim OCR + structured fields) from session history."""
        sm = denidin_app.ai_handler.session_manager
        session = sm.get_session(GODFATHER_CHAT_ID)
        for mid in session.message_ids:
            msg = sm.load_message(session, mid)
            content = getattr(msg, "content", None) or ""
            if msg is not None and getattr(msg, "role", None) == "user" and "חולץ" in content:
                return {"extracted_text": content, "ledger_events": [], "document_analysis": {}}
        return {"extracted_text": "", "ledger_events": [], "document_analysis": {}}

    # ==================================================================== US7
    def test_us7a_deposit_image_zero_matches_new_client(self, denidin_app, http_server):
        """US7a — deposit slip whose payer has ZERO Morning matches. The detour
        collects full name + email + phone, `add_client` runs, and the deposit is
        recorded against the new exact Morning name."""
        manifest = load_manifest("deposit_zero_matches")
        res = manifest["client_resolution"]
        first = self._send_image(http_server, manifest["source_file"],
                                 "הפקדה שנכנסה היום, תרשום ביומן", "F069_US7A")
        bank = resolution_answer_bank(
            full_name=res["operator_stated_name"],
            email=res["new_client_email"],
            phone=res["new_client_phone"],
        )
        events, _ = self._run_detour_until_captured(denidin_app, first, bank, "F069_US7A")
        assert events, "US7a: deposit never recorded"
        assert_event_matches_manifest_two_hop(
            self._extractor_output_for_chat(denidin_app), events, manifest
        )

    def _seed_from_manifest(self, manifest):
        for seed in manifest.get("seed_clients", []):
            _seed_client(GODFATHER_CHAT_ID, seed["id_prefix"], name=seed["name"],
                         ensure_exists=bool(seed.get("ensure_exists")))
            time.sleep(2)

    def test_us7b_deposit_image_one_partial_match(self, denidin_app, http_server):
        """US7b — the deposit slip's payer (`גרינפלד אורלי`) has ONE partial
        (non-exact) Morning match. The routed turn asks to confirm; the operator
        confirms → the deposit is recorded against that exact Morning name.

        (Shared image with US7c — the candidate *count* is not asserted, since a
        prior US7c run leaves its own partials in the sandbox; the assertion is
        on the final resolved `client_name` via a name-specific answer bank.)
        """
        manifest = load_manifest("deposit_one_partial")
        res = manifest["client_resolution"]
        self._seed_from_manifest(manifest)
        first = self._send_image(http_server, manifest["source_file"],
                                 "הפקדה שנכנסה, תרשום ביומן", "F069_US7B")
        bank = ClarificationAnswerBank(
            [{"topic": "confirm_or_pick",
              "keywords": ["מצאתי", "האם הכוונה", "התכוונת", "נכון", "איזה", "כמה"],
              "answer": f"כן, הכוונה ל{res['morning_name_after_resolution']}"}],
            fallback=f"כן, הכוונה ל{res['morning_name_after_resolution']}",
        )
        events, _ = self._run_detour_until_captured(denidin_app, first, bank, "F069_US7B")
        assert events, "US7b: deposit never recorded"
        assert_event_matches_manifest_two_hop(
            self._extractor_output_for_chat(denidin_app), events, manifest
        )

    def test_us7c_deposit_image_two_plus_matches(self, denidin_app, http_server):
        """US7c — the payer (`גרינפלד אורלי`) has 2+ partial matches; operator
        picks one → capture against that exact Morning name."""
        manifest = load_manifest("deposit_two_plus")
        res = manifest["client_resolution"]
        self._seed_from_manifest(manifest)
        first = self._send_image(http_server, manifest["source_file"],
                                 "הפקדה, תרשום ביומן", "F069_US7C")
        bank = ClarificationAnswerBank(
            [{"topic": "pick_one", "keywords": ["איזה", "מצאתי", "יותר מ", "האם הכוונה", "כמה"],
              "answer": f"הכוונה ל{res['operator_picks']}"}],
            fallback=f"הכוונה ל{res['operator_picks']}",
        )
        events, _ = self._run_detour_until_captured(denidin_app, first, bank, "F069_US7C")
        assert events, "US7c: deposit never recorded"
        assert_event_matches_manifest_two_hop(
            self._extractor_output_for_chat(denidin_app), events, manifest
        )

    def test_us7d_deposit_image_exact_match_no_question(self, denidin_app, http_server):
        """US7d — the deposit slip's payer is an EXACT existing Morning client.
        NO disambiguation question, NO `add_client` — the deposit is recorded
        directly against the existing client, on the routed turn."""
        manifest = load_manifest("deposit_exact_match")
        res = manifest["client_resolution"]
        _seed_client(GODFATHER_CHAT_ID, "F069_US7D",
                     name=res["morning_name_after_resolution"], ensure_exists=True)
        time.sleep(2)
        first = self._send_image(http_server, manifest["source_file"],
                                 "הפקדה שנכנסה, תרשום ביומן", "F069_US7D")
        events, transcript = self._run_detour_until_captured(
            denidin_app, first,
            ClarificationAnswerBank([], fallback="כן תרשום"),
            "F069_US7D", max_turns=3,
        )
        assert events, "US7d: exact-match deposit not recorded"
        assert len(transcript) <= 2, (
            f"US7d: an exact Morning match must not trigger a resolution detour, "
            f"took {len(transcript)-1} follow-up turn(s)"
        )
        assert_event_matches_manifest_two_hop(
            self._extractor_output_for_chat(denidin_app), events, manifest
        )

    # ==================================================================== US9
    def test_us9_photographed_multi_component_agreement(self, denidin_app, http_server):
        """US9 — a photographed multi-tier fee agreement (`agreement_idan_shabtai.jpg`).
        Client not in Morning → detour → `add_client` → every fee tier recorded
        against the new exact Morning name. Two-hop fidelity."""
        manifest = load_manifest("agreement_photo_multi")
        res = manifest["client_resolution"]
        first = self._send_image(http_server, manifest["source_file"],
                                 "ההסכם החתום, תרשום ביומן", "F069_US9")
        bank = resolution_answer_bank(
            full_name=res["operator_stated_name"],
            email=res["new_client_email"],
            phone=res["new_client_phone"],
        )
        events, _ = self._run_detour_until_captured(denidin_app, first, bank, "F069_US9",
                                                    max_turns=7)
        assert events, "US9: photographed agreement never recorded"
        for e in events:
            assert e["source_type"] == "הסכם"
        assert_event_matches_manifest_two_hop(
            self._extractor_output_for_chat(denidin_app), events, manifest
        )
