# Phase 1 Data Model: Ledger Event Querying via AI

**Feature**: 044-ledger-event-querying · **Date**: 2026-08-22 · **Query engine redesigned**:
2026-08-24 (see `research.md`'s "2026-08-24 Redesign" section and `tasks.md`'s "Addendum,
2026-08-24" for the full decision trail — the original 8-separate-structured-filter query
request shape below was replaced wholesale; the persisted-event schema and in-memory index
sections were NOT affected by the redesign).

No change to the persisted ledger event schema (Feature 033) — this feature is
additive read access only (FR-008). This document covers the new in-memory index and the
query request/response shapes the new tool introduces.

## Existing entity (unchanged): persisted ledger event

One JSON file per event under `{data_root}/events/{event_id}.json` (see
`ledger_event_manager.py`'s `add_ledger_event` for the authoritative field list). Fields
this feature actually searches/returns — see `_HINT_GROUPS` in
`src/managers/ledger_event_manager.py` for the authoritative, closed field→hint-group
mapping (the table below is a human-readable summary of it, not a second source of truth):

| Field | Type | Hint group | Scored how |
|---|---|---|---|
| `event_id` | str | — | returned, not searched |
| `event_datetime` / `txn_date` | str \| null | `date` | fuzzy text (`WRatio`) — `event_datetime` is the ONLY creation-date field on any event, including `source_type="חשבונית"` records (2026-08-25: the old `accounting_document_creation_date` field, always a byte-for-byte duplicate of `event_datetime` for those records, was removed entirely) |
| `source_type` / `event_subtype` | str \| null | `event_type` | fuzzy text (`WRatio`) — still NOT an enum (Decision 12); any value the data actually carries is matchable |
| `vat_status` | str \| null | `vat` | fuzzy text (`WRatio`) |
| `client_name` / `payer_name` / `split_partner` | str \| null | `identity` | fuzzy text (`WRatio`), but only wins as a criterion's best field if its raw score clears `_NAME_MATCH_THRESHOLD` (70) — see `_score_criterion`'s docstring |
| *(all string fields, general rule)* | — | — | a field whose own stored value is short (< `_SHORT_VALUE_LENGTH_THRESHOLD`, 8 chars — covers `event_subtype`, `source_type`, `vat_status`'s typical filler values) can only win if its score clears the near-exact `_SHORT_VALUE_MATCH_THRESHOLD` (85), regardless of scorer — see `research.md`'s redesign section, bug #6 |
| `amount` / `hourly_rate` | number \| null | `amount` | numeric equality when the query text parses as a number, else skipped entirely (never fuzzy-compared) |
| `percent` / `percent_base` / `split_percent` | number \| null | `percentage` | numeric equality, same rule as `amount` |
| `description` / `trigger_condition` / `reference_hint` | str \| null | `free_text` | fuzzy text, `partial_ratio` (substring-lenient, since these are the longest/prose-like fields) |
| `accounting_document_display_number` (Feature 025, non-null only when `source_type="חשבונית"`) | str \| null | `document` | numeric equality (it's a Morning document number, i.e. a number, not free text — 2026-08-24 fix) |
| `accounting_document_payment_method` / `accounting_document_status` / `accounting_document_status_label` | str \| null | `document` | fuzzy text (`WRatio`) |
| `bank_number` / `bank_branch` / `bank_account` | str \| null | `banking` | numeric equality, same rule as `amount` |
| `component_label` | str \| null | — | NOT searchable (2026-08-25: dropped from every hint group — it exists only to derive `component_id` at capture time, never a natural search target); returned, not searched |
| `due_date` — **removed** (2026-08-25, user directive): was a dead, always-`None` reserved-for-later field with no populating code path; dropped from the persisted schema, `_HINT_GROUPS`, and every doc/test reference | — | — | N/A |
| `hours` | float \| null | — | returned, not searched (no representative question needs to search by hours directly — the model narrows by identity/date instead, then reads `hours` off each returned event) |
| `accounting_document_type` — **removed** (2026-08-23 update, user): Feature 025 now folds "type of accounting document" into `event_subtype` itself rather than a separate field | — | — | N/A — `event_subtype` already covers this (`event_type` group) |
| `accounting_document_status_code` (Feature 025) | int \| null | — | NOT searchable (raw int, not a natural text/number target — use `accounting_document_status_label` instead); returned, not searched |
| `agreement_id` / `component_id` | str \| null | — | returned, not searched (generated slugs, not natural-language query input) |
| `reference` | str \| null | — | returned, not searched |
| everything else (`session_id`, `captured_at`, `schema_version`, ...) | — | — | returned as-is, not searched |

**NOT a field**: `agreement_label` — a `capture_ledger_event` *input* only, used once to
help build `agreement_id` at capture time, never itself persisted (see `research.md`
Decision correcting an earlier draft of this document). Do not add it as a query criterion —
there is nothing on a persisted record to match it against.

## New: in-memory ledger event index

Owned by `LedgerEventManager` (the existing manager, extended — not a new class):

```python
self._index: List[Dict] = []          # flat list of persisted-event dicts, load order
```
No lock (user decision, 2026-08-23 — see research.md Decision 8's "Concurrency" note).

- **Populated**: once at `LedgerEventManager.__init__`, by scanning
  `{data_root}/events/*.json` (glob, same directory `add_ledger_event` already writes to).
  A file that fails to parse (`json.JSONDecodeError` or any other read error) is skipped and
  logged as an ERROR (FR-007) — never raises, never aborts the rest of the load.
- **Kept current**: `add_ledger_event` appends the newly-written record to `self._index`
  immediately after its atomic file write succeeds (FR-003) — same method, no separate sync
  step.
- **Never persisted itself** — rebuilt from disk on every process start, same as every other
  in-memory cache in this codebase (`GroupMembershipResolver`'s cache, `PendingApprovalManager`).

## New: Query request (the `query_ledger_events` tool's arguments) — 2026-08-24 redesign

**REPLACED the original 8-separate-structured-filter shape entirely** (that shape — one
`client_name`, one `date_from`/`date_to` range, one `amount_min`/`amount_max` range, one
`source_type`, one `event_subtype`, one `free_text` per call — is documented only for
historical context in `research.md`'s pre-redesign decisions; it is no longer what the tool
accepts). A real billed test (`test_payer_name_search`) showed the AND-combined structured
filters let the model accidentally exclude a genuine match by over-constraining one call, and
the design had no way to express OR/NOT/threshold reasoning at all.

The current shape is a single field:

| Field | Type | Matching |
|---|---|---|
| `criteria` | `List[{"text": str, "hint": str \| null}]` | see below |

Each `criteria` entry is scored independently against every event via `_score_criterion`
(see the field table above for exactly how each field is compared) across **every**
searchable field — never restricted to the entry's own `hint`. `hint` (one of `identity`,
`date`, `category`, `amount`, `percentage`, `description`, `document`, `banking`, `split`,
or `null`) is a **soft** signal: if the winning field for a criterion belongs to the stated
hint's group, that criterion's score gets `_HINT_MATCH_BONUS` added — a wrong hint never
excludes an otherwise-real match, it just withholds the bonus.

Within one call, every criterion is **ANDed**: an event only counts as a match if it clears
`_CRITERION_MATCH_FLOOR` on **every** criterion individually (not just on average — see
`research.md`'s redesign section for the empirical finding that made "every criterion
individually" necessary). If `criteria` is empty/null (or every entry's `text` is empty),
the code-side vague-query guard (Decision 6, unchanged in spirit) intercepts before any real
scoring happens.

**OR/NOT/threshold reasoning carries NO dedicated schema support** — deliberately. OR is
answered by issuing one separate call per alternative (multi-call dispatch, unchanged
mechanism, see below). NOT/exclusion and numeric-threshold questions are answered by a
single **broad** call (a criterion or two that retrieves every plausibly-relevant event),
with the actual exclusion/threshold reasoning done by the model itself over the raw returned
events — the same principle `research.md` Decision 5 already established for aggregation,
now extended to cover ranges/exclusions too.

## New: Query result (the tool's `function_call_output`)

Three distinct shapes, mutually exclusive:

**A. Resolved (no entity-level ambiguity)** — the normal case:
```json
{
  "matches": [ { <full event dict, every field>, "confidence": <float> }, ... ],
  "count": <int>
}
```
`matches` is the complete matching set — never truncated/paginated (FR-005, locked at
spec time) — sorted by `confidence` descending. `confidence` (new, 2026-08-24 redesign) is
the mean of the event's per-criterion scores (each of which already cleared
`_CRITERION_MATCH_FLOOR` individually); a higher confidence means a stronger match across
the given criteria — the model uses judgment about how much to trust a borderline one.
`count` is just `len(matches)`, included so the model doesn't need to count manually for a
"how many events" style question.

**B. Ambiguous client identity** — when an `identity`-hinted criterion fuzzy-matched ≥2
distinct stored name strings each above `_NAME_MATCH_THRESHOLD` (Decision 4, mechanism
unchanged by the redesign — just no longer tied to a dedicated `client_name` parameter):
```json
{
  "ambiguous_field": "identity",
  "candidates": [
    {"value": "<a distinct matched client_name/payer_name string>", "event_count": <int>},
    ...
  ]
}
```
No `matches`/`count` key present in this shape — the model must relay `candidates` to the
user and ask which one, then re-call with the confirmed name (which — now matching only one
distinct stored string — resolves to shape A).

**C. Vague-query guard tripped** (Decision 6, `criteria` empty/null):
```json
{"error": "no_search_criteria", "message": "..."}
```
Distinct from an empty result (shape A with `matches: []`, `count: 0`, which means "search
ran, found nothing") — this shape means "no search was even attempted, ask the user what
they mean."

**D. Individual call failed to parse** (research.md Decision 10 — per-call failure
isolation, NOT a whole-turn rejection):
```json
{"status": "error", "reason": "..."}
```
Only ever produced by the `AIHandler` dispatch layer itself (never by `query_events`) when
one specific `function_call`'s `arguments` couldn't be parsed as JSON (truncated
mid-generation, same failure mode as `capture_ledger_event`'s bugfix-018) — that call's own
`function_call_output` gets this shape while every OTHER call from the same turn still
executes normally and gets shape A/B/C. Never poisons the whole turn, unlike
`capture_ledger_event`'s protocol-violation rejection (see research.md Decision 10 for why
that asymmetry is correct here).

## Multi-call dispatch (research.md Decision 10)

A single turn may contain **more than one** `query_ledger_events` function_call — this is
expected and safe (read-only, no corruption risk), unlike `capture_ledger_event` where more
than one call is a hard protocol violation (bugfix-018). `AIHandler` uses
`extract_all_function_calls` (already implemented, generic over tool name) to find every
call, executes `LedgerEventManager.query_events` once per call (independently — one call's
arguments/result never affect another's), and reports ALL of them back in a SINGLE follow-up
`responses.create` call as a list of `function_call_output` items (one per `call_id`) — the
same batching shape `_call_openai_ledger_followup_api` already uses for
`capture_ledger_event`'s multi-component case. OpenAI rejects a follow-up that leaves any
pending call from the prior turn unresolved, so every call_id — successful, empty-result, or
parse-failed (shape D) — MUST get an entry in that same list, none silently omitted.

This is the mechanism by which arbitrarily complex requests are answered without any schema
richer than "a list of ANDed criteria per call" — "client A or client B," "hours in
[month1] or [month2]," "candidates confirmed as both/all" are all just N independent calls
in one turn (one `criteria` list each), combined by the model in its own reply. OR-type
questions are the primary reason this mechanism exists post-redesign (see Query request
section above) — it carries no dedicated OR schema of its own precisely because this
already covers it.

## Validation rules (2026-08-24 redesign)

The original range-validation rules here (inverted `date_from`/`date_to`, inverted
`amount_min`/`amount_max`, malformed dates treated as absent bounds) no longer apply —
`query_events` no longer accepts ranges at all; every criterion is a single `text` value
scored via fuzzy text or numeric equality (see the field table above), so there is no bound
to invert or fail to parse. What replaces range-style validation:

- A criterion's `text` is checked against `_try_parse_number` to decide numeric-vs-text
  scoring (see `_score_criterion`) — this never raises; a value that doesn't parse cleanly
  as a number simply falls through to fuzzy text scoring instead.
- `hint`, if given, must be one of the closed `_HINT_GROUPS` keys or it's treated as if
  absent (`None`) — an unrecognized hint string never raises and never acts as a hard
  filter either way, consistent with hints always being soft signals.
- A "range" or "threshold" question (e.g. "above 100 shekel", "before August") has no
  dedicated validation because it's not expressed in `criteria` at all — see the Query
  request section's NOT/exclusion/numeric-threshold guidance above.
