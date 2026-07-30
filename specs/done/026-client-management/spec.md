# Feature Spec: Client Management (Morning/Green Invoice CRM Clients)

**Feature ID**: 026-client-management
**Priority**: P2
**Status**: Done - Merged (2026-07-30) — implemented, verified (68 new/updated unit tests, 27
real-sandbox tests, all 15 expensive E2E scenarios passing), merged to `master`. See `tasks.md`'s
"Post-implementation follow-up" section and `research.md` Decisions 11-13 for fixes made after
initial completion (list_clients pagination, non-exact-match disclosure, and a separately-filed
unrelated bug, `bugfix-018`, found during expensive-test verification). The manual `quickstart.md`
walkthrough (T026) was not run as part of this merge — automated verification (unit + real-sandbox
+ expensive E2E) was judged sufficient.
**Created**: July 29, 2026
**Branch**: `026-client-management`
**Apps**: `apps/morning-mcp-app/` (primary changes — new/changed MCP tools) + `apps/denidin-app/`
(a small, real code change — extending `ai_handler.py`'s approval-gate tool-name tuples to cover
`add_client`/`update_client` — plus runtime constitution guidance; the Morning server is already
attached as a remote MCP tool for godfather/admin roles per Feature 018, so no new RBAC logic or
integration surface is needed, but this is not a documentation-only touch)

**Input**: User description: "Add management capabilities for Morning/Green Invoice CRM clients
(invoicing customers): list, view details, and update, alongside the existing `add_client` tool
(now brought under an explicit-approval gate), accessible to godfather/admin users via natural
WhatsApp language through the Morning MCP server. **Delete is explicitly out of scope** — see
Clarifications."

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

- **Morning client** / **client record**: a Green Invoice CRM customer record, scoped in this
  feature to exactly four fields — `name` (required), `email` (required), `phone` (required),
  `tax_id` (ע"מ / business ID, optional). **`address` is explicitly out of scope** (dropped), as
  is every other field the real Green Invoice API supports (`mobile`, `city`, `zip`, `country`,
  `contactPerson`, bank details, `labels`, `paymentTerms`, `category`/`subCategory` — see
  Clarifications, round 2). Distinct from the `client` **RBAC role** used elsewhere in this
  codebase (WhatsApp user permission tier) — this spec does **not** touch RBAC roles.
- **`add_client`**: the existing Morning MCP tool (`apps/morning-mcp-app/src/.../tools.py`,
  `server.py:254`) that creates a client record via `POST /clients`. Already built (Feature 005).
- **Morning MCP server**: the FastMCP server in `apps/morning-mcp-app/` exposing invoicing tools
  over streamable-HTTP to `apps/denidin-app` via a real ngrok tunnel (Feature 018). This feature
  adds tools to the same server; no new integration surface is introduced.
- **godfather/admin**: denidin RBAC roles. Per Feature 018, only these roles get the Morning
  server attached as a remote MCP tool — this feature inherits that gating automatically by
  living on the same server, and introduces no new RBAC logic.
- **client_id**: Morning's own identifier for a client record — a UUID string, confirmed via the
  Postman collection's example responses (resolved in Phase 0 research, see `research.md`
  Decision 1/2). **Internal only — never surfaced to the WhatsApp user** in any reply (see
  REQ-CLIENT-018).
- **DEPRECATED**: none.

---

## Clarifications

### Session 2026-07-29

- Q: Should `delete_client` (and/or `update_client`) require an explicit approval turn before
  executing, like Feature 022's document-creation confirmation flow? → A: **Yes, for ALL
  create/update/delete actions on a client — not just delete.** This explicitly **supersedes
  Feature 022's exemption of `add_client`** as "a non-financial record, no-wait behavior" — that
  exemption no longer holds once this feature ships. Only read actions (`list_clients`,
  `get_client_details`) remain immediate/no-wait.
- Q: What should "delete a client" do if the Green Invoice API can't hard-delete a client with
  history? → A: **Delete is out of scope for this feature entirely.** No `delete_client` tool is
  built now; deferred to a future feature.
- Q: Should `tax_id` be editable via `update_client`? → A: **Yes, editable like any other field**
  (email, phone, address) — no special immutability restriction.
- Q: Should this feature change how invoice-creation tools reference/select a client? → A: **No,
  keep invoice creation exactly as-is** (still a free-text client name passed straight through) —
  out of scope here. A **separate new feature** (mandatory reference to an existing client record
  for invoice creation) is tracked as `specs/backlog/027-mandatory-client-reference-invoicing/`.

### Session 2026-07-29 (round 2 — field scope)

- Q: Which fields are mandatory for client creation (`add_client`)? → A: **`name`, `phone`, and
  `email` are ALL mandatory.** If any is missing from the request, the AI MUST ask the user for
  it before proceeding (before creation, and before the approval prompt in REQ-CLIENT-008).
- Q: Any mandatory fields for `update_client`? → A: No individual field is mandatory beyond
  identifying the client and providing at least one field to change.
- Q: What does the real Green Invoice API actually support on the client object (checked against
  the Postman collection checked into the repo,
  `specs/done/005-mcp-morning-green-receipt/Green Invoice Public API.postman_collection.json`)?
  → A: The real schema is much richer than the current 5-field wrapper (`name`, `taxId`,
  `address`, `city`, `zip`, `country`, `phone`, `mobile`, `emails`, `contactPerson`, `bankName`/
  `bankBranch`/`bankAccount`, `labels`, `paymentTerms`, `accountingKey`, `category`/`subCategory`,
  plus computed `id`/`active`/`balanceAmount`/`incomeAmount`/`paymentAmount`/`creationDate`/
  `lastUpdateDate`/`self`). **Decision: stay minimal — only `name`, `email`, `phone`, `tax_id`
  are in scope for this feature; `address` is dropped entirely (not exposed by any tool), and all
  richer fields (mobile, city/zip/country, contactPerson, bank details, labels, paymentTerms,
  category) are explicitly out of scope**, left for a future feature if ever needed.
- **Correction to existing code**: `apps/morning-mcp-app/.../tools.py`'s
  `_build_add_client_payload` docstring claims "`phone` does not appear anywhere in the Postman
  collection's client schemas/examples — it's sent optimistically." This is **incorrect** —
  `phone` (distinct from `mobile`) is confirmed present in a real client record returned by the
  Postman collection's own "Search Clients" example response. This stale comment/assumption MUST
  be corrected as part of this feature's implementation (see REQ-CLIENT-014).

### Session 2026-07-29 (`/speckit.analyze` remediation)

- **Q (F1)**: Should `get_client_details` support lookup by tax ID as well as name (REQ-CLIENT-002
  originally said "name or exact tax ID")? → A: **No — name-only.** The real `Search Clients`
  endpoint's documented filters never include `taxId`, so tax-ID lookup was unconfirmed and is
  dropped from scope (REQ-CLIENT-002 updated).
- **Q (F2)**: Should `add_client` proactively check for a pre-existing same-name/same-tax-ID
  client before creating (as REQ-CLIENT-007 originally required)? → A: **No — "try and fail."**
  Attempt creation normally; if Morning's real API rejects it as a duplicate (or for any other
  reason), surface that rejection clearly so the user is aware and can decide what to do next.
  No proactive duplicate-check logic is built (REQ-CLIENT-007 updated).
- **Noteworthy (new requirement)**: the internal Morning `client_id` (UUID) must **never** be
  exposed to the WhatsApp user in any reply — this also corrects existing Feature-005 code
  (`add_client`'s current confirmation message includes it) — see REQ-CLIENT-018.

### Session 2026-07-29 (round 3 — format validation/normalization)

- Q: Should `email`/`phone` be format-validated and normalized per Morning's own API-layer rules?
  → A: Yes — investigated against Morning's real error-code catalog
  (`specs/done/005-mcp-morning-green-receipt/artifacts/error_codes.json`, ~90 documented codes):
  - **Email has real, documented server-side validation**: `errorCode 1102` ("כתובת מייל לא
    תקינה" — invalid email address) and `1120` ("כתובת הדומיין של המייל לא תקינה" — invalid email
    domain). This feature validates email **client-side, before any tool call or approval
    prompt**, using `email-validator`/pydantic `EmailStr` — already a dependency of
    `apps/morning-mcp-app` (`requirements.txt`) and already the pattern used by the existing
    read-side `Client.email: Optional[EmailStr]` in `models.py`, but currently **unused** by any
    write path. No normalization beyond what `email-validator` itself performs (e.g. domain
    case-normalization); reject with a friendly error otherwise.
  - **Phone has NO documented server-side format validation anywhere** in the error-code catalog,
    the Postman collection, or `data-model.md`. Since there's no Morning-side rule to mirror, this
    is an app-level policy decision: **normalize phone to Israeli local dashed format
    (`0XX-XXXXXXX`, e.g. `054-1234567`)** — matching the format shown in the Postman collection's
    own Business-object examples (its Client examples show the same digits with no dash,
    `0527384938`, confirming the digit sequence is what matters, not the separator). Accept common
    input variants (with/without `+972` country code, with/without separators) and normalize
    before sending to Morning; reject input that doesn't resolve to a plausible Israeli number.
  - **Verification requirement**: a real sandbox test MUST create a client with a phone number
    and then read it back (via `get_client_details`) to confirm Morning actually persists and
    returns the normalized value — empirically proving REQ-CLIENT-014's correction, not just
    asserting on the request payload.

---

## User Stories Reference

**NOTE**: Complete user stories are defined in **`user-stories.md`** (separate file, mandatory,
Given-When-Then format, explicit MCP-tool-dispatch requirements per story).

Quick reference (see `user-stories.md` for full acceptance criteria):

1. **List clients** (P1) — godfather/admin asks "who are my clients?" / "תראה לי את הלקוחות" and
   gets a readable list. No approval wait (read-only).
2. **View client details** (P1) — godfather/admin asks for one client's details by name/tax ID.
   No approval wait (read-only).
3. **Add a client — now approval-gated, 3 fields mandatory** (P2) — existing `add_client` tool
   brought under the same explicit-approval flow as Feature 022's document creation (behavior
   change from today); `name`/`email`/`phone` are all mandatory (AI asks for any missing before
   proceeding), `tax_id` stays optional, `address` is dropped from scope entirely.
4. **Update a client — approval-gated** (P2) — godfather/admin corrects a client's field(s)
   among `name`/`email`/`phone`/`tax_id`; waits for explicit confirmation before executing. No
   individual field is mandatory for an update beyond providing at least one to change.

**Delete is out of scope for this feature** (deferred to a future feature, per Clarifications).

---

## User Scenarios & Testing *(mandatory)*

See `user-stories.md` for the authoritative Given-When-Then acceptance scenarios per story
(List/View = P1, Add/Update = P2 — each independently testable and independently deployable as
an MVP increment. Delete is out of scope — no story exists for it).

### Edge Cases

- What happens when the WhatsApp user asks for a client that doesn't exist / no name match is
  found? → Friendly "no client found" message, no tool error surfaced to the user.
- What happens when more than one client matches the requested name (ambiguous lookup)? →
  Bot MUST list the candidates and ask the user to disambiguate rather than guessing — this
  resolution MUST happen *before* any approval prompt for a create/update action is issued (no
  point confirming "change X's phone" if X is still ambiguous).
- What happens when a `client`-role or `blocked`-role WhatsApp user asks about clients? → No
  Morning tools are attached to their call at all (existing Feature 018 RBAC gating); the model
  has no client-management capability to invoke, so it responds without invoicing knowledge.
- What happens when the Morning MCP server is unreachable (status file stale/missing)? → Existing
  Feature 018 graceful-degrade behavior applies unchanged (no tools attached, normal reply,
  WARNING logged) — this feature introduces no new failure mode here.
- What happens when the user declines the approval prompt for a create/update action? → No tool
  is invoked, no change is made in the Morning sandbox, the bot acknowledges the decline (mirrors
  Feature 022's decline handling).
- Client deletion is explicitly out of scope for this feature (see Clarifications) — no edge
  cases for it are defined here; they belong to the future delete feature.

---

## Requirements *(mandatory)*

### Functional Requirements

- **REQ-CLIENT-001**: System MUST allow a godfather/admin WhatsApp user to list existing Morning
  clients in natural language (Hebrew or English), returning at minimum each client's name and
  identifying detail (tax ID and/or phone) in a human-readable reply. Read-only — no approval
  wait (REQ-CLIENT-008).
- **REQ-CLIENT-002**: System MUST allow retrieving the full detail record (name, email, phone,
  tax_id) of a single client, addressed by **name only** (fuzzy/substring match acceptable).
  **Resolved (analysis 2026-07-29)**: tax-ID-based lookup was considered and dropped — the real
  Green Invoice `Search Clients` endpoint's documented filter fields (`name`, `contactPerson`,
  `email`, `labels`, `active`) never include `taxId`, so it's unconfirmed the API even supports
  it; name-only lookup is sufficient for this feature's scope. Read-only — no approval wait
  (REQ-CLIENT-008).
- **REQ-CLIENT-003**: When a name lookup matches more than one client, system MUST list the
  candidates and ask the user to disambiguate rather than silently acting on the first match.
- **REQ-CLIENT-004**: System MUST allow updating any of the four in-scope fields (`name`,
  `email`, `phone`, `tax_id`) of an existing client record — all editable, no field treated as
  immutable post-creation. No individual field is mandatory for an update request beyond
  providing at least one field to change.
- **REQ-CLIENT-005**: **Deferred / out of scope.** No `delete_client` tool is introduced by this
  feature (see Clarifications). A future feature will define delete semantics (hard-delete vs.
  archival, interaction with historical invoices) separately.
- **REQ-CLIENT-006**: All client-management tools MUST be reachable only through the existing
  Feature 018 RBAC gate (godfather/admin) — no new RBAC code path, no client-role or blocked-role
  access, achieved simply by adding/changing tools on the same already-gated Morning MCP server.
- **REQ-CLIENT-007**: For `update_client`, system MUST resolve *which* client the request refers
  to unambiguously (per REQ-CLIENT-003) before presenting the approval prompt required by
  REQ-CLIENT-008 — never act on, or ask approval for, an inferred guess. For `add_client`,
  **no proactive duplicate-check is performed** (**resolved, analysis 2026-07-29**: a "try and
  fail" approach was chosen over pre-checking for an existing same-name/same-tax-ID client) —
  the creation attempt proceeds normally, and if Morning's real API itself rejects it as a
  duplicate (or any other reason), that rejection MUST be surfaced to the user clearly (via the
  existing friendly-error mapping) so they're aware and can decide what to do next — never
  silently swallowed or misreported as success.
- **REQ-CLIENT-008**: **Every** client-mutating action — `add_client` (create) **and**
  `update_client` — MUST wait for explicit user approval (free-form yes/no reply, same
  affirmative-phrase interpretation as Feature 022: "yes"/"כן"/"אישור"/"בסדר"/"go ahead", anything
  else = decline) before executing against the Morning sandbox/production API. **This explicitly
  supersedes Feature 022's decision to exempt `add_client`** as a non-financial, no-wait action —
  that exemption is reversed as part of this feature. Only `list_clients`/`get_client_details`
  (read-only) remain immediate.
- **REQ-CLIENT-009**: **Resolved — out of scope.** Client deletion is not part of this feature and
  has no requirement here. It should be raised as its own future feature if/when prioritized
  (distinct from `specs/backlog/027-mandatory-client-reference-invoicing/`, which is unrelated —
  that spec covers invoice-side client referencing, not client deletion).
- **REQ-CLIENT-010**: **Resolved.** `tax_id` is editable via `update_client` exactly like any
  other in-scope field (`name`, `email`, `phone`) — no special immutability rule.
- **REQ-CLIENT-011**: Invoice-creation tools (`create_invoice`, etc.) MUST NOT be changed by this
  feature — they continue to accept/pass a free-text client name exactly as today. (A future,
  separate feature — `specs/backlog/027-mandatory-client-reference-invoicing/` — will address
  requiring an existing client record for invoice creation.)
- **REQ-CLIENT-012**: `name`, `email`, and `phone` are ALL mandatory for client creation
  (`add_client`). If the user's request omits any of these three, the AI MUST ask the user for
  the missing field(s) before proceeding to the approval prompt (REQ-CLIENT-008) or the actual
  tool call. `tax_id` remains optional at creation.
- **REQ-CLIENT-013**: `address` (and every other field the real Green Invoice API supports beyond
  `name`/`email`/`phone`/`tax_id` — `mobile`, `city`, `zip`, `country`, `contactPerson`, bank
  details, `labels`, `paymentTerms`, `category`/`subCategory`) is explicitly **out of scope**: not
  exposed as a parameter on any tool this feature builds or changes.
- **REQ-CLIENT-014**: As part of this feature's implementation, the stale docstring/assumption in
  `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`'s `_build_add_client_payload` claiming
  `phone` "does not appear anywhere in the Postman collection's client schemas/examples" MUST be
  corrected — `phone` is a confirmed, real, supported field (distinct from `mobile`), verified
  against the checked-in Postman collection's own "Search Clients" example response.
- **REQ-CLIENT-015**: `email` MUST be format-validated client-side (rejecting malformed input with
  a friendly error) before any client-creating/updating tool call or approval prompt is issued —
  mirroring Morning's own documented server-side validation (`errorCode 1102`/`1120`).
- **REQ-CLIENT-016**: `phone` MUST be normalized to Israeli local dashed format (`0XX-XXXXXXX`)
  before being sent to Morning, accepting common input variants (with/without `+972`, with/without
  separators) and rejecting input that doesn't resolve to a plausible Israeli phone number. No
  Morning-side format rule exists to mirror (confirmed via the full error-code catalog) — this is
  an app-level normalization choice, not a server-mirrored validation.
- **REQ-CLIENT-017**: A real Morning-sandbox test MUST create a client with a phone number and
  then independently read it back (via `get_client_details`) to verify the normalized value is
  actually persisted and returned by Morning — not just that the request payload was well-formed.
  The same round-trip verification applies when `update_client` changes a phone number.
- **REQ-CLIENT-018**: The internal Morning `client_id` (UUID) MUST NEVER be included in any
  Hebrew reply shown to the WhatsApp user — not in `list_clients`, `get_client_details`,
  `add_client`, or `update_client` confirmations/output. **Correction to existing code**:
  `tools.py`'s current `add_client` (built in Feature 005) returns
  `f"נוצר לקוח חדש: {name} (מזהה: {client_id})"`, which **does** expose it — this MUST be fixed
  as part of this feature (drop the `(מזהה: ...)` suffix) even though `add_client` itself isn't
  otherwise being rewritten from scratch.

### Key Entities

- **Client**: a Green Invoice CRM customer record, scoped in this feature to exactly four fields.
  Attributes: `name` (required at creation, mutable), `email` (required at creation, mutable),
  `phone` (required at creation, mutable — confirmed real/supported, see REQ-CLIENT-014),
  `tax_id` (optional at creation, mutable), `client_id` (system-assigned, immutable). `address`
  and every richer field the real API supports are explicitly not modeled by this feature (see
  REQ-CLIENT-013). May have zero or more linked invoices/documents (Feature 018/020/021) —
  irrelevant to this feature since deletion (the only operation where that would matter) is out
  of scope.

---

## Technology Choice: Morning MCP Server Extension (no new technology)

- **Decision Date**: July 29, 2026
- **Decision**: implement `list_clients`, `get_client_details`, `update_client` as additional
  tools on the existing FastMCP server in `apps/morning-mcp-app/`, and bring the existing
  `add_client` tool under the same approval-gate mechanism as document creation (REQ-CLIENT-008)
  — following the exact pattern of the 11 tools already there (same `MorningClient` HTTP wrapper,
  same `BearerTokenMiddleware`, same streamable-HTTP transport). No `delete_client` tool (out of
  scope).
- **Rationale**: Feature 018 already proved the remote-MCP-tool + RBAC-gating architecture
  end-to-end; adding tools to an existing, already-integrated server requires no new
  infrastructure, no `apps/denidin-app` code changes, and no new integration test harness beyond
  what `tests/expensive/e2e_helpers.py` already provides.
- **Alternatives Considered**: a separate CRM microservice — rejected as unnecessary duplication
  for what the Green Invoice API already models as `/clients`. A denidin-side cache/mirror of
  client records — rejected; Morning remains the single source of truth, consistent with how
  invoices are already handled (no local invoice mirror exists either).
- **Migration Path**: none needed; this is additive to an existing, stable integration point.

## Technology Choice: Email/Phone Validation

- **Decision Date**: July 29, 2026
- **Decision**: validate `email` using `email-validator`/pydantic `EmailStr` (already a declared
  dependency in `apps/morning-mcp-app/requirements.txt`, already used by the read-side
  `Client.email` model, but currently unused by any write path — this feature is what puts it to
  use). Normalize `phone` to Israeli local dashed format (`0XX-XXXXXXX`) via a small hand-rolled
  normalizer — no new library.
- **Rationale**: Email validation mirrors Morning's own documented, confirmed server-side rule
  (errorCode 1102/1120) — client-side pre-validation gives a friendly, immediate error instead of
  a round trip to the real API. Phone has no Morning-side rule to mirror, so a minimal
  purpose-built normalizer (regex-based, similar spirit to the existing
  `apps/denidin-app/.../user_manager.py:_normalize_phone`, though for a different purpose/format)
  is proportionate — a full `phonenumbers` dependency would be overkill for a single-country
  (Israel) use case.
- **Alternatives Considered**: `phonenumbers` library for phone (rejected — new dependency,
  general international parsing not needed here since Morning/denidin's userbase is Israel-only).
  No phone validation at all (rejected — user explicitly asked for phone to be validated and
  normalized).
- **Migration Path**: if international clients are ever needed, swap the hand-rolled normalizer
  for `phonenumbers` behind the same function signature.

---

## Assumptions

- **Resolved in Phase 0 research** (`research.md` Decisions 1–3): the Green Invoice API exposes
  `POST /clients/search` (list, name-based lookup, and detail — its `items` are already full
  records, so no separate GET-by-id call is needed) and `PUT /clients/{id}` (update) beyond the
  `POST /clients` already wrapped by `MorningClient.add_client`. `PUT`'s **partial-payload**
  behavior (only changed fields) is assumed from a Postman example but not yet empirically
  confirmed for this feature's four fields — that confirmation happens at Phase 1 RED (tasks.md
  T018a), not here.
- No new RBAC role or permission tier is introduced; this feature rides entirely on Feature 018's
  existing godfather/admin gating.
- Client-management tools require **real Morning sandbox** integration tests per the
  ZERO-MOCKING/CONSTITUTION §I/§V rule — no `unittest.mock` of the Green Invoice API.
- The approval-gate mechanism itself (pending-action state, affirmative-phrase interpretation,
  decline handling) already exists from Feature 022 and is being *extended* to cover
  `add_client`/`update_client`, not built from scratch — Phase 0 research should confirm it can
  be reused as-is or identify what needs generalizing (today it's scoped to document-creating
  tools only).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A godfather/admin WhatsApp user can list all their Morning clients in a single
  conversational turn without needing to know any API terminology or identifiers.
- **SC-002**: A godfather/admin WhatsApp user can retrieve any field of a specific client (found
  by name or tax ID) in a single conversational turn, with ambiguous matches resolved through one
  clarifying follow-up rather than a wrong guess.
- **SC-003**: 100% of client-management actions attempted by a `client`-role or `blocked`-role
  WhatsApp user are inaccessible (no tool available to invoke) — zero new RBAC bypass surface.
- **SC-004**: Zero client-management actions execute against the wrong client record when a name
  lookup is ambiguous (always disambiguates first).
- **SC-005**: 100% of `add_client`/`update_client` actions wait for an explicit user confirmation
  turn before any change reaches the Morning sandbox/production API — zero silent creates/updates.
- **SC-006**: A user who declines a create/update confirmation sees no change land in Morning and
  receives a clear acknowledgement that the action was cancelled.
- **SC-007**: 100% of client-creation requests missing `name`, `email`, or `phone` result in the
  AI asking for the missing field(s) — zero creation attempts proceed (or reach the approval
  prompt) with any of these three fields absent.
- **SC-008**: 100% of client-management replies (list/view/add/update) contain zero occurrences
  of the internal Morning `client_id` — verified by asserting the raw UUID never appears in any
  reply text across all real-sandbox and E2E tests for this feature.
