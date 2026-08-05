"""
Message models for WhatsApp and AI interactions.
Includes WhatsAppMessage, AIRequest, and AIResponse.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
import uuid


def _frame_contact_message_text(contact_message_data: Dict[str, Any]) -> str:
    """Frame a shared WhatsApp contact card's displayName/vcard into readable
    text_content (Feature 030). No dedicated vCard parser - the raw vCard text is
    forwarded verbatim and the model reads its N/FN/TEL/EMAIL lines directly, same
    as it already does for typed add_client requests (research.md Decision 2).
    Confirmed field shape via Green API's official docs
    (contactMessageData.displayName/.vcard)."""
    display_name = contact_message_data.get('displayName', '')
    vcard = contact_message_data.get('vcard', '')
    return (
        "[שותף כרטיס איש קשר בוואטסאפ]\n"
        f"שם תצוגה: {display_name}\n"
        "תוכן vCard:\n"
        f"{vcard}"
    )


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
    is_group: bool = False
    received_timestamp: Optional[datetime] = None  # UTC timestamp when message was received by application
    # Feature 039: resolved human-readable sender name for storage/display, preferring
    # Green API's own WhatsApp-contact-book resolution (senderContactName) over the
    # sender's self-set profile name (senderName) over the raw sender_id - see
    # research.md §4/§4a for why this is not a new contacts-list implementation.
    sender_display_name: str = ""

    @classmethod
    def from_notification(cls, notification) -> 'WhatsAppMessage':
        """
        Parse a WhatsApp notification into a WhatsAppMessage.

        Args:
            notification: Notification object from Green API

        Returns:
            WhatsAppMessage instance
        """
        from datetime import timezone

        event = notification.event
        message_data = event.get('messageData', {})
        sender_data = event.get('senderData', {})

        # Extract message metadata
        message_type = message_data.get('typeMessage', 'textMessage')

        # Extract text content. Forwarded messages, quoted replies, and
        # messages with a link preview arrive as extendedTextMessage, with
        # the body nested under extendedTextMessageData.text instead of
        # textMessageData.textMessage.
        if message_type == 'extendedTextMessage':
            text_content = message_data.get('extendedTextMessageData', {}).get('text', '')
        elif message_type == 'contactMessage':
            text_content = _frame_contact_message_text(message_data.get('contactMessageData', {}))
        else:
            text_content = message_data.get('textMessageData', {}).get('textMessage', '')

        # Extract sender info
        chat_id = sender_data.get('chatId', '')
        sender_id = sender_data.get('sender', '')
        sender_name = sender_data.get('senderName', '')
        sender_display_name = (
            sender_data.get('senderContactName') or sender_name or sender_id
        )

        # Detect if it's a group chat (group chats have @g.us in chat_id)
        is_group = '@g.us' in chat_id
        timestamp = event.get('timestamp', int(datetime.now(timezone.utc).timestamp()))

        # Generate unique message ID (UUID) for tracking throughout lifecycle
        message_id = str(uuid.uuid4())

        # Track when message was received by application (UTC)
        received_timestamp = datetime.now(timezone.utc)

        return cls(
            message_id=message_id,
            chat_id=chat_id,
            sender_id=sender_id,
            sender_name=sender_name,
            text_content=text_content,
            timestamp=timestamp,
            message_type=message_type,
            is_group=is_group,
            received_timestamp=received_timestamp,
            sender_display_name=sender_display_name
        )


@dataclass
class AIRequest:
    """Model representing a request to the AI service."""

    user_prompt: str  # Changed from user_message for consistency
    constitution: str  # Constitution content loaded from file
    max_tokens: int
    model: str
    chat_id: str
    message_id: str
    request_id: str = field(default="")
    timestamp: Optional[int] = None

    def __post_init__(self):
        """Auto-generate fields if not provided"""
        from datetime import timezone
        if not self.request_id:
            self.request_id = f"req_{uuid.uuid4().hex[:12]}"
        if self.timestamp is None:
            self.timestamp = int(datetime.now(timezone.utc).timestamp())

    def to_openai_payload(self) -> Dict[str, Any]:
        """
        Convert AIRequest to OpenAI API payload format.

        Returns:
            Dictionary in OpenAI API format
        """
        return {
            'model': self.model,
            'messages': [
                {
                    'role': 'system',
                    'content': self.constitution
                },
                {
                    'role': 'user',
                    'content': self.user_prompt  # Changed from user_message
                }
            ],
            'max_tokens': self.max_tokens
        }


@dataclass
class AIResponse:
    """Model representing a response from the AI service."""

    request_id: str
    response_text: str
    tokens_used: int
    prompt_tokens: int
    completion_tokens: int
    model: str
    finish_reason: str
    timestamp: int
    is_truncated: bool = False
    # Feature 039: False when AIHandler detected the [[NO_REPLY]] sentinel as this
    # turn's entire response_text - signals denidin.py to skip sending a WhatsApp
    # reply for this turn (the triggering user message is still persisted).
    should_reply: bool = True
    # Feature 018: Morning MCP tool calls made during this response, if any -
    # e.g. [{"name": "create_invoice", "error": None}]. Populated only when the
    # Responses API call had the Morning MCP server attached as a remote tool.
    # Serves both audit logging (REQ-SEC-002) and E2E test verification.
    mcp_calls: List[Dict] = field(default_factory=list)

    @classmethod
    def from_openai_response(cls, response, request_id: Optional[str] = None) -> 'AIResponse':
        """
        Parse an OpenAI API response into an AIResponse.

        Args:
            response: Response object from OpenAI API
            request_id: Optional request ID to associate with response

        Returns:
            AIResponse instance
        """
        # Extract response text
        response_text = response.choices[0].message.content

        # Extract metadata
        finish_reason = response.choices[0].finish_reason
        tokens_used = response.usage.total_tokens
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        model = response.model

        # Check if truncation will be needed
        is_truncated = len(response_text) > 4000

        from datetime import timezone
        return cls(
            request_id=request_id or f"req_{uuid.uuid4().hex[:12]}",
            response_text=response_text,
            tokens_used=tokens_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=model,
            finish_reason=finish_reason,
            timestamp=int(datetime.now(timezone.utc).timestamp()),
            is_truncated=is_truncated
        )

    def truncate_for_whatsapp(self) -> 'AIResponse':
        """
        Truncate response text to fit WhatsApp's 4000 character limit.

        Returns:
            New AIResponse with truncated text if needed
        """
        if len(self.response_text) > 4000:
            truncated_text = self.response_text[:4000] + '...'
            return AIResponse(
                request_id=self.request_id,
                response_text=truncated_text,
                tokens_used=self.tokens_used,
                prompt_tokens=self.prompt_tokens,
                completion_tokens=self.completion_tokens,
                model=self.model,
                finish_reason=self.finish_reason,
                timestamp=self.timestamp,
                is_truncated=True,
                should_reply=self.should_reply,
                mcp_calls=self.mcp_calls
            )
        return self
