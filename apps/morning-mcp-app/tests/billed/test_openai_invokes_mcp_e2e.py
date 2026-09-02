"""Real E2E test: an external OpenAI call drives the running MCP server (Phase 5, T021).

@pytest.mark.billed — uses real, text-only OpenAI API calls (Feature 029,
2026-07-30, split the single `expensive` marker into `billed` and
`expensive`). Per CONSTITUTION §VII / CLAUDE.md: billed tests are cheap and
can be run freely — no per-run approval, no one-at-a-time restriction (unlike
`expensive`, which stays gated behind those rules for real vision/media
calls).

No mocks anywhere: real FastMCP server (streamable-HTTP), real ngrok tunnel,
real OpenAI Responses API call with this server registered as a remote MCP
tool, real Morning sandbox document verification. This proves the thing
tests/integration/test_mcp_server_e2e.py cannot: that an *external* MCP
client neither this app nor its own test suite controls can actually
discover and drive these tools over the real MCP protocol, over the public
internet, exactly as a production integration would.

MCP output-item schema used below (`type == "mcp_call"`, `.name`,
`.arguments`, `.output`, `.error`) was confirmed directly against the
installed `openai` SDK's `openai.types.responses.response_output_item.McpCall`
class — not guessed from documentation, which is thinner on this than the
SDK's own type definitions.

Every test in this module passes the same `instructions` (OpenAI's
system-prompt-level parameter on `responses.create()` — confirmed as a real,
distinct top-level SDK parameter) via
`tests.e2e_helpers.OPENAI_ASSISTANT_INSTRUCTIONS`, so all of them
exercise the model under identical guidance about when these tools apply.
`test_openai_does_not_invoke_mcp_tools_for_unrelated_prompt` is the negative
counterpart: it asserts that guidance actually holds — no Morning tool call
happens for a prompt with nothing to do with invoicing.
"""
from __future__ import annotations

import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest
import uvicorn

APP_ROOT = Path(__file__).resolve().parents[2]
# Uses config.test.json (sandbox), not config.json — per user decision
# 2026-07-09 ("we are not yet in production for this app, so until further
# notice use config.test.json"). config.test.json is gitignored (real
# secrets, incl. openai_api_key/mcp.ngrok_authtoken added for this purpose)
# but its Morning creds already point at the sandbox — so a successful
# create_invoice call here lands in the sandbox, not production.
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"
sys.path.insert(0, str(APP_ROOT))

from tests.e2e_helpers import (  # noqa: E402
    OPENAI_ASSISTANT_INSTRUCTIONS,
    NgrokError,
    discover_running_server,
    ngrok_tunnel,
)

from denidin_mcp_morning.config import load_config  # noqa: E402
from denidin_mcp_morning.morning_client import MorningClient  # noqa: E402
from denidin_mcp_morning.server import build_asgi_app, create_server  # noqa: E402

TEST_HOST = "127.0.0.1"
TEST_PORT = 8792


def _seed_client(morning_client: MorningClient, client_name: str, unique_marker: str) -> None:
    """Create a real Morning client and wait until it's findable.

    Feature 027: create_invoice now resolves client_name against a real
    client record before creating anything - a prompt naming a
    never-before-seen client would otherwise be refused. Seeds directly via
    MorningClient (this file already imports it for verification, unlike
    apps/denidin-app's E2E layer, which has no such access) rather than
    routing through a second OpenAI-driven add_client call.
    """
    morning_client.add_client(
        {"name": client_name, "emails": [f"{unique_marker}@example.com"], "phone": "050-1234567"}
    )
    for _ in range(12):
        if morning_client.search_clients({"name": client_name}).get("items"):
            return
        time.sleep(1.5)

# Same text model denidin-app uses (apps/denidin-app/config/config.dev.json's
# `ai_model`), per user decision 2026-07-09.
OPENAI_MODEL = "gpt-4o-mini"


@pytest.fixture(scope="module")
def config():
    if not CONFIG_PATH.exists():
        pytest.skip("config/config.test.json not found")

    cfg = load_config(CONFIG_PATH)
    if not cfg.openai_api_key:
        pytest.skip("No openai_api_key configured in config/config.test.json")
    if not cfg.mcp_ngrok_authtoken:
        pytest.skip("No mcp.ngrok_authtoken configured in config/config.test.json")
    if not (cfg.api_key_id and cfg.api_key_secret):
        pytest.skip("No Morning credentials in config/config.test.json")
    return cfg


# Shared per-environment status file (019-env-separation) - the same file
# `./run_morning_mcp.sh dev` writes and `apps/denidin-app`'s own tests read
# to discover the live dev tunnel. APP_ROOT is apps/morning-mcp-app/; the
# repo root is two levels up.
DEV_STATUS_FILE_PATH = APP_ROOT.parent.parent / "shared" / "mcp-status-dev" / "morning_mcp_status.dev.json"


@pytest.fixture(scope="module")
def mcp_endpoint(config):
    """Yield (server_url, auth_token) for a real, reachable MCP server.

    Prefers an already-running standalone `./run_morning_mcp.sh dev` server
    (see `discover_running_server`) — its ngrok tunnel is already warm,
    avoiding the cold-start window where a brand-new tunnel is registered
    locally but not yet reachable from the public internet (observed as
    OpenAI returning HTTP 424 Failed Dependency on the very first request).
    Falls back to starting our own local server + ephemeral tunnel only if no
    standalone server is live.
    """
    discovered = discover_running_server(DEV_STATUS_FILE_PATH, config.mcp_auth_token)
    if discovered is not None:
        yield discovered
        return

    client = MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
        auth_url=config.auth_url,
    )
    mcp = create_server(config, client=client)
    mcp.settings.host = TEST_HOST
    mcp.settings.port = TEST_PORT

    auth_token = config.mcp_auth_token or "expensive-test-token"
    app = build_asgi_app(mcp, auth_token=auth_token)
    uv_config = uvicorn.Config(app, host=TEST_HOST, port=TEST_PORT, log_level="warning")
    server = uvicorn.Server(uv_config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    for _ in range(50):
        if server.started:
            break
        time.sleep(0.1)
    else:
        pytest.fail("Local MCP server did not start in time")

    try:
        with ngrok_tunnel(port=TEST_PORT, authtoken=config.mcp_ngrok_authtoken) as public_url:
            yield f"{public_url}/mcp", auth_token
    except NgrokError as exc:
        pytest.skip(f"ngrok tunnel unavailable: {exc}")
    finally:
        server.should_exit = True
        thread.join(timeout=5)


@pytest.mark.billed
@pytest.mark.sanity
def test_openai_invokes_create_invoice_via_remote_mcp(config, mcp_endpoint):
    """A real OpenAI Responses API call, given a natural-language prompt and
    this server registered as a remote MCP tool (over a real public ngrok
    tunnel), must actually invoke create_invoice and produce a real document
    in the Morning sandbox — verified independently, not just trusted from
    the model's own textual claim of success.
    """
    from openai import OpenAI

    server_url, auth_token = mcp_endpoint
    unique_marker = f"DENIDIN_OPENAI_E2E_{int(datetime.now(timezone.utc).timestamp())}"
    client_name = f"Test Corp {unique_marker}"

    # Feature 027: create_invoice now requires a real, pre-existing client.
    morning_client = MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
        auth_url=config.auth_url,
    )
    _seed_client(morning_client, client_name, unique_marker)

    openai_client = OpenAI(api_key=config.openai_api_key)

    response = openai_client.responses.create(
        model=OPENAI_MODEL,
        instructions=OPENAI_ASSISTANT_INSTRUCTIONS,
        input=(
            f"Create an invoice for a client named '{client_name}' for 50 NIS, "
            f"description 'Consulting services {unique_marker}'."
        ),
        tools=[
            {
                "type": "mcp",
                "server_label": "morning-invoices",
                "server_url": server_url,
                "require_approval": "never",
                "headers": {"Authorization": f"Bearer {auth_token}"},
            }
        ],
    )

    mcp_calls = [item for item in response.output if getattr(item, "type", None) == "mcp_call"]
    create_invoice_calls = [call for call in mcp_calls if call.name == "create_invoice"]

    assert create_invoice_calls, (
        f"Model did not invoke create_invoice via the remote MCP server. "
        f"Full output: {response.output!r}"
    )
    assert all(call.error is None for call in create_invoice_calls), (
        f"create_invoice call(s) reported an error: {[c.error for c in create_invoice_calls]}"
    )

    # Independently verify: a real document actually landed in the Morning
    # sandbox, not just that the model/tool claimed success.
    found = False
    last_items = None
    for _ in range(12):
        resp = morning_client.list_invoices(params={"clientName": client_name})
        items = (resp.get("items") or resp.get("data") or []) if isinstance(resp, dict) else resp
        last_items = items
        if any(
            (item.get("client") or {}).get("name") == client_name
            or unique_marker in (item.get("description") or "")
            for item in items
        ):
            found = True
            break
        time.sleep(1.5)

    assert found, (
        f"No invoice for {client_name!r} found in Morning after the OpenAI-driven call; "
        f"last search results: {last_items}"
    )


@pytest.mark.billed
def test_openai_created_invoice_is_signed_per_real_morning_api(config, mcp_endpoint):
    """bugfix-026 regression guard: a document created through this real,
    OpenAI-driven MCP flow must come back from Morning's own real GET
    /documents/{id} endpoint with `signed: true` — not just trusted from the
    model's textual claim or from list_invoices' search-result shape (which
    the sibling test above already checks), but from the exact endpoint
    Morning's "not digitally signed" email-share block cares about.

    Independent from test_openai_invokes_create_invoice_via_remote_mcp (own
    unique_marker/client_name) so it can be re-run alone without depending on
    that test's document existing.
    """
    from openai import OpenAI

    server_url, auth_token = mcp_endpoint
    unique_marker = f"DENIDIN_SIGNED_CHECK_{int(datetime.now(timezone.utc).timestamp())}"
    client_name = f"Test Corp {unique_marker}"

    # Feature 027: create_invoice now requires a real, pre-existing client.
    morning_client = MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
        auth_url=config.auth_url,
    )
    _seed_client(morning_client, client_name, unique_marker)

    openai_client = OpenAI(api_key=config.openai_api_key)

    response = openai_client.responses.create(
        model=OPENAI_MODEL,
        instructions=OPENAI_ASSISTANT_INSTRUCTIONS,
        input=(
            f"Create an invoice for a client named '{client_name}' for 50 NIS, "
            f"description 'Consulting services {unique_marker}'."
        ),
        tools=[
            {
                "type": "mcp",
                "server_label": "morning-invoices",
                "server_url": server_url,
                "require_approval": "never",
                "headers": {"Authorization": f"Bearer {auth_token}"},
            }
        ],
    )

    mcp_calls = [item for item in response.output if getattr(item, "type", None) == "mcp_call"]
    create_invoice_calls = [call for call in mcp_calls if call.name == "create_invoice"]
    assert create_invoice_calls, (
        f"Model did not invoke create_invoice via the remote MCP server. "
        f"Full output: {response.output!r}"
    )
    assert all(call.error is None for call in create_invoice_calls), (
        f"create_invoice call(s) reported an error: {[c.error for c in create_invoice_calls]}"
    )

    # Find the real document's internal id (not just the human-facing number
    # in the Hebrew confirmation text) by searching the sandbox directly,
    # same lookup-by-marker pattern as the sibling test above.
    found_item = None
    for _ in range(12):
        resp = morning_client.list_invoices(params={"clientName": client_name})
        items = (resp.get("items") or resp.get("data") or []) if isinstance(resp, dict) else resp
        for item in items:
            if (item.get("client") or {}).get("name") == client_name or unique_marker in (
                item.get("description") or ""
            ):
                found_item = item
                break
        if found_item:
            break
        time.sleep(1.5)

    assert found_item, f"No invoice for {client_name!r} found in Morning after the OpenAI-driven call."
    document_id = str(found_item.get("id") or found_item.get("documentId") or "")
    assert document_id, f"Found invoice has no usable id: {found_item!r}"

    # The actual regression check: query Morning's real GET /documents/{id}
    # endpoint directly (MorningClient.get_invoice) and assert the document
    # it returns is signed — the exact fact Morning's email-share feature
    # gates on (bugfix-026).
    real_document = morning_client.get_invoice(document_id)
    assert real_document.get("signed") is True, (
        f"Document created via create_invoice was NOT signed per Morning's "
        f"real API response (bugfix-026 regression): {real_document!r}"
    )


@pytest.mark.billed
def test_openai_does_not_invoke_mcp_tools_for_unrelated_prompt(config, mcp_endpoint):
    """A prompt with nothing to do with invoicing must NOT trigger any Morning
    MCP tool call, even though the tools are registered and available. This is
    the negative-case counterpart to
    test_openai_invokes_create_invoice_via_remote_mcp: it proves the model
    respects OPENAI_ASSISTANT_INSTRUCTIONS' scoping guidance rather than
    reaching for these tools indiscriminately.
    """
    from openai import OpenAI

    server_url, auth_token = mcp_endpoint

    openai_client = OpenAI(api_key=config.openai_api_key)

    response = openai_client.responses.create(
        model=OPENAI_MODEL,
        instructions=OPENAI_ASSISTANT_INSTRUCTIONS,
        input="Write a short haiku about the changing seasons.",
        tools=[
            {
                "type": "mcp",
                "server_label": "morning-invoices",
                "server_url": server_url,
                "require_approval": "never",
                "headers": {"Authorization": f"Bearer {auth_token}"},
            }
        ],
    )

    mcp_calls = [item for item in response.output if getattr(item, "type", None) == "mcp_call"]

    assert not mcp_calls, (
        f"Model invoked Morning MCP tool(s) for an unrelated prompt: "
        f"{[c.name for c in mcp_calls]!r}. Full output: {response.output!r}"
    )
