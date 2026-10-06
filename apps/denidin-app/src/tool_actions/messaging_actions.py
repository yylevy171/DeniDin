"""
react_to_message / send_progress_update actions shared by the legacy AIHandler
and the Feature 063 backbone. Moved out of handlers/ai_handler.py with their
bodies unchanged - one implementation, used by both paths.
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def resolve_react_to_message_target(
    session_manager, request, effective_chat_id: Optional[str], explicit_message_id: Optional[str],
) -> Optional[str]:
    """Feature 084's message_id resolution fallback chain (data-model.md):
    explicit arg -> Session.active_document_message_id -> the current turn's
    own Message.whatsapp_id_message. Returns None if nothing resolves (no
    real wire id available at any level - e.g. a replay/test message with no
    original notification)."""
    if explicit_message_id:
        return explicit_message_id

    if effective_chat_id:
        try:
            session = session_manager.get_session(effective_chat_id)
            active_document_message_id: Optional[str] = session.active_document_message_id
            if active_document_message_id:
                return active_document_message_id
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(f"[084] Could not resolve active_document_message_id: {e}")

    return getattr(request.original_message, "whatsapp_id_message", None)


def build_react_to_message_payload(
    denidin, request, effective_chat_id: Optional[str], arguments: Dict[str, Any], call_id: str,
) -> Dict[str, Any]:
    """One parsed react_to_message call: resolves the target message, sends the
    reaction (DeniDin.send_reaction), and returns the tool's output payload
    ({"status": "ok"|"failed"})."""
    emoji = arguments.get("emoji", "")
    explicit_message_id = arguments.get("message_id")
    session_manager = getattr(denidin, "session_manager", None)
    target_id = resolve_react_to_message_target(
        session_manager, request, effective_chat_id, explicit_message_id
    )
    if not target_id or not effective_chat_id:
        logger.warning(
            f"[084] react_to_message call {call_id!r}: nothing to react "
            f"to (target_id={target_id!r}, chat_id={effective_chat_id!r})"
        )
        return {"status": "failed"}

    success = denidin.send_reaction(effective_chat_id, target_id, emoji)
    return {"status": "ok" if success else "failed"}


def send_progress_update_message(denidin, builder, chat_id: Optional[str], text: Optional[str]) -> bool:
    """Sends one interim progress message in the turn in progress in `chat_id`
    (DeniDin.send_progress_update - which wire-logs and stores it); returns whether it
    was sent. Best-effort - never raises."""
    if not text:
        logger.warning("[080] send_progress_update called with no text argument - nothing sent")
        return False
    try:
        sent = bool(denidin.send_progress_update(chat_id, text))
    except Exception as e:  # pylint: disable=broad-except
        # Best-effort, per runtime_constitution.md: a failed interim send must
        # never fail the turn - the real final answer still has to go out below.
        logger.warning(f"[080] send_progress_update: failed to send interim message: {e}")
        return False
    if sent and builder is not None:
        builder.mark_progress_update_sent()
    return sent
