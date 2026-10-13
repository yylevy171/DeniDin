#!/usr/bin/env python3
"""Feature 066 one-time migration: flip every pre-066 bank-deposit ledger event.

Old shape : source_type "בנק", event_subtype "הפקדה"
New shape : source_type "הפקדה", event_subtype "בנק" (the METHOD), schema_version 3
A cancelled one (source_type "בנק", event_subtype "מבוטל") is a mistake and is DELETED (after
the backup, which keeps it).

Nothing else about an event changes: every other field stays byte-for-byte
identical, and filenames and `event_id`s are never touched.

Safe by construction:
  * DRY-RUN by default - prints what it would change and writes nothing.
    `--apply` is required to modify anything.
  * Before the first write, the whole events directory is copied to a sibling
    `events_backup_066_<timestamp>/` (outside `events/`, so no loader reads it).
  * Every flip is verified in memory BEFORE any file is written: the new record
    must equal the old one in every field except the three above, otherwise the
    run aborts with nothing written.
  * Idempotent: an already-flipped event (source_type "הפקדה") is skipped, so a
    second run changes nothing.
  * Atomic per file (tmp file, then replace), written in the same format the
    ledger manager itself uses.

Usage:
  scripts/migrate_066_deposit_flip.py --data-root <data root containing events/> [--apply]
"""
import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

OLD_SOURCE_TYPE = "בנק"
NEW_SOURCE_TYPE = "הפקדה"
NEW_SUBTYPE = "בנק"
OLD_SUBTYPE = "הפקדה"
CANCELLED_SUBTYPE = "מבוטל"  # deleted, not flipped
NEW_SCHEMA_VERSION = 3
CHANGED_KEYS = ("source_type", "event_subtype", "schema_version")


class MigrationAbort(Exception):
    """Raised when a verification fails; nothing has been written."""


def _flipped(record: Dict) -> Dict:
    new = dict(record)
    new["source_type"] = NEW_SOURCE_TYPE
    new["event_subtype"] = NEW_SUBTYPE
    new["schema_version"] = NEW_SCHEMA_VERSION
    return new


def _plan(events_dir: Path) -> Tuple[List[Tuple[Path, Dict, Dict]], List[Path], int]:
    """Returns ([(path, old, new)] to flip, [path] to delete (cancelled), count already in the new shape)."""
    to_flip: List[Tuple[Path, Dict, Dict]] = []
    to_delete: List[Path] = []
    already = 0
    for path in sorted(events_dir.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise MigrationAbort(f"{path.name}: not valid JSON ({exc})") from exc
        if not isinstance(record, dict):
            raise MigrationAbort(f"{path.name}: not a JSON object")
        source_type = record.get("source_type")
        if source_type == NEW_SOURCE_TYPE:
            already += 1
            continue
        if source_type != OLD_SOURCE_TYPE:
            continue
        if record.get("event_subtype") == CANCELLED_SUBTYPE:
            to_delete.append(path)
            continue
        if record.get("event_subtype") != OLD_SUBTYPE:
            raise MigrationAbort(f"{path.name}: source_type בנק with unexpected event_subtype "
                                 f"{record.get('event_subtype')!r} - nothing written")
        new = _flipped(record)
        unchanged_old = {k: v for k, v in record.items() if k not in CHANGED_KEYS}
        unchanged_new = {k: v for k, v in new.items() if k not in CHANGED_KEYS}
        if unchanged_old != unchanged_new or record.get("event_id") != new.get("event_id"):
            raise MigrationAbort(f"{path.name}: verification failed - fields other than {CHANGED_KEYS} would change")
        to_flip.append((path, record, new))
    return to_flip, to_delete, already


def _write(path: Path, record: Dict) -> None:
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(record, f, sort_keys=True, ensure_ascii=False, indent=2)
    tmp.replace(path)


def migrate(data_root: Path, apply: bool) -> Dict[str, object]:
    events_dir = data_root / "events"
    if not events_dir.is_dir():
        raise MigrationAbort(f"{events_dir} does not exist")
    to_flip, to_delete, already = _plan(events_dir)
    result: Dict[str, object] = {"to_flip": len(to_flip), "to_delete": len(to_delete),
                                 "already_flipped": already, "applied": False, "backup": None}
    if not apply or not (to_flip or to_delete):
        return result
    backup = data_root / f"events_backup_066_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copytree(events_dir, backup)
    for path, _old, new in to_flip:
        _write(path, new)
    for path in to_delete:
        path.unlink()
    result.update(applied=True, backup=str(backup))
    return result


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-root", required=True, type=Path, help="data root that contains events/")
    parser.add_argument("--apply", action="store_true", help="actually modify files (default: dry-run)")
    args = parser.parse_args(argv)
    try:
        result = migrate(args.data_root, args.apply)
    except MigrationAbort as exc:
        print(f"ABORTED, nothing written: {exc}", file=sys.stderr)
        return 1
    mode = "APPLIED" if result["applied"] else ("DRY-RUN" if not args.apply else "NOTHING TO DO")
    print(f"{mode}: {result['to_flip']} event(s) to flip, {result['to_delete']} cancelled to delete, {result['already_flipped']} already in the new shape"
          + (f", backup: {result['backup']}" if result["backup"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
