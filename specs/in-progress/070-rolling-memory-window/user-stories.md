# User Stories: Rolling 14-Day Short-Term Memory Window with Nightly Daily-Summary Roll

**Feature**: 070-rolling-memory-window
**Companion to**: `spec.md` (authoritative requirements), `checklists/requirements.md`
**Format**: Given-When-Then. Each story names the concrete system flow (webhook → router →
handler → manager → store) and its integration-test requirement, per METHODOLOGY.md §I and
CONSTITUTION.md §V.

> **Priority key**: P1 = the coherent new memory model (US1-US3), shipped together. P2 = one-time
> operational tasks, each separately gated (US4 migration, US5 log-retention verification).

> **Legacy defects are not their own stories.** bugfix-035 H1/H2/H3 and bugfix-044 are each either
> *structurally eliminated* by the new architecture or *fixed inline* as the new code touches that
> path, and each is proven by a named scenario below — see `spec.md` §"Legacy Defects and How the
> New Model Addresses Them". This feature does **not** open Bug-Driven Development root-cause
> approval gates for them (user direction, 2026-09-01: "I don't want to waste time fixing
> something that is then going to be obsolete anyway").

---

## System context (applies to every story)

Inbound WhatsApp message flow (unchanged by this feature except where noted):

```
Green API webhook
  → denidin.py  HANDLER_REGISTRY / dispatch_notification  (type_message routing)
  → WhatsAppHandler.handle_* (parse → WhatsAppMessage)
  → [group only] GroupMembershipResolver (most-permissive member's role)
  → UserManager (role → token limit, memory scope)
  → SessionManager (resolve the chat's canonical current message store; append message)
  → AIHandler.get_response
      → MemoryManager.recall()  (semantic; daily summaries live here after this feature)
      → build instructions: constitution → recalled memories → "---" → today's date
      → build input: conversation context
          (FLAG OFF: current session history, capped at max_tokens_by_role via write-time prune)
          (FLAG ON:  rolling 14-day verbatim window, capped by token backstop, archive-only)
      → OpenAI Responses API call (model gpt-5.6-luna)
      → [[NO_REPLY]] sentinel check
  → SessionManager (store assistant response)
  → WhatsAppHandler.send_response (if should_reply)
```

Background jobs wired in `denidin.py`'s `initialize_app` / `__main__`:

```
run_startup_cleanup                         (existing — behavior changes under US1/US3)
SessionCleanupThread  (hourly)              (existing — 24h-expiry→transfer→hourly-retry cycle
                                             is RETIRED when the flag is ON; see US1 / bugfix-035 H1)
recover_orphaned_sessions                   (existing — no longer load-bearing under US1; bugfix-044)
reminder_delivery_service scheduler         (existing, APScheduler CronTrigger */5)
accounting_reconciliation_service scheduler (existing, APScheduler IntervalTrigger)
+ nightly memory roll scheduler             (NEW — US2, APScheduler CronTrigger 02:00 Israel)
+ startup catch-up roll sweep               (NEW — US2)
```

---

## US1 — The last 14 days of messages are always in verbatim context (P1)

**Delivers**: the MVP. Every turn's context includes every message (per chat) from the last 14
calendar days (Israel local), verbatim, oldest-first, with Feature 039 `[sender_name]` prefixing
preserved for group turns. No 24-hour idle expiry. A restart does not wipe context. A session
persisted with an unknown field still loads.

**Legacy defects folded in**: bugfix-044 (restart continuity — designed out via deterministic
on-disk lookup), bugfix-035 H2 (tolerant load — fixed inline), bugfix-035 H1 *loop* (the
24h-expiry → per-session-transfer → hourly-retry cycle is retired, so there is nothing to loop
on — the write itself moves to US2).

### Flow (feature flag ON)

Inbound message → `SessionManager` resolves the chat's **canonical current message store** by a
**deterministic on-disk lookup** (scan for the chat's store by `whatsapp_chat`, or per-chat
message storage — `plan.md` decides), never solely by an in-memory `chat_to_session` index →
append message → `AIHandler.get_response` → **NEW** rolling-window builder replaces
`get_conversation_history(...)`: gather every persisted message for the chat with Israel-local
timestamp within the last 14 calendar days, oldest-first, apply Feature 039 `[sender_name]`
prefixing for group user turns, apply the token backstop (US3), feed as input to the Responses
API. The hourly 24h-idle-expiry sweep does not run (or is a no-op) for the chat.

Session load path: `SessionManager` deserialization filters `data` to known fields (mirroring
`denidin.py`'s `valid_fields = {f.name for f in fields(AppConfiguration)}`) and logs **one
WARNING** per dropped key — never raises `TypeError`.

### Flow (feature flag OFF)

Byte-for-byte the current path: current session history, `max_tokens_by_role` write-time prune,
24h idle expiry, per-session transfer on expiry, `chat_to_session` index, orphan recovery — all
unchanged.

### Scenarios

1. **Given** chat `C` has messages timestamped 20d, 15d, 13d, 2d, and 0d ago,
   **When** a new turn for `C` is processed with the flag ON,
   **Then** the 13d/2d/0d messages are in the verbatim window (oldest-first); the 20d/15d
   messages are not (they are represented by daily summaries via `recall()` — US2).

2. **Given** chat `C` has been idle for 3 days (well within 14),
   **When** a new message arrives,
   **Then** the full prior conversation is in context — no "new session, no memory" behavior.

3. **Given** a group chat,
   **When** the window is built,
   **Then** each user turn is prefixed `[<sender display name>]` exactly as the current Feature
   039 behavior.

4. **Given** the feature flag is OFF,
   **When** the same message sequence is processed,
   **Then** the built context is byte-for-byte identical to the pre-feature output (golden-file
   comparison), and the 24h-expiry/transfer/orphan-recovery machinery behaves exactly as today.

5. **Given** an app restart with an in-progress conversation for chat `C` (e.g. 14 messages,
   `last_active` ~12 min before the restart — the bugfix-044 shape),
   **When** the next inbound webhook for `C` is dispatched through `bot.router`,
   **Then** the message appends to `C`'s existing store (message_counter 15) and the prior 14
   turns are in the turn context — **no** `Created new session` log line for `C`, and **no**
   reliance on an orphan-recovery step having re-registered anything.

6. **Given** a `session.json` on disk containing `pending_ledger_events: []` (or any unknown
   top-level key) **and** a future-dated (clock-skew) message,
   **When** the rolling-window builder runs,
   **Then** it does not crash and does not return an empty window; the unknown key is dropped
   with exactly one WARNING (not an ERROR, not one per sweep); the session participates normally
   in the window and in a later roll (bugfix-035 H2).

7. **Given** a future code change removes a field from the `Session` model,
   **When** sessions written before that change are loaded,
   **Then** every one still loads — the tolerance is generic, not a one-off allowlist for
   `pending_ledger_events`.

8. **Given** the window is rebuilt on every turn,
   **When** p95 latency and per-turn token count are measured over the real prod message mix,
   **Then** added latency ≤ 150 ms p95 and per-turn input tokens are within the confirmed
   `gpt-5.6-luna` context budget with ≥ 30% headroom (SC-007).

9. **Given** the flag is ON,
   **When** the hourly `SessionCleanupThread` (or its replacement) runs,
   **Then** it never re-summarizes a still-in-window chat and never loops on a chat it already
   handled — the bugfix-035 H1 unbounded-retry cycle has no code path to execute (REQ-MEM-017).

### Integration test requirement

Real `SessionManager` + real `AIHandler`, tmp `data_root`, OpenAI mocked at the network boundary
only. Seed messages across the date range by dispatching real webhooks through `bot.router`
where possible; where explicit timestamps are needed, use the real `SessionManager` persistence
API (still no internal mocks). For the restart scenario, construct a fresh
`SessionManager`/`AIHandler` against the same `data_root` (simulating a process restart) and
dispatch another real webhook — assert it continued the existing store. For the poison-session
scenario, write a `session.json` fixture with an extra key and assert warning-level log + normal
participation. Include a flag-OFF golden-file regression test asserting on the actual input items
sent to the OpenAI boundary.

---

## US2 — Each night the previous day is summarized into long-term memory (P1)

**Delivers**: the Tier-2 half of the new model. At 02:00 Israel local, for each chat, the
previous calendar day's messages are summarized into **exactly one** daily long-term record
(chat + date keyed), embedded, and stored via `MemoryManager.remember()`. Empty days produce
nothing. Idempotent per (chat, date) via a roll marker. A startup catch-up sweep rolls days
missed while the app was down.

**Legacy defect folded in**: bugfix-035 H1 bugs 1+2 (group-chat collection naming + the raw
`client.get_collection()` verify that threw `NotFoundError` for `@g.us`) — designed out: the roll
writes only through the sanitizing `MemoryManager.remember(collection_name=…)` path and does
**no** raw `client.get_collection()` verify step; collection names for every chat-id shape
resolve through one shared sanitized helper.

### Flow

`initialize_app` registers an `APScheduler` `CronTrigger(hour=2, minute=0)` job (Israel local),
flag-gated, roll hour a config value. On fire: for each known chat, compute "yesterday" (Israel
local calendar day); check the roll marker for (chat, yesterday); if absent → gather that day's
messages (from retained storage, not just the live window) → if non-empty: `AIHandler` summarize
(1 billed call) → `MemoryManager.remember(summary, <collection via shared sanitized helper>,
metadata={chat, date, count, source:"daily-roll"})` → **then** write the roll marker; if empty →
write the roll marker only. On app start, a catch-up sweep does the same for every un-rolled
(chat, date) older than yesterday, without blocking message handling indefinitely.

### Scenarios

1. **Given** chat `C` (including a `…@g.us` group) has messages on calendar day `D`,
   **When** the nightly roll runs for `D`,
   **Then** exactly one daily summary for (`C`, `D`) is stored, retrievable via `recall()` with
   `chat`/`date` metadata, and a roll marker for (`C`, `D`) exists. For the group chat
   specifically: the collection resolves via the shared sanitized helper (no `NotFoundError`),
   and a second roll of the same day makes 0 new billed calls and creates 0 duplicate records
   (bugfix-035 H1).

2. **Given** chat `C` had no messages on day `D`,
   **When** the roll runs for `D`,
   **Then** 0 summaries, 0 OpenAI calls, and (`C`, `D`) is still marked rolled.

3. **Given** (`C`, `D`) already has a roll marker,
   **When** the nightly job or the catch-up sweep processes `D` again,
   **Then** it is skipped — 0 new summaries, 0 new billed calls.

4. **Given** the app was down across days `D1` and `D2`,
   **When** it starts,
   **Then** the catch-up sweep rolls (`C`, `D1`) and (`C`, `D2`) exactly once each before normal
   operation resumes.

5. **Given** a daily summary exists for day `D` which is now outside the 14-day window,
   **When** the user asks a question whose answer is in `D`,
   **Then** semantic recall surfaces `D`'s summary into the "RECALLED MEMORIES" block.

6. **Given** the summarization OpenAI call fails for (`C`, `D`),
   **When** the job runs,
   **Then** no roll marker is written for (`C`, `D`), it is retried with a bounded budget on the
   next run, and one unloadable/erroring chat does not abort the roll for the other chats.

7. **Given** the scheduler and a manually-run roll script both target (`C`, `D`) concurrently,
   **When** both execute,
   **Then** at most one summary is created (marker check-and-write is race-safe).

8. **Given** one chat's session is a bugfix-035 H2 poison record,
   **When** the nightly roll iterates all chats,
   **Then** that chat loads tolerantly (US1) and participates; if it still errors for an
   unrelated reason, its failure is isolated and logged once, and every other chat's roll
   completes.

9. **Given** a roll night that crosses a DST transition (02:00 does not exist, or occurs twice),
   **When** the `CronTrigger` fires,
   **Then** it fires exactly once and "previous calendar day" is unambiguous.

### Integration test requirement

Real `SessionManager` + real `MemoryManager` (real ChromaDB, tmp `data_root`), OpenAI mocked at
the boundary (billed variant exercises the real call). Seed multiple chats/days — including a
`…@g.us` group — via real persistence. Invoke the real roll function (not the scheduler timer).
Assert summary count, marker presence, `recall()` retrievability, and boundary call-count across
a re-run. A separate test simulates downtime and asserts the catch-up sweep's exact coverage. A
focused test asserts the group-chat collection resolves and is created via the shared sanitized
helper with no raw `client.get_collection()` call.

---

## US3 — Raw messages are never deleted, and context never blows the token budget (P1)

**Delivers**: the safety property that makes the new model trustworthy. (a) A message aging past
the 14-day window, or trimmed by the token/size backstop, is **archived** (moved on disk to a
retained path) — never `unlink()`-ed. (b) The verbatim window is bounded by "last 14 days OR last
N tokens, whichever is smaller"; when 14 days exceeds N, the oldest in-window messages are
archived out of the live context (still summarized on their normal nightly schedule).

**Legacy defect folded in**: bugfix-035 H3 (`expired/YYYY-MM-DD/` unbounded growth + tests
picking `rglob(...)[0]`) — subsumed: the archive-retention policy must be an explicit documented
decision, and tests must scope archived-session lookups to their own `session_id`.

### Flow

Window builder (US1) → after selecting the 14-day set, if its token count > backstop `N`: archive
the oldest messages (move `messages/<uuid>.json` to a retained archive path, update the in-memory
view) until it fits. Aging out of 14 days → the same archive move. **The
`_prune_until_under_limit` `unlink()` path is replaced by this archive-only trim when the flag is
ON.** `archive_session` stays a `rename` (move). No feature code path calls `Path.unlink` /
`os.remove` / `shutil.rmtree` on a message or session file.

### Scenarios

1. **Given** a message older than 14 days,
   **When** the window is rebuilt,
   **Then** its raw file exists at a retained archive path (not deleted), and a file-integrity
   audit still balances (live + archived counts == `message_counter` == id-list length).

2. **Given** the 14-day window for chat `C` exceeds the token backstop `N`,
   **When** context is built,
   **Then** the oldest in-window messages are archived out until the window fits `N`, and the
   most recent messages are always retained.

3. **Given** any message archived by the backstop trim,
   **When** its calendar day's nightly roll runs,
   **Then** that message is included in the day's summary (the roll reads from retained storage,
   not just the live window).

4. **Given** the full feature codebase,
   **When** audited for `unlink` / `os.remove` / `shutil.rmtree` against message or session
   paths,
   **Then** there are zero such calls on a live (non-flag-OFF-legacy) path.

5. **Given** `expired/YYYY-MM-DD/` accumulating across many runs (bugfix-035 H3),
   **When** the retention policy is applied,
   **Then** it follows a documented bound (which may be "retain indefinitely by design"), never
   silent deletion of a message's only copy, and the test suite scopes its archived-session
   lookups to its own `session_id` rather than `rglob(...)[0]`.

6. **Given** the token backstop is misconfigured smaller than one day of messages,
   **When** the window is built,
   **Then** it still returns the most recent messages and terminates (no infinite archive loop).

7. **Given** a message timestamped exactly on the 14-day boundary or exactly at midnight between
   two days,
   **When** the window-builder and the roll job both run,
   **Then** the message belongs to exactly one day and is either in the window or summarized —
   never both, never neither (inclusive/exclusive rules explicit and consistent).

### Integration test requirement

Real `SessionManager`, tmp `data_root`, a deliberately tiny configured backstop. Seed more
in-window messages than the backstop allows. Build context via `bot.router`. Assert the live
window fits `N`, every trimmed message file exists at its archive path, and the nightly roll for
that day still includes them. Plus a static audit test / grep assertion that no feature module
deletes message or session files. Plus a file-integrity audit helper asserting
live + archived == `message_counter` == id-list length.

---

## US4 — A one-time migration backfills daily summaries for pre-window history (P2)

_Separately gated: real prod write + real billed calls; fresh explicit approval per run._

### Flow

Operator runs `scripts/…/backfill_daily_summaries.sh --env <env> --since <YYYY-MM-DD>
[--until <YYYY-MM-DD>]` (default `--until` = today − 14d), following the Feature 061/062
backfill-script conventions (explicit CLI args, no hardcoded dates, idempotent, real credentials
never committed). For each chat, for each calendar day in range: check the roll marker; if absent
→ gather the day's messages → non-empty: summarize (billed) → `remember(...)` → write marker;
empty: write marker. Emit a per-chat run report. Reads raw messages only — never moves, archives,
or deletes them.

### Scenarios

1. **Given** prod history 2026-08-05 → (today − 14d) for both prod chats
   (`120363210094632983@g.us`, `972522968679@c.us`),
   **When** the migration runs,
   **Then** every non-empty calendar day in range has exactly one daily summary + a roll marker;
   every empty day has a roll marker only.

2. **Given** the migration completed,
   **When** it is run again with the same args,
   **Then** 0 OpenAI calls, 0 new records — every (chat, date) already has a marker.

3. **Given** the migration completed and the flag is then enabled in prod,
   **When** the nightly job / catch-up sweep first runs,
   **Then** it processes only days after the migration cutoff — no migrated day is re-summarized.

4. **Given** the migration is a real prod data write,
   **When** an agent or operator wants to run it,
   **Then** it requires fresh explicit human approval for that specific run; it never runs as a
   side effect of a deploy or of flipping the feature flag.

5. **Given** raw message files,
   **When** the migration runs,
   **Then** none are moved, archived, or deleted — read-only access confirmed by a before/after
   file-integrity check.

6. **Given** the migration run,
   **When** it finishes,
   **Then** it prints a report: per chat — days processed, summaries created, empty days, total
   billed calls — for human review.

### Integration test requirement (dev/sandbox)

Point the real script at a dev chat seeded with > 14 days of history (real persistence). Run it
(real billed calls — this is the acceptance tier). Assert summary/marker coverage, idempotent
re-run, unchanged raw files, and that a subsequent nightly-roll invocation skips all migrated
days.

---

## US5 — Prod application logs are retained across rotation (P2)

### Flow

Audit: the app's Python logging config (`logs/denidin.log` handler — plain `FileHandler` vs
`RotatingFileHandler` / `TimedRotatingFileHandler`, `backupCount`) + `docker-compose.prod.yml`
log driver options (`max-size` / `max-file` on `json-file`), and the morning-mcp-app equivalent.
Determine what rotates, by what trigger (size/age), and whether rotated segments are retained. If
not retained → specify + verify the minimal config change (a real prod config change goes through
the normal deploy flow, outside this feature).

### Scenarios

1. **Given** the current prod logging setup,
   **When** it is audited,
   **Then** a written finding states each rotation trigger (size/age) and whether every rotated
   segment is kept on disk.

2. **Given** rotation configured by size or age,
   **When** a rotation occurs,
   **Then** the pre-rotation content persists as an on-disk file (compression allowed), not
   discarded.

3. **Given** the application-log history since 2026-08-05,
   **When** any past date's log lines are requested,
   **Then** they are retrievable from disk, bounded only by a documented deliberate retention
   policy — never silent loss.

4. **Given** `json-file` is still the Docker driver for `docker logs`,
   **When** it rotates and drops its oldest chunk,
   **Then** that is acceptable only because the app-level file handler independently holds full
   history; the runbook states this dependency.

### Integration test requirement

Configuration inspection + a forced-rotation verification on a non-prod instance: set a tiny
`maxBytes` / short interval, generate enough log volume to trigger several rotations, assert the
rotated files all still exist on disk with their content intact. Document the finding in
`quickstart.md` / a runbook section.

---

## Cross-story acceptance (final `billed` pass — written & run once, after all unit/integration GREEN)

- **AC-1 (US1+US2)**: A real group-chat (`…@g.us`) conversation over 3 simulated days → nightly
  roll for each day → ask a question answerable only from day 1 (now summarized, outside the
  window) → the bot answers correctly using the recalled daily summary. 1 billed summary call per
  day, 0 duplicates, no `NotFoundError` for the group collection (bugfix-035 H1 proven fixed).
- **AC-2 (US1)**: A real conversation → simulated process restart → new inbound message → the bot
  continues seamlessly with full pre-restart context, no manual re-priming (bugfix-044 proven
  designed out).
- **AC-3 (US1+US3)**: A conversation exceeding the token backstop → the bot still answers using
  the most recent context, and a disk audit shows every trimmed message retained at its archive
  path.
- **AC-4 (US4)**: The dev migration run, end to end, with the per-chat run report reviewed;
  a follow-up nightly-roll invocation skips every migrated day.
- **AC-5 (US1+US2)**: The known bugfix-035 H2 poison-session shape (`0f5eaa04`-style, unknown
  `pending_ledger_events` key), loaded into a running app → no recurring hourly `Failed to load
  session` error → the session participates in a nightly roll.
