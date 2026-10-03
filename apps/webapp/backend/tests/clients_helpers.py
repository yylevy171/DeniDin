"""Shared builders for the Feature 092 Clients-tab tests: real JSON files in a tmp dir and a
real ``ClientsReader`` (official clients + ledger events are constructor-injected callables -
dependency injection, not mocks)."""
import json
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from utils.time_utils import now_local

from webapp_backend.clients_reader import ClientsReader

MIGRATION_KEY = "092_comment_line_status"
PAID_SUBTYPE = "חשבונית מס קבלה"


def recent(days_ago: int = 5) -> str:
    return (now_local() - timedelta(days=days_ago)).strftime("%d/%m/%Y %H:%M")


OLD = "15/06/2025 10:00"  # before clients_reader.PAST_CUTOFF (2025-09-01)


def ev(event_id: str, client: Optional[str], source_type: str, amount: float,
       when: Optional[str] = None, subtype: str = "", desc: str = "d") -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "client_name": client,
        "source_type": source_type,
        "event_subtype": subtype,
        "amount": amount,
        "description": desc,
        "event_datetime": when or recent(),
    }


def agreement(event_id: str, client: Optional[str], amount: float, when: Optional[str] = None):
    return ev(event_id, client, "הסכם", amount, when, subtype="יצירה")


def payment(event_id: str, client: Optional[str], amount: float, when: Optional[str] = None):
    return ev(event_id, client, "חשבונית", amount, when, subtype=PAID_SUBTYPE)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def make_reader(
    tmp_path: Path,
    official: Iterable[str],
    events: List[Dict[str, Any]],
    *,
    comments: Optional[Dict[str, str]] = None,
    status: Optional[Dict[str, str]] = None,
    mapping: Optional[Dict[str, str]] = None,
    notes: Optional[Dict[str, str]] = None,
    migrated: bool = True,
) -> ClientsReader:
    """``migrated=True`` pre-writes the 092 migration marker so a test exercises steady-state
    routing only; ``migrated=False`` leaves it absent so the first compute migrates."""
    clients_dir = tmp_path / "clients"
    clients_dir.mkdir(parents=True, exist_ok=True)
    if comments is not None:
        write_json(clients_dir / "client_comments.json", comments)
    if status is not None:
        write_json(clients_dir / "client_status.json", status)
    if mapping is not None:
        write_json(clients_dir / "client_mapping.json", mapping)
    if notes is not None:
        write_json(clients_dir / "mapping_notes.json", notes)
    if migrated:
        write_json(clients_dir / "migrations.json", {MIGRATION_KEY: "2026-10-01T00:00:00+03:00"})
    official_list = list(official)
    return ClientsReader(
        str(tmp_path), str(clients_dir), lambda: list(official_list), events_fn=lambda: list(events)
    )


def row(report: Dict[str, Any], name: str) -> Dict[str, Any]:
    return next(r for r in report["clients"] if r["official_name"] == name)


def section(report: Dict[str, Any], name: str) -> str:
    return row(report, name)["status"]
