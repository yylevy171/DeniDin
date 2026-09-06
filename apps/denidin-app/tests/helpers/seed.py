"""`seed_message` — append a message dated N calendar days in the past (Feature 070).

Uses the real production `SessionManager.add_message_with_tokens(timestamp=...)`
seam (added in T013b, tested by T012a) — no internal mocks, no hand-written JSON.
The message's persisted `timestamp` field lands N Israel-local calendar days
before "now", which is what the rolling window and the nightly roll bucket on.
"""
from datetime import timedelta
from typing import Optional

from src.utils.time_utils import now_local


def seed_message(
    session_manager,
    chat: str,
    role: str,
    content: str,
    days_ago: int,
    *,
    user_role: str = "godfather",
    sender_name: Optional[str] = None,
    at=None,
) -> str:
    """Append one message to `chat`'s session with a timestamp `days_ago`
    calendar days before `at` (default: now). Returns the message id."""
    base = at or now_local()
    ts = base - timedelta(days=days_ago)
    return session_manager.add_message_with_tokens(
        chat_id=chat,
        role=role,
        content=content,
        user_role=user_role,
        sender_name=sender_name,
        timestamp=ts,
    )
