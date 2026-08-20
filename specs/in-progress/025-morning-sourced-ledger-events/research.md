# Phase 0 Research: Morning-Sourced Ledger Events

**Feature**: 025-morning-sourced-ledger-events · **Date**: 2026-08-20

All decisions below were made directly with the user (see spec.md's "Clarifications" section,
2026-08-20 session, two rounds) plus grounding investigation into the current codebase performed
during this research pass. No open NEEDS CLARIFICATION remain.

## Naming convention (resolved 2026-08-20, second clarification round)

**Decision**: New/renamed fields on the persisted `LedgerEvent` record use an `accounting_document_`
prefix, doc-type-agnostic and vendor-neutral:

| Old / reserved name (Feature 033) | New name (this feature) |
|---|---|
| `morning_document_id` | `accounting_document_id` |
| `invoice_number` | `accounting_document_number` |
| `invoice_type` | `accounting_document_type` |
| `invoice_status` | `accounting_document_status` |
| `invoice_actual_creation_date` | `accounting_document_creation_date` |

**`source_type` stays `"חשבונית"` / letter `"H"`** (the value already reserved in
`ledger_event_manager.py`'s `_LETTER_BY_SOURCE_TYPE` and its comment) — the user explicitly chose
to keep this over a generic `"מסמך"`/`"D"` alternative, on the theory that "חשבונית" is already
used loosely in the real ledger for any Morning-sourced accounting document, not literally only
tax invoices.

**Risk flagged, not yet closed**: this is an assumption about how the *real*, hand-maintained
`Events.csv` (in the separate AHLedger project) actually uses the term "חשבונית" — per
`CONSTITUTION.md`'s "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS" principle (which this repo already
treats as applying to human-maintained downstream conventions, not just third-party APIs — see
Feature 033's own real-`Events.csv`-grounded audits), this should be verified against real
`Events.csv` rows before `speckit.implement` ships it, not simply assumed correct because the user
stated a preference. Carried into `tasks.md` as an explicit verification task, not a blocker to
planning.

**Vendor-neutral naming is scoped to this feature's new/renamed field, tool-parameter, and
service/class names only** — it does NOT rename the existing `apps/morning-mcp-app`,
`MorningClient`, `morning-mcp-app` service labels, `config.mcp.morning_*` config keys, or any other
already-shipped Morning integration naming. Those are out of scope; only what this feature itself
introduces needs to be vendor-neutral.

## Document-type scope (resolved 2026-08-20, second clarification round)

**Decision**: ALL Morning document types (invoices, receipts, credit notes, combo documents), not
invoices only.

**Finding that changes the original risk assessment**: this does NOT require new MCP tooling.
Direct inspection of `apps/morning-mcp-app`:

- `MorningClient.list_invoices()` (`morning_client.py`) POSTs to `/documents/search` with **no
  `type` filter** — `tools._map_list_invoices_filters` only ever sends `fromDate`/`toDate`/
  `clientName`/`number`. It already returns every document type Morning has, invoice-named or not.
- `MorningClient.get_invoice()` GETs `/documents/{id}` directly — also generic, not invoice-scoped.
- `Invoice.type: Optional[int]` (the Pydantic model both tools return) already carries Morning's
  real per-document type code for whatever came back.

So `list_invoices`/`get_invoice_details` are misnamed (a naming artifact of when they were first
built) but already structurally document-type-agnostic. **No morning-mcp-app changes needed** for
this decision — a real, welcome scope reduction from what was flagged as a risk when the question
was first asked.

**Caveat, added by `speckit.analyze` (finding C1)**: the conclusion above is derived entirely
from **static code reading** — no live call has actually confirmed Morning's real
`/documents/search`/`/documents/{id}` genuinely return a non-invoice document (receipt, credit
note, etc.) when queried this way, only that the request-building code sends no `type` filter.
Per `CONSTITUTION.md`'s absolute "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS" principle, this must not
be treated as confirmed until it is — see `tasks.md` T020, a live-verification task against the
real Morning dev sandbox, to be run before this scope decision is relied on by any Acceptance
task.

`accounting_document_type` is populated by decoding `Invoice.type`'s int against Morning's real
`GET /documents/types` endpoint — already confirmed live elsewhere in this codebase
(`tools._build_cancellation_payload`'s docstring: "confirmed live via GET /documents/types: 330 =
'חשבונית זיכוי'"). Reuse/extend that already-verified lookup rather than re-deriving it from
scratch or guessing codes.

## Dedup mechanism (resolved 2026-08-20, first clarification round)

**Decision**: No new store. The "already known" set is derived by scanning existing persisted
`LedgerEvent` files under `{data_root}/events/*.json` for a non-null `accounting_document_id`.

**New code-side guard** (this feature's own addition, consistent with `ledger_event_manager.py`'s
existing "never fully trust the AI's own scoping" philosophy — see `_normalize_amount`,
`vat_status` forcing for `בנק`, `payer_name` rescue): before persisting a new `source_type="חשבונית"`
event, `LedgerEventManager` itself checks whether that `accounting_document_id` already exists
among persisted events and refuses (logs, does not write) if so — a second guard beneath whatever
date-window scoping the reconciliation prompt does on its own. This is a genuinely new method
(`LedgerEventManager` currently has no by-field lookup across all events — `_load_event` looks up
by `event_id` only), so it needs an index/scan helper.

**Poll watermark derivation**: rather than a separate persisted "last poll time" state file, the
"since when" boundary for each poll's `list_invoices(from_date=...)` call is derived the same
way — the latest `accounting_document_creation_date` among already-persisted `source_type="חשבונית"`
events, with a fixed fallback lookback (to be sized in `data-model.md`/`tasks.md`, mirroring
`reminder_delivery_service.py`'s split startup/periodic lookback pattern) for the very first poll
ever run. This has a useful side effect: **a failed poll tick naturally does not advance anything**
— since the watermark isn't a separate counter but is derived from what's actually been
persisted, a tick that errors out before persisting anything simply leaves the derived watermark
unchanged, and the next tick re-covers the same window. No separate failure/retry bookkeeping
needed, unlike a hand-maintained watermark file would require.

## Schema versioning (resolved 2026-08-20, first clarification round)

**Decision**: No `config.feature_flags` gate. Instead, bump `ledger_event_manager.py`'s
`CURRENT_SCHEMA_VERSION` from `1` to `2`. This is a generation marker on the persisted record
shape as a whole (per its own existing docstring/precedent — see Feature 043 US5), not a per-
`source_type` flag — every event persisted going forward (via any of the three sources:
conversational text, image, or this feature's reconciliation sweep) carries `schema_version: 2`
once this feature ships, since they all share one record shape and one `add_ledger_event` write
path.

## Capture mechanism / poll trigger (resolved 2026-08-20, first clarification round)

**Decision**: Proactive, company-wide, periodic polling — not reactive-only. Routed through
OpenAI's Responses API using the same MCP-tool-attachment access pattern (`type: "mcp"`, remote
Morning server, bearer auth) a real godfather turn uses, but this is explicitly **not** a
runtime/conversational turn:

- No `runtime_constitution.md` in `instructions` — a dedicated, purpose-built prompt instead (see
  `contracts/accounting-reconciliation-service.md`), whose entire job is: list and detail every
  Morning document created since the derived watermark, then call `capture_ledger_event` once per
  new document.
- No memory recall, no role/date-context assembly, no chat session — this call has no
  `chat_id`/`session_id` of its own in the normal sense (see data-model.md for what `session_id`
  becomes for a reconciliation-sourced `LedgerEvent`).
- `list_invoices`/`get_invoice_details` are already in `NO_APPROVAL_MCP_TOOLS`
  (`ai_handler.py`) — fully automatic, no `PendingApprovalManager` involvement, consistent with a
  background job having no human to approve anything in the loop. `capture_ledger_event` itself
  has never gone through an approval gate either (Feature 024/033's whole design: captured
  immediately, reviewed later by a human against the persisted file) — the reconciliation sweep's
  writes are the same "capture now, review later" shape, not a new pattern.

**Scheduling**: mirrors `services/reminder_delivery_service.py`'s APScheduler
`BackgroundScheduler` + `CronTrigger` + startup-sweep-plus-periodic-tick shape (see that file
and `contracts/reminder-delivery.md` for the precedent this new service structurally follows).
Exact interval/lookback sizing is a `data-model.md`/`tasks.md`-level decision, not re-litigated
here beyond confirming the pattern to reuse.

## `capture_ledger_event` tool schema extension

`LEDGER_EVENT_TOOL` (`ai_handler.py`) is a `strict: true` function-tool schema — every property
must be listed in `required` (nullable ones use `type: [X, "null"]`), and `additionalProperties:
False`. Adding `source_type="חשבונית"` requires:

- Extending `source_type`'s enum: `["הסכם", "בנק", "חשבונית"]`.
- New top-level (or component-level — TBD in `data-model.md`) fields for
  `accounting_document_id`/`_number`/`_type`/`_status`/`_creation_date`, each nullable, forced
  `null` for `source_type != "חשבונית"` at the `LedgerEventManager` layer — same defensive
  discipline already applied to `bank_number`/`payer_name`/`trigger_condition` for their own
  respective `source_type`s.
- `event_subtype`'s enum needs a new value for `חשבונית` (today's enum is only
  `["יצירה", "הפקדה"]`, one per existing `source_type`) — exact value TBD in `data-model.md`.

Since the reconciliation prompt supplies these values directly from structured `Invoice` model
data (not free-text interpretation), the model's role for a `חשבונית` capture is populate-from-
given-data, not the same "recognize signal in prose" task the existing text/image paths use
`capture_ledger_event` for — worth noting in the tool description so the two usages don't drift/
conflict, and so a real conversational turn is never tempted to self-invoke a `חשבונית` capture
from a `list_invoices` result it happens to see (the exact bug this whole feature exists to
replace with something correct).

**Critical: the reconciliation sweep MUST NOT go through `_handle_ledger_event_capture`
unchanged, and needs its own new handler method.** That existing method currently does two
things that would actively defeat this feature if reused as-is:

1. **Same-turn-`mcp_call` suppression** — it already explicitly detects `mcp_call`/
   `mcp_approval_request` in the same turn's `response.output` and drops every
   `capture_ledger_event` call, with a docstring citing this exact feature ("Morning-sourced
   documents ARE a real, distinct ledger-event source in principle... but capturing them
   properly is a separate, not-yet-built feature — see specs/backlog/025-..."; user directive,
   2026-08-02: "Morning events should NOT trigger ledger events at all"). That directive was
   scoped to ordinary conversational turns (the reactive path) — it must stay exactly as-is
   there. The reconciliation sweep's whole point is to legitimately co-occur `list_invoices`/
   `get_invoice_details` `mcp_call`s with `capture_ledger_event` calls in the same turn, so it
   needs a separate handler this suppression never touches.
2. **"At most one `capture_ledger_event` call per turn, else PROTOCOL VIOLATION, nothing
   persisted"** — correct for a single conversational message describing at most one event, but
   wrong for the reconciliation sweep, where calling it once per new document *within the same
   turn* is the expected, correct shape (a poll tick may need to capture several new documents
   at once). The new handler needs its own multi-call semantics, not this one's.

Both existing behaviors are load-bearing for real, cited incidents in the conversational path —
they are not being weakened or removed, just not reused for a fundamentally different call
pattern. Concrete new method name/shape (e.g. `_handle_accounting_reconciliation_capture`) is a
`data-model.md`/`contracts/`-level decision.
