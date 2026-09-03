# Feature 070 — Full Migration Scope & Reach (prod + dev)

**Status**: DRAFT for human review. Blocks Phase 10 (prod backfill). Written 2026-09-04 after a
read-only inspection of live prod data (`~/denidin-winprod-data`, sshfs read-only mount) and dev
data (`apps/denidin-app/dev_data`).

**Bottom line**: the migration tooling shipped in Phases 1–9 assumes **≈1 session per chat**
(research.md line 59: *"Migrates the 2 prod sessions transparently on first construction"*).
Prod actually has **93 session directories** and **20,871 ChromaDB records**. Deploying 0.5.4
against prod as-is would **silently wipe the bot's working memory of everything except one day
(2026-08-09) per chat** — no crash, no error, just amnesia. Dev only "passed" Phase 9 because the
operator hand-consolidated dev to 2 sessions first and the discarded dev history was test junk.

---

## 1. Observed state

### 1.1 Prod (`~/denidin-winprod-data`, live — mtimes current as of inspection)

| Store | State |
|---|---|
| `sessions/` | **1 "active" dir** (`0f5eaa04…`, chat `972522968679@c.us`, 10 msgs, **last active 2026-08-03**, stale) + **`expired/` with 92 dirs across 24 date folders** (2026-08-04 … 2026-09-02). No `chat_index.db`, no `roll_markers.db` (Feature 070 has never run here). |
| Distinct chats | **2**: `120363210094632983@g.us` (the "$$ גבייה אילה $$" collections group — Ayala, ADMIN, real bookkeeping: fee agreements, per-client work-hour logs) and `972522968679@c.us` (godfather 1:1). |
| `120363210094632983@g.us` sessions | **86 dirs, 926 messages**, 2026-08-05 … 2026-09-02. `max(message_counter)` = **118** (2026-08-09). 8 dirs have 0 messages. |
| `972522968679@c.us` sessions | **7 dirs, 127 messages**, 2026-08-03 … 2026-09-02. `max(message_counter)` = **64** (2026-08-04). Includes the stale "active" `0f5eaa04`. |
| Message-file integrity | Clean — every `session.json` `message_counter` equals its on-disk `messages/*.json` count; 0 `archived/`; nothing unparseable; no unexpected keys **except** `pending_ledger_events: []` on `0f5eaa04` (retired Feature-024 field — tolerant load handles it, but confirms prod carries the poison shape). |
| `memory/` (ChromaDB) | `chroma.sqlite3` **249 MB**, actively being written. 2 collections: `memory_120363210094632983_at_g.us`, `memory_972522968679`. **20,868 `type=session_summary` + 3 `session_summary_fallback` records**, all `text-embedding-3-large`. **0 `daily_summary`.** |
| `events/` | 780 ledger-event JSON files. Each carries `session_id` + `message_id` — **traceability only, never dereferenced** (verified: not in `_SEARCHABLE_FIELDS`/`_HINT_GROUPS`, no `get_session`/file lookup anywhere off them; `whatsapp_chat` was already dropped 2026-08-19 as redundant). |
| `media/` | 38 files, named `DD-<chat_id>-<uuid>.jpg`. Chat-keyed, **no session/message reference**. Includes files for `972506205541@c.us` (Ayala's personal 1:1) — a chat with **no session dir at all**. |
| `reminders/reminders.db` | Present. Not session-referencing. (Separately: bugfix-051 — `list_reminders` cross-chat disclosure — is open against this.) |
| `accounting_reconciliation/pending_review.json` | Present. Feature 025 state, independent of sessions. |

**The 20,868 `session_summary` records are themselves a live prod incident.** Spec §"Out of
Scope" says *"The 27 existing duplicate records are a separate prod cleanup"* — the real number
is **773× higher**. Root cause is almost certainly bugfix-035 H1 still active on 0.5.3: the
group-collection post-write `client.get_collection()` verify throws `NotFoundError`, the session
never gets marked `transferred_to_longterm`, and the hourly `SessionCleanupThread` re-summarises
every un-marked session **every hour, forever** — burning OpenAI embedding spend and bloating
ChromaDB the whole time. Feature 070 deletes the cleanup thread (loop stops), but the 20,871
records **stay in the collections recall reads from**.

### 1.2 Dev (`apps/denidin-app/dev_data`) — current state after the Phase 9 operator cleanup

- `sessions/`: 2 real sessions (`0a303ab4` 1:1 active, `504112c0` promoted group) + `chat_index.db`
  + `expired/` emptied. **`_pre070_sessions_archive_20260903/` (outside `sessions/`) holds the 10
  moved-aside dirs** — 8 stale 1:1 test sessions, 1 test number, 1 group emoji dir.
- `memory_rolls/roll_markers.db`: 21 committed markers/chat (backfill + startup catch-up).
- `memory/`: untouched — still holds the pre-070 `session_summary` records.
- `events/`: 4170 ledger files (dev has been used heavily). 10 of the moved-aside sessions'
  `session_id` pointers are now stale-but-harmless.
- **Dev consequence, accepted**: dev lost its pre-2026-08-24 1:1 history and pre-2026-08-19 group
  history from the rolling window (moved aside, never summarised, never backfilled). Fine for a
  test env; **not acceptable for prod.**

---

## 2. Every persistent store — writer / reader / when

| Store | Written by | Read by | Cadence |
|---|---|---|---|
| `sessions/<uuid>/session.json` | `SessionManager._save_session` (on every `add_message*`, on `archive_*`) | `_load_session`, `_reconcile_chat_index`, `get_session` | every inbound turn; nightly archive |
| `sessions/<uuid>/messages/<mid>.json` | `SessionManager.add_message` (append only — **no write-time prune under 070**) | `_iter_persisted_messages` → `get_rolling_window` (**every turn**), `get_messages_for_local_date` (nightly roll + backfill) | every inbound turn (write); every turn + nightly (read) |
| `sessions/<uuid>/archived/<mid>.json` | `archive_aged_and_backstopped_messages` (`Path.rename` from `messages/`, **never `unlink`**) | same `_iter_persisted_messages` (still read every turn — see §6.1) | nightly roll only |
| `sessions/chat_index.db` (`chat_sessions(chat PK, session_id, updated_at)`) | `_reconcile_chat_index` (`INSERT OR IGNORE` at every `SessionManager.__init__`), `_index_upsert` (`get_session`) | `_index_lookup` (every `get_session`), `known_chats` (nightly roll) | every app start + every turn |
| `{data_root}/memory_rolls/roll_markers.db` (`roll_markers(chat,date PK, status, message_count, summary_memory_id, source, claimed_at, committed_at)`) | `RollMarkerStore.try_claim` / `.commit` | `.is_rolled` (roll + backfill), `.list_markers` (report) | nightly roll; startup catch-up; backfill |
| `memory/` ChromaDB (`chroma.sqlite3` + hnsw seg dirs) | `MemoryManager.remember` (roll writes 1 `daily_summary` per (chat,day); **pre-070: cleanup thread wrote `session_summary`**) | `MemoryManager.recall` / `recall_with_rbac_filter` — **per-chat collection only**, `top_k=daily_summary_top_k` (10), `min_similarity` | **every turn** (recall); nightly (write) |
| `events/<id>.json` | `LedgerEventManager.capture_ledger_event` (immutable, one file per event) | `LedgerEventManager._load_index` (startup), `query_events` (godfather `query_ledger_events` tool) | on capture; on query |
| `reminders/reminders.db` | `ReminderManager` (create/modify/delete/complete) | `list_active`, `get_due_occurrences` (5-min sweep) | on reminder ops; every 5 min |

---

## 3. Every runtime code path that touches session/rolling memory

### 3.1 Inbound conversational turn (`AIHandler.get_response` → `_process_conversational_message`)
1. `effective_chat_id` resolved (group → `GroupMembershipResolver` most-permissive member for RBAC).
2. **Recall**: `collection_name_for_chat(effective_chat_id)` → `recall_with_rbac_filter(query=user_prompt, collection_names=[that ONE collection], top_k=10, min_similarity)` → matches appended to `instructions` as a `RECALLED MEMORIES` block. Reads `daily_summary` **and** legacy `session_summary` records from the same collection.
3. **Window**: `session_manager.get_rolling_window(effective_chat_id, window_days=14, max_tokens=<acting role limit>)`:
   - `get_session(chat)` → `_index_lookup` → `_load_session(session_id)` (active dir, else `expired/*/`).
   - `_iter_persisted_messages(session)` reads **every** file in `message_ids` + `archived_message_ids`.
   - keep those with `local_calendar_date(ts) ≥ today−13d`; sort by `order_num`.
   - if `max_tokens`: walk newest→oldest, `count_tokens` each, stop when over budget; **always keep the single newest**.
4. Messages → OpenAI `input`; constitution+memories+date → `instructions`.
5. **Write**: `add_message_with_tokens(user turn)` then `(assistant turn)` — append 2 files, bump `message_counter`, `_save_session`. `SessionManager.add_message` centrally nulls `recipient` for user / `sender` for assistant (Feature 039).
6. Ledger capture (if any): `capture_ledger_event(session_id=<this session>, message_id=<this msg>, …)` — pointers only.

### 3.2 Nightly roll (`daily_summary_roll_service`, `CronTrigger(hour=2, tz=Asia/Jerusalem)`, `max_instances=1`)
Per `known_chats()` × per candidate date (`_PERIODIC_LOOKBACK_DAYS=2` for the timer; `catchup_lookback_days=21` for startup):
1. `is_rolled(chat, date)` → skip if committed.
2. `try_claim(chat, date, source)` → `INSERT status='claimed'`; lose the race / already-committed → skip; **stale `claimed` (> `stale_claim_minutes`=120) → re-take**.
3. `get_session(chat)` → `get_messages_for_local_date(session, date)` (live + archived).
4. empty → `commit(count=0, memory_id=None)`, log, done (no OpenAI).
5. non-empty → `summarize_conversation(client, model, messages)` (**falls back to raw transcript on any OpenAI error — never raises**), then `collection.delete(where type=daily_summary ∧ chat ∧ date)` (idempotent overwrite), then `remember(summary, collection, metadata{type:daily_summary, chat, date, scope:PRIVATE, user_phone:chat, message_count, source})`, then `commit(count, memory_id)`.
6. after the per-date loop, once per chat: `archive_aged_and_backstopped_messages(session, window_days=14, max_backstop_tokens=100000)` — `Path.rename` out-of-window / beyond-100k-token files `messages/` → `archived/`, update `session.json`. Per-chat `try/except`; errors logged, never escape.

### 3.3 Startup / restart (`denidin.py __main__`, in order)
1. `initialize_app` → `AIHandler.__init__` → **`SessionManager.__init__` → `_reconcile_chat_index()`** (scan every `*/session.json` + `expired/**/session.json`; `INSERT OR IGNORE`; a chat → >1 dir picks `max(message_counter)`, logs one WARNING, deletes nothing) + `RollMarkerStore.__init__` (creates `memory_rolls/roll_markers.db`) + `MemoryManager.__init__` (`PersistentClient` on `memory/`).
2. `run_startup_reminder_sweep`, then reminder scheduler.
3. `run_startup_accounting_reconciliation_sweep` (if `accounting_ledger_update_freq>0` — prod=60), then its scheduler.
4. **`run_startup_daily_roll_sweep`** (`lookback=catchup_lookback_days=21`, `log_prefix="[STARTUP] "`, `source="catch-up"`), then `start_daily_roll_scheduler(roll_hour=2)`.
5. `message_source.start()` → `bot.run_forever()`.

### 3.4 Shutdown (`SIGINT`/`SIGTERM` handler)
`cleanup_thread.stop()` (070: None) → `reminder_scheduler.shutdown(wait=False)` → `accounting_…shutdown(wait=False)` → **`daily_roll_scheduler.shutdown(wait=False)`** → `raise KeyboardInterrupt`. **`wait=False`** means an in-flight roll job is *not* awaited — see §6.4.

### 3.5 System reboot (Windows prod, Feature 035)
Containers come back automatically; watchdog (PID 1) verifies `config.environment` is in `shared/active_env.json` and that the live server reports its own env, then the app boots exactly as §3.3. The 2026-08-25 ngrok/status-file one-shot-handshake incident is a **separate** open issue (CLAUDE.md banner) — orthogonal to this migration.

---

## 4. Reference graph — what points at a session/message, and what breaks on consolidation

| Pointer | Where | Dereferenced? | Breaks if sessions are consolidated? |
|---|---|---|---|
| `chat_index.db.session_id` | `sessions/chat_index.db` | **Yes** — every `get_session` | N/A — it is *created* by the migration; must point at the consolidated session |
| `roll_markers.db (chat,date)` | `memory_rolls/` | Yes — `is_rolled` | No — keyed by (chat, date), not session; survives consolidation |
| ChromaDB `session_summary.metadata.session_id` | `memory/` (20,868 records) | **No** — recall filters by `type`/`chat`/`scope`, never `session_id` | No — but these records **pollute recall** and should be dealt with (§5.3) |
| ChromaDB `daily_summary.metadata` | `memory/` | No (recall filters `type`/`chat`/`date`) | No |
| `LedgerEvent.session_id` / `.message_id` | `events/*.json` (780 prod) | **No** — traceability only | Cosmetically stale (points at a pre-consolidation UUID); **no amendment required**. Optional: rewrite pointers for tidiness. |
| media `DD-<chat>-<uuid>.jpg` | `media/` | Chat-keyed only | No |
| `Message.session_id` (inside each `messages/<mid>.json`) | per message | Only as an FK label; reads go by folder path, not this field | If a consolidator *moves* message files it should rewrite this to the consolidated `session_id` for consistency (not load-bearing, but cheap and correct) |
| `session.storage_path` | `session.json` | **Yes** — `_load_session` / `_iter_persisted_messages` / `_save_session` resolve `storage_path or session_id` | The consolidated session's `storage_path` must be `null` (an active dir); a leftover `expired/…` value would make `_save_session` re-create the `expired/` tree |

**Answer to "do ledger events need amendment?": No.** `session_id`/`message_id` on a `LedgerEvent`
are pure provenance and are never used to look anything up (confirmed by reading
`ledger_event_manager.py` end-to-end). **How dev handles it today: it doesn't — dev's moved-aside
sessions left ~10 ledger events with stale pointers, harmlessly.** A consolidator *may* rewrite
them for cleanliness; it is not required for correctness.

---

## 5. The migration gap — three distinct problems

### 5.1 Session fragmentation (the blocker)
`_reconcile_chat_index` collapses a chat's N dirs to `max(message_counter)`. Post-deploy:
- group `120363210094632983@g.us` → the **118-msg 2026-08-09** session becomes *the* session forever;
- 1:1 `972522968679@c.us` → the **64-msg 2026-08-04** session.
Both winners are > 14 days old ⇒ **`get_rolling_window` returns `[]`** (empty context on every
turn), and the backfill (`get_session(chat)` → the winner → `get_messages_for_local_date`) only
ever sees the winner's single day. ~1,000 messages of real history across ~25 days — including
the most recent (Sep 1–2) conversations — become invisible to the model and are never summarised.

**Required new component**: a **session-consolidation migration** (per chat: gather every
`session.json` + `messages/*` across the active dir and all `expired/**` dirs for that chat →
one canonical active session dir → all messages copied in, sorted by real `timestamp`,
`order_num` renumbered `1..N`, `message_ids` rebuilt in order, `message_counter=N`,
`archived_message_ids=[]`, `storage_path=null`, `pending_ledger_events` dropped → then, and only
then, run reconcile + backfill). Handles: duplicate `message_id` across dirs (dedupe by id,
keep first), empty dirs (skip), the stale "active" `0f5eaa04` (fold in), clock-skew / missing
`timestamp` (fall back to `received_at`, then file mtime, log). Must be **idempotent**,
**dry-run first** (report only), and leave the pre-migration dirs untouched under a
`sessions/_pre070_raw_<date>/` archive (never delete).

### 5.2 The poison `pending_ledger_events` field
On `0f5eaa04` (prod) and one dev fixture. Tolerant load (`_session_from_dict`, bugfix-035 H2)
drops it with a WARNING and does not crash — **but** the consolidator should strip it while
rewriting, so the canonical session is clean and no WARNING fires on every startup.

### 5.3 ChromaDB `session_summary` bloat (20,871 records)
Not load-bearing (recall filters by `type`/`chat`, never `session_id`) and not a crash risk, but:
- recall's `top_k=10` over a collection of ~10k near-duplicate summaries can crowd out the new
  `daily_summary` records for a given query;
- it is ~200 MB of `chroma.sqlite3` and an ongoing embedding-spend leak **until 0.5.4 is deployed**
  (the H1 loop stops only when the cleanup thread is deleted).
**Decision needed** (§9): (a) leave as-is and rely on semantic ranking, (b) delete all
`type IN (session_summary, session_summary_fallback)` records after the backfill (the daily
summaries then fully replace them), or (c) delete + re-run a fuller backfill so every historical
day has a `daily_summary`. Recommended: **(b)** — the backfill + startup catch-up already
reproduce the useful signal as `daily_summary`, and a clean collection makes recall behaviour
predictable.

---

## 6. Failure-mode analysis

### 6.1 `get_rolling_window` cost grows without bound
`_iter_persisted_messages` reads **`message_ids` + `archived_message_ids`** every call, then
date-filters. Archiving moves files but **not** ids out of `archived_message_ids`, and
`archive_retention_days=0` means `archived/` is **never pruned**. So on a consolidated prod group
session, every turn reads ~950 files today, ~1,800 in two months, forever. Amended SC-007 budget
is 300 ms p95 at 1,500 msgs; prod crosses that inside ~3 months.
**Mitigation options**: (a) accept and revisit (a pruner / an `order_num`+date sidecar index is
a follow-up feature), (b) have `get_rolling_window` skip `archived_message_ids` entirely
(archived ⟹ out of window by construction — but a same-day backstop-archived message would then
be missing from the live window; needs care), (c) build the sidecar index now. **Not a
blocker**, but must be a named, accepted risk before deploy.

### 6.2 Consolidator fails partway
Because it only *reads* the raw dirs and *writes* a brand-new canonical dir, a crash leaves the
raw dirs intact and the canonical dir partial. Recovery: delete the partial canonical dir, re-run.
Must refuse to run if a canonical dir already exists unless `--resume`/`--force` is given, and
must run `assert_message_integrity` on the result before declaring success.

### 6.3 Backfill fails partway (existing behaviour)
`_roll_one_chat_day` raises → `main()` returns `_fail(...)` exit 1, **roll markers persisted so
far are kept**; re-run resumes (committed (chat,date) skipped). A `claimed`-but-not-`committed`
marker from a killed process is re-taken after 120 min, or immediately on the next run if the
summariser succeeds (the `claimed` row is overwritten by `try_claim`'s stale path). Verified in
dev (CLI re-run + container-restart startup sweep both no-op'd).

### 6.4 Roll job interrupted by shutdown (`wait=False`)
`daily_roll_scheduler.shutdown(wait=False)` does **not** await an in-flight `_sweep_daily_roll`.
If SIGTERM lands mid-summary: the current (chat,date) is `claimed` but not `committed` → left for
the next startup catch-up sweep (within 21 days) or a later nightly tick. **Safe** — the
claim-first protocol is exactly for this. Worst case: one day's summary is a few hours late.

### 6.5 `summarize_conversation` OpenAI failure
Returns the **raw `{role}: {content}` transcript** instead of raising. The `daily_summary` record
is still written (fallback content), marker committed. A degraded-but-durable record; not
retried (it "succeeded"). Acceptable per research.md D13.

### 6.6 `MemoryManager.remember` (embedding) failure
`_create_embedding` raises → propagates out of `_roll_one_chat_day` → caught by
`_sweep_daily_roll`'s per-(chat,date) `try/except` → **marker left `claimed`, not `committed`** →
retried next sweep. No partial ChromaDB write (embed happens before `collection.add`). Safe.

### 6.7 `roll_markers.db` write failure (disk full / locked)
`try_claim`'s `INSERT` or `commit`'s `UPDATE` raises `sqlite3.OperationalError` → propagates →
per-(chat,date) `try/except` → logged, retried. If `commit` fails *after* the ChromaDB write
landed: next run's `is_rolled` is `False` → `try_claim` (stale path) → `collection.delete(where…)`
removes the orphan → re-`remember` → re-`commit`. **Idempotent overwrite by design.** No
duplicate `daily_summary`.

### 6.8 Window-shortening (`max_tokens` backstop) edge cases
- All in-window messages fit → full list returned.
- Single newest message alone exceeds `max_tokens` → it is still returned (explicit guard).
- A message with an unparseable / future `timestamp` → **kept** (never lets one bad timestamp
  empty the window); it sorts by `order_num=0` → lands at the front. Low risk; worth a WARNING.
- `max_tokens=None` (RBAC unlimited / admin) → no cap; whole 14-day window returned. For the prod
  group that is ~all 926 msgs on day 1 post-consolidation until the first nightly archive — a
  large-but-bounded prompt (~30–60k tokens, well inside the 1.05M context per research.md D11).

### 6.9 Two `PersistentClient`s on one `memory/` path
`denidin-app-prod` (running) + the backfill/consolidator (host `python3`) both open
`PersistentClient(path=prod_data/memory)`. Same `Settings`, but ChromaDB is single-process;
concurrent writers ⇒ `database is locked` / possible corruption of a **249 MB live** file.
**Hard rule: prod container stopped for the entire consolidate + backfill window.** (This is also
forced by the Mac mount being read-only — the write must happen on the Windows box or via a
stopped-container read-write remount.)

### 6.10 `_reconcile_chat_index` on 93 dirs every startup
Opens & parses all 93 `session.json` files on every `SessionManager()` construction, logs the
"maps to N session dirs" WARNING for both chats every boot. Harmless but noisy **until**
consolidation reduces it to 2 clean dirs. Post-consolidation the raw dirs move to
`sessions/_pre070_raw_<date>/` (outside the `*/session.json` + `expired/` scan) so reconcile
sees only the 2 canonical sessions.

### 6.11 Container restart between consolidation and deploy
If the 0.5.3 container is (re)started after consolidation but before the 0.5.4 deploy: 0.5.3
does **not** read `chat_index.db` — it uses its own in-memory `chat_to_session` + `get_session`'s
active-dir scan. It would find the new canonical dir (active, correct `whatsapp_chat`) and
**append the next message to it**, which is fine and forward-compatible. It would also
**not** re-archive it (0.5.3's cleanup only archives sessions past `session_timeout_hours`; a
fresh `last_active` keeps it live). Low risk. Cleanest: keep prod down from consolidation through
deploy.

---

## 7. Proposed prod migration procedure (night, downtime OK)

All steps on the Windows prod host (where `data/` is writable) or via a deliberate stopped-container
read-write remount from the Mac. Each numbered step is its own human go-ahead.

1. **Announce downtime.** Confirm no active client conversation in flight (`tail_logs.sh`).
2. **Stop prod** — `scripts/stop_all.sh prod` (denidin first, then morning-mcp). Confirm both down.
3. **Snapshot** `data/` (full copy: `sessions/`, `memory/`, `events/`, `reminders/`,
   `accounting_reconciliation/`, `media/`) to a dated backup dir on the host + pull a copy to the
   Mac. This is the rollback artifact.
4. **Dry-run the consolidator** (`--report-only`) against a **copy** of `data/sessions/`: per
   chat, N dirs → 1, total message count in vs out (must match), duplicate-id count, timestamp
   fallbacks used, integrity check on the projected result. Human reviews the report.
5. **Run the consolidator** for real against `data/sessions/`: writes 2 canonical active dirs,
   moves the 93 raw dirs to `sessions/_pre070_raw_<date>/`, strips `pending_ledger_events`,
   runs `assert_message_integrity` on each result. Exit non-zero aborts and leaves raw dirs put.
6. **Run the backfill** (`apps/rolling-memory-backfill`, host `python3`) `--since 2026-08-03
   --until <today−14>` against `data/`. Review the per-chat report (expect ~1 summary per
   non-empty pre-window day per chat).
7. **(Decision §5.3)** Optionally purge `type IN (session_summary, session_summary_fallback)`
   from both ChromaDB collections.
8. **Validate** (see §8) — all read-only, prod still stopped.
9. **Merge Feature 070**, `scripts/cut_release.sh denidin-app <version>` (human-supplied version),
   `scripts/deploy_release.sh denidin-app prod <version>` and the morning-mcp deploy — **all
   normal per-action human gates**.
10. **Post-deploy validation** (§8) + real WhatsApp turns in both prod chats (godfather 1:1 and
    the collections group) confirming: full recent context in the window, a backfilled day
    recalled, `0` `Created new session`, `roll_markers.db` fully committed, one more restart is a
    no-op.
11. Leave `sessions/_pre070_raw_<date>/` in place indefinitely (rollback + audit).

**Dev**: re-do the same consolidator against dev's `_pre070_sessions_archive_20260903/` +
current sessions so dev's real history (not the test junk) is properly consolidated and
backfilled — so dev actually exercises the multi-session path before prod does. Or accept dev as
a lighter-weight validation and rely on a **staging copy of prod data** for the true rehearsal
(recommended: rehearse the whole of §7 against the Mac-side snapshot from step 3 first).

---

## 8. Validation checklist (run at step 8 and step 10)

- [ ] `chat_index.db`: exactly 2 rows, each → its canonical active session dir.
- [ ] `assert_message_integrity` clean for both canonical sessions (`counter == live + archived == |ids|`, disjoint, files match ids).
- [ ] Total message count across both canonical sessions == total across the 93 raw dirs (minus deduped duplicate ids, minus empty dirs) — number stated and matched.
- [ ] `order_num` is `1..N` contiguous per canonical session; messages sorted by real timestamp.
- [ ] No `pending_ledger_events` key in either canonical `session.json`; `storage_path` is `null`.
- [ ] `roll_markers.db`: one row per (chat, date) in `[2026-08-03 … today−14]`, **all `committed`**; `source='migration'`.
- [ ] ChromaDB: `daily_summary` count == number of non-empty pre-window (chat, date) pairs; every record recallable with correct metadata.
- [ ] `_pre070_raw_<date>/` contains all 93 original dirs, byte-identical (checksum a sample).
- [ ] `events/`, `media/`, `reminders/reminders.db` — byte-unchanged (mtimes + sample checksums).
- [ ] Post-deploy: startup log shows `_reconcile_chat_index` with **no** "maps to N session dirs" WARNING, `run_startup_daily_roll_sweep` completes, roll scheduler armed for 02:00, **0** "Created new session".
- [ ] Post-deploy real turns: godfather 1:1 gets its recent (Sep) context; group gets its recent (Sep 1–2 work-hours) context; a question answerable only from a mid-August day is answered from that day's `daily_summary`.
- [ ] A second `docker restart` post-deploy: startup sweep is a no-op (0 OpenAI calls, 0 new records, 0 new sessions).

---

## 9. Decisions needed before Phase 10

1. **Consolidator** — approve building it (new component: spec addendum + `data-model` for the
   canonical-session rules + unit/integration tests + a dry-run against the prod snapshot). This
   is the real remaining engineering work; it did not exist in the Phase 1–9 plan.
2. **Rehearsal** — rehearse §7 end-to-end against the Mac-side prod snapshot before touching the
   live box? (Strongly recommended.)
3. **`session_summary` bloat (§5.3)** — leave / purge / purge+fuller-backfill. (Recommend purge
   after backfill.)
4. **`get_rolling_window` unbounded `archived/` read (§6.1)** — accept as a named risk with a
   follow-up ticket, or address now (skip archived ids / build a sidecar index).
5. **Backfill `--since`** — `2026-08-03` (earliest prod message) vs `2026-08-05` (prod go-live)
   vs a shorter horizon. Earlier = more billed summary calls (still cheap: ≤ ~50).
6. **Dev** — re-consolidate dev properly, or treat the prod-snapshot rehearsal as the real test.
7. **bugfix-051** (`list_reminders` cross-chat disclosure) — independent, but if reminders are in
   scope for a prod touch it could ride along. Currently its own branch, awaiting root-cause
   approval.
