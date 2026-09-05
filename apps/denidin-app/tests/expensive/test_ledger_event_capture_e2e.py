"""
End-to-End Integration Test: Ledger Event Recognition - image flow (Feature 069).

Feature 069 (mandatory client resolution before a ledger event): a recognised
fee-agreement / bank-deposit IMAGE no longer persists a LedgerEvent straight off
the OCR. `MediaHandler` builds a structured "ledger stash"; `denidin.py`
(`_process_media_message`) routes it as a SYNTHETIC conversational turn, so
`resolve_client_name` / `add_client` / the approval gate all run; only then does
the post-turn recognition call
(`AIHandler.recognize_ledger_event` -> `LedgerEventManager.persist_recognized_event`)
write the event, with its client resolved to an EXACT Morning name.

Consequences for this file (T052, acceptance-regression-map.md Tier 1):
- Every test runs as the godfather - the Morning client-resolution tools are
  RBAC-gated - and depends on a live Morning tunnel (the `denidin_app` fixture
  fails loudly, never skips, when it is down).
- Every test seeds an exact-match Morning client first, then follows the routed
  turn (+ any resolution detour) with a `ClarificationAnswerBank` until the
  event lands.
- `event_datetime` is NOT asserted against the webhook timestamp anymore - 069
  dates `הסכם`/`בנק` from the COMPLETING (detour) message, and the Phase 11
  acceptance helpers list `event_datetime` in `PROVENANCE_IGNORE` for exactly
  this reason.

Deleted 2026-09-06 (superseded by Feature 069's own Phase 11 acceptance suite,
`tests/expensive/test_e2e_media_client_resolution.py`, which drives the same
images through the full resolution detour with bidirectional-manifest fidelity):
- `test_given_real_agreement_image_when_processed_then_ledger_event_captured_via_image_path`
  -> US9 (`test_us9_photographed_multi_component_agreement`, manifest
  `agreement_photo_multi`: same `agreement_idan_shabtai.jpg`, same 3 tier
  amounts 23,600 / 70,800 / 9,440).
- `test_given_real_bank_deposit_screenshot_when_processed_then_captured_as_bank_deposit`
  -> US7a (`test_us7a_deposit_image_zero_matches_new_client`, manifest
  `deposit_zero_matches`: same `bank_deposit_kehilat_tzair.jpg`, same 9,440;
  `vat_status: "כולל"` folded into that manifest to keep this file's forced-
  field coverage).

Images are real source material from the AHLedger reconciliation project
(tests/fixtures/media/ledger_events/), each with independently verified
ground-truth content:
- Agreement-test-image.jpg (F3) = a real fee-proposal letter (שחר פישר / עו"ד
  אילה הוניגמן, 27.1.253) with FOUR distinct fee components (10,000 /
  hourly-800-capped-10h / 15,000 / 5,000 ₪, all לא כולל מע"מ) - ground truth
  read directly from the image by the implementing agent (2026-07-29).
- Deposit_Eti.jpeg (F4) = a real bank-transfer confirmation (05/08/2026,
  ₪554.00, אסולין אסתר, "שליחות וצילום הערעור לעיריה"), bank 31 / branch 112 /
  account 105397180.
- Agreement-mor.jpg (F5) = a real fee-proposal letter dated 3.12.24 (מור בן
  שעיה / עו"ד אילה הוניגמן), photographed at an angle - the glare band sits on
  the client surname, so the extracted client line comes back partial
  (`מר מור בן [לא קריא]`). This is exactly the case Feature 069's mandatory
  client-resolution detour exists to handle: a seeded exact-match client + a
  confirming operator turn.
- not_an_agreement_personal_note.jpg = a personal handwritten scratch note,
  confirmed NOT a fee agreement during that project's own audit.

Text-flow counterpart lives in tests/billed/test_ledger_event_capture_billed.py
and tests/billed/test_ledger_event_capture_text_billed.py.

NO MOCKING - real OpenAI, real vision pipeline, real Morning sandbox, real
session storage.

Run ONE test at a time, with fresh explicit approval each time:
    scripts/run_single_test.sh \\
      "tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::<name>"
"""

import json
import logging
import threading
import time
import uuid
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote

import pytest

from src.models.config import AppConfiguration
from tests.billed.denidin_mcp_e2e_helpers import (
    NoMorningTunnelError,
    require_live_morning_tunnel,
)
from tests.e2e_helpers import (
    ClarificationAnswerBank,
    create_real_notification,
    get_response,
    assert_response_exists,
    assert_image_path_persisted,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

_SENDER_NAME = "E2E Godfather"


@pytest.mark.expensive
class TestLedgerEventCaptureE2E:
    """
    Given/When/Then E2E coverage for Ledger Event Recognition's image flow under
    Feature 069:
    - Given an image that genuinely warrants capture AND a resolvable client,
      When processed, Then it routes as a synthetic turn, the client resolves to
      an exact Morning name, and the post-turn recognition call persists the
      event(s) in `data/events/`.
    - Given an image that does NOT warrant capture, When processed, Then no
      synthetic ledger routing fires and nothing is persisted - the
      false-positive guard matters as much as the capture itself.
    """

    # ------------------------------------------------------------------ infra
    @pytest.fixture(scope="class")
    def http_server(self):
        """Local HTTP server serving tests/fixtures/media/ledger_events/,
        simulating Green API's file download URLs."""
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "media" / "ledger_events"

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(fixtures_dir), **kwargs)

            def translate_path(self, path):
                return super().translate_path(unquote(path))

            def log_message(self, format, *args):  # pylint: disable=redefined-builtin
                pass

        server = HTTPServer(('127.0.0.1', 8766), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Test HTTP server running at http://127.0.0.1:8766/ serving {fixtures_dir}")
        yield "http://127.0.0.1:8766"
        server.shutdown()

    @pytest.fixture
    def config(self):
        """Load test configuration (real credentials, isolated test_data/ root)."""
        config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
        if not config_path.exists():
            pytest.skip("config.test.json not found")

        from tests.e2e_helpers import sanity_worker_data_root

        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        test_data_root = sanity_worker_data_root()  # per-xdist-worker under the parallel sanity sweep (Feature 075)
        config.data_root = str(test_data_root)
        config.memory['session']['storage_dir'] = str(test_data_root / "sessions")
        config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")
        return config

    @pytest.fixture
    def denidin_app(self, config):
        """Initialize the full denidin app - NO MOCKING.

        Feature 069: the image path now runs the mandatory client-resolution
        detour through the live Morning tunnel, so this fixture fails LOUDLY
        (never skips) when the tunnel is down - same contract as
        tests/billed/conftest.py's `live_morning_tunnel`.
        """
        status_file_path = Path(config.mcp["morning_status_file"])
        max_age = config.mcp.get("url_max_age_seconds", 0) or 0
        try:
            require_live_morning_tunnel(status_file_path, max_age)
        except NoMorningTunnelError as exc:
            pytest.fail(str(exc), pytrace=False)

        import denidin

        if denidin.denidin_app is None:
            config_dict = {
                'green_api_instance_id': config.green_api_instance_id,
                'green_api_token': config.green_api_token,
                'ai_api_key': config.ai_api_key,
                'ai_model': config.ai_model,
                # Must be passed through explicitly - otherwise initialize_app falls
                # back to AppConfiguration's gpt-4o-mini default and the image path
                # silently exercises a different (weaker) vision model than production.
                'ai_vision_model': config.ai_vision_model,
                'ai_embedding_model': config.ai_embedding_model,
                'ai_reply_max_tokens': config.ai_reply_max_tokens,
                'log_level': config.log_level,
                'data_root': config.data_root,
                'feature_flags': config.feature_flags,
                'godfather_phone': config.godfather_phone,
                'memory': config.memory,
                'constitution_config': config.constitution_config,
                'user_roles': config.user_roles,
                'mcp': config.mcp,
            }
            denidin.denidin_app = denidin.initialize_app(config_dict)

        # Safety guard, every call: LedgerEventManager.storage_dir MUST resolve
        # under this test's isolated data_root (test_data/), never the real
        # production/dev data root - a wiring mistake here would write test noise
        # into the real financial ledger. Fails loud and immediately.
        actual_events_dir = Path(denidin.denidin_app.ai_handler.ledger_event_manager.storage_dir).resolve()
        expected_root = Path(config.data_root).resolve()
        assert actual_events_dir.is_relative_to(expected_root), (
            f"LedgerEventManager.storage_dir={actual_events_dir} is NOT under this "
            f"test's isolated data_root={expected_root} - refusing to proceed"
        )
        return denidin.denidin_app

    @pytest.fixture(autouse=True)
    def _clean_ledger(self, denidin_app):
        """Wipe persisted ledger-event state before AND after every test in this
        class - `tests/expensive/` has no directory-wide autouse of its own, and
        Feature 069 dates events from a wall-clock detour turn (not the fixed
        webhook epoch the old `_clean_fixed_timestamp_events` keyed off), so a
        blanket wipe of this isolated test_data/ events dir is the only reliable
        cleanup. Mirrors `test_e2e_media_client_resolution.py::_clean_ledger`."""
        events_dir = Path(denidin_app.ai_handler.ledger_event_manager.storage_dir)

        def _wipe():
            if events_dir.exists():
                for f in events_dir.glob("*.json"):
                    f.unlink()
            mgr = denidin_app.ai_handler.ledger_event_manager
            if hasattr(mgr, "_index"):
                mgr._index = []  # keep the in-memory index consistent with disk

        _wipe()
        yield
        _wipe()

    # ------------------------------------------------------------------ ids / cleanup
    @staticmethod
    def _fresh_chat_id(label: str) -> str:
        """A unique-per-run chat_id for the no-capture guard (no client
        resolution needed there, so it needn't be the godfather)."""
        return f"97250{uuid.uuid4().hex[:7]}_{label}@c.us"

    @staticmethod
    def _godfather_chat_id(config) -> str:
        """Feature 069: every capture test needs a chat whose role gets the
        Morning client-resolution tools attached (RBAC-gated to godfather/admin)."""
        phone = str(config.godfather_phone).lstrip("+")
        return phone if phone.endswith("@c.us") else f"{phone}@c.us"

    @staticmethod
    def _clear_chat_test_data(denidin_app, chat_id):
        """Clear this chat's session + its persisted events before AND after, so
        the fixed godfather chat_id can't collide with a previous run. Only ever
        touches test_data/ - the `denidin_app` fixture already refuses to run if
        LedgerEventManager.storage_dir is not under this test's data_root."""
        session_id = denidin_app.ai_handler.session_manager.get_session(chat_id).session_id
        events_dir = denidin_app.ai_handler.ledger_event_manager.storage_dir
        for f in list(events_dir.glob("*.json")):
            try:
                with open(f, encoding='utf-8') as fh:
                    data = json.load(fh)
            except (OSError, json.JSONDecodeError):
                continue
            if data.get("session_id") == session_id:
                f.unlink()

        session_manager = denidin_app.ai_handler.session_manager
        if session_manager is not None:
            try:
                session_manager.clear_session(chat_id)
            except AttributeError:
                logger.warning("SessionManager has no clear_session - session data not cleared")

    # ------------------------------------------------------------------ event readers
    @staticmethod
    def _events_for_chat(denidin_app, chat_id):
        """All persisted LedgerEvent files for this chat_id's current session,
        sorted by captured_at - reads the real files off disk."""
        session_id = denidin_app.ai_handler.session_manager.get_session(chat_id).session_id
        events_dir = denidin_app.ai_handler.ledger_event_manager.storage_dir
        results = []
        for f in events_dir.glob("*.json"):
            with open(f, encoding='utf-8') as fh:
                data = json.load(fh)
            if data.get("session_id") == session_id:
                results.append(data)
        results.sort(key=lambda d: d["captured_at"])
        return results

    @staticmethod
    def _assert_ledger_events_persisted(denidin_app, chat_id, expected_count):
        """Assert events were persisted for this chat, each carrying the
        bookkeeping fields `persist_recognized_event` adds.

        Feature 069: `event_datetime` is NOT asserted here - 069 dates
        `הסכם`/`בנק` from the COMPLETING (detour) message, not the webhook, and
        the Phase 11 acceptance helpers list `event_datetime` in
        PROVENANCE_IGNORE for the same reason. Presence of `captured_at` /
        `message_id` is still checked.

        expected_count: exact count required, or None to only assert >= 1.
        """
        events = TestLedgerEventCaptureE2E._events_for_chat(denidin_app, chat_id)
        if expected_count is None:
            assert len(events) >= 1, f"Expected at least 1 persisted ledger event for {chat_id}, found 0"
        else:
            assert len(events) == expected_count, (
                f"Expected {expected_count} persisted ledger event(s) for {chat_id}, "
                f"found {len(events)}: {events}"
            )

        for record in events:
            assert record.get("captured_at"), "captured_at was not persisted"
            assert record.get("message_id"), (
                "message_id must be non-null (Feature 033 traceability) - the "
                "completing message the recognition call fired on"
            )
            assert "raw_message_excerpt" not in record, (
                "raw_message_excerpt was removed from the persisted schema (2026-08-18)"
            )
        return events

    @staticmethod
    def _assert_message_links_back_to_event(denidin_app, chat_id, event):
        """The completing message's `ledger_event_ids` (Feature 033) must
        include this event's event_id."""
        session_manager = denidin_app.ai_handler.session_manager
        session_id = session_manager.chat_to_session[chat_id]
        message_id = event["message_id"]
        message_file = session_manager.storage_dir / session_id / "messages" / f"{message_id}.json"
        with open(message_file, encoding='utf-8') as f:
            message_data = json.load(f)
        assert event["event_id"] in message_data["ledger_event_ids"], (
            f"event {event['event_id']} not found in completing message {message_id}'s "
            f"ledger_event_ids={message_data.get('ledger_event_ids')!r}"
        )

    @staticmethod
    def _assert_no_open_invoice_for(chat_id, name, id_prefix):
        """Guard against cross-test interference: the deposit test's expected
        outcome DIFFERS depending on whether an open invoice for the payer
        already exists - 320 when none does, 400 when one does. A leftover open
        invoice from a half-finished run would silently invert the result.

        2026-09-06: reads the parsed `list_invoices` JSON (2026-09-04 JSON-only
        contract) - `status_code == 0` / `status == "unpaid"` means open - not a
        `"פתוח"` substring scan of prose that no longer exists.
        """
        from tests.billed.denidin_mcp_e2e_helpers import _calls_for, _send_turn

        _, ai_response = _send_turn(
            chat_id, f"אילו חשבוניות פתוחות יש ל{name}?", id_prefix=f"{id_prefix}_PRECHECK"
        )
        listings = _calls_for(ai_response, "list_invoices")
        output = (listings[0]["output"] or "") if listings else ""
        open_docs = []
        if output:
            try:
                payload = json.loads(output)
            except json.JSONDecodeError:
                payload = {}
            if isinstance(payload, dict):
                docs = payload.get("documents") or []
            elif isinstance(payload, list):
                docs = payload
            else:
                docs = []
            open_docs = [
                d for d in docs
                if d.get("status_code") == 0 or d.get("status") in ("unpaid", "open")
            ]
        assert not open_docs, (
            f"precondition failed: {name!r} already has an open invoice in the sandbox, "
            f"so this deposit would correctly CLOSE it (a 400) instead of producing a new "
            f"320. Close it in Morning, then re-run. Open docs: {open_docs!r}"
        )

    # ------------------------------------------------------------------ drivers
    @staticmethod
    def _send_image(http_server, filename, *, caption, chat_id, id_prefix):
        """Send one real WhatsApp image through the real router handler and
        return the SYNTHETIC-turn reply (Feature 069 routes the recognised
        stash straight into the conversational pipeline)."""
        from denidin import handle_image_message

        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': int(time.time()),
            'idMessage': f'{id_prefix}_IMG',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': _SENDER_NAME},
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {
                    'downloadUrl': f'{http_server}/{filename}',
                    'fileName': filename,
                    'mimeType': 'image/jpeg',
                    'caption': caption,
                    'jpegThumbnail': '',
                    'isForwarded': False,
                    'forwardingScore': 0,
                }
            }
        })
        handle_image_message(notification)
        reply = get_response(notification)
        assert_response_exists(reply)
        return reply

    def _drive_detour_until_captured(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
        self, denidin_app, chat_id, first_reply, answer_bank, id_prefix, max_turns=6
    ):
        """After the image's synthetic turn, follow the resolution detour with
        `answer_bank`-composed text turns until a LedgerEvent lands (or fail
        after `max_turns`). Stops the instant capture happens - an unconditional
        follow-up after a turn that already captured is what caused a real
        observed double-capture in this mechanism's first version."""
        from denidin import handle_text_message

        events = self._events_for_chat(denidin_app, chat_id)
        text = first_reply
        ts = int(time.time())
        transcript = [{"turn": 0, "sent": "<image>", "reply": first_reply}]
        turn = 0
        while not events and turn < max_turns:
            turn += 1
            nxt, matched = answer_bank.compose_answer(text or "")
            notification = create_real_notification({
                'typeWebhook': 'incomingMessageReceived',
                'timestamp': ts + turn * 30,
                'idMessage': f'{id_prefix}_F{turn}',
                'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
                'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': _SENDER_NAME},
                'messageData': {'typeMessage': 'textMessage', 'textMessageData': {'textMessage': nxt}},
            })
            handle_text_message(notification)
            text = get_response(notification)
            transcript.append({"turn": turn, "sent": nxt, "reply": text, "matched": matched})
            events = self._events_for_chat(denidin_app, chat_id)
        for e in transcript:
            logger.info("TURN %s | sent=%r | reply=%r", e["turn"], e["sent"], e["reply"])
        assert events, (
            f"no LedgerEvent persisted for {chat_id!r} after the image + {turn} detour "
            f"turn(s). Transcript: {transcript!r}"
        )
        return events

    # ==================================================================
    # F3 - multi-component fee-agreement image, seeded exact-match client
    # ==================================================================
    @pytest.mark.sanity
    def test_given_real_multi_component_agreement_image_then_components_correctly_persisted(
        self, denidin_app, http_server, config
    ):
        """Given a real 4-component fee-proposal image (Agreement-test-image.jpg:
        client שחר פישר / עו"ד אילה הוניגמן; components א. 10,000 ₪, ב. hourly
        800 ₪/hr capped at 10h, ג. 15,000 ₪, ד. 5,000 ₪ - all לא כולל מע"מ),
        When the godfather sends it as a WhatsApp image with שחר פישר ALREADY an
        exact Morning client, Then the routed synthetic turn resolves the client
        and the post-turn recognition call persists one הסכם event per fee
        component, each against the exact Morning name.

        The exact component split for THIS document was never separately agreed
        (unlike US9's manifest), so this asserts real, non-placeholder
        properties without presupposing a count: every persisted event is a
        well-formed A-prefixed הסכם against שחר פישר, and each flat-fee amount
        (10,000 / 15,000 / 5,000) is represented somewhere. A wrong extraction
        SHOULD fail this.
        """
        from tests.billed.denidin_mcp_e2e_helpers import _seed_client

        chat_id = self._godfather_chat_id(config)
        self._clear_chat_test_data(denidin_app, chat_id)
        try:
            client_name = "שחר פישר"
            _seed_client(chat_id, "LEDGER_E2E_F3", name=client_name, ensure_exists=True)

            reply = self._send_image(
                http_server, "Agreement-test-image.jpg",
                caption="ההסכם החתום, תרשום ביומן",
                chat_id=chat_id, id_prefix="LEDGER_E2E_IMAGE_AGREEMENT_MULTI",
            )
            # An exact seeded match should resolve silently; the bank only covers
            # the model asking anyway (near-match phrasing / a VAT question).
            bank = ClarificationAnswerBank(
                [
                    {"topic": "which_client",
                     "keywords": ["מצאתי", "האם הכוונה", "התכוונת", "איזה", "לקוח", "נכון"],
                     "answer": f"כן, {client_name}, תרשום ביומן"},
                    {"topic": "vat", "keywords": ['מע"מ', "מעמ"],
                     "answer": 'לא כולל מע"מ, כפי שכתוב בהסכם'},
                ],
                fallback=f"כן, {client_name}, תרשום ביומן",
            )
            self._drive_detour_until_captured(
                denidin_app, chat_id, reply, bank, "LEDGER_E2E_F3"
            )

            events = self._assert_ledger_events_persisted(denidin_app, chat_id, expected_count=None)
            logger.info(f"THEN captured {len(events)} event(s) (persisted): {events}")

            for e in events:
                assert e["source_type"] == "הסכם"
                assert e["event_id"].startswith("A"), f"malformed event_id: {e['event_id']!r}"
                assert "שחר" in (e.get("client_name") or "") or "פישר" in (e.get("client_name") or ""), (
                    f"client_name must resolve to the seeded exact Morning name "
                    f"{client_name!r}, got {e.get('client_name')!r}"
                )
                self._assert_message_links_back_to_event(denidin_app, chat_id, e)

            captured_amounts = {e.get("amount") for e in events}
            for expected_amount in (10000, 15000, 5000):
                assert expected_amount in captured_amounts, (
                    f"expected {expected_amount} among captured amounts {captured_amounts} "
                    f"(document states 10,000 / 15,000 / 5,000 ₪ as its three flat-fee "
                    f"components, plus a 4th hourly component at 800 ₪/hr capped at 10h)"
                )

            image_path = assert_image_path_persisted(denidin_app, chat_id)
            logger.info(f"THEN image_path persisted and resolves to real file: {image_path}")
        finally:
            self._clear_chat_test_data(denidin_app, chat_id)

    # ==================================================================
    # F4 - bank-deposit image -> ledger event AND the document it implies
    #      (bugfix-028), seeded exact-match payer
    # ==================================================================
    @pytest.mark.sanity
    def test_given_real_bank_deposit_image_then_full_fields_correctly_persisted(  # pylint: disable=too-many-locals,too-many-statements
        self, denidin_app, http_server, config
    ):
        """Given a real bank-transfer confirmation screenshot (Deposit_Eti.jpeg:
        05/08/2026, ₪554.00, account holder אסולין אסתר, note "שליחות וצילום
        הערעור לעיריה", bank 31 / branch 112 / account 105397180), When the
        godfather sends it as a WhatsApp image with the payer ALREADY an exact
        Morning client, Then:
        1. it routes as a synthetic turn, resolves the client, and the post-turn
           recognition call persists ONE בנק event - source_type=בנק,
           event_subtype=הפקדה, amount normalized to the exact integer 554,
           B-prefixed event_id, bank_number/branch/account, payer_name forced
           null, client_name carrying the account-holder name, vat_status=כולל,
           txn_date=05/08/2026; and
        2. when the godfather then asks for "an invoice" for that deposit, the
           system creates the right document type (a 320 חשבונית מס/קבלה for
           money already received - never a bare 305), on the deposit's own
           date, booked as a bank transfer (payment type 4), with every value
           coming from the image's own extracted text.

        **bugfix-028** (extended 2026-08-09 with the user's explicit sign-off;
        reworked 2026-09-06 for Feature 069): capture was never the whole story -
        this test used to stop at the ledger event, which is exactly why four
        production invoices came out the wrong type, on the wrong date, unpaid.
        """
        from tests.billed.denidin_mcp_e2e_helpers import (
            _calls_for,
            _seed_client,
            _send_turn,
        )

        BANK_IMAGE_PAYER = "אסתר אסולין"
        BANK_IMAGE_PAYER_SURNAME = "אסולין"

        chat_id = self._godfather_chat_id(config)
        self._clear_chat_test_data(denidin_app, chat_id)
        try:
            # Seed FIRST - Feature 069 requires the client resolved before the
            # בנק event can be persisted at all (not just before the document).
            _seed_client(chat_id, "LEDGER_E2E_F4", name=BANK_IMAGE_PAYER, ensure_exists=True)
            self._assert_no_open_invoice_for(chat_id, BANK_IMAGE_PAYER, id_prefix="LEDGER_E2E_F4")

            reply = self._send_image(
                http_server, "Deposit_Eti.jpeg",
                caption="הפקדה שנכנסה, תרשום ביומן",
                chat_id=chat_id, id_prefix="LEDGER_E2E_IMAGE_BANK_FULL",
            )
            bank = ClarificationAnswerBank(
                [
                    {"topic": "which_client",
                     "keywords": ["מצאתי", "האם הכוונה", "התכוונת", "איזה", "לקוח", "נכון"],
                     "answer": f"כן, {BANK_IMAGE_PAYER}, תרשום ביומן"},
                ],
                fallback=f"כן, {BANK_IMAGE_PAYER}, תרשום ביומן",
            )
            events = self._drive_detour_until_captured(
                denidin_app, chat_id, reply, bank, "LEDGER_E2E_F4", max_turns=4
            )
            events = self._assert_ledger_events_persisted(denidin_app, chat_id, expected_count=1)
            captured = events[0]
            logger.info(f"THEN captured event: {captured}")

            assert captured["source_type"] == "בנק"
            assert captured["event_subtype"] == "הפקדה"
            assert captured["amount"] == 554, (
                f"expected amount normalized to int 554, got {captured['amount']!r}"
            )
            assert captured["event_id"].startswith("B"), f"malformed event_id: {captured['event_id']!r}"
            self._assert_message_links_back_to_event(denidin_app, chat_id, captured)

            assert str(captured.get("bank_number")) == "31", f"bank_number: {captured.get('bank_number')!r}"
            assert str(captured.get("bank_branch")) == "112", f"bank_branch: {captured.get('bank_branch')!r}"
            assert str(captured.get("bank_account")) == "105397180", (
                f"bank_account: {captured.get('bank_account')!r}"
            )
            assert captured.get("payer_name") is None, (
                f"payer_name must be forced null for בנק events, got {captured.get('payer_name')!r}"
            )
            assert BANK_IMAGE_PAYER_SURNAME in (captured.get("client_name") or ""), (
                f"the account-holder name must land in client_name for a בנק event, "
                f"got client_name={captured.get('client_name')!r}"
            )
            assert captured.get("vat_status") == "כולל", (
                f"vat_status is unconditionally כולל for בנק, got {captured.get('vat_status')!r}"
            )
            assert captured.get("txn_date") == "05/08/2026", (
                f"the transaction date on the screenshot (05/08/2026) must be captured, "
                f"got {captured.get('txn_date')!r}"
            )

            # ---------------- bugfix-028: the document the deposit implies -------------
            # Feature 069: the image already routed as a synthetic turn, so the
            # model may take an extra redirect turn before proposing the
            # document. Follow the conversation, approving each round, until a
            # create_combo_document actually fires (max 3 rounds).
            ask_reply, ask_ai = _send_turn(
                chat_id, "תפיק חשבונית עבור זה", id_prefix="LEDGER_E2E_F4_ASK",
            )  # "issue an invoice for this"
            seen_texts = [ask_reply or ""]
            combo_calls = []
            last_ai = ask_ai
            for round_n in range(1, 4):
                assert not _calls_for(last_ai, "create_invoice"), (
                    f"A1: money already in the bank was booked as a plain tax invoice "
                    f"(305) - it leaves the money showing as unpaid. "
                    f"Calls: {last_ai.mcp_calls if last_ai else None!r}"
                )
                combo_calls = _calls_for(last_ai, "create_combo_document")
                if combo_calls:
                    break
                approve_reply, last_ai = _send_turn(
                    chat_id, "כן", id_prefix=f"LEDGER_E2E_F4_APPROVE{round_n}",
                )  # "yes"
                seen_texts.append(approve_reply or "")

            assert combo_calls, (
                f"A1: expected a חשבונית מס/קבלה (320) for an already-received payment "
                f"after 3 approval rounds. Last calls: {last_ai.mcp_calls if last_ai else None!r}"
            )
            assert combo_calls[0]["error"] is None, f"creation failed: {combo_calls[0]!r}"

            approval_text = "\n".join(seen_texts)
            assert BANK_IMAGE_PAYER_SURNAME in approval_text, (
                f"the exchange never names the payer the screenshot shows "
                f"(surname {BANK_IMAGE_PAYER_SURNAME!r}). Turns seen: {seen_texts!r}"
            )
            for element, needle in (("transaction date", "05/08"), ("bank details", "בנק"), ("VAT treatment", "מע")):
                assert needle in approval_text, (
                    f"B3/A2: the exchange omits the {element} even though the screenshot "
                    f"supplied it. Turns seen: {seen_texts!r}"
                )

            _, verify_ai = _send_turn(
                chat_id,
                "תן לי את הפרטים המלאים של המסמך שהופק, כולל התשלומים ותאריך התשלום",
                id_prefix="LEDGER_E2E_F4_VERIFY",
            )
            fetch_calls = _calls_for(verify_ai, "get_invoice_details")
            assert fetch_calls, (
                f"A3/A3b: the verify turn never fetched the document from Morning "
                f"(no get_invoice_details call). Calls: {verify_ai.mcp_calls if verify_ai else None!r}"
            )
            doc = fetch_calls[0].get("output") or ""
            assert "653" not in doc and "654" not in doc, (
                f"A2: the deposited 554 was inflated by 18%: {doc!r}"
            )
            assert "554" in doc, (
                f"A2: the fetched document does not hold the deposited amount: {doc!r}"
            )
            payment = json.loads(doc).get("payment") or {}
            payment_date = payment.get("date") or ""
            for part in ("5", "8", "26"):
                assert part in payment_date, (
                    f"A3: date component {part!r} missing from the fetched document's "
                    f"payment date: {doc!r}"
                )
            assert payment.get("type") == 4, (
                f"A3b: a bank deposit must be booked as payment type 4 (bank transfer), "
                f"the only type Morning stores bank details on: {doc!r}"
            )
        finally:
            self._clear_chat_test_data(denidin_app, chat_id)

    # ==================================================================
    # F5 - photographed 6-component agreement with camera glare on the
    #      client surname; seeded exact-match client + confirming turn
    # ==================================================================
    @pytest.mark.sanity
    def test_given_real_six_component_agreement_image_mor_ben_shaya_then_all_components_correctly_persisted(
        self, denidin_app, http_server, config
    ):
        """Given a real fee-proposal document image (Agreement-mor.jpg: a letter
        dated 3.12.24 between client מור בן שעיה and עו"ד אילה הוניגמן,
        photographed at an angle - the glare band sits on the client surname, so
        the extractor reads the client line as `מר מור בן [לא קריא]` while
        reading the six fee components perfectly), When the godfather sends it as
        a WhatsApp image with מור בן שעיה ALREADY an exact Morning client and
        confirms the partial match when asked, Then it's captured as SIX separate
        components against the resolved exact Morning name:

        1. ייעוץ ופנייה במכתב ראשוני - 2,000 ₪ לפני מע"מ.
        2. ניהול מו"מ, אם לא מגיעים למתווה מוסכם - 4,000 ₪ לפני מע"מ.
        3. ניהול מו"מ, אם מגיעים למתווה מוסכם - 8,000 ₪ לפני מע"מ.
        4. הכנת והגשת כתב תביעה + ייצוג בשלבים מקדמיים - 10,000 ₪ לא כולל מע"מ.
        5. הוכחות וסיכומים - 8,000 ₪ לא כולל מע"מ.
        6. הצלחה בתביעה - 10% מהסכום שנפסק (percent-based, no fixed amount).

        Components 3 and 5 both state 8,000 ₪ - a real duplicate amount; the
        assertion checks the full multiset, to catch a component silently dropped
        for "looking like" a duplicate.

        Feature 069 is what makes this test viable: before 069 there was no
        client-resolution step in the ledger-capture path, so an unreadable
        `client_name` meant `capture_ledger_events_from_text` persisted nothing
        and the model just asked the operator - 0 events, test wants 6. 069's
        mandatory-resolution detour (seeded exact match + a confirming turn) is
        the fix. (Historically tracked as sanity-failure S5, blocked-on-069.)
        """
        from tests.billed.denidin_mcp_e2e_helpers import _seed_client

        chat_id = self._godfather_chat_id(config)
        self._clear_chat_test_data(denidin_app, chat_id)
        try:
            client_name = "מור בן שעיה"
            _seed_client(chat_id, "LEDGER_E2E_F5", name=client_name, ensure_exists=True)

            reply = self._send_image(
                http_server, "Agreement-mor.jpg",
                caption="ההסכם החתום, תרשום ביומן",
                chat_id=chat_id, id_prefix="LEDGER_E2E_IMAGE_AGREEMENT_MOR",
            )
            bank = ClarificationAnswerBank(
                [
                    {"topic": "unreadable_surname_confirm",
                     "keywords": ["מצאתי", "האם הכוונה", "התכוונת", "איזה", "לקוח",
                                  "שם", "לא ברור", "לא קריא", "נכון"],
                     "answer": f"כן, הכוונה ל{client_name}, תרשום ביומן"},
                    {"topic": "vat", "keywords": ['מע"מ', "מעמ"],
                     "answer": 'כפי שכתוב בהסכם - חלק לפני מע"מ וחלק לא כולל מע"מ'},
                ],
                fallback=f"כן, {client_name}, תרשום ביומן",
            )
            self._drive_detour_until_captured(
                denidin_app, chat_id, reply, bank, "LEDGER_E2E_F5", max_turns=6
            )

            events = self._assert_ledger_events_persisted(denidin_app, chat_id, expected_count=6)
            logger.info(f"THEN captured {len(events)} events (persisted): {events}")

            for e in events:
                assert e["source_type"] == "הסכם"
                assert e["event_id"].startswith("A"), f"malformed event_id: {e['event_id']!r}"
                assert "מור" in (e.get("client_name") or "") or "שעיה" in (e.get("client_name") or ""), (
                    f"client_name must resolve to the seeded exact Morning name "
                    f"{client_name!r}, got {e.get('client_name')!r}"
                )
                self._assert_message_links_back_to_event(denidin_app, chat_id, e)

            fixed_amounts = sorted(e.get("amount") for e in events if e.get("amount") is not None)
            assert fixed_amounts == [2000, 4000, 8000, 8000, 10000], (
                f"Expected the 5 real fixed-fee amounts (2,000 / 4,000 / 8,000 twice / "
                f"10,000 - note the genuine duplicate 8,000), got {fixed_amounts}"
            )

            percent_events = [e for e in events if e.get("percent")]
            assert len(percent_events) == 1, (
                f"Expected exactly 1 percent-based component (the 10% success fee), "
                f"got {len(percent_events)}: {percent_events}"
            )
            assert percent_events[0].get("amount") is None, (
                "the percent-based success-fee component should have no fixed amount"
            )
        finally:
            self._clear_chat_test_data(denidin_app, chat_id)

    # ==================================================================
    # False-positive guard - unchanged by Feature 069 (a personal note
    # produces no ledger stash, so no synthetic routing fires)
    # ==================================================================
    def test_given_non_agreement_image_when_processed_then_no_ledger_event_captured(
        self, denidin_app, http_server
    ):
        """Given a real image that is genuinely NOT a fee agreement or bank
        deposit (a personal handwritten note, confirmed out-of-scope during the
        AHLedger project's own audit), When sent as a WhatsApp image, Then no
        ledger stash is built, no synthetic turn is routed, and nothing is
        persisted under data/events/ (T017e). The false-positive guard for
        Feature 069's routing signal - it must NOT fire on this."""
        from denidin import handle_image_message

        chat_id = self._fresh_chat_id("image_neither")
        before = len(self._events_for_chat(denidin_app, chat_id))

        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770000400,
            'idMessage': 'LEDGER_E2E_IMAGE_NEITHER_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {
                    'downloadUrl': f'{http_server}/not_an_agreement_personal_note.jpg',
                    'fileName': 'not_an_agreement_personal_note.jpg',
                    'mimeType': 'image/jpeg',
                    'caption': '',
                    'jpegThumbnail': '',
                    'isForwarded': False,
                    'forwardingScore': 0,
                }
            }
        })

        logger.info("GIVEN a real non-agreement image (personal handwritten note)")
        handle_image_message(notification)
        logger.info("WHEN DeniDin processes it via the image pipeline")

        response = get_response(notification)
        assert_response_exists(response)

        after = len(self._events_for_chat(denidin_app, chat_id))
        logger.info(f"THEN persisted-event count before={before}, after={after}")
        assert after == before, "capture_ledger_event should NOT have been called for a non-agreement image"

        image_path = assert_image_path_persisted(denidin_app, chat_id)
        logger.info(f"THEN image_path persisted and resolves to real file: {image_path}")
