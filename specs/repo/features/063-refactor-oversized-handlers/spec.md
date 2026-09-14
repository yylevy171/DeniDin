# Feature Specification: The Dynamic Capability Backbone (Refactor 063 + 085)

**Feature Branch**: `feature/063-refactor-oversized-handlers` (Bundled with 085)
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

## 2. PM Requirements (Functional)

- **REQ-063-01 (The Backbone)**: The system MUST define a core Backbone prompt that is always loaded. It must contain the core persona, the strict operating boundaries, and a directory of available capabilities.
- **REQ-063-02 (Capability Separation)**: The `runtime_constitution.md` MUST be split into distinct capability markdown files (e.g., `invoice_rules.md`, `ledger_rules.md`).
- **REQ-063-03 (Code Separation)**: The `ai_handler.py` MUST be split into distinct capability python modules (e.g., `invoice_handler.py`, `ledger_handler.py`).
- **REQ-063-04 (Dynamic Loading)**: The AI or router MUST dynamically load a capability's specific prompt/rules *only* when that capability is invoked or deemed necessary for the current user turn.
- **REQ-063-05 (Zero Behavioral Regression)**: Despite the massive structural changes, the end-user MUST NOT experience any degradation in existing features. All existing E2E/billed tests MUST pass without changing the test definitions.

---

## 3. Success Criteria
- **SC-001**: `ai_handler.py` is reduced by at least 70% in line count.
- **SC-002**: `runtime_constitution.md` is reduced to only core backbone rules, with the rest distributed to plugins.
- **SC-003**: 100% pass rate on `billed` and `expensive` test suites, proving zero behavioral regression.
- **SC-004**: Average token input count per conversation turn drops significantly, proving dynamic prompt loading works.
