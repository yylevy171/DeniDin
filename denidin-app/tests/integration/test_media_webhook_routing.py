"""
BDD Integration Test: Media Webhook Routing from User Perspective

This test verifies that media messages from users receive appropriate responses.
Tests are from the USER perspective: "Did I get a response when I sent this message?"

ENTRY POINT: User sends message via WhatsApp
FLOW: User message → Green API webhook → bot.router → handler → response sent back to user
VERIFICATION: Check that the EXACT error message constant was sent to user

**CRITICAL BDD REQUIREMENT**: NO MOCKING
1. Tests use REAL bot.router instance from denidin.py
2. Tests call REAL handler functions
3. Tests create REAL notification objects (not mocked)
4. Tests check REAL behavior - what message the user receives
5. From user perspective: "Did I get the exact message I expected?"

Integration testing is from the user's external perspective, not internal technical details.

See .github/CONSTITUTION.md §V for integration test definition.
"""

import pytest
from pathlib import Path
from src.models.config import AppConfiguration
from src.models.green_api import GreenApiNotification
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
                'ai_reply_max_tokens': config.ai_reply_max_tokens,
                'temperature': config.temperature,
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
        
        **Uses GreenApiNotification**: Real Green API webhook structure (nested fileMessageData)
        """
        from denidin import handle_image_message
        
        # Create REAL Green API webhook notification (not mocked)
        notification = GreenApiNotification.create_image_message(
            sender="972522968679@c.us",
            download_url="https://example.com/media.jpg",
            file_name="test.jpg",
            mime_type="image/jpeg",
            caption="",
            sender_name="Test User"
        )
        
        # When: User sends image message
        handle_image_message(notification)
        
        # Then: User gets response (will fail to download from fake URL)
        sent_message = notification.get_sent_message()
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
        
        **Uses GreenApiNotification**: Real Green API webhook structure (nested fileMessageData)
        """
        from denidin import handle_document_message
        
        # Create REAL Green API webhook notification (not mocked)
        notification = GreenApiNotification.create_document_message(
            sender="972522968679@c.us",
            download_url="https://example.com/document.pdf",
            file_name="test.pdf",
            mime_type="application/pdf",
            caption="",
            sender_name="Test User"
        )
        
        handle_document_message(notification)
        
        sent_message = notification.get_sent_message()
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
        
        # Create notification for unsupported message type (no fileMessageData)
        notification = GreenApiNotification(
            typeWebhook="incomingMessageReceived",
            timestamp=1588091580,
            idMessage="TEST_MESSAGE_ID",
            senderData={
                "chatId": "972522968679@c.us",
                "sender": "972522968679@c.us",
                "senderName": "Test User"
            },
            messageData={
                "typeMessage": "unknownMessageType",
                "textMessage": "Test message"
            }
        )
        
        if denidin_app is None:
            handle_unsupported_message_default(notification)
            
            sent_message = notification.get_sent_message()
            assert sent_message == APP_NOT_READY_RETRY_LATER, (
                f"Expected: {APP_NOT_READY_RETRY_LATER}\n"
                f"Got: {sent_message}"
            )
        else:
            # App is initialized, should get unsupported message handler
            handle_unsupported_message_default(notification)
            
            sent_message = notification.get_sent_message()
            assert sent_message == UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES, (
                f"Expected: {UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES}\n"
                f"Got: {sent_message}"
            )
    
    def test_video_message_user_gets_response(self, config):
        """
        **BDD Scenario**: User sends video via WhatsApp
        
        Given: User sends videoMessage via WhatsApp
        When: Bot receives the webhook
        Then: User gets a response with EXACT error message
        
        **Uses GreenApiNotification**: Real Green API webhook structure (nested fileMessageData)
        """
        from denidin import handle_video_message
        
        # Create REAL Green API webhook notification for video
        notification = GreenApiNotification(
            typeWebhook="incomingMessageReceived",
            timestamp=1588091580,
            idMessage="TEST_MESSAGE_ID",
            senderData={
                "chatId": "972522968679@c.us",
                "sender": "972522968679@c.us",
                "senderName": "Test User"
            },
            messageData={
                "typeMessage": "videoMessage",
                "fileMessageData": {
                    "downloadUrl": "https://example.com/video.mp4",
                    "fileName": "test.mp4",
                    "mimeType": "video/mp4",
                    "caption": "",
                    "jpegThumbnail": "",
                    "isForwarded": False,
                    "forwardingScore": 0,
                    "videoNote": False
                }
            }
        )
        
        handle_video_message(notification)
        
        sent_message = notification.get_sent_message()
        assert sent_message == FAILED_TO_PROCESS_FILE_DEFAULT, (
            f"Expected: {FAILED_TO_PROCESS_FILE_DEFAULT}\n"
            f"Got: {sent_message}"
        )
    
    def test_audio_message_user_gets_response(self, config):
        """
        **BDD Scenario**: User sends audio via WhatsApp
        
        Given: User sends audioMessage via WhatsApp
        When: Bot receives the webhook
        Then: User gets a response with EXACT error message
        
        **Uses GreenApiNotification**: Real Green API webhook structure (nested fileMessageData)
        """
        from denidin import handle_audio_message
        
        # Create REAL Green API webhook notification for audio
        notification = GreenApiNotification(
            typeWebhook="incomingMessageReceived",
            timestamp=1588091580,
            idMessage="TEST_MESSAGE_ID",
            senderData={
                "chatId": "972522968679@c.us",
                "sender": "972522968679@c.us",
                "senderName": "Test User"
            },
            messageData={
                "typeMessage": "audioMessage",
                "fileMessageData": {
                    "downloadUrl": "https://example.com/audio.mp3",
                    "fileName": "test.mp3",
                    "mimeType": "audio/mpeg",
                    "caption": "",
                    "jpegThumbnail": "",
                    "isForwarded": False,
                    "forwardingScore": 0
                }
            }
        )
        
        handle_audio_message(notification)
        
        sent_message = notification.get_sent_message()
        assert sent_message == FAILED_TO_PROCESS_FILE_DEFAULT, (
            f"Expected: {FAILED_TO_PROCESS_FILE_DEFAULT}\n"
            f"Got: {sent_message}"
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
