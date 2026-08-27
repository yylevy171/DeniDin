# Feature Specification: Prod Morning Ledger Backfill — Completion (Phase 4 + Prod Run)

**Feature Branch**: TBD (create at pickup time, e.g. `feature/062-prod-morning-ledger-backfill-completion`)
**Created**: 2026-08-27
**Status**: Backlog — split off from Feature 061 (`specs/done/v0.5.3/061-prod-morning-ledger-backfill`)
when that feature's real, practical goal (a full dev-environment ledger backfill, Method A,
Jul 1 – Aug 27 2026) was completed and closed out, but its tooling was deliberately left short of
full spec completion. Priority: P2 (no urgency — prod's `accounting_ledger_update_freq` stays `0`
until this is done, which is already the accepted current state).

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
