# Quickstart: Client-name resolution architecture fix

Given-When-Then scenarios (serving as this scoped piece's user-stories equivalent — see plan.md's
note on why a separate `user-stories.md` file wasn't used). Each traces a real external entry point
(a WhatsApp message from a godfather/admin) through to the user-facing response, per CONSTITUTION §V.

## US1: Exact name given up front — resolves silently, no extra turn

**Given** a godfather sends "תפיק חשבונית עבור כרמלי דודי על סך 100 ש״ח עבור ייעוץ" and "כרמלי דודי" is
already the real, exact stored name in Morning
**When** the model processes this message
**Then** it calls `resolve_client_name(name="כרמלי דודי")` first, gets back the exact-match confirmation,
then calls `create_invoice(client_name="כרמלי דודי", ..., name_resolved=true)` — the resulting
approval prompt shows the correct client, and approving it creates one real invoice.
**Router/Dispatcher Requirement**: no new webhook/router — this exercises the existing `textMessage` →
`_process_conversational_message` → `AIHandler` → Morning MCP tool-call path unchanged.

## US2: Non-exact name — one clarifying question, then proceeds

**Given** a godfather sends "תפיק חשבונית עבור כרמלי דוד על סך 100 ש״ח" and the real stored client is
"כרמלי דודי" (one letter short, per bugfix-039's T2 regression case)
**When** the model processes this message
**Then** it calls `resolve_client_name(name="כרמלי דוד")` first, gets back "מצאתי לקוח בשם כרמלי דודי —
האם לזה התכוונת?", relays that question to the user (no tool call attempted yet against
`create_invoice`), and — once the user replies "כן" — calls `create_invoice(client_name="כרמלי דודי",
..., name_resolved=true)`, which resolves on the first try (exact match) and proceeds straight to the
approval prompt.

## US3: Client genuinely doesn't exist — offered to create it, never left hanging

**Given** a godfather asks for an invoice for a client name that matches nothing in Morning
**When** the model processes this message
**Then** `resolve_client_name` returns "not found," the model asks for the missing client's phone and
email, calls `add_client` (its own separate approval turn), and once approved, retries the original
request with `name_resolved=true` — never silently gives up, never fabricates success.

## US4: A tool called with `name_resolved` omitted (or false) — hard, immediate refusal, zero Morning calls

**Given** any of the six migrated tools is called with `name_resolved` not `true` (a defect scenario —
this should never happen in normal conversation once the constitution rewrite lands, but must fail
safely if it does, e.g. a prompt regression)
**When** the tool is invoked
**Then** it returns `format_name_not_resolved()`'s message immediately, attempting zero calls against
Morning's real API — verified via a unit test asserting the fake client's `search_clients`/
`get_client`/etc. call list stays empty.

## US5: Indirect reference by client name — receipt/cancellation still resolves the client first

**Given** a godfather asks "תוציא קבלה על החשבונית של דנה כהן" (a receipt against Dana Cohen's invoice —
`create_receipt` itself takes `original_invoice_id`, not a client name)
**When** the model processes this message
**Then** it resolves the client first (`resolve_client_name`), then finds the relevant invoice
(`list_invoices(client_name=<resolved exact name>, name_resolved=true, ...)`), extracts the invoice id,
and only then calls `create_receipt(original_invoice_id=..., ...)` — the user is never asked for a raw
invoice id directly.

## US6: Approval gating is unaffected by resolution

**Given** any request that both needs client-name resolution AND targets a mutating tool
**When** the model completes resolution and calls the mutating tool with `name_resolved=true`
**Then** the existing approval gate (📋 לאישור / כן-לא) still fires exactly as it does today —
resolution is a separate, unapproved, read-only step that happens *before* the approval-gated call,
never a substitute for it, and `resolve_client_name` itself never generates a pending-approval prompt.

## Manual verification steps (once implemented)

1. `cd apps/morning-mcp-app && venv/bin/python3 -m pytest tests/unit/ -v` — full green, no regressions
   outside the deliberately relocated/rewritten tests.
2. `cd apps/morning-mcp-app && venv/bin/python3 -m pytest tests/integration/ -v` — real sandbox, same
   expectation.
3. A handful of `denidin-app` billed tests re-run against the real stack (real OpenAI + real MCP + real
   Morning sandbox) covering US1/US2/US3/US5 above, to confirm the new conversational shape actually
   works end-to-end — not just that individual tool calls behave correctly in isolation.
4. Manually re-read the rewritten `runtime_constitution.md` section against a real live turn before
   treating it as final (CONSTITUTION's "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS" rule).
