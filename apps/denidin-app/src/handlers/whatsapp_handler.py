"""
WhatsAppHandler - Handles WhatsApp message processing with retry logic
Phase 5: US3 - Error Handling & Resilience
"""
from typing import cast
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    retry_if_exception_type
)
from whatsapp_chatbot_python import Notification
from src.constants.error_messages import (
    UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES,
    FAILED_TO_PROCESS_FILE_DEFAULT
)
from src.models.message import WhatsAppMessage, AIResponse
from src.utils.logger import get_logger

logger = get_logger(__name__)


class WhatsAppHandler:
    """
    Handles WhatsApp message processing and response sending.
    Implements retry logic with exponential backoff for Green API calls.
    Phase 6: Adds media message detection and routing to MediaHandler.
    """

    def __init__(self, media_handler=None):
        """
        Initialize WhatsAppHandler
        
        Args:
            media_handler: Optional MediaHandler instance for processing media messages
        """
        self.media_handler = media_handler
        logger.debug("WhatsAppHandler initialized")

    def process_notification(self, notification: Notification) -> WhatsAppMessage:
        """
        Process a Green API notification into a WhatsAppMessage.

        Args:
            notification: Green API notification object

        Returns:
            WhatsAppMessage object
        """
        # Use the from_notification factory method which handles timestamp, message_id, etc.
        message = WhatsAppMessage.from_notification(notification)

        logger.debug(
            f"Processed notification: {message.message_id} from {message.sender_name} "
            f"(group: {message.is_group})"
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
        logger.debug(f"received whatsapp notification: {notification}")

        # contactMessage (Feature 030 - shared WhatsApp contact card) flows through the
        # same conversational pipeline as text messages, see _process_conversational_message.
        if message_type not in ('extendedTextMessage', 'textMessage', 'contactMessage'):
            logger.warning(f"Unsupported message type received: {message_type}")
            return False

        return True

    def handle_unsupported_message(self, notification: Notification) -> None:
        """
        Send auto-reply for unsupported message types.

        Args:
            notification: Green API notification with unsupported message
        """
        message_type = notification.event.get('messageData', {}).get('typeMessage', 'unknown')
        sender_name = notification.event.get('senderData', {}).get('senderName', 'Unknown')

        logger.info(f"Sending unsupported message auto-reply to {sender_name} for {message_type}")

        auto_reply = UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES

        try:
            notification.answer(auto_reply)
            logger.debug("Unsupported message auto-reply sent successfully")
        except Exception as e:
            logger.error(f"Failed to send unsupported message auto-reply: {e}", exc_info=True)

    @retry(
        retry=retry_if_exception_type((requests.Timeout, requests.ConnectionError, requests.HTTPError)),
        stop=stop_after_attempt(2),  # Hardcoded: Initial attempt + 1 retry = 2 total attempts
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
        # bugfix-028 B5: the send boundary is the last place that can tell a
        # deliberate silence from a broken turn, and it used to check neither.
        # Anything that didn't raise was logged as "Response sent successfully",
        # including a literally empty message (sessions 047cacb7 turn 22,
        # 12e158e2 turn 16, logged as "0 chars").
        if not response.should_reply:
            logger.info(
                f"No reply owed for request {response.request_id} (should_reply=False) - "
                f"sending nothing, as intended."
            )
            return
        if not (response.response_text and response.response_text.strip()):
            # Unreachable via AIResponse's own contract, which refuses to build
            # this - kept as a boundary guard because "the user got nothing and
            # nobody noticed" is the failure being eliminated, and defence in
            # depth is cheap here.
            logger.error(
                f"Refusing to send an empty reply for request {response.request_id} - "
                f"a zero-character message is not a response."
            )
            return

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

    def is_media_message(self, notification: Notification) -> bool:
        """
        Check if notification contains a media message.
        
        Args:
            notification: Green API notification
            
        Returns:
            True if message is a media type (image, document, video, audio), False otherwise
        """
        message_type = notification.event.get('messageData', {}).get('typeMessage', '')
        return message_type in ['imageMessage', 'documentMessage', 'videoMessage', 'audioMessage']
    
    def get_media_type(self, notification: Notification) -> str:
        """
        Get the media message type from notification.
        
        Args:
            notification: Green API notification
            
        Returns:
            Media type string (e.g., 'imageMessage', 'documentMessage')
        """
        return cast(str, notification.event.get('messageData', {}).get('typeMessage', ''))
    
    def is_supported_media_message(self, notification: Notification) -> bool:
        """
        Check if the media message type is supported for processing.
        Currently only imageMessage and documentMessage are supported.
        Video and audio are future scope.
        
        Args:
            notification: Green API notification
            
        Returns:
            True if media type is supported, False otherwise
        """
        message_type = self.get_media_type(notification)
        return message_type in ['imageMessage', 'documentMessage']
    
    def handle_media_message(self, notification: Notification) -> None:
        """
        Process WhatsApp media messages (images, documents).
        Routes to MediaHandler and sends summary back to user.
        CHK111: Caption is WhatsApp message text from webhook, not file metadata.
        
        Args:
            notification: Green API notification containing media message
        """
        if not self.media_handler:
            logger.error("MediaHandler not initialized, cannot process media")
            return
        
        message_data = notification.event.get('messageData', {})

        # Feature 033: parse through the SAME WhatsAppMessage.from_notification
        # mechanism text messages use, rather than a separate bespoke field
        # extraction - message_id/chat_id/sender_id/timestamp are decided exactly
        # once, at "this message has arrived" time, by one shared code path (never
        # regenerated downstream). text_content comes back empty for media
        # notifications (irrelevant here - the caption below comes from
        # fileMessageData.caption, not text_content).
        message = WhatsAppMessage.from_notification(notification)
        chat_id = message.chat_id
        sender = message.sender_id
        timestamp = message.timestamp
        message_id = message.message_id

        # Extract media information from Green API webhook
        # Green API nests file metadata inside fileMessageData object
        file_message_data = message_data.get('fileMessageData', {})

        file_url = file_message_data.get('downloadUrl', '')
        filename = file_message_data.get('fileName', 'unknown')
        mime_type = file_message_data.get('mimeType', '')
        caption = file_message_data.get('caption', '')  # CHK111: WhatsApp message text

        # Note: Green API does NOT provide fileSize in webhook
        # File size will be determined after download by MediaFileManager
        file_size = 0  # Placeholder - actual size determined after download

        logger.info(f"Processing media message: {filename} ({mime_type}) from {sender}")

        # Process media through MediaHandler
        result = self.media_handler.process_media_message(
            file_url=file_url,
            filename=filename,
            mime_type=mime_type,
            file_size=file_size,
            caption=caption,  # CHK111: User's message text
            sender_phone=sender,
            chat_id=chat_id,
            timestamp=timestamp,
            message_id=message_id,
            sender_display_name=message.sender_display_name
        )
        
        if not result.get("success", False):
            # Send error message to user
            logger.warning(f"Media processing failed: {result.get('error_message', 'Unknown error')}")
            notification.answer(FAILED_TO_PROCESS_FILE_DEFAULT)
            return
        
        # Send summary to user (no approval workflow - just send as reply)
        summary = result.get("summary", "")
        logger.info(f"Sending media processing summary to {sender}")
        notification.answer(summary)
