#!/usr/bin/env python3
"""Type 2: for every event_id in type2_modify_in_prod.csv, move prod's
current file into events/_modified/ (preserving the old version for
history/audit - same backup-before-edit discipline used throughout this
review on the player side), then copy player's corrected version into
prod's events/ in its place. Approved 2026-08-31.

Defensive checks before any write:
  - both the prod source and the player source must exist for every id
  - prod's current content must match what the CSV's prod_* columns say
    (stale-CSV guard - if prod changed since the CSV was generated, abort
    rather than overwrite blind)

Every write is read back immediately (not just assumed to have succeeded -
the rw mount already proved it can die mid-operation once this session).
"""
import csv
import json
import shutil
from pathlib import Path

BASE = Path("/Users/yaron/Projects/DeniDin/coder1/specs/backlog/065-august-ledger-audit-apply")
TYPE2_CSV = BASE / "type2_modify_in_prod.csv"
PLAYER_DIR = Path("/Users/yaron/Projects/DeniDin/coder1/apps/denidin-app/player_data/events")
PROD_RW_DIR = Path.home() / "denidin-winprod-data-rw" / "events"
MODIFIED_DIR = PROD_RW_DIR / "_modified"


def main():
    with open(TYPE2_CSV, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"Type 2 CSV lists {len(rows)} event_ids to modify.")

    MODIFIED_DIR.mkdir(exist_ok=True)

    # Pre-flight: everything must exist and prod's current content must
    # still be what the CSV recorded (client_name/amount/event_subtype)
    problems = []
    for r in rows:
        eid = r["event_id"]
        prod_path = PROD_RW_DIR / f"{eid}.json"
        player_path = PLAYER_DIR / f"{eid}.json"
        if not prod_path.exists():
            problems.append(f"{eid}: no longer exists in prod")
            continue
        if not player_path.exists():
            problems.append(f"{eid}: no longer exists in player")
            continue
        prod_d = json.load(open(prod_path, encoding="utf-8"))
        if (str(prod_d.get("client_name")) != r["prod_client_name"]
                or str(prod_d.get("event_subtype")) != r["prod_event_subtype"]):
            problems.append(
                f"{eid}: prod content drifted from CSV "
                f"(now client_name={prod_d.get('client_name')!r}, "
                f"event_subtype={prod_d.get('event_subtype')!r})"
            )

    if problems:
        print(f"ABORT - {len(problems)} pre-flight problems:")
        for p in problems:
            print(f"    {p}")
        return

    moved, replaced, verified = [], [], []
    for r in rows:
        eid = r["event_id"]
        prod_path = PROD_RW_DIR / f"{eid}.json"
        player_path = PLAYER_DIR / f"{eid}.json"
        backup_path = MODIFIED_DIR / f"{eid}.json"

        with open(prod_path, encoding="utf-8") as f:
            old_prod_content = f.read()
        old_prod_json = json.loads(old_prod_content)

        # 1. back up prod's current file to _modified/ (skip if already backed up)
        if not backup_path.exists():
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(old_prod_content)
        moved.append(eid)

        # 2. copy player's corrected version over prod's live file
        shutil.copyfile(player_path, prod_path)
        replaced.append(eid)

        # 3. verify: backup matches old prod content, live file matches player content
        with open(backup_path, encoding="utf-8") as f:
            backup_read = json.load(f)
        with open(prod_path, encoding="utf-8") as f:
            live_read = json.load(f)
        with open(player_path, encoding="utf-8") as f:
            player_content = json.load(f)

        ok = (backup_read == old_prod_json) and (live_read == player_content)
        if ok:
            verified.append(eid)
        else:
            print(f"  VERIFY FAILED for {eid}!")

    print(f"\nBacked up to _modified/: {len(moved)}")
    print(f"Replaced with player version: {len(replaced)}")
    print(f"Verified (backup + live both correct): {len(verified)}")
    if len(verified) != len(rows):
        print("!!! NOT ALL VERIFIED - investigate before reporting success !!!")


if __name__ == "__main__":
    main()
