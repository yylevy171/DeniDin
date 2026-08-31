#!/usr/bin/env python3
"""Reconcile real prod ledger events against player-replay ledger events.

Source of truth is ONLY the actual ledger event JSON files on disk, read fresh
on every run - no _review_decisions.jsonl, no needs_clarification.jsonl, no
ledger_changes_august.json, no prior conversation/summary content of any kind.

Produces two CSVs, for the fixed window 2026-07-01 through 2026-08-31:
  - prod_events_jul_aug_reconciliation.csv  - one row per real prod event
  - player_events_jul_aug_reconciliation.csv - one row per player-replay event

Both source_type=בנק and source_type=הסכם are included (every source_type
present in either store, actually - nothing is filtered by type).

Usage:
    python3 reconcile_prod_vs_player.py

Paths are hardcoded below (both are fixed, known locations for this task) -
edit PROD_EVENTS_DIR / PLAYER_EVENTS_DIR / OUT_DIR if they ever move.
"""
import csv
import glob
import json
import os
from datetime import date

PROD_EVENTS_DIR = os.path.expanduser("~/denidin-winprod-data/events")
PLAYER_EVENTS_DIR = os.path.expanduser(
    "~/Projects/DeniDin/coder1/apps/denidin-app/player_data/events"
)
OUT_DIR = os.path.expanduser(
    "~/Projects/DeniDin/coder1/specs/backlog/065-august-ledger-audit-apply"
)

WINDOW_START = date(2026, 7, 1)
WINDOW_END = date(2026, 8, 31)

# Fields compared directly between a prod event and its player counterpart
# (same event_id in both stores). Old prod schema and new player schema use
# the same names for all of these except "reference" (old schema calls it
# "replaced_event_id") - handled via _get_reference() below.
COMPARE_FIELDS = ["client_name", "amount", "event_subtype", "txn_date", "vat_status"]


def _load_events(dirpath):
    """Load every *.json file in dirpath into {event_id: parsed_dict}."""
    events = {}
    for path in sorted(glob.glob(os.path.join(dirpath, "*.json"))):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        eid = d.get("event_id")
        if eid:
            events[eid] = d
    return events


def _effective_date(d):
    """The event's own capture date, from whichever schema fields are present.

    New schema: event_datetime = "DD/MM/YYYY HH:MM".
    Old schema: event_date = "DD/MM/YYYY" (separate event_time field, unused here).
    Falls back to txn_date if neither is present.
    """
    dt = d.get("event_datetime")
    if dt:
        return dt.split(" ")[0]
    ed = d.get("event_date")
    if ed:
        return ed
    return d.get("txn_date") or ""


def _parse_ddmmyyyy(s):
    if not s:
        return None
    parts = s.split("/")
    if len(parts) != 3:
        return None
    try:
        dd, mm, yyyy = (int(p) for p in parts)
        return date(yyyy, mm, dd)
    except ValueError:
        return None


def _in_window(d):
    dt = _parse_ddmmyyyy(_effective_date(d))
    return dt is not None and WINDOW_START <= dt <= WINDOW_END


def _get_reference(d):
    """reference (new schema) / replaced_event_id (old schema) - same concept."""
    return d.get("reference") if "reference" in d else d.get("replaced_event_id")


def _diff(prod_d, player_d):
    """List of "field: prod_value -> player_value" strings for every field that
    differs between the two, comparing str(value) after light normalization
    (int vs numeric-string amount, trimmed whitespace)."""
    diffs = []
    for field in COMPARE_FIELDS:
        pv = prod_d.get(field)
        yv = player_d.get(field)
        pv_n = str(pv).strip() if pv is not None else None
        yv_n = str(yv).strip() if yv is not None else None
        if pv_n != yv_n:
            diffs.append(f"{field}: {pv!r} -> {yv!r}")
    pref = _get_reference(prod_d)
    yref = _get_reference(player_d)
    pref_n = str(pref).strip() if pref else None
    yref_n = str(yref).strip() if yref else None
    if pref_n != yref_n:
        diffs.append(f"reference: {pref!r} -> {yref!r}")
    return diffs


def _sort_key(row):
    parts = (row["date"] or "").split("/")
    if len(parts) == 3:
        return (parts[2], parts[1], parts[0], row["event_id"])
    return ("", "", "", row["event_id"])


def main():
    prod = _load_events(PROD_EVENTS_DIR)
    player = _load_events(PLAYER_EVENTS_DIR)

    prod_in_window = {eid: d for eid, d in prod.items() if _in_window(d)}
    player_in_window = {eid: d for eid, d in player.items() if _in_window(d)}

    print(f"prod events on disk: {len(prod)} total, {len(prod_in_window)} in window")
    print(f"player events on disk: {len(player)} total, {len(player_in_window)} in window")

    # ---- prod CSV ----
    prod_rows = []
    for eid, d in prod_in_window.items():
        pd = player.get(eid)  # look up regardless of pd's own date/window
        if pd is None:
            action, detail = "keep", "no player counterpart with this event_id"
        else:
            diffs = _diff(d, pd)
            if diffs:
                action, detail = "modify", "; ".join(diffs)
            else:
                action, detail = "keep", "identical to player"
        prod_rows.append({
            "event_id": eid,
            "source_type": d.get("source_type"),
            "date": _effective_date(d),
            "txn_date": d.get("txn_date"),
            "client_name": d.get("client_name"),
            "amount": d.get("amount"),
            "event_subtype": d.get("event_subtype"),
            "reference": _get_reference(d),
            "in_player": pd is not None,
            "action": action,
            "detail": detail,
        })
    prod_rows.sort(key=_sort_key)

    prod_out = os.path.join(OUT_DIR, "prod_events_jul_aug_reconciliation.csv")
    with open(prod_out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "event_id", "source_type", "date", "txn_date", "client_name", "amount",
            "event_subtype", "reference", "in_player", "action", "detail",
        ])
        w.writeheader()
        w.writerows(prod_rows)

    # ---- player CSV ----
    player_rows = []
    for eid, d in player_in_window.items():
        prd = prod.get(eid)  # look up regardless of prd's own date/window
        if prd is None:
            action, detail = "add new", "no prod counterpart with this event_id"
        else:
            diffs = _diff(prd, d)
            if diffs:
                action, detail = "modify", "; ".join(diffs)
            else:
                action, detail = "no change", "identical to prod"
        player_rows.append({
            "event_id": eid,
            "source_type": d.get("source_type"),
            "date": _effective_date(d),
            "txn_date": d.get("txn_date"),
            "client_name": d.get("client_name"),
            "amount": d.get("amount"),
            "event_subtype": d.get("event_subtype"),
            "reference": _get_reference(d),
            "in_prod": prd is not None,
            "action": action,
            "detail": detail,
        })
    player_rows.sort(key=_sort_key)

    player_out = os.path.join(OUT_DIR, "player_events_jul_aug_reconciliation.csv")
    with open(player_out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "event_id", "source_type", "date", "txn_date", "client_name", "amount",
            "event_subtype", "reference", "in_prod", "action", "detail",
        ])
        w.writeheader()
        w.writerows(player_rows)

    from collections import Counter
    print("prod actions:", Counter(r["action"] for r in prod_rows), "total", len(prod_rows))
    print("player actions:", Counter(r["action"] for r in player_rows), "total", len(player_rows))
    prod_modify_ids = {r["event_id"] for r in prod_rows if r["action"] == "modify"}
    player_modify_ids = {r["event_id"] for r in player_rows if r["action"] == "modify"}
    print("modify sets identical:", prod_modify_ids == player_modify_ids,
          f"({len(prod_modify_ids)} vs {len(player_modify_ids)})")
    print(f"wrote {prod_out}")
    print(f"wrote {player_out}")


if __name__ == "__main__":
    main()
