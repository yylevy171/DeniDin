"""Feature 092 - READ-ONLY pre-deploy preview of the one-time comment->line-status migration
(quickstart.md §3). Runs the real migration + routing against a TEMPORARY COPY of a clients
data dir and reports:

  * statuses        - the line status each client would get (check / active / closed)
  * section_changes - lines whose section would differ from the pre-092 comment routing
                      (expected: none)
  * amount_changes  - lines whose displayed agreed/paid change (expected: exactly the lines the
                      old "לסגור" hack inflated - bugfix-068 - plus research R-4's rare edge)

Nothing under --clients-dir is ever written.

Usage (from apps/webapp/backend, this clone's venv):
  venv/bin/python scripts/preview_092_migration.py \
      --clients-dir <copy of prod webapp_data/clients> --events-dir <prod data>/events \
      --config config/config.prod.json            # official client list from Morning (read-only)
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

from webapp_backend.clients_reader import MIGRATION_092_KEY, ClientsReader  # noqa: E402  pylint: disable=wrong-import-position
from webapp_backend.ledger_reader import LedgerEventManager  # noqa: E402  pylint: disable=wrong-import-position
from webapp_backend.webapp_denidin import WebappDeniDin  # noqa: E402  pylint: disable=wrong-import-position


def _legacy_flags(comment: str) -> Dict[str, bool]:
    """Pre-092 comment flags (clients_reader._apply_status_directives at f096e06)."""
    is_active = "לקוח פעיל" in comment or "לקוחה פעילה" in comment
    is_delete = "למחוק" in comment or comment.strip() == "להסיר" or "להסיר מהרשימה" in comment
    is_check = not is_delete and "לבדוק" in comment
    is_close = not is_delete and not is_check and ("לסגור" in comment or "אפשר לסגור" in comment)
    return {"active": is_active, "delete": is_delete, "check": is_check, "close": is_close}


def preview(clients_dir: Path, events_dir: Path, official_clients: List[str]) -> Dict[str, Any]:
    clients_dir, events_dir = Path(clients_dir), Path(events_dir)
    # The manager reads {data_root}/events, so the events dir's parent is the data root.
    events = LedgerEventManager(WebappDeniDin(str(events_dir.parent))).list_events()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "clients"
        if clients_dir.exists():
            shutil.copytree(clients_dir, work)
        else:
            work.mkdir(parents=True)
        already = MIGRATION_092_KEY in _read(work / "migrations.json")
        reader = ClientsReader(tmp, str(work), lambda: list(official_clients), events_fn=lambda: events)
        cleared = {r["official_name"]: r for r in reader._compute_report(status_override={})["clients"]}
        after = reader.get_report()["clients"]
        statuses = _read(work / "client_status.json")
        comments = _read(work / "client_comments.json")

    section_changes, amount_changes = [], []
    for row in after:
        c = row["official_name"]
        flags = _legacy_flags(comments.get(c, ""))
        base = cleared.get(c, row)
        if flags["check"]:
            legacy_section = "check"
        elif flags["active"]:
            legacy_section = "active"
        elif flags["close"]:
            legacy_section = "settled"
        elif flags["delete"]:
            legacy_section = "past"
        else:
            legacy_section = base["status"]
        if legacy_section != row["status"]:
            section_changes.append({"client": c, "before": legacy_section, "after": row["status"]})

        now = {"agreed": row["display_agreed"], "paid": row["display_paid"]}
        if flags["close"]:
            cur_agreed = row["manual_agreement_amount"]
            if cur_agreed is None:
                cur_agreed = row["agreements_total"]
            matched = max(cur_agreed, row["invoices_net"])
            before = {"agreed": matched, "paid": matched} if matched > 0 else now
            if before != now:
                amount_changes.append({"client": c, "before": before, "after": now})

    return {
        "already_migrated": already,
        "statuses": statuses,
        "section_changes": section_changes,
        "amount_changes": amount_changes,
    }


def _read(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


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
    args = ap.parse_args(argv)
    result = preview(Path(args.clients_dir), Path(args.events_dir), _official_from_config(args.config))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
