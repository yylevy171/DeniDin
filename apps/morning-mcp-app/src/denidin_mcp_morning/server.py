"""FastMCP server exposing the 7 Morning invoice-management tools.

Served over streamable-HTTP so remote MCP clients (e.g. an OpenAI model via
its remote-MCP connector) can discover and call the tools (see spec.md
§Technology Choice). Startup is gated behind `feature_flags.enable_mcp_server`
(default false, per CONSTITUTION §I/§VI) — when disabled, nothing here runs
and the existing client library is unaffected.

Each `@mcp.tool()` wrapper below takes only the caller-facing arguments (no
`client` parameter) so FastMCP's auto-generated inputSchema matches the real
MCP tool contract; the shared `MorningClient` is bound via closure, created
once per server instance by dependency injection (CONSTITUTION §XVII — no
globals, no monkey-patching).
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

HEALTH_PATH = "/health"

from . import tools
from .config import MorningMCPConfig, load_config
from .errors import friendly_error_message
from .morning_client import MorningClient
from .utils.logger import get_logger

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.json"

logger = get_logger(__name__)


class BearerTokenMiddleware(BaseHTTPMiddleware):
    """Reject requests missing a matching `Authorization: Bearer <token>` header.

    No-op if `token` is falsy — appropriate for pure local/dev use (this
    server's own test suite, manual local testing). This server has one
    expected main consumer (denidin-app) plus ad hoc manual tests, so a
    single shared secret is the right model here, not a multi-tenant OAuth
    system (see spec.md — FastMCP's built-in `auth`/`token_verifier` is full
    OAuth 2.1 resource-server machinery, overkill for this use case).
    """

    def __init__(self, app, token: Optional[str]) -> None:
        super().__init__(app)
        self._expected_header = f"Bearer {token}" if token else None

    async def dispatch(self, request: Request, call_next):
        if request.url.path == HEALTH_PATH:
            return await call_next(request)

        if self._expected_header is None:
            return await call_next(request)

        if request.headers.get("Authorization") != self._expected_header:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        return await call_next(request)


async def _health(_request: Request) -> PlainTextResponse:
    """Unauthenticated liveness probe — used by callers (e.g. the ngrok-tunnel
    health check in tests/expensive/e2e_helpers.py) to confirm the server is
    reachable end-to-end without needing the bearer token."""
    return PlainTextResponse("ok")


def build_asgi_app(mcp: FastMCP, auth_token: Optional[str] = None) -> Starlette:
    """Build the MCP server's ASGI app, optionally wrapped with bearer-token auth.

    Bypasses `FastMCP.run()`'s built-in uvicorn runner so the app can be
    wrapped with `BearerTokenMiddleware` before serving (same pattern already
    proven in tests/integration/test_mcp_server_e2e.py).
    """
    app = mcp.streamable_http_app()
    app.router.routes.append(Route(HEALTH_PATH, _health, methods=["GET"]))
    if auth_token:
        app.add_middleware(BearerTokenMiddleware, token=auth_token)
    return app


def _call_with_error_boundary(func: Callable[..., str], *args: Any) -> str:
    """Run a tools.* function, mapping any exception to a friendly message.

    This is the MCP boundary (CONSTITUTION §X/§XVI): a tool must never
    surface a raw exception/stack trace to the caller, and a single failing
    tool call must never take down the server process. Each call gets its
    own correlation id so the friendly message can be traced back to the
    full technical detail in the logs.
    """
    correlation_id = str(uuid.uuid4())
    try:
        return func(*args)
    except Exception as exc:  # noqa: BLE001 - deliberate MCP-boundary catch-all
        return friendly_error_message(exc, correlation_id)


def create_server(config: MorningMCPConfig, client: Optional[MorningClient] = None) -> FastMCP:
    """Build a FastMCP server with all 7 tools registered, bound to one MorningClient.

    Args:
        config: Validated app config (see config.load_config).
        client: Optional pre-built MorningClient (injected); built from `config`
            if omitted. Exposed as a parameter so tests can inject a client
            without needing a second real config file.

    Returns:
        A FastMCP instance, not yet running.
    """
    morning_client = client or MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
        token_ttl_seconds=config.token_ttl_seconds,
        refresh_before_seconds=config.refresh_before_seconds,
    )

    # FastMCP auto-enables Host-header DNS-rebinding protection restricted to
    # 127.0.0.1/localhost whenever `host` is loopback and no transport_security
    # is given — that silently 424s every request forwarded through a public
    # tunnel (ngrok's Host header is never 127.0.0.1/localhost), breaking the
    # documented ngrok-exposure path (tests/expensive, run_morning_mcp.sh,
    # docker-entrypoint.sh) for both random and reserved domains alike.
    # BearerTokenMiddleware (below) is this server's real access boundary, not
    # Host-header matching, so DNS-rebinding protection is explicitly disabled
    # rather than chasing per-run tunnel hostnames.
    mcp = FastMCP(
        name=config.mcp_server_name,
        host=config.mcp_host,
        port=config.mcp_port,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @mcp.tool()
    def create_invoice(
        client_name: str,
        amount: float,
        description: str,
        due_date: Optional[str] = None,
        vat_included: bool = True,
    ) -> str:
        """Create a new invoice/document in Morning."""
        return _call_with_error_boundary(
            tools.create_invoice, morning_client, client_name, amount, description, due_date, vat_included
        )

    @mcp.tool()
    def list_invoices(
        status: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        client_name: Optional[str] = None,
    ) -> str:
        """List/search invoices with optional filters (status/date range/client name)."""
        return _call_with_error_boundary(
            tools.list_invoices, morning_client, status, from_date, to_date, client_name
        )

    @mcp.tool()
    def get_invoice_details(invoice_id: str) -> str:
        """Fetch full details (status, dates, payments) for one invoice."""
        return _call_with_error_boundary(tools.get_invoice_details, morning_client, invoice_id)

    @mcp.tool()
    def update_invoice_status(
        invoice_id: str,
        status: str,
        payment_date: Optional[str] = None,
    ) -> str:
        """Update an invoice's payment status: "paid", "unpaid", or "cancelled"."""
        return _call_with_error_boundary(
            tools.update_invoice_status, morning_client, invoice_id, status, payment_date
        )

    @mcp.tool()
    def add_client(
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        tax_id: Optional[str] = None,
        address: Optional[str] = None,
    ) -> str:
        """Add a new client to Morning."""
        return _call_with_error_boundary(tools.add_client, morning_client, name, email, phone, tax_id, address)

    @mcp.tool()
    def get_financial_summary(
        period: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> str:
        """Aggregate totals/counts for a period: "month", "quarter", "year", or "custom"."""
        return _call_with_error_boundary(
            tools.get_financial_summary, morning_client, period, from_date, to_date
        )

    @mcp.tool()
    def download_invoice_pdf(invoice_id: str) -> str:
        """Return a PDF download link for an invoice."""
        return _call_with_error_boundary(tools.download_invoice_pdf, morning_client, invoice_id)

    return mcp


def main() -> None:
    """Entry point: `python3 -m denidin_mcp_morning.server`."""
    config = load_config(DEFAULT_CONFIG_PATH)

    if not config.enable_mcp_server:
        logger.info("MCP server disabled (feature_flags.enable_mcp_server=false); exiting.")
        raise SystemExit(
            "MCP server disabled (feature_flags.enable_mcp_server=false in "
            "config/config.json). Set it to true to start the server."
        )

    server = create_server(config)
    logger.info(
        "Starting %s on %s:%s (%s)%s",
        config.mcp_server_name,
        config.mcp_host,
        config.mcp_port,
        config.mcp_transport,
        " [bearer-token auth enabled]" if config.mcp_auth_token else " [no auth configured]",
    )

    if config.mcp_transport == "streamable-http":
        # Bypass FastMCP.run()'s built-in uvicorn runner so the app can be
        # wrapped with BearerTokenMiddleware before serving.
        import uvicorn

        app = build_asgi_app(server, auth_token=config.mcp_auth_token)
        uvicorn.run(app, host=config.mcp_host, port=config.mcp_port, log_level=config.mcp_log_level.lower())
    else:
        # stdio/sse aren't network-exposed the same way; no HTTP-level
        # bearer check applies (and none was requested by this project's
        # single-consumer streamable-http use case).
        server.run(transport=config.mcp_transport)


if __name__ == "__main__":
    main()
