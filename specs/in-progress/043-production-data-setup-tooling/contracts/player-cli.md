# Contract: Player CLI

## Player config file

A single positional argument, a JSON file bundling the settings that stay
constant across most runs of the same replay — everything genuinely
per-invocation (which date range, the production-data-root safety
confirmation) stays a CLI flag instead, deliberately never part of this
file (see `player/player_config.py`'s module docstring for why):

```json
{
  "export_zip": "tests/fixtures/whatsapp_exports/export.zip",
  "chat_id": "120363999999999999@g.us",
  "sender_map": {"display name": "phone@c.us"},
  "data_root": "test_data",
  "denidin_config": "config/config.test.json"
}
```

- `export_zip`, `chat_id`, `data_root`, `denidin_config`: required — the
  player refuses to start (exit 2) if any is missing.
- `sender_map`: required whenever the export contains more than one
  distinct sender display name (a chat export never carries phone numbers
  for saved contacts) — missing entries route that message to a
  `not-qualifying: unmapped-sender` outcome, never guessed. May be omitted/
  empty for a single-sender export.
- `data_root`: **no default anywhere in code.** If it resolves to the
  literal path `data` (the live production default), also requires
  `--confirm-production-data-root` on the command line — belt-and-suspenders,
  since the operator explicitly said the intent is to run this against real
  production data from the Mac (spec.md Environment/data-safety).
- `denidin_config`: an `AppConfiguration`-shaped JSON file (any of
  `config.test.json`/`config.dev.json`/a future `config.player.json` all
  work — only AI/OpenAI settings matter to the player).

## Main replay invocation

```
python3 player/run_player.py <player_config.json> \
    [--start 2025-09-01] [--end 2026-08-06] \
    [--confirm-production-data-root]
```

- `--start`/`--end`: default to `2025-09-01`/today. Clamped server-side —
  `start` can never resolve earlier than `2025-09-01`, `end` never later
  than today, regardless of what's passed. CLI-only, not in the config
  file — no reason to bake one date range into a reusable file.
- `--confirm-production-data-root`: CLI-only, not in the config file —
  it's a safety gate that must force a fresh, deliberate decision every
  single invocation; baking it into a reusable file would silently defeat
  that the first time the file got reused.
- Exit codes follow CONSTITUTION §XVI (0 = success, 2 = configuration
  error, etc. — exact non-zero codes for reconciliation-found-issues vs.
  hard failure decided at `/tasks`).

## Second-pass re-apply invocation

```
python3 player/run_player.py <player_config.json> \
    --reapply-review <path to answered review-queue .jsonl> \
    [--confirm-production-data-root]
```

- `data_root` still comes from the player config file (same file as the
  original run).
- No export parsing, no notification synthesis, no OpenAI calls — pure
  local JSON patching via `LedgerEventManager.apply_review_answer`.
- Mutually exclusive with `--start`/`--end` (a single invocation is either
  a replay or a second-pass re-apply, never both).

## Output (both modes)

- A run summary (stdout + a `{data_root}/events/_runs/<run_id>/summary.json`)
  accounting for every processed message: captured / not-qualifying /
  flagged-for-review, with event ids produced, per US1/US4's "no
  unaccounted-for messages" requirement.
