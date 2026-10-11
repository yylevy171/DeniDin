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
from unittest.mock import Mock

from src.handlers.whatsapp_handler import WhatsAppHandler
from tests.denidin_test_support import make_denidin


def _normalize_self_mentions(text: str, own_whatsapp_number: str) -> str:
    """REQ-063-08: the rewrite lives on WhatsAppHandler, which owns DeniDin's number."""
    handler = WhatsAppHandler(make_denidin())
    handler.own_whatsapp_number = own_whatsapp_number
    return handler.normalize_self_mentions(text)


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


class TestProcessNotificationAppliesSelfMentionNormalization:
    """Confirms WhatsAppHandler.process_notification actually wires own_whatsapp_number
    into the normalization (not just the method in isolation) - own_whatsapp_number is
    set by denidin.py's initialize_app (REQ-063-08: the rewrite moved here from
    AIManager.create_request, so the stored message and the model see the same text)."""

    def _notification(self, text: str) -> Mock:
        notification = Mock()
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'messageData': {'typeMessage': 'textMessage',
                            'textMessageData': {'textMessage': text}},
            'senderData': {'chatId': '120363410226011645@g.us',
                           'sender': '972522968679@c.us', 'senderName': 'Test Sender'},
            'timestamp': 1234567890,
        }
        return notification

    def test_own_number_unset_leaves_text_unchanged(self):
        handler = WhatsAppHandler(make_denidin())
        message = handler.process_notification(self._notification("@972559723730 מי אתה?"))
        assert message.text_content == "@972559723730 מי אתה?"

    def test_own_number_set_normalizes_text(self):
        handler = WhatsAppHandler(make_denidin())
        handler.own_whatsapp_number = "972559723730"
        message = handler.process_notification(self._notification("@972559723730 מי אתה?"))
        assert message.text_content == "@DeniDin מי אתה?"
