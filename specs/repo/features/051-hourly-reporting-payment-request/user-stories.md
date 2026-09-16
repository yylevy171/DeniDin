# User Stories & Acceptance Criteria: Feature 051 (Hourly Reporting & Payment Request Creation)

## Business Value & Overview
Enables third-party payer (union/employer) billing for employee legal representation. Law practitioners log time naturally via WhatsApp, receive immediate budget/cap awareness, review a generated `.docx` report with the payer, and finalize billable hours by issuing Morning Type 300 Transaction Account documents without double-billing risk.

---

## User Acceptance Testing (UAT)

### UAT 1: Natural Language Time Logging & Real-Time Cap Awareness (Priority: P1)
**Given** a Client profile is configured with an active Payer Agreement (specifying `payer_id`, `hourly_rate`, and `max_cap`)
**When** the lawyer submits an hourly log via WhatsApp message (e.g., *"עבדתי 1.5 שעות עבור יוסי כהן על כתב תביעה"*)
**Then** the system MUST persist an unbilled hourly entry in the ledger with date, duration, description, client reference, and linked payer
**And** the system MUST reply in WhatsApp confirming the logged entry, reporting current accumulated monthly hours, and calculating total accrued NIS against the agreement cap (e.g., *"נרשמו 1.5 שעות. סה״כ החודש: 7.5 שעות מתוך תקרה של 10 שעות (1,500 ש״ח מתוך 2,000 ש״ח)"*).

---

### UAT 2: On-Demand DOCX Payer Report Generation (Priority: P1)
**Given** unbilled hours exist across one or more clients linked to a specific Payer (e.g., "הראל")
**When** the lawyer sends a command via WhatsApp requesting the billing report (e.g., *"הפק דוח שעות חודשי עבור הראל"*)
**Then** the system MUST compile all unbilled hours for that payer and invoke `doc_template_engine` using the approved multi-client hourly template
**And** the generated document MUST be a `.docx` containing distinct tables per client (displaying date, task description, hours, rate, and subtotal per client, plus grand total)
**And** the system MUST deliver the generated `.docx` file directly back to the lawyer within the WhatsApp conversation for manual review and payer transmission.

---

### UAT 3: Locking Billed State via Morning Type 300 Generation (Priority: P1)
**Given** the lawyer and payer have reviewed and confirmed the monthly totals from the generated DOCX report
**When** the lawyer instructs the system to issue a payment request (e.g., *"צור חשבון עסקה עבור יוסי כהן על סך 1,500 ש״ח"* or consolidated for the payer)
**Then** the system MUST invoke Morning MCP to generate the Transaction Account document (Document Type 300)
**And** upon successful document creation, the system MUST transition the status of every underlying logged hour covered by that amount from `unbilled` to `billed`
**And** the system MUST stamp each logged hour with the Morning document ID / reference for complete auditability.

---

### UAT 4: Double-Billing Prevention on Subsequent Reports (Priority: P1)
**Given** previously logged hours for a payer have transitioned to `billed` status via UAT 3
**When** the lawyer subsequently requests a new monthly report or subsequent billing cycle for that payer
**Then** all hours marked as `billed` MUST be excluded from the newly generated DOCX report and total calculations
**And** only new `unbilled` hours entered after the Type 300 generation may be aggregated.

---

### UAT 5: Legacy Hourly Data Reconciliation & Migration (Priority: P2)
**Given** the production ledger contains pre-existing unstructured or partial hourly event entries from prior months
**When** the engineering migration script is executed during deployment
**Then** all legacy hourly entries MUST be transformed to match the new Client/Payer/Agreement schema with default fallback attributes
**And** the WebApp and Player interfaces MUST continue loading and displaying historical ledger records with zero rendering crashes or schema validation failures.
