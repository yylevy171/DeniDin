"""
End-to-End Billed Test (DRAFT — Feature 083, Acceptance phase): Fee Agreement Document
Generation.

STATUS: DRAFT, FOR HUMAN REVIEW/APPROVAL BEFORE speckit.tasks/implementation PROCEEDS.
Per the user's explicit request (2026-09-12), these tests are dissected from
`user-stories.md`'s 4 UAT stages BEFORE implementation exists, ahead of METHODOLOGY §VI's
normal "write+run TDD tests once, at the end" sequencing for `billed`/`expensive` tests. They
CANNOT be executed yet — `generate_fee_agreement`, `verify_fee_agreement_document`,
`DocTemplateEngine`, and the WhatsApp document-send path do not exist in `src/` yet. This file
exists purely so the human can confirm "yes, this is what Stage 1-4 of user-stories.md should
mean as real test code" before a single line of production code is written.

Tests the real OpenAI function-calling mechanism end-to-end — NOT unit-testable, since what's
under test is whether the real model (a) selects the right template variant from natural
phrasing, (b) refuses to guess missing financial/legal data and asks instead, (c) proposes
collected values for human approval, (d) after approval, generates + self-verifies the document
before ever sending it, and (e) the file that reaches WhatsApp is intact.

Text-only conversational turns are `billed`; nothing here is `expensive` (no vision/image calls).
The actual WhatsApp `sendFileByUpload` network call is stubbed at the send boundary only (Gate
Zero — a real live send is a separate, explicitly human-approved step per research.md #2, not
exercised by an automated test run) — this mirrors `test_reminder_lifecycle_billed.py`'s existing
precedent of stubbing `send_proactive_message` for the same reason. Every other component
(AIHandler, DocTemplateEngine, PendingLocalToolApprovalManager, OpenAI) is real, per
CONSTITUTION §I/§V.
"""

import logging
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from src.models.config import AppConfiguration
from tests.e2e_helpers import sanity_worker_data_root

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

GODFATHER_CHAT_ID_TEMPLATE = "{phone}@c.us"


@pytest.mark.billed
class TestFeeAgreementGenerationFlow:
    """Given/When/Then E2E coverage for the 4 UAT stages in
    specs/repo/features/083-fee-agreement-docs/user-stories.md.
    """

    @pytest.fixture
    def config(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
        if not config_path.exists():
            pytest.skip("config.test.json not found")
        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        test_data_root = sanity_worker_data_root()
        config.data_root = str(test_data_root)
        config.memory['session']['storage_dir'] = str(test_data_root / "sessions")
        config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")
        # Feature 083: feature-flagged, default false — must be explicitly on for these tests.
        config.feature_flags = dict(config.feature_flags or {})
        config.feature_flags['fee_agreement_docs'] = True
        return config

    @pytest.fixture
    def denidin_app(self, config):
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
        return denidin.denidin_app

    # --- Notification/turn helpers (mirrors test_reminder_lifecycle_billed.py) --------

    @staticmethod
    def _create_notification(chat_id, sender, sender_name, text, msg_id):
        from whatsapp_chatbot_python import Notification

        notification = Notification.__new__(Notification)
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'idMessage': msg_id,
            'senderData': {'chatId': chat_id, 'sender': sender, 'senderName': sender_name},
            'messageData': {'typeMessage': 'textMessage', 'textMessageData': {'textMessage': text}},
        }
        notification._test_sent_messages = []
        notification._test_button_sends = []
        notification._test_document_sends = []

        def track_answer(message):
            notification._test_sent_messages.append(message)
            logger.info(f"Would send to user: {message}")

        def track_answer_with_interactive_buttons(body, buttons, header=None, footer=None):
            from types import SimpleNamespace
            id_message = f"TEST_BUTTONS_{msg_id}_{len(notification._test_button_sends)}"
            notification._test_button_sends.append({'body': body, 'buttons': buttons, 'idMessage': id_message})
            notification._test_sent_messages.append(body)
            return SimpleNamespace(code=200, data={'idMessage': id_message}, error=None)

        notification.answer = track_answer
        notification.answer_with_interactive_buttons = track_answer_with_interactive_buttons
        return notification

    def _send_text(self, chat_id, sender, sender_name, text, label):
        from denidin import handle_text_message
        msg_id = f"billed_{label}_{uuid.uuid4().hex[:8]}"
        notification = self._create_notification(chat_id, sender, sender_name, text, msg_id)
        handle_text_message(notification)
        return notification

    def _tap_button(self, chat_id, sender, selected_id, stanza_id, label):
        from denidin import handle_button_tap
        msg_id = f"billed_{label}_{uuid.uuid4().hex[:8]}"
        notification = self._create_notification(chat_id, sender, "Test Godfather", "", msg_id)
        notification.event['messageData'] = {
            'typeMessage': 'interactiveButtonsResponse',
            'interactiveButtonsResponse': {'selectedId': selected_id, 'stanzaId': stanza_id},
        }
        handle_button_tap(notification)
        return notification

    def _godfather(self, config):
        phone = config.godfather_phone
        return phone, GODFATHER_CHAT_ID_TEMPLATE.format(phone=phone)

    @staticmethod
    def _last_message(notification):
        return notification._test_sent_messages[-1] if notification._test_sent_messages else None

    @staticmethod
    def _pending_approval(denidin_app, chat_id):
        return denidin_app.ai_handler.pending_local_tool_approval_manager.get_pending(chat_id)

    # --- Stage 1: Template Selection Accuracy ------------------------------------

    @pytest.mark.parametrize(
        "user_text,expected_variant",
        [
            ("Create a retainer agreement for NewCo Ltd.", "retainer_agreement"),
            ("I need a standard hourly fee agreement for consultation.", "hourly_consultation"),
            ("Draft a fixed-price contract for building a website.", "fixed_price_project"),
            (
                "Draft an agreement for Delta Ltd with a monthly retainer of 3,000 NIS "
                "plus 400 NIS/hour for anything beyond 10 hours a month.",
                "multi_component_agreement",
            ),
        ],
    )
    def test_stage1_template_selection(self, denidin_app, config, user_text, expected_variant):
        """Test 1.1/1.2/1.3/1.4: the AI selects the correct template variant from phrasing
        alone, surfaced via the PendingLocalToolApproval it creates (which must name the
        variant it intends to generate) before any document is produced. Test 1.4 (added
        per human feedback) verifies a request describing MULTIPLE distinct, separately
        priced fee components is recognized as such rather than forced into one of the
        single-fee variants."""
        phone, chat_id = self._godfather(config)
        self._send_text(chat_id, phone, "Test Godfather", user_text, "stage1")

        pending = self._pending_approval(denidin_app, chat_id)
        assert pending is not None, (
            f"expected a pending fee-agreement approval after {user_text!r} "
            f"(the AI should propose a variant + ask for value confirmation, not "
            f"generate silently or refuse)"
        )
        assert pending.tool_name == "generate_fee_agreement"
        assert pending.arguments.get("variant_id") == expected_variant, (
            f"expected variant {expected_variant!r}, got {pending.arguments.get('variant_id')!r}"
        )

    # --- Stage 2: Data Gathering & Clarification (Anti-Hallucination) ------------

    def test_stage2_clarification_then_collection(self, denidin_app, config):
        """Scenario: 'Draft an agreement for Yossi.' with terms missing.
        Turn 1: AI must ask a clarifying question, NOT create a pending approval
        and NOT generate anything (no guessed fee amount/scope).
        Turn 2: user supplies the missing data; AI must now have everything it
        needs and create a pending approval with the REAL supplied values (never
        a default/placeholder value)."""
        phone, chat_id = self._godfather(config)

        turn1 = self._send_text(
            chat_id, phone, "Test Godfather", "Draft an agreement for Yossi.", "stage2a"
        )
        assert self._pending_approval(denidin_app, chat_id) is None, (
            "AI must not create a pending approval (or generate a document) before "
            "fee amount and scope are known — REQ-083-02 anti-hallucination guardrail"
        )
        reply1 = self._last_message(turn1) or ""
        assert reply1, "AI must ask a clarifying question, not stay silent"

        self._send_text(
            chat_id, phone, "Test Godfather",
            "The fee is 5,000 NIS for tax consultation.", "stage2b",
        )
        pending = self._pending_approval(denidin_app, chat_id)
        assert pending is not None, "AI should now propose values for approval"
        values = pending.arguments.get("values", {})
        fee_value = " ".join(str(v) for v in values.values())
        assert "5,000" in fee_value or "5000" in fee_value, (
            f"AI must use the REAL supplied fee (5,000 NIS), not a guessed/default one; "
            f"got values={values!r}"
        )

    # --- Stage 3: AI Self-Verification (QA) --------------------------------------

    def test_stage3_self_verification_gates_release(self, denidin_app, config):
        """Once the human approves the proposed values, the AI must call
        generate_fee_agreement THEN verify_fee_agreement_document, and the
        verification result (no remaining {{PLACEHOLDER}} tokens, every value
        present) must be true BEFORE any send is attempted. Verified by
        inspecting the actual generated temp file's content directly — not by
        trusting the model's own narration alone."""
        phone, chat_id = self._godfather(config)

        self._send_text(
            chat_id, phone, "Test Godfather",
            "Draft a fixed-price contract for building a website for Acme Corp, "
            "fee 20,000 NIS, due by end of next month.",
            "stage3a",
        )
        pending = self._pending_approval(denidin_app, chat_id)
        assert pending is not None
        stanza_id = getattr(pending, "sent_message_id", None)

        with patch(
            "src.handlers.whatsapp_handler.WhatsAppHandler.send_document_response",
            return_value=True,
        ) as mock_send:
            if stanza_id:
                self._tap_button(chat_id, phone, "denidin_approve", stanza_id, "stage3b")
            else:
                self._send_text(chat_id, phone, "Test Godfather", "כן", "stage3b")

            assert mock_send.called, (
                "expected the document-send boundary to be reached after approval "
                "(self-verification must have passed for this to happen at all)"
            )
            sent_document = mock_send.call_args.args[1] if len(mock_send.call_args.args) > 1 \
                else mock_send.call_args.kwargs.get("document")
            assert sent_document is not None and getattr(sent_document, "verified", False) is True, (
                "a document reaching send_document_response() must have verified=True — "
                "code-level guard per contracts/fee-agreement-verification.md, not just a "
                "prompt-level expectation"
            )
            temp_path = Path(sent_document.temp_path)
            assert temp_path.exists(), "temp file must still exist at the moment of send"

            from docx import Document as DocxDocument
            text = "\n".join(p.text for p in DocxDocument(str(temp_path)).paragraphs)
            assert "{{" not in text, f"leftover placeholder token(s) found in generated doc: {text!r}"
            assert "Acme Corp" in text
            assert "20,000" in text or "20000" in text

    # --- Stage 1b: multi-component with fewer than 3 real components (data-model.md
    # "Variable-length component rows") -------------------------------------------

    def test_multi_component_partial_omits_unused_rows(self, denidin_app, config):
        """A request with only 2 real fee components must not invent a filler value
        for the unused 3rd table row - DocTemplateEngine must delete that row
        entirely rather than the AI guessing something to put there (REQ-083-02
        applies to 'nothing here' just as much as to a wrong number)."""
        phone, chat_id = self._godfather(config)

        self._send_text(
            chat_id, phone, "Test Godfather",
            "Draft an agreement for Gamma LLC with two fee components: a one-time "
            "setup fee of 2,000 NIS, and a monthly maintenance fee of 500 NIS. "
            "Total combined fee 2,500 NIS for the first month.",
            "stage1b",
        )
        pending = self._pending_approval(denidin_app, chat_id)
        assert pending is not None
        values = pending.arguments.get("values", {})
        assert not any(k.startswith("COMPONENT_3_") for k in values), (
            f"AI must not invent a 3rd component when only 2 were described; "
            f"got values={values!r}"
        )
        stanza_id = getattr(pending, "sent_message_id", None)

        with patch(
            "src.handlers.whatsapp_handler.WhatsAppHandler.send_document_response",
            return_value=True,
        ) as mock_send:
            if stanza_id:
                self._tap_button(chat_id, phone, "denidin_approve", stanza_id, "stage1b-approve")
            else:
                self._send_text(chat_id, phone, "Test Godfather", "כן", "stage1b-approve")

            assert mock_send.called
            sent_document = mock_send.call_args.args[1] if len(mock_send.call_args.args) > 1 \
                else mock_send.call_args.kwargs.get("document")
            from docx import Document as DocxDocument
            docx_obj = DocxDocument(str(sent_document.temp_path))
            table_text = "\n".join(
                cell.text for table in docx_obj.tables for row in table.rows for cell in row.cells
            )
            assert "{{" not in table_text, f"leftover placeholder in table: {table_text!r}"
            # Exactly 2 data rows (+1 header row) must remain - the unused 3rd row deleted.
            assert len(docx_obj.tables[0].rows) == 3, (
                f"expected header + 2 component rows (3 total), "
                f"got {len(docx_obj.tables[0].rows)}"
            )

    # --- Stage 4: Successful Delivery ---------------------------------------------

    def test_stage4_delivery_and_cleanup(self, denidin_app, config):
        """After 'Release', Green API's sendFileByUpload-backed send path must be
        invoked exactly once with the real generated file, and the temp file must
        be deleted afterward (SC-003 — no leaked files)."""
        phone, chat_id = self._godfather(config)

        self._send_text(
            chat_id, phone, "Test Godfather",
            "I need a standard hourly fee agreement for consultation for Beta Inc, "
            "rate 500 NIS/hour, scope: monthly bookkeeping review, estimated total 6,000 NIS.",
            "stage4a",
        )
        pending = self._pending_approval(denidin_app, chat_id)
        assert pending is not None
        stanza_id = getattr(pending, "sent_message_id", None)

        with patch(
            "src.handlers.whatsapp_handler.WhatsAppHandler._call_send_file_by_upload",
            return_value=True,
        ) as mock_upload:
            if stanza_id:
                self._tap_button(chat_id, phone, "denidin_approve", stanza_id, "stage4b")
            else:
                self._send_text(chat_id, phone, "Test Godfather", "כן", "stage4b")

            assert mock_upload.call_count == 1, (
                f"expected exactly one sendFileByUpload-equivalent call, "
                f"got {mock_upload.call_count}"
            )
            sent_path = Path(mock_upload.call_args.kwargs.get("file")
                              or mock_upload.call_args.args[0])
            # The boundary call happens BEFORE cleanup — assert the path it was given
            # is a real .docx that existed at call time (checked via the call args'
            # captured path, since by now the file has already been deleted).
            assert sent_path.suffix == ".docx"
            assert not sent_path.exists(), (
                "temp .docx must be deleted after a successful send (SC-003) — "
                "found still on disk after the turn completed"
            )
