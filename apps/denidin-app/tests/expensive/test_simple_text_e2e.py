"""
End-to-End Integration Test: Simple Text Message Processing

Tests simple Hebrew text message handling:
1. User sends simple text message (no files)
2. Bot processes through AI
3. Bot responds with understanding in Hebrew

NO MOCKING - Tests exactly what happens in production.

Run with: pytest tests/expensive/test_simple_text_e2e.py -m expensive -v
"""

import pytest
import logging
from pathlib import Path

from src.models.config import AppConfiguration
from .e2e_helpers import (
    create_real_notification,
    get_response,
    assert_response_exists,
    assert_hebrew_only,
)

# Configure logging for tests
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@pytest.mark.expensive
class TestSimpleTextE2E:
    """
    End-to-end tests for simple text message handling.
    
    These tests use:
    - Real webhook notification structure
    - Real AI API calls
    - Real notification.answer() (tracked, not called to Green API)
    """
    
    @pytest.fixture
    def config(self):
        """Load production configuration."""
        config_path = Path(__file__).parent.parent.parent / "config" / "config.json"
        
        if not config_path.exists():
            pytest.skip("config.json not found")
        
        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        # Use production data_root to access the real constitution file
        config.data_root = str(Path(__file__).parent.parent.parent / "data")
        
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
            denidin.denidin_app = denidin.initialize_app(config_dict)
        
        return denidin.denidin_app
    
    @pytest.mark.expensive
    def test_e2e_simple_text_message_hebrew(self, denidin_app):
        """
        **E2E TEST**: Simple Hebrew text message - AI understanding and Hebrew response.
        
        Flow:
        1. User sends simple text message in Hebrew: "יוסי 7500 שקל"
        2. Bot processes message through AI (REAL API CALL)
        3. Bot responds with what it understood, IN HEBREW
        """
        from denidin import handle_text_message
        
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': 1706601234,
            'idMessage': 'E2E_TEST_TEXT_HEBREW_001',
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
                'typeMessage': 'textMessage',
                'textMessageData': {
                    'body': 'יוסי 7500 שקל'  # Simple Hebrew message
                }
            }
        })
        
        logger.info("\n" + "="*80)
        logger.info("🔥 E2E TEST: Simple Hebrew text message")
        logger.info("   User message: יוסי 7500 שקל")
        logger.info("="*80)
        
        handle_text_message(notification)
        response = get_response(notification)
        
        logger.info(f"Response length: {len(response)} chars")
        logger.info(f"FULL RESPONSE:\n{response}")
        
        # Validate response
        assert_response_exists(response)
        hebrew_ratio = assert_hebrew_only(response)
        
        logger.info(f"✅ SUCCESS - Hebrew ratio: {hebrew_ratio:.1%}")
