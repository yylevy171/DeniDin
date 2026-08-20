# Phase 1 Data Model: Ledger Event Persistence

**Feature**: 033-ledger-event-persistence · **Date**: 2026-07-29

## Entity: `LedgerEvent`

Persisted as `data/events/{event_id}.json`. One file = one event = one fee-component
(a multi-component message produces multiple `LedgerEvent` files, never one combined
file). Keys alphabetized on disk (CONSTITUTION §XV: `json.dump(..., sort_keys=True,
ensure_ascii=False, indent=2)`).

### CSV-mapped fields (all 30 — 29 original + `תאריך_ביצוע` added 2026-07-30 — matching `data/events/Events.csv` exactly, column-for-column, plus the one genuinely new column not yet in the real downstream file)

| Field (code, snake_case) | CSV column (Hebrew) | Type | Population rule (this feature) |
|---|---|---|---|
| `event_id` | מזהה_אירוע | `str` | code-generated: `{A/B}{DDMMYY}{HHMM local}{seq 0-9}` |
| `event_date` | תאריך_אירוע | `str` (`DD/MM/YYYY`) | code-derived, Asia/Jerusalem local, from `message_timestamp` |
| `event_time` | שעת_אירוע | `str` (`HH:MM`) | code-derived, local, from `message_timestamp` |
| `source_type` | מקור | `str` (`הסכם`\|`בנק`) | direct from `capture_ledger_event` |
| `event_subtype` | סוג_אירוע | `str` | direct from `capture_ledger_event` |
| `client_name` | שם | `str \| null` | direct from `capture_ledger_event` |
| `payer_name` | שם_משלם | `str \| null` | direct from `capture_ledger_event` |
| `description` | תיאור | `str \| null` | direct from `capture_ledger_event` |
| `amount` | סכום | `int \| null` | code-normalized: strip `₪`/`ש"ח`/commas, round to signed int; `null` + logged WARNING if unparseable |
| `replaced_event_id` | מזהה_אירוע_מוחלף | `str` (`"צריך למצוא"`) `\| null` | `"צריך למצוא"` iff `replaces_hint` present, else blank/null |
| `reference` | הפניה | `null` (always) | **blank always** — see spec.md Clarifications |
| `notes` | הערות | `str \| null` | direct from `capture_ledger_event` |
| `agreement_id` | הסכם.מזהה_הסכם | `str \| null` | (revised 2026-07-30) code-generated: `"{MMYY}-{slugify(client_name)}-{slugify(agreement_label)}"`, `null` for `source_type=בנק`; identical across all components of one multi-component capture |
| `component_id` | הסכם.מזהה_רכיב | `str \| null` | (revised 2026-07-30) code-generated: `"{agreement_id}-{slugify(component_label)}"`, `null` for `source_type=בנק` |
| `component_label` | הסכם.רכיב | `str \| null` | (revised 2026-07-30) direct from `capture_ledger_event`'s new `component_label` field, `null` for `source_type=בנק` |
| `trigger_condition` | הסכם.תנאי_הפעלה | `null` (always, this feature) | reserved — nuances feature |
| `percent` | הסכם.אחוז | `str \| null` | direct from `capture_ledger_event` |
| `percent_base` | הסכם.בסיס_לאחוז | `str \| null` | direct from `capture_ledger_event` |
| `hours` | הסכם.שעות | `float \| null` | (revised 2026-08-02, REQ-DATA-009) code-normalized from `capture_ledger_event`'s AI-reported verbatim text (a digit string or a common Hebrew hour-count word like "שעתיים"/"שעה וחצי") to a number, same "AI reports verbatim, code converts" discipline as `amount`; `null` + logged WARNING (original text preserved in `notes`) if the text doesn't match a known numeric or word form - never guessed. |
| `hourly_rate` | הסכם.תעריף_שעתי | `str \| null` | direct from `capture_ledger_event` |
| `txn_date` | תאריך_ביצוע | `str \| null` | (added 2026-07-30, REQ-DATA-005/007 — unified 2026-07-30 from what were briefly two separate fields, `hours_date`/`transaction_date`, into one) code-normalized to `DD/MM/YYYY` from `capture_ledger_event`'s AI-resolved ISO-8601 `txn_date`. Two populating cases: for an hourly work-log component, required non-null whenever `hours` is non-null (the actual date the hours were worked, e.g. "אתמול"/"היום" resolved via the AI's injected current-date context); for a `source_type=בנק` component, always optional — populated only when the screenshot itself states an explicit transaction/value date distinct from other dates on screen. `null` + logged WARNING if required-but-missing or stated-but-unparseable. Distinct from both `event_date` (derived from the real message timestamp, the hard pointer) and `message_timestamp` itself — never a substitute for either. |
| `vat_status` | הסכם.סטטוס_מעמ | `str` | direct from `capture_ledger_event` |
| `split_partner` | הסכם.שותף_לחלוקה | `null` (always, this feature) | reserved — nuances feature |
| `split_percent` | הסכם.אחוז_חלוקה | `null` (always, this feature) | reserved — nuances feature |
| `due_date` | הסכם.תאריך_יעד | `null` (always, this feature) | reserved — nuances feature |
| `invoice_status` | חשבונית.סטטוס_מסמך | `null` (always, this feature) | reserved — future Morning-reconciliation feature |
| `invoice_number` | חשבונית.מספר_מסמך | `null` (always, this feature) | reserved — " |
| `invoice_type` | חשבונית.סוג_מסמך | `null` (always, this feature) | reserved — " |
| `morning_document_id` | חשבונית.מזהה_מסמך_מורנינג | `null` (always, this feature) | reserved — " |
| `invoice_actual_creation_date` | חשבונית.תאריך_יצירה_בפועל | `null` (always, this feature) | reserved — " |

### DeniDin-internal fields (not `Events.csv` columns — traceability/evidence, kept alongside)

| Field | Type | Purpose |
|---|---|---|
| `session_id` | `str` | source session — no longer implied by folder nesting, since events live outside `sessions/` |
| `whatsapp_chat` | `str` | source chat JID, same convention as `Session.whatsapp_chat` (`...@c.us`/`...@g.us`) |
| `message_id` | `str` | source message id (NEW — closes the traceability gap; revised 2026-07-30, populated for all events including the 6 migrated legacy ones, recovered from the session's own `messages/*.json`) |
| `message_timestamp` | `str` (ISO8601 UTC) | full source-message timestamp, the "hard pointer"; `event_date`/`event_time` are a local-time derivation of this, not a replacement |
| `sender` | `str` | source message sender JID, same convention as above |
| `captured_at` | `str` (ISO8601 UTC) | when DeniDin captured it |
| `raw_message_excerpt` | `str` | verbatim source text/image description (existing tool field) |
| `agreement_label` | `str \| null` | (added 2026-07-30) short human-readable Hebrew label for the whole matter/agreement, from `capture_ledger_event`'s new field — not itself a CSV column; used to build `agreement_id` and kept alongside it for evidence, same pattern as `replaces_hint`/`reference_hint` |
| `replaces_hint` | `str \| null` | free-text hint (existing tool field), kept alongside the resolved-or-placeholder `replaced_event_id` |
| `reference_hint` | `str \| null` | free-text hint (existing tool field), kept alongside the always-blank `reference` |

**Validation rules**: `event_id` MUST be unique across all files in `data/events/`
(enforced by construction — see `contracts/ledger-event-manager.md`). `amount`, when
non-null, MUST be an integer (no decimals — CSV convention rounds to whole NIS).
`source_type` MUST be one of `הסכם`/`בנק` (matches `LEDGER_EVENT_TOOL`'s existing enum).
(Added 2026-07-30) `agreement_id`/`component_id` MUST be non-null iff `source_type=הסכם`,
always null iff `source_type=בנק`. All components of one multi-component capture MUST share
byte-for-byte the same `agreement_id`. (Added 2026-07-30, unified same day) `txn_date` MUST
be non-null whenever `hours` is non-null (format `DD/MM/YYYY`); for a `source_type=בנק`
component it is always optional regardless of any other field's value — populated only when
the AI judges the screenshot states its own explicit transaction/value date. It is possible
for `hours` to be null and `txn_date` to still be non-null (the בנק case) — the two
conditions aren't mutually exclusive, they're just two different reasons the same field gets
populated. (Added 2026-08-02, REQ-DATA-009) `hours`, when non-null, MUST be numeric
(`int`/`float`, never a raw word/string) — code-normalized the same way `amount` is, from a
bounded Hebrew number-word dictionary plus digit parsing; unparseable input is blank +
WARNING, original text preserved in `notes`, never guessed. The `hours is not None` check
used for `txn_date`'s requiredness above is evaluated on the AI's raw `hours` text, before
normalization — an hours entry that failed to normalize still needs its `txn_date`.

(Added 2026-07-30, summary.md-derived enhancement) `event_subtype` MUST be one of `יצירה`/
`עדכון`/`ביטול`/`אישור-מימוש` (for `source_type=הסכם`) or `הפקדה` (for `source_type=בנק`) —
DeniDin's equivalent of a create/amend/cancel/confirm event-type classification. This field is
**classification only**: regardless of its value, `add_ledger_event`/`add_ledger_events_from_call`
perform the identical append-only write (a new, independent, immutable file) — an `עדכון`/`ביטול`
never patches, merges into, or removes a prior `LedgerEvent` file. Resolving an `עדכון`/`ביטול`
against the specific prior record it targets (i.e. acting on `event_subtype` differently per
value) is out of scope for this feature; today "we only support create" at the storage layer,
by design — `event_subtype` is captured now so a future reconciliation feature has the signal
already on file rather than needing a schema migration to add it retroactively.

(Added 2026-08-02, REQ-DATA-008) `capture_ledger_event`'s `component_count` field is
**validation-only** — popped by `add_ledger_events_from_call` before merging into this
entity's shape, never itself a persisted field. A `LedgerEvent` CAN legitimately have every
component-level field (`amount`, `description`, `component_label`, `percent`, `hours`,
`txn_date`, etc.) `null` at once — this is the fallback shape `add_ledger_events_from_call`
persists when the AI's `components` array came back empty even after a retry, always
distinguishable from a normal record by its `notes` value: `"AI capture returned zero
components (even after a retry) - needs manual review against the original message/image."`
Still gets a real `agreement_id`/`component_id` when `source_type=הסכם` (computed from the
call's own `client_name`/`agreement_label`, same as any other component) so it's traceable
and groupable alongside any siblings, even though this particular record carries no
substantive content of its own.

## Entity: `Message` (existing, `session_manager.py`, extended)

New field: `ledger_event_ids: List[str] = field(default_factory=list)` — the `event_id`(s)
of any `LedgerEvent`(s) captured from this specific message. Empty list for the vast
majority of messages (most messages capture nothing). Populated at message-creation time,
never patched in after the fact (see `contracts/`).

## Entity: `Session` (existing, `session_manager.py`, reduced)

`pending_ledger_events: List[Dict] = field(default_factory=list)` field **removed**.
`Session` no longer has any ledger-event-related field — `LedgerEventManager` is the sole
owner of ledger-event state, independent of any session's lifecycle.

## Appendix: Migration source data (US4, REQ-MIGRATE-001)

Verbatim source of `dev_data/sessions/4454746c-350a-4fa7-a5ef-fda2c685b0d5/session.json`'s
3 combined `pending_ledger_events` records, for `scripts/migrate_stray_ledger_events.py`
(T014b) and its test fixture (T014a) to use directly — copied here so it isn't only
findable by re-reading a dev-only data file.

**Record 1 → splits into 3 components** (client גיליאן דוידיאן, `message_timestamp`
`2026-07-28T11:06:58+00:00`, `sender`/`whatsapp_chat` `972522968679@c.us`,
`source_type=הסכם`, `event_subtype=יצירה`, `reference_hint="משרד הרווחה"`,
`vat_status="לא צוין"`, `replaces_hint=null`):

```text
raw_message_excerpt (shared verbatim by all 3 split components):
גיליאן דוידיאן
משרד הרווחה

1. אם יהיה שימוע להשעיה - 8,000₪
2. ⁠למידת תיק החקירה וניהול משא ומתן מול התביעה בניסיון להגיע לסדר טיעון - 20,000₪
3. ⁠אם המשא ימתן יכשל ונאלץ לנהל הוכחות ימשפט שלום - עוד 30,000₪
```

Component split (per this feature's design conversation, already approved). Source message
found in `dev_data/sessions/4454746c-350a-4fa7-a5ef-fda2c685b0d5/messages/`, matched by
verbatim content: `fc384625-f765-4585-a792-b5de2b44a3d0` (2026-07-28T11:07:08 UTC — the
message-store timestamp always lands a few seconds after `message_timestamp`, which is the
original webhook receipt time; content match is exact and unambiguous). All 3 components
share `agreement_label="משרד הרווחה"` (added 2026-07-30):
1. `description="שימוע להשעיה"`, `amount="8,000₪"` → normalized `8000`,
   `component_label="שימוע להשעיה"`
2. `description="לימוד תיק החקירה וניהול משא ומתן מול התביעה בניסיון להגיע לסדר טיעון"`,
   `amount="20,000₪"` → normalized `20000`, `component_label="הסדר טיעון"`
3. `description="ניהול הוכחות בבית משפט שלום, במקרה שהמשא ומתן להסדר טיעון ייכשל"`,
   `amount="30,000₪"` (from "עוד 30,000₪") → normalized `30000`,
   `component_label="הוכחות בבית משפט שלום"`

**Record 2 → splits into 2 components** (client `עו"ד שרית יוגב ועו"ד מרדכי רצבגר`,
`message_timestamp` `2026-07-28T11:23:22+00:00`, same sender/chat,
`source_type=הסכם`, `event_subtype=יצירה`,
`reference_hint` = the עו"ד אילה הוניגמן contact-info text from the original capture,
`vat_status="כולל"`, `replaces_hint=null`). Source message: `b3a2afb0-86d4-4dc7-a98b-094d34682406`
(2026-07-28T11:23:50 UTC — `[image sent]`, assistant reply confirms the extracted fee-proposal
text matches). Both components share `agreement_label="שירות המילואים"` (added 2026-07-30):

Component split:
1. `description="כתיבת מכתב"`, `amount="1,500 ש\"ח"` → normalized `1500`,
   `component_label="כתיבת מכתב"`
2. `description="הגשת כתב תביעה והישיבה בבית הדין"`, `amount="10,000 ש\"ח"` → normalized `10000`,
   `component_label="כתב תביעה"`

**Record 3 → stays a single event, no split** (client `מלכה בן סעדון לירון עו"ד`,
`message_timestamp` `2026-07-28T11:26:44+00:00`, same sender/chat, `source_type=בנק`,
`event_subtype=הפקדה`, `amount="₪12,500.00"` → normalized `12500`,
`reference_hint=null`, `replaces_hint=null` — not `הסכם`, so no agreement/component
concept applies at all — `agreement_id`/`component_id`/`agreement_label`/`component_label`
all stay `null`). Source message: `6a6fd63f-696a-43c4-93b0-6f63178d0a64`
(2026-07-28T11:26:54 UTC — `[image sent]`, assistant reply confirms the extracted bank-transfer
text matches).

(Revised 2026-07-30 — supersedes the line below) All 6 resulting `LedgerEvent`s get their
real source `message_id` (found above, not `None`); the 3 source message files also get
`ledger_event_ids` populated with the resulting `event_id`(s). All get the full source
`session_id`/`whatsapp_chat` from the parent session. The migration script's `notes` text
for the 2 split records MUST NOT include process/meta commentary about the migration itself
(e.g. "Feature 033", "בעת המעבר לאחסון קבצים נפרדים") — `notes` is real business content a
human reviewer reads, not an engineering changelog; only the substantive ambiguity note
(e.g. which stage's fee is cumulative vs. conditional) belongs there.
