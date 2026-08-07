# Feature Spec: Mandatory Reference to an Existing Client for Invoice Creation

**Feature ID**: 027-mandatory-client-reference-invoicing
**Priority**: P2 (picked up 2026-08-06 — see Status)
**Status**: Done - implemented, tested (89/89 billed tests passing across both apps, plus real
sandbox integration and unit coverage), and merged to master 2026-08-07 (PR pending - see git
history). A related but distinct fuzzy-matching gap found during verification (a client
reference that omits a geresh character entirely, e.g. "גקי" not finding "ג׳קי") was split out
to `specs/bugfixes/bugfix-027-geresh-omitted-entirely-not-fuzzy-matched.md` rather than blocking
this feature - the punctuation-*variant* mismatch case (apostrophe vs. geresh) that this
feature's own verification surfaced IS fixed here, in `_normalize_hebrew_geresh`.
**Created**: July 29, 2026 (placeholder) — respecified August 6, 2026
**Branch**: `feature/027-mandatory-client-reference-invoicing`
**Apps**: `apps/morning-mcp-app/` only (all changes confined to **6** document-creation MCP tools —
corrected 2026-08-06 during `/speckit.plan`, see Clarifications — and their shared helpers; no
`apps/denidin-app` change is needed — the existing per-tool MCP approval gate,
`AIHandler.APPROVAL_REQUIRED_MCP_TOOLS`, already covers `add_client` and every `create_*`/
`close_*` tool individually, and nothing about this feature changes which tools are gated or how)

**Input**: User description: "Today docs created in Morning have a client name that's just a
free-text string, not a reference to a real client record — so Morning never emails the client
(only documents attached to a real client are sent) and per-client accounting doesn't work either.
The system should: (1) search for the client, (2) if found, attach the real client to the
document (verified against the live API), (3) if not found, create the client first (asking the
godfather for missing details like phone/email), then attach it."

---

**CRITICAL - MANDATORY REQUIREMENT**:
🚨 **This feature MUST have a separate `user-stories.md` file** before spec approval:
- Spec approval is BLOCKED if `user-stories.md` does not exist
- See `user-stories.md` in this directory and `.github/METHODOLOGY.md §I`

**This spec complies with**:
- **CONSTITUTION.md** (§I-III, §V): no env vars, UTC timestamps, real-sandbox integration tests
- **METHODOLOGY.md** (§I, II, VIII, IX, X): user stories mandatory, terminology glossary,
  technology choices, requirement IDs

---

## Terminology Glossary

- **Morning client** / **client record**: a Green Invoice CRM customer record, as defined by
  Feature 026 — `name`, `email`, `phone` (all required at creation), `tax_id` (optional). Has a
  system-assigned `client_id` (UUID), never surfaced to the WhatsApp user (REQ-CLIENT-018,
  unchanged by this feature).
- **Document-creation tools**: **6** Morning MCP tools that create a real Green Invoice document,
  in two groups by how each identifies its client (corrected 2026-08-06 during `/speckit.plan` —
  the original placeholder and this spec's first draft both said "5" and assumed one uniform
  mechanism; that was wrong, see Clarifications):
  - **Group A** — `create_invoice`, `create_transaction_account`, `create_combo_document`: take a
    free-text `client_name: str` parameter and pass it straight through as
    `{"client": {"self": False, "name": client_name}}` in the `/documents` payload — a bare string
    with no relationship to any real client record.
  - **Group B** — `create_credit_note`, `create_receipt`, `close_transaction_account`: take **no**
    `client_name` at all. Each takes `original_invoice_id`, fetches that original document via
    `client.get_invoice`, and copies `original["client"]["name"]` into the new (linked) document's
    payload as `{"self": False, "name": ...}` — **discarding `original["client"]["id"]`**, which is
    already present on the fetched original whenever it was itself created with real client
    attachment (confirmed live, see Clarifications).
- **Client-by-id attachment**: the behavior confirmed live in this feature's research (see
  Clarifications and `research.md`) — sending `{"client": {"self": False, "id": "<client_id>"}}`
  instead of a name causes Morning to resolve the document's client from the real client record
  (name, email, etc. all populated server-side from the `id`) rather than from the string.
  **Email delivery gap this fixes**: Morning only emails a document to a client when the document
  is attached to a real client record with a real email — with today's bare-name behavior, no
  document is ever emailed, no matter what name is passed.
- **`_resolve_client_by_name`**: the existing Feature 026 helper
  (`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`) that searches Morning by name and
  returns `(resolved_client, candidates)` — 0 matches → `(None, [])`, exactly 1 → `(client, [client])`,
  >1 → `(None, [client1, client2, ...])` (caller must disambiguate, never guess). This feature
  reuses it unchanged as the lookup step for document creation.
- **`add_client`**: the existing Feature 026 tool that creates a client record (approval-gated).
  This feature's "not found" path relies on the model calling `add_client` itself, then retrying
  the original document-creation call — no new tool, no new approval mechanism.
- **Morning MCP approval gate**: OpenAI's own Responses-API per-tool `require_approval` mechanism
  (`AIHandler.APPROVAL_REQUIRED_MCP_TOOLS`/`NO_APPROVAL_MCP_TOOLS`, Feature 022/026) — each
  individual MCP tool call the model wants to make is independently flagged for human approval or
  not; this is **not** app-level custom state. `add_client` and every `create_*` tool are already
  each independently gated today — this feature introduces no new gating logic, and the "two
  separate approval turns" decision below falls out of this existing per-call mechanism for free.
- **DEPRECATED**: none.

---

## Clarifications

### Session 2026-08-06 (live API verification, prior to `/speckit.clarify`)

- **Q: Does the real Green Invoice `/documents` API actually support attaching a document to an
  existing client by ID (as opposed to only a bare name string)?** → **A: Yes — confirmed live
  against the real Morning sandbox** (not just the Postman collection's documentation), 2026-08-06:
  created a real test client via `add_client`, then created a real test document with
  `{"client": {"self": false, "id": "<created client_id>"}}` (no `name` field in the payload at
  all). The document was created successfully; both the immediate response and a fresh `GET
  /documents/{id}` returned the document's `client` block populated with the real client's full
  record (name, phone, email) resolved server-side from the `id`. This resolves the placeholder
  spec's "verify the API supports this" concern with an empirical result, not an assumption
  (CONSTITUTION's "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS" rule) — see `research.md` for the full
  request/response trace.

### Session 2026-08-06 (`/speckit.specify` scoping)

- **Q: Should mandatory client resolution apply to all 5 document-creation tools, or only
  `create_invoice`?** → **A: All 5 tools uniformly.** The underlying problem (bare client-name
  string, no real client attachment, no email delivery) is identical across all 5 — they all build
  the same `{"client": {"self": False, "name": client_name}}` shape today. No reason to leave 4 of
  the 5 with the old broken behavior.
- **Q: When the named client doesn't exist and needs to be created first, should that be one
  combined approval turn covering both the new client and the document, or two separate approval
  turns?** → **A: Two separate approval turns**, reusing the existing per-tool MCP approval gate
  unchanged: the model calls `add_client` (its own existing approval prompt fires), and once
  approved and the client exists, the model retries the original document-creation call, which
  resolves the now-existing client and fires its own existing approval prompt. **No new
  combined-confirmation UI or app-level pending-state is built** — this falls directly out of the
  existing Feature 022/026 per-tool-call approval mechanism, at zero new complexity.
- **Q: If the named client doesn't exist yet, should document creation (a) fail with a friendly
  "not found, add them first" message, or (b) prompt to create the client inline?** → **A: Both,
  in sequence — this is not actually an either/or.** The document-creation tool itself does (a): it
  never silently creates a bare-name document and never silently invents a client — on zero matches
  it returns a friendly "client not found" message (mirroring `get_client_details`'s existing
  `format_client_not_found()`) and creates nothing. The model, seeing that friendly message plus
  the user's original request, is expected (guided by the runtime constitution, see REQ-INV-004)
  to then pursue (b) itself — ask the godfather for the missing client details (phone/email) and
  call `add_client`, then retry the original document-creation call. This mirrors exactly how a
  human using Morning's own UI behaves (search dropdown finds nothing → manually add the client →
  retry) and requires no new tool signature — `client_name: str` stays the only client-identifying
  parameter document-creation tools take.
- **Q: Does ambiguous client-name matching during document creation block the document entirely
  until resolved, or is Morning's own matching trusted as a fallback?** → **A: Blocks entirely,
  reusing `_resolve_client_by_name`'s existing behavior unchanged** (REQ-CLIENT-003, Feature 026):
  on >1 name matches, the document-creation tool returns the same disambiguation message
  `get_client_details`/`update_client` already return (mirroring `format_ambiguous_clients_message`)
  and creates nothing — the model must ask the user to disambiguate and retry, exactly as it
  already does for `get_client_details`/`update_client`. Morning's own document-side name-matching
  (if any) is never relied upon — this feature's whole point is to stop relying on that.

### Session 2026-08-06 (`/speckit.clarify`)

- **Q: `_resolve_client_by_name` can return exactly one match that isn't an exact name match (a
  fuzzy/substring hit) — should document creation disclose this before/while attaching the
  document, require an exact match only, or silently proceed either way?** → **A: Disclose.** A
  single non-exact match still proceeds (creates the document, attached by real `client_id`), but
  the confirmation reply MUST state which real client name was actually matched — reusing the
  `is_exact_match` disclosure pattern `format_client_details`/`get_client_details` already has
  (Feature 026) — so the godfather sees which client was matched before/as part of approving,
  rather than an invoice silently going out to a same-ish-named but wrong client. See REQ-INV-011
  (new) and US1's updated acceptance criteria.

### Session 2026-08-06 (`/speckit.plan` scoping correction)

- **Q: Re-reading the actual tool implementations for planning found that only 3 of the original
  "5 document-creation tools" (`create_invoice`, `create_transaction_account`,
  `create_combo_document` — Group A) take a `client_name` to resolve; the other 2
  (`create_credit_note`, `create_receipt` — Group B) instead derive their client from an
  `original_invoice_id`'s already-fetched document, and drop its `client.id` in favor of a bare
  name. There's also a 6th tool with the identical Group-B bug that neither the original problem
  description nor this spec's first draft mentioned at all: `close_transaction_account`. Should
  `close_transaction_account` be fixed by this feature too?** → **A: Yes, include it.** Leaving
  one of three identical-shaped tools broken while fixing the other two would be an inconsistency
  this feature itself would introduce. This feature now covers 6 tools total, in the two groups
  defined in the Terminology Glossary.
- **Q: For Group B tools, the fix is "preserve `original.client.id` instead of dropping it for a
  bare name" — but what should happen when the original document predates this feature and has no
  `id` on its `client` sub-object (an old bare-name attachment)?** → **A: Refuse with a friendly
  error, do not fall back to bare-name behavior.** This is an accepted, deliberate limitation: any
  invoice created **before** this feature ships cannot get a credit note, receipt, or closing
  document issued against it **after** this feature ships, until/unless a future feature adds a
  remediation path (e.g. re-attaching a real client to a historical document) — no such
  remediation is built here. This keeps the feature's guarantee absolute (no document this feature
  touches is ever created/re-created with a bare-name-only client) rather than leaving a silent
  degraded path. See REQ-INV-012/013 and `user-stories.md` US6 (new).

---

## User Stories Reference

**NOTE**: Complete user stories are defined in **`user-stories.md`** (separate file, mandatory,
Given-When-Then format, explicit MCP-tool-dispatch requirements per story).

Quick reference (see `user-stories.md` for full acceptance criteria). US1-US4 cover **Group A**
(`create_invoice`, `create_transaction_account`, `create_combo_document`); US6 covers **Group B**
(`create_credit_note`, `create_receipt`, `close_transaction_account`):

1. **Document created for an existing, unambiguous client** (P1, Group A) — godfather asks to
   create a Group A document for a client that already exists in Morning by an exact/unambiguous
   name match; the tool resolves the real `client_id` via `_resolve_client_by_name` and attaches
   the document to the real client record (`{"client": {"self": False, "id": ...}}`) instead of a
   bare name — verified the document is actually attached to the real client (and, where
   feasible, that Morning attempts to email it) rather than just accepting a string.
2. **Document creation blocked on an unknown client, then created after inline client creation**
   (P1, Group A) — godfather asks to create a document for a client name that doesn't exist yet;
   the tool refuses with a friendly "client not found" message and creates nothing; the model asks
   for the missing client details, calls `add_client` (its own existing approval turn), and once
   approved and the client exists, retries the original document-creation request, which now
   succeeds against the newly-created real client.
3. **Document creation blocked on an ambiguous client name** (P2, Group A) — godfather asks to
   create a document for a name matching more than one existing client; the tool refuses, lists
   the candidates, and creates nothing until the model/user disambiguates and retries.
4. **Behavior is uniform across all 3 Group A tools** (P2) — the same resolve/attach/refuse/
   disclose behavior applies identically whether the tool is `create_invoice`,
   `create_transaction_account`, or `create_combo_document`.
5. **RBAC unchanged** — a client/blocked-role sender never gets any of these tools attached.
6. **Group B tools preserve the original's real client, or refuse if it has none** (P1, Group B,
   new 2026-08-06) — `create_credit_note`/`create_receipt`/`close_transaction_account` fetch their
   linked original document and reuse its real `client.id` (instead of dropping it for a bare
   name) when the original has one; when the original predates this feature and has no
   `client.id`, the tool refuses with a friendly error and creates nothing, rather than falling
   back to a bare-name attachment.

---

## User Scenarios & Testing *(mandatory)*

See `user-stories.md` for the authoritative Given-When-Then acceptance scenarios per story (Group
A: found/unambiguous = P1, not-found-then-created = P1, ambiguous = P2, cross-tool uniformity =
P2; Group B: preserve-or-refuse = P1 — each independently testable).

### Edge Cases

**Group A** (`create_invoice`, `create_transaction_account`, `create_combo_document`):

- What happens when the named client matches exactly one existing client? → The document is
  created attached to that client's real `client_id`; no approval-turn change versus today (the
  document-creation tool's own existing approval gate is unaffected — only the payload it builds
  changes).
- What happens when the single match isn't an exact name match (fuzzy/substring)? → The document
  is still created attached to that resolved client (not treated as ambiguous or not-found), but
  the confirmation reply discloses which real client name was actually matched (REQ-INV-011,
  `/speckit.clarify` 2026-08-06) — so a "Danny" request that fuzzy-resolves to "Danny Cohen
  Consulting" shows that full name before/as part of the approval prompt, rather than silently
  invoicing it.
- What happens when the named client doesn't exist at all? → No document is created; a friendly
  "client not found" message is returned instead of the tool silently succeeding with a bare-name
  document as it does today. The model is expected to offer to create the client next.
- What happens when the named client matches more than one existing client? → No document is
  created; the candidates are listed and the model/user must disambiguate before retrying —
  mirrors `get_client_details`'s existing behavior exactly (Feature 026, REQ-CLIENT-003).
- What happens if the model creates the client via `add_client` but the godfather declines that
  approval? → No client is created, no document is created — the original document-creation
  request simply goes unfulfilled, same as any other declined approval (Feature 022/026 pattern,
  no new behavior needed).
- What happens if, between the "not found" response and the model's `add_client` retry, someone
  else creates a same-named client concurrently? → Out of scope / accepted risk — no locking or
  race-detection is introduced; the eventual document-creation retry re-resolves by name and
  behaves per the found/ambiguous/not-found rules above, whatever the state turns out to be at that
  point. This mirrors how Feature 026 already accepts no proactive duplicate-check on `add_client`
  itself ("try and fail").
- What happens to documents created *before* this feature ships (still attached by bare name in
  Morning)? → Out of scope for Group A itself (no retroactive migration/backfill) — but see the
  Group B edge case below, since Group B tools link *to* exactly these older documents.

**Group B** (`create_credit_note`, `create_receipt`, `close_transaction_account`) — new
2026-08-06:

- What happens when the linked original document has a real `client.id` (created post-feature,
  Group A behavior above)? → The new (credit note/receipt/closing) document is created with that
  same real `client.id` — never rebuilt from a bare name (REQ-INV-012).
- What happens when the linked original document predates this feature (`client` sub-object has
  only a `name`, no `id`)? → No new document is created; the tool refuses with a friendly Hebrew
  error explaining the original isn't linked to a real client record, so a linked document can't
  be issued for it (REQ-INV-013). This is an accepted, deliberate limitation, not a bug: such
  historical invoices simply cannot get credit notes/receipts/closing documents after this feature
  ships, unless a future feature adds a remediation path — none is built here.

---

## Requirements *(mandatory)*

### Functional Requirements

- **REQ-INV-001**: All 3 **Group A** document-creation tools (`create_invoice`,
  `create_transaction_account`, `create_combo_document`) MUST resolve their `client_name` argument
  to a real Morning client record via `_resolve_client_by_name` (the same Feature 026 helper
  `get_client_details`/`update_client` already use) before building the `/documents` payload,
  instead of passing the name straight through unresolved. (Corrected 2026-08-06: this requirement
  applies to Group A only — Group B tools take no `client_name` at all; see REQ-INV-012/013.)
- **REQ-INV-002**: When resolution finds exactly one matching client, the document-creation
  payload's `client` object MUST be `{"self": False, "id": "<resolved client_id>"}` — **no `name`
  field** — confirmed live (Clarifications, `research.md`) to cause Morning to attach the document
  to that real client record, populating name/email/etc. server-side. This applies whether the
  single match is exact or non-exact (fuzzy/substring) — see REQ-INV-011 for the disclosure
  requirement on non-exact matches.
- **REQ-INV-003**: When resolution finds zero matching clients, the tool MUST create no document
  and MUST return a friendly "client not found" message (mirroring `get_client_details`'s existing
  `format_client_not_found()`) rather than silently creating a bare-name document as it does today.
- **REQ-INV-004**: On the "client not found" response (REQ-INV-003), the model is expected (guided
  by `config/runtime_constitution.md`, updated as part of this feature's implementation) to ask the
  godfather for the missing client details and call `add_client`, then retry the original
  document-creation request — this is model-guided behavior via prompt/constitution changes, not
  new application code or a new tool signature.
- **REQ-INV-005**: When resolution finds more than one matching client, the **Group A** tool MUST
  create no document and MUST return the same disambiguation-candidates message
  `get_client_details`/`update_client` already return (mirroring
  `format_ambiguous_clients_message`), never guessing which candidate was meant.
- **REQ-INV-006**: This feature introduces **no new MCP tool and no new parameter** on any of the
  6 document-creation tools — Group A's `client_name: str` remains its only client-identifying
  input, and Group B gains no new parameter either (it already has everything it needs in the
  fetched original document); resolution/preservation of a real `client_id` happens entirely
  inside each tool's existing implementation.
- **REQ-INV-007**: This feature introduces **no new approval-gate logic** — `add_client` and each
  of the 6 document-creation tools remain independently gated exactly as today
  (`AIHandler.APPROVAL_REQUIRED_MCP_TOOLS`, unchanged); the "create client, then create document"
  flow (Group A, US2) is two separate, already-existing approval turns falling out of the existing
  per-tool-call mechanism, not a new combined-confirmation feature.
- **REQ-INV-008**: The behavior in REQ-INV-001 through REQ-INV-005 MUST be identical across all 3
  **Group A** tools — no Group A tool is special-cased to keep the old bare-name behavior.
  (Corrected 2026-08-06: this uniformity claim is scoped to Group A; Group B's distinct uniformity
  requirement is REQ-INV-012/013.)
- **REQ-INV-009**: A real Morning-sandbox test MUST create a client, then create a **Group A**
  document referencing that client by name, and independently verify (via a direct
  `MorningClient.get_invoice` call, not just the tool's reply text) that the created document's
  `client.id` matches the real client's `client_id` — empirically proving attachment, not just
  payload construction. At least one such test MUST exist per Group A tool (REQ-INV-008
  uniformity), reusing a shared helper rather than duplicating the full round-trip three times if a
  shared assertion suffices.
- **REQ-INV-010**: This feature does **not** change how the WhatsApp user is informed about a
  successful document creation (the existing Hebrew confirmation message shape, e.g.
  `format_invoice_confirmation`, is unaffected) — only the underlying `client` payload and the
  not-found/ambiguous refusal paths change, **except** as required by REQ-INV-011 (non-exact-match
  disclosure).
- **REQ-INV-011** (`/speckit.clarify`, 2026-08-06): When the single resolved match is **not** an
  exact name match against the requested `client_name` (fuzzy/substring resolution — the same
  `_is_exact_name_match` check `get_client_details` already performs), the document-creation tool
  MUST disclose which real client name was actually matched in its confirmation reply, before or
  as part of the approval prompt — mirroring the existing `is_exact_match=False` disclosure
  language `format_client_details` already uses for `get_client_details`. The document is still
  created against that resolved client (this is NOT treated as ambiguous or not-found) — the
  requirement is disclosure, not refusal, so the godfather can catch a wrong-client match before
  approving rather than after a document has already gone out.
- **REQ-INV-012** (`/speckit.plan` scoping correction, 2026-08-06): All 3 **Group B** tools
  (`create_credit_note`, `create_receipt`, `close_transaction_account`) MUST fetch their linked
  original document (`client.get_invoice(original_invoice_id)`, as they already do) and, when that
  original's `client` sub-object has an `id`, build the new document's `client` object as
  `{"self": False, "id": "<the original's client.id>"}` — preserving the real attachment —
  **instead of** rebuilding `{"self": False, "name": ...}` from just the original's `name` as they
  do today (which silently discards the `id` that's already present).
- **REQ-INV-013** (`/speckit.plan` scoping correction, 2026-08-06): When a Group B tool's linked
  original document's `client` sub-object has **no** `id` (a pre-feature, bare-name-only
  attachment), the tool MUST create no new document and MUST return a friendly Hebrew error
  explaining that the original isn't linked to a real client record, rather than falling back to
  rebuilding a bare-name `client` object as it does today. This is a deliberate, accepted
  limitation (Clarifications) — no remediation path (e.g. retroactively attaching a real client to
  a historical document) is built by this feature.

### Key Entities

- **Client** (unchanged from Feature 026): a Green Invoice CRM customer record — `name`, `email`,
  `phone`, `tax_id` (optional), `client_id` (system-assigned). This feature is the first to make
  document creation *depend* on this entity actually existing, rather than treating it as
  informational only.
- **Document** (Green Invoice type 300/305/320/330/400, per existing document-creation tools):
  gains a real relationship to a **Client** entity via `client.id` in its creation payload, instead
  of an unrelated free-text name string. **Its `client` sub-object now has two shapes in the
  wild** (corrected 2026-08-06): `{"id": ..., "name": ..., ...}` for any document created by this
  feature's Group A tools (or a Group B tool that preserved an id per REQ-INV-012), versus
  `{"name": ...}` only for any document created before this feature shipped. Group B tools must
  branch on which shape a linked original has (REQ-INV-012/013).

---

## Technology Choice: Reuse Feature 026's Client Resolution, No New Infrastructure

- **Decision Date**: August 6, 2026
- **Decision**: Two distinct, group-specific mechanisms (corrected 2026-08-06 — the tools split
  into two groups, not one uniform mechanism):
  - **Group A**: reuse `_resolve_client_by_name` (and its existing not-found/ambiguous message
    formatters) unchanged inside each of the 3 Group A tools' payload-building functions, swapping
    `{"name": client_name}` for `{"id": resolved.id}` in the `client` object on a single match, and
    returning early with a friendly message (no `/documents` call at all) on zero or multiple
    matches.
  - **Group B**: no search/resolution needed at all — just stop discarding the `id` already
    present on the fetched original document. Each Group B payload-building function branches on
    whether `original["client"].get("id")` is present: if so, use `{"self": False, "id": ...}`; if
    not, the calling tool refuses (REQ-INV-013) before ever calling the builder.
- **Rationale**: Feature 026 already built, tested, and shipped `_resolve_client_by_name`'s
  resolution logic for read/update flows — reusing it for Group A means zero new Morning API
  surface, zero new disambiguation logic, and a single well-tested code path shared by 3 tools
  plus the two existing read/update tools. Group B needs no equivalent — it already has the real
  client `id` sitting in memory from a call (`client.get_invoice`) it was already making; the only
  change is stopping the current code from throwing that `id` away. The already-live-confirmed
  `client.id` payload shape (Clarifications) needs no new client library method for either group —
  `MorningClient.create_invoice`'s existing generic `POST /documents` wrapper accepts whatever
  payload dict it's given.
- **Alternatives Considered**: Trusting Morning's own server-side name-matching on the `/documents`
  endpoint (if any exists) — rejected; unconfirmed, and defeats the entire purpose of this feature
  (a single source of truth for "who is this invoice actually for"). Building a brand-new
  resolution helper specific to document creation — rejected as needless duplication of
  `_resolve_client_by_name`, which already has real-sandbox test coverage from Feature 026. For
  Group B, falling back to bare-name attachment when the original has no `id` — rejected per the
  user's explicit Clarifications decision (refuse instead), to keep the feature's guarantee
  absolute rather than reintroducing a silent degraded path.
- **Migration Path**: None needed — purely additive/corrective to existing tool implementations;
  no data migration for historical documents (out of scope, see Edge Cases). Group B's refusal
  behavior is itself the intentional "no migration" consequence made explicit and safe, rather than
  silently perpetuating bare-name attachment forever.

---

## Assumptions

- **Confirmed in this spec's own research** (Clarifications, `research.md`): the Green Invoice
  `/documents` endpoint accepts `client.id` in place of `client.name` and correctly attaches the
  document to that real client record — verified via a real, live sandbox call, not assumed from
  documentation alone.
- Feature 026's `_resolve_client_by_name`/`format_client_not_found`/`format_ambiguous_clients_message`
  are assumed stable and reusable as-is (they already are, unchanged, for `get_client_details`/
  `update_client`) — no changes to Feature 026 code are anticipated, only new call sites.
- Whether Morning actually *sends an email* to the now-real client on document creation is stated
  as this feature's motivating problem but is **not independently re-verified end-to-end by this
  feature** (that would require a real deliverable email inbox check, out of scope for an
  automated test suite) — REQ-INV-009's verification is scoped to confirming the document/client
  relationship server-side (`client.id` on the created document), which is the actionable,
  automatable half of the claim.
- No new RBAC role or permission tier is introduced; document creation remains gated exactly as
  today (godfather/admin only, via the existing Morning MCP tool attachment).
- Client-resolution behavior for document creation requires **real Morning sandbox** integration
  tests per the ZERO-MOCKING/CONSTITUTION §I/§V rule — no `unittest.mock` of the Green Invoice API.
- **Group B's real-sandbox tests need a way to construct/seed an original document with no
  `client.id`** (the pre-feature shape) to exercise REQ-INV-013's refusal path — since this
  feature's own Group A fix means any *newly* created original will always have a real `id`, the
  no-`id` case can only be produced directly (seeding a document via a raw `MorningClient.create_invoice`
  call using the old `{"name": ...}`-only payload shape, bypassing the tool layer), not by using
  any of this feature's own tools. This is a test-authoring detail for `/speckit.tasks`, not a
  design gap.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of documents created for a client name that unambiguously matches exactly one
  existing Morning client are attached to that client's real `client_id` — verified by inspecting
  the created document's `client.id` field directly against the sandbox, not the tool's reply text.
- **SC-002**: 0% of documents are created with a bare, unresolved client-name string once this
  feature ships — every document-creation tool either attaches a real `client_id` or creates
  nothing at all.
- **SC-003**: 100% of document-creation attempts against a not-yet-existing client name result in
  no document being created and a friendly "client not found" message, giving the model everything
  it needs to offer creating the client next — zero silent bare-name fallbacks.
- **SC-004**: 100% of document-creation attempts against an ambiguous client name (>1 match) result
  in no document being created and the real candidate list being surfaced — zero guessed matches.
- **SC-005**: A godfather can go from "create an invoice for a brand-new client" to a real,
  client-attached invoice in a single conversational flow (ask → client details requested → client
  created on approval → invoice created on approval) without needing to separately, manually add
  the client via a different request first.
- **SC-006**: This behavior is identical and independently verified across all 3 **Group A**
  tools — zero Group A tools retain the old bare-name-only behavior.
- **SC-007**: 100% of documents created from a non-exact (fuzzy/substring) single-match resolution
  produce a confirmation reply that names the actual matched client — zero silent non-exact
  attachments (REQ-INV-011).
- **SC-008** (`/speckit.plan` scoping correction, 2026-08-06): 100% of Group B documents
  (`create_credit_note`/`create_receipt`/`close_transaction_account`) created against an original
  that has a real `client.id` preserve that same `client.id` on the new document — verified
  directly against the sandbox on both documents, not the reply text. 0% of Group B documents are
  ever created against an original that has no `client.id` — those attempts always produce zero
  new documents and a friendly refusal instead (REQ-INV-012/013).
