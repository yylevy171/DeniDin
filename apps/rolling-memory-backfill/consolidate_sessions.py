"""Feature 070 migration — session consolidation (Stage 0.3 of MIGRATION-CHECKLIST).

Standalone, operator-run, host ``python3`` (the documented containers-only
exception, same as ``backfill_daily_summaries.py``). Merges the N per-chat
session directories a pre-070 env accumulated (1 active + many
``expired/<date>/<uuid>/``) into **one canonical long-lived session per chat**,
so Feature 070's ``SessionManager._reconcile_chat_index`` finds exactly one dir
per chat and nothing is silently dropped.

Pipeline position: **step 1** of consolidate → backfill → finalize → purge.
See ``specs/in-progress/070-rolling-memory-window/consolidator-spec.md`` §1.

``main(argv=None) -> int``; ``sys.exit(main())``. Preconditions fail closed
(``⚠️`` + ``return 1``) before any write. ``--report-only`` writes nothing.
"""
import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from _denidin_loader import assert_message_integrity  # noqa: F401  (used once implemented)

_RESERVED_DIR_PREFIXES = (".consolidate_tmp_", "_pre070_raw_", "_pre070_sessions_archive_")
_RESERVED_DIR_NAMES = {"expired"}

# Session dataclass fields we write to the canonical session.json. Kept explicit
# (not imported from the dataclass) so a future field addition on the app side
# is a deliberate change here too.
_CANONICAL_SESSION_KEYS = (
    "session_id", "whatsapp_chat", "message_ids", "archived_message_ids",
    "message_counter", "created_at", "last_active", "total_tokens", "storage_path",
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="consolidate_sessions.py",
        description="Feature 070 migration — merge N per-chat session dirs into one canonical session.",
    )
    p.add_argument("--data-root", required=True, help="TARGET env's data/ directory (sessions/ under it)")
    p.add_argument("--report-only", action="store_true", help="dry run: print the plan, write nothing, exit 0")
    p.add_argument("--chat", action="append", default=None, help="repeatable; default = every chat found")
    p.add_argument(
        "--raw-archive-name", default=None,
        help='where source dirs are MOVED; default "_pre070_raw_<YYYYMMDD>" (today, Israel-local)',
    )
    p.add_argument("--resume", action="store_true", help="permit running when a canonical dir already exists")
    return p


def _fail(msg: str) -> int:
    print(f"⚠️  {msg}", file=sys.stderr)
    return 1


# --- helpers (implemented in the GREEN step) -----------------------------------

def _default_raw_archive_name() -> str:
    from _denidin_loader import now_local
    return f"_pre070_raw_{now_local().strftime('%Y%m%d')}"


def _discover_source_sessions(sessions_dir: Path) -> Dict[str, List[Path]]:
    """chat -> [session dir, ...] across active + expired/. NotImplemented until GREEN."""
    raise NotImplementedError


def main(argv: Optional[List[str]] = None) -> int:
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main())
