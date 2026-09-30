"""
react_to_message / send_progress_update actions shared by the legacy AIHandler
and the Feature 063 backbone. Moved out of handlers/ai_handler.py with their
bodies unchanged - one implementation, used by both paths.
"""
import logging
from typing import Any, Dict, Optional

from src.utils.green_api_bot import send_reaction

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
            if session.active_document_message_id:
                return session.active_document_message_id
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(f"[084] Could not resolve active_document_message_id: {e}")

    return getattr(request.original_message, "whatsapp_id_message", None)


def build_react_to_message_payload(
    green_api_bot, session_manager, request, effective_chat_id: Optional[str],
    arguments: Dict[str, Any], call_id: str,
) -> Dict[str, Any]:
    """One parsed react_to_message call: resolves the target message, sends the
    reaction, and returns the tool's output payload ({"status": "ok"|"failed"})."""
    emoji = arguments.get("emoji", "")
    explicit_message_id = arguments.get("message_id")
    target_id = resolve_react_to_message_target(
        session_manager, request, effective_chat_id, explicit_message_id
    )
    if not target_id or not effective_chat_id or green_api_bot is None:
        logger.warning(
            f"[084] react_to_message call {call_id!r}: nothing to react "
            f"through (target_id={target_id!r}, chat_id={effective_chat_id!r}, "
            f"green_api_bot_set={green_api_bot is not None})"
        )
        return {"status": "failed"}

    success = send_reaction(green_api_bot, effective_chat_id, target_id, emoji)
    return {"status": "ok" if success else "failed"}


def send_progress_update_message(callback, builder, chat_id, text) -> bool:
    """Sends one interim progress message through the turn's active callback;
    returns whether it was sent. Best-effort - never raises."""
    sent = False
    if text and callback is not None:
        try:
            # The callback itself (denidin.py's _progress_callback_with_typing_refresh,
            # the only concrete callback ever passed in) already wire-logs both the
            # 'out' send and its 'in' result - logging again here duplicated every
            # progress update's 'out' line in the wire log (found 2026-09-29, via
            # debug_exact_calls trace review: a "sent it twice?" question that turned
            # out to be a logging-only duplicate, not a real double send).
            callback(text)
            sent = True
            if builder is not None:
                builder.mark_progress_update_sent()
        except Exception as e:  # pylint: disable=broad-except
            # Best-effort, per runtime_constitution.md: a failed interim send must
            # never fail the turn - the real final answer still has to go out below.
            logger.warning(f"[080] send_progress_update: failed to send interim message: {e}")
    elif not text:
        logger.warning("[080] send_progress_update called with no text argument - nothing sent")
    else:
        logger.debug("[080] send_progress_update called but no progress_callback is active - nothing sent")
    return sent
