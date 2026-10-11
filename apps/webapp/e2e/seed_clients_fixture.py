"""Feature 087 — Clients-tab acceptance fixture (separate from seed_fixture.py, which the
Feature 068 suite owns and this leaves untouched).

Real stack, no mocking: writes a deterministic on-disk data root (ledger events, password hash,
an empty webapp_data/clients) and a backend config wired to the REAL Morning SANDBOX. The
official client list is whatever the sandbox holds, so the seeder asks the sandbox for it and
builds the ledger events around the first real client it finds (read-only search call only -
nothing is ever created in Morning).

Morning sandbox credentials are read at run time from this clone's own gitignored
apps/webapp/backend/config/config.dev.json (sandbox URLs + key); nothing secret is written
anywhere tracked - the generated config lands in the gitignored .fixture/.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE_ROOT = HERE / ".fixture" / "clients"
PASSWORD = "e2e-pass"
PASSWORD_SALT = "denidin-pw"  # webapp_backend.auth.PASSWORD_SALT
PORT = 8132

DEV_CONFIG = HERE.parent / "backend" / "config" / "config.dev.json"
MORNING_SRC = HERE.parents[1] / "morning-mcp-app" / "src"

UNMATCHED_RAW_NAME = "e2e-לקוח-שאינו-קיים-במורנינג"
AGREEMENT_MARKER = "e2e-agreement-marker"
INVOICE_MARKER = "e2e-invoice-marker"
UNMATCHED_MARKER = "e2e-unmatched-marker"

# Feature 092 - extra real sandbox clients (names[1:], so Feature 087's names[0] client is
# untouched) and the data each approved UAT needs. Additive only: every 087 event/manifest key
# above stays exactly as it was.
F092_ROLES = [
    "debt_client",      # UAT 1: agreed 10,000 / paid 2,000 (red)
    "paid_client",      # UAT 2: agreed 3,000 / paid 3,000 (green, computed)
    "past_client",      # UAT 4: activity only before 2025-09-01 (gray)
    "target_a",         # UAT 3 buttons + UAT 6 mapping target
    "target_b",         # UAT 6 + UAT 7 mapping target
    "mig_check",        # UAT 5: comment "לבדוק"  -> migrated to check
    "mig_active",       # UAT 5: comment "לקוח פעיל" -> migrated to active
    "mig_closed",       # UAT 5: comment "לסגור" -> migrated to closed, real amounts kept
    "yellow_no_agreement",  # manual testing only: paid 1,500, no agreement (yellow)
    "yellow_overpaid",      # manual testing only: agreed 2,000 / paid 2,600 (yellow)
]
YISRAEL_RAW_NAME = "Yisrael I"
YISRAEL_NOTE = "שילם במזומן"
HIDE_RAW_NAME = "e2e-שם-להסרה"
UNKNOWN_EVENTS = [("B01e2e09001", 500, 10), ("B01e2e09002", 1200, 9), ("B01e2e09003", 3000, 8)]
LATE_UNKNOWN_EVENT = ("B01e2e09000", 999, 30)  # written mid-test by UAT 6 (older date)


def _official_client_names(cfg: dict) -> list:
    sys.path.insert(0, str(MORNING_SRC))
    from denidin_mcp_morning.morning_client import MorningClient  # noqa: E402

    client = MorningClient(
        api_key_id=cfg["morning_api_key_id"],
        api_key_secret=cfg["morning_api_key_secret"],
        auth_url=cfg["morning_auth_url"],
        base_url=cfg["morning_api_url"],
    )
    items = client.search_clients({"pageSize": 100}).get("items") or []
    names = sorted({str(i.get("name", "")).strip() for i in items if str(i.get("name", "")).strip()})
    if len(names) < 1 + len(F092_ROLES):
        raise SystemExit("Morning sandbox returned too few clients - cannot build the Clients fixture")
    return names


def _event(events_dir: Path, event_id: str, when: datetime, **fields) -> None:
    rec = {
        "event_id": event_id,
        "source_type": None,
        "event_subtype": None,
        "client_name": None,
        "amount": None,
        "description": None,
        "session_id": None,
        "message_id": None,
        "vat_status": None,
        "event_datetime": when.strftime("%d/%m/%Y %H:%M"),
        "captured_at": when.isoformat(),
    }
    rec.update(fields)
    (events_dir / f"{event_id}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    dev = json.loads(DEV_CONFIG.read_text(encoding="utf-8"))
    for key in ("morning_api_key_id", "morning_api_key_secret"):
        if not dev.get(key) or "PASTE" in dev[key]:
            raise SystemExit(f"{DEV_CONFIG}: {key} is not set - the Clients fixture needs the Morning sandbox key")

    names = _official_client_names(dev)
    official = names[0]
    f092 = dict(zip(F092_ROLES, names[1:1 + len(F092_ROLES)]))

    if FIXTURE_ROOT.exists():
        shutil.rmtree(FIXTURE_ROOT)
    events = FIXTURE_ROOT / "events"
    clients = FIXTURE_ROOT / "webapp_data" / "clients"
    for d in (events, clients, FIXTURE_ROOT / "auth"):
        d.mkdir(parents=True, exist_ok=True)
    for name in ("client_comments.json", "client_mapping.json", "mapping_notes.json"):
        (clients / name).write_text("{}", encoding="utf-8")
    # Feature 092 UAT 5: legacy routing keywords in comments and NO migrations.json, so the
    # backend's first report performs a real first-run migration.
    (clients / "client_comments.json").write_text(json.dumps({
        f092["mig_check"]: "לבדוק",
        f092["mig_active"]: "לקוח פעיל",
        f092["mig_closed"]: "לסגור",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    (clients / "mapping_notes.json").write_text(json.dumps(
        {YISRAEL_RAW_NAME: YISRAEL_NOTE}, ensure_ascii=False, indent=2), encoding="utf-8")
    (FIXTURE_ROOT / "auth" / "password.hash").write_text(
        hashlib.sha256((PASSWORD_SALT + PASSWORD).encode()).hexdigest(), encoding="utf-8"
    )

    now = datetime.now().replace(second=0, microsecond=0)
    _event(events, "A01e2e00001", now - timedelta(days=10), source_type="הסכם", event_subtype="יצירה",
           client_name=official, amount=1000, description=AGREEMENT_MARKER)
    _event(events, "C01e2e00002", now - timedelta(days=5), source_type="חשבונית",
           event_subtype="חשבונית מס קבלה", client_name=official, amount=400, description=INVOICE_MARKER)
    _event(events, "B01e2e00003", now - timedelta(days=3), source_type="בנק", event_subtype="הפקדה",
           client_name=UNMATCHED_RAW_NAME, amount=250, description=UNMATCHED_MARKER)

    # ---- Feature 092 events ----
    agreement, paid = ("הסכם", "יצירה"), ("חשבונית", "חשבונית מס קבלה")
    f092_events = [
        ("A01e2e09101", "debt_client", agreement, 10000, 6),
        ("C01e2e09102", "debt_client", paid, 2000, 5),
        ("A01e2e09103", "paid_client", agreement, 3000, 6),
        ("C01e2e09104", "paid_client", paid, 3000, 5),
        ("A01e2e09106", "target_a", agreement, 10000, 6),
        ("A01e2e09107", "target_b", agreement, 10000, 6),
        ("A01e2e09108", "mig_check", agreement, 4000, 6),
        ("A01e2e09109", "mig_active", agreement, 4000, 6),
        ("A01e2e09110", "mig_closed", agreement, 5000, 6),
        ("C01e2e09111", "mig_closed", paid, 1000, 5),
        ("C01e2e09114", "yellow_no_agreement", paid, 1500, 5),
        ("A01e2e09115", "yellow_overpaid", agreement, 2000, 6),
        ("C01e2e09116", "yellow_overpaid", paid, 2600, 5),
    ]
    for eid, role, (src, sub), amount, days in f092_events:
        _event(events, eid, now - timedelta(days=days), source_type=src, event_subtype=sub,
               client_name=f092[role], amount=amount, description=f"e2e-092-{role}")
    _event(events, "A01e2e09105", datetime(2025, 6, 15, 10, 0), source_type="הסכם", event_subtype="יצירה",
           client_name=f092["past_client"], amount=4000, description="e2e-092-past_client")
    for eid, amount, days in UNKNOWN_EVENTS:
        _event(events, eid, now - timedelta(days=days), source_type="חשבונית",
               event_subtype="חשבונית מס קבלה", client_name=None, amount=amount,
               description=f"e2e-092-unknown-{amount}")
    _event(events, "C01e2e09112", now - timedelta(days=4), source_type="חשבונית",
           event_subtype="חשבונית מס קבלה", client_name=YISRAEL_RAW_NAME, amount=700,
           description="e2e-092-yisrael")
    _event(events, "B01e2e09113", now - timedelta(days=4), source_type="בנק", event_subtype="הפקדה",
           client_name=HIDE_RAW_NAME, amount=50, description="e2e-092-hide")

    cfg = {
        "environment": "test",
        "denidin_data_root": str(FIXTURE_ROOT),
        "denidin_src_path": "",
        "password_hash_file": str(FIXTURE_ROOT / "auth" / "password.hash"),
        "session_expiry_hours": 168,
        "webapp_data_root": str(FIXTURE_ROOT / "webapp_data"),
        "clients_data_root": "",
        "morning_api_key_id": dev["morning_api_key_id"],
        "morning_api_key_secret": dev["morning_api_key_secret"],
        "morning_auth_url": dev["morning_auth_url"],
        "morning_api_url": dev["morning_api_url"],
        # INFO, not WARNING: bugfix-066's /health "logs_writing" check needs fresh log lines
        # (startup + heartbeat are INFO); at WARNING /health is 503 and Playwright's webServer
        # wait never succeeds.
        "http": {"host": "127.0.0.1", "port": PORT, "log_level": "INFO"},
    }
    (FIXTURE_ROOT / "config.clients.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    manifest = {
        "password": PASSWORD,
        "root": str(FIXTURE_ROOT),
        "official_client": official,
        "unmatched_raw_name": UNMATCHED_RAW_NAME,
        "agreement_marker": AGREEMENT_MARKER,
        "invoice_marker": INVOICE_MARKER,
        "unmatched_marker": UNMATCHED_MARKER,
        "comments_file": str(clients / "client_comments.json"),
        "mapping_file": str(clients / "client_mapping.json"),
        # Feature 092
        **f092,
        "events_dir": str(events),
        "status_file": str(clients / "client_status.json"),
        "hidden_file": str(clients / "hidden_unmatched.json"),
        "migrations_file": str(clients / "migrations.json"),
        "notes_file": str(clients / "mapping_notes.json"),
        "yisrael_raw_name": YISRAEL_RAW_NAME,
        "yisrael_note": YISRAEL_NOTE,
        "hide_raw_name": HIDE_RAW_NAME,
        "unknown_events": [{"event_id": e, "amount": a} for e, a, _ in UNKNOWN_EVENTS],
        "late_unknown_event": {"event_id": LATE_UNKNOWN_EVENT[0], "amount": LATE_UNKNOWN_EVENT[1],
                               "event_datetime": (now - timedelta(days=LATE_UNKNOWN_EVENT[2])).strftime("%d/%m/%Y %H:%M")},
    }
    (FIXTURE_ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"seeded {FIXTURE_ROOT} (official client picked from the Morning sandbox)", file=sys.stderr)


if __name__ == "__main__":
    main()
