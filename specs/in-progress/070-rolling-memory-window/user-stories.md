# User Stories: Rolling 14-Day Short-Term Memory Window with Nightly Daily-Summary Roll

**Feature**: 070-rolling-memory-window
**Companion to**: `spec.md` (authoritative requirements), `checklists/requirements.md`
**Format**: Given-When-Then. Each story names the concrete system flow (webhook → router →
handler → manager → store) and its integration-test requirement, per METHODOLOGY.md §I and
CONSTITUTION.md §V.

> **Priority key**: P1 = prerequisite bug fixes that must be correct before the new model is
> layered on. P2 = the new memory model. P3 = one-time operational tasks (separately gated).

---

## System context (applies to every story)

Inbound WhatsApp message flow (unchanged by this feature except where noted):

```
Green API webhook
  → denidin.py  HANDLER_REGISTRY / dispatch_notification  (type_message routing)
  → WhatsAppHandler.handle_* (parse → WhatsAppMessage)
  → [group only] GroupMembershipResolver (most-permissive member's role)
  → UserManager (role → token limit, memory scope)
  → SessionManager (resolve active session for chat via chat_to_session; append message)
  → AIHandler.get_response
      → MemoryManager.recall()  (semantic; daily summaries live here after this feature)
      → build instructions: constitution → recalled memories → "---" → today's date
      → build input: conversation context
          (TODAY: current session history, capped at max_tokens_by_role via write-time prune)
          (AFTER US4: rolling 14-day verbatim window, capped by token backstop, archive-only)
      → OpenAI Responses API call (model gpt-5.6-luna)
      → [[NO_REPLY]] sentinel check
  → SessionManager (store assistant response)
  → WhatsAppHandler.send_response (if should_reply)
```

Background jobs wired in `denidin.py`'s `initialize_app` / `__main__`:

```
run_startup_cleanup                         (existing)
SessionCleanupThread  (hourly)              (existing — behavior changes under US1/US6)
recover_orphaned_sessions                   (existing — behavior changes under US3)
reminder_delivery_service scheduler         (existing, APScheduler CronTrigger */5)
accounting_reconciliation_service scheduler (existing, APScheduler IntervalTrigger)
+ nightly memory roll scheduler             (NEW — US5, APScheduler CronTrigger 02:00 Israel)
+ startup catch-up roll sweep               (NEW — US5)
```

---

## US1 — Group-chat long-term memory transfer actually completes (P1)

_Fixes bugfix-035 H1. Bug-Driven Development: root cause approval required first._

### Flow

`SessionCleanupThread` (hourly) or `run_startup_cleanup` picks an expired session →
`_process_session_cleanup` → STEP 2 `AIHandler.transfer_session_to_long_term_memory(session)` →
AI summarization (1 billed call) → `MemoryManager.remember(content, collection_name, metadata)`
→ **[BUG] post-write verify: `self.memory_manager.client.get_collection(name=collection_name)`
with the RAW, unsanitized name** → `NotFoundError` for `@g.us` chats → broad `except` →
`{"success": False, "reason": "transfer_error"}` → `transferred_to_longterm` never set → session
reprocessed next hour, forever.

### Scenarios

1. **Given** a group chat `120363210094632983@g.us` with an expired session containing real
   conversation content,
   **When** the cleanup sweep runs `transfer_session_to_long_term_memory` for it,
   **Then** the summary is written to the chat's long-term collection (resolved via the same
   sanitization the write uses), the verify step (if kept) confirms it using that same resolution,
   the function returns success, and the session is marked `transferred_to_longterm`.

2. **Given** that session is now marked `transferred_to_longterm`,
   **When** the next hourly sweep runs,
   **Then** the session is skipped entirely — 0 new billed OpenAI calls, 0 new ChromaDB records.

3. **Given** a `@c.us` (1:1) chat session,
   **When** transfer runs,
   **Then** it still succeeds exactly as before (no regression) and resolves the same collection
   it did previously.

4. **Given** a transfer whose ChromaDB write genuinely fails 3 times in a row (real failure, not
   the verify-step false negative),
   **When** the retry budget is exhausted,
   **Then** the session is moved to a distinct dead-letter / failure state, a WARNING/ERROR is
   logged once as a give-up signal (not once per hour forever), and it is not retried until that
   state is cleared.

5. **Given** a group chat that has never had a long-term collection,
   **When** its first daily summary / transfer is written,
   **Then** the collection is created (the create path is also sanitized) and the write succeeds.

### Integration test requirement

Real `SessionManager` + real `MemoryManager` (real ChromaDB, tmp `data_root`) + `AIHandler` with
OpenAI mocked at the network boundary only (billed variant exercises the real call). Drive a real
`imageMessage`/`textMessage` group webhook through `bot.router` to build the session; do not call
manager methods directly to create it. Assert on `recall()` retrievability and
`transferred_to_longterm`, and assert call-count on the OpenAI boundary across two sweeps.

---

## US2 — A session with an unknown persisted field still loads (P1)

_Fixes bugfix-035 H2. Bug-Driven Development: root cause approval required first._

### Flow

`SessionManager._load_sessions()` / lazy load → `Session(**data)` where `data` came from
`session.json` → **[BUG] `__init__() got an unexpected keyword argument 'pending_ledger_events'`**
→ `ERROR Failed to load session …` → session never loaded, never expired, never archived, never
transferred; error re-logged every hourly sweep, every orphan-recovery pass.

### Scenarios

1. **Given** a `session.json` on disk containing `pending_ledger_events: []` (or any unknown
   top-level key),
   **When** `SessionManager` loads it,
   **Then** it deserializes successfully, the unknown key is dropped (mirroring `denidin.py`'s
   `valid_fields = {f.name for f in fields(AppConfiguration)}` filter), and exactly one WARNING
   is logged — not an ERROR, not one per sweep.

2. **Given** that session is loaded,
   **When** the rolling-window builder (US4) and the nightly roll (US5) run,
   **Then** it is processed like any other session — its messages appear in the window / the
   day's summary, and it can be archived normally.

3. **Given** a future code change removes a field from the `Session` model,
   **When** sessions written before that change are loaded,
   **Then** every one of them still loads (the tolerance is generic, not a one-off allowlist for
   `pending_ledger_events`).

4. **Given** the known prod poison session `0f5eaa04-...`,
   **When** the app next starts after the fix,
   **Then** the recurring hourly `Failed to load session 0f5eaa04` ERROR stops, and the "N
   expired sessions" startup count can clear.

### Integration test requirement

Real `SessionManager`, real filesystem (tmp `data_root`). Write a `session.json` fixture with an
extra key, load via the real manager, assert no exception + warning-level log + normal lifecycle
participation. No mocks.

---

## US3 — Conversation context survives an app restart (P1)

_Fixes bugfix-044. Bug-Driven Development: root cause approval required first._

### Flow

App start → `run_startup_cleanup` → `AIHandler.recover_orphaned_sessions()` → for each active
orphan: `short_term_sessions.append(session.session_id)` + log "Recovered active session..."
→ **[BUG] never writes `self.chat_to_session[session.whatsapp_chat] = session.session_id`** →
next inbound message for that chat → `SessionManager` "active session for chat?" → miss →
`Created new session <new-uuid> for chat …` → recovered 14-message session silently abandoned.

Second bug: `remove_from_index(session)` does
`del self.chat_to_session[session.whatsapp_chat]` **without** checking
`self.chat_to_session[chat] == session.session_id` → can evict a newer session's registration.

### Scenarios

1. **Given** chat `C` had an active session `S` (14 messages, `last_active` ~12 min before
   restart) that became orphaned by a restart,
   **When** `recover_orphaned_sessions()` runs,
   **Then** `S` is loaded **and** registered as `C`'s active session in the lookup index.

2. **Given** `S` is recovered and registered,
   **When** the next inbound webhook for `C` is dispatched through `bot.router`,
   **Then** the message appends to `S` (message_counter 15), and `S`'s prior 14 turns are in the
   turn context — **no** `Created new session` log line for `C`.

3. **Given** `chat_to_session[C] == S_new` (a newer session),
   **When** `remove_from_index` is called for a stale older session `S_old` whose
   `whatsapp_chat` is also `C`,
   **Then** after the call `chat_to_session[C]` still equals `S_new`.

4. **Given** both `run_startup_cleanup` and `recover_orphaned_sessions` run at boot,
   **When** they complete in whatever order the fix specifies,
   **Then** for every chat there is either a completed-and-transferred session or a registered
   active session — never neither. The ordering is documented in `plan.md`.

### Integration test requirement

Build session `S` for chat `C` by dispatching real webhooks through `bot.router`. Construct a
fresh `SessionManager`/`AIHandler` (simulating a process restart, same `data_root`). Run
`recover_orphaned_sessions()`. Dispatch another real webhook for `C`. Assert it continued `S`.
Separately, a focused unit test for the `remove_from_index` session-id guard. No internal mocks.

---

## US4 — The last 14 days of messages are always in verbatim context (P2)

### Flow (feature flag ON)

Inbound message → `AIHandler.get_response` → **NEW** rolling-window builder replaces
`get_conversation_history(...)`: gather every persisted message for the chat with Israel-local
timestamp within the last 14 calendar days, oldest-first, apply Feature 039 `[sender_name]`
prefixing for group user turns, apply the token backstop (US6), feed as input to the Responses
API. No 24-hour idle expiry runs.

### Flow (feature flag OFF)

Byte-for-byte the current path: current session history, `max_tokens_by_role` write-time prune,
24h idle expiry.

### Scenarios

1. **Given** chat `C` has messages timestamped 20d, 15d, 13d, 2d, and 0d ago,
   **When** a new turn for `C` is processed with the flag ON,
   **Then** the 13d/2d/0d messages are in the verbatim window (oldest-first); the 20d/15d
   messages are not (they are represented by daily summaries via `recall()`).

2. **Given** chat `C` has been idle for 3 days (well within 14),
   **When** a new message arrives,
   **Then** the full prior conversation is in context — the bot does not behave as if the chat
   is new.

3. **Given** a group chat,
   **When** the window is built,
   **Then** each user turn is prefixed `[<sender display name>]` exactly as the current Feature
   039 behavior.

4. **Given** the feature flag is OFF,
   **When** the same message sequence is processed,
   **Then** the built context is byte-for-byte identical to the pre-feature output (golden-file
   comparison).

5. **Given** a message dated in the future (clock skew) and an unloadable H2-poison session for
   the chat,
   **When** the window is built,
   **Then** it does not crash and does not return an empty window — it includes the valid recent
   messages.

6. **Given** the window is rebuilt on every turn,
   **When** p95 latency and per-turn token count are measured over the real prod message mix,
   **Then** added latency ≤ 150 ms p95 and tokens are within the confirmed model budget with
   ≥ 30% headroom (SC-007).

### Integration test requirement

Seed a chat's messages across the date range by dispatching real webhooks (or, where date control
is needed, by the real `SessionManager` persistence API with explicit timestamps — still no
mocks). Process a new turn through `bot.router`. Assert on the actual input items sent to the
OpenAI boundary. Include a flag-OFF golden-file regression test.

---

## US5 — Each night the previous day is summarized into long-term memory (P2)

### Flow

`initialize_app` registers an `APScheduler` `CronTrigger(hour=2, minute=0)` job (Israel local),
flag-gated. On fire: for each known chat, compute "yesterday" (Israel local calendar day); check
roll marker for (chat, yesterday); if absent → gather that day's messages → if non-empty:
`AIHandler` summarize (1 billed call) → `MemoryManager.remember(summary, <sanitized collection>,
metadata={chat, date, count, source:"daily-roll"})` → **then** write roll marker; if empty →
write roll marker only. On app start, a catch-up sweep does the same for every un-rolled
(chat, date) older than yesterday.

### Scenarios

1. **Given** chat `C` has messages on calendar day `D`,
   **When** the nightly roll runs for `D`,
   **Then** exactly one daily summary for (`C`, `D`) is stored and retrievable via `recall()`
   with `chat`/`date` metadata, and a roll marker for (`C`, `D`) exists.

2. **Given** chat `C` had no messages on day `D`,
   **When** the roll runs for `D`,
   **Then** 0 summaries, 0 OpenAI calls, and (`C`, `D`) is still marked rolled.

3. **Given** (`C`, `D`) already has a roll marker,
   **When** the nightly job or the catch-up sweep processes `D` again,
   **Then** it is skipped — 0 new summaries, 0 new billed calls.

4. **Given** the app was down across days `D1` and `D2`,
   **When** it starts,
   **Then** the catch-up sweep rolls (`C`, `D1`) and (`C`, `D2`) exactly once each.

5. **Given** a daily summary exists for day `D` which is now outside the 14-day window,
   **When** the user asks a question whose answer is in `D`,
   **Then** semantic recall surfaces `D`'s summary into the "RECALLED MEMORIES" block.

6. **Given** the summarization OpenAI call fails for (`C`, `D`),
   **When** the job runs,
   **Then** no roll marker is written for (`C`, `D`), and it is retried (bounded budget) on the
   next run; it is only marked rolled once the summary is durably stored.

7. **Given** the scheduler and a manually-run roll script both target (`C`, `D`) concurrently,
   **When** both execute,
   **Then** at most one summary is created (marker check-and-write is race-safe).

8. **Given** one chat's session is an H2-poison record,
   **When** the nightly roll iterates all chats,
   **Then** that chat's failure is isolated and logged; every other chat's roll still completes.

### Integration test requirement

Real `SessionManager` + real `MemoryManager` (real ChromaDB, tmp `data_root`), OpenAI mocked at
the boundary (billed variant real). Seed multiple chats/days via real persistence. Invoke the
real roll function (not the scheduler timer). Assert summary count, marker presence, `recall()`
retrievability, and boundary call-count across a re-run. A separate test simulates downtime and
asserts the catch-up sweep's exact coverage.

---

## US6 — Raw messages are never deleted, and context never blows the token budget (P2)

### Flow

Window builder (US4) → after selecting the 14-day set, if its token count > backstop `N`: archive
the oldest messages (move `messages/<uuid>.json` to a retained archive path, update the session's
in-memory view) until it fits. Aging out of 14 days → same archive move. **The
`_prune_until_under_limit` `unlink()` path is replaced by this archive-only trim when the flag is
ON.** `archive_session` stays a `rename` (move). Nothing calls `Path.unlink` on message/session
files in the feature's code.

### Scenarios

1. **Given** a message older than 14 days,
   **When** the window is rebuilt,
   **Then** its raw file exists at a retained archive path (not deleted), and a file-integrity
   audit still balances (live + archived counts == message_counter == id-list length).

2. **Given** the 14-day window for chat `C` exceeds the token backstop `N`,
   **When** context is built,
   **Then** the oldest in-window messages are archived out until the window fits `N`, and the
   most recent messages are always retained.

3. **Given** any message archived by the backstop trim,
   **When** its calendar day's nightly roll runs,
   **Then** that message is included in the day's summary (the roll reads from retained storage,
   not just the live window).

4. **Given** the full feature codebase,
   **When** audited for `unlink`/`os.remove`/`shutil.rmtree` against message or session paths,
   **Then** there are zero such calls on a live (non-flag-OFF-legacy) path.

5. **Given** `expired/YYYY-MM-DD/` accumulating across many runs (bugfix-035 H3),
   **When** the retention policy is applied,
   **Then** it follows a documented bound (which may be "retain indefinitely"), never silent
   deletion of a message's only copy, and the test suite scopes its archived-session lookups to
   its own `session_id` rather than `rglob(...)[0]`.

6. **Given** the token backstop is misconfigured smaller than one day of messages,
   **When** the window is built,
   **Then** it still returns the most recent messages and terminates (no infinite archive loop).

### Integration test requirement

Real `SessionManager`, tmp `data_root`, tiny configured backstop. Seed > backstop messages. Build
context via `bot.router`. Assert live window fits `N`, every trimmed message file exists at its
archive path, and the nightly roll for that day still includes them. Plus a static audit test /
grep assertion that no feature module deletes message files.

---

## US7 — A one-time migration backfills daily summaries for pre-window history (P3)

_Separately gated: real prod write + real billed calls; fresh explicit approval per run._

### Flow

Operator runs `scripts/…/backfill_daily_summaries.sh --env <env> --since <YYYY-MM-DD>
[--until <YYYY-MM-DD>]` (default `--until` = today − 14d). For each chat, for each calendar day in
range: check roll marker; if absent → gather day's messages → non-empty: summarize (billed) →
`remember(...)` → write marker; empty: write marker. Emit a per-chat run report. Reads raw
messages only.

### Scenarios

1. **Given** prod history 2026-08-05 → (today − 14d) for both prod chats,
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

## US8 — Prod application logs are retained across rotation (P3)

### Flow

Audit: the app's Python logging config (`logs/denidin.log` handler — plain `FileHandler` vs
`RotatingFileHandler`/`TimedRotatingFileHandler`, `backupCount`) + `docker-compose.prod.yml` log
driver options (`max-size`/`max-file` on `json-file`). Determine what rotates, by what trigger,
and whether rotated segments are retained. If not retained → specify + verify the minimal config
change.

### Scenarios

1. **Given** the current prod logging setup,
   **When** it is audited,
   **Then** a written finding states each rotation trigger (size/age) and whether every rotated
   segment is kept on disk.

2. **Given** rotation configured by size or age,
   **When** a rotation occurs,
   **Then** the pre-rotation content persists as an on-disk file (compression allowed).

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
`maxBytes`/short interval, generate enough log volume to trigger several rotations, assert the
rotated files all still exist on disk with their content intact. Document the finding in
`quickstart.md` / a runbook section.

---

## Cross-story acceptance (final `billed` pass — written & run once, after all unit/integration GREEN)

- **AC-1 (US1+US5)**: A real group-chat conversation over 3 simulated days → nightly roll for each
  day → ask a question answerable only from day 1 (now summarized) → the bot answers correctly
  using the recalled daily summary. 1 billed summary call per day, 0 duplicates.
- **AC-2 (US3+US4)**: A real conversation → simulated restart → new message → the bot continues
  seamlessly with full pre-restart context, no manual re-priming.
- **AC-3 (US4+US6)**: A conversation exceeding the token backstop → the bot still answers using
  the most recent context, and a disk audit shows every trimmed message retained.
- **AC-4 (US7)**: The dev migration run, end to end, with the run report reviewed.
- **AC-5 (US2)**: The known poison-session shape, loaded into a running app, no longer produces
  recurring errors and participates in a roll.
