# User Stories: The Dynamic Capability Backbone (Refactor 063 + 085)

## Business Goal
Evolve the DeniDin AI agent from a massive, singular monolith into a flexible, modular routing engine (Backbone + Plugins). This restructuring enables rapid feature expansion (by just dropping in new plugins) and reduces token costs by only loading capability prompts when strictly needed. The user must experience zero degradation in current functionality.

---

## User Acceptance Testing (UAT)

Because this feature changes the *entire* architectural foundation of how prompts and handlers are executed, the testing bar is absolute: every single existing user flow must work exactly as before.

### UAT 1: Zero Behavioral Regression (Priority: P1)
**Given** the user interacts with the system using existing capabilities (e.g., uploading a bank transfer image, asking about an invoice, setting a reminder)
**When** the AI's new "Backbone" router intercepts the message
**Then** it MUST correctly route to the specific capability module, load that module's constitution rules, and respond perfectly.
**And** 100% of the `tests/billed/` and `tests/expensive/` E2E test suites MUST pass without any modifications to the test files themselves.

### UAT 2: Proof of Dynamic Prompt Loading (Priority: P1)
**Given** a user asks a simple conversational question (e.g., "Good morning, how are you today?")
**When** the Backbone processes the message
**Then** it MUST NOT load the constitution rules or handlers for Ledger Events, Invoices, or Reminders.
**And** the telemetry/logs MUST prove that the LLM was only fed the "Core Backbone" system prompt, significantly reducing the input token count compared to the legacy system.

### UAT 3: Multi-Capability Routing (Priority: P2)
**Given** a user asks a complex question that crosses capability domains (e.g., "Remind me tomorrow to check if Yossi paid his invoice")
**When** the Backbone processes the message
**Then** it MUST successfully recognize the need for both the "Reminders" capability and the "Invoice/Ledger" capability.
**And** it MUST load both sets of capability rules dynamically and execute the correct handlers to satisfy the request seamlessly.

---

## Acceptance Scenarios (§VI.a — explicit human decision, 2026-09-14)

**No new `billed`/`expensive` acceptance scenarios are defined for this feature.** This is a pure
structural refactor — no new user-facing behavior, no new capability, nothing a real person can do
today that they couldn't before, or vice versa. The zero-regression bar (UAT 1, REQ-063-05) *is*
the acceptance criterion, and it is already fully covered by the **pre-existing, unmodified**
`tests/billed/` and `tests/expensive/` suites — every existing user flow (invoicing, ledger capture,
ledger querying, reminders, reactions, progress updates, group etiquette) already has real
user-perspective coverage there. Re-describing those same flows as new AS-N scenarios here would
be pure duplication, not new signal.

Per §VI.a step 4, that pre-existing suite is run once, together, at the end — after every
unit/integration task is GREEN — exactly as it would be for any other change; this feature adds no
scenarios beyond it, and this section satisfies the "define acceptance scenarios before
`speckit.plan`" gate by explicitly recording that decision.

UAT 2 (dynamic-loading proof) and UAT 3 (multi-capability routing) and REQ-063-06/SC-005 (cache
preservation) are internal architectural properties, not user-observable scenarios — they are
verified via telemetry/instrumentation (e.g. a `model_sanity_check.sh`-style script inspecting
`instructions` size and `cached_tokens`) during `speckit.plan`/`speckit.tasks`, not as pytest
acceptance tests. `speckit.plan` should define the concrete instrumentation for this.
