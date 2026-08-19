# Research: Client-name resolution architecture fix

Each entry resolves one open question from `client-name-resolution-plan.md`'s design, grounded in
what the real code does today (read directly, not assumed) — per CONSTITUTION's "NO UNVERIFIED
THIRD-PARTY ASSUMPTIONS" rule extended to internal-code claims in this session's own practice.

## Decision 1: Where does resolution belong — inside each tool, or one upstream step?

**Decision**: One upstream step (`resolve_client_name`), called by the model before any other
client-name-consuming tool. The six tools that used to resolve internally become exact-match-only.

**Rationale**: Traced the actual documented history in `specs/done/bugfixes/bugfix-039-list-invoices-
skips-client-resolution.md` (round 2): the user's *original* intent was exactly this upstream-only
shape, but bugfix-039's round-2 session considered giving the create tools a `client_id` parameter (so
they could "always create" once resolved) and rejected it — not because upstream resolution was wrong,
but because passing `client_id` to the model violates REQ-CLIENT-018. That session then kept the
in-tool fuzzy mechanism as a *workaround* for the id-leak problem, conflating two separate questions
("where does resolution happen" and "how does the model refer to a resolved client without an id").
This bugfix separates them: resolution still happens upstream, but the "confirmed reference without an
id" problem is solved by passing the *exact name* (not an id) back into the target tool, which is
exactly what REQ-CLIENT-018 already allows (it forbids the id, not the name).

**Alternatives considered**:
- *Keep in-tool resolution, extend it to `get_client_details`/`list_invoices` too* (this session's own
  first attempt, before the architecture question was raised) — rejected: perpetuates "10 ways to do
  the same thing" (one fuzzy call site per tool) instead of one shared mechanism; makes every tool's
  contract implicitly stateful-feeling ("might ask a question, might create") when only one, dedicated
  tool needs that shape.
- *`client_id` parameter on the create/update tools* — rejected per the above (REQ-CLIENT-018).

## Decision 2: What tool does the resolving — repurpose `list_clients`, or a new dedicated tool?

**Decision**: New dedicated tool, `resolve_client_name`. `list_clients` stays a plain browsing/listing
tool, unchanged.

**Rationale**: Explicit user decision. Keeps `list_clients`'s existing contract (a plain Morning
prefix search, browsing many clients) uncoupled from `resolve_client_name`'s contract (resolving
exactly one specific client reference to a confirmed exact name) — the two are different operations
that happen to both start from a name string, and conflating them would make `list_clients`'s own
behavior harder to reason about (does a `name` filter now trigger fuzzy growth + confirmation
questions, or a plain filtered list? — ambiguous under a repurposed design, unambiguous with two
separate tools).

## Decision 3: `name_resolved` — plain boolean, or a stronger (token-based) enforcement mechanism?

**Decision**: Plain boolean (`name_resolved: bool = False`), hard-gated (the six tools refuse
immediately, attempting zero Morning calls, when it isn't `True`).

**Rationale**: Read every file under `apps/morning-mcp-app/src/denidin_mcp_morning/` — confirmed there
is no cache, session store, or per-conversation identity threaded through any of the 11 (soon 12) tool
signatures anywhere in this app. `MorningMCPConfig` (`config.py`) is a plain dataclass; `tools.py`
functions are pure, DI-based, no globals (CONSTITUTION §XVII). A token-based mechanism (`resolve_client_
name` mints an opaque, short-lived token; the six tools require it instead of a bare boolean) would
introduce this server's *first* stateful component, with no existing per-conversation identity to key
it by (unlike `denidin-app`'s own `PendingApprovalManager`, which is `chat_id`-keyed one layer up, at
the orchestration layer this server has no visibility into). The realistic failure mode this guards
against is a model carelessly skipping a step, not an adversarial actor defeating a security boundary
(these tools are internal, first-party, reachable only via DeniDin's own OpenAI-backed model over an
authenticated tunnel) — a hard-gated boolean plus audit logging (`log_refusal(tool_name,
"name_not_resolved", ...)`) gives materially the same practical protection for a fraction of the
complexity.

**Alternatives considered**:
- *Opaque resolution token* — rejected per the above; revisit only if production logs
  (`denidin-app`'s own captured `mcp_calls` sequence, `ai_handler.py`) ever show models actually
  asserting `name_resolved=True` without a preceding `resolve_client_name` call in the same turn.
- *No enforcement at all (just a strong constitution instruction)* — rejected: this repo's own
  history (bugfix-039's `list_invoices` incident, this session's investigation of bugfix-028's original
  ₪40,000 incident) shows prompt-only discipline is not reliable enough on its own for a correctness
  property this important; a code-level gate is the deciding difference between "usually resolves
  correctly" and "cannot silently mutate against an unresolved name."

## Decision 4: does `name_resolved=False` raise, or return a plain string?

**Decision**: Returns a plain string (`format_name_not_resolved()`), never raises.

**Rationale**: Directly verified `server.py`'s `_call_with_error_boundary` (lines ~114-148): it catches
every exception and maps it via `errors.py`'s `friendly_error_message`, which has a dedicated branch
only for `ClientNotFoundError` — a bare `ValueError` (or any other exception type) falls into the
generic branch and returns `"❌ הבקשה אינה תקינה. בדקו את הפרטים שסיפקתם."`, discarding whatever specific
message was raised with. If the `name_resolved` refusal were an exception, the model would have no
idea *what* was wrong or that it needs to call `resolve_client_name` — exactly the bug this session's
earlier work (unifying `ClientNotFoundError`'s message) was fixing for a different case. A plain
string return has no such translation step and reaches the model with its full, specific instruction
intact — the same pattern already proven correct for today's "did you mean X?"/ambiguous-candidates
cases (`ClientResolution.refusal_message`, being superseded by this change but validating the pattern).
`ClientNotFoundError` stays reserved for the one case it was built for: a genuine, no-mechanical-
recourse failure (bugfix-028 B4(c)'s founding incident — zero real candidates at all). A missing
`name_resolved` has an entirely mechanical recourse (call `resolve_client_name`, retry) — the same
category as "ambiguous" or "non-exact," never treated as a raised failure in this codebase.

## Decision 5: does the approval-gate list need a companion change?

**Decision**: Yes — `apps/denidin-app/src/handlers/ai_handler.py`'s `NO_APPROVAL_MCP_TOOLS` tuple must
add `"resolve_client_name"`.

**Rationale**: Directly verified `ai_handler.py` lines 97-118: `NO_APPROVAL_MCP_TOOLS`'s own comment
records a confirmed, empirical finding (2026-07-23, real E2E run) that a `require_approval` filter with
only an `"always"` key does **not** leave unlisted tools defaulting to no-approval —
`download_invoice_pdf` (not in `APPROVAL_REQUIRED_MCP_TOOLS`) still generated a pending-approval prompt
until it was added explicitly to `NO_APPROVAL_MCP_TOOLS`. An unlisted `resolve_client_name` would
reproduce that exact failure: every single resolution call would incorrectly stop for user approval,
defeating the entire point of it being a fast, read-only, always-first step.
