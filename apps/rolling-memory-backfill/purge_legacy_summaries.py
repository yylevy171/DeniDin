"""Feature 070 migration — purge legacy `session_summary` records (Stage 0.6).

Pipeline **step 4** of consolidate → backfill → finalize → purge. Deletes the
pre-070 ``type=session_summary`` / ``session_summary_fallback`` ChromaDB records
(on prod: ~20,949 rows = only 84 real sessions, each re-summarized ~250× by the
retired hourly cleanup thread). After the backfill has written one clean
``daily_summary`` per (chat, day) these add only noise + bulk to the two per-chat
collections ``recall`` reads from.

**Guard**: refuses to touch a collection that has no ``daily_summary`` record yet
(purging before the backfill would leave the chat with no long-term memory).

Single-writer ChromaDB — the app MUST be stopped and ``--data-root`` must be
read-write (runs on the host / a pulled copy, never the read-only prod mount).

``main(argv=None) -> int``; ``sys.exit(main())``. ``--report-only`` writes nothing.
See ``specs/done/070-rolling-memory-window/consolidator-spec.md`` §3.
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import Any, List, Optional

import chromadb
from chromadb.config import Settings

from _denidin_loader import collection_name_for_chat

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
logger = logging.getLogger("purge_legacy_summaries")

_LEGACY_TYPES = ("session_summary", "session_summary_fallback")
_RESERVED_SUFFIXES = ("_public", "_private", "system_context")
_LEGACY_WHERE: Any = {"$or": [{"type": {"$eq": t}} for t in _LEGACY_TYPES]}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="purge_legacy_summaries.py",
        description="Feature 070 migration — delete pre-070 session_summary ChromaDB records.",
    )
    p.add_argument("--data-root", required=True, help="TARGET env's data/ directory (memory/ under it)")
    p.add_argument("--report-only", action="store_true", help="count matching records per collection, write nothing")
    p.add_argument("--chat", action="append", default=None,
                   help="repeatable; collection name or chat id; default = every non-reserved memory_* collection")
    return p


def _fail(msg: str) -> int:
    print(f"⚠️  {msg}", file=sys.stderr)
    return 1


def _is_target(name: str) -> bool:
    return name.startswith("memory_") and not name.endswith(_RESERVED_SUFFIXES)


def _wanted(name: str, chat_filters: Optional[List[str]]) -> bool:
    if chat_filters is None:
        return True
    wanted_names = set()
    for f in chat_filters:
        wanted_names.add(f)
        try:
            wanted_names.add(collection_name_for_chat(f))
        except Exception:  # pylint: disable=broad-except
            pass
    return name in wanted_names


def main(argv: Optional[List[str]] = None) -> int:  # pylint: disable=too-many-locals
    """Delete pre-070 session_summary records. See module docstring."""
    args = _build_parser().parse_args(argv)
    data_root = Path(args.data_root)
    memory_dir = data_root / "memory"

    if not data_root.exists():
        return _fail(f"--data-root {data_root} does not exist")
    if not memory_dir.is_dir():
        return _fail(f"{data_root} has no memory/ directory")

    client = chromadb.PersistentClient(path=str(memory_dir), settings=Settings(anonymized_telemetry=False))
    collections = [
        c.name if hasattr(c, "name") else str(c)
        for c in client.list_collections()
    ]
    targets = [n for n in collections if _is_target(n) and _wanted(n, args.chat)]
    if not targets:
        print("No matching collections.")
        return 0

    total_deleted = 0
    for name in sorted(targets):
        coll = client.get_collection(name)
        daily_where: Any = {"type": {"$eq": "daily_summary"}}
        legacy = coll.get(where=_LEGACY_WHERE)
        legacy_ids = legacy.get("ids") or []
        has_daily = bool(coll.get(where=daily_where, limit=1).get("ids"))

        if not has_daily:
            return _fail(
                f"{name}: no daily_summary record present — run the backfill first "
                f"(refusing to purge {len(legacy_ids)} legacy records)"
            )

        before = coll.count()
        if args.report_only:
            print(f"{name}: {len(legacy_ids)} legacy record(s) of {before} would be deleted")
            continue

        coll.delete(where=_LEGACY_WHERE)
        after = coll.count()
        total_deleted += before - after
        logger.info("purged %s: %d -> %d records (%d legacy deleted)", name, before, after, before - after)

    if args.report_only:
        print("\n(--report-only: nothing written)")
    else:
        print(f"\nDeleted {total_deleted} legacy record(s) across {len(targets)} collection(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
