"""
Integration test: Feature 084's fast-path reaction hook, exercised through the real
`dispatch_notification()` webhook entry point (not a direct method call into an
internal component - CONSTITUTION §V).

`send_reaction` is stubbed only at the Green API boundary (permitted - it's the one
genuinely external, third-party call this feature makes); everything else in the
dispatch path (dedup check, HANDLER_REGISTRY lookup, the real handler function) runs
for real, confirming the hook's placement doesn't alter existing dispatch behavior.
"""
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from whatsapp_chatbot_python import Notification

from src.models.config import AppConfiguration


@pytest.mark.integration
class TestReactionDispatchRouting:
    @pytest.fixture
    def config(self):
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
                'user_roles': config.user_roles,
            }
            denidin_module.denidin_app = denidin_module.initialize_app(config_dict)

        # A real live Green API bot is never constructed in tests (research.md R3) -
        # the fast-path hook needs SOME bot object to pass to send_reaction, so this
        # stands in for it, exactly the same role `denidin_app.green_api_bot` plays
        # in production once __main__ sets it.
        denidin_module.denidin_app.green_api_bot = Mock()

        return config

    def _notification(self, event_dict):
        notification = Notification.__new__(Notification)
        notification.event = event_dict
        notification._test_sent_messages = []
        notification.answer = lambda message: notification._test_sent_messages.append(message)
        return notification

    def test_actionable_document_message_triggers_a_reaction_call(self, config):
        import denidin as denidin_module

        notification = self._notification({
            'typeWebhook': 'incomingMessageReceived',
            'idMessage': 'wamid.doc1',
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User',
            },
            'messageData': {
                'typeMessage': 'documentMessage',
                'fileMessageData': {
                    'downloadUrl': 'https://example.com/agreement.pdf',
                    'fileName': 'agreement.pdf',
                    'mimeType': 'application/pdf',
                },
            },
        })

        with patch("denidin.send_reaction") as mock_send_reaction:
            denidin_module.dispatch_notification("documentMessage", notification)

        mock_send_reaction.assert_called_once()
        call_args = mock_send_reaction.call_args[0]
        assert call_args[1] == '972522968679@c.us'
        assert call_args[2] == 'wamid.doc1'
        assert call_args[3] in denidin_module._FAST_PATH_MEDIA_REACTIONS

    def test_ambient_group_message_produces_zero_reaction_calls(self, config):
        """REQ-084-005/SC-003: ambient group chatter not matching either
        classification rule must produce literally zero reaction calls."""
        import denidin as denidin_module

        notification = self._notification({
            'typeWebhook': 'incomingMessageReceived',
            'idMessage': 'wamid.group1',
            'senderData': {
                'chatId': '120363000000000000@g.us',
                'sender': '972500000001@c.us',
                'senderName': 'Alice',
                'chatName': 'Lunch planning',
            },
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': 'haha nice, see you at noon then'},
            },
        })

        with patch("denidin.send_reaction") as mock_send_reaction:
            denidin_module.dispatch_notification("textMessage", notification)

        mock_send_reaction.assert_not_called()

    def test_ambient_1on1_ok_produces_zero_reaction_calls(self, config):
        import denidin as denidin_module

        notification = self._notification({
            'typeWebhook': 'incomingMessageReceived',
            'idMessage': 'wamid.ok1',
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User',
            },
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': 'ok thanks'},
            },
        })

        with patch("denidin.send_reaction") as mock_send_reaction:
            denidin_module.dispatch_notification("textMessage", notification)

        mock_send_reaction.assert_not_called()

    def test_action_command_text_message_triggers_a_reaction_call(self, config):
        import denidin as denidin_module

        notification = self._notification({
            'typeWebhook': 'incomingMessageReceived',
            'idMessage': 'wamid.cmd1',
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User',
            },
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': 'צור חשבונית ל-2000 שח למשה'},
            },
        })

        with patch("denidin.send_reaction") as mock_send_reaction:
            denidin_module.dispatch_notification("textMessage", notification)

        mock_send_reaction.assert_called_once()
        call_args = mock_send_reaction.call_args[0]
        assert call_args[2] == 'wamid.cmd1'
        assert call_args[3] in denidin_module._FAST_PATH_ACTION_REACTIONS

    def test_image_message_still_reaches_its_real_handler_alongside_the_fast_path(self, config):
        """The fast-path hook is a side-effecting pre-step - it must never replace or
        skip the real handler's own dispatch. Reuses the same real imageMessage
        notification shape test_media_webhook_routing.py's own passing test already
        exercises, confirming this feature's hook placement doesn't regress it."""
        import denidin as denidin_module

        notification = self._notification({
            'typeWebhook': 'incomingMessageReceived',
            'idMessage': 'wamid.img1',
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User',
            },
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {
                    'downloadUrl': 'https://example.com/media.jpg',
                    'fileName': 'test.jpg',
                    'mimeType': 'image/jpeg',
                    'caption': '',
                },
            },
        })

        with patch("denidin.send_reaction"):
            denidin_module.dispatch_notification("imageMessage", notification)

        # The real handle_image_message ran and sent SOME response (not silently
        # skipped in favor of the fast-path reaction).
        assert notification._test_sent_messages
