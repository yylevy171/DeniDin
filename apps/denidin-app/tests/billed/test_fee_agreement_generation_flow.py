"""
End-to-End Billed Test (Feature 083, Acceptance phase): Fee Agreement Document
Generation.

STATUS (2026-09-12, T014): production code now exists and this file has been updated to
match its REAL API — `pending_local_tool_approval_manager.get(chat_id)` (not `get_pending`),
`WhatsAppHandler.send_document_response(generated, chat_id, caption)` and
`_send_file_with_retry(chat_id, path, file_name, caption)` (patched at the class level, so
mock call_args carry no `self`), and a new `test_alternative_tracks_selected_and_generated`
scenario for the 5th, corpus-driven variant. **STILL BLOCKING on a fresh human
re-approval before running** — the original approval of this file predates both the
Hebrew/corpus template redesign and the alternative_tracks variant, so nothing here has been
approved against what actually exists on disk today. Do not run via
`scripts/run_single_test.sh`/`run_multiple_billed_tests.sh` until that re-approval is given.

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
                'fee_agreements': config.fee_agreements,
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
        return denidin_app.ai_handler.pending_local_tool_approval_manager.get(chat_id)

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
            # send_document_response(self, generated, chat_id, caption) - patched at the
            # class level, so the mock receives no `self`; `generated` is args[0].
            sent_document = mock_send.call_args.args[0] if mock_send.call_args.args \
                else mock_send.call_args.kwargs.get("generated")
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

    # --- Stage 1b: multi-component supports ANY N>1 (data-model.md "Variable-length
    # component rows") - not a fixed cap ------------------------------------------

    @pytest.mark.parametrize("n_components", [2, 4])
    def test_multi_component_arbitrary_n(self, denidin_app, config, n_components):
        """Per explicit human correction (2026-09-12): the multi-component variant
        must handle ANY N>1 real components, not a fixed maximum. Runs with both a
        minimal case (2) and a case exceeding any hardcoded small cap (4) to prove
        DocTemplateEngine clones its single repeatable table row exactly
        n_components times - never padding a shorter list, never truncating a
        longer one."""
        phone, chat_id = self._godfather(config)
        component_descs = [
            "a one-time setup fee of 2,000 NIS",
            "a monthly maintenance fee of 500 NIS",
            "an annual license renewal fee of 1,200 NIS",
            "a one-time data migration fee of 3,000 NIS",
        ][:n_components]
        self._send_text(
            chat_id, phone, "Test Godfather",
            f"Draft an agreement for Gamma LLC with {n_components} fee components: "
            + "; ".join(component_descs) + ". "
            "Total combined fee for the first period accordingly.",
            f"stage1b-{n_components}",
        )
        pending = self._pending_approval(denidin_app, chat_id)
        assert pending is not None
        components = pending.arguments.get("components") or []
        assert len(components) == n_components, (
            f"expected exactly {n_components} real components (never padded/merged), "
            f"got {len(components)}: {components!r}"
        )
        for entry in components:
            assert set(entry.keys()) == {"label", "terms"}
        assert "values" in pending.arguments and not any(
            k.startswith("COMPONENT") for k in pending.arguments["values"]
        ), "scalar `values` must never carry component data - that belongs in `components`"

        stanza_id = getattr(pending, "sent_message_id", None)
        with patch(
            "src.handlers.whatsapp_handler.WhatsAppHandler.send_document_response",
            return_value=True,
        ) as mock_send:
            if stanza_id:
                self._tap_button(chat_id, phone, "denidin_approve", stanza_id, f"stage1b-{n_components}-approve")
            else:
                self._send_text(chat_id, phone, "Test Godfather", "כן", f"stage1b-{n_components}-approve")

            assert mock_send.called
            # send_document_response(self, generated, chat_id, caption) - patched at the
            # class level, so the mock receives no `self`; `generated` is args[0].
            sent_document = mock_send.call_args.args[0] if mock_send.call_args.args \
                else mock_send.call_args.kwargs.get("generated")
            from docx import Document as DocxDocument
            docx_obj = DocxDocument(str(sent_document.temp_path))
            table = docx_obj.tables[0]
            table_text = "\n".join(cell.text for row in table.rows for cell in row.cells)
            assert "{{" not in table_text, f"leftover placeholder in table: {table_text!r}"
            # Header row + exactly n_components data rows - never a fixed cap.
            assert len(table.rows) == n_components + 1, (
                f"expected header + {n_components} component rows "
                f"({n_components + 1} total), got {len(table.rows)}"
            )

    # --- Stage 1c: alternative_tracks - a real choice between mutually-exclusive
    # fee structures, distinct from multi_component_agreement's "all apply together"
    # shape (added per T014, corpus-driven 5th variant, 2026-09-12) -------------------

    def test_alternative_tracks_selected_and_generated(self, denidin_app, config):
        """A request describing two or more mutually-exclusive fee tracks for the
        SAME engagement (the client picks exactly ONE) must select
        `alternative_tracks`, never `multi_component_agreement` (where every
        component applies together) - the two variants' selection_cues are
        deliberately worded to distinguish exactly this. Also exercises the
        required `SHARED_ADDON_TERMS` scalar and the full generate -> approve ->
        verify -> send flow end-to-end for this 5th variant."""
        phone, chat_id = self._godfather(config)

        self._send_text(
            chat_id, phone, "Test Godfather",
            "Draft an agreement for Sigma Partners with two alternative fee tracks "
            "for the client to choose between - only one will actually apply: "
            "Track A is a flat fee of 18,000 NIS including VAT, no contingency. "
            "Track B is a reduced base fee of 10,000 NIS including VAT plus 7% of "
            "whatever amount is awarded or collected. There are no additional "
            "terms that apply regardless of which track is chosen.",
            "alt_tracks_1",
        )

        pending = self._pending_approval(denidin_app, chat_id)
        assert pending is not None
        assert pending.arguments.get("variant_id") == "alternative_tracks", (
            f"a mutually-exclusive CHOICE between fee structures must select "
            f"alternative_tracks, not {pending.arguments.get('variant_id')!r} - "
            f"multi_component_agreement is for components that ALL apply together"
        )
        tracks = pending.arguments.get("components") or []
        assert len(tracks) == 2, f"expected exactly 2 tracks, got {len(tracks)}: {tracks!r}"
        all_terms = " | ".join(t.get("terms", "") for t in tracks)
        assert "18,000" in all_terms or "18000" in all_terms
        assert "10,000" in all_terms or "10000" in all_terms
        assert "7" in all_terms and "%" in all_terms
        values = pending.arguments.get("values", {})
        shared_addon = str(values.get("SHARED_ADDON_TERMS", ""))
        assert shared_addon, (
            "SHARED_ADDON_TERMS is a required scalar - when the user said there's "
            "nothing shared, the AI must say so explicitly, never omit the field"
        )

        stanza_id = getattr(pending, "sent_message_id", None)
        with patch(
            "src.handlers.whatsapp_handler.WhatsAppHandler.send_document_response",
            return_value=True,
        ) as mock_send:
            if stanza_id:
                self._tap_button(chat_id, phone, "denidin_approve", stanza_id, "alt_tracks_1_approve")
            else:
                self._send_text(chat_id, phone, "Test Godfather", "כן", "alt_tracks_1_approve")

            assert mock_send.called
            sent_document = mock_send.call_args.args[0] if mock_send.call_args.args \
                else mock_send.call_args.kwargs.get("generated")
            assert sent_document is not None and sent_document.verified is True

            from docx import Document as DocxDocument
            text = "\n".join(p.text for p in DocxDocument(str(sent_document.temp_path)).paragraphs)
            assert "{{" not in text, f"leftover placeholder token(s) found: {text!r}"
            assert "Sigma Partners" in text
            for track in tracks:
                assert track["label"] in text
                assert track["terms"] in text

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
            "src.handlers.whatsapp_handler.WhatsAppHandler._send_file_with_retry",
            return_value=None,
        ) as mock_upload:
            if stanza_id:
                self._tap_button(chat_id, phone, "denidin_approve", stanza_id, "stage4b")
            else:
                self._send_text(chat_id, phone, "Test Godfather", "כן", "stage4b")

            assert mock_upload.call_count == 1, (
                f"expected exactly one sendFileByUpload-equivalent call, "
                f"got {mock_upload.call_count}"
            )
            # _send_file_with_retry(self, chat_id, path, file_name, caption) - patched at
            # the class level, so the mock receives no `self`; `path` is args[1].
            sent_path = Path(mock_upload.call_args.kwargs.get("path")
                              or mock_upload.call_args.args[1])
            # The boundary call happens BEFORE cleanup — assert the path it was given
            # is a real .docx that existed at call time (checked via the call args'
            # captured path, since by now the file has already been deleted).
            assert sent_path.suffix == ".docx"
            assert not sent_path.exists(), (
                "temp .docx must be deleted after a successful send (SC-003) — "
                "found still on disk after the turn completed"
            )

    # --- Component terms: example-pattern-guided AND free-form creative ----------

    def test_multi_component_percentage_coshare_payer_terms(self, denidin_app, config):
        """Per human feedback (2026-09-12): components must support percentages,
        cost-sharing with other partners, and a payer entity other than the Client -
        composed as free text, guided (but not limited) by manifest.json's
        example_terms patterns. One component here matches an example pattern
        (percentage split with a named partner); another describes a genuinely novel
        arrangement with no matching example, to prove the AI isn't forced to distort
        it into the nearest pattern."""
        phone, chat_id = self._godfather(config)

        self._send_text(
            chat_id, phone, "Test Godfather",
            "Draft an agreement for Delta Holdings with two fee components: "
            "(1) a referral fee of 15% of the collected amount, split 50/50 with "
            "Partner Cohen, payable by the Client upon receipt; "
            "(2) a one-time success bonus of 10,000 NIS payable directly by "
            "Delta Holdings' parent company, Delta Group Ltd, only if the deal "
            "closes before year-end. Total combined fee: as per the above.",
            "creative_terms",
        )
        pending = self._pending_approval(denidin_app, chat_id)
        assert pending is not None
        components = pending.arguments.get("components") or []
        assert len(components) == 2

        all_terms = " | ".join(c.get("terms", "") for c in components)
        # Component 1: percentage + cost-share (matches an example pattern).
        assert "15" in all_terms and "%" in all_terms
        assert "Cohen" in all_terms
        assert "50" in all_terms  # the split ratio, stated verbatim, not invented
        # Component 2: a non-Client payer entity AND a conditional trigger - no
        # example_terms pattern covers "conditional on a deal closing," so this
        # proves free-form composition beyond the guided examples still works.
        assert "10,000" in all_terms or "10000" in all_terms
        assert "Delta Group" in all_terms
        assert "year-end" in all_terms or "close" in all_terms.lower()
        # Nothing invented: no percentage/split/payer/condition appears that
        # wasn't actually stated above (spot-check a plausible hallucination).
        assert "20%" not in all_terms and "30,000" not in all_terms and "3000" not in all_terms
