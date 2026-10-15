"""Feature 089 (REQ-089-10/11) - READ-ONLY export for the one-time Agreements migration.

For every raw client name carried by an agreement-component `הסכם` ledger event, writes how the
Clients tab resolves it (official Morning name, or null) plus that client's line status and
agreed/paid totals, to `name_resolution.json` (data-model.md shape). The denidin-app migration
script (`apps/denidin-app/scripts/migrate_agreements_089.py --resolution <file>`) consumes it;
the two apps never import each other, hence the file hand-off.

Nothing under --clients-dir or --events-dir is written: the report is computed against a
temporary copy of the clients dir (computing it has side-effect writes).

Usage (from apps/webapp/backend, this clone's venv):
  venv/bin/python scripts/export_name_resolution.py \
      --clients-dir <webapp_data/clients> --events-dir <data>/events \
      --config config/config.prod.json --out name_resolution.json
"""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

_BACKEND = Path(__file__).resolve().parents[1]
for _p in (_BACKEND / "src", _BACKEND.parents[1] / "denidin-app" / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from utils.time_utils import now_local  # noqa: E402  pylint: disable=wrong-import-position
from webapp_backend.clients_reader import (  # noqa: E402  pylint: disable=wrong-import-position
    ClientsReader, _fuzzy_match, _is_hours_line, _load_json, _raw_client_name,
)
from webapp_backend.ledger_reader import LedgerEventManager  # noqa: E402  pylint: disable=wrong-import-position
from webapp_backend.webapp_denidin import WebappDeniDin  # noqa: E402  pylint: disable=wrong-import-position


def _is_component_event(event: Dict[str, Any]) -> bool:
    """An agreement-component `הסכם` event (hours-worked lines are never migrated)."""
    return event.get("source_type") == "הסכם" and not _is_hours_line(event)


def export(clients_dir: Path, events_dir: Path, official_clients: List[str]) -> Dict[str, Any]:
    clients_dir, events_dir = Path(clients_dir), Path(events_dir)
    events = LedgerEventManager(WebappDeniDin(str(events_dir.parent))).list_events()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "clients"
        if clients_dir.exists():
            shutil.copytree(clients_dir, work)
        else:
            work.mkdir(parents=True)
        manual_mapping = _load_json(work / "client_mapping.json")
        reader = ClientsReader(tmp, str(work), lambda: list(official_clients), events_fn=lambda: events)
        rows = {row["official_name"]: row for row in reader.get_report()["clients"]}

    resolution: Dict[str, Dict[str, Any]] = {}
    for event in events:
        if not _is_component_event(event):
            continue
        raw = _raw_client_name(event)
        if raw in resolution:
            continue
        official, _ = _fuzzy_match(raw, official_clients, manual_mapping)
        row: Optional[Dict[str, Any]] = rows.get(official) if official else None
        resolution[raw] = {
            "official_name": official,
            "line_closed": bool(row and row.get("line_status") == "closed"),
            "agreed": row["display_agreed"] if row else None,
            "paid": row["display_paid"] if row else None,
        }
    return {"generated_at": now_local().isoformat(), "clients": resolution}


def _official_from_config(config_path: str) -> List[str]:
    from webapp_backend.config import AppConfig
    from webapp_backend.morning_client_source import MorningClientSource

    cfg = AppConfig.from_file(config_path)
    return MorningClientSource(
        api_key_id=cfg.morning_api_key_id, api_key_secret=cfg.morning_api_key_secret,
        auth_url=cfg.morning_auth_url, api_url=cfg.morning_api_url,
    ).list_active_client_names()


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clients-dir", required=True)
    ap.add_argument("--events-dir", required=True)
    ap.add_argument("--config", required=True, help="webapp config whose Morning creds list the official clients")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    result = export(Path(args.clients_dir), Path(args.events_dir), _official_from_config(args.config))
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.out}: {len(result['clients'])} raw client names, "
          f"{sum(1 for v in result['clients'].values() if v['official_name'] is None)} unresolved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
