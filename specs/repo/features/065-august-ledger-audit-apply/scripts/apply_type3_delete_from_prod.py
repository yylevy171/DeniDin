#!/usr/bin/env python3
"""Type 3: remove prod events that are unsupported (pending Bit transfers,
never confirmed deposits) with no player counterpart to replace them with -
per ledger_changes_august.json's removals_unsupported_bit_transfers, cross-
checked against player_data/events (confirmed: player correctly never
captured these 3 at all). Approved 2026-08-31.

Not a hard delete - moved to events/_removed/ (same preserve-history
discipline as _modified/ for Type 2), with a reason note recorded alongside.
"""
import json
import shutil
from pathlib import Path

PROD_RW_DIR = Path.home() / "denidin-winprod-data-rw" / "events"
REMOVED_DIR = PROD_RW_DIR / "_removed"

ITEMS = [
    ("B06082613311", "unsupported bit transfer (status ממתין / not a confirmed deposit); "
                      "no player counterpart exists - player correctly never captured this "
                      "at all. 065 audit, removals_unsupported_bit_transfers, 2026-08-31."),
    ("B07082606400", "unsupported bit transfer (status ממתין / not a confirmed deposit); "
                      "no player counterpart exists - player correctly never captured this "
                      "at all (this is the Aug-7 06:40 message, confirmed against the real "
                      "WhatsApp export - a pending Bit transfer, never a bank deposit). "
                      "065 audit, removals_unsupported_bit_transfers, 2026-08-31."),
    ("B13082621150", "unsupported bit transfer (status ממתין / not a confirmed deposit); "
                      "no player counterpart exists - player correctly never captured this "
                      "at all. 065 audit, removals_unsupported_bit_transfers, 2026-08-31."),
]


def main():
    REMOVED_DIR.mkdir(exist_ok=True)

    removed = []
    for eid, reason in ITEMS:
        prod_path = PROD_RW_DIR / f"{eid}.json"
        if not prod_path.exists():
            print(f"SKIP {eid}: no longer exists in prod")
            continue

        with open(prod_path, encoding="utf-8") as f:
            content = f.read()

        dest = REMOVED_DIR / f"{eid}.json"
        with open(dest, "w", encoding="utf-8") as f:
            f.write(content)

        reason_path = REMOVED_DIR / f"{eid}.reason.txt"
        with open(reason_path, "w", encoding="utf-8") as f:
            f.write(reason + "\n")

        prod_path.unlink()
        removed.append(eid)
        print(f"REMOVED {eid} -> _removed/ ({reason[:60]}...)")

    print(f"\nRemoved: {len(removed)}")


if __name__ == "__main__":
    main()
