#!/usr/bin/env python3
"""Apply the 065 audit's second-round corrections found by cross-checking
every player_data/events/*.json (source_type=בנק, August) against
august_ledger_vs_morning.csv (the real Morning-derived name/status source of
truth) - approved 2026-08-31.

Each fix: back up original to events/_originals/ (if not already backed up),
edit the live file in place, append an explanatory note to description.
"""
import json
import os
from pathlib import Path

EVENTS_DIR = Path(os.path.expanduser(
    "~/Projects/DeniDin/coder1/apps/denidin-app/player_data/events"
))
ORIGINALS_DIR = EVENTS_DIR / "_originals"

FIXES = [
    # (event_id, {field: new_value}, note)
    ("B09082606220", {"event_subtype": "הפקדה"},
     "REVERT: incorrectly marked מבוטל as 'duplicate of B09082606003' per prod "
     "audit id-labeling, but B09082606003 does not exist in player at all - this "
     "is the sole player copy of the טלאל קרעאן 2,300 transaction, must stay "
     "active per august_ledger_vs_morning.csv (doc 130117, מסמך סגור). "
     "065 audit cross-check, 2026-08-31"),
    ("B09082606280", {"event_subtype": "הפקדה"},
     "REVERT: incorrectly marked מבוטל as 'duplicate of B09082606040' per prod "
     "audit id-labeling, but B09082606040 was already self-cancelled by the bot "
     "itself before this edit (ref 3312, 'מבוטל - מסמך זהה למסמך קודם') - "
     "B09082606280 was player's own active copy and must stay active per "
     "august_ledger_vs_morning.csv (doc 130118, מסמך סגור). "
     "065 audit cross-check, 2026-08-31"),
    ("B05082605310", {"client_name": "עדו דניאל", "event_subtype": "מבוטל"},
     "3rd duplicate capture of the same עדו דניאל 3,000 transaction (ref 3312, "
     "same bank account 2821044/837/10, same txn_date 04/08) - never flagged by "
     "the prod-side audit at all (found only via player-side cross-check). "
     "B09082606280 is kept as the sole active record; this and B09082606040 are "
     "both marked מבוטל. 065 audit cross-check, 2026-08-31"),
    ("B05082621120", {"client_name": "רלי אוחנה"},
     "client_name 'אוחנה אלעד' -> 'רלי אוחנה' per Morning source of truth "
     "(august_ledger_vs_morning.csv doc 130120) - missed by the original "
     "ledger_changes_august.json audit entirely. 065 audit cross-check, 2026-08-31"),
    ("B09082606041", {"client_name": "רלי אוחנה"},
     "client_name 'אוחנה אלעד' -> 'רלי אוחנה' per Morning source of truth "
     "(august_ledger_vs_morning.csv doc 130120), propagated to this duplicate "
     "of B05082621120. 065 audit cross-check, 2026-08-31"),
    ("B09082606350", {"client_name": "רלי אוחנה"},
     "client_name 'אוחנה אלעד' -> 'רלי אוחנה' per Morning source of truth "
     "(august_ledger_vs_morning.csv doc 130120), propagated to this duplicate "
     "of B05082621120. 065 audit cross-check, 2026-08-31"),
    ("B11082606200", {"client_name": "זהבית"},
     "client_name 'צורן זהבית' -> 'זהבית' (verbatim per Morning source of truth, "
     "august_ledger_vs_morning.csv doc 112302) - missed by the original "
     "ledger_changes_august.json audit entirely. 065 audit cross-check, 2026-08-31"),
]


def main():
    for event_id, changes, note in FIXES:
        path = EVENTS_DIR / f"{event_id}.json"
        with open(path, encoding="utf-8") as f:
            d = json.load(f)

        orig_backup = ORIGINALS_DIR / f"{event_id}.json"
        if not orig_backup.exists():
            with open(orig_backup, "w", encoding="utf-8") as f:
                f.write(json.dumps(d, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            # preserve exact original bytes instead - re-read raw file
            with open(path, encoding="utf-8") as f:
                raw = f.read()
            with open(orig_backup, "w", encoding="utf-8") as f:
                f.write(raw)

        for field, value in changes.items():
            d[field] = value
        d["description"] = (d.get("description") or "") + f" [{note}]"

        with open(path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        print(f"FIXED {event_id}: {changes} -- {note[:80]}...")


if __name__ == "__main__":
    main()
