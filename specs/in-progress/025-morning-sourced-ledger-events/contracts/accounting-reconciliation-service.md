# Integration Contract: Accounting Document Reconciliation Service

**Feature**: 025-morning-sourced-ledger-events · Per METHODOLOGY.md §VII format.

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

No feature-flag gate (per spec.md Clarifications — schema-version bump instead), but this is a
real always-on background job making real OpenAI/Morning calls on every tick — `tasks.md` must
size the interval conservatively (this is a cost/traffic concern, not a correctness one) and this
contract does not fix a number here.

**Novel-mechanism risk, flagged by `speckit.analyze` (finding H1)**: step 4 below (a standalone
OpenAI Responses API call with no session/`chat_id`/`AIRequest`) has never been exercised
anywhere in this codebase before — every existing Morning-MCP-authorized call goes through a real
conversational turn. `tasks.md` T010 is a dedicated Gate-Zero task (mirroring Feature 054's own
T014 precedent for its analogous novel-mechanism risk, unprompted WhatsApp sending) that proves
this mechanism works live, once, cheaply, **before** the full multi-scenario Acceptance pass
(T011 onward) is written — not deferred all the way to the end as an unstated assumption.

---

### `_sweep_accounting_documents(global_context)` (shared worker, module-level function)

1. `known_ids, latest_creation_date = ledger_event_manager.scan_accounting_documents()`
   (data-model.md) — one scan answers both "what's already captured" and "since when to poll."
2. `since = latest_creation_date or (now_local().date() - FALLBACK_LOOKBACK)` — `FALLBACK_LOOKBACK`
   sized in `tasks.md`, used only on the very first sweep this environment ever runs (no
   `חשבונית` events persisted yet).
3. Build a **dedicated** prompt (NOT `runtime_constitution.md`, NOT `AIHandler._build_instructions`'s
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
4. Call OpenAI Responses API directly (bypassing `AIHandler.get_response`'s normal request/
   session flow entirely — no `AIRequest`, no `chat_id`, no session):
   `tools = self._build_morning_mcp_tools(...) + [LEDGER_EVENT_TOOL]` (same MCP attachment
   `_build_morning_mcp_tools` already builds — reused as-is, not reimplemented — but called with
   whichever role/config makes the Morning MCP tools attach unconditionally for this job, since
   there is no per-turn `user_obj` to RBAC-check against; TBD in `tasks.md` whether this reuses
   `_build_morning_mcp_tools`'s existing signature with a synthetic authorized role, or a small
   new variant).
5. Parse the response for `capture_ledger_event` calls via `extract_all_function_calls` (existing
   helper, reused as-is). **This is where the sweep's handling diverges from
   `_handle_ledger_event_capture`** (see research.md's "Critical" note) — a **new** handler:
   - Does NOT suppress on same-turn `mcp_call` (the opposite of `_handle_ledger_event_capture`'s
     rule — `list_invoices`/`get_invoice_details` `mcp_call`s are expected and fine here).
   - Does NOT treat multiple `capture_ledger_event` calls in one turn as a protocol violation —
     one call per new document, in the same turn, is the normal case.
   - For each parsed call: **hard-refuse a duplicate** — if `accounting_document_id` is already
     in `known_ids` (step 1), log and skip (do not persist), regardless of what the model itself
     believed was "new." This is the dedup guard's actual enforcement point (data-model.md) —
     the prompt's own date-window framing is a courtesy to reduce redundant `capture_ledger_event`
     calls, never the sole safeguard against a duplicate write.
   - Otherwise: `ledger_event_manager.add_ledger_events_from_call(...)` (existing method, reused
     as-is — same merge-components-into-flat-shape logic already handles a single-component
     `חשבונית` call with no changes needed there).
6. No confirmation reply is sent anywhere — no chat, no `WhatsAppHandler.send_response`, nothing
   user-facing. This is a silent background reconciliation; a captured event's existence is
   discoverable the same way any ledger event already is (the persisted file itself, read by a
   human/downstream tooling), not via a WhatsApp message. (If the user later wants a summary
   notification, that is a new, separate decision — not assumed here.)
7. On any exception (OpenAI call failure, MCP unavailability, parse error): log at ERROR, do not
   persist anything from this tick, return. Per data-model.md's watermark design, this
   self-corrects — the next tick's `scan_accounting_documents()` naturally re-derives the same
   `since` boundary (nothing new was persisted), so no separate retry/backoff state is needed.

---

### `session_id`/`message_id` sentinel values (data-model.md)

Every `LedgerEvent` persisted by this sweep uses `session_id="accounting-reconciliation"`,
`message_id=None` — a fixed, greppable sentinel distinguishing reconciliation-sourced events from
conversational ones in the persisted data, never a fabricated session/message id that could be
mistaken for a real one.
