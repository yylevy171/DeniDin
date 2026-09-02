# Data Model: Post-Turn Ledger Capture with Mandatory Client Resolution

**Phase 1** | **Plan**: [plan.md](./plan.md) | **Research**: [research.md](./research.md)

This feature adds **no persisted schema** and **no config keys**. It adds two transient
in-memory shapes (the recognition-call output; the media-ledger stash), three app-log line
formats, and one fixed marker phrase. `LedgerEvent`'s persisted record and
`CURRENT_SCHEMA_VERSION` are **unchanged** (human decision 2026-08-31).

> **Redesign note (2026-09-01).** An earlier version of this file modelled an inline
> `record_unresolved_ledger_capture` function tool (§4). The redesign removes all inline
> ledger tools except read-only `query_ledger_events`; the "declined by operator" signal now
> comes from the recognition call's tri-state verdict. §4 is replaced with the
> recognition-call output shape.

---

## 1. `LedgerEvent` — UNCHANGED

- No new field. `record` dict (`ledger_event_manager.py:~1079-1145`) unchanged.
- `CURRENT_SCHEMA_VERSION` stays **2**; `SCHEMA_VERSION_HISTORY` untouched;
  `_verify_schema_version_history()` unaffected.
- **No test asserts `schema_version`'s value** (CLAUDE.md rule).

### Which `LedgerEvent` fields are mandatory / retained / generated (FR-069-010..019)

The recognition call must produce these before returning `complete`; the ledgerer generates
the rest. Nothing is added to the schema — this is a completeness contract over existing
fields.

| type | mandatory (recognition call) | conditional | retain-if-provided | generated (ledgerer) |
|---|---|---|---|---|
| `הסכם` | `client_name` (exact Morning name **or** store-anyway free text); event date → `event_datetime` source; `description`; ≥1 entry in `components` **OR** an hours value | per component: `amount` > 0 **OR** `percent` | `payer_name`; per-component `trigger_condition` / `percent` / `percent_base` / `hours` / `hourly_rate`; `reference` / `reference_hint` | `event_id`, `event_datetime`, `captured_at`, `agreement_id`, `component_id` |
| `בנק` | `client_name` (exact **or** store-anyway); `txn_date`; `amount`; `description`; `vat_status` (code-forced `כולל` unless operator states otherwise — `ledger_event_manager.py:1052`) | — | `bank_number` / `bank_branch` / `bank_account`; `reference` / `reference_hint` | `event_id`, `event_datetime`, `captured_at` |
| `חשבונית` | `client_name` (resolved by construction); `txn_date`; `event_subtype` (= document type — **no `accounting_document_type` field**, `ledger_event_manager.py:1084`); `amount`; `accounting_document_display_number` | — | `accounting_document_status` / `_status_code` / `_status_label` / `_payment_method`; `reference` / `reference_hint`; every other `accounting_document_*` field from the Morning response | `event_id`, `event_datetime`, `captured_at` |

`agreement_id` is **generated, never provided** — excluded from retain-if-provided
(operator direction, 2026-09-01).

### The store-anyway marker (FR-069-033) — free text, not a field

- **Phrase (proposed, exact wording approved in `speckit.implement`)**:
  `[לקוח לא אומת במורנינג]`
- Written by the **recognition call** into the `complete` verdict's `event.description`, in
  the same payload that carries the operator-stated free-text `client_name`. The
  constitution's store-anyway guidance instructs it.
- Bracketed so tests assert it as a stable substring of the persisted
  `LedgerEvent.description`, and so a human reading the event sees it plainly.
- The ledgerer persists `description` verbatim — **no code branch** for the marker on the
  write path.

**Assertion contract**: on a store-anyway event —
`"[לקוח לא אומת במורנינג]" in event.description` AND `event.client_name` == the
operator-stated name AND every other manifest field matches (see
`contracts/payload-fidelity-manifest.md`).

---

## 2. Recognition-call output — transient, not persisted (NEW)

**Purpose**: the single structured result of `AIHandler.recognize_ledger_event(...)` — the
one text-only OpenAI call fired after every godfather/admin turn's reply is sent. It is the
**only** place prose → `LedgerEvent` schema mapping happens. Never shown to the operator;
never written to disk; consumed immediately by the ledgerer and discarded.

**Lifetime**: created in `recognize_ledger_event`, passed to
`LedgerEventManager.persist_recognized_event(...)`, then garbage-collected. No dataclass on
disk, no manager field.

**Shape** — a tri-state verdict:

```jsonc
// verdict "complete" — a complete ledger event finished THIS round
{
  "verdict": "complete",
  "event": {
    // fully mapped to the LedgerEvent schema — see the table in §1:
    "source_type": "הסכם" | "בנק" | "חשבונית",
    "event_subtype": "<string>",              // = document type for חשבונית
    "client_name": "<exact Morning name, or operator free text on store-anyway>",
    "description": "<free text; carries the [לקוח לא אומת במורנינג] marker on store-anyway>",
    "amount": <number>,                        // normalized, בנק/חשבונית
    "txn_date": "<ISO date>",                  // בנק/חשבונית
    "vat_status": "כולל" | "לא כולל" | null,   // בנק (code-forced), הסכם
    "components": [                            // הסכם — one entry per fee component
      { "amount": <number|null>, "percent": <number|null>, "percent_base": "<str|null>",
        "trigger_condition": "<str|null>", "hours": <number|null>, "hourly_rate": <number|null>,
        "description": "<str>" }
    ],
    "payer_name": "<str|null>",                // הסכם only, free text, MAY differ from client_name
    "bank_number": "<str|null>", "bank_branch": "<str|null>", "bank_account": "<str|null>",  // בנק
    "accounting_document_display_number": "<str|null>",   // חשבונית — from the real Morning response
    "reference": "<event_id|null>",            // established in conversation via query_ledger_events
    "reference_hint": "<str|null>"
  },
  "trigger_message_id": "<session message id>" // the message that first introduced the event's
                                               // core economic content — the ledgerer reads its
                                               // Green API notification timestamp for event_datetime
}
```

```jsonc
// verdict "none" — nothing complete this round (incl. unresolved client, incomplete fields,
// read-only Morning question, ordinary chatter, mid-detour turn)
{ "verdict": "none" }
```

```jsonc
// verdict "declined" — operator was asked the single closed store-anyway question
// (FR-069-033, no re-ask for email/phone first) and explicitly answered "don't store"
{
  "verdict": "declined",
  "source_type": "הסכם" | "בנק",
  "client_name_stated": "<operator free text that could not be resolved>",
  "reason": "declined_by_operator"
}
```

**Rules**:
- The call is made with `LEDGER_EVENT_TOOL`'s schema so the `event` shape is fixed and
  machine-parseable (the `capture_ledger_events_from_text` pattern, generalized).
- Its input: the conversation so far + the reply just sent + **this turn's Morning MCP tool
  calls and their results verbatim** + the constitution's "Ledger Event Recognition" section.
- On a `create_*` Morning call this turn, `event` is populated from the **real Morning
  response** in the tool-result input (FR-069-025), `source_type="חשבונית"`.
- `complete` is returned **only** when every mandatory field for `source_type` (§1) is
  present. Otherwise `none`.
- One-shot retry on a parse failure / `is_incomplete_capture` (reuses the existing
  `capture_ledger_events_from_text` retry shape).
- The output is **never** appended to the conversation, never sent to the operator, never
  logged verbatim (only the breadcrumb in §3).

---

## 3. The ledgerer — `LedgerEventManager.persist_recognized_event(...)` (NEW code path)

**Zero-AI.** Consumes the §2 output. Makes **no** OpenAI call and does **no** client /
Morning / ledger lookup (FR-069-004).

On **`complete`**:
1. Look up the message named by `verdict["trigger_message_id"]` in the session; parse its
   persisted `Message.timestamp` (an Asia/Jerusalem ISO string) →
   `event_datetime = <parsed dt>.strftime("%d/%m/%Y %H:%M")`. **Never** `now_local()`,
   **never** the recognition-call clock — this is the "hard pointer" every hardcoded
   acceptance-test expectation depends on. (Resolved 2026-09-02, option A: the Green API
   notification epoch is not persisted anywhere; the message's own processing-time ISO
   timestamp is used, differing by sub-second-to-seconds latency — immaterial at minute
   precision. No `local_from_timestamp` call on this path.)
2. `captured_at = now_local()`.
3. Mint `event_id` — source-type prefix (`A`=`הסכם`, `B`=`בנק`; `חשבונית` uses the existing
   accounting prefix) + `DDMMYY` + `HHMM` (from `event_datetime`) + a same-minute sequence
   digit — exactly as `add_ledger_events_from_call` does today.
4. For `הסכם`: mint `agreement_id` and per-component `component_id`; explode `components`
   into one `record` per component via the existing `merged_event = {**shared, **component}`
   loop (`add_ledger_events_from_call`, `ledger_event_manager.py:1173`).
5. Denormalize an already-decided `reference` id into `_linked_document` display fields from
   the in-memory index (`ledger_event_manager.py:~1060-1077`) — formatting of a linkage the
   *conversation* established, not a lookup of *whether* to link.
6. Dedup against the in-memory index; for `חשבונית`, through
   `_ensure_accounting_document_cache()` keyed on `accounting_document_display_number`
   (`ledger_event_manager.py:1163-1169`) so Feature 025's sweep treats it as a duplicate.
7. Persist the immutable JSON (`json.dump(..., sort_keys=True, ensure_ascii=False, indent=2)`
   → `.json.tmp` → `.replace()`), append to `self._index`.
8. Append the new `event_id`(s) to the **completing** message's `Message.ledger_event_ids`
   (the turn on which the event became complete — **not** `trigger_message_id`).
9. Emit the §4 "recognized" line (before persist) and "written" line (after, one per event).

On **`declined`**: emit the §4 "declined by operator" line. Persist nothing. No state to
clear.

On **`none`**: nothing. No log line (DEBUG only).

---

## 4. Ledger capture lifecycle log lines (FR-069-035)

**No module, no in-memory state, no sweep, no config.** Three INFO app-log line formats,
emitted by the ledgerer (§3) through the existing app logger; every line carries a
`now_local()` `time=` field (Israel local, offset-aware).

| Line | When | Format |
|---|---|---|
| **recognized** | recognition call returns `complete`, before persist, one per event | `[069] ledger capture recognized: type=<deposit\|agreement\|invoice> session=<id> chat=<id> time=<iso>` |
| **written** | after a successful persist, one per event | `[069] ledger event written: type=<deposit\|agreement\|invoice> event_id=<id> session=<id> chat=<id> time=<iso>` |
| **declined** | recognition call returns `declined` | `[069] ledger capture declined by operator: type=<deposit\|agreement> name=<client_name_stated!r> session=<id> reason=declined_by_operator time=<iso>` |

`type` maps `בנק`→`deposit`, `הסכם`→`agreement`, `חשבונית`→`invoice`. `session` / `chat` are
the ids already available at the ledgerer's call site.

**Abandonment = a `recognized` line with no matching `written` line for the same `session`**
(a persist failure), or a media-sourced recognition turn that produced no `recognized` line
across the detour (operator walked away). Detected operationally (log inspection), not in
code. Reliable for media-sourced captures (the recognition call runs post-turn every turn);
best-effort for typed-text captures abandoned before the event ever became complete — accepted
2026-08-31.

---

## 5. Media-ledger extraction stash — transient, not persisted, source-type- AND source-medium-aware

**Purpose**: carry every field the media extractor produced into the synthetic conversational
turn verbatim, so the model **transcribes** (never recalls) them through a multi-turn
resolution detour, and so the post-turn recognition call maps them from a clean labelled
block rather than OCR prose (FR-069-022, FR-069-045..047). Applies to `בנק` deposit slips
(US7, incl. 7d), photographed `הסכם` fee agreements (US9), and `docx` `הסכם` fee agreements
(US10).

**Lifetime**: built in `build_ledger_stash_text(...)`, embedded as text in the synthetic
turn's `text_content`, persisted only incidentally as the user-role message of that turn.
Never a dataclass on disk, never in a manager.

**Source**: the extractor's `analyze_media()` return dict — `extracted_text` (verbatim OCR
for images; python-docx paragraphs + table cells for `docx`) + `ledger_events[0]` (the arg
dict `ImageExtractor`'s classify call produced) / `document_analysis` (for `docx` — **no new
classify call is added**, per spec Assumption 8) + `fields` / `doc_type` /
`missing_required_fields`.

**Rendered shape** (Hebrew;
`build_ledger_stash_text(extracted_text, analysis, source_type, source_medium)`).
`source_type` drives field ordering; `source_medium` ∈ `{"image", "document"}` drives the
header and the "extracted text" frame-line wording. `בנק` is always `source_medium="image"`.

```text
<header — see below>

--- טקסט שחולץ מ<התמונה | המסמך> (מילה במילה) ---
<extracted_text verbatim, unmodified>

--- פרטים מובנים שחולצו ---
סוג אירוע: <בנק | הסכם>
<source-type-ordered fields — see below>
<any other non-null field from analysis, one "label: value" line each>
```

`source_medium == "image"` → `--- טקסט שחולץ מהתמונה (מילה במילה) ---`;
`source_medium == "document"` → `--- טקסט שחולץ מהמסמך (מילה במילה) ---`.

### `source_type == "בנק"` (deposit slip — always `source_medium="image"`)

- **Header**: `📸 התקבלה תמונה של אסמכתת העברה/הפקדה בנקאית.`
- **Ordered-first fields**: `תת-סוג` (הפקדה), `סכום`, `מטבע`, `תאריך הפקדה`, `מספר בנק`,
  `מספר סניף`, `מספר חשבון`, `שם על האסמכתא`, `מספר אסמכתא`.

### `source_type == "הסכם"` (fee agreement)

- **Header** (`source_medium == "image"`): `📸 התקבלה תמונה של הסכם שכר טרחה.`
- **Header** (`source_medium == "document"`): `📄 התקבל קובץ מסמך (DOCX) של הסכם שכר טרחה.`
- **Ordered-first fields**: `תת-סוג`, `שם הלקוח בהסכם`, `תאריך ההסכם`, then **every fee
  component**, one line each — percentage (`אחוז: <value> — <basis/description>`) and fixed
  (`סכום קבוע: <value> <currency> — <description>`), in the order the extractor lists them —
  plus `מע"מ` (`כן`/`לא`/`לא זוהה`), `שם המשלם` (`payer_name`) if present, and any free-text
  notes.
- **One line per fee component** — a 6-component agreement produces 6 component lines. This
  is the field FR-069-022 / US9 / US10 assert survives the detour.

**Rules (all source types)**:
- Every non-null field from `analysis` gets a line — no silent drop. The builder iterates; it
  does not hard-code a field list beyond ordering the common ones first.
- A missing/None value renders as `לא זוהה` (so the model — and the recognition call — know
  it was genuinely absent, not forgotten).
- The raw OCR / doc-text block is inserted **unmodified** — no trimming, no normalization.
- Multiple recognized events in one media item: one labelled block per event, prefixed
  `אירוע N מתוך M`, with a leading `מספר אירועים זוהו` note.

---

## 6. Config — none

This feature adds **zero** keys to any `config.*.json` and **no** `AppConfiguration` field
(`config.accounting_ledger_update_freq` — Feature 025 — is untouched; the synchronous
`חשבונית` capture has no gate). Everything in §2–§5 is always active once deployed; there is
no on/off surface.

---

## 7. What is explicitly NOT modeled

- **No feature flag** — no `config.feature_flags.*`, no OFF path.
- **No config key at all** — no `AppConfiguration` field, no `validate()` change.
- **No inline ledger tool** — `capture_ledger_event` / `LEDGER_EVENT_TOOL` /
  `record_unresolved_ledger_capture` / `LEDGER_SKIP_TOOL` do **not** exist on the main
  conversational turn. `query_ledger_events` (read/search) stays.
- **No `_call_openai_ledger_followup_api`** — deleted; the recognition call never touches the
  reply, so no second round-trip is needed.
- **No bugfix-018 MCP-suppression guard, no `>1 call` / unparseable-args protocol-violation
  machinery** — deleted; structurally unreachable without an inline capture tool.
- **No `PendingLedgerResolutionTracker` / `PendingLedgerResolutionManager`** — no in-memory
  dict, no `src/managers/` module, no `SessionCleanupThread` sweep hook. FR-069-035 is
  satisfied by the §4 log lines; resolution state is the conversation itself.
- No new `PendingApproval` subtype — the `add_client` step reuses the existing MCP
  pending-approval flow.
- No `LedgerEvent` field, no schema-version change, no `SCHEMA_VERSION_HISTORY` entry.
- No persistence for the recognition-call output or the stash.
- No change to `capture_ledger_events_from_text`'s signature — the recognition call
  generalizes its *pattern*; whether the same function is reused or a sibling is added is a
  `tasks.md` implementation detail.
- No new AI call in `DOCXExtractor` / `PDFExtractor` / `ImageExtractor` (spec Assumption 8).
