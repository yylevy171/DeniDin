"""Left-panel context: the session/message window around a ledger event's source message,
plus opaque media-token resolution.

Reads denidin-app's on-disk session layout directly (documented in ``data-model.md``), with no
import of ``SessionManager`` (that would drag ``tiktoken`` + the model layer into a read-only
app — same dependency-isolation spirit as ``research.md`` §5's direct ``_index`` access).

Resolution is **by ``message_id``, not ``session_id``** (2026-09-06). Feature 070's session
consolidator ("rolling memory window") merges every historical session for a chat into ONE
canonical session dir, so a ledger event's stored ``session_id`` is usually stale after
migration — but ``message_id`` is stable and the message is carried into whichever session now
owns it (live in ``messages/`` or aged-out in ``archived/``, same dir). We therefore build a
``message_id -> session dir`` index across every layout we might encounter:

* current / post-070:  ``{data_root}/sessions/{sid}/{messages,archived}/{mid}.json``
* legacy whole-session archive (pre-070):  ``{data_root}/sessions/expired/{YYYY-MM-DD}/{sid}/…``
* Feature 070 pre-migration raw backup:  ``{data_root}/sessions/_pre070_raw_<date>/`` and
  ``…/_pre070_sessions_archive_<date>/`` — each holding original dirs directly, or under
  ``active/`` / ``expired/{YYYY-MM-DD}/``.

Canonical dirs win over the raw backup on any ``message_id`` collision.
"""
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

_MAX_LOOKBACK = 60

# Pre-migration raw-backup dir name prefixes the session consolidator uses
# (apps/rolling-memory-backfill/consolidate_sessions.py::_RESERVED_DIR_PREFIXES).
_RAW_BACKUP_PREFIXES = ("_pre070_raw_", "_pre070_sessions_archive_")


def _parse_ts(raw: Any) -> Optional[datetime]:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return datetime.fromisoformat(raw.strip())
    except ValueError:
        return None


def _safe_iterdir(path: Path) -> List[Path]:
    try:
        return list(path.iterdir())
    except (OSError, NotADirectoryError):
        return []


class ContextReader:
    def __init__(self, data_root: str) -> None:
        self._root = Path(data_root).resolve()
        self._sessions = self._root / "sessions"
        self._media_tokens: Dict[str, Path] = {}
        # message_id -> session dir. Lazily built, cheaply rebuilt on a miss (denidin-app keeps
        # writing new messages while this read-only app runs).
        self._msg_index: Optional[Dict[str, Path]] = None

    # --- session/message resolution -------------------------------------------------

    @staticmethod
    def _walk_session_json_dirs(base: Path, priority: int, max_depth: int = 4) -> Iterator[Tuple[Path, int]]:
        """Yield ``(dir, priority)`` for every dir holding a ``session.json`` at or below
        ``base`` (bounded depth). Doesn't descend into a session's own ``messages/`` /
        ``archived/`` once found, or past ``max_depth``."""
        stack: List[Tuple[Path, int]] = [(base, 0)]
        while stack:
            current, depth = stack.pop()
            if (current / "session.json").is_file():
                yield current, priority
                continue
            if depth >= max_depth:
                continue
            for child in _safe_iterdir(current):
                if child.is_dir() and child.name not in ("messages", "archived"):
                    stack.append((child, depth + 1))

    def _candidate_session_dirs(self) -> Iterator[Tuple[Path, int]]:
        """Yield ``(session_dir, priority)`` for every dir holding a ``session.json``.
        Lower priority wins on collision: 0 = canonical (``sessions/<sid>/``), 1 = legacy
        whole-session archive (``sessions/expired/<day>/<sid>/``), 2 = Feature 070
        pre-migration raw backup (``sessions/_pre070_raw_<date>/…``)."""
        root = self._sessions
        if not root.is_dir():
            return
        for child in _safe_iterdir(root):
            if not child.is_dir():
                continue
            if (child / "session.json").is_file():
                yield child, 0
            elif child.name == "expired":
                yield from self._walk_session_json_dirs(child, 1)
            elif child.name.startswith(_RAW_BACKUP_PREFIXES):
                yield from self._walk_session_json_dirs(child, 2)

    def _message_index(self, *, rebuild: bool = False) -> Dict[str, Path]:
        if self._msg_index is not None and not rebuild:
            return self._msg_index
        index: Dict[str, Tuple[Path, int]] = {}
        for sdir, priority in self._candidate_session_dirs():
            for sub in ("messages", "archived"):
                sub_dir = sdir / sub
                if not sub_dir.is_dir():
                    continue
                for msg_file in _safe_iterdir(sub_dir):
                    if msg_file.suffix != ".json":
                        continue
                    mid = msg_file.stem
                    prev = index.get(mid)
                    if prev is None or priority < prev[1]:
                        index[mid] = (sdir, priority)
        self._msg_index = {mid: sdir for mid, (sdir, _) in index.items()}
        return self._msg_index

    def _resolve_session_dir(self, message_id: Optional[str]) -> Optional[Path]:
        if not message_id:
            return None
        hit = self._message_index().get(message_id)
        if hit is None:
            hit = self._message_index(rebuild=True).get(message_id)
        return hit

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

        # Events captured by the silent accounting-reconciliation sweep (Feature 025) have no
        # conversation at all — no message_id, a sentinel session_id. That's not a lookup miss.
        if not message_id:
            return {"error": "context_unavailable", "no_conversation": True,
                    "event_session_id": session_id,
                    "message": "This event was captured automatically and has no conversation."}

        # Resolve by message_id, not by the (possibly stale post-Feature-070) session_id.
        session_dir = self._resolve_session_dir(message_id)
        if session_dir is None:
            return {"error": "context_unavailable", "event_session_id": session_id,
                    "message": "The conversation for this event is no longer available."}

        # SessionManager keeps a session's recent messages in messages/ and ages older ones
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

        # The real (resolved) session this message now lives in — may differ from the event's
        # stored session_id after a Feature 070 consolidation.
        resolved_session_id = session_dir.name

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
            "session_id": resolved_session_id,
            "event_session_id": session_id,
            "messages": out_messages,
            "lookback_minutes_used": lookback,
        }
