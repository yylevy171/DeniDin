# Data Model: Client-name resolution architecture fix

## New entity: `resolve_client_name` (MCP tool)

```python
def resolve_client_name(client: MorningClient, name: str) -> str:
    """Resolve a free-text client name to Morning's real stored name and
    return a Hebrew resolution report. THE canonical, sole entry point for
    fuzzy/word-growth client-name resolution (built on `resolve_client_by_name`,
    bugfix-039 round 3) - supersedes calling that engine directly from any
    caller-facing tool.

    MCP tool: resolve_client_name. Read-only - no approval wait
    (REQ-CLIENT-008). The model MUST call this first, before any other tool
    that needs one specific client, whenever a user's request references a
    client by name - then pass the CONFIRMED, EXACT name back into the
    target tool together with `name_resolved=True`.

    Four outcomes, each a single Hebrew string:
    - Exactly one EXACT match -> discloses the stored name; use it verbatim.
    - Exactly one NON-exact match -> a closed yes/no confirmation question
      (format_client_name_confirmation_question) - same contract every
      other tool already used for this case.
    - More than one match -> an ambiguous-candidates listing
      (format_ambiguous_clients_message), Levenshtein-ordered.
    - Zero matches -> a friendly "not found" message (format_client_not_found).
      Unlike the six tools below, this does NOT raise ClientNotFoundError -
      it is the exploratory FIRST call, before any tool has been asked to
      act on a specific client, so a genuine zero-match here is an
      ordinary, expected outcome of exploring a name, not a failed
      mutation/lookup attempt.

    Args:
        client: An authenticated MorningClient (injected).
        name: Free-text client name (apostrophe/geresh-normalized before
            resolution - see `_normalize_hebrew_geresh`).

    Returns:
        A Hebrew string: the resolved exact name (never the client_id -
        REQ-CLIENT-018), a confirmation question, an ambiguous-candidates
        list, or a "not found" message.
    """
```

## Changed entities: the six name-resolving tools

Each gains `name_resolved: bool = False`, appended as the **last** parameter (never inserted
mid-signature — every existing positional test call stays syntactically valid, and every call site
that doesn't explicitly opt in now hits a visible, correct refusal instead of a silently-wrong
argument shift):

```python
def get_client_details(client: MorningClient, name: str, name_resolved: bool = False) -> str: ...

def list_invoices(
    client: MorningClient, status: Optional[str] = None, from_date: Optional[str] = None,
    to_date: Optional[str] = None, client_name: Optional[str] = None, number: Optional[str] = None,
    token_budget: int = _LIST_INVOICES_TOKEN_BUDGET, name_resolved: bool = False,
) -> str: ...

def create_invoice(
    client: MorningClient, client_name: str, amount: float, description: str,
    due_date: Optional[str] = None, vat_included: bool = True, name_resolved: bool = False,
) -> str: ...

def create_transaction_account(
    client: MorningClient, client_name: str, amount: float, description: str,
    vat_included: bool, due_date: Optional[str] = None, name_resolved: bool = False,
) -> str: ...

def create_combo_document(
    client: MorningClient, client_name: str, amount: float, description: str, vat_included: bool,
    payment_date: str, payment_method: str = _DEFAULT_PAYMENT_METHOD, bank_number: Optional[str] = None,
    bank_branch: Optional[str] = None, bank_account: Optional[str] = None,
    transaction_reference: Optional[str] = None, name_resolved: bool = False,
) -> str: ...

def update_client(
    client: MorningClient, name: str, new_name: Optional[str] = None, email: Optional[str] = None,
    phone: Optional[str] = None, tax_id: Optional[str] = None, name_resolved: bool = False,
) -> str: ...
```

`list_invoices`'s single-word `client_name` carve-out is **unchanged and ungated** — it was never
"resolve one specific client," it's a deliberate substring search (its own docstring says so);
`name_resolved` only applies when `len(client_name.split()) > 1`.

## New internal shape (replaces `ClientResolution`/`_resolve_client_for_document_creation`, both deleted)

```python
class ResolvedClient(NamedTuple):
    """Result of the exact-only, name_resolved-gated lookup shared by the
    six tools that used to do their own fuzzy resolution. Exactly one of
    (client, refusal_message) is set. refusal_message is never a domain
    question here (no "did you mean"/"ambiguous" - that's resolve_client_name's
    job now) - it is only the not-yet-resolved procedural refusal."""
    client: Optional[Client]
    refusal_message: Optional[str]


def _resolve_exact_client_name(client: MorningClient, name: str) -> Optional[Client]:
    """Direct, exact (word-order-independent) lookup only - Step 0 of
    resolve_client_by_name, factored out and reused directly: one Search
    Clients call on the literal name, accepted only if it's a unique client
    whose stored name is a word-for-word (order-independent) match. Never
    grows letters, never picks a 'closest' candidate."""
    name = _normalize_hebrew_geresh(name)
    resolved, _ = _resolve_client_by_name(client, name)
    if resolved is not None and _bag_equal_words(name, resolved.name):
        return resolved
    return None


def _require_resolved_client(
    client: MorningClient, client_name: str, name_resolved: bool, tool_name: str
) -> ResolvedClient:
    """The one gate all six tools share.

    Hard gate: name_resolved must be exactly True, or this refuses
    IMMEDIATELY, without attempting any Morning lookup at all - forcing the
    model through resolve_client_name rather than letting a stale/guessed
    name get lucky against Morning by accident. Once True is asserted, this
    does ONLY an exact, word-order-independent lookup - no fuzzy/letter
    growth, no disambiguation dialogue (that already happened, or should
    have, in resolve_client_name). A multi-candidate OR zero-candidate
    result under this exact-only mode are treated identically -
    ClientNotFoundError - since the correct recovery for either is the
    same: call resolve_client_name and retry.
    """
    if not name_resolved:
        log_refusal(tool_name, "name_not_resolved", client_name=client_name)
        return ResolvedClient(client=None, refusal_message=format_name_not_resolved())
    resolved = _resolve_exact_client_name(client, client_name)
    if resolved is None:
        _raise_client_not_found(tool_name, client_name)
    return ResolvedClient(client=resolved, refusal_message=None)
```

Call-site pattern in each of the six tools mirrors today's `_resolve_client_for_document_creation`
usage (minimal diff):

```python
resolution = _require_resolved_client(client, client_name, name_resolved, "create_invoice")
if resolution.refusal_message is not None:
    return resolution.refusal_message
payload = _build_create_invoice_payload(resolution.client.id, amount, description, due_date, vat_included)
```

`get_client_details` drops its `is_exact_match` branching entirely (always `True` now — the non-exact-
disclosure case moved to `resolve_client_name`):

```python
resolution = _require_resolved_client(client, name, name_resolved, "get_client_details")
if resolution.refusal_message is not None:
    return resolution.refusal_message
return format_client_details(resolution.client, is_exact_match=True)
```

`list_invoices`'s multi-word branch shrinks from its current ~35-line resolve/ask/ambiguous/raise
fan-out to:

```python
if client_name and len(client_name.split()) > 1:
    resolution = _require_resolved_client(client, client_name, name_resolved, "list_invoices")
    if resolution.refusal_message is not None:
        return resolution.refusal_message
    client_name = resolution.client.name
```

## New formatters (`formatters.py`) — one new, three reused as-is

```python
def format_client_name_resolved(resolved_name: str) -> str:
    """Hebrew confirmation for resolve_client_name's EXACT-match case - the
    model should copy resolved_name verbatim into whichever tool it calls
    next, together with name_resolved=True. Deliberately plain/short (no
    client_id, REQ-CLIENT-018) - quoted, matching the existing convention
    (format_invoice_confirmation's 'לקוח: "..."') that names appear in
    "quotes" specifically so the model can spot-and-copy them as one atomic
    token."""
    return f'שם הלקוח המדויק במורנינג: "{resolved_name}"'


def format_name_not_resolved() -> str:
    """Hebrew message when a client-resolving tool is called with
    name_resolved not True. Returned as ORDINARY tool output, never raised -
    this is a procedural instruction for the calling model to act on
    immediately in the same turn (call resolve_client_name, then retry),
    not a domain question meant for the end user to see."""
    return (
        "יש לפנות תחילה לכלי resolve_client_name עם שם הלקוח, לוודא שם מדויק "
        "התואם למאוחסן במורנינג, ולקרוא לכלי הזה שוב עם name_resolved=true "
        "והשם המדויק שהוחזר."
    )
```

`resolve_client_name` reuses `format_client_name_confirmation_question`, `format_ambiguous_clients_
message`, `format_client_not_found` unchanged.

## `server.py` wiring

```python
@mcp.tool()
def resolve_client_name(name: str) -> str:
    """Resolve a client name to Morning's exact stored name before calling
    any other tool that needs one specific client (get_client_details,
    list_invoices with a client_name filter, create_invoice,
    create_transaction_account, create_combo_document, update_client).

    ALWAYS call this first whenever a user's request references a client by
    name - even a name you believe is already exact - then pass the EXACT
    name this returns, verbatim, into the target tool together with
    name_resolved=True. Those six tools no longer do their own fuzzy
    matching: they require name_resolved=True and refuse immediately,
    without attempting any lookup, if it isn't set.
    """
    return _call_with_error_boundary(tools.resolve_client_name, morning_client, name)
```

Each of the six existing `@mcp.tool()` wrappers gains `name_resolved: bool = False` appended to its
own signature, a one-line docstring addition ("REQUIRES name_resolved=True — call resolve_client_name
first…"), and the extra positional arg threaded into its `_call_with_error_boundary(...)` call.

## Companion change: `apps/denidin-app/src/handlers/ai_handler.py`

```python
NO_APPROVAL_MCP_TOOLS = (
    "list_invoices", "get_invoice_details", "get_financial_summary",
    "download_invoice_pdf", "list_clients", "get_client_details",
    "resolve_client_name",
)
```

## Full test-impact enumeration

### `morning-mcp-app/tests/unit/`
- `test_tools_client_resolution.py` — all 7 tests target `_resolve_client_for_document_creation`
  (deleted). Replace with tests for `resolve_client_name` (exact/non-exact/ambiguous/zero, reusing the
  same fixtures) and for `_require_resolved_client`/`_resolve_exact_client_name` (name_resolved=False →
  assert zero `search_clients` calls attempted; True+exact→success; True+non-exact-only→
  ClientNotFoundError; True+zero→ClientNotFoundError; True+multi-candidate-exact-string→
  ClientNotFoundError).
- `test_tools_client_management.py` — non-exact/ambiguous coverage relocates to `resolve_client_name`
  tests: `test_get_client_details_ambiguous_lists_candidates_without_leaking_client_id`,
  `test_get_client_details_non_exact_match_discloses_resolved_name`,
  `test_update_client_ambiguous_lists_candidates_without_mutating`,
  `test_update_client_non_exact_match_asks_for_confirmation_and_updates_nothing`,
  `test_update_client_exact_match_uses_standard_phrasing`,
  `test_get_client_details_exact_match_uses_standard_phrasing`. Remaining tests
  (`test_get_client_details_not_found_raises`, `test_update_client_not_found_raises`, all
  normalization/validation tests) gain `name_resolved=True`.
  `test_resolve_client_for_document_creation_resolves_apostrophe_query_against_geresh_stored_name`
  relocates to `_resolve_exact_client_name` tests. `add_client`/`list_clients`-only tests unaffected.
- `test_tools_document_creation.py` — `test_create_transaction_account_returns_hebrew_confirmation`,
  `test_create_transaction_account_refuses_when_client_not_found`,
  `test_create_combo_document_returns_hebrew_confirmation` gain `name_resolved=True`.
  `test_create_combo_document_refuses_when_client_ambiguous` — **behavior change**: under exact-only
  mode, multi-candidate collapses into `ClientNotFoundError` like zero-candidate; rewrite the
  assertion. Group B tests (credit_note/receipt/close_transaction_account) unaffected — resolve via
  `original_invoice_id`, never by name.
- `test_tools_list_invoices.py` — `test_list_invoices_multi_word_client_name_not_found_raises` (added
  this session) gains `name_resolved=True`; single-word-only tests unaffected.

### `morning-mcp-app/tests/integration/` (real sandbox)
- `test_morning_sandbox_create_invoice_client_resolution.py` — non-exact/single-letter-added/removed/
  ambiguous tests relocate to a new `test_morning_sandbox_resolve_client_name_tool.py`; exact-match/
  zero-match tests on `create_invoice` itself rewritten for `name_resolved=True` plus a new "refuses
  without any Morning call when omitted" test.
- `test_morning_sandbox_client_not_found_is_an_error.py` — the `_raises_when_the_client_cannot_be_
  resolved` tests gain `name_resolved=True`; `test_a_decorated_client_name_asks_for_confirmation`
  imports `_resolve_client_for_document_creation` directly — rewrite against `resolve_client_name`/
  `resolve_client_by_name`.
- `test_morning_sandbox_get_client_details_tool.py` — non-exact/exact-disclosure tests relocate;
  remaining gain `name_resolved=True`.
- `test_morning_sandbox_update_client_tool.py` — ambiguous/non-exact/confirmed-retry/exact-phrasing
  tests relocate; remaining gain `name_resolved=True`.
- `test_morning_sandbox_list_invoices_tool.py` — the name-prefix-variant confirmation test relocates;
  remaining client_name tests gain `name_resolved=True`/rewrite.
- `test_morning_sandbox_document_creation_tools.py` — happy-path `create_transaction_account`/
  `create_combo_document` tests gain `name_resolved=True`.
- `test_morning_sandbox_group_b_client_preservation.py`, `test_morning_sandbox_add_client_tool.py`,
  `test_morning_sandbox_list_clients_tool.py` — unaffected.
- `test_mcp_server_e2e.py` — `EXPECTED_TOOL_NAMES` gains `"resolve_client_name"`; any live
  tool-invoking test in this file gains `name_resolved=True`.

### `denidin-app/tests/billed/` + `tests/expensive/` — **user-facing flow is a hard invariant, not a variable**

**Correction (2026-08-12, explicit user decision)**: billed/expensive tests represent real user
interactions and are "the beacons of truth" — their message sequences, prompts, turn counts, and "כן"
exchanges must NOT be altered by this change. `resolve_client_name` is an internal orchestration step
the model makes *within the same turn* (same as `list_clients` was observed doing in this session's own
live investigation run — an extra MCP call inside one turn, never a separate user-visible round-trip),
not a new conversational step, so nothing about what the human actually sees or types should change.

What CAN legitimately need fixing: **assertions that inspect `ai_response.mcp_calls`** — since a
`resolve_client_name` call may now appear in that list alongside whatever else happened in the turn,
and the "did you mean X?" confirmation-question output moves from living inside `create_invoice`'s own
`output` field to living inside a `resolve_client_name` call's `output` field instead. Any assertion
keyed to "the confirmation question is create_invoice's own output" needs updating to look at
`resolve_client_name`'s output instead; assertions counting/filtering `mcp_calls` by tool name may need
to account for the new tool name appearing. The actual text the user reads, and the number/order of
real WhatsApp messages exchanged, must be verified unchanged (re-run each rewritten test for real and
confirm this, not just assume it from the code).

- `test_denidin_morning_invoice_creation_e2e.py` — `test_create_document_for_existing_client_happy_
  path`, the non-exact-confirmation flow tests, `test_create_document_t1_single_letter_added_to_stored_
  name`, `t2_single_letter_removed`, and the four `test_create_document_for_new_client_*` tests likely
  need their `mcp_calls`-based assertions adjusted (per above) — audit each one against a real run
  before assuming which assertions actually need touching, don't rewrite speculatively.
- `test_denidin_morning_client_management_e2e.py` — same pattern: `test_godfather_update_client_
  ambiguous_name_creates_no_pending_approval`, `test_godfather_finds_client_via_hebrew_vowel_variant`,
  `test_godfather_get_client_details_discloses_first_name_prefix_match`, `test_godfather_update_client_
  discloses_family_name_prefix_match_before_approval` currently assert on the disclosing tool's own
  output — audit whether that's now `resolve_client_name`'s output instead.
  `test_client_role_gets_no_client_management_tools`/`test_blocked_role_gets_no_client_management_
  tools` unaffected — role gating is whole-server, not per-tool-name.
- `test_denidin_morning_list_invoices_e2e.py`, `test_denidin_morning_document_creation_e2e.py` — same
  audit-before-rewrite treatment.
- `tests/expensive/` mirrors — same treatment.
- `denidin_mcp_e2e_helpers.py` — no required change unless a genuinely new, reusable assertion pattern
  emerges from the audit above (e.g. a `_resolve_client_name_call_for(ai_response)` lookup helper) —
  add only once a real duplicated need is found, not speculatively.

Also found: a second constitution copy at `apps/denidin-app/test_data/constitution/runtime_
constitution.md` — no direct references found in tests/src; confirm live whether it's actually used
before Step 7, don't assume in-scope.
