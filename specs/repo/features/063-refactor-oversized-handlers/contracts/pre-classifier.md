# Contract: Pre-Classifier Call

**Component**: `classify_capabilities()`, new function in `src/backbone/pre_classifier.py` (R1/R5)
— only ever called from the new orchestrator, never from `ai_handler.py`. The flag check that
decides whether this runs at all lives in `denidin.py`'s `initialize_app` (which implementation
gets constructed), not inside this function — by the time the new orchestrator exists at all, the
flag is already known to be on.

## Input
- `request: AIRequest` — the same object the main turn call receives (message text, chat_id,
  role, etc.). No new fields required on `AIRequest`; reused as-is by the new orchestrator.

## Behavior
1. Skip entirely and return `[]` if the user's role has zero `role_allowed_capabilities` (e.g.
   `blocked`) — no point classifying a turn that can't attach anything anyway.
2. Otherwise, issue one OpenAI Responses API call:
   - `instructions`: the Backbone's routing section (static, part of `config/backbone.md`) —
     lists all 6 `CapabilityTag`s with a one-line description each.
   - `input`: the turn's message content (text; media turns are out of scope — media messages
     never reach the turn-handling entry point per existing architecture, see CLAUDE.md "Message
     flow").
   - Structured output schema: `{"capabilities": array of enum(CapabilityTag)}` (see
     `data-model.md`'s `ClassificationResult`).
   - Reuses the same retry policy `ai_handler.py::_timed_llm_call` already implements (3
     attempts / 2s wait; rate-limit 3 / 5s) — reimplemented in the new module, not imported from
     `ai_handler.py` (keeps the two implementations independent, per R1).
3. On success: intersect the returned list with `role_allowed_capabilities(user.role)`, drop any
   unrecognized tag (log WARNING), return the filtered list.
4. On failure after retries: log ERROR, **fail open** — return `role_allowed_capabilities(user.role)`
   in full (i.e. every plugin the role could ever see gets attached) rather than `[]`. This
   guarantees a classifier outage degrades to today's "everything always loaded" behavior, never
   to a silent capability gap.

## Output
`List[CapabilityTag]` — see `data-model.md`.

## Non-goals
- Does not decide *tool* attachment directly — the new orchestrator's own tool-assembly step
  (structurally analogous to `ai_handler.py::_assemble_tools`, but new code) owns that, filtered
  by this function's result (a plugin not in the classified set contributes neither its
  constitution block nor its tool schemas to the turn).
- Does not run for the new orchestrator's own pending-approval resolution turn or button-tap
  resolution turn — those already know their own capability deterministically (resuming a
  specific pending action) and skip straight to attaching the relevant plugin, mirroring how
  `ai_handler.py::_resolve_pending_approval` et al. already skip general intent detection today.
- The accounting-reconciliation sweep's standalone OpenAI call (`accounting_reconciliation_service.py`)
  is **out of scope for this feature** — it is not part of either `AIHandler`'s or the new
  orchestrator's per-turn `get_response` path, and continues to build its own prompt exactly as
  today regardless of the flag.
