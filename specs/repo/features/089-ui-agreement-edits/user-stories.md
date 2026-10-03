# User Stories: 089-ui-agreement-edits

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Client Agreements & Components (Priority: P1)

As a law firm partner, I want to see a list of all fee agreements and their underlying components for a specific client within their client profile, so that I can quickly assess their active and historical contracts at a glance.

**Why this priority**: Foundational view to access agreements and components.

**Independent Test**: Can be tested by navigating to the Clients tab, clicking a client, and viewing the new Agreements section displaying existing DB records.

**Acceptance Scenarios**:

1. **UAT 1.1 - Entry Point**:
   * **User Action**: The user navigates to the "לקוחות" (Clients) tab in the Webapp and clicks on a specific client row (e.g., "Israel Israeli") to view their details.
   * **Expected Result**: The UI displays a new dedicated "הסכמים" (Agreements) section right below the client's existing comments and aliases.

2. **UAT 1.2 - The List View (Component Visibility)**:
   * **User Action**: The user looks at the Agreements section for that client.
   * **Expected Result**: The UI displays a list of all fee agreements for that client. For each agreement, its top-level details (Agreement ID, Payer Name, Partner Name, Partner %, Overall Status) are shown. Nested directly underneath, the UI explicitly lists its individual fee components (Label, Amount/Percent, Trigger Condition, Component Status). The user does not need to click into the agreement just to see what the components are.

---

### User Story 2 - Edit Agreement & Components Data (Priority: P1)

As a law firm partner, I want to edit top-level agreement data (payer, partner) separately from the individual fee components, so that I can maintain granular control over the engagement's financial triggers without corrupting unrelated components.

**Why this priority**: Core value of the feature, enabling manual UI overrides at the correct architectural depth.

**Independent Test**: Can be tested by clicking "Edit Agreement" (top level) and "Edit" (component level) and verifying the correct fields are exposed and saved independently.

**Acceptance Scenarios**:

1. **UAT 2.1 - Edit Top-Level Agreement Details**:
   * **User Action**: The user clicks "Edit Agreement" on the overall agreement header.
   * **Expected Result**: An edit dialog opens displaying ONLY the fields that govern the entire matter: `Payer Name`, `Partner Name`, and `Partner %`. Saving updates the parent agreement record in the DB and refreshes the UI header.

2. **UAT 2.2 - Edit Specific Component**:
   * **User Action**: The user clicks "Edit" on a specific component (e.g., Retainer) underneath the agreement.
   * **Expected Result**: An edit dialog opens displaying ONLY the fields for that specific component: `Label`, `Description (Wording)`, `Amount`, `Percent`, `Percent Base`, `Trigger Condition`, `VAT Status`, and `Transaction Date`. Saving pushes the exact updated component fields as a new event revision to the Ledger, without affecting other components.

3. **UAT 2.3 - Add New Component**:
   * **User Action**: The user clicks "+ Add Component" under an agreement.
   * **Expected Result**: A dialog opens requiring the user to explicitly define the component-level fields listed in UAT 2.2. Saving adds it to the DB and generates a new ledger event.

---

### User Story 3 - Manage Component Lifecycle (Pending / Active / Completed / Cancelled) (Priority: P2)

As a law firm partner, I want to track components across four states (Pending, Active, Completed, Cancelled) to accurately reflect my pipeline vs accounts receivable vs realized revenue.

**Why this priority**: Ensures correct historical tracking and reporting of what is still owed vs. what is closed.

**Independent Test**: Test by adding components with/without triggers to see smart defaulting, then manually transitioning their states in the UI.

**Acceptance Scenarios**:

1. **UAT 3.1 - Initial State Assignment (Smart Defaulting)**:
   * **User Action**: The user (or WhatsApp Bot) adds a new component to an agreement.
   * **Expected Result**: If the component has a `trigger_condition` defined (e.g., "if we go to court"), the system automatically assigns it the status **Pending**. If the component has NO trigger condition (e.g., a flat Retainer), it defaults immediately to **Active**.

2. **UAT 3.2 - Transition: Pending -> Active (Condition Met)**:
   * **User Action**: A trigger condition occurs in reality. The user clicks "Mark Active" next to a **Pending** component in the UI.
   * **Expected Result**: The component status changes from Pending to Active, signaling that payment is now expected. A new ledger event is recorded.

3. **UAT 3.3 - Transition: Active -> Completed (Paid)**:
   * **User Action**: The client pays the fee. The user clicks "Mark Completed" next to an **Active** component.
   * **Expected Result**: The component status changes to Completed. Its edit fields are locked (grayed out). The rest of the agreement remains in its current state.

4. **UAT 3.4 - Transition: Cancelled**:
   * **User Action**: The user clicks "Cancel" next to a Pending or Active component.
   * **Expected Result**: The component status changes to Cancelled and is locked. No payment will ever be expected.

5. **UAT 3.5 - Top-Level Agreement Closure**:
   * **User Action**: The user clicks "Mark Completed" or "Cancel" on the *overall agreement* header.
   * **Expected Result**: The parent agreement status changes to Completed/Cancelled. No further payments are expected and no more work is required. The UI strictly disables all action buttons on all underlying components, locking them in their current historical states (e.g., a Pending component stays Pending but locked).

6. **UAT 3.6 - Re-Open**:
   * **User Action**: The user clicks "Reopen" on any closed component (Completed/Cancelled) OR on the overall agreement.
   * **Expected Result**: The status of that specific line (component or parent agreement) is switched back to **Active**, unlocking its edit fields.

---

### User Story 4 - View Revision History & Cross-Platform Consistency (Priority: P2)

As a user interacting with both the UI and the WhatsApp bot, I want a single source of truth for agreements and a chronological history of changes, so that I know what terms were active on a specific past date and who changed them.

**Why this priority**: Crucial for operational trust and dispute resolution.

**Independent Test**: Test by making an edit in the UI, then querying the bot on WhatsApp to confirm it reads the new value.

**Acceptance Scenarios**:

1. **UAT 4.1 - View Revision History**:
   * **User Action**: The user looks at an agreement's expanded view in the UI.
   * **Expected Result**: They see a "Revision History" timeline that lists each revision to the agreement or its components chronologically, showing the date, the actor (Webapp UI or WhatsApp Bot), and a snapshot of the changed values.

2. **UAT 4.2 - WhatsApp Bot Reads UI Edits**:
   * **User Action**: The user edits a component's fee to $1,000 in the UI, then asks the WhatsApp bot about that agreement.
   * **Expected Result**: The bot replies with the $1,000 fee, reading from the latest DB revision established by the UI.

---

## WhatsApp Interaction Flows

### Flow 1: Querying Agreements & Handling Ambiguities
*   **User Action:** User asks, "What is our agreement with Israel?"
*   **System (Detour 1 - Name Resolution):** "מצאתי שני לקוחות שעונים לשם 'Israel'. האם התכוונת לישראל ישראלי או לישראל כהן?"
*   **User Action:** User answers "ישראלי"
*   **System (Detour 2 - Agreement Resolution):** "לישראל ישראלי יש 2 הסכמים פעילים: 1. ייצוג בבית הדין הארצי 2. תביעת נזיקין. לאיזה הסכם התכוונת?"
*   **User Action:** User answers "לארצי"
*   **System (Success):** "ההסכם 'ייצוג בבית הדין הארצי' עבור ישראל ישראלי פעיל. הרכיבים שלו: 1. ריטיינר (5,000 ₪, לא כולל מע״מ). 2. שכר טרחה באחוזים (20% מסכום הזכייה בתיק)."
*   **DB Expectation:** No updates. The system performs a read-only query on the Agreements DB, retrieving the active components for the resolved agreement ID.

### Flow 2: Editing Component-Level Fields
*   **User Action:** User says, "We agreed with Israel on the appeal to raise the retainer to 6,000₪."
*   **System (Success):** "הבנתי. עדכנתי את רכיב הריטיינר בהסכם 'ייצוג בבית הדין הארצי' עבור ישראל ישראלי. הסכום החדש הוא 6,000 ₪. נשמרה גרסה חדשה."
*   **DB Expectation:** The specific retainer component is updated with the new amount in the Agreements DB, creating a new revision. A corresponding ledger event is pushed for financial tracking.

### Flow 3: Editing Top-Level Agreement Fields
*   **User Action:** User says, "For Israel's appeal, add Adv. Cohen as a partner for 25%. Also, the payer is actually the Histadrut, not Israel."
*   **System (Success):** "עדכנתי את נתוני ההסכם 'ייצוג בבית הדין הארצי' של ישראל ישראלי: משלם: ההסתדרות, שותף: עו״ד כהן (25%)."
*   **DB Expectation:** The top-level agreement record in the Agreements DB is updated with the new payer and partner details. No new ledger event is strictly necessary unless top-level changes require financial auditing.

### Flow 4: Adding a New Component to an Existing Agreement
*   **User Action:** User says, "Add a new fee to Israel's appeal agreement: 1,500₪ for every additional court hearing."
*   **System (Success):** "הוספתי רכיב חדש להסכם 'ייצוג בבית הדין הארצי' של ישראל ישראלי כפעיל: תיאור: תוספת עבור דיון נוסף, סכום: 1,500 ₪, תנאי: על כל דיון נוסף מעבר לקבוע מראש."
*   **DB Expectation:** A new component object is appended to the existing agreement's components list in the Agreements DB with an Active status. A new ledger event is triggered for this newly created component.

### Flow 5: Lifecycle Management (Component vs. Overall)
**Scenario A: Completing a single component**
*   **User Action:** User says, "Israel paid the retainer for the appeal."
*   **System (Success):** "סימנתי את רכיב הריטיינר (6,000 ₪) כ'הושלם'. שאר ההסכם (20% וכו') נשאר פעיל."
*   **DB Expectation:** The specific retainer component is marked as "Completed" in the Agreements DB. The parent agreement remains untouched.

**Scenario B: Completing the entire agreement**
*   **User Action:** User says, "Close out Israel's appeal agreement, the case is completely done."
*   **System (Success):** "סימנתי את ההסכם 'ייצוג בבית הדין הארצי' של ישראל ישראלי, ואת כל הרכיבים הפעילים שלו, כ'הושלם'. ההסכם ננעל לעריכה."
*   **DB Expectation:** The top-level agreement is marked as "Completed" in the Agreements DB, which implicitly locks all its underlying components from future edits.
