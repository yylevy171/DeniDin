"""
Unit tests for message models: WhatsAppMessage, AIRequest, and AIResponse.
Tests message parsing, transformation, and handling.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock
from src.models.message import WhatsAppMessage, AIRequest, AIResponse


class TestWhatsAppMessage:
    """Test suite for WhatsAppMessage model."""

    @pytest.fixture
    def sample_text_notification(self):
        """Create a mock notification object with textMessage type."""
        notification = Mock()
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {
                    'textMessage': 'Hello, how are you?'
                }
            },
            'senderData': {
                'chatId': '1234567890@c.us',
                'sender': '1234567890@c.us',
                'senderName': 'John Doe'
            },
            'timestamp': 1234567890
        }
        return notification

    @pytest.fixture
    def sample_group_notification(self):
        """Create a mock notification for a group message."""
        notification = Mock()
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {
                    'textMessage': 'Hello everyone!'
                }
            },
            'senderData': {
                'chatId': '1234567890-5678901234@g.us',  # group chat ID
                'sender': '1234567890@c.us',
                'senderName': 'Jane Smith'
            },
            'timestamp': 1234567890
        }
        return notification

    def test_from_notification_parses_textmessage_correctly(self, sample_text_notification):
        """Test that from_notification() parses textMessage correctly."""
        message = WhatsAppMessage.from_notification(sample_text_notification)
        
        assert message.text_content == 'Hello, how are you?'
        assert message.message_type == 'textMessage'

    def test_from_notification_extracts_sender_info(self, sample_text_notification):
        """Test that from_notification() extracts sender information."""
        message = WhatsAppMessage.from_notification(sample_text_notification)
        
        assert message.chat_id == '1234567890@c.us'
        assert message.sender_id == '1234567890@c.us'
        assert message.sender_name == 'John Doe'

    def test_from_notification_detects_group_chat(self, sample_group_notification):
        """Test that from_notification() detects group vs 1-on-1 chat."""
        message = WhatsAppMessage.from_notification(sample_group_notification)
        
        assert message.is_group is True
        assert '@g.us' in message.chat_id

    def test_from_notification_detects_private_chat(self, sample_text_notification):
        """Test that from_notification() detects private chat."""
        message = WhatsAppMessage.from_notification(sample_text_notification)
        
        assert message.is_group is False
        assert '@c.us' in message.chat_id

    def test_dataclass_attributes(self, sample_text_notification):
        """Test that all dataclass attributes exist and are populated."""
        message = WhatsAppMessage.from_notification(sample_text_notification)
        
        assert hasattr(message, 'message_id')
        assert hasattr(message, 'chat_id')
        assert hasattr(message, 'text_content')
        assert hasattr(message, 'timestamp')
        assert hasattr(message, 'message_type')
        assert hasattr(message, 'sender_id')
        assert hasattr(message, 'sender_name')
        assert hasattr(message, 'is_group')
        
        # Verify they are not None
        assert message.timestamp is not None
        assert message.message_type == 'textMessage'

    def test_message_id_is_unique_uuid(self, sample_text_notification):
        """Test that from_notification() generates unique message_id (UUID)."""
        import uuid
        
        message1 = WhatsAppMessage.from_notification(sample_text_notification)
        message2 = WhatsAppMessage.from_notification(sample_text_notification)
        
        # Verify both are valid UUIDs
        assert isinstance(message1.message_id, str)
        assert isinstance(message2.message_id, str)
        
        # Verify they can be parsed as UUIDs
        uuid.UUID(message1.message_id)
        uuid.UUID(message2.message_id)
        
        # Verify they are unique
        assert message1.message_id != message2.message_id

    def test_received_timestamp_is_utc(self, sample_text_notification):
        """Test that received_timestamp is set to current UTC time."""
        from datetime import timezone
        
        before = datetime.now(timezone.utc)
        message = WhatsAppMessage.from_notification(sample_text_notification)
        after = datetime.now(timezone.utc)
        
        assert hasattr(message, 'received_timestamp')
        assert isinstance(message.received_timestamp, datetime)
        
        # Timestamp should be between before and after
        assert before <= message.received_timestamp <= after
        
        # Verify it has timezone info (UTC)
        assert message.received_timestamp.tzinfo is not None

    def test_message_tracking_fields_in_logging(self, sample_text_notification):
        """Test that message_id and received_timestamp can be used in log messages."""
        message = WhatsAppMessage.from_notification(sample_text_notification)
        
        # Verify fields exist and can be formatted in log strings
        log_message = f"[msg_id={message.message_id}] [recv_ts={message.received_timestamp}] Processing message"
        
        assert message.message_id in log_message
        assert str(message.received_timestamp) in log_message
        assert "[msg_id=" in log_message
        assert "[recv_ts=" in log_message


class TestAIRequest:
    """Test suite for AIRequest model."""

    @pytest.fixture
    def sample_whatsapp_message(self):
        """Create a sample WhatsAppMessage for testing."""
        return WhatsAppMessage(
            message_id='msg_12345',
            chat_id='1234567890@c.us',
            sender_id='1234567890@c.us',
            sender_name='John Doe',
            text_content='What is the weather today?',
            timestamp=1234567890,
            message_type='textMessage',
            is_group=False
        )

    def test_airequest_creation_with_required_fields(self, sample_whatsapp_message):
        """Test AIRequest creation with all required fields."""
        ai_request = AIRequest(
            user_prompt='What is the weather today?',
            system_message='You are a helpful assistant.',
            max_tokens=1000,
            temperature=0.7,
            model='gpt-4o-mini',
            chat_id='1234567890@c.us',
            message_id='msg_12345'
        )
        
        assert ai_request.request_id is not None  # Auto-generated
        assert ai_request.user_prompt == 'What is the weather today?'
        assert ai_request.system_message == 'You are a helpful assistant.'
        assert ai_request.max_tokens == 1000
        assert ai_request.temperature == 0.7
        assert ai_request.timestamp is not None

    def test_to_openai_payload_returns_correct_format(self):
        """Test that to_openai_payload() returns correct API format."""
        ai_request = AIRequest(
            user_prompt='Hello AI',
            system_message='You are helpful.',
            max_tokens=500,
            temperature=0.5,
            model='gpt-4o-mini',
            chat_id='123@c.us',
            message_id='msg_123'
        )
        
        payload = ai_request.to_openai_payload()
        
        assert 'messages' in payload
        assert 'max_tokens' in payload
        assert 'temperature' in payload
        assert 'model' in payload
        assert payload['max_tokens'] == 500
        assert payload['temperature'] == 0.5
        assert payload['model'] == 'gpt-4o-mini'
        assert len(payload['messages']) == 2
        assert payload['messages'][0]['role'] == 'system'
        assert payload['messages'][0]['content'] == 'You are helpful.'
        assert payload['messages'][1]['role'] == 'user'
        assert payload['messages'][1]['content'] == 'Hello AI'

    def test_uuid_generation_for_request_id(self):
        """Test that request_id can be auto-generated as UUID."""
        import uuid
    
        # Create request without specifying request_id
        ai_request = AIRequest(
            user_prompt='Test',
            system_message='System',
            max_tokens=100,
            temperature=0.7,
            model='gpt-4o-mini',
            chat_id='123@c.us',
            message_id='msg_123'
        )
        
        assert ai_request.request_id is not None
        assert isinstance(ai_request.request_id, str)
        assert len(ai_request.request_id) > 0

    def test_timestamp_auto_population(self):
        """Test that timestamp can be auto-populated."""
        ai_request = AIRequest(
            user_prompt='Test',
            system_message='System',
            max_tokens=100,
            temperature=0.7,
            model='gpt-4o-mini',
            chat_id='123@c.us',
            message_id='msg_123'
        )
        
        assert ai_request.timestamp is not None
        assert isinstance(ai_request.timestamp, int)

    def test_system_message_max_tokens_temperature_passthrough(self):
        """Test that system_message, max_tokens, and temperature pass through correctly."""
        ai_request = AIRequest(
            user_prompt='User msg',
            system_message='Custom system message',
            max_tokens=2000,
            temperature=0.9,
            model='gpt-4o-mini',
            chat_id='123@c.us',
            message_id='msg_123'
        )
        
        assert ai_request.system_message == 'Custom system message'
        assert ai_request.max_tokens == 2000
        assert ai_request.temperature == 0.9


class TestAIResponse:
    """Test suite for AIResponse model."""

    @pytest.fixture
    def sample_openai_response(self):
        """Create a mock OpenAI API response."""
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message.content = 'This is the AI response.'
        response.choices[0].finish_reason = 'stop'
        response.usage.total_tokens = 150
        return response

    @pytest.fixture
    def long_openai_response(self):
        """Create a mock OpenAI response with >4000 characters."""
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message.content = 'A' * 4500  # 4500 chars
        response.choices[0].finish_reason = 'stop'
        response.usage.total_tokens = 500
        return response

    def test_from_openai_response_parses_correctly(self, sample_openai_response):
        """Test that from_openai_response() parses OpenAI response correctly."""
        ai_response = AIResponse.from_openai_response(sample_openai_response)
        
        assert ai_response.response_text == 'This is the AI response.'
        assert ai_response.finish_reason == 'stop'
        assert ai_response.tokens_used == 150

    def test_truncate_for_whatsapp_truncates_long_messages(self, long_openai_response):
        """Test that truncate_for_whatsapp() truncates messages >4000 chars."""
        ai_response = AIResponse.from_openai_response(long_openai_response)
        truncated = ai_response.truncate_for_whatsapp()
        
        assert len(truncated.response_text) <= 4003  # 4000 + "..."
        assert truncated.response_text.endswith('...')
        assert truncated.is_truncated is True

    def test_truncate_for_whatsapp_preserves_short_messages(self, sample_openai_response):
        """Test that truncate_for_whatsapp() preserves messages <=4000 chars."""
        ai_response = AIResponse.from_openai_response(sample_openai_response)
        truncated = ai_response.truncate_for_whatsapp()
        
        assert truncated.response_text == 'This is the AI response.'
        assert truncated.is_truncated is False

    def test_is_truncated_flag_set_correctly(self):
        """Test that is_truncated flag is set correctly."""
        import time
        # Short message
        short_response = AIResponse(
            request_id='req_123',
            response_text='Short message',
            tokens_used=10,
            prompt_tokens=5,
            completion_tokens=5,
            model='gpt-4o-mini',
            finish_reason='stop',
            timestamp=int(time.time()),
            is_truncated=False
        )
        assert short_response.is_truncated is False
        
        # Long message marked as truncated
        long_response = AIResponse(
            request_id='req_124',
            response_text='A' * 4001,
            tokens_used=100,
            prompt_tokens=50,
            completion_tokens=50,
            model='gpt-4o-mini',
            finish_reason='stop',
            timestamp=int(time.time()),
            is_truncated=True
        )
        assert long_response.is_truncated is True

    def test_tokens_used_extraction(self, sample_openai_response):
        """Test that tokens_used is extracted correctly."""
        ai_response = AIResponse.from_openai_response(sample_openai_response)
        
        assert ai_response.tokens_used == 150

    def test_finish_reason_handling(self):
        """Test that finish_reason is handled correctly."""
        import time
        for reason in ['stop', 'length', 'content_filter', 'null']:
            response = AIResponse(
                request_id='req_123',
                response_text='Test',
                tokens_used=10,
                prompt_tokens=5,
                completion_tokens=5,
                model='gpt-4o-mini',
                finish_reason=reason,
                timestamp=int(time.time()),
                is_truncated=False
            )
            assert response.finish_reason == reason
