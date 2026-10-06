# Feature Specification: The Dynamic Capability Backbone (Refactor 063 + 073 + 085)

**Feature Branch**: `feature/063-refactor-oversized-handlers` (Bundled with 073, 085 — both filed
under `specs/obsolete/`, their scope absorbed here)
**Status**: Done - implemented and tested (backbone flag ON parity reruns), merging to master
**Input**: Refactor `ai_handler.py` and `runtime_constitution.md` into a modular "backbone and plugins" architecture where capability prompts and code are dynamically loaded only at need.

---

## 1. Business & Architectural Goals

The DeniDin monolith has grown too large. Both the central code router (`ai_handler.py` at ~4,000 lines) and the AI's central brain (`runtime_constitution.md` at ~1,700 lines) are choked with distinct capabilities (Ledger Events, Reminders, Document Creation, etc.).

**The Goal**: Move from a "Monolith Agent" to a **"Dynamic Capability Backbone"**.
Instead of passing every single rule and capability to the AI on every turn, we will establish:
1. **The Backbone**: A core constant prompt and core routing logic. The Backbone's only job is to understand the user's intent, maintain core persona, and decide *which* capability plugin to invoke.
2. **The Capability Plugins**: Self-contained modules (e.g., `ledger_capability`, `reminder_capability`). Each plugin contains:
   - **Its Code**: The specific python handlers broken out from `ai_handler.py`.
   - **Its Prompt/Constitution**: The specific markdown rules broken out from `runtime_constitution.md`.

**Why?**
- **LLM Context Efficiency**: By only loading the capability prompts "at need," we drastically reduce the prompt size per turn, saving money and increasing AI focus.
- **Developer Velocity**: Adding a new feature simply means dropping a new "Capability Plugin" into the folder, rather than creating merge conflicts in massive central files.

---

## Clarifications

### Session 2026-09-14

- Q: How should the Backbone decide which capability plugin(s) to load for a turn (REQ-063-04)? → A: A cheap pre-classifier LLM call runs first; only the matched plugin's prompt+tools are attached to the real turn call.
- Q: Capability plugin prompts vary per turn — how is OpenAI's fixed-prefix prompt caching preserved? → A: The Backbone stays first and byte-stable (the cached prefix); capability blocks are appended after it in a deterministic, canonical order, so identical capability-sets across turns still hit cache.
- Q: May unit tests (many import AIHandler internals directly) be rewritten to match new module boundaries, given REQ-063-05 only names billed/expensive E2E tests? → A: Yes — only billed/expensive/sanity E2E tests are the immutable regression gate; unit tests are restructured alongside the code they test, like any normal refactor.
- Q: Should the capability plugin boundaries be enumerated in this spec now, or left to speckit.plan? → A: Enumerate now, organized by user-experience expectation (always-present vs. present-only-when-needed) crossed with CRUD (write/state-change vs. read/query, since approval-gating and response shape differ) — see "Capability Plugin Taxonomy" below.

### Session 2026-09-14 (plan-phase revision, post-`speckit.plan` draft)

- Q: Should this refactor be an in-place strip-down of `ai_handler.py`/`runtime_constitution.md` behind a feature flag, or two fully separate, parallel implementations? → A: Two fully separate implementations. `ai_handler.py` and `runtime_constitution.md` stay byte-for-byte untouched for as long as the flag exists; the Backbone+Plugins path is entirely new code (`config/backbone.md`, `config/capabilities/*.md`, a new backbone module), selected once at `denidin.py`'s `initialize_app` startup based on `config.feature_flags.enable_capability_backbone`. This directly informed dropping the old SC-001 (see below) and rewriting REQ-063-02/03 as REQ-063-07.
- Q: With `ai_handler.py` no longer shrinking under this design, what replaces the old SC-001 ("`ai_handler.py` reduced by ≥70%")? → A: Dropped entirely — no line-count target. Success is measured by SC-002 (constitution split) and SC-004 (token reduction), not by `ai_handler.py`'s size, since it is intentionally never modified.

### Session 2026-09-14 (second plan-phase revision — resolution mechanism corrected)

- Q: Should feature flags be added to new work by default? → A: No — a separate, same-day CONSTITUTION.md §VI revision makes flags opt-in, asked-for per feature rather than automatic. This feature keeps its flag because the human explicitly requested one for this specific large refactor.
- Q: Should the media-analysis prompts (`prompts/image_analysis.txt`, `prompts/docx_analysis.txt`) and the ledger-recognition prompt (`config/ledger_recognition_prompt.md`) be folded into this same refactor? → A: Yes. All prompts consolidate under a new `config/prompts/` folder for the new path (legacy files untouched, REQ-063-07 unaffected). Media Analysis becomes a 7th domain capability. `ledger_recognition_prompt.md`'s content splits: the generic "run a post-turn recognition step, call this tool exactly once" mechanism moves into the Backbone (reusable by any capability that wants a recognition step), while the domain-specific rules (the three verdicts, הסכם/בנק specifics, client-resolution heuristics) stay in the Ledger Events — Capture capability's own prompt.
- Q: Is the routing mechanism a separate "pre-classifier" call producing structured JSON before the real turn call (the original plan-phase design)? → A: **No — corrected.** There is no separate classifier endpoint. The Backbone is a single, always-alive **tool-backbone kernel**: its own reasoning steps (deciding intent, building a plan) are themselves capabilities with their own dedicated prompts — **Intent Identification** and **Planning** — not static instructions baked into the Backbone's prompt text. The Backbone calls Intent Identification (as a tool/followup step) to understand what's needed, then Planning (another tool/followup step) to build a checklist of further tool calls, then executes that plan step by step — reusing the existing followup-call pattern `ai_handler.py` already implements for reminders/ledger-query/etc. (`_call_openai_reminder_followup_api` and siblings), generalized as the primary mechanism instead of a bolted-on special case.
- Q: How do media messages enter this model? → A: Through the **same** Backbone as any text turn — there is no separate deterministic pre-Backbone media-routing step. Image/PDF/DOCX extraction (Media Analysis) is simply a tool in the Backbone's toolbox; when the Backbone's plan calls for it (because the incoming message is a media message), it invokes that tool, reads the result, and continues driving from there (e.g. extracted text → Intent Identification → Ledger Capture, or Invoicing, or both) — the same unified loop, not two different mechanisms for text vs. media.

### Session 2026-09-16 (resolution mechanism corrected again — the two-call design retired)

- Q: The two-call Intent Identification → Planning design above (JSON `Plan` step-list, `fail_open_plan` fallback) shipped and was tested — does it stand? → A: **No — retired.** A real billed-test investigation found Planning's JSON contract wasn't reliably followed by the model, silently triggering `fail_open_plan`'s "run every capability, last one wins" fallback. A merged single-call replacement with its own hand-authored JSON envelope was then implemented unapproved and reverted the same day (design decisions require approval before code — see project memory). The design that replaces both: see **[`contracts/tool-driven-loop.md`](contracts/tool-driven-loop.md)**, itself superseded 2026-09-24 by **[`contracts/capability-resolution-loop.md`](contracts/capability-resolution-loop.md)** (`use_capability`/`note` removed; `load_capability` attaches prompt + real tools; persisted loaded set; `unload_capability`/`reset_to_backbone`; idle reset) — one merged backbone call, zero hand-authored JSON, four real function-calling tools (`load_capability`, `use_capability`, `record_planning_status`, `send_to_user`) driving a generalized version of the existing chained tool-dispatch loop. `contracts/intent-planning-loop.md` is retained as historical record only, marked superseded.
- Q: Does this feature also add fee-agreement document generation (Feature 083's capability) to the Backbone? → A: Yes, as a new `cap_docx_write` domain capability — design: **[`contracts/docx-write-capability.md`](contracts/docx-write-capability.md)**. Wraps `FeeAgreementToolHandler`/`DocTemplateEngine` unmodified; needs its own inner multi-round tool-dispatch loop (get_template→render→verify→send, no approval gate) local to that one capability.

---

## Capability Plugin Taxonomy (revised 2026-09-14, second plan-phase pass)

The Backbone is a thin, always-alive **backbone kernel** — it holds only the constant
persona/boundaries/always-on UX pieces below as static prompt text. Everything that involves
*deciding what to do* is itself a capability, with its own dedicated prompt, invoked by the
backbone as a tool/followup step (see `research.md` R2) — including the backbone's own
reasoning steps. (Revised 2026-09-24: there are only domain capabilities — the backbone itself is one tool-driven loop, `contracts/capability-resolution-loop.md`.)

- **Domain capabilities** — the same 6 write/read business-domain plugins as the first pass, plus
  a 7th: **Media Analysis**, folding in what was previously two standalone files
  (`prompts/image_analysis.txt`, `prompts/docx_analysis.txt`) outside any capability structure at
  all.

**Note on the method names below**: these name the existing `ai_handler.py` methods whose
*behavior* the new capability code reimplements — a reference for equivalence, not a list of
methods being extracted or removed. Per REQ-063-07 (revised 2026-09-30), `ai_handler.py` is modified only to move shared logic out into shared modules, leaving thin wrappers.

**Backbone (static prompt text, always loaded, every turn)** — behavioral constants only, nothing
that requires "deciding what's next":
- Core Identity, Behavioral Guidelines, User Roles, Privacy & Security, Contexts of Operation
- Group Conversation Etiquette, Edited & Deleted Message Markers
- The generic post-turn-recognition mechanism (moved out of `config/ledger_recognition_prompt.md`
  — the reusable "run once, call your report tool exactly once, when in doubt do nothing" protocol
  shape, parameterized per capability rather than ledger-specific)
- Proactive Progress Updates (`_build_progress_update_tools`, `_handle_send_progress_update`, `_call_openai_send_progress_update_followup_api`, `_compute_send_progress_update_outputs`)
- Reaction Management (`_resolve_react_to_message_target`, `_call_openai_react_to_message_followup_api`, `_compute_react_to_message_outputs`, `_handle_react_to_message`)

**Domain capabilities** (own prompt + tools, loaded by the model via `load_capabilities` (and organized into blueprint **flows**, `load_flows`, under `config/prompts/flows/`), which attaches the prompt AND the real tools):
- **Invoicing/Morning — Write**: `create_invoice`, `create_transaction_account`, `create_combo_document`, `create_credit_note`, `create_receipt`, `create_combo_document_as_reference`, `cancel_transaction_account`, `add_client`, `update_client` (Morning MCP tools; `_build_morning_mcp_tools` write subset)
- **Invoicing/Morning — Read**: `list_invoices`, `get_invoice_details`, `list_clients`, `resolve_client_name`, `get_client_details`, `get_financial_summary`, `download_invoice_pdf`
- **Ledger capture is not a capability** (revised 2026-09-24): recognizing and recording fee agreements/bank deposits is `denidin.py`'s shared post-turn recognition step (`_run_post_turn_ledger_recognition`), which sees every turn; the Backbone only keeps the generic post-turn-recognition mechanism text.
- **Ledger Events — Query**: `query_ledger_events`, `_handle_query_ledger_events`, `_call_openai_query_ledger_events_followup_api`, `_compute_query_ledger_events_outputs` — the read side of `ledger_event_manager.py`
- **Reminders — Write**: `create_reminder`/`modify_reminder`/`delete_reminder` (`_handle_reminder_creation_proposal`, `_handle_reminder_modify_or_delete_proposal`, `_propose_reminder_modify_or_delete`, `_call_openai_reminder_followup_api`) — the write side of `reminder_manager.py`
- **Reminders — Read**: `list_reminders` (`_handle_list_reminders`, `_call_openai_list_reminders_followup_api`, `_compute_list_reminders_outputs`) — the read side of `reminder_manager.py`
- **Media Analysis** (NEW, previously not a capability at all): image/PDF/DOCX extraction —
  functionally equivalent to `ImageExtractor`/`PDFExtractor`/`DOCXExtractor`'s existing logic
  (`handlers/extractors/*.py`, all untouched per REQ-063-07), reached as a tool the backbone's
  plan can call for any media message, whether the plan then routes the extracted text to Ledger
  Capture, Invoicing, both, or neither, rather than today's fixed "media always gets ledger
  recognition run on it" behavior.

`session_manager.py` (991 lines, REQ-063-03) is cross-cutting infrastructure shared by every
capability and the Backbone alike (session/window resolution), not itself a capability. It stays
exactly where it is and unmodified — imported, as-is, by both the legacy `AIHandler` and the new
backbone (see `plan.md`'s Project Structure).

---

## 2. PM Requirements (Functional)

- **REQ-063-01 (The Backbone)**: The system MUST define a core Backbone prompt that is always loaded, containing only static behavioral constants (persona, operating boundaries, always-on UX: Progress Updates, Reactions, Group Etiquette, Edited/Deleted Markers, the generic post-turn-recognition mechanism) — no routing/classification logic as static text (the model's own `load_capability` choice does that, REQ-063-04).
- **REQ-063-02 (Capability Separation)**: A new `config/prompts/` folder MUST be authored (backbone.md + capabilities/*.md — domain capabilities per the taxonomy above), consolidating what is today split across `config/runtime_constitution.md`, `config/ledger_recognition_prompt.md`, and the standalone `prompts/image_analysis.txt`/`prompts/docx_analysis.txt`. All of those existing files are left untouched (REQ-063-07) — the new folder is additive.
- **REQ-063-03 (Code Separation, New Module)**: A new backbone module (parallel to, not replacing, `ai_handler.py`) MUST implement the Backbone-as-backbone + capability logic per the taxonomy above. `managers/ledger_event_manager.py` and `managers/reminder_manager.py` MUST stay exactly where they are, completely unmodified — the new backbone's capability handlers import from those same existing locations rather than duplicating their storage logic; `handlers/extractors/*.py` (Media Analysis's existing equivalent) likewise stay untouched and are imported, not duplicated. `ai_handler.py` itself requires zero changes, including zero import changes. `session_manager.py` is Backbone-layer shared infrastructure, used unmodified by both implementations, not a capability.
- **REQ-063-04 (Model-Driven Dynamic Loading, not a Separate Classifier)**: The Backbone MUST NOT statically embed routing/classification logic as prompt text, and there is no separate Intent Identification/Planning call. The model itself decides which capability(ies) a request touches (guided by the rendered capability catalog) and calls `load_capability`; the loaded set persists per chat (`Session.active_capabilities`) and is managed with `unload_capability`/`reset_to_backbone` plus an idle sweep (`capabilities_reset_minutes`). Instructions AND tools are rebuilt from that set on every call. Multi-capability turns (UAT3) are simply several loaded capabilities. See `contracts/capability-resolution-loop.md`.
- **REQ-063-04a (Media as an Driven Tool, not a Pre-Route)**: Media messages MUST enter through the same Backbone as text messages — no separate deterministic pre-Backbone media-routing step. Media Analysis (extraction) is a capability the model can load and call (`analyze_media`); it then continues based on the extracted content (e.g. loading Invoicing, or neither).
- **REQ-063-06 (Cache-Prefix Preservation)**: The Backbone content MUST remain the stable, byte-identical prefix of every call (as `runtime_constitution.md` is today); loaded capability content MUST be appended after it in a deterministic, canonical order so that repeated identical capability-sets across turns continue to hit OpenAI's prompt cache.
- **REQ-063-05 (Zero Behavioral Regression)**: Despite the massive structural changes, the end-user MUST NOT experience any degradation in existing features. All existing `billed`/`expensive`/`sanity` E2E tests MUST pass without changing the test definitions themselves, against both implementations (flag off and flag on). Unit tests for the new backbone are new, standalone unit tests, not rewrites of `AIHandler`'s existing ones.
- **REQ-063-08 (DeniDin Owns the App; One AIManager — added 2026-10-02)**: The `DeniDin` object owns DeniDin's data and infrastructure (users, sessions, roll markers, memory, ledger events, reminders, the Morning MCP locator, telemetry, the chat log, the document template engine, its own WhatsApp number, the OpenAI client, `last_response`), built by `initialize_app` regardless of the flag. The AI implementation is one more object of the app, not the one controlling it: an abstract `AIManager` with exactly two implementations, `AIHandler` (flag off) and `Backbone` (flag on), held by `DeniDin` as its single `ai_manager`. With the flag on, `AIHandler` and everything only it owns (its pending-approval managers) MUST NOT be constructed at all; with the flag off, `Backbone` is not constructed. Logic both implementations need is a single implementation in the `AIManager` base class. Everything else reads data from `DeniDin`, and reads `ai_manager` only for AI-related needs. Ledger-event recognition and accounting reconciliation are their own classes, not `AIManager` methods. Found 2026-10-02: billed tests silently read the legacy handler's never-written approval state with the flag on (every lookup returned `None`, never an error), because `AIHandler` was still constructed unconditionally and every service reached DeniDin's data through it.
- **REQ-063-07 (Separate Path, Shared Code — revised 2026-09-30)**: The Backbone is a **separate PATH**, not a separate reimplementation of working functionality. `denidin.py`'s `initialize_app` selects, once at startup, which path to construct based on `config.feature_flags.enable_capability_backbone`, and dispatches to it explicitly (legacy `AIHandler.get_response` vs `Backbone.turn_with_rounds`). Any logic both paths need — calling the model with retry, fallback responses, turn persistence, the rolling window, memory recall, the [[NO_REPLY]] check, tool actions — MUST exist exactly once, in a shared module (`src/core/`, `src/tool_actions/`), called by both; never copied into the backbone. `ai_handler.py` is LEGACY and will be deleted: the Backbone MUST NEVER import, inject, or call it. When the Backbone needs logic that currently lives in `ai_handler.py` (or legacy `MediaHandler`), that logic is refactored out into a shared module and `ai_handler.py` keeps a thin wrapper — `ai_handler.py` MAY be modified for this, provided the flag-off path's behavior is unchanged. The new prompt set (`config/prompts/`) stays separate from `runtime_constitution.md`/`ledger_recognition_prompt.md`/`prompts/*.txt`, which remain untouched while the flag exists. (Supersedes the 2026-09-14 "parallel implementation, byte-for-byte untouched" wording, which produced drifting "mirrors AIHandler" copies — e.g. the Backbone's own `_persist_turn` had lost `whatsapp_id_message`, interim messages and the replay offset.) **Feature flags are opt-in per CONSTITUTION.md §VI (revised 2026-09-14, same day)** — this feature keeps one because the human explicitly requested it for this specific large refactor, not because flags are now a default for new work.

---

## 3. Success Criteria
- **SC-002**: The new `config/prompts/backbone.md` contains only static behavioral constants, with the domain capabilities in `config/prompts/capabilities/*.md`; `config/runtime_constitution.md`, `config/ledger_recognition_prompt.md`, and `prompts/*.txt` are all untouched and still used verbatim by the legacy `AIHandler`/extractor path.
- **SC-003**: 100% pass rate on `billed` and `expensive` test suites, proving zero behavioral regression.
- **SC-004**: Average token input count per conversation turn (text and media alike) drops significantly, proving driven dynamic loading works — including media turns, which today unconditionally load the full constitution for every vision call.
- **SC-005**: A turn matching zero domain capabilities (e.g. small talk) measurably hits OpenAI prompt caching on the Backbone prefix, and a turn matching the same capability set as a prior turn also hits cache on the appended capability content (REQ-063-06), measured via `scripts/model_sanity_check.sh`-style `cached_tokens` inspection.
