# User Stories — Feature 026 (Client Management)

Given-When-Then user stories (METHODOLOGY §I). The **external entry point** for this feature is
the same real **Green API webhook** dispatched through `@bot.router.message(...)` in
`apps/denidin-app/denidin.py` that every WhatsApp message already uses. Natural-language intent
parsing (deciding which client-management tool to call) is done by the **OpenAI model** via the
Responses API, reaching the Morning MCP server as a **remote MCP tool** over the existing ngrok
tunnel (Feature 018). No new router, no new RBAC code path — these tools live on the same
already-integrated, already-gated Morning MCP server as the invoicing tools.

Each story traces **External Input (webhook) → Router/Dispatch → WhatsAppHandler → AIHandler
(Responses API + MCP tool) → Morning sandbox → Response to user**, lists its **Router
Requirement**, and is covered by a **real-API E2E test** (no mocks, per CONSTITUTION §I/§V) that
fails before implementation. All state-changing stories are independently verified against the
Morning sandbox via a direct `MorningClient` call (the model's reply text is never trusted as
proof).

Roles referenced: `admin`, `godfather`, `client`, `blocked` (denidin RBAC). Client-management
tools are attached to the OpenAI call **only** for `godfather`/`admin` — identical gating to the
existing invoicing tools, inherited automatically (Feature 018).

**Approval gate (per Clarifications, 2026-07-29)**: `add_client` and `update_client` now require
an explicit approval turn before executing, mirroring Feature 022's confirmation flow — this
**reverses Feature 022's exemption of `add_client`**. Only `list_clients`/`get_client_details`
(read-only) stay immediate. **Delete is out of scope for this feature entirely** — no
`delete_client` story exists here.

**Field scope (per Clarifications, round 2, 2026-07-29)**: exactly four client fields are in
scope — `name`, `email`, `phone`, `tax_id`. `name`/`email`/`phone` are **mandatory at creation**
(the AI must ask for any that are missing before proceeding); `tax_id` stays optional at
creation. `address` and every richer field the real Green Invoice API supports (`mobile`, `city`,
`zip`, `country`, `contactPerson`, bank details, `labels`, `paymentTerms`, `category`) are
explicitly out of scope. No field is mandatory for `update_client` beyond providing at least one
field to change.

---

## US1 — Godfather lists their clients via WhatsApp (Priority: P1)

**Given** the Morning MCP server is running and reachable (current ngrok URL published to the
shared status file) and at least one client exists in the Morning sandbox
**When** the godfather sends "מי הלקוחות שלי?" ("who are my clients?") and Green API delivers the
`textMessage` webhook
**Then** `@bot.router.message` dispatches it → `WhatsAppHandler` → `AIHandler.get_response` makes
a Responses API call with the Morning MCP server registered as a remote tool → the model invokes
`list_clients` → the bot replies **immediately, with no approval wait** (read-only) in Hebrew
with a human-readable list of client names (and identifying detail, e.g. tax ID/phone).

**Independent Test**: Can be fully tested standalone by seeding one sandbox client and asserting
the reply text contains its name — delivers value (visibility into existing clients) without any
other story implemented.

Acceptance criteria:
- The reply is generated via `client.responses.create` (Responses API).
- The model output contains an `mcp_call` for `list_clients` with no error, and no pending
  approval state is created (read-only action).
- The returned client names match what actually exists in the Morning sandbox (verified via a
  direct `MorningClient` call, not the model's reply text alone).
- The reply text never contains any client's internal `client_id` (UUID) — REQ-CLIENT-018.

**Router Requirement**: `@bot.router.message(type_message='textMessage')` must route to
`WhatsAppHandler` → `AIHandler`; the AIHandler must attach the Morning MCP tool for the godfather
role (existing Feature 018 behavior, unchanged).

---

## US2 — Godfather views a specific client's details (Priority: P1)

**Given** the same setup, with a known sandbox client "Tech Solutions" (tax ID 308253681)
**When** the godfather sends "פרטים על הלקוח Tech Solutions" ("details for client Tech Solutions")
**Then** the model invokes `get_client_details` with a **name-only** lookup (tax-ID lookup was
considered and dropped — analysis 2026-07-29, spec.md REQ-CLIENT-002) → the bot replies
**immediately, with no approval wait** (read-only) in Hebrew with the client's full record (name,
email, phone, tax_id — the four in-scope fields, **never including the internal `client_id`**,
REQ-CLIENT-018).

**Independent Test**: Can be fully tested standalone against a seeded sandbox client and asserting
the reply contains its known tax ID — delivers value independent of list/add/update.

Acceptance criteria:
- `get_client_details` `mcp_call` succeeds with no error; no pending approval state is created.
- The returned fields match the real sandbox record (verified via `MorningClient`).
- A name that matches zero clients yields a friendly "no client found" reply — no stack trace, no
  tool error surfaced, no crash.
- A name that matches more than one client causes the bot to list the candidates and ask the user
  to disambiguate, rather than acting on the first match (REQ-CLIENT-003).
- The reply text never contains the client's internal `client_id` (UUID) — only
  name/email/phone/tax_id (REQ-CLIENT-018).

**Router Requirement**: same `textMessage` route + Morning MCP tool attachment for godfather.

---

## US3 — Godfather adds a client, now with mandatory fields and required approval (Priority: P2)

**Given** the same setup, with no existing client named "Tech Solutions"
**When** the godfather sends "הוסף לקוח Tech Solutions, טלפון 050-1234567, מייל
tech@example.com" (name + phone + email all present)
**Then** the system validates the email format and normalizes the phone to Israeli local dashed
format (`0XX-XXXXXXX`) — **no proactive duplicate-name/tax-ID check is performed** ("try and
fail" — analysis 2026-07-29, spec.md REQ-CLIENT-007) → the bot asks for explicit confirmation
before creating anything (e.g. "ליצור לקוח חדש: Tech Solutions, טלפון 050-1234567, מייל
tech@example.com? (כן/לא)") → **no `add_client` call is made yet**
**When** the godfather replies with an affirmative ("כן"/"אישור"/"בסדר"/"go ahead")
**Then** the model invokes `add_client` with the normalized phone → a real client is created in
the Morning sandbox → the bot confirms in Hebrew.

**Independent Test**: Can be fully tested standalone as a two-turn conversation: request → confirm
→ verify via a direct `MorningClient.search_clients(...)` call (or `get_client_details` tool
call) that the client now exists in the sandbox **with the phone number actually persisted and
returned**, not just that the creation request was accepted.

Acceptance criteria:
- The first turn produces **no** `add_client` `mcp_call` — only a confirmation question.
- A decline reply ("לא"/anything non-affirmative) results in **no** client created in the sandbox
  and a clear cancellation acknowledgement — this **reverses Feature 022's prior no-wait behavior
  for `add_client`**, so any existing test asserting immediate creation must be updated
  (tests are immutable only until a re-approved change like this one — CONSTITUTION §VIII).
- Once approved, `add_client` `mcp_call` succeeds with no error and the client is verified to
  exist in the Morning sandbox (not just the reply text). **A dedicated real-sandbox test MUST
  create a client with a phone number and then separately read it back (`get_client_details`) to
  confirm the normalized phone is actually persisted and returned by Morning**
  (REQ-CLIENT-014/017) — empirically correcting the prior "phone is silently ignored" assumption.
- **Email format is validated before the confirmation prompt** (REQ-CLIENT-015): a malformed
  email (e.g. "not-an-email") triggers a friendly Hebrew error asking for a valid email —
  no confirmation prompt, no tool call. Mirrors Morning's own documented `1102`/`1120` errors.
- **Phone is normalized to Israeli local dashed format** (`0XX-XXXXXXX`) regardless of how the
  user typed it (REQ-CLIENT-016) — e.g. "+972501234567", "0501234567", and "050-123-4567" all
  normalize to the same "050-1234567" before being sent to Morning and before being shown back to
  the user in the confirmation prompt. Input that doesn't resolve to a plausible Israeli number
  (e.g. too few digits, non-Israeli country code) triggers a friendly error asking for a valid
  phone number — before the confirmation prompt.
- An invalid Israeli tax id yields a friendly Hebrew error at the confirmation stage (no crash).
  `tax_id` itself is optional — a request with no tax_id at all proceeds normally once
  name/email/phone are present and valid.
- **A request missing `name`, `email`, or `phone` (any of the three) causes the AI to ask for the
  missing field(s) before even reaching the confirmation step** (REQ-CLIENT-012) — e.g. "הוסף
  לקוח Tech Solutions" alone (no phone, no email) triggers a follow-up question asking for both,
  not a confirmation prompt and not a tool call.
- `address` is never asked for and never sent — it is out of scope (REQ-CLIENT-013).
- **If Morning's real API rejects the creation as a duplicate (or any other reason), the
  rejection is surfaced to the user clearly** (via the existing friendly-error mapping) — never
  silently swallowed or misreported as a successful creation (REQ-CLIENT-007).
- **The confirmation reply never contains the client's internal `client_id`** (UUID) —
  REQ-CLIENT-018, correcting the existing Feature-005 `add_client` message which currently
  includes `"(מזהה: {client_id})"`.

**Router Requirement**: same `textMessage` route + Morning MCP tool attachment for godfather.

---

## US4 — Godfather updates a client's details, with required approval (Priority: P2)

**Given** the same setup, with a known sandbox client whose phone number is outdated
**When** the godfather sends "עדכן את הטלפון של Tech Solutions ל-050-1234567"
**Then** the AIHandler resolves the client unambiguously (REQ-CLIENT-003/007) → the system
normalizes the new phone to Israeli local dashed format → the bot asks for explicit confirmation
before updating anything → **no `update_client` call is made yet**
**When** the godfather replies with an affirmative
**Then** the model invokes `update_client` with the resolved client identifier and the normalized
phone value → a real update is persisted in the Morning sandbox → the bot confirms in Hebrew.

**Independent Test**: Can be fully tested standalone as a two-turn conversation: seed a client,
request the update, confirm, verify via a direct `MorningClient.search_clients(...)` call (or
`get_client_details`) that the phone field actually changed **and reads back as the normalized
value** in the sandbox.

Acceptance criteria:
- The first turn produces **no** `update_client` `mcp_call` — only a confirmation question.
- A decline reply results in **no** change in the sandbox and a clear cancellation
  acknowledgement.
- Once approved, `update_client` `mcp_call` succeeds with no error; the change is verified
  directly against the Morning sandbox (not just the reply text), including reading the updated
  phone back to confirm the normalized value round-trips (REQ-CLIENT-017).
- An ambiguous or not-found client name triggers the same disambiguation/not-found behavior as
  US2 rather than confirming against the wrong record or a non-existent one.
- `tax_id` is updatable exactly like any other in-scope field (`name`, `email`, `phone`) — no
  special restriction (REQ-CLIENT-010). No field is individually mandatory for the update request
  itself — only that at least one of the four in-scope fields is being changed.
- `address` cannot be updated via this tool — it is out of scope (REQ-CLIENT-013); a request to
  change it should be declined with a friendly explanation, not silently ignored or errored.
- Updating `email` to a malformed value triggers the same format-validation error as US3
  (REQ-CLIENT-015), before the confirmation prompt.
- Updating `phone` to an implausible value (doesn't resolve to an Israeli number) triggers the
  same normalization/validation error as US3 (REQ-CLIENT-016), before the confirmation prompt.
- **The confirmation reply never contains the client's internal `client_id`** (UUID) —
  REQ-CLIENT-018.

**Router Requirement**: same `textMessage` route + Morning MCP tool attachment for godfather.

---

## US5 — A client-role or blocked-role user has no client-management capability (RBAC)

**Given** the same setup, but the sender is a **client** (not godfather/admin)
**When** the client sends "מי הלקוחות שלי?" and the `textMessage` webhook is dispatched
**Then** the AIHandler makes the reply call **without** attaching any Morning MCP tool → the
model cannot invoke `list_clients`/`get_client_details`/`add_client`/`update_client` → no data is
read or changed in the Morning sandbox → the bot replies normally (e.g. explaining it can't do
that / a general answer).

Acceptance criteria:
- The Responses call for a client/blocked role carries no `mcp` tool (existing Feature 018
  behavior — this feature adds no new RBAC surface).
- Nothing is read or changed in the Morning sandbox (verified via `MorningClient`).
- The bot does not crash and returns a normal reply.

**Router Requirement**: same route; tool attachment remains role-gated (godfather/admin only,
unchanged from Feature 018).

---

## Out of Scope for This Feature

- **Client deletion** — no `delete_client` tool, no story here. Would need its own future feature
  (delete semantics against the Green Invoice API are undecided — see spec.md REQ-CLIENT-009).
- **Invoice-creation client referencing** — `create_invoice` and friends keep accepting a
  free-text client name unchanged. Tracked separately as
  `specs/backlog/027-mandatory-client-reference-invoicing/`.
- **`address` and every richer client field** (`mobile`, `city`, `zip`, `country`,
  `contactPerson`, bank details, `labels`, `paymentTerms`, `category`/`subCategory`) — the real
  Green Invoice API supports all of these, but this feature deliberately stays to exactly four
  fields (`name`, `email`, `phone`, `tax_id`). See spec.md REQ-CLIENT-013.
