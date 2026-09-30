> **SUPERSEDED 2026-09-24 by [`capability-resolution-loop.md`](capability-resolution-loop.md).** Historical record only.

# Contract: Tool-Driven Orchestration Loop (supersedes `orchestration-loop.md`)

**Status**: superseded (was approved design, 2026-09-16). Supersedes
`orchestration-loop.md`'s two-call Intent Identification → Planning → `_execute_plan`
step-list design in full — that contract's own JSON `Plan`/`fail_open_plan` shape is
retired by this one, not layered alongside it. `orchestration-loop.md` is kept in
place as historical record (the reasoning that led here, including the reverted
JSON-schema merge attempt this design deliberately avoids repeating) rather than
deleted.

**Component**: `src/backbone/orchestrator.py`'s `get_response()`.

## Why this shape

Two prior designs were considered and rejected before this one, in order:

1. **Two separate calls** (`identify_intent` + `build_plan`, `orchestration-loop.md`'s
   design): the user's objection — these are genuinely one concern ("you can't plan
   without understanding intent, and can't form intent without understanding the
   plan"), not two.
2. **One merged call outputting a hand-authored JSON envelope**
   (`{"reply", "steps", "status_note"}` or similar): implemented once, unapproved,
   2026-09-16, and reverted the same day. Real failure mode observed via billed-test
   diagnostics: the model did not reliably produce the invented JSON shape (free-lanced
   a different schema, or returned plain prose, on 3 of 4 turns), which silently
   triggered `fail_open_plan`'s "run every capability, last one wins" fallback —
   itself a separate, real bug this design also eliminates by removing the concept of
   a JSON plan to fail to parse in the first place.

This design (option 3, described below) avoids both failure modes: it is one merged
concern (satisfying #1), and it carries **zero hand-authored JSON contract for the
model to freehand** — everything the model decides is expressed through **real,
native OpenAI function-calling tools** (the same reliable mechanism already used for
`create_reminder` and every other tool in this app), never through prose the model
must format into an invented schema and code must parse.

Guiding principle throughout (explicit user instruction): **minimal code, maximal
AI.** Code's job is limited to dispatching whichever tool call came back and piping
its result back to the model — never deciding *what* to do, *when* a plan is
"complete," or *how* to phrase anything.

## The four tools

Replacing Intent Identification, Planning, and `_execute_plan`'s JSON step-list
entirely. All four are attached to every call this loop makes, alongside the existing
cross-cutting `BACKBONE_TOOLS` (`send_progress_update`, `react_to_message`, unchanged).

1. **`load_capability(capability)`** — code returns that capability's prompt file
   (`config/prompts/capabilities/<tag>.md`) verbatim as the tool's output. Nothing is
   pre-selected by code any more; the model asks for exactly the detail it decides it
   needs, when it decides it needs it.
2. **`use_capability(capability, note)`** — means "the capability you just loaded is
   now live." **Where possible, this attaches that capability's own real domain
   tools directly to the SAME ongoing chain** (via `previous_response_id`, no
   `instructions`/history resend) so the model calls them itself, in the very next
   round of the SAME conversation — never a separate, disconnected AI call that has
   to re-derive structured fields from `note` in isolation with no memory of how it
   was composed. `note` is relayed back only as the activation acknowledgment's own
   text, never re-parsed by code. `_dynamic_capability_tools` in `orchestrator.py`
   is the allowlist of tags migrated to this mechanism (`cap_reminders_write` as of
   2026-09-23 — see "Dynamic tool-attachment" below for the full contract and why
   this superseded the original per-capability-`call_capability_step` design). For
   any tag NOT yet migrated, falls back to the existing, unmodified
   `call_capability_step`-based dispatch (same mapping `_resolve_capability_handler`
   already implements — `cap_ledger_query`, `cap_docx_write`, etc. — see
   `docx-write-capability.md` for the new one), which DOES issue its own separate
   Responses API call (full `instructions` + history rebuilt) and returns its real
   result as the tool's output — acceptable there because those capabilities either
   have no strict-schema field the model needs to independently re-derive from prose
   (`cap_ledger_query`, `cap_media_analysis`) or have their own protocol constraint that
   requires a standalone call regardless (`cap_invoicing_write`'s real OpenAI MCP
   `require_approval` handshake).
3. **`record_planning_status(where_i_was, this_turns_purpose, expectation)`** — three
   free-text fields, always all three, whenever called:
   - `where_i_was`: the full plan/state as understood coming into this round —
     "no plan existed yet" is a valid value the first time.
   - `this_turns_purpose`: what this round is trying to achieve.
   - `expectation`: what result is expected from whatever this round does next.
   Code never parses or validates the content of any field — it is pure prose, the
   model's own account, stored and later re-surfaced verbatim (see "Cross-turn
   persistence" below). `backbone.md`'s prompt tells the model to call this on
   essentially every round — that guidance lives entirely in prose, not in code.
4. **`send_to_user(text)`** — the only way a turn ends. Ending the turn is a
   deliberate tool call like everything else, not something code infers from "a
   round came back with no tool calls." `text == "[[NO_REPLY]]"` keeps working
   exactly as today (same sentinel, same downstream handling in `_finalize_response`).

## The loop

Generalizes the existing `_resolve_backbone_tool_calls` (already chains follow-up
rounds via `previous_response_id`, so no code needs to manually resend conversation
history/capability catalog/planning status each round — the Responses API keeps all
of that in scope automatically across chained rounds within one turn) to also
dispatch `load_capability` / `use_capability` / `record_planning_status`, in addition
to the two tools it already handles. Capped by the same kind of iteration bound
(`MAX_BACKBONE_TOOL_LOOP_ITERATIONS`) already in place, purely as a runaway-loop
safety net — never expected to bind in normal operation.

Loop, per round:
- Dispatch every tool call the round's response contains (any mix of the four above
  plus the existing two).
- `load_capability`/`use_capability`/`record_planning_status` results are submitted
  as tool outputs via a chained follow-up call; the loop continues.
- `send_to_user` ends the loop — its `text` argument is the turn's final reply,
  handled by `_finalize_response` exactly as today's `final_text` is.
- A round's response can also contain a just-activated capability's own domain
  tool call (e.g. `create_reminder`) — see "Dynamic tool-attachment" below; these
  are dispatched and submitted the same chained way, just not one of the four
  fixed tools above.

## Dynamic tool-attachment (2026-09-23, corrects the original per-capability
`call_capability_step` design below for migrated capabilities)

**Original design flaw, found via a real T3 sanity-test trace**
(`tests/billed/T3_rawlog_*.log`): `use_capability` used to *always* dispatch to
`call_capability_step` — a brand-new, non-chained Responses API call that resent
the full Backbone + capability prompt text and the whole conversation history
from scratch, with the model's own free-text `note` as the only signal of what to
do. For a capability like `cap_reminders_write`, whose `create_reminder` tool has a
strict-schema required field (`one_time_due_at`, a concrete ISO-8601 datetime)
that has to be independently *re-derived* from prose like "in two hours from
now," this gave the model two disconnected chances to compute the same relative
date — once implicitly, composing `note`; once explicitly, filling the schema in
total isolation, with no memory of the first computation. Both computations were
observed wrong, with two *different* wrong years, on the same real current date
correctly present in both calls' own `instructions`. Explicit correction from the
user: **"use_capability... was meant as such - use the capability you just
loaded... Never another AI call - that's just unnecessary overhead."**

**Corrected contract**: for a capability tag `_dynamic_capability_tools` (in
`orchestrator.py`) allowlists, `use_capability` attaches that capability's real
domain tools directly to `tools` for the loop's own already-existing chained
follow-up round (the same one that resolves this round's other tool calls,
`previous_response_id`-linked to the response that made the `use_capability`
call) — never a separate call. The model then calls the domain tool itself, in
that SAME follow-up round, still with the same `instructions`/date it was given
at the top of the turn, and — critically — with its own reasoning context from
composing `note` moments earlier still present in the chain, not thrown away and
reconstructed from scratch. `_extract_dynamic_capability_calls` /
`_dispatch_dynamic_capability_call` handle recognizing and executing that domain
call once it comes back (`cap_reminders_write` → directly against `ReminderManager`
via `reminders/handler.py::dispatch_direct_tool_call`, no `call_capability_step`
involved at all for this tag).

**Not every capability is migrated to this mechanism, and that's deliberate, not
an oversight**: `_dynamic_capability_tools` returns `None` for any tag not
explicitly listed, and that tag's `use_capability` call falls back to the
original `call_capability_step`-based dispatch unchanged (see the `use_capability`
tool description above for exactly which capabilities and why — `cap_invoicing_write`
has its own real OpenAI MCP `require_approval` handshake that already requires a
standalone round-trip regardless; `cap_ledger_query`/`cap_media_analysis` have no
strict-schema field the model needs to blindly re-derive from prose, so the
double-computation risk this fix targets doesn't apply to them). Migrating
another capability to this mechanism is a small, mechanical, per-capability
change (add its tag + tool list to `_dynamic_capability_tools`, add its
call-extraction/dispatch branch to the two methods above) — not a blanket
rewrite, and should be done capability-by-capability, reviewed on its own.

## Cross-turn persistence (the only new persisted state)

Whatever `record_planning_status` last produced **this** turn is persisted as its own
distinct, clearly-tagged internal-note entry in the turn's history record (alongside,
not merged into, the real `send_to_user` reply that was actually sent to WhatsApp) —
via the same `SessionManager.add_message_with_tokens` call that already persists the
turn. Nothing new is stored beyond that: no separate manager, no schema, no
validation. Because the rolling window already threads full conversation history into
every call (`_turn_conversation_history`), this note flows back in automatically next
turn — code's only job is tagging it distinctly enough that the prompt can tell the
model "this was your own internal note, never something actually said to the user."

`backbone.md`'s prompt is the sole authority on *when* to call `record_planning_status`
— guidance there should say "call this on essentially every round," not code deciding
whether a turn "needs" one. This applies uniformly: a fully-resolved turn persists a
status too (next turn's model reasons "nothing pending" on its own from reading it,
rather than code deciding whether to bother persisting).

## Deleted by this design

- `src/backbone/intent_identification.py`
- `src/backbone/planning.py` (`Plan`, `PlanStep`, `build_plan`, `fail_open_plan`,
  `role_allowed_capabilities` — the last of these, RBAC-scoped capability filtering,
  is retained but relocated, since something still must compute which capabilities a
  role may reach for; exact new location TBD at implementation time, not a design
  question)
- `_execute_plan`'s step-list loop in `orchestrator.py`

## Approval as a plain capability (no more pending-approval state)

`approval` is a normal domain capability, `CapabilityTag.APPROVAL` — nothing MCP-
specific, nothing tied to invoicing/reminders/docx. It's a **standalone capability
that can be used any time, from anywhere** — any capability's own reasoning can
decide "this needs human confirmation first" and have the model call
`use_capability("approval", note)`. Its `handle()` does one thing: phrase a plain
yes/no question back (becomes this turn's `send_to_user` text, shown with WhatsApp's
real interactive buttons — `handle()` sets a turn-scoped flag the same lightweight
way `_turn_mcp_calls` already gets threaded, so `_finalize_response` knows to offer
buttons, mirroring Feature 047's existing `offer_approval_buttons` behavior
unchanged).

There is **no stored pending-approval record of any kind** — `PendingApprovalManager`
and `PendingLocalToolApprovalManager` are both eliminated by this design. Resumption
is purely the model's own cross-turn continuity, via the same `record_planning_status`
mechanism described above:

- Turn N: model calls `use_capability("approval", "confirm creating invoice X for
  client Y")`, then `record_planning_status(where_i_was="proposed invoice X",
  this_turns_purpose="get user confirmation", expectation="if the user says כן next
  turn, call cap_invoicing_write to actually create it")`, then `send_to_user("...לאשר?
  (כן/לא)")`.
- Turn N+1: user replies "כן" (typed, or a real button tap). The merged call sees
  the persisted planning-status note (which already says what to do if approved)
  plus real conversation history, reasons "user approved, now call cap_invoicing_write,"
  and does — no code anywhere decides this, it's the model reading its own note.

`cap_invoicing_write`/`cap_reminders_write`/any future write capability become pure "just do
the thing" capabilities — asking permission first is a separate capability call the
model makes before them, never logic baked into the write capability itself.

One piece of real plumbing this does NOT remove: a WhatsApp interactive-button tap
still arrives as its own webhook type and must be converted to a synthetic "כן"/"לא"
`AIRequest` at the `denidin.py` boundary before it can enter this loop at all —
unavoidable, wire-protocol-level, unrelated to approval-tracking itself. What
disappears is the `sent_message_id`-staleness bookkeeping that only existed to
protect a stored pending record — there is no record left to protect. A stale tap
(replying to a since-superseded question) becomes an ordinary confusing message the
model reasons about from real conversation history, same as any other ambiguous
reply.

## Common capability interface (`src/capabilities/base.py`)

Every domain capability (`reminders`, `invoicing`, `ledger_events`, `cap_media_analysis`,
the new `docx`, and the new `approval` — see `docx-write-capability.md` and "Approval
as a plain capability" above) exposes its own free-function entry points today
(`read`/`propose_write`/`query`/`capture`/`extract`/etc.), dispatched via
`_resolve_capability_handler`'s hand-written if/elif chain. As capability count grows
(4 → 6+ with `cap_docx_write`/`approval`, more later), this duplication (each module
reinventing function-call extraction, one dispatch site hand-listing every tag) is
exactly what an abstract base class exists to remove. New with this design — and
simpler than the first draft of this section, since eliminating stored pending-
approval state (above) also eliminates the need for any `resolve_button_tap`/
`resolve_typed_reply`-shaped methods on this interface at all — every capability now
needs only two entry points:

```python
# src/capabilities/base.py
class Capability(ABC):
    tag: ClassVar[CapabilityTag]

    def load(self) -> str:
        """Entry point for load_capability(tag) - default: read
        config/prompts/capabilities/<tag>.md verbatim (pure file I/O, no LLM
        call). Overridable, though no capability needs to yet - cap_docx_write's
        variant-specific template/examples stay a separate, later tool call
        inside its own inner loop (see docx-write-capability.md), not part of
        load()."""
        return read_capability_prompt_file(self.tag)

    @abstractmethod
    def handle(self, orchestrator, request: AIRequest, note: str,
               turn_context: Dict[str, Any]) -> str:
        """Entry point for use_capability(tag, note) - returns the text fed back
        to the model as that tool call's output."""

    # Shared helpers, available to every subclass instead of each module
    # reimplementing them (moved here from reminders/tools.py, the only module
    # that currently has them - invoicing's structurally different
    # find_approval_request/count_executed_calls, MCP-approval-specific and
    # itself retired by the approval-as-capability redesign above, is not
    # generalized here):
    @staticmethod
    def extract_function_call(response, tool_name: str) -> Optional[Dict]: ...
    @staticmethod
    def extract_function_call_id(response, tool_name: str) -> Optional[str]: ...
    @staticmethod
    def extract_any_function_call(response, tool_names: List[str]): ...
```

A small module-level registry (`CAPABILITY_REGISTRY: Dict[CapabilityTag, Capability]`,
built once at import time from each capability module's own concrete instance)
replaces `_resolve_capability_handler`'s if/elif chain — both `load_capability`'s and
`use_capability`'s dispatch become one uniform `CAPABILITY_REGISTRY[tag].load()` /
`.handle(...)` lookup, no hand-written per-tag branching anywhere.

Each existing capability module's free functions become methods on its own
`Capability` subclass (e.g. `RemindersCapability.handle` wraps today's
`propose_write`/`read` dispatch by `note`'s implied read-vs-write intent, or — simpler
— `use_capability` itself already knows read vs. write from which capability tag the
model named, e.g. `cap_reminders_read` vs `cap_reminders_write` stay two distinct
`CapabilityTag` values as today, each its own registry entry) — exact per-module
method bodies are a mechanical port of the existing free functions, not a design
question; only the shared interface/registry shape above is the actual design
decision.

## Capability design philosophy — binding for every capability, present and future

Explicit user instruction, generalized from how `cap_docx_write` was already built (Feature
083) and how `invoicing` already works: **every capability plugin is, as much as
possible, a file server — a thin adapter handing prompts/templates/reference material
to the AI and mechanically executing whatever the AI decided, never a place where code
itself decides or judges anything.** Concretely, per capability:

- **`load()`** serves whatever static content the AI needs to act — its prompt file at
  minimum; for a capability with reference assets (templates, examples — `cap_docx_write`),
  those too. Pure file I/O, no branching on content.
- **`handle()`** mechanically executes: attach a tool (`invoicing`), dispatch to an
  existing manager's CRUD call (`reminders`, `ledger_events` — a deterministic
  operation like "create this reminder" is unavoidable mechanical work, not a judgment
  call, same category as file I/O), merge text into a fixed template and save a file
  (`cap_docx_write`'s render), scan for one literal pattern and report the fact
  (`cap_docx_write`'s verify). **Never**: deciding if content is good enough, choosing
  between options on the AI's behalf, or phrasing anything the AI didn't write itself.
- The one narrow exception is **`cap_media_analysis`**, whose `handle()` makes a real,
  additional AI call (vision extraction) — unavoidable, since the orchestrator's own
  conversation never sees raw image/PDF/DOCX bytes (see "Why media analysis is a
  separate AI call" reasoning, captured in this feature's discussion history). Even
  there, code never judges the extraction's *content* — it returns whatever came back,
  verbatim, and the AI decides what it means.

Every future capability should be reviewed against this bar before it's considered
done: if `handle()` contains a decision an AI could have made via a tool call and a
prompt instead, that's a design smell, not an acceptable shortcut for "less code to
write right now."

## Non-goals (unchanged from `orchestration-loop.md`)
- Does not change `WhatsAppHandler.send_response`, `PendingApprovalManager`,
  `SessionManager`, or any other shared infrastructure.
- The accounting-reconciliation sweep's standalone OpenAI call is out of scope.
- Button-tap / pending-approval resolution turns still skip straight to resuming the
  specific pending step, bypassing this loop entirely — unchanged.
