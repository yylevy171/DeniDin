# Phase 0 Research: Client Management (Feature 026)

All research below was done against evidence already checked into this repo (Postman collection,
error-code catalog, existing code) — no live network calls were made during specification/
planning. One item is flagged as needing empirical sandbox confirmation during Phase 1 (TDD RED
phase), not resolved here.

---

## Decision 1: Green Invoice `/clients` endpoints to use

- **Decision**: `POST /clients/search` (list + name-based lookup + detail — its `items` are
  already full records, confirmed via the Postman example, so no separate GET-by-id call is
  needed anywhere), `PUT /clients/{id}` (partial update). `POST /clients` (`add_client`) already
  exists.
- **Rationale**: confirmed directly from the Postman collection checked into the repo
  (`specs/done/v0.0.1/005-mcp-morning-green-receipt/Green Invoice Public API.postman_collection.json`),
  which contains real example requests/responses for `Add Client`, `Get Client`, `Update Client`,
  `Delete Client`, `Search Clients`, `Associate Existing Documents to a Client`, `Merge Clients`,
  and `Change Client Balance`. `Get Client` (GET by id) exists in Green Invoice but this feature
  never calls it — every tool resolves by name via Search Clients, and search results already
  carry full record detail, making a follow-up GET redundant. Delete, associate-documents, merge,
  and balance are all out of scope per spec.md.
- **Alternatives Considered**: `GET /clients` (a bare list-all endpoint) does not appear in the
  collection at all — `Search Clients` (`POST /clients/search`) is the only listing mechanism
  Green Invoice exposes, so `list_clients` is implemented as a `search_clients` call with an
  empty/unfiltered payload, not a distinct endpoint. A dedicated `get_client(id)` wrapper for
  `GET /clients/{id}` — rejected as unused/premature: nothing in this feature's tool set ever has
  a bare `client_id` without having just resolved it via search (which already returns full
  detail), so adding the method would be dead code.

## Decision 2: Real client field schema (confirmed via Postman examples)

- **Decision**: the full real schema is: `id`, `name`, `active` (bool), `send` (bool), `taxId`,
  `accountingKey`, `paymentTerms`, `address`, `city`, `zip`, `country`, `category`/`subCategory`,
  `emails` (array), `phone`, `mobile`, `bankName`/`bankBranch`/`bankAccount`, `labels` (array),
  `contactPerson`, `incomeAmount`/`paymentAmount`/`balanceAmount` (computed), `creationDate`/
  `lastUpdateDate` (unix timestamps), `self` (bool). Feature 026 intentionally scopes to exactly
  four settable fields: `name`, `email` (singular, mapped to `emails: [str]`), `phone`, `taxId`.
- **Rationale**: verified from the "Add Client" request body example, the "Get Client"/"Search
  Clients" response examples, and the "Update Client" request/response pair — all in the same
  Postman collection file. See spec.md Clarifications round 2 for the scope-narrowing decision
  and rationale (deliberately minimal, not a schema limitation).
- **Alternatives Considered**: supporting the full schema now — rejected by the user (spec.md
  round 2) to keep this feature's surface small; tracked as available future scope if ever needed.
- **Correction surfaced**: `tools.py`'s existing `_build_add_client_payload` docstring incorrectly
  claims `phone` doesn't appear in the Postman collection at all. It does (in the Search Clients
  example, distinct from `mobile`) — REQ-CLIENT-014 requires this comment be fixed.

## Decision 3: `PUT /clients/{id}` partial-update semantics

- **Decision**: assume `PUT /clients/{id}` accepts a **partial** payload (only the fields being
  changed), matching the Postman "Update Client" example (`{"category": 6, "subCategory": 601}` —
  a two-field body, not a full record). This assumption drives `update_client`'s design (build a
  payload containing only the fields the user actually asked to change).
- **Rationale**: it's the only real example available; a PUT that required the full record would
  make partial updates impossible without a preceding GET, which the example doesn't show being
  done.
- **NOT YET EMPIRICALLY CONFIRMED for this feature's four fields** (`name`/`email`/`phone`/
  `tax_id`) — Phase 1's RED-phase sandbox test for `update_client` must confirm a single-field
  partial payload (e.g. `{"phone": "..."}`) actually changes only that field and leaves the rest
  of the record untouched, before the GREEN-phase implementation is written. If this assumption
  is wrong, `update_client` must instead GET-then-merge-then-PUT (higher-risk change, would need
  re-approval of the test plan).

## Decision 4: Email validation — `email-validator` / pydantic `EmailStr`

- **Decision**: validate `email` using `email-validator` (already declared in
  `apps/morning-mcp-app/requirements.txt`, currently unused by any write path) via pydantic's
  `EmailStr`, matching the existing read-side `Client.email: Optional[EmailStr]` in `models.py`.
- **Rationale**: Green Invoice documents real server-side email validation in its error-code
  catalog (`specs/done/v0.0.1/005-mcp-morning-green-receipt/artifacts/error_codes.json`): `1102`
  ("כתובת מייל לא תקינה" — invalid email address) and `1120` ("כתובת הדומיין של המייל לא תקינה" —
  invalid email domain). Client-side pre-validation mirrors this and fails fast (friendly Hebrew
  error, no network round-trip) instead of surfacing a Morning 400 after the fact.
- **Alternatives Considered**: a hand-rolled regex — rejected, `email-validator` is already a
  project dependency and already the established pattern (`models.py`), no reason to duplicate.

## Decision 5: Phone normalization — hand-rolled Israeli-format normalizer

- **Decision**: normalize `phone` to Israeli local dashed format (`0XX-XXXXXXX`, e.g.
  `054-1234567`) via a small regex-based function; accept `+972`-prefixed, no-prefix, dashed, or
  undashed input; reject anything that doesn't resolve to a plausible Israeli number (wrong digit
  count, non-Israeli country code).
- **Rationale**: Green Invoice's error-code catalog documents **no** phone-format validation
  error anywhere (confirmed by scanning all ~90 documented codes) — there is no server-side rule
  to mirror, so this is a deliberate app-level policy (spec.md Clarifications round 2, user
  decision). The Postman collection's own examples are internally inconsistent about
  separator style (`0527384938` in one client example, `054-1234567` in a business example) —
  the dashed form was chosen as the canonical output since it's the more human-readable of the two
  and matches at least one real example verbatim.
- **Alternatives Considered**: `phonenumbers` library (E.164 international) — rejected, new
  dependency for a single-country (Israel-only) use case is disproportionate; no normalization at
  all — rejected, the user explicitly asked for phone to be validated/normalized.

## Decision 6: Approval-gate extension mechanism

- **Decision**: reuse Feature 022's existing mechanism verbatim — add `"update_client"` (and move
  `"add_client"`) into the tool-name list passed as `require_approval.always.tool_names` on the
  Morning MCP tool's Responses-API registration (`ai_handler.py:537-551`); no new code, no new
  state machine.
- **Rationale**: confirmed the gate is implemented at the OpenAI Responses API level
  (`require_approval` parameter, which makes OpenAI itself withhold execution and return an
  `mcp_approval_request` output item) plus `PendingApprovalManager`
  (`apps/denidin-app/src/managers/pending_approval_manager.py`, in-memory, one pending approval
  per `chat_id`) — both already built and working for the six `DOCUMENT_CREATING_MCP_TOOLS`.
  Extending coverage to two more tool names is a one-line change to an existing tuple, not new
  infrastructure.
- **Alternatives Considered**: a denidin-app-level pending-state check specific to client tools —
  rejected, would duplicate `PendingApprovalManager` for no benefit; the existing mechanism is
  tool-name-based already and doesn't care what kind of tool it's gating.
- **Naming note**: `DOCUMENT_CREATING_MCP_TOOLS`/`NON_DOCUMENT_CREATING_MCP_TOOLS` are imprecise
  once client-record tools are added (they don't create Morning *documents*). Renaming to
  `APPROVAL_REQUIRED_MCP_TOOLS`/`NO_APPROVAL_MCP_TOOLS` is in scope since both tuples are already
  being edited by this feature (see plan.md Project Structure).

## Decision 7: Client disambiguation — code-level, not prompt-only

- **Decision**: `get_client_details`/`update_client` resolve a client by name via a shared
  `_resolve_client_by_name` helper that calls `search_clients` and handles 0/1/many results in
  code (not-found / resolved / ambiguous-list), rather than relying solely on the model to
  disambiguate conversationally.
- **Rationale**: matches spec.md REQ-CLIENT-003/007 exactly (never act on an inferred guess) and
  gives a real, testable guarantee — the existing invoice_id-resolution guidance in
  `runtime_constitution.md` (lines 160-163) is a *prompt-level* convention with no code-level
  enforcement for invoices; client-management chooses to add the stronger code-level guarantee
  since ambiguity here would otherwise let OpenAI's `require_approval` gate trigger a pending
  approval for update **before** disambiguation could happen (the gate fires purely on tool name,
  not argument validity) — so the tool itself must refuse to proceed on ambiguous input rather
  than trusting the model never to call it that way.
- **Alternatives Considered**: prompt-only disambiguation (mirroring the invoice pattern exactly)
  — rejected as insufficient here specifically because of the approval-gate ordering risk above.

## Decision 8: Search-index eventual consistency (discovered during Phase 2 implementation)

- **Finding**: the real Green Invoice sandbox's `POST /clients/search` index lags briefly after
  a `POST /clients` write — a client created via `add_client` is not immediately findable via
  `search_clients`, confirmed empirically (2026-07-29): a search performed <1s after creation
  returned zero matches; the same search a couple of seconds later found it.
- **This is the exact same class of issue already known and handled for documents** in this repo
  — see `test_morning_sandbox_invoices_crud.py`'s `test_search_invoice_by_fields` (poll up to
  12×1.5s / 18s before giving up, widened from an earlier, flakier 6×1s window under load).
- **Decision**: any real-sandbox test that creates a client and then immediately searches for it
  by name (`get_client_details`/`update_client` round-trip verification, REQ-CLIENT-017, and any
  `_resolve_client_by_name` usage right after a fresh `add_client` in the same test) MUST use the
  same poll-retry pattern (`test_morning_sandbox_list_clients_tool.py` now does this) rather than
  a single immediate search — applies to Phase 3/4/5's tests (T009a, T013a, T018a, T022a).
- **Not a production code fix**: this is a test-infrastructure concern only. In real WhatsApp
  usage, a human is very unlikely to ask about a client within ~1-2 seconds of creating it, so
  no retry/wait logic is added to `tools.py` itself.

## Decision 9: `models.Client` taxId mapping bug (discovered during Phase 3 implementation)

- **Finding**: `models.Client` (built Feature 005) declares a `tax_id` field but its
  `_map_morning_client_shape` validator only ever mapped `emails` → `email` — it never mapped
  Morning's real `taxId` (camelCase) → `tax_id`. Since nothing before Feature 026 ever called
  `Client.model_validate()` on a real response (only `response.get("id", "")` was read directly),
  this bug was latent and unnoticed until `get_client_details`'s real-sandbox test asserted on
  `tax_id` and got `None`.
- **Decision**: fixed the same validator to also map `taxId` → `tax_id` (mirrors the existing
  `emails` → `email` mapping style, and the `documentDate` → `document_date` pattern already used
  by `LinkedDocument`). Scope limited to `tax_id` only — `creationDate`/`created_at` has the same
  latent gap but is not required by any Feature 026 requirement or test, so left unfixed to avoid
  scope creep.
- **Also observed**: Morning lowercases email addresses server-side; tests comparing email
  values do so case-insensitively rather than assuming case preservation.

## Decision 10: F2 "try and fail" duplicate-name behavior (confirmed empirically, Phase 4)

- **Finding**: the real Green Invoice sandbox does **not** reject `POST /clients` for a name that
  already exists — `test_add_client_tool_second_call_with_same_name_is_try_and_fail` (real
  sandbox) confirmed that creating a second client with the exact same `name` (different
  email/phone) succeeds and produces a genuinely distinct second record (both found via
  `search_clients`, two items).
- **Decision**: no code change needed — this confirms REQ-CLIENT-007/F2's "try and fail" design
  is already correct as built: `add_client` has no proactive duplicate-check, and since Morning
  itself doesn't reject same-name creates, there is nothing to surface as an error in this case.
  If Morning ever adds server-side duplicate rejection in the future, it would surface through the
  same generic exception → `server.py`'s `_call_with_error_boundary` path already exercised by the
  malformed-email/implausible-phone tests — no special-case handling required.
- **Scope note (2026-07-30, user decision)**: only name-duplication was empirically tested per
  explicit user instruction ("add the test, but for name only - don't care for tax id") —
  duplicate-tax_id behavior remains unconfirmed and is not required by any Feature 026
  requirement.

## Decision 11: `list_clients` single-page limitation actually manifested (2026-07-30)

- **Finding**: `test_list_clients_includes_seeded_clients` failed on a post-merge full-suite run
  — the sandbox has accumulated 30+ test clients from this feature's own repeated test runs
  today, and `list_clients`'s unfiltered `search_clients({})` call only returns Morning's default
  first page, which no longer reliably includes the most-recently-created pair. Reproduced twice
  (not a transient flake).
- **Decision**: this is the single-page limitation already called out and explicitly accepted in
  data-model.md ("pagination fields beyond page 1 are not needed at this feature's scale, mirrors
  `list_invoices`' existing single-page assumption") — not a regression from this session's work
  (`list_clients`'s implementation is untouched by the master merge). No production code change
  made. Flagged here rather than silently ignored, since it's now an observable test failure, not
  just a theoretical gap — a future feature adding real pagination support (or a test-data cleanup
  mechanism for the shared sandbox) would resolve it, but is out of scope for Feature 026.

## Decision 13: pending-approval fallback message must use the approval's own arguments (2026-07-30)

- **Finding**: `test_godfather_update_client_discloses_family_name_prefix_match_before_approval` failed on
  first run - the model correctly resolved a partial client reference via `get_client_details` first
  (per this feature's own new constitution guidance) and correctly passed the resolved full name into
  `update_client`'s pending-approval arguments, but produced no narrating text of its own that turn.
  `ai_handler.py`'s existing (pre-Feature-026, Feature 022) fallback for exactly this case was a fully
  generic "there's a pending action, reply yes" string that ignored the pending approval's own
  `arguments` - even though those arguments already contained the resolved client name.
- **Decision**: added `_build_pending_approval_fallback_text(tool_name, arguments_json)` to
  `ai_handler.py` - builds a tool-specific fallback message from the pending approval's own arguments
  for all 8 tools in `APPROVAL_REQUIRED_MCP_TOOLS`, falling back to the original fully generic text on
  any parsing issue or unrecognized tool name. `create_credit_note`/`create_receipt`/
  `close_transaction_account` (keyed by `original_invoice_id`, a raw internal UUID) never include that
  id in the fallback - only the action name plus any safe fields present (amount) - per the existing
  "never ask for or mention invoice_id" rule.
- **Scope**: this is a shared Feature-022 mechanism fix, not Feature-026-specific, but the user
  explicitly requested it be fixed for all 8 tools once the gap was found via this feature's own new
  disclosure test. Verified via 14 new unit tests (`test_ai_handler_pending_approval_fallback.py`) plus
  the real E2E test that originally caught it.

## Outstanding item for Phase 1 RED phase

- Decision 3 (partial-update semantics) is the only unconfirmed assumption. The first
  `update_client` sandbox test must empirically verify it before the GREEN-phase implementation
  is trusted.
