# Contract: Backbone Orchestration Loop (supersedes the retired `pre-classifier.md`)

**Component**: `src/backbone/orchestrator.py`'s `get_response()` (the new module's equivalent
entry point to `ai_handler.py::AIHandler.get_response`) + `src/backbone/intent_identification.py`
+ `src/backbone/planning.py`.

## Input
- `request: AIRequest` — same object the legacy `get_response` receives (message text, chat_id,
  role, etc.) for a text turn. No new fields required.
- For a media turn (R2a, REQ-063-04a): the same entry point receives the media message
  (previously this never reached anything resembling `AIHandler.get_response` at all — see
  `plan.md`'s Project Structure for the `denidin.py` dispatch change, flag-gated).

## Behavior (the loop)

1. **Intent Identification step**: attach Backbone content + `intent_identification`'s prompt
   (see `data-model.md`'s per-capability prompt loading). Input includes whether this is a text
   or media message (media messages don't get parsed/extracted yet — Intent Identification just
   knows "this is media", not what it contains). Output: a short natural-language/structured
   statement of what the turn needs (free-form enough to feed Planning; not itself a `CapabilityTag`
   list — that's Planning's job, keeping the two capabilities genuinely separate concerns).
2. **Planning step**: a followup call, Backbone + `planning`'s prompt + Intent Identification's
   output + the RBAC-filtered `available_capabilities_for_planning` (`data-model.md`). Output: a
   `Plan` (ordered list of domain-capability steps, possibly empty).
3. **Execution loop**: for each step in the `Plan`, in order:
   - Attach Backbone + that step's capability prompt + tools + all prior steps' results
     (accumulated context) + today's date.
   - Issue the call (reusing `_timed_llm_call`'s retry policy, reimplemented in the new module —
     see `research.md` R2's point 4).
   - If the step is `media_analysis`: the call's tool is a wrapper around the existing, unmodified
     `ImageExtractor`/`PDFExtractor`/`DOCXExtractor` (dispatched by MIME type exactly as
     `MediaHandler` does today) — its result (extracted text + ledger/document analysis) becomes
     part of the accumulated context for the next step.
   - If the step is a write-capability (`*_write`, `ledger_capture`): existing approval-gate
     machinery applies unchanged in spirit — a pending approval is created via the same
     `PendingApprovalManager`/`PendingLocalToolApproval` pattern, just invoked from the new
     orchestrator's code instead of `ai_handler.py`'s.
   - A step's own failure (tool error, malformed output) does not abort the whole plan — logged,
     and the loop continues to the next step with an error note in the accumulated context (so a
     later step, or the final reply, can acknowledge the failure) unless the failure is itself
     fatal to the turn (e.g. the OpenAI call itself errors after retries — then REQ-063-05's
     "friendly user-facing error" convention applies, same as today).
4. **Final reply**: composed from the last step's output (or Intent Identification's output alone,
   if the plan was empty) — same `[[NO_REPLY]]` sentinel handling, same truncation-on-send
   behavior as today (`WhatsAppHandler.send_response`, unmodified either way).

## Output
`AIResponse` — same shape the legacy `get_response` returns, so `denidin.py`'s calling code is
unaffected by which implementation produced it (REQ-063-07).

## Non-goals
- Does not change `WhatsAppHandler.send_response`, `PendingApprovalManager`, `SessionManager`, or
  any other shared infrastructure — those are used, unmodified, by both implementations.
- The accounting-reconciliation sweep's standalone OpenAI call
  (`accounting_reconciliation_service.py`) is **out of scope** — not part of this loop, continues
  building its own prompt exactly as today regardless of the flag.
- Button-tap / pending-approval resolution turns skip straight to resuming the specific pending
  step (they already know their capability deterministically) — Intent Identification/Planning
  don't run for those, mirroring how `ai_handler.py::resolve_button_tap`/`_resolve_pending_approval`
  already skip general intent detection today.
