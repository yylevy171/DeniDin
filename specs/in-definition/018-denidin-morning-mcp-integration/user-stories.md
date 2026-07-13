# User Stories — Feature 018 (DeniDin ↔ Morning MCP Integration)

Given-When-Then user stories (METHODOLOGY §I). The **external entry point** for this feature
is a real **Green API webhook** dispatched through `@bot.router.message(...)` in
`apps/denidin-app/denidin.py` — the same production entry every WhatsApp message uses. Natural
-language intent parsing (deciding which invoicing tool to call) is done by the **OpenAI
model** via the Responses API, which reaches the Morning MCP server as a **remote MCP tool**
over the current ngrok tunnel. The Morning server and its 7 tools already exist (Feature 005);
this feature connects the WhatsApp bot to them.

Each story traces **External Input (webhook) → Router/Dispatch → WhatsAppHandler → AIHandler
(Responses API + MCP tool) → Morning sandbox → Response to user**, lists its **Router
Requirement**, and is covered by a **real-API E2E test** (no mocks) that fails before
implementation. All state-changing stories are **independently verified against the Morning
sandbox** via a direct `MorningClient` (the model's reply text is never trusted as proof).

Roles referenced: `admin`, `godfather`, `client`, `blocked` (denidin RBAC). Invoicing tools
are attached to the OpenAI call **only** for `godfather`/`admin`.

---

## US1 — Godfather creates an invoice via WhatsApp
**Given** the Morning MCP server is running and reachable (its current ngrok URL is published
to the shared status file) and the godfather's WhatsApp number is configured
**When** the godfather sends a text message "צור חשבונית ל-Tech Corp על 50 ₪ עבור ייעוץ" and
Green API delivers the `textMessage` webhook
**Then** `@bot.router.message` dispatches it → `WhatsAppHandler` → `AIHandler.get_response`
makes a Responses API call **with the Morning MCP server registered as a remote tool** → the
model invokes `create_invoice` → a real document is created in the Morning sandbox → the bot
replies in Hebrew with the invoice confirmation.

Acceptance criteria:
- The reply is generated via `client.responses.create` (Responses API), not chat completions.
- The model output contains an `mcp_call` for `create_invoice` with no error.
- A matching document actually exists in the Morning sandbox (verified via `MorningClient`).
- The reply is Hebrew and human-readable.

**Router Requirement**: `@bot.router.message(type_message='textMessage')` must route to
`WhatsAppHandler` → `AIHandler`; the AIHandler must attach the Morning MCP tool for the
godfather role.

## US2 — Godfather queries and updates invoices via WhatsApp
**Given** the same setup and at least one existing sandbox invoice
**When** the godfather sends "הצג חשבוניות של Tech Corp", "פרטים על חשבונית <id>",
"סמן חשבונית <id> כשולמה", "בטל את חשבונית <id>", "מה ההכנסות שלי החודש?", or
"תן לי PDF של חשבונית <id>" (each as a separate `textMessage` webhook)
**When** the webhook is dispatched through the router into the Responses-API reply path
**Then** the model invokes the corresponding Morning tool (`list_invoices`,
`get_invoice_details`, `update_invoice_status`, `get_financial_summary`,
`download_invoice_pdf`) and the bot replies in Hebrew with the result.

Acceptance criteria:
- Each intent maps to the correct `mcp_call` with no error.
- "סמן כשולמה" produces a linked Receipt; "בטל" produces a linked Credit Invoice (type 330) —
  both independently verified in the sandbox.
- Read intents ("הצג"/"פרטים"/"הכנסות"/"PDF") return the real data in the reply.

**Router Requirement**: same `textMessage` route + Morning MCP tool attachment for godfather.

## US3 — Add a client via WhatsApp
**Given** the same setup
**When** the godfather sends "הוסף לקוח Tech Solutions עם ח.פ 308253681"
**Then** the model invokes `add_client`, a real client is created in the Morning sandbox, and
the bot confirms in Hebrew.

Acceptance criteria:
- `add_client` `mcp_call` succeeds; the client exists in the sandbox.
- An invalid Israeli tax id yields a friendly Hebrew error (no stack trace, no crash).
- A request missing the required name causes the AI to ask for it rather than calling the tool
  with bad input.

**Router Requirement**: same `textMessage` route + Morning MCP tool attachment for godfather.

## US4 — A client is denied invoicing tools (RBAC)
**Given** the same setup, but the sender is a **client** (not godfather/admin)
**When** the client sends "צור חשבונית ל-X על 100 ₪" and the `textMessage` webhook is dispatched
**Then** the AIHandler makes the reply call **without** attaching any Morning MCP tool → the
model cannot invoke invoicing tools → **no** document is created in the sandbox → the bot still
replies normally (e.g. explaining it can't do that / general answer).

Acceptance criteria:
- The Responses call for a client role carries no `mcp` tool.
- Nothing is created in the Morning sandbox (verified via `MorningClient`).
- The bot does not crash and returns a normal reply.

**Router Requirement**: same route; tool attachment is role-gated (godfather/admin only).

## US5 — Unrelated prompt makes no tool call (scope)
**Given** the godfather (who *does* have the tools attached)
**When** they send a message unrelated to invoicing (e.g. "כתוב לי הייקו על הסתיו")
**Then** the model answers normally with **no** `mcp_call` — the tools are available but the
runtime constitution's scoping guidance keeps them unused.

Acceptance criteria:
- `response.output` contains no `mcp_call` items.
- The bot replies normally.

**Router Requirement**: same route; correctness of the runtime-constitution tool-scoping.

## US6 — Morning server/tunnel down → graceful degrade
**Given** the Morning MCP server or its tunnel is unavailable, so the shared status file is
missing or stale
**When** the godfather sends an invoicing prompt
**Then** the AIHandler's locator returns no URL → the reply call is made **without** MCP tools
→ the bot replies normally (e.g. that invoicing is temporarily unavailable) and **does not
crash**; a WARNING is logged.

Acceptance criteria:
- No `mcp` tool is attached when the status file is absent/stale.
- The bot returns a normal reply; no unhandled exception; nothing created in the sandbox.

**Router Requirement**: same route; tool attachment additionally gated on locator availability.

---

## Cross-cutting
- **Entry point / dispatch**: every story begins at a real Green API webhook JSON dispatched
  through `@bot.router.message` (CONSTITUTION §V) — never a direct method call into internals.
- **Confirmation policy (runtime-constitution-driven)**: whether the AI confirms before a
  state-changing action is decided by the runtime constitution prompt, carried across WhatsApp
  turns by the existing session memory — no dedicated code path (covered by a multi-turn
  scenario test).
- **Multi-message scenarios**: full lifecycle (add client → create → list → cancel),
  conversational slot-filling (create with missing details → AI asks → user supplies →
  create), and confirm-before-act — each a single E2E test spanning several WhatsApp turns.
- **Independent verification**: every state-changing story asserts the real effect in the
  Morning **sandbox** via a direct `MorningClient`, not the model's textual claim.
- Each story is verified by a **real-API E2E test** (`@pytest.mark.expensive`, no mocks) that
  fails before implementation, per METHODOLOGY §VI and CONSTITUTION §V.
