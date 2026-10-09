"""Feature 089 - the webapp backend's Agreements facade, end to end: browser-shaped requests
through the real Starlette app (session gate included) -> real HTTP -> a real denidin-app
Agreements API process (`python -m src.services.agreements_api`, launched with denidin-app's
own interpreter on a throwaway data root). Nothing in the chain is faked."""
import json
import socket
import subprocess
import time
from pathlib import Path
from urllib.parse import quote

import pytest
import requests

pytestmark = pytest.mark.integration

DENIDIN_APP = Path(__file__).resolve().parents[4] / "denidin-app"
TOKEN = "facade-test-token"
CLIENT = "ישראל ישראלי"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# Function-scoped on purpose: a minute only has ten ledger event-id slots per source letter
# (refused loudly beyond that), so tests must not share one data root.
@pytest.fixture
def denidin_api(tmp_path_factory):
    interpreter = DENIDIN_APP / "venv" / "bin" / "python3"
    if not interpreter.exists():
        pytest.skip("denidin-app venv not available")
    root = tmp_path_factory.mktemp("agreements_api")
    config = root / "config.json"
    config.write_text(json.dumps({
        "green_api_instance_id": "x", "green_api_token": "x", "ai_api_key": "x",
        "data_root": str(root), "agreements_api": {"port": 0, "auth_token": TOKEN},
    }), encoding="utf-8")
    port = _free_port()
    log = (root / "api.log").open("w")
    process = subprocess.Popen(
        [str(interpreter), "-m", "src.services.agreements_api", "--config", str(config), "--port", str(port)],
        cwd=DENIDIN_APP, stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                if requests.get(f"{url}/is_alive", timeout=1).ok:
                    break
            except requests.RequestException:
                time.sleep(0.5)
        else:
            pytest.fail("denidin-app Agreements API did not come up: " + (root / "api.log").read_text()[-500:])
        yield url
    finally:
        process.terminate()
        process.wait(timeout=10)
        log.close()


def _build_client(tmp_path, password_hash_file, known_password, url, token):
    from starlette.testclient import TestClient

    from webapp_backend.config import AppConfig
    from webapp_backend.server import build_app

    (tmp_path / "data" / "events").mkdir(parents=True, exist_ok=True)
    config = AppConfig(
        environment="test", password_hash_file=str(password_hash_file),
        denidin_data_root=str(tmp_path / "data"), webapp_data_root=str(tmp_path / "webapp_data"),
        denidin_agreements_url=url, denidin_agreements_token=token,
    )
    c = TestClient(build_app(config, official_clients_fn=lambda: [CLIENT]))
    c.__enter__()
    session = c.post("/api/auth/login", json={"password": known_password}).json()["token"]
    c.headers.update({"Authorization": f"Bearer {session}"})
    return c


@pytest.fixture
def api(tmp_path, password_hash_file, known_password, denidin_api):
    c = _build_client(tmp_path, password_hash_file, known_password, denidin_api, TOKEN)
    yield c
    c.__exit__(None, None, None)


def _create(api, title="ערעור"):
    response = api.post("/api/agreements", json={
        "client_name": CLIENT, "title": title,
        "components": [{"label": "ריטיינר", "amount": 5000}, {"label": "הצלחה", "percent": 12, "trigger_condition": "זכייה"}],
    })
    assert response.status_code == 200, response.text
    return response.json()["agreement"]


class TestFacade:
    def test_requires_a_webapp_session(self, api):
        api.headers.pop("Authorization")
        assert api.get(f"/api/clients/{quote(CLIENT)}/agreements").status_code == 401
        assert api.post("/api/agreements", json={}).status_code == 401

    def test_create_then_list_for_client(self, api):
        created = _create(api, "רשימה")
        listed = api.get(f"/api/clients/{quote(CLIENT)}/agreements").json()["agreements"]
        assert created["agreement_id"] in [a["agreement_id"] for a in listed]

    def test_writes_are_stamped_with_the_webapp_actor(self, api):
        agreement = _create(api, "שחקן")
        revisions = api.get(f"/api/agreements/{agreement['agreement_id']}/revisions").json()["revisions"]
        assert {r["actor"] for r in revisions} == {"webapp"}

    def test_edit_status_and_delete_flow(self, api):
        agreement = _create(api, "זרימה")
        aid = agreement["agreement_id"]
        key = next(c["component_key"] for c in agreement["components"] if c["label"] == "ריטיינר")
        assert api.patch(f"/api/agreements/{aid}/components/{key}", json={"amount": 6000}).status_code == 200
        assert api.post(f"/api/agreements/{aid}/components/{key}/status", json={"action": "complete"}).status_code == 200
        locked = api.patch(f"/api/agreements/{aid}/components/{key}", json={"amount": 1})
        assert locked.status_code == 409 and locked.json()["error"]["code"] == "locked"
        other = next(c["component_key"] for c in agreement["components"] if c["label"] == "הצלחה")
        deleted = api.delete(f"/api/agreements/{aid}/components/{other}")
        assert deleted.status_code == 200
        assert [c["label"] for c in deleted.json()["agreement"]["components"]] == ["ריטיינר"]
        closed = api.post(f"/api/agreements/{aid}/status", json={"action": "cancel"})
        assert closed.json()["agreement"]["status"] == "Cancelled"

    def test_denidin_errors_pass_through_unchanged(self, api):
        response = api.patch("/api/agreements/nope", json={"payer_name": "x"})
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    def test_browser_cannot_forge_the_actor(self, api):
        agreement = _create(api, "זיוף")
        api.patch(f"/api/agreements/{agreement['agreement_id']}", json={"actor": "whatsapp", "payer_name": "חברה"})
        revisions = api.get(f"/api/agreements/{agreement['agreement_id']}/revisions").json()["revisions"]
        assert {r["actor"] for r in revisions} == {"webapp"}


class TestUnavailable:
    def test_unreachable_denidin_is_502_agreements_unavailable(self, tmp_path, password_hash_file, known_password):
        c = _build_client(tmp_path, password_hash_file, known_password, f"http://127.0.0.1:{_free_port()}", TOKEN)
        try:
            response = c.get(f"/api/clients/{quote(CLIENT)}/agreements")
        finally:
            c.__exit__(None, None, None)
        assert response.status_code == 502
        assert response.json()["error"]["code"] == "agreements_unavailable"

    def test_unconfigured_is_502_too(self, tmp_path, password_hash_file, known_password):
        c = _build_client(tmp_path, password_hash_file, known_password, "", "")
        try:
            assert c.get(f"/api/clients/{quote(CLIENT)}/agreements").status_code == 502
        finally:
            c.__exit__(None, None, None)
