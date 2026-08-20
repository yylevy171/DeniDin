# Phase 1 Data Model: Morning-Sourced Ledger Events

**Feature**: 025-morning-sourced-ledger-events · **Date**: 2026-08-20

## Entity: `LedgerEvent` (existing, `ledger_event_manager.py` — extended, not replaced)

Same file/record shape Feature 033 built (`{data_root}/events/{event_id}.json`, one file per
event, `json.dump(..., sort_keys=True, ensure_ascii=False, indent=2)`). This feature extends it —
no new storage mechanism, no new manager class for storage.

### Field changes to the persisted record

| Old field (Feature 033, always `null` to date) | New field (this feature) | Population rule |
|---|---|---|
| `morning_document_id` | `accounting_document_id` | Morning's `Invoice.id` — the dedup key (see below) |
| `invoice_number` | `accounting_document_number` | Morning's `Invoice.number` |
| `invoice_type` | `accounting_document_type` | Morning's `Invoice.type` (int), decoded to its Hebrew label via `GET /documents/types` (already confirmed live elsewhere in `morning-mcp-app` — reuse that lookup) |
| `invoice_status` | `accounting_document_status` | Morning's `Invoice.status` (already normalized to a canonical vocabulary by the `Invoice` model) |
| `invoice_actual_creation_date` | `accounting_document_creation_date` | Morning's `Invoice.issue_date`, formatted `DD/MM/YYYY` (same convention as `event_datetime`/`txn_date`) — **the only real timestamp `Invoice` currently exposes**; there is no separate Morning-side "system creation" timestamp distinct from the document's own issue/document date, so this is what "creation date" resolves to, not a guess pending further investigation |

All five: **non-null only when `source_type == "חשבונית"`**, forced `null` for `הסכם`/`בנק`
regardless of what any caller passes — same defensive discipline `add_ledger_event` already
applies to `bank_number`/`bank_branch`/`bank_account` (בנק-only) and `trigger_condition`/
`component_label` (הסכם-only).

Renaming these (rather than adding new fields alongside the always-null old ones) is safe: per
`specs/done/v0.2.0/033-ledger-event-persistence/data-model.md`, they have been `null` in **every**
real persisted file to date — no real data to migrate.

### `source_type` enum extension

`_LETTER_BY_SOURCE_TYPE` (`ledger_event_manager.py`) gains `"חשבונית": "H"` — the letter already
reserved in that dict's own comment. `event_id` generation (`{letter}{DDMMYY}{HHMM}{seq}`) needs
no other change — `חשבונית` events use the same collision-avoidance scheme as `הסכם`/`בנק`.

### `event_subtype` enum extension

Today: `["יצירה", "הפקדה"]` (one value per existing `source_type`). New value for `חשבונית`:
**`"הפקה"`** (issuance — Hebrew accounting terminology for a document being issued), proposed
here as the natural per-`source_type` echo of `יצירה`/`הפקדה`'s pattern. **Flagged for
confirmation during `speckit.tasks`/implementation**, same as the `source_type="חשבונית"` term
itself (see research.md's naming risk) — not a blocking unknown, but a real-world-vocabulary
choice worth a quick sanity check against how the term is actually used, not assumed correct
because it's internally consistent.

### Fields that do NOT apply to `source_type="חשבונית"` (forced `null`, mirroring existing per-type discipline)

`agreement_id`, `component_id`, `component_label`, `trigger_condition`, `percent`,
`percent_base`, `hours`, `hourly_rate`, `bank_number`, `bank_branch`, `bank_account`,
`payer_name` — none of these concepts apply to a Morning-sourced document capture. A `חשבונית`
event is always a single-component capture (`component_count=1`, `components` has exactly one
entry) — there is no multi-component/agreement concept for a Morning document the way there is
for a fee agreement; `amount`, `description`, `vat_status`, `txn_date` are reused as-is from the
existing component shape (`amount` = `Invoice.total_amount` or `Invoice.amount`; `txn_date` =
`accounting_document_creation_date`'s underlying date; `vat_status` derived from whether
`Invoice.vat_amount` is present/non-zero).

### `LEDGER_EVENT_TOOL` schema changes (`ai_handler.py`)

- `source_type.enum`: `["הסכם", "בנק", "חשבונית"]`.
- `event_subtype.enum`: `["יצירה", "הפקדה", "הפקה"]`; description updated to state the
  `חשבונית`→`הפקה` mapping alongside the existing two.
- Five new **top-level** (shared, not per-component) properties, all `["string", "null"]`,
  matching the naming table above, each added to `required` (strict-mode requirement) with a
  description stating they are populated ONLY for `source_type="חשבונית"`, always `null`
  otherwise, and — critically — that they must be copied verbatim from the structured document
  data given in this call's own instructions, never inferred/guessed from conversation text.
- Tool `description` gets an added sentence distinguishing the two populate-this-tool
  situations: recognizing a fee-agreement/bank-deposit signal in free text/images (existing,
  unchanged) vs. transcribing a given Morning document's already-structured fields
  (`source_type="חשבונית"`, new) — so the two usages read as clearly different jobs to the model,
  not one blurred instruction.

## Entity: `AccountingDocumentReconciliationState` (derived, not persisted — no new entity)

Deliberately **not** a new persisted entity. The "since when" watermark for each poll tick is
computed on demand by scanning existing `source_type="חשבונית"` `LedgerEvent` files for the
maximum `accounting_document_creation_date`, with a fallback lookback constant when none exist
yet (mirrors `reminder_delivery_service.py`'s `STARTUP_SWEEP_LOOKBACK`/`PERIODIC_SWEEP_LOOKBACK`
split — exact values TBD in `tasks.md`, not fixed here since they're a tuning decision, not a
data-shape one).

New `LedgerEventManager` method (index/scan helper — this class currently has no by-field lookup
across all events, only `_load_event(event_id)`):

```python
def scan_accounting_documents(self) -> Tuple[Set[str], Optional[date]]:
    """Scan every persisted source_type="חשבונית" event and return
    (known_accounting_document_ids, latest_accounting_document_creation_date).
    Both empty/None if no such event has ever been persisted. Used by the
    reconciliation service both as the dedup guard's known-id set AND to
    derive the next poll's "since" watermark - one scan, two answers, kept
    in one method so both stay trivially consistent with each other."""
```

Called once per poll tick (before the OpenAI call, to build the prompt's "since" date; and again,
or reusing the same result, as the duplicate guard before each persist) — a full directory scan
of `{data_root}/events/*.json`. Acceptable at current/foreseeable event volume (single-digit to
low-hundreds of files, per Feature 033's own stated scale) — no index file, no caching, matching
this manager's existing "flat files, no database" design throughout.

Implementation note (`speckit.analyze` finding L3): this signature needs imports
`ledger_event_manager.py` doesn't currently have — `Set`/`Tuple` from `typing` (today's import
line is `from typing import Dict, List, Optional`) and `date` from `datetime` (today's is
`from datetime import datetime`, no bare `date`).

## Entity: `Session`/`Message` (existing — untouched by this feature)

A reconciliation-sourced `LedgerEvent` has no real originating chat session or WhatsApp message —
unlike the text/image capture paths. `session_id`/`message_id` on the persisted record (existing
DeniDin-internal traceability fields, unchanged shape) get sentinel values for this source
(`session_id="accounting-reconciliation"`, `message_id=None`) rather than a fabricated real-
looking id — exact sentinel convention confirmed in `contracts/`, not invented ad hoc per call
site.
