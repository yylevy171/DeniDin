# Integration Contract: Accounting Document Reconciliation Service

**Feature**: 025-morning-sourced-ledger-events · Per METHODOLOGY.md §VII format.

> **Phase 9 (2026-08-23) — the flow below is now a SINGLE model tool call.** The sweep asks
> `list_invoices` for `output_format="json"` and captures one `capture_ledger_event` per returned
> document, copying its JSON verbatim. Structured bank details and `linkedDocuments` do come from
> the single-document GET — but **`morning-mcp-app` performs that fan-out server-side**, as
> deterministic code. Delegating it to the model was tried live and failed: it called
> `list_invoices`, emitted two captures and stopped, never once calling `get_invoice_details`,
> even after that tool's misleading description was fixed. The safety-cap check now reads
> `total_matched` from the JSON payload rather than parsing Hebrew prose.

**Revised 2026-08-21 (round 3, `spec.md`'s Clarifications)**: adds the `config.accounting_ledger_update_freq`
config gate, a service-side (non-AI) safety-cap pre-check before ever calling OpenAI, and removes
the hard-refusal dedup step from this file's step 5 (that decision now lives entirely inside
`LedgerEventManager` — see `contracts/ledger-event-manager-extension.md`).

---

### Scheduling: APScheduler `BackgroundScheduler` + one `CronTrigger` job (new: `src/services/accounting_reconciliation_service.py`)

Structurally mirrors `services/reminder_delivery_service.py` (Feature 054) — one shared job for
the whole process, a startup catch-up sweep plus a periodic tick, both calling the same shared
worker function:

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=lambda: _sweep_accounting_documents(global_context),
    trigger=CronTrigger(...),   # interval TBD, tasks.md
    id="accounting_document_reconciliation_sweep",
    max_instances=1,             # a slow tick must not overlap the next one
)
scheduler.start()
```

`run_startup_accounting_reconciliation_sweep(global_context)` runs synchronously on the main
thread before `scheduler.start()`, same precedent as `run_startup_cleanup`/
`run_startup_reminder_sweep`.

**Per `reminder-delivery.md`'s own hard-won correction (2026-08-17)**: this scheduler MUST be
started in the `if __name__ == "__main__":` block, alongside `bot.run_forever()` — **never**
inside `initialize_app()`, which `tests/integration/` calls directly against a process-global
`denidin_app` singleton. Starting a real background poller that makes real OpenAI + Morning MCP
calls there would let an ordinary test run reach live external services unattended. Exact wiring
(`denidin.accounting_reconciliation_scheduler`, `.shutdown()` on SIGINT/SIGTERM alongside the
existing `cleanup_thread`/`reminder_scheduler` shutdowns) — `tasks.md`.

No `config.feature_flags` gate (per spec.md Clarifications — schema-version bump covers the
record-shape side), but there IS a plain config gate on whether the scheduler runs at all:
`config.accounting_ledger_update_freq` (top-level, minutes, int; `0` = inactive — the scheduler is
never started, no job registered, no startup sweep). `denidin.py`'s `__main__` wiring (T009) reads
this value and skips `start_accounting_reconciliation_scheduler`/
`run_startup_accounting_reconciliation_sweep` entirely when it's `0`.

**Novel-mechanism risk, flagged by `speckit.analyze` (finding H1)**: step 5 below (a standalone
OpenAI Responses API call with no session/`chat_id`/`AIRequest`) has never been exercised
anywhere in this codebase before — every existing Morning-MCP-authorized call goes through a real
conversational turn. `tasks.md` T010 is a dedicated Gate-Zero task (mirroring Feature 054's own
T014 precedent for its analogous novel-mechanism risk, unprompted WhatsApp sending) that proves
this mechanism works live, once, cheaply, **before** the full multi-scenario Acceptance pass
(T011 onward) is written — not deferred all the way to the end as an unstated assumption.

---

### `_sweep_accounting_documents(global_context)` (shared worker, module-level function)

1. `since = ledger_event_manager.get_accounting_document_watermark()` (new small method — the max
   timestamp across the lazily-built in-memory cache described in
   `contracts/ledger-event-manager-extension.md`; the cache itself is built via **one** disk scan
   on first use per process, never re-scanned per tick, per round 3). `None` if no `חשבונית`
   event has ever been captured this process.
2. `since = since or (now_local() - FALLBACK_LOOKBACK)` — `FALLBACK_LOOKBACK` sized in `tasks.md`,
   used only on the very first sweep this environment ever runs (no `חשבונית` events persisted
   yet).
3. **Safety cap — split pre-check/post-check (revised round 4, `spec.md`'s Clarifications — no
   direct MCP-client mechanism exists in denidin-app to do this fully pre-hoc, and building one
   from scratch is out of scope for this one check)**:
   - **5-day half — genuine pre-check**: if `now_local() - since > timedelta(days=5)`, **skip the
     entire tick** before ever calling OpenAI: log ERROR, `return`. Pure local computation from
     the cache watermark, no call needed.
   - **100-document half — post-check, after step 5's one OpenAI+MCP call completes**: the
     service inspects the real `list_invoices` `mcp_call` item(s) in `response.output` (same
     `item.name`/`item.output` shape `ai_handler.py` already extracts elsewhere) and parses the
     TRUE total count from the tool's own real output text (never the AI's summary/prose) —
     `morning-mcp-app`'s `format_invoice_list`/`format_too_many_invoices_message` always state
     it, in one of a few fixed phrasings. If that total exceeds 100, **discard the entire turn's
     captures** — never call step 6's handler at all — log ERROR, `return`; the watermark stays
     unchanged (nothing was persisted). Still never trusted to the model's own scoping (the code
     reads the tool's real output, not AI-authored text) — just checked after the one call
     instead of before, since no cheaper mechanism exists.
   This is deliberately NOT a backfill mechanism (spec.md Clarifications, round 3) — a real,
   human-resolved gap is surfaced via the ERROR log, never auto-caught-up.
**Revised again 2026-08-22 (round 5) — steps 4-6 are now a SINGLE-tool-call flow.** The
`get_invoice_details`-per-document chaining these steps originally described is gone: measured
live, `get_invoice_details` adds only `linkedDocuments`/`userName` over a `/documents/search`
item, and `morning-mcp-app` now renders the creation timestamp + description in `list_invoices`'
own output. The model makes **one** `list_invoices` call, then one `capture_ledger_event` per
document, taking every value from that one result. See `spec.md`'s round-5 Clarifications for the
measurement and for why the old design could never work (a tool's own description outranks the
prompt). The prompt text below is superseded by
`services/accounting_reconciliation_service.py`'s `_build_reconciliation_prompt` — kept here only
as the shape/constraints record.

4. Build a **dedicated** prompt (NOT `runtime_constitution.md`, NOT `AIHandler._build_instructions`'s
   normal assembly) instructing the model, roughly:
   > List every Morning document created on or after `{since}` (use `list_invoices` with
   > `from_date={since}`, paginate/re-query as needed to see all of them). For each one not
   > already known to you from this list (cross-reference is NOT the model's job — see below),
   > call `get_invoice_details` to get its full fields, then call `capture_ledger_event` with
   > `source_type="חשבונית"` populated directly from that document's real fields — never
   > inferred, never guessed. Call `capture_ledger_event` once per document. Do not produce any
   > other reply text — this is not a conversation.
   Exact final prompt text — `tasks.md`/implementation (this contract fixes the *shape and
   constraints*, not the literal wording).
5. Call OpenAI Responses API directly (bypassing `AIHandler.get_response`'s normal request/
   session flow entirely — no `AIRequest`, no `chat_id`, no session):
   `tools = self._build_morning_mcp_tools(...) + [LEDGER_EVENT_TOOL]` (same MCP attachment
   `_build_morning_mcp_tools` already builds — reused as-is, not reimplemented — but called with
   whichever role/config makes the Morning MCP tools attach unconditionally for this job, since
   there is no per-turn `user_obj` to RBAC-check against; TBD in `tasks.md` whether this reuses
   `_build_morning_mcp_tools`'s existing signature with a synthetic authorized role, or a small
   new variant).
5b. **100-document cap post-check (round 4)**: before parsing anything, extract every
   `list_invoices` `mcp_call` item from `response.output` (`item.name == "list_invoices"`,
   `item.output` = the tool's real returned Hebrew text) and parse the true total count from it
   (step 3's "100-document half" above). If exceeded: log ERROR, `return` immediately — step 6
   below never runs, nothing from this turn is persisted.
6. Parse the response for `capture_ledger_event` calls via `extract_all_function_calls` (existing
   helper, reused as-is). **This is where the sweep's handling diverges from
   `_handle_ledger_event_capture`** (see research.md's "Critical" note) — a **new** handler:
   - Does NOT suppress on same-turn `mcp_call` (the opposite of `_handle_ledger_event_capture`'s
     rule — `list_invoices`/`get_invoice_details` `mcp_call`s are expected and fine here).
   - Does NOT treat multiple `capture_ledger_event` calls in one turn as a protocol violation —
     one call per new document, in the same turn, is the normal case.
   - For each parsed call: passes straight through to
     `ledger_event_manager.add_ledger_events_from_call(...)` — **no dedup/anomaly logic in this
     handler at all (round 3 revision)**. The new/duplicate/anomaly decision (including any
     `pending_review.json` write) happens entirely inside `LedgerEventManager` itself — see
     `contracts/ledger-event-manager-extension.md`. This handler trusts the manager exactly like
     every other capture path already does.
7. **After the OpenAI call/parse loop completes** (success or partial success), call
   `ledger_event_manager.prune_accounting_document_cache()` once — the per-tick cache pruning step
   (`contracts/ledger-event-manager-extension.md`).
8. No confirmation reply is sent anywhere — no chat, no `WhatsAppHandler.send_response`, nothing
   user-facing. This is a silent background reconciliation; a captured event's existence is
   discoverable the same way any ledger event already is (the persisted file itself, read by a
   human/downstream tooling), not via a WhatsApp message. (If the user later wants a summary
   notification, that is a new, separate decision — not assumed here.)
9. On any exception (OpenAI call failure, MCP unavailability, parse error): log at ERROR, do not
   persist anything from this tick, return (skip step 7's prune for that tick — harmless to skip,
   next successful tick's prune call catches up). Per data-model.md's watermark design, this
   self-corrects — the next tick's `get_accounting_document_watermark()` naturally re-derives the
   same `since` boundary (nothing new was persisted, and the in-memory cache is unchanged), so no
   separate retry/backoff state is needed.

---

### `session_id`/`message_id` sentinel values (data-model.md)

Every `LedgerEvent` persisted by this sweep uses `session_id="accounting-reconciliation"`,
`message_id=None` — a fixed, greppable sentinel distinguishing reconciliation-sourced events from
conversational ones in the persisted data, never a fabricated session/message id that could be
mistaken for a real one.
