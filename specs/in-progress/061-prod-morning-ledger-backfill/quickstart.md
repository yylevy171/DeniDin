# Quickstart: Prod Morning Ledger Backfill

**Feature**: 061-prod-morning-ledger-backfill

An operator runbook, not a conversational feature — no WhatsApp user ever sees any of this run.
Every step that touches real prod Morning data requires its own fresh, explicit human approval, per
root `CLAUDE.md`'s "NEVER START AN ENVIRONMENT... WITHOUT EXPLICIT APPROVAL" banner — even though
this feature never starts a container, downloading real prod financial data (or writing to prod's
real data store) is its own "touch prod" action, gated the same way.

**Revised 2026-08-25 (round 4)**: adds Step D, the Phase 3.5 validation gate, between Transform and
Load. All five phases run locally — no SSH fetch, no MCP server, no live `denidin-app`/
`morning-mcp-app` container involved anywhere in this runbook (until Phase 4's eventual load step,
whose exact mechanism is still TBD).

## One-time setup (per operator machine)

1. `cd apps/prod-ledger-backfill` (this feature's own new app — set up its virtualenv/dependencies
   per its own `requirements.txt`, same pattern as `apps/morning-mcp-app`'s local test-running
   setup).
2. Create `apps/prod-ledger-backfill/config/backfill_prod_creds.local.json` by hand — see
   `contracts/backfill-creds-file.md` for the exact shape. Paste `api_key_id`/`api_key_secret`/
   `auth_url`/`base_url` from `creds/DeniDin Prod Creds.txt`. **Never commit this file** — it's
   gitignored via the existing `*.local.*` convention.
3. Create `apps/prod-ledger-backfill/config/backfill_sandbox_creds.local.json` by hand too — same
   four-field shape as step 2, values hand-transcribed from
   `apps/morning-mcp-app/config/config.test.json`'s existing sandbox credentials (its `api_url`
   field becomes this file's `base_url`; `api_key_id`/`api_key_secret`/`auth_url` copy over
   unchanged). This is a second, small, gitignored file — `download.py` only ever understands this
   one shape, so no separate credential-parsing path exists for sandbox vs. prod
   (`contracts/backfill-creds-file.md`).

## Step A: Phase 2's sandbox method-selection experiment (one-time, before Phase 3 is ever built)

Never touches prod. Run once, during implementation, to decide how `transform.py` is built:

```bash
cd apps/prod-ledger-backfill
python3 download.py --since <a date covering ~20 known sandbox documents> \
    --output-dir ./output/sandbox_sample \
    --creds-file config/backfill_sandbox_creds.local.json
python3 select_method.py --input-dir ./output/sandbox_sample --report-out ./method_selection_report.json
```

Read the printed verdict (`IDENTICAL — adopt Method A` or `DIFFERS on: <fields> — adopt Method B`)
and the full report. `transform.py`'s real implementation is then built using the selected method —
this step is not repeated for every later real run.

## Step B: Phase 1 — download real prod documents

Ask for fresh, explicit approval before this step — every run, no exceptions (REQ-BACKFILL-007),
regardless of whether an earlier run already covered part of the same window.

```bash
cd apps/prod-ledger-backfill
python3 download.py --since <operator-supplied start date> \
    --output-dir ./output/<a stable, descriptive name — reused for any future re-run>
```

Inspect the console summary (documents seen / newly downloaded / already-present-skipped) before
proceeding.

## Step C: Phase 3 — transform into ledger events

Purely local — no real Morning API call, no approval gate needed for this step itself.

```bash
python3 transform.py --input-dir ./output/<same name as Step B> \
    --output-dir ./ledger_events/<a stable, descriptive name — reused for any future re-run>
```

## Step D: Phase 3.5 — validate before trusting the result (NEW, required, per window)

Also purely local, no approval gate for running it — but its **output requires a human sign-off**
before Step E may happen for this window:

```bash
python3 validate.py --raw-dir ./output/<same name as Step B> \
    --ledger-dir ./ledger_events/<same name as Step C> \
    --report-out ./validation_reports/<same descriptive name>.json
```

Read the report in full:
- **Document-count reconciliation** — every raw document from Step B accounted for in Step C's
  output, or explicitly explained as an intentional skip. Any unexplained gap needs investigation
  before proceeding — do not sign off with an unexplained mismatch.
- **Surfaced anomalies** — anything `LedgerEventManager`'s own tri-state guard flagged during Step
  C. Review each one.
- **Sampled field-level comparison** — spot-check a handful of documents' raw source fields against
  their transformed `LedgerEvent` fields by eye.

Only once this looks correct: **sign off** on this specific report (mechanism — editing the report
file, or `python3 validate.py --approve --report-in <path>`, per the implementation's final
`contracts/cli-contract.md` — check that file for the exact command once built). Sign-off is
per-window and per-run — it does not carry over to a different window or a later re-run of the same
window, even one that looks identical.

## After Steps B/C/D

- Confirm no prod credential landed in any git-tracked file (`git status`).
- **Do not** attempt to hand-copy `LedgerEvent` files onto prod's real data store — Phase 4
  (`load.py`) is the sanctioned mechanism for that, designed and implemented once Steps B-D have
  been exercised and trusted (see `plan.md`'s Close-out), and it will itself refuse to run without
  Step D's sign-off for the target window.

## Re-running / extending a backfill

Reuse the exact same `--output-dir` for both Step B and Step C across separate invocations — this
is what makes re-running safe (cross-cutting re-run-safety requirement): Step B overwrites
already-downloaded documents byte-identically rather than duplicating them under a new filename,
and `LedgerEventManager` rebuilds its dedup cache by scanning `--output-dir` fresh each time, so
already-captured documents are silently skipped, never duplicated. A re-run still needs its own
fresh Step D validation report and its own fresh sign-off — a prior window's sign-off never covers
a new or overlapping run.

## Step E: Phase 4 — load into prod's real data store (future step, mechanism TBD)

Not yet designed (`research.md` R10) — will get its own short runbook addition once implemented, as
a later phase of this same feature. Whatever the mechanism, it will (per REQ-BACKFILL-010): refuse
to run without a signed-off Step D report for the exact target window; only ever write the
already-validated local `LedgerEvent` files Steps B-D produced — never re-derive or re-fetch
anything at load time; and require its own fresh, explicit approval, every run, same as Step B.
