# Phase 8 code-eye sweep — findings (2026-08-12)

**Purpose**: Before running any billed/expensive test against the rebuilt dev containers,
read every billed/expensive test file in both apps to find spots where the client-name-
resolution architecture fix (`resolve_client_name` + `name_resolved`-gated tools, see
`client-name-resolution-plan.md`) might make a test's *assertion* stop meaning what it used
to — per the user's explicit framing (2026-08-12): the tests' flows/message sequences/turn
counts are the fixed ground truth ("beacon of truth"); only assertion internals may need
adjusting, and only after being audited against a real run, never speculatively.

**Method**: static code read only. No test was run, no test file was edited, as part of this
sweep (the one exception, done separately at the user's explicit instruction: `max_attempts`
in `denidin_mcp_e2e_helpers.py` was reverted from 25 back to 5).

**Status column**: `OPEN` (not yet discussed), `LIVE-VERIFIED` (confirmed against a real run),
`FIXED` (assertion changed, re-verified green), `NO CHANGE NEEDED` (discussed, found safe as
written), `DEFERRED` (real issue, deliberately not tackled now).

---

## Background: what actually changed, precisely

Six tools (`create_invoice`, `create_transaction_account`, `create_combo_document`,
`update_client`, `get_client_details`, `list_invoices` for multi-word `client_name` only) now
require `name_resolved: bool` and do **only** an exact, word-order-independent lookup via
`_require_resolved_client`:
- `name_resolved` not `True` → returns an ordinary string, `format_name_not_resolved()`
  ("יש לפנות תחילה לכלי resolve_client_name..."), **`error=None`** — a brand-new failure mode
  that didn't exist before tonight.
- `name_resolved=True` but no exact match → raises `ClientNotFoundError`, caught by
  `server.py`'s error boundary, surfaces as `format_client_not_found()` text — **also
  `error=None`** at the `mcp_calls` level (confirmed in the prior session: the raise/return
  distinction has no observable effect above morning-mcp-app's own `errors.py`).
- `name_resolved=True` and exact match → tool proceeds normally.

So **`call["error"] is None` no longer implies success** for any of these six tools — same
class of bug already found and fixed (pre-pivot) in `test_denidin_approval_content_and_vat_e2e.py`
and `test_denidin_morning_invoice_creation_e2e.py` via the `_is_genuine_document_creation`
helper (checks `output.startswith("חשבונית #")` — valid for all three creation tools, confirmed
live this session for `create_transaction_account` too).

**Not gated, unaffected**: `add_client` (new client, nothing to resolve), `list_clients`
(browsing filter), `get_invoice_details`/`get_financial_summary` (invoice-id/date based, not
client-name based), `create_receipt`/`create_credit_note`/`close_transaction_account` (Group B
tools — take `original_invoice_id`, not a client name; bugfix-038 territory, separate).

---

## S1 — 🔴 `OPENAI_ASSISTANT_INSTRUCTIONS` doesn't teach the new flow, may actively contradict it

**File**: `apps/morning-mcp-app/tests/e2e_helpers.py:45-65`
**Affects**: every test in `apps/morning-mcp-app/tests/billed/test_openai_invokes_mcp_e2e.py`
that touches a gated tool — `test_openai_invokes_create_invoice_via_remote_mcp`,
`test_openai_created_invoice_is_signed_per_real_morning_api`,
`test_openai_asks_for_confirmation_on_client_name_variant_lookup`,
`test_openai_reports_no_invoice_when_client_truly_does_not_exist`.

This system prompt (separate from denidin-app's `runtime_constitution.md` — this file drives
OpenAI directly against the MCP server, proving the raw protocol works over the public
internet, independent of denidin-app) never mentions `resolve_client_name`, and says the
opposite of the new required order: *"if a client name is given, do not ask whether that
client already exists or should be created first; just call the document-creation tool
directly."*

**Mitigating factor**: MCP tool schemas (built from each tool's own docstring, which does say
"MUST call this first") reach the model independently of this instructions string. The model
may self-discover the right order from the tool description alone. **This is a real unknown,
not a certainty from static reading — needs a live run before any change is made.**

**Risk if wrong**: not a silent false-positive — these tests independently verify against the
real Morning sandbox (`found` checks), so a genuine failure here would show up as a real,
loud test failure, not a false green.

**Status**: LIVE-VERIFIED, NO CHANGE NEEDED (2026-08-12). Ran
`test_openai_invokes_create_invoice_via_remote_mcp` unmodified. Passed. Confirmed via
morning-mcp-app's own container log the model self-discovered the new order entirely from the
tool's own MCP description, with zero help from `OPENAI_ASSISTANT_INSTRUCTIONS`:
```
TOOL CALL resolve_client_name args=('Test Corp DENIDIN_OPENAI_E2E_1786523123',)
TOOL OK resolve_client_name result_chars=67
TOOL CALL create_invoice args=('Test Corp DENIDIN_OPENAI_E2E_1786523123', 50.0, ..., True, True)
AUDIT create_invoice OK ... document={'number': 51920, ...}
```
User's call (2026-08-12): this file deliberately carries no WhatsApp/turn/flow concepts by
design (it proves the raw MCP protocol works, independent of denidin-app) — leave
`OPENAI_ASSISTANT_INSTRUCTIONS` untouched rather than add `resolve_client_name` to its tool
enumeration for completeness, since the passing test already proves it isn't needed.

---

## S2 — 🟠 Single-shot `error is None` checks on gated tools, same false-positive class already fixed elsewhere

No shape-based check (`_is_genuine_document_creation`-equivalent) guards these — a "please
resolve first" or "not found" refusal would pass `error is None` silently.

| # | File | Line(s) | Detail |
|---|---|---|---|
| S2a | `test_denidin_morning_invoice_lifecycle_e2e.py` | 122-123 | direct assert, `create_invoice` |
| S2b | `test_denidin_morning_invoice_lifecycle_e2e.py` | 328-329 | direct assert, `create_transaction_account` |
| S2c | `test_denidin_morning_invoice_lifecycle_e2e.py` | 89 (`_seed_fresh_invoice`) | **chokepoint helper** — feeds `test_godfather_marks_invoice_paid_via_whatsapp`, `test_godfather_cancels_invoice_via_whatsapp`, `test_godfather_declines_invoice_cancellation`, `test_godfather_marks_already_paid_credit_invoice_as_paid_is_rejected` |
| S2d | `test_denidin_morning_invoice_lifecycle_e2e.py` | 326 (`_seed_transaction_account_invoice`) | **chokepoint helper** — feeds `test_godfather_marks_transaction_account_invoice_paid_via_whatsapp`, `test_godfather_declines_marking_transaction_account_invoice_paid` |
| S2e | `test_denidin_morning_list_invoices_e2e.py` | 577-578 | seed step, `create_invoice`, inside `test_godfather_searches_invoice_by_number_finds_it` |
| S2f | `test_denidin_morning_client_management_e2e.py` | 267 | `test_godfather_updates_client_via_whatsapp` — real risk: if the ASK-turn proposal didn't already carry a resolved name, the APPROVE-turn's actual execution could hit the procedural refusal and this assertion wouldn't catch it |
| S2g | `test_denidin_morning_document_creation_e2e.py` | 91-92 (`_seed_fresh_invoice_and_get_number`) | **chokepoint helper**, `create_invoice` — also parses the invoice number out of the output text, which would itself likely fail loudly (not silently) on a refusal string |
| S2h | `test_denidin_morning_document_creation_e2e.py` | 140-149 | `create_transaction_account`, `test_godfather_creates_transaction_account_via_whatsapp` |
| S2i | `test_denidin_morning_document_creation_e2e.py` | 203-217 | `create_combo_document`, `test_godfather_creates_combo_document_via_whatsapp` |
| S2j | `test_denidin_morning_invoice_creation_e2e.py` | 146 | `test_godfather_creates_invoice_via_whatsapp` |
| S2k | `test_denidin_morning_invoice_creation_e2e.py` | 246 | `test_godfather_approval_survives_intervening_small_talk` |
| S2l | `test_denidin_morning_invoice_creation_e2e.py` | 465 | `test_create_document_for_existing_client_happy_path` — **already known-red for an unrelated reason (Hebrew geresh normalization bug), not yet fixed; this finding rides along on the same line** |
| S2m | `expensive/test_ledger_event_capture_e2e.py` | 759 | A1-T1's `create_combo_document` check. **Passed 2026-08-10 — before tonight's architecture pivot.** Needs re-verification, not assumed still-green. |
| S2n | `expensive/test_group_b_reference_approval_e2e.py` | 230 | seed step, `create_invoice`. The test itself is already known-red per bugfix-038 (unrelated reason — `create_receipt` reference-data gap) — this finding is about the seed step specifically, which executes before that known-red assertion is even reached. |

**Status**: OPEN (all)

---

## S3 — 🟡 Flow-shape tension: tests presume the OLD architecture for `get_client_details`/`update_client`

| # | File | Test | Detail |
|---|---|---|---|
| S3a | `test_denidin_morning_client_management_e2e.py` | `test_godfather_get_client_details_discloses_first_name_prefix_match` (~line 456) | Presumes `get_client_details` itself does prefix-matching + discloses which client it found. Confirmed by reading source: `get_client_details` now hardcodes `is_exact_match=True` — that job belongs entirely to `resolve_client_name` now. |
| S3b | `test_denidin_morning_client_management_e2e.py` | `test_godfather_update_client_discloses_family_name_prefix_match_before_approval` (~line 497) | Same premise, for `update_client`'s pre-approval disclosure. |

**Why not necessarily broken**: both assertions only check that the resolved full name
*appears somewhere in the reply* — and `resolve_client_name`'s own "did you mean X?"
confirmation question also contains that full name (`format_client_name_confirmation_question`).
These may keep passing by coincidence, through a different mechanism than their docstrings
describe. Genuinely needs a live run to know either way, not a static-read call.

**Status**: OPEN

---

## S4 — 🟢 Checked and ruled safe (no action needed, listed for completeness)

- `test_godfather_gets_client_details_via_whatsapp` — asserts on final reply content
  (`client_name in response`, `seed_email in response`), not intermediate call success; its own
  docstring explains why. Robust by design against this whole bug class.
- `test_create_document_t1_single_letter_added_to_stored_name` /
  `test_create_document_t2_single_letter_removed_from_stored_name` — already routed through
  `_run_similarly_named_client_flow`/`_assert_similarly_named_client_flow_succeeded`, which
  already use `_is_genuine_document_creation`.
- `test_a_client_qualified_by_its_tax_id_still_resolves` — already fixed **and live-verified
  this session** (see conversation: real `list_clients` → `resolve_client_name` →
  `create_transaction_account` trace captured in `logs/test_logs/`).
- `add_client`, `list_clients`, `get_invoice_details`, `get_financial_summary`,
  `create_receipt`, `create_credit_note`, `close_transaction_account` calls throughout every
  file — none of these tools take `name_resolved`/go through the new gate.
- `test_denidin_vcf_contact_e2e.py`'s `add_client` checks (lines 205, 268) — safe, same reason.

**Status**: NO CHANGE NEEDED (all)

---

## Confirmed, unrelated to tonight's pivot, already tracked elsewhere

- `test_create_document_for_existing_client_happy_path` — still red (Hebrew-geresh
  normalization: Morning stores `ריצ'רד` as `ריצ׳רד`), unfixed. `_normalize_hebrew_geresh`
  helper exists in `denidin_mcp_e2e_helpers.py` but isn't wired into any of its 5 known call
  sites yet (this test's line 484, plus `test_denidin_morning_invoice_creation_e2e.py:703`,
  `test_denidin_morning_client_management_e2e.py:106,163`, `test_denidin_morning_list_invoices_e2e.py:603`).
- `max_attempts` in `_fresh_nonexistent_client_name` — reverted to 5 per explicit user
  instruction (2026-08-12); the underlying freshness-check-exhaustion question is still open,
  unresolved, needs a real decision (bigger name pool vs. redefined freshness check vs.
  something else) rather than a bigger retry budget.

---

## Root-cause fix discovered and implemented while discussing S2 (2026-08-12)

Before assessing S2 item-by-item, the user pushed back hard on a wrong claim made mid-discussion
(that a "please resolve first" refusal was a legitimate third outcome, neither success nor
failure): **"That is NOT the confirmed intent. The tool can succeed and it can fail. There is
no in the middle!"** Investigating this properly surfaced a real, root-cause-level defect in
tonight's own overnight work, not just a test-assertion gap — and fixing it changes the
analysis for every S2 item below.

### What was actually wrong

`_require_resolved_client` (the gate shared by all six client-name-consuming tools) raised
`ClientNotFoundError` for a genuine no-match, correctly - but for the "caller skipped
`resolve_client_name`" case, it returned an ordinary string (`format_name_not_resolved()`) with
no error attached. **This is the exact same silent-failure shape bugfix-028 B4(c) exists to
kill** (the ₪40,000-approved-8x-created-0x incident), just reintroduced in a new spot the
overnight session didn't apply the same principle to.

### Two separate, both-real, both-fixed problems

1. **Even a genuinely raised exception never reached the AI as a real failure at all.**
   `server.py`'s `_call_with_error_boundary` caught every exception and returned it as an
   ordinary string - MCP's real `isError` protocol flag was never set, previously confirmed
   dead in the prior session's own investigation ("the raise/return distinction has zero
   observable effect"). **That conclusion was itself wrong** - it was reached by testing only
   the "caught and converted to text" path, never a genuinely uncaught one. Verified for real
   (throwaway FastMCP server + real MCP client, no mocking): a raised exception that reaches
   FastMCP itself **does** set `isError=True` automatically - and further, a tool can `return`
   (not raise) an explicit `CallToolResult(isError=True, content=[...])` and get full control
   of both the flag and the exact friendly wording, with none of FastMCP's own auto-generated
   `"Error executing tool X: <raw message>"` prefix. One real landmine found along the way:
   FastMCP forbids declaring a tool's return type as `Union[str, CallToolResult]` (raises
   `InvalidSignature` at registration), and a bare `-> str` annotation silently mangles a
   returned `CallToolResult` into a confusing Pydantic validation error unless
   `structured_output=False` is passed to `@mcp.tool()`. Both confirmed via a real, running
   server + real client, not read from docs.
2. **The "not resolved" case never raised in the first place.** Fixed to match `ClientNotFoundError`'s
   already-correct shape: two outcomes only, succeed or raise. A new `ClientNameNotResolvedError`
   (distinct from `ClientNotFoundError` - user: "you can have many exception classes for the
   different kinds of errors that can happen, if it's meaningful, I think it is") is raised
   instead of returned.

### What changed (`apps/morning-mcp-app/src/denidin_mcp_morning/`)
- `server.py` - `_call_with_error_boundary` now returns `CallToolResult(isError=True, ...)` on
  any exception (not a plain string); all 15 `@mcp.tool()` decorators get `structured_output=False`.
- `tools.py` - `_require_resolved_client` returns a plain `Client` or raises; `ResolvedClient`
  NamedTuple removed (no longer needed - there's no third outcome to carry); all six call sites
  simplified accordingly. New `ClientNameNotResolvedError`.
- `errors.py` - new branch maps `ClientNameNotResolvedError` to its own specific message, same
  pattern as the existing `ClientNotFoundError` branch (both are `ValueError` subclasses, so
  both need a branch ABOVE the generic `ValueError` catch-all or they'd lose their specific text).

### Tests
6 new/updated unit tests (`test_server.py` x4, `test_errors.py` x1, plus the 5 pre-existing
`_not_resolved_refuses_without_any_lookup` tests across `test_tools_resolved_client_gate.py`/
`test_tools_client_management.py`/`test_tools_document_creation.py`/`test_tools_list_invoices.py`
updated from "expect returned text" to "expect a raise" - **273/273 unit passing**. 2 new/strengthened
real-protocol integration tests in `test_mcp_server_e2e.py` (asserting the actual `isError` flag
over a live server+client, no mocking). Found and fixed 2 unrelated pre-existing integration-test
gaps this surfaced (`test_add_client_tool_normalizes_and_persists_phone`,
`test_list_invoices_shows_receipt_document_type` - both called a gated tool without
`name_resolved=True`, a latent test bug, not a fix-caused one) plus 4 more integration tests in
`test_morning_sandbox_*` files updated the same way as the unit tests. Every touched integration
file individually verified green; a full-bundle `tests/integration/` run in one process hit the
documented sandbox 403 burst issue (not a code problem - confirmed by isolating one "failing"
file alone and it still 403s, from today's unusually high real-call volume) and was not chased
further, per the handoff's own prior finding that a single-process full green pass is "a
nice-to-have, not a blocker."

### Still open, blocks re-assessing S2
Whether OpenAI's Responses API actually threads MCP's `isError` through to the `mcp_call.error`
field `ai_handler.py` reads (`item.error`) on the **denidin-app** side is still unverified - the
FastMCP/MCP-library half is now proven; the OpenAI half is not. This determines whether S2's
original concern (`error is None` unreliable on the six gated tools) is now moot, or still live.
Needs one real, cheap `billed`-tier check before going through S2 item-by-item.

## OpenAI-side link verified (2026-08-12) - S2's original concern is now moot

Rebuilt/redeployed morning-mcp-app dev (code-only change, this app alone). One real, direct,
cheap OpenAI Responses API call against the live rebuilt server (forcing the "not resolved" path
explicitly rather than relying on model judgment, for a deterministic result) - confirmed:

```
error: {'type': 'mcp_tool_execution_error', 'content': [{'text': '<our friendly Hebrew text>'}]}
output: None
status: 'failed'
```

**`mcp_call.error` is populated (not None) on a real failure.** `ai_handler.py`'s
`mcp_calls[i]["error"]` is a reliable success/failure signal again, exactly as originally
designed - **every S2 item's original concern (that a "please resolve first"/"not found" refusal
could pass an `error is None` check) is now moot at the source.** No per-test assertion patching
needed for S2's items.

## denidin-app-side consequence found and fixed (2026-08-12)

Checking "everything that uses the new code" (user's explicit direction) surfaced one real
production-code (not test) regression risk, entirely within denidin-app: `output` is now `None`
on a failed call (the reason moved to `.error`) - `_resolve_pending_approval`'s B4(b)
"approved tool never ran" handler (`ai_handler.py`) extracted the failure reason from `.output`
only, so it would have silently gone back to a fully generic message with the real reason
dropped - the exact same silent-failure shape bugfix-028 exists to kill, one layer up from where
it was originally found.

**Fixed**: new `AIHandler._extract_mcp_error_text` static helper (pulls the text out of the
`{"type": "mcp_tool_execution_error", "content": [{"text": ...}]}` shape, confirmed live above),
used as a fallback when `.output` is empty. One new unit test
(`test_failure_detail_from_a_real_mcp_error_field_is_surfaced` in
`test_ai_handler_zero_execution_detection.py`) - the existing `.output`-based test for the OLD
shape still passes unchanged (backward compatible). **denidin-app unit+integration: 794/794
passing** (793 + 1 new).

Also checked `runtime_constitution.md` for staleness (grepped every `error`/`refus`/`isError`
mention): both relevant sections describe model-observable behavior only (what the model sees,
never the Python raise/return mechanism) and remain accurate - if anything, now more reliably
true, since the model gets an unambiguous failure signal instead of text it had to interpret.
**No constitution changes needed.**

**Not yet done**: denidin-app's own dev container hasn't been rebuilt with this fix (only
morning-mcp-app was rebuilt, per the user's explicit "morning-mcp-app only" answer earlier) -
this new `ai_handler.py` code isn't live yet. Needs its own separate rebuild/redeploy approval
before it can be verified against a real live turn.

## S2 closed (2026-08-12) - live spot-check confirms the root-cause fix, no per-item work needed

denidin-app dev rebuilt/redeployed with the `ai_handler.py` fix. Spot-check attempt 1
(`test_godfather_marks_invoice_paid_via_whatsapp`, uses the S2c chokepoint) failed - but for a
completely unrelated, pre-existing reason (the model correctly asked for a payment date per
`create_receipt`'s A3 behavior, which this test's script never supplies - nothing to do with
client-name resolution, untouched by tonight's work). Attempt 2
(`test_godfather_cancels_invoice_via_whatsapp`, same S2c chokepoint, no A3 involvement) **PASSED**,
with the full trace confirming the fix live end-to-end:
```
resolve_client_name → create_invoice(name_resolved=true) → חשבונית #51976   [seed]
resolve_client_name → list_invoices → get_invoice_details → create_credit_note → חשבונית זיכוי מספר 70250   [cancel]
```
All clean, no errors, real documents created and verified. **S2 is closed** - every item in the
original table (S2a-S2n) needs no individual fix; the root-cause fix (this section + the two
above) resolves the whole category at once.

## S3 closed (2026-08-12) - both tests were obsolete, replaced with tests of the correct new flow

User's direction: both S3 tests were obsolete (asserted a disclosure mechanism that no longer
exists), and should be replaced - not patched - with tests of the actual, correct flow: one
piece of missing information (exact client identity) that the AI asks to confirm, the user
confirms, and the action is then genuinely performed.

**Confirmed via full code trace first** (not assumed): all six gated tools funnel through the
exact same `_require_resolved_client` -> `_resolve_exact_client_name` path - zero fuzzy logic of
their own, `get_client_details`/`update_client` identical in this respect to the other four. The
only place fuzzy/word-growth matching still happens is inside `resolve_client_name` itself.
`list_clients`'s own direct `search_clients` calls are the separate, always-existed plain-browsing
feature, correctly out of scope.

**Replaced** (`test_denidin_morning_client_management_e2e.py`):
- `test_godfather_get_client_details_discloses_first_name_prefix_match` ->
  `test_godfather_get_client_details_resolves_ambiguous_first_name_prefix_after_confirmation` -
  two real turns: ask (ambiguous prefix) -> `resolve_client_name` confirmation question, zero
  `get_client_details` calls yet; confirm ("כן") -> real `get_client_details` call, verified via
  the seeded email appearing in the final reply (not just the name echoed back).
- `test_godfather_update_client_discloses_family_name_prefix_match_before_approval` ->
  `test_godfather_update_client_resolves_ambiguous_family_name_prefix_after_confirmation` - three
  real turns (identity confirmation and mutation approval are separate steps): ask (ambiguous) ->
  confirmation question, zero `update_client` activity; confirm ("כן") -> the real `update_client`
  pending-approval prompt (still not executed); approve ("כן") -> genuine execution, independently
  verified via a follow-up `get_client_details` call showing the new phone.

Both wired through `_normalize_hebrew_geresh` (already built, previously unwired) for their
`full_name in response`-style checks, after a live run caught the already-known geresh bug for
real (a randomly-drawn family name containing an apostrophe) - these two new tests are now
immune to it regardless of whether the other 5 known call sites ever get fixed.

**Live verification status**: `get_client_details` version - **fully passed**, clean trace
matching the design exactly (confirmation question -> confirm -> real detail retrieval with
email proof). `update_client` version - mechanics confirmed correct as far as it got (ask-turn
confirmation question, correctly geresh-normalized), but full end-to-end live confirmation was
blocked by accumulated session noise on the shared `GODFATHER_CHAT_ID` from this session's very
high real-call volume today (not a bug - a pre-existing hazard of this suite's fixed shared test
identity + disk-persisted session across separate pytest invocations). User's call: accept as
sufficiently verified rather than spend further real API calls chasing a polluted session
tonight - both tests' designs are symmetric and the shared mechanism is already proven.

## Sweep status: CLOSED

S1 (moot, live-verified) + S2 (root cause fixed, live-verified) + S3 (obsolete tests replaced,
live-verified) + S4 (always safe, no action needed) = every item from the original 2026-08-12
code-eye sweep is now resolved. Remaining work on this bugfix branch is outside this sweep's
scope (see `bugfix-028-HANDOFF.md`'s "Exact next steps" - reviewing/committing the diff, the
still-open `max_attempts`/geresh-other-call-sites items, and resuming the wider billed-test
sweep).
