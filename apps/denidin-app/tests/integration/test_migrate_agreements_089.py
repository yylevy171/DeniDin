"""Feature 089 (T037, UAT 7.1-7.5): the one-time migration of ledger fee agreements into the
Agreements DB on a throwaway, real-shaped ledger. Real files and a real AgreementsManager; the
script is loaded from scripts/ and run through its `migrate()` entry point."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.managers.agreements_manager import AgreementsManager

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "migrate_agreements_089.py"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("migrate_agreements_089", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _event(event_id, **fields):
    base = {"event_id": event_id, "source_type": "הסכם", "event_subtype": "יצירה", "schema_version": 2,
            "event_datetime": "2026-07-05T10:00:00+03:00", "hours": None, "reference": None}
    base.update(fields)
    return base


def _component(event_id, client, agreement, label, amount, **extra):
    return _event(event_id, client_name=client, payer_name=client, agreement_id=agreement,
                  component_id=f"{agreement}-{label}", component_label=label, amount=str(amount),
                  description=label, **extra)


@pytest.fixture
def world(tmp_path):
    data_root = tmp_path / "data"
    events = data_root / "events"
    events.mkdir(parents=True)
    all_events = [
        # closed + paid in full (dirty raw name, resolves to an official one)
        _component("A010726000", "דנה כוהן", "0726-דנה-ערעור", "ריטיינר", 1000),
        _component("A010726001", "דנה כוהן", "0726-דנה-ערעור", "הצלחה", 500, trigger_condition="זכייה"),
        # closed with less paid
        _component("A010726002", "רן לוי", "0726-רן-ייעוץ", "ריטיינר", 2000),
        # open client, plus a legacy cancellation of one of its components
        _component("A010726003", "מיכל בר", "0726-מיכל-חוזה", "בסיס", 3000),
        _component("A010726004", "מיכל בר", "0726-מיכל-חוזה", "בונוס", 400),
        _event("A010726005", client_name="מיכל בר", agreement_id="0726-מיכל-חוזה", component_label="בונוס",
               event_subtype="מבוטל", amount="400"),
        # unresolvable name
        _component("A010726006", "גורם זר", "0726-זר-משהו", "בסיס", 100),
        # hours-worked line, bank event, invoice event: never touched
        _event("A010726007", client_name="דנה כהן", hours="4", amount="400"),
        {"event_id": "B010726008", "source_type": "בנק", "client_name": "דנה כהן", "schema_version": 2, "amount": "50"},
        {"event_id": "C010726009", "source_type": "חשבונית", "client_name": "דנה כהן", "schema_version": 2, "amount": "9"},
    ]
    for e in all_events:
        (events / f"{e['event_id']}.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    resolution = {"clients": {
        "דנה כוהן": {"official_name": "דנה כהן", "line_closed": True, "agreed": 1500, "paid": 1500},
        "רן לוי": {"official_name": "רן לוי", "line_closed": True, "agreed": 2000, "paid": 500},
        "מיכל בר": {"official_name": "מיכל בר", "line_closed": False, "agreed": 3400, "paid": 0},
        "גורם זר": {"official_name": None, "line_closed": False, "agreed": None, "paid": None},
    }}
    res_path = tmp_path / "name_resolution.json"
    res_path.write_text(json.dumps(resolution, ensure_ascii=False), encoding="utf-8")
    return SimpleNamespace(root=data_root, events=events, resolution=res_path)


def _manager(root):
    return AgreementsManager(SimpleNamespace(config=SimpleNamespace(data_root=str(root))))


def _read(world, event_id):
    return json.loads((world.events / f"{event_id}.json").read_text(encoding="utf-8"))


def _components(root):
    out = {}
    for agreement in _manager(root).list_agreements():
        for c in agreement["components"]:
            out[(agreement["agreement_id"], c["label"])] = (agreement["status"], c["status"])
    return out


def test_us7_1_components_created_hours_bank_invoice_untouched(script, world):
    before = {i: _read(world, i) for i in ("A010726007", "B010726008", "C010726009")}
    report = script.migrate(world.root, world.resolution)
    assert report["status"] == "migrated"
    assert report["agreements"] == 4 and report["components"] == 6
    ids = {a["agreement_id"] for a in _manager(world.root).list_agreements()}
    assert ids == {"0726-דנה-ערעור", "0726-רן-ייעוץ", "0726-מיכל-חוזה", "0726-זר-משהו"}
    assert {i: _read(world, i) for i in before} == before


def test_us7_2_events_rewritten_to_v4_with_clean_names(script, world):
    original = _read(world, "A010726000")
    script.migrate(world.root, world.resolution)
    event = _read(world, "A010726000")
    assert event["client_name"] == "דנה כהן" and event["original_client_name"] == "דנה כוהן"
    unchanged = {k: v for k, v in event.items()
                 if k not in ("client_name", "original_client_name", "schema_version", "component_status", "agreement_status")}
    assert unchanged == {k: v for k, v in original.items() if k not in ("client_name", "schema_version")}
    unresolved = _read(world, "A010726006")
    assert unresolved["client_name"] == "גורם זר" and unresolved["original_client_name"] == "גורם זר"


def test_us7_3_status_inference(script, world):
    script.migrate(world.root, world.resolution)
    components = _components(world.root)
    assert components[("0726-דנה-ערעור", "ריטיינר")] == ("Completed", "Completed")
    assert components[("0726-דנה-ערעור", "הצלחה")] == ("Completed", "Completed")
    assert components[("0726-רן-ייעוץ", "ריטיינר")] == ("Cancelled", "Cancelled")
    assert components[("0726-מיכל-חוזה", "בסיס")] == ("Active", "Active")


def test_us7_4_legacy_cancellation_marks_component_cancelled(script, world):
    script.migrate(world.root, world.resolution)
    components = _components(world.root)
    assert components[("0726-מיכל-חוזה", "בונוס")] == ("Active", "Cancelled")
    assert ("0726-מיכל-חוזה", "מבוטל") not in components  # the cancellation event is not a component
    assert _read(world, "A010726005")["component_status"] == "Cancelled"


def test_us7_5_second_run_is_noop_and_backup_exists_first(script, world):
    originals = {p.name: p.read_bytes() for p in world.events.glob("*.json")}
    first = script.migrate(world.root, world.resolution)
    backup = Path(first["backup"])
    assert {p.name: p.read_bytes() for p in backup.glob("*.json")} == {
        n: b for n, b in originals.items() if n in {p.name for p in backup.glob("*.json")}}
    assert len(list(backup.glob("*.json"))) == first["events_rewritten"] == 7
    snapshot = {p.name: p.read_bytes() for p in world.events.glob("*.json")}
    second = script.migrate(world.root, world.resolution)
    assert second["status"] == "already_migrated"
    assert {p.name: p.read_bytes() for p in world.events.glob("*.json")} == snapshot
    assert len(_manager(world.root).list_agreements()) == 4


def test_dry_run_writes_nothing(script, world):
    originals = {p.name: p.read_bytes() for p in world.events.glob("*.json")}
    report = script.migrate(world.root, world.resolution, dry_run=True)
    assert report["status"] == "dry_run" and report["components"] == 6
    assert report["unresolved_names"] == ["גורם זר"]
    assert {p.name: p.read_bytes() for p in world.events.glob("*.json")} == originals
    assert not (world.root / "agreements" / "migration_089.json").exists()


def test_duplicate_labels_block_the_migration_and_write_nothing(script, world):
    dup = _component("A010726010", "מיכל בר", "0726-מיכל-חוזה", "בסיס", 700)
    (world.events / "A010726010.json").write_text(json.dumps(dup, ensure_ascii=False), encoding="utf-8")
    originals = {p.name: p.read_bytes() for p in world.events.glob("*.json")}
    report = script.migrate(world.root, world.resolution)
    assert report["status"] == "blocked_duplicate_labels"
    assert report["duplicate_labels"] == [{"agreement_id": "0726-מיכל-חוזה", "labels": ["בסיס"]}]
    assert {p.name: p.read_bytes() for p in world.events.glob("*.json")} == originals
    assert not (world.root / "agreements" / "migration_089.json").exists()
