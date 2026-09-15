# Feature Specification: Support Bit, PayBox, Checks, and Cash

**Feature Branch**: `feature/066-support-bit-and-paybox`
**Created**: 2026-08-30
**Status**: DRAFT (Backlog)
**Input**: CEO requirement to support 4 new deposit flows (Bit, PayBox, Checks, Cash) by fundamentally refactoring the ledger data model to unify all deposits under a single `deposit` event type.

---

## 1. Business & Architectural Goals

Historically, DeniDin only supported standard Bank Transfers (recorded as `type="bank", subtype="deposit"`). When clients send screenshots of Bit, PayBox, or Check deposits, the AI either fails to recognize them or hallucinates incorrect bank details.

**The Goal**: Expand DeniDin's accounting capabilities to natively support the 4 most common alternative payment methods in Israel: Bit, PayBox, Checks (via image), and Cash (via text).

To do this cleanly, we are **flipping the data model**. Instead of making everything a subset of "bank", all incoming funds will be unified under a single primary event type (`deposit`), with the payment method acting as the subtype.

---

## 2. PM Requirements (Functional Scope)

### 2.1 The Data Model "Flip"
- **REQ-066-01**: The ledger event data model MUST be refactored. The event type for all incoming funds MUST be `deposit` (הפקדה).
- **REQ-066-02**: The event subtype MUST explicitly declare the payment method. Valid subtypes are: `bank` (בנק), `bit` (ביט), `paybox` (פייבוקס), `check` (צ׳ק), and `cash` (מזומן).

### 2.2 New Capture Flows
- **REQ-066-03 (Bit & PayBox)**: The AI MUST recognize Bit and PayBox transfer screenshots, extract the relevant sender details and amounts, and record them as `deposit` + `bit`/`paybox`.
- **REQ-066-04 (Checks)**: The AI MUST recognize images of checks, extract the amount, bank details, and check number, and record them as `deposit` + `check`.
- **REQ-066-05 (Cash)**: The AI MUST recognize natural language text inputs indicating cash receipt (e.g., "Received 500 NIS in cash from Yossi") and record it as `deposit` + `cash`.

### 2.3 Morning API Integration
- **REQ-066-06 (Receipts & Combos)**: The Morning API handlers for Receipts (Type 320) and Combo Documents (Type 400) MUST be updated to accept all 5 subtypes and correctly map them to the corresponding Morning API `payment_type` fields.

### 2.4 Data Migration
- **REQ-066-07 (Migration Script)**: A one-off migration script MUST be created and executed against the production `events/` folder to rewrite all historical `type="bank", subtype="deposit"` events to the new `type="deposit", subtype="bank"` format.

### 2.5 Ecosystem Impact
- **REQ-066-08 (Peripheral Apps)**: The `apps/webapp` (UI dashboard), the `player` (Replay system), and the `accounting_reconciliation` app MUST be audited and updated to ensure they correctly parse and render the new `type="deposit"` data model without crashing.

---

## 3. Success Criteria
- **SC-001**: A client can send a Bit screenshot, a PayBox screenshot, a Check image, or a Cash text message, and a correct ledger event is recorded for each.
- **SC-002**: A Morning receipt generated from a Bit transfer successfully reflects the "Bit" payment method on the official PDF.
- **SC-003**: The data migration script runs successfully on production, migrating 100% of historical bank deposits to the new format with zero data loss.
- **SC-004**: The UI Dashboard and Player Replay apps load successfully after the migration without any rendering errors related to the new event types.
