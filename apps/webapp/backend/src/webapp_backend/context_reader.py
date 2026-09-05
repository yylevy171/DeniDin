"""Left-panel context: the session/message window around a ledger event's source message,
plus opaque media-token resolution.

Reads denidin-app's on-disk session layout directly (documented in ``data-model.md``):
``{data_root}/sessions/{sid}/session.json`` + ``.../messages/{mid}.json`` for recent messages
+ ``.../archived/{mid}.json`` for messages SessionManager has pruned out of the live token
window (still session history — a ledger event's source message is usually here), with whole
archived sessions under ``{data_root}/sessions/expired/{YYYY-MM-DD}/{sid}/``. This is a deliberate,
dependency-isolated read (same spirit as ``research.md`` §5's direct ``_index`` access) —
importing ``SessionManager`` would drag ``tiktoken`` + the model layer into a read-only app.
"""
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

_MAX_LOOKBACK = 60


def _parse_ts(raw: Any) -> Optional[datetime]:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return datetime.fromisoformat(raw.strip())
    except ValueError:
        return None


class ContextReader:
    def __init__(self, data_root: str) -> None:
        self._root = Path(data_root).resolve()
        self._sessions = self._root / "sessions"
        self._media_tokens: Dict[str, Path] = {}

    # --- session/message resolution -------------------------------------------------

    def _find_session_dir(self, session_id: str) -> Optional[Path]:
        if not session_id:
            return None
        active = self._sessions / session_id
        if (active / "session.json").is_file():
            return active
        expired_root = self._sessions / "expired"
        if expired_root.is_dir():
            for day_dir in sorted(expired_root.iterdir(), reverse=True):
                candidate = day_dir / session_id
                if (candidate / "session.json").is_file():
                    return candidate
        return None

    def _mint_media_token(self, image_path: str) -> Optional[str]:
        target = (self._root / image_path).resolve()
        try:
            target.relative_to(self._root)
        except ValueError:
            return None  # path-traversal containment (research.md §3)
        if not target.is_file():
            return None
        token = secrets.token_urlsafe(24)
        self._media_tokens[token] = target
        return token

    def resolve_media(self, token: str) -> Optional[Path]:
        path = self._media_tokens.get(token)
        if path is None:
            return None
        try:
            path.resolve().relative_to(self._root)
        except ValueError:
            return None
        return path if path.is_file() else None

    def build_context(
        self, session_id: Optional[str], message_id: Optional[str], lookback_minutes: int = 10
    ) -> Dict[str, Any]:
        lookback = max(0, min(int(lookback_minutes), _MAX_LOOKBACK))
        session_dir = self._find_session_dir(session_id or "")
        if session_dir is None:
            return {"error": "context_unavailable",
                    "message": "The conversation for this event is no longer available."}

        # SessionManager keeps a session's recent messages in messages/ and prunes older ones
        # (out of the live token window) into archived/ — both are still part of the session's
        # history. A ledger event's source message is usually old, so it's almost always in
        # archived/; read both, live copy wins on any message_id collision.
        by_id: Dict[str, Dict[str, Any]] = {}
        for sub in ("archived", "messages"):
            sub_dir = session_dir / sub
            if not sub_dir.is_dir():
                continue
            for msg_file in sub_dir.glob("*.json"):
                try:
                    msg = json.loads(msg_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                mid = msg.get("message_id") or msg_file.stem
                by_id[mid] = msg
        raw_messages: List[Dict[str, Any]] = list(by_id.values())

        anchor = next((m for m in raw_messages if m.get("message_id") == message_id), None)
        if anchor is None:
            return {"error": "context_unavailable",
                    "message": "The source message for this event could not be found."}

        anchor_ts = _parse_ts(anchor.get("timestamp"))
        # Window spans BOTH directions around the anchor: the event's trigger message and the
        # bot's confirmation/capture reply that follows it are both needed to make sense of a
        # capture (2026-09-05 feedback).
        if anchor_ts:
            window_start = anchor_ts - timedelta(minutes=lookback)
            window_end = anchor_ts + timedelta(minutes=lookback)
        else:
            window_start = window_end = None

        selected = []
        for m in raw_messages:
            ts = _parse_ts(m.get("timestamp"))
            if anchor_ts and ts is not None:
                if ts < window_start or ts > window_end:  # inclusive both ends
                    continue
            elif m.get("message_id") != message_id:
                continue
            selected.append((ts, m))

        selected.sort(key=lambda t: (t[0] is None, t[0] or datetime.min))

        out_messages = []
        for ts, m in selected:
            role = m.get("role") or "user"
            if role == "assistant":
                sender_name = "דני דין"
            else:
                sender_name = m.get("sender_name") or m.get("sender")
            entry = {
                "message_id": m.get("message_id"),
                "role": role,
                "side": "left" if role == "assistant" else "right",
                "content": m.get("content") or "",
                "timestamp": m.get("timestamp"),
                "sender_name": sender_name,
            }
            image_path = m.get("image_path")
            if isinstance(image_path, str) and image_path.strip():
                token = self._mint_media_token(image_path)
                if token:
                    entry["media_url"] = f"/api/media/{token}"
            out_messages.append(entry)

        return {
            "session_id": session_id,
            "messages": out_messages,
            "lookback_minutes_used": lookback,
        }
