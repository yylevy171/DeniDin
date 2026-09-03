---
description: "Task list — Feature 070 Rolling 14-Day Memory Window"
---

# Tasks: Rolling 14-Day Short-Term Memory Window with Nightly Daily-Summary Roll

**Input**: `specs/in-progress/070-rolling-memory-window/` — [plan.md](./plan.md), [spec.md](./spec.md),
[user-stories.md](./user-stories.md), [research.md](./research.md), [data-model.md](./data-model.md),
[contracts/](./contracts/) (9), [quickstart.md](./quickstart.md)

**Branch**: `feature/070-rolling-memory-window`

---

**Compliance** (non-negotiable):

- **CONSTITUTION.md**: no env vars (§I — config keys only, DI-passed); **Israel local time**
  (§II/bugfix-037 — `now_local()`, never naive/UTC); `pathlib.Path` (§XIV); JSON files 2-space +
  `sort_keys=True` + UTF-8 + LF (§XV); no monkey-patching (§XVII); ZERO MOCKING of internal
  components — real `SessionManager`/`MemoryManager`/`AIHandler` in every test, OpenAI + Green API
  the only mockable boundary, **never `unittest.mock` inside `tests/integration/`**; NO UNVERIFIED
  THIRD-PARTY ASSUMPTIONS (T004 gates design lock-in).
- **METHODOLOGY.md §VI**: unit/integration tests are **Task A (write, RED) → 👤 HUMAN APPROVAL →
  Task B (implement, GREEN)**; approved tests are **IMMUTABLE** without fresh human re-approval.
  The **`billed` acceptance tests** (Phase 8) are described plain-language here and coded + run
  **once, together**, after every unit/integration task is GREEN.
- **No feature flag** (spec Clarifications 2026-09-02 — deliberate, user-directed). Retired paths
  are **deleted**, not disabled.
- **Ledger frozen** — no task touches `ledger_event_manager.py` / `CURRENT_SCHEMA_VERSION`
  (REQ-MEM-043).

**Git**: work on `feature/070-rolling-memory-window`. Conventional commits referencing `REQ-MEM-*`.
Merge commits, not squash. **No deploy, no environment start, no haleluya, no prod backfill** as
part of these tasks — each is a separate explicit human decision.

### plan.md phase ↔ tasks.md phase

| `plan.md` | `tasks.md` |
|---|---|
| Phase 0 — Research spike (BLOCKING) | **T005** (inside Phase 2 Foundational) |
| Phase 1 — US1 rolling window + tolerant load + lookup | **Phase 3** (T010–T019) |
| Phase 2 — US2 nightly roll + roll markers + catch-up | **Phase 4** (T020–T025) |
| Phase 3 — US3 archive-only safety + retention | **Phase 5** (T030–T032) |
| Phase 4 — US4 one-time migration (tool build + non-billed tests) | **Phase 6** (T040a, T041a, T045–T047) |
| Phase 5 — US5 log retention (unit + integration/acceptance) | **Phase 7** (T050a–T052a, T050b–T053b) |
| Phase 6 — Final acceptance, all stories (billed AC-1/2/3/5 + SC-007, non-billed AC-6) | **Phase 8** (T070–T072) |
| Phase 4 — US4 migration *executed* on **dev** + verified | **Phase 9** (T090a, T090b, T091, T092) |
| Phase 4 — US4 migration *executed* on **prod**, non-intrusive checks only | **Phase 10** (T100, T101) |
| (setup / shared helpers / polish, implicit in plan) | **Phase 1** (T001–T004), **Phase 2** (T006–T009), **Phase 11** polish (T060–T063) |

**Phase order (2026-09-03, user-directed):** …7 US5 → **8 acceptance+billed** → **9 dev backfill+test** →
**10 prod backfill (minimal non-intrusive test)** → **11 polish (always last)**.

**Format**: `- [ ] [TaskID] [P?] [Story?] Description — file path`
`[P]` = parallelisable (different files, no incomplete-task dependency). `👤` = human gate.

---

## Phase 1: Setup

- [x] T001 [P] Add Feature 070 config keys to `AppConfiguration` — `apps/denidin-app/src/models/config.py`: extend `memory_defaults['session']` with `window_days: 14`; `memory_defaults['longterm']` with `daily_summary_top_k: 10`; add `memory_defaults` top-level `archive_retention_days: 0` and a `memory_defaults['roll']` section `{hour: 2, catchup_lookback_days: 21, stale_claim_minutes: 120}`; add a new dataclass field `logging: Dict = field(default_factory=dict)` + `from_file` defaults `{rotation_when: "midnight", backup_count: 0}`; keep tolerating a still-present `memory.session.session_timeout_hours` (ignored). No validation change beyond a non-negative check on the numeric roll keys.
- [x] T002 [P] Propagate new keys into every config file — `apps/denidin-app/config/config.example.json`, `config.dev.json`, `config.test.json`, `config.prod.json`: add `memory.session.window_days`, `memory.longterm.daily_summary_top_k`, `memory.archive_retention_days`, `memory.roll.{hour,catchup_lookback_days,stale_claim_minutes}`, and top-level `logging.{rotation_when,backup_count}`. (2-space, `sort_keys` on save, LF.)
- [x] T003 Forward the new top-level field in the hand-curated `__main__` config subset — `apps/denidin-app/denidin.py:~1024`: add `'logging': config.logging` to `config_dict` (verify `'memory': config.memory` already forwards the nested `memory.*` keys whole — it does at `denidin.py:1010`).
- [x] T004 [P] Scaffold the migration sub-app skeleton — `apps/rolling-memory-backfill/`: `requirements.txt` (openai, chromadb, tiktoken — mirror `apps/prod-ledger-backfill/requirements.txt` minus Morning deps), `conftest.py` (puts `apps/denidin-app` on `sys.path`; autouse tmp/wipe fixture pattern), `pytest.ini` (register `billed` marker; `addopts = -m "not billed"`), `tests/{unit,integration,billed}/` dirs each with `__init__.py`/`.gitkeep`, `.gitignore` (`config/*.local.json`, `venv/`, `output/`), `config/` dir with a `.gitkeep`, and `_denidin_loader.py` (import-and-re-export stubs for `SessionManager`, `RollMarkerStore`, `MemoryManager`, `collection_name_for_chat`, `summarize_conversation`, `assert_message_integrity` — filled in T045b). No business logic yet. **Runs with host `python3`** — the same documented "deliberate, narrow exception to containers-only" that `apps/prod-ledger-backfill/` uses (root `CLAUDE.md`).

**Checkpoint**: `cd apps/denidin-app && python3 -m pytest tests/unit/test_config*.py -q` still green with the new keys defaulted; `AppConfiguration.from_file('config/config.test.json')` loads and `.validate()` passes.

---

## Phase 2: Foundational — BLOCKING (must complete before ANY user story)

### T005 — Research spike (BLOCKING, gates design lock-in)

- [x] T005 👤 **BILLED-CALL APPROVAL GATE** — approved & run 2026-09-03. Delivered as a **permanent tracked tool** (not a throwaway, per user): `apps/denidin-app/scripts/model_sanity_check.{sh,py}` — "run whenever `config.ai_model` changes". Checks: (a) large 14-day-window-shaped call succeeds + `usage`; (b) prompt caching engages on identical repeat; (c) prints model + a pointer to verify published context window / pricing; (d) RECALLED MEMORIES placement A/B + an out-of-window needle-recall check.
  **RESULTS** (`logs/model_sanity_check/gpt-5.6-luna_20260903_*.txt`; recorded in `research.md` D11–D13):
  - (a) `input_tokens=99,449` (constitution **26,618** + 66,136-token window + 6 local tools) — **call SUCCEEDS**; usable window ≥ ~100K.
  - (b) identical repeat → `cached_tokens=99,446/99,449` (**~100% cache hit**) — D12 CONFIRMED.
  - (c) **CLOSED 2026-09-03** — published `gpt-5.6-luna`: context window **1,050,000** tokens, max output 128K, input $0.20 / cached $0.02 / output $1.20 per 1M (long-context surcharge only >272K input). Worst-case prompt ~130K vs 1.05M ⇒ **~88% headroom, SC-007 PASSES**. No design change; no reason to raise the 100K `max_tokens_by_role` backstop.
  - (d) **Decision: do NOT relocate the RECALLED MEMORIES block** — current placement (trailing the constitution in `instructions`) caches ~100% and the needle fact (window position 0 of 66K) is recalled correctly. Zero code change. Plan-mode decision C closed as "no change".
  - ⚠️ constitution grew 6.6× since CLAUDE.md's stale "~4.0K tokens" note — now 26.6K, a real uncached first-turn cost.

### Shared helpers (block US1/US2/US3)

- [x] T006a [P] Tests for `time_utils` day-bucketing — `apps/denidin-app/tests/unit/test_time_utils_daybucket.py`: `local_calendar_date` (aware + naive + `+00:00` legacy input all bucket to the correct Israel-local date), `start_of_local_day` (aware midnight, DST spring-forward + fall-back days), `n_calendar_days_ago(13)` / `n_calendar_days_ago(1, now=<fixed>)`, and the boundary rules from `contracts/time-utils-daybucket.md` (midnight → later day; 14-day boundary inclusive). RED.
- [x] T006b 👤 approval → implement `time_utils` day-bucketing — `apps/denidin-app/src/utils/time_utils.py`: add `local_calendar_date(dt) -> date`, `start_of_local_day(dt) -> datetime`, `n_calendar_days_ago(n, now=None) -> date` per `contracts/time-utils-daybucket.md`. Then copy **byte-identical** into `apps/morning-mcp-app/src/denidin_mcp_morning/utils/time_utils.py` and run `diff` to prove identity.
- [x] T007a [P] Tests for `collection_name_for_chat` — `apps/denidin-app/tests/unit/test_collection_name_helper.py`: pins the two live prod names (`972522968679@c.us` → `memory_972522968679`; `120363210094632983@g.us` → `memory_120363210094632983_at_g.us`), plus a `…@lid` / odd-shape input returns a collection-safe string and never raises. RED.
- [x] T007b 👤 approval → implement — `apps/denidin-app/src/managers/memory_collections.py`: `collection_name_for_chat(whatsapp_chat: str) -> str` per `contracts/memory-collections.md` (strip `@c.us`, then `.replace('@','_at_').replace(':','_')`).
- [x] T008 [P] Test-support helper only (no production code) — `apps/denidin-app/tests/helpers/__init__.py` + `apps/denidin-app/tests/helpers/seed.py`: `seed_message(session_manager, chat, role, content, days_ago)` that appends a message and then rewrites its persisted timestamp field N days back **via the real on-disk message JSON** (no internal mocks). The production-code `timestamp=` seam it *may* call is added in **T013b** (tested by T012a) — this task ships only the test helper so nothing production-facing lands without a preceding approved test.
- [x] T009 [P] `assert_message_integrity` helper — `apps/denidin-app/tests/helpers/message_integrity.py`: `assert_message_integrity(session_dir: Path)` asserting `len(messages/*.json) + len(archived/*.json) == session.message_counter == len(set(message_ids) | set(archived_message_ids))`.

**Checkpoint**: T006/T007 tests green; `time_utils.py` twin `diff` is empty; T008 seam leaves production behavior byte-identical (an existing `add_message*` test still green unchanged).

---

## Phase 3: User Story 1 — the last 14 days are always in verbatim context (P1, MVP) 🎯

**Goal**: every turn's context = every message from the last 14 Israel-local calendar days,
verbatim, oldest-first, `[sender_name]` prefix for group turns, capped read-only by the acting
role's `max_tokens_by_role`; one long-lived `Session` per chat resolved via a durable on-disk
index; tolerant session load; **the 24h-expiry / hourly-cleanup / write-time-prune machinery is
deleted**.

**Independent test**: seed a chat with messages dated 20/15/13/2/0 days ago, build the turn
context via the real path → 13/2/0-day present verbatim oldest-first, 20/15-day absent; restart
sim continues the session; poison-session loads with one WARNING.

### Tests (RED) — 👤 approval gate before ANY Phase 3 implementation

- [x] T010a [P] [US1] `apps/denidin-app/tests/unit/test_session_manager_window.py` — `get_rolling_window`: US1 sc1 (20/15/13/2/0-day seed → correct set, oldest-first), sc3 (group `[sender_name]` prefix), sc4 (window > `max_tokens` → oldest dropped, newest always present, terminates when `max_tokens` < newest message), legacy `+00:00` message bucketing, future-dated (clock-skew) message → not-empty + no crash, empty chat → `[]`.
- [x] T011a [P] [US1] `apps/denidin-app/tests/unit/test_session_manager_tolerant_load.py` — `_session_from_dict`: unknown top-level key dropped, **exactly one** WARNING (not ERROR, not per-load), session still fully usable; generic (a second unknown key name also tolerated — not an allowlist); a legacy message dict missing `content`/`role` read via `.get(...)` without `KeyError`.
- [x] T012a [P] [US1] `apps/denidin-app/tests/unit/test_session_chat_index.py` — chat→session stable across a fresh `SessionManager` on the same `data_root` (restart sim); `_reconcile_chat_index()` picks up a pre-existing UUID-dir session (incl. one under `expired/`); a chat mapping to >1 dir → keeps `max(message_counter)`, one WARNING, **deletes nothing**; `chat_to_session` cache is a read-through over the DB; the **`add_message_with_tokens(..., timestamp=<past dt>)` seam** persists the given timestamp (production default `None` → `now_local()`, byte-identical to before).
- [x] T013a [P] [US1] `apps/denidin-app/tests/unit/test_retired_paths_removed.py` — **static** (SC-011): 0 source references (outside this test + `specs/`) to `session_timeout_hours` expiry logic, `SessionCleanupThread`, `run_startup_cleanup`, `_process_session_cleanup`, `transferred_to_longterm` reads, `_prune_until_under_limit`, `prune_to_limit`, `clear_session`, `remove_from_index`, `find_expired_active_sessions`, `find_untransferred_archived_sessions`, `recover_orphaned_sessions`, `transfer_session_to_long_term_memory`; and no `Path.unlink` / `os.remove` / `shutil.rmtree` on a message/session path in `session_manager.py` / `daily_summary_roll_service.py` / `ai_handler.py` (roll path) / `memory_collections.py`. **Also asserts** (negative constraints, G1/G3): the feature's changed modules add **0** references to `CURRENT_SCHEMA_VERSION` / `ledger_event_manager` (REQ-MEM-043), and no `feature_flags` key is introduced for Feature 070 in any `config/config.*.json` or in code (REQ-MEM-060).
- [x] T014a [P] [US1] `apps/denidin-app/tests/integration/test_rolling_window_integration.py` — real `SessionManager` + real `AIHandler`, tmp `data_root`, OpenAI mocked at the network boundary only: seed a dated conversation via the real persistence API; **golden-file** assertion on the exact `input` items handed to the OpenAI boundary for a fixed message sequence (pins the new builder's output); **restart scenario** — construct a fresh `SessionManager`/`AIHandler` on the same `data_root`, dispatch a real Green API webhook JSON through `bot.router` → asserts the existing session continued (`message_counter` +1, prior turns in context, **no** "Created new session" log for that chat) = US1 sc5 / AC-2 shape; **poison-session** — write a `session.json` fixture with `pending_ledger_events: []` + a future-dated message → WARNING-level log + normal participation.
- [x] T015a [P] [US1] **Replacement tests** (old approved tests are IMMUTABLE — these are new files/classes, not edits): `apps/denidin-app/tests/unit/test_session_manager_tokens_v2.py` — asserts the new config values load and that there is **no write-time prune** (append 200 messages over the client 4000-token limit → all 200 on disk, `message_counter == 200`); and a new `TestConversationHistoryV2` in `test_ai_handler_memory.py` asserting `get_response` feeds `get_rolling_window` output (not the old `get_conversation_history`).

### 👤 APPROVAL GATE — review & approve T010a–T015a. Tests are frozen after this.

### Implementation (GREEN) — blocked until the gate above

- [x] T010b [US1] Implement `get_rolling_window(whatsapp_chat, *, now=None, window_days=14, max_tokens=None) -> List[Dict]` — `apps/denidin-app/src/managers/session_manager.py` per `contracts/session-manager-window.md`: resolve the session via the index; load each id from `messages/` else `archived/` (missing → skip + WARNING); in-window iff `local_calendar_date(ts) >= n_calendar_days_ago(window_days-1, now)`; oldest-first; Feature 039 `[sender_name]` prefix reused from `get_conversation_history_for_session`; if `max_tokens`: accumulate `count_tokens` newest→oldest, stop once over, exclude the oldest, always keep the newest. Read-only.
- [x] T011b [US1] Implement `_session_from_dict(data)` tolerant filter — `apps/denidin-app/src/managers/session_manager.py`: `{f.name for f in fields(Session)}` filter + one WARNING on dropped keys; wire into `_load_session` / `_load_sessions`; per-message reads use `.get("content","")` / `.get("ai_required_role") or .get("role") or "user"`. Add `Session.archived_message_ids: List[str] = field(default_factory=list)`.
- [x] T012b [US1] Implement `chat_index.db` + `_reconcile_chat_index()` — `apps/denidin-app/src/managers/session_manager.py` per `contracts/session-manager-window.md` + `data-model.md` §2: `ReminderManager` connection idiom (one long-lived `sqlite3.connect(check_same_thread=False)`, `row_factory=Row`, idempotent `_init_schema`, never reads `AppConfiguration` — caller composes the path); `get_session` resolves via `SELECT` then the in-memory cache; `_reconcile_chat_index()` scans `*/session.json` (+ `expired/`), `INSERT OR IGNORE`, dup → `max(message_counter)` + WARNING + no delete; runs once in `__init__`.
- [x] T013b [US1] `add_message_with_tokens(...)` replaces `add_message_with_token_limit` — `apps/denidin-app/src/managers/session_manager.py`: same persistence, **no** prune call; add an **optional** `timestamp: Optional[datetime] = None` parameter (default `None` → `now_local()`, production byte-identical — the T012a-tested seam); update the chat index `updated_at`. Swap call sites: `ai_handler.py:~3099,~3115,~3763,~3768` and `services/reminder_delivery_service.py:~128`.
- [x] T014b [US1] **Delete** retired `SessionManager` symbols — `apps/denidin-app/src/managers/session_manager.py`: remove `_prune_until_under_limit`, `prune_to_limit`, `clear_session`, `is_session_expired`, `find_expired_active_sessions`, `find_untransferred_archived_sessions`, `get_sessions_needing_cleanup`, `remove_from_index`, the `session_timeout_hours` ctor param + `self.session_timeout_hours`.
- [x] T015b [US1] **Delete** the cleanup service + its `AIHandler` counterparts — delete `apps/denidin-app/src/services/cleanup_service.py`; remove `AIHandler.transfer_session_to_long_term_memory` and `AIHandler.recover_orphaned_sessions` (`apps/denidin-app/src/handlers/ai_handler.py`); remove the `session_timeout_hours` kwarg at `ai_handler.py:~1461`.
- [x] T016b [US1] Wire `AIHandler` to the window builder + shared collection helper — `apps/denidin-app/src/handlers/ai_handler.py`: history fetch (~`ai_handler.py:2039-2057`) → `session_manager.get_rolling_window(chat, max_tokens=user_obj.token_limit, window_days=config.memory['session']['window_days'])`; recall collection name via `collection_name_for_chat`; the single per-turn conversational recall call's `top_k` → `config.memory['longterm'].get('daily_summary_top_k', 10)` per `contracts/ai-handler-recall.md` (leave `MemoryManager.recall`'s parameter default at 5).
- [x] T017b [US1] Remove cleanup wiring from `denidin.py` — `apps/denidin-app/denidin.py`: delete the `run_startup_cleanup` call (~L414), the `SessionCleanupThread` start + `denidin.cleanup_thread` (~L417-428), the `recover_orphaned_sessions` call in `__main__` (~L1088), the `cleanup_thread` stop lines in all shutdown sites, `DeniDin.cleanup_thread`, and the now-dead imports (`from src.services.cleanup_service import ...`).
- [x] T018b [US1] **Delete** retired test files — `apps/denidin-app/tests/unit/test_background_cleanup.py`, `apps/denidin-app/tests/unit/test_session_manager_tokens.py`, `apps/denidin-app/tests/integration/test_archived_session_recovery.py`, `apps/denidin-app/tests/billed/test_session_transfer.py`; and remove the named classes/methods in `test_session_manager.py` (`TestSessionExpiration`, `TestSessionManagement::test_clear_session`), `test_ai_handler_memory.py` (`TestAIHandlerSessionToLongTermMemory`, `TestAIHandlerStartupRecovery`, `test_handle_summarization_failure_gracefully`, `TestSessionTransferRealMethod`), `test_memory_integration.py` (`test_session_expiration_detection`, `test_session_manager_clears_session`), `test_memory_integration_billed.py` (`test_orphaned_session_recovery_active_session`).
- [x] T019b [US1] Audit `config/runtime_constitution.md` for stale memory-model language (G2) — `apps/denidin-app/config/runtime_constitution.md`: grep for `session`, `expire`, `24 hour`, `24h`, `short-term`, `RECALLED MEMORIES`, hourly-cleanup references. This feature adds **no** model-facing tool, so no new tool-boundary section is needed — but if the constitution *describes* the retired mechanism to the model (e.g. "your memory of a conversation resets after…"), update it to describe the rolling 14-day window + daily summaries instead. If T005/T070 relocates the RECALLED MEMORIES block, reflect the new placement here. If nothing stale is found, record "audited, no change" in the commit message. (Config = hot-reloaded; no code dependency.)

**Checkpoint (US1 done)**: `cd apps/denidin-app && python3 -m pytest tests/unit tests/integration -v` all green; `test_retired_paths_removed.py` green; a manual restart sim (fresh `SessionManager`, same `data_root`) continues the session; `pylint src/ --fail-under=7.0` + `mypy src/` clean on changed files. **US1 is independently shippable** (14-day verbatim window works; history older than 14 days simply isn't recalled yet — US2 adds that).

---

## Phase 4: User Story 2 — each night the previous day is summarized into long-term memory (P1)

**Goal**: 02:00 Israel-local `CronTrigger` job (wired in `denidin.py __main__`) that, per chat,
summarizes the previous calendar day into **exactly one** ChromaDB `daily_summary` record via the
sanitizing `remember()` path; empty days get a marker, no billed call; idempotent per (chat, date)
via `RollMarkerStore` (`PRIMARY KEY(chat,date)`, claim-first `claimed`→`committed`); a bounded
startup catch-up sweep covers days missed while down.

**Independent test**: seed 2 chats (incl. a `…@g.us`) across 3 past days (one empty for one chat);
run the roll worker for those dates → one summary per non-empty (chat, date), zero for the empty
one, each recall-able with correct metadata, a re-run makes 0 billed calls; simulate 2-day
downtime → catch-up rolls exactly the missed days once each.

### Tests (RED) — 👤 approval gate

- [x] T020a [P] [US2] `apps/denidin-app/tests/unit/test_roll_marker_store.py` — `try_claim` → `commit` → `is_rolled` true only after commit; double `try_claim` → second `False`; empty-day marker (`commit(count=0, memory_id=None)`) → `is_rolled` true; a `claimed` row younger than `stale_claim_minutes` → `try_claim` `False`; older → re-claimable `True`; never overwrites a `committed` row; ctor takes only `storage_dir` (asserts it does **not** accept `AppConfiguration`).
- [x] T021a [P] [US2] `apps/denidin-app/tests/unit/test_summarizer.py` — `summarize_conversation(client, model, messages)` returns the model summary on success (OpenAI mocked); on the mocked call raising → returns the raw `role: content` transcript (fallback), logs one WARNING, does **not** raise; no embedding / ChromaDB / marker side effects.
- [x] T022a [P] [US2] `apps/denidin-app/tests/unit/test_daily_roll_service.py` — `_sweep_daily_roll` (OpenAI mocked): one summary per non-empty (chat, date) incl. `@g.us`; empty day → marker, 0 boundary calls; re-run over an already-`committed` range → 0 summaries / 0 boundary calls (SC-010); downtime D1+D2 → each rolled once via `run_startup_daily_roll_sweep`; OpenAI failure for one (chat, date) → no `commit`, retried next run, **other chats still roll** (REQ-MEM-027); poison session isolated; a backstop-archived message (in `archived/`) still included in its day's summary (Contract 3); day-bucketing identical to `get_rolling_window`; DST roll night fires once via the `trigger=` / `now=` seams; a (chat, date) older than `catchup_lookback_days` is NOT auto-rolled and logs one INFO pointing at the backfill; **an outage spanning > `window_days`** (C2 / REQ-MEM-030) → `run_startup_daily_roll_sweep` rolls every day within `catchup_lookback_days` exactly once, days older are left for the backfill, and no roll fails for "missing raw content" (US3 guarantees it is all on disk).
- [x] T023a [P] [US2] `apps/denidin-app/tests/integration/test_daily_roll_integration.py` — real `SessionManager` + real `MemoryManager` + real ChromaDB, tmp `data_root`, OpenAI mocked at the boundary: invoke the real `_sweep_daily_roll` (not the timer); assert summary count, `roll_markers.db` rows + states, `recall()` retrievability + metadata (`type/chat/date/scope/user_phone/message_count/source`), boundary call-count across a re-run; the **group** collection resolves + is created via `collection_name_for_chat` with **no** raw `client.get_collection` in the roll path (bugfix-035 H1); the `collection.delete(where=…)` idempotent-overwrite on a manual marker reset.
- [x] T024a [P] [US2] `apps/denidin-app/tests/integration/test_recall_surfaces_daily_summary.py` — seed 12+ `daily_summary` records over ~3 weeks + a couple of legacy `session_summary` records for a chat; ask (through `bot.router`, OpenAI mocked) a question whose answer is in the oldest daily summary → it appears in the RECALLED MEMORIES block (proves `top_k=10` keeps it where 5 would drop it — `contracts/ai-handler-recall.md`); US2 sc5.

### 👤 APPROVAL GATE — review & approve T020a–T024a. Frozen after.

### Implementation (GREEN)

- [x] T020b [US2] Implement `RollMarkerStore` — `apps/denidin-app/src/managers/roll_marker_store.py` per `contracts/roll-marker-store.md` + `data-model.md` §3: `ReminderManager` connection idiom; schema `roll_markers(chat, date, status, message_count, summary_memory_id, source, claimed_at, committed_at, PRIMARY KEY(chat, date))`; `try_claim` (atomic `INSERT`; `sqlite3.IntegrityError` → `False` unless stale `claimed`); `commit`; `is_rolled` (= `status='committed'`); `stale_claim_minutes` a plain arg (caller passes `config.memory['roll']['stale_claim_minutes']`). Path: caller composes `str(Path(config.data_root) / "memory_rolls")`.
- [x] T021b [US2] Implement `summarize_conversation` — `apps/denidin-app/src/handlers/summarizer.py` per `contracts/summarizer.md`: module-level function; lift the existing session-summary `responses.create(model, instructions=<the current summarizer str, verbatim>, input="Summarize this conversation...\n\n{conv_text}", max_output_tokens=1000)` + raw-transcript fallback out of the (now-deleted) `transfer_session_to_long_term_memory`. No new prompt.
- [x] T022b [US2] Implement `get_messages_for_local_date(session, date)` — `apps/denidin-app/src/managers/session_manager.py` per `contracts/session-manager-window.md`: all of that chat's messages (live `messages/` + `archived/`) whose `local_calendar_date` equals `date`, oldest-first, same item shape as `get_rolling_window`.
- [x] T023b [US2] Implement `daily_summary_roll_service` — `apps/denidin-app/src/services/daily_summary_roll_service.py` per `contracts/daily-summary-roll-service.md`, mirroring `reminder_delivery_service.py`: `start_daily_roll_scheduler(global_context, *, roll_hour=2, trigger=None)` → `BackgroundScheduler` + one `add_job(max_instances=1, CronTrigger(hour=roll_hour, minute=0, timezone=LOCAL_TZ))`; `run_startup_daily_roll_sweep(global_context)` (synchronous, `lookback_days=catchup_lookback_days`); `_sweep_daily_roll(global_context, *, now=None, lookback_days=None, log_prefix="")`; `_roll_one_chat_day` per the contract's step list (`is_rolled`→skip / `try_claim`→skip / gather / empty→`commit(0)` / else `summarize_conversation`→`collection.delete(where=…)`→`remember(...)`→`commit`); per-chat `try/except`, errors never escape; retry bound = the lookback window (contract §"Retry semantics").
- [x] T024b [US2] `AIHandler.__init__` gains `self.roll_marker_store` — `apps/denidin-app/src/handlers/ai_handler.py`: construct `RollMarkerStore(str(Path(config.data_root) / "memory_rolls"))` alongside the existing `SessionManager` construction; reachable as `global_context.ai_handler.roll_marker_store`.
- [x] T025b [US2] Wire the roll into `denidin.py __main__` — `apps/denidin-app/denidin.py` per `contracts/daily-summary-roll-service.md` §Wiring: after `initialize_app` + the reminder + accounting startup sweeps → `run_startup_daily_roll_sweep(denidin)` → `denidin.daily_roll_scheduler = start_daily_roll_scheduler(denidin, roll_hour=denidin.config.memory.get("roll",{}).get("hour",2))` → then `message_source.start(...)`. `DeniDin.__init__` gains `daily_roll_scheduler=None`; add `.shutdown(wait=False)` in all 3 shutdown sites.

**Checkpoint (US2 done)**: unit + integration green; re-run of `_sweep_daily_roll` over a
`committed` range → 0 boundary calls, 0 new records (SC-010); group path raises no `NotFoundError`;
`pylint`/`mypy` clean. **US1+US2 together = the coherent new model.**

---

## Phase 5: User Story 3 — raw messages are never deleted; context never blows the token budget (P1)

**Goal**: the read-only per-turn cut (T010b) + a nightly **physical archive move** (`rename` into
`{session_dir}/archived/`, never `unlink`) of messages older than 14 days or beyond the *largest*
role N (100000); documented "retain forever" policy; test suite scopes archived lookups to its own
`session_id`.

**Independent test**: tiny configured backstop, seed > backstop in-window messages, build context →
live window fits N, every trimmed file exists at its archive path, the nightly roll for that day
still includes them.

### Tests (RED) — 👤 approval gate

- [x] T030a [P] [US3] `apps/denidin-app/tests/unit/test_archive_only_maintenance.py` — `archive_aged_and_backstopped_messages`: an aged (>14d) message → moved to `archived/`, `assert_message_integrity` still balances; in-window messages beyond N=100000 → oldest archived, newest retained; a tiny `max_backstop_tokens` → terminates, keeps the newest; idempotent (2nd call moves nothing new); retention policy documented as keep-all (`archive_retention_days=0` → no pruning path exists).
- [x] T031a [P] [US3] `apps/denidin-app/tests/integration/test_archive_only_integration.py` — real `SessionManager`, tmp `data_root`, tiny configured backstop; seed > backstop via the T008 seam; drive `bot.router` → live window fits N; every trimmed message file exists at `{session_dir}/archived/<id>.json`; the nightly roll (`_sweep_daily_roll`) for that day still includes the archived messages; **static** audit: no `unlink`/`os.remove`/`rmtree` on message/session paths across all feature modules; archived-session lookups in the whole test suite use their own `session_id`, never `rglob(...)[0]` (bugfix-035 H3).

### 👤 APPROVAL GATE — approve T030a–T031a.

### Implementation (GREEN)

- [x] T030b [US3] Implement `archive_aged_and_backstopped_messages(session, *, now, window_days, max_backstop_tokens) -> int` — `apps/denidin-app/src/managers/session_manager.py` per `contracts/session-manager-window.md`: `rename` (never `unlink`) into `{session_dir}/archived/` messages older than `n_calendar_days_ago(window_days-1, now)` OR beyond `max_backstop_tokens` newest→oldest; move ids `message_ids` → `archived_message_ids`; persist `session.json`; `message_counter` unchanged; return count moved.
- [x] T031b [US3] Call the archive step once per chat per sweep — `apps/denidin-app/src/services/daily_summary_roll_service.py`: after the per-(chat, date) roll loop, `session_manager.archive_aged_and_backstopped_messages(session, now=now, window_days=config.memory['session']['window_days'], max_backstop_tokens=100000)`, per-chat `try/except`.
- [x] T032b [US3] Document the retention policy — `apps/denidin-app/src/managers/session_manager.py` docstring + `quickstart.md`: `archive_retention_days=0` = retain archived messages forever by design; no pruner built this feature (REQ-MEM-034).

**Checkpoint (US3 done)**: `assert_message_integrity` balances after aging + backstop trim; static
audit finds 0 message/session deletions in feature modules (SC-004, SC-011); misconfigured tiny
backstop still returns the newest message and terminates.

---

## Phase 6: User Story 4 — build the one-time migration tool (P2, separately gated; executed in Phases 9–10)

**Goal**: standalone `apps/rolling-memory-backfill/backfill_daily_summaries.py` that creates one
daily summary per non-empty calendar day older than 14 days + a marker for every processed
(chat, date), idempotent via the shared roll-marker DB, reads raw messages only.

### Tests (RED) — 👤 approval gate before ANY Phase 6 implementation

- [x] T040a [P] [US4] `apps/rolling-memory-backfill/tests/unit/test_backfill_cli.py` — **non-billed**, loader mocked at the seam (`_denidin_loader` symbols replaced with fakes; OpenAI never constructed): `argparse` contract from `contracts/backfill-cli.md` (`--since` required no default, `--until` default `today_local−14d`, `--chat` repeatable, `--yes`, **no** `--env` / `--dry-run`); every precondition failure (`--until` inside the 14-day window, `--since` after `--until`, missing `{data_root}/sessions/`, unreadable `--config`) → `⚠️` message + return 1 **before** any loader/network call; the typed-`yes` confirm prompt is shown unless `--yes`; the per-(chat, date) decision logic (`is_rolled`→skip, empty day→`commit(0)` no summary call, non-empty→summarize→remember→commit) exercised against the fake loader with call-count assertions; a mid-run per-item exception aborts loudly with a non-zero return and a partial report; the grand-total + per-chat report lines are emitted. RED.
- [x] T041a [P] [US4] `apps/rolling-memory-backfill/tests/integration/test_backfill_integration.py` — **non-billed**, real `SessionManager` + real `RollMarkerStore` + real `MemoryManager` + real ChromaDB via the real `_denidin_loader`, tmp `data_root`, **OpenAI mocked at the network boundary only** (constitution — no internal mocks): seed a chat (via the T008 seam) with history spanning > 14 days incl. one fully-empty past day; run `main([...])` end to end → one `daily_summary` record per non-empty pre-window (chat, date) recallable with correct metadata (`type/chat/date/scope/user_phone/message_count/source="migration"`), one `roll_markers.db` row per (chat, date) incl. empty (`committed`); `assert_message_integrity` byte-identical before + after; a same-args re-run → 0 boundary calls, 0 new records (idempotent via the shared marker DB); a subsequent real `_sweep_daily_roll` over the same range → skips every migrated day; the `…@g.us` collection resolves via `collection_name_for_chat` with **no** raw `client.get_collection` (bugfix-035 H1). RED.

### 👤 APPROVAL GATE — review & approve T040a–T041a. Frozen after.

### Acceptance test (AC-4) — described here; coded + first run in Phase 9 (the dev **billed** run)

- **T090a [US4]** (Phase 9) — the same flow as T041a but **real billed** against a live dev chat + live `apps/morning-mcp-app-dev`, with the printed per-chat report reviewed by a human. Non-billed correctness is already locked by T040a/T041a here; Phase 9 only adds the real-money end-to-end confirmation + the operator-report review.

### Implementation (GREEN) — build the tool, no execution against any real data

- [x] T045b [P] [US4] Fill `_denidin_loader.py` — `apps/rolling-memory-backfill/_denidin_loader.py`: put `apps/denidin-app` on `sys.path`; import + re-export the real `SessionManager` (with `get_messages_for_local_date` / the chat index), `RollMarkerStore`, `MemoryManager`, `collection_name_for_chat`, `summarize_conversation`, `assert_message_integrity`.
- [x] T046b [US4] Implement the CLI — `apps/rolling-memory-backfill/backfill_daily_summaries.py` per `contracts/backfill-cli.md`: `main(argv=None) -> int` / `sys.exit(main())`; `argparse` (`--data-root` req, `--config` req, `--since YYYY-MM-DD` req no default, `--until` optional default `today_local−14d`, `--chat` repeatable, `--yes`; **no** `--env`, **no** `--dry-run`); preconditions before any network call (fail closed, `⚠️` + return 1); `assert_message_integrity` before; enumerate chats from `{data_root}/sessions/*/session.json` (+ `expired/`); per (chat, date) in range → `is_rolled` skip / `try_claim(source="migration")` / gather / empty→`commit(0)` / else `summarize_conversation`→`remember(source="migration")`→`commit`; mid-run per-item failure aborts loudly; `assert_message_integrity` after; per-chat + grand-total report; typed-`yes` confirm unless `--yes`.
- [x] T047b [P] [US4] `apps/rolling-memory-backfill/quickstart.md` — the operator runbook (mirror `quickstart.md` Part 1), covering **both** the dev run (Phase 9) and the prod run (Phase 10): approve → stop the target container → temp read-write mount → dry-check without `--yes` → confirm estimate → run → review report → tear down mount → (separately) deploy the new-model code. Why stopping matters (two `PersistentClient`s on one path). `catchup_lookback_days` safety net. Fresh approval per environment-touching step.

**Checkpoint (US4 tool built)**: T040a + T041a green (`cd apps/rolling-memory-backfill && python3 -m pytest tests/ -q`);
`main(["--help"])` works; preconditions fail closed with `⚠️` + exit 1 **before** any network call;
`_denidin_loader.py` imports the real components cleanly; idempotency + integrity proven non-billed.
**No run against dev or prod happens in this phase** — dev execution is Phase 9, prod execution is
Phase 10, each a separate per-run human-approved operation per the runbook.

---

## Phase 7: User Story 5 — prod application logs retained across rotation (P2, parallelisable)

**Goal**: one root-logger handler (kills the multi-handler rotation race),
`TimedRotatingFileHandler(backupCount=0)` + gzip, and a `logging:` `json-file` cap on both compose
services — `denidin-app` **and** its byte-identical `morning-mcp-app` twin.

### 👤 DESIGN-REVIEW CHECKPOINT — DONE (2026-09-03): user walked through `contracts/logger-retention.md`; approved with two additions — `json-file` cap raised 10m→**50m**, and **lossless rotation** (fail-safe gzip rotator + a dedicated multi-thread test). Twin resolved as "mirror the core, allow documented deltas" (literal byte-identity impossible: per-app `log_filename`/`log_level` defaults, `DEFAULT_VERSION_FILE`, morning-only `reconfigure_package_log_level`); `TestTwinCoreIsMirrored` guards the shared core. `test_logger.py` (both apps) rewritten to the root-handler model (blanket unit-test approval this session).

### Tests (RED) — 👤 approval gate

- [x] T050a [P] [US5] `apps/denidin-app/tests/unit/test_logger_retention.py` — point `setup_logger` at a tmp dir with a sub-second `when`, emit enough lines to force ≥ 3 rotations → every rotated `*.gz` exists, decompresses, content intact + ordered; after N `get_logger(name_i)` calls the **root** logger has exactly one file handler + one stream handler (no per-name stacking); a child logger has 0 handlers and `propagate is True`; `backup_count=0` keeps **all** rotations (nothing deleted). **Lossless-rotation test (contract §4)**: several threads emit a known countable sequence `1..N` continuously while `when="S"` forces ≥ 2 rotations under load → the full set `1..N` appears exactly once across `{active file} ∪ {*.gz} ∪ {any leftover plaintext}` — no gaps, no dupes; a `rotator` that raises leaves the plaintext segment in place (not unlinked). **`test_logger.py`'s size-based `RotatingFileHandler` / `.1..5` / `maxBytes==10MB` / per-name-handler assertions are superseded here** — those tests are updated/removed in the same GREEN step (unit tests, blanket-approved this session).
- [x] T051a [P] [US5] `apps/morning-mcp-app/tests/unit/test_logger_retention.py` — the twin assertions for the morning-mcp-app logger, including the same lossless-rotation test (contract §4).
- [x] T052a [P] [US5] `apps/denidin-app/tests/integration/test_logger_retention_integration.py` — the spec's US5 "Integration test requirement" + the **US5 acceptance evidence** (non-billed; see Phase 8 AC-6): drive the logger **through the real config→`setup_logger` path** used at boot (compose the `logging` block from a tmp `config.*.json` via `AppConfiguration`, tmp log dir, tiny `when`), run a real bootstrap that emits app log lines, force ≥ 3 rotations under load → all rotated `*.gz` retained + decompress + ordered; assert the live process has **exactly one** root file handler after `initialize_app` (multi-handler race designed out); assert `docker/docker-compose.{dev,prod}.yml` each declare the `json-file` `max-size`/`max-file` cap on both services (parse the YAML, not `grep`). RED.

### 👤 APPROVAL GATE — approve T050a–T052a.

### Implementation (GREEN)

- [x] T050b [US5] Refactor `logger.py` — `apps/denidin-app/src/utils/logger.py` per `contracts/logger-retention.md`: attach file + console handlers **once to the root logger** in `setup_logger` (guarded against re-stacking); `get_logger(name)` → `logging.getLogger(name)`, `propagate=True`, no own handlers; `_VersionFilter` → root logger; file handler → `TimedRotatingFileHandler(when=<logging.rotation_when>, backupCount=<logging.backup_count=0>, encoding="utf-8")` with gzip `rotator`/`namer` (the `namer` appends `.gz`; the `rotator` gzips + removes the plaintext intermediate — a *log* file, allow-listed in T031a's audit). Keep `LocalTimeFormatter` + `LOCAL_LOG_DATEFMT`. `setup_logger` reads `when`/`backupCount` from its params (composed from `config.logging` by the caller).
- [x] T051b [US5] Mirror the refactor into `apps/morning-mcp-app/src/denidin_mcp_morning/utils/logger.py`; the **shared core** (`_gzip_*`, `_build_file_handler`, `setup_logger`, `reconfigure_file_rotation`, `get_logger`, formatter/filter) must be identical — `TestTwinCoreIsMirrored` asserts it, normalising the documented per-app deltas.
- [x] T052b [P] [US5] Compose `logging:` cap — `docker/docker-compose.prod.yml` + `docker/docker-compose.dev.yml`: add `logging: {driver: json-file, options: {max-size: "50m", max-file: "5"}}` to **both** `denidin-app-<env>` and `morning-mcp-app-<env>` services. Verify with `docker compose --project-directory . -f docker/docker-compose.dev.yml config`.
- [x] T053b [P] [US5] Written audit finding → `quickstart.md` Part 2 is already drafted; confirm it matches the final code (root-handler design + `TimedRotatingFileHandler` + gzip + the `json-file` dependency statement + the post-deploy read-only verification commands).

**Checkpoint (US5 done)**: both apps' `test_logger_retention.py` (unit) + `test_logger_retention_integration.py`
green; `docker compose config` shows the cap on all 4 service entries; `diff` of the two `logger.py`
files is empty. T052a is the standing **US5 acceptance evidence** (AC-6) — it runs with the normal
non-billed suite, no separate billed pass needed (logging makes no OpenAI call).

---

## Phase 8: Final acceptance pass — every user story covered (AC-1..AC-6, SC-007) — after Phases 3–7 are GREEN

**Story coverage:** US1 → AC-2, AC-3, SC-007 · US2 → AC-1 · US3 → AC-3 · US4 → AC-4 (Phase 9,
billed) · US5 → AC-6 (the T052a integration test — non-billed, logging makes no OpenAI call). Every
Feature 070 user story has at least one acceptance-level scenario; the `billed` ones are here, the
non-billed US5 one rides the normal suite and is only *confirmed* here.

Per METHODOLOGY §VI: the billed scenarios are **described plain-language below**; the test code is
written **here** (not earlier) and run **once, together**. `billed` tier — no per-run approval,
`scripts/run_single_test.sh`, **sound off each result as it completes**. `apps/morning-mcp-app-dev`
must be up for any cross-app scenario. AC-4 (backfill billed run) is Phase 9.

- [x] T070 [P] Write `apps/denidin-app/tests/billed/test_rolling_memory_billed.py` covering:
  - **AC-1 (US1+US2)** — seed a real `@g.us` conversation across 3 *simulated* days (timestamps via the T008 seam; `window_days=2` in the test config so day-1 is out of window); call `_sweep_daily_roll` with an explicit `now` per day (3 real summarization calls); ask (real OpenAI) a question answerable only from day-1 → correct answer from the recalled daily summary; assert 1 billed summary call/day, 0 duplicate records, no `NotFoundError` for the group collection.
  - **AC-2 (US1)** — real conversation → build a fresh `SessionManager`/`AIHandler` on the same `data_root` (restart sim) → dispatch a new webhook → the bot (real OpenAI) continues seamlessly with pre-restart context, no re-priming.
  - **AC-3 (US1+US3)** — tiny `max_tokens_by_role` in the test config; seed > that many in-window messages; the bot (real OpenAI) answers from the newest context; disk audit shows every trimmed message at its `archived/` path.
  - **AC-5 (US1+US2)** — load a `session.json` fixture with `pending_ledger_events` (the `0f5eaa04` shape) into a running app → one WARNING, no `TypeError`, no recurring load error on subsequent turns/sweeps → the chat participates in a `_sweep_daily_roll` (1 real summary call).
  - **SC-007** — time `get_rolling_window()` over a ~1500-message realistic window, N iterations → added p95 ≤ 300 ms (amended 2026-09-03); measure the worst-case window's real token count + constitution + tools → within the `gpt-5.6-luna` budget confirmed in T005 with ≥ 30% headroom.
- [x] T071 Run T070 scenario-by-scenario via `scripts/run_single_test.sh`, sounding off each PASS/FAIL. **All 5 green (2026-09-03):** AC-1, AC-2, AC-3, AC-5, SC-007. SC-007 latency budget amended 150→300 ms p95 (user sign-off — synthetic 1500-msg window on cold storage measured ~219 ms; real prod days ~30-60 msgs). AC-5 fixture reworked to build the session through `SessionManager` + inject `pending_ledger_events` into the real `session.json` (the hand-rolled dir was never linked to the chat index).
- [x] T072 [US5] **AC-6 confirmation (non-billed)** — `apps/denidin-app/tests/integration/test_logger_retention_integration.py` re-run green (7 passed, 2026-09-03).

**Checkpoint (Phase 8 done)**: AC-1, AC-2, AC-3, AC-5, SC-007 green in one billed pass **and** AC-6
(T052a) green — i.e. an acceptance scenario has passed for every one of US1–US5 (US4/AC-4 lands in
Phase 9).

---

## Phase 9: US4 backfill — executed against **dev**, with full testing (AC-4)

The Phase 6 tool is now run for real against dev data. `billed` tier, cross-app (`apps/morning-mcp-app-dev`
must be up). Every environment-touching step is a **separate, explicit, per-run human approval** — the
`run_denidin.sh dev` / container stop / mount steps are all env-start actions under CLAUDE.md.

- [ ] T090a [US4] Code `apps/rolling-memory-backfill/tests/billed/test_backfill_billed.py` — the **real-billed** twin of T041a (AC-4): against a live dev chat seeded via the T008 seam with > 14 days of history + `apps/morning-mcp-app-dev` up → one real summary per non-empty past day + markers for every day incl. empty; same-args re-run → **0 billed calls** / 0 new records; a following real `_sweep_daily_roll` skips every migrated day; `assert_message_integrity` before + after; the per-chat report is printed and human-reviewed. (T040a/T041a already lock the non-billed logic — this proves the real-money path.)
- [ ] T090b [US4] 👤 **env-start approval** → run the real backfill against **dev** per `apps/rolling-memory-backfill/quickstart.md`: stop `denidin-app-dev`, temp read-write mount, dry-check (no `--yes`), confirm the estimate, run with `--since <dev history start>`, review the per-chat report, tear the mount down.
- [ ] T091 [US4] Post-run dev verification: one `daily_summary` record per non-empty pre-window (chat, date) in the dev ChromaDB; one `roll_markers.db` row per (chat, date) in range, all `committed`; `assert_message_integrity` across every dev session dir clean; start `denidin-app-dev` again and confirm a normal turn still recalls a backfilled day.
- [ ] T092 [US4] Manual dev continuity E2E (👤 env-start approval): send a message, `docker restart denidin-app-dev`, send another → `logs/dev/denidin.log` shows no "Created new session"; force a catch-up sweep → one `daily_summary` per past day + one `roll_markers.db` row per (chat, date).

**Checkpoint (Phase 9 done)**: T090a green; the dev backfill ran once, is idempotent on re-run, left
every raw message byte-unchanged; dev continuity across a real container restart confirmed.

---

## Phase 10: US4 backfill — executed against **prod**, minimal non-intrusive testing only

Real production data. **No test seeds, no synthetic chats, no write beyond the backfill's own
`daily_summary` + marker records.** Verification is **read-only**. This entire phase is gated on a
fresh, explicit, prod-specific human go-ahead for **each** step; nothing here is automatic.

- [ ] T100 [US4] 👤 **explicit prod approval** → run the real backfill against **prod** per `apps/rolling-memory-backfill/quickstart.md` (Windows-prod box): stop `denidin-app-prod`, temp read-write mount, dry-check (no `--yes`) and **report the estimate to the human before proceeding**, run with `--since <prod history start>` only on go-ahead, capture the per-chat report, tear the mount down, restart `denidin-app-prod`.
- [ ] T101 [US4] Non-intrusive prod verification (read-only, no approval needed — not a start/stop): via the standing read-only `~/denidin-winprod-data` mount + `tail_logs.sh` — spot-check that new `daily_summary` records exist for a handful of known pre-window (chat, date) pairs; `roll_markers.db` row count is in the expected range and all `committed`; `denidin-app-prod` logs show a clean startup and a normal turn recalling a backfilled day; **no** message-file mtimes changed (compare against the read-only mount). No bulk re-scan, no synthetic traffic.

**Checkpoint (Phase 10 done)**: prod backfill ran once under per-step approval; read-only checks
confirm summaries + markers present and raw prod messages untouched; prod is back up.

---

## Phase 11: Polish & cross-cutting — always last

- [ ] T060 [P] `pylint src/ --fail-under=7.0 --rcfile=.pylintrc` + `mypy src/ --config-file=mypy.ini` clean for `apps/denidin-app`; same for `apps/morning-mcp-app` on its changed files.
- [ ] T061 [P] Full non-billed suite green — `cd apps/denidin-app && python3 -m pytest tests/ -v` (billed + expensive excluded by default) — 0 failures, 0 errors, 0 unexpected skips; `cd apps/morning-mcp-app && python3 -m pytest tests/ -v`.
- [ ] T062 [P] Update `.github/ARCHITECTURE.md` — the memory-flow diagram + the "Message flow" section: rolling window replaces `get_conversation_history`; nightly roll replaces the hourly cleanup cycle; note the chat index + roll-marker DB.
- [ ] T063 [P] `[haleluya]` Update the root + clone `CLAUDE.md` "Architecture" section — `session_manager.py` / `memory_manager.py` bullets, the new `daily_summary_roll_service.py` / `roll_marker_store.py` / `memory_collections.py` / `summarizer.py`, and remove the `cleanup_service.py` bullet. **Deferred execution — runs as part of the haleluya flow, not Phase 11 proper.**

**Feature complete** when Phase 8's acceptance pass is green and Phase 9's checkpoint holds. Phase 10
(prod backfill) and haleluya (docs + spec move + the bugfix-035 / bugfix-044 "Superseded by Feature
070" closure notes + PR) and deploying the new-model code anywhere are **separate** explicit human
decisions made after that.

---

## Dependencies & completion order

```
Phase 1 (Setup: T001-T004)
      ↓
Phase 2 (Foundational: T005 spike 👤 BLOCKING · T006-T009 shared helpers)
      ↓
Phase 3  US1  (T010-T018)  ── MVP, independently shippable
      ↓
Phase 4  US2  (T020-T025)  ── needs US1 (session model, chat index, collection helper, window builder)
      ↓
Phase 5  US3  (T030-T032)  ── needs US1 (builder) + US2 (roll service to call the archive step)
      ↓
Phase 6  US4 tool build + non-billed tests  (T040a,T041a,T045-T047)  ── needs US1+US2+US3   [P2 · separately gated]
Phase 7  US5  (T050a-T052a,T050b-T053b)  ── independent of US1-US4; PARALLEL with Phases 3-6   [P2]
      ↓
Phase 8  Acceptance — every story (billed AC-1/2/3/5 + SC-007; non-billed AC-6/US5)  (T070-T072)
      ↓
Phase 9  US4 backfill executed on DEV + tested  (T090a, T090b, T091, T092)  ── AC-4; per-run env approval
      ↓
Phase 10 US4 backfill executed on PROD, non-intrusive checks only  (T100, T101)  ── separate explicit prod approval per step
      ↓
Phase 11 Polish (T060-T063)  ── always last
```

- **US1 → US2 → US3** are ordered, with one nuance: `T030a/T030b` (the `archive_aged_and_backstopped_messages` method itself) need only US1 and can be built in parallel with Phase 4; only `T031b` (wiring the archive call into `_sweep_daily_roll`) actually gates on US2.
- **US5 (Phase 7)** touches only `logger.py` (+ twin) + compose + config — no overlap with US1-US4
  files. It may be done any time after Phase 1. `[P]` at the phase level.
- **US4 tool (Phase 6)** is P2 and separately gated; its *code* can be built once US1-US3 land. It is
  never *run* against real data until Phase 9 (dev) / Phase 10 (prod), each a separate human decision.
- **Phase 10 (prod backfill)** is not a prerequisite for "feature complete" — Phase 8 green + Phase 9
  checkpoint is. Phase 10 and deploying the new-model code are follow-on human-gated operations.

## Parallel opportunities

- **Phase 1**: T001 ∥ T002 ∥ T004 (T003 after T001).
- **Phase 2**: T006a ∥ T007a ∥ T008 ∥ T009 (all different files); T005 (spike) is independent and
  can run first while the helper tests are written.
- **Phase 3 tests**: T010a ∥ T011a ∥ T012a ∥ T013a ∥ T014a ∥ T015a (six different test files).
- **Phase 4 tests**: T020a ∥ T021a ∥ T022a ∥ T023a ∥ T024a.
- **Phase 5 tests**: T030a ∥ T031a.
- **Phase 6 tests**: T040a ∥ T041a.
- **Phase 7 tests**: T050a ∥ T051a ∥ T052a.
- **Phase 7** runs fully parallel to Phases 3-6.
- **Phase 8**: T070 is one file; T071 runs its scenarios sequentially; T072 (AC-6, non-billed) any time.
- **Phase 9**: T090a first (RED → 👤), then T090b (dev run) → T091 → T092 sequentially.
- **Phase 11**: T060 ∥ T061 ∥ T062 ∥ T063.

## MVP scope

**Phase 1 + Phase 2 + Phase 3 (US1)** = the MVP: the 14-day verbatim window, one long-lived session
per chat, restart continuity, tolerant load, and the retired machinery gone. Ships value on its own
for any chat < 14 days old. US2 is the immediate fast-follow (co-equal P1) so aging chats don't
regress.

## Independent test criteria (per story)

| Story | Independently testable by |
|---|---|
| US1 | Seed 20/15/13/2/0-day messages → build context → assert the 13/2/0 set oldest-first, 20/15 absent; restart sim continues; poison-session loads with one WARNING. (T010a, T012a, T014a) |
| US2 | Seed 2 chats × 3 past days (1 empty) → run `_sweep_daily_roll` → one summary per non-empty (chat, date), 0 for empty, recall-able; re-run → 0 billed calls; 2-day downtime → catch-up rolls each missed day once. (T022a, T023a) |
| US3 | Tiny backstop, seed > backstop → build context fits N, every trimmed file at its archive path, nightly roll still includes them; static no-`unlink` audit. (T030a, T031a) |
| US4 | Chat with > 14 days history → `main([...])` (real components, OpenAI-boundary mock) → one summary per non-empty past day + markers; same-args re-run no-op; follow-up roll skips migrated days; raw files byte-unchanged; every precondition fails closed before any network call. (T040a unit, T041a integration; T090a billed in Phase 9) |
| US5 | Config→`setup_logger` path, tmp dir, tiny `when`, force ≥ 3 rotations under load → all `.gz` retained + intact; exactly one root file handler after `initialize_app`; both compose files declare the `json-file` cap on both services. (T050a/T051a unit, T052a integration = AC-6) |
| US5 | Tmp dir, tiny `when`, force ≥ 3 rotations → every `*.gz` segment present + intact; one root handler after N `get_logger` calls. (T050a, T051a) |

## Format validation

All tasks above carry `- [ ]`, a `T###` id, `[P]` where parallelisable, `[US#]` on every user-story
task (none on Setup/Foundational/Polish/Acceptance), and an explicit file path. Test tasks are
`T###a` (RED, 👤 gate) → `T###b` (GREEN). ✅
