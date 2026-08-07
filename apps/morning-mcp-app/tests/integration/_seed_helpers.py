"""Shared real-sandbox seeding helper for feature 027's integration tests.

Feature 027: create_invoice/create_transaction_account/create_combo_document
now resolve their client_name against a real client record before creating
anything - every real-sandbox test/fixture that used to create a document
for a never-before-seen client_name must seed that client first via this
helper, or its create_* call will now be refused ("client not found").
"""
import time
from typing import Optional, Tuple

from denidin_mcp_morning.morning_client import MorningClient


def seed_real_client(morning_client: MorningClient, marker: str, name: Optional[str] = None) -> Tuple[str, str]:
    """Create a real Morning client and return (client_id, client_name).

    `name` defaults to "Test Client {marker}"; pass an explicit `name` when
    a test needs a specific client name shape (e.g. testing substring
    matching against a realistic-looking name).

    Also polls `search_clients` afterward (the sandbox's search index can
    lag briefly after a write - the same eventual-consistency class
    documented in Feature 026's research.md Decision 8 and
    test_morning_sandbox_list_clients_tool.py, up to 12x/1.5s = 18s) so the
    client is actually findable before any caller immediately tries to
    resolve it by name via a create_* tool.
    """
    client_name = name or f"Test Client {marker}"
    response = morning_client.add_client(
        {"name": client_name, "emails": [f"{marker}@example.com"], "phone": "050-1234567"}
    )
    client_id = response["id"]
    for _ in range(12):
        if morning_client.search_clients({"name": client_name}).get("items"):
            break
        time.sleep(1.5)
    return client_id, client_name
