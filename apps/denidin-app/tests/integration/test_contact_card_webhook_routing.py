"""
BDD Integration Test: Contact Card (vCard) Webhook Routing (Feature 030)

Verifies the two new Green API notification types this feature adds routing for:
- contactMessage (single shared contact) - covered indirectly via unit tests
  (test_message.py) plus the billed E2E tests (tests/billed/test_denidin_vcf_contact_e2e.py),
  since a full round-trip needs a real OpenAI call.
- contactsArrayMessage (multiple contacts shared at once) - this feature declines it outright
  at the router level with NO OpenAI call at all, so it's fully testable here without any
  external service, mirroring test_media_webhook_routing.py's pattern (real Notification, real
  handler function, no mocks - CONSTITUTION SS V).

ENTRY POINT: User shares 2+ contacts via WhatsApp
FLOW: Green API webhook (typeMessage=contactsArrayMessage) -> bot.router ->
      handle_contacts_array_message -> friendly decline reply
VERIFICATION: exact friendly-message constant sent, and denidin_app.ai_handler never invoked.
"""

import pytest
from pathlib import Path
from whatsapp_chatbot_python import Notification
from src.models.config import AppConfiguration
from src.constants.error_messages import CONTACT_CARD_ONE_AT_A_TIME


@pytest.mark.integration
class TestContactsArrayMessageRouting:
    """User shares multiple contacts at once - v1 declines with a friendly message."""

    @pytest.fixture
    def config(self):
        """Load test configuration and initialize denidin_app."""
        config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"

        if not config_path.exists():
            pytest.skip("config.test.json not found")

        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        config.data_root = str(Path(__file__).parent.parent.parent / "test_data")

        import denidin as denidin_module
        if denidin_module.denidin_app is None:
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
                'user_roles': config.user_roles
            }
            denidin_module.denidin_app = denidin_module.initialize_app(config_dict)

        return config

    def _create_notification(self, event_dict):
        """Real SDK Notification, not a mock - tracks sent messages for assertions."""
        notification = Notification.__new__(Notification)
        notification.event = event_dict
        notification._test_sent_messages = []

        def tracking_answer(message):
            notification._test_sent_messages.append(message)

        notification.answer = tracking_answer
        return notification

    def _get_sent_message(self, notification):
        return notification._test_sent_messages[0] if notification._test_sent_messages else None

    def test_contacts_array_message_declines_with_friendly_message(self, config):
        """
        **BDD Scenario**: Godfather shares 2+ contacts at once via WhatsApp.

        Given: contactsArrayMessage webhook (per contracts/contactsArrayMessage.json's
               confirmed shape - messageData.messageData.contacts, doubled nesting)
        When: bot.router dispatches it
        Then: friendly "one at a time" reply is sent, with no AIHandler/OpenAI call at all.
        """
        from denidin import handle_contacts_array_message

        notification = self._create_notification({
            'typeWebhook': 'incomingMessageReceived',
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test Godfather'
            },
            'messageData': {
                'typeMessage': 'contactsArrayMessage',
                'messageData': {
                    'contacts': [
                        {
                            'displayName': 'Contact One',
                            'vcard': 'BEGIN:VCARD\nVERSION:3.0\nFN:Contact One\nEND:VCARD'
                        },
                        {
                            'displayName': 'Contact Two',
                            'vcard': 'BEGIN:VCARD\nVERSION:3.0\nFN:Contact Two\nEND:VCARD'
                        }
                    ],
                    'forwardingScore': 0,
                    'isForwarded': False
                }
            }
        })

        handle_contacts_array_message(notification)

        # No mocking (CONSTITUTION SS V forbids unittest.mock in tests/integration/): the
        # direct-reply router path never constructs a WhatsAppMessage/AIRequest or calls
        # AIHandler at all, so the exact friendly-decline constant below - rather than an
        # AI-generated Hebrew reply, an exception from a placeholder OpenAI key, or the
        # multi-second latency a real API round trip would add - is itself the proof that
        # AIHandler.get_response was never reached.
        sent_message = self._get_sent_message(notification)
        assert sent_message == CONTACT_CARD_ONE_AT_A_TIME, (
            f"Expected friendly one-at-a-time decline (constant): {CONTACT_CARD_ONE_AT_A_TIME}\n"
            f"Got: {sent_message}"
        )
        assert len(notification._test_sent_messages) == 1, (
            "Expected exactly one reply sent (the decline), got: "
            f"{notification._test_sent_messages}"
        )
