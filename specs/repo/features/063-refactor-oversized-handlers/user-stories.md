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
