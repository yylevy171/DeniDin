#!/usr/bin/env python3
"""Copy the 8 real prod events (all dated after 19/08/2026, so outside the
player replay's own processed range) into player_data/events, converting
each from prod's old schema_version=1 shape to the real, current
schema_version=2 shape (see LedgerEventManager.CURRENT_SCHEMA_VERSION /
SCHEMA_VERSION_HISTORY), and correcting client_name to the Morning source of
truth (august_ledger_vs_morning.csv). Approved 2026-08-31.

Schema v2 field set (34 fields, taken from a real, live v2 prod event,
B28082611200) = the old set minus {due_date, invoice_actual_creation_date,
invoice_number, invoice_status, invoice_type, morning_document_id} plus the
5 accounting_document_* fields (display_number, payment_method, status,
status_code, status_label) - all left null here since none of these 8 have
gone through the app's own document-linking/reconciliation pipeline.

event_id is preserved unchanged from prod (verified: none collide with any
existing player event_id).
"""
import json
from pathlib import Path

PROD_DIR = Path.home() / "denidin-winprod-data" / "events"
PLAYER_DIR = Path("/Users/yaron/Projects/DeniDin/coder1/apps/denidin-app/player_data/events")

SCHEMA_V2_FIELDS = [
    "accounting_document_display_number", "accounting_document_payment_method",
    "accounting_document_status", "accounting_document_status_code",
    "accounting_document_status_label", "agreement_id", "amount", "bank_account",
    "bank_branch", "bank_number", "captured_at", "client_name", "component_id",
    "component_label", "description", "event_datetime", "event_id",
    "event_subtype", "hourly_rate", "hours", "message_id", "payer_name",
    "percent", "percent_base", "reference", "reference_hint", "schema_version",
    "session_id", "source_type", "split_partner", "split_percent",
    "trigger_condition", "txn_date", "vat_status",
]

# (prod source event_id, correct Morning name, note)
ITEMS = [
    ("B23082606010", "אתי אסולין",
     "copied from prod (dated after 19/08, outside player replay window); "
     "client_name 'אסולין אסתר' -> 'אתי אסולין' per Morning (doc 130122); "
     "prod also has a duplicate B23082606020 (same amount/date, not copied here - "
     "needs its own duplicate-handling decision)"),
    ("B23082606050", "מקורות",
     "copied from prod (dated after 19/08, outside player replay window); "
     "client_name already correct ('מקורות') per Morning (doc 112309)"),
    ("B23082606560", "גדי רוזן",
     "copied from prod (dated after 19/08, outside player replay window); "
     "client_name 'שושנה רוזן' -> 'גדי רוזן' per Morning (doc 112310), matching "
     "the same correction already approved in ledger_changes_august.json; prod "
     "also has a duplicate B23082607030 (not copied here)"),
    ("B24082606100", "אורלי גרינפלד",
     "copied from prod (dated after 19/08, outside player replay window); "
     "client_name 'גרינפלד אורלי' -> 'אורלי גרינפלד' per Morning (doc 112311)"),
    ("B25082609180", "גלית סיטבון",
     "copied from prod (dated after 19/08, outside player replay window); "
     "client_name 'סיטיבנק ישראל גי' -> 'גלית סיטבון' per Morning (doc 112312), "
     "matching ledger_changes_august.json"),
    ("B27082606300", "דודי אדלר",
     "copied from prod (dated after 19/08, outside player replay window); "
     "client_name 'דודי חיפה' -> 'דודי אדלר' per Morning (doc 130123), matching "
     "ledger_changes_august.json"),
    ("B27082609150", "יעל לוריא",
     "copied from prod (dated after 19/08, outside player replay window); "
     "client_name 'לור יעל' -> 'יעל לוריא' per Morning (doc 112313), matching "
     "ledger_changes_august.json"),
    ("B28082611200", "רמי בן חמו",
     "copied from prod (dated after 19/08, outside player replay window); "
     "client_name 'רוני רמי בן חמו' -> 'רמי בן חמו' per Morning (doc 130124), "
     "matching ledger_changes_august.json"),
]


def main():
    for event_id, correct_name, note in ITEMS:
        src_path = PROD_DIR / f"{event_id}.json"
        with open(src_path, encoding="utf-8") as f:
            prod = json.load(f)

        dest_path = PLAYER_DIR / f"{event_id}.json"
        if dest_path.exists():
            print(f"SKIP {event_id}: already exists in player - not overwriting")
            continue

        new_event = {field: prod.get(field) for field in SCHEMA_V2_FIELDS}
        new_event["client_name"] = correct_name
        new_event["schema_version"] = 2
        new_event["description"] = (prod.get("description") or "") + f" [{note}, 2026-08-31]"

        with open(dest_path, "w", encoding="utf-8") as f:
            json.dump(new_event, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
        print(f"CREATED {event_id}: client_name={correct_name!r}, schema_version=2")


if __name__ == "__main__":
    main()
