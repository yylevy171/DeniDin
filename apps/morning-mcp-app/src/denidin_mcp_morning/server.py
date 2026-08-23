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
from typing import Any, Callable, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent
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
from .utils.correlation import correlation_scope, new_correlation_id
from .utils.logger import DEFAULT_VERSION_FILE, read_version, get_logger, reconfigure_package_log_level

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


def _make_health_handler(environment: Optional[str], version: str) -> Callable[[Request], Any]:
    """Build the /health handler, closing over this process's own declared
    `environment` (2026-07-21 incident: watchdog.py needs a caller-visible,
    at-rest AND external-tunnel way to confirm which environment a server
    is actually serving as, not just what its mounted config claims) and its
    current `version` (Feature 034, REQ-VER-002 - read once at startup, not
    per-request, since a version can't change mid-process)."""

    async def _health(_request: Request) -> JSONResponse:
        """Unauthenticated liveness probe - used by callers (e.g. the
        ngrok-tunnel health check in tests/e2e_helpers.py, and each
        environment's watchdog.py) to confirm the server is reachable
        end-to-end without needing the bearer token, and which environment
        it's actually running as."""
        return JSONResponse({"status": "ok", "environment": environment, "version": version})

    return _health


def build_asgi_app(
    mcp: FastMCP,
    auth_token: Optional[str] = None,
    environment: Optional[str] = None,
    version_file: Path = DEFAULT_VERSION_FILE,
) -> Starlette:
    """Build the MCP server's ASGI app, optionally wrapped with bearer-token auth.

    Bypasses `FastMCP.run()`'s built-in uvicorn runner so the app can be
    wrapped with `BearerTokenMiddleware` before serving (same pattern already
    proven in tests/integration/test_mcp_server_e2e.py).

    `version_file` (Feature 034, REQ-VER-002): defaults to this app's real VERSION file;
    tests pass a scratch path.
    """
    app = mcp.streamable_http_app()
    version = read_version(Path(version_file))
    app.router.routes.append(
        Route(HEALTH_PATH, _make_health_handler(environment, version), methods=["GET"])
    )
    if auth_token:
        app.add_middleware(BearerTokenMiddleware, token=auth_token)
    return app


def _call_with_error_boundary(func: Callable[..., str], *args: Any) -> "str | CallToolResult":
    """Run a tools.* function, mapping any exception to a friendly message
    AND a real MCP-level failure - never plain text indistinguishable from
    success.

    This is the MCP boundary (CONSTITUTION §X/§XVI): a tool must never
    surface a raw exception/stack trace to the caller, and a single failing
    tool call must never take down the server process. Each call gets its
    own correlation id so the friendly message can be traced back to the
    full technical detail in the logs.

    Client-name-resolution architecture fix follow-up (2026-08-12, user
    decision): every tool has exactly two outcomes - it succeeds, or it
    raises. There is no third "ordinary text that happens to describe a
    failure" outcome (that was the exact shape of bugfix-028 B4(c)'s
    original bug - a tool that didn't do what was asked, returning text
    indistinguishable from success). Confirmed live (real FastMCP server,
    real MCP client, no mocking) that a tool function can RETURN (not just
    raise) a `CallToolResult(isError=True, ...)` and the real `isError` flag
    survives the round-trip untouched, with fully controlled friendly
    content - unlike letting the exception propagate uncaught, which would
    still set `isError=True` but with FastMCP's own auto-generated
    "Error executing tool X: <raw message>" text instead of ours. Every
    `@mcp.tool()` registration that routes through this function must pass
    `structured_output=False` (confirmed live too: without it, FastMCP
    auto-generates a `{"result": <str>}` output schema from the declared
    `-> str` return annotation, and validating our returned CallToolResult
    against that schema fails with a confusing Pydantic error - a strictly
    WORSE outcome than the bug this fixes).

    It is also the one point every tool passes through, so it owns the
    call-level half of the audit trail (bugfix-036): which tool was invoked,
    with which caller-facing arguments, and how it ended. The per-Morning-call
    half - payload sent, response received - is written by `audit.py` from
    inside the mutating tools, under the same correlation id.

    `args[0]` is always the injected MorningClient; it is dropped from the
    logged arguments (it carries the API credentials and is identical for
    every call, so logging it would be both a leak risk and pure noise).
    """
    correlation_id = new_correlation_id()
    tool_name = getattr(func, "__name__", repr(func))
    with correlation_scope(correlation_id):
        logger.info("[corr_id=%s] TOOL CALL %s args=%r", correlation_id, tool_name, args[1:])
        try:
            result = func(*args)
        except Exception as exc:  # noqa: BLE001 - deliberate MCP-boundary catch-all
            logger.info("[corr_id=%s] TOOL ERROR %s", correlation_id, tool_name)
            friendly_message = friendly_error_message(exc, correlation_id)
            return CallToolResult(
                content=[TextContent(type="text", text=friendly_message)],
                isError=True,
            )
        # Full result body (2026-08-19, user decision - supersedes the prior
        # length-only design below): this app's tool arguments/results are all
        # plain text/JSON, never binary (confirmed - even download_invoice_pdf
        # returns a URL string, not file bytes), so there is no redaction
        # concern here the way there is for denidin-app's WhatsApp media
        # webhooks. "Everything that comes in, everything that goes out" now
        # applies uniformly to every tool, mutating or read-only alike -
        # mutations still ALSO get their own audit.py record (payload sent to
        # Morning, response received, resolved client), which this does not
        # replace.
        #
        # Previously: result length only, never the body - read tools return
        # formatted lists that can run to thousands of characters and would
        # bury the mutation records audit.py preserves. Kept as history, not
        # current behavior.
        logger.info(
            "[corr_id=%s] TOOL OK %s result_chars=%d result=%r",
            correlation_id, tool_name, len(result or ""), result,
        )
        return result


def create_server(config: MorningMCPConfig, client: Optional[MorningClient] = None) -> FastMCP:
    """Build a FastMCP server with all 11 tools registered, bound to one MorningClient.

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
        auth_url=config.auth_url,
        refresh_before_seconds=config.refresh_before_seconds,
    )

    # FastMCP auto-enables Host-header DNS-rebinding protection restricted to
    # 127.0.0.1/localhost whenever `host` is loopback and no transport_security
    # is given — that silently 424s every request forwarded through a public
    # tunnel (ngrok's Host header is never 127.0.0.1/localhost), breaking the
    # documented ngrok-exposure path (tests/billed, run_morning_mcp.sh,
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

    @mcp.tool(structured_output=False)
    def create_invoice(
        client_name: str,
        amount: float,
        description: str,
        due_date: Optional[str] = None,
        vat_included: bool = True,
        name_resolved: bool = False,
    ) -> str:
        """Create an ordinary TAX INVOICE ("חשבונית מס", document type 305) - a
        request for payment that has NOT yet been received, which stays open/unpaid
        until a receipt is issued against it.

        Do NOT use this for money that has already arrived (a bank deposit, a
        transfer confirmation, a payment screenshot): use create_combo_document for
        a new payment, or create_receipt against the invoice the payment settles.

        REQUIRES name_resolved=True: call resolve_client_name first with this
        client_name, then pass the EXACT name it returns here, together with
        name_resolved=True. Without it, this refuses immediately.
        """
        return _call_with_error_boundary(
            tools.create_invoice, morning_client, client_name, amount, description,
            due_date, vat_included, name_resolved
        )

    @mcp.tool(structured_output=False)
    def create_transaction_account(
        client_name: str,
        amount: float,
        description: str,
        vat_included: bool,
        due_date: Optional[str] = None,
        name_resolved: bool = False,
    ) -> str:
        """Create a non-tax transaction account ("חשבון עסקה", document type 300) -
        like an invoice, but not itself a tax document. Use when the user explicitly
        asks for a חשבון עסקה rather than an ordinary tax invoice.

        `vat_included` is REQUIRED: state whether `amount` already includes VAT.
        There is no default and no "unknown" - ask the user if it isn't clear.
        Getting it wrong silently changes what the client is billed (Morning adds
        ~18% to an amount declared as VAT-exclusive).

        REQUIRES name_resolved=True: call resolve_client_name first with this
        client_name, then pass the EXACT name it returns here, together with
        name_resolved=True. Without it, this refuses immediately.
        """
        return _call_with_error_boundary(
            tools.create_transaction_account, morning_client, client_name, amount,
            description, vat_included, due_date, name_resolved
        )

    @mcp.tool(structured_output=False)
    def create_combo_document(
        client_name: str,
        amount: float,
        description: str,
        vat_included: bool,
        payment_date: str,
        payment_method: str = "bank_transfer",
        bank_number: Optional[str] = None,
        bank_branch: Optional[str] = None,
        bank_account: Optional[str] = None,
        transaction_reference: Optional[str] = None,
        name_resolved: bool = False,
    ) -> str:
        """Create a combo tax invoice + receipt ("חשבונית מס/קבלה", document type 320)
        for a payment that has ALREADY been received - a single self-contained,
        already-paid document, never a request for later payment.

        This is the right document for a bank deposit or transfer confirmation when
        no earlier invoice covers that money. If an unpaid invoice for it already
        exists, issue a receipt against that invoice instead (create_receipt for a
        305, create_combo_document_as_reference for a 300) - never a second document for the
        same money.

        `vat_included` and `payment_date` are REQUIRED and must come from the real
        transaction, never a guess: `payment_date` is the date the money actually
        moved (ISO YYYY-MM-DD, never a future date, never "today" unless that is
        genuinely when it arrived). Ask the user if either is unclear.

        `payment_method` records how it arrived: "bank_transfer" (default), "cash",
        "cheque", "credit_card", "paypal", or an app ("bit", "pay", "paybox",
        "colu", "google pay", "apple pay"). Bank details are stored only on a bank
        transfer; a reference number (אסמכתה) only on an app or PayPal payment.
        `bank_number` is the bank's NUMBER (e.g. "31"), not its name - never
        invent a bank's name when only its number is known.

        REQUIRES name_resolved=True: call resolve_client_name first with this
        client_name, then pass the EXACT name it returns here, together with
        name_resolved=True. Without it, this refuses immediately.
        """
        return _call_with_error_boundary(
            tools.create_combo_document, morning_client, client_name, amount, description,
            vat_included, payment_date, payment_method, bank_number, bank_branch,
            bank_account, transaction_reference, name_resolved
        )

    @mcp.tool(structured_output=False)
    def create_credit_note(
        original_internal_morning_id: str,
        amount: Optional[float] = None,
        description: Optional[str] = None,
    ) -> str:
        """Create a standalone credit note ("חשבונית זיכוי", document type 330)
        linked to an existing document, identified by original_internal_morning_id (the
        Morning document id of the invoice being credited - resolve this first,
        e.g. via list_invoices, if the user only gave a client name or invoice
        number). Defaults to a full credit against the original's total; pass
        amount for a partial credit note. Also the correct target for "cancel
        this invoice" phrasing (there is no separate status-update tool) -
        call this directly with the full amount in that case."""
        return _call_with_error_boundary(
            tools.create_credit_note, morning_client, original_internal_morning_id, amount, description
        )

    @mcp.tool(structured_output=False)
    def create_receipt(
        original_internal_morning_id: str,
        payment_date: str,
        amount: Optional[float] = None,
    ) -> str:
        """Create a standalone receipt ("קבלה", document type 400) linked to an
        existing document, identified by original_internal_morning_id (the Morning document
        id of the invoice being paid - resolve this first, e.g. via list_invoices,
        if the user only gave a client name or invoice number). Defaults to the
        original's full total; pass amount for a partial-payment receipt. Also
        the correct target for "mark as paid" phrasing once the referenced
        document's type is resolved to 305, not 300 (there is no separate
        status-update tool) - only supports type-305 originals, raises a clear
        error for a type-300 original (use create_combo_document_as_reference instead).

        REQUIRES payment_date: the real date the money moved, ISO YYYY-MM-DD.
        "Today" is a genuinely fine answer for a verbal "mark as paid" request,
        but only once asked and confirmed - never silently assumed. Ask the
        user if it isn't already stated in the conversation."""
        return _call_with_error_boundary(
            tools.create_receipt, morning_client, original_internal_morning_id, payment_date, amount
        )

    @mcp.tool(structured_output=False)
    def create_combo_document_as_reference(
        original_internal_morning_id: str,
        payment_date: str,
        amount: Optional[float] = None,
        description: Optional[str] = None,
        vat_included: bool = True,
        payment_method: str = "bank_transfer",
        bank_number: Optional[str] = None,
        bank_branch: Optional[str] = None,
        bank_account: Optional[str] = None,
        transaction_reference: Optional[str] = None,
    ) -> str:
        """Create a combo document ("חשבונית מס/קבלה", document type 320) that
        closes an existing transaction account ("חשבון עסקה", document type 300),
        identified by original_internal_morning_id (the Morning document id of the
        transaction account being closed - resolve this first, e.g. via
        list_invoices, if the user only gave a client name or document number).
        Defaults to closing the full amount; pass amount for a partial close.
        Only supports type-300 originals - raises a clear error for any other
        original document type. A transaction account itself carries no VAT
        field to infer vat_included from - if it isn't clear from the
        conversation whether VAT should be included, ask the user rather than
        guessing. Also the correct target for "mark as paid" phrasing once
        the referenced document's type is resolved to 300 (there is no
        separate status-update tool).

        REQUIRES payment_date: the real date the money moved, ISO YYYY-MM-DD.
        "Today" is a genuinely fine answer for a verbal "mark as paid" request,
        but only once asked and confirmed - never silently assumed. Ask the
        user if it isn't already stated in the conversation (bugfix-038 - same
        treatment as create_receipt/create_combo_document; this tool used to
        silently default to today, which is exactly the bug this fixed).

        `payment_method` records how it arrived: "bank_transfer" (default), "cash",
        "cheque", "credit_card", "paypal", or an app ("bit", "pay", "paybox",
        "colu", "google pay", "apple pay"). Bank details are stored only on a bank
        transfer; a reference number (אסמכתה) only on an app or PayPal payment.
        `bank_number` is the bank's NUMBER (e.g. "31"), not its name."""
        return _call_with_error_boundary(
            tools.create_combo_document_as_reference, morning_client, original_internal_morning_id, payment_date,
            amount, description, vat_included, payment_method, bank_number, bank_branch,
            bank_account, transaction_reference
        )

    @mcp.tool(structured_output=False)
    def list_invoices(
        status: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        client_name: Optional[str] = None,
        document_display_number: Optional[str] = None,
        name_resolved: bool = False,
        output_format: str = "text",
        purpose: str = "conversation",
    ) -> str:
        """List/search invoices with optional filters (status/date range/client
        name/exact document_display_number - e.g. "51365", the human-visible
        label - NEVER an internal_morning_id).

        output_format: leave unset (or "text") for the normal Hebrew,
        human-readable result - that is what you want when answering a person.
        Pass "json" ONLY for automated bookkeeping/reconciliation tasks that
        explicitly ask for machine-readable output; it returns every match
        untruncated, with native types and explicit nulls.

        purpose: leave unset (or "conversation") whenever you are answering a
        person - this is almost always what you want. Pass "reconciliation"
        ONLY for an automated ledger/bookkeeping sweep that explicitly asks for
        it: it makes this tool fetch full per-document details (payment bank
        number/branch/account, linked documents) for EVERY matching document,
        which is far more expensive and is never needed to answer a question.

        A MULTI-WORD client_name REQUIRES name_resolved=True: call
        resolve_client_name first, then pass the EXACT name it returns here,
        together with name_resolved=True. A single-word client_name is a
        plain substring search and does not need this.
        """
        return _call_with_error_boundary(
            tools.list_invoices,
            morning_client,
            status,
            from_date,
            to_date,
            client_name,
            document_display_number,
            config.list_invoices_token_budget,
            name_resolved,
            output_format,
            purpose,
        )

    @mcp.tool(structured_output=False)
    def get_invoice_details(internal_morning_id: str, output_format: str = "text") -> str:
        """Fetch full details for one document: status, dates, payments
        (including structured bank number/branch/account for a bank transfer),
        and any linked documents.

        Use this whenever you need a document's complete data, in EITHER of
        these situations:
        (a) resolving a document's real type/current status before deciding
            which create_*/close_* tool to call for a status-change request
            ("mark as paid", "cancel it") - there is no separate status-update
            tool, only document creation; and
        (b) any automated bookkeeping/reconciliation task that needs a
            document's full detail - in particular its payment and linked
            document information, which list_invoices does not carry.

        (Reworded 2026-08-23: the previous description mentioned only case (a),
        and a real automated task consequently never called this tool at all,
        across six live attempts, no matter how explicitly it was instructed
        to - the tool's own description outweighed the instruction.)

        output_format: leave unset (or "text") for the normal Hebrew,
        human-readable view. Pass "json" ONLY for automated tasks that
        explicitly ask for machine-readable output."""
        return _call_with_error_boundary(
            tools.get_invoice_details, morning_client, internal_morning_id, output_format
        )

    @mcp.tool(structured_output=False)
    def add_client(
        name: str,
        email: str,
        phone: str,
        tax_id: Optional[str] = None,
    ) -> str:
        """Add a new client to Morning. name/email/phone are all required -
        ask the user for any that are missing rather than guessing."""
        return _call_with_error_boundary(tools.add_client, morning_client, name, email, phone, tax_id)

    @mcp.tool(structured_output=False)
    def list_clients(name: Optional[str] = None) -> str:
        """List existing Morning clients. Pass name to narrow server-side
        (token-prefix match) - useful when a bare list would match too many
        clients to display (the tool itself reports the real total and asks
        to narrow when that happens)."""
        return _call_with_error_boundary(tools.list_clients, morning_client, name)

    @mcp.tool(structured_output=False)
    def resolve_client_name(name: str) -> str:
        """Resolve a client name to Morning's exact stored name before calling
        any other tool that needs one specific client (get_client_details,
        list_invoices with a client_name filter, create_invoice,
        create_transaction_account, create_combo_document, update_client).

        ALWAYS call this first whenever a user's request references a client by
        name - even a name you believe is already exact - then pass the EXACT
        name this returns, verbatim, into the target tool together with
        name_resolved=True. Those six tools no longer do their own fuzzy
        matching: they require name_resolved=True and refuse immediately,
        without attempting any lookup, if it isn't set.
        """
        return _call_with_error_boundary(tools.resolve_client_name, morning_client, name)

    @mcp.tool(structured_output=False)
    def get_client_details(name: str, name_resolved: bool = False) -> str:
        """Get a single client's full details by name.

        REQUIRES name_resolved=True: call resolve_client_name first with
        this name, then pass the EXACT name it returns here, together with
        name_resolved=True. Without it, this refuses immediately.
        """
        return _call_with_error_boundary(tools.get_client_details, morning_client, name, name_resolved)

    @mcp.tool(structured_output=False)
    def update_client(
        name: str,
        new_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        tax_id: Optional[str] = None,
        name_resolved: bool = False,
    ) -> str:
        """Update an existing client's fields. `name` identifies which client;
        at least one of new_name/email/phone/tax_id must be given.

        REQUIRES name_resolved=True: call resolve_client_name first with
        this name, then pass the EXACT name it returns here, together with
        name_resolved=True. Without it, this refuses immediately.
        """
        return _call_with_error_boundary(
            tools.update_client, morning_client, name, new_name, email, phone, tax_id, name_resolved
        )

    @mcp.tool(structured_output=False)
    def get_financial_summary(
        period: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> str:
        """Aggregate totals/counts for a period: "month", "quarter", "year", or "custom"."""
        return _call_with_error_boundary(
            tools.get_financial_summary, morning_client, period, from_date, to_date
        )

    @mcp.tool(structured_output=False)
    def download_invoice_pdf(internal_morning_id: str) -> str:
        """Return a PDF download link for an invoice."""
        return _call_with_error_boundary(tools.download_invoice_pdf, morning_client, internal_morning_id)

    return mcp


def main() -> None:
    """Entry point: `python3 -m denidin_mcp_morning.server`."""
    config = load_config(DEFAULT_CONFIG_PATH)
    # Every module's logger was already created (at import time, before config
    # existed) via get_logger(__name__)'s INFO default - retroactively raise/lower
    # them to the real configured level now that we have it (see
    # reconfigure_package_log_level's docstring for why this can't happen earlier).
    reconfigure_package_log_level(config.mcp_log_level)

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

        app = build_asgi_app(server, auth_token=config.mcp_auth_token, environment=config.environment)
        uvicorn.run(app, host=config.mcp_host, port=config.mcp_port, log_level=config.mcp_log_level.lower())
    else:
        # stdio/sse aren't network-exposed the same way; no HTTP-level
        # bearer check applies (and none was requested by this project's
        # single-consumer streamable-http use case).
        server.run(transport=config.mcp_transport)


if __name__ == "__main__":
    main()
