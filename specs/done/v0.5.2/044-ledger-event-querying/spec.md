# Feature Specification: Ledger Event Querying via AI

**Feature Branch**: `feature/044-ledger-event-querying`
**Created**: 2026-08-06
**Status**: Implemented and accepted — `query_ledger_events` (single fuzzy `criteria`/`hint`
search, no hard filters) is wired into `AIHandler` for godfather/admin roles; Phase 1/2 unit +
integration suites and a 29-scenario `billed` acceptance pass (T008-T011/T013-T015/T017-T029, all
GREEN against real OpenAI) cover all three user stories, including OR/NOT/threshold reasoning,
owed-vs-received netting, and the ledger-as-cache-over-Morning fallback rule. The
identity-ambiguity code-level gate originally in `query_events` was removed by explicit user
decision in favor of pure model judgment (see `tasks.md`'s 2026-08-26 addendum). T016 (manual
`quickstart.md` WhatsApp walkthrough) was explicitly skipped at close — the automated `billed`
coverage was judged sufficient on its own; see `tasks.md` for that decision recorded in place.
Shipped via [PR #256](https://github.com/yylevy171/DeniDin/pull/256).
**Input**: User description: "ledger querying from AI - allowing the AI to query past ledger
events in the system without needing to send them all as context. perhaps using a function
call like the one we use to write, this would be to query, and perhaps we need to keep them
all in memory for easy querying as there are not expected to be more than a few thousands of
events overall"

---

**IMPORTANT**: This spec complies with:
- **CONSTITUTION.md** (§I-III, §V, §XVII): No env vars, UTC timestamps internally, feature
  branch workflow, integration tests as E2E, no monkey-patching.
- **METHODOLOGY.md** (§I, II, VIII, IX, X): Spec-first development, mandatory user stories,
  Terminology Glossary, Technology Choices, Requirement IDs.

**Required Files**: `user-stories.md` (present, DRAFT) ✅ · `spec.md` (this file, DRAFT) ·
`plan.md` (NOT STARTED) · `research.md` (NOT STARTED) · `data-model.md` (NOT STARTED) ·
`contracts/` (NOT STARTED) · `quickstart.md` (NOT STARTED) · `tasks.md` (NOT STARTED).

---

## Origin

This feature was proposed after a real investigation (2026-08-06) into why two ledger events
appeared for the same fee agreement (`A05082620170.json` / `A05082620180.json` — a same-session
VAT correction that produced a second event instead of superseding the first). Answering that
question required a human to `ssh`/mount the prod data volume and read raw JSON files by hand,
because DeniDin itself has no way to look back at its own ledger history in conversation — it
can only write new events (Feature 033), never read past ones back. Root-causing/fixing that
specific duplicate-event bug is out of scope here (it belongs to Feature 040, agreement
cancellation/modification); this feature is the general capability that would have let a
godfather just *ask DeniDin* instead.

## User Stories Reference

Complete Given-When-Then acceptance criteria live in **`user-stories.md`**. Summary:

| # | Title | Priority |
|---|---|---|
| US1 | Answer a question about a specific client/agreement from the ledger | P1 |
| US2 | Answer a date-ranged or multi-event summary question | P2 |
| US3 | Ledger querying is denied to unauthorized roles | P2 |

## Terminology Glossary

- **Ledger event**: An existing per-event JSON record under `{data_root}/events/*.json`
  (Feature 033/`ledger_event_manager.py`), one immutable file per fee-agreement/deposit event
  recognized by the runtime constitution's "Ledger Event Recognition" rules.
- **Ledger event index**: The in-memory representation of ledger events this feature
  introduces, so a query does not require re-reading every file from disk on every call. Exact
  structure (whether a flat list, indexed by client/date, etc.) is a `plan.md` decision, not
  fixed here.
- **Query tool**: The new AI-callable local tool this feature adds (working name only —
  final name/schema is a `plan.md`/`contracts/` decision), analogous in kind to the existing
  `capture_ledger_event` write tool, but for reading instead of writing.

## Problem Statement

1. **DeniDin's ledger is write-only from the AI's perspective.** `capture_ledger_event`
   (Feature 033) persists events, but nothing in `AIHandler`'s system prompt, tools, or memory
   recall path ever surfaces previously captured events back to the model. Any question about
   past agreements/events currently requires a human to read the raw files directly.
2. **The obvious naive fix — pasting all events into context — does not scale.** The ledger is
   expected to reach "a few thousand" events; that is far too much to inject into every
   conversation turn, and would defeat the constitution/prompt-caching prefix design
   (`ai_handler.py`'s instructions-ordering rationale — see CLAUDE.md's `ai_handler.py`
   description) by making per-call content large and non-cacheable.
3. **A few thousand events is still small enough to hold entirely in memory** per running
   process, which is what makes an in-process, queryable index a reasonable answer instead of
   introducing a real database — an explicit constraint from the feature's origin request, not
   an assumption made here.

## Decisions Locked at Specification Time

These were raised as open questions during `speckit.specify` and resolved directly with the
user (2026-08-06), so they are **not** re-opened at `speckit.clarify`:

- **RBAC scope**: The query tool is gated to **godfather/admin roles only** — the same roles
  already gated onto `capture_ledger_event` and the Morning MCP tools (US3). A client-role user
  asking a ledger question must not trigger the tool or receive ledger data.
- **Result sizing**: The tool returns **the full matching result set**, not a capped/truncated
  page — "a few thousand events" is explicitly small enough to not require pagination. Where a
  query's natural answer is a computed aggregate (a count, a sum, a "most recent N") rather
  than a raw list, the tool **may also perform server-side aggregation** rather than forcing
  the model to aggregate itself from a raw dump; which queries get raw-list vs. aggregate
  treatment is a `plan.md` design decision, not fixed here.
- **Query surface (filters/fields) is explicitly deferred**: this spec intentionally does NOT
  enumerate the filter fields, query grammar, or exact tool schema — "the what before the
  how." `plan.md`/`contracts/` are where the concrete filter set (e.g. client, agreement,
  date range, event type, free text) and the query mechanism get designed, once this spec's
  scope is approved.

## User Scenarios & Testing

See `user-stories.md` for full Given-When-Then detail (referenced above).

### Edge Cases

- The in-memory ledger index has not finished loading yet (e.g. a query arrives in the small
  window right after process startup) — must fail gracefully, not crash the turn.
- A ledger event is captured by one conversation while a query from a different, concurrent
  conversation is in flight — must not return a torn/partial read.
- Malformed/corrupted event JSON on disk — index load must skip and log the corrupt file
  rather than fail the entire index or app startup.
- A client/agreement has multiple events on file for what is conceptually "the same"
  agreement (e.g. an unresolved correction, per the Feature 040 duplicate-event scenario) —
  the query tool must return all matching events rather than silently picking or merging one,
  leaving disambiguation to the model/response, not to the query layer.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST provide an AI-callable tool that retrieves previously captured
  ledger events matching caller-supplied criteria, without requiring the full ledger history
  to be included in the conversation's context/session tokens.
- **FR-002**: The system MUST maintain an in-memory index of all ledger events for the running
  environment, loaded fully from `{data_root}/events/*.json` at process startup, so queries do
  not require re-reading every event file from disk on every call.
- **FR-003**: The system MUST update the in-memory index immediately whenever a new ledger
  event is captured in the same running process, so query results reflect same-session writes
  without requiring a restart.
- **FR-004**: The query tool MUST be attached only for godfather/admin roles, mirroring the
  existing RBAC gate on `capture_ledger_event` and the Morning MCP tools; other roles must
  never have the tool attached or receive ledger data through it.
- **FR-005**: The query tool MUST return the complete set of events matching the given
  criteria (no silent truncation/pagination), and MAY additionally return server-computed
  aggregates (counts, sums, most-recent-N, etc.) when that better answers the query than a raw
  event list — the specific queries eligible for aggregate treatment are a design decision for
  `plan.md`.
- **FR-006**: When a query matches multiple events for what appears to be the same underlying
  agreement/matter (e.g. an unresolved correction), the tool MUST return all matching events
  rather than silently selecting or merging one.
- **FR-007**: A corrupted or unreadable individual event file MUST NOT prevent the index from
  loading the remaining valid events, and MUST be logged (per CONSTITUTION.md logging rules —
  technical detail to logs, not to the user).
- **FR-008**: This feature MUST NOT alter how ledger events are captured, persisted, or
  formatted (Feature 033's write path/schema is unchanged) — it is additive read access only.

### Key Entities

- **Ledger event** (existing, Feature 033): one immutable JSON record per recognized ledger
  event; unchanged by this feature.
- **Ledger event index** (new): the in-memory, queryable representation of all ledger events
  for the running environment; internal structure is a `plan.md` decision.
- **Query request / result** (new): the AI-callable tool's input (caller-supplied criteria) and
  output (matching events and/or aggregates); exact shape is a `plan.md`/`contracts/`
  decision.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A godfather/admin can get a correct answer to a question about a previously
  captured ledger event/agreement entirely through conversation, with no human needing to
  inspect raw event files.
- **SC-002**: Answering such a question does not require injecting the full ledger history
  into the conversation's context on every turn — only matching results for that specific
  query are used.
- **SC-003**: The feature performs correctly at the stated ledger scale (on the order of a few
  thousand events) without a human-perceptible slowdown in DeniDin's reply time.
- **SC-004**: A non-godfather/admin user asking a ledger question never receives ledger data
  through this feature, in any tested scenario.
