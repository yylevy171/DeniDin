"""
The chat's session log (2026-09-30): every WhatsApp message is stored the moment
it crosses the boundary - a message from the user as soon as it's received, a
message to the user right after it's successfully sent. Nothing is batched until
"the end of the turn", so nothing can be lost when a turn fails partway, and there
is no separate notion of interim/progress messages: each is just a message.

Facts learned later (a media file's saved path, its extracted text, ledger event
ids) are filled into the already-stored message via update(). Reactions and typing
indicators are not messages - they're only wire-logged, never stored here.

One instance per app (denidin.py's initialize_app), shared by the legacy AIHandler
path, the Backbone, WhatsAppHandler and MediaHandler.
"""
import logging
from typing import Any, Dict, List, Optional

from src.core.model_calls import sane_source_epoch
from src.utils.time_utils import local_from_timestamp

logger = logging.getLogger(__name__)

# A WhatsApp-export player replay stores DeniDin's reply this many seconds after
# the replayed message it answers, so replayed history keeps its original order.
REPLAY_REPLY_OFFSET_SECONDS = 10


class ChatLog:
    """Stores inbound/outbound WhatsApp messages in the chat's session. Every method
    is best-effort: a storage failure is logged and never affects the conversation."""

    def __init__(self, session_manager: Any, user_manager: Any, *, rbac_enabled: bool,
                 own_whatsapp_number: Optional[str] = None):
        self.session_manager = session_manager
        self.user_manager = user_manager
        self.rbac_enabled = rbac_enabled
        # Bare digits (bugfix-024's getWaSettings call), resolved once at startup;
        # "" / None when unresolved (no live Green API client, e.g. the player).
        self.own_whatsapp_number = own_whatsapp_number

    @property
    def _own_jid(self) -> Optional[str]:
        return f"{self.own_whatsapp_number}@c.us" if self.own_whatsapp_number else None

    def _role(self, phone: Optional[str]) -> Any:
        """The stored role: the user's real RBAC role when known, else "client"."""
        if self.rbac_enabled and self.user_manager and phone:
            return self.user_manager.get_user(phone).role
        return "client"

    def store_inbound(self, message: Any, *, content: Optional[str] = None,
                      internal: bool = False) -> Optional[str]:
        """Stores a message received from the user (a WhatsAppMessage), under its own
        `message.message_id`, the moment it arrives. `content` defaults to
        message.text_content. A group message is addressed to the group itself.

        `internal=True` marks content DeniDin generated on the user's behalf (the
        Feature 069 ledger-stash turn) - stored without the WhatsApp idMessage, since
        it isn't the user's WhatsApp message itself.

        A Green API redelivery of a message already stored (same idMessage) is not
        stored twice. Returns the stored message_id, or None if nothing was stored."""
        if not (self.session_manager and message.chat_id):
            return None
        try:
            whatsapp_id = None if internal else getattr(message, "whatsapp_id_message", None)
            if whatsapp_id and self.session_manager.has_whatsapp_id_message(message.chat_id, whatsapp_id):
                logger.info(f"Inbound message {whatsapp_id} already stored for {message.chat_id} - not storing again")
                return None
            epoch = sane_source_epoch(message.timestamp)
            return str(self.session_manager.add_message_with_tokens(
                chat_id=message.chat_id, role="user",
                content=message.text_content if content is None else content,
                user_role=self._role(message.sender_id),
                sender=message.sender_id, sender_name=message.sender_display_name,
                recipient=message.chat_id if message.is_group else self._own_jid,
                recipient_name=(message.chat_name or message.chat_id) if message.is_group else "DeniDin",
                message_id=message.message_id,
                timestamp=None if epoch is None else local_from_timestamp(epoch),
                whatsapp_id_message=whatsapp_id,
            ))
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Failed to store inbound message for {getattr(message, 'chat_id', None)}: {e}",
                         exc_info=True)
            return None

    def store_outbound(self, reply_to: Any, content: str, *,
                       whatsapp_id_message: Optional[str] = None,
                       mcp_calls: Optional[List[Dict]] = None) -> Optional[str]:
        """Stores a message DeniDin just sent in the conversation of `reply_to` (the
        inbound WhatsAppMessage it answers - used only for addressing and the stored
        role). Call right AFTER a successful send, never for a failed one: the stored
        log is what the user actually saw. Timestamp is the send time (now); for a
        player replay, the replayed message's own time + REPLAY_REPLY_OFFSET_SECONDS."""
        if not (self.session_manager and reply_to.chat_id and content):
            return None
        try:
            timestamp = None
            if getattr(reply_to, "is_replay", False):
                epoch = sane_source_epoch(reply_to.timestamp)
                if epoch is not None:
                    timestamp = local_from_timestamp(epoch + REPLAY_REPLY_OFFSET_SECONDS)
            return str(self.session_manager.add_message_with_tokens(
                chat_id=reply_to.chat_id, role="assistant", content=content,
                user_role=self._role(reply_to.sender_id),
                sender=self._own_jid, sender_name="DeniDin",
                recipient=reply_to.chat_id if reply_to.is_group else reply_to.sender_id,
                recipient_name=(reply_to.chat_name or reply_to.chat_id) if reply_to.is_group
                else reply_to.sender_display_name,
                mcp_calls=mcp_calls, timestamp=timestamp,
                whatsapp_id_message=whatsapp_id_message,
            ))
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Failed to store outbound message for {getattr(reply_to, 'chat_id', None)}: {e}",
                         exc_info=True)
            return None

    def store_outbound_to_chat(self, chat_id: str, content: str) -> Optional[str]:
        """Stores a message just sent to `chat_id` when there's no inbound message to
        address it from (e.g. a generated document sent by a tool) - addressed to the
        chat itself."""
        if not (self.session_manager and chat_id and content):
            return None
        try:
            return str(self.session_manager.add_message_with_tokens(
                chat_id=chat_id, role="assistant", content=content,
                user_role=self._role(chat_id if chat_id.endswith("@c.us") else None),
                sender=self._own_jid, sender_name="DeniDin",
                recipient=chat_id, recipient_name=chat_id,
            ))
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Failed to store outbound message for {chat_id}: {e}", exc_info=True)
            return None

    def store_note(self, reply_to: Any, content: str) -> Optional[str]:
        """Stores an internal assistant-side note that is never sent to the user (the
        Backbone's [[INTERNAL_PLANNING_NOTE]]) at the moment it's produced - same
        addressing as store_outbound."""
        return self.store_outbound(reply_to, content)

    def update(self, chat_id: Optional[str], message_id: Optional[str], **fields: Any) -> bool:
        """Fills facts learned after a message was stored (image_path, extracted_text,
        ledger_event_ids, mcp_calls) into it. False - never raises - on any failure."""
        if not (self.session_manager and chat_id and message_id and fields):
            return False
        try:
            return bool(self.session_manager.update_message(chat_id, message_id, **fields))
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Failed to update message {message_id} in {chat_id}: {e}", exc_info=True)
            return False
