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

... (truncated for brevity; full content preserved in original file)

```
