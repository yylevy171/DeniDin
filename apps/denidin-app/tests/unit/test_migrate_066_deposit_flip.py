"""Feature 066 migration script - on a temp copy only, never real data."""
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "migrate_066_deposit_flip.py"
spec = importlib.util.spec_from_file_location("migrate_066", SCRIPT)
migrate_066 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrate_066)


def _event(event_id, source_type, subtype, **extra):
    base = {"event_id": event_id, "source_type": source_type, "event_subtype": subtype, "client_name": "לקוח",
            "amount": 1500, "txn_date": "2026-07-12", "bank_number": "12", "vat_status": "כולל",
            "schema_version": 2, "captured_at": "2026-07-12T10:00:00+03:00"}
    base.update(extra)
    return base


def _dump(record):
    return json.dumps(record, sort_keys=True, ensure_ascii=False, indent=2)


@pytest.fixture
def root(tmp_path):
    events = tmp_path / "events"
    events.mkdir()
    for rec in (_event("B1", "בנק", "הפקדה"), _event("B2", "בנק", "הפקדה", amount=20),
                _event("A1", "הסכם", "יצירה"), _event("H1", "חשבונית", "חשבונית מס")):
        (events / f"{rec['event_id']}.json").write_text(_dump(rec), encoding="utf-8")
    return tmp_path


def _read(root, name):
    return json.loads((root / "events" / f"{name}.json").read_text(encoding="utf-8"))


def _snapshot(root):
    return {p.name: p.read_bytes() for p in (root / "events").glob("*.json")}


def test_dry_run_changes_nothing_and_makes_no_backup(root):
    before = _snapshot(root)

    result = migrate_066.migrate(root, apply=False)

    assert result["to_flip"] == 2 and not result["applied"]
    assert _snapshot(root) == before
    assert not list(root.glob("events_backup_066_*"))


def test_apply_flips_only_bank_events_and_nothing_else_in_them(root):
    old = {n: _read(root, n) for n in ("B1", "B2", "A1", "H1")}
    untouched = {n: (root / "events" / f"{n}.json").read_bytes() for n in ("A1", "H1")}

    result = migrate_066.migrate(root, apply=True)

    assert result["applied"] and result["to_flip"] == 2
    for name in ("B1", "B2"):
        new = _read(root, name)
        assert (new["source_type"], new["event_subtype"], new["schema_version"]) == ("הפקדה", "בנק", 3)
        assert {k: v for k, v in new.items() if k not in migrate_066.CHANGED_KEYS} == \
               {k: v for k, v in old[name].items() if k not in migrate_066.CHANGED_KEYS}
    for name, raw in untouched.items():
        assert (root / "events" / f"{name}.json").read_bytes() == raw
    assert sorted(p.name for p in (root / "events").glob("*.json")) == ["A1.json", "B1.json", "B2.json", "H1.json"]


def test_backup_holds_the_original_files(root):
    before = _snapshot(root)

    result = migrate_066.migrate(root, apply=True)

    backup = Path(result["backup"])
    assert {p.name: p.read_bytes() for p in backup.glob("*.json")} == before


def test_second_apply_is_a_no_op(root):
    migrate_066.migrate(root, apply=True)
    after_first = _snapshot(root)

    again = migrate_066.migrate(root, apply=True)

    assert again["to_flip"] == 0 and again["already_flipped"] == 2 and not again["applied"]
    assert _snapshot(root) == after_first
    assert len(list(root.glob("events_backup_066_*"))) == 1


def test_a_broken_event_file_aborts_before_anything_is_written(root):
    (root / "events" / "BAD.json").write_text("{not json", encoding="utf-8")
    before = _snapshot(root)

    with pytest.raises(migrate_066.MigrationAbort):
        migrate_066.migrate(root, apply=True)

    assert _snapshot(root) == before
    assert not list(root.glob("events_backup_066_*"))


def test_main_reports_and_returns_nonzero_on_abort(root, capsys):
    (root / "events" / "BAD.json").write_text("[]", encoding="utf-8")

    assert migrate_066.main(["--data-root", str(root), "--apply"]) == 1
    assert "ABORTED" in capsys.readouterr().err
