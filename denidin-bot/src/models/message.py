"""
Message models for WhatsApp and AI interactions.
Includes WhatsAppMessage, AIRequest, and AIResponse.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any
import uuid


@dataclass
class WhatsAppMessage:
    """Model representing a WhatsApp message."""
    
    message_id: str
    chat_id: str
    sender_id: str
    sender_name: str
    text_content: str
    timestamp: int
    message_type: str
    is_group: bool

    @classmethod
    def from_notification(cls, notification) -> 'WhatsAppMessage':
        """
        Parse a WhatsApp notification into a WhatsAppMessage.
        
        Args:
            notification: Notification object from Green API
            
        Returns:
            WhatsAppMessage instance
        """
        event = notification.event
        message_data = event.get('messageData', {})
        sender_data = event.get('senderData', {})
        
        # Extract text content
        text_message_data = message_data.get('textMessageData', {})
        text_content = text_message_data.get('textMessage', '')
        
        # Extract sender info
        chat_id = sender_data.get('chatId', '')
        sender_id = sender_data.get('sender', '')
        sender_name = sender_data.get('senderName', '')
        
        # Detect if it's a group chat (group chats have @g.us in chat_id)
        is_group = '@g.us' in chat_id
        
        # Extract message metadata
        message_type = message_data.get('typeMessage', 'textMessage')
        timestamp = event.get('timestamp', int(datetime.now().timestamp()))
        
        # Generate message ID (could use idMessage from event if available)
        message_id = event.get('idMessage', f"msg_{uuid.uuid4().hex[:12]}")
        
        return cls(
            message_id=message_id,
            chat_id=chat_id,
            sender_id=sender_id,
            sender_name=sender_name,
            text_content=text_content,
            timestamp=timestamp,
            message_type=message_type,
            is_group=is_group
        )


@dataclass
class AIRequest:
    """Model representing a request to the AI service."""
    
    request_id: str
    user_message: str
    system_message: str
    max_tokens: int
    temperature: float
    timestamp: datetime

    def to_openai_payload(self) -> Dict[str, Any]:
        """
        Convert AIRequest to OpenAI API payload format.
        
        Returns:
            Dictionary in OpenAI API format
        """
        return {
            'messages': [
                {
                    'role': 'system',
                    'content': self.system_message
                },
                {
                    'role': 'user',
                    'content': self.user_message
                }
            ],
            'max_tokens': self.max_tokens,
            'temperature': self.temperature
        }


@dataclass
class AIResponse:
    """Model representing a response from the AI service."""
    
    response_text: str
    finish_reason: str
    tokens_used: int
    timestamp: datetime
    is_truncated: bool = False

    @classmethod
    def from_openai_response(cls, response) -> 'AIResponse':
        """
        Parse an OpenAI API response into an AIResponse.
        
        Args:
            response: Response object from OpenAI API
            
        Returns:
            AIResponse instance
        """
        # Extract response text
        response_text = response.choices[0].message.content
        
        # Extract metadata
        finish_reason = response.choices[0].finish_reason
        tokens_used = response.usage.total_tokens
        
        # Check if truncation will be needed
        is_truncated = len(response_text) > 4000
        
        return cls(
            response_text=response_text,
            finish_reason=finish_reason,
            tokens_used=tokens_used,
            timestamp=datetime.now(),
            is_truncated=is_truncated
        )

    def truncate_for_whatsapp(self) -> str:
        """
        Truncate response text to fit WhatsApp's 4000 character limit.
        
        Returns:
            Truncated text with "..." appended if needed
        """
        if len(self.response_text) > 4000:
            self.is_truncated = True
            return self.response_text[:4000] + '...'
        return self.response_text
