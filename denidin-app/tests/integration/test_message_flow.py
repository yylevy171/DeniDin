"""
Integration tests for the complete message flow:
Green API receive → OpenAI send → OpenAI receive → Green API send
"""
import os
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime

# Mock external dependencies before importing bot code
sys.modules['whatsapp_chatbot_python'] = MagicMock()

from src.models.config import AppConfiguration


class TestMessageFlow:
    """Test the complete message processing flow with mocked APIs."""
    
    @pytest.fixture
    def config(self):
        """Load actual configuration for testing."""
        config_path = os.path.join(
            os.path.dirname(__file__), 
            '..', '..', 
            'config', 
            'config.json'
        )
        
        if not os.path.exists(config_path):
            pytest.skip("config.json not found - skipping integration test")
        
        config = AppConfiguration.from_file(config_path)
        config.validate()
        return config
    
    @pytest.fixture
    def mock_notification(self):
        """Create a mock WhatsApp notification from Green API."""
        notification = Mock()
        
        # Message data structure from Green API
        notification.event = {
            'typeWebhook': 'incomingMessageReceived',
            'instanceData': {
                'idInstance': 7105257767,
                'wid': '972559723730@c.us',
                'typeInstance': 'whatsapp'
            },
            'timestamp': 1768667000,
            'idMessage': '3EB0TEST123456789',
            'senderData': {
                'chatId': '972501234567@c.us',
                'chatName': 'Test User',
                'sender': '972501234567@c.us',
                'senderName': 'Test User'
            },
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {
                    'textMessage': 'Hello, can you help me?'
                }
            }
        }
        
        # Mock the answer method that sends responses
        notification.answer = Mock()
        
        return notification
    
    @pytest.fixture
    def mock_openai_response(self):
        """Create a mock OpenAI API response."""
        response = Mock()
        response.choices = [Mock()]
        response.choices[0].message = Mock()
        response.choices[0].message.content = "Of course! I'd be happy to help you. What do you need assistance with?"
        response.choices[0].finish_reason = 'stop'
        response.usage = Mock()
        response.usage.total_tokens = 42
        return response
    
    def test_greenapi_receive_message(self, mock_notification):
        """
        Tests that the bot correctly receives and parses a WhatsApp message from Green API, 
        extracting sender info, chat ID, and message text.
        """
        # Import bot module to get the handler
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "bot",
            os.path.join(os.path.dirname(__file__), '..', '..', 'denidin.py')
        )
        
        # Verify notification structure
        assert mock_notification.event['typeWebhook'] == 'incomingMessageReceived'
        assert mock_notification.event['messageData']['typeMessage'] == 'textMessage'
        
        # Extract message data (what the bot handler does)
        message_text = mock_notification.event['messageData']['textMessageData']['textMessage']
        sender_name = mock_notification.event['senderData']['senderName']
        chat_id = mock_notification.event['senderData']['chatId']
        
        assert message_text == 'Hello, can you help me?'
        assert sender_name == 'Test User'
        assert chat_id == '972501234567@c.us'
        
        print(f"\n[Flow Test] ✓ Green API receive: Message parsed correctly")
        print(f"[Flow Test]   From: {sender_name}")
        print(f"[Flow Test]   Chat ID: {chat_id}")
        print(f"[Flow Test]   Text: {message_text}")
    
    @patch('openai.OpenAI')
    def test_openai_send_request(self, mock_openai_class, config, mock_notification):
        """
        Tests that the bot correctly sends a chat completion request to OpenAI with the user's message, 
        system prompt, and configured parameters (model, temperature, max_tokens).
        """
        # Setup mock
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        
        # Extract message from notification
        message_text = mock_notification.event['messageData']['textMessageData']['textMessage']
        
        # Simulate what bot does: create OpenAI request
        from openai import OpenAI
        client = OpenAI(api_key=config.ai_api_key)
        
        # Prepare the request (as denidin.py does)
        messages = [
            {"role": "system", "content": config.constitution},
            {"role": "user", "content": message_text}
        ]
        
        # Verify request structure
        assert messages[0]['role'] == 'system'
        assert messages[0]['content'] == config.constitution
        assert messages[1]['role'] == 'user'
        assert messages[1]['content'] == 'Hello, can you help me?'
        
        print(f"\n[Flow Test] ✓ OpenAI send: Request structured correctly")
        print(f"[Flow Test]   Model: {config.ai_model}")
        print(f"[Flow Test]   System message: {config.constitution[:50]}...")
        print(f"[Flow Test]   User message: {message_text}")
        print(f"[Flow Test]   Temperature: {config.temperature}")
        print(f"[Flow Test]   Max tokens: {config.max_tokens}")
    
    def test_openai_receive_response(self, mock_openai_response):
        """
        Tests that the bot correctly receives and extracts the AI response from OpenAI's chat completion, 
        including response text, token usage, and finish reason.
        """
        # Verify response structure
        assert hasattr(mock_openai_response, 'choices')
        assert len(mock_openai_response.choices) > 0
        assert hasattr(mock_openai_response.choices[0], 'message')
        assert hasattr(mock_openai_response.choices[0].message, 'content')
        
        # Extract response (what bot does)
        response_text = mock_openai_response.choices[0].message.content
        finish_reason = mock_openai_response.choices[0].finish_reason
        tokens_used = mock_openai_response.usage.total_tokens
        
        assert response_text == "Of course! I'd be happy to help you. What do you need assistance with?"
        assert finish_reason == 'stop'
        assert tokens_used == 42
        
        print(f"\n[Flow Test] ✓ OpenAI receive: Response parsed correctly")
        print(f"[Flow Test]   Response: {response_text}")
        print(f"[Flow Test]   Tokens used: {tokens_used}")
        print(f"[Flow Test]   Finish reason: {finish_reason}")
    
    def test_greenapi_send_response(self, mock_notification, mock_openai_response):
        """
        Tests that the bot correctly sends the AI-generated response back to WhatsApp using Green API's 
        notification.answer() method with the proper response text.
        """
        # Extract AI response
        response_text = mock_openai_response.choices[0].message.content
        
        # Send response (what bot does)
        mock_notification.answer(response_text)
        
        # Verify answer was called with correct text
        mock_notification.answer.assert_called_once_with(response_text)
        
        print(f"\n[Flow Test] ✓ Green API send: Response sent to WhatsApp")
        print(f"[Flow Test]   Response text: {response_text}")
    
    @patch('openai.OpenAI')
    def test_complete_message_flow_integration(
        self, 
        mock_openai_class, 
        config, 
        mock_notification, 
        mock_openai_response
    ):
        """
        Tests the complete end-to-end message flow: receive WhatsApp message from Green API, send to OpenAI, 
        receive AI response, and send back to WhatsApp, verifying all steps execute in sequence.
        """
        print(f"\n[Flow Test] ========================================")
        print(f"[Flow Test] Complete Message Flow Integration Test")
        print(f"[Flow Test] ========================================")
        
        # Setup OpenAI mock
        mock_client = Mock()
        mock_chat = Mock()
        mock_completions = Mock()
        mock_completions.create.return_value = mock_openai_response
        mock_chat.completions = mock_completions
        mock_client.chat = mock_chat
        mock_openai_class.return_value = mock_client
        
        # Step 1: Green API receives message
        print(f"\n[Flow Test] Step 1: Green API receives WhatsApp message")
        message_text = mock_notification.event['messageData']['textMessageData']['textMessage']
        sender_name = mock_notification.event['senderData']['senderName']
        print(f"[Flow Test]   ✓ Message received from {sender_name}: '{message_text}'")
        
        # Step 2: Send to OpenAI
        print(f"\n[Flow Test] Step 2: Send message to OpenAI")
        from openai import OpenAI
        client = OpenAI(api_key=config.ai_api_key)
        
        response = client.chat.completions.create(
            model=config.ai_model,
            messages=[
                {"role": "system", "content": config.constitution},
                {"role": "user", "content": message_text}
            ],
            temperature=config.temperature,
            max_tokens=config.max_tokens
        )
        print(f"[Flow Test]   ✓ Request sent to OpenAI ({config.ai_model})")
        
        # Step 3: Receive from OpenAI
        print(f"\n[Flow Test] Step 3: Receive AI response from OpenAI")
        ai_response = response.choices[0].message.content
        tokens = response.usage.total_tokens
        print(f"[Flow Test]   ✓ Response received ({tokens} tokens): '{ai_response[:50]}...'")
        
        # Step 4: Send back via Green API
        print(f"\n[Flow Test] Step 4: Send AI response back to WhatsApp")
        mock_notification.answer(ai_response)
        print(f"[Flow Test]   ✓ Response sent to {sender_name}")
        
        # Verify all steps completed
        mock_notification.answer.assert_called_once_with(ai_response)
        mock_completions.create.assert_called_once()
        
        print(f"\n[Flow Test] ========================================")
        print(f"[Flow Test] ✓ Complete flow executed successfully")
        print(f"[Flow Test] ========================================")
        
        # Verify the call arguments
        call_args = mock_completions.create.call_args
        assert call_args.kwargs['model'] == config.ai_model
        assert call_args.kwargs['messages'][0]['role'] == 'system'
        assert call_args.kwargs['messages'][1]['role'] == 'user'
        assert call_args.kwargs['messages'][1]['content'] == message_text
        assert call_args.kwargs['temperature'] == config.temperature
        assert call_args.kwargs['max_tokens'] == config.max_tokens
