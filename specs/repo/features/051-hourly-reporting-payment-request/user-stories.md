# User Stories & Acceptance Criteria: Feature 051 (Hourly Reporting & Payment Request Creation)

## Business Value & Overview
Enables third-party payer (union/employer) billing for employee legal representation. Law practitioners log time naturally via WhatsApp, receive immediate budget/cap awareness, review an on-demand generated `.docx` report with the payer, and maintain clean historical continuity across the ecosystem.

---

## User Acceptance Testing (UAT)

### UAT 1: Natural Language Time Logging with Reference Population & Inferred Context (Priority: P1)
**Given** the payer has been successfully identified through the client resolution routine in Morning
**When** the lawyer reports hours via WhatsApp (e.g., *"עבדתי 1.5 שעות עבור יוסי כהן על כתב תביעה"*)
**Then** a ledger event MUST be recorded with:
- `payer`: The resolved Morning client/payer name.
- `description`: The task performed ("כתב תביעה").
- `reference` and `reference_hint`: Populated to link the event to the agreement (or agreement reference details) if an agreement is identified. If no agreement is found, these fields reflect that accordingly.
**And** the bot does NOT output a rigid template; instead, the AI infers the natural question *"what is the current status for this client/agreement?"* and provides a dynamic status assessment based on whatever context it finds across the ledger and active agreements.

---

### UAT 2: End-to-End Client & Payer Resolution Chain (Priority: P1)
**Given** the lawyer sends a bare-bones hourly report in WhatsApp specifying only client and hours (e.g., *"3 שעות עבור אלכס בלכס"*)
**When** the system receives the message and executes the resolution pipeline:
1. Search for the client name in the ledger/system ("אלכס בלכס").
2. Determine the affiliated paying entity (payer name).
3. Verify that the payer name exists in Morning via `resolve_client`.
**Then** the outcome MUST satisfy:
- **Happy Path (Complete Chain Resolved):** If client is found, payer is determined, and payer exists in Morning:
  - No clarifying questions asked.
  - Ledger event is persisted immediately with `reference` and `reference_hint` populated.
  - AI provides its contextual status summary directly.
- **Broken Chain (Clarification Gate):** If any link in the chain fails:
  - **No ledger event is persisted.**
  - The bot prompts the lawyer in WhatsApp for the specific missing link (seeds/clarifies client name, asks for payer attachment, or clarifies/creates payer in Morning).
  - The ledger event is created ONLY after the entire chain is whole.

---

### UAT 3: On-Demand DOCX Payer Report Generation (Priority: P1)
**Given** unbilled hours exist across several clients who share the same affiliated Payer (e.g., "הראל")
**When** the lawyer sends a natural language command via WhatsApp (e.g., *"הפק דוח שעות חודשי עבור הראל"*)
**Then** the system MUST query all currently unbilled hours affiliated with payer "הראל"
**And** the system MUST execute `doc_template_engine` using the verified DOCX template to generate a single `.docx` file containing:
- Header details for the payer ("הראל") and the relevant period/date.
- Structured tables per client (showing date, description of work, hours, rate, and totals).
- Grand totals aggregated across all clients for this payer.
**And** the generated `.docx` file MUST be delivered directly to the lawyer via WhatsApp as a document message for manual review and payer transmission.

---

### UAT 4: Legacy Hourly Data Reconciliation & Migration (Priority: P2)
**Given** the production ledger currently contains historical, unstructured, or partially populated hourly entries from prior months
**When** the engineering migration script executes against the production ledger files as part of the deployment runbook
**Then** all existing hourly events in the ledger MUST be reconciled and updated to populate the correct client, payer, and agreement references (using `reference` and `reference_hint`) where inferrable, or marked with clean fallbacks
**And** the UI dashboard (`apps/webapp`) and the session player (`apps/denidin-app/src/player`) MUST successfully load, parse, and render the historical events without any schema mismatches, missing key exceptions, or frontend crashes.
