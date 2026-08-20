# Integration Contract: LedgerEventManager Extension for `source_type="חשבונית"`

**Feature**: 025-morning-sourced-ledger-events · Per METHODOLOGY.md §VII format. Extends
`specs/done/v0.2.0/033-ledger-event-persistence/contracts/ledger-event-manager.md` (historical,
do not edit) — this contract documents only the delta.

---

### `add_ledger_event` (existing method, extended)

New forced-null-unless-`חשבונית` block, same position/style as the existing בנק-only and
הסכם-only blocks:

```python
if source_type == "חשבונית":
    accounting_document_id = event.get("accounting_document_id")
    accounting_document_number = event.get("accounting_document_number")
    accounting_document_type = event.get("accounting_document_type")
    accounting_document_status = event.get("accounting_document_status")
    accounting_document_creation_date = _normalize_iso_date(event.get("accounting_document_creation_date"))
else:
    accounting_document_id = None
    accounting_document_number = None
    accounting_document_type = None
    accounting_document_status = None
    accounting_document_creation_date = None
```

`record[...]` dict: the five old always-`None` reserved keys (`morning_document_id`,
`invoice_number`, `invoice_type`, `invoice_status`, `invoice_actual_creation_date`) are renamed
in place to the five above — same position in the dict, no reordering of surrounding fields
(alphabetized on disk by `json.dump(sort_keys=True)` regardless).

`CURRENT_SCHEMA_VERSION = 2` (module constant, was `1`) — applies to every event persisted by
this method regardless of `source_type`, per spec.md Clarifications (schema-version bump instead
of a feature flag).

**Duplicate guard (new)**: before generating `event_id`/writing anything, when
`source_type == "חשבונית"` and `accounting_document_id` is not `None`:

```python
known_ids, _ = self.scan_accounting_documents()
if accounting_document_id in known_ids:
    logger.warning(
        f"Refusing to persist duplicate חשבונית event for "
        f"accounting_document_id={accounting_document_id!r} - already known"
    )
    return None
```

Returns `None` (same sentinel `add_ledger_event` already uses for the REQ-ID-003 seq-exhaustion
case) — callers already handle a `None` return by skipping that event_id, no new return-shape
needed. Placed at the top of the method (before `_next_seq`) since there's no reason to burn a
seq digit on something about to be refused anyway.

---

### `scan_accounting_documents` (new method)

```python
def scan_accounting_documents(self) -> Tuple[Set[str], Optional[date]]:
```

Iterates `self.storage_dir.glob("*.json")` (skipping `.json.tmp` partials, same as `_next_seq`
already does implicitly via its own glob pattern), loads each file, and for every record with
`source_type == "חשבונית"` and non-null `accounting_document_id`:
- adds it to the returned `Set[str]`
- tracks the maximum `accounting_document_creation_date` (parsed via the existing `DD/MM/YYYY`
  convention, same format `_normalize_iso_date`'s output already uses elsewhere)

Returns `(set(), None)` if no such record exists. A malformed/unparseable individual file logs a
WARNING and is skipped, never raises — same defensive read discipline `_load_event` already
uses.

Called by both `add_ledger_event`'s new duplicate guard (previous section) and the
reconciliation service's watermark derivation
(`contracts/accounting-reconciliation-service.md`) — one implementation, two call sites, same
"single shared answer" pattern as `_sweep_due_reminders` in Feature 054.

---

### `LEDGER_EVENT_TOOL` (`ai_handler.py`, existing dict constant — extended)

```python
"source_type": {
    "type": "string",
    "enum": ["הסכם", "בנק", "חשבונית"],
    "description": "הסכם for a fee-agreement event, בנק for a bank deposit/transfer, חשבונית "
                    "for a Morning-sourced accounting document (any document type — invoice, "
                    "receipt, credit note, etc.) transcribed from structured document data "
                    "given to you directly, never inferred from conversation.",
},
"event_subtype": {
    ...
    "enum": ["יצירה", "הפקדה", "הפקה"],
    "description": "...  For source_type=חשבונית: always הפקה.",
},
"accounting_document_id": {
    "type": ["string", "null"],
    "description": (
        "Only for source_type=חשבונית: the Morning document's own id, copied verbatim "
        "from the structured document data you were given. ALWAYS null for הסכם/בנק."
    ),
},
"accounting_document_number": { ... same pattern, Morning's human-visible document number ... },
"accounting_document_type": { ... same pattern, the document's type label ... },
"accounting_document_status": { ... same pattern, the document's status ... },
"accounting_document_creation_date": {
    "type": ["string", "null"],
    "description": (
        "Only for source_type=חשבונית: the document's own date (ISO-8601 YYYY-MM-DD), "
        "copied verbatim from the structured document data you were given. ALWAYS null "
        "for הסכם/בנק."
    ),
},
```

All five added to the top-level `required` array (strict-mode requirement — every property must
be listed, nullable ones just allow `null`). Tool `description` (top of `LEDGER_EVENT_TOOL`)
gains a sentence distinguishing "recognize a fee-agreement/bank-deposit signal in free text or an
image" (existing use) from "transcribe a given Morning document's already-structured fields
verbatim" (`source_type="חשבונית"`, new use) — two different jobs under one tool, not one blurred
instruction (research.md).

**`additionalProperties: False` stays unchanged** — every new field is declared, not smuggled in
implicitly.

---

### `_handle_ledger_event_capture` (existing method — UNCHANGED)

Explicitly **not** touched by this feature. Its same-turn-`mcp_call` suppression and "one call
per turn" rule both stay exactly as they are today, for the conversational (reactive) path —
see research.md's "Critical" note for why reusing/loosening this method would reintroduce the
exact 2026-07-28/2026-08-02 bugs it exists to prevent. The reconciliation sweep gets its own
separate handler (`contracts/accounting-reconciliation-service.md`, step 5) that never touches
this method.
