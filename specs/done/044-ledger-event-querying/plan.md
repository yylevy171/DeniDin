# Implementation Plan: Ledger Event Querying via AI — Feature 044

**Feature**: 044-ledger-event-querying
**Branch**: `feature/044-ledger-event-querying`
**Spec**: `./spec.md` · **User Stories**: `./user-stories.md` · **Research**: `./research.md`
**Status**: PLANNED — ready for `speckit.tasks`
**Updated**: 2026-08-22

**Compliance**: CONSTITUTION.md (§I no env vars — N/A, no config touched; Israel local
time — N/A, date-range filtering reuses the model's own already-established relative-date
resolution, no new datetime-construction code; §III git workflow — on
`feature/044-ledger-event-querying`, off `master`; §V zero-mocking — new tests exercise the
real `LedgerEventManager`/`AIHandler` code paths directly, no internal component mocked;
§XVII no monkey-patching — a new manager method + a new local tool, no runtime patching).
No feature flag: this is purely additive (a new tool, only ever attached for
godfather/admin, never changes any existing behavior when absent) — satisfies "default
behavior unchanged" without needing a toggle, same reasoning `create_reminder`/Feature 054
used.

---

## Summary

One new local `function` tool, `query_ledger_events` (contracts/query-ledger-events-tool.md),
backed by a new in-memory index inside the existing `LedgerEventManager` (data-model.md).
Lets a godfather/admin ask natural-language questions about previously captured ledger
events — explicit ("what did we agree on with X") or implicit ("how much does X still
owe," requiring the model to find and reason over both the agreement and payment events
itself) — without a human ever opening raw JSON files, and without injecting the whole
ledger into every conversation's context.

Matching mechanism (research.md, Decisions 1-3): code-side fuzzy string scoring
(`rapidfuzz`) for name and free-text fields; plain deterministic min/max ranges for
dates/amounts, with the model responsible for its own "how wide should I search" reasoning.
No embeddings, no semantic index, no new external service. No server-side aggregation
(Decision 5) — the tool always returns raw matching events; the model does any arithmetic
itself, same as it already does for any other financial reasoning in conversation
(including a broad "income this month" question — Decision 11 — which means `source_type=
"בנק"` deposits specifically, summed by the model, never a computed tool-side total).

Arbitrarily complex requests — "client A or B," multiple disjoint date ranges, "both" as an
answer to a disambiguation question — are handled WITHOUT any schema richer than one
name/one date range/one amount range per call (research.md Decision 10): the tool
explicitly permits, and its own description invites, multiple `query_ledger_events` calls
in the same turn, one per criterion, combined by the model itself. This deliberately mirrors
— and inverts — `capture_ledger_event`'s existing bugfix-018 multi-call handling: that tool
(a WRITE) rejects the whole turn if called more than once, to prevent ledger corruption from
a truncation-induced duplicate-call burst; this tool (READ-ONLY) has no such risk, so
multiple calls per turn are safe and expected, reusing the same `extract_all_function_calls`/
multi-item-`function_call_output` machinery already proven out for `capture_ledger_event`.

## Technical Context

- **Language/Version**: Python 3.9 (`apps/denidin-app`'s existing venv — confirmed via
  `logs/test_logs/pytest_results/*.txt` headers, not assumed).
- **Primary Dependencies**: **new** — `rapidfuzz` (research.md Decision 2), added to
  `apps/denidin-app/requirements.txt`. No other new dependency; reuses the existing
  `LedgerEventManager`/`AIHandler`/Responses-API-follow-up machinery.
- **Storage**: no new persistence — the in-memory index is rebuilt from the existing
  `{data_root}/events/*.json` files at startup (data-model.md); nothing new is written to
  disk by this feature.
- **Testing**: `apps/denidin-app/tests/unit/` (fuzzy-matching scoring logic, vague-query
  guard, entity-ambiguity grouping — all pure functions/methods, real `LedgerEventManager`
  instance, no mocking needed) + `apps/denidin-app/tests/integration/` (a real webhook-shaped
  turn dispatched through `bot.router`, asserting `query_ledger_events` is attached/not
  attached per role, and that a same-turn follow-up round-trip actually happens — same
  pattern `list_reminders`' own integration coverage already established) +
  `apps/denidin-app/tests/billed/` for the four representative user-perspective scenarios
  (§VI.a — real OpenAI text calls, described now in `tasks.md`'s Acceptance phase, written
  and run once at the end).
- **Target Platform**: `apps/denidin-app` only — no morning-mcp-app involvement, no new
  container/runtime, no cross-app contract. Requires the usual rebuild-and-redeploy step
  once merged (a separate, explicit human decision per CLAUDE.md, not part of this plan).
- **Scale/Scope**: one new manager method (`LedgerEventManager.query_events`) plus index
  load/append wiring, one new local tool schema, one new `AIHandler` dispatch method +
  follow-up-call method (mirroring `_handle_list_reminders`/
  `_call_openai_list_reminders_followup_api`), one new RBAC constant, one new
  `requirements.txt` line.

## Constitution Check

- **No env vars** — PASS: nothing here touches config-loading.
- **Israel local time** — N/A: `date_from`/`date_to` are plain `YYYY-MM-DD` strings the
  model already resolves itself (no new "what is today" logic — reuses the existing
  `_build_instructions` current-date injection); no new datetime arithmetic is introduced by
  this feature beyond string-range comparison.
- **Feature branch** — PASS: `feature/044-ledger-event-querying`, off `master`.
- **Feature flags** — N/A, see Compliance note above (purely additive, RBAC-gated,
  no-tool-attached-means-byte-identical-to-today).
- **Zero-mocking** — PASS: unit tests exercise `LedgerEventManager`/the new tool-dispatch
  logic directly against a real (temp-dir-backed) instance; integration tests dispatch a
  real webhook-shaped notification through `bot.router`, per CONSTITUTION §V; `billed` tests
  make real OpenAI calls.
- **No monkey-patching** — PASS: new code paths only (a new manager method, a new tool
  constant, two new `AIHandler` methods, one new RBAC tuple) — no runtime method
  replacement.
- **Test immutability (§VIII)** — PASS: no existing test file is touched; all new coverage
  lives in new test functions/files.
- **NO UNVERIFIED THIRD-PARTY ASSUMPTIONS** — N/A: this feature has no third-party network
  dependency at all (pure local matching over already-owned data) — the one real "unverified
  assumption" risk this project usually flags (an external API's actual behavior) doesn't
  apply here.
- **New dependency justification** (not a standard Constitution Check line, but flagged per
  this project's general "no unnecessary new deps" bias) — see research.md Decision 2:
  `rapidfuzz` is justified because fuzzy matching is the feature's core stated requirement,
  not an incidental convenience; the stdlib alternative would mean hand-rolling exactly what
  it already provides, tested.

## Project Structure

### Documentation (this feature)

```text
specs/in-progress/044-ledger-event-querying/
├── spec.md               # done — no [NEEDS CLARIFICATION] markers, checklist passed
├── user-stories.md       # done
├── research.md           # done — query-surface/matching-mechanism decisions (2026-08-22)
├── plan.md               # this file
├── data-model.md          # done
├── contracts/             # done — query-ledger-events-tool.md
├── quickstart.md          # done
└── tasks.md               # NOT YET STARTED (/speckit.tasks)
```

### Source Code

```text
apps/denidin-app/requirements.txt
├── + rapidfuzz (new dependency, research.md Decision 2)

apps/denidin-app/src/managers/ledger_event_manager.py
├── __init__: build self._index (List[Dict]) by scanning {data_root}/events/*.json at
│   construction — corrupt files skipped + logged (FR-007), never abort the load. No lock
│   (user decision, 2026-08-23 — research.md Decision 8's "Concurrency" note).
├── add_ledger_event: after the existing atomic file write succeeds, append the new record
│   to self._index (FR-003) — same method, no separate sync step.
├── NEW: query_events(client_name, date_from, date_to, amount_min, amount_max,
│   source_type, event_subtype, free_text) -> dict
│   Returns one of data-model.md's three shapes (matches/candidates/no_search_criteria).
│   Implements: vague-query guard (all-None short-circuit), fuzzy name scoring +
│   entity-ambiguity grouping (research.md Decisions 4/6), free-text fuzzy scoring, plain
│   date/amount range checks (Decision 7), source_type/event_subtype exact filters.
├── NEW: module-level constants _NAME_MATCH_THRESHOLD = 70, _FREE_TEXT_MATCH_THRESHOLD = 60
│   (research.md Decision 3).

apps/denidin-app/src/handlers/ai_handler.py
├── NEW: LEDGER_QUERY_AUTHORIZED_ROLES = (Role.GODFATHER, Role.ADMIN) (research.md
│   Decision 9 — a new constant, not reused from MORNING_MCP_AUTHORIZED_ROLES/
│   REMINDER_AUTHORIZED_ROLES, matching this codebase's existing per-feature-constant
│   convention even where values coincide).
├── NEW: QUERY_LEDGER_EVENTS_TOOL: Dict[str, Any] (contracts/query-ledger-events-tool.md's
│   exact schema).
├── _build_reminder_tools-style NEW: _build_ledger_query_tools(user_obj) -> List[Dict],
│   RBAC-gated exactly like _build_reminder_tools.
├── _assemble_tools: append the new (RBAC-gated) ledger-query tool into the combined list,
│   alongside morning/ledger-capture/reminder tools.
├── NEW: _handle_query_ledger_events(request, response, tools) -> Optional[response]
│   NOT list_reminders' single-call pattern (research.md Decision 10) - uses
│   extract_all_function_calls (same helper capture_ledger_event already uses) since a
│   turn may contain SEVERAL query_ledger_events calls at once (this is how "client A or
│   B" / multi-date-range requests get answered - see research.md Decision 10). Runs
│   self.ledger_event_manager.query_events(**args) once per call independently (one
│   call's args/result never affect another's); a call whose arguments fail to parse gets
│   its own isolated error output (data-model.md shape D) without affecting any other
│   call from the same turn - the deliberate OPPOSITE of capture_ledger_event's bugfix-018
│   whole-turn rejection, safe here because nothing is written. Reports ALL calls back in
│   ONE follow-up call, return the follow-up response (or None if no call was made this
│   turn / the follow-up itself failed).
├── NEW: _call_openai_query_ledger_events_followup_api(...) — mirrors
│   _call_openai_ledger_followup_api's multi-item function_call_output batching (a list
│   comprehension, one output item per call_id), NOT
│   _call_openai_list_reminders_followup_api's single-item shape.
├── _finalize_response: wire the new handler in, same position/pattern as
│   list_reminders_followup (checked alongside it — a turn calls at most one read-only
│   query tool in practice, same assumption already made for list_reminders vs.
│   create/modify/delete_reminder).

apps/denidin-app/tests/unit/
├── test_ledger_event_manager.py (existing file, extended)
│   # index load-at-construction (including the corrupt-file-skip case), append-on-write,
│   #   query_events: name fuzzy match (single/ambiguous/no-match), free-text fuzzy match,
│   #   date-range (both date-bearing fields), amount-range, source_type/event_subtype
│   #   exact filters, AND-combination of multiple filters, vague-query guard (all-None),
│   #   entity-ambiguity grouping (2+ distinct matching names).
├── test_ai_handler.py (existing file, extended)
│   # LEDGER_QUERY_AUTHORIZED_ROLES gating in _assemble_tools (attached for godfather/
│   #   admin, absent for client/blocked); _handle_query_ledger_events dispatch + follow-up
│   #   wiring, mirroring existing test_ai_handler.py coverage for _handle_list_reminders.

apps/denidin-app/tests/integration/
├── (existing or new file covering ledger-query RBAC/dispatch wiring via a real webhook-
│   shaped notification through bot.router) — confirms the tool is genuinely
│   attached/executed/not-attached per role end-to-end, not just at the unit level.

apps/denidin-app/tests/billed/
├── (new file(s), Phase 3, §VI.a) — the four representative real-conversation scenarios:
│   US1 explicit lookup, US1 no-match, US1 ambiguous-name disambiguation, US2 date-ranged
│   summary. The owed-balance/cross-event-type reasoning scenario (quickstart.md step 6) is
│   exercised manually (quickstart.md), not as an automated billed test, since asserting on
│   the MODEL'S OWN arithmetic in a reply is inherently less stable than asserting on
│   structured tool-call behavior — same caution already applied elsewhere in this
│   codebase to model-authored free text.
```

## Phased Execution

**TDD note (METHODOLOGY §VI, redefined 2026-08-18)**: "Test" below, within Phase 1/2, means
§VI.b's unit/integration RED→GREEN discipline. "TDD" proper — §VI.a's `billed` user-
perspective tests — is only described (user-experience terms, no code) during these same
phases; actual test code is written and run together, once, in Phase 3.

### Phase 1 — Index + query engine (US1, P1)
1. **Test (§VI.b)**: unit tests for `LedgerEventManager`'s index load (incl. corrupt-file
   skip), append-on-write, and `query_events`'s matching logic across every filter
   individually and combined (RED).
2. **Implement**: `self._index`/`self._index_lock`, index-load-at-construction,
   append-in-`add_ledger_event`, `query_events`, `_NAME_MATCH_THRESHOLD`/
   `_FREE_TEXT_MATCH_THRESHOLD`, add `rapidfuzz` to `requirements.txt`. Tests go GREEN.
3. **Verify**: full existing `LedgerEventManager` test suite still passes unchanged
   (FR-008 — capture path byte-for-byte unaffected).
4. **TDD scenario (§VI.a)**: `tasks.md` describes (user-experience terms) US1's explicit-
   lookup, no-match, and ambiguous-name scenarios now — real test code written/run in
   Phase 3.

### Phase 2 — Tool wiring + RBAC (US1/US2/US3, ties the tool to AIHandler)
1. **Test (§VI.b)**: unit tests for `_build_ledger_query_tools`'s RBAC gating and
   `_handle_query_ledger_events`'s dispatch/follow-up wiring (RED); integration test
   dispatching a real webhook-shaped turn through `bot.router` confirming attachment/
   non-attachment per role (RED).
2. **Implement**: `LEDGER_QUERY_AUTHORIZED_ROLES`, `QUERY_LEDGER_EVENTS_TOOL`,
   `_build_ledger_query_tools`, `_assemble_tools` wiring, `_handle_query_ledger_events`,
   `_call_openai_query_ledger_events_followup_api`, `_finalize_response` wiring. Tests go
   GREEN.
3. **TDD scenario (§VI.a)**: `tasks.md` describes US2's date-ranged-summary and US3's
   RBAC-denial scenarios now — real test code written/run in Phase 3.

### Phase 3 — Acceptance (§VI.a — TDD proper, `billed`, run once)
The scenarios described in Phase 1/Phase 2 (US1 explicit/no-match/ambiguous-name, US2
date-ranged summary, US3 RBAC denial) prove the feature end-to-end from a real user's
perspective. Test code written AND run, together, only here, once, after Phase 1 AND
Phase 2 are both GREEN. The owed-balance cross-event-type reasoning scenario is verified
manually via `quickstart.md` step 6, not automated (see Project Structure note above).

### Phase 4 — Close out
Move spec to `specs/done/` once merged, per folder movement rules (part of the `haleluya`
flow, not run unprompted).

## Complexity Tracking

No Constitution Check violations requiring justification beyond the flagged new dependency
(`rapidfuzz`), which is addressed inline above and in research.md Decision 2.
