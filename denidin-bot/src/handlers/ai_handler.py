"""
AIHandler - Handles OpenAI API interactions with retry logic and error handling
Phase 5: US3 - Error Handling & Resilience
"""
import time
from typing import Optional
from openai import OpenAI, APITimeoutError, RateLimitError, APIError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    retry_if_exception_type
)
from src.models.config import BotConfiguration
from src.models.message import WhatsAppMessage, AIRequest, AIResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Maximum message length to prevent excessive API costs
MAX_MESSAGE_LENGTH = 10000


class AIHandler:
    """
    Handles AI operations including request creation and OpenAI API calls.
    Implements retry logic with exponential backoff for transient failures.
    """
    
    def __init__(self, openai_client: OpenAI, config: BotConfiguration):
        """
        Initialize AIHandler with OpenAI client and configuration.
        
        Args:
            openai_client: Configured OpenAI client instance
            config: Bot configuration with AI settings
        """
        self.client = openai_client
        self.config = config
        logger.debug(f"AIHandler initialized with model: {config.ai_model}")
    
    def create_request(self, message: WhatsAppMessage) -> AIRequest:
        """
        Create an AIRequest from a WhatsApp message.
        Validates and truncates message length if needed.
        
        Args:
            message: WhatsApp message to convert
            
        Returns:
            AIRequest ready for OpenAI API
        """
        # Validate and truncate message length
        user_prompt = message.text_content
        if len(user_prompt) > MAX_MESSAGE_LENGTH:
            logger.warning(
                f"Message length {len(user_prompt)} exceeds maximum {MAX_MESSAGE_LENGTH} chars. "
                f"Truncating from sender {message.sender_name}"
            )
            user_prompt = user_prompt[:MAX_MESSAGE_LENGTH]
        
        # Create AI request
        request = AIRequest(
            user_prompt=user_prompt,
            system_message=self.config.system_message,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            model=self.config.ai_model,
            chat_id=message.chat_id,
            message_id=message.message_id
        )
        
        logger.debug(f"Created AIRequest {request.request_id} for message {message.message_id}")
        return request
    
    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
        stop=stop_after_attempt(2),  # Initial attempt + 1 retry = 2 total
        wait=wait_fixed(1),  # 1 second wait between retries
        reraise=True
    )
    def _call_openai_api(self, request: AIRequest):
        """
        Make the actual OpenAI API call with retry logic.
        Retries ONCE (max 2 attempts) on transient failures, waits 1 second.
        
        Args:
            request: AI request to send
            
        Returns:
            OpenAI completion response
            
        Raises:
            RateLimitError: After 2 attempts (1 retry)
            APITimeoutError: After 2 attempts (1 retry)
            APIError: After 2 attempts (1 retry)
        """
        logger.debug(f"Calling OpenAI API for request {request.request_id}")
        
        messages = [
            {"role": "system", "content": request.system_message},
            {"role": "user", "content": request.user_prompt}
        ]
        
        completion = self.client.chat.completions.create(
            model=request.model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        
        return completion
    
    def get_response(self, request: AIRequest) -> AIResponse:
        """
        Get AI response for a request with error handling and fallbacks.
        
        Args:
            request: AI request to process
            
        Returns:
            AIResponse with generated text or fallback message
        """
        try:
            # Call OpenAI API with retry logic
            completion = self._call_openai_api(request)
            
            # Extract response
            response_text = completion.choices[0].message.content
            tokens_used = completion.usage.total_tokens
            
            logger.info(
                f"AI response generated for request {request.request_id}: "
                f"{tokens_used} tokens, {len(response_text)} chars"
            )
            logger.debug(f"Full response: {response_text[:200]}...")
            
            # Create response object
            response = AIResponse(
                request_id=request.request_id,
                response_text=response_text,
                tokens_used=tokens_used,
                prompt_tokens=completion.usage.prompt_tokens,
                completion_tokens=completion.usage.completion_tokens,
                model=completion.model,
                finish_reason=completion.choices[0].finish_reason,
                timestamp=int(time.time()),
                is_truncated=False
            )
            
            # Check if response needs truncation for WhatsApp
            if len(response_text) > 4000:
                response = response.truncate_for_whatsapp()
                logger.warning(f"Response truncated to 4000 chars for WhatsApp")
            
            return response
            
        except APITimeoutError as e:
            logger.error(
                f"OpenAI API timeout for request {request.request_id} after retries: {e}",
                exc_info=True
            )
            return self._create_fallback_response(
                request.request_id,
                "Sorry, I'm having trouble connecting to my AI service. Please try again later."
            )
            
        except RateLimitError as e:
            logger.error(
                f"OpenAI rate limit exceeded for request {request.request_id} after retries: {e}",
                exc_info=True
            )
            return self._create_fallback_response(
                request.request_id,
                "I'm currently at capacity. Please try again in a minute."
            )
            
        except APIError as e:
            logger.error(
                f"OpenAI API error for request {request.request_id} after retries: {e}",
                exc_info=True
            )
            return self._create_fallback_response(
                request.request_id,
                "Sorry, I encountered an error processing your request. Please try again."
            )
            
        except Exception as e:
            logger.error(
                f"Unexpected error in get_response for request {request.request_id}: {e}",
                exc_info=True
            )
            return self._create_fallback_response(
                request.request_id,
                "Sorry, I encountered an unexpected error. Please try again."
            )
    
    def _create_fallback_response(self, request_id: str, message: str) -> AIResponse:
        """
        Create a fallback AIResponse for error cases.
        
        Args:
            request_id: Original request ID
            message: Fallback message to send
            
        Returns:
            AIResponse with fallback content
        """
        return AIResponse(
            request_id=request_id,
            response_text=message,
            tokens_used=0,
            prompt_tokens=0,
            completion_tokens=0,
            model="error-fallback",
            finish_reason="error",
            timestamp=int(time.time()),
            is_truncated=False
        )
