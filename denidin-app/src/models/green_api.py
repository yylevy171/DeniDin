"""
Green API Webhook Data Models

These models represent the EXACT webhook notification structures as defined by Green API.
Documentation: https://green-api.com/en/docs/api/receiving/notifications-format/

All models match Green API specification precisely for accurate testing and integration.
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
    """Green API sender data object."""
    chatId: str
    sender: str
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


@dataclass
class GreenApiNotification:
    """
    Complete Green API webhook notification object.
    
    This represents the EXACT structure sent by Green API webhooks.
    Use this for integration testing to ensure webhook parsing is correct.
    
    Example for imageMessage:
    {
      "typeWebhook": "incomingMessageReceived",
      "instanceData": {...},
      "timestamp": 1588091580,
      "idMessage": "F7AEC1B7086ECDC7E6E45923F5EDB825",
      "senderData": {...},
      "messageData": {
        "typeMessage": "imageMessage",
        "fileMessageData": {
          "downloadUrl": "https://api.green-api.com/...",
          "caption": "Image",
          "fileName": "example.jpg",
          "mimeType": "image/jpeg"
        }
      }
    }
    """
    typeWebhook: str
    timestamp: int
    idMessage: str
    senderData: SenderData
    messageData: MessageData
    instanceData: Optional[InstanceData] = None
    
    # For compatibility with whatsapp_chatbot_python library's Notification interface
    def __init__(
        self,
        typeWebhook: str,
        timestamp: int,
        idMessage: str,
        senderData: Dict[str, Any],
        messageData: Dict[str, Any],
        instanceData: Optional[Dict[str, Any]] = None
    ):
        self.typeWebhook = typeWebhook
        self.timestamp = timestamp
        self.idMessage = idMessage
        self.instanceData = InstanceData(**instanceData) if instanceData else None
        self.senderData = SenderData(**senderData)
        
        # Build MessageData with nested FileMessageData if present
        msg_data_dict = messageData.copy()
        if 'fileMessageData' in msg_data_dict and msg_data_dict['fileMessageData']:
            msg_data_dict['fileMessageData'] = FileMessageData(**msg_data_dict['fileMessageData'])
        if 'quotedMessage' in msg_data_dict and msg_data_dict['quotedMessage']:
            msg_data_dict['quotedMessage'] = QuotedMessage(**msg_data_dict['quotedMessage'])
        
        self.messageData = MessageData(**msg_data_dict)
        
        # For compatibility with Notification interface: store as 'event' dict
        # The 'event' property should match the full Green API webhook structure
        self.event = {
            'typeWebhook': typeWebhook,
            'timestamp': timestamp,
            'idMessage': idMessage,
            'messageData': messageData,  # Keep original dict with nested structure
            'senderData': senderData
        }
        if instanceData:
            self.event['instanceData'] = instanceData
        
        # Store sent messages for testing
        self._sent_messages = []
    
    def answer(self, message: str) -> None:
        """
        Send response to user (for testing - captures the message).
        This implements the Notification interface for compatibility.
        """
        self._sent_messages.append(message)
    
    def get_sent_message(self) -> Optional[str]:
        """Get the first message sent to user (for test assertions)."""
        return self._sent_messages[0] if self._sent_messages else None
    
    @classmethod
    def create_image_message(
        cls,
        sender: str,
        download_url: str,
        file_name: str = "image.jpg",
        mime_type: str = "image/jpeg",
        caption: str = "",
        sender_name: str = "Test User",
        chat_id: Optional[str] = None
    ) -> "GreenApiNotification":
        """
        Factory method to create a realistic imageMessage webhook notification.
        
        Args:
            sender: WhatsApp ID (e.g., "972501234567@c.us")
            download_url: File download URL
            file_name: Image file name
            mime_type: Image MIME type
            caption: Image caption
            sender_name: Sender display name
            chat_id: Chat ID (defaults to sender for direct messages)
        
        Returns:
            GreenApiNotification with correct nested structure
        """
        chat_id = chat_id or sender
        
        return cls(
            typeWebhook="incomingMessageReceived",
            timestamp=1588091580,
            idMessage="TEST_MESSAGE_ID",
            instanceData={
                "idInstance": 7103000000,
                "wid": "79876543210@c.us",
                "typeInstance": "whatsapp"
            },
            senderData={
                "chatId": chat_id,
                "sender": sender,
                "senderName": sender_name,
                "chatName": sender_name
            },
            messageData={
                "typeMessage": "imageMessage",
                "fileMessageData": {
                    "downloadUrl": download_url,
                    "caption": caption,
                    "fileName": file_name,
                    "mimeType": mime_type,
                    "jpegThumbnail": "",
                    "isForwarded": False,
                    "forwardingScore": 0
                }
            }
        )
    
    @classmethod
    def create_document_message(
        cls,
        sender: str,
        download_url: str,
        file_name: str,
        mime_type: str,
        caption: str = "",
        sender_name: str = "Test User",
        chat_id: Optional[str] = None
    ) -> "GreenApiNotification":
        """
        Factory method to create a realistic documentMessage webhook notification.
        
        Args:
            sender: WhatsApp ID (e.g., "972501234567@c.us")
            download_url: File download URL
            file_name: Document file name
            mime_type: Document MIME type
            caption: Document caption
            sender_name: Sender display name
            chat_id: Chat ID (defaults to sender for direct messages)
        
        Returns:
            GreenApiNotification with correct nested structure
        """
        chat_id = chat_id or sender
        
        return cls(
            typeWebhook="incomingMessageReceived",
            timestamp=1588091580,
            idMessage="TEST_MESSAGE_ID",
            instanceData={
                "idInstance": 7103000000,
                "wid": "79876543210@c.us",
                "typeInstance": "whatsapp"
            },
            senderData={
                "chatId": chat_id,
                "sender": sender,
                "senderName": sender_name,
                "chatName": sender_name
            },
            messageData={
                "typeMessage": "documentMessage",
                "fileMessageData": {
                    "downloadUrl": download_url,
                    "caption": caption,
                    "fileName": file_name,
                    "mimeType": mime_type,
                    "jpegThumbnail": "",
                    "isForwarded": False,
                    "forwardingScore": 0
                }
            }
        )
