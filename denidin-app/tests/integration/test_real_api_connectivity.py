"""
Real API connectivity tests - NO MOCKING.
Tests actual network calls to Green API and OpenAI to verify:
- API keys are valid
- Network connectivity works
- Request/response formats are correct
- The bot can actually communicate with external services

These tests will consume API quotas but ensure real-world functionality.
"""
import os
import sys
import pytest
import time

# Import real clients (NO mocking)
from whatsapp_api_client_python.API import GreenAPI
from openai import OpenAI

from src.models.config import AppConfiguration


class TestRealGreenAPIConnectivity:
    """Test real Green API connectivity - NO MOCKS."""
    
    @pytest.fixture
    def config(self):
        """Load actual configuration."""
        config_path = os.path.join(
            os.path.dirname(__file__), 
            '..', '..', 
            'config', 
            'config.json'
        )
        
        if not os.path.exists(config_path):
            pytest.skip("config.json not found - skipping real API test")
        
        config = AppConfiguration.from_file(config_path)
        config.validate()
        return config
    
    @pytest.fixture
    def green_api_client(self, config):
        """Create REAL Green API client - NO MOCKS."""
        return GreenAPI(
            config.green_api_instance_id,
            config.green_api_token
        )
    
    def test_greenapi_real_connection(self, green_api_client):
        """
        Tests REAL Green API connection by calling getStateInstance() API endpoint,
        verifying credentials are valid and account is authorized.
        
        This is a REAL API call - NO MOCKING.
        """
        print(f"\n[Real API Test] Testing Green API connectivity...")
        print(f"[Real API Test] This is a REAL API call (not mocked)")
        
        try:
            # REAL API call to Green API
            response = green_api_client.account.getStateInstance()
            
            assert response is not None, "Green API returned None response"
            
            if hasattr(response, 'data'):
                state = response.data.get('stateInstance', 'unknown')
                print(f"[Real API Test] ✓ Green API connection successful")
                print(f"[Real API Test]   Account state: {state}")
                print(f"[Real API Test]   Response type: {type(response)}")
                
                # Verify account is authorized
                if state != 'authorized':
                    pytest.fail(f"Green API account not authorized. State: {state}")
            else:
                print(f"[Real API Test] ✓ Green API connection successful")
                print(f"[Real API Test]   Response: {response}")
                
        except Exception as e:
            pytest.fail(f"Green API connection failed with real API call: {e}")
    
    def test_greenapi_can_send_message(self, green_api_client, config):
        """
        Tests REAL Green API message sending by attempting to send a test message,
        verifying the API accepts the request and returns a message ID.
        
        This is a REAL API call that sends an actual WhatsApp message.
        """
        print(f"\n[Real API Test] Testing Green API message sending...")
        print(f"[Real API Test] This will send a REAL WhatsApp message")
        
        # Send to the configured phone number (yourself)
        chat_id = "972559723730@c.us"
        test_message = f"[API Test {int(time.time())}] Green API connectivity verified"
        
        try:
            # REAL API call to send message
            response = green_api_client.sending.sendMessage(
                chatId=chat_id,
                message=test_message
            )
            
            assert response is not None, "sendMessage returned None"
            
            if hasattr(response, 'data'):
                message_id = response.data.get('idMessage', 'unknown')
                print(f"[Real API Test] ✓ Message sent successfully")
                print(f"[Real API Test]   Message ID: {message_id}")
                print(f"[Real API Test]   Sent to: {chat_id}")
                
                assert message_id != 'unknown', "No message ID returned"
            else:
                print(f"[Real API Test] ✓ Message sent successfully")
                print(f"[Real API Test]   Response: {response}")
                
        except Exception as e:
            pytest.fail(f"Green API sendMessage failed with real API call: {e}")


class TestRealOpenAPIConnectivity:
    """Test real OpenAI API connectivity - NO MOCKS."""
    
    @pytest.fixture
    def config(self):
        """Load actual configuration."""
        config_path = os.path.join(
            os.path.dirname(__file__), 
            '..', '..', 
            'config', 
            'config.json'
        )
        
        if not os.path.exists(config_path):
            pytest.skip("config.json not found - skipping real API test")
        
        config = AppConfiguration.from_file(config_path)
        config.validate()
        return config
    
    @pytest.fixture
    def openai_client(self, config):
        """Create REAL OpenAI client - NO MOCKS."""
        return OpenAI(
            api_key=config.openai_api_key,
            timeout=30.0
        )
    
    def test_openai_real_connection(self, openai_client, config):
        """
        Tests REAL OpenAI connection by making an actual chat completion API call,
        verifying API key is valid and the service responds correctly.
        
        This is a REAL API call that consumes OpenAI quota.
        """
        print(f"\n[Real API Test] Testing OpenAI connectivity...")
        print(f"[Real API Test] This is a REAL API call (will consume quota)")
        
        test_message = "Please respond with exactly: 'API test successful'"
        
        try:
            # REAL API call to OpenAI
            response = openai_client.chat.completions.create(
                model=config.ai_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Follow instructions exactly."},
                    {"role": "user", "content": test_message}
                ],
                temperature=0.3,  # Low temperature for consistent response
                max_tokens=50
            )
            
            assert response is not None, "OpenAI returned None response"
            assert len(response.choices) > 0, "OpenAI returned no choices"
            
            ai_response = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            finish_reason = response.choices[0].finish_reason
            
            print(f"[Real API Test] ✓ OpenAI connection successful")
            print(f"[Real API Test]   Model: {config.ai_model}")
            print(f"[Real API Test]   Response: {ai_response}")
            print(f"[Real API Test]   Tokens used: {tokens_used}")
            print(f"[Real API Test]   Finish reason: {finish_reason}")
            
            # Verify response structure
            assert ai_response is not None and len(ai_response) > 0, "Empty AI response"
            assert tokens_used > 0, "Token count should be positive"
            assert finish_reason in ['stop', 'length'], f"Unexpected finish reason: {finish_reason}"
            
        except Exception as e:
            pytest.fail(f"OpenAI API call failed: {e}")
    
    def test_openai_can_receive_and_parse_response(self, openai_client, config):
        """
        Tests that the bot can receive and correctly parse OpenAI responses,
        extracting message content, token usage, and completion metadata.
        
        This is a REAL API call that consumes OpenAI quota.
        """
        print(f"\n[Real API Test] Testing OpenAI response parsing...")
        print(f"[Real API Test] This is a REAL API call (will consume quota)")
        
        try:
            # REAL API call with a question
            response = openai_client.chat.completions.create(
                model=config.ai_model,
                messages=[
                    {"role": "system", "content": config.system_message},
                    {"role": "user", "content": "What is 2+2? Answer with just the number."}
                ],
                temperature=config.temperature,
                max_tokens=config.max_tokens
            )
            
            # Verify we can access all necessary fields
            assert hasattr(response, 'choices'), "Response missing 'choices'"
            assert len(response.choices) > 0, "Response has no choices"
            assert hasattr(response.choices[0], 'message'), "Choice missing 'message'"
            assert hasattr(response.choices[0].message, 'content'), "Message missing 'content'"
            assert hasattr(response.choices[0], 'finish_reason'), "Choice missing 'finish_reason'"
            assert hasattr(response, 'usage'), "Response missing 'usage'"
            assert hasattr(response.usage, 'total_tokens'), "Usage missing 'total_tokens'"
            
            content = response.choices[0].message.content
            tokens = response.usage.total_tokens
            
            print(f"[Real API Test] ✓ Response parsed successfully")
            print(f"[Real API Test]   Content: {content}")
            print(f"[Real API Test]   Tokens: {tokens}")
            print(f"[Real API Test]   All required fields present")
            
        except Exception as e:
            pytest.fail(f"OpenAI response parsing failed: {e}")


class TestRealEndToEndFlow:
    """Test complete E2E flow with REAL API calls - NO MOCKS."""
    
    @pytest.fixture
    def config(self):
        """Load actual configuration."""
        config_path = os.path.join(
            os.path.dirname(__file__), 
            '..', '..', 
            'config', 
            'config.json'
        )
        
        if not os.path.exists(config_path):
            pytest.skip("config.json not found - skipping real E2E test")
        
        config = AppConfiguration.from_file(config_path)
        config.validate()
        return config
    
    @pytest.fixture
    def green_api_client(self, config):
        """Create REAL Green API client."""
        return GreenAPI(
            config.green_api_instance_id,
            config.green_api_token
        )
    
    @pytest.fixture
    def openai_client(self, config):
        """Create REAL OpenAI client."""
        return OpenAI(
            api_key=config.openai_api_key,
            timeout=30.0
        )
    
    def test_complete_real_api_flow(self, config, green_api_client, openai_client):
        """
        Tests the complete message flow with REAL API calls:
        1. Verify Green API can connect
        2. Send a message via OpenAI (simulating bot processing)
        3. Receive OpenAI response
        4. Send response via Green API to WhatsApp
        
        This test uses REAL APIs and will:
        - Consume OpenAI quota
        - Send actual WhatsApp messages
        - Test real network connectivity
        """
        print(f"\n[Real E2E Test] ========================================")
        print(f"[Real E2E Test] Complete End-to-End Flow - REAL APIs")
        print(f"[Real E2E Test] ========================================")
        print(f"[Real E2E Test] WARNING: This test uses real APIs and quotas")
        
        chat_id = "972559723730@c.us"
        test_question = f"[E2E Test {int(time.time())}] What is the capital of France? Answer in one word."
        
        try:
            # Step 1: Verify Green API connection
            print(f"\n[Real E2E Test] Step 1: Verify Green API connection")
            state_response = green_api_client.account.getStateInstance()
            state = state_response.data.get('stateInstance') if hasattr(state_response, 'data') else 'unknown'
            print(f"[Real E2E Test]   ✓ Green API connected (state: {state})")
            
            assert state == 'authorized', f"Green API not authorized: {state}"
            
            # Step 2: Send question to OpenAI (simulating incoming WhatsApp message)
            print(f"\n[Real E2E Test] Step 2: Send message to OpenAI")
            print(f"[Real E2E Test]   Question: {test_question}")
            
            openai_response = openai_client.chat.completions.create(
                model=config.ai_model,
                messages=[
                    {"role": "system", "content": config.system_message},
                    {"role": "user", "content": test_question}
                ],
                temperature=config.temperature,
                max_tokens=config.max_tokens
            )
            
            print(f"[Real E2E Test]   ✓ Request sent to OpenAI")
            
            # Step 3: Receive and parse OpenAI response
            print(f"\n[Real E2E Test] Step 3: Receive OpenAI response")
            ai_answer = openai_response.choices[0].message.content
            tokens_used = openai_response.usage.total_tokens
            
            print(f"[Real E2E Test]   ✓ Response received from OpenAI")
            print(f"[Real E2E Test]   AI Answer: {ai_answer}")
            print(f"[Real E2E Test]   Tokens used: {tokens_used}")
            
            assert ai_answer is not None and len(ai_answer) > 0, "Empty OpenAI response"
            
            # Step 4: Send AI response back via Green API
            print(f"\n[Real E2E Test] Step 4: Send response via Green API")
            
            full_message = f"E2E Test Result:\nQ: {test_question}\nA: {ai_answer}\n(Tokens: {tokens_used})"
            
            send_response = green_api_client.sending.sendMessage(
                chatId=chat_id,
                message=full_message
            )
            
            message_id = send_response.data.get('idMessage') if hasattr(send_response, 'data') else 'unknown'
            
            print(f"[Real E2E Test]   ✓ Response sent to WhatsApp")
            print(f"[Real E2E Test]   Message ID: {message_id}")
            
            assert message_id != 'unknown', "Failed to get message ID"
            
            # Success!
            print(f"\n[Real E2E Test] ========================================")
            print(f"[Real E2E Test] ✓ Complete E2E flow successful!")
            print(f"[Real E2E Test] ========================================")
            print(f"[Real E2E Test] Summary:")
            print(f"[Real E2E Test] - Green API: Connected and authorized")
            print(f"[Real E2E Test] - OpenAI: Sent request, received response")
            print(f"[Real E2E Test] - Green API: Sent message to WhatsApp")
            print(f"[Real E2E Test] - Check WhatsApp {chat_id.replace('@c.us', '')} for message")
            print(f"[Real E2E Test] ========================================")
            
        except Exception as e:
            print(f"\n[Real E2E Test] ✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            pytest.fail(f"Real E2E test failed: {e}")
