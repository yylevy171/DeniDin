"""RollMarkerStore - idempotency ledger for the nightly daily-summary roll (Feature 070).

One SQLite row per ``(chat, date)`` records whether that calendar day has been
rolled into a ChromaDB ``daily_summary`` record yet. ``PRIMARY KEY(chat, date)``
+ ``sqlite3.IntegrityError`` is the *only* synchronization primitive - valid
across two scheduler ticks (kept from overlapping by the job's
``max_instances=1``) and across the scheduler vs. a hand-run backfill in a
separate process (the primary-key ``INSERT`` is atomic in SQLite regardless of
process). No app-level mutex, no lockfile.

Claim-first two-phase protocol (REQ-MEM-025, REQ-MEM-026):

    try_claim()  -> INSERT status='claimed'      (a racer wins here)
    ... summarize + remember() ...
    commit()     -> UPDATE status='committed'    (only the winner, only after
                                                  the summary is durably stored
                                                  or the day is confirmed empty)

A process that dies between ``try_claim`` and ``commit`` leaves a ``claimed``
row; it becomes re-takeable once ``claimed_at`` is older than
``stale_claim_minutes`` (``memory.roll.stale_claim_minutes``, default 120).

Connection idiom mirrors ``ReminderManager``: one long-lived
``sqlite3.connect(check_same_thread=False)`` opened in ``__init__`` and never
closed, ``row_factory = sqlite3.Row``, idempotent ``executescript`` schema,
``execute`` + immediate ``commit()``. The store never reads ``AppConfiguration``
- the caller composes ``storage_dir`` (a unit test pins this).
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from src.utils.logger import get_logger
from src.utils.time_utils import now_local, to_local

logger = get_logger(__name__)

_DEFAULT_STALE_CLAIM_MINUTES = 120

_SCHEMA = """
CREATE TABLE IF NOT EXISTS roll_markers (
    chat               TEXT NOT NULL,
    date               TEXT NOT NULL,
    status             TEXT NOT NULL,
    message_count      INTEGER,
    summary_memory_id  TEXT,
    source             TEXT NOT NULL,
    claimed_at         TEXT NOT NULL,
    committed_at       TEXT,
    PRIMARY KEY (chat, date)
);
"""


class RollMarkerStore:
    """See module docstring."""

    def __init__(self, storage_dir: str, stale_claim_minutes: int = _DEFAULT_STALE_CLAIM_MINUTES) -> None:
        self._stale_claim_minutes = stale_claim_minutes
        storage_path = Path(storage_dir)
        storage_path.mkdir(parents=True, exist_ok=True)
        self._db_path = storage_path / "roll_markers.db"
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # --- claim / commit ----------------------------------------------------

    def _is_stale_claim(self, row: sqlite3.Row) -> bool:
        if row["status"] != "claimed":
            return False
        try:
            claimed_at = to_local(datetime.fromisoformat(row["claimed_at"]))
        except (TypeError, ValueError):
            return True  # unparseable timestamp - treat as stale, safe to re-take
        return now_local() - claimed_at > timedelta(minutes=self._stale_claim_minutes)

    def try_claim(self, chat: str, date: str, source: str) -> bool:
        """Attempt to claim ``(chat, date)`` for rolling. Returns ``True`` iff
        this caller now owns it and must proceed to ``commit``."""
        now = now_local().isoformat()
        try:
            self._conn.execute(
                "INSERT INTO roll_markers "
                "(chat, date, status, message_count, summary_memory_id, source, claimed_at, committed_at) "
                "VALUES (?, ?, 'claimed', NULL, NULL, ?, ?, NULL)",
                (chat, date, source, now),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            row = self._conn.execute(
                "SELECT * FROM roll_markers WHERE chat = ? AND date = ?", (chat, date)
            ).fetchone()
            if row is None:  # extremely unlikely race - let a later tick retry
                return False
            if row["status"] == "committed":
                return False
            if not self._is_stale_claim(row):
                return False
            # Stale claim - re-take it.
            self._conn.execute(
                "UPDATE roll_markers SET status='claimed', source=?, claimed_at=?, "
                "message_count=NULL, summary_memory_id=NULL, committed_at=NULL "
                "WHERE chat=? AND date=?",
                (source, now, chat, date),
            )
            self._conn.commit()
            return True

    def commit(self, chat: str, date: str, message_count: int, memory_id: Optional[str]) -> None:
        """Mark ``(chat, date)`` committed. Called only by the racer that won
        ``try_claim``, and only after the summary is durably stored (or the day
        is confirmed empty: ``message_count=0``, ``memory_id=None``)."""
        cur = self._conn.execute(
            "UPDATE roll_markers SET status='committed', message_count=?, "
            "summary_memory_id=?, committed_at=? WHERE chat=? AND date=? AND status='claimed'",
            (message_count, memory_id, now_local().isoformat(), chat, date),
        )
        self._conn.commit()
        if cur.rowcount == 0:
            logger.warning(
                "RollMarkerStore.commit: no 'claimed' row for (%s, %s) - no-op", chat, date
            )

    def is_rolled(self, chat: str, date: str) -> bool:
        """``True`` iff a ``committed`` row exists. A ``claimed``-only row is not
        rolled (it will be retried)."""
        row = self._conn.execute(
            "SELECT 1 FROM roll_markers WHERE chat=? AND date=? AND status='committed'",
            (chat, date),
        ).fetchone()
        return row is not None

    def list_markers(self, chat: str) -> List[sqlite3.Row]:
        """All rows for ``chat`` ordered by date (read-only) - the backfill report helper."""
        return self._conn.execute(
            "SELECT * FROM roll_markers WHERE chat=? ORDER BY date", (chat,)
        ).fetchall()
