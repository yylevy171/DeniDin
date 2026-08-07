# Implementation Plan: WhatsApp Export → Ledger Event Player

**Feature ID**: 043-production-data-setup-tooling
**Input**: spec.md, user-stories.md (both reviewed/confirmed with user),
research.md, data-model.md, contracts/

## Architecture summary

The player replays historical WhatsApp export messages through DeniDin's
real, unmodified live processing pipeline (`denidin.py`'s handler
functions → `WhatsAppHandler`/`MediaHandler` → `AIHandler` →
`LedgerEventManager`), for a `[start, end]` date range. Two structural
changes to shared/live code are required first (both small, additive,
behavior-preserving when unused); everything else is new, player-only code
under `scripts/player/`.

### Shared/live code changes (prerequisite, sequenced first — see tasks.md)

1. **`MessageSource` abstraction** (`src/sources/`, new package) — extracts
   `denidin.py`'s hardwired Green API bot construction (currently at
   module-import time, `denidin.py:80`, plus module-scope `@bot.router.
   message(...)` decorators) into `GreenAPIMessageSource`, constructed only
   from the live entry point. Handler functions become plain, undecorated
   functions; a dispatch table replaces decorator-based registration. See
   contracts/message-source.md. **Live behavior when actually run must
   verify byte-for-byte identical** — this is the highest-risk change in
   this feature precisely because it touches code the real production app
   depends on, even though it's a pure wiring refactor with no processing-
   logic changes.
2. **`ai_handler.py` timestamp fix** — `_build_instructions(constitution,
   today_timestamp: Optional[int] = None)`; `None` default preserves
   current wall-clock behavior exactly. Threaded through 4 call sites
   (886, 1531, 1599, 1665); the 1599 site
   (`capture_ledger_events_from_text`) needs the parameter threaded 4 hops
   from `MediaHandler.process_media_message`'s existing `timestamp`
   argument through `_extract_text` → `ImageExtractor.analyze_media`.
   `AIRequest.timestamp` already exists (`Optional[int]`, `src/models/
   message.py:121`) — no new dataclass field needed for the text path.
3. **`LedgerEventManager` additions** — `CURRENT_SCHEMA_VERSION` constant +
   `schema_version` field in `add_ledger_event`'s record dict;
   `resolve_replaced_event_id()`; `apply_review_answer()`. All additive,
   no existing method signature changes.

### New player code (`apps/denidin-app/scripts/player/`)

```
scripts/player/
    __init__.py
    export_parser.py       # WhatsApp export .txt + zip -> List[ParsedMessage]
    notification_synth.py  # ParsedMessage -> Green-API-shaped Notification
    export_source.py       # PlayerExportSource(MessageSource)
    media_server.py        # local static HTTP server over export media dir
    relevancy.py            # US2: deterministic replaces_hint resolution
    reconciliation.py       # US1/US4: orphan detection, to-delete moves
    review_queue.py         # US3: notes-heuristic flagging + queue I/O
    run_player.py           # CLI entry point / orchestrator
    README.md                # US6: operator documentation
```

- **`export_parser.py`**: regex `^(\d{1,2}/\d{1,2}/\d{2}), (\d{1,2}:\d{2}) -
  ([^:]+): (.*)$` for message-start lines; continuation lines joined until
  the next match. Sender-name cleanup strips `‏`/emoji-adjacent
  whitespace. Attachment lines (`^(.+) \(file attached\)$`) resolved
  against the zip's extracted media files. System-message filtering and
  caption-on-attachment-line handling: finalized once the full real sample
  is re-checked (research.md's open items) — not guessed now.
- **`notification_synth.py`**: builds the same `event_dict` shape
  `create_real_notification` (`tests/e2e_helpers.py`) already produces.
  `mimeType` inference reuses `MediaFileManager`'s own extension table
  rather than a second, possibly-inconsistent one.
- **`media_server.py`**: `LocalMediaServer` context manager, same pattern
  as the expensive tests' `HTTPServer`, OS-assigned port (`port=0`) to
  avoid fixed-port collisions on a long-running replay.
- **`relevancy.py`**: deterministic v1 matching (client_name +
  source_type=הסכם + most-recent-first + agreement_label tiebreak),
  triggered only when the model already set `replaces_hint`/
  `reference_hint`; calls `LedgerEventManager.resolve_replaced_event_id`.
- **`reconciliation.py`**: snapshots pre-run event files in `[start,end]`
  before any writes; after the run, moves (never deletes) anything not
  freshly reproduced to `_to_delete/<run_id>/`, writes manifest.
- **`review_queue.py`**: scans each captured component's `notes` field for
  a small fixed list of Hebrew ambiguity-marker phrases (e.g. "לא ברור",
  "ייתכן", "צריך לבדוק", "ספק אם" — finalized at `/tasks`); writes queue
  entries. **No changes to `LEDGER_EVENT_TOOL`'s live schema** — the
  review-queue mechanism is external accounting, not part of the ledger
  event record itself (per user's explicit rejection of a shared-schema
  signal).
- **`run_player.py`**: parses CLI args (contracts/player-cli.md), loads
  `config/config.player.json` + required `--data-root`, parses the export,
  filters/clamps the date range, starts `LocalMediaServer`, drives
  `PlayerExportSource.start(dispatch)`, runs relevancy after each message,
  runs reconciliation at the end, writes the run summary. Also implements
  `--reapply-review` mode (no export parsing, no OpenAI calls).

### Config (`config/config.player.json`, new)

Same shape as `AppConfiguration`, `data_root` deliberately absent (see
data-model.md §7). No Green API credentials needed — the player never
constructs `GreenAPIMessageSource`.

## File-by-file impact

| File | Change |
|---|---|
| `denidin.py` | Refactor: plain handler functions + dispatch table, `GreenAPIMessageSource` construction moved to live entry point |
| `src/sources/message_source.py` (new) | `MessageSource` ABC |
| `src/sources/green_api_source.py` (new) | `GreenAPIMessageSource` |
| `src/handlers/ai_handler.py` | `_build_instructions` gains `today_timestamp`; `capture_ledger_events_from_text` gains `today_timestamp`; 4 call sites updated |
| `src/handlers/media_handler.py` | Threads `today_timestamp` into `_extract_text`/`analyze_media` calls |
| `src/handlers/extractors/image_extractor.py` | `analyze_media` gains `today_timestamp` passthrough |
| `src/managers/ledger_event_manager.py` | `CURRENT_SCHEMA_VERSION`, `schema_version` field, `resolve_replaced_event_id`, `apply_review_answer` |
| `scripts/player/*` (new) | All player code, see above |
| `config/config.player.json` (new) | Player's own config |
| `tests/e2e_helpers.py` | Possibly extended/refactored if `MessageSource` changes how tests construct notifications (confirm at `/tasks`) |

## Test strategy

- **Unit** (default marker, no OpenAI/network): `export_parser.py`,
  `notification_synth.py`, `reconciliation.py`, `relevancy.py`,
  `review_queue.py`'s heuristic, `schema_version` field presence,
  `_build_instructions(today_timestamp=...)` override-vs-default
  behavior, `MessageSource`/`GreenAPIMessageSource` wiring (assert `import
  denidin` alone no longer constructs a bot — a real regression test for
  R3's fix). Fixtures: synthetic WhatsApp-export-format snippets only,
  never the real sample (per user's explicit instruction).
- **`billed`**: a small number of real, text-only end-to-end replays
  (fee-agreement statement, a correction, an ambiguous message) asserting
  historical-date-correctness (the whole point of the timestamp fix) and
  US2's relevancy linking end-to-end.
- **`expensive`**: one or two full image-path replays through
  `LocalMediaServer` + `handle_image_message`, confirming the timestamp fix
  reaches the image-classification call and produces a historically-correct
  `txn_date`.
- **Not re-tested**: text/image extraction *correctness* — already covered
  by the existing suite, the player calls that code unmodified (per spec's
  explicit "player" framing, US3-US5 dropped from user-stories.md for this
  reason).

## Verification (of this plan against spec/user-stories)

- US1 (date-range replay, reconciliation) → `run_player.py` main loop +
  `reconciliation.py`.
- US2 (relevancy linking) → `relevancy.py` +
  `resolve_replaced_event_id`.
- US3 (review queue) → `review_queue.py`, external to ledger schema.
- US4 (no orphans) → `reconciliation.py`'s snapshot/move/manifest.
- US5 (schema version) → `CURRENT_SCHEMA_VERSION` field.
- US6 (permanent, git-tracked, documented) → `scripts/player/` package +
  README.md + full test coverage above.

## Next step

`/tasks` — break this into a sequenced tasks.md (tests-first per
METHODOLOGY.md §II), starting with the `MessageSource` refactor and
timestamp fix (foundational, everything else depends on both), per the
order in this session's approved plan file.
