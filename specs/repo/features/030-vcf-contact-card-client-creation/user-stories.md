# User Stories — Feature 030 (vCard Contact Card → Client Creation)

Given-When-Then user stories (METHODOLOGY §I). The **external entry point** for this feature is
the same real **Green API webhook** dispatched through `@bot.router.message(...)` in
`apps/denidin-app/denidin.py` that every WhatsApp message already uses — specifically a
notification with `typeMessage: "contactMessage"`, which today has **no dedicated router** and
falls through to the catch-all handler (`denidin.py:292-450`), doing nothing useful with it.

Once routed, this feature does **not** invent a new confirmation or approval mechanism: parsed
vCard fields are handed to `AIHandler` the same way any other message content is, so the model
proposes an `add_client` call exactly as it would from typed text. `add_client` is already in
`AIHandler.APPROVAL_REQUIRED_MCP_TOOLS` (Feature 026) — the existing
`PendingApprovalManager`/`mcp_approval_request` flow and the existing "ask for missing
name/email/phone before proceeding" behavior (REQ-CLIENT-012, Feature 026 US3) are inherited
automatically. This feature's own scope is: routing the new message type, parsing the vCard into
name/phone/email, and presenting it to the model/user in a way that flows into that existing
pipeline.

Each story traces **External Input (webhook) → Router/Dispatch → WhatsAppHandler → AIHandler
(+ existing Feature 026 approval gate) → Morning sandbox → Response to user**, lists its **Router
Requirement**, and is covered by a real-API E2E test (no mocks, per CONSTITUTION §I/§V).

Roles referenced: `admin`, `godfather`, `client`, `blocked` (denidin RBAC) — inherited unchanged
from the existing Morning MCP tool-attachment gating (Feature 018); this feature introduces no new
RBAC logic.

---

## Fixture Note

`apps/denidin-app/tests/fixtures/contacts/00005372-גיל ברטל .vcf` is a real WhatsApp-exported
vCard 3.0 (name + phone via `TEL;type=CELL;type=VOICE;waid=...`, **no `EMAIL` field**). US1's
"complete card" scenario therefore needs its own synthetic fixture with an email added (or a
second real card that happens to have one); the real fixture itself is the natural one to drive
US2 (missing-email path), since that's exactly the shape it has.

## Phone Normalization Note

No new phone-normalization code is needed. `_normalize_israeli_phone`
(`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py:886`) already runs inside `add_client`/
`update_client` (Feature 026, REQ-CLIENT-016) and already handles every shape a vCard `TEL` field
can hand it — verified directly against the real fixture's value:
- `TEL` value `"+972 50-795-1824"` → `"050-7951824"`
- `waid` param value `"972507951824"` (no `+`, no spaces) → `"050-7951824"`

Both resolve to the same normalized result (strips all non-digits, replaces a leading `972` with
`0`, then formats as `0XX-XXXXXXX`/`0X-XXXXXXX`). This feature can extract **either** the `TEL`
value or the `waid` parameter from the vCard and pass it straight through as `add_client`'s
`phone` argument unmodified — normalization, validation, and the "implausible number" friendly
error are all inherited as-is.

---

## US1 — Godfather shares a complete single contact card (Priority: P1)

**Given** the Morning MCP server is running and reachable, and no client named "Tech Solutions"
exists yet in the Morning sandbox
**When** the godfather shares a WhatsApp contact card for "Tech Solutions" (phone
`050-1234567`, email `tech@example.com` both present in the vCard) and Green API delivers a
`contactMessage` webhook
**Then** the new router dispatches it → `WhatsAppHandler` parses the vCard text into
name/phone/email → `AIHandler` receives this as the turn's content → the model proposes calling
`add_client` with those fields → the existing Feature 026 approval gate intercepts it (no
`add_client` executes yet) → the bot asks for explicit confirmation, naming the parsed
name/phone/email
**When** the godfather replies with an affirmative ("כן")
**Then** the model invokes `add_client` for real (existing Feature 026 mechanism, unchanged) → a
real client is created in the Morning sandbox → the bot confirms in Hebrew.

**Independent Test**: Fully testable standalone — seed no matching client, send a real
`contactMessage` webhook payload, confirm, then verify via a direct
`MorningClient.search_clients(...)` call that the client now exists with the phone/email
persisted.

Acceptance criteria:
- The vCard's name/phone/email are correctly extracted and match what's shown in the confirmation
  prompt (no truncation, no field swap).
- The first turn produces **no** `add_client` `mcp_call` — only a confirmation question (inherits
  Feature 026's approval gate; no new approval code is written by this feature).
- Once approved, the client is verified to exist in the Morning sandbox by direct API call, not
  just by trusting the reply text.
- The confirmation reply never contains the client's internal `client_id` (inherits REQ-CLIENT-018).

**Router Requirement**: a new `@bot.router.message(type_message='contactMessage')` handler in
`denidin.py` must route to a vCard-parsing step and then into the existing `WhatsAppHandler` →
`AIHandler` pipeline — mirroring the existing per-type dispatcher pattern already used for
`imageMessage`/`documentMessage`/etc.

---

## US2 — Contact card is missing a mandatory field (Priority: P1)

**Given** the same setup
**When** the godfather shares a contact card for "Dana Cohen" that has a phone number but no email
address (a common real vCard shape)
**Then** the router/parser hands the model name+phone only → the model recognizes email is
missing (inherits Feature 026 REQ-CLIENT-012 behavior — `add_client` requires name/email/phone) →
the bot asks the godfather for the missing email **before** offering any creation confirmation —
no confirmation prompt, no tool call yet.

**Independent Test**: Fully testable standalone — send a `contactMessage` webhook with a vCard
missing an email field, assert the reply asks specifically for an email and that no
`add_client`/approval state was created.

Acceptance criteria:
- No `add_client` `mcp_call` and no pending-approval state is created while a mandatory field is
  missing.
- The bot's follow-up question names the specific missing field(s), not a generic error.
- Once the godfather supplies the missing email in a follow-up message, the flow proceeds exactly
  as US1 (confirmation → approval → creation).

**Router Requirement**: same new `contactMessage` route as US1.

---

## US3 — Multi-contact card share (Priority: P2)

**Given** the same setup
**When** the godfather shares a WhatsApp message containing **more than one** contact at once
(Green API delivers this as a **distinct notification type**, `typeMessage:
"contactsArrayMessage"` — confirmed via Green API's official docs, 2026-07-30 — not multiple
vCards inside a `contactMessage`)
**Then** the new `contactsArrayMessage` router replies with a friendly message asking the
godfather to share contacts one at a time → **no vCard is parsed, no AI/tool call is made at
all, no approval state created** — this can be answered directly at the router level, without
ever calling `AIHandler`.

**Independent Test**: Fully testable standalone — send a real `contactsArrayMessage` webhook
payload (per the confirmed shape: `messageData.messageData.contacts`, an array of
`{displayName, vcard}`), assert the friendly "one at a time" reply and that no
`add_client`/approval state was created and no OpenAI call was made.

Acceptance criteria:
- Detection is purely type-based (`typeMessage == "contactsArrayMessage"`) — no vCard content is
  ever inspected for this story, regardless of how many contacts the array actually contains.
- The friendly reply is in the project's standard user-facing error style (no stack trace, no
  partial processing of "just the first contact" silently).
- Explicitly out of scope for v1: batch-creating all contacts, or looping confirmation per
  contact — deferred to a future feature if ever needed.

**Router Requirement**: a new `@bot.router.message(type_message='contactsArrayMessage')` handler
in `denidin.py`, separate from the `contactMessage` route (US1/US2) — replies directly, no
`AIHandler` involvement needed.

---

## Out of Scope for This Feature

- **A dedicated RBAC/non-godfather test** — not needed as a new story. Tool attachment stays
  role-gated exactly as it already is (Feature 018: no Morning MCP tool for client/blocked roles),
  and this feature adds no new RBAC surface for a `contactMessage` webhook to bypass — it flows
  into the same `AIHandler` gating every other message type already goes through.

- **Multi-contact card handling beyond the "one at a time" friendly message** (US3) — no
  batch-creation, no per-contact confirmation loop.
- **Any change to `add_client`'s validation, approval gate, or schema** — this feature is a new
  *source* of `add_client` calls (a parsed vCard instead of typed text), not a change to how
  `add_client` itself behaves. All of Feature 026's validation/approval/missing-field behavior is
  inherited unchanged.
- **Malformed/unparseable vCard text** beyond the missing-mandatory-field case (US2) — falls back
  to the project's standard friendly-error style; no new bespoke vCard-repair logic.
- **Any Morning-sourced-event ledger capture** — unrelated to Feature 025; not touched here.
