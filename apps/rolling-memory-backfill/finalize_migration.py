"""Feature 070 migration — finalize / archive step (Stage 0.3b, task T065).

Pipeline **step 3** of consolidate → backfill → finalize → purge. After the
backfill has written a ``daily_summary`` for every pre-window day, this
physically moves every >14-day message out of ``messages/`` and into
``archived/`` per chat — the exact same ``rename`` the nightly roll would do —
so the app's first ``run_startup_daily_roll_sweep`` finds only the ≤ 2 un-rolled
leftover days and does no bulk archive on boot.

``main(argv=None) -> int``; ``sys.exit(main())``. ``--report-only`` writes
nothing. See ``specs/done/070-rolling-memory-window/consolidator-spec.md`` §2.
"""
import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional

from _denidin_loader import SessionManager, assert_message_integrity, local_calendar_date, now_local

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
logger = logging.getLogger("finalize_migration")

_WINDOW_DAYS = 14
_BACKSTOP_TOKENS = 100000


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="finalize_migration.py",
        description="Feature 070 migration — archive every >14-day message before the app starts.",
    )
    p.add_argument("--data-root", required=True, help="TARGET env's data/ directory (sessions/ under it)")
    p.add_argument("--report-only", action="store_true", help="project the per-chat move count, write nothing, exit 0")
    p.add_argument("--chat", action="append", default=None, help="repeatable; default = every chat")
    p.add_argument("--now", default=None, help="ISO datetime test seam; default = now (Israel-local)")
    return p


def _fail(msg: str) -> int:
    print(f"⚠️  {msg}", file=sys.stderr)
    return 1


def _parse_now(raw: Optional[str]) -> Optional[datetime]:
    if raw is None:
        return now_local()
    try:
        return datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None


def _projected_aged_count(session_dir: Path, cutoff: date) -> int:
    live = session_dir / "messages"
    if not live.exists():
        return 0
    n = 0
    for mfile in live.glob("*.json"):
        try:
            rec = json.loads(mfile.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        raw = rec.get("timestamp") or rec.get("received_at")
        if not raw:
            continue
        try:
            mdate = local_calendar_date(datetime.fromisoformat(raw))
        except (TypeError, ValueError):
            continue
        if mdate < cutoff:
            n += 1
    return n


def main(argv: Optional[List[str]] = None) -> int:  # pylint: disable=too-many-return-statements
    """Archive every >14-day message per chat. See module docstring."""
    args = _build_parser().parse_args(argv)
    data_root = Path(args.data_root)
    sessions_dir = data_root / "sessions"

    if not data_root.exists():
        return _fail(f"--data-root {data_root} does not exist")
    if not sessions_dir.is_dir():
        return _fail(f"{data_root} has no sessions/ directory")

    now = _parse_now(args.now)
    if now is None:
        return _fail(f"--now is not a valid ISO datetime: {args.now!r}")

    sm = SessionManager(storage_dir=str(sessions_dir))
    all_chats = sorted(sm.known_chats())
    targets = args.chat or all_chats
    missing = [c for c in targets if c not in all_chats]
    if missing:
        return _fail(f"chat(s) not found under --data-root: {', '.join(missing)}")
    if not targets:
        print("No chats to finalize.")
        return 0

    cutoff = local_calendar_date(now) - timedelta(days=_WINDOW_DAYS - 1)

    if args.report_only:
        for chat in targets:
            session = sm.get_session(chat)
            sdir = Path(sm.storage_dir) / (session.storage_path or session.session_id)
            print(f"{chat}: ~{_projected_aged_count(sdir, cutoff)} message(s) would move messages/ -> archived/ "
                  f"(cutoff local date < {cutoff.isoformat()})")
        print("\n(--report-only: nothing written)")
        return 0

    for chat in targets:
        session = sm.get_session(chat)
        moved = sm.archive_aged_and_backstopped_messages(
            session, now=now, window_days=_WINDOW_DAYS, max_backstop_tokens=_BACKSTOP_TOKENS,
        )
        sdir = Path(sm.storage_dir) / (session.storage_path or session.session_id)
        try:
            assert_message_integrity(sdir)
        except AssertionError as e:
            return _fail(f"{chat}: integrity check failed after archive on {sdir}: {e}")
        logger.info("finalize %s: archived %d message(s); %d now live, %d archived",
                    chat, moved, len(session.message_ids), len(session.archived_message_ids))
    return 0


if __name__ == "__main__":
    sys.exit(main())
