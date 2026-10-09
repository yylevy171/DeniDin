"""Feature 089 (T035) - the read-only name-resolution export that feeds the one-time Agreements
migration: per raw client name of an agreement-component `הסכם` event, the official Morning
name (or null), the line status and the agreed/paid totals. Real files, real ClientsReader."""
import importlib.util
import json
from pathlib import Path

import pytest

from tests.clients_helpers import MIGRATION_KEY, ev, payment, write_json

pytestmark = pytest.mark.integration

OFFICIAL = ["ישראל ישראלי", "דנה כהן"]


def _load_script():
    path = Path(__file__).resolve().parents[2] / "scripts" / "export_name_resolution.py"
    spec = importlib.util.spec_from_file_location("export_name_resolution", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_events(data_root, events):
    events_dir = data_root / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    for event in events:
        (events_dir / f"{event['event_id']}.json").write_text(json.dumps(event, ensure_ascii=False), encoding="utf-8")
    return events_dir


def _events():
    hours = ev("A1", "ישראל ישראלי", "הסכם", 400, subtype="יצירה")
    hours["hours"] = "4"
    return [
        ev("A2", "ישראל ישראלי", "הסכם", 1000, subtype="יצירה"),
        payment("A3", "ישראל ישראלי", 1000),
        ev("A4", "דנה כוהן", "הסכם", 2000, subtype="יצירה"),     # typo: fuzzy-matches דנה כהן
        ev("A5", "מישהו לא ידוע", "הסכם", 300, subtype="יצירה"),  # unresolvable
        hours,                                                    # hours line: never exported on its own
        ev("A6", "גורם בנק", "בנק", 50),                          # not an agreement component
    ]


def test_export_resolves_names_line_status_and_totals(tmp_path):
    clients_dir = tmp_path / "webapp_data" / "clients"
    write_json(clients_dir / "migrations.json", {MIGRATION_KEY: "2026-10-01T00:00:00+03:00"})
    write_json(clients_dir / "client_status.json", {"ישראל ישראלי": "closed"})
    events_dir = _write_events(tmp_path / "data", _events())

    result = _load_script().export(clients_dir, events_dir, OFFICIAL)["clients"]

    assert set(result) == {"ישראל ישראלי", "דנה כוהן", "מישהו לא ידוע"}  # no hours-only / bank names
    assert result["ישראל ישראלי"]["official_name"] == "ישראל ישראלי"
    assert result["ישראל ישראלי"]["line_closed"] is True
    assert result["ישראל ישראלי"]["paid"] == 1000 and result["ישראל ישראלי"]["agreed"] == 1400
    assert result["דנה כוהן"]["official_name"] == "דנה כהן"
    assert result["דנה כוהן"]["line_closed"] is False
    assert result["מישהו לא ידוע"] == {"official_name": None, "line_closed": False, "agreed": None, "paid": None}


def test_export_is_read_only(tmp_path):
    clients_dir = tmp_path / "webapp_data" / "clients"
    write_json(clients_dir / "client_status.json", {"ישראל ישראלי": "closed"})
    events_dir = _write_events(tmp_path / "data", _events())
    before = {p.name: p.read_bytes() for p in clients_dir.iterdir()}
    events_before = {p.name: p.read_bytes() for p in events_dir.iterdir()}

    _load_script().export(clients_dir, events_dir, OFFICIAL)

    assert {p.name: p.read_bytes() for p in clients_dir.iterdir()} == before
    assert {p.name: p.read_bytes() for p in events_dir.iterdir()} == events_before
