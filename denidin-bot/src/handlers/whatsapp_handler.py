"""
WhatsAppHandler - Handles WhatsApp message processing with retry logic
Phase 5: US3 - Error Handling & Resilience
"""
import requests
import time
from typing import Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    retry_if_exception_type
)
from whatsapp_chatbot_python import Notification
from src.models.message import WhatsAppMessage, AIResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WhatsAppHandler:
    """
    Handles WhatsApp message processing and response sending.
    Implements retry logic with exponential backoff for Green API calls.
    """
    
    def __init__(self):
        """Initialize WhatsAppHandler"""
        logger.debug("WhatsAppHandler initialized")
    
    def process_notification(self, notification: Notification) -> WhatsAppMessage:
        """
        Process a Green API notification into a WhatsAppMessage.
        
        Args:
            notification: Green API notification object
            
        Returns:
            WhatsAppMessage object
        """
        event = notification.event
        
        # Extract message data
        message_data = event.get('messageData', {})
        text_data = message_data.get('textMessageData', {})
        sender_data = event.get('senderData', {})
        
        # Determine if group message
        chat_id = sender_data.get('chatId', sender_data.get('sender', ''))
        is_group = '@g.us' in chat_id
        
        message = WhatsAppMessage(
            message_id=event.get('idMessage', ''),
            chat_id=chat_id,
            sender_id=sender_data.get('sender', ''),
            sender_name=sender_data.get('senderName', 'Unknown'),
            text_content=text_data.get('textMessage', ''),
            timestamp=event.get('timestamp', 0),
            message_type=message_data.get('typeMessage', 'textMessage'),
            is_group=is_group
        )
        
        logger.debug(
            f"Processed notification: {message.message_id} from {message.sender_name} "
            f"(group: {is_group})"
        )
        
        return message
    
    def validate_message_type(self, notification: Notification) -> bool:
        """
        Validate that the message type is supported (textMessage only).
        
        Args:
            notification: Green API notification
            
        Returns:
            True if message type is supported, False otherwise
        """
        message_type = notification.event.get('messageData', {}).get('typeMessage', '')
        
        if message_type != 'textMessage':
            logger.warning(f"Unsupported message type received: {message_type}")
            return False
        
        return True
    
    def is_bot_mentioned_in_group(self, message: WhatsAppMessage, bot_name: str = "DeniDin") -> bool:
        """
        Check if bot is mentioned in a group message.
        
        Args:
            message: WhatsApp message to check
            bot_name: Name of the bot to look for
            
        Returns:
            True if bot is mentioned or message is 1-on-1, False otherwise
        """
        # Always process 1-on-1 messages
        if not message.is_group:
            return True
        
        # In groups, only respond if mentioned
        text_lower = message.text_content.lower()
        bot_name_lower = bot_name.lower()
        
        is_mentioned = bot_name_lower in text_lower
        
        if not is_mentioned:
            logger.debug(
                f"Bot not mentioned in group message {message.message_id}, skipping"
            )
        
        return is_mentioned
    
    def handle_unsupported_message(self, notification: Notification) -> None:
        """
        Send auto-reply for unsupported message types.
        
        Args:
            notification: Green API notification with unsupported message
        """
        message_type = notification.event.get('messageData', {}).get('typeMessage', 'unknown')
        sender_name = notification.event.get('senderData', {}).get('senderName', 'Unknown')
        
        logger.info(f"Sending unsupported message auto-reply to {sender_name} for {message_type}")
        
        auto_reply = "I currently only support text messages. Please send your message as text."
        
        try:
            notification.answer(auto_reply)
            logger.debug("Unsupported message auto-reply sent successfully")
        except Exception as e:
            logger.error(f"Failed to send unsupported message auto-reply: {e}", exc_info=True)
    
    @retry(
        retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError, requests.HTTPError)),
        stop=stop_after_attempt(2),  # Initial attempt + 1 retry = 2 total
        wait=wait_fixed(1),  # 1 second wait
        reraise=True
    )
    def _send_with_retry(self, notification: Notification, message: str) -> None:
        """
        Send message via Green API with retry logic.
        Retries ONCE (max 2 attempts) only on 5xx errors and network errors, waits 1 second.
        Does NOT retry 4xx client errors.
        
        Args:
            notification: Green API notification to reply to
            message: Message text to send
            
        Raises:
            requests.RequestException: After 2 attempts (1 retry) or immediately on 4xx errors
        """
        try:
            notification.answer(message)
        except requests.HTTPError as e:
            # Check if this is a 4xx error that shouldn't be retried
            if hasattr(e, 'response') and e.response is not None:
                if 400 <= e.response.status_code < 500:
                    logger.error(f"HTTP {e.response.status_code} client error - not retrying: {e}")
                    raise  # Don't retry 4xx errors
                # 5xx errors: let tenacity retry them by raising
            raise
    
    def send_response(self, notification: Notification, response: AIResponse) -> None:
        """
        Send AI response back to WhatsApp with error handling.
        
        Args:
            notification: Green API notification to reply to
            response: AI response to send
        """
        try:
            logger.debug(f"Sending response for request {response.request_id}")
            
            # Use retry wrapper for actual send
            self._send_with_retry(notification, response.response_text)
            
            logger.info(
                f"Response sent successfully for request {response.request_id}: "
                f"{len(response.response_text)} chars"
            )
            
        except requests.HTTPError as e:
            # Log specific HTTP error details
            status_code = e.response.status_code if hasattr(e, 'response') else 'unknown'
            
            if status_code == 400:
                logger.error(f"Green API 400 Bad Request error: {e}", exc_info=True)
            elif status_code == 401:
                logger.error(f"Green API 401 Authentication error: {e}", exc_info=True)
            elif status_code == 429:
                logger.error(f"Green API 429 Rate limit error: {e}", exc_info=True)
            elif status_code == 500:
                logger.error(f"Green API 500 Server error: {e}", exc_info=True)
            else:
                logger.error(f"Green API HTTP {status_code} error: {e}", exc_info=True)
            
            raise  # Re-raise after logging
            
        except requests.Timeout as e:
            logger.error(f"Green API timeout error: {e}", exc_info=True)
            raise
            
        except requests.ConnectionError as e:
            logger.error(f"Green API connection error: {e}", exc_info=True)
            raise
            
        except requests.RequestException as e:
            logger.error(f"Green API request error: {e}", exc_info=True)
            raise
            
        except Exception as e:
            logger.error(f"Unexpected error sending response: {e}", exc_info=True)
            raise
