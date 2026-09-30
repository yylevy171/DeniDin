"""
The per-turn context both message paths feed the model (2026-09-30
consolidation): the Feature 070 rolling conversation window and the long-term
`daily_summary` memory recall. Previously AIHandler and the Backbone each had
their own copy; both now call these.
"""
import logging
from typing import Any, Dict, List, Optional

from src.managers.memory_collections import collection_name_for_chat

logger = logging.getLogger(__name__)

RECALLED_MEMORIES_HEADER = "RECALLED MEMORIES (from past conversations):\n"


def load_rolling_window(session_manager: Any, chat_id: Optional[str], *,
                        window_days: int, max_tokens: int) -> List[Dict[str, Any]]:
    """Feature 070: the chat's rolling verbatim window (oldest-first
    {"role", "content"} dicts, trimmed oldest-first to `max_tokens`, read-only).
    Returns [] - never raises - when there's no session manager/chat or the read
    fails: a turn with no history is degraded, not crashed."""
    if not (session_manager and chat_id):
        return []
    try:
        history = session_manager.get_rolling_window(
            chat_id, window_days=window_days, max_tokens=max_tokens,
        )
        if history:
            logger.info(f"Retrieved {len(history)} messages from session history")
        return list(history) if history else []
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"Failed to retrieve conversation history: {e}", exc_info=True)
        return []


def recall_memory_context(memory_manager: Any, *, query: str, chat_id: Optional[str],
                          top_k: int, min_similarity: float,
                          user_manager: Any = None, user_phone: Optional[str] = None) -> str:
    """One semantic-similarity recall over this chat's `daily_summary`
    collection, formatted as the RECALLED MEMORIES block (header + one
    "- <content> (relevance: 0.NN)" line per memory). RBAC-filtered by the
    user's allowed_memory_scopes/can_see_all_memories when `user_manager` and
    `user_phone` are given, else a plain recall. Returns "" - never raises - when
    there's no query (e.g. a media message without a caption), nothing relevant
    is found, or recall fails."""
    if memory_manager is None or not chat_id or not query:
        return ""
    try:
        collection_name = collection_name_for_chat(chat_id)
        if user_manager is not None and user_phone:
            user = user_manager.get_user(user_phone)
            recalled = memory_manager.recall_with_rbac_filter(
                query=query,
                collection_names=[collection_name],
                user_phone=user_phone,
                allowed_scopes=user.allowed_memory_scopes,
                can_see_all_memories=user.can_see_all_memories,
                top_k=top_k,
                min_similarity=min_similarity,
            )
        else:
            recalled = memory_manager.recall(
                query=query,
                collection_names=[collection_name],
                top_k=top_k,
                min_similarity=min_similarity,
            )
        if not recalled:
            return ""
        logger.info(f"Recalled {len(recalled)} memories for {chat_id}")
        return RECALLED_MEMORIES_HEADER + "".join(
            f"- {mem['content']} (relevance: {mem['similarity']:.2f})\n" for mem in recalled
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"Failed to recall memories: {e}", exc_info=True)
        return ""
