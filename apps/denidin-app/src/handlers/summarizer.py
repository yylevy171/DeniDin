"""Conversation summarizer (Feature 070).

`summarize_conversation` is the module-level lift of the call shape that used to
live inside the now-deleted ``AIHandler.transfer_session_to_long_term_memory``
(``ai_handler.py`` pre-Feature-070). It is usable without an ``AIHandler``
instance so both the nightly ``daily_summary_roll_service`` and the standalone
``apps/rolling-memory-backfill`` sub-app can call it.

**No new prompt** — the instruction string is the existing session-summary one,
verbatim (Out of Scope forbids prompt-format churn; research.md D13).

**No side effects** — this function does not embed, does not write ChromaDB,
does not touch roll markers. The caller owns all persistence.
"""
from typing import Dict, List

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Lifted verbatim from the retired AIHandler.transfer_session_to_long_term_memory.
_SUMMARIZER_INSTRUCTIONS = (
    "You are a conversation summarizer that extracts both explicit and implicit "
    "information. Start your summary by listing key facts as bullet points (e.g., "
    "names, preferences, decisions, entities mentioned). Then provide context, "
    "relationships, and logical deductions. Make information easily retrievable "
    "for future questions. Keep summaries under 500 words."
)


def _render_transcript(messages: List[Dict]) -> str:
    """`"{role}: {content}"` per line, oldest-first — the exact rendering the
    retired method used. Group items may already carry a ``[sender_name]``
    prefix inside ``content``; that is left as-is."""
    return "\n".join(
        f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages
    )


def summarize_conversation(client, model: str, messages: List[Dict]) -> str:
    """Summarize an oldest-first conversation slice into a single string.

    Args:
        client: an OpenAI client (``openai.OpenAI(...)``). The caller owns
            construction / ``max_retries`` / timeouts.
        model: ``config.ai_model`` (e.g. ``gpt-5.6-luna``).
        messages: oldest-first, in the shape ``get_messages_for_local_date`` /
            ``get_rolling_window`` return (at least ``role`` + ``content``).
            Never empty — the caller skips empty days before calling.

    Returns:
        The model's summary on success; on **any** exception from the OpenAI
        call, the raw ``"{role}: {content}"`` transcript (the historical
        ``used_fallback=True`` degradation). This function therefore does not
        raise for an ordinary OpenAI failure — a fallback transcript is still a
        durable, useful daily record.
    """
    conv_text = _render_transcript(messages)
    try:
        resp = client.responses.create(
            model=model,
            instructions=_SUMMARIZER_INSTRUCTIONS,
            input=f"Summarize this conversation, leading with facts then inferences:\n\n{conv_text}",
            max_output_tokens=1000,
        )
        return (resp.output_text or "").strip() or conv_text
    except Exception as e:  # pylint: disable=broad-except
        logger.warning(
            "summarize_conversation: OpenAI call failed (%s) - using raw transcript fallback",
            e,
        )
        return conv_text
