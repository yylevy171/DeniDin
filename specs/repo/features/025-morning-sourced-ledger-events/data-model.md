# Phase 1 Data Model: Morning-Sourced Ledger Events

> **Superseded in part by Phase 9 (2026-08-23)** — see the "Phase 9 final shape" section at the
> bottom of this file. The field-naming and dedup design below still holds; what changed is how
> the data reaches the ledger (one verbatim JSON payload, mapped in code) and which extra fields
> are persisted.

**Feature**: 025-morning-sourced-ledger-events · **Date**: 2026-08-20

## Entity: `LedgerEvent` (existing, `ledger_event_manager.py` — extended, not replaced)

Same file/record shape Feature 033 built (`{data_root}/events/{event_id}.json`, one file per
event, `json.dump(..., sort_keys=True, ensure_ascii=False, indent=2)`). This feature extends it —
no new storage mechanism, no new manager class for storage.

### Field changes to the persisted record

**Revised 2026-08-21 (round 3)**: the field count drops from the originally-planned 5 to **4** —
round 2's separate `accounting_document_id` (Morning's opaque internal id) and
`accounting_document_number` (the human-visible number) collapse into **one** field,
`accounting_document_display_number`, per user correction (`spec.md`'s round-3 Clarifications):
*"document id... is the USER FACING display number - NOT the morning internal id."* Morning's
internal id (`Invoice.id`) is used only transiently within a sweep tick (to call
`get_invoice_details`) — never persisted, never its own field.

| Old field (Feature 033, always `null` to date) | New field (this feature) | Population rule |
|---|---|---|
| `morning_document_id` + `invoice_number` (merged) | `accounting_document_display_number` | Morning's real `number` field (confirmed live 2026-08-21: non-null on all 25 real dev-sandbox documents observed, across 6 distinct document types) — **the dedup key** (see "Dedup mechanism" below) |
| `invoice_type` | `accounting_document_type` | Morning's `Invoice.type` (int), decoded to its Hebrew label via `GET /documents/types` (already confirmed live elsewhere in `morning-mcp-app` — reuse that lookup) |
| `invoice_status` | `accounting_document_status` | Morning's `Invoice.status` (already normalized to a canonical vocabulary by the `Invoice` model) |
| `invoice_actual_creation_date` | `accounting_document_creation_date` | **Revised 2026-08-21**: Morning's raw `creationDate` field — a real Unix epoch integer with full second-level precision (confirmed live: e.g. `1787241168` → `2026-08-20 18:52:48` Israel local) — NOT `documentDate`/`Invoice.issue_date` (date-only) as round 1/2 assumed. Formatted `DD/MM/YYYY HH:MM` (matching `event_datetime`'s full-instant convention, not `txn_date`'s date-only one). **`apps/morning-mcp-app`'s `Invoice` model does not currently map `creationDate` at all** — this feature adds that mapping (see `tasks.md`'s new morning-mcp-app task) |

All four: **non-null only when `source_type == "חשבונית"`**, forced `null` for `הסכם`/`בנק`
regardless of what any caller passes — same defensive discipline `add_ledger_event` already
applies to `bank_number`/`bank_branch`/`bank_account` (בנק-only) and `trigger_condition`/
`component_label` (הסכם-only).

Renaming these (rather than adding new fields alongside the always-null old ones) is safe: per
`specs/done/v0.2.0/033-ledger-event-persistence/data-model.md`, they have been `null` in **every**
real persisted file to date — no real data to migrate.

**`event_id`/`event_datetime` generation for a `חשבונית` capture**: unlike the text/image paths
(which derive these from the source *message's* timestamp), a reconciliation capture has no real
source message — `message_timestamp` passed into `add_ledger_event` is instead the epoch derived
from the document's own real `creationDate` (full HH:MM precision, confirmed live — see table
above). This means `event_id`'s `ddmmyy`/`hhmm` portion reflects the document's own real creation
moment, not sweep processing time, which is also what makes the dedup mechanism's
"same display number + same creation timestamp → true duplicate" comparison meaningful (see
below).

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
- **Four** (not five, per round 3's field merge) new **top-level** (shared, not per-component)
  properties, all `["string", "null"]`, matching the naming table above, each added to `required`
  (strict-mode requirement) with a description stating they are populated ONLY for
  `source_type="חשבונית"`, always `null` otherwise, and — critically — that they must be copied
  verbatim from the structured document data given in this call's own instructions, never
  inferred/guessed from conversation text.
- Tool `description` gets an added sentence distinguishing the two populate-this-tool
  situations: recognizing a fee-agreement/bank-deposit signal in free text/images (existing,
  unchanged) vs. transcribing a given Morning document's already-structured fields
  (`source_type="חשבונית"`, new) — so the two usages read as clearly different jobs to the model,
  not one blurred instruction.

## Entity: `AccountingDocumentReconciliationState` (revised 2026-08-21, round 3 — in-memory, not persisted; `pending_review.json` IS a new small persisted entity)

**Round 1 design (superseded)**: fully re-derived by scanning every `LedgerEvent` file on every
poll tick. **Rejected by the user** (*"ideally no reading and parsing of the ledger events is
required per tick"*) in favor of the design below.

**Round 3 design**: `LedgerEventManager` holds an **in-process, in-memory** cache —
`self._accounting_document_cache: Optional[Dict[str, List[datetime]]]` (`None` until first built)
— mapping each `accounting_document_display_number` to the list of distinct
`accounting_document_creation_date` timestamps ever seen for it (almost always exactly one; more
than one only in the anomaly case, see "Dedup mechanism" below). Built **once** per process
lifetime, lazily, on the first `source_type="חשבונית"` call to `add_ledger_event`:

```python
def scan_accounting_documents(self) -> Dict[str, List[datetime]]:
    """One-time disk scan (never called more than once per process - see
    _ensure_accounting_document_cache): every persisted source_type="חשבונית"
    event, grouped by accounting_document_display_number into the list of
    distinct creation datetimes seen for it. Empty dict if none exist yet.
    Malformed/unparseable JSON files are skipped with a WARNING, never
    raise (mirrors _load_event's existing defensive-read discipline)."""

def _ensure_accounting_document_cache(self) -> Dict[str, List[datetime]]:
    """Lazy-builds self._accounting_document_cache via scan_accounting_documents()
    on first call; every subsequent call in this process's lifetime returns
    the already-built, in-memory-mutated cache unchanged - no re-scan."""
```

**Tri-state duplicate/anomaly/new decision** — lives inside `add_ledger_event` itself for
`source_type="חשבונית"` (a ledger-persistence concern, not an AI-handler one — user directive:
*"it's clearly a ledger requirement regardless of ai"*):

```python
def _resolve_accounting_document_status(
    self, display_number: str, creation_dt: datetime
) -> Literal["new", "duplicate", "anomaly"]:
    """Consults (and does NOT itself mutate) the lazily-built cache.
    "new": display_number not in cache.
    "duplicate": display_number in cache AND creation_dt matches one of its
        recorded timestamps exactly - a true re-poll of the identical
        document. add_ledger_event silently discards (returns None, no file
        written, cache untouched) - never trusted to a refusal/exception,
        just a normal no-op return.
    "anomaly": display_number in cache but creation_dt does NOT match any
        recorded timestamp - "this should never happen" for a real Morning
        document (per user). add_ledger_event persists this as a NEW
        LedgerEvent (own new event_id, driven by the differing creation_dt)
        exactly like "new", but ALSO logs a WARNING and appends an entry to
        pending_review.json (see below), and adds creation_dt to the cache
        entry's timestamp list (now holding 2+ timestamps for this
        display_number)."""
```

**Pruning, every tick** (called from the reconciliation service, once per sweep, after any new
captures for that tick): drop any cache entry whose *every* recorded timestamp is older than the
5-day safety-cap boundary (see below) plus a ~2-day margin (7 days total) before `now_local()` —
the forward-only watermark can never legitimately cause a document that old to be re-queried
again. **Flagged for live confirmation** of Morning's actual `from_date` filter semantics before
this exact margin is trusted (folds into `tasks.md`'s live-verification task) — the reasoning is
sound in principle, not yet independently confirmed for the boundary behavior itself.

**Poll watermark** is simply `max(timestamp for timestamps in cache.values() for timestamp in
timestamps)`, or `None` if the cache is empty — no separate field, no separate file.

## Entity: `pending_review.json` (new, 2026-08-21, round 3)

`{data_root}/accounting_reconciliation/pending_review.json` — append-only list, one entry per
"anomaly" detection above:

```json
{
  "accounting_document_display_number": "40406",
  "prior_event_id": "H2008211852...",
  "prior_creation_date": "20/08/2026 18:52",
  "new_event_id": "H2108210930...",
  "new_creation_date": "21/08/2026 09:30",
  "detected_at": "21/08/2026 09:35"
}
```

Written by `LedgerEventManager` (same directory family as `events/`, sibling
`accounting_reconciliation/` subdirectory of `{data_root}`) — a human reviews this file
out-of-band, the same "capture now, review later, no notification" philosophy the rest of this
feature already follows. No reader/consumer of this file exists yet within this feature's own
scope (matches `REFERENCE_PLACEHOLDER`'s existing precedent of a flag meant for a *later*,
not-yet-built review step).

## Safety cap (new, 2026-08-21, round 3)

5 days OR 100 not-yet-known documents since the derived watermark, whichever binds first. Checked
by the reconciliation service directly (a plain, non-AI-mediated `list_invoices(from_date=since)`
call solely for counting/date-checking), before ever constructing the OpenAI+MCP prompt. On
breach: skip the entire tick (no captures, watermark unchanged), log ERROR only — no persisted
tracker, no WhatsApp (this stays a silent, log-discoverable-only mechanism, same as the rest of
this feature).

## Entity: `Session`/`Message` (existing — untouched by this feature)

A reconciliation-sourced `LedgerEvent` has no real originating chat session or WhatsApp message —
unlike the text/image capture paths. `session_id`/`message_id` on the persisted record (existing
DeniDin-internal traceability fields, unchanged shape) get sentinel values for this source
(`session_id="accounting-reconciliation"`, `message_id=None`) rather than a fabricated real-
looking id — exact sentinel convention confirmed in `contracts/`, not invented ad hoc per call
site.


---

## Phase 9 final shape (2026-08-23, as built)

### How a `חשבונית` capture arrives

`capture_ledger_event`'s four transcribed `accounting_document_*` arguments were replaced by a
**single** argument, `accounting_document_json`: the whole document object from
`morning-mcp-app`, copied verbatim by the model as one string.
`LedgerEventManager._expand_accounting_document_json` parses it and derives every persisted value
**in code** — the model copies, it never interprets. Parsed with `strict=False`: a real run lost
3 of 18 documents silently because the model re-emitted the payload with literal newlines where
`json.dumps` had written `\n` (content intact, escaping mangled in transit); genuinely malformed
JSON is still rejected loudly.

### `event_subtype` carries the Morning document type (2026-08-23)

The document type is persisted **in `event_subtype`**, using Morning's own retrieved label:
`חשבון עסקה` / `חשבונית מס` / `חשבונית מס / קבלה` / `חשבונית זיכוי` / `קבלה`. Derived in code from
the JSON payload's `type_name`; whatever the model passes is overridden. **`accounting_document_type`
is removed** — the type now lives in `event_subtype` and storing it twice would be redundant.
`הסכם`/`בנק` keep `יצירה`/`הפקדה` unchanged.

### Persisted fields added

| Field | Source | Note |
|---|---|---|
| `accounting_document_status_code` | `status` (raw int) | Morning's real axis is open/closed |
| `accounting_document_status_label` | Morning's own label | e.g. `מסמך סגור` — kept because mapping closed→"paid" is an interpretation that can be wrong for a proforma |
| `accounting_document_payment_method` | `payment[].name` | `העברה בנקאית` / `מזומן` / … |

### Existing fields reused (no new field)

- `bank_number` / `bank_branch` / `bank_account` ← `payment[].bankName/bankBranch/bankAccount`.
  The `בנק`-only force-null is **lifted**; `הסכם` still forces them null.
- **`txn_date`** ← `payment[].date` — it already means "the transaction/value date" and persists
  to Events.csv's `תאריך_ביצוע`.
- **`reference` / `reference_hint`** ← `linkedDocuments[0]`. The hint is code-generated and always
  carries the linked number **and its Hebrew type name** (never the raw code); resolution happens
  at capture time against the in-memory cache, writing the target's real `event_id` into
  `reference`, else leaving `REFERENCE_PLACEHOLDER` **and stating the failure in the hint**.
- `vat_status` — derived in code from `vat_amount`; a VAT-exempt document asserts neither
  `כולל` nor `לא כולל` (both would be false) and records `לא צוין`.

### Line items

Only the **first** `income[]` entry is used, with a WARNING naming how many were dropped and for
which document. A `400`/`קבלה` has no `income[]` at all and falls back to the document-level
description.

### `schema_version` 2 → 3

Applies globally to every new write regardless of `source_type`. Pre-existing records are never
retro-updated (the established rule).

### Skipped deliberately (reviewed field-by-field, 2026-08-23)

`amount_open` (volatile), `amount_excl_vat` + `vat_rate` (derivable), `vat_amount`, `issue_date`
(matched the creation date on all 5 sampled types), `currency` (ILS-only today), `morning_id`
(display number is the identity), `issued_by` (constant today). These are read from the payload
where needed for derivation, just not persisted.
