# Phase 0 Research: The Dynamic Capability Backbone (063)

All items below were "NEEDS CLARIFICATION" in the initial plan-template Technical Context; each
is resolved here by direct audit of the existing codebase (`ai_handler.py`,
`runtime_constitution.md`, `models/config.py`, `CONSTITUTION.md`) rather than external research,
since this is an internal refactor of code that already exists and already has a governing
architecture.

---

## R1 — Rollout mechanism: feature flag selecting between two fully parallel implementations

**Decision** (revised in the plan-phase clarification, 2026-09-14): `config.feature_flags` gains
`enable_capability_backbone` (default `false`), but this is **not** a conditional woven through
`ai_handler.py` — it is a **one-time selection, at startup**, between two entirely separate,
independently-complete implementations:
- **Flag off (default)**: `denidin.py`'s `initialize_app` constructs the existing `AIHandler`
  exactly as today, reading `config/runtime_constitution.md` exactly as today. `ai_handler.py`
  and `runtime_constitution.md` are **not modified** by this feature, at all, for as long as the
  flag exists (REQ-063-07).
- **Flag on**: `initialize_app` constructs a new orchestrator (the Backbone), reading
  `config/prompts/backbone.md` + `config/prompts/capabilities/*.md`. This is genuinely new code
  living in new files/modules, not a code path spliced into the old handler.

Both implementations expose the same interface `denidin.py`'s routing layer already calls
(`get_response`, `resolve_button_tap`, etc.), so the rest of the app (WhatsAppHandler, the
`HANDLER_REGISTRY` dispatch table, etc.) is unaware which one it's talking to.

**Rationale**: This is a stronger isolation guarantee than a conditional-inside-one-file design —
REQ-063-05's zero-regression bar is proven not by careful branching inside a modified
`ai_handler.py` (where a mistake in the "flag off" branch could still regress today's behavior),
but by the fact that the flag-off code path is **literally the same, untouched file** that
production runs today. The blast radius of a bug in the new orchestrator is fully contained to
when the flag is explicitly turned on. This also directly satisfies the human's stated preference
(2026-09-14): "keep ai_handler.py as-is" for modularized=False, a genuinely separate file set for
modularized=True.

**Rationale for keeping the flag at all** (vs. no flag): still the safest rollout for the largest
structural change this codebase has undergone — full A/B comparability in `dev`, instant
rollback (flip the flag back), and incremental `speckit.tasks` delivery (build the new
orchestrator's plugins one at a time) without ever touching, and therefore never risking, the
live behavior. Flipping the default to `true` and eventually retiring the legacy `AIHandler` path
is explicitly **out of scope** for this feature's completion — a separate, later, human-approved
decision (CLAUDE.md's "VERSION AND RELEASE DECISIONS ARE HUMAN-ONLY" posture applied to a risky
behavioral cutover).

**Alternatives considered**:
- *Conditional branches inside `ai_handler.py`* (the original plan-draft design) — superseded:
  the human explicitly preferred full file-level isolation over intra-file branching, for a
  cleaner regression boundary and a codebase where `git blame`/diff review on the legacy path
  stays empty for this feature entirely.
- *Hard cutover in one PR, no flag* — rejected: no rollback path if a plugin's extraction has a
  subtle bug the `billed`/`expensive` suite doesn't happen to cover.
- *Per-capability flags (9 separate flags)* — rejected as unnecessary complexity: Planning (R2)
  already makes capability attachment conditional *within* the new path; a single flag toggles
  which implementation is constructed, which is the actual risk boundary.

---

## R2 — Orchestration mechanism: Backbone as tool-orchestrator kernel, not a separate classifier (REVISED, second plan-phase pass)

**Superseded decision**: the original design (a bespoke "pre-classifier" call with a static
routing prompt and structured JSON output) is replaced. The corrected mechanism:

**Decision**: The Backbone holds no routing logic as static prompt text. Instead:
1. The orchestrator's first call attaches Backbone content + **Intent Identification**'s
   prompt+tool (a lightweight capability, not a bespoke classifier endpoint).
2. Intent Identification's result feeds a followup call attaching **Planning**'s prompt+tool,
   which produces an ordered plan: a list of steps, each naming a domain capability (or Media
   Analysis, if the message is media) to invoke, in order.
3. The orchestrator executes the plan step by step: for each step, attach that domain
   capability's prompt+tools (only that one, not all 7) and issue a followup call; feed its
   result back into the next step (later steps may reference earlier results — e.g. "check the
   ledger" after "extract the image").
4. This reuses the existing followup-call pattern `ai_handler.py` already implements for
   reminders/ledger-query/progress-updates/reactions (`_call_openai_reminder_followup_api`,
   `_call_openai_query_ledger_events_followup_api`, etc.) — generalized as the *primary*
   mechanism for every turn, not a special case bolted onto one main call.

A turn with an empty plan (small talk, AS-1's case) never proceeds past Intent Identification +
Planning — no domain capability content is ever attached. A turn whose plan names 2+ domain
capabilities (UAT3) naturally executes both steps in sequence — no separate "multi-capability"
mechanism needed, it's just a longer plan.

Model: reuse `config.ai_model` for every step (Intent Identification, Planning, each domain
capability call) — consistent with CLAUDE.md's single-shared-model note; `max_output_tokens` is
capped appropriately per step (Intent Identification/Planning are short; domain capability calls
keep today's existing limits).

RBAC intersection: Planning's available domain-capability set is filtered by
`role_allowed_capabilities(user.role)` *before* Planning even runs (Planning is only ever told
about capabilities the role can use) — mirroring `_assemble_tools`' existing RBAC checks, applied
one step earlier than in the original (classifier) design.

**Rationale**: Making Intent Identification and Planning real capabilities (own prompt files)
rather than static Backbone text keeps the Backbone itself genuinely minimal and lets routing
logic be iterated on independently — directly serving the spec's "Developer Velocity" goal
(Business & Architectural Goals) the same way any other capability does. Reusing the existing
followup-call pattern (rather than a new classifier-call shape) means R2 introduces zero new
call-orchestration code patterns — only new prompt content and new capability wiring.

**Alternatives considered**:
- *Original design: single classifier call with structured JSON output, one shot, no planning
  step* — rejected: doesn't generalize to genuinely multi-step flows (e.g. media → extraction →
  conditional ledger vs. invoicing routing) without becoming a second bespoke mechanism; the
  human specifically wanted one unified orchestration model for text and media alike.
- *Keyword/regex heuristic* — still rejected (unchanged from the first clarify pass): brittle
  against natural Hebrew/English phrasing.
- *No Planning step; Intent Identification directly names one capability, no multi-step plans* —
  rejected: loses UAT3 (cross-domain requests) and the media → conditional-routing case (REQ-063-04a)
  without reintroducing some other multi-step mechanism elsewhere.

---

## R2a — Media Analysis: a 7th domain capability, invoked as an orchestrator tool, not a pre-route

**Decision**: Image/PDF/DOCX extraction becomes **Media Analysis**, a domain capability like any
other — own prompt (consolidating today's `prompts/image_analysis.txt`/`prompts/docx_analysis.txt`,
both left untouched per REQ-063-07) + a tool wrapping the existing, unmodified
`ImageExtractor`/`PDFExtractor`/`DOCXExtractor` classes. When an incoming message is media, the
orchestrator's Planning step is simply told the message is media (so extraction is very likely
step one of the plan, but this is Planning's own judgment, not a hardcoded branch) — the
orchestrator then executes that step, gets extracted text back, and continues Planning/execution
from there exactly as it would for any other intermediate tool result, per REQ-063-04a.

This replaces `denidin.py`'s current media dispatch, which routes `handleMediaMessage` straight to
`WhatsAppHandler.handle_media_message` → `MediaHandler`, **bypassing `AIHandler.get_response`
entirely** (see CLAUDE.md's Message flow note) — when the flag is on, media messages instead route
into the new orchestrator's equivalent of `get_response`, exactly like text messages, so the same
single control loop handles both. When the flag is off, `denidin.py`'s existing dispatch table is
completely unchanged — media still bypasses `AIHandler` exactly as it does today (REQ-063-07 covers
`denidin.py`'s dispatch logic too: the legacy dispatch path for the flag-off case is not modified,
only extended with a flag check at the routing layer to choose between the two paths).

**Rationale**: Directly closes a real inefficiency named in SC-004 — every vision call today
prepends the *entire* `runtime_constitution.md` (`_vision_extract`'s "constitution prepended"
comment), regardless of relevance; under the new path a vision-adjacent call only ever carries
Backbone + Media Analysis (+ whatever the plan's next step turns out to need), not the full
7-capability surface. It also fixes a real behavioral rigidity: today, ledger recognition always
runs after any image extraction, unconditionally; under the new plan-driven model, whether Ledger
Capture (or Invoicing, or neither) follows extraction is a real judgment call per message, not a
hardcoded step.

**Alternatives considered**:
- *Keep media routing fully separate, deterministic, outside the orchestrator* — the original
  plan-phase design; rejected per the human's explicit correction: the Backbone must be the single
  always-alive orchestrator for every message type, not two parallel mechanisms.

---

## R2b — `config/prompts/` folder: consolidates all new-path prompts, legacy files untouched

**Decision**: New folder `apps/denidin-app/config/prompts/`:
```
config/prompts/
├── backbone.md                       # static behavioral constants only (spec.md's Backbone list)
└── capabilities/
    ├── intent_identification.md      # meta
    ├── planning.md                   # meta
    ├── invoicing_write.md
    ├── invoicing_read.md
    ├── ledger_capture.md             # includes domain-specific rules split out of
    │                                  #   config/ledger_recognition_prompt.md
    ├── ledger_query.md
    ├── reminders_write.md
    ├── reminders_read.md
    └── media_analysis.md             # consolidates prompts/image_analysis.txt + docx_analysis.txt
```
Existing files (`config/runtime_constitution.md`, `config/ledger_recognition_prompt.md`,
`prompts/image_analysis.txt`, `prompts/docx_analysis.txt`) are **left in place, untouched** — the
legacy `AIHandler`/extractor path keeps reading them exactly as today (REQ-063-07). The new
`config/prompts/` files are freshly authored content (informed by, not copy-pasted from, the
legacy files), since the new orchestration model (multi-step plans, capability-scoped prompts)
isn't a mechanical text split.

**Rationale**: One consolidated, discoverable home for every new-path prompt (spec's "Developer
Velocity" goal), while the file-level isolation from legacy content keeps REQ-063-07's
zero-touch guarantee simple to audit (`git diff` against the legacy `config/`/`prompts/` files
must show nothing, ever, for this feature).

---

## R3 — Prompt assembly per step: Backbone-first, single-capability append per call (REVISED)

**Decision** (updated for R2's step-by-step plan execution): each call in a plan — Intent
Identification, Planning, and every domain-capability step — carries `instructions = Backbone
content + that one step's capability content + accumulated plan context (prior steps' results,
appended after the capability content, analogous to how `_build_instructions` appends memory
context today) + "---" + date`. The Backbone is always first and byte-identical call-to-call,
exactly as `_build_instructions` guarantees today; a given capability's own content block is also
byte-identical whenever that capability is the active step. This directly implements REQ-063-06:
OpenAI's prompt caching matches on the longest identical prefix, so **every** call sharing the
same active capability (not just calls within one turn — any two Intent Identification calls
across any two turns, any two Ledger Capture calls, etc.) shares a cache hit on the
Backbone+capability prefix, before the turn/plan-specific tail (accumulated context, date) even
enters the picture. This is a *stronger* caching property than the original single-multi-plugin-call
design, since the cached prefix is shorter and more repeatable (Backbone + 1 capability, not
Backbone + a variable union of N capabilities).

**File layout**: a new, separate `backbone_config` (not an extension of `constitution_config` —
see `data-model.md`'s Config additions) pointing at `config/prompts/backbone.md` +
`config/prompts/capabilities/`, one `.md` file per capability (2 meta + 7 domain, R2b). Each file
gets its own independent mtime-based cache entry in the new orchestrator, structurally mirroring
(not sharing code with) today's `_load_constitution`/Feature 069's `_load_recognition_prompt`
mtime-cache pattern.

**Rationale**: Minimal deviation from a caching mechanism that already works and is already
tested (mtime hot-reload, `base_dir` override for tests), while actually improving the
cache-hit property by keeping each call's prompt to exactly Backbone + one capability, per R2's
step-by-step execution model.

**Alternatives considered**:
- *Concatenate ALL of a plan's matched capabilities into one call's instructions, single call per
  turn* — this was the original (superseded) design; rejected because it doesn't fit R2's
  step-by-step followup-call execution model (each step is its own call with its own tool
  availability, mirroring how `ai_handler.py`'s existing followup calls already work).
- *Single file with conditional sections marked by delimiters, loaded whole and trimmed* —
  rejected: still reads/parses one large file every call regardless of which sections are kept,
  and doesn't give each capability an independently-editable file (loses REQ-063-02's "distinct
  capability markdown files" and the spec's "Developer Velocity" goal).

---

## R4 — Backbone content scope (confirmed from Capability Plugin Taxonomy, no new research needed)

Already resolved in `spec.md`'s Capability Plugin Taxonomy: Core Identity, Behavioral Guidelines,
User Roles, Privacy & Security, Contexts of Operation, Group Conversation Etiquette, Edited &
Deleted Message Markers, the generic post-turn-recognition mechanism, Proactive Progress Updates,
Reaction Management — static behavioral constants only. Routing/classification logic is explicitly
**not** Backbone content (R2) — it lives in the Intent Identification and Planning capabilities'
own prompt files instead. This file becomes `config/prompts/backbone.md` (R2b) — a new file, not
`runtime_constitution.md` renamed or trimmed.

---

## R5 — Code layout: `src/backbone/` (orchestrator + meta) + `src/capabilities/<domain>/`, `ai_handler.py` untouched

**Decision** (revised alongside R1/R2): two new top-level packages, both fully additive:

- **`apps/denidin-app/src/backbone/`** — the orchestrator kernel and the two meta-capabilities:
  `orchestrator.py` (the plan-execution loop, the new `get_response`/`resolve_button_tap`
  equivalent `denidin.py` constructs when the flag is on), `intent_identification.py`,
  `planning.py`. This is where R2's step-by-step followup-call loop actually lives.
- **`apps/denidin-app/src/capabilities/`** — one subpackage per **domain** (not per write/read
  pair, not counting the 2 meta-capabilities which live in `backbone/` since they're about
  orchestration, not a business domain) — `invoicing/`, `ledger_events/`, `reminders/`,
  `media_analysis/` (4 domain subpackages; write/read stays a prompt/tool-attachment distinction
  per R3, not a Python file split), each holding:
  - `handler.py`: **new** handler logic, written for the new orchestrator (may closely mirror
    `ai_handler.py`'s existing method bodies as a starting point, but lives in its own file,
    maintained independently — no shared inheritance or delegation back into `AIHandler`).
  - No `manager.py` — for the two domains with real local storage (Ledger Events, Reminders),
    `managers/ledger_event_manager.py` / `managers/reminder_manager.py` **stay exactly where they
    are, completely unmodified**; `capabilities/ledger_events/handler.py` /
    `capabilities/reminders/handler.py` simply import from those same existing locations — same
    file, two importers. Media Analysis follows the identical pattern:
    `handlers/extractors/{image,pdf,docx}_extractor.py` stay exactly where they are, completely
    unmodified; `capabilities/media_analysis/handler.py` imports from there. This is genuinely
    zero changes to `ai_handler.py`/the extractors (not even an import-source change), fully
    satisfying REQ-063-07, while avoiding any duplicated extraction/storage logic.

Invoicing has no local manager (Morning MCP is a remote tool) —
`capabilities/invoicing/handler.py` is new code building the same Morning MCP tool-attachment
logic `_build_morning_mcp_tools` implements today, independently.

`session_manager.py` (991 lines) stays exactly where it is, `src/managers/session_manager.py`,
used unmodified by both implementations — it is Backbone-layer shared infrastructure, not a
capability, and both `AIHandler` and the new orchestrator depend on it as-is.

**Rationale**: Matches the taxonomy 1:1 for discoverability in the new path, while the shared
manager-storage relocation (not duplication) avoids two independently-evolving copies of the same
SQLite schema/iCalendar logic drifting apart — a real correctness risk a full duplication would
introduce that a "don't touch `ai_handler.py`" rule alone wouldn't prevent.

**Alternatives considered**:
- *One folder per plugin (6 folders)* — rejected: forces the storage layer to either duplicate or
  awkwardly share state across two "cohesive" plugin folders, contradicting REQ-063-03's own
  encapsulation intent.
- *Duplicate the manager storage code wholesale into each implementation* — rejected: two live
  copies of ledger-event/reminder persistence logic is a correctness hazard (schema drift,
  double-write risk) far worse than the minor coupling of both implementations importing the same
  existing, unmodified manager module.
- *Relocate the manager files to a new shared location, update `ai_handler.py`'s import* —
  rejected: this would itself be a modification to `ai_handler.py` (even if only its import
  line), violating REQ-063-07's "byte-for-byte untouched." Leaving the manager files exactly where
  they already are and having only the *new* code import from there achieves the same sharing
  with zero footprint on the legacy file.

---

## R6 — Instrumentation for UAT2/UAT3/SC-004/SC-005 (no new pytest acceptance tests — see user-stories.md)

**Decision**: Extend `scripts/model_sanity_check.sh` (Feature 070 T005's existing billed
instrumentation script) with a new mode that, with the flag on: (a) sends a small-talk turn and
asserts the plan is empty / no domain capability step ever executes (UAT2); (b) sends a
cross-domain turn and asserts the plan has ≥2 domain-capability steps (UAT3); (c) sends a media
message and asserts Media Analysis is a plan step whose result feeds a conditional next step
(REQ-063-04a); (d) sends two turns that both exercise the same capability (e.g. two Ledger Query
turns, possibly in different conversations) and asserts the second's Backbone+capability prefix
call reports `cached_tokens > 0` (REQ-063-06/SC-005). This is billed, human-approved per run like
the rest of that script, not part of the automated pytest suite.

**Rationale**: Reuses existing tooling rather than inventing a parallel measurement path; keeps
the "no new acceptance scenarios" decision consistent (this is a diagnostic script, not a test
asserting user-facing behavior).
