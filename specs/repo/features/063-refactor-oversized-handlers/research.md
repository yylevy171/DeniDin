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
  `config/backbone.md` + `config/capabilities/*.md`. This is genuinely new code living in new
  files/modules, not a code path spliced into the old handler.

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
- *Per-plugin flags (6 separate flags)* — rejected as unnecessary complexity: the pre-classifier
  (R2) already makes plugin attachment conditional *within* the new path; a single flag toggles
  which implementation is constructed, which is the actual risk boundary.

---

## R2 — Pre-classifier: dedicated lightweight OpenAI call, structured output

**Decision**: A new, minimal OpenAI Responses API call runs before the main turn call, whenever
the feature flag is on. Its `instructions` is a short, static routing prompt (part of the
Backbone's own content, always loaded — see R4) listing the 6 capability plugins by name +
one-line description; its input is the same user turn content the main call would receive. It
returns **structured output**: a JSON object `{"capabilities": ["ledger_query", "reminders_write",
...]}` (empty list = Backbone-only, matching AS-1's small-talk case). Multi-capability turns
(UAT3) naturally fall out of this as a list with >1 entry — no separate mechanism needed.

Model: reuse `config.ai_model` (already the single shared model across dev/prod/test per
CLAUDE.md) rather than introducing a second configured model. This keeps config surface minimal;
a future swap to a cheaper/faster classifier model is a one-line config change if ever warranted,
not a design dependency of this feature. `max_output_tokens` is capped low (classification output
is a short JSON list), keeping the added call cheap in the `billed` sense the constitution already
uses.

RBAC intersection: the classifier's output is intersected with the turn's role-based tool
availability *after* classification (mirroring `_assemble_tools`' existing RBAC checks) — a
`client`-role user's turn never attaches Invoicing/Ledger/Reminders plugin content regardless of
what the classifier returns, exactly as today's RBAC gating already prevents those tools from
being offered.

**Rationale**: Reuses the existing OpenAI retry policy (3 attempts/2s wait, rate-limit 3/5s) and
error-handling conventions already in `_timed_llm_call`/`_call_openai_api` rather than inventing a
new call pattern. Structured JSON output is deterministic to parse and directly satisfies
REQ-063-04's "union of matched plugins" requirement for UAT3.

**Alternatives considered**:
- *Keyword/regex heuristic* — rejected in the clarify pass (2026-09-14): brittle against natural
  Hebrew/English phrasing, doesn't generalize to UAT3's cross-domain requests.
- *No separate call; infer from which tool the main call ends up invoking* — rejected: this is
  circular (you'd need the tool schemas — i.e. the plugin content — attached *before* the model
  can choose one), defeating the token-savings goal (SC-004) entirely.

---

## R3 — Constitution assembly: Backbone-first, canonical-order plugin append

**Decision**: `_build_instructions`'s existing fixed assembly order (constitution text → recalled
memory context → `---` separator → date) is preserved in shape, but "constitution text" becomes
"Backbone content + matched plugins' content, concatenated in a fixed canonical order" (the order
fixed in the Capability Plugin Taxonomy: Invoicing-Write, Invoicing-Read, Ledger-Capture,
Ledger-Query, Reminders-Write, Reminders-Read). The Backbone is always first and byte-identical
call-to-call; a given plugin's own content block is also byte-identical whenever it's included.
This directly implements REQ-063-06 (cache-prefix preservation): OpenAI's prompt caching matches
on the longest identical prefix, so two turns with the same matched-plugin-set (in the same
canonical order) share a cache hit on the Backbone+plugins block, not just the Backbone alone.

**File layout**: extend `constitution_config` (currently `{file, base_dir}`) with a
`capabilities_dir` (default `config/capabilities/`) holding one `.md` file per plugin, named
after the taxonomy (`invoicing_write.md`, `invoicing_read.md`, `ledger_capture.md`,
`ledger_query.md`, `reminders_write.md`, `reminders_read.md`). Each file gets its own independent
mtime-based cache entry, exactly like today's single-file mechanism (`_load_constitution`) and
Feature 069's `_load_recognition_prompt` sibling — no new caching *strategy*, just N independent
instances of the existing one.

**Rationale**: Minimal deviation from a mechanism that already works and is already tested
(mtime hot-reload, `base_dir` override for tests). Preserves the byte-stable-prefix property that
069/070/080 all depend on for caching, per REQ-063-06.

**Alternatives considered**:
- *Single file with conditional sections marked by delimiters, loaded whole and trimmed* —
  rejected: still reads/parses the full 1,879-line file every call regardless of which sections
  are kept, and doesn't give each plugin an independently-editable file (loses REQ-063-02's
  "distinct capability markdown files" and the "developer velocity" goal in the spec's Business
  Goals).

---

## R4 — Backbone content scope (confirmed from Capability Plugin Taxonomy, no new research needed)

Already resolved in `spec.md`'s Capability Plugin Taxonomy (2026-09-14 clarify pass): Core
Identity, Behavioral Guidelines, User Roles, Privacy & Security, Contexts of Operation, Group
Conversation Etiquette, Edited & Deleted Message Markers, Proactive Progress Updates, Reaction
Management, plus the new pre-classifier routing prompt (R2) itself. This file becomes
`config/backbone.md`, replacing today's single `runtime_constitution.md` as the value of
`constitution_config.file`.

---

## R5 — Code layout: new `src/capabilities/<domain>/` package, `ai_handler.py` untouched

**Decision** (revised alongside R1): `apps/denidin-app/src/capabilities/` is **new** code, not an
extraction that removes anything from `ai_handler.py`. One subpackage per taxonomy domain (not
per write/read pair) — `invoicing/`, `ledger_events/`, `reminders/` — each holding:
- `handler.py`: **new** write-side and read-side handler logic, written for the new orchestrator
  (may closely mirror `ai_handler.py`'s existing method bodies as a starting point, but lives in
  its own file and is maintained independently — no shared inheritance or delegation back into
  `AIHandler` that would couple the two implementations together). The *plugin* split (write vs.
  read) is at the constitution/prompt and tool-attachment level per R2/R3, not a second Python
  file, since REQ-063-03 groups a domain's handler+manager logic together as one cohesive unit.
- No `manager.py` per domain — for the two domains with real local storage (Ledger Events,
  Reminders), `managers/ledger_event_manager.py` / `managers/reminder_manager.py` **stay exactly
  where they are, completely unmodified**. The new `capabilities/ledger_events/handler.py` /
  `capabilities/reminders/handler.py` simply import from those same existing locations — the same
  file, two importers (`ai_handler.py`, unchanged, and the new handler). This is genuinely zero
  changes to `ai_handler.py` (not even an import-source change), fully satisfying REQ-063-07,
  while still avoiding any duplicated storage/schema logic between the two implementations.

Invoicing has no local manager (Morning MCP is a remote tool) —
`capabilities/invoicing/handler.py` is new code building the same Morning MCP tool-attachment
logic `_build_morning_mcp_tools` implements today, independently.

`session_manager.py` (991 lines) stays exactly where it is, `src/managers/session_manager.py`,
used unmodified by both implementations — per the clarify pass, it is Backbone-layer shared
infrastructure, not a capability, and both `AIHandler` and the new orchestrator depend on it as-is.

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
asserts the `instructions` string size / plugin-count is Backbone-only (UAT2); (b) sends a
cross-domain turn and asserts ≥2 plugins matched (UAT3); (c) sends two same-capability-set turns
back-to-back and asserts the second reports `cached_tokens > 0` covering the combined
Backbone+plugin block (REQ-063-06/SC-005/AS-9's old intent, now framed as instrumentation per the
human's 2026-09-14 decision that no new acceptance-test scenarios are needed). This is billed,
human-approved per run like the rest of that script, not part of the automated pytest suite.

**Rationale**: Reuses existing tooling rather than inventing a parallel measurement path; keeps
the "no new acceptance scenarios" decision consistent (this is a diagnostic script, not a test
asserting user-facing behavior).
