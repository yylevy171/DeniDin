# WhatsApp Export → Ledger Event Player

Replays a real WhatsApp chat export through DeniDin's real, live message
pipeline — no Green API, no live WhatsApp connectivity at any point — so
that fee-agreement/bank-deposit messages missed while DeniDin wasn't running,
or a gap that needs re-capturing, can be (re)processed exactly as if they'd
arrived live. Every dispatched message goes through the same
`AIHandler`/`MediaHandler`/`LedgerEventManager` code the real app uses; only
the *source* of notifications differs (`PlayerExportSource` instead of
`GreenAPIMessageSource` — see `contracts/message-source.md`).

Full design background: `specs/in-progress/043-production-data-setup-tooling/`
(`spec.md`, `plan.md`, `data-model.md`, `contracts/player-cli.md`).

## What's implemented today

- **Replaying a date range** (this document) — parsing a real export,
  synthesizing Green-API-shaped notifications, dispatching them through the
  live pipeline, producing real ledger events.
- **Bank/payment-detail capture** — the ledger event schema (as of Phase 11,
  2026-08-16) captures `bank_number`/`bank_branch`/`bank_account` for a בנק
  event, alongside the rest of the schema — see `data-model.md` §1b.

**Not implemented yet** (tracked in `tasks.md` as later phases — do not
assume any of the following works):
- Reconciliation (Phase 5) — no orphaned-file cleanup on a re-run yet.
- Relevancy/reference resolution (Phase 6) — a correction message's
  `reference_hint` is captured, but nothing yet auto-resolves it to the real
  prior `event_id` (`LedgerEventManager.resolve_reference` exists as a
  method, but nothing calls it in this player yet).
- Review queue / second-pass re-apply (Phase 7) — there is **no**
  `--reapply-review` flag despite it being speced in
  `contracts/player-cli.md`; that contract describes the *intended* shape,
  not current behavior.
- Note: `quickstart.md` in this feature's spec directory predates the actual
  implementation and describes a different (now-superseded) CLI shape
  (separate `--export-zip`/`--chat-id`/`--sender-map`/`--data-root` flags).
  This README describes what's actually built; treat `quickstart.md` as
  historical design intent, not a working guide.

## Invocation

```bash
cd apps/denidin-app
python3 player/run_player.py <player_config.json> \
    [--start YYYY-MM-DD] [--end YYYY-MM-DD] \
    [--confirm-production-data-root]
```

One positional argument: a player config JSON file (see below). Everything
genuinely per-invocation (date range, the production-data-root safety
confirmation) stays a CLI flag, deliberately never baked into a reusable
config file.

### Player config file

```json
{
  "export_zip": "tests/fixtures/whatsapp_exports/export.zip",
  "chat_id": "120363999999999999@g.us",
  "sender_map": {"display name": "phone@c.us"},
  "data_root": "test_data",
  "denidin_config": "config/config.test.json"
}
```

(A real example, `player_run_gviya_test.json`, lives alongside this file.)

| Field | Required | Meaning |
|---|---|---|
| `export_zip` | yes | Path to the WhatsApp export zip (chat `.txt` + media). |
| `chat_id` | yes | The chat JID every synthesized notification is attributed to. |
| `sender_map` | only if the export has >1 distinct sender | Maps each export sender **display name** (a chat export never carries phone numbers for saved contacts) to a real phone JID. A message from an unmapped sender is skipped with outcome `unmapped-sender`, never guessed. |
| `data_root` | yes | Where events/sessions/media get written. **No default anywhere in code.** |
| `denidin_config` | yes | An `AppConfiguration`-shaped JSON file (`config.test.json`/`config.dev.json`/etc.) — only its AI/OpenAI settings matter to the player; its own `data_root` is always overridden by this file's `data_root`, never used. |

`load_player_config` (`player_config.py`) raises a clear error and exits
with code `2` if the file is missing, isn't valid JSON, or is missing any of
`export_zip`/`chat_id`/`data_root`/`denidin_config`.

### `--start` / `--end`

`YYYY-MM-DD`. Clamped server-side regardless of what's passed: `--start`
never resolves earlier than `2025-09-01`; `--end` never resolves later than
today. Both default to the full allowed range when omitted.

### `--data-root` safety — `--confirm-production-data-root`

There is no `--data-root` CLI flag — `data_root` always comes from the
player config file above. But if that value resolves to the literal path
`data` (the live app's real production default), the player refuses to
start unless `--confirm-production-data-root` is **also** passed on the
command line, every single invocation — a deliberate, belt-and-suspenders
gate (`config_safety.py`) that can never be satisfied by anything baked
into a reusable file, forcing a fresh, conscious decision each time.

## What a run does

For every message in `[start, end]`, chronologically:
1. Resolve the sender via `sender_map` (skip with `unmapped-sender` if
   absent).
2. Synthesize a Green-API-shaped notification from the parsed message
   (text or attachment — unsupported attachment types are skipped with
   outcome `unsupported-type`).
3. Dispatch it through `denidin.dispatch_notification` — the exact same
   function the live app's `GreenAPIMessageSource` calls — so RBAC, session
   storage, ledger-event capture, and (for image/document messages) a
   locally-served copy of the attachment via `LocalMediaServer` all behave
   identically to a live message.

`run_replay`'s return value (and `main`'s printed summary) is one outcome
entry per message: `status` is one of `dispatched` / `unmapped-sender` /
`unsupported-type`, plus `raw_line_no` for tracing back to the export file.
There is **no** written run-summary JSON file yet (`{data_root}/events/
_runs/<run_id>/summary.json`, described in `contracts/player-cli.md`, is
part of the not-yet-built reconciliation/review-queue phases) — today's
summary is stdout only.

## Safety notes

- The player never touches Green API or live WhatsApp connectivity at any
  point (`research.md` R3) — safe to run alongside the live production app
  without risk of draining its pending notifications.
- `import denidin` at the top of a replay is safe for the same reason: the
  `MessageSource` refactor means importing `denidin.py` no longer
  constructs a live bot as an import-time side effect.
- Every run needs its own explicit human approval before executing against
  real production data — this tooling existing does not itself authorize
  any specific run (CLAUDE.md's environment-start discipline applies to
  mutating real data, same spirit even though this isn't a container
  start).
