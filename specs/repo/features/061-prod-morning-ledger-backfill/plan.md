# Implementation Plan: Prod Morning Ledger Backfill

**Branch**: `feature/061-prod-morning-ledger-backfill` | **Date**: 2026-08-25 (round 4 revision) | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/in-progress/061-prod-morning-ledger-backfill/spec.md`

**Note on process**: this repo's real branch-naming convention (`feature/###-description`) diverges
from the vanilla SpecKit `setup-plan.sh`'s `^[0-9]{3}-` branch-name check, so this plan is authored
manually against the vanilla template's structure, following the idiom established by
`specs/done/v0.5.1/056-receipts-without-invoice/plan.md`.

**Revision note (2026-08-25, round 4)**: adds **Phase 3.5 (Validate)** — a required review gate
between Transform and Load that earlier rounds of this plan didn't cover. Also renames the
pipeline's stages from "Pass 1/2/3" to "Phase 1 → 2 → 3 → 3.5 → 4," matching `spec.md`/
`user-stories.md`'s current numbering (this is one operator running one linear pipeline, not
several independent user personas — see `user-stories.md`'s own note).

---

**Compliance**: This plan complies with CONSTITUTION.md §I (no env vars — all real credentials
come exclusively from dedicated, gitignored `*.local.*` files, loaded via plain file I/O, no
`os.getenv`), §II (Israel local time — `--since` is interpreted Israel-local), §III (no
monkey-patching — `LedgerEventManager` is reused via ordinary construction and its existing public
methods, never patched), §V (real systems, no mocks — Phase 1/Phase 4's acceptance tests run
against the real prod Morning account, Phase 2's experiment against the real Morning sandbox, per
METHODOLOGY.md's "TDD redefinition" for `billed`/`expensive` acceptance tests), and the "no
unverified third-party assumptions" discipline (every claim in `research.md` is grounded in a real,
line-numbered read of the actual source).

## Summary

A new, standalone app (`apps/prod-ledger-backfill/`) implementing a five-phase, operator-run
pipeline: **Phase 1 (`download.py`)** constructs `MorningClient` directly (imported from
`apps/morning-mcp-app`'s package) and downloads every real prod Morning accounting document from an
operator-supplied start date forward into local raw files — no live service, no AI. **Phase 2
(`select_method.py`)**, a one-time sandbox-only experiment, decides whether Phase 3 uses a
deterministic or an AI-mediated transform method. **Phase 3 (`transform.py`)** reads Phase 1's
local files and produces `LedgerEvent` records using the selected method. **Phase 3.5
(`validate.py`)** reconciles Phase 3's output against Phase 1's input, surfaces every anomaly, and
requires an explicit human sign-off before Phase 4 may run for that window. **Phase 4 (`load.py`)**,
designed last, writes the validated local output into prod's real, live data store. All five
phases (plus the two cross-cutting requirements — re-run safety and credential security) are this
feature's own scope.

## Technical Context

**Language/Version**: Python 3.11 (matches the rest of this repo).
**Primary Dependencies**: `apps/morning-mcp-app`'s own `denidin_mcp_morning` package (imported
directly — `MorningClient`, `MorningAuth` — as a local path dependency in this new app's own
`requirements.txt`, per `research.md` R9). `openai`, only if Method B is selected for Phase 3
(R7) — otherwise no OpenAI dependency at all for the real pipeline. `apps/denidin-app`'s
`managers/ledger_event_manager.py` — reused for Phase 3's output persistence/dedup, and as the
source of Phase 3.5's anomaly data, as pure local library code (importable directly; no cross-app
runtime dependency — see `research.md` R5).
**Storage**: Local directories per backfill effort — Phase 1's raw-document output directory,
Phase 3's `LedgerEvent` output directory (via `LedgerEventManager(storage_dir=...)`, same file
format `{data_root}/events/*.json` already uses), and Phase 3.5's per-window validation report
file. No database, no ChromaDB.
**Testing**: A new, small `apps/prod-ledger-backfill/tests/` suite (`unit/`, and a `billed/`-tier
acceptance pass) following the same `pytest` conventions as the other two apps. Per METHODOLOGY §VI:
unit tests keep RED→GREEN discipline throughout; the real-prod/real-sandbox acceptance passes are
described here in user-experience terms and written/run together, once, at the end.
**Target Platform**: Local host Python process on the operator's own machine — not Docker. A
deliberate, narrow exception to "containers-only" (root `CLAUDE.md`'s Environments section),
justified because this is a one-shot operator tool, never a long-running/unattended service.
**Scale/Scope**: One new standalone app, five (four now, Phase 4 stubbed) small scripts, zero
changes to `denidin-app` or `morning-mcp-app`'s own existing source — both are used exactly as they
already exist (`morning-mcp-app`'s package imported as a library; `denidin-app`'s
`LedgerEventManager` imported as a library).

## Constitution Check

- ✅ No env vars (§I) — `backfill_prod_creds.local.json` (plain file I/O), matches existing
  `*.local.*` convention.
- ✅ Israel local time everywhere (§II) — `--since` parsed as Israel-local throughout.
- ✅ No monkey-patching (§III) — `MorningClient`, `LedgerEventManager` constructed and called via
  their existing public surface only.
- ✅ `pathlib.Path`, not string concatenation (matches existing codebase convention throughout).
- N/A Feature flags — standalone scripts, not a `denidin.py` runtime code path; nothing about
  either existing app's live behavior changes.
- ✅ Real systems, no mocks (§V) — Phase 1/Phase 4's real runs hit the real prod Morning account;
  Phase 2's experiment hits the real Morning sandbox; no external service is ever mocked.
- ✅ Retry policy — `MorningClient` already wires urllib3 `Retry` internally (`research.md` R1); no
  new retry logic needed in this feature's own code.
- ✅ User-facing errors — N/A in the WhatsApp sense (REQ-BACKFILL-008: no message ever sent);
  console-facing errors instead follow "what happened, what to do next" framing.

## Project Structure

### Documentation (this feature)

```
specs/in-progress/061-prod-morning-ledger-backfill/
├── spec.md
├── user-stories.md
├── checklists/requirements.md
├── plan.md                              # this file
├── research.md                          # Phase 0 output
├── data-model.md                        # Phase 1 (design) output
├── contracts/
│   ├── backfill-creds-file.md           # Phase 1 (design) output
│   └── cli-contract.md                  # Phase 1 (design) output
└── quickstart.md                        # Phase 1 (design) output
```

(Note: "Phase 0"/"Phase 1" above are SpecKit's own generic planning-phase names, unrelated to this
feature's own Phase 1-4 pipeline numbering — same overlap noted in `research.md`.)

### Source Code (repository root)

```
apps/prod-ledger-backfill/               # NEW standalone app
├── requirements.txt                     # depends on apps/morning-mcp-app (local path) + apps/
│                                         #   denidin-app's ledger_event_manager module (mechanism
│                                         #   for pulling in a single module vs. the whole app's
│                                         #   src/ tree decided at implementation time)
├── download.py                          # Phase 1 entry point (contracts/cli-contract.md)
├── select_method.py                     # Phase 2's one-time sandbox experiment, not part of the
│                                         #   real per-run pipeline
├── method_a.py                          # Method A: deterministic field mapping (research.md R7) —
│                                         #   imported by select_method.py AND transform.py, not a
│                                         #   standalone CLI entry point
├── method_b.py                          # Method B: AI-mediated mapping (research.md R7) — same
│                                         #   import relationship as method_a.py
├── transform.py                         # Phase 3 entry point — imports method_a.py OR method_b.py,
│                                         #   whichever select_method.py's verdict selected
│                                         #   (contracts/cli-contract.md)
├── validate.py                          # Phase 3.5 entry point — reconciliation + anomaly report +
│                                         #   sign-off gate (REQ-BACKFILL-010)
├── load.py                              # Phase 4 entry point — STUB/TBD, designed once Phases 1-3.5
│                                         #   are proven correct (research.md R10)
├── config/
│   └── backfill_prod_creds.local.json   # NEW, gitignored, created by hand
│       (backfill-creds-file.md)
└── tests/
    ├── unit/
    │   ├── test_download.py             # CLI arg parsing, creds-file validation, pagination logic
    │   ├── test_select_method.py        #   against fixture Morning JSON (no live network call)
    │   ├── test_transform.py            #   diff-helper logic against synthetic fixture pairs
    │   └── test_validate.py             #   count reconciliation + anomaly-surfacing logic against
    │                                     #   fixture raw/ledger directory pairs
    └── billed/
        └── test_backfill_acceptance.py  # the real-prod / real-sandbox acceptance pass, written +
                                          #   run together at the end per METHODOLOGY §VI

apps/denidin-app/                        # UNCHANGED — this feature does not modify denidin-app's
                                          #   own source; LedgerEventManager is imported as-is
apps/morning-mcp-app/                    # UNCHANGED — MorningClient/MorningAuth imported as-is
```

## Phased Execution

(Task-breakdown phases below — distinct from this feature's own Phase 1-4 pipeline numbering,
though they're deliberately built in the same order.)

### Phase 0: Research (complete — see `research.md`)

Resolved: `MorningClient`/`MorningAuth` real contracts (R1/R2), why `tools.list_invoices` is unsafe
for Phase 1 (R3/R4), `LedgerEventManager` reuse validity for both Phase 3's persistence and Phase
3.5's anomaly data (R5), the corrected credentials shape (R6), the Phase 2 method-selection
experiment design (R7), cross-run dedup (R8), the new app's location (R9), and Phase 4's
deliberately-open status (R10).

### Phase 1 (design): Design (complete — see `data-model.md`, `contracts/`, `quickstart.md`)

No new persisted domain schema (`LedgerEvent` reused unchanged). Two contracts fix the exact
shapes: the prod creds file, and the five scripts' CLI surface (including the new `validate.py`).

### Task Group 1 — Phase 1: An operator downloads real prod Morning documents to local files (P1)

- **Test** (unit, RED first): `test_download.py` — CLI rejects a missing `--since` with a clear
  error and non-zero exit (no default ever accepted, REQ-BACKFILL-001); creds-file validation
  (missing file / malformed JSON / missing field) fails before any network call; pagination logic
  against a fixture multi-page Morning response correctly follows `page`/`pages`/`total` with no
  artificial cap.
- **Implement** (GREEN): `download.py` — CLI parsing, creds-file loading, `MorningClient`
  construction, the uncapped pagination loop (`research.md` R3/R4), one raw file per document
  written to `--output-dir`.
- **Verify**: unit suite green; a small, real-prod dry run (own approval gate — REQ-BACKFILL-007)
  confirms the console summary looks correct for a known small window before any larger run.
- **TDD scenario (described here, coded/run only in the Acceptance phase)**: an operator runs
  `download.py` with a real start date against the real prod Morning account; every accounting
  document from that date forward is written to a local file with no document silently dropped for
  exceeding a conversational fetch/token cap; no WhatsApp message is sent; no `LedgerEvent` file is
  written yet.

### Task Group 2 — Phase 2: A sandbox experiment decides Phase 3's transform method (P1)

- **Test** (unit, RED first): `test_select_method.py` — the field-by-field diff helper is unit-
  tested against synthetic fixture `LedgerEvent` pairs (identical → passes with an "IDENTICAL"
  verdict; one field differing → fails with a clear description of exactly which field(s) differ,
  excluding `event_id`).
- **Implement** (GREEN): `method_a.py`/`method_b.py` (the two candidate mapping implementations, as
  their own dedicated, importable modules — not standalone CLI scripts) plus `select_method.py`,
  which runs both against a directory of already-downloaded sandbox files, diffs, writes the
  report, prints the verdict.
- **Verify**: unit suite green for the diff helper.
- **TDD scenario (described here, coded/run only in the Acceptance phase)**: for ~20 known sandbox
  documents (downloaded via `download.py` pointed at sandbox creds), `select_method.py` produces a
  clear field-level verdict; `transform.py` (Task Group 3) is then built using whichever method it
  selected.

### Task Group 3 — Phase 3: Downloaded files are transformed into ledger events locally (P1)

- **Test** (unit, RED first): `test_transform.py` — given a directory of fixture raw Morning
  document files and the method Phase 2 selected, `transform.py`'s mapping produces correctly-
  shaped `LedgerEvent` dicts (`schema_version=2`, all `accounting_document_*` fields populated)
  with no live network call made during the test.
- **Implement** (GREEN): `transform.py` — reads `--input-dir`, applies the selected method, persists
  via `LedgerEventManager.add_ledger_event`/`add_ledger_events_from_call` pointed at `--output-dir`,
  retaining every anomaly outcome for `validate.py` to read.
- **Verify**: unit suite green; run against a real Phase-1 output directory (from Task Group 1's
  dry run) to confirm end-to-end shape before the Acceptance phase.
- **TDD scenario (described here, coded/run only in the Acceptance phase)**: given a directory of
  real Phase-1-downloaded documents, `transform.py` produces a correctly-populated `LedgerEvent`
  file for every one, with zero live Morning API calls during this phase and zero WhatsApp messages
  sent.

### Task Group 3.5 — Phase 3.5: Validate Phase 3's output before it is trusted for load (P1) — NEW

- **Test** (unit, RED first): `test_validate.py` — given a fixture Phase-1 directory and a fixture
  Phase-3 output directory with a known, deliberate mismatch (a raw document with no corresponding
  `LedgerEvent`, and a corresponding pair with a deliberately wrong field), the count reconciliation
  flags the missing document and the field-level sample check flags the mismatched field; given a
  fully-matching fixture pair, both checks report clean.
- **Implement** (GREEN): `validate.py` — reads `--raw-dir`/`--ledger-dir` (no live Morning API
  call), computes the count reconciliation, collects Phase 3's retained anomaly outcomes, samples
  documents for field-level comparison, writes the report with an unsigned sign-off field.
- **Verify**: unit suite green; run against Task Group 1/3's real dry-run output to confirm the
  report reads sensibly for a human before the Acceptance phase.
- **TDD scenario (described here, coded/run only in the Acceptance phase)**: given real Phase-1 and
  Phase-3 output for a window, `validate.py` produces a report with a document-count
  reconciliation, every surfaced anomaly, and a sampled field-level comparison — and a human's
  explicit sign-off on that report is required before that window's `load.py` run is attempted.

### Task Group 4 — Cross-cutting: Re-running any phase never creates duplicate output (P2)

- **Test** (unit, RED first): running `download.py` twice against the same fixture window
  overwrites the same local filename rather than creating a second copy; constructing two separate
  `LedgerEventManager` instances against the same `storage_dir` (simulating two `transform.py`
  invocations) confirms the second instance's `add_ledger_event` call for an already-present
  document returns the existing dedup outcome, not a new file.
- **Implement**: `download.py`'s filename-keyed overwrite behavior (new, small); `transform.py`'s
  half needs no new code beyond Task Group 3 — it's satisfied entirely by `LedgerEventManager`'s
  existing guard, given a stable `--output-dir` (`research.md` R8) — documented as a usage
  convention in `quickstart.md`, not a new mechanism.
- **Verify**: both unit tests above pass.
- **TDD scenario (described here, coded/run only in the Acceptance phase)**: running `download.py`
  or `transform.py` twice over the same or overlapping window/input against real data produces zero
  duplicate output the second time.

### Task Group 5 — Cross-cutting: Real prod credentials never land in git (P2)

- **Test** (unit, RED first): missing `backfill_prod_creds.local.json` → `download.py` exits
  non-zero with a clear error before any network call (assert no `MorningClient` construction is
  reached — testable via dependency injection, not mocking internal logic); malformed JSON → same;
  missing any of the four required fields → same.
- **Implement** (GREEN): the precondition-checking sequence in `download.py`
  (`contracts/cli-contract.md`'s "Preconditions checked" list).
- **Verify**: unit suite green; manual confirmation the new file's path matches the existing
  `.gitignore`'s `*.local.*` glob (or a new entry is added if it doesn't, checked at implementation
  time).
- **TDD scenario (described here, coded/run only in the Acceptance phase)**: after a real
  `download.py` run, `git status`/`git diff` show no unexpected tracked-file changes and no prod
  credential appears anywhere in a git-tracked file.

### Task Group 6 — Phase 4: Validated local output is loaded into prod's real data store (P3)

Deliberately implemented **last**, after Phases 1-3.5 are proven correct via the Acceptance phase
below. Its own research (mechanism for writing into prod's real data store, given today's
read-only sshfs access — `research.md` R10), test plan, and implementation are designed as their
own short follow-up pass at that time — not prescribed here. Still fully in this feature's scope
(REQ-BACKFILL-009); `speckit.tasks` will carry a placeholder task for "design + implement Phase 4"
rather than a fleshed-out task breakdown, since the concrete design doesn't exist yet. Whatever the
mechanism, `load.py` MUST check for a signed-off Phase 3.5 report for the exact target window
before writing anything (REQ-BACKFILL-010).

### Acceptance Phase (billed/expensive, written + run together, once, at the end — METHODOLOGY §VI)

Per the TDD redefinition, the TDD scenarios described above (Task Groups 1 through 5) are written
as real, end-to-end tests only now, against real systems:

- A `billed`-tier test for Phase 1: run `download.py` against real prod data with a narrow, small
  real start-date window; assert raw document files appear locally with the expected shape.
- A `billed`-tier test for Phase 2: the ~20-sandbox-document experiment, run for real, producing a
  real verdict.
- A `billed`-tier test for Phase 3: run `transform.py` against Phase 1's real output; assert
  correctly-shaped `LedgerEvent` files appear.
- A test for Phase 3.5: run `validate.py` against real Phase 1/Phase 3 output; assert the report
  correctly reconciles counts and surfaces zero unexplained anomalies for a clean real window.
- A `billed`-tier test for the re-run-safety cross-cutting requirement: run `download.py` and
  `transform.py` each twice over the same real window/input; assert the second run's newly-captured
  count is zero.
- A test for the credential-security cross-cutting requirement: after a real `download.py` run,
  assert no prod credential in any git-tracked file.

Every real-prod-touching run among these, per root `CLAUDE.md`, requires its own fresh, explicit
human approval before running — this plan does not pre-approve any of them. Phase 2's sandbox
experiment is the one exception needing no such gate (never touches prod).

### Close-out

Once the Acceptance phase (Phases 1-3.5 and both cross-cutting requirements) is green and the user
has reviewed real Phase-1/Phase-3 output and at least one Phase-3.5 report for correctness: report
back, then (separately, on its own go-ahead) design and implement Task Group 6 (Phase 4) as this
feature's final phase before `speckit.tasks`'s own close-out / `speckit.implement`'s haleluya flow.

## Complexity Tracking

No constitution deviations to track beyond the one already-justified structural exception (`Target
Platform`: local host process, not Docker — one-shot operator tool, never unattended).
