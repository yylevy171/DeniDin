# Tasks: Ledger Event Querying via AI — Feature 044

**Spec**: `./spec.md` · **Plan**: `./plan.md` · **User stories**: `./user-stories.md` ·
**Research**: `./research.md` · **Data model**: `./data-model.md` · **Contracts**: `./contracts/`
**App**: `apps/denidin-app/` only (no `morning-mcp-app` involvement)
**Branch**: `feature/044-ledger-event-querying`

## Conventions

- Task ID `T###`. `[P]` = parallelizable (different files, no dependency on an incomplete task).
- **"TDD" (METHODOLOGY §VI, redefined 2026-08-18)** means specifically Phase 3's `billed`
  acceptance test(s) below — defined now, in user-experience terms only, but not written as code
  and not run until Phase 1 and Phase 2 are both fully GREEN.
- **Unit/integration test discipline for this feature (user directive, 2026-08-23 — overrides
  METHODOLOGY §VI.b's literal per-pair approval gate for THIS feature's Phase 1-2 work): the
  human-approval gate applies ONLY at the `billed` test step (T014/T015 below), not to each
  individual `a`/`b` unit-or-integration-test pair.** Within Phase 1-2, tests are still written
  first and confirmed RED before their implementation task goes green (the RED→GREEN discipline
  itself is unchanged), but implementation proceeds directly after RED is confirmed — no
  per-task stop-and-wait. `a`/`b` labeling is kept for traceability/ordering, not as an approval
  checkpoint marker, for this feature.
- **No locks**: no `threading.Lock`/synchronization primitive anywhere in this feature without
  separate, explicit approval first (user directive, 2026-08-23) — see research.md Decision 8.
- **No per-story phases** (a deliberate departure from the tasks-template's default
  one-phase-per-user-story shape, same kind of documented departure Feature 054's `tasks.md`
  made for its own reasons): US1/US2/US3 are all served by the SAME single tool
  (`query_ledger_events`) called with different arguments — there is no separable code path per
  story the way Feature 056 had two genuinely independent tools. Phases below instead follow
  `plan.md`'s own Phase 1 (query engine) / Phase 2 (tool wiring + RBAC) / Phase 3 (acceptance)
  structure, with each task labeled `[US1]`/`[US2]`/`[US3]`/`[Shared]` for traceability.
  **US3 (RBAC denial) has no dedicated phase of its own** — it's fully satisfied by Phase 2's
  RBAC-gating tasks (T005/T007), which prove both the positive case (attached for godfather/
  admin) and the negative case (absent for client/blocked) together, since they're the same
  gating logic.
- Paths relative to `apps/denidin-app/` unless stated otherwise.

---

## Phase 1 — Index + Query Engine (`LedgerEventManager`) [Shared foundation for US1/US2]

**Goal**: `LedgerEventManager` gains an in-memory index (loaded at startup, kept current on
writes) and a `query_events` method implementing every filter/matching rule from
`data-model.md` — entirely independent of `AIHandler`/the tool layer, testable on its own.

**Independent Test**: construct a `LedgerEventManager` against a temp dir with a handful of
pre-written event JSON files (plus one deliberately corrupt file), call `query_events` with
various filter combinations directly, and assert on the returned shape — no `AIHandler`, no
OpenAI, no tool schema involved at all.

- [x] **T001a** [P] [Shared] Write unit tests in `tests/unit/test_ledger_event_manager.py`
  (existing file, extended) for the in-memory index itself: (1) constructing a
  `LedgerEventManager` against a storage dir containing several valid event JSON files
  populates `self._index` with all of them at construction time; (2) a deliberately malformed
  JSON file in that same dir is skipped (not raised, not crashing construction) and logged as
  an ERROR (FR-007) while every other valid file still loads; (3) calling `add_ledger_event`
  after construction appends the newly-persisted record to `self._index` immediately (FR-003).
  *(2026-08-23: confirmed RED — all 6 tests fail with `AttributeError` against current code,
  full pre-existing suite (101 tests) still green. Written against `manager._index` directly
  rather than a `query_events` round-trip, since `query_events` doesn't exist until T002b/
  T003b — this task's own scope needs to be provable in isolation.)*
- [x] **T001b** [Shared] Implement `self._index: List[Dict]`, index-population in `__init__`
  (glob `{data_root}/events/*.json`, skip+log corrupt files), and the append in
  `add_ledger_event` right after its existing atomic file write succeeds, in
  `src/managers/ledger_event_manager.py`. No lock (user directive, 2026-08-23).
- [x] **T002a** [P] [US1] Write unit tests in `tests/unit/test_ledger_event_manager.py` for
  `query_events`'s **structured** filters (no fuzziness involved yet): `date_from`/`date_to`
  matching against EITHER `event_datetime` OR `txn_date` (data-model.md Decision 7, including
  the case where only one of the two fields is populated on a given record); `amount_min`/
  `amount_max` inclusive range; `source_type`/`event_subtype` exact match; multiple filters
  AND-combined (e.g. a date range AND a source_type together narrow correctly); an inverted
  range (`date_from > date_to` or `amount_min > amount_max`) yields an empty result rather
  than raising; a malformed date string is treated as if that bound were absent, not raised.
- [x] **T002b** [US1] Implement the structured-filter portion of `query_events` in
  `src/managers/ledger_event_manager.py` (depends on T001b for `self._index` to exist).
- [x] **T003a** [P] [US1] Write unit tests in `tests/unit/test_ledger_event_manager.py` for
  `query_events`'s **fuzzy** matching: (1) `client_name` with a typo/partial name still
  matches the intended stored `client_name` (and separately, a stored `payer_name`) above
  `_NAME_MATCH_THRESHOLD`; (2) a query name that fuzzy-matches exactly one distinct stored
  name returns that client's events normally (shape A); (3) a query name that fuzzy-matches
  TWO OR MORE distinct stored name strings above threshold returns the candidates shape
  (shape B) instead of events — the core of Decision 4/US1 scenario 3's disambiguation
  requirement; (4) a name with no plausible match at all returns an empty `matches`, not a
  false-positive; (5) `free_text` fuzzy-matches `description`/`component_label`/
  `trigger_condition` above `_FREE_TEXT_MATCH_THRESHOLD`, and explicitly does NOT match a
  paraphrased-but-differently-worded field (documenting the accepted limitation from
  research.md as a real, asserted test case, not just prose).
- [x] **T003b** [US1] Implement the fuzzy-matching portion of `query_events` (name scoring +
  entity-ambiguity grouping, free-text scoring) plus `_NAME_MATCH_THRESHOLD = 70`/
  `_FREE_TEXT_MATCH_THRESHOLD = 60` module constants in
  `src/managers/ledger_event_manager.py`; add `rapidfuzz` to `requirements.txt` (depends on
  T001b).
- [x] **T004a** [P] [US1] [US2] Write unit tests in `tests/unit/test_ledger_event_manager.py`
  for `query_events`'s vague-query guard: every one of the eight filter arguments `None` →
  returns the `{"error": "no_search_criteria", ...}` shape (data-model.md shape C), and
  crucially does NOT return the whole ledger; any single non-null filter (even just one) →
  proceeds to a normal search instead.
- [x] **T004b** [US1] [US2] Implement the guard as the first check inside `query_events`.

*(2026-08-23: Phase 1 complete. `rapidfuzz>=3.9.0` added to `requirements.txt` and installed.
20 new tests across `TestQueryEventsStructuredFilters`/`TestQueryEventsFuzzyMatching`/
`TestQueryEventsVagueQueryGuard` confirmed RED against pre-implementation code, then GREEN
after implementing `query_events` + its helper methods (`_distinct_name_candidates`,
`_count_events_for_name`, `_event_matches_name`, `_event_matches_amount`,
`_event_in_date_range`, `_event_matches_free_text`) and the module-level
`_parse_query_date`/`_parse_event_date_field` helpers. Full suite: 126/126 passing, zero
regressions on the 101 pre-existing tests.)*

**Checkpoint**: `LedgerEventManager.query_events` is fully implemented and unit-tested in
isolation — every filter, both fuzzy mechanisms, the ambiguity shape, and the vague-query
guard all work, with zero `AIHandler`/tool-layer involvement yet.

---

## Phase 2 — Tool Wiring + RBAC (`AIHandler`) [US1, US2, US3]

**Goal**: `query_ledger_events` exists as a real local tool, attached only for godfather/
admin, dispatched immediately (read-only, no approval gate) with a same-turn follow-up
round-trip — wiring `AIHandler` to Phase 1's `query_events` the same way `_handle_list_reminders`
already wires to `ReminderManager.list_active`.

**Independent Test**: with Phase 1 already GREEN, a real webhook-shaped turn (via
`bot.router`, no direct method calls) whose stubbed OpenAI response already contains a
`query_ledger_events` function_call is dispatched, and the resulting `function_call_output`
correctly reflects `LedgerEventManager.query_events`'s real return value — role-gated
correctly in both directions.

- [x] **T005a** [P] [US1] [US2] [US3] Write unit tests in a new
  `tests/unit/test_ai_handler_ledger_query.py` (mirrors `test_ai_handler_reminders.py`'s
  file-per-feature convention, kept separate from `test_ai_handler_ledger_events.py` since
  that file covers `capture_ledger_event`, a different tool) for RBAC gating: (1) godfather
  and admin roles get `QUERY_LEDGER_EVENTS_TOOL` attached in `_assemble_tools`'s combined
  tools list; (2) client and blocked roles do NOT (US3's core assertion, at the unit level);
  (3) `LEDGER_QUERY_AUTHORIZED_ROLES` is its own distinct constant (not accidentally reusing
  `MORNING_MCP_AUTHORIZED_ROLES`/`REMINDER_AUTHORIZED_ROLES` by reference in a way that would
  make an independent future RBAC change to one silently affect this one).
- [x] **T005b** [US1] [US2] [US3] Implement `LEDGER_QUERY_AUTHORIZED_ROLES =
  (Role.GODFATHER, Role.ADMIN)`, `QUERY_LEDGER_EVENTS_TOOL` (exact schema from
  `contracts/query-ledger-events-tool.md`), `_build_ledger_query_tools(user_obj)`, and its
  wiring into `_assemble_tools` in `src/handlers/ai_handler.py`.
- [x] **T006a** [P] [US1] [US2] Write unit tests in `tests/unit/test_ai_handler_ledger_query.py`
  for dispatch (research.md Decision 10 — the multi-call pattern, NOT `list_reminders`'
  single-call pattern): (1) a turn whose response contains exactly ONE `query_ledger_events`
  call triggers a follow-up reporting `LedgerEventManager.query_events`'s real return value
  back as that call's `function_call_output`, chained via `previous_response_id`; (2) a turn
  whose response contains TWO (or more) `query_ledger_events` calls (e.g. simulating "client A
  or client B") executes `query_events` independently for EACH, and reports ALL of them back
  in a SINGLE follow-up call as a list of `function_call_output` items, one per `call_id` —
  mirrors `_call_openai_ledger_followup_api`'s existing multi-item batching, asserted via
  `extract_all_function_calls`, never `extract_function_call`/`extract_function_call_id`;
  (3) one call's `arguments` fail to parse (simulated truncated JSON) while a second
  well-formed call is present in the same turn → the failed call gets its own isolated error
  output (data-model.md shape D) and the second call STILL executes and returns its own real
  result — explicit regression test proving this does NOT inherit `capture_ledger_event`'s
  bugfix-018 whole-turn-rejection behavior; (4) a turn with NO such function_call leaves
  `_handle_query_ledger_events` returning `None` (no follow-up attempted); (5) the
  vague-query-guard shape (all-null args on one call) is passed through to `query_events`
  unmodified — `AIHandler` doesn't need its own duplicate guard, `query_events` already
  enforces it (Phase 1, T004b).
- [x] **T006b** [US1] [US2] Implement `_handle_query_ledger_events` (using
  `extract_all_function_calls`, per-call independent execution, per-call parse-failure
  isolation) and `_call_openai_query_ledger_events_followup_api` (multi-item
  `function_call_output` batching, mirroring `_call_openai_ledger_followup_api`'s shape) in
  `src/handlers/ai_handler.py`, and wire the new handler into `_finalize_response` alongside
  the existing `list_reminders_followup` check (depends on T005b).
- [x] **T007a** [P] [US1] [US3] Write a real router-dispatch integration test in a new
  `tests/integration/test_ledger_query_conversation_routing.py`, mirroring
  `test_reminder_conversation_routing.py`'s structure exactly (real textMessage-shaped Green
  API notification → `bot.router` → `handle_text_message` → `WhatsAppHandler` →
  `AIHandler.get_response` → `_finalize_response` → `_handle_query_ledger_events`; only the
  OpenAI client's `responses.create` is stubbed, everything else real internal wiring per
  CONSTITUTION §V): (1) as godfather, a stubbed response containing a `query_ledger_events`
  call is dispatched and the resulting reply reflects the follow-up call's content — proves
  the tool is genuinely attached AND genuinely reachable through the real pipeline, not just
  at the unit level; (2) as a client-role sender, the SAME stubbed-response shape (if the
  model somehow tried to call it) never actually reaches `_handle_query_ledger_events`,
  because the tool was never attached to that turn's `tools` list in the first place —
  US3's real end-to-end proof.
- [x] **T007b** [US1] [US3] Verify GREEN — run the new integration test file plus the full
  existing `tests/unit/` + `tests/integration/` suite, confirm zero regressions.

*(2026-08-23: T005-T007b complete. New `tests/unit/test_ai_handler_ledger_query.py` (15
tests: RBAC attachment, single-call dispatch, multi-call dispatch, per-call failure
isolation) and `tests/integration/test_ledger_query_conversation_routing.py` (2 tests: real
router-dispatch reply, real RBAC denial) all GREEN on first implementation pass. Full suite:
1120/1120 unit tests, 38/38 integration tests, zero regressions. `pylint`/`mypy` clean on
both modified files (pylint 9.24/10, well above the 7.0 threshold; the one mypy finding is
pre-existing and in an untouched file, `reminder_manager.py`).)*
- [x] **T007c** [Shared] Add a new **"Ledger Event Querying"** section to
  `config/runtime_constitution.md` (CLAUDE.md's mandatory "every tool-bearing feature needs
  explicit constitution boundaries" rule — missed in the original plan, added 2026-08-23):
  scope (when `query_ledger_events` applies — natural-language questions about past ledger
  events, godfather/admin only), explicit negative scoping (when it does NOT — e.g. a
  client-role turn, an ambiguous message that should be resolved by asking rather than
  reaching for this tool, media messages), the 20-item chat-reply display cap
  (research.md — "too many results" refinement: summarize/ask-to-narrow past 20 listed
  items, the tool's own retrieval stays unbounded), and that ambiguity is resolved by asking
  the user, never guessing (mirrors the existing "Contexts of Operation" general rule this
  section should point back to rather than re-deriving). **Cross-reference in both
  directions**: add a line to Reminder Management, Ledger Event Recognition (capture), and
  the Morning MCP section each explicitly stating ledger *querying* is out of scope for them
  too — one-way scoping isn't enough (CLAUDE.md's explicit requirement). No test-then-impl
  split needed (this is documentation/prompt content, not code) — its effect is verified by
  Phase 3's `billed` tests (RBAC denial, the 20-item cap scenario) actually exercising the
  guidance for real.

*(2026-08-23: T007c complete — new "Ledger Event Querying" section added to
`runtime_constitution.md` (scope, negative scoping, fuzzy-matching summary, ambiguous-name/
multi-call guidance, arithmetic-is-your-job note, and the 20-item display cap), plus
cross-references added in both directions: "Contexts of Operation" now calls it out as a
separate capability (mirroring the existing Reminders paragraph); "Invoice Management
Context" and "Reminder Management" both now explicitly exclude it; "Ledger Event
Recognition" Step 1 gained a new classify bullet distinguishing querying (read) from
capturing (write). Full suite (1158 tests) still green after the edit — confirmed the
~19.2K pre-existing constitution token count (measured via tiktoken's o200k_base) is stale
documentation in CLAUDE.md (last measured 2026-07-23 at ~4.0K, long since grown from other
features), not a regression from this feature - this feature's own addition is ~1.6K
tokens.)*

**Checkpoint**: the tool is real, RBAC-gated correctly in both directions, and reachable
through the actual router/handler pipeline — US1 and US2's mechanics and US3's RBAC boundary
are all proven at the unit/integration level. Only real-model conversational judgment (does
the model actually call this tool at the right moment, with sensible arguments, for a real
Hebrew question) remains unverified — that's Phase 3.

**Addendum, 2026-08-23 (Feature 025 forward-compatibility, reactive — not originally planned as
its own task)**: pulled `master` and found Feature 025 (Morning-sourced ledger events,
`specs/in-progress/025-morning-sourced-ledger-events/`) fully designed through 6 clarification
rounds — code on its own branch, docs already merged. Its persisted `LedgerEvent` extensions
(`source_type="חשבונית"`, a proposed `event_subtype="הפקה"`, six new `accounting_document_*`
fields) would have silently broken `source_type`/`event_subtype` filtering the moment 025 merges,
because `QUERY_LEDGER_EVENTS_TOOL` copied `capture_ledger_event`'s strict-enum discipline — the
right call for a WRITE tool, wrong for a READ/filter parameter. Fixed (research.md Decision 12):
- `source_type`/`event_subtype` are now plain exact-match text filters with **no `enum`
  constraint** — permanently forward-compatible with any future source type, not just this one,
  with zero schema maintenance going forward.
- `free_text` now implicitly also searches the four new `accounting_document_*` text fields
  (`_display_number`/`_type`/`_status_label`/`_payment_method`) — user directive: *"not as
  explicits, but as implicit fields like any other."* `accounting_document_status_code` (raw int)
  deliberately excluded; `_event_matches_free_text` now defensively `str()`-casts every field
  value so a non-string field anywhere can never raise.
- 6 new unit tests added (`test_source_type_filter_accepts_any_value_not_just_known_ones`,
  `test_event_subtype_filter_accepts_any_value_not_just_known_ones`, and 4 covering the new
  free-text fields incl. the non-string-value defensive case) — all GREEN, full suite 1168/1168,
  `pylint` 9.38/10 (up from 9.24 — the enum removal simplified things), `mypy` clean (same
  pre-existing unrelated finding in an untouched file). No other Feature 044 code needed changing
  — every other filter already read fields generically with no assumption about which
  `source_type` values exist, confirmed by reading 025's `data-model.md` field-by-field against
  `query_events`'s actual implementation rather than assumed.
- **Follow-up same day**: user reported Feature 025's design moved further —
  `accounting_document_type` is being replaced entirely by `event_subtype` (the "type of
  accounting document" concept folds into `event_subtype` itself). Needed **zero**
  `query_events` filtering change (`event_subtype` was already a plain exact-match, no-enum
  filter from the fix above — already forward-compatible with whatever values it ends up
  holding). One small follow-up: removed `accounting_document_type` from `_FREE_TEXT_FIELDS`
  (that field is going away) and replaced the now-wrong unit test with two — one confirming
  `accounting_document_type` is no longer free-text-searched, one confirming `event_subtype`
  itself still works as an exact-match filter regardless of which value it holds. Full suite
  1169/1169, `pylint` unchanged at 9.83/10 for this file.

---

## Phase 3 — Acceptance: TDD (`billed`, user-perspective, run once) (§VI.a)

**Goal**: prove the feature works for a real user, through the real OpenAI Responses API —
not just that the internal wiring is correct.

**Revised 2026-08-23** (expanded per user review of the original 5-scenario draft — several
real query shapes were missing and needed their own scenario, not just an assertion tweaked
into an existing one):

**Further revised 2026-08-23 (user request: "test the majority as unit tests so we don't
need to iterate on billed tests")**: for every scenario below where the "juicy part" is
*mechanics* (does the right filter/dispatch/multi-call happen, given a KNOWN set of tool-call
arguments) rather than real model *judgment* (does the model decide to call the tool at all,
extract the right arguments from Hebrew, phrase its reply correctly), that mechanical
coverage now ALSO exists as a stubbed-response integration test in
`tests/integration/test_ledger_query_conversation_routing.py` — same real router/handler/
manager pipeline as T007a, just with the OpenAI response hand-constructed instead of real.
Specifically now covered there, in addition to T007a's original 2: payer-name search
(T008.4), the "both/all → two calls, merged" flow (T009.2), monthly income aggregation with
a same-month negative control (T010.3), and a genuine four-distinct-clients multi-criterion
request combining name+date per call (T011) — 6 integration tests total, all GREEN, confirmed
idempotent across repeated runs (see that file's own "Test-data hygiene" docstring for a real
collision this surfaced and fixed while writing them — two similar-sounding seeded names
tripped the fuzzy-match ambiguity check against each other).

**Further hardened 2026-08-23 (user directives after review)**: (1) test names never use a
generic "חברת X" company-prefix pattern — real ledger clients in this codebase's own data are
individuals, referred to by real first+last names (matching the style of the actual historical
records already in `test_data/events/`, e.g. "רונית כהן"/"עמוס כהן"), and where a payer entity
genuinely is an organization (an insurer routing payment), it's a real proper noun like the
existing data's own "הראל" — never a fabricated "חברת X" placeholder; (2) cleanup upgraded from
"delete only what I seeded" to a full wipe of `test_data/events/` (disk + in-memory index)
BEFORE AND AFTER every test via an autouse fixture — this is unit/integration-tier data, safe
to clear unconditionally, and removes the whole class of cross-test collision risk rather than
trying to out-clever it; (3) the two-client "A or B" multi-criterion test was replaced with a
four-client version, each call ALSO carrying a date-range filter (two filter dimensions per
call, not one); (4) a new T014 scenario added for natural-language exclusion (a fact the user
states in conversation, not derivable from the ledger itself) — not mechanically stubbable at
all, `billed`-only.

**This does not eliminate Phase 3** — a stubbed test proves "if the model calls it this way,
everything downstream works," never "the model actually decides to call it this way,
unprompted, from a real Hebrew question." What's left for T008-T014's actual `billed` runs is
now the smaller, harder-to-fake slice: real tool-call decision-making, real argument
extraction (e.g. resolving "August" to a date range), real incorporation of a stated fact not
in the ledger (T014), and — for T013 specifically — real
model-authored reply text (the 20-item cap is about what the MODEL says, which a stub can't
exercise at all, since the stub supplies the reply verbatim).

**Seeding convention for T015 (user directive, 2026-08-23): every scenario seeds MORE than
the minimum needed — real distractor/noise events (other clients, other dates/months, other
amounts, the occasional other source_type) alongside the actual target data, not a suspiciously
minimal dataset containing only what the question needs.** This is closer to a real ledger's
shape and is a materially stronger proof than a clean-room dataset — it's the difference
between "the model can find the right answer when it's the only thing there" and "the model
can find the right answer among noise," which is what actually matters in production. Applies
to every T008-T014 scenario, not just the ones that already needed a negative control (T010.3's
same-month agreed-but-unpaid event, T011's four distinct clients) — even T008's single-lookup
scenarios should have a handful of unrelated events seeded alongside the target one.

- [ ] **T008** [P] **[TDD — DESCRIBE NOW, IN USER-EXPERIENCE TERMS]** US1 core lookups, in a
  new `apps/denidin-app/tests/billed/test_ledger_query_billed.py`: (1) explicit lookup — a
  real pre-seeded event for a known client/matter/amount, ask "כמה סוכם עם [client] על
  [matter]?" → reply states the correct amount, sourced from a real `query_ledger_events`
  call this turn (not session memory, not fabricated); (2) same mechanism, a date-bearing
  question ("מתי [client] התחיל את ההסכם?") → reply states the correct date — proves the
  date-field lookup path, not just amount; (3) no matching event at all → reply plainly says
  nothing found, never fabricates; (4) **payer-name search** (new) — an event whose
  `payer_name` (not `client_name`) is the searched-for name (a routed/insurer payment,
  matching the schema's own `payer_name` semantics) → reply correctly finds and states it,
  proving `client_name`'s dual client_name/payer_name matching (data-model.md) works for
  real, not just at the unit level.
- [ ] **T009** [P] **[TDD — DESCRIBE NOW, IN USER-EXPERIENCE TERMS]** US1 ambiguity handling,
  same file: (1) two distinct clients with names that both fuzzy-match a short/partial query
  name → reply asks which client is meant, listing both — never guesses one (US1 scenario 3 /
  Decision 4); (2) **the "both/all" follow-up** (new) — continuing scenario (1)'s
  conversation, reply "גם וגם"/"שניהם" (both) → DeniDin issues one `query_ledger_events` call
  per confirmed distinct name (assert TWO calls happened this turn, per research.md Decision
  10) and its reply reflects BOTH clients' events combined, not just one.
- [ ] **T010** [P] **[TDD — DESCRIBE NOW, IN USER-EXPERIENCE TERMS]** US2 aggregation
  scenarios, same file: (1) date-ranged hours summary — several real pre-seeded hours-logged
  events for one client across a calendar month (plus a different-client/different-month
  negative control) → "כמה שעות אני צריך לחייב את [client] ב[month]?" → reply reflects only
  that client's matching events for that month (model sums itself, per Decision 5), never
  pulling in the negative control; (2) **aggregate hours by payer** (new) — same shape as (1)
  but the hours-logged events share a `payer_name` rather than `client_name` → proves the
  payer-based aggregation path, not just client-based; (3) **monthly income aggregation**
  (new, no client named at all) — several real בנק (deposit) events across a month for
  MULTIPLE different clients, plus a הסכם (agreed-but-unpaid) event in the SAME month as a
  negative control → "כמה הכנסות היו לי ב[month]?" → reply sums only the deposit events
  (research.md Decision 11 — "income" means received, not agreed) and does not include the
  agreed-but-unpaid amount; also confirms the vague-query guard does NOT block a
  date-range-only, client-less query (Decision 11's guard-interaction note).
- [ ] **T011** [P] **[TDD — DESCRIBE NOW, IN USER-EXPERIENCE TERMS]** US1/US2 genuine
  multi-criterion request (new, distinct from T009's typo-driven ambiguity — this is a
  request that NAMES several real, unambiguous, already-known-distinct clients directly).
  **Revised 2026-08-23 (user note): "A or B" was only an illustrative example — the real
  requirement is N criteria, unbounded, potentially combined with other filter dimensions at
  once (a name AND a date range together), not just two names alone.** Real pre-seeded events
  for FOUR clearly different real clients within the same month (no name overlap/typo involved
  at all) → "מה סוכם באוגוסט עם [A], [B], [C] או [D]?" → assert DeniDin issues FOUR separate
  `query_ledger_events` calls in this one turn (one per named client, each ALSO carrying the
  same date-range filter — two filter dimensions combined per call, per research.md Decision
  10) and its reply correctly reflects all four clients' agreements distinctly (not merged
  into one number, not only answering for a subset of them). The mechanical shape of this
  (N calls, each combining name+date) is already proven at the integration tier
  (`test_four_way_multi_criterion_with_date_range_issues_four_calls_over_the_real_route`) —
  this billed test is about whether the MODEL actually decomposes a 4-way "or" question into
  four calls unprompted, which no stub can prove.
- ~~**T012** US3 RBAC denial~~ — **REMOVED (user, 2026-08-23): not needed as a `billed` test.**
  RBAC denial has no real model-judgment component to prove — the tool is structurally absent
  from `tools` for a client-role turn (a deterministic, code-driven fact, not something the
  model decides), so a real OpenAI call here would only be testing "does the model decline to
  call a tool it was never given," which isn't informative. Already fully proven at the
  integration tier (`test_client_role_never_receives_query_ledger_events_tool_over_the_real_route`,
  Phase 2/T007a) — that's the real, sufficient proof for this requirement. Number left as a gap
  rather than renumbering everything downstream a second time.
- [ ] **T013** [P] **[TDD — DESCRIBE NOW, IN USER-EXPERIENCE TERMS]** 20-item display cap
  (new, 2026-08-23 — concrete/testable, distinct from the owed-balance case which stays
  manual-only): seed MORE than 20 real matching events for a broad query (e.g. many events
  across a wide date range) → ask a question that would match all of them → assert the reply
  does NOT enumerate more than 20 individual events verbatim (count distinct
  event/line-item mentions in the reply text) — it must summarize/group/state a total or ask
  to narrow instead, per the new `runtime_constitution.md` "Ledger Event Querying" section
  (T007c). This is a real regression test for a prompt-level rule with no code-side
  enforcement (research.md — honest distinction from the vague-query guard, which DOES have
  a code backstop).
- [ ] **T014** [P] **[TDD — DESCRIBE NOW, IN USER-EXPERIENCE TERMS]** Natural-language
  exclusion (new, 2026-08-23, user example: *"כמה כסף חייבים לי עדיין באוגוסט חוץ מיוסי ברנע
  שאני יודע ששילם כבר"* — "how much am I still owed in August, except Yossi Barnea who I know
  already paid"). **No schema change** — the tool has no exclusion parameter and never will;
  this is entirely the model's own job (research.md Decision 5, "model reasons over raw
  events"): call `query_ledger_events` for the August range, get back the raw agreement +
  payment events, and incorporate the user's own stated fact (not necessarily reflected in the
  ledger itself) when composing the reply. **Not mechanically stubbable at all** — unlike
  T008-T011 above, there is no "given these tool-call arguments, does the pipeline work"
  question here; the entire scenario IS the model's own natural-language reasoning. Real
  pre-seeded agreement events for 2-3 clients in August (at least one with no corresponding
  payment event, matching "Yossi" in the example) → assert the reply's final number correctly
  excludes the named client, using the user's own stated reason, not the ledger data alone.
- [x] **T015** **[TDD — WRITE + RUN, ONCE Phase 1 AND Phase 2 are both GREEN]** Turn
  T008-T011/T013/T014's descriptions (T012 removed - see above) into real `billed` tests in
  `apps/denidin-app/tests/billed/test_ledger_query_billed.py` (following the existing
  `test_ledger_event_capture_billed.py`/`test_reminder_lifecycle_billed.py` pattern) — written
  2026-08-23, 11 tests covering T008 (4)/T009 (1, two-turn)/T010 (3)/T011 (1)/T013 (1)/T014
  (1).
  **Data seeding vs. the test itself (user directive, 2026-08-23): seeding pre-existing ledger
  events for a scenario to query against is done directly at the
  `LedgerEventManager.add_ledger_event` level (real internal code, same helper pattern as the
  integration tests' `_seed`) - never by first running a real/simulated capture conversation
  just to get data in place. Apart from that seeding step, the test itself has NO mocking of
  any kind - the OpenAI client is never monkeypatched/stubbed here (unlike
  `test_ledger_query_conversation_routing.py`'s stubbed responses) - every model call is real,
  same as every other file in `tests/billed/`.**
  **Correction (2026-08-23): does NOT need `denidin-app` dev running.** Checked against
  `test_ledger_event_capture_billed.py`/`test_reminder_lifecycle_billed.py`'s own established
  pattern before writing this file — every existing `billed` test constructs the app entirely
  in-process (`denidin.initialize_app(config_dict)`) against `config.test.json`'s own real
  OpenAI credentials and isolated `test_data/` root, exactly like the Phase 2 integration
  tests' `denidin_app` fixture — none of them touch the `denidin-app-dev`/`morning-mcp-app-dev`
  Docker containers at all. The earlier draft of this task wrongly assumed a running container
  was needed; fixed before writing any code against that wrong assumption.
  **Seeding convention applied**: every scenario seeds 6 distractor/noise events (different
  clients, last month, different amounts) alongside its target data, via `_seed_noise`.
  **All test amounts kept ≤100 (user directive, 2026-08-23)** — e.g. ₪45 instead of ₪5,000 -
  applies uniformly across every scenario, including the 25-event T013 cap test.
  **Dates are `now_local()`-relative** ("this month"/"last month" helpers, never a hardcoded
  calendar month) so the file doesn't go stale on a future rerun; prompts say "החודש" rather
  than a specific month name for the same reason. **Each test gets its own fresh, isolated
  chat_id/session** (`_fresh_chat_id`, godfather's real phone + a unique per-test suffix) -
  the 11 tests never share conversation history with each other, even though they share the
  same underlying `test_data/events/` pool within one pytest run.
  Full suite (1169 unit+integration) still green after adding this file; `pylint` 7.33/10
  (the remaining findings are the SAME `E1135` false-positive pattern - pylint's Optional-
  narrowing across an `assert x is not None` boundary - already present and accepted in
  `test_reminder_lifecycle_billed.py`).
  **NOT YET RUN for real** — writing and running happen together per §VI.a, but the actual
  run against real OpenAI still needs its own fresh, explicit go-ahead (this task wrote the
  code; running it billed-for-real is the next, separate step). On failure: fix forward (real
  acceptance validation against completed code, not a RED-phase check).
- [ ] **T016** 👤 **MANUAL APPROVAL GATE**: run `quickstart.md`'s full scenario set for real,
  alongside or after T015 — including the owed-balance cross-event-type reasoning scenario
  (kept manual-only per user decision, 2026-08-23 — model arithmetic in free text is less
  stable to assert on automatically than structured tool-call behavior) and startup index
  reload (needs its own separate, explicit approval to restart the dev environment).

**Checkpoint**: the whole feature is proven to work end-to-end from a real user's
perspective, across all three user stories. This is the feature's actual "done."

---

## Dependencies

- Within Phase 1: T001b depends on T001a. T002b depends on T002a AND T001b. T003b depends on
  T003a AND T001b. T004b depends on T004a (and conceptually sits "first" inside `query_events`,
  but can be implemented/tested in any order relative to T002/T003 since it's a pure early-return
  guard with no interaction with the other filters).
- Within Phase 2: T005b depends on T005a. T006b depends on T006a AND T005b (needs the tool
  schema/RBAC wiring to exist before dispatch can be wired to it) AND all of Phase 1 (needs a
  real `query_events` to call). T007a can be drafted in parallel with T005a/T006a (`[P]`,
  different file), but T007b depends on T005b + T006b + T007a-approved.
- **Phase 2 depends on Phase 1 being fully complete** (T001b/T002b/T003b/T004b all GREEN) —
  `_handle_query_ledger_events` has nothing real to call otherwise.
- **Phase 3 depends on BOTH Phase 1 and Phase 2 being fully complete.** T008-T014 (the
  user-experience descriptions, no code) can be written early/in parallel with either phase
  since every scenario is already fully known from `spec.md`/`user-stories.md`/this revision,
  but T015 (write the actual test code AND run it) and T016 (manual gate) cannot start until
  every earlier phase is GREEN.
- T007c (the constitution section) has no code dependency but should land before T013's
  20-item-cap scenario is actually run (T015), since that scenario exercises the guidance
  T007c writes — drafting T013's description doesn't need to wait, only T015's real run does.

## Parallel Execution

- T001a, T002a, T003a, T004a can all be drafted in parallel initially (same file, but
  non-overlapping test functions covering independent concerns) — though T002a/T003a/T004a's
  fixtures naturally converge once T001a's index-loading fixture shape is approved, so drafting
  T001a first and reusing its fixture is more efficient than fully parallel drafting in practice.
- T005a and T006a can be drafted in parallel with each other; T007a can be drafted in parallel
  with both (different file); T007c (constitution prose) has no file overlap with any of these
  and can be drafted any time.
- T008-T014 (Phase 3's user-experience descriptions) can each be written in parallel with
  Phase 1 and/or Phase 2's work, and with each other, since what each scenario should do
  end-to-end is already fully known — only T015/T016 are gated on both phases being GREEN.

## Implementation Strategy

**MVP = Phase 1 + Phase 2 together** — unlike Feature 056's two genuinely independent tools,
this feature has exactly one tool and one manager method; there is no meaningful "ship half of
it" increment. Phase 1 alone has no user-visible effect (nothing calls `query_events` yet);
Phase 2 alone has nothing to wire to. Once both are GREEN, the feature is code-complete and
Phase 3 (`billed` acceptance, all three user stories) is the single final proof pass.
