"""
Unit tests for bugfix-024: normalizing a native WhatsApp @-mention of DeniDin's own
phone number into the name-shaped "@DeniDin" form the model's existing addressee
judgment already recognizes.

Root cause (see specs/bugfixes/bugfix-024-*.md): a real WhatsApp native @-mention
picker inserts the mentioned contact's raw phone number into message text, never a
display name - confirmed via a real Green API getWaSettings call, NOT assumed from
documentation (CONSTITUTION.md "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS"). These tests
cover the pure normalization function directly - no OpenAI call, no network.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.handlers.ai_handler import AIHandler, _normalize_self_mentions
from src.models.config import AppConfiguration
from src.models.message import WhatsAppMessage


class TestNormalizeSelfMentions:
    def test_self_mention_by_bare_digits_is_rewritten_to_at_denidin(self):
        result = _normalize_self_mentions("@972559723730 מי אתה?", "972559723730")
        assert result == "@DeniDin מי אתה?"

    def test_self_mention_mid_sentence_is_rewritten(self):
        result = _normalize_self_mentions("שלום @972559723730 מה קורה", "972559723730")
        assert result == "שלום @DeniDin מה קורה"

    def test_other_persons_number_is_left_untouched(self):
        text = "@972501234567 מי אתה?"
        result = _normalize_self_mentions(text, "972559723730")
        assert result == text

    def test_no_mention_at_all_is_unchanged(self):
        text = "בוקר טוב, מה שלומך?"
        result = _normalize_self_mentions(text, "972559723730")
        assert result == text

    def test_empty_own_whatsapp_number_is_a_no_op(self):
        """own_whatsapp_number empty means the startup fetch never resolved (or
        hasn't run) - must fail open, never raise, never alter the text."""
        text = "@972559723730 מי אתה?"
        result = _normalize_self_mentions(text, "")
        assert result == text

    def test_manually_typed_at_denidin_name_mention_is_unaffected(self):
        """A manually-typed "@DeniDin" (not via the native picker) was never broken -
        confirms this fix doesn't double-transform or otherwise interfere with the
        pre-existing, already-verified name-shaped mention path (case6 billed test)."""
        text = "אתה יכול לבדוק את זה? @DeniDin"
        result = _normalize_self_mentions(text, "972559723730")
        assert result == text

    def test_multiple_mentions_only_self_mention_is_rewritten(self):
        text = "@972501234567 ו@972559723730 שניכם תעזרו לי"
        result = _normalize_self_mentions(text, "972559723730")
        assert result == "@972501234567 ו@DeniDin שניכם תעזרו לי"


class TestCreateRequestAppliesSelfMentionNormalization:
    """Confirms AIHandler.create_request actually wires own_whatsapp_number into the
    normalization (not just the pure function in isolation) - own_whatsapp_number is
    set by denidin.py's initialize_app, never passed to create_request directly."""

    @pytest.fixture
    def handler(self):
        config = AppConfiguration(
            green_api_instance_id="test",
            green_api_token="test",
            ai_api_key="test-key",
            ai_model="gpt-4o-mini",
            ai_reply_max_tokens=100,
            log_level="INFO",
        )
        handler = AIHandler(MagicMock(), config)
        handler.session_manager.get_conversation_history = MagicMock(return_value=[])
        return handler

    def _message(self, text_content: str) -> WhatsAppMessage:
        return WhatsAppMessage(
            message_id='msg_bugfix024',
            chat_id='120363410226011645@g.us',
            sender_id='972522968679@c.us',
            sender_name='Test Sender',
            text_content=text_content,
            timestamp=1234567890,
            message_type='textMessage',
            is_group=True,
            received_timestamp=datetime.now(timezone.utc),
        )

    def test_own_number_unset_leaves_prompt_unchanged(self, handler):
        request = handler.create_request(self._message("@972559723730 מי אתה?"))
        assert request.user_prompt == "@972559723730 מי אתה?"

    def test_own_number_set_normalizes_prompt(self, handler):
        handler.own_whatsapp_number = "972559723730"
        request = handler.create_request(self._message("@972559723730 מי אתה?"))
        assert request.user_prompt == "@DeniDin מי אתה?"
