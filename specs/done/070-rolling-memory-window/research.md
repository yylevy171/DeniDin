# Phase 0 Research: Rolling 14-Day Memory Window

**Feature**: 070-rolling-memory-window · **Date**: 2026-09-02 · **Plan**: [plan.md](./plan.md)

Format per METHODOLOGY §IX: **Decision / Rationale / Alternatives considered** (+ **Decision date**
and **Migration path** where they add information). **Decision date for every entry below: 2026-09-02**
(during `/speckit.plan`). **Migration path**: none of D1–D13 requires a data migration — every new
store (`chat_index.db`, `roll_markers.db`) is created empty on first construction and back-filled
by its own reconcile/catch-up path (D2's `_reconcile_chat_index`, D9's startup sweep, US4's
backfill); every new config key has a default that existing config files pick up on load; the only
*deletion* is retired code + retired tests (SC-011), not data.

Decisions D1–D10 are settled by following existing project patterns and need no user input (they
close requirements.md lines 109-115). D11–D13 are **unverified third-party assumptions** —
CONSTITUTION "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS" forbids locking the design on them until the
Phase 0 billed spike confirms them; each carries a verify-before-design-lock plan and this file is
updated with the measured numbers before Phase 1 implementation begins.

---

## D1 — Nightly-roll scheduler wiring: `denidin.py __main__`, not `initialize_app`

**Decision.** The nightly roll's `start_daily_roll_scheduler(...)` and
`run_startup_daily_roll_sweep(...)` are called from `denidin.py`'s `__main__` block, after
`initialize_app` returns and after the existing reminder + accounting startup sweeps — never inside
`initialize_app`.

**Rationale.** Every existing billed-call scheduler follows this exact rule: `start_reminder_scheduler`
is called at `denidin.py:1070`, `start_accounting_reconciliation_scheduler` at `denidin.py:1081` —
both in `__main__`, both with an explicit comment (`denidin.py:430-443`) that `initialize_app` is
what `tests/integration/` calls against a process-global `denidin_app` singleton, so a real
`APScheduler` started there would let an ordinary test run reach live OpenAI / Green API unattended.
REQ-MEM-020 originally said "wired in `initialize_app`"; that was imprecise — `__main__` is the
correct, consistent home. `plan.md` Contract 6 records it and spec.md REQ-MEM-020 + the
§Clarifications plan-mode note were corrected 2026-09-02 to match.

**Alternatives considered.** `initialize_app` (spec's literal wording) — rejected: breaks the
test-isolation guarantee the other two schedulers were deliberately moved out of `initialize_app`
to preserve (a real incident, `tasks.md` T013 note, 2026-08-17). A dedicated
`memory_roll_scheduler` module-global started at import time — rejected: Feature 043 removed
import-time bot construction for the same reason.

## D2 — Chat→session lookup: a dedicated SQLite index `{data_root}/sessions/chat_index.db`

**Decision.** A new table `chat_sessions(chat TEXT PRIMARY KEY, session_id TEXT NOT NULL,
updated_at TEXT)` in `{data_root}/sessions/chat_index.db`, owned by `SessionManager`, using the
`ReminderManager` connection idiom (one long-lived `sqlite3.connect(check_same_thread=False)`,
`row_factory=Row`, idempotent `executescript` schema in `_init_schema()`, `execute` + immediate
`commit()`, never reads `AppConfiguration`). Session directories stay UUID-named. The in-memory
`chat_to_session: Dict[str,str]` stays as a **non-authoritative read-through cache** over the
index. `_reconcile_chat_index()` runs once in `__init__`: scan every `*/session.json` (+
`expired/`), `INSERT OR IGNORE`; a chat mapping to >1 directory → pick `max(message_counter)`, log
one WARNING, delete nothing.

**Rationale.** REQ-MEM-014 requires a *deterministic* lookup; bugfix-044's failure was precisely an
in-memory index a recovery path forgot to populate. A 3-column SQLite table is the smallest
durable primitive, mirrors an idiom the repo already trusts (`reminders.db`), and leaves the
message-file / archive / `expired/` code completely untouched (zero blast radius). Migrates the 2
prod sessions transparently on first construction.

**Alternatives considered.** Rename session dirs to `<sanitized-chat>/` — rejected (REQ-MEM-014,
spec Q3): touches every path-handling code path for no benefit over an index. Keep only the
in-memory map — rejected: that is the status quo bugfix-044 broke. A JSON sidecar file — rejected:
no atomic multi-writer guarantee, and the SQLite idiom already exists.

## D3 — In-memory `chat_to_session` cache survives; `remove_from_index` guard is moot

**Decision.** The in-memory `chat_to_session` map is kept purely as a cache (D2). With no session
expiry there is **no "remove a live session from the index" path**, so `remove_from_index()` and
the entire 4-step `_process_session_cleanup` are **deleted** rather than guarded. REQ-MEM-016's
guard requirement is satisfied vacuously (the method it would guard no longer exists).

**Rationale.** The guard only mattered while sessions were removed on expiry. The redesign removes
expiry (REQ-MEM-002), so the safest resolution is deletion, not defensive code around a
now-unreachable path.

**Alternatives considered.** Keep `remove_from_index` with the REQ-MEM-016 guard "just in case" —
rejected: dead code with a test burden; SC-011 wants the retired mechanisms *gone*.

## D4 — Archive retention: keep forever by design; safety-valve config key, no pruner

**Decision.** `memory.archive_retention_days` default `0` = never prune. No pruner is built in this
feature. The documented policy (REQ-MEM-034) is "retain archived messages indefinitely by design."

**Rationale.** Two prod chats, ~2,200 tokens/day ≈ a few hundred KB of message JSON per chat per
year — negligible for years. The user's hard precondition for the whole feature is that raw data is
never lost; a pruner is a future, separately-approved decision. The config key exists so a future
operator has a lever without a code change.

**Alternatives considered.** A default N-day pruner — rejected: silently deletes a message's only
copy, the exact failure mode US3 exists to prevent, and unnecessary at this scale. No config key at
all — rejected: leaves no future lever.

## D5 — `top_k` for multi-week recall: new `memory.longterm.daily_summary_top_k`, default 10

**Decision date.** 2026-09-02.

**Decision.** A new key `memory.longterm.daily_summary_top_k` (default 10). It is the `top_k` for
**the single per-turn conversational recall call** — the one over the chat's own collection, which
after this feature returns `daily_summary` **and** legacy `session_summary` records together.
There is **no second recall call**. `memory.longterm.top_k_results` (5) stays as the
`MemoryManager.recall` parameter default and for any other/future recall call site. Full mechanism
in `contracts/ai-handler-recall.md`.

**Rationale.** REQ-MEM-047 explicitly leaves this to `plan.md` and forbids assuming it in the spec.
`daily_summary` and `session_summary` records rank together in one collection; a multi-week
question ("what did we agree three weeks ago?") plausibly needs more than 5 hits when each hit is
one day. 10 is conservative — one call, same recall path, no embedding or prompt-format change
(Out of Scope). `test_recall_surfaces_daily_summary.py` proves 5 would drop the relevant old day
and 10 keeps it; bump via config if a real scenario needs more.

**Alternatives considered.** Reuse `top_k_results=5` for the conversational call — rejected: risks
dropping the relevant day for older questions. A **second** recall call dedicated to daily
summaries — rejected: unnecessary (they live in the same collection and rank fine together) and
adds a per-turn embedding + query round-trip. Date-filtered / unbounded recall in ChromaDB —
rejected: out of scope (no recall-scoring change); the model does its own aggregation over
returned records (Feature 044 precedent).

**Migration path.** None — new config key with a default; existing configs pick up 10 on load. No
data migration.

## D6 — Roll-marker race handling: claim-first two-phase (`claimed` → `committed`)

**Decision.** `RollMarkerStore.try_claim(chat, date, source)` does an atomic `INSERT` of a
`status='claimed'` row; `sqlite3.IntegrityError` (from `PRIMARY KEY(chat, date)`) is the
"claim lost" signal → the caller skips that (chat, date). After the summary is durably stored (or
the day is confirmed empty), `commit(chat, date, message_count, memory_id)` flips the row to
`status='committed'`. `is_rolled` is true **only** for `committed`. A `claimed` row older than
`memory.roll.stale_claim_minutes` (default 120) may be re-claimed (crash between claim and commit).

**Rationale.** REQ-MEM-025 (marker only after durable store) + REQ-MEM-026 (race-safe, ≤ 1 billed
call) together require an atomic claim *before* the OpenAI call, not just a `UNIQUE` backstop that
tolerates one duplicate. `PRIMARY KEY` + `IntegrityError` is the minimal primitive and survives
across the two separate processes (app scheduler + standalone backfill sub-app) that
`max_instances=1` cannot coordinate. The stale-claim TTL prevents a crashed run from permanently
blocking a day.

**Alternatives considered.** `UNIQUE(chat, date)` as a pure backstop, tolerate one duplicate record
for later cleanup (spec.md REQ-MEM-026 offers this as acceptable) — rejected as the primary
mechanism: we already have 27 duplicate records in prod from a similar "tolerate it" stance;
claim-first costs one extra column and one status flip. `SELECT then INSERT` (ReminderManager's
manual idiom) — rejected: TOCTOU window.

**Retry bound (REQ-MEM-025/027 "bounded retry budget", resolved).** No per-item retry counter. A
day that fails to `commit` is retried on every nightly tick + startup sweep for as long as it
stays within `memory.roll.catchup_lookback_days` (21) of today; older than that, it is the US4
backfill's job. The lookback window *is* the bound. See
`contracts/daily-summary-roll-service.md` §"Retry semantics". A `PRIMARY KEY`/`UNIQUE` naming note:
`PRIMARY KEY(chat, date)` was chosen over a bare `UNIQUE(chat, date)` — same atomicity guarantee,
plus `NOT NULL`, and it *is* the natural key.

## D7 — Roll-marker DB location: `{data_root}/memory_rolls/roll_markers.db`

**Decision.** `RollMarkerStore` writes `roll_markers.db` under
`str(Path(config.data_root) / "memory_rolls")` — a **new** sibling directory, deliberately not
`{data_root}/memory/` (ChromaDB's `PersistentClient` owns that directory) and not
`{data_root}/sessions/` (that is `SessionManager`'s and now holds `chat_index.db`). The caller
composes the path; the store never reads `AppConfiguration`.

**Rationale.** Keeps each datastore's directory single-owner, avoids any chance of a stray
`.db` confusing ChromaDB's directory scan, and matches how `ReminderManager` gets
`{data_root}/reminders/`.

**Alternatives considered.** `{data_root}/memory/roll_markers.db` — rejected: shares a directory
with ChromaDB's internal files. `{data_root}/roll_markers.db` at the root — rejected: less tidy,
and the backfill sub-app needs a predictable subdir to point at.

## D8 — Migration script: standalone sub-app `apps/rolling-memory-backfill/`

**Decision.** A new standalone Python sub-app mirroring `apps/prod-ledger-backfill/`: host
`python3` (the documented containers-only exception), own `requirements.txt` / `conftest.py` /
`pytest.ini` / `.gitignore`, `_denidin_loader.py` to put `apps/denidin-app` on `sys.path` and
import the real components, `backfill_daily_summaries.py` with `main(argv=None) -> int` /
`sys.exit(main())` / `argparse`.

**Rationale.** REQ-MEM-040 mandates Feature 061/062 conventions; REQ-MEM-048 requires it to run
standalone against a running *or* stopped env, writing into that env's `data/` — that is exactly
`apps/prod-ledger-backfill/`'s shape and rules out both an in-process app step and a shell script.

**Alternatives considered.** A `scripts/` bash wrapper — rejected: 061/062 explicitly established
"not a shell script, not Docker." An `apps/denidin-app/scripts/` Python module — rejected: it would
import app internals as a sibling and blur the "standalone, separately gated" boundary.

## D9 — Boot order in `__main__` after `initialize_app`

**Decision.** reminder startup sweep + scheduler → accounting startup sweep + scheduler → **NEW**
daily-roll startup catch-up sweep (bounded by `memory.roll.catchup_lookback_days`) → **NEW**
daily-roll scheduler → `message_source.start()`. `initialize_app` **loses** `run_startup_cleanup`,
the `SessionCleanupThread` start, and `recover_orphaned_sessions`.

**Rationale.** The catch-up sweep is synchronous and must finish before the scheduler exists (same
as the reminder/accounting sweeps) and before message handling begins, so the first real turn after
a restart already sees a consistent roll state. Placing it after the other two sweeps keeps the
existing ordering stable. The three deletions are the retired cycle (REQ-MEM-005).

**Alternatives considered.** Run the catch-up sweep in a background thread — rejected: CONSTITUTION
§XVIII wants the bounded startup handshake to complete deterministically, and a half-swept state
during the first turns is avoidable. Keep `recover_orphaned_sessions` as a no-op safety net —
rejected: SC-011 wants it gone; D2's `_reconcile_chat_index` subsumes its only useful effect.

## D10 — Backstop trim: read-only per-turn cut + nightly physical archive move

**Decision.** Two mechanisms, both non-deleting: (a) **per turn**, `get_rolling_window` reads
newest→oldest accumulating `count_tokens`, stops once `> max_tokens`; the excluded messages are
**always the oldest**, the newest message is always returned even if it alone exceeds `max_tokens`.
This is read-only — it moves nothing. (b) **nightly**, `archive_aged_and_backstopped_messages`
`rename`s into `{session_dir}/archived/` any message older than the 14-day cutoff **or** beyond the
**largest** role `N` (100000, role-independent so the on-disk state is deterministic regardless of
who spoke last), appending to `session.archived_message_ids`. Never `unlink()`.

**Rationale.** Plan-mode decision A (approved). The per-turn cut has to be role-aware (a client
turn sees 4000 tokens, a godfather turn 100000) so it cannot be a physical move — the same chat
would thrash files between `messages/` and `archived/` turn to turn. The nightly move uses the
*maximum* role limit so physical archival is monotonic and never removes something a higher-role
turn would still want live. Both feed the nightly roll from `messages/` **and** `archived/`
(Contract 3), so a trimmed message is still summarized (REQ-MEM-036).

**Alternatives considered.** Physical move on every turn keyed to the acting role — rejected: file
thrash, non-deterministic disk state, and a race between a client turn and a godfather turn.
Per-turn cut only, no physical archival ever — rejected: `messages/` grows unbounded for an
always-active chat (acceptable at this scale but the nightly move is cheap and keeps the live dir
bounded to ~14 days + 100 K tokens).

## D11 — `gpt-5.6-luna` usable context window · **CONFIRMED (T005 spike 2026-09-03 + published numbers)**

**Spike result** (`apps/denidin-app/scripts/model_sanity_check.sh --config config/config.dev.json`,
full log under `logs/model_sanity_check/`):

- One real `responses.create` to `gpt-5.6-luna` with a synthetic **66,136-token** 14-day-window-shaped
  `input` + the real `runtime_constitution.md` as `instructions` + the 6 local function tools
  (`capture_ledger_event`, `query_ledger_events`, 4× reminder) → **`input_tokens = 99,449`,
  `output_tokens` fine, call SUCCEEDS.**

**Published `gpt-5.6-luna` numbers (OpenAI docs, retrieved 2026-09-03):**

| | value |
|---|---|
| Context window | **1,050,000 tokens** |
| Max output | 128,000 tokens |
| Input | $0.20 / 1M |
| Cached input | $0.02 / 1M |
| Output | $1.20 / 1M |
| Long-context surcharge | >272K **input** tokens → 2× input, 1.5× output for the whole request |

**SC-007 ≥ 30 % headroom — PASS with enormous margin.** Worst-case total prompt today ≈
`constitution 26,618 + window backstop ≤ 100,000 + tool schemas + output headroom` ≈ **~130 K
tokens** against a **1,050,000-token** window ⇒ ~**88 % headroom**. The design is nowhere near the
ceiling, and stays well below the 272 K long-context surcharge threshold, so the ordinary
$0.20/$0.02/$1.20 rates apply. Even the 100 K `max_tokens_by_role` backstop for godfather/admin is
comfortable — no reason to raise it (raising it only eats headroom and buys nothing for realistic
14-day windows, which measure ≈ 30 K today / ≈ 62 K absolute worst case).

- ⚠️ **The constitution is 26,618 tokens / 111 KB** (`tiktoken o200k_base`), not the ~4.0 K in
  CLAUDE.md's stale 2026-07-23 note — grown ~6.6× with 13 months of features. It caches at ~100 %
  after the first turn (D12), but it is a real ~26 K uncached cost on every fresh conversation /
  cache miss, adds latency, and dilutes instruction-following. **Optimising it is tracked as
  backlog Feature 073 (`specs/backlog/073-optimize-runtime-constitution/`)** — not a Feature 070
  blocker (headroom is fine), a standalone quality/cost/latency improvement.

**Design status.** Keep `window_days=14` default (already a config key, REQ-MEM-008) — the call
works and the mitigation is cheap. Do NOT lock the ≥30 %-headroom claim until the published number
is in.

## D12 — OpenAI automatic prompt-caching on the new prompt shape · **CONFIRMED (T005, 2026-09-03)**

**Spike result.**

- **Caching engages, ~100 %.** Two identical back-to-back calls: first `cached_tokens = 0`, second
  `cached_tokens = 99,446` of `99,449` input tokens (99.997 %). The byte-stable
  constitution+memories+date prefix is fully cached; only the changing tail (the needle question)
  is uncached on turn 2.
- **A/B on RECALLED MEMORIES placement:** block trailing the constitution inside `instructions`
  (**current shape**) → full caching. Block moved to the first `input` item (with the constitution
  alone as `instructions`) → `cached_tokens = 0` and it splits the window with no demonstrated
  benefit.
- **Functional needle check:** a fact planted as the very first turn of the 66 K synthetic window
  (`מספר הפרויקט הסודי הוא 74-ALPHA-9152`) is recalled **correctly** when asked at the end of the
  window.

**Decision — DO NOT relocate the RECALLED MEMORIES block.** Keep it trailing the constitution in
`instructions` (current production shape). Caching is already ~100 % there and recall of an
early/out-of-window fact works. Plan-mode decision C's "relocation in scope" is **closed as: no
change**. Zero code change to `_build_instructions` / `create_request`.

## D13 — Nightly summarizer prompt reuse · **CONFIRMED (T005, 2026-09-03)** — call shape works at scale

**Decision (D11/D12 spike confirms the call shape).** `summarize_conversation(client, model,
messages) -> str` lifts the existing `AIHandler.transfer_session_to_long_term_memory` call shape
verbatim: `client.responses.create(model=config.ai_model, instructions=<plain summarizer str>,
input=f"Summarize this conversation...\n\n{conv_text}", max_output_tokens=1000)`, with the same
`try/except` → raw `role: content` transcript fallback (`used_fallback=True`). Extracted to a
module-level function so the backfill sub-app can call it without an `AIHandler`.

**Rationale.** This call shape is already in production for session summaries; a daily summary is
the same task on a day's worth of messages. Reuse avoids a second, divergent summarizer prompt.

**Alternatives considered.** A new day-specific summarizer prompt — rejected: no evidence the
existing one is inadequate, and Out of Scope forbids recall/prompt-format churn. Summarize via a
tool call — rejected: adds a model-facing tool this feature explicitly avoids.

---

## Settled-decision → requirement traceability

| Decision | Closes | Requirement(s) |
|---|---|---|
| D1 | scheduler wiring (req.md L110) | REQ-MEM-020 (corrected: `__main__`) |
| D2, D3 | chat→session lookup + `remove_from_index` guard (req.md L111-113) | REQ-MEM-014, REQ-MEM-015, REQ-MEM-016 |
| D4 | archive retention policy (req.md L113) | REQ-MEM-034 |
| D5 | `top_k` for multi-week recall (req.md L114) | REQ-MEM-047, REQ-MEM-029 |
| D6, D7 | roll-marker path/schema + race handling (req.md L110) | REQ-MEM-024, REQ-MEM-025, REQ-MEM-026, REQ-MEM-046 |
| D8 | migration script location | REQ-MEM-040, REQ-MEM-048 |
| D9 | boot ordering (req.md L115) | REQ-MEM-005, REQ-MEM-028 |
| D10 | backstop trim mechanism (req.md L112) | REQ-MEM-024b, REQ-MEM-032, REQ-MEM-033, REQ-MEM-036 |
| D11 | model context fit | REQ-MEM-037, SC-007 |
| D12 | prompt-cache behavior | Technology Choices (Assumptions), plan-mode C |
| D13 | summarizer reuse | REQ-MEM-021 |
