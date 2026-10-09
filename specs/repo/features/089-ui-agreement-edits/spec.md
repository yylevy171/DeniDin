# Feature Specification: Edit Agreements from UI & WhatsApp (Component Architecture)

**Feature Branch**: `feature/089-ui-agreement-edits`  
**Created**: 2026-09-30  
**Updated**: 2026-10-05  
**Status**: Draft (clarified 2026-10-05)  
**Category**: Capability  
**Input**: User description: "allow to manage agreements, specifically edit wording and numbers from the ui. Edits reach ledger. Completely different module for agreements (Agreements DB) that handles lifecycle. DB is source of truth, each change is a new revision. Ledger becomes documentation of initial creation."

---

## Executive Summary

*(Note: This feature officially absorbs and obsoletes Feature 040 (Agreement Cancellation & Modification via Reply Reference), handling those requirements under the new Component Architecture lifecycle.)*

Currently, fee agreements are immutable records stored only in the financial Ledger. Since agreements are "alive" and constantly change (wording, fees, status), the system is shifting to a dual-source architecture. 

This feature introduces a new "Agreements Database" that handles the living lifecycle and revisions of agreements. Structurally, an Agreement is now treated as a **Container of Components**, allowing granular control over individual fee triggers (e.g., a retainer vs. a success fee) rather than treating the entire engagement as a single monolithic block. 

The Webapp UI will integrate this into the existing "Clients" tab, allowing users to view a client's agreements, create new agreements, open an Edit Dialog to modify wording/numbers at the specific component level, delete components, and manage lifecycle statuses (Pending, Active, Completed, Cancelled). Every write, from the UI or the WhatsApp bot, goes to the Agreements DB first and creates a new revision there; the DB write then pushes the matching event to the Ledger to maintain strict financial integrity. The UI and WhatsApp bot will both read/write to this DB, adopting a "last write wins" concurrency model.

---

## Terminology Glossary

- **Agreement**: the engagement container for one client matter (`agreement_id`, e.g. `0726-ישראל_ישראלי-ערעור`). Holds payer, partner, partner %, status.
- **Component**: one fee rule inside an agreement (`component_id`, e.g. retainer, success fee). Has its own status and amount/percent.
- **Component status**: `Pending` (has a trigger, not yet triggered), `Active` (payment expected), `Completed` (paid), `Cancelled`.
- **Agreement status**: `Active`, `Completed`, `Cancelled`. A closed agreement locks all its components.
- **Locked**: a component that cannot be edited or have its status changed except by Reopen: Completed or Cancelled, or belonging to a non-Active agreement.
- **Cascade**: the component status changes forced by closing an agreement (see REQ-089-06).
- **Revision**: one immutable history row per Agreements DB write, with actor and a snapshot.
- **Actor**: who made a write: `webapp`, `whatsapp` or `migration`.
- **Agreements DB**: the SQLite source of truth for current agreement state, owned by denidin-app.
- **Agreements API**: the bearer-authenticated HTTP API on denidin-app through which the webapp reads and writes the Agreements DB.
- **Hours-worked line**: a `הסכם` ledger event with a non-null `hours`; ledger-only, never a component.
- **`original_client_name`**: the raw, un-normalized client name preserved on a migrated ledger event; empty on new events.
- **DEPRECATED: "agreement event" meaning a mutable ledger record**: ledger events stay append-only documentation; current state lives in the Agreements DB.

---

## Clarifications

### Session 2026-10-05

- Note (2026-10-09): the original input said the ledger "becomes documentation of initial creation". The later human decisions supersede that: every component write, agreement-level edit, close and reopen also writes ledger events (REQ-089-07), so the ledger mirrors the DB's history while the DB stays the source of truth for current state.
- Q: Ledger schema version bump (REQ-089-10)? → A: **Approved by the human, 2026-10-04; the target version was set to 4 (not 3) on 2026-10-09**, covering the new fields `original_client_name`, `component_status`, `agreement_status` and populating `split_partner`/`split_percent`. The same commit that changes `CURRENT_SCHEMA_VERSION` must add the matching `SCHEMA_VERSION_HISTORY` entry.
- Q: Rewriting historical prod ledger events (REQ-089-10)? → A: **Approved by the human, 2026-10-04**, as a one-time exception to ledger immutability, limited to the scope in REQ-089-10.
- Q: Who owns the Agreements DB? → A: denidin-app owns it. The webapp writes to it through an HTTP API on denidin-app, and its read-only mount of denidin-app's data stays read-only.
- Q: What ledger event does an edit or status change push? → A: A `source_type=הסכם` event with `event_subtype=יצירה` carrying the component's full new state. No new subtypes for edits.
- Q: Where does the Clients-tab "agreed" total come from? → A: The Agreements DB: the sum of the client's non-Cancelled components, plus the hours-worked ledger amounts (REQ-089-13). The `הסכם <amount>` comment override is unchanged.
- Q: Are hours-worked lines agreement components? → A: No. They are excluded from the Agreements DB and stay ledger-only. An hours-worked line is any `הסכם` event with a non-null `hours` value.
- Q: How is a new agreement born? → A: From a WhatsApp capture, as today, and also from a new "create agreement" action in the UI. Both write to the DB first, and the DB write produces the ledger events.
- Q: What changes in WhatsApp? → A: Nothing in the conversation. Flows 1–5 stay in scope and behave as they do today. The only change is that the bot no longer writes `הסכם` ledger events directly; it writes to the Agreements DB, and the DB write produces the ledger event.
- Q: Where does the bot read agreements from? → A: The Agreements DB, so it reports terms edited in the UI (SC-002).
- Q: What happens if the DB write succeeds but the ledger write fails? → A: Out of scope for this spec (edge case, not specified).
- Q: Where does the migration get the true Morning client name? → A: The Clients-tab mapping (confirmed mappings plus its automatic match to official Morning names). A name it cannot resolve keeps its raw value, with `original_client_name` still filled.
- Q: Which status do migrated agreements of a client whose line is closed get? → A: Completed if the client has paid at least the agreed amount, otherwise Cancelled.
- Q: How are the legacy `מבוטל`/`ביטול` ledger events migrated? → A: They mark the component they refer to as Cancelled.
- Q: Is creating an agreement from the UI in scope? → A: Yes.
- Q: Is deleting a component from the UI in scope? → A: Yes, as a hard delete (for example, duplicates). It pushes a `הסכם` ledger event with `event_subtype=ביטול` whose `reference` is the event_id of the component's original ledger event.
- Q: Feature flag? → A: No feature flag.
- Q (session 2026-10-09, human): Ledger events for top-level edits, wording edits, agreement close/reopen? → A (revised same day): Top-level edits, agreement close and agreement reopen all write ledger events, one per component of the agreement. Wording-only component edits: yes, one event.
- Q (2026-10-09): Does closing an agreement cascade? → A: Yes. Completed: Active components become Completed, Pending become Cancelled. Cancelled: every non-Completed component becomes Cancelled. Already Completed/Cancelled ones remain. Reopen does not restore them.
- Q (2026-10-09): Default status of a component added by the bot with a trigger condition? → A: Pending, same as the UI.
- Q (2026-10-09): How do [UI] acceptance tests run? → A: Playwright against a real denidin-app Agreements API on a seeded throwaway data root, no stand-in.
- Q: Which ledger events does the v4 rewrite cover? → A: Only agreement-component `הסכם` events. Hours-worked lines, bank events and invoice events are not rewritten and keep their current schema version.

---

## User Stories Reference

**NOTE**: Complete user stories and User Acceptance Tests (UATs) are defined in the **`user-stories.md`** file (SEPARATE from this spec).

*   **User Story 1:** View Client Agreements & Components List
*   **User Story 2:** Create & Edit Agreement & Components Data (Top-Level vs Component-Level, incl. create agreement and delete component)
*   **User Story 3:** Manage Component Lifecycle (Pending / Active / Completed / Cancelled)
*   **User Story 4:** View Revision History & Cross-Platform Consistency
*   **User Story 5:** WhatsApp Agreement Conversations (Flows 1–5 as numbered UATs)
*   **User Story 6:** Clients-Tab Agreed Total (REQ-089-14)
*   **User Story 7:** One-Time Migration of Existing Agreements (REQ-089-09..12)

---

## Requirements *(mandatory)*

### Functional Requirements

- **REQ-089-01: Agreements Database Integration (Living State)**  
  The system MUST establish a new Agreements module as the source of truth for current agreement states. It is owned by denidin-app. Both the Webapp UI and WhatsApp Bot MUST read and write to this module for all agreement queries and updates. The webapp MUST reach it through an HTTP API on denidin-app; its mount of denidin-app's data stays read-only. Neither the UI nor the bot writes agreement (`הסכם`, non-hours) ledger events directly: every write goes to the Agreements DB first, and the DB write produces the ledger event (REQ-089-07).
- **REQ-089-02: Component-Level Granularity**  
  An Agreement MUST NOT be treated as a single monolithic text block. It MUST be structured as a top-level container (holding Client, Payer, Partner info) with an array of distinct financial **Components** (each holding its own Label, Amount/Percent, Trigger Condition, and Status).
- **REQ-089-03: UI Location & Client Profile Integration**  
  The Webapp MUST display a new "הסכמים" (Agreements) section inside the specific client detail view. This section MUST list all agreements and explicitly list their underlying components so they are visible without requiring a click-through.
- **REQ-089-04: Edit Dialog & Independent Mutation**  
  The system MUST allow users to edit Top-Level Agreement details completely independently from Component-Level details. Modifying a specific component's value MUST NOT overwrite or alter the state of sibling components in the agreement.
- **REQ-089-05: 4-State Lifecycle Management**  
  Components MUST support four states: `Pending` (conditional, not yet triggered), `Active` (triggered, payment expected), `Completed` (paid), and `Cancelled`. The UI MUST provide actions to transition between these states. The WhatsApp bot keeps today's conversational behavior (Flows 1–5 in `user-stories.md`); only its write path changes (REQ-089-01).
- **REQ-089-06: Smart Defaulting & Locking**  
  New components with a trigger condition MUST default to `Pending`; those without must default to `Active`. If an overall Agreement is marked `Completed` or `Cancelled`, all its underlying components MUST be locked from edits, and the close cascades (decision 2026-10-09): marking the agreement `Completed` sets every `Active` component to `Completed` and every `Pending` component to `Cancelled`; marking it `Cancelled` sets every component that is not `Completed` to `Cancelled`. Components already `Completed`/`Cancelled` keep their status. Reopening the agreement sets only the agreement to `Active`; cascaded components stay as they are until reopened individually. 
- **REQ-089-07: Ledger Synchronization**  
  Any UI or WhatsApp write that creates a component, changes any field of a component (including wording-only edits) or changes a component's status (including by an agreement-level close cascade, REQ-089-06) MUST push a new event to the financial Ledger, produced by the Agreements DB write. Agreement-level changes (edits to payer, partner, partner %, and the agreement's own close/reopen) also write ledger events: one per component of the agreement, each carrying that component's full state with the agreement-level values. The event is `source_type=הסכם`, `event_subtype=יצירה`, and carries the component's full new state. Deleting a component (REQ-089-15) pushes a `source_type=הסכם`, `event_subtype=ביטול` event whose `reference` is the event_id of the component's original ledger event.
- **REQ-089-08: Concurrency Strategy**  
  The system MUST adopt a "last write wins" strategy if concurrent edits are made between the Webapp UI and the WhatsApp Bot. Revisions MUST be chronologically viewable.
- **REQ-089-13: Hours-Worked Lines Stay Ledger-Only**  
  A `הסכם` ledger event with a non-null `hours` value is an hours-worked line, not an agreement component. Hours-worked lines MUST NOT enter the Agreements DB, by migration or by new captures, and keep being written to the ledger as today.
- **REQ-089-14: Clients-Tab Agreed Total**  
  The Clients tab's "agreed" total for a client MUST be the sum of that client's non-Cancelled components from the Agreements DB plus the client's hours-worked ledger amounts (REQ-089-13). The existing `הסכם <amount>` comment override keeps working unchanged.
- **REQ-089-15: Create Agreement & Delete Component from the UI**  
  The UI MUST let the user create a new agreement (top-level details plus at least one component) for a client, and MUST let the user hard-delete a component (for example, a duplicate). A delete pushes the ledger event defined in REQ-089-07.
- **REQ-089-16: WhatsApp Reads from the Agreements DB**  
  When the bot answers a question about an agreement, it MUST read the agreement's current state from the Agreements DB, so it reports terms edited in the UI. Per CLAUDE.md's tool-boundary rule, any new or changed bot tool for this needs its own `runtime_constitution.md` section, with cross-references to and from every existing tool-bearing section.
- **REQ-089-17: No Feature Flag**  
  This feature ships without a `config.feature_flags` gate (human decision, 2026-10-05). Rollback is the previous release.

### Key Entities

- **Agreement (Top-Level)**: Represents the engagement container. Contains Client Name, Payer Name, Partner Name, Partner %, and an overall lifecycle status.
- **Component (Child)**: Represents a distinct financial rule or trigger (e.g., Retainer, Success Fee). Contains Label, Description, Value (Amount/Percent), VAT Status, Trigger Condition, and its own lifecycle status.
- **Agreement Revision**: A historical snapshot of an Agreement or Component. Created upon any mutation (via UI or Bot).
- **Hours-Worked Line** *(not an entity of the Agreements DB)*: A `הסכם` ledger event with `hours` set. Lives only in the ledger (REQ-089-13).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can successfully edit a specific fee component (e.g. Retainer) via the Webapp UI without altering the other components (e.g. Success fee) in that same agreement.
- **SC-002**: A user can ask the WhatsApp bot about an agreement immediately after a UI edit, and the bot accurately reports the newly edited terms 100% of the time based on the shared DB.
- **SC-003**: A user can mark an individual component as "Completed" (paid) while leaving the rest of the agreement "Active".
- **SC-004**: All UI edits to fee numbers result in a corresponding Ledger event, ensuring financial audits match the current active component state.

### Historical Migration & Data Hygiene
- **REQ-089-09: One-Time Ledger Migration**  
  A one-time migration script MUST execute to convert all existing agreement-component `fee_agreement` ledger events (`source_type=הסכם`, `hours` not set) into the new Agreements DB schema (Agreement -> Components). Hours-worked lines are not migrated (REQ-089-13).
- **REQ-089-10: Ledger Schema Version 4 Upgrade (Mutating History)**  
  *(Schema bump and prod rewrite both approved by the human, 2026-10-04.)* Despite the ledger's immutable nature, the migration MUST perform a one-time rewrite of the historical agreement-component `הסכם` ledger events (the same set as REQ-089-09) to bump them to Schema Version 4. Hours-worked lines, bank events and invoice events are NOT rewritten and keep their current schema version. This upgrade will move the existing dirty client name into a new `original_client_name` field on the ledger event itself, resolve the true Morning client name into the `client_name` field, and save the modified event back to the ledger file system. The true name comes from the Clients-tab mapping (confirmed mappings plus its automatic match to official Morning names); a name it cannot resolve keeps its raw value in `client_name`, with `original_client_name` still filled. New agreements created post-migration MUST enforce strict resolution upfront, leaving `original_client_name` empty.
- **REQ-089-11: Smarter Status Inference**  
  The migration script MUST NOT blindly default all historical components to `Active`. It MUST cross-reference the client's current line status in the Webapp Clients tab. If a client's line is closed, their migrated agreements MUST become `Completed` when the client has paid at least the agreed amount, and `Cancelled` otherwise. Otherwise, components get the normal defaults (REQ-089-06).
- **REQ-089-11a: Legacy Cancellation Events**  
  The legacy `הסכם` ledger events with `event_subtype` `מבוטל` or `ביטול` MUST mark the component they refer to as `Cancelled` in the Agreements DB.
- **REQ-089-12: UI De-Duplication**  
  Any duplicated or misunderstood legacy agreements that bypass the inference rules will manifest in the UI, where partners can manually clean them up using the new Lifecycle UI controls and the component delete action (REQ-089-15).
