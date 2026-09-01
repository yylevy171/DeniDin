# Feature Specification: Prod Morning Ledger Backfill — Completion (Phase 4 + Prod Run)

**Feature Branch**: `feature/062-prod-morning-ledger-backfill-completion`
**Created**: 2026-08-27
**Status**: Done — the real prod backfill this feature exists for was executed and verified
2026-09-01 (see "Prod Backfill Executed" below). Per explicit user direction, this was run as a
**one-time chore, not a speckit feature**: no `user-stories.md`/`plan.md`/`tasks.md`, and T022–T035
below (the regression-test suite + a real `load.py` Phase-4 mechanism) were deliberately **not**
built — the same ad-hoc, human-supervised, temporary-rw-sshfs-mount method already used and proven
by `specs/done/065-august-ledger-audit-apply` was reused instead. This closes the feature's actual
goal; the original "Input" scope below (T022–T035) is recorded as intentionally not pursued, not
as work still outstanding.

---

## Prod Backfill Executed (2026-09-01)

Real one-shot backfill of Morning-sourced accounting-document ledger events into prod, `--since
2025-09-01` (no `--until`), using `apps/prod-ledger-backfill/` (Feature 061's pipeline, reused
as-is per explicit user direction — "no need for speckit for this feature, its a one time
backfill... no need for a load py script").

**Pipeline run:**
- **Phase 1 (download)**: 595 real documents pulled from Morning prod via `download.py`, full
  `get_invoice()` detail per document (not shallow search-list data) — verified via code path,
  log line counts, and sample content.
- **Phase 3 (transform)**: 595 `LedgerEvent` files produced via `transform.py` → real
  `LedgerEventManager.add_ledger_event`. `_load_raw_documents` was fixed to sort by Morning's real
  `creationDate` (ascending) instead of filename — halved the number of unresolved same-batch
  cross-references (74/146 → 11/146 genuinely unresolvable, all confirmed pre-`2025-09-01`).
- **Phase 3.5 (validate)**: clean report — 595 raw documents, 595 ledger events, 0 discrepancy,
  0 anomalies. Signed off by Yaron Levy, 2026-09-01. The report's obsolete third check
  ("sampled field-level comparison" against `method_a.transform()`) was removed — see
  `validate.py`'s own module docstring for why (the oracle stopped one pipeline stage short of the
  real save path and always reported false mismatches; Method A vs. B was already settled).
- **Prod write**: via a temporary rw sshfs mount (`~/denidin-winprod-data-rw`, mirroring 065's
  method exactly — separate from the permanent read-only mount, torn down immediately after use).
  `scripts/apply_backfill_to_prod.py` (this folder) did a plain, resumable byte-for-byte copy —
  dedup pre-flight (by filename and by `accounting_document_display_number`) found **zero**
  conflicts of any kind (prod had 0 Morning-sourced events before this run). The mount died
  mid-copy once (same known sshfs failure mode 065 hit); the script's resumability handled it
  cleanly. 499 + 96 macOS AppleDouble sidecar files (`._*`) were found and removed, matching 065's
  precedent. All 595 events verified byte-identical against the source after the write, and again
  independently via a fresh `LedgerEventManager` instantiation against the live prod storage path
  from inside the running `denidin-app-prod` container (`index_size: 741`; `חשבונית: 595`,
  `הסכם`/`בנק`: the pre-existing 146).
- **Apps restarted** (`morning-mcp-app-prod` first, then `denidin-app-prod`, per the bundling
  order rule) so `LedgerEventManager` reloaded its in-memory index from disk.
- **Independent cross-check**: two real CSV exports pulled directly from Morning by the user
  (invoices/receipts/credit-notes, and transaction accounts separately — Morning's export format
  excludes `חשבון עסקה` from the first) were cross-referenced against the backfill by internal
  Morning document UUID. Result: 527/527 and 66/66 exact matches — zero missing documents, zero
  amount/number/client-name mismatches on either side.
- **Follow-up, same day**: user set `accounting_ledger_update_freq: 60` in prod config (was `0`)
  and restarted both apps again — confirmed live in the running container's own loaded config.

**Two real, unrelated bugs found and fixed along the way** (both required and received explicit
user approval before any code change, per this repo's standing rules):
- `apps/morning-mcp-app/src/denidin_mcp_morning/models.py`: `Invoice.amount`/`Payment.amount`/
  `LinkedDocument.amount` had a `Field(ge=0)` lower bound that rejected 15 real prod type-400
  receipt-cancellation documents ("ביטול חשבונית מס / קבלה...") which carry genuinely negative
  amounts by Morning's own reversal convention. Loosened to plain `float`. The one test that
  pinned the old (wrong) behavior was replaced, with separate explicit sign-off, per this repo's
  test-immutability rule.
- `apps/prod-ledger-backfill/transform.py`: raw-document processing order was filename (UUID) sort
  — effectively random relative to real chronology — which left roughly half of all genuine
  same-batch cross-references unresolved purely by processing-order luck. Fixed to sort by real
  Morning `creationDate` ascending (see the pipeline-run notes above for the measured effect and
  its limits).

**Deliberately not pursued** (see Status above): T022–T028 (re-run-safety and credential-
precondition regression tests) and T029/T030/T032–T035 (a real `load.py` Phase-4 mechanism and its
acceptance tests) — this was a one-time, human-supervised chore, not a piece of standing
infrastructure meant to be re-run unattended, so building a repeatable/idempotent loader and its
test suite was judged not worth it for a single execution. If Morning-sourced ledger backfill is
ever needed again as a recurring or unattended operation, that scope should be revisited then,
not assumed still relevant from this closed-out spec.

**Still open, tracked separately, not this feature's concern**: two pre-existing issues surfaced
incidentally while verifying this backfill's prod restart — (1) one orphaned session
(`0f5eaa04-6277-46ec-8e86-c9cae932170a`) has failed to load on every hourly cleanup sweep since
2026-08-27 18:23 (`SessionManager.__init__() got an unexpected keyword argument
'pending_ledger_events'` — a schema mismatch on a stuck session file; caught and logged, not
crashing anything); (2) `denidin-app-prod` restarted a second time, unexplained, ~2 minutes after
this session's own first restart on 2026-09-01, from an external SIGTERM this session did not
send. Neither is caused by or related to this backfill; flagged for the human to decide whether
either warrants its own bugfix.

---

## Original Scope (superseded — recorded for history, not pursued)

Priority was P2 (no urgency — prod's `accounting_ledger_update_freq` stayed `0` until this was
done, which was the accepted state at the time this spec was drafted).

**Input**: Everything Feature 061's `tasks.md` left unchecked as of 2026-08-27 closeout:
- **T022–T025 (XC-Rerun)**: unit tests + implementation proving `download.py`/`transform.py` are
  safe to re-run over an overlapping date window (dedup via overwrite-by-id) — largely already
  demonstrated empirically during the real dev backfill (multiple overlapping runs, no corruption
  from re-running), but never captured as a committed regression test.
- **T026–T028 (XC-Creds)**: unit tests + implementation for credential-file precondition failures
  (missing file, malformed JSON, missing required field) — `load_credentials()` in `download.py`
  already implements this defensively; the corresponding Task A/B tests were never written.
- **T029 (Phase 4 placeholder)**: design the actual **Load** mechanism — currently `dev_data/events/`
  was populated by direct file copy (an ad-hoc operator action, not a script), which was fine for
  a one-time dev backfill under close supervision but is not what should happen against real prod
  data. Needs a real `load.py` (or equivalent) that's idempotent, dry-run-capable, and doesn't
  require a human to eyeball a diff before every copy.
- **T030, T032–T035 (Acceptance)**: `billed`/`expensive`-tier acceptance tests for Phase 1
  (download), Phase 3 (transform), Phase 3.5 (validate), re-run safety, and credential security —
  none were ever written; the real dev backfill run served as an ad-hoc, manually-verified stand-in
  for T030/T032/T033, but not as a repeatable automated test.
- **The actual prod run**: once the above is done, execute the real one-shot prod backfill this
  feature exists for, using real prod Morning credentials (`config/backfill_prod_creds.local.json`)
  and `dev_data/events/`'s prod equivalent — gated the same way as every other environment-affecting
  action (fresh explicit approval, no exceptions).

**Known findings from the dev run to carry forward** (see Feature 061's `research.md`/session
history for full detail — do not rediscover these from scratch):
- Morning's real sandbox/prod API rate-limits (403, not 429) after bursts of ~650-710 sequential
  calls in a short window; recovers partially after ~15-20 minutes. Any Phase 4/prod-run tooling
  should assume this will recur and either pace requests or handle it gracefully (the dev run used
  a manual 5-minute retry loop — not itself a committed feature, just an ad-hoc operator workaround).
- Morning's `/documents/search` pagination is confirmed **newest-first (descending)**, not
  oldest-first — verified empirically, do not re-assume the opposite.
- The event-id `seq` digit is a **single digit (0-9)**, matching a real external `Events.csv`
  convention (see `specs/done/v0.2.0/033-ledger-event-persistence/research.md`) — this is
  deliberate and must NOT be permanently widened. A prod run hitting >10 accounting documents in
  the same real-world minute for the same source-type letter needs its own explicit human decision
  each time, same as the dev run's "just for this run" 2-digit widening (never committed).
- **A real, reproducible AI-transcription corruption bug exists in the live
  `accounting_reconciliation_service` pipeline** (Method B's AI-relay path, and separately
  confirmed in a live dev sweep on 2026-08-27) — Hebrew text fields (`description`,
  `accounting_document_status_label`) can come back with substituted/transposed characters when
  the model transcribes them into the `capture_ledger_event` tool call. This was accepted as a
  known, live risk for the dev thread ("I'll live with the model's garbling for now, although I am
  a bit concerned about it" — user, 2026-08-27) but should be considered before turning on prod's
  reconciliation scheduler at any real frequency; a root-cause investigation/fix is out of scope
  for Feature 061/062 specifically and would need its own bug-driven-development spec if pursued.

**Required Files**: `user-stories.md`, `plan.md`, `tasks.md` — none started yet; this file is a
holding spec recording scope and context only, per METHODOLOGY.md's spec-first requirement — full
`speckit.specify`/`clarify`/`plan`/`tasks` pipeline still needs to run before implementation.
