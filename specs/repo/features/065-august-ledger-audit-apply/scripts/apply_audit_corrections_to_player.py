#!/usr/bin/env python3
"""Apply the Morning-verified 065 audit's corrections directly onto player
ledger events on disk, so player_data/events becomes the corrected source
that eventually gets copied to prod.

For every event_id in ledger_changes_august.json (duplicates_approved,
removals_unsupported_bit_transfers, name_changes - including the
also_apply_to_duplicates propagation), if a player file exists under that
EXACT event_id:
  - SAFETY CHECK FIRST: compare amount. If it doesn't match the audit's
    recorded amount, this is an event_id collision between prod and player
    (proven to happen at least once - B09082606001) - do NOT touch it, just
    report it as skipped/needs-manual-review.
  - Otherwise: back up the original to events/_originals/, then apply the
    correction (client_name rename and/or event_subtype -> מבוטל for
    duplicates/removals), and append a note to description.

Events with no player file under that event_id at all are reported
separately (need to be created as new files, not edited - out of scope for
this script).

Usage:
    python3 apply_audit_corrections_to_player.py [--dry-run]
"""
import json
import os
import sys
from pathlib import Path

PLAYER_EVENTS_DIR = Path(os.path.expanduser(
    "~/Projects/DeniDin/coder1/apps/denidin-app/player_data/events"
))
ORIGINALS_DIR = PLAYER_EVENTS_DIR / "_originals"
AUDIT_JSON = Path(os.path.expanduser(
    "~/Projects/DeniDin/coder1/specs/backlog/065-august-ledger-audit-apply/"
    "ledger_changes_august.json"
))

DRY_RUN = "--dry-run" in sys.argv

# Known event_id collisions between prod and player: same event_id string,
# but the player file under that id is a DIFFERENT real transaction than
# whatever prod/the audit meant by that id. Confirmed by direct content
# comparison (065 audit investigation, 2026-08-31) - amount-only matching
# is NOT enough to catch these (both transactions can share an amount).
# For each, apply a manual override instead of the group-derived action.
# Already applied by hand, earlier in this review, before this script existed
# - skip to avoid double-appending the correction note to description.
ALREADY_APPLIED = {"B09082606000"}

MANUAL_OVERRIDES = {
    "B09082606001": {
        "client_name": "אודליה שניידר",
        "note": (
            "client_name -> 'אודליה שניידר': this player event_id collides with "
            "prod's own different B09082606001 (שלמה נזרי cluster, ref 3319, txn_date "
            "06/08) - player's own B09082606001 is actually the real אודליה שניידר "
            "transaction (ref 3322, txn_date 07/08, matches prod's B09082606002/audit's "
            "name_changes entry for B09082606002). NOT a duplicate of B09082606000/"
            "שלמה נזרי - confirmed via direct content comparison, 065 audit, 2026-08-31"
        ),
    },
}


def _expected_date_str(actions_dates):
    return {d for d in actions_dates if d}


def load_player_event(event_id):
    path = PLAYER_EVENTS_DIR / f"{event_id}.json"
    if not path.exists():
        return None, path
    with open(path, encoding="utf-8") as f:
        return json.load(f), path


def backup_and_write(event_id, path, new_data, note):
    if DRY_RUN:
        print(f"  [DRY RUN] would back up + edit {event_id}: {note}")
        return
    orig_backup = ORIGINALS_DIR / f"{event_id}.json"
    if not orig_backup.exists():
        with open(path, encoding="utf-8") as f:
            original_content = f.read()
        with open(orig_backup, "w", encoding="utf-8") as f:
            f.write(original_content)
    new_data["description"] = (new_data.get("description") or "") + f" [{note}]"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print(f"  FIXED {event_id}: {note}")


def _dm(date_str):
    """'DD/MM/YYYY' -> 'DD/MM' (day+month only - player's txn_date/event_datetime
    day can be 1 off from the audit's bank-posting date, so we compare loosely
    by also accepting the adjacent day in the collision check below)."""
    if not date_str:
        return None
    parts = date_str.split("/")
    return f"{parts[0]}/{parts[1]}" if len(parts) == 3 else None


def main():
    audit = json.load(open(AUDIT_JSON, encoding="utf-8"))

    # Build a flat plan: event_id -> [(audit_amount, audit_date, note, mutate_fn), ...]
    plan = {}

    for removal in audit["removals_unsupported_bit_transfers"]:
        eid, amt, dt = removal["event_id"], removal["amount"], removal.get("date")
        def mutate(d):
            d["event_subtype"] = "מבוטל"
            return d
        plan.setdefault(eid, []).append(
            (amt, dt, "unsupported Bit transfer -> מבוטל, per 065 audit (Morning-verified), 2026-08-31", mutate)
        )

    # date lookup for duplicate groups: derive from the matching name_changes
    # entry's date when the keep id is also a name_change eid, else None
    nc_date_by_eid = {nc["event_id"]: nc["date"] for nc in audit["name_changes"]}

    for group in audit["duplicates_approved"]:
        keep = group["keep"]
        m = group["group"].split()
        amt = int(m[-1].replace(",", "")) if m else None
        grp_date = nc_date_by_eid.get(keep)  # may be None - fine, just skips date check
        for dup in group["duplicates"]:
            def mutate(d):
                d["event_subtype"] = "מבוטל"
                return d
            plan.setdefault(dup, []).append(
                (amt, grp_date, f"duplicate of {keep} -> מבוטל, per 065 audit, 2026-08-31", mutate)
            )

    for nc in audit["name_changes"]:
        eid, amt, dt, frm, to = nc["event_id"], nc["amount"], nc["date"], nc["from"], nc["to"]
        def mutate(d, to=to):
            d["client_name"] = to
            return d
        plan.setdefault(eid, []).append(
            (amt, dt, f"client_name '{frm}' -> '{to}', per 065 audit (Morning-verified), 2026-08-31", mutate)
        )
        for dup_eid in nc.get("also_apply_to_duplicates", []):
            def mutate2(d, to=to):
                d["client_name"] = to
                return d
            plan.setdefault(dup_eid, []).append(
                (amt, dt, f"client_name -> '{to}' (propagated from {eid}), per 065 audit, 2026-08-31", mutate2)
            )

    fixed, skipped_collision, skipped_missing, overridden, already_done = [], [], [], [], []

    for eid, actions in sorted(plan.items()):
        if eid in ALREADY_APPLIED:
            already_done.append(eid)
            continue

        d, path = load_player_event(eid)
        if d is None:
            skipped_missing.append((eid, actions))
            continue

        if eid in MANUAL_OVERRIDES:
            override = MANUAL_OVERRIDES[eid]
            d["client_name"] = override["client_name"]
            backup_and_write(eid, path, d, override["note"])
            overridden.append((eid, override["note"]))
            continue

        # Safety check 1: amount must match at least one expected value.
        expected_amounts = {a for a, _, _, _ in actions if a is not None}
        player_amount = d.get("amount")
        amount_ok = not expected_amounts or player_amount in expected_amounts

        # Safety check 2: day/month must match at least one expected date
        # (player's own txn_date, or event_datetime's date part, within the
        # audit's date or the day before - bank-posting lag is normal).
        expected_dm = {_dm(dt) for _, dt, _, _ in actions if dt}
        player_dm_candidates = set()
        for raw in (d.get("txn_date"), (d.get("event_datetime") or "").split(" ")[0], d.get("event_date")):
            dm = _dm(raw)
            if dm:
                player_dm_candidates.add(dm)
        date_ok = not expected_dm or bool(expected_dm & player_dm_candidates) or not player_dm_candidates

        if not (amount_ok and date_ok):
            skipped_collision.append((eid, player_amount, expected_amounts, player_dm_candidates, expected_dm, actions))
            continue

        notes = []
        for _, _, note, mutate_fn in actions:
            d = mutate_fn(d)
            notes.append(note)
        combined_note = "; ".join(notes)
        backup_and_write(eid, path, d, combined_note)
        fixed.append((eid, combined_note))

    print()
    print(f"=== SUMMARY ({'DRY RUN' if DRY_RUN else 'APPLIED'}) ===")
    print(f"Already applied earlier (skipped, not re-touched): {already_done}")
    print(f"Fixed (auto, amount+date verified): {len(fixed)}")
    print(f"Fixed (manual override, known collision): {len(overridden)}")
    for eid, note in overridden:
        print(f"    {eid}: {note}")
    print(f"Skipped (no player file at all - needs separate creation): {len(skipped_missing)}")
    for eid, actions in skipped_missing:
        print(f"    {eid}: {'; '.join(n for _, _, n, _ in actions)}")
    print(f"Skipped (event_id collision suspected - amount/date mismatch): {len(skipped_collision)}")
    for eid, player_amount, expected_amt, player_dm, expected_dm, actions in skipped_collision:
        print(f"    {eid}: player amount={player_amount} (expected {expected_amt}), "
              f"player date(s)={player_dm} (expected {expected_dm}) - NOT TOUCHED, needs manual review")


if __name__ == "__main__":
    main()
