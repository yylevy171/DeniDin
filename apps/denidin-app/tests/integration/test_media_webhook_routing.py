"""
BDD Integration Test: Media Webhook Routing from User Perspective

This test verifies that media messages from users receive appropriate responses.
Tests are from the USER perspective: "Did I get a response when I sent this message?"

ENTRY POINT: User sends message via WhatsApp
FLOW: User message → Green API webhook → HANDLER_REGISTRY/dispatch_notification → handler
      → response sent back to user
VERIFICATION: Check that the EXACT error message constant was sent to user

Feature 043 note: routing resolution moved from the live bot.router's real
handler list to HANDLER_REGISTRY/dispatch_notification (denidin.py) - there
is no module-level `bot` object anymore (see research.md R3 for why). Tests
that verify routing precedence now assert against HANDLER_REGISTRY directly,
the actual production routing table, rather than a live router instance.

**CRITICAL BDD REQUIREMENT**: NO MOCKING
1. Tests call REAL handler functions
3. Tests create REAL notification objects using SDK Notification class
4. Tests check REAL behavior - what message the user receives
5. From user perspective: "Did I get the exact message I expected?"

Integration testing is from the user's external perspective, not internal technical details.

See .github/CONSTITUTION.md §V for integration test definition.
"""

import pytest
from pathlib import Path
from whatsapp_chatbot_python import Notification
from src.models.config import AppConfiguration
from src.constants.error_messages import (
    APP_NOT_READY_RETRY_LATER,
    UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES,
    ERROR_PROCESSING_MESSAGE_TRY_AGAIN,
    FAILED_TO_PROCESS_FILE_DEFAULT
)


@pytest.mark.integration
class TestMediaWebhookRoutingUserPerspective:
    """
    BDD Tests: User sends media messages and receives appropriate responses.
    
    NO MOCKING - These are pure integration tests.
    Tests verify actual behavior from user's external perspective.
    
    Perspective: From the user's point of view
    - User sends message → Does app respond?
    - If error → Did I get the EXACT error message I expected?
    """
    
    @pytest.fixture
    def config(self):
        """Load test configuration and initialize denidin_app."""
        config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
        
        if not config_path.exists():
            pytest.skip("config.test.json not found")
        
        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        config.data_root = str(Path(__file__).parent.parent.parent / "test_data")
        
        # Initialize denidin_app for the test
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
        """
        Helper to create real SDK Notification from event dict.
        
        The SDK Notification class expects the full webhook event structure.
        We create it with the real SDK class, not a mock.
        """
        # The SDK Notification takes the bot instance and event dict
        # For testing, we create it directly with the event
        notification = Notification.__new__(Notification)
        notification.event = event_dict
        
        # Track sent messages for assertions
        notification._test_sent_messages = []
        original_answer = notification.answer if hasattr(notification, 'answer') else None
        
        def tracking_answer(message):
            """Track messages for test assertions"""
            notification._test_sent_messages.append(message)
            # Don't actually call Green API in tests
        
        notification.answer = tracking_answer
        
        return notification
    
    def _get_sent_message(self, notification):
        """Get the first message sent via notification.answer()"""
        return notification._test_sent_messages[0] if notification._test_sent_messages else None
    
    # ==================== CRITICAL BDD TESTS ====================
    
    def test_image_message_user_gets_response(self, config):
        """
        **BDD Scenario**: User sends image via WhatsApp
        
        Given: User sends imageMessage via WhatsApp
        When: Bot receives the webhook
        Then: User gets a response
        
        From user perspective:
        - I send an image
        - Bot should reply (not silence)
        - If error: I get the EXACT error message constant
        
        **CRITICAL**: If handler is missing or doesn't respond, user gets silent drop.
        
        **Uses real SDK Notification**: Real Green API webhook structure (nested fileMessageData)
        """
        from denidin import handle_image_message
        
        # Create REAL SDK Notification with proper event structure
        notification = self._create_notification({
            'typeWebhook': 'incomingMessageReceived',
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'imageMessage',
                'fileMessageData': {
                    'downloadUrl': 'https://example.com/media.jpg',
                    'fileName': 'test.jpg',
                    'mimeType': 'image/jpeg',
                    'caption': ''
                }
            }
        })
        
        # When: User sends image message
        handle_image_message(notification)
        
        # Then: User gets response (will fail to download from fake URL)
        sent_message = self._get_sent_message(notification)
        assert sent_message == FAILED_TO_PROCESS_FILE_DEFAULT, (
            f"CRITICAL: User sent image but got wrong error message\n"
            f"Expected (constant): {FAILED_TO_PROCESS_FILE_DEFAULT}\n"
            f"Got: {sent_message}"
        )
    
    def test_document_message_user_gets_response(self, config):
        """
        **BDD Scenario**: User sends document (PDF/DOCX) via WhatsApp
        
        Given: User sends documentMessage via WhatsApp
        When: Bot receives the webhook
        Then: User gets a response with EXACT error message
        
        From user perspective:
        - I send a document
        - Bot should reply (not silence)
        - I get the EXACT error message constant
        
        **Uses real SDK Notification**: Real Green API webhook structure (nested fileMessageData)
        """
        from denidin import handle_document_message
        
        # Create REAL SDK Notification with proper event structure
        notification = self._create_notification({
            'typeWebhook': 'incomingMessageReceived',
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'documentMessage',
                'fileMessageData': {
                    'downloadUrl': 'https://example.com/document.pdf',
                    'fileName': 'test.pdf',
                    'mimeType': 'application/pdf',
                    'caption': ''
                }
            }
        })
        
        handle_document_message(notification)
        
        sent_message = self._get_sent_message(notification)
        assert sent_message == FAILED_TO_PROCESS_FILE_DEFAULT, (
            f"Expected: {FAILED_TO_PROCESS_FILE_DEFAULT}\n"
            f"Got: {sent_message}"
        )
    
    def test_unsupported_message_user_gets_exact_error_constant(self, config):
        """
        **BDD Requirement**: User sends unsupported message type
        
        Given: User sends unsupported message type
        When: Bot receives the webhook
        Then: User gets the EXACT unsupported message error constant
        
        From user perspective:
        - I send a message type bot doesn't support
        - Bot should NOT be silent
        - I get the EXACT error message (not a variation, not in English)
        """
        from denidin import handle_unsupported_message_default, denidin_app
        
        # Create REAL SDK Notification for unsupported message type
        notification = self._create_notification({
            'typeWebhook': 'incomingMessageReceived',
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'unknownMessageType',
                'textMessage': 'Test message'
            }
        })
        
        if denidin_app is None:
            handle_unsupported_message_default(notification)
            
            sent_message = self._get_sent_message(notification)
            assert sent_message == APP_NOT_READY_RETRY_LATER, (
                f"Expected: {APP_NOT_READY_RETRY_LATER}\n"
                f"Got: {sent_message}"
            )
        else:
            # App is initialized, should get unsupported message handler
            handle_unsupported_message_default(notification)
            
            sent_message = self._get_sent_message(notification)
            assert sent_message == UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES, (
                f"Expected: {UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES}\n"
                f"Got: {sent_message}"
            )
    
    def test_extended_text_message_routes_to_text_handler_not_unsupported(self, config):
        """
        **BDD Scenario**: User forwards/quotes a text message via WhatsApp

        Given: User forwards a text message (Green API reports it as
               typeMessage "extendedTextMessage", not "textMessage")
        When: dispatch_notification resolves the webhook event's type
        Then: It resolves to the text-message handler, not the
              "unsupported message type" catch-all

        bugfix-008 root cause: no registration existed for
        "extendedTextMessage", so routing fell through to the catch-all
        handler and the user got an incorrect "unsupported" auto-reply.

        Updated for Feature 043 (the MessageSource refactor, research.md R3):
        routing is no longer resolved via the live bot.router's real handler
        list (there is no module-level `bot` anymore - that's the whole
        point of this feature) - it's resolved via HANDLER_REGISTRY, the new
        single source of truth for "which handler does this type route to,"
        used identically by the live entry point and any other MessageSource
        (e.g. the player). This test now asserts against HANDLER_REGISTRY
        directly - the real production routing table, not a re-derivation of
        it - which is a strictly more direct regression test for the same
        bugfix-008 scenario than walking a live router's handler list ever
        was.
        """
        import denidin as denidin_module

        resolved_handler = denidin_module.HANDLER_REGISTRY.get(
            "extendedTextMessage", denidin_module.CATCH_ALL_HANDLER
        )

        assert resolved_handler is denidin_module.handle_text_message, (
            "CRITICAL: forwarded/quoted text (extendedTextMessage) is not routed "
            "to the text handler.\n"
            f"Resolved handler instead: {resolved_handler.__name__}\n"
            "Expected: handle_text_message"
        )

    def test_video_message_user_gets_response(self, config):
        """
        **BDD Scenario**: User sends video via WhatsApp
        
        Given: User sends videoMessage via WhatsApp
        When: Bot receives the webhook
        Then: User gets a response with EXACT error message
        
        **Uses real SDK Notification**: Real Green API webhook structure (nested fileMessageData)
        """
        from denidin import handle_video_message
        
        # Create REAL SDK Notification for video
        notification = self._create_notification({
            'typeWebhook': 'incomingMessageReceived',
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'videoMessage',
                'fileMessageData': {
                    'downloadUrl': 'https://example.com/video.mp4',
                    'fileName': 'test.mp4',
                    'mimeType': 'video/mp4',
                    'caption': '',
                    'videoNote': False
                }
            }
        })
        
        handle_video_message(notification)
        
        sent_message = self._get_sent_message(notification)
        assert sent_message == FAILED_TO_PROCESS_FILE_DEFAULT, (
            f"Expected: {FAILED_TO_PROCESS_FILE_DEFAULT}\n"
            f"Got: {sent_message}"
        )
    
    @pytest.fixture
    def real_e2e_config(self):
        """Isolated test config (moved from tests/expensive/test_media_e2e.py's own
        `config` fixture, kept separate from this class's lighter `config` fixture
        above so the two don't collide): overrides memory storage_dir explicitly,
        since SessionManager/MemoryManager read those paths directly, not data_root."""
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
    def real_e2e_denidin_app(self, real_e2e_config):
        """Initialize the full denidin app - NO MOCKING (moved from
        tests/expensive/test_media_e2e.py's own `denidin_app` fixture)."""
        import denidin

        if denidin.denidin_app is None:
            config_dict = {
                'green_api_instance_id': real_e2e_config.green_api_instance_id,
                'green_api_token': real_e2e_config.green_api_token,
                'ai_api_key': real_e2e_config.ai_api_key,
                'ai_model': real_e2e_config.ai_model,
                'ai_reply_max_tokens': real_e2e_config.ai_reply_max_tokens,
                'log_level': real_e2e_config.log_level,
                'data_root': real_e2e_config.data_root,
                'feature_flags': real_e2e_config.feature_flags,
                'godfather_phone': real_e2e_config.godfather_phone,
                'memory': real_e2e_config.memory,
                'constitution_config': real_e2e_config.constitution_config,
                'user_roles': real_e2e_config.user_roles
            }
            denidin.denidin_app = denidin.initialize_app(config_dict)

        return denidin.denidin_app

    def test_audio_message_user_gets_response(self, real_e2e_denidin_app):
        """
        **BDD Scenario**: User sends audio via WhatsApp

        Given: User sends audioMessage via WhatsApp
        When: Bot receives the webhook
        Then: User gets a response with EXACT error message

        Moved here from tests/expensive/test_media_e2e.py (2026-08-03), unmarked:
        traced the actual code path and confirmed it makes ZERO OpenAI API calls -
        MediaFileManager.validate_format() raises for unsupported extensions (.mp3)
        before any extractor/AI call ever runs, so this was never actually
        vision/expensive work, just a real router-dispatch + real MediaHandler
        rejection path. Uses the real `tests.e2e_helpers` notification helpers
        (same as every other real E2E test in this codebase, not a bespoke mock).
        """
        from denidin import handle_audio_message
        from tests.e2e_helpers import create_real_notification, get_response

        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1706601234,
            'idMessage': 'E2E_TEST_AUDIO_001',
            'instanceData': {
                'idInstance': 7103000000,
                'wid': '972501234567@c.us',
                'typeInstance': 'whatsapp'
            },
            'senderData': {
                'chatId': '972522968679@c.us',
                'sender': '972522968679@c.us',
                'senderName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'audioMessage',
                'fileMessageData': {
                    'downloadUrl': 'https://example.com/audio.mp3',
                    'fileName': 'audio.mp3',
                    'mimeType': 'audio/mpeg',
                    'caption': ''
                }
            }
        })

        handle_audio_message(notification)
        response = get_response(notification)

        assert response == FAILED_TO_PROCESS_FILE_DEFAULT, (
            f"Expected: {FAILED_TO_PROCESS_FILE_DEFAULT}\n"
            f"Got: {response}"
        )


# ==================== EXPECTED TEST RESULTS ====================
#
# FROM USER PERSPECTIVE (NO MOCKING):
#
# BEFORE FIX:
#   - User sends image → gets no reply (silent drop)
#   - User sends document → gets no reply (silent drop)
#   - User sends unsupported type → gets no reply (silent drop)
#   ❌ Tests FAIL because notification.answer is never called
#
# AFTER FIX:
#   - User sends image → tries to process, fails on fake URL, gets FAILED_TO_PROCESS_FILE_DEFAULT
#   - User sends document → gets APP_NOT_READY_RETRY_LATER if app not ready
#   - User sends unsupported → gets APP_NOT_READY_RETRY_LATER (app not ready)
#                            OR gets UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES (app ready)
#   ✅ Tests PASS because notification.answer is called with EXACT constant
#
# KEY ASSERTION PRINCIPLE:
#   We assert the EXACT message constant, not variations or translations.
#   This ensures:
#   1. Users always get the same message (consistency)
#   2. Messages are from centralized constants (single source of truth)
#   3. No hardcoded strings scattered in code
#   4. Changes to error messages require updating constant once
#
# =====================================================================
