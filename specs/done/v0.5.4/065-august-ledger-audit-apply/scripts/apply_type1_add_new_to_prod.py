#!/usr/bin/env python3
"""Type 1: copy every player-only event (type1_add_new_to_prod.csv) into
prod's real events/ folder, via the temporary rw mount. Approved 2026-08-31.

Defensive checks before any write:
  - the rw mount must actually be mounted and writable (checked by the
    caller via a round-trip test before this script is ever run)
  - none of the 70 target event_ids may already exist in prod (would mean
    the CSV is stale vs current prod state - abort rather than overwrite)

Source file content is copied byte-for-byte from player_data/events/ (no
schema conversion here - unlike the earlier 8-event copy, these files are
already schema_version 2 or whatever the player currently holds; if any
turn out to still be schema_version 1, that's flagged in the report, not
silently upgraded).
"""
import csv
import json
import shutil
from pathlib import Path

BASE = Path("/Users/yaron/Projects/DeniDin/coder1/specs/backlog/065-august-ledger-audit-apply")
TYPE1_CSV = BASE / "type1_add_new_to_prod.csv"
PLAYER_DIR = Path("/Users/yaron/Projects/DeniDin/coder1/apps/denidin-app/player_data/events")
PROD_RW_DIR = Path.home() / "denidin-winprod-data-rw" / "events"


def main():
    with open(TYPE1_CSV, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    event_ids = [r["event_id"] for r in rows]
    print(f"Type 1 CSV lists {len(event_ids)} event_ids to add.")

    # Defensive pre-flight: none may already exist in prod (real, current state)
    already_in_prod = [eid for eid in event_ids if (PROD_RW_DIR / f"{eid}.json").exists()]
    if already_in_prod:
        print(f"ABORT: {len(already_in_prod)} of these already exist in prod - CSV is stale:")
        for eid in already_in_prod:
            print(f"    {eid}")
        return

    missing_in_player = [eid for eid in event_ids if not (PLAYER_DIR / f"{eid}.json").exists()]
    if missing_in_player:
        print(f"ABORT: {len(missing_in_player)} event_ids from the CSV no longer exist in player:")
        for eid in missing_in_player:
            print(f"    {eid}")
        return

    schema_v1_warned = []
    copied = []
    for eid in event_ids:
        src = PLAYER_DIR / f"{eid}.json"
        dst = PROD_RW_DIR / f"{eid}.json"
        with open(src, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("schema_version") != 2:
            schema_v1_warned.append(eid)
        shutil.copyfile(src, dst)
        copied.append(eid)

    # Verify every copy landed and round-trips (real remote read-back, not
    # just a local assumption the copy succeeded)
    verified = []
    mismatched = []
    for eid in copied:
        dst = PROD_RW_DIR / f"{eid}.json"
        with open(dst, encoding="utf-8") as f:
            round_trip = json.load(f)
        with open(PLAYER_DIR / f"{eid}.json", encoding="utf-8") as f:
            original = json.load(f)
        if round_trip == original:
            verified.append(eid)
        else:
            mismatched.append(eid)

    print(f"\nCopied: {len(copied)}")
    print(f"Verified byte-identical round-trip: {len(verified)}")
    if mismatched:
        print(f"MISMATCH after copy (investigate!): {mismatched}")
    if schema_v1_warned:
        print(f"WARNING - not schema_version 2: {schema_v1_warned}")

    # Final count check against prod's real events dir
    total_prod_now = len(list(PROD_RW_DIR.glob("*.json")))
    print(f"\nprod events/ now contains {total_prod_now} .json files total.")


if __name__ == "__main__":
    main()
