# User Stories: Prod Morning Ledger Backfill

**Feature**: 061-prod-morning-ledger-backfill
**Format**: Given-When-Then (Gherkin/BDD), per METHODOLOGY.md §I — MANDATORY, blocks spec approval
until present.

**Revised 2026-08-25 (round 2)**: this feature is one operator running one pipeline, not several
personas each getting independent value — so "user story" is a loose fit. Framed instead as
**Phases** of that one pipeline, each still carrying full Given-When-Then acceptance criteria (the
METHODOLOGY format itself is unchanged; only the framing/numbering is). **Phase 3.5 (Validate) is
new this round** — a required review gate between Transform and Load that nothing in the original
draft covered: nothing previously confirmed Phase 3's output was actually correct before Phase 4
would have written it into prod's real, live data store.

- **Phase 1 — Download**: a new standalone script imports `MorningClient` directly (real prod
  Green Invoice credentials, no live `morning-mcp-app-prod` server, no AI) and downloads every
  real prod accounting document from an operator-supplied start date forward, writing each as a
  raw local file (Morning's own response shape, unprocessed).
- **Phase 2 — Method Selection Experiment**: a one-time, sandbox-only comparison decides which of
  two candidate methods Phase 3 uses.
- **Phase 3 — Transform**: reads Phase 1's local raw files (never re-calling the live Morning API)
  and produces `LedgerEvent` records locally, via whichever method Phase 2 selected.
- **Phase 3.5 — Validate**: reviews Phase 3's output for correctness — count reconciliation,
  anomaly surfacing, sampled field-level spot-checks — and requires an explicit human sign-off
  before Phase 4 is allowed to run.
- **Phase 4 — Load**: writes Phase 3's validated `LedgerEvent` files into prod's real, live data
  store. In scope for this feature; implemented last, after Phases 1-3.5 are solid.

Two cross-cutting requirements apply across every phase above rather than being their own step in
the pipeline: **re-run safety** (no phase may duplicate output on a second run) and **credential
security** (real prod credentials never land in git). Both get their own Given-When-Then criteria
below, same as a phase would.

None of this adds a new webhook/router entry point or any conversational flow — this feature is an
**operator-run set of scripts**, not something a WhatsApp user ever triggers.

---

## Phase 1 — An operator downloads real prod Morning documents to local files (Priority: P1)

The foundation of the whole pipeline: given a start date, pull every real prod accounting document
from that date forward straight from Morning's API into local files — no intermediate live
service, no AI involved in this step at all.

**Why this priority**: Everything downstream (Phase 2's experiment inputs, Phase 3's transform,
Phase 3.5's validation, Phase 4's eventual load) operates on what this phase produces. Nothing else
can be built or validated without it.

**Independent Test**: Run the download script against the real prod Morning account with a known
start date covering a small number of real historical documents. Verify one local file per
document appears, containing Morning's full raw response for that document (matching what a
direct `GET /documents/{id}` call against the real API would return) — not a truncated or
token-budget-limited subset.

**Router/Integration Requirement**: The script MUST construct a `MorningClient` directly (real
`api_key_id`/`api_key_secret`/`auth_url`/`base_url` from the dedicated creds file) and call its
raw methods (`list_invoices`/`get_invoice`) itself — NOT `apps/morning-mcp-app`'s higher-level
`tools.list_invoices` wrapper, whose 100-item fetch cap and token-budget truncation exist
specifically for a bounded conversational reply and would silently refuse or truncate a real
bulk-historical download (see `research.md`). NOT the live `morning-mcp-app-prod` MCP server, NOT
`AIHandler`, NOT any OpenAI call.

**Acceptance Scenarios**:

1. **Given** an operator supplies a start date on the command line, **When** the download script
   runs against the real prod Morning account, **Then** every accounting document created on or
   after that date is written to a local file in Morning's native response shape, with no
   document silently dropped for exceeding a conversational fetch/token cap.
2. **Given** the same run, **When** it completes, **Then** no WhatsApp message is sent to anyone
   and no local `LedgerEvent` file is written yet (that's Phase 3's job, not this one's).

---

## Phase 2 — A sandbox experiment decides Phase 3's transform method (Priority: P1)

Before building Phase 3's real transform logic, a side-by-side comparison against ~20 known
**sandbox** documents (safe — reuses this repo's existing Morning sandbox credentials, never
touches prod for this experiment) decides which of two candidate methods Phase 3 actually uses.

**Why this priority**: Ships before Phase 3's real implementation is finalized — which method
wins determines what gets built.

**Independent Test**: Download ~20 known documents from the Morning **sandbox** (via Phase 1's own
download script, pointed at sandbox credentials). Run both candidate transform methods against
those local files:
- **Method A (deterministic)**: plain code maps Morning's raw JSON fields directly to
  `LedgerEvent` fields — no AI call.
- **Method B (AI-mediated)**: an OpenAI call (no live MCP tools attached — the document JSON is
  already local, so no tool call is needed) using a prompt adapted from Feature 025's
  `_build_reconciliation_prompt` shape, asking the model to emit the same `capture_ledger_event`
  structure from the pre-fetched JSON.

Diff the two methods' resulting `LedgerEvent` JSON field-by-field (excluding capture-timestamp-
derived ids). If Method A's output exactly matches Method B's, Method A is adopted for the real
Phase 3 implementation (simpler, cheaper, no OpenAI dependency). If they differ, Method B is
adopted.

**Router/Integration Requirement**: Both candidate methods MUST produce output in the exact same
`LedgerEvent` shape (`schema_version=2`, `accounting_document_*` fields) so the diff is meaningful
— this is a genuine apples-to-apples comparison, not two different output formats compared loosely.

**Acceptance Scenarios**:

1. **Given** ~20 known sandbox documents, **When** both candidate methods run against the same
   locally-downloaded files, **Then** a field-by-field diff report is produced naming exactly
   which fields (if any) differ between the two methods' output.
2. **Given** this experiment's result, **When** Phase 3's real implementation is built, **Then**
   it uses whichever method the experiment selected — not a guess, not both methods running
   forever in parallel.

---

## Phase 3 — Downloaded files are transformed into ledger events locally (Priority: P1)

Given the files Phase 1 downloaded, and the method Phase 2 selected, produce correctly populated
`LedgerEvent` files locally.

**Why this priority**: The actual payoff of the feature — Phase 1 alone produces raw data nobody
can use as a ledger; this phase is what makes it usable.

**Independent Test**: Run the transform script against a directory of previously-downloaded raw
documents (from a real prod Phase-1 run). Verify a correctly-populated `LedgerEvent` file is
written locally for each one, matching the existing `source_type="חשבונית"` schema
(`schema_version=2`, `event_subtype` = the real Morning document-type label, all
`accounting_document_*` fields populated) — with no live call back to the Morning API at any
point during this phase.

**Router/Integration Requirement**: Persistence MUST go through `LedgerEventManager`'s existing
`add_ledger_event`/dedup machinery (pure local library code — pointed at a local `storage_dir`,
not a running service, so reusing it does not conflict with "don't reuse anything live") — never a
hand-rolled, parallel persistence mechanism.

**Acceptance Scenarios**:

1. **Given** a directory of Phase-1-downloaded raw documents, **When** the transform script runs
   using the method Phase 2 selected, **Then** every document produces a correctly-populated
   `LedgerEvent` file, written locally.
2. **Given** the same run, **When** it completes, **Then** no live call to the real Morning API
   was made (this phase works entirely off local files) and no WhatsApp message was sent.

---

## Phase 3.5 — Validate Phase 3's output before it is trusted for load (Priority: P1) — NEW

Between Transform and Load: nothing before this phase actually confirms Phase 3's output is
correct. A validation script reconciles Phase 3's output against Phase 1's input and surfaces
anything a human should look at, and Phase 4 is not allowed to run until a human has explicitly
signed off on that specific validation report.

**Why this priority**: Same tier as the phases it sits between — skipping it would mean the first
real check on transform correctness happens only after data has already landed in prod's live
store (Phase 4), which is exactly backwards for real financial data. This is the gate that makes
Phase 4 safe to build/run at all.

**Independent Test**: Run the validation script against a real Phase-1 output directory and its
corresponding real Phase-3 output directory. Verify it reports: (a) a document-count reconciliation
(every raw document from Phase 1 accounted for in Phase 3's output, or explicitly listed as an
intentional skip with a reason), (b) every anomaly `LedgerEventManager`'s own tri-state guard
flagged during Phase 3, surfaced rather than silently absorbed, and (c) a field-level comparison
for a sample of documents between the raw source and the transformed `LedgerEvent`, to catch a
systematic mapping bug the count check alone wouldn't reveal.

**Router/Integration Requirement**: The validation script MUST NOT re-call the real Morning API
(same "no live API call" discipline as Phase 3 — it only reads Phase 1's and Phase 3's already-local
output) and MUST NOT itself write or modify any `LedgerEvent` file — it is read-only, a report
generator, never a second write path.

**Acceptance Scenarios**:

1. **Given** Phase 3 has produced `LedgerEvent` files for a given window, **When** the validation
   script runs against that window's Phase 1 and Phase 3 output, **Then** it produces a report
   showing the document-count reconciliation, every surfaced anomaly, and a sampled field-level
   comparison — with no live Morning API call made during this phase.
2. **Given** a validation report exists, **When** an operator reviews it, **Then** Phase 4 does
   not run for that window until the operator has explicitly signed off on that specific report —
   sign-off on one window's or run's report never carries over to a different window or a re-run.
3. **Given** the document-count reconciliation shows a mismatch, or a field-level sample comparison
   shows a discrepancy, **When** the report is generated, **Then** it is flagged clearly as
   requiring investigation rather than silently passing — the default posture is "needs a human
   look," not "assume correct."

---

## Phase 4 — Validated local output is loaded into prod's real data store (Priority: P3)

Once Phase 3.5 has validated Phase 3's output and a human has signed off, this feature's final
phase writes the `LedgerEvent` files into prod's actual, live data store (the Windows box) so the
live reconciliation scheduler (`accounting_ledger_update_freq`) can be safely turned on with no
historical gap.

**Why this priority**: Deliberately last — the exact mechanism (given the Windows box's data is
only reachable read-only from the Mac today) is designed once Phases 1-3.5 are proven correct, not
guessed at up front. Still this feature's own scope, not a separate future feature.

**Independent Test**: TBD — the concrete mechanism (temporary write access, running on the Windows
box directly, or another approach) is designed as part of implementing this phase, not prescribed
here.

**Router/Integration Requirement**: TBD at implementation time; whatever mechanism is chosen must
never bypass the "every prod-touching action needs fresh, explicit approval, every time" rule,
must never proceed without Phase 3.5's sign-off for that exact window, and must never write
anything to prod's live data store other than the already-validated local `LedgerEvent` files
Phase 3 produced (no re-deriving or re-fetching at load time).

**Acceptance Scenarios**:

1. **Given** validated local `LedgerEvent` files from Phases 1-3.5, and an explicit sign-off on
   that window's Phase 3.5 report, **When** Phase 4 runs, **Then** those exact files (or their
   exact content) appear in prod's real, live `{data_root}/events/` directory on the Windows box,
   with no duplication of anything already there.
2. **Given** Phase 4 has completed for a given window, **When**
   `accounting_ledger_update_freq` is later turned on in prod (a separate, later, human-driven
   config/deploy decision — out of this feature's scope), **Then** the periodic scheduler picks up
   cleanly with no historical gap and no duplication against what Phase 4 already landed.

---

## Cross-Cutting — Re-running any phase never creates duplicate output (Priority: P2)

A phase may be interrupted, or an operator may need to re-run it over an overlapping window — it
must never double-download or double-capture.

**Why this priority**: Without this, a second/overlapping run is actively harmful (duplicate real
prod financial records, or wasted duplicate real-API download traffic) rather than merely
redundant.

**Independent Test**: Run Phase 1 twice over the same (or overlapping) date range — verify the
second run does not re-fetch documents already downloaded (or, at minimum, overwrites them
byte-identically rather than creating a second, differently-named copy). Separately, run Phase 3
twice over the same input directory — verify the second run creates zero new `LedgerEvent` files
for documents already transformed.

**Router/Integration Requirement**: Phase 3's re-run safety relies on `LedgerEventManager`'s
existing tri-state duplicate/anomaly/new guard, keyed on `accounting_document_display_number` +
creation timestamp — the same mechanism the live periodic sweep already depends on.

**Acceptance Scenarios**:

1. **Given** a document was already downloaded by an earlier Phase-1 run, **When** a later
   Phase-1 run's window includes that same document again, **Then** the local raw file for it is
   not duplicated under a second name.
2. **Given** a document was already transformed by an earlier Phase-3 run, **When** a later
   Phase-3 run processes the same input again, **Then** no duplicate `LedgerEvent` file is
   created for it.

---

## Cross-Cutting — Real prod credentials never land in git (Priority: P2)

Phase 1 talks to prod's real Green Invoice account using real, raw API credentials — a live
production concern requiring the same operational discipline as any other prod-touching action in
this codebase.

**Why this priority**: Not the core capability, but a hard operational guardrail — a leaked
credential causes real harm even if the download/transform logic itself is correct.

**Independent Test**: Inspect the repository after a real Phase-1 run: no prod Morning credential
appears anywhere in a git-tracked file, and `git status`/`git diff` show no unexpected
tracked-file changes.

**Router/Integration Requirement**: Credential loading MUST follow this project's existing "config
is code, secrets are not" convention — a new, dedicated, gitignored file matching the `*.local.*`
convention, never hardcoded, never an environment variable.

**Acceptance Scenarios**:

1. **Given** a real Phase-1 run completes, **When** the repository is inspected afterward, **Then**
   no prod credential is present in any git-tracked file.
2. **Given** the credentials file is missing or malformed, **When** Phase 1 starts, **Then** it
   fails with a clear error before making any real Morning API call — never falls back to a
   different, unintended credential source.
