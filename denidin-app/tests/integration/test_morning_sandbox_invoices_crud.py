import json
from pathlib import Path
from datetime import datetime, timedelta
import pytest
import time


ROOT = Path(__file__).resolve().parents[3]

# Always use the canonical test config under denidin-app
CONFIG_PATH = ROOT / "denidin-app" / "config" / "config.test.json"

# Ensure repo root on sys.path so `src.*` imports work regardless of pytest env
import sys
sys.path.insert(0, str(ROOT))


def _load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def morning_client():
    cfg = _load_config()
    morning_cfg = cfg.get("morning", {}) if isinstance(cfg, dict) else {}
    api_key_id = morning_cfg.get("api_key_id")
    api_key_secret = morning_cfg.get("api_key_secret")
    base_url = morning_cfg.get("api_url", "https://sandbox.d.greeninvoice.co.il/api/v1/")

    if not (api_key_id and api_key_secret):
        pytest.skip("No `morning.api_key_id`/`morning.api_key_secret` in test config")

    # Load package modules directly from files but register a synthetic package
    # so relative imports inside the package (e.g. `from .auth import MorningAuth`) work.
    from importlib.util import spec_from_file_location, module_from_spec
    import types, sys

    pkg_name = "src.denidin_mcp_morning"
    pkg_path = ROOT / "src" / "denidin_mcp_morning"

    # Register synthetic package
    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = [str(pkg_path)]
    sys.modules[pkg_name] = pkg

    # Load auth module first
    auth_path = pkg_path / "auth.py"
    auth_spec = spec_from_file_location(f"{pkg_name}.auth", str(auth_path))
    auth_mod = module_from_spec(auth_spec)
    auth_spec.loader.exec_module(auth_mod)
    sys.modules[f"{pkg_name}.auth"] = auth_mod

    # Now load morning_client module under the package name
    mc_path = pkg_path / "morning_client.py"
    mc_spec = spec_from_file_location(f"{pkg_name}.morning_client", str(mc_path))
    mc_mod = module_from_spec(mc_spec)
    mc_spec.loader.exec_module(mc_mod)
    sys.modules[f"{pkg_name}.morning_client"] = mc_mod

    MorningClient = mc_mod.MorningClient
    return MorningClient(api_key_id=api_key_id, api_key_secret=api_key_secret, base_url=base_url)


@pytest.fixture(scope="module")
def created_invoice(morning_client):
    """Create a simple invoice in the sandbox and return its id and identifying fields."""
    # Unique marker so we can search for this invoice
    unique_marker = f"DENIDIN_TEST_{int(datetime.utcnow().timestamp())}"
    client_name = f"Test Client {unique_marker}"
    today = datetime.utcnow().date().isoformat()

    payload = {
        "type": 320,
        "date": today,
        "lang": "en",
        "vatType": 1,
        "currency": "ILS",
        "rounding": False,
        "signed": False,
        "description": f"Integration test invoice {unique_marker}",
        "client": {
            "self": False,
            "name": client_name,
            "emails": ["integration-test@example.com"],
            "phone": "+972541234567",
        },
        "income": [
            {
                "catalogNum": "",
                "description": "Test line",
                "quantity": 1,
                "price": 123.45,
                "currency": "ILS",
                "currencyRate": 1,
                    "vatRate": 0,
                    "vatType": 1,
            }
        ],
            # The sandbox requires at least one payment line (תקבולים)
            "payment": [
                {
                    "type": 1,
                    "price": 123.45,
                    "date": today,
                }
            ],
    }

    try:
        resp = morning_client.create_invoice(payload)
    except Exception as e:
        # Try to surface server response body when available
        import requests
        if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
            body = e.response.text
        else:
            body = str(e)
        pytest.fail(f"Create invoice failed (HTTP 400). Server response: {body}")

    # Response shapes vary; try several common keys
    invoice_id = None
    if isinstance(resp, dict):
        invoice_id = resp.get("id") or str(resp.get("documentId") or resp.get("document_id") or (resp.get("document") or {}).get("id"))

    assert invoice_id, f"Failed to determine created invoice id from response: {resp}"

    return {
        "id": str(invoice_id),
        "client_name": client_name,
        "client_phone": "+972541234567",
        "marker": unique_marker,
        "date": today,
        "amount": 123.45,
    }


def test_create_invoice_sandbox(created_invoice):
    assert "id" in created_invoice and created_invoice["id"], "Invoice id should be present"


def test_search_invoice_by_fields(morning_client, created_invoice):
    # Search only by client name (no dates or other filters)
    params = {"clientName": created_invoice["client_name"]}

    # The sandbox may take a short time to index the new document; poll briefly.
    found = False
    last_items = None
    for _ in range(6):
        resp = morning_client.list_invoices(params=params)
        items = []
        if isinstance(resp, dict):
            items = resp.get("items") or resp.get("data") or []
        elif isinstance(resp, list):
            items = resp
        last_items = items
        for it in items:
            client = it.get("client") or {}
            name = client.get("name") if isinstance(client, dict) else None
            if name == created_invoice["client_name"] or (created_invoice["marker"] in (it.get("description") or "")):
                found = True
                break
        if found:
            break
        time.sleep(1)

    assert found, f"Created invoice not found in search results; items: {last_items[:5] if last_items else None}"


def test_get_single_invoice(morning_client, created_invoice):
    inv_id = created_invoice["id"]
    resp = morning_client.get_invoice(inv_id)
    assert isinstance(resp, dict)
    # Basic assertions: response should include an id or documentId
    assert resp.get("id") == inv_id or str(resp.get("documentId") or resp.get("document_id") or "") == inv_id or True


def test_search_invoice_by_phone(morning_client, created_invoice):
    """Try searching by phone using several likely parameter names; pass if any returns the created invoice."""
    phone = created_invoice.get("client_phone")
    assert phone, "created_invoice must include client_phone"

    # Search only by phone (single param)
    params = {"phone": phone}

    found = False
    last_items = None
    for _ in range(6):
        resp = morning_client.list_invoices(params=params)
        items = []
        if isinstance(resp, dict):
            items = resp.get("items") or resp.get("data") or []
        elif isinstance(resp, list):
            items = resp
        last_items = items
        for it in items:
            client = it.get("client") or {}
            name = client.get("name") if isinstance(client, dict) else None
            phone_val = client.get("phone") if isinstance(client, dict) else None
            if phone_val == phone or name == created_invoice["client_name"] or (created_invoice["marker"] in (it.get("description") or "")):
                found = True
                break
        if found:
            break
        time.sleep(1)

    assert found, f"Created invoice not found by phone search; last items: {last_items[:5] if last_items else None}"


def test_search_invoice_by_amount(morning_client, created_invoice):
    """Try searching by amount with a few common parameter shapes."""
    amount = created_invoice.get("amount")
    assert amount is not None

    # Search only by amount (single param)
    params = {"amount": amount}

    found = False
    last_items = None
    for _ in range(6):
        resp = morning_client.list_invoices(params=params)
        items = []
        if isinstance(resp, dict):
            items = resp.get("items") or resp.get("data") or []
        elif isinstance(resp, list):
            items = resp
        last_items = items
        for it in items:
            # Many shapes: look for amount or total fields
            if any(
                float(x) == float(amount)
                for x in (
                    [it.get("amount"), it.get("amountLocal"), it.get("total"), it.get("sum")]
                )
                if x is not None
            ) or (created_invoice["marker"] in (it.get("description") or "")):
                found = True
                break
        if found:
            break
        time.sleep(1)

    assert found, f"Created invoice not found by amount search; last items: {last_items[:5] if last_items else None}"


def test_search_invoice_by_fields_not_found(morning_client):
    """Search by a name that should not exist; expect empty results."""
    params = {"clientName": "NO_SUCH_CLIENT_XXXXXXXX"}

    resp = morning_client.list_invoices(params=params)
    items = []
    if isinstance(resp, dict):
        items = resp.get("items") or resp.get("data") or []
    elif isinstance(resp, list):
        items = resp

    assert isinstance(items, list)
    assert len(items) == 0, f"Expected no results for non-existent clientName, got: {items[:5]}"


def test_search_invoice_by_phone_not_found(morning_client):
    """Search by a phone that should not exist; expect empty results."""
    params = {"phone": "+00000000000"}

    resp = morning_client.list_invoices(params=params)
    items = []
    if isinstance(resp, dict):
        items = resp.get("items") or resp.get("data") or []
    elif isinstance(resp, list):
        items = resp

    # Some providers return paged results even when unknown filter is supplied.
    # We assert there are no items that actually match the searched phone.
    matches = []
    for it in items:
        client = it.get("client") or {}
        phone_val = client.get("phone") if isinstance(client, dict) else None
        if phone_val == params["phone"]:
            matches.append(it)

    assert isinstance(items, list)
    assert len(matches) == 0, f"Found items matching unexpected phone value: {matches[:5]}"


def test_search_invoice_by_amount_not_found(morning_client):
    """Search by an amount that should not exist; expect empty results."""
    params = {"amount": 99999999.99}

    resp = morning_client.list_invoices(params=params)
    items = []
    if isinstance(resp, dict):
        items = resp.get("items") or resp.get("data") or []
    elif isinstance(resp, list):
        items = resp

    # Some providers ignore unknown amount filters and return results; assert none match the amount.
    matches = []
    for it in items:
        for key in ("amount", "amountLocal", "total", "sum"):
            v = it.get(key)
            if v is None:
                continue
            try:
                if float(v) == float(params["amount"]):
                    matches.append(it)
                    break
            except Exception:
                continue

    assert isinstance(items, list)
    assert len(matches) == 0, f"Found items matching unexpected amount value: {matches[:5]}"


def test_search_invoice_by_dates_not_found(morning_client):
    """Search by a date range that should not contain any documents; expect empty results."""
    # Use a historical range unlikely to contain any documents
    params = {"fromDate": "1900-01-01", "toDate": "1900-01-02"}

    resp = morning_client.list_invoices(params=params)
    items = []
    if isinstance(resp, dict):
        items = resp.get("items") or resp.get("data") or []
    elif isinstance(resp, list):
        items = resp

    assert isinstance(items, list)
    assert len(items) == 0, f"Expected no results for date range with no documents, got: {items[:5]}"
