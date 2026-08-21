# Integration Contract: LedgerEventManager Extension for `source_type="חשבונית"`

**Feature**: 025-morning-sourced-ledger-events · Per METHODOLOGY.md §VII format. Extends
`specs/done/v0.2.0/033-ledger-event-persistence/contracts/ledger-event-manager.md` (historical,
do not edit) — this contract documents only the delta.

**Revised 2026-08-21 (round 3, `spec.md`'s Clarifications)**: replaces the original hard-refusal
duplicate guard entirely with an in-memory tri-state (new/duplicate/anomaly) design, and collapses
the originally-planned `accounting_document_id`/`accounting_document_number` field pair into one
field, `accounting_document_display_number`. See `research.md`/`data-model.md` for the full
reasoning; this file is the code-level delta only.

---

### `add_ledger_event` (existing method, extended)

New forced-null-unless-`חשבונית` block, same position/style as the existing בנק-only and
הסכם-only blocks:

```python
if source_type == "חשבונית":
    accounting_document_display_number = event.get("accounting_document_display_number")
    accounting_document_type = event.get("accounting_document_type")
    accounting_document_status = event.get("accounting_document_status")
    accounting_document_creation_date = local_dt.strftime("%d/%m/%Y %H:%M")  # from message_timestamp - see below
else:
    accounting_document_display_number = None
    accounting_document_type = None
    accounting_document_status = None
    accounting_document_creation_date = None
```

`record[...]` dict: the five old always-`None` reserved keys (`morning_document_id`,
`invoice_number`, `invoice_type`, `invoice_status`, `invoice_actual_creation_date`) are replaced
by the **four** fields above (round 3 merged `morning_document_id`/`invoice_number` into one) —
same position in the dict, no reordering of surrounding fields (alphabetized on disk by
`json.dump(sort_keys=True)` regardless).

`CURRENT_SCHEMA_VERSION = 2` (module constant, was `1`) — applies to every event persisted by
this method regardless of `source_type`, per spec.md Clarifications (schema-version bump instead
of a feature flag).

**`message_timestamp` for a `חשבונית` capture**: unlike the text/image paths (a real source
message's own timestamp), the caller (the new `ai_handler.py` reconciliation handler) passes the
epoch derived from the Morning document's own real `creationDate` (full HH:MM:SS precision,
confirmed live — see `data-model.md`) — this is what drives both `event_id`'s date/time portion
and `accounting_document_creation_date`'s value, and is exactly what makes the duplicate/anomaly
comparison below meaningful (a genuine re-poll of the same document always derives the identical
`local_dt`).

**Duplicate/anomaly guard — REPLACED (round 3)**: no hard refusal. Before generating `event_id`/
writing anything, when `source_type == "חשבonית"` and `accounting_document_display_number` is not
`None`:

```python
cache = self._ensure_accounting_document_cache()  # lazy one-time disk scan, see below
seen_timestamps = cache.get(accounting_document_display_number, [])

if local_dt in seen_timestamps:
    logger.info(
        f"חשבונית re-poll: accounting_document_display_number="
        f"{accounting_document_display_number!r} at {local_dt!r} already captured - "
        f"discarding (true duplicate, no new file)"
    )
    return None  # same sentinel add_ledger_event already uses (REQ-ID-003 exhaustion case)

if seen_timestamps:  # known display_number, but this timestamp is new -> anomaly
    logger.warning(
        f"חשבונית anomaly: accounting_document_display_number="
        f"{accounting_document_display_number!r} previously seen at "
        f"{seen_timestamps!r}, now seen at {local_dt!r} - persisting as a NEW event "
        f"(not overwriting) and flagging to pending_review.json for human review"
    )
    self._append_pending_review(
        accounting_document_display_number, seen_timestamps, local_dt,
    )
# "new" (empty seen_timestamps) and "anomaly" both fall through to the normal
# persist path below - the difference is only the logging/pending_review side
# effect. cache[accounting_document_display_number] is appended with local_dt
# AFTER a successful write (see end of method).
```

`_ensure_accounting_document_cache` and `_append_pending_review` are new private helpers (see
below). Placed at the top of the method (before `_next_seq`), same position the old hard-refusal
guard used to occupy.

---

### `scan_accounting_documents` (new method — startup bootstrap only, never called per-tick)

```python
def scan_accounting_documents(self) -> Dict[str, List[datetime]]:
```

Iterates `self.storage_dir.glob("*.json")` (skipping `.json.tmp` partials, same as `_next_seq`
already does implicitly via its own glob pattern), loads each file, and for every record with
`source_type == "חשבונית"` and non-null `accounting_document_display_number`, appends its parsed
`accounting_document_creation_date` (format `DD/MM/YYYY HH:MM`, parsed to a `datetime`) to that
display number's list. Returns `{}` if no such record exists. A malformed/unparseable individual
file logs a WARNING and is skipped, never raises — same defensive read discipline `_load_event`
already uses.

**Called exactly once per process**, not per tick — see `_ensure_accounting_document_cache` below.

```python
def _ensure_accounting_document_cache(self) -> Dict[str, List[datetime]]:
    """Lazy-builds self._accounting_document_cache (instance attribute,
    None until first built) via scan_accounting_documents() on first call.
    Every subsequent call in this process's lifetime returns the
    already-built, in-memory-mutated cache directly - no re-scan, per
    spec.md's round-3 "no reading and parsing of the ledger events... per
    tick" directive."""
    if self._accounting_document_cache is None:
        self._accounting_document_cache = self.scan_accounting_documents()
    return self._accounting_document_cache
```

`self._accounting_document_cache: Optional[Dict[str, List[datetime]]] = None` is a new
`__init__`-set instance attribute.

**After a successful `חשבונית` persist** (end of `add_ledger_event`, both the "new" and "anomaly"
cases — never the "duplicate" case, which returns early):

```python
cache.setdefault(accounting_document_display_number, []).append(local_dt)
```

**Pruning (new method, called once per sweep tick by the reconciliation service, NOT by
`add_ledger_event` itself — see `contracts/accounting-reconciliation-service.md`)**:

```python
def prune_accounting_document_cache(self, now: Optional[datetime] = None) -> None:
    """Drops any cache entry whose every recorded timestamp is older than
    the 5-day safety-cap boundary plus a ~2-day margin (7 days total)
    before now (now_local() if not given - testability seam only, same
    convention as reminder_delivery_service.py's `now` parameter). Safe
    because the forward-only watermark can never legitimately cause a
    document that old to be re-queried again - see data-model.md's
    "Pruning" note for the still-open live-verification caveat on this
    margin."""
```

---

### `_append_pending_review` (new private method)

Appends one entry to `{data_root}/accounting_reconciliation/pending_review.json` (creating the
directory/file on first use, same tmp-then-replace atomic-write pattern `_write_event` already
uses) — see `data-model.md`'s `pending_review.json` entity for the exact entry shape. Never reads
back / resolves entries — this feature has no consumer of this file yet, it exists purely so a
human has somewhere to look (matches `REFERENCE_PLACEHOLDER`'s existing "flag for a future,
not-yet-built resolution step" precedent).

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
"accounting_document_display_number": {
    "type": ["string", "null"],
    "description": (
        "Only for source_type=חשבונית: the Morning document's user-facing display "
        "number (never Morning's internal id), copied verbatim from the structured "
        "document data you were given. ALWAYS null for הסכם/בנק."
    ),
},
"accounting_document_type": { ... same pattern, the document's type label ... },
"accounting_document_status": { ... same pattern, the document's status ... },
"accounting_document_creation_date": {
    "type": ["string", "null"],
    "description": (
        "Only for source_type=חשבונית: the document's own real creation date+time "
        "(ISO-8601, e.g. 2026-08-20T18:52:48), copied verbatim from the structured "
        "document data you were given. ALWAYS null for הסכם/בנק."
    ),
},
```

**Four** fields (not five — round 3 merged the planned `_id`/`_number` pair into one
`_display_number` field), all added to the top-level `required` array (strict-mode requirement —
every property must be listed, nullable ones just allow `null`). Tool `description` (top of
`LEDGER_EVENT_TOOL`) gains a sentence distinguishing "recognize a fee-agreement/bank-deposit
signal in free text or an image" (existing use) from "transcribe a given Morning document's
already-structured fields verbatim" (`source_type="חשבונית"`, new use) — two different jobs under
one tool, not one blurred instruction (research.md).

**`additionalProperties: False` stays unchanged** — every new field is declared, not smuggled in
implicitly.

---

### `_handle_ledger_event_capture` (existing method — UNCHANGED)

Explicitly **not** touched by this feature. Its same-turn-`mcp_call` suppression and "one call
per turn" rule both stay exactly as they are today, for the conversational (reactive) path —
see research.md's "Critical" note for why reusing/loosening this method would reintroduce the
exact 2026-07-28/2026-08-02 bugs it exists to prevent. The reconciliation sweep gets its own
separate handler (`contracts/accounting-reconciliation-service.md`, step 5) that never touches
this method, and — per round 3 — that new handler is a thin adapter with no dedup logic of its
own; the new/duplicate/anomaly decision documented above lives entirely inside
`LedgerEventManager`.
