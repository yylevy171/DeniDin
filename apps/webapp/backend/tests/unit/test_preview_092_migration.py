"""Feature 092 T037 - the read-only pre-deploy migration preview (quickstart.md §3)."""
import json

from tests.clients_helpers import agreement, payment, write_json


def _write_events(events_dir, events):
    events_dir.mkdir(parents=True, exist_ok=True)
    for e in events:
        (events_dir / f"{e['event_id']}.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")


def test_preview_lists_statuses_and_amount_changes_and_writes_nothing(tmp_path):
    from scripts.preview_092_migration import preview

    clients_dir = tmp_path / "clients"
    events_dir = tmp_path / "events"
    _write_events(events_dir, [
        agreement("A1", "דנה", 10000), payment("C1", "דנה", 2000),
        agreement("A2", "דן", 3000),
        agreement("A3", "רות", 1000),
    ])
    comments = {"דנה": "לסגור", "דן": "לבדוק", "רות": "סתם הערה"}
    write_json(clients_dir / "client_comments.json", comments)
    before = sorted(p.name for p in clients_dir.iterdir())

    result = preview(clients_dir, events_dir, official_clients=["דנה", "דן", "רות"])

    assert result["statuses"] == {"דנה": "closed", "דן": "check"}
    assert result["section_changes"] == []
    changed = {c["client"]: c for c in result["amount_changes"]}
    assert set(changed) == {"דנה"}
    assert changed["דנה"]["before"] == {"agreed": 10000, "paid": 10000}
    assert changed["דנה"]["after"] == {"agreed": 10000, "paid": 2000}
    # read-only: nothing added or modified in the real clients dir
    assert sorted(p.name for p in clients_dir.iterdir()) == before
    assert json.loads((clients_dir / "client_comments.json").read_text(encoding="utf-8")) == comments
