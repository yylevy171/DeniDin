```markdown
# user-stories.md — Given/When/Then user stories (METHODOLOGY §I requirement)

Each user story below follows Given-When-Then format and includes acceptance criteria and router/dispatcher requirements.

1) Invoice Creation
Given a user sends a natural-language request via MCP (WhatsApp or desktop) to create an invoice
When the NLU extracts a `create_invoice` intent with `client_name`, `amount`, and `description`
Then the MCP server must call the `create_invoice` tool with validated schema and return a human-readable confirmation including invoice number, amount, status and PDF link.

Acceptance criteria:
- Tool input validated against `contracts/create_invoice.json`.
- If multiple clients match `client_name`, respond with a selection prompt listing candidates with IDs.
- On success, respond in Hebrew with invoice number and PDF link.

Router Requirement: `@bot.router.message(intent='create_invoice')` must route to `denidin_mcp_morning.tools.create_invoice`.

2) Invoice Query (List)
Given a user requests invoices for a date range or 'this month' via MCP
When NLU maps the request to `list_invoices` with optional `status`, `from_date`, `to_date`
Then MCP server must call `list_invoices` tool, format results into a readable list (max 10 items, paginated) and include totals.

Acceptance criteria:
- Parameters validated against `contracts/list_invoices.json`.
- Response includes at most 10 items and a continuation token if more results exist.

Router Requirement: `@bot.router.message(intent='list_invoices')` → `denidin_mcp_morning.tools.list_invoices`.

3) Payment Tracking / Status
Given a user asks "Which invoices are still unpaid?" or asks for a specific invoice status
When the request maps to `list_invoices` (status=unpaid) or `get_invoice_details` (invoice_id provided)
Then the MCP server returns invoice statuses and summary counts; for `get_invoice_details`, return detailed payment records.

Acceptance criteria:
- `get_invoice_details` requires `invoice_id` and returns `status`, `payments`, `issue_date`, `due_date`.
- `list_invoices` returns unpaid invoice list and totals.

Router Requirement: map payments/status queries to `list_invoices` or `get_invoice_details` as appropriate.

4) Client Management (Add Client)
Given a user requests "Add a new client named X" with optional fields (email, phone, tax_id)
When NLU maps to `add_client` intent and validated payload
Then MCP server calls `add_client` tool and returns the created client ID and summary.

Acceptance criteria:
- Input validated against `contracts/add_client.json`.
- If required fields missing, prompt user for them.

Router Requirement: `@bot.router.message(intent='add_client')` → `denidin_mcp_morning.tools.add_client`.

5) Financial Reports
Given a user asks for a period summary (month/quarter/year/custom)
When NLU maps to `get_financial_summary` with `period` and optional `from_date`/`to_date`
Then MCP server calls the summary tool, aggregates results if necessary, and returns totals and counts in Hebrew.

Acceptance criteria:
- `period` validated per `contracts/get_financial_summary.json`.
- Response contains total_invoiced, total_paid, total_unpaid, invoice_count.

Router Requirement: `@bot.router.message(intent='get_financial_summary')` → `denidin_mcp_morning.tools.get_financial_summary`.

6) Document Retrieval (Download PDF)
Given a user asks for the PDF of invoice #ID
When NLU extracts `invoice_id` and maps to `download_invoice_pdf`
Then MCP server returns a pre-signed URL or Base64 PDF (short responses should be a link) and offer to send via WhatsApp.

Acceptance criteria:
- `download_invoice_pdf` returns `pdf_url` or `file_base64` and valid URL expires per provider.
- If user requests sending via WhatsApp, call `send_invoice` with the invoice_id and phone.

Router Requirement: `@bot.router.message(intent='download_invoice_pdf')` → `denidin_mcp_morning.tools.download_invoice_pdf`.

7) Status Updates (Ask if paid)
Given a user asks "Did invoice #123 get paid?"
When NLU extracts `invoice_id` and maps to `get_invoice_details`
Then MCP server returns status and payment details, and if unpaid, suggests actions (send reminder, mark paid) with quick action buttons.

Acceptance criteria:
- Response must include `status` and `payments` (if any).
- Provide suggested quick actions when unpaid.

Router Requirement: `@bot.router.message(intent='get_invoice_status')` → `denidin_mcp_morning.tools.get_invoice_details`.

8) Bulk Operations (Mark multiple invoices paid)
Given a user requests a bulk operation (e.g., mark November invoices as paid)
When NLU maps to `update_invoice_status` with filter or list of invoice IDs
Then MCP server confirms operation with the user (listing affected invoices) before applying; upon confirmation, perform updates and return a summary of success/failure counts.

Acceptance criteria:
- Confirmation step required for destructive/bulk ops.
- Partial failures reported with reasons (e.g., invoice not found, API error).

Router Requirement: Bulk ops route to `denidin_mcp_morning.tools.update_invoice_status` with explicit confirmation flow in `server.py`.

---
Notes:
- All user stories must be accompanied by unit and integration tests per `METHODOLOGY.md` §VI (TDD). Each story must list the tests that will be written (happy path + edge cases).
- All responses should be in Hebrew by default (unless user preference indicates otherwise).

``` 
