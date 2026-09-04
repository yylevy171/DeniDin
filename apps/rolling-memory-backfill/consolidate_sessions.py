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
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

from _denidin_loader import assert_message_integrity

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", force=True)
logger = logging.getLogger("consolidate_sessions")

_RESERVED_DIR_PREFIXES = (".consolidate_tmp_", "_pre070_raw_", "_pre070_sessions_archive_")
_RESERVED_DIR_NAMES = {"expired"}

# Session dataclass fields we write to the canonical session.json, in this order.
# Explicit (not imported from the dataclass) so a future app-side field change is
# a deliberate edit here too. `transferred_to_longterm` is intentionally omitted
# (dead under 070; tolerant load ignores its absence).
_CANONICAL_SESSION_KEYS = (
    "session_id", "whatsapp_chat", "message_ids", "archived_message_ids",
    "message_counter", "created_at", "last_active", "total_tokens", "storage_path",
)

_SENTINEL_DT = datetime(1970, 1, 1, tzinfo=timezone.utc)


class _Src(NamedTuple):
    dir: Path
    session_id: str
    chat: str
    counter: int
    created_at: str
    is_expired: bool
    expired_date: Optional[str]


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


def _default_raw_archive_name() -> str:
    from _denidin_loader import now_local  # pylint: disable=import-outside-toplevel
    return f"_pre070_raw_{now_local().strftime('%Y%m%d')}"


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _parse_dt(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return _aware(datetime.fromisoformat(raw))
    except (TypeError, ValueError):
        return None


# --- discovery ---------------------------------------------------------------

def _iter_session_json(sessions_dir: Path):
    """Yield (session_json_path, is_expired, expired_date) for every source dir."""
    for child in sorted(sessions_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name in _RESERVED_DIR_NAMES or child.name.startswith(_RESERVED_DIR_PREFIXES):
            continue
        sj = child / "session.json"
        if sj.exists():
            yield sj, False, None
    expired = sessions_dir / "expired"
    if expired.exists():
        for date_folder in sorted(expired.iterdir()):
            if not date_folder.is_dir():
                continue
            for child in sorted(date_folder.iterdir()):
                sj = child / "session.json"
                if child.is_dir() and sj.exists():
                    yield sj, True, date_folder.name


def _discover_source_sessions(sessions_dir: Path) -> Tuple[Dict[str, List[_Src]], List[str]]:
    """chat -> [_Src, ...] across active + expired/. Second element: names of dirs
    whose session.json could not be parsed (caller aborts)."""
    by_chat: Dict[str, List[_Src]] = {}
    errors: List[str] = []
    for sj, is_expired, expired_date in _iter_session_json(sessions_dir):
        try:
            data = json.loads(sj.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            errors.append(sj.parent.name)
            continue
        chat = data.get("whatsapp_chat")
        if not chat:
            errors.append(sj.parent.name)
            continue
        counter = data.get("message_counter")
        if not isinstance(counter, int):
            counter = len(data.get("message_ids", []))
        by_chat.setdefault(chat, []).append(_Src(
            dir=sj.parent,
            session_id=data.get("session_id", sj.parent.name),
            chat=chat,
            counter=counter,
            created_at=data.get("created_at") or data.get("session_start") or "",
            is_expired=is_expired,
            expired_date=expired_date,
        ))
    return by_chat, errors


# --- merge ------------------------------------------------------------------

def _read_all_messages(src_dirs: List[Path]) -> Tuple[List[dict], int, int]:
    """Return (merged records, duplicate_id_count, timestamp_fallback_count).
    First occurrence of a message_id wins; src_dirs must already be in a stable
    order. Records are sorted timestamp -> received_at -> order_num -> message_id."""
    seen: Dict[str, str] = {}
    records: List[dict] = []
    dup = 0
    fallback = 0
    for sdir in src_dirs:
        for sub in ("messages", "archived"):
            mdir = sdir / sub
            if not mdir.exists():
                continue
            for mfile in sorted(mdir.glob("*.json")):
                rec = json.loads(mfile.read_text(encoding="utf-8"))
                mid = rec.get("message_id", mfile.stem)
                if mid in seen:
                    dup += 1
                    logger.warning(
                        "duplicate message_id %s in %s — keeping the copy from %s",
                        mid, sdir.name, seen[mid],
                    )
                    continue
                seen[mid] = sdir.name
                if _parse_dt(rec.get("timestamp")) is None:
                    fallback += 1
                    logger.warning(
                        "message %s (%s): no parseable 'timestamp' — sorting by received_at/order_num",
                        mid, sdir.name,
                    )
                records.append(rec)

    def _key(rec: dict):
        primary = _parse_dt(rec.get("timestamp")) or _parse_dt(rec.get("received_at")) or _SENTINEL_DT
        secondary = _parse_dt(rec.get("received_at")) or _SENTINEL_DT
        return (primary, secondary, rec.get("order_num", 0), rec.get("message_id", ""))

    records.sort(key=_key)
    return records, dup, fallback


def _canonical_id(sources: List[_Src]) -> str:
    """Greatest message_counter wins; tie -> lexicographically smallest session_id."""
    return sorted(sources, key=lambda s: (-s.counter, s.session_id))[0].session_id


def _extremum_iso(values: List[str], pick) -> str:
    parsed: List[Tuple[datetime, str]] = []
    for v in values:
        dt = _parse_dt(v)
        if dt is not None:
            parsed.append((dt, v))
    return pick(parsed, key=lambda t: t[0])[1] if parsed else ""


def _min_iso(values: List[str]) -> str:
    return _extremum_iso(values, min)


def _max_iso(values: List[str]) -> str:
    return _extremum_iso(values, max)


def _write_canonical(tmp_dir: Path, canonical_id: str, chat: str, sources: List[_Src],
                     records: List[dict]) -> None:
    (tmp_dir / "messages").mkdir(parents=True)
    (tmp_dir / "archived").mkdir(parents=True)
    ids: List[str] = []
    last_ts: List[str] = []
    for i, rec in enumerate(records, start=1):
        rec = dict(rec)
        mid = str(rec.get("message_id") or "")
        rec["order_num"] = i
        rec["session_id"] = canonical_id
        ids.append(mid)
        if rec.get("timestamp"):
            last_ts.append(rec["timestamp"])
        (tmp_dir / "messages" / f"{mid}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    created = _min_iso([s.created_at for s in sources])
    last_active = _max_iso([_load_last_active(s.dir) for s in sources] + last_ts)
    session = {
        "session_id": canonical_id,
        "whatsapp_chat": chat,
        "message_ids": ids,
        "archived_message_ids": [],
        "message_counter": len(records),
        "created_at": created,
        "last_active": last_active,
        "total_tokens": 0,
        "storage_path": None,
    }
    ordered = {k: session[k] for k in _CANONICAL_SESSION_KEYS}
    (tmp_dir / "session.json").write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_last_active(session_dir: Path) -> str:
    try:
        return json.loads((session_dir / "session.json").read_text(encoding="utf-8")).get("last_active", "")
    except (OSError, json.JSONDecodeError):
        return ""


def _archive_source(src: _Src, raw_dir: Path) -> Path:
    if src.is_expired and src.expired_date:
        dest = raw_dir / "expired" / src.expired_date / src.dir.name
    else:
        dest = raw_dir / "active" / src.dir.name
    if dest.exists():
        k = 1
        while (dest.parent / f"{dest.name}_dup{k}").exists():
            k += 1
        dest = dest.parent / f"{dest.name}_dup{k}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src.dir), str(dest))
    return dest


def _consolidate_chat(sessions_dir: Path, chat: str, sources: List[_Src], raw_dir: Path) -> int:
    ordered_sources = sorted(sources, key=lambda s: (s.created_at, s.session_id))
    records, dup, fallback = _read_all_messages([s.dir for s in ordered_sources])
    n = len(records)
    total_in = sum(s.counter for s in sources)
    if n > total_in:
        return _fail(f"{chat}: merged {n} messages > sum of source counters {total_in} — aborting, wrote nothing")

    canonical_id = _canonical_id(sources)
    tmp_dir = sessions_dir / f".consolidate_tmp_{hashlib.sha1(chat.encode()).hexdigest()[:12]}"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)

    _write_canonical(tmp_dir, canonical_id, chat, sources, records)
    for src in ordered_sources:
        _archive_source(src, raw_dir)
    final_dir = sessions_dir / canonical_id
    tmp_dir.rename(final_dir)

    try:
        assert_message_integrity(final_dir)
    except AssertionError as e:
        return _fail(f"{chat}: integrity check failed on {final_dir}: {e}")

    logger.info(
        "consolidated %s: %d source dir(s) -> %s (%d messages, %d dup, %d ts-fallback)",
        chat, len(sources), canonical_id, n, dup, fallback,
    )
    return 0


# --- report ---------------------------------------------------------------

def _report(by_chat: Dict[str, List[_Src]], targets: List[str]) -> int:
    for chat in targets:
        sources = by_chat[chat]
        ordered = sorted(sources, key=lambda s: (s.created_at, s.session_id))
        records, dup, fallback = _read_all_messages([s.dir for s in ordered])
        print(f"\n=== {chat} ===")
        print(f"  source dirs: {len(sources)}")
        for s in ordered:
            loc = f"expired/{s.expired_date}" if s.is_expired else "active"
            print(f"    - {loc}/{s.session_id}  (message_counter={s.counter})")
        print(f"  Σ source messages : {sum(s.counter for s in sources)}")
        print(f"  merged messages   : {len(records)}")
        print(f"  duplicate ids     : {dup}")
        print(f"  timestamp fallback: {fallback}")
        print(f"  canonical id      : {_canonical_id(sources)}")
        print(f"  projected integrity: {'PASS' if len(records) <= sum(s.counter for s in sources) else 'FAIL'}")
    print("\n(--report-only: nothing written)")
    return 0


# --- main ----------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:  # pylint: disable=too-many-return-statements,too-many-locals,too-many-branches
    """Consolidate every per-chat session dir into one canonical session. See module docstring."""
    args = _build_parser().parse_args(argv)
    data_root = Path(args.data_root)
    sessions_dir = data_root / "sessions"

    if not data_root.exists():
        return _fail(f"--data-root {data_root} does not exist")
    if not sessions_dir.is_dir():
        return _fail(f"{data_root} has no sessions/ directory")

    raw_dir = sessions_dir / (args.raw_archive_name or _default_raw_archive_name())
    if raw_dir.exists() and not args.resume:
        return _fail(f"{raw_dir.name} already exists — pass --resume to continue a previous run")

    by_chat, parse_errors = _discover_source_sessions(sessions_dir)
    if parse_errors:
        return _fail(f"unparseable session.json in: {', '.join(sorted(parse_errors))} — aborting, wrote nothing")

    targets = args.chat or sorted(by_chat)
    missing = [c for c in targets if c not in by_chat]
    if missing:
        return _fail(f"no source session dir found for chat(s): {', '.join(missing)}")

    if args.report_only:
        return _report(by_chat, targets)

    if args.resume:
        # Fold-in mode: a straggler is any source dir that is NOT the current
        # highest-counter TOP-LEVEL dir for its chat (that one is the prior run's
        # canonical). No stragglers anywhere -> nothing to do.
        pending = {}
        for chat in targets:
            top = [s for s in by_chat[chat] if not s.is_expired]
            prior_canonical = max(top, key=lambda s: (s.counter, s.session_id)).dir if top else None
            stragglers = [s for s in by_chat[chat] if s.dir != prior_canonical]
            if stragglers:
                pending[chat] = by_chat[chat]  # re-merge the WHOLE set
        if not pending:
            print("--resume: nothing pending, no changes made")
            return 0
        by_chat = pending
        targets = sorted(pending)

    # A pre-existing chat_index.db (from a prior SessionManager construction —
    # e.g. an operator opening the fragmented tree, or a partial earlier run) maps
    # chats to dirs we are about to MOVE. INSERT-OR-IGNORE means the next
    # SessionManager would keep the stale row and crash on get_session. Delete it
    # here — it is rebuilt, correctly, on the next construction (finalize / app start).
    index_db = sessions_dir / "chat_index.db"
    if index_db.exists():
        index_db.unlink()
        logger.info("removed stale %s — rebuilt on next SessionManager construction", index_db.name)

    raw_dir.mkdir(parents=True, exist_ok=True)
    for chat in targets:
        rc = _consolidate_chat(sessions_dir, chat, by_chat[chat], raw_dir)
        if rc != 0:
            return rc

    _prune_empty_expired(sessions_dir)
    return 0


def _prune_empty_expired(sessions_dir: Path) -> None:
    """After moving every source dir out, remove the now-empty expired/<date>/
    folders (and expired/ itself if empty) so _reconcile_chat_index's per-startup
    scan sees a clean tree."""
    expired = sessions_dir / "expired"
    if not expired.is_dir():
        return
    for date_folder in list(expired.iterdir()):
        if date_folder.is_dir() and not any(date_folder.iterdir()):
            date_folder.rmdir()
    if not any(expired.iterdir()):
        expired.rmdir()
        logger.info("removed empty sessions/expired/ tree")


if __name__ == "__main__":
    sys.exit(main())
