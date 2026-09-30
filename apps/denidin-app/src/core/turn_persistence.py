"""
The ONE place a finished turn is written to the chat's session (2026-09-30
consolidation). Previously three drifting copies existed - AIHandler._persist_turn
(text turns), MediaHandler._store_media_turn (legacy media turns), and the
Backbone's own _persist_turn - and the Backbone's copy had already lost
whatsapp_id_message, ledger_event_ids, interim progress messages and the
player-replay reply offset. All three are now thin wrappers over persist_turn().
"""
import logging
from typing import Any, Dict, List, Optional

from src.core.model_calls import sane_source_epoch
from src.utils.time_utils import local_from_timestamp

logger = logging.getLogger(__name__)

# A WhatsApp-export player replay stores the reply this many seconds after the
# replayed operator message, so it sorts just after the turn it answers.
REPLAY_REPLY_OFFSET_SECONDS = 10


def resolve_user_role(user_manager: Any, rbac_enabled: bool, phone: Optional[str]) -> Any:
    """The persisted role for a turn: the sender's real RBAC role when RBAC is on
    and the phone is known, else "client" - same fallback every path always used."""
    if rbac_enabled and user_manager and phone:
        return user_manager.get_user(phone).role
    return "client"


def persist_turn(session_manager: Any, *, chat_id: Optional[str], user_role: Any,
                 count_tokens: bool, own_whatsapp_number: Optional[str],
                 user_text: str, reply_text: Optional[str], should_reply: bool,
                 sender_phone: Optional[str], sender_display: Optional[str],
                 user_phone: Optional[str] = None, is_group: bool = False,
                 chat_name: Optional[str] = None, source_timestamp: Optional[int] = None,
                 replayed: bool = False, message_id: Optional[str] = None,
                 whatsapp_id_message: Optional[str] = None,
                 ledger_event_ids: Optional[List[str]] = None,
                 mcp_calls: Optional[List[Dict]] = None,
                 image_path: Optional[str] = None, extracted_text: Optional[str] = None,
                 interim_messages: Optional[List[str]] = None,
                 trailing_notes: Optional[List[str]] = None) -> None:
    """Stores one turn in `chat_id`'s session, in the order the user saw it:

    1. the user's message (`user_text`, with message_id / whatsapp_id_message /
       ledger_event_ids / image_path / extracted_text attached to it only);
    2. every interim progress message actually sent this turn (`interim_messages`
       - consumed: the list is cleared so a second call can't store them twice);
    3. the reply (`reply_text`, with `mcp_calls`) - only when `should_reply`
       (a [[NO_REPLY]] turn stores no assistant message);
    4. `trailing_notes` - extra assistant-side entries stored regardless of
       should_reply (the Backbone's [[INTERNAL_PLANNING_NOTE]]).

    Addressing (2026-08-19): Message.sender/.recipient are real WhatsApp JIDs,
    *_name the display names. A group message is addressed to the group itself,
    never to one member or to DeniDin alone. The sender JID is `sender_phone`
    (the ACTUAL sender), falling back to `user_phone` and then - 1:1 only - to
    `chat_id` (Green API's 1:1 chatId IS the contact's JID).

    Timestamps (Feature 069): the source epoch (Green API send time, or the
    player's original conversation time) when plausible, else processing time;
    a replayed reply is offset by REPLAY_REPLY_OFFSET_SECONDS.

    `count_tokens` selects add_message_with_tokens (updates the session's token
    total) over add_message. Never raises: a storage failure is logged and must
    not affect the reply."""
    if not (session_manager and chat_id):
        return
    try:
        own_number_jid = f"{own_whatsapp_number}@c.us" if own_whatsapp_number else None
        resolved_sender = sender_phone or user_phone or (chat_id if not is_group else None)
        user_recipient = chat_id if is_group else own_number_jid
        user_recipient_name = (chat_name or chat_id) if is_group else "DeniDin"
        reply_recipient = chat_id if is_group else resolved_sender
        reply_recipient_name = (chat_name or chat_id) if is_group else sender_display

        epoch = sane_source_epoch(source_timestamp)
        user_ts = None if epoch is None else local_from_timestamp(epoch)
        reply_ts = None if epoch is None else local_from_timestamp(
            epoch + (REPLAY_REPLY_OFFSET_SECONDS if replayed else 0)
        )

        add = session_manager.add_message_with_tokens if count_tokens else session_manager.add_message

        add(
            chat_id=chat_id, role="user", content=user_text, user_role=user_role,
            sender=resolved_sender, sender_name=sender_display,
            recipient=user_recipient, recipient_name=user_recipient_name,
            ledger_event_ids=ledger_event_ids, message_id=message_id,
            image_path=image_path, extracted_text=extracted_text,
            timestamp=user_ts, whatsapp_id_message=whatsapp_id_message,
        )

        if interim_messages:
            texts = list(interim_messages)
            interim_messages.clear()
            for text in texts:
                session_manager.add_message(
                    chat_id=chat_id, role="assistant", content=text, user_role=user_role,
                    sender=own_number_jid, sender_name="DeniDin",
                    recipient=reply_recipient, recipient_name=reply_recipient_name,
                    timestamp=reply_ts,
                )

        if should_reply:
            add(
                chat_id=chat_id, role="assistant", content=reply_text, user_role=user_role,
                sender=own_number_jid, sender_name="DeniDin",
                recipient=reply_recipient, recipient_name=reply_recipient_name,
                mcp_calls=mcp_calls, timestamp=reply_ts,
            )

        for note in trailing_notes or []:
            add(
                chat_id=chat_id, role="assistant", content=note, user_role=user_role,
                sender=own_number_jid, sender_name="DeniDin",
                recipient=reply_recipient, recipient_name=reply_recipient_name,
                timestamp=reply_ts,
            )

        storage_note = (
            " + assistant reply" if should_reply
            else " (no-reply sentinel, no assistant message stored)"
        )
        logger.debug(f"Stored user message{storage_note} in session {chat_id}")
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"Failed to store messages in session: {e}", exc_info=True)
