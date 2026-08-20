# Phase 0 Research: Mandatory Client Reference for Invoicing (Feature 027)

Unlike Feature 026, this feature's key API-behavior question was answered with a **real, live
sandbox call** during specification (not from documentation alone) — per CONSTITUTION's "NO
UNVERIFIED THIRD-PARTY ASSUMPTIONS" rule. This file consolidates that finding plus everything
discovered while re-reading the actual `tools.py` implementations for this plan.

---

## Decision 1: `/documents` accepts `client.id` in place of `client.name` (confirmed live)

- **Decision**: Sending `{"client": {"self": false, "id": "<client_id>"}}` (no `name` field at
  all) in a `POST /documents` payload causes Morning to attach the document to that real client
  record, resolving name/email/phone server-side from the `id`.
- **Rationale**: Confirmed via a real sandbox round-trip, 2026-08-06: created a real client via
  `add_client` → got a real `client_id` → created a real type-305 tax invoice with only
  `{"self": false, "id": client_id}` as its `client` object → the immediate create response's
  `client` block was `{"id": client_id}` → a fresh `GET /documents/{id}` returned the **full**
  client sub-record (`id`, `name`, `phone`, `emails`) resolved server-side. Not assumed from the
  Postman collection's documentation (which shows the same shape in an example, but an example is
  not a confirmed live behavior per this repo's constitution).
- **Alternatives Considered**: None — this was a factual API-behavior question with one right
  answer to confirm, not a design choice.

## Decision 2: The 6 document-creation tools split into two mechanically distinct groups

- **Decision**: Group A (`create_invoice`, `create_transaction_account`, `create_combo_document`)
  take a free-text `client_name: str` and must **search** for a matching client. Group B
  (`create_credit_note`, `create_receipt`, `close_transaction_account`) take no `client_name` —
  they take `original_invoice_id`, already fetch that original document via `client.get_invoice`
  (to build their own payload from its line items/currency/etc.), and **already have** the
  original's `client` sub-object in hand — they just currently discard its `id` in favor of
  rebuilding `{"name": client_info.get("name")}`.
- **Rationale**: Read every one of the 6 tools' actual implementations in
  `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` directly (not assumed from the spec's
  first-draft description, which incorrectly generalized from `create_invoice`'s shape to all "5"
  tools). Concretely:
  - `_build_create_invoice_payload`/`_build_transaction_account_payload`/
    `_build_combo_document_payload` (Group A) each take `client_name: str` as a parameter and
    build `"client": {"self": False, "name": client_name}`.
  - `_build_cancellation_payload` (used by `create_credit_note`), `_build_payment_receipt_payload`
    (used by `create_receipt`), and `_build_combo_closing_payload` (used by
    `close_transaction_account`) each start with `client_info = original.get("client") or {}` and
    build `"client": {"self": False, "name": client_info.get("name")}` — note there is no
    `client_name` parameter anywhere in these three functions' signatures; `client_info` comes
    entirely from the already-fetched `original` document.
- **Alternatives Considered**: Treating all 6 uniformly by having Group B tools also call
  `_resolve_client_by_name` on `client_info.get("name")` — rejected: pointless indirection (search
  by a name to re-derive an `id` that was already sitting in the very dict being searched from),
  and strictly worse than just using the `id` already present (a name-based re-search could even
  resolve ambiguously or to the wrong client if multiple clients share that name).

## Decision 3: Group B's fix is "stop discarding `id`," not "add resolution logic"

- **Decision**: Each Group B payload-building function changes from
  `"client": {"self": False, "name": client_info.get("name")}` to checking
  `client_info.get("id")` first: if present, `"client": {"self": False, "id": client_info["id"]}`;
  if absent, the **calling tool function** (not the payload builder) refuses before ever calling
  the builder or `client.create_invoice` (REQ-INV-013) — no partial/malformed payload is ever sent.
- **Rationale**: `client_info` is exactly `original.get("client")` — whatever Morning's own `GET
  /documents/{id}` returns for that field. Per Decision 1, any document created via this feature's
  Group A fix (or a Group B tool that itself preserved an id) will have a real `id` there; any
  document created before this feature shipped will not (Decision 1's live test's `client_info`
  before the fix only ever contained `name`, since that's all the old code ever sent — Morning
  doesn't invent an `id` for a client it was never given one for).
- **Alternatives Considered**: See Decision 4 below (backward-compat).

## Decision 4: Backward compatibility — refuse, don't fall back (user decision, 2026-08-06)

- **Decision**: When a Group B tool's linked original has no `client.id` (pre-feature document),
  the tool creates no new document and returns a friendly Hebrew refusal — it does **not** fall
  back to today's bare-name behavior.
- **Rationale**: User's explicit choice when presented with both options during `/speckit.plan`.
  Falling back would silently perpetuate exactly the bug this feature exists to eliminate, just
  for older documents' descendants — an invisible exception to the feature's own guarantee.
  Refusing keeps the guarantee absolute: **no document this feature's code path ever creates or
  helps create has a bare-name-only client** — the tradeoff (older invoices can't get new linked
  documents after this ships) is accepted and documented (spec.md Edge Cases, Assumptions) rather
  than silently absorbed.
- **Alternatives Considered**: Fall back to bare-name (rejected, see above). GET-then-resolve the
  original's `name` via `_resolve_client_by_name` as a fallback — rejected as a needless
  reintroduction of exactly the ambiguity/staleness risk this feature is designed to remove, for a
  case (historical documents) explicitly declared out of scope for migration.

## Decision 5: Non-exact-match disclosure reuses `is_exact_match`, not a new mechanism

- **Decision**: `_is_exact_name_match` (already used by `get_client_details`/`update_client`,
  Feature 026) is reused as-is by Group A tools to decide whether to disclose the real matched
  name in the confirmation reply. The disclosure itself is a plain prepended line at the *call
  site* in `tools.py` (e.g. `"מצאתי והשתמשתי בלקוח הבא: {resolved.name}\n" + format_invoice_confirmation(invoice)`)
  — **not** a new parameter added to the shared `format_invoice_confirmation` formatter, since that
  formatter is reused by other flows (`get_invoice_details`, the idempotent-no-op returns in
  `create_receipt`/`close_transaction_account`) that have no such disclosure concept.
- **Rationale**: Keeps `formatters.py`'s existing, widely-reused functions untouched; the
  disclosure is purely additive text built once in the Group A tool functions that need it.
- **Alternatives Considered**: Adding an `is_exact_match` parameter to `format_invoice_confirmation`
  itself (mirroring `format_client_details`'s own parameter) — rejected, would force every
  *unrelated* caller of `format_invoice_confirmation` to pass a meaningless `True` for no benefit.

## Decision 6: No new formatter needed for Group A's not-found/ambiguous paths

- **Decision**: Group A tools reuse `format_client_not_found()` and
  `format_ambiguous_clients_message(candidates)` verbatim (Feature 026) for their own zero-match/
  multi-match cases — no new formatter text.
- **Rationale**: Identical situation (a name search against the same `search_clients` endpoint,
  via the same `_resolve_client_by_name` helper) — no reason for different wording depending on
  which tool triggered it.

## Decision 7: Group B's refusal needs one new formatter

- **Decision**: A new formatter, e.g. `format_original_not_linked_to_client()`, is needed for
  Group B's REQ-INV-013 refusal — `format_client_not_found()`'s wording ("no client found by that
  name") doesn't fit; the problem here isn't a failed name search, it's "this specific original
  document has no real client attached to copy from."
- **Rationale**: Distinct user-facing situation deserves distinct, accurate wording (constitution's
  friendly-error shape: "[emoji] [what happened]. [what to do next]." — "what happened" here is
  "this invoice isn't linked to a real client record," "what to do next" has no actual remediation
  offered by this feature, so the message should say so plainly rather than implying a fix exists).
- **Alternatives Considered**: Reusing `format_client_not_found()` — rejected, misleading wording
  (there's no "name" being searched for at all in this path).

## Decision 8: Automated tests reuse the existing unique-marker naming mechanism, not literal names

- **Decision**: Every automated (pytest, real-sandbox) test this feature adds MUST generate its
  client names via this codebase's existing unique-marker mechanism — `_unique_marker(label)` /
  `f"DENIDIN_{...}_{int(datetime.now(timezone.utc).timestamp())}"` (or the UUID-hex variant,
  `uuid.uuid4().hex[:16].upper()`, for same-timestamp collision safety — see
  `test_morning_sandbox_get_client_details_tool.py`), composed into a name like
  `f"Test Client {marker}"` — exactly the pattern every existing `apps/morning-mcp-app/tests/integration/*.py`
  file already uses (`test_morning_sandbox_document_creation_tools.py`'s own `_unique_marker`,
  reused identically by `test_morning_sandbox_create_invoice_tool.py`,
  `test_morning_sandbox_add_client_tool.py`, `test_morning_sandbox_get_client_details_tool.py`,
  etc.). **Never a fixed literal name** (like the illustrative "Danny Cohen"/"Ronit Levi"/"Danny
  Katz" used in `user-stories.md`'s Given-When-Then narrative, or `quickstart.md`'s manual
  walkthrough) in any automated test — the shared sandbox accumulates real data across every test
  run (Feature 026's own research.md Decision 11 already observed 278+ real clients there), and a
  fixed name would either collide across repeated CI runs or silently reuse stale data from a
  previous run instead of the fixture the test just created.
- **Rationale**: This is not a new mechanism to build — it already exists and is used
  consistently by every real-sandbox integration test in this app. The narrative persona names in
  `user-stories.md`/`quickstart.md` exist purely so a human reader can follow a Given-When-Then
  story or type something recognizable into WhatsApp during manual verification (mirrors Feature
  026's own `user-stories.md`, which used "Tech Solutions" narratively while its actual tests used
  `unique_marker`-based names throughout) — they were never meant to be copied verbatim into
  automated test code, but that intent is now made explicit here to avoid ambiguity for whoever
  writes the actual tests at `/speckit.tasks`/implementation time.
- **Applies to US3/US6 specifically**: US3's two "ambiguous" clients and US6's "preserve" vs.
  "refuse" originals must each get their own fresh `_unique_marker`-based name per test run (e.g.
  two markers sharing a common random prefix to simulate "same first name," rather than the
  literal strings "Danny Cohen"/"Danny Katz") — the *shape* of the scenario (two similarly-prefixed
  names) is what the test needs to reproduce, not the literal persona names themselves.
- **Alternatives Considered**: Literal fixed names — rejected (collision/staleness risk above).
  `Faker`/a random-human-name library — rejected as an unneeded new dependency; the existing
  marker mechanism already fully solves the actual problem (uniqueness), and no test assertion in
  this feature depends on the name *looking* like a real human name rather than a marker string.

## Outstanding items for Phase 1 RED phase

- None on the client-attachment mechanism itself (Decisions 1-4 are all empirically confirmed or
  directly read from existing code, not assumptions).
- **Test-authoring note** (not a design gap): Group B's REQ-INV-013 refusal test needs a way to
  seed an original document with no `client.id` — since this feature's own Group A fix means any
  *newly created* original always has a real `id`, that document must be seeded via a raw
  `MorningClient.create_invoice` call using the old `{"name": ...}`-only payload shape directly
  (bypassing the tool layer), not via any of this feature's own tools. Flagged for `/speckit.tasks`.
