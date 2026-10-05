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
2025-01-01. It must become **0.18**. ⚠️ Editing config files needs explicit human approval
(CLAUDE.md "Config is code") - **pending**.

**Alternatives**: hard-code 18% (rejected: VAT has changed before); a new field
(rejected: an unused field with the right name already exists).

## R4 - How the refusal is surfaced

**Decision**: new `ClientTaxIdRequiredError(ValueError)` in `tools.py`, raised after a
`log_refusal(tool, "client_tax_id_required", ...)`. `errors.py.friendly_error_message`
gets a branch for it (like `ClientNotFoundError`) that returns its Hebrew message verbatim.
`_call_with_error_boundary` already turns that into an MCP `isError=True` result.

**Rationale**: the established "succeed or raise" contract (`server.py:196-214`). A plain
`ValueError` would be swallowed into the generic "❌ הבקשה אינה תקינה".

## R5 - Threshold delivery to DeniDin (PM decision Q3)

**Decision**: a new read-only MCP tool on Morning-MCP, `get_invoicing_rules()` →
`{"allocation_threshold_nis": 5000}`. DeniDin calls it **directly** at startup (not
through OpenAI), using the `mcp` Python client library over streamable-HTTP, with the
same tunnel URL (`MorningMcpLocator`) and bearer token (`mcp.morning_auth_token`) it
already uses. The same tool is attached to the model like any other Morning tool, which
is also what UAT 4.2 exercises.

**New dependency**: `mcp>=1.0.0,<2.0.0` in `apps/denidin-app/requirements.txt` (the same
pin `morning-mcp-app` uses).

**Retry (CONSTITUTION §XVIII)**: a background thread started by `initialize_app` polls
every 2s for up to 60s; if still unavailable, it keeps retrying every 5 minutes until it
succeeds. It never blocks startup and never gives up permanently.

**Alternatives**: a plain authenticated HTTP route (e.g. `GET /invoicing_rules`) called
with `requests` - simpler, no new dependency, precedent in `health_server.py`'s
`/is_alive` call. Rejected for now because PM described an MCP route and UAT 4.2 (approved)
asks Morning-MCP for the threshold over MCP; a route plus a tool would be two contracts
for one value. **Revisit if the `mcp` client dependency in denidin-app is unwanted.**

## R6 - Injecting the threshold into DeniDin's prompt

**Decision**: `runtime_constitution.md` uses a placeholder, `{{ALLOCATION_THRESHOLD_NIS}}`.
`AIHandler._load_constitution` substitutes it (same place as the Feature 080 marker
handling, `ai_handler.py:2057`), from an injected `InvoicingRules` holder:
- value known → `5,000 ₪`;
- not yet known → `the allocation threshold (unknown right now)` wording, with the rule
  telling the model to rely on Morning's refusal.

The value is fixed after it arrives, so the constitution stays a stable prefix and
prompt caching is preserved (one prefix change, the moment the value first arrives).

**Backbone (Feature 063)**: same placeholder, substituted wherever 063 loads flow /
capability prompts. See plan.md "Feature 063 dependency".

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

CONSTITUTION §VI requires new behavior behind a default-off flag, and integration tests
must never set flags. With a default-off flag, the backstop's integration tests could
not exercise it. Precedent: Feature 092 shipped with no flag by PM approval (2026-10-03).
**Pending PM decision** (plan.md D-1).
