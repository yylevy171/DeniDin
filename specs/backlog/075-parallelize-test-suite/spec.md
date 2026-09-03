# Feature Specification: Parallelize the billed/expensive Test Suite

**Feature Branch**: `feature/075-parallelize-test-suite`
**Created**: 2026-09-03
**Status**: Placeholder — not yet clarified/specced. Captured during Feature 059 test-stabilization
work (2026-09-03), when the question "why do these take so long / can they run in parallel" came
up. Run `speckit.specify` + `speckit.clarify` before implementation.

## Input

User description: the `billed` (and `expensive`) E2E tests each take **40–100 s** — the full
`billed` suite is ~25–40 min serial, the `sanity` billed subset alone ~25–40 min. Almost all of
that is unavoidable per-test cost (real OpenAI Responses API, real Morning MCP server over a real
ngrok tunnel, `model → tool → model` chained rounds over the ~4K-token constitution, plus
deliberate `time.sleep(3/5)` for Morning's search-index lag — no mocking, by constitution).
The lever left is **running independent tests concurrently**. Make that possible and safe.

## Why it's a real problem

- One `billed` test ≈ 5–13 real conversational turns; each turn ≈ 3 memory-recall embedding
  calls + 2–3 chained `/responses` calls (~6–13 s) + 1–2 Morning-sandbox REST calls through the
  tunnel.
- Seeding dominates the heavy tests: `_seed_client` / `_seed_fresh_invoice*` /
  `_seed_transaction_account_*` run a whole `add_client` / create-doc conversation *before* the
  assertion-relevant turns. Feature 059's own N1/N2 fixes made this worse on purpose (swapped
  `pick_existing_client()` → a real fresh-client seed for determinism: N1 went 24 s → 64 s).
- There is no CI here, so this is entirely about local developer/agent iteration time.

## Notes captured so far (2026-09-03 analysis)

Feasible unit of parallelism is **the test file**, not the individual test:

- **`pytest-xdist` is not installed** — `apps/denidin-app/venv` has only `pytest`, `pytest-cov`,
  `pytest-mock`. `apps/morning-mcp-app` likewise needs checking.
- **Module-scoped shared WhatsApp session.** `tests/billed/conftest.py`'s `denidin_config` /
  `denidin_app` fixtures are `scope="module"`, and tests within a file deliberately share one
  long chat on `GODFATHER_CHAT_ID` (create → mark paid → …). Per-test parallelism would
  interleave turns in the same conversation. `-n N --dist loadfile` (each file pinned to one
  worker) keeps within-file order serial while running files concurrently.
- **`config.data_root` is a single hardcoded `apps/denidin-app/test_data/`** (conftest.py:53-57)
  — ChromaDB long-term memory, ledger-event JSON files (`data/events/`), sessions, reminders all
  live there. Parallel workers would corrupt each other. Needs a per-worker root, e.g.
  `test_data/gw<PYTEST_XDIST_WORKER>/` (xdist sets `PYTEST_XDIST_WORKER`; `worker_id` fixture on
  the `xdist` plugin). The process-start `sessions_dir` wipe and the autouse
  `_clean_reminders_around_every_test` fixture become per-worker-safe once the root is
  per-worker.
- **Single shared Morning sandbox account.**
  - Client seeding: `_unique_client_name()` draws from ~334K real-name combinations with a
    genuine EXACT-collision redraw (`_seed_client`, bugfix-045) — safe under concurrency.
  - Count/summary-sensitive tests are NOT safe: anything asserting "client X has exactly N
    documents", `get_financial_summary` totals, `list_invoices` page contents, or a
    fixed-ground-truth client's doc count (`דורית אשכנזי`, `יוסי שמואלי` history growth,
    `זהבית צור` — see `GROUND_TRUTH_CLIENTS.md` and Feature 059's `sanity-failures.md` N3/N4)
    would see other workers' writes. These need auditing and probably per-run unique clients.
  - Morning sandbox API rate limits: unknown, need to confirm they tolerate `-n 4–8`.
- **One Morning MCP container + one ngrok tunnel.** FastMCP is plain HTTP — concurrent requests
  are fine. ngrok free-tier tunnel connection cap (~40) is well above any realistic `-n`.
- **OpenAI limits** (from live response headers): 5000 req/min, 1,000,000 tok/min — not a
  constraint at `-n 4–8`.
- **`scripts/run_sanity.sh` stays serial by design.** Its whole contract — one test per process,
  live `>>> SANITY [k/N] PASSED|FAILED` sound-off, stop-on-first-failure, resumable
  `sanity_state.tsv` — is inherently sequential and was shaped by explicit user incidents
  ("SOUND OFF GODDAMNIT", "STOP AT FAILURE"). Parallel execution must be a **separate**
  entrypoint (a "is the whole suite green?" fast sweep), never a mode of `run_sanity.sh`.

## Rough payoff

Sanity billed set ≈ 30 tests across 16 files. ~25–40 min serial → **~6–10 min at `-n 6`**
(file-level). Full billed suite proportionally.

## Open questions for `speckit.clarify`

- Parallelism grain: file-level (`--dist loadfile`, low-risk) only, or invest in per-test
  isolation (every test its own `chat_id`, module fixtures → function scope)?
- Per-worker `data_root`: exact scheme, and whether `morning-mcp-app`'s suite needs the same.
- Which existing tests break under a shared sandbox with concurrent writers — full audit needed;
  candidate list above. Fix by per-run unique clients, or by serializing just those (an xdist
  group)?
- Confirm Morning sandbox + Green Invoice API tolerate `-n 4–8` concurrent callers.
- New entrypoint shape: `scripts/run_billed_parallel.sh` / a `pytest -n` wrapper — what does it
  report, does it keep any stop-on-failure semantics, how does it relate to `run_sanity.sh`.
- Does `apps/morning-mcp-app`'s own sandbox integration suite get the same treatment.
- Whether to pin `-n` in `pytest.ini` `addopts` (no — keep opt-in; default stays serial).

## Touches

`apps/denidin-app/requirements.txt` (+ `pytest-xdist`), `apps/denidin-app/tests/billed/conftest.py`
(per-worker `data_root`), possibly `apps/morning-mcp-app/` equivalents, a handful of
count/summary-sensitive billed tests, a new parallel-sweep script. Does **not** touch
`scripts/run_sanity.sh`, `scripts/run_single_test.sh`, or `scripts/run_multiple_billed_tests.sh`.
