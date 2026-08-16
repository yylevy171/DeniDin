# Data Model: WhatsApp Export → Ledger Event Player

## 1. Ledger event record — `schema_version` addition (US5)

Extends the existing Feature 033 schema
(`specs/done/033-ledger-event-persistence/data-model.md`) with one new
DeniDin-internal (non-CSV) field, the 11th such field:

| Field | Type | Rule |
|---|---|---|
| `schema_version` | int | `CURRENT_SCHEMA_VERSION` at write time — a module-level constant in `ledger_event_manager.py`, starting at `1`. Bumped by hand exactly when `LEDGER_EVENT_TOOL`'s schema or `LedgerEventManager`'s field-population rules materially change, in the same commit as that change. |

Written by `LedgerEventManager.add_ledger_event` — the single shared
persistence method both live capture and the player go through, so this is
not player-specific logic, just a new constant referenced there. **Not
retro-applied** to pre-existing event files: leaving old records without
this field is itself the accurate signal "predates schema-version
tracking" — retro-applying would require guessing which historical rule
generation actually produced each old record, which is exactly the problem
this field exists to avoid solving by inference.

`replaced_event_id` — no schema change, but a new **write path**: today
this field is only ever `null` or the literal placeholder
`REPLACED_EVENT_PLACEHOLDER` ("צריך למצוא"). The player's relevancy step
(US2) may now overwrite that placeholder with a real resolved `event_id`,
via a new manager method (see §3).

### 1b. `CURRENT_SCHEMA_VERSION` v2 — bank/payment-detail fields (Phase 11, implemented 2026-08-16)

Five more DeniDin-internal (non-CSV, same category as `replaces_hint`/
`reference_hint`/`agreement_label`) fields, mirroring the argument names
bugfix-028/038 added to the Morning invoicing tools for the identical
underlying deposit screenshot — closing the gap where the ledger's own בנק
capture had no way to state where the money came from:

| Field | Type | Rule |
|---|---|---|
| `payment_method` | `str \| null` | direct from `capture_ledger_event`; `null` for `source_type=הסכם` (forced code-side, regardless of what the caller/AI passed — same discipline as `agreement_label` being forced null for `בנק`) |
| `bank_number` | `str \| null` | direct from `capture_ledger_event`; the bank's NUMBER, never its name; `null` for `source_type=הסכם` |
| `bank_branch` | `str \| null` | direct from `capture_ledger_event`; `null` for `source_type=הסכם` |
| `bank_account` | `str \| null` | direct from `capture_ledger_event`; `null` for `source_type=הסכם` |
| `transaction_reference` | `str \| null` | direct from `capture_ledger_event` (the אסמכתה on a bit/paybox/paypal payment); `null` for `source_type=הסכם` |

Not mapped to an Events.csv column (unlike `bugfix-028`'s Morning-tool
counterparts, which feed a real document) — these are DeniDin-internal
evidence fields only, same status as `agreement_label`. `payment_date` was
deliberately NOT duplicated here: `txn_date` (already on every component)
already serves that role for a `בנק` event. `CURRENT_SCHEMA_VERSION` is `2`
as of this addition. See tasks.md Phase 11 (T027a/T027b) for the full gap
writeup and test coverage (`TestLedgerEventToolBankPaymentFields` in
`test_ai_handler_ledger_events.py`, `TestBankPaymentDetailFields` in
`test_ledger_event_manager.py`).

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
