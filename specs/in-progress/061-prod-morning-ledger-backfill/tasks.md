---
description: "Task list for 061-prod-morning-ledger-backfill"
---

# Tasks: Prod Morning Ledger Backfill

**Input**: Design documents from `specs/in-progress/061-prod-morning-ledger-backfill/`
**Prerequisites**: plan.md, spec.md, user-stories.md, research.md, data-model.md, contracts/,
quickstart.md (all present and consistent as of round 4, 2026-08-25)

**How this deviates from the generic template**: this repo's real convention (per `CLAUDE.md`'s
Spec-Driven Workflow section and METHODOLOGY §VI) is TDD via Task-a/Task-b pairs — a RED test task
blocked-on-approval, then a GREEN implementation task — for every unit/integration-level phase
below, plus a final Acceptance phase whose `billed` scenarios are only described here in
user-experience terms (no test code yet) and are written + run together, once, at the very end.
This feature is one operator running one linear pipeline rather than several independent personas,
so phases below are organized around the pipeline's own **Phase 1 → 2 → 3 → 3.5 → 4** numbering
(`spec.md`/`user-stories.md`) plus two cross-cutting requirements, not around unrelated user roles
— matching `plan.md`'s own "Task Group" structure, which this file turns into concrete checklist
tasks.

**Tests**: REQUIRED for every phase below except Phase 4 (Load — deliberately deferred, no design
yet to test against) — this repo's TDD discipline is not optional, unlike the vanilla template's
default.

## Format: `[ID] [P?] [Phase] Description with file path`

- **[P]**: Parallelizable — different files, no dependency on an incomplete task in the same group.
- **[Phase]**: `[Ph1]`/`[Ph2]`/`[Ph3]`/`[Ph3.5]`/`[Ph4]` map to this feature's own pipeline phases
  (`user-stories.md`); `[XC-Rerun]`/`[XC-Creds]` map to the two cross-cutting requirements.

---

## Phase A: Setup

**Purpose**: Stand up the new standalone app before any pipeline code exists.

- [x] T001 Create `apps/prod-ledger-backfill/` directory structure (`config/`, `tests/unit/`,
      `tests/billed/`) per `plan.md`'s Project Structure
- [x] T002 Author `apps/prod-ledger-backfill/requirements.txt` — **corrected during implementation**:
      not a "local path dependency" (neither sibling app is pip-installable — no setup.py/
      pyproject.toml in either); real PyPI packages only (`requests`/`urllib3`/`pytest`), with
      sibling-app access via `sys.path` in `conftest.py`, matching `apps/morning-mcp-app`'s and
      `apps/denidin-app`'s own established convention. `openai` deliberately not listed unless/until
      Phase 2's real experiment selects Method B.
- [x] T003 [P] Created `apps/prod-ledger-backfill/.gitignore` — **corrected during implementation**:
      this repo has no `*.local.*` glob anywhere (each app's `.gitignore` lists real secret
      filenames explicitly, confirmed by reading both sibling apps' `.gitignore`s); added explicit
      entries for both creds files plus local pipeline output directories.
- [x] T004 [P] Authored `apps/prod-ledger-backfill/conftest.py` (**at the app root, not
      `tests/conftest.py`** — matches both sibling apps' actual convention, confirmed by reading
      their own `conftest.py` files) — `sys.path` bootstrap for both external-app imports, plus
      fixtures: `tmp_output_dir`, `fixture_creds_dict`/`fixture_creds_file`, `fixture_raw_document`,
      `fixture_search_page_1`/`fixture_search_page_2` (150-document multi-page fixture, per
      `research.md` R3/R4).

**Checkpoint**: new app scaffold exists, installable, empty test suite collects with zero errors.

---

## Phase B: Foundational

**Purpose**: Nothing below is testable without the one real, external-boundary dependency every
phase touches — a way to construct `MorningClient` against either a fixture HTTP layer (unit
tests) or the real Morning sandbox/prod (Acceptance phase only).

- [x] T005 Confirmed via `tests/unit/test_imports.py::test_morning_client_and_auth_import_cleanly`
      — `MorningClient`/`MorningAuth` import cleanly from a real venv (`requirements.txt` +
      `conftest.py`'s `sys.path` bootstrap). Test passes.
- [x] T006 [P] **Real gap found and fixed during implementation**: a plain
      `from src.managers.ledger_event_manager import LedgerEventManager` triggers
      `src/managers/__init__.py`'s eager imports of `SessionManager` (needs `tiktoken`),
      `MemoryManager` (needs `chromadb`/`openai`), etc. — none of which `LedgerEventManager` itself
      needs, but Python always runs a package's `__init__.py` when importing any submodule.
      Resolved via `_ledger_event_manager_loader.py` (new): loads the one file directly via
      `importlib`, under a synthetic module name outside the `src.managers` package hierarchy, so
      `src/managers/__init__.py` never executes. No change to any file under
      `apps/denidin-app/`. Confirmed via `test_ledger_event_manager_imports_cleanly` AND
      `test_ledger_event_manager_does_not_drag_in_heavy_siblings` (asserts `tiktoken` never lands
      in `sys.modules`). Both pass.

**Checkpoint**: both external-app imports (`morning-mcp-app`'s client, `denidin-app`'s
`LedgerEventManager`) are provably importable before any pipeline logic is written against them.

---

## Phase C: Phase 1 — An operator downloads real prod Morning documents to local files (P1)

**Goal**: `download.py` — `MorningClient`-direct, uncapped pagination, one raw file per document.
**Independent Test**: see `user-stories.md` Phase 1.

- [x] T007 [Ph1] **Task A (RED) — WRITTEN, RED CONFIRMED (`ModuleNotFoundError: No module named
      'download'`), AWAITING APPROVAL before T008** — `apps/prod-ledger-backfill/tests/unit/test_download.py`:
      CLI rejects missing `--since` (non-zero exit, clear error, REQ-BACKFILL-001); creds-file
      validation fails before any network call for missing file / malformed JSON / missing field
      (REQ-BACKFILL-006); pagination logic against a fixture multi-page `/documents/search` response
      correctly follows `page`/`pages`/`total` with no 100-item cap (`research.md` R3/R4) — 🚨
      human approval required before Task B proceeds (METHODOLOGY §VI)
- [x] T008 [Ph1] **Task B (GREEN)** — `apps/prod-ledger-backfill/download.py`: CLI parsing
      (`--since`/`--output-dir`/`--creds-file`, `contracts/cli-contract.md`), creds-file
      load+validate, `MorningClient` construction, the uncapped pagination loop, one raw JSON file
      per document keyed on the document's own Morning id (`data-model.md` entity 1)
- [x] T009 [Ph1] Verify: `test_download.py` green (15/15); manual read-through confirms
      `download.py`'s only import beyond stdlib is `denidin_mcp_morning.morning_client.MorningClient`
      — no `tools.py`, `AIHandler`, or any live-MCP/OpenAI code path anywhere (REQ-BACKFILL-002)
- [x] **Bug found and fixed (2026-08-26, user's own scrutiny of the mcp/Method-A relationship)** —
      real-code trace of `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`'s
      `get_invoice_details`/`list_invoices(include_full_details=True)` confirmed Stage 1+2
      (`Invoice.model_validate` + `format_invoice_json`) are byte-identical, literally the same
      imported functions, between production and `method_a.build_capture_envelope()` — but
      surfaced that production's per-document fan-out silently falls back to shallower search-page
      data on a `get_invoice()` failure and keeps going, while `download_all_documents()` had NO
      error handling at all (a single failure would crash the whole run). Human decision: fail
      loudly instead (a backfill's whole point is fidelity — silently persisting less-complete
      data is worse than stopping; re-running is safe via overwrite-by-id dedup). Added
      `DocumentDownloadError` (names the failed document id) + a try/except in
      `download_all_documents()` + clean non-zero-exit handling in `main()`. Two new RED-then-GREEN
      tests added to `test_download.py` (17/17 now green; full unit suite 34/34 green).
- [x] **`--until` added (2026-08-26, user directive)** — this session's first real Method A run
      against the dev sandbox showed the gap: `--since` alone pulled 97 documents spanning a week
      (2026-08-20 through today) when only one day's ~18 were wanted, requiring a manual local
      filter-by-`documentDate` after the fact. Rather than repeat that every time, `download.py`
      gained an optional `--until` (inclusive stop date, defaults to `None` — the unbounded-forward
      sweep stays the default, unchanged for a real prod run) — `parse_until_date` (parses or
      raises `BackfillPreconditionError`, `None` passes through), `validate_date_range` (rejects
      `--until` before `--since`; equal is allowed — a legitimate single-day window), and
      `paginate_document_ids`/`download_all_documents` now accept `until` and pass Morning's real,
      confirmed-live `toDate` search param (same key `denidin_mcp_morning/tools.py`'s own
      `_map_list_invoices_filters` uses) — server-side filtering, not a local post-fetch filter, so
      a bounded pull never over-fetches in the first place. Since both `select_method.py`'s
      `--generate-a`/`--generate-b` and `transform.py` just iterate whatever `--input-dir` already
      contains, bounding it once at the `download.py` step is sufficient for both methods — no
      separate date-filtering logic needed in either generator. 11 new RED-then-GREEN tests in
      `test_download.py` (28/28 now green; full unit suite 74/74 green).

**Checkpoint**: Phase 1 unit-tested and implemented; no real network call made yet.

---

## Phase D: Phase 2 — A sandbox experiment decides Phase 3's transform method (P1)

**Goal**: `select_method.py` — diffs Method A vs Method B output, one-time, sandbox-only.
**Independent Test**: see `user-stories.md` Phase 2.

- [x] T010 [Ph2] **Task A (RED) — approved, then GREEN** — `apps/prod-ledger-backfill/tests/unit/test_select_method.py`:
      the field-by-field diff helper, given synthetic fixture `LedgerEvent` pairs, reports
      "IDENTICAL" for a fully-matching pair and names the exact differing field(s) for a
      deliberately-mismatched pair, always excluding `event_id`. 7/7 green.
- [x] T011 [Ph2] [P] **Task B (GREEN)** — `apps/prod-ledger-backfill/method_a.py`: Method A, the
      deterministic field mapping (raw Morning JSON → `LedgerEvent` fields), per `research.md` R7.
      **Corrected during implementation**: rather than hand-rolling a mapping, reuses
      `denidin_mcp_morning.models.Invoice` + `.formatters.format_invoice_json` (parses
      `MorningClient.get_invoice()`'s raw shape into the same machine-readable JSON Feature 025's
      live pipeline already produces) piped straight into
      `ledger_event_manager._expand_accounting_document_json` (reached via
      `_ledger_event_manager_loader.py`) — the exact same code-derived expansion the real,
      running ledger already depends on. No new mapping logic at all, just glue. Verified both by
      unit tests (`tests/unit/test_method_a.py`, 3 tests, real-shaped raw-document fixtures, no
      network) and by an ad-hoc smoke test against a hand-built realistic raw document, producing
      a fully-correct `LedgerEvent` dict. Along the way, corrected a real field-name error in the
      earlier planning docs — see `research.md`/`data-model.md` for the fixed field list.
- [x] T012 [Ph2] [P] **Task B (GREEN)** — `apps/prod-ledger-backfill/method_b.py`: Method B, the
      AI-mediated mapping (OpenAI call, no MCP tool attached, adapted from Feature 025's
      `_build_reconciliation_prompt`/`LEDGER_EVENT_TOOL` shape), per `research.md` R7. Defines its
      own local, minimal `_CHESHBONIT_CAPTURE_TOOL` schema (faithful to the real `LEDGER_EVENT_TOOL`'s
      חשבונית-relevant fields only — `ai_handler.py`'s own top-level imports are too heavy to reuse
      directly, unlike `LedgerEventManager`) since a real OpenAI call is never exercised by a unit
      test; `openai_client` is injectable for testability, real `OpenAI()` constructed only when
      actually invoked.
- [x] T013 [Ph2] **Task B (GREEN)** — `apps/prod-ledger-backfill/select_method.py`: CLI
      (`--input-dir`/`--report-out`), runs both T011/T012 against every file, diffs, writes the
      report (`data-model.md` entity 3), prints the verdict.
- [x] T014 [Ph2] Verify: `test_select_method.py` green (7/7), plus `test_method_a.py` (3/3) added
      as a regression test locking in the real reuse-based design. Full unit suite: 28/28 green.

- [x] **T010-T014 REDESIGNED (2026-08-26, per direct user direction)** — the comparison above
      (T013's `run_experiment`/`build_arg_parser`/`main`, calling `method_a.transform()`/
      `method_b.transform()` and diffing full `LedgerEvent` output via `diff_ledger_events`) was
      never exercised by any test and is now superseded, NOT deleted (kept working, in case still
      useful later — `diff_ledger_events`/`format_verdict` themselves are UNCHANGED and stay, since
      `validate.py`'s Phase 3.5 sampled field comparison depends on `diff_ledger_events` directly).
      **Why redesigned**: comparing at the final `LedgerEvent` level (Stage 3) conflated two
      separate questions — "does Stage1+2 survive a live AI relay intact?" vs "does Stage 3's own
      derivation logic work?" — user's framing: "The goal is to compare the raw inputs (assuming
      AI doesn't botch the passthrough, which is also sort of tested in this setup)." Also: the
      original design recomputed both methods' output live inside the comparison step itself; user
      direction: "no computing on the fly during the run — a run... creates the data and computes
      the hash for each json string and stores it. The validation just compares total no of items
      and then the individual hashes."
      **New design**: compares Method A vs Method B at the CANONICAL JSON level (Stage 1+2 only —
      `format_invoice_json`'s output) via sha256 hashes, computed once per "run" and stored in a
      manifest — never recomputed during comparison.
      - `method_a.py` gained `compute_canonical_json(raw_document) -> str` (Stage 1+2 only, no
        Stage 3) — `build_capture_envelope()` now calls it internally rather than duplicating it.
      - `select_method.py` gained `generate_method_a_manifest(input_dir, output_dir)` (pure local
        code, no live server — runnable now: for every raw document, writes its canonical JSON
        file + records its sha256 in `manifest.json`), `compare_manifests(manifest_a, manifest_b)`
        (pure dict diff — count/only-in-A/only-in-B/mismatched-hashes/identical),
        `format_manifest_verdict(...)`, and a new CLI surface: `--generate-a`/`--generate-b
        --input-dir --output-dir` and `--compare --manifest-a --manifest-b --report-out` (two
        separate parsers, `build_generate_arg_parser`/`build_compare_arg_parser`, dispatched by
        `main()` sniffing argv for `--compare` — same pattern as `validate.py`'s `--approve`
        dispatch).
      - New tests: `tests/unit/test_select_method_manifest.py`, 13 tests (manifest generation is
        deterministic/covers every document with no sampling; comparison catches a hash mismatch,
        a missing-on-either-side document; CLI required-args; the deferred Method B generator
        fails loudly and specifically, not silently). Full unit suite: 60/60 green.
      - **`generate_method_b_manifest(...)` fully implemented 2026-08-26** (per explicit follow-up
        instruction: "implement everything that requires implementation, but dont touch morning
        app or denidin app code"): a real OpenAI Responses API call per document, with a real
        remote `type: "mcp"` tool attached to the live dev/sandbox `morning-mcp-app` server —
        `select_method._discover_mcp_server_url` independently reimplements (no import)
        `MorningMcpLocator`'s shared-status-file-reading pattern, reading a NEW, separate,
        gitignored `config/backfill_mcp_creds.local.json`
        (`contracts/backfill-mcp-creds-file.md`); `select_method._build_mcp_tool` independently
        reimplements (no import) `ai_handler.py`'s remote-MCP-tool shape, scoped to
        `get_invoice_details` only, in the "never-approval" bucket. The model is asked to fetch
        the document via the real MCP protocol, then relay the exact canonical JSON string it got
        back verbatim through a local `relay_canonical_json` function-tool call — deliberately not
        just reading the MCP call's own raw output, so the passthrough-fidelity risk the user's
        design is meant to test ("assuming AI doesn't botch the passthrough, which is also sort of
        tested in this setup") is actually exercised. Fails closed with a new
        `MethodBUnavailableError` (distinct from the old `NotImplementedError` — it now means "the
        code exists, the live prerequisites aren't there right now", not "not written yet") before
        any OpenAI call, if the creds file / status file / running-server prerequisites aren't
        met. New tests (`tests/unit/test_select_method_manifest.py`, +4, replacing the old
        "explicitly not yet implemented" test): relay-per-document with a fake OpenAI client and a
        fixture MCP status file (asserts the real MCP tool + local relay tool shape, no real
        network call), full document coverage, missing-creds-file and server-not-running failure
        modes. Full unit suite: 63/63 green (also required installing the already-declared
        `email-validator` dependency into this app's own venv — a pre-existing, unrelated gap that
        was silently breaking `test_method_a.py`/`test_transform.py`/`test_validate.py`
        collection before this session).
      - **Still deferred, its own approval gate**: actually RUNNING Method B's generator (needs
        the real dev/sandbox `morning-mcp-app` server started) and the real 20-document Phase 2
        experiment itself remain Acceptance-phase concerns (T031) — writing this code did not
        start any environment or make any real network/OpenAI call.

**Checkpoint**: Phase 2's diff mechanism and both candidate methods exist; the real sandbox
comparison itself runs in the Acceptance phase, not here.

---

## Phase E: Phase 3 — Downloaded files are transformed into ledger events locally (P1)

**Goal**: `transform.py` — applies whichever method Phase 2's real experiment selects.
**Independent Test**: see `user-stories.md` Phase 3.
**Depends on**: Phase D's Acceptance-phase experiment result (which method to wire up for real) —
see the Acceptance phase below; `transform.py`'s own scaffolding can be built against either method
via a flag/parameter, with the real default set once the experiment concludes.

- [x] T015 [Ph3] **Task A (RED) — approved, then GREEN** — `apps/prod-ledger-backfill/tests/unit/test_transform.py`:
      given a directory of fixture raw Morning document files, `transform.py`'s mapping produces
      correctly-shaped `LedgerEvent` dicts (`schema_version>=2` — asserted as a floor, not pinned
      to the real app's current `CURRENT_SCHEMA_VERSION=3`, so this test doesn't break every time
      the real app bumps its own schema further; all `accounting_document_*` fields populated),
      with no live network call reachable (`transform.py` never imports `MorningClient` at all,
      unlike `download.py` — asserted directly); ALSO (speckit.analyze finding U1,
      REQ-BACKFILL-005) a large fixture `--input-dir` (155 raw document files, one per minute to
      stay clear of `LedgerEventManager`'s real per-minute event_id sequence-digit cap) produces
      155 `LedgerEvent` files, proving no artificial cap exists on Phase 3's own output count. 4
      tests total.
- [x] T016 [Ph3] **Task B (GREEN)** — `apps/prod-ledger-backfill/transform.py`: CLI
      (`--input-dir`/`--output-dir`), reads raw files, persists via
      `LedgerEventManager.add_ledger_event` pointed at `--output-dir` (REQ-BACKFILL-004),
      retaining every anomaly outcome (LedgerEventManager's own `pending_review.json`) for Phase
      3.5 to read. **Design note discovered during implementation**: `method_a.transform()`/
      `method_b.transform()` (T011/T012) return the already-Stage-3-expanded `LedgerEvent` dict —
      correct for Phase 2's field-by-field comparison, but `add_ledger_event` expects the
      UN-expanded `{"source_type": "חשבונית", "accounting_document_json": ...}` envelope (it does
      its own Stage-3 expansion internally). So both `method_a.py` and `method_b.py` were extended
      with a new `build_capture_envelope()` function each (stops one step earlier than
      `transform()`), and `transform.py` calls that instead — this is what lets
      `LedgerEventManager`'s own real event_id generation and dedup/anomaly guard run for real
      rather than being bypassed. Currently wired to Method A only (`_DEFAULT_BUILD_ENVELOPE_FN`)
      — swapping to Method B once T031's real sandbox verdict is in is a one-line change
      (`build_envelope_fn` parameter already exists for this and for testability).
- [x] T017 [Ph3] Verify: `test_transform.py` green (4/4); confirmed zero imports of any live
      Morning-API-calling code inside `transform.py` (`argparse`/`json`/`sys`/`pathlib`/`typing`/
      `method_a`/the ledger-event-manager loader only — no `MorningClient`, no `requests`, no
      `openai`). Full unit suite: 32/32 green.
**Checkpoint**: Phase 3 unit-tested and implemented against fixtures.

---

## Phase F: Phase 3.5 — Validate Phase 3's output before it is trusted for load (P1) — NEW

**Goal**: `validate.py` — count reconciliation, anomaly surfacing, sampled field comparison,
sign-off gate. **Depends on**: Phase C/E (needs real raw + `LedgerEvent` fixture shapes).
**Independent Test**: see `user-stories.md` Phase 3.5.

- [x] T018 [Ph3.5] **Task A (RED) — approved, then GREEN** — `apps/prod-ledger-backfill/tests/unit/test_validate.py`:
      given a fixture Phase-1 directory and a fixture Phase-3 output directory with a deliberate
      mismatch (one raw document with no corresponding `LedgerEvent`, one pair with a deliberately
      wrong field), the count reconciliation flags the missing document and the field-level sample
      check flags the mismatched field; given a fully-matching fixture pair, both checks report
      clean. Field-level comparison design: reuses `method_a.transform()` as a deterministic
      ground-truth oracle (recomputes the expected `LedgerEvent` from the raw document) and
      `select_method.diff_ledger_events()` for the comparison itself — no new mapping/diff logic.
      Also covers: anomalies read from `pending_review.json` at `ledger_dir.parent /
      "accounting_reconciliation"` — a SIBLING of `--ledger-dir`, not nested inside it (confirmed
      directly against `LedgerEventManager._append_pending_review`, not assumed); the read-only
      guarantee (directory listing unchanged after a run); and the sign-off/`--approve` mechanism
      (T020). 13 tests total (corrected from an earlier miscount of 15).
- [x] T019 [Ph3.5] **Task B (GREEN)** — `apps/prod-ledger-backfill/validate.py`: CLI
      (`--raw-dir`/`--ledger-dir`/`--report-out`/`--sample-size`), reads both directories only (no
      live Morning API call), computes the count reconciliation, collects Phase 3's retained anomaly
      outcomes, samples documents for field-level comparison, writes the report with an unsigned
      sign-off field (`data-model.md` entity 4, REQ-BACKFILL-010). **Design note**: `--approve` mode
      lives on its own separate `build_approve_arg_parser()`, not `build_arg_parser()` — argparse
      can't cleanly express "required only if --approve is set" on one shared parser; `main()`
      dispatches to whichever parser matches by checking for `--approve` in argv first.
- [x] T020 [Ph3.5] **Task B (GREEN)** — implemented as `validate.py --approve --report-in <path>
      --signed-by <name>`: rewrites the report's `sign_off` field to `{signed: true, signed_by,
      signed_at}` (Israel-local timestamp via `src.utils.time_utils.now_local`) — a separate,
      explicit action, never automatic; `--signed-by` is required (no guessing who approved it);
      approving a missing report fails cleanly (non-zero exit, no traceback).
- [x] T021 [Ph3.5] Verify: `test_validate.py` green (13/13); confirmed `validate.py` never opens
      any file for writing under `--ledger-dir` (directory listing byte-identical before/after a
      run, asserted directly, not just "we didn't call open()"). Full unit suite: 47/47 green.

**Checkpoint**: Phase 3.5's gate exists and is provably read-only and provably catches both a
count mismatch and a field mismatch in a controlled fixture.

---

## Phase G: Cross-cutting — Re-running any phase never creates duplicate output (P2)

**Independent Test**: see `user-stories.md`'s re-run-safety cross-cutting section.

- [ ] T022 [XC-Rerun] **Task A (RED)** — extend `test_download.py`: running `download.py` twice
      against the same fixture window overwrites the same local filename rather than creating a
      second copy — 🚨 human approval required before Task B proceeds
- [ ] T023 [XC-Rerun] **Task A (RED)** — extend `test_transform.py`: constructing two separate
      `LedgerEventManager` instances against the same `storage_dir` (simulating two `transform.py`
      invocations) confirms the second instance's `add_ledger_event` call for an already-present
      document returns the existing dedup outcome, not a new file — 🚨 human approval required
      before Task B proceeds
- [ ] T024 [XC-Rerun] **Task B (GREEN)** — `download.py`'s filename-keyed overwrite behavior (new,
      small addition to T008's implementation)
- [ ] T025 [XC-Rerun] Verify: both extended tests green; `transform.py` needs no code change beyond
      Phase E (satisfied entirely by `LedgerEventManager`'s existing guard, per `research.md` R8)

**Checkpoint**: re-run safety proven at the unit level for both Phase 1 and Phase 3.

---

## Phase H: Cross-cutting — Real prod credentials never land in git (P2)

**Independent Test**: see `user-stories.md`'s credential-security cross-cutting section.

- [ ] T026 [XC-Creds] **Task A (RED)** — extend `test_download.py`: missing
      `backfill_prod_creds.local.json` → `download.py` exits non-zero with a clear error before any
      `MorningClient` construction is reached (assert via dependency injection, not mocking internal
      logic); malformed JSON → same; missing any of the four required fields → same — 🚨 human
      approval required before Task B proceeds
- [ ] T027 [XC-Creds] **Task B (GREEN)** — the precondition-checking sequence in `download.py`
      (already scaffolded by T008; this task closes any gap the extended test reveals)
- [ ] T028 [XC-Creds] Verify: extended test green; manually confirm
      `apps/prod-ledger-backfill/config/backfill_prod_creds.local.json`'s path matches the existing
      `.gitignore`'s `*.local.*` glob (add an explicit entry if it doesn't)

**Checkpoint**: credential-loading failure modes are all fail-closed, verified before any real
creds file is ever created on an operator's machine.

---

## Phase I: Phase 4 — Validated local output is loaded into prod's real data store (P3)

**Goal**: `load.py` — deliberately deferred. **Depends on**: the Acceptance phase below being green
and reviewed (`plan.md`'s Close-out).

- [ ] T029 [Ph4] **Placeholder** — design Phase 4's load mechanism (`research.md` R10: temporary
      elevated write access vs. running directly on the Windows box over the `denidin-winprod` SSH
      alias) as its own short research pass, once Phases 1-3.5 are proven correct against real data
      — not broken into concrete sub-tasks here, since the design doesn't exist yet. This task is
      **not started** as part of this `speckit.tasks` pass; revisit after the Acceptance phase.

**Checkpoint**: N/A until T029 is picked up as its own follow-up planning pass.

---

## Acceptance Phase (billed/expensive, written + run together, once, at the end — METHODOLOGY §VI)

Per the TDD redefinition, the scenarios below are written as real, end-to-end tests only now,
against real systems — described here in user-experience terms, not as test code yet:

- [ ] T030 **Acceptance — Phase 1**: `apps/prod-ledger-backfill/tests/billed/test_backfill_acceptance.py`
      — run `download.py` against real prod data with a narrow, small real start-date window;
      assert raw document files appear locally with the expected shape; assert no document was
      silently dropped for exceeding a conversational fetch/token cap; assert no WhatsApp message
      is sent as a side effect (speckit.analyze finding U2, REQ-BACKFILL-008) 🚨 requires its own
      fresh, explicit human approval before running (REQ-BACKFILL-007) — real prod data
- [ ] T031 **Acceptance — Phase 2**: the real ~20-document sandbox experiment (`select_method.py`
      against real sandbox downloads); records the real verdict and updates `transform.py`'s default
      method (T016) to match — no prod approval needed, sandbox only
- [ ] T032 **Acceptance — Phase 3**: run `transform.py` against Phase 1's real output (T030); assert
      correctly-shaped `LedgerEvent` files appear; assert zero live Morning API calls during this
      run and zero WhatsApp messages sent
- [ ] T033 **Acceptance — Phase 3.5**: run `validate.py` against T030/T032's real output; assert the
      report correctly reconciles counts and surfaces zero unexplained anomalies for a clean real
      window; operator reviews and signs off
- [ ] T034 **Acceptance — Re-run safety**: run `download.py` and `transform.py` each twice over the
      same real window/input; assert the second run's newly-captured count is zero 🚨 requires fresh
      approval — real prod data
- [ ] T035 **Acceptance — Credential security**: after T030's real run, assert no prod credential
      appears in any git-tracked file (`git status`/`git diff`)

Every real-prod-touching run above (T030, T034, and any prod-side portion of T035) requires its own
fresh, explicit human approval per root `CLAUDE.md` — this task list does not pre-approve any of
them. T031 (sandbox) needs no such gate.

---

## Dependencies & Execution Order

```
Phase A (Setup)
  └─→ Phase B (Foundational) — both import boundaries proven
        ├─→ Phase C (Ph1, P1)   ──┐
        ├─→ Phase D (Ph2, P1)   ──┤ Ph1/Ph2 are independent of each other
        │                          │ (Ph2 only needs Ph1's download.py for
        │                          │ its own sandbox input files, not its
        │                          │ implementation)
        │                          ▼
        │                    Phase E (Ph3, P1) — needs Ph2's Acceptance-phase
        │                          │              verdict (T031) for its real
        │                          │              default method, but its
        │                          │              scaffolding (T015/T016) can
        │                          │              be built against either
        │                          ▼
        │                    Phase F (Ph3.5, P1) — needs Ph1/Ph3's real fixture
        │                          │               shapes
        │                          ▼
        ├─→ Phase G (XC-Rerun, P2) — extends Ph1/Ph3, can start once Phase C/E
        │                            checkpoints pass
        ├─→ Phase H (XC-Creds, P2) — extends Ph1, can start once Phase C
        │                            checkpoint passes
        └─→ Phase I (Ph4, P3) — placeholder only, not started this pass
  └─→ Acceptance Phase — after Phases C-H are all green; T031 (Phase 2's real
                          verdict) gates T032/T033's real default-method choice
```

**Suggested MVP scope**: Phase A + Phase B + Phase C (Ph1) + Phase D (Ph2) + Phase E (Ph3) — a
working download → method-selection → transform pipeline, unit-tested, ready for its first real
Acceptance-phase run. Phase F (Ph3.5) and the two cross-cutting phases layer on top before any real
prod data is trusted; Phase I (Ph4/Load) is explicitly out of this pass's scope.

## Parallel Execution Examples

- Phase D: T011 (Method A) and T012 (Method B) are independent files, no ordering dependency.
- Phase G/H: T022/T023 (re-run tests) and T026 (creds test) touch different existing test files and
  can be written in either order relative to each other.
- Phase A: T003 (gitignore check) and T004 (conftest fixtures) have no ordering dependency on each
  other.
