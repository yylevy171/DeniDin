"""Feature 089 - Agreements acceptance fixture (Playwright suite `tests-agreements/`).

Run with denidin-app's own interpreter from apps/denidin-app (agreements_serve.sh does this):
it seeds a throwaway data root holding a REAL Agreements DB and real ledger event files by
driving the real AgreementsManager (so the fixture state is exactly what the product produces),
plus the configs and password hash for the two real servers the suite starts:

  * denidin-app's Agreements API (`python -m src.services.agreements_api`)
  * the webapp backend (agreements_backend.py), wired to that API

No Morning call is made: the official client list is injected into the webapp backend by the
launcher (dependency injection, same as the backend's own integration tests), because the
suite does not need the Morning sandbox.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
DENIDIN_APP = HERE.parents[1] / "denidin-app"
sys.path.insert(0, str(DENIDIN_APP))

FIXTURE_ROOT = HERE / ".fixture" / "agreements"
PASSWORD = "e2e-pass"
PASSWORD_SALT = "denidin-pw"  # webapp_backend.auth.PASSWORD_SALT
API_PORT = 8310
BACKEND_PORT = 8133
TOKEN = "e2e-agreements-token"

VIEW = "ישראל ישראלי"        # UAT 1.x, 4.1, 6.1 (reads + one edit)
EDIT = "לקוח עריכה"          # UAT 2.1-2.3, 2.5, 3.1-3.4
CLOSED = "לקוח סגור"         # UAT 2.6
CASCADE = "לקוח סגירה"       # UAT 3.5 / 3.6
NEW = "לקוח חדש"             # UAT 2.4
EMPTY = "לקוח ללא הסכמים"    # UAT 1.4
OFFICIAL = [VIEW, EDIT, CLOSED, CASCADE, NEW, EMPTY]
TITLE_VIEW = "ייצוג בבית הדין הארצי"

_clock = {"n": 0}
_BASE = int((datetime.now() - timedelta(days=5)).replace(second=0, microsecond=0).timestamp())


def ts() -> int:
    """A distinct past minute per write: a minute has only ten ledger event-id slots."""
    _clock["n"] += 1
    return _BASE + 60 * _clock["n"]


def main() -> None:
    from denidin import DeniDin
    from src.managers.agreements_manager import AgreementsManager
    from src.managers.ledger_event_manager import LedgerEventManager
    from src.models.config import AppConfiguration

    if FIXTURE_ROOT.exists():
        shutil.rmtree(FIXTURE_ROOT)
    data = FIXTURE_ROOT / "denidin_data"
    webapp_data = FIXTURE_ROOT / "webapp_data"
    for d in (data, webapp_data / "clients", FIXTURE_ROOT / "auth"):
        d.mkdir(parents=True, exist_ok=True)
    (webapp_data / "clients" / "migrations.json").write_text(
        json.dumps({"092_comment_line_status": "2026-10-01T00:00:00+03:00"}), encoding="utf-8")
    (FIXTURE_ROOT / "auth" / "password.hash").write_text(
        hashlib.sha256((PASSWORD_SALT + PASSWORD).encode()).hexdigest(), encoding="utf-8")

    denidin_cfg = {
        "green_api_instance_id": "x", "green_api_token": "x", "ai_api_key": "x", "data_root": str(data),
        "agreements_api": {"port": API_PORT, "auth_token": TOKEN},
    }
    (FIXTURE_ROOT / "config.denidin.json").write_text(json.dumps(denidin_cfg), encoding="utf-8")
    backend_cfg = {
        "environment": "test", "denidin_data_root": str(data), "denidin_src_path": "",
        "password_hash_file": str(FIXTURE_ROOT / "auth" / "password.hash"), "session_expiry_hours": 168,
        "webapp_data_root": str(webapp_data), "clients_data_root": "",
        "denidin_agreements_url": f"http://127.0.0.1:{API_PORT}", "denidin_agreements_token": TOKEN,
        "http": {"host": "127.0.0.1", "port": BACKEND_PORT, "log_level": "INFO"},
    }
    (FIXTURE_ROOT / "config.backend.json").write_text(json.dumps(backend_cfg), encoding="utf-8")

    config = AppConfiguration.from_file(str(FIXTURE_ROOT / "config.denidin.json"))
    app = DeniDin(config)
    app.ledger_event_manager = LedgerEventManager(app)
    manager = AgreementsManager(app)
    ledger = app.ledger_event_manager

    def component(label, **kw):
        return {"label": label, **kw}

    def create(client, title, components, **kw):
        agreement, _ = manager.create_agreement(client_name=client, title=title, components=components,
                                                actor="webapp", message_timestamp=ts(), **kw)
        return agreement

    def key(agreement, label):
        return next(c["component_key"] for c in agreement["components"] if c["label"] == label)

    def set_status(agreement, label, action):
        manager.set_component_status(agreement["agreement_id"], key(agreement, label), action, "webapp",
                                     message_timestamp=ts())

    # ---- VIEW: UAT 1.x / 4.1 / 6.1 - 5,000 Active + 3,000 Pending + a Cancelled 2,000 + 1,000 hours
    view = create(VIEW, TITLE_VIEW, [
        component("ריטיינר", amount=5000, vat_status="לא כולל", description="ריטיינר חודשי"),
        component("שכר הצלחה", amount=3000, trigger_condition="זכייה בתיק"),
        component("רכיב שבוטל", amount=2000),
    ], payer_name="ישראל ישראלי", partner_name="עו״ד כהן", partner_percent=25)
    set_status(view, "רכיב שבוטל", "cancel")
    # a WhatsApp-sourced edit, for the revision history (UAT 4.1)
    manager.edit_component(view["agreement_id"], key(view, "ריטיינר"), {"description": "ריטיינר חודשי (עודכן בוואטסאפ)"},
                           "whatsapp", message_timestamp=ts())
    ledger.add_ledger_events_from_call(
        session_id=None, message_id=None, message_timestamp=ts(),
        call_arguments={"source_type": "הסכם", "client_name": VIEW, "description": "שעות עבודה",
                        "components": [{"amount": "1000", "hours": "5", "txn_date": "01/10/2026"}],
                        "component_count": 1})

    # ---- EDIT: UAT 2.1-2.3, 2.5, 3.1-3.4
    create(EDIT, "הסכם עריכה", [
        component("ריטיינר", amount=5000, vat_status="לא כולל", description="ריטיינר חודשי"),
        component("שכר הצלחה", percent=12, trigger_condition="זכייה"),
        component("הוצאות", amount=700),
    ])

    # ---- CLOSED: UAT 2.6
    closed = create(CLOSED, "הסכם עם רכיבים סגורים", [
        component("שולם", amount=1000), component("בוטל", amount=2000), component("פתוח", amount=3000)])
    set_status(closed, "שולם", "complete")
    set_status(closed, "בוטל", "cancel")
    cancelled = create(CLOSED, "הסכם מבוטל", [component("רכיב", amount=500)])
    manager.set_agreement_status(cancelled["agreement_id"], "cancel", "webapp", message_timestamp=ts())

    # ---- CASCADE: UAT 3.5 / 3.6 (Active, Pending, already-Completed)
    cascade = create(CASCADE, "הסכם לסגירה", [
        component("פעיל", amount=1000), component("ממתין", amount=2000, trigger_condition="אם יידרש"),
        component("שולם", amount=3000)])
    set_status(cascade, "שולם", "complete")

    # Clients with no agreements still need a row: a paid invoice event gives them numbers.
    for name, amount in ((NEW, 100), (EMPTY, 100)):
        ledger.add_ledger_events_from_call(
            session_id=None, message_id=None, message_timestamp=ts(),
            call_arguments={"source_type": "חשבונית", "event_subtype": "חשבונית מס קבלה",
                            "client_name": name, "description": "e2e invoice",
                            "components": [{"amount": str(amount)}], "component_count": 1})

    manifest = {
        "password": PASSWORD, "root": str(FIXTURE_ROOT), "events_dir": str(data / "events"),
        "api_url": f"http://127.0.0.1:{BACKEND_PORT}", "titles": {"view": TITLE_VIEW},
        "clients": {"view": VIEW, "edit": EDIT, "closed": CLOSED, "cascade": CASCADE, "new": NEW, "empty": EMPTY},
        "seeded_events": sorted(p.name for p in (data / "events").glob("*.json")),
    }
    (FIXTURE_ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"seeded {FIXTURE_ROOT}", file=sys.stderr)
    time.sleep(0)


if __name__ == "__main__":
    main()
