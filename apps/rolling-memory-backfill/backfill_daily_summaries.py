"""Feature 070 (US4) — rolling 14-day memory backfill.

Standalone, operator-run. Fills the ChromaDB ``daily_summary`` gap for every
calendar day between ``--since`` and ``--until`` (inclusive) that predates the
nightly roll's / catch-up sweep's reach, reusing the **exact** nightly roll code
path (``daily_summary_roll_service._roll_one_chat_day``) so a migrated summary is
byte-for-byte a nightly one bar ``source="migration"``.

Mirrors ``apps/prod-ledger-backfill`` conventions: host ``python3`` (documented
containers-only exception), ``main(argv=None) -> int``, ``sys.exit(main())``, no
``--env`` / no ``--dry-run``, preconditions fail closed before any network call, a
mid-run per-item failure aborts the whole run loudly (a re-run resumes from the
roll markers).

See ``contracts/backfill-cli.md`` and ``quickstart.md``.
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import List, Optional

from openai import OpenAI

from _denidin_loader import (
    MemoryManager,
    RollMarkerStore,
    SessionManager,
    assert_message_integrity,
    local_calendar_date,
    now_local,
    roll_service,
)

_LIVE_WINDOW_GUARD_DAYS = 14


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="backfill_daily_summaries.py",
        description="Feature 070 US4 — backfill ChromaDB daily_summary records for a date range.",
    )
    p.add_argument("--data-root", required=True, help="TARGET env's data/ directory")
    p.add_argument("--config", required=True, help="TARGET env's config.json (OpenAI key, embedding model, memory.*)")
    p.add_argument("--since", required=True, help="YYYY-MM-DD, inclusive, no default")
    p.add_argument("--until", default=None, help="YYYY-MM-DD, inclusive; default = today_local - 14d")
    p.add_argument("--chat", action="append", default=None, help="repeatable; default = all chats under --data-root")
    p.add_argument("--yes", action="store_true", help="skip the typed-'yes' confirmation")
    return p


def _fail(msg: str) -> int:
    print(f"⚠️  {msg}", file=sys.stderr)
    return 1


def _parse_iso_date(raw: str) -> Optional[date]:
    try:
        return date.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _daterange(since: date, until: date) -> List[date]:
    return [since + timedelta(days=k) for k in range((until - since).days + 1)]


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    # --- Preconditions (fail closed, before any network call) --------------------
    data_root = Path(args.data_root)
    if not data_root.is_dir():
        return _fail(f"--data-root does not exist: {data_root}")
    sessions_dir = data_root / "sessions"
    if not sessions_dir.is_dir():
        return _fail(f"--data-root has no sessions/ subdirectory: {data_root}")

    config_path = Path(args.config)
    if not config_path.is_file():
        return _fail(f"--config file not found: {config_path}")
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        return _fail(f"--config could not be parsed: {e}")

    api_key = config.get("ai_api_key")
    embedding_model = config.get("ai_embedding_model")
    memory_block = config.get("memory")
    ai_model = config.get("ai_model")
    if not api_key:
        return _fail("--config is missing 'ai_api_key'")
    if not embedding_model:
        return _fail("--config is missing 'ai_embedding_model'")
    if not isinstance(memory_block, dict):
        return _fail("--config is missing a 'memory' block")
    if not ai_model:
        return _fail("--config is missing 'ai_model'")

    since = _parse_iso_date(args.since)
    if since is None:
        return _fail(f"--since is not a valid YYYY-MM-DD date: {args.since!r}")

    today_local = local_calendar_date(now_local())
    latest_allowed = today_local - timedelta(days=_LIVE_WINDOW_GUARD_DAYS)
    if args.until is None:
        until = latest_allowed
    else:
        until = _parse_iso_date(args.until)
        if until is None:
            return _fail(f"--until is not a valid YYYY-MM-DD date: {args.until!r}")

    if since > until:
        return _fail(f"--since ({since}) is after --until ({until})")
    if until > latest_allowed:
        return _fail(
            f"--until ({until}) is inside the live {_LIVE_WINDOW_GUARD_DAYS}-day verbatim window "
            f"(must be <= {latest_allowed}); backfilling into it is the nightly roll's job"
        )

    # --- Real components via the loader ----------------------------------------
    session_manager = SessionManager(storage_dir=str(sessions_dir))
    roll_marker_store = RollMarkerStore(str(data_root / "memory_rolls"))
    ai_client = OpenAI(api_key=api_key)
    memory_manager = MemoryManager(
        storage_dir=str(data_root / "memory"),
        embedding_model=embedding_model,
        ai_client=ai_client,
    )

    all_chats = sorted(session_manager.known_chats())
    if args.chat:
        chats = [c for c in args.chat if c in all_chats]
        missing = [c for c in args.chat if c not in all_chats]
        if missing:
            return _fail(f"--chat not found under --data-root: {missing}")
    else:
        chats = all_chats
    if not chats:
        print("No chats to process.")
        return 0

    def _session_dir(session) -> Path:
        return Path(session_manager.storage_dir) / (getattr(session, "storage_path", None) or session.session_id)

    # --- Integrity BEFORE --------------------------------------------------------
    for chat in chats:
        assert_message_integrity(_session_dir(session_manager.get_session(chat)))

    dates = _daterange(since, until)

    # --- Confirmation ----------------------------------------------------------
    if not args.yes:
        print(f"data-root : {data_root}")
        print(f"chats     : {len(chats)}")
        for c in chats:
            print(f"            {c}")
        print(f"date range: {since} .. {until}  ({len(dates)} days)")
        print(f"max billed calls (upper bound): {len(chats) * len(dates)}")
        if input("Type 'yes' to proceed: ").strip() != "yes":
            return _fail("aborted at confirmation prompt")

    global_context = SimpleNamespace(
        session_manager=session_manager,
        ai_handler=SimpleNamespace(
            roll_marker_store=roll_marker_store,
            memory_manager=memory_manager,
            client=ai_client,
            config=SimpleNamespace(ai_model=ai_model, memory=memory_block),
        ),
        config=SimpleNamespace(memory=memory_block),
    )

    grand = {"summaries": 0, "empty": 0, "skipped": 0, "billed": 0}
    for chat in chats:
        per = {"summaries": 0, "empty": 0, "skipped": 0, "billed": 0}
        for d in dates:
            date_str = d.isoformat()
            if roll_marker_store.is_rolled(chat, date_str):
                per["skipped"] += 1
                continue
            session = session_manager.get_session(chat)
            msgs = session_manager.get_messages_for_local_date(session, d)
            try:
                roll_service._roll_one_chat_day(  # pylint: disable=protected-access
                    global_context, chat, d, source="migration", log_prefix="[BACKFILL] "
                )
            except Exception as e:  # pylint: disable=broad-except
                return _fail(
                    f"mid-run failure on {chat} {date_str}: {e}. "
                    f"Roll markers persisted so far — re-run to resume."
                )
            if roll_marker_store.is_rolled(chat, date_str):
                if msgs:
                    per["summaries"] += 1
                    per["billed"] += 1
                else:
                    per["empty"] += 1
            else:
                per["skipped"] += 1
        print(
            f"\n[{chat}] days={len(dates)} summaries={per['summaries']} "
            f"empty={per['empty']} skipped/already-rolled={per['skipped']} billed_calls={per['billed']}"
        )
        for k in grand:
            grand[k] += per[k]

    # --- Integrity AFTER -------------------------------------------------------
    for chat in chats:
        assert_message_integrity(_session_dir(session_manager.get_session(chat)))

    print(
        f"\n=== GRAND TOTAL === chats={len(chats)} summaries={grand['summaries']} "
        f"empty_days={grand['empty']} skipped={grand['skipped']} billed_calls={grand['billed']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
