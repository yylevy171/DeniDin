# Research: Feature 098

Phase 0 output of `speckit.plan` (2026-10-05). Each entry: Decision / Rationale /
Alternatives. Items marked **LIVE-VERIFY** are third-party behavior that must be confirmed
with a real sandbox call before the code depending on them is written (CONSTITUTION "No
unverified third-party assumptions").

---

## R1 - Where the client's ID comes from, per tool

**Decision**:
- `create_invoice` (305) and `create_combo_document` (320): from the `Client` that
  `_require_resolved_client` already returns. It comes from `POST /clients/search`, whose
  items carry `taxId` (mapped to `Client.tax_id`, confirmed live 2026-07-29 per
  `models.py:88-94`). No extra Morning call.
- `create_combo_document_as_reference` (320 closing a 300): the original document carries
  only the client snapshot taken when the 300 was created, which can predate the ID being
  added. So fetch the **current** client record by id: new `MorningClient.get_client(id)`
  → `GET /clients/{id}`.

**LIVE-VERIFY**: (a) `GET /clients/{id}` exists on the sandbox and returns `taxId`;
(b) a client updated with `taxId` a moment ago is returned with it on the next search
(the existing `wait_until` helper in the update-client tests suggests short indexing lag).

**Alternatives**: search by the original's `client.name` (rejected: names aren't unique;
the id is exact). Trust the document's client snapshot (rejected: stale after Story 2).

## R2 - Which amount is compared

**Decision**: compute the pre-VAT amount from the **built payload**, right before
`client.create_invoice(payload)`: `sum(price * quantity)` over `income`; if the payload's
`vatType == 1` (amount includes VAT), divide by `1 + vat_rate`. One helper, used by all
three tools, so it reflects exactly what would be sent - including the as-reference path's
`amount=None` (defaults to the 300's total).

Comparison: `pre_vat > threshold` (strictly greater - "עולה על", spec §3). Round
`pre_vat` to 2 decimals before comparing, so 5,900 incl. VAT at 18% = 5,000.00 exactly,
not 5,000.0000001 (UAT 3.2).

**Alternatives**: compare the tool's `amount` argument (rejected: the as-reference tool's
amount may be `None`).

## R3 - VAT rate

**Decision**: reuse `morning-mcp-app`'s existing `default_vat_rate` config field
(`config.py:36`, currently unused in code). Its value is **0.17** in the code default,
`config.example.json`, `config.dev.json` and `config.prod.json`; Israel's VAT is 18% since
2025-01-01. It becomes **0.18**. Config edits **approved by PM 2026-10-05** (D-2).

**Alternatives**: hard-code 18% (rejected: VAT has changed before); a new field
(rejected: an unused field with the right name already exists).

## R4 - How the refusal is surfaced

**Decision**: new `ClientTaxIdRequiredError(ValueError)` in `tools.py`, raised after a
`log_refusal(tool, "client_tax_id_required", ...)`. `errors.py.friendly_error_message`
gets a branch for it (like `ClientNotFoundError`) that returns its Hebrew message verbatim.
`_call_with_error_boundary` already turns that into an MCP `isError=True` result.

**Rationale**: the established "succeed or raise" contract (`server.py:196-214`). A plain
`ValueError` would be swallowed into the generic "❌ הבקשה אינה תקינה".

## R5 - Threshold in DeniDin (PM decisions Q3 + D-4, revised 2026-10-05)

**Decision (PM)**: DeniDin keeps its **own copy** of the threshold in its own config,
`allocation_threshold_nis` (top-level, next to `accounting_ledger_update_freq`), in
`apps/denidin-app/config/config.{example,dev,prod,test}.json`, loaded by
`AppConfiguration` like any other field. Default 5000.

**Rationale**: easy to implement, no startup call, no retry machinery; speed matters more
than a single source of truth here.

**Cost accepted**: two places to change together (documented in quickstart.md and in
CLAUDE.md's config notes); nothing detects drift between them. If they drift, Morning-MCP's
refusal is still authoritative - the worst case is DeniDin's prompt quoting a stale number
or asking for an ID one step later.

**Rejected**: fetching it through OpenAI at startup (heavier: a billed call per start,
retry machinery, live verification of forcing an MCP tool). Rejected outright (PM): any
direct call or import from DeniDin to morning-mcp-app.

## R6 - Injecting the threshold into DeniDin's prompt

**Decision**: `runtime_constitution.md` uses a placeholder, `{{ALLOCATION_THRESHOLD_NIS}}`.
`AIHandler._load_constitution` substitutes it from `config.allocation_threshold_nis`
(same place as the Feature 080 marker handling, `ai_handler.py:2057`), formatted `5,000`.
The value never changes while running, so the constitution stays a stable prefix and
prompt caching is unaffected.

**Getting the number into the prompt.** With a config copy the value is known at startup,
so the timing problem disappears. Two things still have to hold:
1. **Every prompt that mentions it** - today only `runtime_constitution.md`. A unit test
   asserts no `{{ALLOCATION_THRESHOLD_NIS}}` survives into any final `instructions` string.
2. **Backbone (Feature 063)** - 063 loads `backbone.md` plus per-flow/per-capability prompt
   files dynamically. The substitution must sit at 063's single prompt-assembly point so it
   covers every file, whichever is loaded. Hand-off item for 063.

## R7 - Asking before the approval prompt (REQ-098-04)

**Finding**: the approval gate fires on the creation tool call **before** the tool runs
(`ai_handler.py:4138-4176`). So the Morning-side refusal (R4) only fires after the user
taps "כן" - correct as a backstop, wrong as the primary UX.

**Decision**: the prompt rule tells the model: before proposing a 305/320 whose pre-VAT
amount exceeds the threshold, call `get_client_details` (a read tool, no approval) and,
if `tax_id` is not 9 digits, ask for the ID instead of proposing the document.

**Alternatives**: add `tax_id` to `resolve_client_name`'s result to save a call
(rejected: mixes concerns into the resolver, and the model calls `get_client_details`
anyway in the as-reference flow).

## R8 - Two approvals in a row (UAT 2.1)

**Finding (code)**: after an approved MCP action, the approval response goes through
`_finalize_response` (`ai_handler.py:4879`), which detects a **new**
`mcp_approval_request` in that same response and stores it as the next pending approval
with buttons (`ai_handler.py:4138-4176`). So "update_client approved → model immediately
proposes the 320 → second buttons" is already mechanically supported; no code change.

**Not verified**: that the model actually chains the 320 proposal in that response rather
than just reporting the update. The prompt rule states it explicitly; UAT 2.1 is the proof.

## R9 - Feature flag

**Decision (PM, 2026-10-05)**: **no feature flag.** The feature is mandatory and there is
no going back. Documented exception to CONSTITUTION §VI, same as Feature 092.
