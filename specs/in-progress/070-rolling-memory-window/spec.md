# Feature Specification: Rolling 14-Day Short-Term Memory Window with Nightly Daily-Summary Roll

**Feature Branch**: `feature/070-rolling-memory-window`
**Created**: 2026-09-01
**Status**: Draft — pending `speckit.clarify`
**Input**: User description: Replace the 24-hour session-expiry memory lifecycle with a rolling
14-day verbatim short-term window plus a nightly 2am (Israel local) roll that summarizes the
previous calendar day into long-term memory. Fix the group-chat long-term-memory naming bugs
(bugfix-035 H1/H2/H3) and the restart context-loss bugs (bugfix-044) as prerequisites. Perform a
one-time prod migration to backfill daily summaries for history older than 14 days. Guarantee raw
messages are never deleted (only archived). Verify prod application logs are never lost on
rotation.

---

**IMPORTANT**: This spec MUST comply with:

- **CONSTITUTION.md** (§I-III, §V): no environment variables (all config via `AppConfiguration`
  DI); Israel local time everywhere (`now_local()`); `pathlib.Path`; no monkey-patching; ZERO
  MOCKING of internal components (real `SessionManager`/`MemoryManager`/`AIHandler` code paths in
  every test — OpenAI and Green API are the only mockable boundaries, and never inside
  `tests/integration/`); NO UNVERIFIED THIRD-PARTY ASSUMPTIONS; feature-flagged new behavior
  (`config.feature_flags`, default `false`, byte-for-byte identical path when disabled); tests
  immutable once approved.
- **METHODOLOGY.md** (§I, II, VI, VII, VIII, IX, X): spec-first; mandatory `user-stories.md`
  (Given-When-Then, separate file, spec approval BLOCKED without it); Terminology Glossary;
  Technology Choices; Requirement IDs (`REQ-MEM-*` series — a new series, since this is a
  memory-lifecycle change, not a Morning invoicing-logic change); **Bug-Driven Development
  (§VII)** for the three prerequisite bug clusters (root cause → human approval → test-gap
  analysis → failing test → human approval → minimal fix → verify); "TDD" = the `billed`
  acceptance tests, described here in plain language, code written and run once at the end.
- The root `CLAUDE.md` banners: the **one-time prod migration** (User Story 7) is its own gated
  action requiring fresh, explicit human approval every time it is run, independent of approval to
  build the feature; it performs a real prod data write and real billed OpenAI calls.

**Required Files**: `user-stories.md` (pending) · `spec.md` (this file) ✅ ·
`checklists/requirements.md` (pending) · `plan.md` (later) · `tasks.md` (later).

---

## User Stories Reference

**NOTE**: Complete Given-When-Then acceptance criteria live in **`user-stories.md`** (SEPARATE
from this spec). This section is a quick reference only.

| # | Title | Priority | Kind |
|---|---|---|---|
| US1 | Group-chat long-term memory transfer actually completes (bugfix-035 H1) | P1 | Bug fix (prerequisite) |
| US2 | A session with an unknown persisted field still loads (bugfix-035 H2) | P1 | Bug fix (prerequisite) |
| US3 | Conversation context survives an app restart (bugfix-044) | P1 | Bug fix (prerequisite) |
| US4 | The last 14 days of messages are always in verbatim context | P2 | New capability |
| US5 | Each night the previous day is summarized into long-term memory | P2 | New capability |
| US6 | Raw messages are never deleted, and context never blows the token budget | P2 | New capability |
| US7 | A one-time migration backfills daily summaries for pre-window history | P3 | Operational (separately gated) |
| US8 | Prod application logs are retained across rotation | P3 | Operational verification |

---

## Problem Statement

### The current model and why it is being replaced

Today, Tier-1 ("short-term") memory is **session-scoped**. A `Session` is created per chat, holds
its messages verbatim, and **expires after 24 hours of inactivity** (`session_timeout_hours: 24`).
On expiry the hourly `SessionCleanupThread` archives the session, AI-summarizes it (one billed
OpenAI call), embeds the summary, and stores it as **one ChromaDB record per expired session** in
collection `memory_<chat>`. Every inbound message then does a semantic `recall()` over that
collection and injects a "RECALLED MEMORIES" block into the system prompt.

Three structural problems with this model, all observed in real production:

1. **Group chats never actually get Tier-2 memory.** The transfer's collection-name derivation
   only strips `@c.us`, so a group chat (`…@g.us`) produces an invalid raw collection name; the
   post-write "verify" step then bypasses the sanitizer and throws `NotFoundError`, so a transfer
   that *actually succeeded* is reported as failed. `transferred_to_longterm` is never set, the
   session is reprocessed **every hour, forever**, each iteration costing a fresh billed OpenAI
   call and writing another duplicate summary record. As of the 2026-08-09 review: 27 near-
   identical records for a single session, still growing. (bugfix-035 H1.)

2. **A restart can silently discard live conversation context.** After the 2026-08-25 prod
   restart, orphaned-session recovery reloaded the right session (`99d0129e`, 14 messages, from
   ~12 min before the restart) and logged success — but never registered it as the chat's active
   session, so the next inbound message fell through to "no active session → create a new empty
   one," discarding all 14 recovered messages. The user had to re-provide context manually.
   (bugfix-044.) A related schema-migration bug (bugfix-035 H2) strands any session written with a
   since-removed field (`pending_ledger_events`): `Session(**data)` raises `TypeError`, so the
   session can never be loaded, expired, archived, or transferred, and logs an error every hour
   indefinitely.

3. **Summary granularity is arbitrary and unpredictable.** "One summary per expired session"
   means a burst of five short exchanges in an evening produces five thin summaries, while a
   day-long active conversation that never idles for 24h produces *zero* summaries and instead
   silently prunes its oldest messages once the godfather 100K-token write-time cap is hit — with
   no summary of what was dropped. Multi-week questions ("what did we agree with Galit back in
   August?") land against a semantic collection whose contents depend entirely on when sessions
   happened to idle out.

### The target model

- **Short-term memory becomes time-scoped, not session-scoped.** Every message from the **last 14
  days** (per chat) is loaded verbatim into context on every turn. There is no 24-hour idle
  expiry.
- **A nightly job at 02:00 Israel local time rolls the window.** For each chat, it summarizes
  **the previous calendar day's** messages into **exactly one** long-term (daily) ChromaDB record,
  keyed by chat + date. Empty days are skipped (no record, no billed call). The job is idempotent
  per (chat, date): a marker records that (chat, date) was rolled, so a re-run or a catch-up sweep
  never double-summarizes or double-charges.
- **A startup catch-up sweep** rolls any (chat, date) pairs that fell outside the window while the
  app was down, so a multi-day outage does not leave a permanent hole.
- **Raw messages are never deleted.** Messages that age past the 14-day window are *archived*
  (moved on disk), never `unlink()`-ed. A token/size backstop under the window caps the verbatim
  context, but trimming for the backstop also only archives — it never deletes.
- **A one-time prod migration** backfills one daily summary per non-empty calendar day for all
  history older than 14 days (the bot went live 2026-08-05, so roughly two-plus weeks of daily
  summaries), so the new model starts with a complete Tier-2 record rather than a hole.
- **Prod application logs are verified to survive rotation** — rotation by size or age is fine,
  but each rotated segment must be kept as an on-disk file, not discarded (the lossy Docker
  json-file log driver rotation is not sufficient as the system of record).

Since the bot went live 2026-08-05 and there are only two prod chats ever, the end state is: a
14-day verbatim window plus ~2-3 weeks of daily summaries per chat, growing by one summary per
chat per active day.

---

## Terminology Glossary

- **Short-term window / rolling window**: the set of messages, per chat, whose timestamp is within
  the last 14 calendar days (Israel local). Loaded verbatim into `instructions`/input on every
  turn. Replaces the concept of "the current session's history."
- **Nightly roll**: the 02:00 Israel-local job that, per chat, summarizes the previous calendar
  day's messages into one daily summary and records a roll marker for that (chat, date).
- **Daily summary**: exactly one AI-generated summary of one chat's messages for one calendar day,
  embedded and stored as one record in that chat's long-term collection, with metadata including
  the chat id and the summarized date. The unit of Tier-2 memory under the new model (replacing
  "per-expired-session summary").
- **Roll marker / idempotency marker**: a durable record that (chat, date) has been rolled. Its
  presence means "do not summarize this (chat, date) again." Checked by the nightly job, the
  startup catch-up sweep, and the one-time migration alike.
- **Startup catch-up sweep**: on app start, rolls every (chat, date) pair that is now older than
  "yesterday" but has no roll marker and is not covered by a still-loaded window — i.e. days that
  passed while the app was down.
- **Token/size backstop**: a per-chat upper bound on the verbatim window (e.g. "the last 14 days,
  OR the last N tokens, whichever is smaller"). When the 14-day window exceeds the bound, the
  oldest in-window messages are archived out of the live context until it fits — they are still
  summarized by the nightly roll on their normal schedule and their raw files are retained.
- **Archive (of a message/session)**: a move on disk (`rename`) to a retained location
  (`data/sessions/expired/YYYY-MM-DD/…` or an equivalent per-message archive path). Never a
  delete. The raw content remains on disk and auditable indefinitely.
- **One-time prod migration**: an operator-run, separately-approved script that creates daily
  summaries for every non-empty calendar day of prod history older than 14 days, writing roll
  markers as it goes, so the periodic model starts with no Tier-2 gap. A real prod data write and
  real billed OpenAI calls.
- **Log retention (rotation with on-disk copies)**: the property that the application log file may
  be rotated by size or age, but every rotated segment is kept as a file on disk (compressed is
  fine), so the full application-log history since go-live remains reconstructable — as opposed to
  Docker's `json-file` driver silently dropping the oldest chunk.
- **bugfix-035 H1 / H2 / H3**: the three prerequisite defects — H1: group-chat collection naming +
  self-corrupting verify step + unbounded retry; H2: intolerant `Session` deserialization; H3:
  `expired/` accumulating unbounded across runs (also surfacing as a test-isolation failure).
- **bugfix-044**: the prerequisite defect where a recovered session is not re-registered as its
  chat's active session after a restart, so the next message discards it.

## Technology Choices

- **Scheduling**: the existing `APScheduler` `BackgroundScheduler` pattern already used by
  `services/reminder_delivery_service.py` (`CronTrigger`) and
  `services/accounting_reconciliation_service.py` (`IntervalTrigger`). The nightly roll is
  wall-clock-anchored → `CronTrigger(hour=2, minute=0)` in Israel local time. One shared scheduler
  job, wired in `denidin.py`'s `initialize_app` alongside the existing schedulers. No new
  scheduling technology.
- **Time**: `now_local()` / the `Asia/Jerusalem`-aware helpers in `apps/denidin-app/src/utils/time_utils.py`.
  "Calendar day" and "14 days" are both evaluated in Israel local time. No UTC anywhere.
- **Short-term storage**: the existing on-disk session/message JSON layout under `data/sessions/`.
  The window is computed from message timestamps already persisted per message; no new datastore.
- **Long-term storage**: the existing `MemoryManager` / ChromaDB collections and OpenAI embeddings
  (`config.ai_embedding_model`). Daily summaries are ordinary `remember()` writes with richer
  metadata; recall is the existing semantic `recall()` path. No schema-version bump to
  `LedgerEventManager` (this feature does not touch the ledger).
- **Roll markers**: a durable, per-(chat, date) record. Concrete storage (a markers file under
  `data/`, a metadata flag on the daily-summary record, or a small index) is a `plan.md`
  decision; the requirement is only that it survives restarts and is checked by all three roll
  paths. [NEEDS CLARIFICATION: see FR-MEM-053.]
- **Config**: new keys under the existing `memory` block and a `config.feature_flags` flag. No env
  vars.
- **Migration & log-retention verification**: standalone operator scripts under `scripts/` /
  `apps/denidin-app/scripts/`, following the Feature 061/062 backfill-script conventions (explicit
  CLI args, no hardcoded dates, idempotent, real credentials never committed).
- **Third-party behavior that MUST be verified against a real call before design is finalized**
  (CONSTITUTION "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS"):
  - `gpt-5.6-luna`'s real usable context-window size and token pricing — the 14-day verbatim
    window's worst-case size must be shown to fit with margin, against confirmed numbers, not
    assumed ones. (Real prod measurement to date: group chat full history ≈ 62K tokens over the
    whole Aug 5–Sep 1 life; growth ≈ 2,200 tokens/day; a 14-day window is a fraction of that — but
    the model's confirmed limits are still the load-bearing check.)
  - OpenAI automatic prompt-caching behavior on the new prompt shape (constitution prefix stable;
    the 14-day window stable between nightly rolls) — confirm the cache actually engages as
    expected rather than assuming it.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Group-chat long-term memory transfer actually completes (Priority: P1)

Fixes bugfix-035 H1. Today, long-term-memory transfer for any group chat (`…@g.us`) can never
succeed: the collection name keeps its raw `@`, the post-write verify step calls the underlying
Chroma client with the unsanitized name and throws `NotFoundError`, and the broad `except` reports
a succeeded write as failed. The session is never marked `transferred_to_longterm`, so the hourly
sweep reprocesses it forever — a fresh billed OpenAI summary and a duplicate ChromaDB record every
hour.

**Why this priority**: It is actively accruing unbounded OpenAI cost and polluting the primary
production channel's semantic memory right now. The new model leans entirely on daily summaries
reaching Tier-2 reliably — building US4/US5 on top of a transfer path that silently fails for the
main prod chat would ship the same bug in new packaging. This is a hard prerequisite.

**Independent Test**: With the feature flag OFF, drive a real group-chat webhook through
`bot.router` into a session, expire it, run the cleanup sweep, and assert: the daily/long-term
record is queryable via `MemoryManager.recall()`, the session is marked `transferred_to_longterm`,
and a second sweep does **not** produce a second summary or a second billed call.

**Acceptance Scenarios**:

1. **Given** a group chat `…@g.us` with a completed session, **When** long-term transfer runs,
   **Then** the summary is written to and retrievable from that chat's collection, and the session
   is marked transferred.
2. **Given** a transfer that has already succeeded once, **When** the next hourly sweep runs,
   **Then** the session is skipped — no new summary, no new billed OpenAI call, no duplicate
   record.
3. **Given** a transfer that genuinely fails N consecutive times, **When** the retry budget is
   exhausted, **Then** it stops retrying, the failure is surfaced as a distinct visible signal
   (dead-letter / error state), and it is not retried again until that state is cleared.
4. **Given** the existing recall path for a group chat, **When** it runs after the fix, **Then**
   it still resolves the same collection (no regression to reads, which already work via the
   sanitizing wrapper).

---

### User Story 2 - A session with an unknown persisted field still loads (Priority: P1)

Fixes bugfix-035 H2. Session `0f5eaa04` was persisted on 2026-08-03 with a `pending_ledger_events`
field the current `Session` model no longer accepts. `Session(**data)` raises
`__init__() got an unexpected keyword argument 'pending_ledger_events'`, so the session can never
be loaded, expired, archived, or transferred — it logs an error every hourly sweep, on every load,
and on every orphan-recovery pass, indefinitely, and is why the "N expired sessions" startup count
can never fully clear.

**Why this priority**: The rolling window and the nightly roll both iterate persisted sessions/
messages. A single poison record that hard-fails deserialization can wedge the sweep or the
window-builder for a whole chat. Any future field rename strands every session written before it
in exactly the same way unless deserialization is made tolerant now.

**Independent Test**: Persist a `session.json` containing an extra unknown key, then load it via
the real `SessionManager` (no mocks). Assert it loads, the unknown key is ignored (and logged once
as a warning, not an error), the session participates normally in window-building and the nightly
roll, and no `TypeError` is raised anywhere in the lifecycle.

**Acceptance Scenarios**:

1. **Given** a persisted session with an unknown top-level field, **When** `SessionManager` loads
   it, **Then** it deserializes successfully, the unknown field is dropped, and one warning
   (not error) is logged.
2. **Given** that same session, **When** the nightly roll and the cleanup sweep run, **Then** it
   is processed like any other session — no permanent-stuck state, no per-run error log line.
3. **Given** a future field is removed from the `Session` model, **When** sessions written before
   the removal are loaded, **Then** they still load (same tolerance), rather than every one of
   them becoming permanently unloadable.

---

### User Story 3 - Conversation context survives an app restart (Priority: P1)

Fixes bugfix-044. After a restart, orphaned-session recovery reloads a chat's active session and
logs success, but does not register it into the `chat_to_session` index that
`SessionManager` consults for "is there an active session for this chat?" — so the next inbound
message for that chat creates a brand-new empty session and discards the recovered context. A
second contributing defect: `remove_from_index()` deletes the index entry for a chat without first
checking that the entry actually points at the session being removed, so it can evict a *different*
(newer) session's registration for the same chat.

**Why this priority**: Under the new model the "active session" concept is subsumed by the rolling
window, but the same index and the same recovery path still decide which on-disk session new
messages append to. If recovery doesn't re-register, every restart still silently starts a fresh
empty session and the 14-day window's most recent day is orphaned. This must be correct before the
window is layered on.

**Independent Test**: Build a session for a chat, simulate a restart (fresh `SessionManager` +
run `recover_orphaned_sessions()`), then dispatch a new inbound webhook for the same chat through
`bot.router`. Assert the new message appends to the recovered session (not a new one), and the
prior messages are in context. Separately: register session A for a chat, then register session B
for the same chat, then `remove_from_index(A)`; assert B's registration survives.

**Acceptance Scenarios**:

1. **Given** an app restart with an orphaned active session for chat C, **When** recovery runs,
   **Then** chat C's active-session lookup resolves to the recovered session.
2. **Given** the recovered session for chat C, **When** the next inbound message for C arrives,
   **Then** it appends to the recovered session and the earlier turns are present in context —
   no new empty session is created.
3. **Given** `chat_to_session[C]` points at session B, **When** `remove_from_index` is called for
   a stale session A (also for chat C), **Then** the index still maps C → B afterward.
4. **Given** startup ordering, **When** the cleanup sweep and orphan recovery both run at boot,
   **Then** their order does not leave a chat with neither an archived-and-transferred session nor
   a registered active one.

---

### User Story 4 - The last 14 days of messages are always in verbatim context (Priority: P2)

The core capability. Regardless of session boundaries or idle gaps, every turn's context includes
every message (per chat) from the last 14 calendar days (Israel local), verbatim, in order, with
the Feature 039 `[sender_name]` prefixing preserved for group turns. There is no 24-hour idle
expiry any more.

**Why this priority**: This is the feature. It depends on US1-US3 being correct (reliable
transfer, tolerant load, restart-safe active session) but delivers the user-visible value: the bot
stops "forgetting" a conversation that paused for a day, and multi-day context is always present
without relying on semantic recall to reconstruct it.

**Independent Test**: Seed a chat with messages dated 20, 15, 13, 2, and 0 days ago. Build the
turn context via the real code path. Assert the 13/2/0-day messages are present verbatim and in
order; the 20/15-day messages are not in the verbatim window (they are represented by daily
summaries instead — see US5). With the feature flag OFF, assert the context is byte-for-byte the
current session-scoped behavior.

**Acceptance Scenarios**:

1. **Given** messages spanning 30 days for a chat, **When** a new turn is processed, **Then**
   exactly the messages from the last 14 days are in the verbatim window, oldest-first.
2. **Given** a chat that has been idle for 3 days, **When** a new message arrives, **Then** the
   prior conversation (still within 14 days) is fully in context — no "new session, no memory"
   behavior.
3. **Given** a group chat, **When** the window is built, **Then** user turns carry the
   `[sender_name]` prefix exactly as today.
4. **Given** the feature flag is OFF, **When** any turn is processed, **Then** behavior is
   identical to the pre-feature session-scoped model (byte-for-byte).
5. **Given** the window is built on every turn, **When** measured, **Then** the added latency and
   the added token count per turn are within the Success Criteria bounds.

---

### User Story 5 - Each night the previous day is summarized into long-term memory (Priority: P2)

At 02:00 Israel local, for each chat, the previous calendar day's messages are summarized into
**exactly one** daily long-term record (chat + date keyed), embedded, and stored. Empty days
produce nothing (no record, no billed call). The job is idempotent per (chat, date) via a roll
marker. A startup catch-up sweep rolls any (chat, date) pairs missed while the app was down.

**Why this priority**: Without the nightly roll, days that scroll out of the 14-day window would
have no Tier-2 representation at all — the exact "silent hole" failure the current model already
has for always-active chats. It is P2 (not P1) only because US4 delivers value on its own for the
first 14 days; the roll becomes load-bearing as history ages past two weeks.

**Independent Test**: Seed two chats with messages across three past calendar days (one day empty
for one chat). Run the roll job for those dates. Assert: exactly one daily summary per non-empty
(chat, date); zero for the empty one; each summary retrievable via `recall()` with correct
chat/date metadata; a re-run produces no new summaries and no new billed calls. Then simulate a
2-day downtime and assert the startup catch-up sweep rolls exactly the missed days, once each.

**Acceptance Scenarios**:

1. **Given** chat C has messages on calendar day D, **When** the nightly roll runs for D, **Then**
   exactly one daily summary for (C, D) is stored and a roll marker for (C, D) is recorded.
2. **Given** chat C has no messages on day D, **When** the roll runs for D, **Then** no summary
   is created, no OpenAI call is made, and (C, D) is marked rolled (so it is not retried).
3. **Given** (C, D) already has a roll marker, **When** the roll job or the catch-up sweep runs
   again, **Then** it is skipped — no second summary, no second billed call.
4. **Given** the app was down across days D1 and D2, **When** it starts, **Then** the catch-up
   sweep rolls (C, D1) and (C, D2) exactly once each before normal operation resumes.
5. **Given** a daily summary exists for (C, D), **When** a user later asks a question whose answer
   is in day D (now outside the 14-day window), **Then** semantic recall surfaces that day's
   summary into context.
6. **Given** the roll job fails partway (e.g. OpenAI error) for one (chat, date), **When** it next
   runs, **Then** it retries that (chat, date) with a bounded budget and does not mark it rolled
   until it actually succeeds.

---

### User Story 6 - Raw messages are never deleted, and context never blows the token budget (Priority: P2)

Two guarantees. (a) A message aging past the 14-day window, or being trimmed by the token/size
backstop, is **archived** (moved on disk to a retained path) — never `unlink()`-ed. The current
live deletion path (`_prune_until_under_limit`, which `unlink()`s message files) is replaced by
archive-only trimming. (b) The verbatim window is bounded by "last 14 days OR last N tokens,
whichever is smaller"; when 14 days exceeds N tokens, the oldest in-window messages are archived
out of the live context (still summarized on their normal nightly schedule).

**Why this priority**: The user's explicit precondition for approving this whole feature was that
all raw data is preserved. A rolling window that quietly deletes to stay under a token cap would
reintroduce exactly the "messages dropped with no summary" failure. It is P2 because it is a
safety property of US4/US5, not a standalone journey.

**Independent Test**: Configure a deliberately tiny token backstop. Seed a chat with more in-window
messages than the backstop allows. Build the context. Assert: the live window is trimmed to fit
the backstop; every trimmed message's raw file still exists (at its archive path); the trimmed
messages are still picked up by the nightly roll for their day. Separately, audit that no code
path in the feature calls `unlink()` / `Path.unlink` / equivalent on a message or session file.

**Acceptance Scenarios**:

1. **Given** a message older than 14 days, **When** the window is rebuilt, **Then** it is archived
   (present at a retained on-disk path), not deleted.
2. **Given** the 14-day window exceeds the token backstop for a chat, **When** context is built,
   **Then** the oldest messages are archived out until it fits, and the backstop is respected.
3. **Given** any message trimmed for the backstop, **When** its day's nightly roll runs, **Then**
   that message is still included in the day's summary.
4. **Given** the whole feature's code, **When** audited, **Then** there is no live path that
   deletes a persisted message or session file — only archive/move.
5. **Given** `expired/` (bugfix-035 H3), **When** archives accumulate over many runs, **Then**
   there is a confirmed retention/bound policy for `expired/YYYY-MM-DD/` (documented, even if the
   bound is "keep everything, forever, by design"), and the test suite scopes its archived-session
   lookups to the session it created rather than `rglob(...)[0]`.

---

### User Story 7 - A one-time migration backfills daily summaries for pre-window history (Priority: P3)

An operator-run, separately-approved script creates one daily summary per non-empty calendar day
for all prod history older than 14 days (bot went live 2026-08-05), writing a roll marker for each
(chat, date) as it goes, so the periodic model starts with a complete Tier-2 record and the
nightly job never re-summarizes those days.

**Why this priority**: Needed exactly once, for prod, before the feature flag is turned on there.
It is P3 because the feature is buildable and testable in dev without it, and because it is a
separately-gated real-prod-write action that happens outside the normal implement flow.

**Independent Test** (dev/sandbox, real code, real billed calls): Point the script at a dev chat
with >14 days of seeded history. Run it. Assert: one daily summary per non-empty past day; roll
markers written for every processed (chat, date) including empty ones; a re-run is a no-op (no new
summaries, no new billed calls); after the run, the nightly job and catch-up sweep both skip every
migrated day; the 14-day verbatim window is unchanged by the migration.

**Acceptance Scenarios**:

1. **Given** prod history from 2026-08-05 to (today − 14d), **When** the migration runs, **Then**
   every non-empty calendar day in that range has exactly one daily summary and a roll marker.
2. **Given** the migration has completed, **When** it is run a second time, **Then** it makes no
   OpenAI calls and writes no new records (idempotent via roll markers).
3. **Given** the migration has completed, **When** the feature flag is enabled in prod and the
   nightly job first runs, **Then** it processes only genuinely un-rolled days (i.e. from the
   migration cutoff forward) and never re-summarizes a migrated day.
4. **Given** the migration is a real prod write, **When** it is initiated, **Then** it requires
   fresh explicit human approval for that specific run, and does not run as a side effect of
   deploying or enabling the feature.
5. **Given** raw messages, **When** the migration runs, **Then** it only reads them — no message
   or session file is moved or deleted by the migration.

---

### User Story 8 - Prod application logs are retained across rotation (Priority: P3)

Verify (and, if needed, configure) that the prod application log (`logs/denidin.log` and the
morning-mcp-app equivalent) is rotated by size or age but **every rotated segment is kept on
disk** — so the full application-log history since 2026-08-05 remains reconstructable. Docker's
`json-file` log driver rotation (which drops the oldest chunk) is not the system of record.

**Why this priority**: The user asked for it explicitly alongside the raw-message guarantee — the
same "never silently lose the audit trail" principle applied to logs. It is P3 because it is a
verification/config task, not application logic, and does not block US4/US5.

**Independent Test**: Inspect the current logging configuration (app-level handler + Docker log
driver options) and the prod box's on-disk log directory. Produce a written finding: what rotates
what, by what trigger, and whether rotated segments are retained. If retention is not guaranteed,
specify the minimal config change (e.g. a `RotatingFileHandler` / `TimedRotatingFileHandler` with
`backupCount` high enough to never drop, or logrotate with no `rotate` cap / an archive dir), and
verify the change keeps segments after a forced rotation.

**Acceptance Scenarios**:

1. **Given** the current prod logging setup, **When** it is audited, **Then** there is a written
   statement of the rotation trigger(s) and whether every rotated segment is retained on disk.
2. **Given** rotation by size or age is configured, **When** a rotation occurs, **Then** the
   pre-rotation content still exists as an on-disk file (optionally compressed), not discarded.
3. **Given** the application-log history since go-live, **When** any past date is requested,
   **Then** that date's application log lines are retrievable from disk (subject only to a
   documented, deliberate retention bound — not silent loss).
4. **Given** the Docker `json-file` driver is still in use for `docker logs`, **When** it rotates,
   **Then** that loss is acceptable *only because* the app-level file handler retains the full
   history independently.

---

### Edge Cases

- **DST transition on a roll night.** 02:00 Israel local on a spring-forward night may not exist;
  on a fall-back night it occurs twice. The `CronTrigger` must fire exactly once and the
  "previous calendar day" boundary must stay well-defined. [Covered by FR-MEM-032.]
- **A message whose timestamp is exactly on the 14-day boundary**, or exactly at midnight between
  two calendar days — inclusive/exclusive rules must be explicit and consistent between the
  window-builder and the roll job (a message must belong to exactly one day and be either in the
  window or summarized, never both, never neither).
- **A pre-2026-08-10 message with a `+00:00` timestamp** (written before the Israel-local switch).
  Both sides are timezone-aware; the day-bucketing must convert to Israel local consistently.
- **Clock skew / a message timestamped in the future.** The window-builder must not crash or
  exclude everything.
- **The roll job runs while a message for "yesterday" is still arriving at 02:00:00.** Define the
  cutoff so a late-night message is attributed to exactly one day and not lost between the window
  and the summary.
- **A chat with zero messages ever.** No window, no roll, no error.
- **ChromaDB collection does not exist yet for a chat** (first-ever daily summary) — must create,
  not fail (the H1 fix must cover the create path too).
- **The app is down for longer than 14 days.** The catch-up sweep must roll every missed day, and
  days with no retained raw messages (if any were archived to cold storage) must be handled by a
  defined rule, not a crash. [NEEDS CLARIFICATION: see FR-MEM-054.]
- **Two app instances / a manual script and the scheduler racing on the same (chat, date).** The
  roll marker check-and-write must be safe against a double roll (idempotent even under a race).
- **Feature flag flipped OFF after some daily summaries already exist.** Recall must not break;
  the system falls back cleanly to session-scoped behavior without the daily summaries causing
  errors.
- **The token backstop is set smaller than a single day's messages.** The window must still
  contain at least the most recent messages and must not loop forever archiving.
- **bugfix-035 H2 poison session encountered mid-roll.** One unloadable session must not abort the
  whole night's roll for other chats.

## Requirements *(mandatory)*

### Functional Requirements — Prerequisite bug fixes (User Stories 1-3)

- **REQ-MEM-001**: Long-term-memory transfer MUST derive the ChromaDB collection name for a chat
  using the same sanitization the write path uses, for **all** chat-id shapes (`@c.us`, `@g.us`,
  and any other suffix), so group chats resolve to a valid collection. (bugfix-035 H1 bug 1)
- **REQ-MEM-002**: The post-write "verify" step MUST either use the identical name resolution as
  the write, or be removed entirely if `remember()` already returns a durable id that proves the
  write. It MUST NOT call the underlying Chroma client with an unsanitized name. (bugfix-035 H1
  bug 2)
- **REQ-MEM-003**: A transfer that has actually succeeded MUST mark the session
  `transferred_to_longterm` and MUST NOT be reprocessed by a later sweep.
- **REQ-MEM-004**: Transfer retries MUST be bounded (defined budget + backoff). On budget
  exhaustion the transfer MUST stop, record a distinct dead-letter / failure state, and emit a
  visible signal; it MUST NOT silently retry forever.
- **REQ-MEM-005**: The recall path's collection-name derivation MUST be fixed to match (no
  regression; reads already work via the sanitizing wrapper, but both derivations must be
  consistent).
- **REQ-MEM-010**: `SessionManager` session deserialization MUST tolerate unknown persisted
  top-level fields — ignore them (mirroring `denidin.py`'s `valid_fields` filter pattern) and log
  **one warning** (not an error), rather than raising `TypeError`. (bugfix-035 H2)
- **REQ-MEM-011**: A session with an unknown persisted field MUST participate normally in every
  lifecycle step (load, window inclusion, nightly roll, archive) after the tolerance fix.
- **REQ-MEM-012**: The tolerance MUST be general (any unknown key), so a future field removal does
  not strand previously-persisted sessions.
- **REQ-MEM-020**: Orphaned-session recovery MUST register each recovered active session into the
  index/lookup that `SessionManager` consults for "active session for this chat" (`chat_to_session`
  or its successor), so the next inbound message for that chat continues the recovered session.
  (bugfix-044 RC4)
- **REQ-MEM-021**: `remove_from_index()` MUST remove a chat's index entry **only if** that entry
  currently points at the session being removed — never evict a different (e.g. newer) session's
  registration for the same chat. (bugfix-044 RC3)
- **REQ-MEM-022**: Startup ordering of the cleanup sweep and orphan recovery MUST NOT leave a chat
  with neither a completed transfer nor a registered active session. The ordering MUST be
  explicit and documented.
- **REQ-MEM-023**: `expired/YYYY-MM-DD/` MUST have a documented retention/bound policy (bugfix-035
  H3). The test suite MUST scope archived-session lookups to the session under test (not
  `rglob(...)[0]`).

### Functional Requirements — Rolling window (User Story 4)

- **REQ-MEM-030**: With the feature flag ON, the per-turn conversation context MUST include every
  message for the chat whose timestamp falls within the last 14 calendar days (Israel local),
  verbatim, oldest-first, subject only to the token backstop (REQ-MEM-040).
- **REQ-MEM-031**: With the feature flag ON, there MUST be no 24-hour idle session expiry; a chat
  idle for up to 14 days retains full verbatim context.
- **REQ-MEM-032**: "Last 14 days" and "calendar day" MUST be evaluated in Israel local time via
  `time_utils`, with explicit, documented inclusive/exclusive boundary rules, correct across DST
  transitions, and consistent with the roll job's day-bucketing (REQ-MEM-050) — every message
  belongs to exactly one day and is either in the window or summarized, never both or neither.
- **REQ-MEM-033**: Group-chat user turns in the window MUST retain the Feature 039 `[sender_name]`
  prefix.
- **REQ-MEM-034**: With the feature flag OFF, the conversation-context code path MUST be
  byte-for-byte identical to the pre-feature session-scoped behavior.
- **REQ-MEM-035**: The window MUST be built from messages already persisted per message (their
  existing timestamps); no new per-message datastore.
- **REQ-MEM-036**: The window-builder MUST tolerate clock skew / future-dated messages and an
  unloadable (H2-poison) session without crashing or emptying the window.

### Functional Requirements — Nightly roll (User Story 5)

- **REQ-MEM-040**: A single `APScheduler` `CronTrigger` job MUST run at 02:00 Israel local time,
  wired in `denidin.py`'s `initialize_app` alongside the existing schedulers, gated by the feature
  flag.
- **REQ-MEM-041**: For each chat, the roll MUST summarize the previous calendar day's messages
  into **exactly one** daily long-term record, embedded and stored via `MemoryManager`, with
  metadata including at least the chat id and the summarized calendar date.
- **REQ-MEM-042**: A calendar day with zero messages for a chat MUST produce no summary and no
  OpenAI call, and MUST still be marked rolled (so it is never retried).
- **REQ-MEM-043**: The roll MUST be idempotent per (chat, date) via a roll marker checked before
  any OpenAI call; a re-run or catch-up pass MUST NOT create a second summary or make a second
  billed call for an already-rolled (chat, date).
- **REQ-MEM-044**: A roll marker for a non-empty (chat, date) MUST be written **only after** the
  daily summary is durably stored — a mid-roll failure MUST leave (chat, date) un-rolled for a
  bounded retry, not falsely marked done.
- **REQ-MEM-045**: The check-and-write of a roll marker MUST be safe against concurrent rollers
  (scheduler + manual script) — no double summary under a race.
- **REQ-MEM-046**: One unloadable or erroring chat/session MUST NOT abort the roll for other
  chats; per-chat failures are isolated and retried with a bounded budget.
- **REQ-MEM-050**: A startup catch-up sweep MUST, on app start, roll every (chat, date) pair that
  is older than "yesterday", has no roll marker, and is not otherwise covered — exactly once each
  — before or concurrently with normal operation, without blocking message handling
  indefinitely. [NEEDS CLARIFICATION: see FR-MEM-054 for the >14-day-outage / archived-raw case.]
- **REQ-MEM-051**: Daily summaries MUST be retrievable through the existing semantic `recall()`
  path so a question about a day now outside the 14-day window surfaces that day's summary.
- **REQ-MEM-052**: This feature MUST NOT change `LedgerEventManager.CURRENT_SCHEMA_VERSION` or any
  ledger schema (it does not touch the ledger).
- **REQ-MEM-053**: [NEEDS CLARIFICATION] Roll-marker storage mechanism — a dedicated markers file
  under `data/`, a queryable flag on the daily-summary record, or a small index — to be decided in
  `plan.md`. Requirement: survives restarts; checked identically by the nightly job, the catch-up
  sweep, and the one-time migration.
- **REQ-MEM-054**: [NEEDS CLARIFICATION] Behavior when a (chat, date) needs rolling but its raw
  messages are no longer available in hot storage (e.g. outage longer than any hot-retention
  bound, or raw archived to cold storage) — summarize from whatever is retained, skip with a
  visible warning, or is this impossible by construction because raw is never deleted? Depends on
  the `expired/` retention decision (REQ-MEM-023).

### Functional Requirements — Raw-data & token safety (User Story 6)

- **REQ-MEM-060**: No code path introduced or modified by this feature may delete a persisted
  message or session file. Aging out of the window and token-backstop trimming MUST both be
  archive-only (move/rename to a retained path).
- **REQ-MEM-061**: The existing live deletion path `_prune_until_under_limit` (and any other
  `unlink()` of message files) MUST be replaced with archive-only trimming when the feature flag
  is ON. With the flag OFF, existing behavior is unchanged (REQ-MEM-034).
- **REQ-MEM-062**: The verbatim window MUST be bounded by "last 14 days OR last N tokens,
  whichever is smaller". When 14 days exceeds N tokens, the oldest in-window messages are archived
  out of the live context until it fits. [NEEDS CLARIFICATION: value of N — see FR list note; a
  candidate is the current godfather `max_tokens_by_role` 100000, or lower.]
- **REQ-MEM-063**: A message trimmed by the token backstop MUST still be included in its calendar
  day's nightly roll summary.
- **REQ-MEM-064**: `gpt-5.6-luna`'s confirmed usable context window MUST be shown (against a real
  verified figure) to accommodate the worst-case 14-day window plus constitution plus tools plus
  reply headroom, with margin, before implementation is considered complete. Unverified model
  limits MUST NOT be built on (CONSTITUTION).
- **REQ-MEM-065**: `expired/YYYY-MM-DD/` growth MUST be bounded by the documented policy from
  REQ-MEM-023; whatever the bound, it MUST NOT be silent deletion of the only copy of a message.

### Functional Requirements — One-time prod migration (User Story 7)

- **REQ-MEM-070**: The migration MUST be a standalone operator script (Feature 061/062
  conventions: explicit CLI args, no hardcoded dates, real credentials never committed).
- **REQ-MEM-071**: The migration MUST create exactly one daily summary per non-empty calendar day
  of history older than 14 days, and write a roll marker for every processed (chat, date)
  including empty ones.
- **REQ-MEM-072**: The migration MUST be idempotent — a second run makes no OpenAI calls and
  writes no new records, via the same roll markers the nightly job uses.
- **REQ-MEM-073**: After the migration, the nightly job and catch-up sweep MUST skip every
  migrated day and only process genuinely un-rolled days forward.
- **REQ-MEM-074**: The migration MUST only read raw messages — it MUST NOT move, archive, or
  delete any message or session file.
- **REQ-MEM-075**: Running the migration against real prod data MUST require fresh, explicit human
  approval for that specific run, independent of feature-build approval and independent of any
  deploy. It MUST NOT run as a side effect of a deploy or of enabling the feature flag.
- **REQ-MEM-076**: The migration MUST produce a written run report (per chat: days processed,
  summaries created, days skipped-empty, billed-call count) for human review.

### Functional Requirements — Log retention (User Story 8)

- **REQ-MEM-080**: The current prod logging configuration (app-level handler + Docker log driver
  options) MUST be audited and documented: what rotates, by what trigger (size / age), and whether
  every rotated segment is retained on disk.
- **REQ-MEM-081**: The application log MUST be configured so that rotation by size or age keeps
  every rotated segment as an on-disk file (compression allowed); silent discard of the oldest
  segment is not acceptable as the system of record.
- **REQ-MEM-082**: If the current config does not guarantee retention, the minimal config change
  MUST be specified and verified (force a rotation, confirm the prior segment persists on disk).
- **REQ-MEM-083**: The `json-file` Docker driver's lossy rotation is acceptable for `docker logs`
  convenience **only** because the app-level file handler independently retains full history
  (REQ-MEM-081); this dependency MUST be stated in the runbook.
- **REQ-MEM-084**: Any deliberate retention bound (app logs and `expired/` archives alike) MUST be
  documented as a conscious decision, not left implicit.

### Feature-flag & config requirements

- **REQ-MEM-090**: All new behavior MUST sit behind `config.feature_flags.<flag>` (name TBD in
  plan), default `false`. Flag OFF ⇒ code path byte-for-byte identical to pre-feature.
- **REQ-MEM-091**: New tunables (14-day window length, token backstop N, catch-up lookback,
  retry budgets, roll hour) MUST be config keys under the existing `memory` block with documented
  defaults — no magic numbers, no env vars.
- **REQ-MEM-092**: Unit tests MAY set the flag; integration tests MUST NOT (they test default
  production behavior) — so integration coverage of the new model requires the flag to become the
  default only after sign-off, or dedicated `billed` acceptance tests that exercise it explicitly.
  [Confirm approach in plan.]

## Key Entities

- **Rolling window**: derived, not stored. Per chat: the ordered list of messages with
  Israel-local timestamp within the last 14 calendar days, capped by the token backstop.
- **Daily summary**: one ChromaDB record. Attributes: summary text, embedding, chat id,
  summarized calendar date, message count, created-at (Israel local), source = "daily-roll" or
  "migration". Replaces the "per-expired-session summary" as the unit of Tier-2 memory.
- **Roll marker**: durable per-(chat, date) record meaning "this day is rolled — do not
  summarize again". Written by the nightly job, catch-up sweep, and migration.
- **Archived message / archived session**: a message or session file moved (never deleted) to a
  retained path when it ages past the window or is trimmed by the backstop.
- **Transfer dead-letter state**: a distinct, visible state for a long-term transfer that has
  exhausted its retry budget (bugfix-035 H1).
- **Log segment**: a rotated slice of the application log, retained on disk (bugfix-...
  User Story 8).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any prod chat, after a pause of up to 14 days, the bot's next reply demonstrably
  uses context from before the pause — 0 occurrences of "new session, context lost" for gaps ≤ 14
  days.
- **SC-002**: Group-chat long-term-memory transfer completes successfully on the first attempt;
  the count of repeated hourly re-summarizations of the same session drops to 0, and the count of
  duplicate summary records for one session stays at 1.
- **SC-003**: Billed OpenAI summarization calls attributable to memory settle at **≤ 1 per chat
  per active calendar day** (down from unbounded hourly retries + per-session bursts).
- **SC-004**: 100% of messages that age past the 14-day window, or are trimmed by the token
  backstop, still exist on disk at a retained path — verified by a file-integrity audit
  (counters == id-lists == files-on-disk, extended to include archived paths). 0 message files
  deleted.
- **SC-005**: Every non-empty calendar day since 2026-08-05, per prod chat, has exactly one daily
  summary retrievable via `recall()` after the migration — 0 gaps, 0 duplicates.
- **SC-006**: A restart followed by a new inbound message continues the pre-restart session in
  100% of cases (0 orphaned recovered sessions that are never used).
- **SC-007**: Added per-turn latency from building the 14-day window is ≤ 150 ms p95 over the real
  prod message mix; added per-turn input tokens are within the confirmed model context budget with
  ≥ 30% headroom.
- **SC-008**: A session persisted with an unknown field loads with 0 `TypeError`s and exactly 1
  warning log line; the per-hour recurring error for the known poison session goes to 0.
- **SC-009**: After a forced log rotation on the prod box, the pre-rotation log content is still
  retrievable from an on-disk file — 100% of rotations retain their prior segment.
- **SC-010**: Re-running the nightly roll, the catch-up sweep, or the one-time migration over an
  already-rolled range produces 0 new summaries and 0 new billed calls.
- **SC-011**: With the feature flag OFF, the full existing test suite passes unchanged and the
  conversation-context output is byte-for-byte identical to pre-feature.

## Out of Scope

- Changing the embedding model, the semantic-recall scoring (`top_k_results`, `min_similarity`),
  or the "RECALLED MEMORIES" prompt block format — except any `top_k` adjustment that
  `speckit.clarify`/`plan` determines is required for multi-week questions (flag it there; do not
  assume it here).
- Purging the 27 existing duplicate records in `memory_120363210094632983_at_g.us` — that is a
  separate prod data write needing its own approval (bugfix-035 "Prod cleanup" note).
- Any change to the Morning/ledger subsystems.
- Migrating existing pre-2026-08-10 `+00:00` timestamps (they compare correctly as-is).
- Cold-storage / offsite backup of archived messages beyond the on-disk retained path.
- Deploying the feature or enabling the flag in any environment — always a separate explicit human
  decision.

## Dependencies & Assumptions

- **Prerequisite bug fixes** (US1-US3) go through Bug-Driven Development (METHODOLOGY §VII): each
  root cause needs explicit human approval before test-gap analysis. The root causes are drafted
  in `specs/bugfixes/bugfix-035-*` and `specs/bugfixes/bugfix-044-*`; this spec assembles them as
  prerequisites but does not bypass their approval gate.
- **Raw-data preservation is already verified** (2026-09-01 audit): the only live deletion path
  (`_prune_until_under_limit`) has provably never fired in prod (monotonic `message_counter` ==
  `len(message_ids)` == files-on-disk for all 90 sessions); `clear_session`/`prune_to_limit` have
  zero callers; `archive_session` is a `rename`. This feature must keep it that way.
- **Two prod chats only** (`120363210094632983@g.us`, `972522968679@c.us`); go-live 2026-08-05.
  The migration's real scope is small (~2-3 weeks × 2 chats).
- **`gpt-5.6-luna` context/pricing** and **OpenAI prompt-cache behavior on the new prompt shape**
  are unverified third-party facts and MUST be confirmed against real calls before the design is
  locked (CONSTITUTION).
- Prod is on the always-on Windows box (Feature 035); log-retention verification uses the existing
  read-only mount / `tail_logs.sh` paths and, for any config change, the normal deploy flow (not
  part of this feature).
