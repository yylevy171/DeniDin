# Data Model: Ledger Event Recognition (original shipped shape)

**Feature**: 024-ledger-event-recognition · **Reconstructed**: 2026-07-30, sourced verbatim
from `git show ae49b0e:apps/denidin-app/src/handlers/ai_handler.py`'s `LEDGER_EVENT_TOOL`
definition (the actual merged commit) — not reconstructed from memory or inference.

## `capture_ledger_event` tool arguments (16 keys, original shape)

`type: "function"`, `strict: True`, `additionalProperties: False`. All 16 keys are listed in
`required` (strict mode requires every property present; nullable ones are typed
`["<type>", "null"]` rather than being optional).

| Field | Type | Description (verbatim from the shipped tool schema) |
|---|---|---|
| `source_type` | `string` enum `["הסכם", "בנק"]` | הסכם for a fee-agreement event, בנק for a bank deposit/transfer. |
| `event_subtype` | `string` enum `["יצירה", "עדכון", "ביטול", "אישור-מימוש", "הפקדה"]` | For source_type=הסכם: יצירה (new)/עדכון (correction)/ביטול (cancellation)/אישור-מימוש (payment/milestone confirmed). For source_type=בנק: always הפקדה. |
| `client_name` | `string \| null` | The client's name, verbatim. |
| `payer_name` | `string \| null` | The paying entity, ONLY if different from client_name (e.g. an insurer/union routing payment). |
| `description` | `string \| null` | The matter/engagement, verbatim or closely paraphrased. |
| `amount` | `string \| null` | The stated amount, verbatim (no currency conversion, no math). |
| `percent` | `string \| null` | A stated percentage figure, if any (e.g. success-fee percentage). |
| `percent_base` | `string \| null` | What the percent applies to, if stated. |
| `hours` | `string \| null` | Stated hours, for an hourly work-log entry. |
| `hourly_rate` | `string \| null` | Stated hourly rate, if any. |
| `vat_status` | `string` enum `["כולל", "לא כולל", "לא צוין"]` | VAT-inclusive, VAT-exclusive, or not stated - never assumed. |
| `replaces_hint` | `string \| null` | Free-text description of a prior arrangement this corrects/cancels, ONLY if identifiable from this conversation - never a guess. |
| `reference_hint` | `string \| null` | Free-text loose reference to a related (not replaced) prior matter, if any. |
| `notes` | `string \| null` | Any ambiguity or uncertainty worth flagging for the human reviewer. |
| `raw_message_excerpt` | `string` (required, non-null) | Verbatim source text (or a precise description of the image) this capture is based on - the hard pointer for later verification. |

## Storage shape at this feature's original shipped time

Captured arguments were appended to `Session.pending_ledger_events` (a list of dicts) inside
`session.json`, via `SessionManager.add_pending_ledger_event` — no independent persistence,
no `event_id` scheme yet, no `message_id` traceability field. **This storage layer was
entirely replaced by Feature 026** (`data/events/*.json` via `LedgerEventManager`); this
section is preserved here only for historical accuracy about what this feature itself shipped.

## Since superseded

Feature 026 (2026-07-29/30) extended this schema to 19 keys (`agreement_label`,
`component_label`, `hours_date` added) and moved storage entirely — see
`specs/in-progress/026-ledger-event-persistence/data-model.md` for the current, authoritative
shape. This document intentionally describes only the original 16-key shape this feature
shipped with.
