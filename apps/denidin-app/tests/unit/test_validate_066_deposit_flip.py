"""Feature 066 validation script - on a temp copy only, never real data. It must FAIL before the
migration and PASS after it."""
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migrate_066 = _load("migrate_066", "migrate_066_deposit_flip.py")
validate_066 = _load("validate_066", "validate_066_deposit_flip.py")


def _event(event_id, source_type, subtype, schema_version=2):
    return {"event_id": event_id, "source_type": source_type, "event_subtype": subtype, "client_name": "לקוח",
            "amount": 1500, "schema_version": schema_version}


@pytest.fixture
def root(tmp_path):
    events = tmp_path / "events"
    events.mkdir()
    for rec in (_event("B1", "בנק", "הפקדה"), _event("B2", "בנק", "הפקדה", 1), _event("C1", "בנק", "מבוטל", 1),
                _event("A1", "הסכם", "יצירה"), _event("H1", "חשבונית", "חשבונית מס")):
        (events / f"{rec['event_id']}.json").write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    return tmp_path


def test_it_fails_before_the_migration_and_names_every_old_event(root):
    result = validate_066.validate(root)

    assert len(result["problems"]) == 3
    assert validate_066.main(["--data-root", str(root)]) == 1


def test_it_passes_after_the_migration_and_against_its_backup(root):
    migration = migrate_066.migrate(root, apply=True)

    result = validate_066.validate(root, Path(migration["backup"]))

    assert result["problems"] == [] and result["deposits"] == 2
    assert validate_066.main(["--data-root", str(root), "--backup", migration["backup"]]) == 0


def test_a_file_deleted_that_was_not_a_cancelled_bank_event_is_caught_against_the_backup(root):
    migration = migrate_066.migrate(root, apply=True)
    (root / "events" / "B1.json").unlink()

    assert any("removed" in p for p in validate_066.validate(root, Path(migration["backup"]))["problems"])


def test_a_deposit_that_is_not_a_method_or_cancelled_fails(root):
    migrate_066.migrate(root, apply=True)
    (root / "events" / "X.json").write_text(json.dumps(_event("X", "הפקדה", "הפקדה", 3)), encoding="utf-8")

    assert any("not a method" in p for p in validate_066.validate(root)["problems"])


def test_an_old_schema_deposit_fails(root):
    migrate_066.migrate(root, apply=True)
    (root / "events" / "X.json").write_text(json.dumps(_event("X", "הפקדה", "ביט", 2)), encoding="utf-8")

    assert any("schema_version" in p for p in validate_066.validate(root)["problems"])


def test_a_change_beyond_the_flip_is_caught_against_the_backup(root):
    migration = migrate_066.migrate(root, apply=True)
    path = root / "events" / "B1.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["amount"] = 1
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    problems = validate_066.validate(root, Path(migration["backup"]))["problems"]

    assert any("B1.json" in p and "changed" in p for p in problems)


def test_a_missing_events_folder_is_an_error(tmp_path):
    assert validate_066.main(["--data-root", str(tmp_path)]) == 2
