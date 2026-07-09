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

from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from . import tools
from .config import MorningMCPConfig, load_config
from .morning_client import MorningClient

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "config.json"


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

    mcp = FastMCP(name=config.mcp_server_name, host=config.mcp_host, port=config.mcp_port)

    @mcp.tool()
    def create_invoice(
        client_name: str,
        amount: float,
        description: str,
        due_date: Optional[str] = None,
        vat_included: bool = True,
    ) -> str:
        """Create a new invoice/document in Morning."""
        return tools.create_invoice(morning_client, client_name, amount, description, due_date, vat_included)

    @mcp.tool()
    def list_invoices(
        status: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        client_name: Optional[str] = None,
    ) -> str:
        """List/search invoices with optional filters (status/date range/client name)."""
        return tools.list_invoices(morning_client, status, from_date, to_date, client_name)

    @mcp.tool()
    def get_invoice_details(invoice_id: str) -> str:
        """Fetch full details (status, dates, payments) for one invoice."""
        return tools.get_invoice_details(morning_client, invoice_id)

    @mcp.tool()
    def update_invoice_status(
        invoice_id: str,
        status: str,
        payment_date: Optional[str] = None,
    ) -> str:
        """Update an invoice's payment status: "paid", "unpaid", or "cancelled"."""
        return tools.update_invoice_status(morning_client, invoice_id, status, payment_date)

    @mcp.tool()
    def add_client(
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        tax_id: Optional[str] = None,
        address: Optional[str] = None,
    ) -> str:
        """Add a new client to Morning."""
        return tools.add_client(morning_client, name, email, phone, tax_id, address)

    @mcp.tool()
    def get_financial_summary(
        period: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> str:
        """Aggregate totals/counts for a period: "month", "quarter", "year", or "custom"."""
        return tools.get_financial_summary(morning_client, period, from_date, to_date)

    @mcp.tool()
    def download_invoice_pdf(invoice_id: str) -> str:
        """Return a PDF download link for an invoice."""
        return tools.download_invoice_pdf(morning_client, invoice_id)

    return mcp


def main() -> None:
    """Entry point: `python3 -m denidin_mcp_morning.server`."""
    config = load_config(DEFAULT_CONFIG_PATH)

    if not config.enable_mcp_server:
        raise SystemExit(
            "MCP server disabled (feature_flags.enable_mcp_server=false in "
            "config/config.json). Set it to true to start the server."
        )

    server = create_server(config)
    server.run(transport=config.mcp_transport)


if __name__ == "__main__":
    main()
