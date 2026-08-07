# Research: WhatsApp Export → Ledger Event Player

Findings from this session's investigation (3 parallel Explore agents, 1
Plan-agent design pass, targeted verification reads, and a real sample
export file). Written as decision records — conclusion + rationale + what
was actually checked, per CONSTITUTION's "no unverified third-party
assumptions" discipline (extended here to internal code behavior too:
verify by reading, don't guess from memory of "how it should work").

## R1 — WhatsApp export text format (confirmed against a real sample)

Sample: `/Users/yaron/Projects/AHLedger/5.8.26 גבייה/WhatsApp Chat with $$
גבייה אילה $$.txt` (read in full, 65 lines, single-sender excerpt).

```
M/D/YY, H:MM - SenderName: message text
(continuation lines, no timestamp prefix, until the next
 "M/D/YY, H:MM - Name:" line)
M/D/YY, H:MM - SenderName: FILENAME.jpg (file attached)
```

Confirmed quirks:
- Sender names may contain emoji ("אילה 🦋") and Unicode RTL marks (U+200F,
  `‏`) — both need stripping/normalizing before use as a display name or
  sender-map lookup key.
- Multi-line messages have no per-line timestamp; a line is a continuation
  iff it doesn't match the `M/D/YY, H:MM - Name:` prefix regex.
- Media messages are a line whose content is exactly `FILENAME (file
  attached)`, filename matching a real file physically present in the
  export's media folder.
- Some timestamp lines have empty content (`8/3/26, 14:41 - אילה 🦋: `)
  immediately followed by several image-attachment lines at the identical
  timestamp — a multi-image send. These are NOT single WhatsApp
  notification events server-side; Green API delivers each image as its
  own separate webhook. The parser must therefore **not** merge them —
  each attachment line becomes its own `ParsedMessage`, matching what live
  processing would have seen.
- No explicit timezone is present in the export; WhatsApp exports use the
  exporting device's local wall-clock time. **Decision**: treat export
  timestamps as Asia/Jerusalem local time and convert to UTC, matching
  `LedgerEventManager`'s own existing `ISRAEL_TZ` convention
  (`ledger_event_manager.py:29`) — this needs confirming against the real
  full export (only a 65-line excerpt was read) before implementation, not
  assumed to hold for every line.

**T002 re-check (addendum, this session)**: re-grepped the same sample
specifically for system-message markers (`encrypted`, `created group`,
`added`, `changed the`, `left`, `removed`, `security code`, `missed
voice/video`, `<Media omitted>`, `joined using`) and for any attachment
line carrying trailing text after `(file attached)` — **zero matches for
either**, confirming the earlier read: this 65-line sample contains no
system-message lines and no attachment-line captions at all.

**Still not fully resolved — this sample is not sufficient proof for the
real full export**: it's an 11-day, single-sender excerpt, not "the full
history from the beginning of time" the real production export will be.
WhatsApp inserts a standard opening notice ("Messages and calls are
end-to-end encrypted...") into essentially every real export, which this
short excerpt (evidently a mid-conversation slice, not from message 1)
simply doesn't include. **Decision for `/tasks` T009a/T009b**: implement
`export_parser.py`'s system-message filter defensively against a small,
documented, known-template list (the standard encryption notice, group-
membership-change notices, `<Media omitted>`) rather than assuming none
exist — a filter that never fires is harmless; skipping the filter
entirely and hitting an unexpected line in the real export is not. Treat
the filter list as best-effort/extendable, not exhaustively verified,
until the actual real full export is run through the parser once.
Attachment-line captions: no evidence found in either read; parser should
still handle the case defensively (capture any trailing text after
`(file attached)` as a caption if present, empty string otherwise) rather
than assuming the format can never include one.

## R2 — The "same pipeline as live" architecture

Confirmed via `tests/expensive/test_ledger_event_capture_e2e.py`,
`tests/billed/test_ledger_event_capture_text_billed.py`, and
`tests/e2e_helpers.py`: the established, already-working pattern for
driving one message through DeniDin's real pipeline without a live webhook
is to build a synthetic Green-API-shaped `Notification` object
(`create_real_notification`, `tests/e2e_helpers.py:18-44` — a real SDK
`Notification` via `Notification.__new__`, with only `.answer()`
monkeypatched to capture outgoing text instead of hitting Green API) and
call `denidin.py`'s handler functions (`handle_text_message`,
`handle_image_message`, `handle_document_message`) directly. Everything
downstream (`WhatsAppMessage` parsing, `AIHandler`, `SessionManager`,
`LedgerEventManager`, real OpenAI calls) runs completely unmodified. This
is the pattern the player replicates — not a reimplementation of any
extraction/classification logic, per spec.md's explicit "player" framing.

For image/document messages, `MediaHandler` fetches the file over HTTP via
`downloadUrl` — the expensive tests spin up a local `HTTPServer` serving
fixture files (`test_ledger_event_capture_e2e.py:78-97`); the player needs
an equivalent local static file server over the export's extracted media
folder.

`WhatsAppMessage.from_notification` (`src/models/message.py:47-107`)
generates its own `message_id` as a fresh UUID (`message.py:91`) — **Green
API's own `idMessage` is never read anywhere in `src/`** (confirmed by
repo-wide grep). This means a fabricated `idMessage` in a synthesized
notification is harmless/unused; the real per-message identity downstream
is whatever UUID gets generated at parse time.

## R3 — The `MessageSource` finding (session's major architectural pivot)

Original assumption (Plan-agent draft): guard against `denidin.py`'s
module-level Green API bot construction with a preflight credential check.
User's actual direction, given the player never needs live WhatsApp
connectivity at all: **structurally eliminate the risk** by abstracting the
input source into an interface with two implementations, rather than
merely detecting a dangerous configuration at runtime.

Confirmed root cause (`denidin.py`, read directly):
- Line 80: `bot = DeniDinGreenAPIBot(config.green_api_instance_id,
  config.green_api_token)` — module-level, unconditional. Its constructor
  drains pending notifications from the real configured Green API instance
  as a side effect (`src/utils/green_api_bot.py`).
- Every `handle_*_message` function (lines ~491 onward) is decorated
  `@bot.router.message(type_message=...)` at module definition time,
  requiring `bot` to already exist as a module-level name — this is what
  forces line 80 to run unconditionally on `import denidin`.
- `config/config.json` (the path `denidin.py:33`'s `CONFIG_PATH` always
  loads) is gitignored and **not a fixed convention** — confirmed via `git
  check-ignore`/`git ls-files`: in this clone it currently happens to be a
  symlink to `config.test.json`, but nothing in the codebase or CONSTITUTION
  guarantees that; it's whatever a developer set up locally. So a
  preflight "does config.json look like prod" check would be checking an
  arbitrary, unowned signal — a structural fix is stronger than a runtime
  guard here.

Decision: extract `MessageSource` (new `src/sources/` package — this is now
a core app concern, not player-only tooling) with `GreenAPIMessageSource`
(today's behavior, but constructed only when live listening actually
starts, never at import) and a player-side source. See data-model.md for
the interface shape and plan.md for the `denidin.py` refactor.

## R4 — Player timestamp audit (full results)

Full audit of every `datetime.now(...)`/`time.time()` usage in the live
message/ledger-capture path, and whether it's a historical fact (must use
the message's own timestamp when replayed) or genuine write-time bookkeeping
(correctly wall-clock even during replay):

| File:Line | Used for | Historical fact or bookkeeping? | Correct today? |
|---|---|---|---|
| `ai_handler.py:838` (`_build_instructions`) | "THE CURRENT DATE IS {today}" injected into every ledger-capable call's instructions, used by the model to resolve relative dates into `txn_date` etc. | **Historical fact** — must reflect the replayed message's own date | **NO — the one real bug.** Wall-clock always, no parameter exists to override it |
| `ai_handler.py:1319` (`PendingApproval.created_at`) | When an MCP approval-pending state was created in-process | Bookkeeping | Correct as-is |
| `ai_handler.py:1447`, `:1821` (`AIResponse.timestamp`) | When the assistant's reply was generated | Bookkeeping | Correct as-is |
| `ledger_event_manager.py:270/376` (`captured_at`) | When the ledger record was written to disk | Bookkeeping (genuinely "now" even during a replay run) | Correct as-is |
| `ledger_event_manager.py:_resolve_local_dt` (`event_date`/`event_time`/`agreement_id` MMYY) | The event's own date/time, and agreement id | Historical fact | **Already correct** — derives from the passed-in `message_timestamp`; wall-clock only as a documented, logged fallback when `message_timestamp is None` |
| `session_manager.py` (`Session.created_at`/`last_active`, expiry cutoffs) | Session bookkeeping / real elapsed-time expiry sweeps | Bookkeeping | Correct as-is; not part of ledger-date resolution (ledger events use `message_timestamp` threaded explicitly through call args, never the session-stored copy) |
| `media_handler.py:202` (`event_timestamp` fallback) | Ledger event's message_timestamp when the real webhook timestamp is unavailable | Historical fact | **Already correct** — real `timestamp` argument used whenever present (previously fixed, per the surrounding code comment referencing a real 2026-07-28 incident); wall-clock only as a documented fallback |
| `models/message.py:88` (`WhatsAppMessage.timestamp` origin) | The single origin point everything above ultimately traces back to | Historical fact | **Correct AND load-bearing for the player**: real notification `event['timestamp']` used whenever present, wall-clock only if the key is missing entirely. The player's correctness hinges on always populating `timestamp` in every synthesized notification — this is not new code to fix, it's an existing contract the player must honor |
| `models/message.py:94` (`received_timestamp`) | Stored but never read anywhere else in the codebase (confirmed by grep) | Dead weight | Harmless either way |

**Conclusion**: exactly one real fix needed (`ai_handler.py:838` and its
4 call sites) — see plan.md. Everything else in the ledger-capture path is
already historically-correct by construction, given the player always
populates a real historical `timestamp` in every synthesized notification.

## R5 — Ledger event schema (Feature 033, authoritative)

Full field-by-field schema already documented at
`specs/done/033-ledger-event-persistence/data-model.md`: 30 CSV-mapped
fields (matching `Events.csv` column-for-column) + 8 DeniDin-internal
fields (`session_id`, `whatsapp_chat`, `message_id`, `message_timestamp`,
`sender`, `captured_at`, `raw_message_excerpt`, `agreement_label`,
`replaces_hint`, `reference_hint` — that's actually 10, not 8; corrected
count here). This feature adds one more internal field, `schema_version`
(R-decision in data-model.md), making 11.

## R6 — No existing WhatsApp export parser anywhere in the repo

Confirmed via broad grep (`WhatsApp Chat with`, `chat_export`, `chat
export`, `whatsapp.*\.txt`, `parse.*whatsapp.*export`, `import.*whatsapp.*
chat`) across both `apps/denidin-app` and `apps/morning-mcp-app` — nothing
relevant. This piece is greenfield.

## R7 — Existing one-off migration script (style reference only)

`scripts/migrate_stray_ledger_events.py` calls `LedgerEventManager`
directly (not via the live pipeline) to hand-migrate 3 specific historical
records. Useful only as a style/structure reference (argparse, `--dry-run`,
`sys.path` setup for importing `src.*` from `scripts/`) — **not** the
architecture to copy for the player's main replay loop, since the whole
point of the player is running messages through the *real* live pipeline
(R2), not reimplementing persistence calls by hand.
