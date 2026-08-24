# Phase 0 Research: Ledger Event Querying via AI

**Feature**: 044-ledger-event-querying · **Date**: 2026-08-22

This document resolves the spec's one deliberately-deferred decision (the query surface —
filter fields, matching mechanism, tool schema) via direct discussion with the user
(2026-08-22), plus the implementation-detail choices that follow from those decisions.

## Background: what "search" actually needs to do here

Four representative real questions drove this (user-supplied, English glosses of what are
always real Hebrew conversations — see "Cross-script names" below):

1. Explicit: "search for my agreement with [client] — how much money did we agree on?"
2. Implicit: "how much does [client] still owe me?" (requires finding the agreement AND
   the payments against it, then subtracting)
3. Implicit: "how many hours do I need to bill [client] in August?" (requires finding every
   hours-logged event for that client in a date range, then summing)
4. Explicit: "when did [client] start the agreement?"

None of these give the model exact stored field values — a name may be misspelled/partial,
a date may be a month name, an amount may or may not include VAT. The obvious naive
approach (an exact-match filter, `SELECT ... WHERE field = value`) fails all four unless the
user happens to type the ledger's exact stored spelling — not something to rely on.

## Decision 1: Matching mechanism — code-side fuzzy matching, not embeddings

**Decision**: fuzzy matching lives in code (a fuzzy string-scoring library), never in an
embedding/semantic-search index. Two sub-mechanisms, split by field type:

- **Name fields** (`client_name`, `payer_name`): fuzzy string scoring (rapidfuzz) — tolerant
  of typos, partial names, word-order variance.
- **Free-text fields** (`description`, `component_label`, `trigger_condition`): the SAME
  fuzzy string scoring, applied more loosely — this catches typos/near-identical wording,
  explicitly NOT paraphrase/topic-level matching (a description reading "צו מניעה" will not
  match a differently-worded description of the same legal matter — confirmed acceptable to
  the user 2026-08-22, a known, deliberate limitation, not an oversight).
- **Dates, amounts**: plain deterministic `[min, max]` range filters — no fuzziness/tolerance
  logic lives in the tool at all. The model does its own "how wide should I search" reasoning
  (exactly as it already resolves relative dates in `capture_ledger_event`/reminders today) —
  e.g. "August" → `date_from=2026-08-01, date_to=2026-08-31`; "₪40,000, might include VAT" →
  widen `amount_min`/`amount_max` itself.
- **`source_type`, `event_subtype`**: exact/enum filters, optional (so a client-wide search
  naturally spans both fee-agreement and bank-deposit events — needed for question #2 above).

**Rationale**: all four representative questions are structured-field lookups (name + date/
amount/hours), not open-ended topic search. Embeddings solve "find something related in
meaning" but don't help name-typo tolerance (a misspelled name isn't reliably close to the
correct one in vector space) and don't help numeric/date tolerance at all (an embedding
can't reason "is 42,000 within 18% of 40,000" — that logic has to exist in code regardless
of matching mechanism, per Alternatives below). Fuzzy string scoring handles the actual
failure mode (typos, partial names) directly, deterministically, and is trivially fast at
"a few thousand events" scale (no index/ANN structure needed — score every candidate on
every query).

**Alternatives considered**:
- *Embedding/semantic search* (reusing `MemoryManager`'s ChromaDB + OpenAI-embeddings
  pattern) — rejected. Would add: a second index to keep in sync with every
  `add_ledger_event` write, a real OpenAI embedding call per query (cost/latency), and
  non-deterministic-feeling similarity scores (harder to unit-test with fixed thresholds)
  — for a paraphrase-matching capability none of the four representative questions actually
  need. Explicitly discussed and rejected by the user (2026-08-22) even after walking through
  the tradeoff in detail.
- *Hybrid* (fuzzy for structured fields + embedding fallback for free text) — rejected for
  the same reason; the user found the added complexity unwarranted given the actual query
  shapes in play.
- *Cross-script matching* (Hebrew ⟷ English/transliterated) — explicitly out of scope. Ledger
  `client_name` is ALWAYS Hebrew (user, 2026-08-22, emphatic) — the English-language examples
  above are only glosses of what are real Hebrew conversations. No transliteration layer
  needed anywhere in this feature.

## Decision 2: Library — `rapidfuzz`, a new dependency

**Decision**: `rapidfuzz` (MIT-licensed, ships prebuilt wheels, no heavy transitive deps),
specifically `rapidfuzz.fuzz.WRatio` for name scoring (handles partial matches and
word-order variance well) and `rapidfuzz.fuzz.partial_ratio` for free-text field scoring
(finds a close substring match within a longer field, appropriate for `description`/
`component_label`/`trigger_condition`).

**Rationale**: the stdlib alternative (`difflib.SequenceMatcher`) has no built-in
word-order-invariant or partial/substring scoring — reproducing that by hand (tokenizing,
trying token permutations) is exactly what `rapidfuzz` already implements, tested, and
fast. This is a new runtime dependency (flagged in the Constitution Check in `plan.md`),
justified because fuzzy string matching is genuinely core to this feature's stated
requirement ("search values may not be provided exactly as stored" — spec's Problem
Statement), not an incidental convenience.

**Alternatives considered**: `difflib.SequenceMatcher` (stdlib, zero new dependency) —
rejected; would require hand-rolling token-order-invariant matching logic that `rapidfuzz`
already provides, well-tested, for a feature whose whole point is robust fuzzy matching.

## Decision 3: Matching thresholds (concrete defaults)

- **Name match threshold** (`_NAME_MATCH_THRESHOLD = 70`, `WRatio` 0-100 scale): a stored
  `client_name`/`payer_name` value is a "plausible candidate" if its score against the
  query name is ≥ 70.
- **Free-text match threshold** (`_FREE_TEXT_MATCH_THRESHOLD = 60`): looser than the name
  threshold since `description`/`component_label`/`trigger_condition` values are longer and
  noisier — a `partial_ratio` ≥ 60 against the query text counts as a match.
- Both are named module-level constants (never inline magic numbers), documented as tunable
  based on real usage, same convention as `_normalize_amount`/`_normalize_hours`'s own
  regex/threshold constants in `ledger_event_manager.py`.

## Decision 4: Entity-level ambiguity vs. result multiplicity — NOT the same thing

**Decision** (correcting an earlier draft of this document that conflated the two,
2026-08-22): these are two entirely different things, handled differently:

- **Entity resolution** ("which *client* did you mean") — real ambiguity. If the query's
  `client_name` fuzzy-matches **two or more distinct stored name strings** (grouped by
  exact string value across `client_name` ∪ `payer_name` in the index) each scoring ≥ the
  name-match threshold, the tool cannot know which real person is meant — it returns a
  `candidates` list (each distinct matched name + how many events it has) instead of
  events, and the model asks the user to disambiguate. Mirrors the existing
  `resolve_client_name` (Morning MCP) "did you mean X or create new?" UX exactly, but this
  is an entirely separate, local mechanism — no cross-app dependency.
- **Result multiplicity** (how many *events* matched once the client/filters are settled)
  — never ambiguous. Per the spec's already-locked FR-005 (full result set, no
  pagination/truncation), a confidently-resolved query can and normally will return many
  events (all of a client's August hours-log entries; every fee-agreement AND bank-deposit
  event for the owed-balance question) — this is the expected, correct shape of the answer,
  not something requiring a follow-up question.

## Decision 5: Query surface — no server-side aggregation, no cross-event linking

**Decision**: the tool always returns the raw list of matching events (every field, per
event) — never a computed sum/count, and never an attempt to link a `בנק` (payment) event
to the `הסכם` (agreement) event it's presumably paying down. All arithmetic (summing hours,
subtracting payments from an agreed amount) is the model's job in its natural-language
reply, exactly as it already reasons about any other financial question in conversation.

**Rationale** (user, 2026-08-22): there is no reliable structural link today between a
payment event and the agreement it's against (no FK — the two source types are connected
only loosely, by shared `client_name`/proximity in time), so a generic "compute the
balance" aggregate isn't mechanizable without a data-model change that's explicitly out of
scope here. Given that, keeping the *other* case (a simple same-field sum, e.g. total
hours in August) server-side while leaving the harder case to the model would mean two
different answer-construction paths for what looks like the same kind of question from the
user's side — one small consistency win (server-computed sums are more reliable, matching
this codebase's general "never trust the AI's own math" philosophy for *captured* values)
was traded for a simpler, single code path. This is explicitly a user decision, not a
default — a future revision could add server-side aggregation for the mechanizable subset
of questions if inconsistent model arithmetic turns out to be a real problem in practice.

## Decision 6: Vague-query guard — enforced in the tool description AND a code-side fallback

**Decision**: the tool's own `description` instructs the model never to call it with every
filter empty/null — if the user's question gives nothing to search on, ask for the missing
detail first. As a belt-and-suspenders code-side backstop (models don't always follow
prompted instructions), `AIHandler`'s dispatch checks whether every filter argument the
model actually supplied is null; if so, it does NOT execute a whole-ledger dump — it
returns a distinct `function_call_output` telling the model no search criteria were given,
so the model's next-turn reply asks the user rather than silently working from an empty
result or (worse) the entire ledger.

**Rationale**: relying on prompt-following alone has a real, observed failure history in
this codebase (e.g. bugfix-018's `capture_ledger_event` safety net, several `LEDGER_EVENT_TOOL`
description hardening rounds after real billed-test misfires) — a code-side guard for the
one clearly-detectable "genuinely nothing to search on" case is cheap insurance.

## Decision 7: Date matching spans BOTH date-bearing fields

**Decision**: a `date_from`/`date_to` filter matches an event if **either** its
`event_datetime` (when the event was captured/happened) or its `txn_date` (the
hours-worked/transaction date, only sometimes populated) falls in range — not a single
fixed field the model must pick.

**Rationale**: the two fields answer different real questions (`txn_date` for "hours worked
in August," `event_datetime` for "when did the agreement start") and the model has no
reliable way to know, per query, which one the ledger actually populated for a given
record — checking both is strictly more forgiving (better recall) and matches this
feature's overall "fuzzy, not exact-match" spirit, at no real precision cost (a
false-positive date match is still gated by the OTHER filters — client name, amount, etc.
— in the same query).

## Decision 8: In-memory index — plain flat list, built at startup, updated on write

**Decision**: `LedgerEventManager` gains an in-memory `List[Dict]` (`self._index`) loaded
once at construction by scanning `{data_root}/events/*.json` (mirrors `add_ledger_event`'s
own read/write conventions), with corrupt/unparseable files skipped and logged (FR-007) —
never failing the whole load. `add_ledger_event` appends the newly-persisted record to
`self._index` immediately after a successful write (FR-003) — same method, same
transaction, no separate sync step to forget.

**Concurrency**: no lock (user decision, 2026-08-23 — no `threading.Lock`/synchronization
primitive anywhere in this feature without separate explicit approval first). Python's GIL
already makes a plain list's `append`/iteration individually atomic, which is what the
spec's own Edge Cases rely on ("doesn't need to guarantee the brand-new event is included if
the race is exact" — a query concurrent with a write may or may not see that exact write,
but never sees a torn/partially-constructed record, since a record is only ever added to the
index as one already-fully-built dict, after its file write already succeeded). No
additional locking is introduced on top of that.

**Rationale**: a flat list is the simplest structure that satisfies "a few thousand events"
— no index/lookup structure needed for performance (a full linear scan + fuzzy-score pass
over a few thousand short dicts is sub-100ms territory, no human-perceptible slowdown,
satisfying SC-003), and it's the structure every other manager in this codebase already
defaults to for small-scale in-memory state (e.g. `PendingApprovalManager`'s plain dict).

**Alternatives considered**: pre-grouping by client_name/date at load time — rejected as
premature optimization; a flat list scanned fresh per query is simpler, and "a few thousand"
rows is nowhere near the scale where that would matter.

## Decision 9: Tool dispatch pattern — read-only, immediate, same-turn follow-up

**Decision**: `query_ledger_events` is a local `type: "function"` tool, RBAC-gated
(godfather/admin only, new `LEDGER_QUERY_AUTHORIZED_ROLES` constant — see "RBAC" below),
dispatched **immediately** on a matching `function_call` — no `PendingLocalToolApproval`,
no approval gate (this is read-only, same reasoning as `list_reminders`/
`capture_ledger_event`). Needs the same same-turn follow-up round-trip
(`function_call_output` → a second `responses.create` call chained via
`previous_response_id`) as `list_reminders`/the ledger-capture follow-up, since a
reasoning-model turn that emits a `function_call` never also emits a text reply in that
same turn.

**RBAC naming**: a new `LEDGER_QUERY_AUTHORIZED_ROLES = (Role.GODFATHER, Role.ADMIN)`
constant, rather than reusing `MORNING_MCP_AUTHORIZED_ROLES`/`REMINDER_AUTHORIZED_ROLES`
(both already identical tuples) — matches this codebase's existing convention of one named
constant per feature even when the values coincide (e.g. `REMINDER_AUTHORIZED_ROLES` was
added as its own constant in Feature 054 rather than reusing `MORNING_MCP_AUTHORIZED_ROLES`).

**Correction to the spec's own stated rationale** (found during this research, 2026-08-22):
`spec.md`'s FR-004 says the RBAC gate "mirror[s] the existing RBAC gate on
`capture_ledger_event`" — this is factually incorrect against current code:
`_build_ledger_event_tool` explicitly has **no** RBAC/role restriction ("always attached in
the text path... unlike the Morning MCP tools"). The functional requirement itself (gate
`query_ledger_events` to godfather/admin) is unaffected and stays locked exactly as
written — only the spec's own stated analogy to `capture_ledger_event` is wrong; the real
precedent is the Morning MCP tools and the reminder tools, both of which ARE role-gated.

## Decision 10: Unbounded query complexity via multiple calls per turn — NOT a richer schema

**Decision** (added 2026-08-23, after walking through real query examples with the user —
"what was agreed with client A or B," "hours for client X across two separate date ranges,"
etc. — that the original 8-field, single-value-per-field schema can't express directly):
`query_ledger_events` keeps its exact schema from Decision 9/contracts (single `client_name`,
single date range, single amount range — AND-combined within one call). Arbitrarily complex
requests (an OR across two client names, an OR across two disjoint date ranges, any
combination the user's own question implies) are handled by the model calling the tool
**multiple times in the same turn** — once per disjunct — and combining/reasoning over the
union of all returned events itself when composing its reply. This is the SAME "model
reasons over raw events" principle already locked in Decision 5 (the owed-balance case),
just spanning several tool calls instead of one.

**This is a deliberate mirror of `capture_ledger_event`'s existing multi-call machinery,
with one crucial reversal.** `capture_ledger_event` (bugfix-018) treats more than one call
in a single turn as an unconditional PROTOCOL VIOLATION — real incident: a truncation bug
produced 17 near-duplicate WRITE calls in one turn, and since each successful call persists
a new file, an uncontrolled multi-call burst risks silently corrupting the ledger with
duplicates. `query_ledger_events` has no such risk — it writes nothing, and any number of
calls (redundant, overlapping, or genuinely disjoint) are perfectly safe to all execute:
worst case is wasted tokens, never data corruption. So `query_ledger_events` deliberately
does the OPPOSITE of bugfix-018 — it explicitly **allows and invites** multiple calls per
turn, and the tool's own `description` says so.

**Reused, not reinvented**: the dispatch layer uses `extract_all_function_calls` (already
implemented, generic over tool name, used today by `capture_ledger_event`) instead of the
single-call `extract_function_call`/`extract_function_call_id` pair `list_reminders` uses.
The follow-up round-trip batches one `function_call_output` per `call_id` into a single
`responses.create` call — the exact same list-comprehension shape
`_call_openai_ledger_followup_api` already uses for its multi-component-call case. Both
pieces of machinery are reused verbatim in kind, not copied-and-modified into something new.

**Per-call failure isolation** (the one place this deliberately does NOT mirror
`capture_ledger_event`): if one call's `arguments` fail to parse (the same
truncation-mid-generation failure mode bugfix-018 guards against), only THAT call's
`function_call_output` reports an error (`{"status": "error", "reason": "..."}` —
data-model.md shape D) — every other well-formed call in the same turn still executes and
returns its own real result. There is no "reject the whole turn" behavior here, because
unlike `capture_ledger_event`, one call's failure has zero bearing on any other call's
correctness (each is an independent, side-effect-free read).

**The "candidates → user says 'both'/'all'" flow, resolved by this same mechanism**: when a
prior turn returned the ambiguous-candidates shape (Decision 4) and the user's next message
confirms they want more than one (or literally "both"/"all"), the model simply issues one
`query_ledger_events` call per confirmed distinct name — each now resolving unambiguously
(shape A, since it's the exact stored string, no longer subject to fuzzy grouping) — and
merges the results itself. No new tool mechanism needed beyond what's already described
above.

**"Too many results" — refined (user, 2026-08-23): the boundary is on what gets LISTED TO
THE USER, not on what the tool returns or retrieves.** The tool/`query_events` itself is
completely unbounded (FR-005, unchanged — hundreds of events internally is fine, matches
"how much income in August" style broad queries). The boundary is specifically: **DeniDin's
chat reply must never enumerate more than 20 individual events verbatim**, across everything
gathered this turn (one call or several, per Decision 10's multi-call mechanism) — past that,
the model must summarize (counts, groupings, totals) or ask the user to narrow, never just
dump a long list into the chat. This is a concrete, testable threshold, not open-ended
"judgment" the way the original draft of this decision put it.

**Where this rule lives**: `config/runtime_constitution.md`'s new "Ledger Event Querying"
section (see below — this is reply-shaping guidance, not tool-schema/code, since there is no
clean code-side way to inspect/enforce the SHAPE of a natural-language reply the way the
vague-query guard's code-side backstop enforces its own rule). Reinforced by a `billed`
regression test (tasks.md) asserting a broad, >20-matching-event query's reply does not
enumerate every event — this is prompt-level guidance with a real test catching drift, not a
code-enforced hard cap, an honest distinction from Decision 6's vague-query guard (which DOES
have a code backstop) worth stating plainly rather than implying false parity between the two.

**New required artifact (CLAUDE.md's mandatory "every tool-bearing feature needs explicit
constitution boundaries" rule, missed in the first pass of this plan)**: `query_ledger_events`
needs its own `runtime_constitution.md` section — scope (when it applies), explicit negative
scoping (when it does NOT — client_role turns, media messages, anything the tool's own RBAC
gate already excludes structurally, but ALSO conversational-confusion cases where the model
might otherwise reach for it), the 20-item display cap above, and cross-references FROM every
other existing tool-bearing section (Reminder Management, Ledger Event Recognition, Morning
MCP) stating ledger querying is out of scope for them too — mirroring the pattern
Feature 054's own constitution work established. Folded into Phase 2 (tasks.md).

## Decision 11: "Income" aggregation means money actually received

**Decision** (user, 2026-08-23): a broad aggregation question with no client named (e.g.
"how much income did I have in August") means money that was actually **received** —
`source_type="בנק"` (bank-deposit) events only, never `"הסכם"` (agreed-but-possibly-unpaid)
amounts. No new tool capability needed: the model sets `source_type="בנק"` plus a date
range, leaves `client_name` null, and sums the returned `amount` fields itself (Decision 5 —
no server-side aggregation).

**Vague-query guard interaction**: a date-range-only query (no client name at all) still
counts as having "one identifying filter" — the guard (Decision 6) only blocks the
all-null case, never a single populated filter on its own, however broad the resulting
match set turns out to be. Worth its own explicit test (tasks.md) confirming a
date-only, client-less query is never treated as "too vague."

## Decision 12: `source_type`/`event_subtype` are plain text filters, never enums — and
## `free_text` implicitly covers Feature 025's new fields

**Decision** (added 2026-08-23, after pulling `master` and reading Feature 025's now-fully-
designed spec — see below): `source_type` and `event_subtype` in `QUERY_LEDGER_EVENTS_TOOL`
have **no `enum` constraint** — plain `["string", "null"]`, exact-match against whatever value
the persisted event actually carries. This was a design mistake in the original draft, not a
deliberate choice: it copied `LEDGER_EVENT_TOOL` (`capture_ledger_event`)'s own strict-enum
discipline, which makes sense there (the model is producing a canonical WRITE classification,
and OpenAI's structured-output enum is the right guardrail for that) but makes no sense for a
READ/filter parameter, where an unrecognized value simply matches nothing — no data-integrity
risk, no reason to structurally block a real value the model hasn't been told about yet.

**Trigger**: Feature 025 (Morning-sourced ledger events — `specs/in-progress/
025-morning-sourced-ledger-events/`, fully designed through 6 clarification rounds, code on
its own branch not yet merged) extends the persisted `LedgerEvent` schema with
`source_type="חשבונית"` and a proposed `event_subtype="הפקה"`. Had `source_type`/`event_subtype`
stayed enum-constrained, the model would have been structurally unable to filter by these new
values the moment 025 merges — a silent capability gap, not a crash (name/date/amount/free_text
filters all read fields generically and would still find these events, just not by type). The
enum removal fixes this permanently, for THIS extension and any future one — no more tracking
"which source_type values are confirmed yet" in this tool's schema at all.

**`event_subtype="הפקה"` specifically was NOT hardcoded anywhere** (not even as a comment/
example) — Feature 025's own spec lists it under "still genuinely open," unconfirmed against
real accounting terminology. Since there's no enum, this is a non-issue: the model can pass it,
or any other subtype value, the moment real data justifies it, with zero code change needed here
either way. **Update, 2026-08-23 (user): Feature 025's design has since moved further —
`event_subtype` will replace `accounting_document_type` entirely** (the "type of accounting
document" concept folds into `event_subtype` itself, e.g. holding a value like `"חשבונית מס
קבלה"`, rather than living in its own separate field). This needed zero `query_events` code
change — `event_subtype` was already a plain exact-match filter with no enum (this same
decision), so it already accepts any value regardless of which specific ones Feature 025 ends up
using. What DID need a small follow-up fix: `accounting_document_type` was removed from
`_FREE_TEXT_FIELDS` below, since that field is going away.

**`free_text` now also searches Feature 025's new `accounting_document_*` text fields**
(`accounting_document_display_number`, `accounting_document_status_label`,
`accounting_document_payment_method` — NOT `accounting_document_type`, per the above) — user
directive, 2026-08-23: *"not as explicits, but as implicit fields like any other. a query with
some text should also search over these fields like any other."* No new tool parameter —
`_FREE_TEXT_FIELDS` (`ledger_event_manager.py`) is simply extended with these field names, same
mechanism already covering `description`/`component_label`/`trigger_condition`. Deliberately
excludes `accounting_document_status_code` (a raw int, not a natural free-text target — its label
counterpart, `accounting_document_status_label`, is included instead) and
`accounting_document_creation_date` (a date, already covered by `date_from`/`date_to` against
`event_datetime`/`txn_date` — free-text date matching would be redundant and less precise).
`_event_matches_free_text` now casts every field value to `str()` before scoring, defensively —
these are fields this class doesn't itself populate, so a non-string value must never raise.

**No other Feature 044 code changes needed.** Every other filter (`client_name`/`payer_name`
fuzzy matching, `date_from`/`date_to`, `amount_min`/`amount_max`) already reads fields
generically via `.get()` with no assumption about which `source_type` values exist — confirmed
by reading Feature 025's `data-model.md` field-by-field against `query_events`'s actual
implementation, not assumed. `client_name` itself is NOT among Feature 025's forced-null fields
for `חשבונית` (only `payer_name`/`component_label`/`trigger_condition`/`agreement_id`/
`component_id`/`percent*`/`hours*` are), so a Morning-sourced document's client is findable by
name exactly like any other event, automatically, today.
