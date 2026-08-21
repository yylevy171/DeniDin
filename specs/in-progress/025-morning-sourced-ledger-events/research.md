# Phase 0 Research: Morning-Sourced Ledger Events

**Feature**: 025-morning-sourced-ledger-events · **Date**: 2026-08-20

All decisions below were made directly with the user (see spec.md's "Clarifications" section,
2026-08-20 session, two rounds) plus grounding investigation into the current codebase performed
during this research pass. No open NEEDS CLARIFICATION remain.

## Naming convention (resolved 2026-08-20, second round; revised 2026-08-21, third round)

**Decision**: New/renamed fields on the persisted `LedgerEvent` record use an `accounting_document_`
prefix, doc-type-agnostic and vendor-neutral:

| Old / reserved name (Feature 033) | New name (this feature) |
|---|---|
| `morning_document_id` / `invoice_number` | `accounting_document_display_number` (**merged**, round 3 — see below) |
| `invoice_type` | `accounting_document_type` |
| `invoice_status` | `accounting_document_status` |
| `invoice_actual_creation_date` | `accounting_document_creation_date` |

**Round 3 correction (2026-08-21)**: round 2 originally planned `accounting_document_id` (from
Morning's opaque internal `Invoice.id`) as a *separate* field from `accounting_document_number`
(from the human-visible `Invoice.number`), with `_id` doing dedup-key duty. User correction: *"document
id... is the USER FACING display number - NOT the morning internal id... rename it everywhere to
document_display_number."* These collapse into **one** field, `accounting_document_display_number`
— sourced from `Invoice.number`/raw `number` — which is also the dedup key (see "Dedup mechanism"
below). Morning's internal id (`Invoice.id`) is used only transiently within a sweep tick (to call
`get_invoice_details`) and is never persisted or exposed as its own field. **Field count: 4, not 5.**

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

**Caveat, added by `speckit.analyze` (finding C1), partially closed 2026-08-21 (round 3)**: the
original conclusion was derived entirely from static code reading. A real, read-only probe against
the actual Morning **dev** sandbox (2026-08-21) confirmed `list_invoices`/`get_invoice` (called
directly via `MorningClient`, bypassing all Pydantic mapping) return real documents spanning **6
distinct document types** (raw `type` codes 300, 305, 320, 330, 400) from one `/documents/search`
call with no `type` filter — direct, live confirmation that these endpoints are genuinely
type-agnostic, not just request-code-agnostic. **Still not fully closed**: only 6 of Morning's full
type set were observed live (whatever real documents happened to exist in the dev sandbox at probe
time) — `tasks.md`'s live-verification task is retained to explicitly create/observe at least one
type outside this set if practical, but the core "no new tooling needed for the search/get
endpoints themselves" claim is now live-evidence-backed, not just inferred from code.

`accounting_document_type` is populated by decoding `Invoice.type`'s int against Morning's real
`GET /documents/types` endpoint — already confirmed live elsewhere in this codebase
(`tools._build_cancellation_payload`'s docstring: "confirmed live via GET /documents/types: 330 =
'חשבונית זיכוי'"). Reuse/extend that already-verified lookup rather than re-deriving it from
scratch or guessing codes.

**New finding, round 3 (2026-08-21) — real scope addition, not previously planned**: the same live
probe also checked `number` (display number) and creation-time granularity. **Every one of the 25
real documents observed, across all 6 types, had a non-null `number`** (e.g. `"40406"`, `"80645"`,
`"52204"`, `"60444"`, `"70284"`) — confirming `accounting_document_display_number` (see "Naming
convention" above) can be sourced reliably. **The raw response also carries a `creationDate` field
— a genuine Unix epoch integer with full second-level precision** (e.g. `1787241168` →
`2026-08-20 18:52:48` Israel local), not just the date-only `documentDate` round 1/2 assumed was
the only available creation-time signal. **But `apps/morning-mcp-app`'s `Invoice` Pydantic model
currently maps neither `number`-as-guaranteed nor `creationDate` in a way this feature can consume
for full-precision timestamps** — it only maps `documentDate` (date-only) into `issue_date`. This
is a real, material addition to this feature's scope (user decision, 2026-08-21: land it as part
of Feature 025 rather than a separate PR) — see `tasks.md`'s new morning-mcp-app task(s): map
`creationDate` into a new `Invoice` field and expose it through `get_invoice_details`'s tool
output, so the reconciliation sweep's OpenAI+MCP call can actually see it.

## Dedup mechanism (resolved 2026-08-20, first round; **fully redesigned 2026-08-21, third round**)

**Round 1 design (superseded — kept here for history only)**: a hard refusal inside
`add_ledger_event`, checking against a full re-scan of `{data_root}/events/*.json` every time.
User rejected this outright: *"I don't like the hard refusal and never asked for it. What if the
original was a mistake?... The 'since when' mechanism SHOULD NOT RELY ON A REFUSAL MECHANISM."*
Also rejected: re-scanning the events directory on every tick (*"ideally no reading and parsing of
the ledger events is required per tick"*).

**Round 3 design (current)**: `LedgerEventManager` owns an **in-process, in-memory** cache —
`Dict[accounting_document_display_number, Set[creation_datetime]]` — never a second persisted
store, never rebuilt from disk more than once per process lifetime:

- **Lazy one-time build**: on the first `add_ledger_event` call with `source_type="חשבונית"` in a
  given `LedgerEventManager` instance's lifetime, the cache is built by scanning
  `{data_root}/events/*.json` once (`scan_accounting_documents`, revised to return
  `Dict[str, List[datetime]]` rather than the old `Tuple[Set[str], Optional[date]]` — see
  `data-model.md`). Every subsequent call reuses the already-built in-memory cache — no re-scan.
- **Tri-state decision** per incoming `(display_number, creation_datetime)` pair (this is a
  ledger-persistence concern, decided **inside `LedgerEventManager`**, not the new `ai_handler.py`
  handler — user directive: *"it's clearly a ledger requirement regardless of ai"*):
  - `display_number` unseen → **new**: persist normally, add `creation_datetime` to the cache
    entry for that `display_number`.
  - `display_number` seen, and `creation_datetime` matches a timestamp already recorded for it →
    **true duplicate** (a re-poll of the identical document) → **silently discard**, no new file,
    cache unchanged.
  - `display_number` seen, but `creation_datetime` does **not** match any timestamp already
    recorded for it → **anomaly** (a real Morning document's own creation time should never
    change across polls — "this should never happen", per user) → **persist as a new
    `LedgerEvent`** (its own new `event_id`, driven by the differing timestamp — duplicates-by-
    display-number are allowed to coexist as separate event files) **and** log a WARNING **and**
    append an entry to a new persisted `{data_root}/accounting_reconciliation/pending_review.json`
    tracker (display_number, prior event_id/timestamp, new event_id/timestamp, detected_at). No
    WhatsApp alert — this stays a silent, log/file-discoverable mechanism.
- **Pruning, every tick**: an entry can be dropped from the cache once its (only remaining, or
  all) timestamp(s) are older than the 5-day safety cap (see "Capture mechanism" below) plus a
  small margin (7 days total) before `now_local()` — the forward-only watermark can never
  legitimately cause a document that old to be re-queried again. **Flagged for live confirmation**
  of Morning's actual `from_date` filter semantics before this margin is trusted as exactly right
  (folded into `tasks.md`'s live-verification task) — the reasoning is sound in principle but not
  yet independently confirmed against how Morning's own date filtering actually behaves at the
  boundary.

**Poll watermark derivation**: still no separate persisted "last poll time" file — the "since when"
boundary for each poll's `list_invoices(from_date=...)` call is derived from the same in-memory
cache (the maximum `creation_datetime` across all its entries), not a re-scan. A fixed fallback
lookback applies only when the cache is empty (first-ever poll on a fresh environment, or after
every prior `חשבונית` event aged out of the cache's own retention — unlikely but not impossible).
**A failed or capped-out tick naturally does not advance anything** — since the watermark is
derived from the cache's actual contents (which only change on a successful persist), a tick that
errors out, or is skipped entirely for exceeding the safety cap (see below), simply leaves the
derived watermark unchanged, and the next tick re-covers the same window. No separate
failure/retry bookkeeping needed.

## Safety cap on catch-up scope (new, 2026-08-21, third round)

**Decision**: this sweep is explicitly **not a backfill mechanism**. If the gap since the derived
watermark exceeds **5 days OR would surface more than 100 not-yet-known documents**, whichever
binds first, the sweep **skips the entire tick** — captures nothing, does not advance the
watermark — rather than attempting a partial catch-up. Logged at ERROR; no WhatsApp alert (kept
consistent with this sweep's existing "no confirmation reply anywhere, silent background
mechanism" contract). Resolving a capped-out gap is an explicit admin/human action outside this
feature's scope (the sweep's job is only to *identify* the gap via the ERROR log, not resolve it).

**The cap check is done by the service directly, never trusted to the model**: before ever
constructing the OpenAI+MCP prompt, `_sweep_accounting_documents` makes its own plain,
non-AI-mediated `list_invoices(from_date=since)` call (via the same `MorningClient` machinery,
just not through the OpenAI Responses API) solely to count/date-check the candidate documents.
Only if within both bounds does it proceed to the real OpenAI+MCP-mediated capture call. This
matches this codebase's existing "never trust the AI's own math/scoping" philosophy already
applied elsewhere in `ledger_event_manager.py` (`_normalize_amount`, `vat_status` forcing for
`בנק`, the `payer_name`-rescue logic).

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

**Interval, resolved 2026-08-21 (round 3)**: a new top-level DeniDin config field —
`config.accounting_ledger_update_freq` (minutes, int). `0` means the feature is inactive and the
scheduler never starts at all (no job registered, no startup sweep). This is a plain
`AppConfiguration` field like any other (no env vars, per CONSTITUTION.md), not a
`config.feature_flags` entry — the schema-version bump (see "Schema versioning" above) remains
the mechanism distinguishing old vs. new record shape; this config field only controls whether the
background poller runs at all.

## `capture_ledger_event` tool schema extension

`LEDGER_EVENT_TOOL` (`ai_handler.py`) is a `strict: true` function-tool schema — every property
must be listed in `required` (nullable ones use `type: [X, "null"]`), and `additionalProperties:
False`. Adding `source_type="חשבונית"` requires:

- Extending `source_type`'s enum: `["הסכם", "בנק", "חשבונית"]`.
- New top-level fields for `accounting_document_display_number`/`_type`/`_status`/
  `_creation_date` (**4 fields, not 5** — round 3 collapsed the planned `_id`/`_number` pair into
  one `_display_number` field, see "Naming convention" above), each nullable, forced `null` for
  `source_type != "חשבונית"` at the `LedgerEventManager` layer — same defensive discipline already
  applied to `bank_number`/`payer_name`/`trigger_condition` for their own respective
  `source_type`s.
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

**Round 3 scope correction**: this new `ai_handler.py` handler owns turn-shape concerns only (no
suppression, multi-call-per-turn allowed) — it does **not** own the duplicate/anomaly decision
described in "Dedup mechanism" above. That decision lives entirely inside
`LedgerEventManager.add_ledger_event` (via the in-memory cache) — the new handler is a thin
adapter that parses each `capture_ledger_event` call and passes it straight through to
`add_ledger_event`, exactly like every other capture path already does, trusting the manager to
decide new/duplicate/anomaly on its own.
