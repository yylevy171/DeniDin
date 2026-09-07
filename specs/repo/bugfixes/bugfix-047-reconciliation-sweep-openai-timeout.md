# Bugfix Spec: Feature 025 reconciliation sweep inherits the 30s conversational OpenAI timeout and always times out

## Bug ID
bugfix-047-reconciliation-sweep-openai-timeout

## Title
The accounting-document reconciliation back thread (Feature 025) never captures anything in
dev: every hourly sweep's single OpenAI Responses call fails with `APITimeoutError` because it
reuses the shared OpenAI client, which is built with `timeout=30.0` for short conversational
turns — far too low for the sweep's much heavier MCP + reasoning-model turn.

## Priority
**P1** — a silent, client-relevant capability outage (the ledger silently misses every Morning
document created directly in Morning) that self-perpetuates every hour.

## Status
**Done — implemented, tested, validated in dev, Merged to master (PR #267).** Root cause investigated and presented;
human approved fix #1 (a dedicated per-call timeout) and explicitly rejected the other four
proposals (service-side deterministic capture, morning-mcp concurrent fan-out, watermark
handling changes, extra failure observability) — "code must stay stupid, all the smartness in
the models". Human also explicitly **waived the failing E2E/acceptance test** ("we'll just
shoot it in prod since it can't do any harm") — see Test-Gap Analysis below.

## Date Opened
2026-08-29

## Reported By
yaronlev171 — "check that the back thread for morning events is working fine and picking up
events in dev. which events did it find over the past 3 days since 0.5.3 was deployed?"

## Symptom (observed)
In `apps/denidin-app/logs/dev/denidin.log`, since v0.5.3 was deployed (2026-08-27 18:08:45):
- 21× `Request timed out.` (`APITimeoutError`) raised from
  `accounting_reconciliation_service.py` at the `responses.create` call site
- 1× `Connection error.`
- 1× partial success — a single sweep captured exactly 1 event (`H27082616350`, receipt
  #80660)

Every timeout failure takes **exactly 60s** = 2 × 30s attempts (the shared client's
`max_retries=1`). 100% of the OpenAI-timeout tracebacks in the dev log originate from the
reconciliation service; ordinary conversational turns never time out. The behavior predates
v0.5.3 — it began under v0.5.2 (~2026-08-27 04:00) as the Morning sandbox's in-window document
count grew past ~13.

Net data impact in dev: the watermark froze at 2026-08-27 16:35, so nothing created after that
was reconciled. (Investigating this also surfaced bugfix-048 — the pre-timeout sweeps had been
*re-persisting* every already-captured 27/08 document on each tick because the dedup guard
broke across restarts. Both are fixed together on this branch.)

## Root Cause
The reconciliation sweep (`services/accounting_reconciliation_service._sweep_accounting_documents`)
issues **one** OpenAI Responses API call with the Morning MCP server attached as a remote tool
plus the local `capture_ledger_event` tool. In a single turn that call:
1. fetches the Morning MCP tool list over the ngrok tunnel,
2. runs `list_invoices(from_date=<watermark>, output_format="json", include_full_details=true)`
   — which triggers a **sequential** server-side per-document `client.get_invoice(id)` fan-out
   in `apps/morning-mcp-app` (~7s for 16 documents, and growing),
3. has a reasoning model (`gpt-5.6-luna`) emit one verbose `capture_ledger_event` call per
   document.

That legitimately takes 30–60s+ and scales with document volume. But `ai_handler.client` is
the single shared `OpenAI(...)` instance built in `denidin.py` with `timeout=30.0` — a value
chosen (2026-07-05) for interactive WhatsApp turns, where 30s is already generous. The sweep
inherited it implicitly. Once the sandbox held enough in-window documents that a sweep turn
exceeded 30s, **every** sweep started failing (2 × 30s, then `APITimeoutError`), and the
watermark never advanced, so the same too-large window was retried every hour forever.

## Test-Gap Analysis
The existing unit tests for this service (`tests/unit/test_accounting_reconciliation_service.py`)
stub the OpenAI client entirely, so no test exercises real call latency, and none asserted
anything about the client's timeout/retry configuration for this call path. A real failing
end-to-end/acceptance test that reproduces "a sweep turn that takes >30s against the real
sandbox + real tunnel" was **explicitly waived by the human** for this fix ("we'll just shoot
it in prod since it can't do any harm" — the sweep is silent and idempotent, so a bad deploy
carries no user-facing risk). Validation is instead: deploy to prod-equivalent, observe the
next sweep in the log capture events instead of timing out.

One minimal regression guard was added in lieu of the waived E2E test:
`test_openai_call_overrides_the_conversational_timeout_and_retry` — asserts the sweep issues
its call via `client.with_options(timeout=RECONCILIATION_CALL_TIMEOUT_SECONDS, max_retries=0)`
and that the constant is ≥ 300s. This folds into the existing stubbed-client test class; it
does not attempt to reproduce the latency itself.

## The Fix (minimal)
`src/services/accounting_reconciliation_service.py` only:
- New module constant `RECONCILIATION_CALL_TIMEOUT_SECONDS = 300.0` with a comment explaining
  why the sweep call is heavier than a conversational turn.
- The call site now issues the request via
  `ai_handler.client.with_options(timeout=RECONCILIATION_CALL_TIMEOUT_SECONDS, max_retries=0).responses.create(**reconciliation_kwargs)`
  — the same `.with_options()` per-call override mechanism `ai_handler._call_openai_approval_api`
  already uses. `max_retries=0` because a retry re-runs the entire sweep (list_invoices fan-out
  included) from scratch, and the hourly scheduler tick is already the real retry; the
  scheduler runs at most one sweep at a time (`max_instances=1`), so a long-running call is
  harmless.

The shared client's `timeout=30.0` in `denidin.py` is **not** changed — conversational turns
should keep the tight ceiling. No change to `apps/morning-mcp-app`, no change to the watermark
logic, no service-side deterministic capture, no new config key.

### Test-compatibility change
`tests/unit/test_accounting_reconciliation_service.py`'s `mock_ai_client` fixture now does
`client.with_options.return_value = client` (self-return), so the ~15 existing
`mock_ai_client.responses.create` assertions keep addressing the same call unchanged.

## Incidental: two time-bomb tests fixed in the same change
`tests/unit/test_accounting_reconciliation_service.py` pinned its `ACCOUNTING_DOC` fixture to a
frozen `creation_date` of `2026-08-20T18:52:00+03:00`. The reconciliation watermark, the 5-day
catch-up cap, and the ~7-day cache-retention prune all key off that timestamp, so once
wall-clock time moved >7 days past it (2026-08-30), two tests began failing on `master`,
unrelated to any code change:
- `test_gap_within_five_days_proceeds_normally` — watermark now 10 days stale → sweep hit the
  5-day skip → `responses.create` never called.
- `test_second_tick_capturing_the_same_document_persists_nothing_new` — the post-sweep
  `prune_accounting_document_cache` dropped the >7-day-old cache entry between the two ticks, so
  the tri-state dedup guard had nothing to match against on tick 2 and the same document was
  persisted twice.
Neither is a real dedup/product bug — both windows are the only ones in which a document can
ever be re-queried, and dedup works correctly for anything inside them. Fix: `ACCOUNTING_DOC`'s
date fields are now computed as `now_local() - timedelta(hours=1)`, and the dedup test gained
an `assert responses.create.call_count == 2` so it can never again pass by silently skipping
tick 2.

## Files Changed
- `apps/denidin-app/src/services/accounting_reconciliation_service.py`
- `apps/denidin-app/tests/unit/test_accounting_reconciliation_service.py`

## Recovery on redeploy
Redeploying runs `run_startup_accounting_reconciliation_sweep` on boot with
`from_date=2026-08-27` (watermark unchanged — it never advanced past the last success). The
gap is under the 5-day / 100-document safety cap, so the sweep proceeds; with bugfix-048's
(date, display_number) guard it dedups every 27/08 document already present and advances the
watermark. Verify afterward per bugfix-048's Verification section.
