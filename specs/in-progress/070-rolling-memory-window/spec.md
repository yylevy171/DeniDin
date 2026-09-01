# Feature Specification: Rolling 14-Day Short-Term Memory Window with Nightly Daily-Summary Roll

**Feature Branch**: `feature/070-rolling-memory-window`
**Created**: 2026-09-01
**Status**: Draft — pending `speckit.clarify`
**Input**: User description: Replace the 24-hour session-expiry memory lifecycle with a rolling
14-day verbatim short-term window plus a nightly 2am (Israel local) roll that summarizes the
previous calendar day into long-term memory. Build the new model first; the known legacy defects
(bugfix-035 H1/H2/H3, bugfix-044) are either structurally eliminated by the new architecture or
fixed inline as the new code touches that path — **not** as a separate prerequisite bug-fix phase
("I don't want to waste time fixing something that is then going to be obsolete anyway", user,
2026-09-01). Perform a one-time prod migration to backfill daily summaries for history older than
14 days. Guarantee raw messages are never deleted (only archived). Verify prod application logs
are never lost on rotation.

---

**IMPORTANT**: This spec MUST comply with:

- **CONSTITUTION.md** (§I-III, §V): no environment variables (all config via `AppConfiguration`
  DI); Israel local time everywhere (`now_local()`); `pathlib.Path`; no monkey-patching; ZERO
  MOCKING of internal components (real `SessionManager`/`MemoryManager`/`AIHandler` code paths in
  every test — OpenAI and Green API are the only mockable boundaries, and never inside
  `tests/integration/`); NO UNVERIFIED THIRD-PARTY ASSUMPTIONS; feature-flagged new behavior
  (`config.feature_flags`, default `false`, byte-for-byte identical path when disabled); tests
  immutable once approved.
- **METHODOLOGY.md** (§I, II, VI, VIII, IX, X): spec-first; mandatory `user-stories.md`
  (Given-When-Then, separate file, spec approval BLOCKED without it); Terminology Glossary;
  Technology Choices; Requirement IDs (`REQ-MEM-*` series — a new series, since this is a
  memory-lifecycle change, not a Morning invoicing-logic change); "TDD" = the `billed`
  acceptance tests, described here in plain language, code written and run once at the end.
- **Legacy defects are not a Bug-Driven Development track here.** Per the user's explicit
  direction, this feature does not open separate root-cause-approval gates for bugfix-035 /
  bugfix-044. Instead, §"Legacy Defects and How the New Model Addresses Them" below states, for
  each, whether it is *structurally eliminated* by the redesign or *fixed inline*, and which
  acceptance test proves it. The two bugfix specs get a status note pointing here at haleluya
  time; they are not worked as standalone bugs.
- The root `CLAUDE.md` banners: the **one-time prod migration** (User Story 4) is its own gated
  action requiring fresh, explicit human approval every time it is run, independent of approval to
  build the feature; it performs a real prod data write and real billed OpenAI calls. Deploying
  the feature or enabling its flag in any environment is likewise always a separate explicit human
  decision.

**Required Files**: `user-stories.md` ✅ · `spec.md` (this file) ✅ · `checklists/requirements.md`
✅ · `plan.md` (later) · `tasks.md` (later).

---

## User Stories Reference

**NOTE**: Complete Given-When-Then acceptance criteria live in **`user-stories.md`** (SEPARATE
from this spec). This section is a quick reference only.

| # | Title | Priority | Kind |
|---|---|---|---|
| US1 | The last 14 days of messages are always in verbatim context | P1 | New model (MVP) |
| US2 | Each night the previous day is summarized into long-term memory | P1 | New model |
| US3 | Raw messages are never deleted, and context never blows the token budget | P1 | New model — safety property |
| US4 | A one-time migration backfills daily summaries for pre-window history | P2 | Operational (separately gated) |
| US5 | Prod application logs are retained across rotation | P2 | Operational verification |

Legacy defects (bugfix-035 H1/H2/H3, bugfix-044) are addressed **within** US1-US3, not as their
own stories — see §"Legacy Defects and How the New Model Addresses Them".

---

## Problem Statement

### The current model and why it is being replaced

Today, Tier-1 ("short-term") memory is **session-scoped**. A `Session` is created per chat, holds
its messages verbatim, and **expires after 24 hours of inactivity** (`session_timeout_hours: 24`).
On expiry the hourly `SessionCleanupThread` archives the session, AI-summarizes it (one billed
OpenAI call), embeds the summary, and stores it as **one ChromaDB record per expired session** in
collection `memory_<chat>`. Every inbound message then does a semantic `recall()` over that
collection and injects a "RECALLED MEMORIES" block into the system prompt.

Structural problems with this model, all observed in real production:

1. **Group chats never actually get Tier-2 memory.** The transfer's collection-name derivation
   only strips `@c.us`, so a group chat (`…@g.us`) produces an invalid raw collection name; the
   post-write "verify" step then bypasses the sanitizer and throws `NotFoundError`, so a transfer
   that *actually succeeded* is reported as failed. `transferred_to_longterm` is never set, so the
   hourly sweep reprocesses the session **forever** — a fresh billed OpenAI summary and a
   duplicate ChromaDB record every hour (27 near-identical records for one session as of the
   2026-08-09 review, still growing). *(bugfix-035 H1.)*

2. **A restart can silently discard live conversation context.** After the 2026-08-25 prod
   restart, orphaned-session recovery reloaded the right session (14 messages, from ~12 min
   before the restart) and logged success — but never registered it as the chat's active session,
   so the next inbound message created a brand-new empty session and discarded the recovered
   context. *(bugfix-044.)*

3. **A since-removed field strands old sessions.** Session `0f5eaa04` was persisted 2026-08-03
   with `pending_ledger_events`, a field the current `Session` model rejects. `Session(**data)`
   raises `TypeError`, so it can never be loaded, expired, archived, or transferred, and logs an
   error every hour indefinitely. *(bugfix-035 H2.)*

4. **Summary granularity is arbitrary.** "One summary per expired session" means five short
   evening exchanges produce five thin summaries, while a day-long conversation that never idles
   for 24h produces *zero* summaries and instead silently prunes its oldest messages once the
   godfather 100K-token write-time cap is hit — with no summary of what was dropped. Multi-week
   questions land against a semantic collection whose contents depend on when sessions happened to
   idle out.

### The target model

- **Short-term memory becomes time-scoped, not session-scoped.** Every message from the **last 14
  days** (per chat) is loaded verbatim into context on every turn. No 24-hour idle expiry.
- **A nightly job at 02:00 Israel local time rolls the window.** For each chat, it summarizes
  **the previous calendar day's** messages into **exactly one** long-term (daily) ChromaDB
  record, keyed by chat + date. Empty days are skipped (no record, no billed call). The job is
  idempotent per (chat, date) via a roll marker.
- **A startup catch-up sweep** rolls any (chat, date) pairs that fell outside the window while
  the app was down.
- **Raw messages are never deleted.** Messages that age past the 14-day window are *archived*
  (moved on disk), never `unlink()`-ed. A token/size backstop under the window caps the verbatim
  context; trimming for the backstop also only archives.
- **A one-time prod migration** backfills one daily summary per non-empty calendar day for all
  history older than 14 days (bot went live 2026-08-05).
- **Prod application logs are verified to survive rotation** — rotation by size or age is fine,
  but each rotated segment must be kept on disk.

Since the bot went live 2026-08-05 and there are only two prod chats ever, the end state per
chat is: a 14-day verbatim window plus ~2-3 weeks of daily summaries, growing by one summary per
chat per active day.

---

## Legacy Defects and How the New Model Addresses Them

Per the user's direction, none of these is a standalone bug-fix task. Each is either eliminated by
the new architecture or fixed inline as the new code is written, and each is proven by a named
acceptance test rather than its own regression suite.

| Ref | Defect | Disposition under Feature 070 | Proven by |
|---|---|---|---|
| **bugfix-035 H1** | Group-chat Tier-2 collection name keeps raw `@`; post-write `client.get_collection()` verify with the unsanitized name throws `NotFoundError`; succeeded write reported as failed; hourly re-summarization forever. | **Structurally eliminated.** The per-expired-session transfer invoked by the hourly cleanup (`AIHandler.transfer_session_to_long_term_memory` as a cleanup step) is **retired** under the new model — there is no "expire session → summarize → mark transferred" cycle to loop on. The nightly roll writes *only* via `MemoryManager.remember(collection_name=…)`, which sanitizes on the write path, and does **no** raw `client.get_collection()` verify step (REQ-MEM-011, REQ-MEM-012). Group and 1:1 chats resolve their collection through one shared sanitized helper (REQ-MEM-013). The 27 existing duplicate records are a separate prod cleanup, out of scope (needs its own approval). | AC-1 / US2 group-chat scenario: a `…@g.us` chat's daily summary is stored and retrievable via `recall()`, and a second roll makes no new billed call. |
| **bugfix-035 H2** | `Session(**data)` raises `TypeError` on an unknown persisted key; session permanently unloadable; hourly error log. | **Fixed inline.** The new window-builder and nightly roll both iterate persisted sessions/messages, so tolerant deserialization is on their critical path. `SessionManager` session load filters `data` to known fields (mirroring `denidin.py`'s `valid_fields = {f.name for f in fields(AppConfiguration)}` pattern) and logs one warning for dropped keys (REQ-MEM-020, REQ-MEM-021). Not a separate phase — it lands with the first task that touches session loading. | US1 poison-session scenario + AC-5: a session file with an unknown key loads with 0 `TypeError`, 1 warning, and participates in a roll. |
| **bugfix-035 H3** | `expired/YYYY-MM-DD/` accumulates unbounded across runs; test picks `rglob(...)[0]` and matches a stale archived session. | **Subsumed into US3.** The archive-retention policy (REQ-MEM-034) must be an explicit documented decision (bound or "retain indefinitely by design"); the test suite must scope archived-session lookups to the session under test, not `rglob(...)[0]` (REQ-MEM-035). | US3 scenario 5. |
| **bugfix-044** | Orphan recovery reloads a session and logs success but never registers it into `chat_to_session`; next message creates a new empty session. Also: `remove_from_index()` deletes a chat's entry without checking it points at the session being removed. | **Structurally eliminated (design).** The new model does not rely on an in-memory `chat_to_session` index that a recovery path can forget to populate. "Where does a new inbound message for chat C append?" is answered by a **deterministic on-disk lookup** for C's canonical current message store (`plan.md` decides: one long-lived session per chat found by scanning `whatsapp_chat`, or per-chat message storage) — so a restart cannot leave a recovered store unreferenced (REQ-MEM-014, REQ-MEM-015). The `remove_from_index` guard is included only if an index survives the redesign at all; otherwise it's moot. | US1 restart scenario + AC-2: conversation → simulated restart → next message continues with full pre-restart context, no manual re-priming. |

---

## Terminology Glossary

- **Short-term window / rolling window**: the set of messages, per chat, whose timestamp is
  within the last 14 calendar days (Israel local). Loaded verbatim into the turn context on every
  turn. Replaces "the current session's history".
- **Nightly roll**: the 02:00 Israel-local job that, per chat, summarizes the previous calendar
  day's messages into one daily summary and records a roll marker for that (chat, date).
- **Daily summary**: exactly one AI-generated summary of one chat's messages for one calendar
  day, embedded and stored as one record in that chat's long-term collection, with metadata
  including the chat id and the summarized date. The unit of Tier-2 memory under the new model.
- **Roll marker / idempotency marker**: a durable record that (chat, date) has been rolled. Its
  presence means "do not summarize this (chat, date) again". Checked by the nightly job, the
  startup catch-up sweep, and the one-time migration alike.
- **Startup catch-up sweep**: on app start, rolls every (chat, date) pair that is now older than
  "yesterday", has no roll marker, and is not otherwise covered — days that passed while the app
  was down.
- **Token/size backstop**: a per-chat upper bound on the verbatim window ("the last 14 days, OR
  the last N tokens, whichever is smaller"). When the 14-day window exceeds the bound, the oldest
  in-window messages are archived out of the live context until it fits — they are still
  summarized by the nightly roll on their normal schedule and their raw files are retained.
- **Canonical current message store (for a chat)**: whatever the redesign settles on as "the one
  place a new inbound message for chat C is appended" — resolved by a deterministic on-disk
  lookup, not a losable in-memory index. (`plan.md` decides the concrete shape.)
- **Archive (of a message/session)**: a move on disk (`rename`) to a retained location. Never a
  delete. Raw content remains on disk and auditable indefinitely.
- **One-time prod migration**: an operator-run, separately-approved script that creates daily
  summaries for every non-empty calendar day of prod history older than 14 days, writing roll
  markers as it goes. A real prod data write and real billed OpenAI calls.
- **Log retention (rotation with on-disk copies)**: the property that the application log file
  may be rotated by size or age, but every rotated segment is kept as a file on disk (compressed
  is fine) — as opposed to Docker's `json-file` driver silently dropping the oldest chunk.

## Technology Choices

- **Scheduling**: the existing `APScheduler` `BackgroundScheduler` pattern
  (`services/reminder_delivery_service.py`, `services/accounting_reconciliation_service.py`). The
  nightly roll is wall-clock-anchored → `CronTrigger(hour=2, minute=0)` in Israel local time, one
  shared job wired in `denidin.py`'s `initialize_app` alongside the existing schedulers. No new
  scheduling technology.
- **Time**: the `Asia/Jerusalem`-aware helpers in `apps/denidin-app/src/utils/time_utils.py`.
  "Calendar day" and "14 days" are both evaluated in Israel local time. No UTC anywhere.
- **Short-term storage**: the existing on-disk session/message JSON layout under `data/sessions/`.
  The window is computed from message timestamps already persisted per message. Whether the
  redesign keeps one long-lived `Session` per chat or moves to per-chat message storage is a
  `plan.md` decision (see REQ-MEM-014) — but no new datastore technology either way.
- **Long-term storage**: the existing `MemoryManager` / ChromaDB collections and OpenAI
  embeddings (`config.ai_embedding_model`). Daily summaries are ordinary `remember()` writes with
  richer metadata; recall is the existing semantic `recall()` path. No `LedgerEventManager`
  schema-version change (this feature does not touch the ledger — REQ-MEM-043).
- **Roll markers**: a durable, per-(chat, date) record. Concrete storage (a markers file under
  `data/`, a metadata flag on the daily-summary record, or a small index) is a `plan.md`
  decision. [NEEDS CLARIFICATION: see REQ-MEM-046.]
- **Config**: new keys under the existing `memory` block and a `config.feature_flags` flag. No
  env vars.
- **Migration & log-retention verification**: standalone operator scripts under `scripts/` /
  `apps/denidin-app/scripts/`, following the Feature 061/062 backfill-script conventions
  (explicit CLI args, no hardcoded dates, idempotent, real credentials never committed).
- **Third-party behavior that MUST be verified against a real call before design is finalized**
  (CONSTITUTION "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS"):
  - `gpt-5.6-luna`'s real usable context-window size and token pricing — the 14-day verbatim
    window's worst case must be shown to fit with margin against confirmed numbers. (Real prod
    measurement to date: group chat full history ≈ 62K tokens over the whole Aug 5–Sep 1 life;
    growth ≈ 2,200 tokens/day; a 14-day window is a fraction of that — but the model's confirmed
    limits are still the load-bearing check.)
  - OpenAI automatic prompt-caching behavior on the new prompt shape (constitution prefix stable;
    the 14-day window stable between nightly rolls) — confirm the cache actually engages.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The last 14 days of messages are always in verbatim context (Priority: P1)

The core capability and the MVP. Regardless of session boundaries or idle gaps, every turn's
context includes every message (per chat) from the last 14 calendar days (Israel local),
verbatim, in order, with Feature 039 `[sender_name]` prefixing preserved for group turns. There
is no 24-hour idle expiry. A new inbound message after a restart continues the same conversation
(the bugfix-044 failure mode is designed out). A session persisted with an unknown field still
loads (bugfix-035 H2, fixed inline).

**Why this priority**: This is the feature. It delivers the user-visible value on its own for the
first 14 days of any chat's life — the bot stops "forgetting" a conversation that paused for a
day, and multi-day context is always present without relying on semantic recall to reconstruct
it.

**Independent Test**: Seed a chat with messages dated 20, 15, 13, 2, and 0 days ago. Build the
turn context via the real code path. Assert the 13/2/0-day messages are present verbatim and in
order; the 20/15-day messages are not in the verbatim window. With the feature flag OFF, assert
the context is byte-for-byte the current session-scoped behavior.

**Acceptance Scenarios**:

1. **Given** messages spanning 30 days for a chat, **When** a new turn is processed with the flag
   ON, **Then** exactly the messages from the last 14 days are in the verbatim window,
   oldest-first.
2. **Given** a chat idle for 3 days, **When** a new message arrives, **Then** the prior
   conversation (still within 14 days) is fully in context — no "new session, no memory" behavior.
3. **Given** a group chat, **When** the window is built, **Then** user turns carry the
   `[sender_name]` prefix exactly as today.
4. **Given** the feature flag is OFF, **When** any turn is processed, **Then** behavior is
   identical to the pre-feature session-scoped model (byte-for-byte golden file).
5. **Given** an app restart with an in-progress conversation for chat C, **When** the next inbound
   message for C arrives, **Then** it appends to C's existing message store and the pre-restart
   turns are in context — no new empty session, no manual re-priming (bugfix-044 designed out).
6. **Given** a session file with an unknown persisted key and a future-dated (clock-skew)
   message, **When** the window is built, **Then** it does not crash and does not return an empty
   window; the unknown key is dropped with one warning (bugfix-035 H2).
7. **Given** the window is rebuilt on every turn, **When** p95 latency and per-turn token count
   are measured over the real prod message mix, **Then** added latency ≤ 150 ms p95 and tokens
   are within the confirmed model budget with ≥ 30% headroom.

---

### User Story 2 - Each night the previous day is summarized into long-term memory (Priority: P1)

At 02:00 Israel local, for each chat, the previous calendar day's messages are summarized into
**exactly one** daily long-term record (chat + date keyed), embedded, and stored via
`MemoryManager.remember()` (sanitized collection resolution — group chats included; bugfix-035 H1
designed out). Empty days produce nothing. The job is idempotent per (chat, date) via a roll
marker. A startup catch-up sweep rolls any (chat, date) pairs missed while the app was down.

**Why this priority**: Without the nightly roll, days that scroll out of the 14-day window would
have no Tier-2 representation — the exact "silent hole" the current model already has for
always-active chats. It is P1 (co-equal with US1) because the two together are the coherent new
model; shipping US1 alone would regress memory for history older than 14 days once chats age.

**Independent Test**: Seed two chats with messages across three past calendar days (one day empty
for one chat). Run the roll job for those dates. Assert: exactly one daily summary per non-empty
(chat, date) including the group chat; zero for the empty one; each retrievable via `recall()`
with correct chat/date metadata; a re-run produces no new summaries and no new billed calls. Then
simulate a 2-day downtime and assert the catch-up sweep rolls exactly the missed days once each.

**Acceptance Scenarios**:

1. **Given** chat C (including a `…@g.us` group) has messages on calendar day D, **When** the
   nightly roll runs for D, **Then** exactly one daily summary for (C, D) is stored, retrievable
   via `recall()`, and a roll marker for (C, D) is recorded.
2. **Given** chat C has no messages on day D, **When** the roll runs for D, **Then** no summary,
   no OpenAI call, and (C, D) is still marked rolled.
3. **Given** (C, D) already has a roll marker, **When** the roll job or catch-up sweep runs
   again, **Then** it is skipped — no second summary, no second billed call.
4. **Given** the app was down across days D1 and D2, **When** it starts, **Then** the catch-up
   sweep rolls (C, D1) and (C, D2) exactly once each before normal operation resumes.
5. **Given** a daily summary exists for D (now outside the 14-day window), **When** a user asks a
   question whose answer is in D, **Then** semantic recall surfaces that day's summary.
6. **Given** the summarization OpenAI call fails for one (C, D), **When** the job runs, **Then**
   no roll marker is written for (C, D), it is retried with a bounded budget on the next run, and
   one unloadable/erroring chat does not abort the roll for other chats.
7. **Given** the scheduler and a manually-run roll script both target (C, D) concurrently,
   **When** both execute, **Then** at most one summary is created (marker check-and-write is
   race-safe).

---

### User Story 3 - Raw messages are never deleted, and context never blows the token budget (Priority: P1)

Two guarantees. (a) A message aging past the 14-day window, or trimmed by the token/size
backstop, is **archived** (moved on disk to a retained path) — never `unlink()`-ed. The current
live deletion path (`_prune_until_under_limit`, which `unlink()`s message files) is replaced by
archive-only trimming when the flag is ON. (b) The verbatim window is bounded by "last 14 days OR
last N tokens, whichever is smaller"; when 14 days exceeds N tokens, the oldest in-window
messages are archived out of the live context (still summarized on their normal nightly
schedule).

**Why this priority**: The user's explicit precondition for approving this whole feature was that
all raw data is preserved. A rolling window that quietly deletes to stay under a token cap would
reintroduce exactly the "messages dropped with no summary" failure. Co-equal P1 with US1/US2 — it
is the safety property that makes the new model trustworthy, not a follow-up.

**Independent Test**: Configure a deliberately tiny token backstop. Seed a chat with more
in-window messages than the backstop allows. Build the context. Assert: the live window is
trimmed to fit; every trimmed message's raw file still exists at its archive path; the trimmed
messages are still picked up by the nightly roll for their day. Separately, a static audit that
no feature code path calls `unlink()` / `os.remove` / `rmtree` on a message or session file.

**Acceptance Scenarios**:

1. **Given** a message older than 14 days, **When** the window is rebuilt, **Then** it is
   archived (present at a retained on-disk path), not deleted, and a file-integrity audit still
   balances (live + archived == message_counter == id-list length).
2. **Given** the 14-day window exceeds the token backstop for a chat, **When** context is built,
   **Then** the oldest messages are archived out until it fits, and the most recent messages are
   always retained.
3. **Given** any message trimmed for the backstop, **When** its day's nightly roll runs,
   **Then** that message is still included in the day's summary.
4. **Given** the whole feature's code, **When** audited, **Then** there is no live path that
   deletes a persisted message or session file — only archive/move.
5. **Given** `expired/YYYY-MM-DD/` accumulating across many runs (bugfix-035 H3), **When** the
   retention policy is applied, **Then** it follows a documented bound (which may be "retain
   indefinitely by design"), never silent deletion of a message's only copy, and the test suite
   scopes its archived-session lookups to its own `session_id` rather than `rglob(...)[0]`.
6. **Given** the token backstop is misconfigured smaller than one day of messages, **When** the
   window is built, **Then** it still returns the most recent messages and terminates (no
   infinite archive loop).

---

### User Story 4 - A one-time migration backfills daily summaries for pre-window history (Priority: P2)

An operator-run, separately-approved script creates one daily summary per non-empty calendar day
for all prod history older than 14 days (bot went live 2026-08-05), writing a roll marker for
each (chat, date) as it goes, so the periodic model starts with a complete Tier-2 record and the
nightly job never re-summarizes those days.

**Why this priority**: Needed exactly once, for prod, before the feature flag is turned on there.
P2 because the feature is buildable and testable in dev without it, and it is a separately-gated
real-prod-write action outside the normal implement flow.

**Independent Test** (dev/sandbox, real code, real billed calls): Point the script at a dev chat
with >14 days of seeded history. Run it. Assert: one daily summary per non-empty past day; roll
markers for every processed (chat, date) including empty ones; a re-run is a no-op; after the
run the nightly job and catch-up sweep skip every migrated day; the 14-day verbatim window is
unchanged by the migration.

**Acceptance Scenarios**:

1. **Given** prod history 2026-08-05 → (today − 14d) for both prod chats, **When** the migration
   runs, **Then** every non-empty calendar day in that range has exactly one daily summary and a
   roll marker; every empty day has a roll marker only.
2. **Given** the migration completed, **When** it is run again, **Then** 0 OpenAI calls, 0 new
   records.
3. **Given** the migration completed and the flag is then enabled in prod, **When** the nightly
   job first runs, **Then** it processes only days after the migration cutoff.
4. **Given** the migration is a real prod write, **When** anyone wants to run it, **Then** it
   requires fresh explicit human approval for that specific run and never runs as a side effect
   of a deploy or of flipping the flag.
5. **Given** raw messages, **When** the migration runs, **Then** it only reads them — no message
   or session file is moved or deleted (before/after file-integrity check).
6. **Given** the migration run, **When** it finishes, **Then** it prints a per-chat report (days
   processed, summaries created, empty days, billed-call count) for human review.

---

### User Story 5 - Prod application logs are retained across rotation (Priority: P2)

Verify (and, if needed, configure) that the prod application log (`logs/denidin.log` and the
morning-mcp-app equivalent) is rotated by size or age but **every rotated segment is kept on
disk** — so the full application-log history since 2026-08-05 remains reconstructable. Docker's
`json-file` log driver rotation (which drops the oldest chunk) is not the system of record.

**Why this priority**: The user asked for it explicitly alongside the raw-message guarantee — the
same "never silently lose the audit trail" principle applied to logs. P2 because it is a
verification/config task, not application logic, and does not block US1-US3.

**Independent Test**: Inspect the current logging config (app-level handler + Docker log driver
options) and the prod box's on-disk log directory. Produce a written finding: what rotates what,
by what trigger, and whether rotated segments are retained. If retention is not guaranteed,
specify the minimal config change and verify it keeps segments after a forced rotation.

**Acceptance Scenarios**:

1. **Given** the current prod logging setup, **When** it is audited, **Then** a written statement
   describes each rotation trigger (size/age) and whether every rotated segment is retained.
2. **Given** rotation by size or age, **When** a rotation occurs, **Then** the pre-rotation
   content still exists as an on-disk file (compression allowed), not discarded.
3. **Given** the application-log history since go-live, **When** any past date is requested,
   **Then** that date's log lines are retrievable from disk, bounded only by a documented
   deliberate retention policy — not silent loss.
4. **Given** the `json-file` Docker driver is still in use for `docker logs`, **When** it
   rotates, **Then** that loss is acceptable only because the app-level file handler retains full
   history independently; the runbook states this dependency.

---

### Edge Cases

- **DST transition on a roll night.** 02:00 Israel local on a spring-forward night may not exist;
  on a fall-back night it occurs twice. The `CronTrigger` must fire exactly once and "previous
  calendar day" must stay well-defined. *(REQ-MEM-031.)*
- **A message timestamped exactly on the 14-day boundary or exactly at midnight between two
  days** — inclusive/exclusive rules must be explicit and consistent between the window-builder
  and the roll job (a message belongs to exactly one day and is either in the window or
  summarized, never both, never neither).
- **A pre-2026-08-10 message with a `+00:00` timestamp** (written before the Israel-local
  switch). Both sides are timezone-aware; day-bucketing must convert to Israel local
  consistently.
- **Clock skew / a message timestamped in the future.** The window-builder must not crash or
  exclude everything.
- **The roll job runs while a message for "yesterday" is still arriving at 02:00:00.** Define the
  cutoff so a late-night message is attributed to exactly one day and not lost between the window
  and the summary.
- **A chat with zero messages ever.** No window, no roll, no error.
- **ChromaDB collection does not exist yet for a chat** (first-ever daily summary) — must create,
  not fail (the sanitized helper must cover the create path too — this is where bugfix-035 H1
  would recur if done carelessly).
- **The app is down for longer than 14 days.** The catch-up sweep must roll every missed day.
  Since raw messages are never deleted (US3), the raw content for those days is always still on
  disk — so this is bounded work, not a data-availability problem. *(Confirms REQ-MEM-030.)*
- **Two rollers racing on the same (chat, date)** (scheduler + manual script). Marker
  check-and-write must be idempotent under a race.
- **Feature flag flipped OFF after some daily summaries already exist.** Recall must not break;
  the system falls back cleanly to session-scoped behavior without the daily summaries causing
  errors.
- **The token backstop set smaller than a single day's messages.** The window must still contain
  the most recent messages and must not loop forever archiving.
- **An unloadable (bugfix-035 H2) session encountered mid-roll.** One poison session must not
  abort the whole night's roll for other chats.

## Requirements *(mandatory)*

### Functional Requirements — Rolling window (User Story 1)

- **REQ-MEM-001**: With the feature flag ON, the per-turn conversation context MUST include every
  message for the chat whose timestamp falls within the last 14 calendar days (Israel local),
  verbatim, oldest-first, subject only to the token backstop (REQ-MEM-024).
- **REQ-MEM-002**: With the feature flag ON, there MUST be no 24-hour idle session expiry; a chat
  idle for up to 14 days retains full verbatim context.
- **REQ-MEM-003**: "Last 14 days" and "calendar day" MUST be evaluated in Israel local time via
  `time_utils`, with explicit documented inclusive/exclusive boundary rules, correct across DST,
  and consistent with the roll job's day-bucketing (REQ-MEM-011) — every message belongs to
  exactly one day and is either in the window or summarized, never both or neither.
- **REQ-MEM-004**: Group-chat user turns in the window MUST retain the Feature 039 `[sender_name]`
  prefix.
- **REQ-MEM-005**: With the feature flag OFF, the conversation-context code path MUST be
  byte-for-byte identical to the pre-feature session-scoped behavior.
- **REQ-MEM-006**: The window MUST be built from message timestamps already persisted per message;
  no new per-message datastore.
- **REQ-MEM-007**: The window-builder MUST tolerate clock skew / future-dated messages and an
  unloadable session without crashing or emptying the window.
- **REQ-MEM-008**: The 14-day window length MUST be a config value (default 14), not a literal.

### Functional Requirements — Restart continuity & tolerant load (User Story 1, legacy defects folded in)

- **REQ-MEM-010**: `SessionManager` session deserialization MUST tolerate unknown persisted
  top-level fields — drop them (mirroring `denidin.py`'s `valid_fields` filter) and log **one
  warning** (not an error), rather than raising `TypeError`. The tolerance MUST be generic (any
  unknown key), so a future field removal does not strand previously-persisted sessions.
  *(bugfix-035 H2, fixed inline.)*
- **REQ-MEM-011**: A tolerantly-loaded session MUST participate normally in every lifecycle step
  (window inclusion, nightly roll, archive).
- **REQ-MEM-014**: "Where does a new inbound message for chat C append?" MUST be answered by a
  **deterministic on-disk lookup** for C's canonical current message store — never solely by an
  in-memory index that a recovery path can fail to populate. `plan.md` decides the concrete
  shape (one long-lived session per chat located by `whatsapp_chat`, or per-chat message
  storage). *(bugfix-044 designed out.)*
- **REQ-MEM-015**: After a process restart, the next inbound message for a chat with prior
  history MUST append to that chat's existing store and see the prior turns in context — with no
  reliance on an orphan-recovery step having re-registered anything.
- **REQ-MEM-016**: If the redesign retains any in-memory chat→store index, `remove_from_index()`
  MUST remove a chat's entry only if it currently points at the store being removed. If no such
  index survives, this requirement is N/A (state so in `plan.md`).
- **REQ-MEM-017**: The retirement of the 24h-expiry → per-session-transfer → hourly-retry cycle
  MUST NOT leave `SessionCleanupThread` (or its replacement) able to re-summarize an
  already-rolled day or a still-in-window session. *(bugfix-035 H1 loop designed out.)*

### Functional Requirements — Nightly roll (User Story 2)

- **REQ-MEM-020**: A single `APScheduler` `CronTrigger` job MUST run at 02:00 Israel local time,
  wired in `denidin.py`'s `initialize_app` alongside the existing schedulers, gated by the
  feature flag; the roll hour MUST be a config value.
- **REQ-MEM-021**: For each chat, the roll MUST summarize the previous calendar day's messages
  into **exactly one** daily long-term record, embedded and stored via `MemoryManager`, with
  metadata including at least the chat id and the summarized calendar date.
- **REQ-MEM-022**: The daily-summary collection name for a chat MUST be resolved through a single
  shared helper that sanitizes for all chat-id shapes (`@c.us`, `@g.us`, any other), on both the
  write path and any read/verify path. No raw `client.get_collection()` call with an unsanitized
  name anywhere. *(bugfix-035 H1 bug 1+2, designed out.)*
- **REQ-MEM-023**: A calendar day with zero messages for a chat MUST produce no summary and no
  OpenAI call, and MUST still be marked rolled.
- **REQ-MEM-024**: The roll MUST be idempotent per (chat, date) via a roll marker checked before
  any OpenAI call; a re-run or catch-up pass MUST NOT create a second summary or make a second
  billed call for an already-rolled (chat, date).
- **REQ-MEM-025**: A roll marker for a non-empty (chat, date) MUST be written **only after** the
  daily summary is durably stored — a mid-roll failure MUST leave (chat, date) un-rolled for a
  bounded retry, not falsely marked done.
- **REQ-MEM-026**: The check-and-write of a roll marker MUST be safe against concurrent rollers
  (scheduler + manual script) — no double summary under a race.
- **REQ-MEM-027**: One unloadable or erroring chat/session MUST NOT abort the roll for other
  chats; per-chat failures are isolated and retried with a bounded budget.
- **REQ-MEM-028**: A startup catch-up sweep MUST, on app start, roll every (chat, date) pair
  older than "yesterday" with no roll marker — exactly once each — without blocking message
  handling indefinitely.
- **REQ-MEM-029**: Daily summaries MUST be retrievable through the existing semantic `recall()`
  path so a question about a day now outside the 14-day window surfaces that day's summary.
- **REQ-MEM-030**: Because raw messages are never deleted (REQ-MEM-032), the catch-up sweep after
  any outage — even one longer than 14 days — always has the raw content it needs on disk; it
  MUST NOT assume a message may be missing.
- **REQ-MEM-031**: The roll and the catch-up sweep MUST behave correctly across DST transitions
  (fire once; "previous calendar day" unambiguous).

### Functional Requirements — Raw-data & token safety (User Story 3)

- **REQ-MEM-032**: No code path introduced or modified by this feature may delete a persisted
  message or session file. Aging out of the window and token-backstop trimming MUST both be
  archive-only (move/rename to a retained path).
- **REQ-MEM-033**: The existing live deletion path `_prune_until_under_limit` (and any other
  `unlink()` of message files) MUST be replaced with archive-only trimming when the feature flag
  is ON. With the flag OFF, existing behavior is unchanged (REQ-MEM-005).
- **REQ-MEM-024b / REQ-MEM-024**: The verbatim window MUST be bounded by "last 14 days OR last N
  tokens, whichever is smaller". When 14 days exceeds N tokens, the oldest in-window messages are
  archived out of the live context until it fits. [NEEDS CLARIFICATION: value of N — a candidate
  is the current godfather `max_tokens_by_role` 100000, or lower. See REQ-MEM-047.]
- **REQ-MEM-036**: A message trimmed by the token backstop MUST still be included in its calendar
  day's nightly roll summary.
- **REQ-MEM-037**: `gpt-5.6-luna`'s confirmed usable context window MUST be shown (against a real
  verified figure) to accommodate the worst-case 14-day window + constitution + tools + reply
  headroom, with margin, before implementation is considered complete. Unverified model limits
  MUST NOT be built on (CONSTITUTION).
- **REQ-MEM-034**: `expired/YYYY-MM-DD/` (and any per-message archive path) growth MUST be
  bounded by a documented, deliberate policy — which MAY be "retain indefinitely by design" — but
  MUST NOT be silent deletion of a message's only copy. *(bugfix-035 H3.)*
- **REQ-MEM-035**: The test suite MUST scope archived-session lookups to the session under test
  (its own `session_id`/`chat_id`), not `rglob(...)[0]`. *(bugfix-035 H3.)*

### Functional Requirements — One-time prod migration (User Story 4)

- **REQ-MEM-040**: The migration MUST be a standalone operator script (Feature 061/062
  conventions: explicit CLI args, no hardcoded dates, real credentials never committed).
- **REQ-MEM-041**: The migration MUST create exactly one daily summary per non-empty calendar day
  of history older than 14 days, and write a roll marker for every processed (chat, date)
  including empty ones.
- **REQ-MEM-042**: The migration MUST be idempotent — a second run makes no OpenAI calls and
  writes no new records, via the same roll markers the nightly job uses.
- **REQ-MEM-044**: After the migration, the nightly job and catch-up sweep MUST skip every
  migrated day and only process genuinely un-rolled days forward.
- **REQ-MEM-045**: The migration MUST only read raw messages — it MUST NOT move, archive, or
  delete any message or session file.
- **REQ-MEM-048**: Running the migration against real prod data MUST require fresh, explicit
  human approval for that specific run, independent of feature-build approval and of any deploy.
- **REQ-MEM-049**: The migration MUST produce a written per-chat run report (days processed,
  summaries created, empty days, billed-call count) for human review.

### Functional Requirements — Log retention (User Story 5)

- **REQ-MEM-050**: The current prod logging configuration (app-level handler + Docker log driver
  options) MUST be audited and documented: what rotates, by what trigger (size/age), and whether
  every rotated segment is retained on disk.
- **REQ-MEM-051**: The application log MUST be configured so that rotation by size or age keeps
  every rotated segment as an on-disk file (compression allowed); silent discard of the oldest
  segment is not acceptable as the system of record.
- **REQ-MEM-052**: If the current config does not guarantee retention, the minimal config change
  MUST be specified and verified (force a rotation, confirm the prior segment persists).
- **REQ-MEM-053b**: The `json-file` Docker driver's lossy rotation is acceptable for `docker
  logs` convenience only because the app-level file handler independently retains full history;
  this dependency MUST be stated in the runbook.

### Cross-cutting

- **REQ-MEM-043**: This feature MUST NOT change `LedgerEventManager.CURRENT_SCHEMA_VERSION` or
  any ledger schema.
- **REQ-MEM-046**: [NEEDS CLARIFICATION] Roll-marker storage mechanism — a dedicated markers file
  under `data/`, a queryable flag on the daily-summary record, or a small index — decided in
  `plan.md`. Requirement: survives restarts; checked identically by the nightly job, the catch-up
  sweep, and the one-time migration.
- **REQ-MEM-047**: [NEEDS CLARIFICATION] Token-backstop value N (see REQ-MEM-024). Also: does the
  daily-summary `recall()` need a larger `top_k_results` than the current 5 to answer multi-week
  questions, or is that out of scope? Decide in `plan.md`/`clarify`.

### Feature-flag & config requirements

- **REQ-MEM-060**: All new behavior MUST sit behind `config.feature_flags.<flag>` (name TBD in
  plan), default `false`. Flag OFF ⇒ code path byte-for-byte identical to pre-feature.
- **REQ-MEM-061**: New tunables (window length, token backstop N, catch-up lookback, retry
  budgets, roll hour) MUST be config keys under the existing `memory` block with documented
  defaults — no magic numbers, no env vars.
- **REQ-MEM-062**: Unit tests MAY set the flag; integration tests MUST NOT (they test default
  production behavior). Integration/acceptance coverage of the new model therefore uses dedicated
  `billed` acceptance tests that exercise it explicitly, OR the flag becomes default-on only
  after sign-off. Decide in `plan.md`.

## Key Entities

- **Rolling window**: derived, not stored. Per chat: the ordered list of messages with
  Israel-local timestamp within the last 14 calendar days, capped by the token backstop.
- **Daily summary**: one ChromaDB record. Attributes: summary text, embedding, chat id,
  summarized calendar date, message count, created-at (Israel local), source ("daily-roll" or
  "migration"). The unit of Tier-2 memory under the new model.
- **Roll marker**: durable per-(chat, date) record meaning "this day is rolled — do not
  summarize again". Written by the nightly job, catch-up sweep, and migration.
- **Canonical current message store**: per chat, the one on-disk location new messages append to,
  found by deterministic lookup.
- **Archived message / archived session**: a message or session file moved (never deleted) to a
  retained path when it ages past the window or is trimmed by the backstop.
- **Log segment**: a rotated slice of the application log, retained on disk.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any prod chat, after a pause of up to 14 days, the bot's next reply demonstrably
  uses context from before the pause — 0 occurrences of "new session, context lost" for gaps ≤ 14
  days.
- **SC-002**: Group-chat long-term memory works: after the nightly roll, a `…@g.us` chat's daily
  summary is retrievable via `recall()`; repeated hourly re-summarization of the same session
  drops to 0; duplicate summary records for one day stays at 1.
- **SC-003**: Billed OpenAI summarization calls attributable to memory settle at **≤ 1 per chat
  per active calendar day** (down from unbounded hourly retries + per-session bursts).
- **SC-004**: 100% of messages that age past the 14-day window, or are trimmed by the token
  backstop, still exist on disk at a retained path — verified by a file-integrity audit
  (live + archived counts == `message_counter` == id-list length). 0 message files deleted.
- **SC-005**: Every non-empty calendar day since 2026-08-05, per prod chat, has exactly one daily
  summary retrievable via `recall()` after the migration — 0 gaps, 0 duplicates.
- **SC-006**: A restart followed by a new inbound message continues the pre-restart conversation
  in 100% of cases (0 abandoned prior message stores).
- **SC-007**: Added per-turn latency from building the 14-day window is ≤ 150 ms p95 over the
  real prod message mix; added per-turn input tokens are within the confirmed model context
  budget with ≥ 30% headroom.
- **SC-008**: A session persisted with an unknown field loads with 0 `TypeError`s and exactly 1
  warning; the per-hour recurring error for the known poison session goes to 0.
- **SC-009**: After a forced log rotation on the prod box, the pre-rotation log content is still
  retrievable from an on-disk file — 100% of rotations retain their prior segment.
- **SC-010**: Re-running the nightly roll, the catch-up sweep, or the one-time migration over an
  already-rolled range produces 0 new summaries and 0 new billed calls.
- **SC-011**: With the feature flag OFF, the full existing test suite passes unchanged and the
  conversation-context output is byte-for-byte identical to pre-feature.

## Out of Scope

- Changing the embedding model or the "RECALLED MEMORIES" prompt block format. (`top_k_results`
  adjustment for multi-week questions is an open `plan.md`/`clarify` question, REQ-MEM-047, not
  assumed here.)
- Purging the 27 existing duplicate records in `memory_120363210094632983_at_g.us` — a separate
  prod data write needing its own approval.
- Any change to the Morning/ledger subsystems.
- Migrating existing pre-2026-08-10 `+00:00` timestamps (they compare correctly as-is).
- Cold-storage / offsite backup of archived messages beyond the on-disk retained path.
- Deploying the feature or enabling the flag in any environment.
- Standalone regression suites for bugfix-035 / bugfix-044 — their coverage rides on the named
  acceptance tests per §"Legacy Defects".

## Dependencies & Assumptions

- **Raw-data preservation is already verified** (2026-09-01 audit): the only live deletion path
  (`_prune_until_under_limit`) has provably never fired in prod (monotonic `message_counter` ==
  `len(message_ids)` == files-on-disk for all 90 sessions); `clear_session`/`prune_to_limit` have
  zero callers; `archive_session` is a `rename`. This feature must keep it that way.
- **Two prod chats only** (`120363210094632983@g.us`, `972522968679@c.us`); go-live 2026-08-05.
  The migration's real scope is small (~2-3 weeks × 2 chats).
- **`gpt-5.6-luna` context/pricing** and **OpenAI prompt-cache behavior on the new prompt shape**
  are unverified third-party facts and MUST be confirmed against real calls before the design is
  locked (CONSTITUTION).
- Prod is on the always-on Windows box (Feature 035); log-retention verification uses the
  existing read-only mount / `tail_logs.sh` paths and, for any config change, the normal deploy
  flow (not part of this feature).
- The legacy bugfix specs (`specs/bugfixes/bugfix-035-*`, `bugfix-044-*`) will get a status note
  at haleluya time recording that Feature 070 subsumed them; they are not worked as standalone
  Bug-Driven Development tracks.
