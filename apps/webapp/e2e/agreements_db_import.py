"""Feature 089 - gives a ledger-only e2e fixture the Agreements DB it now depends on.

Since 089 the Clients tab's agreed total comes from the Agreements DB (plus hours-worked lines),
not from summing `הסכם` ledger events. The older fixtures (Feature 087 / 092 Clients suite) seed
agreement amounts as ledger events only, so this puts each one into a real Agreements DB under the
same data root - exactly the state the product has after agreements exist (the ledger events stay;
nothing new is written to the ledger).

Run with denidin-app's own interpreter from apps/denidin-app:
    python3 agreements_db_import.py <fixture root holding events/> <api port> <token>
It also writes <root>/config.denidin.json for `python -m src.services.agreements_api`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "denidin-app"))


def main(root: str, port: int, token: str) -> None:
    from denidin import DeniDin
    from src.managers.agreements_manager import AgreementsManager
    from src.models.config import AppConfiguration

    root_path = Path(root)
    cfg_path = root_path / "config.denidin.json"
    cfg_path.write_text(json.dumps({
        "green_api_instance_id": "x", "green_api_token": "x", "ai_api_key": "x", "data_root": str(root_path),
        "agreements_api": {"port": port, "auth_token": token},
    }), encoding="utf-8")
    manager = AgreementsManager(DeniDin(AppConfiguration.from_file(str(cfg_path))))

    imported = 0
    for path in sorted((root_path / "events").glob("*.json")):
        event = json.loads(path.read_text(encoding="utf-8"))
        hours = event.get("hours")
        if event.get("source_type") != "הסכם" or (hours is not None and str(hours).strip() != ""):
            continue
        if event.get("amount") is None:
            continue
        client = event.get("client_name") or event.get("payer_name")
        if not client:
            continue
        manager.import_migrated_agreement(
            agreement_id=f"e2e-{event['event_id']}", title=event.get("description") or event["event_id"],
            client_name=client, payer_name=None, partner_name=None, partner_percent=None, status="Active",
            components=[{"label": "רכיב", "description": event.get("description"), "amount": event["amount"],
                         "status": "Active", "origin_event_id": event["event_id"]}],
        )
        imported += 1
    print(f"imported {imported} agreements into {manager.db_path}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3])
