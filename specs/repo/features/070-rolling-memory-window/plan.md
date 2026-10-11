# Implementation Plan: Rolling 14-Day Short-Term Memory Window with Nightly Daily-Summary Roll

**Branch**: `feature/070-rolling-memory-window` (speckit id `070-rolling-memory-window`) | **Date**: 2026-09-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/done/v0.5.4-70/070-rolling-memory-window/spec.md` (+ [user-stories.md](./user-stories.md), [checklists/requirements.md](./checklists/requirements.md))

---

**IMPORTANT**: This plan complies with:

- **CONSTITUTION.md**: no environment variables (§I — all tunables are `memory.*` / `logging.*`
  config keys, DI-passed); **Israel local time everywhere** (§II, as amended by bugfix-037 —
  `now_local()` / `time_utils`; there is no UTC in this codebase, so the template's own
  "UTC timestamps mandatory" line above is **stale** and does not apply); `pathlib.Path` (§XIV);
  JSON files 2-space indent + `sort_keys=True` + UTF-8 + LF (§XV); no monkey-patching (§XVII);
  startup external handshakes retry with bounded backoff (§XVIII — the catch-up sweep's bounded
  lookback and per-chat isolation); ZERO MOCKING of internal components (§I/§V — real
  `SessionManager` / `MemoryManager` / `AIHandler` in every test, OpenAI + Green API the only
  mockable boundary, never `unittest.mock` inside `tests/integration/`); NO UNVERIFIED THIRD-PARTY
  ASSUMPTIONS (Phase 0 spike gates design lock-in for `gpt-5.6-luna` context/pricing + prompt
  caching).
- **METHODOLOGY.md**: §IV phased execution with a validation/checkpoint gate per phase; §VI "TDD"
  = the final `billed` acceptance pass (Phase 6), described plain-language in `tasks.md`, coded and
  run once at the end — unit/integration tests keep the RED→GREEN / Task A→approval→Task B /
  test-immutable discipline (§VI.b); §VII **Integration Contracts** (mandatory — see the section
  below); §IX Technology Choice records (`research.md`).
- **Root `CLAUDE.md` banners**: `LedgerEventManager.CURRENT_SCHEMA_VERSION` is **not touched**
  (REQ-MEM-043); this feature adds **no** model-facing tools, so no new `runtime_constitution.md`
  tool-boundary section is required; the one-time prod backfill (US4) and every environment
  start/deploy remain separate, explicit, per-run human decisions outside this plan.

**Deliberate CONSTITUTION override**: **no feature flag** for the new memory model (clarified
2026-09-02, explicit user direction). Justified in [Complexity Tracking](#complexity-tracking).

---

## Summary

Replace DeniDin's session-expiry Tier-1 memory (24-hour idle expiry → hourly `SessionCleanupThread`
→ per-session billed summarization → one ChromaDB record per expired session) with a **time-scoped**
model:

1. **Rolling 14-day verbatim window.** One long-lived `Session` per chat that never expires,
   resolved by a deterministic on-disk lookup keyed on `whatsapp_chat` (a small SQLite chat index).
   Every turn's context is every message from the last 14 Israel-local calendar days, oldest-first,
   Feature 039 `[sender_name]` prefixing intact, capped by a **read-only per-turn token backstop**
   `N` = the acting role's `max_tokens_by_role` (drops the *oldest* in-window messages; newest
   always kept).
2. **Nightly roll at 02:00 Israel local.** One shared `APScheduler` `CronTrigger` job (mirroring
   `reminder_delivery_service.py`), wired in `denidin.py __main__`. Per chat, summarize the previous
   calendar day's messages into **exactly one** ChromaDB daily-summary record via the sanitizing
   `MemoryManager.remember()` path — no raw `client.get_collection()` verify (bugfix-035 H1 gone).
   Idempotent per (chat, date) via a **SQLite roll-marker store** with `PRIMARY KEY(chat, date)`
   and a claim-first two-phase (`claimed` → `committed`) protocol. Empty days get a marker, no
   billed call. A bounded startup catch-up sweep (`memory.roll.catchup_lookback_days`) covers days
   missed while down.
3. **Raw messages are never deleted.** The `_prune_until_under_limit` `unlink()` path is removed.
   A nightly physical **archive move** (`rename` into `{session_dir}/archived/`, never `unlink`)
   relocates messages older than 14 days or beyond the largest role `N` (100000). A file-integrity
   helper asserts `live + archived == message_counter == id-list length`.
4. **US4** — a standalone `apps/rolling-memory-backfill/` sub-app (mirroring
   `apps/prod-ledger-backfill/`) backfills daily summaries for history older than 14 days. Run
   against a target env **before** the new-model code is deployed there; separate explicit approval
   per run.
5. **US5** — full logger fix: one root-logger handler (kills the multi-handler rotation race),
   `TimedRotatingFileHandler(backupCount=0)` + gzip, and a `logging:` `json-file` size cap on both
   compose services — applied to `denidin-app` **and** its byte-identical `morning-mcp-app` twin.

Legacy defects (bugfix-035 H1/H2/H3, bugfix-044) are structurally eliminated by the redesign or
fixed inline, each proven by a named acceptance scenario (spec.md §"Legacy Defects"); the bugfix
specs get a "Superseded by Feature 070" status note at haleluya, not now.

## Technical Context

**Language/Version**: Python 3.9.6 (both apps — 3.9-compatible syntax only: no `X | Y` unions, no `match`)
**Primary Dependencies**: `APScheduler` (`BackgroundScheduler` + `CronTrigger`, Israel-local
timezone) · `chromadb` (`PersistentClient`, cosine) · `sqlite3` (stdlib — roll-marker store + chat
index) · OpenAI Python SDK (Responses API, `model=gpt-5.6-luna`, `max_retries=config.max_retries`)
· `tiktoken`-backed `count_tokens` (existing) · standard `logging` + `logging.handlers`
**Storage**:
- session/message JSON under `{data_root}/sessions/<uuid>/` (unchanged layout; dirs stay UUID-named)
- archived messages under `{data_root}/sessions/<uuid>/archived/` (new; `rename` target)
- ChromaDB collections under `{data_root}/memory/` (unchanged; `daily_summary` records join the
  existing `session_summary` records in the same per-chat collection)
- **new** SQLite chat index: `{data_root}/sessions/chat_index.db`
- **new** SQLite roll-marker store: `{data_root}/memory_rolls/roll_markers.db` (deliberately **not**
  under `{data_root}/memory/` — ChromaDB owns that directory)
**Testing**: `pytest` — `tests/unit/`, `tests/integration/` (real internal components, OpenAI/Green
API mocked at the network boundary only), `tests/billed/` (real text-only OpenAI calls; the Phase 6
acceptance tier + the US4 backfill test)
**Target Platform**: Linux Docker container (`dev` local, `prod` on the always-on Windows box,
Feature 035). The US4 backfill sub-app runs with host `python3` (the same documented
containers-only exception `apps/prod-ledger-backfill/` uses).
**Project Type**: single project (`apps/denidin-app/`) + one **new** standalone sub-app
(`apps/rolling-memory-backfill/`). `apps/morning-mcp-app/` is touched only for the byte-identical
`time_utils.py` / `logger.py` twins and its two compose services' `logging:` cap.
**Performance Goals**: SC-007 — added per-turn latency for building the 14-day window ≤ 150 ms p95
over the real prod message mix; added per-turn input tokens within the confirmed `gpt-5.6-luna`
context budget with ≥ 30 % headroom.
**Constraints**: Israel local time only (no UTC, no naive datetimes); no environment variables; no
`config.feature_flags` entry; `CURRENT_SCHEMA_VERSION` unchanged; no embedding-model or
"RECALLED MEMORIES" block-format change beyond what Phase 0 verifies for prompt-cache; nightly
summarization settles at ≤ 1 billed call per chat per active day (SC-003).
**Scale/Scope**: 2 prod chats ever (`120363210094632983@g.us`, `972522968679@c.us`), go-live
2026-08-05. Group chat ≈ 62 K tokens full history (Aug 5 – Sep 1), growth ≈ 2,200 tokens/day.
Godfather/admin `max_tokens_by_role` = 100000; client 4000; blocked 0. End state per chat: a 14-day
verbatim window + a few weeks of daily summaries, +1 summary per chat per active day.

**NEEDS CLARIFICATION**: none. All five `/speckit.clarify` questions were closed 2026-09-02
(spec.md §Clarifications); the remaining `plan.md`-deferred design points (requirements.md
lines 109-115) are settled below and in `research.md` by following existing project patterns — no
further user input required.

## Constitution Check

*GATE: must pass before Phase 0 research. Re-evaluated after Phase 1 design (see
[Post-Design Re-evaluation](#post-design-constitution-re-evaluation)).*

| Gate | Rule | Status | How this plan satisfies it |
|---|---|---|---|
| **No env vars** | §I — `os.getenv`/`os.environ` forbidden | ✅ PASS | Every tunable is a config key under `memory.*` or a new top-level `logging` dict, defaulted in `config.py` and DI-passed. `SessionManager` / `RollMarkerStore` never read `AppConfiguration` (caller composes paths — `ReminderManager` discipline). |
| **Feature flag for new behavior** | §I / CLAUDE.md — new behavior behind `config.feature_flags`, default false, byte-identical when off | ⚠️ **DELIBERATE OVERRIDE** | No flag. Clarified 2026-09-02 by explicit user direction — a half-installed dual memory model is more dangerous than a clean cutover preceded by a one-time backfill. Retired paths are **deleted**, not disabled. See [Complexity Tracking](#complexity-tracking). |
| **Israel local time** | §II (bugfix-037) — `now_local()`, aware `Asia/Jerusalem`, never naive / never `timezone.utc` | ✅ PASS | New `time_utils` helpers (`start_of_local_day`, `local_calendar_date`, `n_calendar_days_ago`) build on `LOCAL_TZ` / `now_local()`. Day-bucketing for the window builder and the roll job share one implementation. `+00:00` legacy timestamps stay comparable (both sides aware). |
| **`pathlib.Path`** | §XIV | ✅ PASS | All new path handling uses `Path`. |
| **JSON file format** | §XV — 2-space, `sort_keys=True`, UTF-8, LF | ✅ PASS | No new JSON *file* format introduced; `session.json` writes keep their existing serializer. `archived_message_ids` is an ordinary list field. |
| **No monkey-patching** | §XVII | ✅ PASS | New services use the DI + module-function pattern of `reminder_delivery_service.py`. The logger refactor moves handlers onto the root logger (ordinary `logging` config), not a runtime patch. `trigger=` / `now=` seams are ordinary parameters. |
| **Bounded-backoff startup handshakes** | §XVIII | ✅ PASS | The startup catch-up sweep is bounded by `memory.roll.catchup_lookback_days` (default 21), runs synchronously before the scheduler, isolates per-chat failures, and never blocks message handling indefinitely. |
| **ZERO MOCKING internal components** | §I / §V | ✅ PASS | Every unit/integration test names real `SessionManager` / `MemoryManager` / `AIHandler` / real ChromaDB on a tmp `data_root`. OpenAI + Green API are the only mocked boundaries and never with `unittest.mock` inside `tests/integration/` (webhook JSON through `bot.router`). |
| **NO UNVERIFIED THIRD-PARTY ASSUMPTIONS** | CONSTITUTION | ✅ PASS (via Phase 0) | `gpt-5.6-luna` context window + token pricing and OpenAI prompt-cache behavior are marked **unverified** in `research.md` and design lock-in is gated on the Phase 0 billed spike. |
| **Ledger schema frozen** | CLAUDE.md | ✅ PASS | REQ-MEM-043 — no `CURRENT_SCHEMA_VERSION` change, no `SCHEMA_VERSION_HISTORY` entry, no `LedgerEvent` field change. This feature does not import `ledger_event_manager`. |
| **New tool-bearing feature → constitution boundaries** | CLAUDE.md | ✅ N/A | Feature 070 adds **no** model-facing tools (no local `type:"function"` tool, no MCP tool). The nightly roll and backfill call OpenAI directly with a fixed summarizer prompt; the model never chooses to invoke them. No `runtime_constitution.md` change. |
| **Integration Contracts** | METHODOLOGY §VII | ✅ PASS | Multi-component feature — see [Integration Contracts](#integration-contracts). |
| **Never work on `master`** | CONSTITUTION | ✅ PASS | Branch `feature/070-rolling-memory-window`. |

**Result: GATE PASSED** (one deliberate, user-directed override, tracked in Complexity Tracking).

## Project Structure

### Documentation (this feature)

```text
specs/done/v0.5.4-70/070-rolling-memory-window/
├── spec.md                     # ✅ committed, clarified 2026-09-02
├── user-stories.md             # ✅ committed (US1–US5 + AC-1..AC-6)
├── checklists/requirements.md   # ✅ committed
├── PLAN-HANDOFF.md              # working note — deleted/ignored at haleluya
├── plan.md                     # This file (/speckit.plan)
├── research.md                 # Phase 0 output
├── data-model.md               # Phase 1 output
├── quickstart.md               # Phase 1 output — US4 operator runbook + US5 audit finding
├── contracts/                  # Phase 1 output — internal API + CLI + logger contracts
│   ├── session-manager-window.md
│   ├── roll-marker-store.md
│   ├── daily-summary-roll-service.md
│   ├── summarizer.md
│   ├── memory-collections.md
│   ├── ai-handler-recall.md
│   ├── time-utils-daybucket.md
│   ├── backfill-cli.md
│   └── logger-retention.md
└── tasks.md                    # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code

```text
apps/denidin-app/
├── denidin.py                                  # MOD — __main__: + daily-roll startup sweep + scheduler
│                                               #        + shutdown; − run_startup_cleanup / SessionCleanupThread
│                                               #        / recover_orphaned_sessions; config_dict gains 'logging'
├── src/
│   ├── managers/
│   │   ├── session_manager.py                  # MOD — get_rolling_window / add_message_with_tokens /
│   │   │                                       #        _session_from_dict (tolerant) / chat_index.db +
│   │   │                                       #        _reconcile_chat_index / get_messages_for_local_date /
│   │   │                                       #        archive_aged_and_backstopped_messages;
│   │   │                                       #        − _prune_until_under_limit / expiry / remove_from_index
│   │   ├── memory_collections.py               # NEW — collection_name_for_chat(whatsapp_chat) -> str
│   │   ├── roll_marker_store.py                # NEW — RollMarkerStore (SQLite, PRIMARY KEY(chat,date))
│   │   └── memory_manager.py                   # (unchanged API — remember/recall used for daily summaries)
│   ├── handlers/
│   │   ├── ai_handler.py                       # MOD — history fetch → get_rolling_window(max_tokens=role);
│   │   │                                       #        recall collection via memory_collections;
│   │   │                                       #        self.roll_marker_store; − transfer_session_to_long_term_memory
│   │   │                                       #        / recover_orphaned_sessions
│   │   └── summarizer.py                       # NEW — summarize_conversation(client, model, messages) -> str
│   ├── services/
│   │   ├── daily_summary_roll_service.py       # NEW — mirrors reminder_delivery_service.py
│   │   └── cleanup_service.py                  # DELETED
│   ├── utils/
│   │   ├── time_utils.py                       # MOD — start_of_local_day / local_calendar_date /
│   │   │                                       #        n_calendar_days_ago  (+ morning-mcp-app twin)
│   │   └── logger.py                           # MOD — single root-logger handler + TimedRotatingFileHandler
│   │                                           #        (backupCount=0) + gzip  (+ morning-mcp-app twin)
│   └── models/
│       └── config.py                           # MOD — memory.session.window_days / memory.longterm.daily_summary_top_k /
│                                               #        memory.archive_retention_days / memory.roll.* defaults;
│                                               #        NEW top-level `logging` dict
├── config/
│   ├── config.example.json  config.dev.json  config.prod.json  config.test.json   # MOD — new memory.* + logging keys
├── tests/
│   ├── helpers/message_integrity.py            # NEW — assert_message_integrity(session_dir)
│   ├── unit/
│   │   ├── test_session_manager_window.py          # NEW
│   │   ├── test_session_manager_tolerant_load.py   # NEW
│   │   ├── test_session_chat_index.py              # NEW
│   │   ├── test_collection_name_helper.py          # NEW
│   │   ├── test_retired_paths_removed.py           # NEW (static — SC-011)
│   │   ├── test_roll_marker_store.py               # NEW
│   │   ├── test_daily_roll_service.py              # NEW
│   │   ├── test_archive_only_maintenance.py        # NEW
│   │   ├── test_logger_retention.py                # NEW (US5 unit)
│   │   ├── test_background_cleanup.py              # DELETED
│   │   └── test_session_manager_tokens.py          # DELETED
│   ├── integration/
│   │   ├── test_rolling_window_integration.py      # NEW
│   │   ├── test_daily_roll_integration.py          # NEW
│   │   ├── test_recall_surfaces_daily_summary.py   # NEW
│   │   ├── test_archive_only_integration.py        # NEW
│   │   ├── test_logger_retention_integration.py    # NEW (US5 integration = AC-6)
│   │   └── test_archived_session_recovery.py       # DELETED
│   └── billed/
│       ├── test_rolling_memory_billed.py           # NEW (tasks Phase 8 — billed AC-1/2/3/5, SC-007)
│       └── test_session_transfer.py                # DELETED

apps/morning-mcp-app/
└── src/denidin_mcp_morning/utils/
    ├── time_utils.py                           # MOD — byte-identical twin
    └── ... logger.py                           # MOD — byte-identical twin
apps/morning-mcp-app/tests/unit/test_logger_retention.py   # NEW (twin unit coverage)

apps/rolling-memory-backfill/                   # NEW standalone sub-app (mirrors apps/prod-ledger-backfill/)
├── _denidin_loader.py                          # puts apps/denidin-app on sys.path; imports the real components
├── backfill_daily_summaries.py                 # main(argv=None) -> int ; sys.exit(main())
├── requirements.txt   conftest.py   pytest.ini   .gitignore
├── config/                                     # gitignored creds/config target
├── quickstart.md                               # (canonical runbook also mirrored into the feature quickstart.md)
└── tests/
    ├── unit/test_backfill_cli.py               # NEW (argparse + preconditions + decision logic, loader faked)
    ├── integration/test_backfill_integration.py # NEW (real components, OpenAI-boundary mock, main() end-to-end)
    └── billed/test_backfill_billed.py          # NEW — dev/sandbox real billed, US4 acceptance / AC-4 (tasks Phase 9)

docker/
├── docker-compose.prod.yml                     # MOD — logging: {driver: json-file, options: {max-size, max-file}}
└── docker-compose.dev.yml                      #        on both denidin-app-<env> and morning-mcp-app-<env>
```

**Structure Decision**: single project + one new standalone sub-app. The new memory model lives
entirely inside `apps/denidin-app/src/` reusing the existing manager/service/util layering. The
one-time migration is a separate sub-app (not an in-process app step, not a shell script) because
REQ-MEM-048 requires it to run standalone against a running *or* stopped environment and it is a
separately-gated real-prod-write action — exactly the shape `apps/prod-ledger-backfill/`
established for Features 061/062. `apps/morning-mcp-app/` is touched only where it already carries
byte-identical twins of `time_utils.py` / `logger.py` and for its compose `logging:` cap.

## Integration Contracts

*(METHODOLOGY §VII — mandatory for a multi-component feature. Full method signatures and payload
shapes are in [`contracts/`](./contracts/); this section states the cross-component obligations.)*

### Contract 1 — `AIHandler` ↔ `SessionManager` (per-turn window)

- **`AIHandler` MUST** call `session_manager.get_rolling_window(whatsapp_chat, now=None,
  window_days=<config memory.session.window_days>, max_tokens=<acting role's token_limit>)` in
  place of `get_conversation_history(...)` at the history-fetch site, and pass the result as the
  conversation-context `input` items unchanged in shape.
- **`SessionManager` PROVIDES** an ordered (oldest-first) `List[Dict]` with the exact same per-item
  shape and Feature 039 `[sender_name]` group-prefix behavior as `get_conversation_history` today;
  it is **read-only** (moves/deletes nothing); it never raises on a future-dated message, an
  unloadable session, or a missing message file; it returns at least the single newest message even
  when `max_tokens` is smaller than that message.
- **`SessionManager` EXPECTS** `max_tokens` to already be the RBAC/group-resolved limit (the caller
  owns role resolution, incl. `GroupMembershipResolver` for group turns); `now` is a test-only
  seam and production always leaves it `None`.

### Contract 2 — `AIHandler` ↔ `SessionManager` (canonical store / restart continuity)

- **`AIHandler` MUST** resolve "where does chat C's next message append?" only via
  `session_manager.get_session(whatsapp_chat)` — never by inspecting or repopulating an in-memory
  index itself, and never via an orphan-recovery step (that method is deleted).
- **`SessionManager` PROVIDES** exactly one long-lived `Session` per `whatsapp_chat`, resolved
  through `chat_index.db` (authoritative) with the in-memory `chat_to_session` dict as a
  non-authoritative read-through cache; the resolution is stable across a fresh `SessionManager`
  constructed on the same `data_root` (a process-restart simulation) with no "Created new session"
  side effect.
- **`SessionManager` EXPECTS** its constructor to receive a composed `storage_dir` path (it never
  reads `AppConfiguration`); `_reconcile_chat_index()` runs once in `__init__`, `INSERT OR IGNORE`
  for every `*/session.json` (+ `expired/`), and on a chat mapping to >1 dir picks
  `max(message_counter)`, logs one WARNING, deletes nothing.

### Contract 3 — `daily_summary_roll_service` ↔ `SessionManager`

- **The roll service MUST** obtain a day's messages via
  `session_manager.get_messages_for_local_date(session, date)` (which reads **both** live
  `messages/` and `archived/`), so a message archived by the backstop trim is still summarized on
  its normal schedule (REQ-MEM-036).
- **`SessionManager` PROVIDES** the full set of that chat's messages whose Israel-local calendar
  date equals `date`, using the *same* day-bucketing as `get_rolling_window` (one message belongs
  to exactly one day).
- **The roll service EXPECTS** to iterate all known chats from the sessions on disk; one unloadable
  chat/session must not abort the sweep for others.

### Contract 4 — `daily_summary_roll_service` ↔ `RollMarkerStore`

- **The roll service MUST**, for each (chat, date): call `is_rolled(chat, date)` → skip if true;
  else `try_claim(chat, date, source)` → skip if `False` (another racer owns it or a fresh claim
  exists); only after the summary is durably stored (or the day is confirmed empty) call
  `commit(chat, date, message_count, memory_id)`.
- **`RollMarkerStore` PROVIDES** atomicity via `PRIMARY KEY(chat, date)` — `try_claim` does an
  `INSERT` and treats `sqlite3.IntegrityError` as "claim lost"; a `claimed` row older than
  `memory.roll.stale_claim_minutes` (default 120) may be re-taken (crash recovery); `is_rolled`
  is true **only** for `status='committed'`.
- **`RollMarkerStore` EXPECTS** a composed `storage_dir` (never reads config); one long-lived
  `sqlite3.connect(check_same_thread=False)` connection; the scheduler job's `max_instances=1`
  plus SQLite serialization are the concurrency guarantees (no app-level mutex).

### Contract 5 — `daily_summary_roll_service` ↔ `MemoryManager` (+ `memory_collections`)

- **The roll service MUST** write the summary via
  `memory_manager.remember(summary, collection_name_for_chat(chat), metadata=<daily-summary
  metadata>)` and MUST NOT call `client.get_collection()` (or any raw unsanitized collection
  access) anywhere in the roll path (bugfix-035 H1). Before `remember`, it MUST
  `collection.delete(where={"type":"daily_summary","chat":chat,"date":date})` for
  idempotent-by-overwrite on a manual marker reset.
- **`memory_collections.collection_name_for_chat` PROVIDES** the single source of truth for a
  chat's collection name, reproducing the existing prod names byte-for-byte
  (`972522968679@c.us` → `memory_972522968679`; `120363210094632983@g.us` →
  `memory_120363210094632983_at_g.us`) for every chat-id shape.
- **`MemoryManager` EXPECTS** metadata carrying `scope="PRIVATE"` and `user_phone=<chat>` so
  `recall_with_rbac_filter` surfaces the record (matches the existing `session_summary`
  convention). Recall stays a **single** per-turn call over the one per-chat collection (no second
  call); its `top_k` becomes `memory.longterm.daily_summary_top_k` (default 10); the
  `MemoryManager.recall` parameter default and every other call site keep `top_k_results=5`. Full
  mechanism: [`contracts/ai-handler-recall.md`](./contracts/ai-handler-recall.md).

### Contract 6 — `denidin.py __main__` ↔ `daily_summary_roll_service`

- **`__main__` MUST** call `run_startup_daily_roll_sweep(denidin)` synchronously **after**
  `initialize_app` and after the reminder + accounting startup sweeps, then
  `denidin.daily_roll_scheduler = start_daily_roll_scheduler(denidin, roll_hour=<config
  memory.roll.hour>)`, then `message_source.start(...)`; and MUST call
  `denidin.daily_roll_scheduler.shutdown(wait=False)` in all three existing shutdown sites.
- **The service PROVIDES** the same `start_*` / `run_startup_*_sweep` / `_sweep_*(global_context,
  now=None, lookback_days=None, log_prefix="")` triad as the reminder/accounting services, wired in
  `__main__` **only** (never `initialize_app` — integration tests call `initialize_app` against a
  process-global singleton and a real scheduler there would reach live OpenAI unattended).
- **`__main__` EXPECTS** `initialize_app` to no longer start `SessionCleanupThread`, call
  `run_startup_cleanup`, or run `recover_orphaned_sessions` (all removed).

### Contract 7 — backfill sub-app ↔ `apps/denidin-app` internals

- **The backfill MUST** import the real `SessionManager` day-gather, `RollMarkerStore`,
  `MemoryManager`, `collection_name_for_chat`, and `summarize_conversation` via `_denidin_loader.py`
  — no re-implementation — and MUST write markers + summaries into the **target env's own**
  `data/` (roll-marker DB + ChromaDB), reading raw messages only.
- **`apps/denidin-app` PROVIDES** `summarize_conversation(client, model, messages) -> str` as a
  module-level function usable without an `AIHandler` instance.
- **The backfill EXPECTS** to run before the new-model code is deployed to that env (runbook
  ordering); `memory.roll.catchup_lookback_days` is the safety net if that ordering is violated.

## Phased Execution

Phases map to the spec's user stories; P1 (US1–US3) ships first as the coherent model. Each phase
has a Validation/Checkpoint gate. Unit/integration tests are RED→GREEN with the Task A (tests) →
human approval → Task B (impl) split and are immutable once approved (METHODOLOGY §VI.b). The
`billed` acceptance tests are described plain-language in `tasks.md` and coded + run once in
Phase 6 (§VI.a).

### Phase 0 — Research spike **(BLOCKING)** · gate: billed-call approval

One throwaway script (not shipped). Satisfies "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS" for
`gpt-5.6-luna` and settles plan-mode decision C (prompt placement).

- One real `gpt-5.6-luna` Responses API call: synthetic ~62–70 K-token 14-day-window-shaped
  `input` + the real constitution `instructions` + the real assembled tool set. Capture: does it
  fit; `response.usage` (`input_tokens`, `input_tokens_details.cached_tokens`, `output_tokens`).
- Repeat with the same prefix → confirm `cached_tokens > 0` on the second call.
- Confirm `gpt-5.6-luna` max context window + token pricing against the OpenAI account / docs.
- **Prompt-shape A/B** (decision C): measure `cached_tokens` with the RECALLED MEMORIES block where
  it is today (inside `instructions`, between the constitution and the `---`) vs. relocated into
  the first `input` item; and whether the 14-day window as leading `input` items caches cleanly
  turn-to-turn (append-only, no reorder). For any placement that improves caching, run a scripted
  multi-turn functional-regression check whose correct answer depends on an early message / an
  out-of-window recalled fact — **no placement ships without that check passing** (REQ-MEM-037,
  plan-mode C).

**Validation/Checkpoint**: `research.md` updated with confirmed `gpt-5.6-luna` context + pricing,
the SC-007 ≥ 30 % headroom calculation against the real prod window size, `cached_tokens` evidence,
and the chosen prompt shape + its functional-check evidence. If the window does not fit with
margin, STOP and escalate — the design changes.

### Phase 1 — US1: rolling 14-day window + tolerant load + deterministic lookup (P1, MVP)

**New:** `src/managers/memory_collections.py`.
**Modified:** `src/utils/time_utils.py` (+ twin), `src/managers/session_manager.py` (chat index +
`_reconcile_chat_index`, `_session_from_dict` tolerant filter, `get_rolling_window`,
`add_message_with_tokens`, `Session.archived_message_ids`; **delete** `_prune_until_under_limit`,
`prune_to_limit`, `clear_session`, expiry helpers, `remove_from_index`, `session_timeout_hours`
ctor param), `src/handlers/ai_handler.py` (history fetch → `get_rolling_window`; recall collection
via `collection_name_for_chat`; the per-turn conversational recall call's `top_k` →
`memory.longterm.daily_summary_top_k` per `contracts/ai-handler-recall.md`; **delete**
`transfer_session_to_long_term_memory`, `recover_orphaned_sessions`), `src/services/reminder_delivery_service.py` (swap the
`add_message_with_token_limit` call), `denidin.py` (remove cleanup wiring + dead imports),
`src/models/config.py` (`memory.session.window_days` 14, `memory.longterm.daily_summary_top_k` 10,
`memory.archive_retention_days` 0; tolerate a still-present `session_timeout_hours`),
`config/config.*.json`.
**Deleted:** `src/services/cleanup_service.py`.
**Tests (RED→GREEN):** unit `test_session_manager_window.py`, `test_session_manager_tolerant_load.py`,
`test_session_chat_index.py`, `test_collection_name_helper.py`, `test_retired_paths_removed.py`
(static, SC-011); integration `test_rolling_window_integration.py` (golden-file on the exact OpenAI
`input` items; restart scenario through a real Green API webhook via `bot.router`; poison-session
fixture). **Delete whole files** `test_background_cleanup.py`, `test_session_manager_tokens.py`,
`test_archived_session_recovery.py`, `test_session_transfer.py`. **Delete named classes/methods**
(exact list in `tasks.md`, per the approved plan). **Replace** (not edit — old approved tests are
immutable) `test_session_manager.py::TestTokenLimits` and
`test_ai_handler_memory.py::TestAIHandlerConversationHistory` with new tests asserting the new
behavior.

**Validation/Checkpoint**: `cd apps/denidin-app && python3 -m pytest tests/unit tests/integration
-v` green; `test_retired_paths_removed.py` proves 0 live references to the deleted symbols and no
`unlink`/`rmtree` on message/session paths in feature modules; a restart simulation continues the
session with `message_counter` +1 and no "Created new session" log; `pylint`/`mypy` clean on the
changed files.

### Phase 2 — US2: nightly roll + roll markers + catch-up sweep (P1)

**New:** `src/managers/roll_marker_store.py`, `src/handlers/summarizer.py`,
`src/services/daily_summary_roll_service.py`.
**Modified:** `src/handlers/ai_handler.py` (`__init__` gains `self.roll_marker_store`),
`src/managers/session_manager.py` (`get_messages_for_local_date`), `denidin.py __main__` (startup
sweep + scheduler + 3 shutdown sites; `DeniDin.__init__` gains `daily_roll_scheduler=None`),
`src/models/config.py` (`memory.roll`: `hour` 2, `catchup_lookback_days` 21,
`stale_claim_minutes` 120), `config/config.*.json`.
**Tests (RED→GREEN, OpenAI mocked):** unit `test_roll_marker_store.py`, `test_daily_roll_service.py`
(one summary per non-empty (chat, date) incl. `@g.us`; empty day → marker, 0 calls; re-run →
0 summaries/0 boundary calls; D1+D2 downtime → each rolled once; OpenAI failure → no commit,
retried, other chats still roll; poison session isolated; backstop-archived message still in its
day's summary; DST night fires once via `trigger=`/`now=` seams). integration
`test_daily_roll_integration.py` (real `SessionManager` + real `MemoryManager` + real ChromaDB;
invoke `_sweep_daily_roll` directly; assert summary count, marker rows, `recall()` retrievability
+ metadata, boundary call-count across a re-run; group collection via `collection_name_for_chat`
with **no** raw `client.get_collection` in the roll path), `test_recall_surfaces_daily_summary.py`
(out-of-window `daily_summary` seeded → asked through `bot.router` → appears in RECALLED MEMORIES —
US2 sc5).

**Validation/Checkpoint**: unit + integration green; a re-run of `_sweep_daily_roll` over an
already-rolled range makes 0 boundary calls and creates 0 records (SC-010); the group-chat path
raises no `NotFoundError`; `pylint`/`mypy` clean.

### Phase 3 — US3: archive-only safety property + retention (P1)

Most of US3 lands in Phase 1 (read-only builder, deletions removed). Phase 3 adds the physical
archival step + the audit helper.
**Modified:** `src/managers/session_manager.py` —
`archive_aged_and_backstopped_messages(session, *, now, window_days, max_backstop_tokens)`:
`rename` into `{session_dir}/archived/` (a) messages older than the 14-day cutoff and (b) in-window
messages beyond the **largest** role `N` (100000 — role-independent, deterministic); append to
`session.archived_message_ids`; **never `unlink`**. `src/services/daily_summary_roll_service.py` —
call it once per chat per sweep. `src/models/config.py` — `memory.archive_retention_days` (already
added Phase 1; 0 = keep forever; no pruner built).
**New:** `tests/helpers/message_integrity.py` — `assert_message_integrity(session_dir)`.
**Tests:** unit `test_archive_only_maintenance.py`; integration `test_archive_only_integration.py`
(tiny configured backstop; seed > backstop; drive `bot.router`; live window fits `N`; every
trimmed file exists at its archive path; the nightly roll for that day still includes them; static
no-`unlink` audit across all feature modules; archived-session lookups scoped to their own
`session_id`, never `rglob(...)[0]` — bugfix-035 H3).

**Validation/Checkpoint**: `assert_message_integrity` balances after aging + backstop trim; the
static audit finds 0 deletions of message/session files in feature modules (SC-004, SC-011); a
misconfigured tiny backstop still returns the newest message and terminates.

### Phase 4 — US4: one-time migration (P2, separately gated)

> **Execution split (tasks.md, 2026-09-03 user-directed):** building this tool is tasks.md **Phase 6**;
> *running* it is separated by environment — **Phase 9** executes + fully tests it against **dev**
> (AC-4), **Phase 10** executes it against **prod** with **read-only, non-intrusive** verification only.
> tasks.md **Phase 8** is the AC-1/2/3/5 + SC-007 billed acceptance pass; **Phase 11** is polish, always last.

**New:** `apps/rolling-memory-backfill/` mirroring `apps/prod-ledger-backfill/` —
`_denidin_loader.py`, `backfill_daily_summaries.py` (`main(argv=None) -> int`; `argparse`:
`--data-root` required, `--config` required, `--since YYYY-MM-DD` required no default, `--until`
optional default `today_local − 14d`, `--chat` repeatable default all, `--yes`; **no** `--env`,
**no** `--dry-run` — 061/062 convention), `requirements.txt`, `conftest.py`, `pytest.ini`,
`.gitignore`, `quickstart.md`.
**Tests (both non-billed, RED→approval→GREEN like every other unit/integration task):**
- `tests/unit/test_backfill_cli.py` — argparse contract, every precondition failing closed before
  any loader/network call, the typed-`yes` confirm, per-(chat, date) decision logic + call counts
  against a faked `_denidin_loader`, mid-run abort, report lines.
- `tests/integration/test_backfill_integration.py` — real `SessionManager` + `RollMarkerStore` +
  `MemoryManager` + ChromaDB via the real loader, tmp `data_root`, OpenAI mocked at the network
  boundary only: `main([...])` end to end → one `daily_summary` per non-empty pre-window (chat,
  date) with correct metadata + one marker per (chat, date) incl. empty; `assert_message_integrity`
  byte-identical before + after; same-args re-run → 0 boundary calls / 0 new records; a following
  `_sweep_daily_roll` skips every migrated day; `@g.us` collection via `collection_name_for_chat`,
  no raw `client.get_collection`.
- **AC-4 (billed)** — `tests/billed/test_backfill_billed.py`, the real-money twin of the integration
  test, run once against a live dev chat in the dev-migration phase (tasks Phase 9), operator report
  reviewed.

**Validation/Checkpoint**: the two non-billed tests are the tool's correctness gate and pass here
(tasks Phase 6). The billed run + running against real prod data = **fresh explicit human approval
per run** (never a deploy side effect), tasks Phases 9 (dev) / 10 (prod). The `quickstart.md` runbook
enforces backfill-before-deploy ordering. `assert_message_integrity` before and after every run.

### Phase 5 — US5: log retention (P2, parallelisable)

**Modified:** `src/utils/logger.py` (+ twin) — attach the file + console handlers **once, to the
root logger** in `setup_logger`; `get_logger(name)` returns `logging.getLogger(name)` with
`propagate=True`; file handler → `TimedRotatingFileHandler(when=<config>, backupCount=0)` with a
gzip `rotator`/`namer`; keep `LocalTimeFormatter` + `_VersionFilter` (version filter moves to the
root logger; the `get_logger` test-env shortcut still works via propagation to pytest's root
handlers). `src/models/config.py` — new top-level `logging: Dict` (`rotation_when` "midnight",
`backup_count` 0). `denidin.py:~1024` `config_dict` — add `'logging': config.logging`.
`docker/docker-compose.prod.yml` + `docker/docker-compose.dev.yml` — `logging: {driver: json-file,
options: {max-size: "10m", max-file: "5"}}` on both `denidin-app-<env>` and
`morning-mcp-app-<env>`.
**Tests:**
- unit `test_logger_retention.py` (both apps) — tiny interval, force several rotations, assert every
  rotated (gzipped) segment exists on disk with intact content, scoped to a tmp dir; exactly one
  file + one stream handler on the root logger after N `get_logger` calls; child loggers carry 0
  handlers + `propagate is True`; `backup_count=0` deletes nothing.
- integration `test_logger_retention_integration.py` (`apps/denidin-app`) — the spec's US5
  "Integration test requirement" **and the US5 acceptance evidence (AC-6)**: drive the logger
  through the real `AppConfiguration`→`setup_logger` boot path on a tmp dir, force ≥ 3 rotations
  under load, assert `.gz` retention + ordering; assert exactly one root file handler after
  `initialize_app`; parse both compose files and assert the `json-file` cap on both services. Runs
  in the normal non-billed suite; confirmed green in the Phase 6 acceptance pass (no OpenAI call —
  a billed AC-6 would be meaningless).

**Validation/Checkpoint**: because `logger.py` is a shared byte-twinned core util, a short
design-review checkpoint with the user before the refactor lands. Both apps' `test_logger_retention.py`
green. `quickstart.md` carries the written US5 audit finding (the measured prod-logging table + the
multi-handler-race explanation + the `json-file` dependency statement + the forced-rotation
verification procedure).

### Phase 6 — Final acceptance pass, every story (billed AC-1/2/3/5 + SC-007; non-billed AC-6/US5) · gate: billed-run approval

Plain-language in `tasks.md`; coded + run once here (METHODOLOGY §VI). NEW
`tests/billed/test_rolling_memory_billed.py`: **AC-1** (US1+US2 — group `@g.us`, 3 simulated days,
roll each day, ask a day-1-only question → correct from the recalled summary; 1 billed call/day,
0 duplicates, no `NotFoundError`), **AC-2** (US1 — restart → continuation), **AC-3** (US1+US3 —
exceed backstop → newest-context answer + disk audit), **AC-5** (US1+US2 — poison-session shape →
no recurring hourly error → participates in a roll), **SC-007** (added latency ≤ 150 ms p95 +
input tokens with ≥ 30 % headroom). **AC-4** is the `apps/rolling-memory-backfill` billed test
(tasks Phase 9). **AC-6 (US5)** is the non-billed `test_logger_retention_integration.py`, confirmed
green in this same pass — every user story US1–US5 then has a passing acceptance scenario.

**Validation/Checkpoint**: run each scenario via `scripts/run_single_test.sh` (billed tier — no
per-run approval, sound off each result). All green → feature complete, ready for `/speckit.tasks`
consumers and eventually haleluya.

## Post-Design Constitution Re-evaluation

*Completed 2026-09-02 after `research.md` + `data-model.md` + `contracts/` were written.*

**Result: GATE STILL PASSED — no new violations, no change to the pre-Phase-0 assessment.**

| Gate | Post-design finding |
|---|---|
| No env vars (§I) | Confirmed. `data-model.md` §7 lists 6 `memory.*` keys + 2 `logging.*` keys, all defaulted in `config.py` and DI-passed. `SessionManager` / `RollMarkerStore` constructors take a composed `storage_dir` and never read `AppConfiguration` (`contracts/session-manager-window.md`, `contracts/roll-marker-store.md`) — a unit test pins each ctor signature. |
| Feature flag (§I / CLAUDE.md) | Still the one deliberate override — tracked in Complexity Tracking, unchanged. |
| Israel local time (§II) | Confirmed. `contracts/time-utils-daybucket.md` makes every day boundary go through `to_local()` first (so `+00:00` legacy timestamps bucket correctly), and the window builder + roll job share the same three helpers. No naive datetime, no `timezone.utc`, anywhere in the new code. |
| `pathlib.Path` (§XIV) | Confirmed — all new path handling in the contracts is `Path`. |
| JSON file format (§XV) | Confirmed — no new JSON *file* format; `session.json` keeps its serializer; `archived_message_ids` is a plain list. |
| No monkey-patching (§XVII) | Confirmed. New services are DI + module functions (`reminder_delivery_service.py` shape). The logger refactor (`contracts/logger-retention.md`) sets `handler.rotator`/`handler.namer` — the standard `logging.handlers` extension points, not a runtime patch — and moves handlers onto the root logger via ordinary `addHandler`. |
| Bounded-backoff startup handshakes (§XVIII) | Confirmed. `contracts/daily-summary-roll-service.md`: `run_startup_daily_roll_sweep` is bounded by `memory.roll.catchup_lookback_days` (21), synchronous before the scheduler, per-chat try/excepted, ≤ ~42 (chat, date) pairs at prod scale. |
| ZERO MOCKING internal components (§I/§V) | Confirmed — every test in the Project Structure tree names real `SessionManager` / `MemoryManager` / real ChromaDB; OpenAI + Green API are the only boundary mocks; integration tests drive `bot.router` webhook JSON. |
| NO UNVERIFIED THIRD-PARTY ASSUMPTIONS | Confirmed. `research.md` D11–D13 mark `gpt-5.6-luna` context/pricing + prompt-cache behavior as **unverified assumptions** with an explicit Phase 0 verify-before-design-lock plan; Phase 0 is BLOCKING with a billed-call approval gate. |
| Ledger schema frozen | Confirmed — no contract, entity, or module in this design imports or touches `ledger_event_manager` / `CURRENT_SCHEMA_VERSION` (REQ-MEM-043). |
| New tool-bearing feature boundaries | Confirmed N/A — `data-model.md` and every contract add zero model-facing tools; the roll + backfill call OpenAI directly with the fixed summarizer prompt (`contracts/summarizer.md`). No `runtime_constitution.md` change. |
| Integration Contracts (METHODOLOGY §VII) | 7 contracts documented in-plan + 9 detail files in `contracts/`. |

**Net-new repo pattern** (recorded in Complexity Tracking + `research.md` D6): `PRIMARY KEY(chat,
date)` + `except sqlite3.IntegrityError` as the roll-claim-loss signal. Reviewed post-design as the
minimal correct cross-process primitive; a `UNIQUE`-backstop-only alternative was explicitly
rejected (we already carry 27 duplicate records from a prior "tolerate it" stance). Small, standard
SQLite idiom — accepted.

## Complexity Tracking

| Violation / new complexity | Why needed | Simpler alternative rejected because |
|---|---|---|
| **No feature flag** for the new memory model (overrides CONSTITUTION §I / CLAUDE.md "feature-flag new behavior, default false, byte-identical when off") | Explicit user direction, clarified 2026-09-02: "I don't want to waste time fixing something that is then going to be obsolete anyway." A flag would require the 24h-expiry cleanup cycle, `_prune_until_under_limit`, and the new window builder to **coexist** — two memory models writing the same `session.json` / ChromaDB collection, with the flag deciding per-turn which history the model sees and per-night whether cleanup or the roll runs. The safe rollout is operational instead: run the one-time backfill against a target env first, then deploy the new-model code (spec.md §Clarifications Q5, REQ-MEM-060). | A dual-path flag is *more* dangerous here: a half-installed dual model can silently prune messages (old path) while the new path assumes they're archived, or double-summarize a day (cleanup + roll), and every test would have to run twice. Clean cutover + backfill-first has a smaller, testable blast radius. |
| **New pattern: `PRIMARY KEY(chat, date)` + `except sqlite3.IntegrityError`** as the roll-claim-loss signal (no existing SQLite table in the repo uses a `UNIQUE`/`IntegrityError` idiom — `ReminderManager` does manual SELECT-then-INSERT) | REQ-MEM-026 requires the marker check-and-write to be race-safe under scheduler + manual-script concurrency with at most one billed call per (chat, date). An atomic `INSERT ... PRIMARY KEY` claim is the minimal correct primitive; a SELECT-then-INSERT has a TOCTOU window a manual script run during the nightly job could hit. | `max_instances=1` alone only serializes the scheduler's *own* ticks, not the scheduler vs. a hand-run backfill/roll script. An app-level mutex/lockfile is more machinery than a one-column primary key and doesn't survive across the two separate processes (app + standalone sub-app). |
| **Second SQLite database** (`chat_index.db`) added to `SessionManager` alongside the roll-marker store | REQ-MEM-014 requires a *deterministic* on-disk lookup of a chat's single long-lived session; session dirs are UUID-named and a full-disk-scan-per-lookup does not scale and is exactly the fragile in-memory-rebuild path bugfix-044 exposed. | Renaming session dirs to `<chat>/` was considered and rejected (spec.md Q3 / REQ-MEM-014) — it touches every message-file, archive, and `expired/` code path (large blast radius) for no gain over a 3-column index. Keeping only the in-memory `chat_to_session` map is the status quo that bugfix-044 broke. |

---

*End of plan.md. Phase 0 research → [`research.md`](./research.md); Phase 1 design →
[`data-model.md`](./data-model.md), [`contracts/`](./contracts/), [`quickstart.md`](./quickstart.md).*
