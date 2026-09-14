# Feature Specification: The Dynamic Capability Backbone (Refactor 063 + 073 + 085)

**Feature Branch**: `feature/063-refactor-oversized-handlers` (Bundled with 073, 085 — both filed
under `specs/obsolete/`, their scope absorbed here)
**Status**: Draft
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

- Q: Should this refactor be an in-place strip-down of `ai_handler.py`/`runtime_constitution.md` behind a feature flag, or two fully separate, parallel implementations? → A: Two fully separate implementations. `ai_handler.py` and `runtime_constitution.md` stay byte-for-byte untouched for as long as the flag exists; the Backbone+Plugins path is entirely new code (`config/backbone.md`, `config/capabilities/*.md`, a new orchestrator module), selected once at `denidin.py`'s `initialize_app` startup based on `config.feature_flags.enable_capability_backbone`. This directly informed dropping the old SC-001 (see below) and rewriting REQ-063-02/03 as REQ-063-07.
- Q: With `ai_handler.py` no longer shrinking under this design, what replaces the old SC-001 ("`ai_handler.py` reduced by ≥70%")? → A: Dropped entirely — no line-count target. Success is measured by SC-002 (constitution split) and SC-004 (token reduction), not by `ai_handler.py`'s size, since it is intentionally never modified.

---

## Capability Plugin Taxonomy

Organizing principle (2026-09-14): a capability lives in the **Backbone** if the user always
expects it to be available regardless of topic (it is UX, not a domain); it becomes a **gated
Plugin** only if it is topic-specific and can genuinely be skipped on turns that don't need it.
Within the gated plugins, each topic that has both a state-changing and a read-only surface is
split along that seam, since write flows carry approval-gating (Feature 022/047's pending-approval
UX) that read flows don't, and the two have materially different response shapes.

**Note on the method names below (updated 2026-09-14, plan-phase revision)**: these name the
existing `ai_handler.py` methods whose *behavior* the new Backbone/plugin code reimplements —
they are a reference for what the new code must do equivalently, not a list of methods being
extracted or removed. Per REQ-063-07, `ai_handler.py` itself is never modified; these methods stay
exactly where they are, doing exactly what they do today, for the legacy path.

**Backbone (always loaded, every turn)** — the new orchestrator's always-on logic, functionally
equivalent to these existing behaviors:
- Core Identity, Behavioral Guidelines, User Roles, Privacy & Security, Contexts of Operation
- Group Conversation Etiquette, Edited & Deleted Message Markers
- Intent recognition / the pre-classifier routing step itself (REQ-063-04)
- Proactive Progress Updates (`_build_progress_update_tools`, `_handle_send_progress_update`, `_call_openai_send_progress_update_followup_api`, `_compute_send_progress_update_outputs`)
- Reaction Management (`_resolve_react_to_message_target`, `_call_openai_react_to_message_followup_api`, `_compute_react_to_message_outputs`, `_handle_react_to_message`)

**Capability Plugins (loaded only when the pre-classifier matches them)** — 6 plugins, 3 domains
× write/read:
- **Invoicing/Morning — Write**: `create_invoice`, `create_transaction_account`, `create_combo_document`, `create_credit_note`, `create_receipt`, `create_combo_document_as_reference`, `cancel_transaction_account`, `add_client`, `update_client` (Morning MCP tools; `_build_morning_mcp_tools` write subset)
- **Invoicing/Morning — Read**: `list_invoices`, `get_invoice_details`, `list_clients`, `resolve_client_name`, `get_client_details`, `get_financial_summary`, `download_invoice_pdf`
- **Ledger Events — Capture**: `recognize_ledger_event`, `capture_ledger_events_from_text`, `_handle_accounting_reconciliation_capture` — the write side of `ledger_event_manager.py` (one of the "3 other files" this feature also refactors)
- **Ledger Events — Query**: `query_ledger_events`, `_handle_query_ledger_events`, `_call_openai_query_ledger_events_followup_api`, `_compute_query_ledger_events_outputs` — the read side of `ledger_event_manager.py`
- **Reminders — Write**: `create_reminder`/`modify_reminder`/`delete_reminder` (`_handle_reminder_creation_proposal`, `_handle_reminder_modify_or_delete_proposal`, `_propose_reminder_modify_or_delete`, `_call_openai_reminder_followup_api`) — the write side of `reminder_manager.py`
- **Reminders — Read**: `list_reminders` (`_handle_list_reminders`, `_call_openai_list_reminders_followup_api`, `_compute_list_reminders_outputs`) — the read side of `reminder_manager.py`

`session_manager.py` (991 lines, REQ-063-03) is cross-cutting infrastructure shared by every
plugin and the Backbone alike (session/window resolution), not itself a capability plugin. Per the
plan-phase revision (2026-09-14), it stays exactly where it is and unmodified — imported, as-is,
by both the legacy `AIHandler` and the new orchestrator (see `plan.md`'s Project Structure).

---

## 2. PM Requirements (Functional)

- **REQ-063-01 (The Backbone)**: The system MUST define a core Backbone prompt that is always loaded. It must contain the core persona, the strict operating boundaries, a directory of available capabilities, the always-on UX behaviors (Progress Updates, Reactions, Group Etiquette, Edited/Deleted Markers), and the intent pre-classifier routing step.
- **REQ-063-02 (Capability Separation)**: A new `config/backbone.md` + `config/capabilities/*.md` file set MUST be authored, splitting the equivalent of today's `runtime_constitution.md` content into distinct capability markdown files per the Capability Plugin Taxonomy above (6 plugin files + the Backbone file). `config/runtime_constitution.md` itself is left untouched (REQ-063-07).
- **REQ-063-03 (Code Separation, New Module)**: A new orchestrator module (parallel to, not replacing, `ai_handler.py`) MUST implement the Backbone+Plugins turn-handling logic, organized into cohesive Capability Plugin code per the taxonomy above (a single "Capability" encapsulates both its handler logic and its manager logic). `managers/ledger_event_manager.py` and `managers/reminder_manager.py` MUST stay exactly where they are, completely unmodified — the new orchestrator's capability handlers import from those same existing locations rather than duplicating their storage logic; `ai_handler.py` itself requires zero changes, including zero import changes, since it already imports these modules from where they already live. `session_manager.py` is Backbone-layer shared infrastructure, used unmodified by both implementations, not a plugin.
- **REQ-063-04 (Dynamic Loading)**: A cheap pre-classifier LLM call, run before the main turn call, MUST determine which capability plugin(s) apply to the current user turn; only the matched plugin(s)' prompt+tools MUST be attached to the main call. Multi-capability turns (UAT3) attach the union of matched plugins.
- **REQ-063-06 (Cache-Prefix Preservation)**: The Backbone content MUST remain the stable, byte-identical prefix of every call (as `runtime_constitution.md` is today); matched capability plugin content MUST be appended after it in a deterministic, canonical order (e.g. taxonomy order) so that repeated identical capability-sets across turns continue to hit OpenAI's prompt cache.
- **REQ-063-05 (Zero Behavioral Regression)**: Despite the massive structural changes, the end-user MUST NOT experience any degradation in existing features. All existing `billed`/`expensive`/`sanity` E2E tests MUST pass without changing the test definitions themselves, against both implementations (flag off and flag on). Unit tests for the new orchestrator are new, standalone unit tests, not rewrites of `AIHandler`'s existing ones.
- **REQ-063-07 (Parallel Implementation, not In-Place Refactor)**: `ai_handler.py` and `runtime_constitution.md` MUST remain fully untouched (byte-for-byte) for as long as `config.feature_flags.enable_capability_backbone` exists as a flag. The Backbone + 6 Capability Plugins are a **new, separate** orchestrator module and a new `config/backbone.md` + `config/capabilities/*.md` file set — not an in-place strip-down of the existing files. `denidin.py`'s `initialize_app` selects, once at startup, which implementation (`AIHandler` vs. the new orchestrator) to construct, based on the flag; the rest of `denidin.py` (routing, `WhatsAppHandler`, etc.) is unaware which one it's talking to (both expose the same `get_response`/`resolve_button_tap`/etc. interface).

---

## 3. Success Criteria
- **SC-002**: The new `config/backbone.md` contains only core backbone rules, with the 6 capability plugins in `config/capabilities/*.md`; `config/runtime_constitution.md` is untouched and still used verbatim by the legacy `AIHandler` path.
- **SC-003**: 100% pass rate on `billed` and `expensive` test suites, proving zero behavioral regression.
- **SC-004**: Average token input count per conversation turn drops significantly, proving dynamic prompt loading works.
- **SC-005**: A turn matching zero capability plugins (e.g. small talk) measurably hits OpenAI prompt caching on the Backbone prefix, and a turn matching the same capability plugin(s) as a prior turn also hits cache on the appended plugin content (REQ-063-06), measured via `scripts/model_sanity_check.sh`-style `cached_tokens` inspection.
