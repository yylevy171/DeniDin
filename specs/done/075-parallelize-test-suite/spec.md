# Feature Specification: Parallelize the Sanity Test Suite

**Feature Branch**: `feature/075-parallelize-test-suite`
**Created**: 2026-09-03
**Status**: Done — merged in PR #276 (Feature 059 follow-up)
**Priority**: P2 (developer/agent iteration time only — there is no CI here)

## Goal

The `billed` sanity subset (41 tests across 17 files after the split below,
run serially by
`scripts/run_sanity.sh`) takes ~25–40 min. Almost all of that is unavoidable
per-test cost (real OpenAI Responses API, real Morning MCP over a real ngrok
tunnel, chained model→tool→model rounds, deliberate `time.sleep` for Morning's
search-index lag — no mocking, by constitution). The only lever is running
independent tests concurrently. **Target: the whole sanity billed subset green
in ~5 minutes.**

## Scope (what this feature does)

- **New, separate entrypoint `scripts/run_sanity_parallel.sh`.** A fast "is the
  whole billed sanity subset green?" sweep. `scripts/run_sanity.sh` is **not
  touched in behavior** — its sequential contract (one test per process, live
  `>>> SANITY [k/N] PASSED|FAILED` sound-off, stop-on-first-failure, resumable
  `sanity_state.tsv`) is inherently serial and was shaped by explicit user
  incidents. The parallel sweep trades all of that for wall time.
  - Runs the `morning-mcp-app` gate test first, serially (a broken tunnel fails
    everything downstream).
  - Then `pytest -n <N> --dist loadfile -m "sanity and not expensive"` over
    `apps/denidin-app/tests/billed/`. Default `-n 8`, override with `-n N`.
  - `--dist loadfile` pins every test **file** to one worker → the deliberate
    within-file "one long shared chat" ordering (create → mark paid → …) stays
    serial; different files run in parallel.
  - `expensive` sanity tests are **never** run here — same rule as
    `run_sanity.sh` (fresh explicit approval per expensive test). Reported via
    `run_sanity.sh --status`.
  - **Subset mode**: trailing sanity node-id args run just those in one
    parallel round — `-n` defaults to the number of distinct files among them
    (each file its own worker, capped by an explicit `-n`), gate skipped by
    default. For fast "re-run just these N" iteration.

- **Per-xdist-worker `test_data/` root.** `tests/e2e_helpers.py::sanity_worker_data_root()`
  returns `test_data/<PYTEST_XDIST_WORKER>/` when running under xdist, else the
  canonical `test_data/` unchanged. Every sanity-subset config fixture sources
  `config.data_root` from it — `tests/billed/conftest.py`, the 8 billed test
  files with their own local `config` fixture, **and the 2 expensive sanity
  files** (`test_image_classification_e2e.py`, `test_ledger_event_capture_e2e.py`).
  All of them must agree: `--dist loadfile` can land an expensive sanity file and
  a billed one on the same worker (one process, one module-global
  `denidin.denidin_app`), and whichever fixture builds that singleton first wins
  — if they disagreed on the root, the second file's own isolation guard would
  trip. This also keeps parallel workers from corrupting each other's ChromaDB
  long-term memory, ledger-event JSON (`events/`), `reminders.db`, and sessions
  — and makes `tests/billed/conftest.py`'s autouse before-AND-after cleanup
  fixtures (`_clean_reminders_around_every_test`,
  `_clean_ledger_events_around_every_test`) per-worker-safe (they were wiping a
  single shared path before/after *every* test).

- **One retry round for infra-signature failures.** The single shared ngrok
  free-tier tunnel is the real concurrency ceiling — under burst load it browns
  out for ~60–90s, and every in-flight MCP call in that window fails (OpenAI
  reports `mcp_network_error` / "Connection failed." / HTTP 424 "Failed
  Dependency" on the tool-list fetch). That is harness-induced infra, not a
  product defect. After the initial round, `run_sanity_parallel.sh` re-runs
  **only** the failures whose traceback carries such a signature
  (`scripts/_sanity_retryable_failures.py` classifies; real assertion failures
  and model nondeterminism are terminal and never re-run). Defaults: one initial
  round + one retry round, retry fires immediately (delay 0). `--retry-max-rounds
  N` adds rounds with a `--retry-delay` that escalates by `--retry-factor` (1.5)
  each round; `--no-retry` for a single raw pass. The final banner lists terminal
  failures and still-red infra failures separately.

- **Split `test_denidin_morning_invoice_creation_e2e.py`.** It had grown to
  hold 7 `@pytest.mark.sanity` tests (~4.5–5 min serial), making it the long
  pole of a file-level parallel run. The self-contained "Feature 027" block
  (the 8 `create_document_*` flows + the T1/T2 similarly-named-client variants,
  3 of them `sanity`) moved verbatim into a new
  `test_denidin_morning_document_flows_e2e.py` — pure reorganization, zero test
  logic changed. `scripts/run_sanity.sh`'s node-id array updated for the 3
  moved sanity node ids; `scripts/verify_sanity_lists.sh` passes.

- **`pytest-xdist>=3.6.0`** added to `apps/denidin-app/requirements.txt`.

## Out of scope

- The full `billed` suite (only the `sanity` subset is parallelized here).
- `apps/morning-mcp-app`'s own sandbox integration suite.
- Per-test isolation (every test its own `chat_id`, module fixtures → function
  scope). File-level parallelism is the low-risk unit; per-test isolation was
  explicitly considered and deferred as too destabilising for the payoff.
- Pinning `-n` in `pytest.ini addopts` — default stays serial; parallel is
  opt-in via the new script only.

## Known risks / follow-ups

- **Shared Morning sandbox, concurrent writers.** Most sanity billed tests seed
  fresh unique clients (`_seed_client`, ~334K name combos with exact-collision
  redraw) — safe. Count/summary-sensitive tests are the risk: anything
  asserting "client X has exactly N documents", `get_financial_summary` totals,
  `list_invoices` page contents, or a fixed ground-truth client's history
  (`דורית אשכנזי`, `זהבית צור`, `כרמלי דודי` — see `GROUND_TRUTH_CLIENTS.md`).
  Plan: run the parallel sweep once with the container up, fix only the
  specific tests that actually break under concurrency (per-run unique clients,
  or an `xdist_group` to serialize them). Candidates from Feature 059's
  `sanity-failures.md`: S2 (already blocked on Feature 069), the `זהבית`
  collision family.
- **ngrok tunnel brownout under concurrent load.** Confirmed real: `-n 8`
  dropped a `create_receipt` mid-request (2026-09-04), and `-n 6` later lost a
  ~70s window that took out 3 in-flight MCP calls across 3 workers (server
  received zero requests 01:18:14→01:19:30 while OpenAI reported
  `mcp_network_error` / 424). The free tunnel simply can't absorb 6 workers'
  bursts. Mitigations in place: default `-n 6` (not 8), the gate test warms the
  tunnel first, and the one retry round (see Scope) re-runs exactly these
  failures. A permanent fix (paid tunnel / a second tunnel / app-level MCP
  backoff) is out of scope here.
- Morning sandbox / Green Invoice API rate limits under `-n 6`+ are unconfirmed
  — no rate-limit errors seen in runs so far.

## Touches

`apps/denidin-app/requirements.txt`, `apps/denidin-app/tests/e2e_helpers.py`
(`billed_test_data_root` → `sanity_worker_data_root`),
`apps/denidin-app/tests/billed/conftest.py`,
`apps/denidin-app/tests/billed/denidin_mcp_e2e_helpers.py` (re-export),
8 `tests/billed/test_*.py` + 2 `tests/expensive/test_*.py` local `config`
fixtures (per-worker root),
`tests/billed/test_denidin_morning_document_flows_e2e.py` (new, split-out),
`apps/denidin-app/conftest.py` (SANITY_PARALLEL_SOUNDOFF: `>>> SANITY [k/N]`
per-test sound-off on the xdist controller, mirroring `run_sanity.sh`; no-op
otherwise),
`scripts/run_sanity_parallel.sh` (new),
`scripts/_sanity_retryable_failures.py` (new — retry-round failure classifier),
`scripts/run_sanity.sh` (3 moved node ids only — no behavior change).

### Also carried in this PR (sanity-subset stabilization surfaced by the parallel sweep)

- **F1 — `test_ledger_query_billed.py::test_hours_by_client_this_month` → `test_hours_by_client_last_month`.** The old fixture seeded ledger entries on fixed days of the *current* month, which became future-dated dates whenever the run happened before that day-of-month (real failure 2026-09-04). Re-anchored to the 3rd + 14th of the **previous** month (+ a two-months-ago decoy), query is now "בחודש שעבר", assertion is the sum of the first two. `scripts/run_sanity.sh` node-id updated.
- **F2 — bank-deposit image swap `Bank-test-image.jpg` → `Deposit_Eti.jpeg`** in `test_image_classification_e2e.py` and `test_ledger_event_capture_e2e.py`. 23 accumulated ₪1,500 sandbox invoices for the old fixed payer made the model refuse an apparent duplicate. New image (₪554, 05/08/2026, payer אסתר אסולין, bank 31/branch 112/account 105397180); name assertions loosened to the shared surname token; both docstrings carry a "swap the image again after 20+ invoices" note. New client `אסתר אסולין` one-time seeded in the Morning sandbox and added to `pull_sandbox_clients.py`'s `DENYLIST_EXACT` + `tests/billed/GROUND_TRUTH_CLIENTS.md`; `tests/fixtures/morning_sandbox_clients.json` regenerated (the retired `עטיה רועי מאיר` stays denylisted — `test_group_b_reference_approval_e2e.py` still uses the old image).
- **Feature 059 spec moved `specs/backlog/` → `specs/done/`** (it shipped) — cross-references in `.github/{CONSTITUTION,METHODOLOGY,quick-ref-constitution}.md`, `CLAUDE.md`, `bugfix-045`/`bugfix-050`, and 3 test-file docstrings repointed.

## No TDD

Per explicit user instruction (2026-09-03): this is test-infrastructure
plumbing, not application behavior. Validation is the parallel sweep itself
running green, compared against the serial `run_sanity.sh` baseline — no new
`billed`/`expensive` acceptance tests are written for it.
