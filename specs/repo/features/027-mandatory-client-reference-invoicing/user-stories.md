# User Stories — Feature 027 (Mandatory Client Reference for Invoicing)

Given-When-Then user stories (METHODOLOGY §I). The **external entry point** for this feature is
the same real **Green API webhook** dispatched through `@bot.router.message(...)` in
`apps/denidin-app/denidin.py` that every WhatsApp message already uses. Natural-language intent
parsing (deciding which document-creation tool to call, and whether to call `add_client` first) is
done by the **OpenAI model** via the Responses API, reaching the Morning MCP server as a **remote
MCP tool** over the existing ngrok tunnel (Feature 018). No new router, no new RBAC code path, no
new MCP tool, no new approval-gate mechanism — every story below plays out entirely within the
existing per-tool approval gate (`AIHandler.APPROVAL_REQUIRED_MCP_TOOLS`, Feature 022/026).

Each story traces **External Input (webhook) → Router/Dispatch → WhatsAppHandler → AIHandler
(Responses API + MCP tool) → Morning sandbox → Response to user**, lists its **Router
Requirement**, and is covered by a **real-API E2E test** (no mocks, per CONSTITUTION §I/§V) that
fails before implementation. All state-changing stories are independently verified against the
Morning sandbox via a direct `MorningClient` call (the model's reply text is never trusted as
proof) — per REQ-INV-009/REQ-INV-013, specifically checking the created document's `client.id`
matches the real client's `client_id`, not just that a document was created.

Roles referenced: `admin`, `godfather`, `client`, `blocked` (denidin RBAC). Document-creation and
`add_client` tools are attached to the OpenAI call **only** for `godfather`/`admin` — unchanged
from Feature 018/022/026, inherited automatically.

**Two groups, six tools (per Clarifications, 2026-08-06, `/speckit.plan` scoping correction)** —
this feature covers 6 tools, not 5, split by how each one identifies its client:

- **Group A** (`create_invoice`, `create_transaction_account`, `create_combo_document`): take a
  free-text `client_name: str` and resolve it by search. US1-US4 below (written against
  `create_invoice` as the representative example, US4 covering the other two).
- **Group B** (`create_credit_note`, `create_receipt`, `close_transaction_account`): take no
  `client_name` at all — they take `original_invoice_id`, and derive their client from the
  original document they're linked to. US6 below covers all three.

**Persona names below ("Danny Cohen", "Ronit Levi", "Danny Katz") are narrative illustration
only** — for a human reading the Given-When-Then flow. Actual automated (pytest, real-sandbox)
tests MUST generate client names via this codebase's existing unique-marker mechanism
(`_unique_marker(label)` → `f"Test Client {marker}"`, already used by every
`apps/morning-mcp-app/tests/integration/*.py` file — see research.md Decision 8), never these
literal strings — the shared sandbox accumulates real data across every run, and a fixed name
would collide or reuse stale data.

---

## US1 — Document created for an existing, unambiguous client (Priority: P1) [Group A]

**Given** the Morning MCP server is running and reachable, and a client named "Danny Cohen"
already exists uniquely in the Morning sandbox (from a prior `add_client` or seeded directly via
`MorningClient`)
**When** the godfather sends "תוציא חשבונית לדני כהן על 500 שקל בעבור ייעוץ" ("create an invoice
for Danny Cohen for 500 NIS for consulting") and Green API delivers the `textMessage` webhook
**Then** `@bot.router.message` dispatches it → `WhatsAppHandler` → `AIHandler.get_response` makes
a Responses API call with the Morning MCP server registered as a remote tool → the model's
`create_invoice` call is flagged for approval (existing gate, unchanged) → the godfather approves
→ `create_invoice`'s implementation resolves "Danny Cohen" via `_resolve_client_by_name` to the
one real matching client, builds the `/documents` payload with
`"client": {"self": False, "id": "<Danny Cohen's real client_id>"}` (no `name` field) → the
document is created in the Morning sandbox attached to that real client → the bot confirms in
Hebrew exactly as it does today (REQ-INV-010, no reply-shape change).

**Independent Test**: Can be fully tested standalone by seeding one sandbox client, requesting an
invoice for it by name, approving, and asserting (via `MorningClient.get_invoice`) that the created
document's `client.id` equals the seeded client's real `client_id` — delivers value (real client
attachment, the whole point of this feature) without any other story implemented.

Acceptance criteria:
- The reply is generated via `client.responses.create` (Responses API); the model's `create_invoice`
  `mcp_call` fires the existing approval flow unchanged (no new pending-state logic).
- The document-creation payload sent to Morning contains `client.id`, and does **not** contain
  `client.name` (REQ-INV-002).
- Fetching the created document directly (`MorningClient.get_invoice`) shows `client.id` equal to
  the real, pre-existing client's `client_id` — not merely that some document was created
  (REQ-INV-009).
- The Hebrew confirmation reply to the user is unchanged in shape from today's behavior
  (REQ-INV-010) — this feature is invisible to the user on the happy path except for the
  now-correct underlying attachment.
- If "Danny Cohen" only resolves via a non-exact (fuzzy/substring) match — e.g. the real client is
  actually named "Danny Cohen Consulting" — the confirmation reply discloses the real matched name
  before/as part of the approval prompt (REQ-INV-011, `/speckit.clarify` 2026-08-06), mirroring
  `get_client_details`'s existing `is_exact_match=False` disclosure. An exact match discloses
  nothing extra (current behavior, unchanged).

**Router Requirement**: `@bot.router.message(type_message='textMessage')` must route to
`WhatsAppHandler` → `AIHandler`; the AIHandler must attach the Morning MCP tool for the godfather
role (existing Feature 018 behavior, unchanged).

---

## US2 — Document creation blocked on an unknown client, then created after inline client creation (Priority: P1) [Group A]

**Given** the same setup, but no client named "Ronit Levi" exists yet in the Morning sandbox
**When** the godfather sends "תוציא חשבונית לרונית לוי על 1000 שקל בעבור שירותי תכנות"
**Then** the model's `create_invoice` call is approved (existing gate) → `create_invoice`'s
implementation resolves "Ronit Levi" via `_resolve_client_by_name`, finds zero matches, creates
**no document**, and returns a friendly "client not found" message (REQ-INV-003) instead of a
document confirmation
**When** the model, informed by `config/runtime_constitution.md`'s guidance (REQ-INV-004), asks the
godfather for the missing client details ("אין לי לקוח בשם רונית לוי — מה הטלפון והמייל שלה כדי
שאוכל להוסיף אותה?") and the godfather replies with phone + email
**Then** the model calls `add_client` (its own existing, separate approval turn, Feature 026,
unchanged) → the godfather approves → a real client "Ronit Levi" is created in the Morning sandbox
**When** the model then retries the original request and calls `create_invoice` again for "Ronit
Levi" (its own existing, separate approval turn)
**Then** `create_invoice`'s implementation now resolves "Ronit Levi" to the just-created real
client and creates the document attached to its real `client_id`, exactly as in US1.

**Independent Test**: Can be fully tested standalone as a multi-turn conversation: request invoice
for a nonexistent client → assert no document was created and the reply is a not-found message →
provide client details → approve `add_client` → verify the client now exists via
`MorningClient.search_clients` → retry the invoice request → approve `create_invoice` → verify
(via `MorningClient.get_invoice`) the document is attached to the newly-created client's real
`client_id`.

Acceptance criteria:
- The first `create_invoice` attempt produces **zero** documents in the sandbox and a reply that
  is a "client not found" message, not an invoice confirmation (REQ-INV-003).
- No new tool or parameter is invoked/added to ask for client details or to link the flows — this
  is model/prompt-driven behavior on top of existing tools (REQ-INV-004/REQ-INV-006).
- `add_client`'s approval turn and `create_invoice`'s (second) approval turn are two **separate**
  approval events — verified by observing two distinct `mcp_approval_request`/response exchanges
  in the Responses API turn sequence, not one combined confirmation (REQ-INV-007, Clarifications).
- If the godfather declines the `add_client` approval, no client and no document are created — the
  original invoice request simply goes unfulfilled (Edge Cases, no new decline-handling needed).
- Once both approvals succeed, the final document's `client.id` matches the newly-created client's
  real `client_id` (REQ-INV-009) — same verification standard as US1.

**Router Requirement**: same `textMessage` route + Morning MCP tool attachment for godfather.

---

## US3 — Document creation blocked on an ambiguous client name (Priority: P2) [Group A]

**Given** the same setup, with two existing sandbox clients both named "Danny" — "Danny Cohen" and
"Danny Katz"
**When** the godfather sends "תוציא חשבונית לדני על 200 שקל"
**Then** `create_invoice`'s implementation resolves "דני"/"Danny" via `_resolve_client_by_name`,
finds more than one match, creates **no document**, and returns the same disambiguation-candidates
message `get_client_details`/`update_client` already return (REQ-INV-005) — listing both
candidate names
**When** the godfather clarifies which one they meant (e.g. "Danny Cohen")
**Then** the model retries `create_invoice` with the disambiguated name, which now resolves
unambiguously and proceeds exactly as US1.

**Independent Test**: Can be fully tested standalone by seeding two similarly-named sandbox
clients, requesting an invoice by the ambiguous shared first name, and asserting (a) no document
was created and (b) the reply text contains both candidate names — delivers value (prevents a
wrong-client invoice) independent of US1/US2.

Acceptance criteria:
- Zero documents are created in the sandbox from the ambiguous request (REQ-INV-005).
- The reply lists the real candidate names as they exist in the sandbox (verified via
  `MorningClient.search_clients`, not just asserted from the reply text alone).
- After disambiguation and retry, the document is created attached to the correctly-resolved
  client's real `client_id` (REQ-INV-009).

**Router Requirement**: same `textMessage` route + Morning MCP tool attachment for godfather.

---

## US4 — Uniform behavior across the remaining 2 Group A tools (Priority: P2) [Group A]

**Given** the same setup as US1 (one existing, unambiguous client, "Danny Cohen")
**When** the godfather separately requests `create_transaction_account` and
`create_combo_document` for that same existing client (in addition to `create_invoice`, already
covered by US1-US3)
**Then** each tool independently resolves the client via `_resolve_client_by_name` and attaches
the created document to the real `client_id` exactly as `create_invoice` does — no Group A tool
retains the old bare-name-only payload shape (REQ-INV-008).

**Independent Test**: Can be fully tested as 2 additional standalone scenarios (one per remaining
Group A tool), each seeding a client, requesting that specific document type, approving, and
verifying (via `MorningClient.get_invoice`) that tool's created document's `client.id` matches the
real client — reusing a shared assertion helper rather than duplicating the full round-trip
narrative for each tool (REQ-INV-009).

Acceptance criteria:
- Both remaining Group A tools show the same three behaviors already proven for `create_invoice`
  in US1-US3: attach-by-id on a single match, refuse-with-friendly-message on zero matches,
  refuse-with-candidates on multiple matches, disclose-on-non-exact-match.
- No tool-specific exception or special-casing exists anywhere in Group A's implementation
  (REQ-INV-008) — a code-level check (e.g. a shared helper used by all 3 Group A tools' payload
  builders) is an acceptable way to demonstrate this, not just 3 independent test passes.

**Router Requirement**: same `textMessage` route + Morning MCP tool attachment for godfather.

---

## US5 — A client-role or blocked-role user has no document-creation capability (RBAC, unchanged)

**Given** the same setup, but the sender is a **client** (not godfather/admin)
**When** the client sends "תוציא לי חשבונית" and the `textMessage` webhook is dispatched
**Then** the AIHandler makes the reply call **without** attaching any Morning MCP tool (existing
Feature 018 behavior, unaffected by this feature) → no document is created, no client is resolved
or created → the bot replies normally (e.g. explaining it can't do that).

**Independent Test**: Can be fully tested standalone — assert no Morning API calls occur at all for
a client-role sender attempting to trigger this feature's new behavior.

Acceptance criteria:
- The Responses call for a client/blocked role carries no `mcp` tool (existing behavior — this
  feature adds no new RBAC surface, REQ-INV-007-adjacent).
- Nothing is read, resolved, or created in the Morning sandbox.

**Router Requirement**: same route; tool attachment remains role-gated (godfather/admin only,
unchanged from Feature 018).

---

## US6 — Group B tools preserve the original document's real client, or refuse if it has none (Priority: P1) [Group B, new 2026-08-06]

**Given** an existing tax invoice for "Danny Cohen" was created via `create_invoice` **after** this
feature shipped (so its `client` sub-object is `{"id": "<real client_id>", "name": "Danny Cohen",
...}`, per US1)
**When** the godfather sends "תעשה זיכוי לחשבונית הזאת" ("issue a credit note for this invoice") /
"תוציא קבלה על החשבונית הזאת" ("issue a receipt for this invoice"), naming that invoice
**Then** `create_credit_note`/`create_receipt` fetches the original via `client.get_invoice`, finds
a real `client.id` on it, and builds the new (credit note / receipt) document's payload with that
same `{"self": False, "id": "<the same real client_id>"}` — **not** rebuilding a bare-name object
from `client.name` as it does today (REQ-INV-012) — the new document is created attached to the
same real client as the original.

**Given** instead an existing tax invoice for "Danny Cohen" that **predates** this feature (its
`client` sub-object is `{"name": "Danny Cohen"}` only — no `id`, since it was created before this
feature ever attached by real client)
**When** the godfather asks for a credit note / receipt / closing document against that older
invoice
**Then** the tool finds no `client.id` on the original and **refuses** — creates no new document
and returns a friendly Hebrew error explaining that this invoice isn't linked to a real client
record so a linked document can't be issued for it (REQ-INV-013) — it does **not** silently fall
back to attaching the new document by bare name either.

**Independent Test**: Two independent scenarios, each fully testable standalone: (a) seed a real
client + an invoice created with real attachment (post-feature shape) → request a credit
note/receipt → verify (via `MorningClient.get_invoice` on the *new* document) its `client.id`
matches the original's; (b) construct/seed an invoice whose `client` sub-object has no `id` (the
pre-feature shape) → request a credit note/receipt → assert **zero** new documents are created and
the reply is the friendly refusal message, not a document confirmation.

Acceptance criteria:
- `create_credit_note`, `create_receipt`, and `close_transaction_account` all show this same
  preserve-or-refuse behavior — no tool-specific exception (REQ-INV-012/013 apply uniformly across
  Group B, mirroring REQ-INV-008's uniformity-within-a-group principle for Group A).
- On the preserve path, the new document's `client.id` is verified equal to the original's
  `client.id` directly against the sandbox (`MorningClient.get_invoice` on both documents) — not
  inferred from the reply text.
- On the refuse path, zero new documents are created in the sandbox and the reply text is a
  friendly Hebrew error (constitution-compliant "[emoji] [what happened]. [what to do next]."
  shape) — never a raw exception, never a silently-succeeded bare-name document.
- This is an accepted, deliberate limitation (spec.md Edge Cases, Clarifications 2026-08-06): any
  invoice created **before** this feature ships cannot get a credit note, receipt, or closing
  document issued against it **after** this feature ships, unless/until a future feature adds a
  remediation path (e.g. re-attaching a real client to a historical document) — no such
  remediation is built by this feature.

**Router Requirement**: same `textMessage` route + Morning MCP tool attachment for godfather.

---

## Out of Scope for This Feature

- **Retroactive migration of documents already created with a bare-name client** — no backfill,
  no re-attachment of historical documents (see spec.md Edge Cases). This is also why Group B
  tools refuse rather than fall back (US6) — there is deliberately no code path that would let a
  pre-feature document's descendants silently inherit real attachment.
- **End-to-end verification that Morning actually emails the now-real client** — this feature
  verifies the document/client attachment (`client.id` on the created document), which is the
  automatable, actionable half of the motivating problem; a real email-delivery check is out of
  scope for this feature's automated test suite (spec.md Assumptions).
- **Any new MCP tool, new tool parameter, or new approval-gate/combined-confirmation mechanism** —
  this feature is a pure internal-behavior change to the 6 existing document-creation tools,
  reusing Feature 026's existing resolution/approval machinery entirely unchanged.
- **Client deletion** — untouched, unrelated to this feature (Feature 026 already scoped it out
  separately).
