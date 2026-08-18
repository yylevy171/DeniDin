# Data Model: WhatsApp Export → Ledger Event Player

## 1. Ledger event record — `schema_version` addition (US5)

Extends the existing Feature 033 schema
(`specs/done/033-ledger-event-persistence/data-model.md`) with one new
DeniDin-internal (non-CSV) field:

| Field | Type | Rule |
|---|---|---|
| `schema_version` | int | `CURRENT_SCHEMA_VERSION` at write time — a module-level constant in `ledger_event_manager.py`. Bumped by hand exactly when `LEDGER_EVENT_TOOL`'s schema or `LedgerEventManager`'s field-population rules materially change, in the same commit as that change. |

Written by `LedgerEventManager.add_ledger_event` — the single shared
persistence method both live capture and the player go through, so this is
not player-specific logic, just a new constant referenced there. **Not
retro-applied** to pre-existing event files: leaving old records without
this field is itself the accurate signal "predates schema-version
tracking" — retro-applying would require guessing which historical rule
generation actually produced each old record, which is exactly the problem
this field exists to avoid solving by inference.

### 1b. Phase 11 (2026-08-16) — real-data-grounded field audit and revision

**Context**: while scoping T027 (originally: add `payment_method`/`bank_number`/
`bank_branch`/`bank_account`/`transaction_reference` to close a gap where
bugfix-028/038 added bank-detail arguments to the Morning invoicing tools but
`capture_ledger_event` never mirrored them), the user asked for every field of
the persisted record — not just the new ones — to be reviewed one by one
against the **real** historical `Events.csv` (1159 rows,
`apps/denidin-app/tests/fixtures/whatsapp_exports/Events.csv`), plus
`summary.md` (the AHLedger project's own build-heuristics retrospective,
`/Users/yaron/Projects/AHLedger/summary.md`), rather than assumptions. Several
fields turned out to duplicate each other or diverge from real usage. Every
change below was individually confirmed field-by-field, not batch-approved.

**Fields removed:**
- `message_timestamp` — fully covered by `event_datetime` (below); the raw
  epoch is still an `add_ledger_event` input parameter (drives id/datetime
  generation), just no longer persisted as its own redundant field.
- `sender` — confirmed via grep to have **zero readers anywhere in the
  codebase**; write-only since it was added, no concrete use case beyond a
  hypothetical future audit need.
- `notes` (CSV column, הערות) — its two real roles now route to whichever
  field actually matches the content: unparseable-amount/hours-value fallback
  text (this component's own content) appends onto `description`;
  AI-authored relationship reasoning ("why does this replace/relate to a
  prior event") is the AI's own job to state directly in `reference_hint`.
  Component-level tool-schema `notes` was removed the same way, merged into
  `description`.
- `replaced_event_id` (CSV) / `replaces_hint` — folded into
  `reference`/`reference_hint` (see below); no longer separate fields.
- `agreement_label` — no longer persisted as its own field (still a
  `LEDGER_EVENT_TOOL` **input**, stated once per new agreement, used to build
  `agreement_id`) — human requirement: *"I never want to see the label in the
  data except embedded in the agreement id itself."* Real-data check: no
  Events.csv column ever held this separately either (only embedded inside
  `הסכם.מזהה_הסכם`'s composite string) — always a DeniDin-only construction
  aid, never a mirrored real field. Every component still shares the
  identical `agreement_id`, computed once per call/message and never
  re-derived later (same discipline as a UUID — a later related message gets
  its own fresh `agreement_id`, cross-linked via `reference`, never by
  reconstructing this one from a re-typed label).
- `payment_method`, `transaction_reference` — added by this same phase's
  first pass (T027b), then reverted same-day: no payment-app (bit/paybox/
  paypal) support exists yet, and `payment_method` was redundant once
  `bank_number`/`bank_branch`/`bank_account`'s own presence already implies a
  bank transfer.

**Fields merged:**
- `event_date` + `event_time` (CSV) → single `event_datetime` (CSV), format
  `DD/MM/YYYY HH:MM`.
- `captured_at` reformatted to the same `DD/MM/YYYY HH:MM` convention
  (previously ISO-8601 with a timezone offset) — kept as a separate field
  from `event_datetime` (they can genuinely differ, e.g. a replayed/batched
  message processed long after it was sent).

**Fields kept, confirmed after real-data review (no change):** `session_id`,
`whatsapp_chat`, `message_id` (DeniDin's own synthetic per-message UUID, not
Green API's real `idMessage` — confirmed by reading `WhatsAppMessage.
from_notification`; still useful as a pointer into DeniDin's own session
record), `raw_message_excerpt` (no real historical precedent — Events.csv
never stored verbatim source text, only a human bookkeeper's own paraphrase;
exists specifically to let a human check the AI's `description`/`amount`
against what was actually said, a new need an AI-era pipeline has that a
trusted human bookkeeper didn't), `payer_name` (0% populated across all 1159
real rows, kept anyway — the scenario it covers, per its own tool description,
is real, just never occurred in this particular window), `component_label` +
`description` (CSV) — genuinely different jobs (short slug-feeding tag vs.
fuller free-text), not redundant.

**`reference`/`reference_hint` — unified mechanism (real-data finding):**
`reference` (CSV, הפניה) and the former `replaced_event_id` (CSV,
מזהה_אירוע_מוחלף) were assumed to be two different things (a live, prepared
"replaces" mechanism vs. a permanently-blank, deferred "loose reference" one).
Direct inspection of the real 1159-row file found this wrong: **both hold
real `event_id`(s) in practice** (`reference`: 20 rows, `replaced_event_id`: 7
rows), the only actual difference being direction — `replaced_event_id` is
one-directional (the new event names what it supersedes); `reference` was
found to be genuinely **bidirectional** in several real rows (e.g. `A11062611274`
and `A04072620298` each list the other). Folded into one field pair:
- `reference_hint` (internal) — free text covering replace/correct/cancel AND
  looser non-superseding relation, uniformly ("both are termed as
  'reference'" — human decision; no separate relationship-type field).
- `reference` (CSV) — `null`, or the literal placeholder `REFERENCE_PLACEHOLDER`
  ("צריך למצוא") when `reference_hint` is present, resolvable later via
  `LedgerEventManager.resolve_reference` (renamed from
  `resolve_replaced_event_id`). Real historical data already shows
  comma-separated multiple ids in several rows — multi-ref support exists
  informally in the historical convention already.
- **Explicitly deferred, not decided in this phase**: whether `reference`
  should also be reused for Morning-document references (not just
  ledger-to-ledger), and whether it should support genuine bidirectional/
  multi-ref linking as first-class behavior (today's placeholder mechanism is
  one-directional-by-construction — the new event points at the old one,
  the old one is never retroactively updated).

**Fields added (the original T027 gap):**

| Field | Type | Rule |
|---|---|---|
| `bank_number` | `str \| null` | direct from `capture_ledger_event`; the bank's NUMBER, never its name; `null` for `source_type=הסכם` (forced code-side) |
| `bank_branch` | `str \| null` | direct from `capture_ledger_event`; `null` for `source_type=הסכם` |
| `bank_account` | `str \| null` | direct from `capture_ledger_event`; `null` for `source_type=הסכם` |

Not mapped to an Events.csv column (unlike bugfix-028's Morning-tool
counterparts, which feed a real document) — DeniDin-internal evidence fields
only. `payment_date` was deliberately not duplicated: `txn_date` (already on
every component) already serves that role for a `בנק` event.

**`CURRENT_SCHEMA_VERSION` reset to `1`** (not incremented) — human decision:
given the breadth of this revision, today's result is treated as a new
baseline generation rather than an increment on the pre-Phase-11 shape. Safe
to reset because no real persisted file has ever carried a `schema_version`
value at all (confirmed: all 29 real files under `test_data/events/` predate
the field entirely).

**Final internal-field count**: 10 (`session_id`, `whatsapp_chat`,
`message_id`, `captured_at`, `raw_message_excerpt`, `reference_hint`,
`schema_version`, `bank_number`, `bank_branch`, `bank_account`) — down from
11 pre-Phase-11 (and briefly 16, during T027b's now-reverted first pass).
CSV-mapped field count: 27 (was 30 — `event_date`/`event_time`/`notes`/
`replaced_event_id` removed, `event_datetime` added).

See tasks.md Phase 11 (T027a/T027b, and the same-day follow-up revision) for
the full task history, and `test_ai_handler_ledger_events.py`'s
`TestLedgerEventToolBankPaymentFields` / `test_ledger_event_manager.py`'s
full suite (substantially rewritten the same day) for test coverage.

### 1c. Interactive player review follow-up (2026-08-18)

A full 33-message interactive human review of a real export (see the review
protocol in this feature's own tasks — dispatching one message at a time
through the real, unmodified pipeline, human approve/correct each capture)
surfaced 10 concrete findings against the Phase 11 shape above, all
addressed the same day:

**`raw_message_excerpt` removed entirely** (from `LEDGER_EVENT_TOOL`'s
schema AND `LedgerEventManager`'s persisted record — internal-field count
now **9**, not 10). Rationale: the ledger event's own `message_id` +
`session_id` already deterministically locate the exact source message file
on disk (`{session_id}/messages/{message_id}.json`), so duplicating the
source text into the ledger event was redundant — the "hard pointer"
requirement is now met structurally via that pointer instead of a tool-call
field the model had to author. This unblocked closing the finding that the
model never actually captured a real verbatim excerpt for image messages
(only a derived/OCR'd description) — fixing it at the source: **new
`Message.extracted_text` field** (`session_manager.py`), populated by
`MediaHandler` from the media extractor's own `extracted_text` (image/PDF/
DOCX all now genuinely return this key — PDF/DOCX previously only returned
`raw_response`, a pre-existing gap fixed as part of this). For a text
message, `Message.content` already held the verbatim text; no change needed
there.

**`trigger_condition` wired up** — previously hardcoded `null` in
`LedgerEventManager` with no schema property at all (structurally
impossible for the model to populate). Now a real `LEDGER_EVENT_TOOL`
component property, forced `null` for `בנק` (no conditional-fee concept
applies to a bank deposit) same as `component_label`.

**Code-side (not just prompt) enforcement added for two near-universal
model misses**, since tool-description guidance alone proved insufficient
against real, observed failure rates in the review:
- `payer_name` forced `null` for `בנק` events; a misplaced depositor name
  (found in `payer_name` instead of `client_name`, ~half the time in the
  real review) is rescued into `client_name` rather than discarded.
- `vat_status` forced `כולל` for every `בנק` event, unconditionally — the
  model applied this correctly only 1 of 15 times in the real review,
  despite the same principle already existing elsewhere in the constitution
  for Morning payment-reference documents.

**Constitution guidance strengthened** (`runtime_constitution.md`, no
schema/code change): checks (`שיק`) must prompt a clarifying question
rather than being silently captured as `בנק` or silently declined; material
name ambiguity (e.g. a hyphenated name) gets a concrete anchored example;
`reference_hint` guidance now explicitly covers "addition" phrasing
("תוספת") that was previously under-triggering it; hourly work-log entries'
"always capture, no exceptions" rule was made more emphatic after a real
miss; several stale `notes`-field references (dead since Phase 11 removed
that field) were corrected to `description`.

See this session's review notes (throwaway, not committed) for the full
10-finding writeup; `test_ledger_event_manager.py`'s `TestPayerNameBankHandling`/
`TestVatStatusBankDefault`/`TestTriggerConditionField` and
`test_session_manager.py`'s `TestExtractedTextStorage` for test coverage.

## 2. `MessageSource` interface (new, `src/sources/`)

A core app abstraction (not player-only), extracted from `denidin.py`'s
current hardwired Green API coupling:

```python
class MessageSource(ABC):
    """Supplies Notification-shaped objects to a dispatch callable, in
    whatever order/cadence is natural to the source. Downstream processing
    (WhatsAppMessage parsing, AIHandler, MediaHandler, LedgerEventManager)
    is 100% identical regardless of which MessageSource is active — this
    interface's only job is producing Notification objects whose `.event`
    dict has the same shape `WhatsAppMessage.from_notification` already
    parses today."""

    @abstractmethod
    def start(self, dispatch: Callable[[str, Notification], None]) -> None:
        """Begin supplying notifications. `dispatch(type_message,
        notification)` is called once per notification, synchronously, in
        the source's natural order. Returns when the source is exhausted
        (player) or blocks indefinitely (live)."""
```

**`GreenAPIMessageSource(config)`** (`src/sources/green_api_source.py`) —
today's behavior, relocated: constructs `DeniDinGreenAPIBot(
config.green_api_instance_id, config.green_api_token)` and registers the
handler dispatch table against `bot.router` — but only inside `start()`,
never at import/construction time of the module. Only ever instantiated
from `denidin.py`'s live entry point (`if __name__ == '__main__':` or
equivalent), never by tests or the player.

**Player-side source** (`player/export_source.py`,
`PlayerExportSource`) — takes the parsed, date-range-filtered, chronologically
ordered `List[ParsedMessage]` (see §4) plus a `chat_id`/sender-map, and for
each one synthesizes a `Notification` object (via `notification_synth.py`)
and calls `dispatch(type_message, notification)` directly, in order,
synchronously — no threads, no listening loop, `start()` returns once the
range is exhausted.

`denidin.py`'s handler functions (`handle_text_message`, etc.) stay plain,
undecorated functions; a small dispatch table (`type_message → handler`)
replaces the current `@bot.router.message(...)` decorators, referenced by
both `GreenAPIMessageSource.start()` (registers it against `bot.router`)
and `PlayerExportSource.start()`'s caller (calls the mapped function
directly per notification).

## 3. New `LedgerEventManager` methods (additive, no existing method changed)

```python
def resolve_replaced_event_id(self, event_id: str, resolved_target_id: str) -> bool:
    """US2: in-place field update on an already-persisted event file,
    replacing REPLACED_EVENT_PLACEHOLDER with the real prior event_id the
    relevancy step matched. Same tmp-file-then-replace pattern as
    add_ledger_event. Returns False (logs ERROR, no exception) if event_id
    doesn't exist or its replaced_event_id isn't currently the placeholder
    (never overwrites a value someone/something else already resolved)."""

def apply_review_answer(self, event_id: str, component_field_updates: Dict) -> bool:
    """US3 second pass: patches specific fields on one already-persisted
    event file per an operator's review-queue answer. Same tmp-then-replace
    pattern. Never touches unrelated events. Returns False (logs ERROR) if
    event_id doesn't exist."""
```

Both keep `LedgerEventManager` as the sole owner of the on-disk JSON format
— the player never hand-writes event JSON directly.

## 4. Player-internal types (`player/`)

```python
@dataclass
class ParsedMessage:
    timestamp: datetime          # tz-aware UTC (converted from assumed
                                  # Asia/Jerusalem export wall-clock time)
    sender_display_name: str     # emoji/RTL-mark-stripped
    text: str                    # multi-line continuations joined
    attachments: List[Path]      # resolved paths in the extracted media
                                  # dir; [] for plain text messages
    raw_line_no: int              # source line, for error messages/audit
```

## 5. Review-queue artifact (US3)

`{data_root}/events/_review_queue/<run_id>.jsonl` — one JSON object per
line:

```json
{
  "event_id": "A02022604480",
  "component_id": "0224-...-...",
  "question": "<the notes text that triggered the flag>",
  "source_type": "הסכם",
  "client_name": "...",
  "agreement_label": "...",
  "message_timestamp": "2026-08-02T09:53:00+00:00",
  "status": "open"
}
```

Second pass: operator edits a copy, flips `status` to `"answered"`, adds an
`answer` field (free-form text or structured field updates — exact shape
decided at `/tasks`, since it depends on what the notes-heuristic actually
flags in practice). `run_player.py --reapply-review <path>` reads answered
entries and calls `LedgerEventManager.apply_review_answer` per entry.

## 6. Reconciliation manifest (US1/US4)

`{data_root}/events/_to_delete/<run_id>/manifest.json`:

```json
{
  "run_id": "...",
  "range": {"start": "2025-09-01", "end": "2026-08-06"},
  "moved": [
    {"event_id": "A...", "original_path": "events/A....json",
     "reason": "not_reproduced_by_run_<run_id>_for_range_[start,end]",
     "moved_at": "2026-08-06T..."}
  ]
}
```

Each moved event file itself is relocated unchanged (not rewritten) to
`{data_root}/events/_to_delete/<run_id>/<event_id>.json`, alongside the
manifest.

## 7. Player configuration — `config/config.player.json` (new)

Same shape as `AppConfiguration` (matching `config.test.json`/
`config.dev.json`), but with **`data_root` deliberately absent** — always
supplied via the required `--data-root` CLI flag, never defaulted, per
spec's Environment/data-safety requirement. Holds AI/OpenAI settings
only — no Green API credentials are needed at all (the player never
constructs `GreenAPIMessageSource`).
