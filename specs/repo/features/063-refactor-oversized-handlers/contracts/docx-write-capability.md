# Contract: `cap_docx_write` Capability (fee agreement documents)

**Status**: approved design, 2026-09-16, not yet implemented.

**Component**: new `src/capabilities/docx/handler.py`, invoked via the tool-driven
resolution loop's (superseded 2026-09-24: `load_capability("cap_docx_write")` then direct tool calls) — see
`tool-driven-loop.md`.

## Reuse (unmodified)
- `src/handlers/fee_agreement_tools.py`'s `FeeAgreementToolHandler` and its 4 tool
  schemas (`GET_FEE_AGREEMENT_TEMPLATE_TOOL`, `RENDER_FEE_AGREEMENT_DOCUMENT_TOOL`,
  `VERIFY_FEE_AGREEMENT_DOCUMENT_TOOL`, `SEND_FEE_AGREEMENT_DOCUMENT_TOOL`) — same
  class, same schemas, no fork (mirrors how `reminders`/`invoicing` capabilities wrap
  `ReminderManager`/Morning MCP unmodified).
- `src/managers/doc_template_engine.py`'s `DocTemplateEngine` — unmodified.
- `WhatsAppHandler.send_document_response` — same call `handle_send` already makes.

## New pieces
- `CapabilityTag.DOCX_WRITE` added to the tag enum + catalog description ("Composing
  and sending a fee agreement document (הסכם שכר טרחה) to a client... never for
  invoices/receipts (Morning tools) or reminders").
- `Backbone` gains `fee_agreement_tools: Optional[FeeAgreementToolHandler]`
  and `whatsapp_handler: Optional[Any]` constructor params, mirroring the existing
  `reminder_manager`/`pending_approval_manager` pattern — wired in `denidin.py`
  exactly like the legacy `ai_handler.fee_agreement_tools = FeeAgreementToolHandler(...)`
  construction already there.

## The one genuinely new piece: an inner multi-round dispatch loop

Fee-agreement's 4 tools have no approval gate (2026-09-13 human decision, unchanged) —
the model must be able to call `get_template` → `render` → `verify` → (`render` again)
→ `verify` → `send`, seeing each tool's real output before deciding the next call,
all within the same `use_capability("cap_docx_write", ...)` invocation. This needs its
own bounded, iterative dispatch loop *inside* `docx/handler.py` — reimplemented as new,
standalone code per REQ-063-07 (no cross-import from `ai_handler.py`'s
`_dispatch_all_local_tools`), using `backbone.call_capability_step(..., tools=
FEE_AGREEMENT_TOOL_NAMES's schemas, return_response=True)` for each round, dispatching
whichever of `handle_get_template`/`handle_render`/`handle_verify`/`handle_send` the
model called, feeding the tool output back as a follow-up call, until the model
returns plain text (its own confirmation the document was sent, or a question) or the
iteration cap is hit.

This loop is local to this one capability — not a generalization of the top-level
tool-driven resolution loop in `tool-driven-loop.md`, since no other
current capability needs an approval-free multi-step tool sequence like this within a
single `use_capability` call.
