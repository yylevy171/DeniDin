#!/usr/bin/env python3
"""Derive the Type 1 (add new to prod) and Type 2 (modify in prod) CSVs from
the existing prod_events_jul_aug_reconciliation.csv / player_events_jul_aug_
reconciliation.csv - no fresh read of the raw ledger JSON files, per the
user's "using the existing csv's" instruction (2026-08-31).

Type 1 = every player CSV row with action="add new" (event_id exists only in
player - to be copied as a new file into prod's events/).

Type 2 = every event_id with action="modify" in both CSVs (already confirmed
identical id sets by reconcile_prod_vs_player.py) - one row per event_id,
prod's current field values (prod_*) next to player's target field values
(player_*), plus the diff detail - the actual before/after change-list for
the "move prod's current file to _modified/, copy player's file in" step.

Type 3 (deletion) is NOT produced here - flagged separately, see chat.
"""
import csv
from pathlib import Path

OUT_DIR = Path("/Users/yaron/Projects/DeniDin/coder1/specs/backlog/065-august-ledger-audit-apply")
PROD_CSV = OUT_DIR / "prod_events_jul_aug_reconciliation.csv"
PLAYER_CSV = OUT_DIR / "player_events_jul_aug_reconciliation.csv"


def _read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    prod_rows = {r["event_id"]: r for r in _read(PROD_CSV)}
    player_rows = {r["event_id"]: r for r in _read(PLAYER_CSV)}

    # ---- Type 1: add new to prod ----
    type1 = [r for r in player_rows.values() if r["action"] == "add new"]
    type1.sort(key=lambda r: (r["date"] or "", r["event_id"]))

    type1_out = OUT_DIR / "type1_add_new_to_prod.csv"
    with open(type1_out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "event_id", "source_type", "date", "txn_date", "client_name",
            "amount", "event_subtype", "reference",
        ])
        w.writeheader()
        for r in type1:
            w.writerow({k: r[k] for k in w.fieldnames})

    # ---- Type 2: modify in prod ----
    modify_ids = sorted(
        eid for eid, r in prod_rows.items() if r["action"] == "modify"
    )
    # sanity: player side must agree exactly (reconcile_prod_vs_player.py already
    # asserts this at generation time, re-checked here defensively)
    player_modify_ids = {eid for eid, r in player_rows.items() if r["action"] == "modify"}
    assert set(modify_ids) == player_modify_ids, "prod/player modify sets diverged - re-run reconcile script"

    type2 = []
    for eid in modify_ids:
        p, y = prod_rows[eid], player_rows[eid]
        type2.append({
            "event_id": eid,
            "source_type": p["source_type"],
            "date": p["date"],
            "prod_client_name": p["client_name"], "player_client_name": y["client_name"],
            "prod_amount": p["amount"], "player_amount": y["amount"],
            "prod_event_subtype": p["event_subtype"], "player_event_subtype": y["event_subtype"],
            "prod_txn_date": p["txn_date"], "player_txn_date": y["txn_date"],
            "prod_reference": p["reference"], "player_reference": y["reference"],
            "detail": p["detail"],
        })
    type2.sort(key=lambda r: (r["date"] or "", r["event_id"]))

    type2_out = OUT_DIR / "type2_modify_in_prod.csv"
    with open(type2_out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "event_id", "source_type", "date",
            "prod_client_name", "player_client_name",
            "prod_amount", "player_amount",
            "prod_event_subtype", "player_event_subtype",
            "prod_txn_date", "player_txn_date",
            "prod_reference", "player_reference",
            "detail",
        ])
        w.writeheader()
        w.writerows(type2)

    print(f"Type 1 (add new to prod): {len(type1)} rows -> {type1_out}")
    print(f"Type 2 (modify in prod): {len(type2)} rows -> {type2_out}")


if __name__ == "__main__":
    main()
