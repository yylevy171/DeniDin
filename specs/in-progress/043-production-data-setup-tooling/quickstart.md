# Quickstart: WhatsApp Export → Ledger Event Player

**Not yet implemented** — this describes the intended operator workflow
once `/tasks` and `/implement` land. Nothing in this file is runnable yet.

## Preconditions

- A WhatsApp export zip (chat `.txt` + media files) for the real production
  conversation, covering (at minimum) the date range you intend to replay.
- A `--sender-map` JSON file mapping every distinct sender display name in
  the export to a real phone JID (e.g. `{"אילה 🦋": "972501234567@c.us"}`)
  — a human-provided input, never guessed.
- `config/config.player.json` populated with real OpenAI credentials (copy
  from `config/config.example.json`'s shape).
- Explicit, separate human approval for the specific run about to happen —
  per CLAUDE.md, this is production data mutation, not authorized by this
  spec alone.

## 1. Replay a date range

```bash
cd apps/denidin-app
python3 scripts/player/run_player.py \
    --export-zip /path/to/export.zip \
    --chat-id "972501234567@c.us" \
    --sender-map /path/to/sender_map.json \
    --data-root /path/to/real/production/data \
    --start 2025-09-01 --end 2026-08-06 \
    --confirm-production-data-root
```

Produces:
- Fresh event files under `{data_root}/events/` for every qualifying
  message in range.
- `{data_root}/events/_to_delete/<run_id>/` — any stale/orphaned
  pre-existing event file in range, moved (never deleted), with a manifest.
- `{data_root}/events/_review_queue/<run_id>.jsonl` — flagged ambiguous
  captures needing a human answer.
- `{data_root}/events/_runs/<run_id>/summary.json` — full accounting of
  every processed message's outcome.

## 2. Review flagged captures

Open the review-queue `.jsonl`, answer each open entry (edit in place,
flip `status` to `"answered"`, add an `answer` field), save a copy.

## 3. Re-apply answers (second pass)

```bash
python3 scripts/player/run_player.py \
    --reapply-review /path/to/answered_queue.jsonl \
    --data-root /path/to/real/production/data
```

No OpenAI calls, no export parsing — pure local patching of the specific
flagged records.

## 4. Repairing a narrower gap

Same command as step 1, with a narrower `--start`/`--end` — this is the
same operation, not a different mode (per US1).

## Safety notes

- `--data-root` is always required, never defaulted.
- The player never touches Green API / live WhatsApp connectivity at all
  (see the `MessageSource` design in plan.md) — safe to run alongside the
  live production app without risk of draining its notifications.
- Files outside the requested `[start, end]` range are never read for
  reconciliation purposes, let alone moved or altered.
