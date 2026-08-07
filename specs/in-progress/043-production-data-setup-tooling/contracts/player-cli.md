# Contract: Player CLI

## Main replay invocation

```
python3 scripts/player/run_player.py \
    --export-zip <path to WhatsApp export zip> \
    --chat-id <the real chat's JID or a stable player-assigned id> \
    --sender-map <path to {"display name": "phone@c.us"} JSON> \
    --data-root <path to the target events/sessions/media root> \
    [--start 2025-09-01] [--end 2026-08-06] \
    [--config config/config.player.json]
```

- `--data-root`: **required, no default anywhere in code.** Refuses to
  start if omitted. If it resolves to the literal path `data` (the live
  production default), also requires `--confirm-production-data-root` —
  belt-and-suspenders, since the operator explicitly said the intent is to
  run this against real production data from the Mac (spec.md
  Environment/data-safety).
- `--start`/`--end`: default to `2025-09-01`/today. Clamped server-side —
  `start` can never resolve earlier than `2025-09-01`, `end` never later
  than today, regardless of what's passed.
- `--sender-map`: required whenever the export contains more than one
  distinct sender display name (a chat export never carries phone numbers
  for saved contacts) — missing entries route that message to a
  `not-qualifying: unmapped-sender` outcome, never guessed.
- `--chat-id`: required, no default — the operator identifies which real
  production chat this export came from.
- Exit codes follow CONSTITUTION §XVI (0 = success, 2 = configuration
  error, etc. — exact non-zero codes for reconciliation-found-issues vs.
  hard failure decided at `/tasks`).

## Second-pass re-apply invocation

```
python3 scripts/player/run_player.py \
    --reapply-review <path to answered review-queue .jsonl> \
    --data-root <same data root as the original run> \
    [--config config/config.player.json]
```

- No export parsing, no notification synthesis, no OpenAI calls — pure
  local JSON patching via `LedgerEventManager.apply_review_answer`.
- Mutually exclusive with `--export-zip`/`--start`/`--end` (a single
  invocation is either a replay or a second-pass re-apply, never both).

## Output (both modes)

- A run summary (stdout + a `{data_root}/events/_runs/<run_id>/summary.json`)
  accounting for every processed message: captured / not-qualifying /
  flagged-for-review, with event ids produced, per US1/US4's "no
  unaccounted-for messages" requirement.
