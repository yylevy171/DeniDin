# Feature Specification: Hourly Reporting & Payment Request Creation

**Feature Branch**: `feature/051-hourly-reporting-payment-request`
**Created**: 2026-08-13
**Status**: DRAFT (Backlog)
**Input**: CEO requirement to support B2B professional services billing, specifically tracking hourly work against union/payer agreements, generating monthly reporting DOCX files, and issuing Morning API Transaction Account documents (Type 300).

---

## 1. Business & Architectural Goals

DeniDin currently operates on flat-fee retainers where the client is the payer. To support unionized legal representation, DeniDin must evolve into a B2B third-party billing engine where the "Client" (the worker) is distinct from the "Payer" (the Union). 

**The Goal**: Enable the lawyer to naturally log hours worked per client via WhatsApp, automatically track those hours against a defined agreement (rate and cap), generate a detailed monthly DOCX report for the Payer to audit, and finally lock those hours as "Billed" by generating a Morning API Transaction Account document (Type 300).

---

## 2. PM Requirements (Functional Scope)

### 2.1 The Data Model: Definitions & Agreements
- **REQ-051-01 (Payer vs Client)**: The data model MUST decouple the Payer (the entity receiving the invoice) from the Client (the individual receiving the service).
- **REQ-051-02 (Agreements)**: The Client profile MUST support an `Agreement` definition containing:
  - `payer_id`: The ID of the Payer/Union footing the bill.
  - `hourly_rate`: The fixed hourly rate agreed upon with the Payer.
  - `max_cap`: The total or monthly billable limit for this specific client.
  - `payer_reference_id`: A generic field for external case numbers required by the Payer (e.g., Harel case IDs).

### 2.2 Time Tracking via WhatsApp
- **REQ-051-03 (Logging)**: The lawyer MUST be able to log hours in natural language via WhatsApp (e.g., "Worked 1.5 hours for Yossi on statement of claim").
- **REQ-051-04 (Feedback Loop)**: Upon logging, the system MUST reply to the lawyer confirming the entry and displaying the running monthly total (hours and expected revenue) against the Client's `max_cap`.

### 2.3 Monthly Reporting (DOCX)
- **REQ-051-05 (Manual Trigger)**: The lawyer MUST be able to manually trigger a report generation via WhatsApp (e.g., "Generate the monthly report for Harel").
- **REQ-051-06 (DOCX Artifact)**: The system MUST query all *unbilled* hours for the requested Payer and use the `doc_template_engine.py` to generate a `.docx` file based on a pre-defined template. The document must include tables detailing hours, days, and amounts per client.
- **REQ-051-07 (Review Buffer)**: DeniDin MUST send this generated `.docx` file to the lawyer in WhatsApp for review. (Manual edits to the DOCX or ledger JSON are acceptable if the Payer disputes an hour).

### 2.4 Invoicing & State Management
- **REQ-051-08 (Type 300 Generation)**: Once the Payer approves the DOCX report, the lawyer MUST be able to instruct DeniDin to create a Transaction Account Document (Type 300) in Morning (one per client, or consolidated, depending on Payer preference).
- **REQ-051-09 (The "Billed" Lock)**: The exact moment the Type 300 document is successfully generated, the underlying logged hours MUST be permanently marked as "Billed" in the ledger so they are excluded from future monthly reports.

### 2.5 Prod Data Migration
- **REQ-051-10 (Reconciliation Script)**: A one-off migration script MUST be written to scan the production ledger for legacy, unstructured hourly logs and retroactively map them to the new Client/Payer/Agreement schema so they can be invoiced.

---

## 3. Success Criteria
- **SC-001**: A lawyer can log hours for a client and receive an immediate WhatsApp reply showing the updated monthly running total against the agreement cap.
- **SC-002**: The system successfully generates a correctly formatted `.docx` file containing all unbilled hours for a specific Payer and sends it to the lawyer via WhatsApp.
- **SC-003**: Generating a Type 300 document successfully locks the associated hours as "Billed", preventing them from appearing in subsequent DOCX reports.
- **SC-004**: The data migration script successfully upgrades all legacy hourly logs in production without data loss.
