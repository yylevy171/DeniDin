#!/usr/bin/env python3
"""Feature 066 validation: is every ledger event in the new deposit shape?

Read-only - never writes anything. Pairs with scripts/migrate_066_deposit_flip.py:
it FAILS (exit 1) while any pre-066 bank-deposit event is still in the old shape, and
PASSES (exit 0) once the migration has been applied.

Checks, over every event in <data root>/events/:
  1. no event is still in the old shape (source_type "בנק", whatever its event_subtype);
  2. every event with source_type "הפקדה" has a real method as its event_subtype;
  3. every such event carries schema_version 3 or above;
  4. with --backup <dir> (the events_backup_066_<timestamp> the migration made): the only files
     gone are the cancelled bank events (source_type "בנק" / event_subtype "מבוטל"), nothing new
     appeared, and every flipped event differs from its backup only in
     source_type / event_subtype / schema_version.

Usage:
  scripts/validate_066_deposit_flip.py --data-root <data root containing events/> [--backup <backup events dir>]
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

OLD_SOURCE_TYPE = "בנק"
CANCELLED_SUBTYPE = "מבוטל"  # a cancelled bank event is deleted by the migration
DEPOSIT_SOURCE_TYPE = "הפקדה"
METHODS = ("בנק", "ביט", "פייבוקס", "צ׳ק", "מזומן")
MIN_SCHEMA_VERSION = 3
CHANGED_KEYS = ("source_type", "event_subtype", "schema_version")


def _load(events_dir: Path) -> Dict[str, Dict]:
    records: Dict[str, Dict] = {}
    for path in sorted(events_dir.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError(f"{path.name}: not a JSON object")
        records[path.name] = record
    return records


def validate(data_root: Path, backup: Optional[Path] = None) -> Dict[str, object]:
    """Returns {"events", "deposits", "problems": [str, ...]}; no problems means valid."""
    events_dir = data_root / "events"
    if not events_dir.is_dir():
        raise ValueError(f"{events_dir} does not exist")
    records = _load(events_dir)
    problems: List[str] = []
    deposits = 0
    for name, record in records.items():
        source_type, subtype = record.get("source_type"), record.get("event_subtype")
        if source_type == OLD_SOURCE_TYPE:
            problems.append(f"{name}: still in the old shape (source_type בנק / event_subtype {subtype})")
        elif source_type == DEPOSIT_SOURCE_TYPE:
            deposits += 1
            if subtype not in METHODS:
                problems.append(f"{name}: deposit with event_subtype {subtype!r}, not a method")
            if (record.get("schema_version") or 0) < MIN_SCHEMA_VERSION:
                problems.append(f"{name}: deposit with schema_version {record.get('schema_version')!r}")
    if backup is not None:
        problems.extend(_compare_with_backup(records, _load(backup)))
    return {"events": len(records), "deposits": deposits, "problems": problems}


def _compare_with_backup(records: Dict[str, Dict], before: Dict[str, Dict]) -> List[str]:
    problems: List[str] = []
    deleted = set(before) - set(records)
    unexpected = [n for n in deleted
                  if not (before[n].get("source_type") == OLD_SOURCE_TYPE
                          and before[n].get("event_subtype") == CANCELLED_SUBTYPE)]
    if unexpected or set(records) - set(before):
        problems.append(f"files differ from the backup: removed {sorted(unexpected)[:5]} (not cancelled bank events), "
                        f"new {sorted(set(records) - set(before))[:5]}")
    for name in sorted(set(records) & set(before)):
        old, new = before[name], records[name]
        if old == new:
            continue
        if old.get("event_id") != new.get("event_id"):
            problems.append(f"{name}: event_id changed")
        rest_old = {k: v for k, v in old.items() if k not in CHANGED_KEYS}
        rest_new = {k: v for k, v in new.items() if k not in CHANGED_KEYS}
        if rest_old != rest_new:
            problems.append(f"{name}: a field other than {CHANGED_KEYS} changed")
    return problems


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-root", required=True, type=Path, help="data root that contains events/")
    parser.add_argument("--backup", type=Path, help="the migration's events backup folder, to compare against")
    args = parser.parse_args(argv)
    try:
        result = validate(args.data_root, args.backup)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    problems = result["problems"]
    print(f"{result['events']} event(s), {result['deposits']} in the new deposit shape, {len(problems)} problem(s)")
    for line in problems[:50]:  # type: ignore[index]
        print(f"  - {line}")
    if len(problems) > 50:  # type: ignore[arg-type]
        print(f"  ... and {len(problems) - 50} more")  # type: ignore[operator]
    print("VALID" if not problems else "INVALID")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
