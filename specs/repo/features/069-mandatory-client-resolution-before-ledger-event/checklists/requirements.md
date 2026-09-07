# Specification Quality Checklist: Post-Turn Ledger Capture with Mandatory Client Resolution

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-30 · **Redesigned**: 2026-09-01
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs) — *reuse of named existing
  components (`resolve_client_name`, `add_client`, `query_ledger_events`,
  `capture_ledger_events_from_text`) is stated as constraint/context, not as new
  implementation; the genuinely new mechanism (post-turn recognition call + zero-AI ledgerer)
  is described in outcome terms in the spec and detailed only in plan/contracts*
- [x] Focused on user value and business needs (one client identity, Morning as source of truth,
  no lost reply mid-flow, full-payload fidelity)
- [x] Written for non-technical stakeholders (glossary + operator-visible scenarios)
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain — every deferred item (deposit-image path
  mechanism; store-anyway marker field/schema question; feature-flag question; abandonment
  record; the `capture_ledger_event` inline mechanism itself) was resolved during
  `speckit.plan` / the 2026-09-01 redesign with operator sign-off (see Notes)
- [x] Requirements are testable and unambiguous — FR-069-001…047 each map to acceptance
  scenarios in `user-stories.md`; FR-069-022 mandates the **exhaustive bidirectional**
  per-fixture manifest match on every event-creating scenario; FR-069-045/046/047 govern the
  media-routing path (no new AI call in any extractor)
- [x] Success criteria are measurable (SC-001…009: percentages, counts, "0 new files",
  "exactly 1 event", "reply byte-for-byte unchanged when recognition fails")
- [x] Success criteria are technology-agnostic (framed as persisted-event / operator-visible
  outcomes)
- [x] All acceptance scenarios are defined (`user-stories.md`, **10 stories** US1–US10,
  Given-When-Then, plus the "mechanism these stories exercise" shared-context section)
- [x] Edge cases are identified (abandon → `recognized` breadcrumb with no `written`; decline
  email/phone → **one** closed store-anyway / don't-store question (no re-ask), plus a
  proactive store-anyway election with no "are you sure" turn; ambiguous disambiguation
  reply → re-ask once as a closed choice → abandonment; multi-event; correction reuse; client
  from earlier conversation context; `payer_name` free text; tunnel down → capture nothing;
  group chat; unrelated debited account; read-only Morning question → `none`; mid-`create_*`
  field-filling reply → `none`)
- [x] Scope is clearly bounded (explicit Out of Scope section: `pdf` → Feature 071; durable
  client-name cache → Feature 072; retro backfill → Feature 065; no schema field; no code
  gate; no financial-content pre-filter on the recognition call)
- [x] Dependencies and assumptions identified (Dependencies + Assumptions sections; Assumption
  8 — no new OpenAI call is added to `DOCXExtractor` or any extractor)

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria (FR ↔ US mapping in
  `user-stories.md` and `contracts/client-resolution-gate.md` "Tests" table)
- [x] User scenarios cover primary flows — mechanism move / decoupling (US1), Morning create
  synchronous (US2), regression guard (US3), new-client typed `הסכם` (US4), ambiguous typed
  `הסכם` (US5), exact-match silent (US6), deposit-image 0/1/2+/exact matches (US7
  7a/7b/7c/7d), won't-provide-email/phone — single ask + proactive election (US8),
  photographed multi-component `הסכם` (US9), `docx` multi-component `הסכם` (US10)
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification beyond named reuse constraints

## Notes

- **Redesigned 2026-09-01 (operator direction, locked across sessions).** *"the whole
  mechanism is wrong. ledger capturing yes or no should come LAST, not first. Like a finally
  code block."* Ledger capture is no longer an inline `capture_ledger_event` tool call the
  conversational model makes mid-reply. After the operator's reply is finalized and sent, one
  dedicated **text-only OpenAI recognition call** asks the single question *did a complete
  ledger event finish this round, and if so here is its data mapped to the ledger schema* —
  and a mechanical zero-AI **ledgerer** mints ids, dedups, persists the immutable JSON, and
  links it from the completing session message. `query_ledger_events` (read/search) stays on
  the main turn as the only ledger tool the conversational model may call. **Deleted:**
  `_call_openai_ledger_followup_api`, the bugfix-018 MCP-suppression guard, the
  `>1 call` / unparseable-args protocol-violation whole-turn-rejection machinery,
  `_handle_ledger_event_capture`, and `LEDGER_EVENT_TOOL` / `capture_ledger_event` on the main
  turn.
- **Scope (operator, verbatim):** *"include: mechanism move + morning 'creates' + mandatory
  client for agreements, deposits, and morning docs"* — a resolved-to-exact-Morning-name
  `client_name` is a mandatory "complete event" field for `הסכם`, `בנק`, **and** `חשבונית`.
  A `create_*` MCP call that succeeds in-conversation is a complete `חשבונית` event (client
  resolved by construction) captured **synchronously that turn** by the recognition call
  reading the real Morning response; Feature 025's reconciliation sweep still handles docs
  created manually / by Morning automation and dedups against 069's synchronous writes
  (keyed on `accounting_document_display_number`).
- **Resolved in `speckit.plan` / redesign** (operator sign-off, 2026-08-31 & 2026-09-01):
  the media ledger path — `בנק` deposit slips, photographed `הסכם` agreements, **and `docx`
  `הסכם` agreements** — gains interactive client resolution by **routing the extractor output
  + extracted text through the `AIHandler` conversational pipeline** as a synthetic turn
  (Feature 030 contact-card pattern) carrying a verbatim structured stash
  (`build_ledger_stash_text(extracted_text, analysis, source_type, source_medium)`), so the
  same post-turn recognition call covers it. **No new OpenAI call is added to `DOCXExtractor`
  or any extractor** (spec Assumption 8) — the extractor's *existing* analysis
  (`ImageExtractor` vision classify; `DOCXExtractor` `document_analysis.document_type`) is the
  routing signal only. Because the recognition call is text-only (`config.ai_model`), the
  `docx` `הסכם` story (US10) is a **`billed`** acceptance test; the image stories (US7, US9)
  are **`expensive`**. `pdf` agreements are **deferred to Feature 071**
  (`specs/backlog/071-pdf-single-call-extraction/` — operator direction 2026-08-31: *"New
  spec 71 for pdf single extraction. Remove from 69 scope and continue 69 with images and
  docx"*). Rejected alternatives (a dedicated `PendingLedgerResolutionManager`; keeping
  photographed `הסכם` on the direct-persist path; attaching MCP tools to the vision call —
  reverted for Feature 024, produces zero extraction text) are recorded in spec §Technology
  Choices and `research.md` R1.
- **Resolved** (operator sign-off, 2026-08-31): the "client not resolved in Morning" marker
  is **free text written into the existing `LedgerEvent.description`** — the fixed phrase
  `[לקוח לא אומת במורנינג]` — **no** new schema field, **no** `CURRENT_SCHEMA_VERSION` bump.
  `LedgerEvent`'s persisted schema is unchanged by this feature. `CURRENT_SCHEMA_VERSION`
  stays **2** (human decision 2026-08-31); **no test asserts `schema_version`'s value**
  anywhere (CLAUDE.md rule).
- **Resolved** (operator direction, 2026-08-31): **no feature flag** and **no new config
  key at all.** The feature ships unconditionally — a deliberate, operator-authorized
  departure from CLAUDE.md's "feature flags for new behavior" convention, recorded in
  `plan.md` Complexity Tracking (deviation 1).
- **Resolved** (operator direction, 2026-08-31): the recognized-but-not-captured record is
  **app-log breadcrumbs** — three INFO lines (`[069] ledger capture recognized` /
  `[069] ledger event written` / `[069] ledger capture declined by operator`), emitted by
  the ledgerer, not a stateful in-memory tracker. The earlier
  `PendingLedgerResolutionTracker` + hourly `SessionCleanupThread` sweep + a
  `ledger_unresolved_abandon_ttl_hours` config knob were dropped as disproportionate.
  Abandonment detection is **operational** (log grep for a `recognized` with no matching
  `written` / `declined`), not coded. Trade-off: a silent abandon on the typed-text path
  before the event ever became complete leaves no log line; image/`docx` captures always
  leave the `recognized` breadcrumb because the recognition call runs post-turn on every
  turn.
- **Resolved** (operator direction, 2026-09-01): unit and integration tests do **not** need
  the operator's approval — no Task A → Task B human sign-off gate for that tier
  (Feature-069-scoped). Tests are still written **RED first** and are **immutable once
  committed**. The `expensive` per-run approval and the constitution / operator-facing
  wording (METHODOLOGY §XIX) approval gates are **unaffected**. Recorded in `plan.md`
  Complexity Tracking (deviation 2).
- **FR-069-016 (multi-event / staggered captures)** is covered at the **unit** tier only
  (`tests/unit/test_recognition_call.py` — one `complete` event per turn, no lost sibling);
  no dedicated `billed`/`expensive` scenario, recorded in `user-stories.md` "Cross-cutting
  test requirements". Deliberate — a real multi-event operator turn is disproportionate to
  stage against the sandbox and the per-turn emit is deterministic.
- Enforcement of the mandatory-client rule is **constitution guidance + acceptance tests
  only** — no hard code gate (FR-069-040 / redesign), per operator decision. The recognition
  call simply returns `none` ("nothing complete this round") when the client is unresolved or
  any mandatory field is missing.
- Store-anyway (FR-069-033/034/035) is the one sanctioned unresolved-client capture and is
  always an explicit operator election — either an answer to the **single** closed
  store-anyway question or a **proactive** request made up front (which DeniDin honours with
  no "are you sure" confirmation turn). Never volunteered before the operator has declined
  the contact details or proactively asked, never a default.
- Forward-only; Feature 065 owns the August 2026 `בנק` backfill.
- **Known internal doc drift for `speckit.analyze` to reconcile**: the `plan.md` source-tree
  comment (~line 315) still names the ledgerer's 3rd parameter `trigger_message_id`; the
  authoritative contract (`contracts/recognition-and-logging.md` C6) names it
  `completing_message_id` (positional — the message that receives the
  `Message.ledger_event_ids` back-link), with `trigger_message_id` carried as a **field
  inside the `complete` verdict** and used only for the `event_datetime` hard-pointer lookup.
  `data-model.md` §3 already reads `persist_recognized_event(...)` and is consistent with C6.
