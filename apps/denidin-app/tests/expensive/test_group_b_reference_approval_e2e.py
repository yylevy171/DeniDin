"""bugfix-038 — Group B document approvals (create_receipt/create_credit_note/
close_transaction_account) referencing an existing document must show the user
what they're actually approving, and go fetch what's missing rather than
present a blank preview.

Moved here 2026-08-10 from bugfix-028's test_ledger_event_capture_e2e.py, where
this scenario (A1-T2: a deposit matching an existing type-305 invoice) was
originally written and approved. Investigating its failure showed it depends on
infrastructure bugfix-028 never scoped: `create_receipt`'s only reference
argument is `original_invoice_id`, an internal Morning GUID the constitution
forbids showing the user, and none of the three Group B tools carry the
original document's real data (its display number, its own amount, its actual
VAT treatment) anywhere the approval-builder can read it. See
specs/bugfixes/bugfix-038-group-b-approval-missing-reference-data.md for the
full root-cause writeup and the design directed by the user.

Still RED - the fix isn't implemented. Kept here rather than in bugfix-028's
suite so it doesn't block or misrepresent that bugfix's own (separately
complete) test results.

Same fixtures/helpers as test_ledger_event_capture_e2e.py, duplicated rather
than imported across test-class boundaries (matching this app's existing
per-file class-scoped fixture convention, e.g. test_media_e2e.py).

NO MOCKING - real OpenAI API calls, real image pipeline, real Morning sandbox.

Run ONE test at a time, with fresh explicit approval each time:
    pytest tests/expensive/test_group_b_reference_approval_e2e.py::TestGroupBReferenceApprovalE2E::<name> -v -m expensive
"""

import logging
import re
import threading
import uuid
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

import pytest

from src.models.config import AppConfiguration
from tests.e2e_helpers import create_real_notification

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@pytest.mark.expensive
class TestGroupBReferenceApprovalE2E:
    """bugfix-038: a Group B approval (something created AGAINST an existing
    document) must state that document's real, current data - not an internal
    id, not a blank placeholder."""

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

        server = HTTPServer(('127.0.0.1', 8767), Handler)  # distinct port from 8766
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Test HTTP server running at http://127.0.0.1:8767/ serving {fixtures_dir}")
        yield "http://127.0.0.1:8767"
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

        actual_events_dir = Path(denidin.denidin_app.ai_handler.ledger_event_manager.storage_dir).resolve()
        expected_root = Path(config.data_root).resolve()
        assert actual_events_dir.is_relative_to(expected_root), (
            f"LedgerEventManager.storage_dir={actual_events_dir} is NOT under this "
            f"test's isolated data_root={expected_root} - refusing to proceed, this "
            f"would write into production/dev ledger data"
        )
        return denidin.denidin_app

    @staticmethod
    def _godfather_chat_id(config) -> str:
        """bugfix-028: the deposit->document tests need a chat whose role actually
        gets the Morning tools attached (RBAC-gated to godfather/admin), so they
        cannot use a random fresh chat_id."""
        phone = str(config.godfather_phone).lstrip("+")
        return phone if phone.endswith("@c.us") else f"{phone}@c.us"

    # bugfix-028: the payer named on Bank-test-image.jpg. This test resolves the
    # name from the IMAGE's own extracted text, so it has to exist as a real
    # Morning client for the tool call to be able to create anything.
    BANK_IMAGE_PAYER = "עטיה רועי מאיר"

    @staticmethod
    def _ensure_client_exists(chat_id, name, id_prefix):
        """Seed `name` as a real Morning client, but only if it isn't one already.
        See test_ledger_event_capture_e2e.py's identical helper for the full
        rationale (idempotent by design, decided on tool output not model prose)."""
        from tests.billed.denidin_mcp_e2e_helpers import (
            _calls_for,
            _seed_client_via_conversation,
            _send_turn,
        )

        _, ai_response = _send_turn(
            chat_id, f"תן לי את הפרטים של הלקוח {name}", id_prefix=f"{id_prefix}_LOOKUP"
        )
        lookups = _calls_for(ai_response, "get_client_details")
        already_exists = bool(lookups) and "לא נמצא" not in (lookups[0]["output"] or "")
        if already_exists:
            logger.info(f"client {name!r} already exists - not re-seeding")
            return
        _seed_client_via_conversation(chat_id, name, id_prefix=f"{id_prefix}_SEED")

    @staticmethod
    def _clear_chat_test_data(denidin_app, chat_id):
        """Clear this chat's test data before AND after (user requirement,
        bugfix-028, 2026-08-09), so a shared, non-random chat_id can't collide
        across runs. Only ever touches test_data/ - the denidin_app fixture above
        already refuses to run at all if LedgerEventManager.storage_dir is not
        under this test's isolated data_root."""
        import json as _json

        events_dir = denidin_app.ai_handler.ledger_event_manager.storage_dir
        for f in list(events_dir.glob("*.json")):
            try:
                with open(f, encoding='utf-8') as fh:
                    data = _json.load(fh)
            except (OSError, _json.JSONDecodeError):
                continue
            if data.get("whatsapp_chat") == chat_id:
                f.unlink()

        session_manager = denidin_app.ai_handler.session_manager
        if session_manager is not None:
            try:
                session_manager.clear_session(chat_id)
            except AttributeError:
                logger.warning("SessionManager has no clear_session - session data not cleared")

    def test_given_a_deposit_matching_an_existing_tax_invoice_then_a_receipt_closes_it(
        self, denidin_app, http_server, config
    ):
        """bugfix-038 (originally bugfix-028 A1-T2, user's own framing,
        2026-08-09): "Bank image provided with payment details but there is
        already a seeded 305 which matches this payment, so the resulting doc
        should be a 400, not a 320. The user must be alarmed at this and the
        approval must state this clearly."

        Given a real type-305 tax invoice already issued for a client, When a bank
        deposit screenshot for that same payment arrives, Then the document that
        closes it is a **קבלה (400) against that invoice** - never a fresh 320,
        which would double-count the money as a second, unrelated sale.

        RED per bugfix-038: `create_receipt`'s only reference argument is
        `original_invoice_id` (an internal id the constitution forbids showing),
        so today's approval has nothing to render for the invoice reference,
        client, purpose, or VAT. Fixing this needs create_receipt extended with
        the same payment-detail parameters create_combo_document already has
        (bugfix-028 A3/A3b), plus the model resolving and passing the original's
        display data explicitly (bugfix-038's directed design) so
        _build_pending_approval_details can render a real two-part approval.
        """
        from denidin import handle_image_message
        from tests.billed.denidin_mcp_e2e_helpers import (
            _calls_for,
            _send_turn,
            _send_turn_and_approve,
        )

        chat_id = self._godfather_chat_id(config)
        self._clear_chat_test_data(denidin_app, chat_id)

        try:
            client_name = self.BANK_IMAGE_PAYER
            self._ensure_client_exists(chat_id, client_name, id_prefix="B038_A1T2")

            logger.info("GIVEN an existing type-305 tax invoice awaiting payment")
            _, (_, seed_ai) = _send_turn_and_approve(
                chat_id,
                f"תפיק חשבונית מס ל{client_name} על סך 1500 ₪ כולל מע״מ, עבור ייעוץ משפטי",
                id_prefix="B038_A1T2_SEED305",
            )
            seed_calls = _calls_for(seed_ai, "create_invoice")
            assert seed_calls and seed_calls[0]["error"] is None, (
                f"precondition failed - could not seed the type-305: "
                f"{seed_ai.mcp_calls if seed_ai else None!r}"
            )
            seeded_output = seed_calls[0]["output"] or ""
            invoice_number = next(
                (t for t in re.findall(r"\d{3,}", seeded_output) if t != "1500"), None
            )
            assert invoice_number, f"could not read the seeded invoice number from {seeded_output!r}"

            logger.info("WHEN the deposit screenshot for that same payment arrives")
            notification = create_real_notification({
                'typeWebhook': 'incomingMessageReceived',
                'timestamp': 1770001500,
                'idMessage': 'LEDGER_E2E_IMAGE_BANK_MATCHING_305',
                'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us',
                                 'typeInstance': 'whatsapp'},
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
            handle_image_message(notification)

            ask_result, (_, ai_response) = _send_turn_and_approve(
                chat_id,
                "תפיק חשבונית עבור זה",
                id_prefix="B038_A1T2",
            )
            approval_text = ask_result[0] or ""

            assert not _calls_for(ai_response, "create_combo_document"), (
                f"a standalone 320 was issued while a matching 305 was open - "
                f"the same money is now recorded twice and the original stays unpaid. "
                f"Calls: {ai_response.mcp_calls if ai_response else None!r}"
            )
            receipt_calls = _calls_for(ai_response, "create_receipt")
            assert receipt_calls, (
                f"expected a קבלה (400) closing invoice {invoice_number}. "
                f"Calls: {ai_response.mcp_calls if ai_response else None!r}"
            )
            assert receipt_calls[0]["error"] is None, f"creation failed: {receipt_calls[0]!r}"

            # bugfix-038's core assertion: the reference invoice's DISPLAY number
            # must appear - never the internal original_invoice_id.
            assert invoice_number in approval_text, (
                f"the approval never says which invoice this receipt closes "
                f"(expected {invoice_number}). Approval was: {approval_text!r}"
            )

            details, _ = _send_turn(
                chat_id, f"תן לי את הפרטים המלאים של חשבונית {invoice_number}",
                id_prefix="B038_A1T2_VERIFY",
            )
            assert details and "שולם" in details, (
                f"the original invoice must now read as paid: {details!r}"
            )
        finally:
            self._clear_chat_test_data(denidin_app, chat_id)
