#!/usr/bin/env python3
"""
One-off migration script (Feature 033, US4/REQ-MIGRATE-001).

Migrates the 3 combined `pending_ledger_events` records in session
4454746c-350a-4fa7-a5ef-fda2c685b0d5's session.json (captured live 2026-07-28,
predating this feature) into 6 new-format files under {events_dir}, split per
fee-component per this feature's design.

Hardcoded for this ONE specific historical session - not general-purpose
splitting logic. Source data and the agreed component split are documented in
specs/in-progress/033-ledger-event-persistence/data-model.md's migration
appendix; the raw text below is copied verbatim from that session's real
session.json, not paraphrased.

Each component's message_id is the real source message id, recovered from the
session's own messages/*.json files by matching verbatim content (revised
2026-07-30 - message_id is no longer left null for migrated events). The 3
source message files also get their ledger_event_ids patched for two-way
traceability. agreement_label/component_label are hand-written (same as the
existing hand-written description/notes) - REQ-DATA-004's agreement_id/
component_id are then derived from them via LedgerEventManager.build_agreement_id,
computed once per record so every component of one record shares an identical
agreement_id, never typed out by hand per component.

Usage:
    python3 scripts/migrate_stray_ledger_events.py --dry-run
    python3 scripts/migrate_stray_ledger_events.py
    python3 scripts/migrate_stray_ledger_events.py --session-file <path> --events-dir <path>
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.managers.ledger_event_manager import LedgerEventManager  # noqa: E402  pylint: disable=wrong-import-position

SESSION_ID = "4454746c-350a-4fa7-a5ef-fda2c685b0d5"
WHATSAPP_CHAT = "972522968679@c.us"
SENDER = "972522968679@c.us"

DEFAULT_SESSION_FILE = f"dev_data/sessions/{SESSION_ID}/session.json"
DEFAULT_EVENTS_DIR = "dev_data/events"
DEFAULT_MESSAGES_DIR = f"dev_data/sessions/{SESSION_ID}/messages"

# Real source message ids, recovered from dev_data/sessions/{SESSION_ID}/messages/*.json
# by matching verbatim content (2026-07-30) - see data-model.md's migration appendix.
GILYAN_MESSAGE_ID = "fc384625-f765-4585-a792-b5de2b44a3d0"
SARIT_MESSAGE_ID = "b3a2afb0-86d4-4dc7-a98b-094d34682406"
MALKA_MESSAGE_ID = "6a6fd63f-696a-43c4-93b0-6f63178d0a64"


def _epoch(iso_ts: str) -> int:
    return int(datetime.fromisoformat(iso_ts).timestamp())


def build_components() -> List[Dict]:
    """Returns the 6 component records to migrate, each shaped as
    {session_id, whatsapp_chat, sender, message_id, message_timestamp (epoch),
    event (the 19-key capture_ledger_event arguments dict, including
    agreement_label/component_label/txn_date)} - ready to pass straight into
    LedgerEventManager.add_ledger_event (agreement_id computed separately, once
    per record, by run_migration)."""

    gilyan_raw_excerpt = (
        "גיליאן דוידיאן\n"
        "משרד הרווחה\n\n"
        "1. אם יהיה שימוע להשעיה - 8,000₪\n"
        "2. ⁠למידת תיק החקירה וניהול משא ומתן מול התביעה בניסיון להגיע להסדר טיעון - 20,000₪\n"
        "3. ⁠אם המשא ימתן יכשל ונאלץ לנהל הוכחות ימשפט שלום - עוד 30,000₪"
    )
    gilyan_notes = (
        "מדובר בשלושה שלבים/תרחישים מצטברים או מותנים, לפי הניסוח: 8,000₪ אם יהיה "
        "שימוע להשעיה; 20,000₪ עבור לימוד התיק וניהול משא ומתן להסדר טיעון; ועוד "
        "30,000₪ אם המשא ומתן ייכשל ויידרש ניהול הוכחות בבית משפט שלום. לא ברור אם "
        "20,000₪ כוללים את שלב השימוע או מתווספים אליו."
    )
    gilyan_ts = _epoch("2026-07-28T11:06:58+00:00")
    gilyan_base = {
        "session_id": SESSION_ID, "whatsapp_chat": WHATSAPP_CHAT, "sender": SENDER,
        "message_id": GILYAN_MESSAGE_ID, "message_timestamp": gilyan_ts,
    }

    def gilyan_component(description: str, amount: str, component_label: str) -> Dict:
        return {
            **gilyan_base,
            "event": {
                "source_type": "הסכם", "event_subtype": "יצירה",
                "client_name": "גיליאן דוידיאן", "payer_name": None,
                "description": description, "amount": amount,
                "percent": None, "percent_base": None, "hours": None, "hourly_rate": None,
                "vat_status": "לא צוין", "replaces_hint": None,
                "reference_hint": "משרד הרווחה", "notes": gilyan_notes,
                "raw_message_excerpt": gilyan_raw_excerpt,
                "agreement_label": "משרד הרווחה", "component_label": component_label,
            },
        }

    sarit_raw_excerpt = (
        "טקסט מופק של הצעת שכר טרחה: בין עו\"ד שרית יוגב ומרדכי רצבגר (להלן - "
        "הלקוחות) לבין עו\"ד אילה הוניגמן (להלן - עוה\"ד). מצוין: \"שכר טרחה בסך "
        "של 1,500 ש\"ח כולל מע\"מ\" עבור כתיבת מכתב; וכן \"10,000 ש\"ח כולל מע\"מ\" "
        "עבור הגשת כתב תביעה והישיבה בבית הדין לעבודה. בסוף: תאריך 2.6.26, "
        "www.honigman-law.com, Ah@honigman-law.com, tel 050-6205544, fax 077-4701835."
    )
    sarit_reference_hint = (
        "עו\"ד אילה הוניגמן מצוינת כעוה\"ד במסמך; מצוין גם דוא\"ל "
        "Ah@honigman-law.com וטלפון 050-6205544."
    )
    sarit_notes = (
        "הטקסט מכיל קטעי OCR משובשים מאוד. לא ניתן לחלץ בוודאות את מלוא תנאי שכר "
        "הטרחה, לרבות סעיפים אפשריים הנוגעים להמשך הליכים או אחוזים. התאריך 2.6.26 "
        "מופיע בסיכום שסופק, אך אינו מופיע בבירור בגוף הטקסט."
    )
    sarit_ts = _epoch("2026-07-28T11:23:22+00:00")
    sarit_base = {
        "session_id": SESSION_ID, "whatsapp_chat": WHATSAPP_CHAT, "sender": SENDER,
        "message_id": SARIT_MESSAGE_ID, "message_timestamp": sarit_ts,
    }

    def sarit_component(description: str, amount: str, component_label: str) -> Dict:
        return {
            **sarit_base,
            "event": {
                "source_type": "הסכם", "event_subtype": "יצירה",
                "client_name": "עו\"ד שרית יוגב ועו\"ד מרדכי רצבגר", "payer_name": None,
                "description": description, "amount": amount,
                "percent": None, "percent_base": None, "hours": None, "hourly_rate": None,
                "vat_status": "כולל", "replaces_hint": None,
                "reference_hint": sarit_reference_hint, "notes": sarit_notes,
                "raw_message_excerpt": sarit_raw_excerpt,
                "agreement_label": "שירות המילואים", "component_label": component_label,
            },
        }

    malka_ts = _epoch("2026-07-28T11:26:44+00:00")
    malka_component = {
        "session_id": SESSION_ID, "whatsapp_chat": WHATSAPP_CHAT, "sender": SENDER,
        "message_id": MALKA_MESSAGE_ID, "message_timestamp": malka_ts,
        "event": {
            "source_type": "בנק", "event_subtype": "הפקדה",
            "client_name": "מלכה בן סעדון לירון עו\"ד", "payer_name": None,
            "description": "שכר טרחה", "amount": "₪12,500.00",
            "percent": None, "percent_base": None, "hours": None, "hourly_rate": None,
            "vat_status": "לא צוין", "replaces_hint": None,
            "reference_hint": None,
            "notes": (
                "הטקסט מציין העברה מחשבון על שם מלכה בן סעדון לירון עו\"ד; לא צוין "
                "במפורש מי הלקוח או מי המוטב."
            ),
            "raw_message_excerpt": (
                "טקסט מופק: העברה ממלכה בן סעדון לירון עו\"ד לירון עו\"ד; ₪12,500.00; "
                "16/07/26; 16/07/2026 יום ערך; מספר אסמכתא 3273; ערוץ ביצוע אינטרנט; "
                "שם חשבון מחויב מלכה בן סעדון לירון עו\"ד; מספר בנק מחויב 11; מספר "
                "סניף מחויב 99; מספר חשבון מחויב 5650560; סניף בו בוצעה הפעולה 0219 "
                "טלבנק; שכר טרחה. סוג מסמך: העברת תשלום."
            ),
            "agreement_label": None, "component_label": None,
        },
    }

    return [
        gilyan_component("שימוע להשעיה", "8,000₪", "שימוע להשעיה"),
        gilyan_component(
            "לימוד תיק החקירה וניהול משא ומתן מול התביעה בניסיון להגיע להסדר טיעון",
            "20,000₪", "הסדר טיעון",
        ),
        gilyan_component(
            "ניהול הוכחות בבית משפט שלום, ככל שהמשא ומתן ייכשל", "30,000₪",
            "הוכחות בבית משפט שלום",
        ),
        sarit_component("כתיבת מכתב מטעם הלקוחות לנציגת שירות המילואים", "1,500 ש\"ח כולל מע\"מ", "כתיבת מכתב"),
        sarit_component(
            "הליכים בבית הדין לעבודה, לרבות הגשת כתב תביעה והישיבה בבית הדין",
            "10,000 ש\"ח כולל מע\"מ", "כתב תביעה",
        ),
        malka_component,
    ]


def _patch_message_ledger_event_ids(messages_dir: Path, ids_by_message: Dict[str, List[str]]) -> None:
    """REQ-MIGRATE-001 (revised 2026-07-30): two-way traceability on migrated data
    too - each source message file's ledger_event_ids gains the resulting
    event_id(s), same field Message already carries for live captures."""
    for message_id, event_ids in ids_by_message.items():
        message_file = messages_dir / f"{message_id}.json"
        with message_file.open(encoding="utf-8") as f:
            message_data = json.load(f)
        message_data["ledger_event_ids"] = event_ids
        with message_file.open("w", encoding="utf-8") as f:
            json.dump(message_data, f, ensure_ascii=False, indent=2, sort_keys=True)
        print(f"Patched {message_file} with ledger_event_ids={event_ids}")


def run_migration(session_file: Path, events_dir: str, messages_dir: Path, dry_run: bool) -> int:
    """Returns 0 on success, 1 on failure. Never clears pending_ledger_events
    from session_file unless every component was written successfully first
    (contracts/ledger-event-manager.md's migration-script contract)."""
    components = build_components()

    if dry_run:
        print(f"DRY RUN - would write {len(components)} files to {events_dir}, "
              f"patch message files under {messages_dir}, then clear "
              f"pending_ledger_events from {session_file}\n")
        for i, c in enumerate(components):
            print(f"--- component {i} ({c['event']['client_name']!r}, "
                  f"{c['event']['description']!r}, amount={c['event']['amount']!r}, "
                  f"message_id={c['message_id']!r}, "
                  f"agreement_label={c['event']['agreement_label']!r}, "
                  f"component_label={c['event']['component_label']!r}) ---")
        return 0

    manager = LedgerEventManager(storage_dir=events_dir)

    # REQ-DATA-004: compute agreement_id once per record (message_id), not once per
    # component - every component sharing a message_id shares one agreement_id.
    agreement_id_by_message: Dict[str, str] = {}
    for c in components:
        if c["event"]["source_type"] != "הסכם" or c["message_id"] in agreement_id_by_message:
            continue
        agreement_id_by_message[c["message_id"]] = manager.build_agreement_id(
            c["event"]["client_name"], c["event"]["agreement_label"], c["message_timestamp"],
        )

    written_ids = []
    ids_by_message: Dict[str, List[str]] = {}
    for c in components:
        event_id = manager.add_ledger_event(
            session_id=c["session_id"], whatsapp_chat=c["whatsapp_chat"],
            event=c["event"], message_id=c["message_id"],
            message_timestamp=c["message_timestamp"], sender=c["sender"],
            agreement_id=agreement_id_by_message.get(c["message_id"]),
        )
        if event_id is None:
            print(
                f"ERROR: failed to persist component (client="
                f"{c['event'].get('client_name')!r}) - aborting, NOT clearing "
                f"{session_file}", file=sys.stderr,
            )
            return 1
        written_ids.append(event_id)
        ids_by_message.setdefault(c["message_id"], []).append(event_id)
        print(f"Wrote {event_id}")

    _patch_message_ledger_event_ids(messages_dir, ids_by_message)

    with session_file.open(encoding="utf-8") as f:
        session_data = json.load(f)
    session_data.pop("pending_ledger_events", None)
    with session_file.open("w", encoding="utf-8") as f:
        json.dump(session_data, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"\nCleared pending_ledger_events from {session_file}")
    print(f"Migration complete: {len(written_ids)} events written: {written_ids}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-file", default=DEFAULT_SESSION_FILE)
    parser.add_argument("--events-dir", default=DEFAULT_EVENTS_DIR)
    parser.add_argument("--messages-dir", default=DEFAULT_MESSAGES_DIR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    session_file = Path(args.session_file)
    if not session_file.exists():
        print(f"ERROR: session file not found: {session_file}", file=sys.stderr)
        sys.exit(2)

    sys.exit(run_migration(session_file, args.events_dir, Path(args.messages_dir), args.dry_run))


if __name__ == "__main__":
    main()
