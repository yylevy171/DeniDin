# Feature Specification: Prod Morning Ledger Backfill

**Feature Branch**: `feature/061-prod-morning-ledger-backfill`
**Created**: 2026-08-24
**Status**: **Closed 2026-08-27 (dev goal achieved, tooling completion deferred)** — Method A vs
Method B experiment run for real (T031), Method B rejected (real AI-transcription data corruption
+ a truncation crash), Method A adopted. A real, full dev-environment ledger backfill (Jul 1 – Aug
27 2026, ~4,067 documents, real dev/sandbox Morning data) was completed and verified: dev's ledger
now has complete coverage, the live `accounting_reconciliation_service` watermark correctly
resumes from the latest backfilled document, and the reconciliation sweep runs successfully
against real data going forward. Remaining `tasks.md` items (Phase 4 load-mechanism design,
XC-Rerun/XC-Creds regression tests, and the full acceptance-test suite T030/T032-T035) were
deliberately NOT completed — the real prod backfill run itself is still pending and was
explicitly deferred ("we will do prod another day," user, 2026-08-27) — see follow-up spec
`specs/backlog/062-prod-morning-ledger-backfill-completion` for that remaining scope.

Previously: Clarified (round 4, 2026-08-25) — five-phase pipeline (Download → Method Selection →
Transform → **Validate** → Load), plus two cross-cutting requirements; ready for `speckit.plan`
(revised).
**Input**: User description: a one-shot, operator-run backfill that populates prod's ledger with
Morning accounting documents created before Feature 025's periodic reconciliation scheduler is
ever turned on in prod (`accounting_ledger_update_freq` is deliberately `0` there today, pending
exactly this backfill — see Feature 025's spec, Status line).

---

**IMPORTANT**: This spec complies with:
- **CONSTITUTION.md** (§I-III, §V): no env vars, no monkey-patching, real prod credentials never
  committed to git, integration/acceptance verification against real systems (real prod Morning
  account, real Morning sandbox for the Phase 2 method-selection experiment), not mocks.
- **METHODOLOGY.md** (§I, II, VIII, IX, X): spec-first development, mandatory user stories,
  Terminology Glossary, Technology Choices, Requirement IDs (new series, `REQ-BACKFILL-*`, since
  this is an operational/tooling capability rather than a Morning invoicing-logic change like the
  existing `REQ-INV-*` series).
- The root `CLAUDE.md` banners on **environment starts** and **version/release actions**: running
  this pipeline against real prod data is its own gated action requiring fresh, explicit approval
  every time, independent of approval to build the feature itself.

**Required Files**: `user-stories.md` (present) ✅ · `spec.md` (this file) ✅ · `plan.md` (present,
being revised) · `tasks.md` (pending).

---

## Phases Reference

Complete Given-When-Then acceptance criteria live in **`user-stories.md`**. This is one operator
running one pipeline, so it's framed as **Phases**, not independent user personas — see
`user-stories.md`'s own note. Summary:

| # | Title | Priority |
|---|---|---|
| Phase 1 | An operator downloads real prod Morning documents to local files | P1 |
| Phase 2 | A sandbox experiment decides Phase 3's transform method | P1 |
| Phase 3 | Downloaded files are transformed into ledger events locally | P1 |
| Phase 3.5 | Validate Phase 3's output before it is trusted for load — **new, round 4** | P1 |
| Phase 4 | Validated local output is loaded into prod's real data store | P3 |
| Cross-cutting | Re-running any phase never creates duplicate output | P2 |
| Cross-cutting | Real prod credentials never land in git | P2 |

## Terminology Glossary

- **Backfill**: this whole feature — a five-phase, operator-run set of scripts (not a scheduled
  job, not a conversational feature) that captures historical Morning accounting documents,
  created before the periodic reconciliation scheduler's first live tick in prod, into prod's real
  ledger, given an explicit operator-supplied start date.
- **Phase 1 (Download)**: constructs `MorningClient` directly (real prod Green Invoice credentials)
  and downloads every matching real prod document into local files, in Morning's native response
  shape — no live MCP server, no AI.
- **Phase 2 (Method Selection Experiment)**: a one-time, sandbox-only comparison between a
  deterministic (Method A) and an AI-mediated (Method B) implementation of Phase 3's transform
  logic, deciding which one is actually built out for the real prod run. Never touches prod.
- **Phase 3 (Transform)**: reads Phase 1's local files (no live Morning API call) and produces
  `LedgerEvent` records locally, via whichever method Phase 2 selected.
- **Phase 3.5 (Validate)**: a required review gate between Transform and Load — reconciles Phase
  3's output against Phase 1's input (document counts, surfaced anomalies, sampled field-level
  checks) and requires an explicit human sign-off, per window, before Phase 4 may run for that
  window.
- **Phase 4 (Load)**: writes Phase 3's validated `LedgerEvent` files into prod's real, live data
  store, only after Phase 3.5's sign-off for that window. This feature's own scope, implemented
  last.
- **Prod ledger**: the real `{data_root}/events/*.json` `LedgerEvent` files for the `prod`
  environment (Windows always-on box, Feature 035) — currently populated only by conversational
  capture (Feature 024) and manual entry, never by the Feature 025 reconciliation mechanism, since
  `accounting_ledger_update_freq` is `0` in prod today.

## Problem Statement

Feature 025 built `services/accounting_reconciliation_service.py`, a periodic sweep that captures
Morning-sourced accounting documents into the ledger going forward. Its spec explicitly deferred
turning this on in prod: *"`0` in `prod` (deliberately, until a full backfill from a
human-specified start date is done — nothing populates the ledger for documents Morning already
held before the scheduler's first tick, so turning this on in `prod` without backfilling first
would leave a silent historical gap)."*

Feature 061 is that backfill. Unlike Feature 025's live sweep — which is inseparable from a
running `denidin-app`/`morning-mcp-app-<env>` pair and OpenAI-mediated MCP tool calls — this
feature deliberately does **not** reuse any live service for its core capture step. It talks to
Morning's real API directly (`MorningClient`, imported from `apps/morning-mcp-app`'s own package)
and only reaches for an AI call at all if a sandbox experiment (Phase 2) proves a plain
deterministic mapping isn't sufficient. And because Phase 4 writes into prod's real, live data
store, Phase 3.5 exists specifically so that write is never the first time anyone actually checked
Phase 3's output was correct.

Once Phase 4 completes and is verified, `accounting_ledger_update_freq` can be safely set to a
nonzero value in prod's config, and the periodic scheduler picks up cleanly from where the
backfill left off — no gap, and (per the re-run-safety cross-cutting requirement) no duplication
with what the backfill already captured.

## Clarifications

### Session 2026-08-24

- **Q: Start date?** → **A:** Supplied as a command-line argument to Phase 1 — no default, no
  hardcoded date anywhere in code. The real value is a human decision made at run time, each time.
- **Q: Execution location?** → **A:** Runs locally (on the operator's own machine), not on the
  Windows prod box itself.
- **Q: Byte-equal validation before trusting the pipeline at scale?** → **A:** Confirmed as a
  required gate — not optional, not deferred. (Its concrete shape evolved across later rounds — see
  round 3's method-selection experiment and round 4's Phase 3.5 below — but the underlying
  requirement, "prove correctness before trusting real output," was never dropped.)
- **Q: Prod Morning credentials?** → **A:** Loaded from a file (not an environment variable, not
  hardcoded) — never committed to git.

### Session 2026-08-24 (round 2 — since superseded by round 3)

Round 2 concluded the script should reuse Feature 025's live AI/MCP reconciliation pipeline,
writing output locally while deferring the write-to-prod mechanism entirely out of this feature's
scope. **That conclusion was wrong** — corrected in round 3. Kept here for an honest history of how
the spec evolved; do not implement against round 2's language.

### Session 2026-08-25 (round 3 — architecture correction: three passes, all in scope)

- **Q: Should the script reuse the live reconciliation pipeline (`AIHandler`, the running
  `morning-mcp-app-prod` MCP server, OpenAI Responses API + MCP tools)?** → **A: No.** Verbatim
  user correction: *"the decision was to use MorningClient directly in a new app/script. Not reuse
  anything live anywhere."* Built as a new standalone script/app that imports `MorningClient`
  directly, never going through any running service.
- **Q: Is turning downloaded files into `LedgerEvent` records part of this feature?** → **A: Yes.**
  Verbatim: *"pass 2 is this features job as well."* Not deferred, not a separate feature.
- **Q: Is writing the result into prod's real, live data store part of this feature?** → **A:
  Yes**, eventually. Verbatim: *"and so is the writing to prod data eventually."* Reverses round
  2's "Out of Scope" framing entirely — this is this feature's own scope, implemented last.
- **Q: How does the pipeline decide between a deterministic and an AI-mediated transform?** → **A:**
  A side-by-side experiment against ~20 known **sandbox** documents (never prod, for this
  experiment specifically) — verbatim: *"pass 2 method requires a side-by-side comparison of 20 or
  so sandbox items - if the 2 ways produce the exact same results we go the easy way, which is
  directly from morning. Otherwise, we do the AI route."*

### Session 2026-08-25 (round 4 — phases, not user stories; add a validation gate)

- **Q: Is "user stories" the right frame for a single operator running one linear pipeline?** →
  **A: No.** Verbatim: *"these are hardly user stories, they are more like phases."* Restructured
  as **Phases** (`user-stories.md` keeps the mandatory Given-When-Then format per METHODOLOGY §I —
  only the framing/numbering changed, not the acceptance-criteria discipline).
- **Q: Is there a step that reviews Transform's output for correctness before Load writes it into
  prod's real, live data store?** → **A: Yes — add one.** Verbatim: *"We will have phase 3.5 -
  validation of results."* This is genuinely new — nothing before this round checked Phase 3's
  output was correct before Phase 4 would have written it live. See Phase 3.5 in the Terminology
  Glossary and `user-stories.md`.

## Assumptions (no reasonable-default clarification needed)

- **Direct API access, not pipeline reuse**: this feature does NOT reuse Feature 025's live AI/MCP
  machinery as its primary path. Phase 1 talks to Morning directly via `MorningClient`; Phase 3 may
  or may not involve an AI call at all, decided by the Phase 2 experiment, and if it does, that call
  is a plain OpenAI call working from local files, not a live MCP round-trip.
- **`tools.py`'s conversational caps do not apply to Phase 1**: `apps/morning-mcp-app`'s
  higher-level `tools.list_invoices` wrapper caps results at 100 items and truncates by token
  budget — both exist specifically to keep a WhatsApp reply short, and both would silently break
  or truncate a real bulk historical download. Phase 1 therefore calls `MorningClient`'s raw
  methods directly and implements its own uncapped pagination (see `research.md`), rather than
  reusing that wrapper.
- **Real prod Morning account for Phases 1/4, real sandbox for Phase 2's experiment only**: Phase
  1's real backfill run and Phase 4's eventual load are inherently production-data operations,
  gated by explicit human approval each time. Phase 2's method-selection experiment deliberately
  runs against the Morning sandbox instead — safe, reuses this repo's existing sandbox
  credentials, and never needs to touch prod just to decide which Phase-3 implementation to build.
- **Phase 3.5 is a gate, not a formality**: sign-off is per-window and does not carry over to a
  different window or a re-run of the same window — same discipline as every other "ask every
  time" gate in this codebase (root `CLAUDE.md`).
- **Silent, non-conversational**: no WhatsApp message is ever sent by any phase of this feature — it
  is a data-population operation, not a user-facing one.

## Functional Requirements

- **REQ-BACKFILL-001**: Phase 1 MUST accept a start date as a required command-line argument. No
  default or hardcoded start date may exist anywhere in the implementation.
- **REQ-BACKFILL-002**: Phase 1 MUST construct `MorningClient` directly (imported from
  `apps/morning-mcp-app`'s package) using real prod Green Invoice credentials, and MUST NOT go
  through the live `morning-mcp-app-prod` MCP server, `AIHandler`, or any OpenAI call. Pagination
  MUST be handled without the 100-item cap `apps/morning-mcp-app`'s `tools.list_invoices` wrapper
  imposes (see Assumptions).
- **REQ-BACKFILL-003**: Phase 3 MUST be implemented using whichever method (deterministic or
  AI-mediated) the Phase 2 sandbox experiment selects — not both, not a guess made without running
  the experiment. The experiment itself MUST run against the Morning sandbox, never prod.
- **REQ-BACKFILL-004**: Phase 3's persisted `LedgerEvent` files MUST match the existing schema
  (`schema_version=2`, `accounting_document_*` fields, `event_subtype` = Morning's own
  document-type label) and MUST be written via `LedgerEventManager`'s existing
  `add_ledger_event`/dedup machinery (pointed at a local `storage_dir` — pure local library reuse,
  not a live service).
- **REQ-BACKFILL-005**: No phase MUST hard-cap or skip its run based on window size/document count
  the way Feature 025's live periodic sweep does (its 5-day/100-doc catch-up cap) — a large
  historical window is the expected, normal case for a backfill, not an anomaly to guard against.
  (Distinct from REQ-BACKFILL-002's `tools.list_invoices` cap, a different, conversational-reply-
  oriented limit that also must not apply here.)
- **REQ-BACKFILL-006**: Real prod Green Invoice API credentials required by Phase 1 (and Phase 4,
  once designed) MUST be loaded from a dedicated, new, gitignored file (matching the `*.local.*`
  convention), never hardcoded, and never supplied via an environment variable. Exact shape: see
  `contracts/backfill-creds-file.md` — raw `api_key_id`/`api_key_secret`/`auth_url`/`base_url`,
  matching `MorningClient`'s own constructor, since this feature talks to Morning directly rather
  than through `morning-mcp-app`'s bearer-token-protected MCP server.
- **REQ-BACKFILL-007**: Every run of any phase against real prod data (Phase 1's download, Phase
  4's eventual load) is its own separate, gated action requiring fresh, explicit human approval —
  approval to build/run once does not carry forward to a later or repeated run. (Phase 2's sandbox
  experiment is explicitly NOT gated this way — it never touches prod.)
- **REQ-BACKFILL-008**: No phase of this feature MUST send any WhatsApp message to any user as a
  side effect of running — output is limited to persisted local files, script-local
  logging/console output, and Phase 3.5's validation report, plus, once Phase 4 is built, real
  `LedgerEvent` files landed in prod's data store.
- **REQ-BACKFILL-009**: Phase 1 MUST write downloaded documents, and Phase 3 MUST write transformed
  `LedgerEvent` records, to local output locations on the machine the scripts run on. Phase 4 MUST
  eventually write Phase 3's validated local output into prod's real, live data store — this is in
  scope for this feature, implemented as the feature's last phase, once Phases 1-3.5 are proven
  correct.
- **REQ-BACKFILL-010** (round 4, new): Phase 4 MUST NOT run for a given window until Phase 3.5 has
  produced a validation report for that exact window's output AND a human has explicitly signed off
  on that specific report. Phase 3.5's report MUST include, at minimum: a document-count
  reconciliation between Phase 1's input and Phase 3's output, every anomaly `LedgerEventManager`'s
  tri-state guard surfaced during Phase 3, and a sampled field-level comparison between raw source
  documents and their transformed `LedgerEvent` output. Phase 3.5 MUST NOT call the real Morning
  API and MUST NOT write or modify any `LedgerEvent` file — it is read-only.

## Out of Scope

- Changing prod's `accounting_ledger_update_freq` value itself, or restarting/redeploying
  `denidin-app-prod` — a separate, later, fully explicit human decision (per the root `CLAUDE.md`'s
  "version and release decisions are human-only" + "never start an environment without approval"
  rules), not part of this feature's own scripts.
- Any change to Feature 025's live reconciliation pipeline itself — this feature builds new,
  separate scripts; it does not modify `accounting_reconciliation_service.py`, `AIHandler`, or the
  live MCP server.
- Backfilling dev/test — Feature 025 already actively runs there (`accounting_ledger_update_freq:
  60`); this feature is prod-only by definition.
- A UI/dashboard for Phase 3.5's validation report — a plain local file (JSON/Markdown) an operator
  reads directly is sufficient; no web UI is being built for this.
- The exact Phase 4 (load-to-prod) mechanism — genuinely deferred, but as a **later design step
  within this feature**, not descoped to a different feature.

## Success Criteria

- **SC1**: An operator can run Phase 1 once, with a real start date, against the real prod Morning
  account, and every accounting document from that date forward is downloaded to a local file with
  no document silently dropped for exceeding a conversational fetch/token cap.
- **SC2**: The Phase 2 sandbox experiment produces a clear, field-level diff result and Phase 3 is
  built using whichever method it selected.
- **SC3**: Phase 3 produces a correctly-populated `LedgerEvent` file locally for every downloaded
  document, with zero WhatsApp messages sent as a side effect.
- **SC4**: Phase 3.5 produces a validation report (count reconciliation, anomalies, sampled
  field-level checks) for every window, and Phase 4 never runs without an explicit human sign-off
  on that window's report.
- **SC5**: Running Phase 1 or Phase 3 twice over the same or overlapping range produces zero
  duplicate output the second time.
- **SC6**: No prod Morning credential ever appears in a git-tracked file at any point during or
  after development/use of this feature.
- **SC7**: Phase 4, once built, lands Phase 3's validated local output into prod's real, live data
  store with no duplication of anything already there.

## References

- `specs/done/025-morning-sourced-ledger-events/` — the reconciliation pipeline this feature
  explicitly does NOT reuse for its core capture step (see Clarifications round 3), though Phase
  3's Method B (if selected) adapts its `LEDGER_EVENT_TOOL`/prompt shape to work from local files.
- `apps/morning-mcp-app/src/denidin_mcp_morning/morning_client.py` — `MorningClient`, constructed
  directly by Phase 1 (`list_invoices`/`get_invoice`, real raw Morning API calls).
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` — `list_invoices`'s 100-item cap and
  token-budget truncation, confirmed as unsafe to reuse for Phase 1's bulk download (see
  `research.md`).
- `apps/denidin-app/src/managers/ledger_event_manager.py` — `add_ledger_events_from_call`, the
  tri-state dedup guard this feature depends on for both re-run safety and Phase 3.5's anomaly
  surfacing, reused as pure local library code in Phase 3.
- `specs/done/v0.2.0/035-windows-always-on-prod/quickstart.md` — the real prod data-access model
  (read-only sshfs mount, `denidin-winprod` SSH host alias) that Phase 4's eventual design must
  work within.
- Root `CLAUDE.md` — "Environment isolation & locking," "AI AGENTS: NEVER START AN ENVIRONMENT...
  WITHOUT EXPLICIT APPROVAL," "AI AGENTS: VERSION AND RELEASE DECISIONS ARE HUMAN-ONLY" — all
  directly bind how/when Phase 1/Phase 4 may ever actually be run against prod.

## Next Steps

1. ~~Resolve Open Questions~~ — done, four rounds of clarification, round 4 (2026-08-25) is
   authoritative.
2. `speckit.plan` (revised) — `plan.md`, `research.md`, `data-model.md`, `contracts/`,
   `quickstart.md`, all updated for the five-phase architecture (Phase 3.5 added).
3. `speckit.tasks` — TDD task breakdown, human approval gate before implementation.
4. `speckit.analyze` — cross-artifact consistency check.
5. `speckit.implement`.
