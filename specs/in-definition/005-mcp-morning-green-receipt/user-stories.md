# User Stories — Feature 005 (MCP → Morning, Invoice Management)

Given-When-Then user stories (METHODOLOGY §I). The **external entry point** for this app is
an **MCP tool call** (the server registers each tool with `@mcp.tool()` and serves it over
streamable-HTTP). This replaces the WhatsApp `@bot.router.message` router concept, which
belongs to `denidin-app`, not here. Natural-language intent parsing is the MCP **client's**
job (e.g. the OpenAI model); these stories begin at the validated tool call.

Each story lists its acceptance criteria and its **MCP Tool Requirement** (the tool that
must be registered and dispatchable). Per METHODOLOGY §VI, each story is covered by a
**real Morning-sandbox integration test** (no mocks) that fails before implementation.

---

## US1 — Invoice Creation
**Given** an MCP client calls `create_invoice` with `client_name`, `amount`, `description`
**When** the server validates the input against `contracts/create_invoice.json` and maps it
onto a Morning document payload
**Then** it calls `MorningClient.create_invoice` (`POST /documents`) and returns a
human-readable (Hebrew) confirmation with the invoice number, amount, status, and PDF link.

Acceptance criteria:
- Input validated against `contracts/create_invoice.json` (and the Pydantic model).
- On success, respond in Hebrew with the Morning `documentId` and a PDF link.
- Friendly error if the amount is invalid or the client can't be resolved.

**MCP Tool Requirement**: `@mcp.tool() create_invoice` registered and dispatchable over
streamable-HTTP → `denidin_mcp_morning.tools.create_invoice`.

## US2 — Invoice Query / List
**Given** a client calls `list_invoices` with optional `status`/`from_date`/`to_date`/`client_name`
**When** the server validates and calls `MorningClient.list_invoices` (`POST /documents/search`)
**Then** it returns a readable list (≤10 items, continuation token if more) with totals.

Acceptance criteria:
- Params validated against `contracts/list_invoices.json`.
- At most 10 items per response; continuation token when more results exist.

**MCP Tool Requirement**: `@mcp.tool() list_invoices` → `tools.list_invoices`.

## US3 — Payment Tracking / Status
**Given** a client calls `get_invoice_details` (with `invoice_id`) or `list_invoices` (status=unpaid)
**When** the server validates and calls the corresponding Morning endpoint
**Then** it returns status + payment records for one invoice, or the unpaid list with totals.

Acceptance criteria:
- `get_invoice_details` requires `invoice_id`; returns `status`, `payments`, `issue_date`, `due_date`.
- `list_invoices` (unpaid) returns the list and totals.

**MCP Tool Requirement**: `@mcp.tool() get_invoice_details` → `tools.get_invoice_details`
(and `list_invoices` for the aggregate view).

## US4 — Client Management (Add Client)
**Given** a client calls `add_client` with `name` (+ optional `email`/`phone`/`tax_id`/`address`)
**When** the server validates against `contracts/add_client.json`
**Then** it calls `MorningClient.add_client` (`POST /clients`) and returns the created
client id + summary.

Acceptance criteria:
- `name` required; missing required fields → friendly prompt for them.

**MCP Tool Requirement**: `@mcp.tool() add_client` → `tools.add_client`.

## US5 — Financial Reports
**Given** a client calls `get_financial_summary` with `period` (+ optional dates)
**When** the server validates against `contracts/get_financial_summary.json`
**Then** it aggregates via `POST /documents/search` and returns totals/counts in Hebrew.

Acceptance criteria:
- Response includes `total_invoiced`, `total_paid`, `total_unpaid`, `invoice_count`.

**MCP Tool Requirement**: `@mcp.tool() get_financial_summary` → `tools.get_financial_summary`.

## US6 — Update Invoice Status
**Given** a client calls `update_invoice_status` with `invoice_id` + `status` (+ optional `payment_date`)
**When** the server validates against `contracts/update_invoice_status.json`
**Then** it updates the document (`PUT /documents/{id}`) and returns the new status.

Acceptance criteria:
- `invoice_id` + `status` required; invalid/nonexistent id → friendly error.

**MCP Tool Requirement**: `@mcp.tool() update_invoice_status` → `tools.update_invoice_status`.

## US7 — Send Invoice (Morning-native delivery)
**Given** a client calls `send_invoice` with `invoice_id` (+ optional `phone_number`/`message`)
**When** the server validates against `contracts/send_invoice.json`
**Then** it triggers **Morning's own** send (`POST /documents/{id}/send`, email/SMS) and
returns a delivery confirmation. It does **not** call `denidin-app`.

Acceptance criteria:
- `invoice_id` required; if the client has no contact and none is supplied → friendly error
  asking for a phone/email.
- No import of or dependency on `denidin-app`.
- (Future, architecture TBD: delivering over WhatsApp from denidin-app's number — spec §Future Work.)

**MCP Tool Requirement**: `@mcp.tool() send_invoice` → `tools.send_invoice`.

## US8 — Download Invoice PDF
**Given** a client calls `download_invoice_pdf` with `invoice_id`
**When** the server validates against `contracts/download_invoice_pdf.json`
**Then** it returns a PDF download URL (or Base64) obtained from Morning.

Acceptance criteria:
- Returns `pdf_url` or `file_base64`; nonexistent id → friendly error.

**MCP Tool Requirement**: `@mcp.tool() download_invoice_pdf` → `tools.download_invoice_pdf`.

---

## Cross-cutting
- **Entry point / dispatch story**: Given the FastMCP server is running with
  `feature_flags.enable_mcp_server=true`, When an MCP client connects over streamable-HTTP,
  Then all 8 tools are discoverable and invocable (covered by the E2E dispatch test,
  `tests/integration/test_mcp_server_e2e.py`).
- Responses are Hebrew by default (₪, DD/MM/YYYY, Hebrew status terms).
- Each story is verified by a **real Morning-sandbox integration test** (no mocks) that
  fails before implementation, per METHODOLOGY §VI and CONSTITUTION §V.
