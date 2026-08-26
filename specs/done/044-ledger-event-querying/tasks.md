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
trying to out-clever it — **correction, 2026-08-24: this was a decision, not a completed
implementation — no such fixture actually existed in the test file, and `test_payer_name_search`
accumulated four leftover identical records across separate manual runs as a direct result.
Now genuinely implemented as a directory-wide autouse fixture in `tests/billed/conftest.py`
(`_clean_ledger_events_around_every_test`), covering this file and every other billed test in
the directory — see `.github/METHODOLOGY.md` §VI.a point 5 for the resulting standing rule.**;
(3) the two-client "A or B" multi-criterion test was replaced with a
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

- [x] **T008** [P] **[TDD — DESCRIBE NOW, IN USER-EXPERIENCE TERMS]** US1 core lookups, in a
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
- [x] **T009** [P] **[TDD — DESCRIBE NOW, IN USER-EXPERIENCE TERMS]** US1 ambiguity handling,
  same file: (1) two distinct clients with names that both fuzzy-match a short/partial query
  name → reply asks which client is meant, listing both — never guesses one (US1 scenario 3 /
  Decision 4); (2) **the "both/all" follow-up** (new) — continuing scenario (1)'s
  conversation, reply "גם וגם"/"שניהם" (both) → DeniDin issues one `query_ledger_events` call
  per confirmed distinct name (assert TWO calls happened this turn, per research.md Decision
  10) and its reply reflects BOTH clients' events combined, not just one.
- [x] **T010** [P] **[TDD — DESCRIBE NOW, IN USER-EXPERIENCE TERMS]** US2 aggregation
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
- [x] **T011** [P] **[TDD — DESCRIBE NOW, IN USER-EXPERIENCE TERMS]** US1/US2 genuine
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
- [x] **T013** [P] ~~20-item display cap~~ **REMOVED (2026-08-26, user directive)** — its
  `billed` test (below) reached OpenAI and failed on a real run: the model grouped 25 events
  into five date-range buckets but still named all 25 clients individually, which the test's
  strict "count distinct events named ≤ 20" check rejected. User's read: there's no point
  steering the model to overcome a barrier aimed at protecting reply length, when the actual,
  strictly-enforced backstop is the reply's own output-token budget, not a specific event
  count. `runtime_constitution.md`'s "Ledger Event Querying" section was reworded from a fixed
  20-event cap to general "keep it readable for WhatsApp, use your own judgment" guidance, and
  the corresponding `billed` test was deleted outright rather than adjusted to a softer
  assertion (see the T015 test file for the removal note). Originally added 2026-08-23
  (concrete/testable, distinct from the owed-balance case which stays manual-only): seed MORE
  than 20 real matching events for a broad query → ask a question that would match all of
  them → assert the reply does not enumerate more than 20 individual events verbatim.
- [x] **T014** [P] **[TDD — DESCRIBE NOW, IN USER-EXPERIENCE TERMS]** Natural-language
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
  **Explicitly SKIPPED at feature close (2026-08-26, user decision: "skip T16, mark the rest as
  done - go haleluya!")** — the extensive real, automated `billed` acceptance coverage
  (T015/T017-T029, all passing against real OpenAI) was judged sufficient proof on its own;
  this manual WhatsApp walkthrough was not performed. Left unchecked deliberately rather than
  marked done, so this gap stays visible rather than silently implied-covered.

**Addendum, 2026-08-24 (query-engine redesign, discovered via T008.4's real failure)**: running
T008.4 (`test_payer_name_search`) live surfaced that the query engine's actual design is wrong,
not just that one test's prompt — real, per-field AND-combined structured filters
(`source_type`/`event_subtype`/`amount_min`/`amount_max` alongside the two separate fuzzy
mechanisms `client_name`/`free_text`) let the model accidentally exclude a genuine match by
over-constraining a single call, and can't express OR/NOT/threshold reasoning at all. Agreed
redesign (user decision, 2026-08-24), **not yet implemented** — this replaces `client_name` +
`free_text` + `source_type`/`event_subtype`/`date_from`/`date_to`/`amount_min`/`amount_max`
entirely with:
- A single fuzzy `text` search reaching every field on a record, structured or not (identity,
  description, `reference_hint`, `trigger_condition`, numbers/dates in their string form —
  literally everything, not a hand-picked subset).
- Each `text` value carries an optional **hint** naming a **closed group** of fields it's
  most likely targeting (e.g. `identity` → exactly `client_name`/`payer_name`; `date` →
  `event_datetime`/`txn_date`; other groups TBD during implementation) — a *soft* weighting
  signal that boosts relevant fields' scoring, never a hard filter a match must satisfy. A
  ledger field may belong to 0-N hint groups.
- A call may carry **multiple** `(text, hint)` pairs. Retrieval happens first, broadly, THEN
  every candidate is scored against all supplied pairs — filtering never happens before
  retrieval. Each returned match carries a confidence/score, not just a boolean in-or-out.
- Explicit **OR**: the model issues multiple `(text, hint)` pairs (or multiple calls, exact
  mechanics TBD) for alternative criteria and the low-level engine (or the model over raw
  results) combines them — never a single AND-only pass that can only narrow.
- Explicit **NOT** / exclusion and **numeric threshold** reasoning (e.g. "amount above 100",
  "percent above 50") are NOT expected to be solved by the retrieval layer's scoring at all —
  the tool returns the broad, relevant candidate set (by category/hint), and the model does the
  actual exclusion/comparison arithmetic itself over the raw returned events, same principle
  research.md Decision 5 already established for aggregation.
- Real embeddings (mirroring `MemoryManager`'s existing ChromaDB/OpenAI-embedding pattern) were
  discussed and explicitly deferred, not adopted — the ledger is small and fully structured
  (unlike free-form memory text), so a rapidfuzz-based soft scorer was chosen as the concrete
  starting design; revisit only if the scored/weighted approach proves insufficient in practice.
- **Full field→hint-group mapping, the exact OR/NOT calling convention, and the confidence
  scoring formula are still open design questions** — none of this is implemented yet.
  Phase 1/2's existing code (`query_events`, `QUERY_LEDGER_EVENTS_TOOL`, `_handle_query_ledger_events`)
  and every already-written unit/integration test will need real rework once the design is
  finalized — **the 11 already-written T015 `billed` tests themselves need NO changes** (user,
  2026-08-24 — they cover real, still-valid scenarios; they were just an incomplete set, and
  the current, wrong implementation is what would have made a broader set fail).

**Redesign implementation — DONE (2026-08-24), same day as the addendum above.** All of the
"still open" items above are resolved; see `research.md`'s "2026-08-24 Redesign" section for
the full field→hint-group mapping (`_HINT_GROUPS`), the OR/NOT calling convention (both reuse
existing mechanisms — multi-call dispatch for OR, "model reasons over raw events" for NOT/
threshold — no new schema needed for either), and the confidence formula (mean of per-criterion
scores, each of which must individually clear `_CRITERION_MATCH_FLOOR`). Concretely:
- `LedgerEventManager.query_events(criteria: Optional[List[Dict]])` replaces the old
  8-parameter signature entirely — `src/managers/ledger_event_manager.py`.
- `QUERY_LEDGER_EVENTS_TOOL`'s JSON schema (`src/handlers/ai_handler.py`) now exposes
  `criteria: [{text, hint}]` instead of the 8 old separate parameters; `_handle_query_ledger_events`'s
  dispatch (`self.ledger_event_manager.query_events(**call["arguments"])`) needed no change —
  it already unpacks whatever keys the model supplies.
- `tests/unit/test_ledger_event_manager.py`'s `TestQueryEventsStructuredFilters`/
  `TestQueryEventsFuzzyMatching`/`TestQueryEventsVagueQueryGuard` (old 8-parameter shape) were
  replaced with `TestQueryEventsCriteriaMatching`/`TestQueryEventsIdentityAmbiguity`/
  `TestQueryEventsVagueQueryGuard` (new `criteria` shape) — 171 tests passing.
  `tests/unit/test_ai_handler_ledger_query.py` updated to build `criteria`-shaped call
  arguments (`_criteria_args` helper) — 16 tests passing. `tests/integration/
  test_ledger_query_conversation_routing.py` (6 tests) also updated to the new shape — all
  6 passing. Full suite (`tests/unit/` + `tests/integration/`): **1274 passed**.
- `config/runtime_constitution.md`'s "Ledger Event Querying" section rewritten to describe the
  unified `criteria`/`hint` mechanism and the OR/NOT/threshold guidance.
- `data-model.md`, `research.md`, and `contracts/query-ledger-events-tool.md` all updated to
  describe the new design (the old 8-parameter shape is kept only as historical/superseded
  context, clearly marked as such).
- Six real scoring bugs found via empirical sanity-testing (not assumed correct) and fixed —
  see `research.md`'s "Three scoring bugs found via empirical sanity-testing" subsection (now
  six, despite the heading) for the full list: raising `_CRITERION_MATCH_FLOOR`, numeric-only
  comparison for numeric queries, per-criterion-must-individually-clear-the-floor, identity
  fields needing `_NAME_MATCH_THRESHOLD` specifically, `accounting_document_display_number`
  needing numeric-not-fuzzy scoring, and (found last, via the integration-test rewrite) a
  general short-stored-value gate (`_SHORT_VALUE_LENGTH_THRESHOLD`/
  `_SHORT_VALUE_MATCH_THRESHOLD`) after short filler/categorical values (`event_subtype`,
  `component_label`) twice produced spurious cross-matches against unrelated real names.

**Still pending, NOT part of "done" above**: re-running the 11 existing T015 `billed` tests
against the new engine (prompts unchanged, per user's explicit instruction — only the
implementation changed) requires fresh, explicit user approval before running, per a standing
instruction given during this same investigation ("do not rerun the test without my approval!
only investigate") — not yet requested/granted as of this note. `test_monthly_income_aggregation`
(T008.8)'s original failure was never root-caused (investigation was superseded by the redesign
before returning to it) and needs re-checking against the new engine. T017-T020's actual test
code (below) has not been written or run yet — still description-only, per this feature's
Phase 3 convention (write+run together, once, at the very end).

**New Phase 3 scenarios (2026-08-24, user directive — described now, in user-experience terms
only, exactly like T008-T014; NOT test code yet, and depend on the redesign above actually being
implemented first)**:
- [x] **T017** [P] **[TDD — written and run, GREEN]** Explicit OR across two
  distinct, unambiguous identities in ONE request (distinct from T009.2's "both/all"
  follow-up, which is a two-turn confirm-then-merge flow after an ambiguity prompt — this is a
  single-turn OR named up front, no ambiguity involved at all): real pre-seeded בנק/הפקדה
  deposit events, one for "אלי אבירם" and a separate one for "דוד כרמון", both amount 100,
  plus the usual noise events for other clients/months — "האם קיבלנו תשלום של 100 שקל מאלי
  אבירם או מדוד כרמון?" ("did we receive a payment of 100 shekel from Eli Aviram or David
  Carmon?") → reply correctly reports BOTH matching payments (not just one), each correctly
  attributed to its own name.
- [x] **T018** [P] **[TDD — written and run, GREEN]** Explicit NOT/exclusion
  combined with a numeric threshold, over a field never exercised by any earlier scenario
  (`percent`) — real pre-seeded percentage-based fee agreements (`percent` field populated,
  `source_type="הסכם"`) for at least three distinct clients: one named "קרן שלו" at 60%, and
  two or more others at values above 50% too (so the exclusion is the only thing narrowing the
  answer, not the threshold alone), plus at least one other client at or below 50% as a
  negative control — "מי, חוץ מקרן שלו, הסכים על אחוזים מעל 50%?" ("who, other than Keren
  Shalev, agreed to percentages above 50%?") → reply lists the other above-50% client(s) by
  name and correctly EXCLUDES קרן שלו even though her own agreement genuinely is above 50% —
  proving real exclusion reasoning, not just threshold filtering.
- [x] **T019** [P] **[TDD — written and run, GREEN]** Broad-category +
  numeric-threshold reasoning with no name given at all (the "who owes above 100 shekel"
  scenario from the redesign discussion itself) — real pre-seeded הסכם (agreement, i.e. owed,
  unpaid) events for several distinct clients spanning a range of amounts, at least two above
  100 and at least two at-or-below 100 (a real negative control, not just an absence), plus a
  separate בנק/הפקדה deposit event for one of the above-100 clients in the SAME period (a
  paid, not owed, control — must NOT be counted as still-owed regardless of its own amount) —
  "מי כל הלקוחות שחייבים לי מעל 100 שקל?" ("which clients owe me more than 100 shekel?") →
  reply correctly lists only the genuinely-still-owed clients above the threshold, by name,
  excluding both the below-threshold clients and the one client whose amount was already paid.
- [x] **T020** [P] **[TDD — written and run, GREEN]** Cross-category retrieval
  for ONE identity in a single turn — two DIFFERENT facts about the same client, from two
  different event categories, reported side by side (distinct from T016's manual-only
  owed-balance scenario, which requires computing a subtraction/difference; this only requires
  correctly retrieving and stating two separate numbers without conflating them, so it's
  automatable): real pre-seeded events for "משה כהן" — one הסכם (agreement) event, amount 45
  (what was agreed), and one separate בנק/הפקדה (deposit) event, amount 20 (what he's actually
  paid so far, deliberately a different value so the two figures are distinguishable in the
  reply), plus the usual noise events for other clients/months — "כמה משה כהן הסכים לשלם, וכמה
  הוא שילם עד היום?" ("how much did Moshe Cohen agree to, and how much did he pay to date?") →
  reply correctly states BOTH figures (45 agreed, 20 paid), each attributed to the right
  question, not conflated into one number or only answering half the question.

**Checkpoint**: the whole feature is proven to work end-to-end from a real user's
perspective, across all three user stories. This is the feature's actual "done."

---

**Addendum, 2026-08-25 (real billed-test crash → architectural loop-dispatch fix, debug
logging, hint-group redesign)**: running `test_monthly_income_aggregation` (already-committed
Phase 3 acceptance test) crashed with `AIResponse.__post_init__`'s "owes a reply but carries no
text" `ValueError`. Root cause was NOT this feature's own code — `_finalize_response`
(`ai_handler.py`) ran each local-tool handler (`capture_ledger_event`/`query_ledger_events`/
`list_reminders`) at most ONCE against the turn's ORIGINAL response, never re-checking a
follow-up response for a further legitimate tool call; when the model genuinely needed a
second local-tool round-trip, nothing executed it and `output_text` stayed empty. Fixed with a
real dispatch loop, `_run_local_tool_dispatch_loop()` (`MAX_LOCAL_TOOL_LOOP_ITERATIONS = 5`),
replacing the old fixed one-hop chain, plus a generic empty-`response_text` safety net
(`LEDGER_FOLLOWUP_FAILED_TRY_AGAIN`) that now also covers `query_ledger_events`/
`list_reminders` follow-up failures, not just `capture_ledger_event`'s pre-existing one. Massive
raw-request/response logging (`_log_outgoing_request`/`_log_raw_response`, called at all 11
`responses.create()` call sites app-wide) and deep `[044][SCORE]`/`[044][RAWLOG]` scoring-
internals tracing (`_score_criterion`/`query_events`) were added alongside, per explicit user
directive ("disk space is not a constraint") — all DEBUG-gated, zero cost when DEBUG is off.

Using the new logs to diagnose a subsequent live rerun surfaced a genuinely separate, real
design gap this feature's own schema/prompting had: a time-scoped question ("how much income
this month") could be answered with a category-only criterion, no `date` criterion at all —
`query_events` does no date filtering of its own by design, so this is silently unsafe against
real multi-month history (the test's own fixture happened not to catch it - see
`research.md`/`data-model.md` for the full analysis). Fixed via explicit tool-description and
`config/runtime_constitution.md` guidance: any time-scoped question always needs a paired
`date`-hinted criterion.

Investigating that gap triggered a full user review of `_HINT_GROUPS` itself (user: *"why are
those in this 'category'??? They are unrelated... you cant use 'category' as a categorical enum
value - that is way misleading"*), which found the group conflated three unrelated axes
(event classification, VAT treatment, document lifecycle status) and that `hint`'s own JSON
schema carried no per-value documentation at all (the mapping existed only in a separate prose
paragraph in the tool's top-level `description`, far from the enum). Redesigned to 9 groups —
`identity` (now also `split_partner`), `date` (now `event_datetime`/`txn_date` only), new
`event_type` (`source_type`/`event_subtype`), new standalone `vat`, `amount`, `percentage`,
`free_text` (renamed from `description`, `component_label` dropped from search entirely - it
exists only to derive `component_id`, never a real search target), `document` (now also
`accounting_document_status`/`accounting_document_status_label`), `banking` — `split` group
eliminated (its one field moved into `identity`). Per-value documentation moved onto the `hint`
parameter's own schema `description`, co-located with the enum.

Same review also removed two fields entirely, from the persisted schema, `_HINT_GROUPS`, and
every doc/test reference (user directive, emphatic - *"GET RID OF THIS FIELD, I DONT WANT TO
SEE IT EVER AGAIN ANYWHERE"*): `due_date` (a dead, always-null reserved-for-later field with no
populating code path anywhere), and `accounting_document_creation_date` (a byte-for-byte
duplicate of `event_datetime` for every חשבונית record it ever appeared on). `event_datetime`
is now the sole creation-date field, for every `source_type` alike. The internal mechanism that
derives it for a reconciliation-sourced document (Morning's own real `creation_date`, never the
capture instant) still works, now via a private, never-persisted intermediate key rather than
a field name that also happened to leak into the schema. This also retired
`AIHandler._accounting_document_message_timestamp` entirely - a second, independent derivation
of the same value that, on inspection, never actually fired in real production traffic (it read
the raw, un-expanded call arguments, which never carried this field) - its ISO-8601 robustness
test coverage moved to a new unit-test class exercising the function that actually runs
(`LedgerEventManager._parse_iso_local`).

`CURRENT_SCHEMA_VERSION` stays **2** — a stray, since-superseded 2→3 bump from an earlier
intermediate commit was corrected back down (user: *"I dont know who or why it was bumped. It's
2!"*), and today's field-removal/hint-redesign change was judged not schema-affecting enough on
its own to bump further. Every test asserting `schema_version` now compares against the
imported `CURRENT_SCHEMA_VERSION` constant rather than a hardcoded literal (user correction:
*"you should never assert on the sche[ma] version! what happens when it goes up?"*), so a real
future bump needs no test edits.

Full verification after all of the above: 1273/1273 unit+integration tests pass, pylint
9.52/10 (unchanged from baseline, zero new findings), mypy shows the same 4 pre-existing
baseline errors (zero new).

**Addendum, 2026-08-26 (billed-test sweep resumed → T013 20-item cap removed)**: resuming the
paused Phase 3 `billed` sweep, `test_twenty_item_display_cap` (T013) reached OpenAI and failed
on a real run - the model grouped 25 seeded events into five date-range buckets in its reply
but still named all 25 clients individually, which the test's strict "≤20 named events" check
rejected. User's call: don't try to make the model reliably overcome an artificial numeric
barrier when the real, strictly-enforced constraint is the reply's own output-token budget, not
a specific event count. `runtime_constitution.md`'s "Ledger Event Querying" section was
reworded from a fixed 20-event cap to general "this is a WhatsApp conversation, keep it
readable, use your own judgment" guidance (no number to target), and the test was deleted
outright (see T013's own entry above) rather than softened to a looser assertion. Sweep
resumed from test 9 (`test_four_way_multi_criterion_with_date_range`, passed) through test 10
(`test_twenty_item_display_cap`, failed → removed per above); tests 11-15
(`test_natural_language_exclusion` onward) still pending a resumed run against this change.

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

**Addendum, 2026-08-26 (owed/received semantics + T021-T029 + identity-ambiguity gate removal)**:

- **"What counts as owed vs. received" — new `runtime_constitution.md` section.** Per detailed
  user specification: owed (debit) signals are `הסכם` (agreement, may be modified/cancelled by
  a later `הסכם` for the same client — report the CURRENT state, never sum blindly), Morning
  type 300 (חשבון עסקה, payment request), and type 305 (חשבונית מס, tax invoice) — non-exclusive,
  reconciled by same-client + same-amount (not date) dedup, diverging figures get a clarifying
  question. Received (credit) signals are בנק/הפקדה and Morning type 320/400 receipts, net of
  type 330 credit notes (which reverse a receipt, not an agreement). All joined by `client_name`.
  A companion "Multi-round search: look, then look again" section establishes the general
  principle (search by client name FIRST, broad, then follow up based on what comes back) that
  underlies this reasoning.
- **9 new `billed` tests (T021-T029)**, each seeding real data via `_seed`/a new
  `_seed_accounting_document` helper (never a simulated capture conversation): T021 (transaction
  account with no agreement at all), T022 (tax invoice closed by its own receipt, excluded from
  a combined owed sum), T023 (credit note reverses a receipt, invoice stays owed), T024
  (agreement modification reports the latest state — client renamed from אורי כספי to שלומית
  ברגר mid-session after it fuzzy-collided with `_seed_noise`'s "אורית כרמי"), T025 (dedup of a
  matching deposit+receipt), T026 (combined owed across two unrelated clients, proving real
  multi-round tool use), T027 (a conditional agreement component whose trigger never confirmed
  stays genuinely uncertain, never guessed either way), T028 (a payment recorded under a
  different payer's name still resolves once the user clarifies the relationship), T029 (a
  one-character client-name typo resolved or clarified, never silently dropped). All 9 pass.
- **Identity-ambiguity CODE gate removed from `query_events`** (explicit user directive: *"why
  is there a CODE ambiguity check?! It should all be done in the model! Remove the code check
  for ambiguity!"*). The tool used to intercept an `identity`-hinted criterion matching 2+
  distinct stored `client_name`/`payer_name` values and return a `{"ambiguous_field": "identity",
  "candidates": [...]}` shape INSTEAD of real events — found, via T028, to have no escape valve:
  every future call touching either name re-triggered the identical block, even after the user
  had already resolved the ambiguity in conversation, stalling the model into "I can't determine
  this from the search" instead of ever answering. Removed `_distinct_name_candidates`/
  `_count_events_for_name` and the blocking early-return entirely; `query_events` now always
  returns real scored matches, and recognizing/resolving multiple distinct names is the model's
  own judgment call, per a rewritten "Ambiguous names, OR, NOT, and threshold questions"
  constitution section. Audited for similar code-level judgment gates elsewhere in this same
  method: `_CRITERION_MATCH_FLOOR`/the identity-specific `_NAME_MATCH_THRESHOLD` scoring gate
  were kept (relevance/precision mechanisms, not business decisions — removing them makes
  matching too noisy to function, confirmed via the module's own documented empirical scores);
  the `no_search_criteria` empty-criteria guard was kept (removing it causes a real
  `ZeroDivisionError`, not a judgment call being made on the model's behalf). Re-verified after
  removal: `tests/unit/test_ledger_event_manager.py` (175/175), plus all three tests whose
  behavior actually depends on this mechanism — T009 (pre-existing ambiguity test, still asks a
  clarifying question on pure model judgment), T029 (still asks), and T028 (now resolves in ONE
  search, one turn, no clarification loop needed — confirmed via the real reply text, not a
  substring-match artifact).

### Follow-up (not part of this feature — separate task, do not action here)

**DONE (2026-08-26), per explicit user decision ("yes, do all 3. bugfix is 46"):** the three
items below are now real, filed spec files under `specs/bugfixes/` rather than loose pointers —
this section is kept only as a historical index into them. None of the three has been
investigated or actioned beyond filing/cross-referencing — root-cause work on all three is still
fully separate from Feature 044, per Bug-Driven Development (METHODOLOGY.md §VII: symptom filed →
human approval → investigation, in that order).

- **`specs/bugfixes/bugfix-045-refuses-to-create-new-client-despite-clear-request.md`** — brought
  into this branch from `origin/master` (it postdates this feature branch's fork point) and
  extended with a "Related Occurrence (2026-08-26)" section: a second, independently-triggered
  case of the same failure shape, found via
  `test_godfather_creates_credit_note_against_real_invoice` during this feature's closing
  regression sweep — a diacritic round-trip on a just-created client name (`שאדן בוגדנין` vs.
  Morning's own `שׁאדן בוגדנין`) causes `resolve_client_name` to report "similar, not exact,"
  and a plain "כן" cannot resolve a multi-option question. That new section also carries the
  cross-reference to this feature's removed identity-ambiguity gate as a candidate fix direction
  (same principle: don't force a canned "insufficient" response when real candidates exist — let
  the model reason over them).

- **`specs/bugfixes/bugfix-035-hourly-maintenance-bugs.md`** — extended with a new "H3" section:
  `test_session_transfer.py::test_session_transfer_and_recall_after_expiration` failed during the
  2026-08-26 random-20-billed-test sweep (`AssertionError: Archived session ID should match` — an
  unscoped `expired_dir.rglob("*/session.json")[0]` picked up a stale, pre-existing archived
  session instead of the one the run itself created and expired). Filed as H3 under bugfix-035 by
  explicit user decision, alongside H1/H2, rather than as its own separate bug.

- **`specs/bugfixes/bugfix-046-list-invoices-status-filter-contradicts-unfiltered-result.md`**
  (new) — Morning's `list_invoices` status filter returns an empty/contradictory result.
  Uncovered by `test_client_explicit_everything_request_gets_the_complete_picture` (2026-08-26
  random-20-billed-test sweep): `list_invoices(client_name="דורית אשכנזי")` returned several
  `שולם` (paid) invoices, but an immediately-following `list_invoices(client_name="דורית אשכנזי",
  status="שולם")` came back with "לא נמצאו חשבוניות התואמות את החיפוש" (no matching invoices
  found) for the exact same client. Filed with full verbatim evidence; not investigated further,
  no root cause confirmed yet.
