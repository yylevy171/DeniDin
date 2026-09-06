# Feature 070 — `/speckit.plan` Handoff

**Written**: 2026-09-02 · **Branch**: `feature/070-rolling-memory-window` (speckit ID `070-rolling-memory-window`)
**Clone**: `coder1` (Avi) · **Working dir**: `/Users/yaron/Projects/DeniDin/coder1`

This file records where the `/speckit.plan` step for Feature 070 stands so the next
session can resume without re-deriving context. It is a working note, **not** a SpecKit
artifact — delete it (or ignore it) at haleluya time.

---

## 1. What the task is

Governing request: **"go plan / continue"** → run SpecKit `/speckit.plan` for Feature 070
(Rolling 14-Day Memory Window), following `.github/agents/speckit.plan.agent.md` manually
(there is no `Skill` entry for speckit — it returns "Unknown skill").

Feature 070 replaces DeniDin's 24h session-expiry Tier-1 memory with:
- a rolling **14-day verbatim** short-term window (one long-lived `Session` per chat, never
  expires, deterministic on-disk lookup; restart no longer wipes context);
- a nightly **02:00 Israel-local** per-day summary roll into **one ChromaDB record per
  (chat, date)**, idempotent via SQLite roll markers, with a bounded startup catch-up sweep;
- a **token/size backstop** = `min(last 14 calendar days, last N tokens)` where
  `N = acting role's max_tokens_by_role` — read-only per-turn cut dropping the **oldest**
  in-window messages + a nightly physical **archive move** (`rename`, never `unlink`);
- **US4** — one-time prod migration (standalone sub-app) to backfill summaries for history
  older than 14 days (go-live 2026-08-05). Separate explicit approval per run; run backfill
  against target env FIRST, then deploy new-model code;
- **US5** — audit + fix prod app logs so they survive rotation (single root-logger handler
  kills the multi-handler race + `TimedRotatingFileHandler backupCount=0` + gzip + a
  `logging:` cap on both compose services; both `denidin-app` and `morning-mcp-app` twins).

Legacy defects (bugfix-035 H1/H2/H3, bugfix-044) are **NOT** a separate Bug-Driven-Development
track (explicit user direction 2026-09-01) — each is structurally eliminated by the new
architecture or fixed inline, proven by a named acceptance scenario. Bugfix specs get a
"Superseded by Feature 070" status note **at haleluya, not now**.

---

## 2. State of the SpecKit artifacts

| Artifact | Path | Status |
|---|---|---|
| `spec.md` | `specs/done/v0.5.4-70/070-rolling-memory-window/spec.md` | ✅ committed, clarified 2026-09-02 |
| `user-stories.md` | same dir | ✅ committed (US1–US5 + AC-1..AC-6) |
| `checklists/requirements.md` | same dir | ✅ committed, all `[NEEDS CLARIFICATION]` resolved |
| `plan.md` | same dir | ⬜ **still the empty 118-line template** — `setup-plan.sh` copied it, nothing filled in |
| `research.md` | same dir | ⬜ not created |
| `data-model.md` | same dir | ⬜ not created |
| `contracts/` | same dir | ⬜ not created |
| `quickstart.md` | same dir | ⬜ not created |

`setup-plan.sh --json` was already run (with `SPECIFY_FEATURE=070-rolling-memory-window`
prefix — required, because `feature/070-…` fails speckit's `^[0-9]{3}-` branch regex). Output:
```
{"FEATURE_SPEC":".../spec.md","IMPL_PLAN":".../plan.md",
 "SPECS_DIR":".../070-rolling-memory-window","BRANCH":"070-rolling-memory-window","HAS_GIT":"true"}
```

**No artifact file has been written yet.** No git changes on the branch from this plan work.

---

## 3. The approved plan (source content for every artifact)

`ExitPlanMode` was called and the plan is **APPROVED**. Full text lives at:
`/Users/yaron/.claude/plans/groovy-stargazing-lollipop.md` (re-injected into context each
session as a system-reminder). Do **not** edit it unless the user asks for plan changes.

### 3a. Locked decisions (5 clarify + 3 plan-mode)

| # | Decision | Resolution |
|---|---|---|
| Clarify 1 | Roll-marker storage | Small SQLite DB under `data/`, one row per (chat, date) incl. empty days, Feature 054 `reminders.db` pattern |
| Clarify 2 | Token-backstop `N` | Acting role's existing `max_tokens_by_role` limit — no new config key for the value. Group turn: role `GroupMembershipResolver` resolves |
| Clarify 3 | Canonical message store | One long-lived `Session` per chat, never expires, deterministic on-disk lookup keyed on `whatsapp_chat` |
| Clarify 4 | Feature flag | **No feature flag** — deliberate override of the CLAUDE.md/CONSTITUTION §I default. Retired paths deleted, not disabled. Tests cover only new behavior |
| Clarify 5 | Bounding catch-up sweep | Run one-time backfill against target env FIRST, then deploy new-model code. Bounded `catchup_lookback_days` config key as safety net |
| Plan-mode A | Backstop trim | Read-only per-turn cut (builder reads newest→oldest, stops at `N`; **excluded = always oldest**, newest always kept) + nightly physical archive move of messages older than 14 days or beyond the largest role `N` (100000). Never `unlink()` |
| Plan-mode B | US5 fix depth | Full fix — single root-logger handler + daily rotation `backupCount=0` + gzip + `logging:` size cap on both compose services, both app twins |
| Plan-mode C | Prompt placement | **IN scope** (overrides spec's "Out of Scope" line). Phase 0 may relocate the RECALLED MEMORIES block AND reconsider 14-day-window placement, optimizing for prompt-cache — but every change verified with real billed `gpt-5.6-luna` calls showing no functional regression |

### 3b. Decisions the plan settles (were open per requirements.md lines 109-115; no user input needed — follow existing patterns)

- **Nightly-roll scheduler wiring** → `denidin.py __main__`, NOT `initialize_app` (every existing
  billed-call scheduler is wired there; `denidin.py:430-443` comment explains why — spec text
  saying `initialize_app` is imprecise).
- **Chat→session lookup** → dedicated tiny SQLite index `{data_root}/sessions/chat_index.db`,
  table `chat_sessions(chat TEXT PRIMARY KEY, session_id TEXT NOT NULL, updated_at TEXT)`,
  owned by `SessionManager`, `ReminderManager` connection idiom. Session dirs stay UUID-named.
  `chat_to_session` stays as a non-authoritative read-through cache. `_reconcile_chat_index()`
  runs once in `__init__`, scans existing `*/session.json` (+ `expired/`), `INSERT OR IGNORE`;
  a chat mapping to >1 dir → pick `max(message_counter)`, log one WARNING, delete nothing.
- **`remove_from_index` guard** → moot; no expiry ⇒ no "remove a live session" path;
  `remove_from_index` + the whole 4-step cleanup are deleted.
- **Archive retention** → keep forever by design. Config safety valve
  `memory.archive_retention_days` default `0` = never prune; pruner NOT built this feature.
- **`top_k` for multi-week recall** → new key `memory.longterm.daily_summary_top_k` default
  `10`, used only for the per-chat recall call. Global `top_k_results=5` untouched.
- **Roll-marker race handling** → claim-first two-phase (`claimed` → `committed`) with
  `PRIMARY KEY(chat, date)` + `sqlite3.IntegrityError` as the claim-loss signal.
- **Migration script location** → new standalone sub-app `apps/rolling-memory-backfill/`,
  mirroring `apps/prod-ledger-backfill/`.
- **Boot order** in `__main__` after `initialize_app`: reminder startup sweep + scheduler →
  accounting startup sweep + scheduler → NEW daily-roll startup catch-up sweep (bounded by
  `memory.roll.catchup_lookback_days`) → NEW daily-roll scheduler → `message_source.start()`.
  `initialize_app` LOSES `run_startup_cleanup`, `SessionCleanupThread` start,
  `recover_orphaned_sessions`.

### 3c. New config keys

`memory.session.window_days` (14) · `memory.longterm.daily_summary_top_k` (10) ·
`memory.archive_retention_days` (0) · `memory.roll.hour` (2) ·
`memory.roll.catchup_lookback_days` (21) · `memory.roll.stale_claim_minutes` (120) ·
new top-level `logging` dict (`rotation_when: "midnight"`, `backup_count: 0`) ·
compose `logging: {driver: json-file, options: {max-size: "10m", max-file: "5"}}` on both
services in both `docker/docker-compose.{prod,dev}.yml`.

### 3d. New files the plan creates

- `apps/denidin-app/src/managers/memory_collections.py` — `collection_name_for_chat(whatsapp_chat) -> str`
- `apps/denidin-app/src/managers/roll_marker_store.py` — `RollMarkerStore`
- `apps/denidin-app/src/handlers/summarizer.py` — `summarize_conversation(client, model, messages) -> str`
- `apps/denidin-app/src/services/daily_summary_roll_service.py`
- `apps/denidin-app/tests/helpers/message_integrity.py` — `assert_message_integrity(session_dir)`
- `apps/rolling-memory-backfill/` sub-app (`_denidin_loader.py`, `backfill_daily_summaries.py`,
  `quickstart.md`, `requirements.txt`, `conftest.py`, `tests/test_backfill.py`)

### 3e. Deleted

`apps/denidin-app/src/services/cleanup_service.py`; test files
`tests/unit/test_background_cleanup.py`, `tests/unit/test_session_manager_tokens.py`,
`tests/integration/test_archived_session_recovery.py`, `tests/billed/test_session_transfer.py`;
named test classes/methods across `test_session_manager.py`, `test_ai_handler_memory.py`,
`test_memory_integration.py`, `test_memory_integration_billed.py` (exact list in the approved plan).

### 3f. New key signatures

```
SessionManager.get_rolling_window(whatsapp_chat, *, now=None, window_days=14, max_tokens=None) -> List[Dict]
SessionManager.get_messages_for_local_date(session, date)
SessionManager.add_message_with_tokens(...)   # replaces add_message_with_token_limit
SessionManager.archive_aged_and_backstopped_messages(session, *, now, window_days, max_backstop_tokens)
RollMarkerStore.try_claim(chat, date, source) -> bool
RollMarkerStore.commit(chat, date, message_count, memory_id)
RollMarkerStore.is_rolled(chat, date) -> bool
collection_name_for_chat(whatsapp_chat) -> str
summarize_conversation(client, model, messages) -> str
daily_summary_roll_service._sweep_daily_roll(global_context, *, now=None, lookback_days=None, log_prefix="")
daily_summary_roll_service.run_startup_daily_roll_sweep(global_context)
daily_summary_roll_service.start_daily_roll_scheduler(global_context, *, roll_hour=2, trigger=None)
time_utils.start_of_local_day(dt) / local_calendar_date(dt) -> date / n_calendar_days_ago(n, now=None)
```

### 3g. Daily-summary ChromaDB record

metadata: `{"type":"daily_summary","chat":<chat>,"date":"YYYY-MM-DD","scope":PRIVATE,
"user_phone":<chat>,"message_count":N,"source":"daily-roll"|"catch-up"|"migration"}`
(`user_phone = chat` matches the existing `session_summary` RBAC convention so
`recall_with_rbac_filter` returns it). Before `remember`,
`collection.delete(where={"type":"daily_summary","chat":chat,"date":date})` for idempotent overwrite.

### 3h. RollMarkerStore DB

Path: `roll_markers.db` under `str(Path(config.data_root) / "memory_rolls")` — deliberately
NOT under `{data_root}/memory/` (ChromaDB owns that dir). Schema:
`roll_markers(chat, date, status, message_count, summary_memory_id, source, claimed_at, committed_at, PRIMARY KEY(chat, date))`.

### 3i. 7-phase approach

0. Research spike (BLOCKING, needs billed-call approval) — real `gpt-5.6-luna` calls: ~62–70K
   window fits with ≥30% headroom (SC-007); `cached_tokens > 0` on repeat; confirm max
   context + pricing vs OpenAI account/docs; A/B RECALLED MEMORIES / chat-history placement
   with a scripted multi-turn functional-regression check (REQ-MEM-037, plan-mode C).
1. US1 rolling window + tolerant load + deterministic lookup (MVP)
2. US2 nightly roll + roll markers + catch-up
3. US3 archive-only safety + retention
4. US4 one-time prod migration
5. US5 log retention
6. Final acceptance pass — every story (billed AC-1/2/3/5 + SC-007; non-billed AC-6/US5)

---

## 4. Measured facts to bake into the artifacts

### Prod logging state (measured live 2026-09-02 via `denidin-winprod` docker context)

`src/utils/logger.py` uses `RotatingFileHandler` size-based, `maxBytes=10MB`,
`backupCount=5`, no gzip, no `basicConfig`/`dictConfig`. Every module → its **own** handler on
the **same** `logs/denidin.log`, `propagate=False`. Plus a `StreamHandler` (stderr),
`LocalTimeFormatter` (renders `Asia/Jerusalem` with `%z`), `_VersionFilter`. `get_logger`
test-env shortcut: if root logger already has handlers (pytest), returns
`logging.getLogger(name)` + version filter, reusing root handlers. `/app/logs` is a host bind
mount (`docker-compose.prod.yml:20` → `./apps/denidin-app/logs/prod:/app/logs`).

LIVE prod: `denidin.log` ~6.99 MB active; `denidin.log.1..5` = 8.4KB / 11KB / 3.7KB / 27KB /
9.2KB, all frozen 2026-08-31 14:56–15:08, **out of order** (`.2` newer than `.1`) — the
multi-handler-race signature. Nothing before 2026-08-31 15:08 survives (go-live 2026-08-05).
`docker logs`: `json-file` driver, `Opts=map[]` — **NO** `max-size`/`max-file` on either
service in either compose file; path `/var/lib/docker/containers/<id>/<id>-json.log` on the
Windows box, unbounded across container lifetime. Byte-identical logger twin in
`apps/morning-mcp-app`.

### Prod scale

Two prod chats only: `120363210094632983@g.us`, `972522968679@c.us`. Go-live 2026-08-05.
Group chat full history ≈ 62K tokens over Aug 5–Sep 1; growth ≈ 2,200 tokens/day; godfather
`max_tokens_by_role` = 100000. Existing prod ChromaDB collection names:
`972522968679@c.us` → `memory_972522968679`; `120363210094632983@g.us` →
`memory_120363210094632983_at_g.us`.

### Raw-data-preservation audit (done 2026-09-01, in spec.md Dependencies)

`_prune_until_under_limit` provably never fired in prod — monotonic `message_counter` ==
`len(message_ids)` == files-on-disk for all 90 sessions; `clear_session`/`prune_to_limit` have
zero callers; `archive_session` is a `rename`.

### Unverified third-party facts (CONSTITUTION "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS")

`gpt-5.6-luna` context window + token pricing, and OpenAI prompt-cache behavior, are
**unverified** — `research.md` MUST mark them explicitly as unverified assumptions with a
verify-before-design-lock plan (the Phase 0 spike). The doc explicitly permits this.

---

## 5. Key code locations (from the approved plan's appendix — verify line numbers, they drift)

- `SessionManager` constructed **inside `AIHandler.__init__`** (`ai_handler.py:1459-1462`), not
  `initialize_app`. Nightly roll reaches it via `denidin.ai_handler.session_manager`.
- `chat_to_session: Dict[str,str]` in-memory only, rebuilt by disk scan in `_load_sessions`
  (`session_manager.py:440-456`).
- `get_conversation_history_for_session` (`session_manager.py:325-375`) — group
  `[sender_name] ` prefix block; `max_tokens` accepted but ignored today.
- Write-time cap: `add_message_with_token_limit` → `_prune_until_under_limit`
  (`session_manager.py:870-895`) — `message_file.unlink()`, called from
  `ai_handler.py:3099,3115,3763,3768`.
- `Session(**data)` deserialization in 3 places, NO field filtering (bugfix-035 H2). Tolerant
  `{f.name for f in fields(...)}` pattern already exists in `config.py` and `denidin.py:~360`.
- Cleanup: `SessionCleanupThread` (`services/cleanup_service.py`), `cleanup_interval_seconds`
  default 3600. `_process_session_cleanup` 4-step: archive → `transfer_session_to_long_term_memory`
  → `remove_from_index` → `transferred_to_longterm=True`. bugfix-035 H1 unbounded retry:
  failed transfer never runs step 4 → `find_untransferred_archived_sessions` re-selects hourly
  forever. Collection name `f"memory_{whatsapp_chat.replace('@c.us','')}"` (`ai_handler.py:3976`)
  leaves `@g.us` intact; `client.get_collection` (`ai_handler.py:4002`) raises `NotFoundError`
  for groups. `recover_orphaned_sessions` at `ai_handler.py:4019-4087`, called `denidin.py:1088`.
- `memory_manager.py` (432 lines) — one collection per chat. Sanitization is a single inline
  expr `collection_name.replace('@','_at_').replace(':','_')` at `memory_manager.py:114` inside
  `get_or_create_collection` (not a named helper). `remember(content, collection_name,
  metadata=None) -> id`; `recall(query, collection_names, top_k=5, min_similarity=0.0)`;
  `recall_with_rbac_filter(...)` is what `AIHandler` calls (needs `metadata['scope']` +
  `metadata['user_phone']`).
- Recall happens in **`create_request`** (`ai_handler.py:1597-1709`), not `get_response`.
  Final `instructions` order (`_build_instructions`, `ai_handler.py:1815-1873`): constitution
  text → `"\n\nRECALLED MEMORIES (from past conversations):\n"` + `- <content> (relevance:
  X.XX)` lines → `"\n\n---\n"` → `"THE CURRENT DATE AND TIME IS …"` → `"YOUR CURRENT VERSION
  IS <v>"`. The RECALLED MEMORIES block sits between the stable constitution and the `---` →
  breaks the cache prefix at the first memory line.
- Primary call `_call_openai_api` (`ai_handler.py:1875-1929`): `responses.create(model=
  config.ai_model, instructions=..., input=input_items, max_output_tokens=request.max_tokens
  [, tools=...])`. No temperature/previous_response_id/store. SDK `max_retries=config.max_retries` (=1).
- Summarizer call `transfer_session_to_long_term_memory` (`ai_handler.py:3915-4017`):
  `responses.create(model=config.ai_model, instructions=<plain str>, input=f"Summarize this
  conversation...\n\n{conv_text}", max_output_tokens=1000)`; try/except → raw `role: content`
  transcript fallback (`used_fallback=True`, `type='session_summary_fallback'`). Reuse this shape.
- `config.py`: `memory` is a plain untyped `Dict` (no `MemoryConfig` dataclass). Add nested
  keys to `memory_defaults` at `config.py:139-152`; storage-path loop `for section in
  ['session','longterm']` at ~164. `__main__` in `denidin.py` has a hand-curated `config_dict`
  subset (`denidin.py:997-1024`) — SECOND place any new top-level field must be added; nested
  `memory.*` rides along only if `memory` is forwarded whole (verify).
- `time_utils`: `now_local()` = `datetime.now(ZoneInfo("Asia/Jerusalem"))`. NO day-bucketing /
  start-of-day / "N days ago" helper exists — must add.
- SQLite idiom (`reminder_manager.py`): ONE long-lived `sqlite3.connect(check_same_thread=
  False)`, `row_factory=Row`, opened in `__init__`, held on `self._conn`, never closed;
  idempotent `executescript` `CREATE TABLE IF NOT EXISTS` in `_init_schema()`; `execute` +
  immediate `commit()`; no `with conn:`; manager NEVER reads `AppConfiguration` (test asserts
  ctor signature); no migration framework. NO `UNIQUE`/`IntegrityError` idiom exists there yet
  — `PRIMARY KEY(chat,date)` + `sqlite3.IntegrityError` is a NEW small standard pattern.
- Scheduler idiom (`reminder_delivery_service.py`, `accounting_reconciliation_service.py`):
  bare `BackgroundScheduler()` in `start_*_scheduler(global_context, ...)`, single `add_job`
  `max_instances=1`, `trigger: Any = None` testability seam, `_sweep_*(global_context, ...,
  now=None, log_prefix="")` worker + synchronous `run_startup_*_sweep(global_context)` twin
  (wider lookback, main thread before scheduler starts), wired in `denidin.py __main__` ONLY.
  `CronTrigger(hour=2, minute=0, timezone=LOCAL_TZ)` valid; `CronTrigger(minute="*/60")`
  raises ValueError. `.shutdown(wait=False)` in 3 sites.
- Backfill precedent (061/062): `apps/prod-ledger-backfill/` standalone Python sub-app, host
  `python3` (documented containers-only exception), `argparse`, `main(argv=None) -> int`,
  `sys.exit(main())`; `--since YYYY-MM-DD` required no default, `--until` optional inclusive,
  reused output-dir = dedup key, `--creds-file` gitignored; NO `--env`, NO `--dry-run`.
  Preconditions before any network call; fail closed; mid-run per-item failure aborts loudly;
  re-run resumes. Prod apply = ad-hoc script over a temporary rw sshfs mount
  `~/denidin-winprod-data-rw` (torn down after); apps restarted after
  (`morning-mcp-app-prod` first, then `denidin-app-prod`).

---

## 6. METHODOLOGY / CONSTITUTION anchors for `plan.md`

- **METHODOLOGY §VI** — "TDD" = the `billed`/`expensive` acceptance tests (§VI.a), described
  plain-language in `speckit.tasks`, code written + run once at the end (this plan's Phase 6).
  Unit/integration keep RED→GREEN / Task A→approval→Task B / immutable discipline (§VI.b).
- **METHODOLOGY §VII "Integration Contracts"** — mandatory section in `plan.md` for
  multi-component features. Format: `Component A ↔ Component B Contract` with
  "A MUST" / "B PROVIDES" / "B EXPECTS".
- **METHODOLOGY §IV** — Phase 0 Research → Phase 1 Design → Phase 2 Tasks → Phase 3 Impl;
  Constitution check before Phase 0, re-check after Phase 1; each phase needs a
  Validation/Checkpoint section.
- **METHODOLOGY §IX** — Technology Choice sections (Decision Date / Rationale / Alternatives /
  Migration Path) for significant tech decisions.
- **CONSTITUTION** — ZERO MOCKING of internal components (mocks only for OpenAI/Green API, never
  in `tests/integration/`); NO UNVERIFIED THIRD-PARTY ASSUMPTIONS (→ Phase 0 spike + unverified
  markers); §I no env vars (feature-flag default **deliberately overridden** — justify in
  Complexity Tracking); §II Israel local time (`now_local()`); §XIV `pathlib.Path`; §XV JSON
  2-space + `sort_keys=True` + UTF-8 + LF; §XVII no monkey-patching; §XVIII startup external
  handshakes must retry with bounded backoff (applies to the catch-up sweep's bounded lookback).
- **CLAUDE.md** — LEDGER SCHEMA VERSION is human-only; Feature 070 REQ-MEM-043 forbids touching
  `CURRENT_SCHEMA_VERSION`. Every new tool-bearing feature needs constitution boundaries —
  Feature 070 adds **no** model-facing tools (note this in `plan.md`).
- The plan.md template's own top note says "comply with CONSTITUTION.md (§I-III)" and mentions
  "UTC timestamps mandatory" — that is **stale**; bugfix-037 replaced UTC-everywhere with
  Israel-local-everywhere. Use `now_local()`, note the template line is outdated.

---

## 7. Remaining steps (in order)

1. **Fill `plan.md`** from §3 above: Summary; Technical Context (Python 3.11 / APScheduler +
   ChromaDB + `sqlite3` / storage: session JSON + ChromaDB + SQLite roll-marker + SQLite chat
   index / pytest / Docker Linux / single project + `apps/rolling-memory-backfill/` sub-app /
   Perf: SC-007 ≤150ms p95 added latency + ≥30% context headroom / Constraints: Israel local
   time, no env vars, no ledger change / Scale: 2 prod chats, ~2,200 tokens/day); Constitution
   Check + gates; Project Structure (concrete `apps/denidin-app/src/...` tree + backfill
   sub-app tree, no "Option" labels); **Integration Contracts** section; Phase 0–6 with
   Validation/Checkpoint each; Complexity Tracking (the deliberate no-feature-flag override +
   the new `PRIMARY KEY(chat,date)` + `IntegrityError` pattern).
2. **`research.md`** — Decision / Rationale / Alternatives format; the ~8 settled decisions
   (§3b) + the Phase 0 spike deliverables marked "unverified assumption — MUST verify before
   design lock".
3. **`data-model.md`** — entities: long-lived `Session` (+ `archived_message_ids: List[str] =
   field(default_factory=list)`); `chat_sessions` table; `roll_markers` table + states
   `claimed`→`committed` (+ stale re-take after `stale_claim_minutes`); daily-summary ChromaDB
   record + metadata; config keys.
4. **`contracts/`** — internal API contracts for every signature in §3f + the backfill CLI
   contract + the logger contract.
5. **`quickstart.md`** — US4 operator runbook (approve → stop target container → run backfill
   against its `data/` → deploy new-model code → catch-up + nightly roll take over; why
   stopping matters = avoid two ChromaDB `PersistentClient`s on one path; `catchup_lookback_days`
   safety net; fresh approval per prod-touching step) + the US5 written audit finding (the §4
   prod-logging table + multi-handler-race explanation + `json-file` dependency statement +
   forced-rotation verification procedure).
6. **Run** `SPECIFY_FEATURE=070-rolling-memory-window .specify/scripts/bash/update-agent-context.sh copilot`
   (verify `which python3` / venv resolves inside `coder1` first).
7. **Re-evaluate Constitution Check** post-design in `plan.md`.
8. **Stop and report** branch + IMPL_PLAN path + generated artifacts.
9. **Then `/speckit.analyze`** for cross-artifact consistency (requirements.md lines 116-117
   note this pass has not happened).

## 8. Do NOT

Run haleluya · deploy anything · start any environment · run the migration · make billed calls
without the Phase 0 approval gate · spawn agents (user hasn't asked) · edit the approved plan
file · touch sibling clones · add the "Superseded by Feature 070" notes to the bugfix specs
(that is a haleluya-time step).
