# Tasks: Client Management (Morning/Green Invoice CRM Clients) — Feature 026

**Spec**: `./spec.md` · **Plan**: `./plan.md` · **User stories**: `./user-stories.md`
**Apps**: `apps/morning-mcp-app/` (primary) + `apps/denidin-app/` (approval-gate tuples +
runtime constitution + E2E tests only — no new denidin-app module)
**Branch**: `026-client-management`

## Conventions

- Task ID `T###`. `[P]` = parallelizable (different files, no dependency on an incomplete task).
- **TDD gate (METHODOLOGY §VI)**: the test task (`a`) is written first, must **fail** (RED), and
  needs **explicit human approval** before the implementation task (`b`). Approved tests are
  **immutable** (CONSTITUTION §VIII) — one explicit, spec-approved exception below (T016a).
- **Two-tier testing** (mirrors this repo's actual existing pattern, e.g.
  `tests/unit/test_tools_document_creation.py`'s `_FakeMorningClient` + the real
  `tests/integration/test_morning_sandbox_*.py` suite): fast unit tests with a fake `MorningClient`
  double for pure business logic (resolution, validation, payload-building — allowed per
  CONSTITUTION §I/§V, which permits mocking *external* services, not internal components), plus
  slower **real Morning-sandbox** integration tests (no mocks) proving the actual wire contract,
  plus real-API E2E tests (`apps/denidin-app`, `@pytest.mark.expensive`) through the real Green
  API webhook router for RBAC/approval-gate behavior.
- **Expensive-test discipline (CLAUDE.md)**: human approval before **every** run of anything under
  `apps/denidin-app/tests/expensive/`, one at a time, never a bare `-m expensive` sweep, read
  `logs/test_logs/` before re-running.
- **Environment-start discipline (CLAUDE.md)**: any manual-approval-gate task that needs a running
  dev environment requires separate, explicit approval to start it — never assumed from a prior
  approval in this task list.
- **Search-index eventual consistency (discovered during Phase 2, research.md Decision 8)**: any
  real-sandbox test that creates a client and then immediately searches/resolves it by name
  (T009a, T013a, T018a, T022a) MUST poll (12×1.5s, mirroring
  `test_morning_sandbox_invoices_crud.py`'s existing pattern for documents) rather than searching
  once — the sandbox's search index lags briefly after a write. Not a production-code concern.
- Paths relative to `apps/morning-mcp-app/` or `apps/denidin-app/` as stated per task.

---

## Phase 1 — Foundation (shared building blocks, no user-facing behavior yet)

- [x] **T001** [P] Add `MorningClient.search_clients(payload: dict) -> dict` (`POST
  /clients/search`) and `MorningClient.update_client(client_id: str, payload: dict) -> dict`
  (`PUT /clients/{id}`) in `apps/morning-mcp-app/src/denidin_mcp_morning/morning_client.py` —
  mirrors the existing `add_client`/`get_invoice` method style (same file, ~line 94).
- [x] **T002a** Write unit tests (fake `MorningClient`, per `_FakeMorningClient` pattern) for a
  new `_resolve_client_by_name` helper in
  `apps/morning-mcp-app/tests/unit/test_tools_client_management.py`: 0 matches → not-found
  sentinel; 1 match → resolved `Client`; >1 matches → ambiguous sentinel carrying all candidates.
- [x] **T002b** Implement `_resolve_client_by_name` in
  `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` (calls `MorningClient.search_clients`)
  (BLOCKED until T002a approved).
- [x] **T003a** [P] Write unit tests for `_validate_email`/`_normalize_israeli_phone` in the same
  `test_tools_client_management.py`: valid/malformed email formats (`EmailStr` behavior); phone
  variants (`+972501234567`, `0501234567`, `050-123-4567`, `0501234567` with/without dashes) all
  normalize to `050-1234567`; digit counts/prefixes that don't resolve to a plausible Israeli
  number are rejected (`ValueError`).
- [x] **T003b** Implement `_validate_email` (thin wrapper around pydantic `EmailStr`/
  `email-validator`, matching `models.py`'s existing `Client.email` pattern) and
  `_normalize_israeli_phone` in `tools.py` (BLOCKED until T003a approved).
- [x] **T004** [P] Rename `DOCUMENT_CREATING_MCP_TOOLS` → `APPROVAL_REQUIRED_MCP_TOOLS` and
  `NON_DOCUMENT_CREATING_MCP_TOOLS` → `NO_APPROVAL_MCP_TOOLS` in
  `apps/denidin-app/src/handlers/ai_handler.py` (pure rename, tuple *contents* unchanged for now
  — `add_client` stays in the no-approval tuple until T014). Verify zero regression by re-running
  the existing approved expensive E2E suite **(needs its own explicit human approval to run, per
  CLAUDE.md — not implied by this task)**.

**Checkpoint**: client-resolution, validation/normalization, and the renamed (but not yet
content-changed) approval tuples are ready. No user-facing behavior has changed yet.

---

## Phase 2 — User Story 1: List clients (Priority: P1) 🎯 MVP

**Goal**: godfather/admin lists existing Morning clients via natural WhatsApp language, read-only,
no approval wait.

**Independent Test**: seed a client via the existing `add_client`, ask "מי הלקוחות שלי?", confirm
the reply contains its name.

- [x] **T005a** [P] [US1] Write real-sandbox integration test
  `apps/morning-mcp-app/tests/integration/test_morning_sandbox_list_clients_tool.py`: seed 2+
  clients, call `list_clients`, assert both names appear; zero-clients edge case returns a
  friendly message, not an error; **assert the raw `client_id` never appears in the output**
  (REQ-CLIENT-018). *(Discovered search-index eventual-consistency lag — see research.md
  Decision 8 — fixed with a 12×1.5s poll, same pattern as the existing invoice tests.)*
- [x] **T005b** [US1] Implement `tools.list_clients` (uses `MorningClient.search_clients`) +
  `formatters.format_client_list` (mirrors `format_invoice_list`) (BLOCKED until T005a approved).
- [x] **T006** [US1] Register `@mcp.tool() list_clients` in
  `apps/morning-mcp-app/src/denidin_mcp_morning/server.py`.
- [x] **T007a** [US1] Write real-API E2E test in
  `apps/denidin-app/tests/expensive/test_denidin_morning_mcp_e2e.py`: godfather asks "מי הלקוחות
  שלי" → `list_clients` `mcp_call` with no error, **no** pending approval created, reply contains
  the seeded name(s). *(Test written as `test_godfather_lists_clients_via_whatsapp`; includes a
  3s sleep before the list turn per research.md Decision 8 — cost-free local wait vs. retrying a
  billed conversational turn.)*
- [x] **T007b** [US1] Verify GREEN — **PASSED** (2026-07-30, real OpenAI billing, explicit
  approval given). Required a `morning-mcp-app-dev` container rebuild first (was serving stale
  pre-Feature-026 code); confirmed `list_clients` correctly covered by `NO_APPROVAL_MCP_TOOLS`.
- [ ] **T008** [US1] 👤 **MANUAL APPROVAL GATE**: run `quickstart.md`'s US1 scenario for real
  (needs explicit approval to start the dev environment and to run the expensive E2E test).

**Checkpoint**: User Story 1 fully functional and independently deployable (MVP).

---

## Phase 3 — User Story 2: View a specific client's details (Priority: P1)

**Goal**: godfather/admin retrieves one client's full record by name, read-only, no approval wait,
with disambiguation on ambiguous name matches.

**Independent Test**: seed a known client, ask for its details by name, confirm the reply
contains its tax_id; seed two similarly-named clients, confirm the shared-substring query
produces a disambiguation list instead of picking one.

- [x] **T009a** [P] [US2] Write real-sandbox integration test
  `test_morning_sandbox_get_client_details_tool.py`: positive (seeded client → full detail
  including phone/email/tax_id, **but never the raw `client_id`** — REQ-CLIENT-018); not-found
  (no match → friendly message); ambiguous (2 seeded similarly-named clients → candidate list,
  **showing each candidate's tax_id/phone as the identifying detail that lets the user tell them
  apart — only the internal `client_id` is forbidden, not legitimate business identifiers**);
  **lookup is name-only** (tax-ID lookup was considered and dropped — F1, spec.md
  REQ-CLIENT-002). *(Also fixed a latent Feature-005 bug found via this test: `models.Client`
  never mapped Morning's `taxId` → `tax_id`, so `tax_id` silently came back `None` on every real
  parse until now.)*
- [x] **T009b** [US2] Implement `tools.get_client_details` (uses `_resolve_client_by_name`) +
  `formatters.format_client_details` (mirrors `format_invoice_details`) (BLOCKED until T009a
  approved).
- [x] **T010** [US2] Register `@mcp.tool() get_client_details` in `server.py`.
- [x] **T011a** [US2] Write real-API E2E test: godfather asks for a known client's details →
  positive; unknown name → friendly not-found reply. *(Ambiguous-name E2E scenario deferred —
  already covered at the unit level; not duplicated at the expensive-test tier to limit billed
  test count.)*
- [x] **T011b** [US2] Verify GREEN — **PASSED** (2026-07-30, real OpenAI billing, explicit
  approval given, as part of the end-of-feature batch run).
- [ ] **T012** [US2] 👤 **MANUAL APPROVAL GATE**: `quickstart.md` US2 scenario (needs explicit
  run approval).

**Checkpoint**: US1 + US2 both work independently — the full read-only slice is complete.

---

## Phase 4 — User Story 3: Add a client — now approval-gated, 3 fields mandatory (Priority: P2)

**Goal**: `add_client` requires `name`/`email`/`phone` (no `address`), validates/normalizes email
and phone client-side, and now waits for explicit approval before executing — reversing Feature
022's exemption.

**Independent Test**: two-turn conversation (request → confirm) creates a real sandbox client
whose phone reads back normalized.

- [x] **T013a** [P] [US3] Update `test_morning_sandbox_add_client_tool.py`: name/email/phone each
  individually omitted → rejected before any network call (`ValueError`); malformed email
  rejected before any network call; phone in various input formats normalizes to
  `0XX-XXXXXXX` **and round-trips on read-back via a follow-up search** (REQ-CLIENT-017,
  correcting the stale "phone is ignored" assumption — REQ-CLIENT-014); calling with an `address`
  kwarg is a `TypeError` (proves REQ-CLIENT-013 — no longer a parameter at all); `tax_id` stays
  optional; existing invalid-tax_id server-side checksum test (`errorCode 1111`) unchanged;
  **creating a client with a name/tax_id that already exists is attempted with no proactive
  check** (F2 — "try and fail") and whatever Morning's real API does (second record created, or a
  rejection) is asserted explicitly, not assumed; **the returned confirmation string never
  contains the raw `client_id`** (REQ-CLIENT-018 — this is also a regression check, since the
  existing code currently includes it).
- [x] **T013b** [US3] Update `tools.add_client`/`server.py`'s `add_client` tool signature: drop
  `address` parameter entirely, make `email`/`phone` required (no `Optional`, no default), call
  `_validate_email`/`_normalize_israeli_phone` before building the payload, fix the stale
  `_build_add_client_payload` docstring/comment claiming phone isn't in the Postman collection
  (REQ-CLIENT-014), add **no** duplicate-check logic (F2), and **drop the `(מזהה: {client_id})`
  suffix from the return string** (REQ-CLIENT-018) (BLOCKED until T013a approved).
- [x] **T014** [US3] Move `"add_client"` from `NO_APPROVAL_MCP_TOOLS` into
  `APPROVAL_REQUIRED_MCP_TOOLS` in `ai_handler.py`.
- [x] **T015** [US3] Update `apps/denidin-app/config/runtime_constitution.md`: move `add_client`
  out of the "need no confirmation" line into the approval-required block (with a Hebrew
  pending-action example, e.g. `"ליצור לקוח חדש: ... — לאשר?"`); add guidance that
  name/email/phone are all required — ask the user for any missing one rather than calling the
  tool incomplete.
- [x] **T016a** [US3] 🚨 **CONSTITUTION §VIII EXCEPTION (explicitly approved, spec.md
  Clarifications round 1)**: rewrite `test_godfather_add_client_still_single_turn`
  (`test_denidin_morning_mcp_e2e.py:505-524`) into a two-turn `_send_turn_and_approve` test
  (rename to reflect the new behavior, e.g. `test_godfather_add_client_requires_approval`); add
  scenarios: missing field → AI asks instead of calling the tool; malformed email → rejected
  before the approval prompt; decline → no client created; approved creation → verified via a
  follow-up `get_client_details` call within the same test that phone round-trips normalized.
- [x] **T016b** [US3] Verify GREEN / close any real gap found — **PASSED** (2026-07-30, all 4
  scenarios: requires-approval, missing-field, malformed-email, decline).
- [ ] **T017** [US3] 👤 **MANUAL APPROVAL GATE**: `quickstart.md` US3 scenario (needs explicit
  environment-start approval and separate explicit approval for the expensive E2E run).

**Checkpoint**: US1 + US2 + US3 all functional; `add_client`'s behavior reversal is fully verified
by both a rewritten unit/sandbox test and a rewritten E2E test.

---

## Phase 5 — User Story 4: Update a client — approval-gated (Priority: P2)

**Goal**: `update_client` changes one or more of `name`/`email`/`phone`/`tax_id` on an existing
client, resolved by name, requiring explicit approval before executing.

**Independent Test**: two-turn conversation updates a seeded client's phone; a follow-up read
confirms only that field changed.

- [x] **T018a** [P] [US4] Write real-sandbox integration test
  `test_morning_sandbox_update_client_tool.py`. **First test in this file MUST confirm the
  research.md Decision 3 assumption**: a `PUT` with only `{"phone": ...}` changes just that field
  and leaves `name`/`email`/`tax_id` on the record untouched. Then cover: each field individually
  updatable — **specifically, updating `phone` MUST be verified by reading it back via a
  follow-up search and confirming it round-trips in normalized `0XX-XXXXXXX` form**
  (REQ-CLIENT-017, same round-trip standard as T013a for create, not just "the PUT call
  succeeded"); `tax_id` editable like any other (REQ-CLIENT-010); a call with none of
  `new_name`/`email`/`phone`/`tax_id` is rejected ("nothing to update"); not-found/ambiguous name
  handled identically to US2; malformed email/phone rejected before any network call; **the
  returned confirmation string never contains the raw `client_id`** (REQ-CLIENT-018).
- [x] **T018b** [US4] Implement `MorningClient.update_client` (from T001, already exists — wire
  it) + `tools.update_client` (BLOCKED until T018a approved **and** the partial-payload
  assumption is confirmed true by that test; if false, STOP and get human re-approval for a
  revised GET-then-merge-then-PUT approach before continuing).
- [x] **T019** [US4] Register `@mcp.tool() update_client` in `server.py`.
- [x] **T020** [US4] Add `"update_client"` to `APPROVAL_REQUIRED_MCP_TOOLS` in `ai_handler.py`.
- [x] **T021** [US4] Update `runtime_constitution.md`: add `update_client` to the
  approval-required block; add client-resolution guidance mirroring the existing invoice_id
  guidance ("resolve which client via `get_client_details` first, never guess a name/id").
- [x] **T022a** [US4] Write real-API E2E test (two-turn approve pattern): positive update,
  verified via a follow-up `get_client_details` call that only the intended field changed;
  decline leaves no change; ambiguous name → disambiguation reply with **no pending-approval
  state created** for the unresolved attempt (proves research.md Decision 7's ordering concern is
  actually handled, not just theorized).
- [x] **T022b** [US4] Verify GREEN / close any real gap found — **PASSED** (2026-07-30, all 3
  scenarios: positive update + read-back verification, decline, ambiguous-name-no-pending-approval).
- [ ] **T023** [US4] 👤 **MANUAL APPROVAL GATE**: `quickstart.md` US4 scenario (needs explicit
  environment-start approval and separate explicit approval for the expensive E2E run).

**Checkpoint**: all four functional user stories complete.

---

## Phase 6 — User Story 5: RBAC denial (safety net — no new code expected)

**Goal**: confirm client-management tools are inaccessible to `client`/`blocked`-role users,
exactly like every other Morning tool (Feature 018, unchanged).

- [x] **T024a** [US5] Write real-API E2E test: a `client`-role and a `blocked`-role WhatsApp
  sender each ask about clients → assert **zero** `mcp_call`s for any of
  `list_clients`/`get_client_details`/`add_client`/`update_client`; bot still replies normally,
  no crash.
- [x] **T024b** [US5] Verify GREEN (this is existing Feature 018 RBAC gating — no new code is
  expected; this task exists to prove it, not to build anything) — **PASSED** (2026-07-30, both
  client-role and blocked-role scenarios).

**Checkpoint**: full spec covered end-to-end; the RBAC safety net is empirically confirmed, not
assumed.

---

## Phase 7 — Polish & Cross-Cutting

- [x] **T025** [P] Update `apps/morning-mcp-app/README.md`/`ARCHITECTURE.md`: document the 3 new
  tools and `add_client`'s changed contract (mandatory fields, approval-gated, no `address`).
- [ ] **T026** Run `quickstart.md`'s full manual scenario sequence in order (US1→US5) as a final
  sanity pass (needs explicit environment-start approval).
- [x] **T027** `pylint`/`mypy` pass on every changed file in both apps. (denidin-app: pylint
  8.94/10 full-suite, changed files' own diffs are comment/tuple-content only, no new mypy
  errors introduced beyond pre-existing unrelated ones, confirmed via diff review;
  morning-mcp-app has no pylint/mypy tooling configured at all - pre-existing state, not a gap
  from this feature.)
- [x] **T028** Full non-expensive `pytest tests/` pass on both apps (`-m "not expensive"`,
  already the default).

---

## Dependencies & Execution Order

- **Phase 1 (Foundation) before every user-story phase** — `_resolve_client_by_name`,
  `_validate_email`/`_normalize_israeli_phone`, and the renamed approval tuples are shared
  prerequisites (US1/US2 need the resolution+search plumbing; US3/US4 additionally need
  validation + the approval-tuple rename already done, before adding their own tool name to it).
- Within each story: test task (`a`) approved **before** implementation task (`b`).
- **T018a/b (US4) has an extra gate**: the partial-payload assumption must be confirmed true by
  T018a's first test before T018b is trusted — this is a plan-level checkpoint (research.md
  Decision 3), not just the normal TDD approval.
- T014/T015 (US3's tuple + constitution edits) before T016a (E2E rewrite needs the new behavior
  actually wired up to test against).
- T020/T021 (US4's tuple + constitution edits) before T022a, for the same reason.
- Phases 2 (US1) and 3 (US2) can proceed in parallel once Phase 1 is done (different tool
  surfaces, no shared new state). Phases 4 (US3) and 5 (US4) can also proceed in parallel once
  Phase 1 is done, though both touch `ai_handler.py`'s tuples and `runtime_constitution.md` — take
  care to merge sequentially there to avoid clobbering each other's edits.

## MVP

Phase 1 (Foundation) + Phase 2 (US1) = a godfather listing real sandbox clients from WhatsApp,
verified end-to-end via a real sandbox client and a real E2E test.

## Incremental Delivery

Foundation → US1 (MVP) → US2 (read-only slice complete) → US3 (add, with the `add_client`
behavior reversal) → US4 (update) → US5 (RBAC safety net) → Polish. Each story phase ends with a
checkpoint that leaves the feature in a shippable, independently-demonstrable state.

## Out of Scope (see spec.md §Requirements / Clarifications)

`delete_client`; `address` and any richer Green Invoice client field (`mobile`, `city`, `country`,
`contactPerson`, bank details, `labels`, `paymentTerms`, `category`); changes to invoice-creation's
client-referencing behavior (tracked separately as
`specs/backlog/027-mandatory-client-reference-invoicing/`); tax-ID-based client lookup (F1,
`/speckit.analyze` remediation — the real `Search Clients` filters don't document `taxId`
support); proactive duplicate-name/tax-ID checking before `add_client` creates a record (F2 —
"try and fail" chosen instead).

---

## Post-implementation follow-up (2026-07-30, user-requested after initial completion)

Found via manual review that `list_clients` had no real pagination handling (production accounts
can have hundreds of clients - confirmed live: 278 in the real sandbox) and that `get_client_details`/
`update_client` never disclosed when a search resolved via a non-exact (partial/prefix) match rather
than the literal stored name. Both fixed, full TDD cycle, plus 3 new expensive E2E tests:

- [x] `list_clients` reworked: optional `name` filter (server-side narrowing via Morning's real
  token-prefix search), real `total`/`pages`-based pagination (fetches all pages internally when
  under a display cap of 30, reports the real total and asks to narrow when over it - never
  silently truncates). `format_too_many_clients_message` added to `formatters.py`.
- [x] `_is_exact_name_match` helper added; `get_client_details`/`update_client` now explicitly
  disclose the resolved client's name when the match wasn't an exact (case-insensitive) copy of
  what was searched - `format_client_details(client, is_exact_match=...)` and `update_client`'s own
  confirmation string both branch on this.
- [x] `runtime_constitution.md` updated: strict-prefix-search-not-fuzzy guidance (retry with a
  shorter prefix / common Hebrew vowel-letter spelling variant on a zero-result search before
  reporting "not found"); narrow-before-asking guidance for `list_clients`'s "too many" case;
  resolve-via-`get_client_details`-first guidance for `update_client` so the pending-approval
  prompt itself names the real client, not just the user's partial wording.
- [x] Real diverse Israeli first/family name pools (565/591 unique entries - Hebrew/Jewish,
  Arab-Israeli, Russian/FSU, Ethiopian-Israeli, Western/English-transliterated) generated and
  saved to `apps/denidin-app/tests/expensive/data/hebrew_{first,family}_names.txt`, loaded by the
  new expensive tests instead of synthetic markers.
- [x] 3 new expensive E2E tests, all passing: Hebrew vowel-variant retry
  (`test_godfather_finds_client_via_hebrew_vowel_variant`), first-name-prefix disclosure
  (`test_godfather_get_client_details_discloses_first_name_prefix_match`), family-name-prefix
  disclosure before approval (`test_godfather_update_client_discloses_family_name_prefix_match_before_approval`).
- [x] **Real bug found and fixed along the way** (research.md Decision 13): the last test above
  surfaced that `ai_handler.py`'s existing (Feature 022) pending-approval fallback message was
  fully generic even when the model had already correctly resolved a specific client/amount/etc.
  into the pending tool call's own arguments. Added `_build_pending_approval_fallback_text`,
  covering all 8 tools in `APPROVAL_REQUIRED_MCP_TOOLS` (never exposing `original_invoice_id`, per
  the existing "never mention invoice_id" rule), with 14 new unit tests.
- [x] Unit tests: 54 (client-management) + 14 (fallback text) = 68 new/updated, all passing.
  Real-sandbox tests: 27, all passing (including the real 278-client "too many" scenario). Full
  non-expensive suite both apps: 563 (denidin-app) + 267 (morning-mcp-app), no regressions.
