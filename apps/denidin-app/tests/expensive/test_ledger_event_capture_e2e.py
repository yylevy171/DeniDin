"""
End-to-End Integration Test: Ledger Event Recognition (runtime_constitution.md) - image flow

Tests the real OpenAI function-calling mechanism end-to-end - NOT unit-testable, since
what's actually under test is whether the real model (a) classifies correctly (calls
`capture_ledger_event` only when the content genuinely warrants it) and (b) extracts
fields correctly via the real vision/image pipeline.

Feature 033 (Ledger Event Persistence): events now persist as their own files under
`{data_root}/events/{event_id}.json` via LedgerEventManager, not in session.json's
(now-removed) `pending_ledger_events`. See
specs/in-progress/033-ledger-event-persistence/ for the full design - data-model.md's
migration appendix has the verbatim source text used by the multi-stage test below.

Images are real source material from the AHLedger reconciliation project
(tests/fixtures/media/ledger_events/), each with independently verified ground-truth
content (see the corresponding AHLedger transcript for the exact wording each image
should produce):
- agreement_idan_shabtai.jpg = WhatsApp גבייה/IMG-20250925-WA0026.jpg (a real signed
  fee-agreement letter: עידן שבתאי, disciplinary proceeding, tiered pricing 20,000/60,000/
  8,000 ₪ + VAT)
- bank_deposit_kehilat_tzair.jpg = bank/00000650-PHOTO-2025-10-07-20-29-27.jpg (a real
  bank-transfer confirmation screenshot: קהילת צעיר, 9,440 ₪, "זיכוי ממס"ב")
- not_an_agreement_personal_note.jpg = WhatsApp גבייה/IMG-20260316-WA0021.jpg (a personal
  handwritten scratch note, confirmed NOT a fee agreement during that project's own audit)
- Agreement-test-image.jpg (T024a) = a real fee-proposal letter (שחר פישר / עו"ד אילה
  הוניגמן, 27.1.253) with FOUR distinct fee components (10,000 / hourly-800-capped-10h /
  15,000 / 5,000 ₪, all לא כולל מע"מ) - ground truth read directly from the image by the
  implementing agent (2026-07-29), no separate human transcript for this one.
- Bank-test-image.jpg (T024b) = a real bank-transfer confirmation (12/07/2026, ₪1,500.00,
  עטיה רועי מאיר, "יעוץ משפטי (הערת לקוח)") - same, ground truth read directly from the image.

Text-flow counterpart split across two tests/billed/ files:
- tests/billed/test_ledger_event_capture_billed.py (Feature 029's original split)
- tests/billed/test_ledger_event_capture_text_billed.py (2026-08-03: 9 more text-only
  tests found still living here under `@pytest.mark.expensive`, despite sending plain
  textMessage webhooks with no vision call at all - moved out during a test-tier audit)
Only genuinely image-flow tests stay `expensive` here since they make real vision calls.

NO MOCKING - real OpenAI API calls, real image pipeline, real session storage.

Run ONE test at a time, with fresh explicit approval each time:
    pytest tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::<name> -v -m expensive
"""

import json
import logging
import re
import threading
import uuid
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote

import pytest

from src.models.config import AppConfiguration
from src.utils.time_utils import local_from_timestamp
from tests.e2e_helpers import (
    create_real_notification,
    get_response,
    assert_response_exists,
    assert_image_path_persisted,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@pytest.mark.expensive
class TestLedgerEventCaptureE2E:
    """
    Given/When/Then E2E coverage for Ledger Event Recognition's image flow:
    - Given an image that genuinely warrants capture, When processed, Then
      `capture_ledger_event` is called and the result lands in its own file under
      `data/events/`, correctly shaped per data-model.md.
    - Given an image that doesn't, When processed, Then it is NOT called - the
      false-positive guard matters as much as the capture itself.
    """

    @pytest.fixture(scope="class")
    def http_server(self):
        """Local HTTP server serving tests/fixtures/media/ledger_events/, simulating
        Green API's file download URLs (same pattern as test_media_e2e.py)."""
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "media" / "ledger_events"

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(fixtures_dir), **kwargs)

            def translate_path(self, path):
                return super().translate_path(unquote(path))

            def log_message(self, format, *args):
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

        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        test_data_root = Path(__file__).parent.parent.parent / "test_data"
        config.data_root = str(test_data_root)
        config.memory['session']['storage_dir'] = str(test_data_root / "sessions")
        config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")
        return config

    @pytest.fixture
    def denidin_app(self, config):
        """Initialize the full denidin app - NO MOCKING."""
        import denidin

        if denidin.denidin_app is None:
            config_dict = {
                'green_api_instance_id': config.green_api_instance_id,
                'green_api_token': config.green_api_token,
                'ai_api_key': config.ai_api_key,
                'ai_model': config.ai_model,
                # Must be passed through explicitly - otherwise initialize_app falls
                # back to AppConfiguration's gpt-4o-mini default and the image path
                # silently exercises a different (weaker) vision model than production,
                # which passes these same keys (see denidin.py __main__ config_dict).
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

        # Safety guard, every call (not just first-init): LedgerEventManager.storage_dir
        # MUST resolve under this test's isolated data_root (test_data/), never the real
        # production/dev data root - a wiring mistake here would write test noise into
        # the real financial ledger. Fails loud and immediately rather than silently
        # polluting data/events/ or dev_data/events/.
        actual_events_dir = Path(denidin.denidin_app.ai_handler.ledger_event_manager.storage_dir).resolve()
        expected_root = Path(config.data_root).resolve()
        assert actual_events_dir.is_relative_to(expected_root), (
            f"LedgerEventManager.storage_dir={actual_events_dir} is NOT under this "
            f"test's isolated data_root={expected_root} - refusing to proceed, this "
            f"would write into production/dev ledger data"
        )
        return denidin.denidin_app

    # Fixed webhook 'timestamp' epochs used across this class's tests (mirrored
    # from each test's own notification literal) - these are FIXED, not "now",
    # so every run maps to the exact same LedgerEventManager event_id bucket
    # (letter+ddmmyy+hhmm). REQ-ID-003 only allows 10 seq-digit files per
    # bucket; without cleanup, test_data/events/ accumulates one file per run
    # and permanently exhausts the bucket after ~10 runs - the same bug that
    # broke tests/billed/test_ledger_event_capture_text_billed.py 2026-08-10
    # (bugfix-028 billed run), fixed there the same way.
    _FIXED_MESSAGE_TIMESTAMPS = (
        1770000200, 1770000300, 1770000400, 1770001300, 1770001400, 1770001500,
    )

    @classmethod
    def _event_id_bucket_prefixes(cls) -> set:
        """The event_id prefix (letter+ddmmyy+hhmm, sans seq digit) each fixed
        timestamp above maps to, computed the same way LedgerEventManager does
        (bugfix-037: via time_utils.local_from_timestamp) - so cleanup targets
        exactly the files these tests could have produced, nothing else in
        test_data/events/."""
        return {
            f"A{local_from_timestamp(ts).strftime('%d%m%y%H%M')}"
            for ts in cls._FIXED_MESSAGE_TIMESTAMPS
        }

    @pytest.fixture(autouse=True)
    def _clean_fixed_timestamp_events(self, config):
        """Before AND after every test in this class: remove any previously-
        persisted event file for this class's fixed-timestamp buckets, so
        REQ-ID-003's 10-seq-digit cap never silently exhausts across repeated
        runs again (see _FIXED_MESSAGE_TIMESTAMPS docstring above)."""
        def _clean():
            events_dir = Path(config.data_root) / "events"
            if not events_dir.exists():
                return
            prefixes = self._event_id_bucket_prefixes()
            for f in events_dir.glob("*.json"):
                if any(f.stem.startswith(p) for p in prefixes):
                    f.unlink()

        _clean()
        yield
        _clean()

    @staticmethod
    def _fresh_chat_id(label: str) -> str:
        """A unique-per-run chat_id, so re-running a single test doesn't accumulate
        unbounded ledger events for a shared chat and confuse assertions."""
        return f"97250{uuid.uuid4().hex[:7]}_{label}@c.us"

    @staticmethod
    def _godfather_chat_id(config) -> str:
        """bugfix-028: the deposit->document tests need a chat whose role actually
        gets the Morning tools attached (RBAC-gated to godfather/admin), so they
        cannot use a random `_fresh_chat_id`."""
        phone = str(config.godfather_phone).lstrip("+")
        return phone if phone.endswith("@c.us") else f"{phone}@c.us"

    # bugfix-028: the payer named on Bank-test-image.jpg. Both deposit->document
    # tests must resolve this name from the IMAGE's own extracted text (user,
    # 2026-08-09: "use the extracted text for every data"), so it has to exist as
    # a real Morning client for either test to be able to create anything.
    BANK_IMAGE_PAYER = "עטיה רועי מאיר"

    @staticmethod
    def _assert_no_open_invoice_for(chat_id, name, id_prefix):
        """Guard against cross-test interference: both deposit tests use the same
        payer (the one on the screenshot), and their expected outcome DIFFERS
        depending on whether an unpaid invoice for that payer already exists -
        320 when none does, 400 when one does. A leftover open invoice from a
        half-finished run would silently invert the expected result.
        """
        from tests.billed.denidin_mcp_e2e_helpers import _calls_for, _send_turn

        _, ai_response = _send_turn(
            chat_id, f"אילו חשבוניות פתוחות יש ל{name}?", id_prefix=f"{id_prefix}_PRECHECK"
        )
        listings = _calls_for(ai_response, "list_invoices")
        output = (listings[0]["output"] or "") if listings else ""
        assert "פתוח" not in output, (
            f"precondition failed: {name!r} already has an unpaid invoice in the "
            f"sandbox, so this deposit would correctly close it (a 400) instead of "
            f"producing a new 320. Close it in Morning, then re-run. Listing: {output!r}"
        )

    @staticmethod
    def _clear_chat_test_data(denidin_app, chat_id):
        """bugfix-028 (user requirement, 2026-08-09): clear this chat's test data
        before AND after, so a shared, non-random chat_id can't collide with a
        previous run's events/session or leave duplicates behind for the next one.

        Only ever touches test_data/ - the `denidin_app` fixture above already
        refuses to run at all if LedgerEventManager.storage_dir is not under this
        test's isolated data_root.
        """
        # 2026-08-19: LedgerEvent no longer carries its own whatsapp_chat (removed -
        # redundant with session_id) - resolve session_id via SessionManager
        # instead (safe even pre-test, when no real session exists yet: creates
        # an empty one that matches zero real event files).
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

    @staticmethod
    def _events_for_chat(denidin_app, chat_id):
        """All persisted LedgerEvent files (data/events/*.json) for this chat_id,
        sorted by captured_at - reads the real files off disk, not an in-memory
        proxy, so assertions prove the event genuinely landed in permanent storage
        (Feature 033's whole point).

        2026-08-19: LedgerEvent no longer carries its own whatsapp_chat (removed -
        redundant with session_id, which already points at a session that carries
        its own whatsapp_chat) - filters by session_id instead, resolved via the
        real SessionManager for this chat_id."""
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
    def _assert_ledger_events_persisted(denidin_app, chat_id, expected_count, expected_event_timestamp):
        """Asserts events were persisted for this chat, each with the bookkeeping
        fields LedgerEventManager.add_ledger_event adds (event_datetime = the real
        hard pointer, captured_at, message_id) present and correct. Returns the
        events in capture order for further field-specific assertions.

        expected_count: exact count required, or None to only assert >=1 (used when
        the real component split is genuinely uncertain - e.g. a multi-component
        document whose exact chunking by the model hasn't been separately agreed,
        unlike the גיליאן דוידיאן case).

        expected_event_timestamp: the real Green API notification timestamp (unix
        epoch seconds) these events should be pointed at - the constitution's "hard
        pointer" requirement (never processing time, never a guess).

        2026-08-20 (billed/expensive test sweep for Feature 043's Phase 11 schema
        revision): this helper was stale in the exact same way
        tests/billed/test_ledger_event_capture_billed.py's copy was found and fixed
        on 2026-08-18 - `message_timestamp` and `sender` were both removed from the
        persisted record (folded into event_datetime; see data-model.md SS1b), but
        this expensive-tier copy still asserted on them, which would have failed
        the very next real (billed) run of this file. Fixed to check
        `event_datetime` (DD/MM/YYYY HH:MM, Israel local) and dropped the sender
        assertion entirely, matching the billed helper exactly.
        """
        events = TestLedgerEventCaptureE2E._events_for_chat(denidin_app, chat_id)
        if expected_count is None:
            assert len(events) >= 1, f"Expected at least 1 persisted ledger event for {chat_id}, found 0"
        else:
            assert len(events) == expected_count, (
                f"Expected {expected_count} persisted ledger event(s) for {chat_id}, "
                f"found {len(events)}: {events}"
            )

        # bugfix-037/Phase 11: event_datetime is Israel local time, "DD/MM/YYYY HH:MM".
        expected_event_datetime = local_from_timestamp(expected_event_timestamp).strftime("%d/%m/%Y %H:%M")
        for record in events:
            assert record.get("event_datetime") == expected_event_datetime, (
                f"event_datetime={record.get('event_datetime')!r} does not match the "
                f"real notification timestamp {expected_event_datetime!r} - the constitution's "
                f"'hard pointer' requirement (never processing time, never a guess)"
            )
            assert record.get("captured_at"), "captured_at was not persisted"
            assert record.get("message_id"), (
                "message_id must be non-null for events captured after Feature 033 - "
                "closes the traceability gap that motivated this feature"
            )
            assert "raw_message_excerpt" not in record, (
                "raw_message_excerpt was removed from the persisted schema (2026-08-18) - "
                "the source content now lives on the message record itself "
                "(Message.content for text, Message.extracted_text for media)"
            )
        return events

    @staticmethod
    def _assert_message_links_back_to_event(denidin_app, chat_id, event):
        """Cross-checks the reverse link: the source message's ledger_event_ids
        (Feature 033) must include this event's event_id."""
        session_manager = denidin_app.ai_handler.session_manager
        session_id = session_manager.chat_to_session[chat_id]
        message_id = event["message_id"]
        message_file = session_manager.storage_dir / session_id / "messages" / f"{message_id}.json"
        with open(message_file, encoding='utf-8') as f:
            message_data = json.load(f)
        assert event["event_id"] in message_data["ledger_event_ids"], (
            f"event {event['event_id']} not found in source message {message_id}'s "
            f"ledger_event_ids={message_data.get('ledger_event_ids')!r}"
        )

    # ------------------------------------------------------------------
    # IMAGE FLOW (also exercises bugfix-017's session-linkage fix)
    # ------------------------------------------------------------------

    @pytest.mark.sanity
    def test_given_real_agreement_image_when_processed_then_ledger_event_captured_via_image_path(
        self, denidin_app, http_server
    ):
        """Given a real, previously-transcribed fee-agreement document image (עידן
        שבתאי, disciplinary-proceeding representation), When sent as a WhatsApp image,
        Then it's captured via the image path (ImageExtractor -> MediaHandler) as
        THREE separate components, matching the document's real structure verified
        directly against the image (2026-07-30) - never one combined event (T017c):
        1. שימוע + מו"מ להסדר טיעון (track א', no evidence hearing needed): 20,000 ₪
           + VAT = 23,600 ₪.
        2. ניהול תיק מלא עם שמיעת ראיות (track ב', if no plea deal reached): 60,000 ₪
           + VAT = 70,800 ₪.
        3. תוספת: שימוע אצל נציב שירות המדינה לבחינת השעיה - additive on top of
           whichever of track א'/ב' applies: 8,000 ₪ + VAT = 9,440 ₪.

        This is the same "never aggregate" principle as hourly work-log entries,
        generalized to multi-stage/conditional fee agreements (constitution updated
        2026-07-30 - see config/runtime_constitution.md's Ledger Event Recognition
        Step 2). Also confirms (Feature 033) a real, non-null message_id on the
        image path."""
        from denidin import handle_image_message

        chat_id = self._fresh_chat_id("image_agreement")
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770000200,
            'idMessage': 'LEDGER_E2E_IMAGE_AGREEMENT_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {
                    'downloadUrl': f'{http_server}/agreement_idan_shabtai.jpg',
                    'fileName': 'agreement_idan_shabtai.jpg',
                    'mimeType': 'image/jpeg',
                    'caption': '',
                    'jpegThumbnail': '',
                    'isForwarded': False,
                    'forwardingScore': 0,
                }
            }
        })

        logger.info("GIVEN a real fee-agreement document image (עידן שבתאי, 3 conditional fee tiers)")
        handle_image_message(notification)
        logger.info("WHEN DeniDin processes it via the image pipeline")

        response = get_response(notification)
        assert_response_exists(response)

        # THEN: verify against the real persisted data/events/{event_id}.json files,
        # including event_datetime being the real notification timestamp
        # (1770000200) - NOT processing time (the bug found and fixed 2026-07-28).
        events = self._assert_ledger_events_persisted(
            denidin_app, chat_id, expected_count=3, expected_event_timestamp=1770000200
        )
        logger.info(f"THEN captured {len(events)} events (persisted): {events}")

        for e in events:
            assert e["source_type"] == "הסכם"
            assert e["event_subtype"] == "יצירה"
            assert "עידן" in (e.get("client_name") or "") or "שבתאי" in (e.get("client_name") or "")
            assert e["event_id"].startswith("A")
            # Feature 033: this is the first real proof message_id threading works on
            # the image path end-to-end (component tests use a real object but not a
            # real call).
            self._assert_message_links_back_to_event(denidin_app, chat_id, e)

        amounts = sorted(e.get("amount") for e in events)
        assert amounts == [9440, 23600, 70800], (
            f"Expected the 3 real fee-tier amounts (23,600 / 70,800 / 9,440), got "
            f"{amounts} - if this fails, the model did not split the document per "
            f"stage/condition despite the constitution's explicit rule for this"
        )

        # Also confirms bugfix-017: the media turn itself must be visible in the session,
        # not just the captured ledger event.
        session = denidin_app.ai_handler.session_manager.get_session(chat_id)
        assert len(session.message_ids) >= 2, "bugfix-017: media turn was not stored in the session"

        # bugfix-009 (reopened 2026-07-30): the media turn's user message must also
        # carry a real image_path, not just exist.
        image_path = assert_image_path_persisted(denidin_app, chat_id)
        logger.info(f"THEN image_path persisted and resolves to real file: {image_path}")

    @pytest.mark.sanity
    def test_given_real_bank_deposit_screenshot_when_processed_then_captured_as_bank_deposit(
        self, denidin_app, http_server
    ):
        """Given a real bank-transfer confirmation screenshot (קהילת צעיר, 9,440 ₪),
        When sent as a WhatsApp image, Then it's captured with source_type=בנק, a
        B-prefixed event_id, and normalized integer amount (T017d)."""
        from denidin import handle_image_message

        chat_id = self._fresh_chat_id("image_bank")
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770000300,
            'idMessage': 'LEDGER_E2E_IMAGE_BANK_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {
                    'downloadUrl': f'{http_server}/bank_deposit_kehilat_tzair.jpg',
                    'fileName': 'bank_deposit_kehilat_tzair.jpg',
                    'mimeType': 'image/jpeg',
                    'caption': '',
                    'jpegThumbnail': '',
                    'isForwarded': False,
                    'forwardingScore': 0,
                }
            }
        })

        logger.info("GIVEN a real bank-deposit screenshot (קהילת צעיר, 9,440 ₪)")
        handle_image_message(notification)
        logger.info("WHEN DeniDin processes it via the image pipeline")

        response = get_response(notification)
        assert_response_exists(response)

        events = self._assert_ledger_events_persisted(
            denidin_app, chat_id, expected_count=1, expected_event_timestamp=1770000300
        )
        captured = events[0]
        logger.info(f"THEN captured event (persisted): {captured}")

        assert captured["source_type"] == "בנק"
        assert captured["event_subtype"] == "הפקדה"
        assert captured["amount"] == 9440, f"expected amount normalized to int 9440, got {captured['amount']!r}"
        assert captured["event_id"].startswith("B")
        self._assert_message_links_back_to_event(denidin_app, chat_id, captured)

        # Phase 11 (2026-08-16): payer_name is a הסכם-only concept, forced null for
        # every בנק event regardless of what the model passed - no bank_number/
        # bank_branch/bank_account ground truth is asserted for THIS image (a
        # "זיכוי ממס"ב" credit, visually distinct from Bank-test-image.jpg and not
        # confirmed at the extraction layer either - see
        # test_image_classification_e2e.py's test_kehilat_tzair_deposit_is_classified_
        # as_a_bank_deposit, which only asserts amount for the same reason), but this
        # payer_name/vat_status enforcement is unconditional and applies here too.
        assert captured.get("payer_name") is None, (
            f"payer_name must be forced null for בנק events, got {captured.get('payer_name')!r}"
        )
        assert captured.get("vat_status") == "כולל", (
            f"vat_status is unconditionally כולל for בנק (money already deposited "
            f"necessarily contains the VAT element already), got {captured.get('vat_status')!r}"
        )

        # Feature 043 (2026-08-18): raw_message_excerpt was removed from the ledger
        # event itself - the source message's own extracted_text is now where this
        # content lives (real proof on the real image E2E path, not just a unit test).
        session_manager = denidin_app.ai_handler.session_manager
        session_id = session_manager.chat_to_session[chat_id]
        message_file = (
            session_manager.storage_dir / session_id / "messages" / f"{captured['message_id']}.json"
        )
        with open(message_file, encoding='utf-8') as f:
            message_data = json.load(f)
        assert message_data.get("extracted_text"), (
            "the real vision extraction's text must land on the message record"
        )

        # bugfix-009 (reopened 2026-07-30): the media turn's user message must also
        # carry a real image_path, not just exist.
        image_path = assert_image_path_persisted(denidin_app, chat_id)
        logger.info(f"THEN image_path persisted and resolves to real file: {image_path}")

    def test_given_non_agreement_image_when_processed_then_no_ledger_event_captured(
        self, denidin_app, http_server
    ):
        """Given a real image that is genuinely NOT a fee agreement or bank deposit (a
        personal handwritten note, confirmed out-of-scope during the AHLedger project's
        own audit), When sent as a WhatsApp image, Then capture_ledger_event is NOT
        called - no file created under data/events/ (T017e)."""
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

        # bugfix-009 (reopened 2026-07-30): even when no ledger event is captured,
        # the media turn itself must still carry a real image_path.
        image_path = assert_image_path_persisted(denidin_app, chat_id)
        logger.info(f"THEN image_path persisted and resolves to real file: {image_path}")

    # ------------------------------------------------------------------
    # REAL-IMAGE DATA-MODEL CORRECTNESS (Feature 033) - 2 new real images (T024a/b),
    # ground truth read directly from the images by the implementing agent (2026-07-29,
    # no separate human transcript available for these two, unlike the three images
    # above) - see each test's docstring for what's actually on the image.
    # ------------------------------------------------------------------

    @pytest.mark.sanity
    def test_given_real_multi_component_agreement_image_then_components_correctly_persisted(
        self, denidin_app, http_server
    ):
        """Given a real fee-proposal document image (Agreement-test-image.jpg: a
        letter between client שחר פישר and עו"ד אילה הוניגמן, 27.1.253, with FOUR
        distinct fee components - א. כתב הגנה+כתב תשובה מקדמי, 10,000 ₪ לא כולל
        מע"מ; ב. גישור, שעתי 800 ₪/שעה עד 10 שעות, לא כולל מע"מ; ג. הוכחות, 15,000 ₪
        לא כולל מע"מ; ד. סיכומים, 5,000 ₪ לא כולל מע"מ), When sent as a WhatsApp
        image, Then it's captured via the image path with source_type=הסכם.

        Unlike the גיליאן דוידיאן multi-stage test (T020a), the "correct" component
        split for THIS specific document was not separately agreed with the user
        before writing this test - so this asserts real, meaningful, non-placeholder
        properties without presupposing an exact event count: every persisted event
        for this chat has a well-formed A-prefixed event_id and source_type=הסכם
        (T024a's "assert for some id" instruction), and the flat-fee amounts stated
        in the document (10,000 / 15,000 / 5,000) are each represented somewhere
        across the persisted event(s)' amount fields - proving genuine correct
        extraction happened, not just that *something* got captured. If the model
        doesn't extract these correctly, this SHOULD fail - that's real information,
        not something to soften (same philosophy as T020a)."""
        from denidin import handle_image_message

        chat_id = self._fresh_chat_id("image_agreement_multi")
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770001300,
            'idMessage': 'LEDGER_E2E_IMAGE_AGREEMENT_MULTI_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {
                    'downloadUrl': f'{http_server}/Agreement-test-image.jpg',
                    'fileName': 'Agreement-test-image.jpg',
                    'mimeType': 'image/jpeg',
                    'caption': '',
                    'jpegThumbnail': '',
                    'isForwarded': False,
                    'forwardingScore': 0,
                }
            }
        })

        logger.info("GIVEN a real 4-component fee-proposal document image (שחר פישר / עו\"ד אילה הוניגמן)")
        handle_image_message(notification)
        logger.info("WHEN DeniDin processes it via the image pipeline")

        response = get_response(notification)
        assert_response_exists(response)

        events = self._assert_ledger_events_persisted(
            denidin_app, chat_id, expected_count=None, expected_event_timestamp=1770001300
        )
        logger.info(f"THEN captured {len(events)} event(s) (persisted): {events}")

        for e in events:
            assert e["source_type"] == "הסכם"
            assert e["event_id"].startswith("A"), f"malformed event_id: {e['event_id']!r}"
            self._assert_message_links_back_to_event(denidin_app, chat_id, e)

        captured_amounts = {e.get("amount") for e in events}
        for expected_amount in (10000, 15000, 5000):
            assert expected_amount in captured_amounts, (
                f"expected {expected_amount} among captured amounts {captured_amounts} "
                f"(document states 10,000/15,000/5,000 ₪ as its three flat-fee "
                f"components, plus a 4th hourly component at 800 ₪/hr capped at 10h)"
            )

    @pytest.mark.sanity
    def test_given_real_bank_deposit_image_then_full_fields_correctly_persisted(
        self, denidin_app, http_server, config
    ):
        """Given a real bank-transfer confirmation screenshot (Bank-test-image.jpg:
        a Bank Hapoalim-style transfer, 12/07/2026, ₪1,500.00, from account holder
        עטיה רועי מאיר, note "יעוץ משפטי (הערת לקוח)"), When sent as a WhatsApp
        image, Then it's captured with source_type=בנק, event_subtype=הפקדה, and
        amount normalized to the exact integer 1500 (T024b).

        **bugfix-028 (A1, A2-T3, A3-T2, A3b, B3-optionals), extended 2026-08-09
        with the user's explicit sign-off to modify an already-approved test.**
        Capture was never the whole story: this test used to stop at the ledger
        event and never ask for the document the deposit implies, which is exactly
        why four production invoices came out as the wrong document type, on the
        wrong date, unpaid. It now continues into document creation and asserts
        what Morning actually stored.

        This makes the test dependent on a live Morning tunnel and on running as
        the godfather (the Morning tools are RBAC-gated), unlike every other test
        in this class.
        """
        from denidin import handle_image_message
        from tests.billed.denidin_mcp_e2e_helpers import (
            _calls_for,
            _seed_client,
            _send_turn,
            _send_turn_and_approve,
        )

        chat_id = self._godfather_chat_id(config)
        self._clear_chat_test_data(denidin_app, chat_id)
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770001400,
            'idMessage': 'LEDGER_E2E_IMAGE_BANK_FULL_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {
                    'downloadUrl': f'{http_server}/Bank-test-image.jpg',
                    'fileName': 'Bank-test-image.jpg',
                    'mimeType': 'image/jpeg',
                    'caption': '',
                    'jpegThumbnail': '',
                    'isForwarded': False,
                    'forwardingScore': 0,
                }
            }
        })

        logger.info("GIVEN a real bank-transfer confirmation screenshot (₪1,500.00, עטיה רועי מאיר)")
        handle_image_message(notification)
        logger.info("WHEN DeniDin processes it via the image pipeline")

        response = get_response(notification)
        assert_response_exists(response)

        events = self._assert_ledger_events_persisted(
            denidin_app, chat_id, expected_count=1, expected_event_timestamp=1770001400
        )
        captured = events[0]
        logger.info(f"THEN captured event: {captured}")

        assert captured["source_type"] == "בנק"
        assert captured["event_subtype"] == "הפקדה"
        assert captured["amount"] == 1500, f"expected amount normalized to int 1500, got {captured['amount']!r}"
        assert captured["event_id"].startswith("B"), f"malformed event_id: {captured['event_id']!r}"
        self._assert_message_links_back_to_event(denidin_app, chat_id, captured)

        # Phase 11 (2026-08-16/2026-08-20 sweep): bank_number/bank_branch/bank_account
        # are new persisted fields (real-data-grounded schema revision), with known
        # ground truth for this exact image already established at the extraction
        # layer (tests/expensive/test_image_classification_e2e.py's
        # test_bank_test_image_is_classified_as_a_bank_deposit) - this is the first
        # real proof those fields survive all the way through to the persisted
        # ledger event, not just the model's raw extraction.
        assert str(captured.get("bank_number")) == "31", f"bank_number: {captured.get('bank_number')!r}"
        assert str(captured.get("bank_branch")) == "109", f"bank_branch: {captured.get('bank_branch')!r}"
        assert str(captured.get("bank_account")) == "105542585", (
            f"bank_account: {captured.get('bank_account')!r}"
        )

        # Finding #4 (2026-08-18 player review) + payer_name/vat_status enforcement:
        # payer_name is a הסכם-only concept, forced null for בנק regardless of what
        # the model passed - the account-holder name is rescued into client_name
        # instead (never lose a real captured name to a field-choice mistake).
        assert captured.get("payer_name") is None, (
            f"payer_name must be forced null for בנק events, got {captured.get('payer_name')!r}"
        )
        assert self.BANK_IMAGE_PAYER.split()[0] in (captured.get("client_name") or ""), (
            f"the account-holder name (עטיה רועי מאיר) must land in client_name for "
            f"a בנק event, got client_name={captured.get('client_name')!r}"
        )
        assert captured.get("vat_status") == "כולל", (
            f"vat_status is unconditionally כולל for בנק (money already deposited "
            f"necessarily contains the VAT element already), got {captured.get('vat_status')!r}"
        )

        # ---------------- bugfix-028: the document the deposit implies ----------------
        try:
            # Asserted in the PERSISTED form, not the model's raw output: the
            # model emits ISO (per capture_ledger_event's schema) and
            # `_normalize_iso_date` converts it to this project's stored
            # DD/MM/YYYY convention, matching `event_datetime`'s date portion
            # (REQ-DATA-005/007). Despite its name that helper normalizes FROM
            # ISO, not to it.
            assert captured.get("txn_date") == "12/07/2026", (
                f"A3: the transaction date on the screenshot (12/07/2026) must be "
                f"captured, got {captured.get('txn_date')!r} - the document date cannot "
                f"be right if the deposit's own date was never established"
            )

            # Everything the document needs comes from the image's own extracted
            # text - payer, amount, date, bank details (user, 2026-08-09). The
            # request itself supplies nothing but the intent, and deliberately
            # says "חשבונית", the ordinary word a user would use, NOT a document
            # type: choosing the type is the system's job and is what A1 is about.
            _seed_client(chat_id, "B028_A1T1", name=self.BANK_IMAGE_PAYER, ensure_exists=True)
            self._assert_no_open_invoice_for(chat_id, self.BANK_IMAGE_PAYER, id_prefix="B028_A1T1")

            logger.info("WHEN the godfather asks for an invoice for that deposit")
            ask_result, (reply, ai_response) = _send_turn_and_approve(
                chat_id,
                "תפיק חשבונית עבור זה",
                id_prefix="B028_A1T1",
            )
            approval_text = ask_result[0] or ""

            # The payer was never typed - it can only have come from the image.
            assert self.BANK_IMAGE_PAYER.split()[0] in approval_text, (
                f"the approval doesn't name the payer the screenshot shows "
                f"({self.BANK_IMAGE_PAYER}) - the extracted text is not being used. "
                f"Approval was: {approval_text!r}"
            )

            # A1: money already in the bank is never a bare 305.
            assert not _calls_for(ai_response, "create_invoice"), (
                f"A1: a deposit produced a plain tax invoice (305) - it leaves the "
                f"money showing as unpaid. Calls: {ai_response.mcp_calls if ai_response else None!r}"
            )
            combo_calls = _calls_for(ai_response, "create_combo_document")
            assert combo_calls, (
                f"A1: expected a חשבונית מס/קבלה (320) for an already-received payment. "
                f"Calls: {ai_response.mcp_calls if ai_response else None!r}"
            )
            assert combo_calls[0]["error"] is None, f"creation failed: {combo_calls[0]!r}"

            # B3 optionals: what the user was asked to approve must carry the
            # transaction date and the bank details, since both are known here.
            for element, needle in (
                ("transaction date", "12/07"),
                ("bank details", "בנק"),
            ):
                assert needle in approval_text, (
                    f"B3: the approval omits the {element} even though the screenshot "
                    f"supplied it. Approval was: {approval_text!r}"
                )

            # A2-T3: a payment reference defaults to VAT included, stated explicitly.
            assert "מע" in approval_text, (
                f"A2: the VAT treatment is never stated. Approval was: {approval_text!r}"
            )

            _, verify_ai = _send_turn(
                chat_id,
                "תן לי את הפרטים המלאים של המסמך שהופק, כולל התשלומים ותאריך התשלום",
                id_prefix="B028_A1T1_VERIFY",
            )
            # Assert on what Morning actually returned for the document (the raw
            # get_invoice_details tool output), not on the model's prose retelling
            # of it - the model nondeterministically restyles dates (12.07.2026 vs
            # 12/07/2026), section headers and which fields it echoes. The verify
            # turn's only job is to make the model FETCH the document; the fetched
            # document is what we assert on. Same pattern as
            # _assert_no_open_invoice_for above.
            fetch_calls = _calls_for(verify_ai, "get_invoice_details")
            assert fetch_calls, (
                f"A3/A3b: the verify turn never fetched the document from Morning "
                f"(no get_invoice_details call). Calls: "
                f"{verify_ai.mcp_calls if verify_ai else None!r}"
            )
            doc = fetch_calls[0].get("output") or ""
            # A2-T3: 1,500 arrived in the bank; 1,500 is what the fetched document
            # holds, never inflated by 18%.
            assert "1,770" not in doc and "1770" not in doc, (
                f"A2: the deposited 1,500 was inflated by 18%: {doc!r}"
            )
            assert "1,500" in doc or "1500" in doc, (
                f"A2: the fetched document does not hold the deposited amount: {doc!r}"
            )
            # A3-T2: the payment carries the deposit's OWN date (12 / 07 / 26),
            # not the day the document was issued. Loosened to the three date
            # components appearing in the payments section rather than one exact
            # separator style, so a dotted or ISO rendering still passes.
            payments_section = doc.split("תשלומים")[-1] if "תשלומים" in doc else doc
            for part in ("12", "7", "26"):
                assert part in payments_section, (
                    f"A3: date component {part!r} missing from the fetched "
                    f"document's payments section: {doc!r}"
                )
            # A3b: booked as a bank transfer (payment type 4) - the only type
            # Morning stores bank details on.
            assert "העברה בנקאית" in doc, (
                f"A3b: a bank deposit must be booked as העברה בנקאית (payment type 4), "
                f"which is the only type Morning stores bank details on: {doc!r}"
            )
        finally:
            self._clear_chat_test_data(denidin_app, chat_id)

    # NOTE (2026-08-10): the deposit-matching-an-existing-305 scenario (formerly
    # A1-T2) has been MOVED to
    # tests/expensive/test_group_b_reference_approval_e2e.py, since investigating
    # its failure showed it depends on bugfix-038's fix (Group B approval
    # reference data), not this bugfix's approved scope. See
    # specs/bugfixes/bugfix-038-group-b-approval-missing-reference-data.md.

    @pytest.mark.sanity
    def test_given_real_six_component_agreement_image_mor_ben_shaya_then_all_components_correctly_persisted(
        self, denidin_app, http_server
    ):
        """Given a real fee-proposal document image (Agreement-mor.jpg: a letter
        dated 3.12.24 between client מור בן שעיה and עו"ד אילה הוניגמן, photographed
        at an angle with real image quality issues - not a clean screenshot), When
        sent as a WhatsApp image, Then it's captured as SIX separate components,
        matching the document's real structure - ground truth read directly from
        the image (2026-07-30), independent of and deliberately NOT informed by the
        constitution wording added for the (different) עידן שבתאי document, to
        verify the multi-stage/conditional splitting rule genuinely generalizes
        rather than being overfit to one specific document's numbers:

        1. ייעוץ ופנייה במכתב ראשוני - 2,000 ₪ לפני מע"מ.
        2. ניהול מו"מ עד גיבוש מתווה מוסכם, במידה ולא מגיעים למתווה מוסכם - 4,000 ₪
           לפני מע"מ.
        3. ניהול מו"מ עד גיבוש מתווה מוסכם, במידה ומגיעים למתווה מוסכם - 8,000 ₪
           לפני מע"מ.
        4. הכנת והגשת כתב תביעה + ייצוג בשלבים מקדמיים (עד הוכחות) - 10,000 ₪ לא
           כולל מע"מ.
        5. הוכחות וסיכומים - 8,000 ₪ לא כולל מע"מ.
        6. הצלחה בתביעה - 10% מהסכום שנפסק לטובת התובע (percent-based, no fixed
           amount).

        Note components 3 and 5 both state 8,000 ₪ - a real duplicate amount, not a
        test-writing mistake; the assertion below checks the full multiset, not a
        deduplicated set, specifically to catch a component silently dropped for
        "looking like" a duplicate of another."""
        from denidin import handle_image_message

        chat_id = self._fresh_chat_id("image_agreement_mor")
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1770001500,
            'idMessage': 'LEDGER_E2E_IMAGE_AGREEMENT_MOR_001',
            'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
            'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {
                    'downloadUrl': f'{http_server}/Agreement-mor.jpg',
                    'fileName': 'Agreement-mor.jpg',
                    'mimeType': 'image/jpeg',
                    'caption': '',
                    'jpegThumbnail': '',
                    'isForwarded': False,
                    'forwardingScore': 0,
                }
            }
        })

        logger.info("GIVEN a real 6-component fee-proposal document image (מור בן שעיה / עו\"ד אילה הוניגמן)")
        handle_image_message(notification)
        logger.info("WHEN DeniDin processes it via the image pipeline")

        response = get_response(notification)
        assert_response_exists(response)

        events = self._assert_ledger_events_persisted(
            denidin_app, chat_id, expected_count=6, expected_event_timestamp=1770001500
        )
        logger.info(f"THEN captured {len(events)} events (persisted): {events}")

        for e in events:
            assert e["source_type"] == "הסכם"
            assert e["event_id"].startswith("A"), f"malformed event_id: {e['event_id']!r}"
            assert "מור" in (e.get("client_name") or "") or "שעיה" in (e.get("client_name") or "")
            self._assert_message_links_back_to_event(denidin_app, chat_id, e)

        fixed_amounts = sorted(e.get("amount") for e in events if e.get("amount") is not None)
        assert fixed_amounts == [2000, 4000, 8000, 8000, 10000], (
            f"Expected the 5 real fixed-fee amounts (2,000 / 4,000 / 8,000 twice / "
            f"10,000 - note the genuine duplicate 8,000), got {fixed_amounts} - if "
            f"this fails, the model did not split the document per component despite "
            f"the constitution's multi-stage/conditional agreement rule, or dropped "
            f"one of the two genuinely-distinct 8,000 ₪ components as a false duplicate"
        )

        percent_events = [e for e in events if e.get("percent")]
        assert len(percent_events) == 1, (
            f"Expected exactly 1 percent-based component (the 10% success fee), "
            f"got {len(percent_events)}: {percent_events}"
        )
        assert percent_events[0].get("amount") is None, (
            "the percent-based success-fee component should have no fixed amount"
        )

