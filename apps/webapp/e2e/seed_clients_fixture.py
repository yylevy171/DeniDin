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


def _official_client_name(cfg: dict) -> str:
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
    if not names:
        raise SystemExit("Morning sandbox returned no clients - cannot build the Clients fixture")
    return names[0]


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

    official = _official_client_name(dev)

    if FIXTURE_ROOT.exists():
        shutil.rmtree(FIXTURE_ROOT)
    events = FIXTURE_ROOT / "events"
    clients = FIXTURE_ROOT / "webapp_data" / "clients"
    for d in (events, clients, FIXTURE_ROOT / "auth"):
        d.mkdir(parents=True, exist_ok=True)
    for name in ("client_comments.json", "client_mapping.json", "mapping_notes.json"):
        (clients / name).write_text("{}", encoding="utf-8")
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
        "http": {"host": "127.0.0.1", "port": PORT, "log_level": "WARNING"},
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
    }
    (FIXTURE_ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"seeded {FIXTURE_ROOT} (official client picked from the Morning sandbox)", file=sys.stderr)


if __name__ == "__main__":
    main()
