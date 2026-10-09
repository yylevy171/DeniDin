"""Feature 089 (US6, UAT 6.1) - the Clients tab's agreed total follows the Agreements DB:
non-Cancelled component sum (one bulk totals call) + hours-worked `הסכם` ledger lines, with the
ledger `הסכם` events that merely mirror components NOT added again, the `הסכם <amount>` comment
override unchanged, and an unreachable Agreements API reported as an explicit error (never a
silent zero). Real Starlette app + real files; the totals source is injected like the official
client list (dependency injection - no mock of internal code)."""
import json
from urllib.parse import quote

import pytest

from tests.clients_helpers import MIGRATION_KEY, ev, write_json

pytestmark = pytest.mark.integration

CLIENT = "ישראל ישראלי"


def _hours_line(event_id, amount):
    event = ev(event_id, CLIENT, "הסכם", amount, subtype="יצירה", desc="שעות עבודה")
    event["hours"] = "5"
    return event


def _mirror(event_id, amount):
    return ev(event_id, CLIENT, "הסכם", amount, subtype="יצירה", desc="רכיב")


@pytest.fixture
def make_api(tmp_path, password_hash_file, known_password):
    from starlette.testclient import TestClient

    from webapp_backend.config import AppConfig
    from webapp_backend.server import build_app

    opened = []

    def make(totals_fn, events):
        data_root = tmp_path / "data"
        events_dir = data_root / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        for e in events:
            (events_dir / f"{e['event_id']}.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
        write_json(tmp_path / "webapp_data" / "clients" / "migrations.json", {MIGRATION_KEY: "2026-10-01T00:00:00+03:00"})
        config = AppConfig(
            environment="test", password_hash_file=str(password_hash_file), denidin_data_root=str(data_root),
            webapp_data_root=str(tmp_path / "webapp_data"))
        c = TestClient(build_app(config, official_clients_fn=lambda: [CLIENT], agreements_totals_fn=totals_fn))
        c.__enter__()
        opened.append(c)
        token = c.post("/api/auth/login", json={"password": known_password}).json()["token"]
        c.headers.update({"Authorization": f"Bearer {token}"})
        return c

    yield make
    for c in opened:
        c.__exit__(None, None, None)


def _agreed(api):
    row = next(r for r in api.get("/api/clients").json()["clients"] if r["official_name"] == CLIENT)
    return row["display_agreed"]


def test_agreed_is_db_total_plus_hours_lines_without_double_counting(make_api):
    totals = {CLIENT: 8000.0}  # 5,000 retainer + 3,000 success fee, cancelled 2,000 already excluded
    api = make_api(lambda: dict(totals), [_mirror("A1", 5000), _mirror("A2", 3000), _mirror("A3", 2000), _hours_line("A4", 1000)])
    assert _agreed(api) == 9000


def test_cancelling_a_component_lowers_the_total_after_the_write(make_api):
    totals = {CLIENT: 8000.0}
    api = make_api(lambda: dict(totals), [_hours_line("A4", 1000)])
    assert _agreed(api) == 9000
    totals[CLIENT] = 5000.0  # the DB changed (a component was cancelled)
    # the report is cached, a write through the facade invalidates it; without any
    # facade write the cache is still honoured:
    assert _agreed(api) == 9000
    api.get("/api/clients?refresh=1")
    assert _agreed(api) == 6000


def test_comment_override_still_wins(make_api):
    api = make_api(lambda: {CLIENT: 8000.0}, [_hours_line("A4", 1000)])
    api.post(f"/api/clients/{quote(CLIENT)}/comments", json={"comment": "הסכם 12000"})
    assert _agreed(api) == 12000


def test_client_with_no_components_keeps_only_hours_lines(make_api):
    api = make_api(lambda: {}, [_hours_line("A4", 1000), _mirror("A5", 4000)])
    assert _agreed(api) == 1000


def test_unreachable_agreements_api_is_an_explicit_error_not_zeros(make_api):
    from webapp_backend.agreements_client import AgreementsUnavailable

    def down():
        raise AgreementsUnavailable("connection refused")

    api = make_api(down, [_hours_line("A4", 1000)])
    response = api.get("/api/clients")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "agreements_unavailable"
