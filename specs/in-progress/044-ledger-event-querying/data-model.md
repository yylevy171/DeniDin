# Phase 1 Data Model: Ledger Event Querying via AI

**Feature**: 044-ledger-event-querying · **Date**: 2026-08-22

No change to the persisted ledger event schema (Feature 033) — this feature is
additive read access only (FR-008). This document covers the new in-memory index and the
query request/response shapes the new tool introduces.

## Existing entity (unchanged): persisted ledger event

One JSON file per event under `{data_root}/events/{event_id}.json` (see
`ledger_event_manager.py`'s `add_ledger_event` for the authoritative field list). Fields
this feature actually searches/returns:

| Field | Type | Searchable how |
|---|---|---|
| `event_id` | str | returned, not searched |
| `event_datetime` | str, `DD/MM/YYYY HH:MM` | date-range filter (see Decision 7) |
| `source_type` | str (`"הסכם"`/`"בנק"`/`"חשבונית"`/...) | exact-text filter, NOT an enum (Decision 12) — any value the data actually carries is matchable, including source types this spec never anticipated |
| `event_subtype` | str (`"יצירה"`/`"הפקדה"`/...) | exact-text filter, NOT an enum (Decision 12) |
| `client_name` | str \| null | fuzzy name filter |
| `payer_name` | str \| null | fuzzy name filter (same query param as client_name — matches either) |
| `description` | str \| null | fuzzy free-text filter |
| `component_label` | str \| null | fuzzy free-text filter |
| `trigger_condition` | str \| null | fuzzy free-text filter |
| `accounting_document_display_number` / `_status_label` / `_payment_method` (Feature 025, only non-null when `source_type="חשבונית"`) | str \| null | fuzzy free-text filter (Decision 12) — implicit, no dedicated query parameter |
| `accounting_document_type` — **removed** (2026-08-23 update, user): Feature 025 now folds "type of accounting document" into `event_subtype` itself rather than a separate field | — | N/A — `event_subtype` is already exact-match filterable (Decision 12), no free-text coverage needed |
| `accounting_document_status_code` (Feature 025) | int \| null | NOT free-text searchable (raw int, not a natural text target — use `_status_label` instead); returned, not searched |
| `amount` | int \| null | amount-range filter |
| `hours` | float \| null | returned, not directly filtered (a query narrows by client/date, then the model reads `hours` off each returned event itself — no separate hours-range filter, since none of the four representative questions need one) |
| `txn_date` | str, `DD/MM/YYYY` \| null | date-range filter (see Decision 7) |
| `agreement_id` / `component_id` | str \| null | returned, not searched (generated slugs, not natural-language query input) |
| `reference` | str \| null | returned, not searched |
| everything else (`bank_number`, `session_id`, `captured_at`, `schema_version`, `accounting_document_creation_date`, ...) | — | returned as-is, not searched (`accounting_document_creation_date` is covered indirectly — it's one of `event_datetime`/`txn_date`'s underlying sources at capture time, not searched as its own field here) |

**NOT a field**: `agreement_label` — a `capture_ledger_event` *input* only, used once to
help build `agreement_id` at capture time, never itself persisted (see `research.md`
Decision correcting an earlier draft of this document). Do not add it as a query filter —
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

## New: Query request (the `query_ledger_events` tool's arguments)

| Field | Type | Matching |
|---|---|---|
| `client_name` | str \| null | fuzzy (rapidfuzz `WRatio` ≥ `_NAME_MATCH_THRESHOLD`) against each event's `client_name` AND `payer_name` — either counts as a match |
| `date_from` | str (`YYYY-MM-DD`) \| null | inclusive lower bound, checked against `event_datetime` OR `txn_date` (Decision 7) |
| `date_to` | str (`YYYY-MM-DD`) \| null | inclusive upper bound, same fields |
| `amount_min` | number \| null | inclusive lower bound against `amount` |
| `amount_max` | number \| null | inclusive upper bound against `amount` |
| `source_type` | str \| null | exact match, NOT enum-constrained in the tool schema (Decision 12) — any value the ledger actually holds is a valid filter |
| `event_subtype` | str \| null | exact match, NOT enum-constrained (Decision 12) |
| `free_text` | str \| null | fuzzy (rapidfuzz `partial_ratio` ≥ `_FREE_TEXT_MATCH_THRESHOLD`) against every field in `_FREE_TEXT_FIELDS` — `description`, `component_label`, `trigger_condition`, plus (Decision 12) `accounting_document_display_number`/`_status_label`/`_payment_method` (NOT `_type` — folded into `event_subtype` instead, 2026-08-23) — any one counts as a match |

All fields optional/nullable; every filter given is AND-combined (an event must satisfy
every non-null filter to match). If every field is null, the code-side vague-query guard
(Decision 6) intercepts before any real filtering happens.

## New: Query result (the tool's `function_call_output`)

Two distinct shapes, mutually exclusive:

**A. Resolved (no entity-level ambiguity)** — the normal case:
```json
{
  "matches": [ { <full event dict, every field> }, ... ],
  "count": <int>
}
```
`matches` is the complete matching set — never truncated/paginated (FR-005, locked at
spec time). `count` is just `len(matches)`, included so the model doesn't need to count
manually for a "how many events" style question.

**B. Ambiguous client identity** — when `client_name` was given and fuzzy-matched ≥2
distinct stored name strings each above threshold (Decision 4):
```json
{
  "ambiguous_field": "client_name",
  "candidates": [
    {"value": "<a distinct matched client_name/payer_name string>", "event_count": <int>},
    ...
  ]
}
```
No `matches`/`count` key present in this shape — the model must relay `candidates` to the
user and ask which one, then re-call with the confirmed name (which — now matching only one
distinct stored string — resolves to shape A).

**C. Vague-query guard tripped** (Decision 6, every filter field null):
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
richer than "one client name, one date range, one amount range per call" — "client A or
client B," "hours in [month1] or [month2]," "candidates confirmed as both/all" are all just
N independent calls in one turn, combined by the model in its own reply.

## Validation rules

- `date_from`/`date_to`, if both given, need not be validated `date_from <= date_to` by the
  tool itself — an inverted range simply matches nothing (empty `matches`), which is an
  acceptable, self-correcting outcome (the model sees zero results and can reconsider), not
  a case requiring a distinct error path.
- `amount_min`/`amount_max` — same reasoning; an inverted range just yields no matches.
- Malformed `date_from`/`date_to` (not parseable `YYYY-MM-DD`) is treated as if that bound
  were null (skip the check) rather than raising — matches this codebase's existing
  "never trust unparseable input, degrade gracefully" convention (`_normalize_amount`/
  `_normalize_iso_date` in `ledger_event_manager.py`).
