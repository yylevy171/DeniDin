"""
Green API Webhook Data Models

These models represent the EXACT webhook notification structures as defined by Green API.
Documentation: https://green-api.com/en/docs/api/receiving/notifications-format/

All models match Green API specification precisely for accurate testing and integration.

**CRITICAL: SDK Integration with whatsapp-chatbot-python**

We use the official Green API Python SDK: whatsapp-chatbot-python (v0.9.8+)
GitHub: https://github.com/green-api/whatsapp-chatbot-python

The SDK provides:
- GreenAPIBot: Bot instance that connects to Green API
- Notification: Wrapper around webhook notifications with .answer() method

**Why chatId is REQUIRED in senderData:**

When our handlers call notification.answer(message), the SDK internally:
1. Calls notification.get_chat() 
2. Extracts chatId from notification.event["senderData"]["chatId"]
3. Calls Green API SendMessage endpoint with the chatId

Without chatId in senderData, notification.answer() will raise KeyError.

This is an SDK requirement, not a direct Green API API requirement. The Green API
SendMessage endpoint only needs {chatId, message}, but the SDK's convenience method
notification.answer() depends on chatId being in the incoming notification structure.

**Incoming vs Outgoing Structure:**
- Incoming (webhook): Complex nested structure with senderData.chatId
- Outgoing (SendMessage API): Flat {chatId, message}
- SDK bridges these by extracting chatId from incoming structure

**Test Fixture Requirements:**
All test fixtures MUST include chatId in senderData to match real Green API webhooks
and to be compatible with the SDK's notification.answer() method.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class InstanceData:
    """Green API instance data object."""
    idInstance: int
    wid: str
    typeInstance: str = "whatsapp"


@dataclass
class SenderData:
    """
    Green API sender data object.
    
    **CRITICAL FIELD: chatId**
    - chatId is REQUIRED for notification.answer() to work
    - SDK extracts chatId to determine where to send responses
    - For 1-on-1 chats: chatId == sender (same WhatsApp ID)
    - For group chats: chatId = group ID, sender = individual who sent message
    
    Without chatId, the SDK cannot route responses and will raise KeyError.
    """
    chatId: str  # REQUIRED - where to send the response
    sender: str  # REQUIRED - who sent the message
    chatName: Optional[str] = None
    senderName: Optional[str] = None
    senderContactName: Optional[str] = None


@dataclass
class FileMessageData:
    """
    Green API fileMessageData object for image/video/audio/document messages.
    
    Note: Green API does NOT provide fileSize in webhook notifications.
    File size must be determined after downloading the file.
    
    Fields:
    - downloadUrl: Link to download file
    - caption: File caption (empty string if none)
    - fileName: File name (auto-generated except for documentMessage)
    - jpegThumbnail: Image preview in base64 (may be empty)
    - mimeType: File MIME type
    - isForwarded: Whether message is forwarded
    - forwardingScore: Number of times forwarded
    - videoNote: (video only) true for instant video, false for regular video
    """
    downloadUrl: str
    caption: str = ""
    fileName: str = ""
    jpegThumbnail: str = ""
    mimeType: str = ""
    isForwarded: bool = False
    forwardingScore: int = 0
    # Video-specific field
    videoNote: Optional[bool] = None


@dataclass
class QuotedMessage:
    """Green API quotedMessage object for quoted/reply messages."""
    stanzaId: str
    participant: str
    typeMessage: str
    # Additional fields depend on quoted message type
    # See Green API docs for complete list


@dataclass
class MessageData:
    """
    Green API messageData object.
    
    For file messages (image/video/audio/document), the file metadata
    is nested inside fileMessageData, NOT at the messageData level.
    """
    typeMessage: str
    fileMessageData: Optional[FileMessageData] = None
    quotedMessage: Optional[QuotedMessage] = None
    # Text message fields
    textMessage: Optional[str] = None


class NotificationValidationError(Exception):
    """
    Raised when notification object fails validation before sending response.
    
    This exception is raised when trying to validate a notification that doesn't
    match the structure required by the whatsapp-chatbot-python SDK.
    """
    pass


def validate_notification_for_response(notification: Any) -> None:
    """
    Validate that notification has required fields for SDK's notification.answer().
    
    **CRITICAL: SDK Dependency**
    The whatsapp-chatbot-python SDK's notification.answer() method internally calls:
        notification.get_chat() -> returns notification.event["senderData"]["chatId"]
    
    Without chatId, the SDK raises KeyError and cannot send responses.
    
    This validation catches structural issues BEFORE calling notification.answer(),
    providing clear error messages for debugging.
    
    **NOT a Green API requirement** - The Green API SendMessage endpoint only needs
    {chatId, message}. This is a requirement of the SDK's convenience wrapper.
    
    Args:
        notification: Notification object from whatsapp-chatbot-python SDK
    
    Raises:
        NotificationValidationError: If notification structure doesn't match SDK requirements
    
    Required structure for SDK compatibility:
        notification.event['senderData']['chatId'] - MUST exist and be non-empty
    
    Example usage in handlers:
        >>> validate_notification_for_response(notification)
        >>> notification.answer("Response message")  # Safe - SDK can extract chatId
    """
    # Check notification has event dict
    if not hasattr(notification, 'event'):
        raise NotificationValidationError(
            "Notification object missing 'event' attribute. "
            "Cannot validate notification structure."
        )
    
    event = notification.event
    
    # Check senderData exists
    if 'senderData' not in event:
        raise NotificationValidationError(
            "Notification event missing 'senderData' field. "
            "Cannot send response without sender information.\n"
            f"Event keys: {list(event.keys())}"
        )
    
    sender_data = event['senderData']
    
    # Check chatId exists (CRITICAL for SDK compatibility)
    if 'chatId' not in sender_data:
        raise NotificationValidationError(
            "Notification senderData missing required 'chatId' field.\n"
            "The whatsapp-chatbot-python SDK requires chatId to route responses.\n"
            "SDK calls: notification.get_chat() -> event['senderData']['chatId']\n"
            f"Current senderData keys: {list(sender_data.keys())}\n"
            f"Current senderData: {sender_data}\n"
            "\n"
            "Fix: Ensure test fixtures include chatId in senderData.\n"
            "Real Green API webhooks ALWAYS include chatId.\n"
            "For 1-on-1 chats: chatId should equal sender field."
        )
    
    # Check chatId is not empty
    chat_id = sender_data['chatId']
    if not chat_id or not str(chat_id).strip():
        raise NotificationValidationError(
            f"Notification senderData has empty chatId: '{chat_id}'. "
            "chatId must be a non-empty string to route responses."
        )
