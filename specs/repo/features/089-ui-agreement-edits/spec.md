# Feature Specification: Edit Agreements from UI & WhatsApp (Component Architecture)

**Feature Branch**: `feature/089-ui-agreement-edits`  
**Created**: 2026-09-30  
**Updated**: 2026-10-03  
**Status**: Draft  
**Category**: Capability  
**Input**: User description: "allow to manage agreements, specifically edit wording and numbers from the ui. Edits reach ledger. Completely different module for agreements (Agreements DB) that handles lifecycle. DB is source of truth, each change is a new revision. Ledger becomes documentation of initial creation."

---

## Executive Summary

Currently, fee agreements are immutable records stored only in the financial Ledger. Since agreements are "alive" and constantly change (wording, fees, status), the system is shifting to a dual-source architecture. 

This feature introduces a new "Agreements Database" that handles the living lifecycle and revisions of agreements. Structurally, an Agreement is now treated as a **Container of Components**, allowing granular control over individual fee triggers (e.g., a retainer vs. a success fee) rather than treating the entire engagement as a single monolithic block. 

The Webapp UI will integrate this into the existing "Clients" tab, allowing users to view a client's agreements, open an Edit Dialog to modify wording/numbers at the specific component level, and manage lifecycle statuses (Pending, Active, Completed, Cancelled). All edits create a new revision in the DB, and crucially, push a new event to the Ledger to maintain strict financial integrity. The UI and WhatsApp bot will both read/write to this DB, adopting a "last write wins" concurrency model.

---

## User Stories Reference

**NOTE**: Complete user stories and User Acceptance Tests (UATs) are defined in the **`user-stories.md`** file (SEPARATE from this spec).

*   **User Story 1:** View Client Agreements & Components List
*   **User Story 2:** Edit Agreement & Components Data (Top-Level vs Component-Level)
*   **User Story 3:** Manage Component Lifecycle (Pending / Active / Completed / Cancelled)
*   **User Story 4:** View Revision History & Cross-Platform Consistency

---

## Requirements *(mandatory)*

### Functional Requirements

- **REQ-089-01: Agreements Database Integration (Living State)**  
  The system MUST establish a new Agreements module as the source of truth for current agreement states. Both the Webapp UI and WhatsApp Bot MUST read and write to this module for all agreement queries and updates.
- **REQ-089-02: Component-Level Granularity**  
  An Agreement MUST NOT be treated as a single monolithic text block. It MUST be structured as a top-level container (holding Client, Payer, Partner info) with an array of distinct financial **Components** (each holding its own Label, Amount/Percent, Trigger Condition, and Status).
- **REQ-089-03: UI Location & Client Profile Integration**  
  The Webapp MUST display a new "הסכמים" (Agreements) section inside the specific client detail view. This section MUST list all agreements and explicitly list their underlying components so they are visible without requiring a click-through.
- **REQ-089-04: Edit Dialog & Independent Mutation**  
  The system MUST allow users to edit Top-Level Agreement details completely independently from Component-Level details. Modifying a specific component's value MUST NOT overwrite or alter the state of sibling components in the agreement.
- **REQ-089-05: 4-State Lifecycle Management**  
  Components MUST support four states: `Pending` (conditional, not yet triggered), `Active` (triggered, payment expected), `Completed` (paid), and `Cancelled`. The UI and WhatsApp bot MUST provide actions to transition between these states.
- **REQ-089-06: Smart Defaulting & Locking**  
  New components with a trigger condition MUST default to `Pending`; those without must default to `Active`. If an overall Agreement is marked `Completed` or `Cancelled`, all its underlying components MUST be locked from edits while retaining their historical internal statuses. 
- **REQ-089-07: Ledger Synchronization**  
  Any UI or WhatsApp edit that modifies a financial value (amount, percent) or changes a status MUST push a new event to the financial Ledger to ensure historical bookkeeping integrity matches the living agreement state.
- **REQ-089-08: Concurrency Strategy**  
  The system MUST adopt a "last write wins" strategy if concurrent edits are made between the Webapp UI and the WhatsApp Bot. Revisions MUST be chronologically viewable.

### Key Entities

- **Agreement (Top-Level)**: Represents the engagement container. Contains Client Name, Payer Name, Partner Name, Partner %, and an overall lifecycle status.
- **Component (Child)**: Represents a distinct financial rule or trigger (e.g., Retainer, Success Fee). Contains Label, Description, Value (Amount/Percent), VAT Status, Trigger Condition, and its own lifecycle status.
- **Agreement Revision**: A historical snapshot of an Agreement or Component. Created upon any mutation (via UI or Bot).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can successfully edit a specific fee component (e.g. Retainer) via the Webapp UI without altering the other components (e.g. Success fee) in that same agreement.
- **SC-002**: A user can ask the WhatsApp bot about an agreement immediately after a UI edit, and the bot accurately reports the newly edited terms 100% of the time based on the shared DB.
- **SC-003**: A user can mark an individual component as "Completed" (paid) while leaving the rest of the agreement "Active".
- **SC-004**: All UI edits to fee numbers result in a corresponding Ledger event, ensuring financial audits match the current active component state.

### Historical Migration & Data Hygiene
- **REQ-089-09: One-Time Ledger Migration**  
  A one-time migration script MUST execute to convert all existing `fee_agreement` ledger events into the new Agreements DB schema (Agreement -> Components).
- **REQ-089-10: Ledger Schema Version 3 Upgrade (Mutating History)**  
  Despite the ledger's immutable nature, the migration MUST perform a one-time rewrite of all historical `fee_agreement` ledger events to bump them to Schema Version 3. This upgrade will move the existing dirty client name into a new `original_client_name` field on the ledger event itself, resolve the true Morning client name into the `client_name` field, and save the modified event back to the ledger file system. New agreements created post-migration MUST enforce strict resolution upfront, leaving `original_client_name` empty.
- **REQ-089-11: Smarter Status Inference**  
  The migration script MUST NOT blindly default all historical components to `Active`. It MUST cross-reference the client's current status in the Webapp cache. If a client is marked as Inactive or Closed, their migrated agreements MUST default to `Completed` or `Cancelled`.
- **REQ-089-12: UI De-Duplication**  
  Any duplicated or misunderstood legacy agreements that bypass the inference rules will manifest in the UI, where partners can manually clean them up using the new Lifecycle UI controls.
