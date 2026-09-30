# User Stories & Acceptance Criteria: Feature 087 (Clients Management in Webapp)

## User Story 1: Overview and Tracking of All Firm Clients (Priority: P1)
**As a** law firm partner or administrator,  
**I want to** navigate to a dedicated "Clients" page in the webapp,  
**So that** I have an instant, high-level view of all active clients, their financial posture, and their current billing status without digging through chat logs or CLI exports.

### Acceptance Criteria / Scenarios:
- **Scenario 1.1**: User navigates from the Ledger view to the Clients tab via the header navbar. The table loads without full-page refreshes.
- **Scenario 1.2**: Each client row shows the primary client name, phone number, Morning client ID, balance/total billed, and a visual health badge (e.g., Paid, Open Debt, Unresolved).
- **Scenario 1.3**: The client search bar instantly filters rows by Hebrew name or phone number with zero lag.

---

## User Story 2: Inline Client Comments & Operational Follow-ups (Priority: P1)
**As an** operations manager,  
**I want to** attach notes, agreement reminders, or follow-up statuses directly to a client row,  
**So that** all team members have shared context on why an account is pending or when payment was promised.

### Acceptance Criteria / Scenarios:
- **Scenario 2.1**: Clicking the note/comment icon opens an inline editor with the existing comment pre-populated.
- **Scenario 2.2**: Submitting the updated note sends `POST /api/clients/{client_id}/comments` and updates local storage.
- **Scenario 2.3**: If network errors occur, the UI displays a clear inline error and retains the draft note.

---

## User Story 3: Managing Aliases & Morning Entity Resolution (Priority: P2)
**As an** operations analyst,  
**I want to** link alias names (from WhatsApp contacts or bank transfer references) to Morning client entities,  
**So that** automated payment matching and billing reports remain clean and accurate.

### Acceptance Criteria / Scenarios:
- **Scenario 3.1**: The client view highlights unlinked or fuzzy-matched names.
- **Scenario 3.2**: An operator can select the correct Morning entity from a searchable dropdown and confirm the link.
- **Scenario 3.3**: The mapping is saved to `client_mapping.json` and immediately used for subsequent queries.
