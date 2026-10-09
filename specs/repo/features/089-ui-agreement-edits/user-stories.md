# User Stories: 089-ui-agreement-edits

> **Acceptance status: DRAFT, NOT YET APPROVED.** The UATs below are the acceptance scenarios that
> `speckit.plan` requires the human to approve first (METHODOLOGY §VI). Nothing here is test code.
> Tightened 2026-10-09: every UAT now names its test tier and its ledger effect, the WhatsApp flows
> are numbered UATs (Story 5), and Stories 6-7 cover REQ-089-09..14, which had no UAT before.
> The six open questions were answered by the human on 2026-10-09 (see "Decisions" at the bottom).

## Test tiers used below

| Tag | Meaning | How it runs |
|---|---|---|
| **[UI]** | A real person in the browser | Playwright (`apps/webapp/e2e`). `webServer` starts a real denidin-app Agreements API on a seeded, throwaway data root next to the webapp; tests assert on the real DB and real ledger files. No stand-in server. Not CI. |
| **[WA]** | A real person in WhatsApp | `billed` test: a real Green API webhook JSON dispatched through the router, with real OpenAI calls. Text-only. |
| **[UI+WA]** | One scenario that crosses both | A [UI] step, then a [WA] step, in one test. |
| **[MIG]** | The one-time migration | `integration` test run against a copy of a real-shaped ledger fixture. No OpenAI. |

**Every UAT that changes data also asserts three things**, even where its text does not repeat them:
(a) the Agreements DB holds the new state, (b) a new revision exists, and (c) the ledger effect named
in that UAT happened, and nothing else was written to the ledger.

**Ledger effect rule (REQ-089-07):** every write goes to the Agreements DB first, and the DB write
produces the ledger event. Component create / financial edit / status change produces one
`הסכם`/`יצירה` event carrying the component's full new state. This includes wording-only edits
(decision 2). An agreement-level change (top-level field edit, close, or reopen) also writes ledger
events (decisions 1 and 3, revised): one `הסכם`/`יצירה` event per component of the agreement, each
carrying that component's full state together with the agreement-level values (payer, partner,
partner %, agreement status). A close's cascade (decision 5) changes the components' statuses first, so
those events carry the cascaded statuses. Component delete produces one
`הסכם`/`ביטול` event whose `reference` is the component's original event_id. Hours-worked lines are
never agreement components.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Client Agreements & Components (Priority: P1)

As a law firm partner, I want to see a list of all fee agreements and their underlying components for a specific client within their client profile, so that I can quickly assess their active and historical contracts at a glance.

**Why this priority**: Foundational view to access agreements and components.

**Independent Test**: Can be tested by navigating to the Clients tab, clicking a client, and viewing the new Agreements section displaying existing DB records.

**Acceptance Scenarios**:

1. **UAT 1.1 - Entry Point** **[UI]**:
   * **User Action**: The user navigates to the "לקוחות" (Clients) tab in the Webapp and clicks on a specific client row (e.g., "Israel Israeli") to view their details.
   * **Expected Result**: The UI displays a new dedicated "הסכמים" (Agreements) section right below the client's existing comments and aliases.
   * **Ledger effect**: None (read-only).

2. **UAT 1.2 - The List View (Component Visibility)** **[UI]**:
   * **User Action**: The user looks at the Agreements section for that client.
   * **Expected Result**: The UI displays a list of all fee agreements for that client. For each agreement, its top-level details (Agreement ID, Payer Name, Partner Name, Partner %, Overall Status) are shown. Nested directly underneath, the UI explicitly lists its individual fee components (Label, Amount/Percent, Trigger Condition, Component Status). The user does not need to click into the agreement just to see what the components are.
   * **Ledger effect**: None (read-only).

3. **UAT 1.3 - Hours-Worked Lines Are Not Components** **[UI]** *(added 2026-10-09, REQ-089-13)*:
   * **User Action**: The user opens a client who has both a fee agreement and logged hours-worked lines.
   * **Expected Result**: The Agreements section shows only the fee agreement's components. The hours-worked lines do not appear as components, have no Edit/lifecycle buttons, and still count toward the client's agreed total (UAT 6.1).
   * **Ledger effect**: None (read-only).

4. **UAT 1.4 - Client With No Agreements** **[UI]** *(added 2026-10-09)*:
   * **User Action**: The user opens a client who has no agreements.
   * **Expected Result**: The "הסכמים" section shows an empty state and the "+ New Agreement" button (UAT 2.4). Nothing breaks.
   * **Ledger effect**: None (read-only).

---

### User Story 2 - Edit Agreement & Components Data (Priority: P1)

As a law firm partner, I want to edit top-level agreement data (payer, partner) separately from the individual fee components, so that I can maintain granular control over the engagement's financial triggers without corrupting unrelated components.

**Why this priority**: Core value of the feature, enabling manual UI overrides at the correct architectural depth.

**Independent Test**: Can be tested by clicking "Edit Agreement" (top level) and "Edit" (component level) and verifying the correct fields are exposed and saved independently.

**Acceptance Scenarios**:

1. **UAT 2.1 - Edit Top-Level Agreement Details** **[UI]**:
   * **User Action**: The user clicks "Edit Agreement" on the overall agreement header.
   * **Expected Result**: An edit dialog opens displaying ONLY the fields that govern the entire matter: `Payer Name`, `Partner Name`, and `Partner %`. Saving updates the parent agreement record in the DB, creates a new revision, and refreshes the UI header. Components are untouched.
   * **Ledger effect**: One `הסכם`/`יצירה` event per component of the agreement (not only the changed ones), each carrying the component's full state with the new payer / partner / partner % (decision 1, revised 2026-10-09). An agreement with N components produces N events.

2. **UAT 2.2 - Edit Specific Component** **[UI]**:
   * **User Action**: The user clicks "Edit" on a specific component (e.g., Retainer) underneath the agreement, changes the amount, and saves.
   * **Expected Result**: An edit dialog opens displaying ONLY the fields for that specific component: `Label`, `Description (Wording)`, `Amount`, `Percent`, `Percent Base`, `Trigger Condition`, `VAT Status`, and `Transaction Date`. Saving writes the new state to the Agreements DB as a new revision of that component only. Sibling components are byte-for-byte unchanged (SC-001).
   * **Ledger effect**: Exactly one new `הסכם`/`יצירה` event, carrying that component's full new state (not only the changed field). *(Reworded 2026-10-09: the UI no longer "pushes to the Ledger"; the DB write produces the event, per REQ-089-01/07.)*

3. **UAT 2.2b - Wording-Only Edit** **[UI]** *(added 2026-10-09)*:
   * **User Action**: The user edits only the `Description (Wording)` of a component and saves.
   * **Expected Result**: The new wording is saved and a revision is recorded.
   * **Ledger effect**: One new `הסכם`/`יצירה` event with the component's full new state, so the ledger copy of the wording never goes stale (decision 2).

4. **UAT 2.3 - Add New Component** **[UI]**:
   * **User Action**: The user clicks "+ Add Component" under an agreement.
   * **Expected Result**: A dialog opens requiring the user to explicitly define the component-level fields listed in UAT 2.2. Saving without the required fields is refused with a clear message. A valid save adds the component to the DB with its default status (UAT 3.1).
   * **Ledger effect**: One new `הסכם`/`יצירה` event for the new component.

5. **UAT 2.4 - Create New Agreement** **[UI]** *(added 2026-10-05, clarify)*:
   * **User Action**: In the client's "הסכמים" section, the user clicks "+ New Agreement", fills in the top-level fields (UAT 2.1) and at least one component (UAT 2.2), and saves.
   * **Expected Result**: The new agreement appears in the client's list with its components. Each component gets its default status (UAT 3.1). Trying to save with zero components is refused.
   * **Ledger effect**: One `הסכם`/`יצירה` event per component, with `original_client_name` empty (the client was resolved upfront, REQ-089-10).

6. **UAT 2.5 - Delete Component** **[UI]** *(added 2026-10-05, clarify)*:
   * **User Action**: The user clicks "Delete" on a component (for example, a duplicate) and confirms. If the user cancels the confirmation, nothing happens.
   * **Expected Result**: The component disappears from the agreement. Sibling components are untouched.
   * **Ledger effect**: One `הסכם` event with subtype `ביטול` whose `reference` is the event_id of that component's original ledger event.

7. **UAT 2.6 - Closed Items Cannot Be Edited** **[UI]** *(added 2026-10-09, REQ-089-06)*:
   * **User Action**: The user looks at a Completed or Cancelled component, and at any component of a Completed or Cancelled agreement.
   * **Expected Result**: Edit and Delete are disabled (grayed out) and cannot be triggered. The only available action is Reopen (UAT 3.6).
   * **Ledger effect**: None.

---

### User Story 3 - Manage Component Lifecycle (Pending / Active / Completed / Cancelled) (Priority: P2)

As a law firm partner, I want to track components across four states (Pending, Active, Completed, Cancelled) to accurately reflect my pipeline vs accounts receivable vs realized revenue.

**Why this priority**: Ensures correct historical tracking and reporting of what is still owed vs. what is closed.

**Independent Test**: Test by adding components with/without triggers to see smart defaulting, then manually transitioning their states in the UI.

**Acceptance Scenarios**:

1. **UAT 3.1 - Initial State Assignment (Smart Defaulting)** **[UI]** (and the same rule in **[WA]** UAT 5.4):
   * **User Action**: The user adds two new components to an agreement: one with a `trigger_condition` (e.g., "if we go to court"), one without (a flat Retainer).
   * **Expected Result**: The component with the trigger is **Pending**. The component without it is **Active**.
   * **Ledger effect**: One `הסכם`/`יצירה` event per component, each carrying its status.

2. **UAT 3.2 - Transition: Pending -> Active (Condition Met)** **[UI]**:
   * **User Action**: A trigger condition occurs in reality. The user clicks "Mark Active" next to a **Pending** component in the UI.
   * **Expected Result**: The component status changes from Pending to Active, signaling that payment is now expected. Other components keep their status.
   * **Ledger effect**: One new `הסכם`/`יצירה` event with the full component state, status Active.

3. **UAT 3.3 - Transition: Active -> Completed (Paid)** **[UI]**:
   * **User Action**: The client pays the fee. The user clicks "Mark Completed" next to an **Active** component.
   * **Expected Result**: The component status changes to Completed. Its edit fields are locked (grayed out). The rest of the agreement remains in its current state.
   * **Ledger effect**: One new `הסכם`/`יצירה` event, status Completed. *(Added 2026-10-09 from REQ-089-07: a status change pushes an event.)*

4. **UAT 3.4 - Transition: Cancelled** **[UI]**:
   * **User Action**: The user clicks "Cancel" next to a Pending or Active component.
   * **Expected Result**: The component status changes to Cancelled and is locked. No payment will ever be expected. It no longer counts toward the client's agreed total (UAT 6.1).
   * **Ledger effect**: One new `הסכם`/`יצירה` event, status Cancelled. (This is a status change, not a delete: no `ביטול` event. Only UAT 2.5 produces `ביטול`.)

5. **UAT 3.5 - Top-Level Agreement Closure** **[UI]**:
   * **User Action**: The user clicks "Mark Completed" or "Cancel" on the *overall agreement* header.
   * **Expected Result** *(revised by decision 5)*: The parent agreement status changes to Completed or Cancelled and all its components are locked (all action buttons disabled except Reopen on the agreement). The components change as follows:
     * **Mark Completed**: the agreement becomes Completed; every **Active** component becomes **Completed**; every **Pending** component becomes **Cancelled**; components already Completed or Cancelled remain as they are.
     * **Cancel**: the agreement becomes Cancelled; every component that is not Completed (that is, Pending or Active) becomes **Cancelled**; components already Completed or Cancelled remain as they are.
   * **Ledger effect**: One `הסכם`/`יצירה` event per component of the agreement, carrying each component's full state after the cascade (including components left as they were) together with the agreement's new status (decision 3, revised).

6. **UAT 3.6 - Re-Open** **[UI]**:
   * **User Action**: The user clicks "Reopen" on any closed component (Completed/Cancelled) OR on the overall agreement.
   * **Expected Result**: The status of that specific line (component or parent agreement) is switched back to **Active**, unlocking its edit fields. Reopening a component of a still-closed agreement is not offered (the agreement must be reopened first).
   * **Ledger effect**: For a component: one new `הסכם`/`יצירה` event, status Active. For the parent agreement: one `הסכם`/`יצירה` event per component of the agreement, carrying the agreement's new status Active (decision 3, revised). Reopening the agreement sets only the agreement to Active and unlocks it; components that the close had cascaded to Completed/Cancelled stay as they are until reopened one by one (decision 5).

---

### User Story 4 - View Revision History & Cross-Platform Consistency (Priority: P2)

As a user interacting with both the UI and the WhatsApp bot, I want a single source of truth for agreements and a chronological history of changes, so that I know what terms were active on a specific past date and who changed them.

**Why this priority**: Crucial for operational trust and dispute resolution.

**Independent Test**: Test by making an edit in the UI, then querying the bot on WhatsApp to confirm it reads the new value.

**Acceptance Scenarios**:

1. **UAT 4.1 - View Revision History** **[UI]**:
   * **User Action**: The user looks at an agreement's expanded view in the UI, after a UI edit and a (seeded) WhatsApp edit have both happened.
   * **Expected Result**: They see a "Revision History" timeline that lists each revision to the agreement or its components chronologically, showing the date, the actor (Webapp UI or WhatsApp Bot), and a snapshot of the changed values. Both edits appear, in order.
   * **Ledger effect**: None (read-only).

2. **UAT 4.2 - WhatsApp Bot Reads UI Edits** **[UI+WA]**:
   * **User Action**: The user edits a component's fee to 1,000 in the UI, then asks the WhatsApp bot about that agreement.
   * **Expected Result**: The bot replies with the 1,000 fee, reading from the latest DB revision established by the UI (SC-002).
   * **Ledger effect**: The UI edit produced one `הסכם`/`יצירה` event (as UAT 2.2). The bot's read produced nothing.

3. **UAT 4.3 - Last Write Wins** **[UI+WA]** *(added 2026-10-09, REQ-089-08)*:
   * **User Action**: The user edits a component's fee in the UI to 1,000, then tells the bot to change the same fee to 1,200, then reloads the UI.
   * **Expected Result**: The UI shows 1,200. The revision history shows both changes in order. Neither write was rejected.
   * **Ledger effect**: Two `הסכם`/`יצירה` events, in order; the latest carries 1,200.

---

### User Story 5 - WhatsApp Agreement Conversations (Priority: P1)

*(Clarified 2026-10-05: these flows behave exactly as they do today. The only change is the write path: the bot writes to the Agreements DB, and that write produces the ledger event. The bot never writes `הסכם` ledger events directly. Reads come from the Agreements DB.)*
*(Numbered as UATs 2026-10-09 so each can be traced to a test. Conversation text is unchanged.)*

As a law firm partner (godfather/admin), I want to query and manage agreements by talking to the bot in Hebrew, so that the WhatsApp channel stays as capable as the UI.

**Acceptance Scenarios** (all **[WA]**, `billed`):

1. **UAT 5.1 - Query Agreements & Handle Ambiguities**:
   * **User Action:** User asks, "What is our agreement with Israel?"
   * **System (Detour 1 - Name Resolution):** "מצאתי שני לקוחות שעונים לשם 'Israel'. האם התכוונת לישראל ישראלי או לישראל כהן?"
   * **User Action:** User answers "ישראלי"
   * **System (Detour 2 - Agreement Resolution):** "לישראל ישראלי יש 2 הסכמים פעילים: 1. ייצוג בבית הדין הארצי 2. תביעת נזיקין. לאיזה הסכם התכוונת?"
   * **User Action:** User answers "לארצי"
   * **System (Success):** "ההסכם 'ייצוג בבית הדין הארצי' עבור ישראל ישראלי פעיל. הרכיבים שלו: 1. ריטיינר (5,000 ₪, לא כולל מע״מ). 2. שכר טרחה באחוזים (20% מסכום הזכייה בתיק)."
   * **Must hold:** Each short reply ("ישראלי", "לארצי") is read as the answer to the pending question, never as a new topic or a different tool (constitution "Contexts of Operation"). The bot picks no agreement or client on its own while ambiguous.
   * **DB / ledger effect:** None. Read-only on the Agreements DB; no ledger event.

2. **UAT 5.2 - Edit a Component-Level Field**:
   * **User Action:** User says, "We agreed with Israel on the appeal to raise the retainer to 6,000₪."
   * **System (Success):** "הבנתי. עדכנתי את רכיב הריטיינר בהסכם 'ייצוג בבית הדין הארצי' עבור ישראל ישראלי. הסכום החדש הוא 6,000 ₪. נשמרה גרסה חדשה."
   * **DB / ledger effect:** Retainer amount is 6,000 in the Agreements DB as a new revision (actor: WhatsApp Bot); sibling components unchanged. Exactly one `הסכם`/`יצירה` event, produced by the DB write, not written by the bot directly. The existing approval step for write actions is preserved as today.

3. **UAT 5.3 - Edit Top-Level Agreement Fields**:
   * **User Action:** User says, "For Israel's appeal, add Adv. Cohen as a partner for 25%. Also, the payer is actually the Histadrut, not Israel."
   * **System (Success):** "עדכנתי את נתוני ההסכם 'ייצוג בבית הדין הארצי' של ישראל ישראלי: משלם: ההסתדרות, שותף: עו״ד כהן (25%)."
   * **DB / ledger effect:** The agreement record holds the new payer and partner as a new revision. Ledger: one `הסכם`/`יצירה` event per component of the agreement (as UAT 2.1, decision 1 revised).

4. **UAT 5.4 - Add a New Component**:
   * **User Action:** User says, "Add a new fee to Israel's appeal agreement: 1,500₪ for every additional court hearing."
   * **System (Success):** "הוספתי רכיב חדש להסכם 'ייצוג בבית הדין הארצי' של ישראל ישראלי במצב ממתין: תיאור: תוספת עבור דיון נוסף, סכום: 1,500 ₪, תנאי: על כל דיון נוסף מעבר לקבוע מראש."
   * **DB / ledger effect:** A new component with status **Pending** (it has a trigger condition, UAT 3.1) is appended to the agreement in the Agreements DB, and one `הסכם`/`יצירה` event is produced. *(Example reply changed from "פעיל" to "ממתין", decision 4.)*

5. **UAT 5.5a - Complete a Single Component**:
   * **User Action:** User says, "Israel paid the retainer for the appeal."
   * **System (Success):** "סימנתי את רכיב הריטיינר (6,000 ₪) כ'הושלם'. שאר ההסכם (20% וכו') נשאר פעיל."
   * **DB / ledger effect:** The retainer is Completed in the Agreements DB; the agreement and other components are untouched. One `הסכם`/`יצירה` event, status Completed (as UAT 3.3).

6. **UAT 5.5b - Complete the Entire Agreement**:
   * **User Action:** User says, "Close out Israel's appeal agreement, the case is completely done."
   * **System (Success):** "סימנתי את ההסכם 'ייצוג בבית הדין הארצי' של ישראל ישראלי, ואת כל הרכיבים הפעילים שלו, כ'הושלם'. ההסכם ננעל לעריכה."
   * **DB / ledger effect:** The agreement is Completed and all its components are locked. Per UAT 3.5 (decision 5) the Active components become Completed and the Pending ones become Cancelled. One `הסכם`/`יצירה` event per component of the agreement, as in UAT 3.5. **The example reply must also mention the Pending→Cancelled change**, e.g. "...ורכיבים ממתינים בוטלו", since the current text only mentions the active ones (reply text to be fixed in the plan/tests).

7. **UAT 5.6 - Boundary: Agreements Are Not Reminders / Invoices** *(added 2026-10-09, CLAUDE.md tool-boundary rule, REQ-089-16)*:
   * **User Action:** Mid-flow in UAT 5.1 or 5.2, the user sends an ambiguous short reply (e.g. "כן" with nothing pending, or a bare name).
   * **Expected Result:** The bot asks what the user means. It does not call reminder, invoice (Morning) or ledger-query tools, and does not invent an agreement id.
   * **DB / ledger effect:** None.

---

### User Story 6 - Clients-Tab Agreed Total (Priority: P2) *(added 2026-10-09, REQ-089-14)*

As a law firm partner, I want the "agreed" total on the Clients tab to follow the live agreements, so that what I see matches what is currently agreed.

**Acceptance Scenarios**:

1. **UAT 6.1 - Agreed Total Follows the Agreements DB** **[UI]**:
   * **User Action:** The user opens a client with a 5,000 retainer (Active), a 3,000 success fee (Pending), a cancelled 2,000 component, and 1,000 of hours-worked lines. They then cancel the 3,000 component.
   * **Expected Result:** Before cancelling, the agreed total is 9,000 (5,000 + 3,000 + 1,000; the cancelled 2,000 is excluded). After cancelling, it is 6,000. A `הסכם <amount>` comment override on that client still wins exactly as today.
   * **Ledger effect:** As UAT 3.4 for the cancellation; nothing else.

---

### User Story 7 - One-Time Migration of Existing Agreements (Priority: P1) *(added 2026-10-09, REQ-089-09..12)*

As the operator, I want the existing ledger agreements moved into the Agreements DB once, safely, so that the new screen starts out correct.

**Acceptance Scenarios** (all **[MIG]**, `integration`, on a copy of a real-shaped ledger; never on live prod data directly):

1. **UAT 7.1 - Components Created, Hours Lines Skipped**:
   * **Action:** Run the migration on a ledger holding fee-agreement `הסכם` events and hours-worked `הסכם` events.
   * **Expected Result:** Every agreement-component event becomes a component of an agreement in the DB. No hours-worked line enters the DB, and hours-worked, bank and invoice events are not rewritten.

2. **UAT 7.2 - Ledger Events Rewritten to v4 With Clean Names**:
   * **Action:** Same run.
   * **Expected Result:** Each migrated component event now carries the clean Morning client name in `client_name` and the old dirty name in `original_client_name`. A name the Clients tab cannot resolve keeps its raw value in `client_name`, with `original_client_name` still filled. Nothing else in the event is altered.

3. **UAT 7.3 - Status Inference**:
   * **Action:** Run on a client whose Clients-tab line is closed and who paid at least the agreed amount, one closed with less paid, and one that is open.
   * **Expected Result:** The first client's agreements are Completed, the second's Cancelled, the third's get the normal defaults (UAT 3.1).

4. **UAT 7.4 - Legacy Cancellation Events**:
   * **Action:** Run on a ledger with `מבוטל`/`ביטול` `הסכם` events.
   * **Expected Result:** The components they refer to are Cancelled in the DB.

5. **UAT 7.5 - Safe To Re-Run And Reversible** *(added 2026-10-09)*:
   * **Action:** Run the migration twice on the same copy; separately, run it on the copy and confirm a pre-migration backup of the ledger event files exists.
   * **Expected Result:** The second run changes nothing and creates no duplicates. The backup exists before any event is rewritten, since this is a one-time exception to ledger immutability on prod data.

---

## Decisions (human, 2026-10-09)

1. **Top-level edits write ledger events** (revised 2026-10-09, was "none"): one `יצירה` event per component, carrying the new payer / partner / partner % (UATs 2.1, 5.3).
2. **Wording-only component edits DO write a ledger event** (UAT 2.2b). So every component field change does.
3. **Closing or reopening the agreement writes ledger events** (revised 2026-10-09, was "none"), on the same per-component basis as decision 1 (UATs 3.5, 3.6, 5.5b).
4. **A bot-added component with a trigger condition starts Pending**; the Flow 4 example reply was changed to say "ממתין" (UAT 5.4).
5. **Closing the agreement cascades to components** (revised 2026-10-09; UATs 3.5, 5.5b). Completed: the agreement becomes Completed, Active components become Completed, Pending components become Cancelled, already Completed/Cancelled ones remain. Cancelled: the agreement becomes Cancelled, every non-Completed component becomes Cancelled, already Completed/Cancelled ones remain. Reopening the agreement does not restore them (UAT 3.6).
6. **[UI] tests run against a real denidin-app Agreements API** on a seeded, throwaway data root, not a stand-in.

Consequences carried to `spec.md` (REQ-089-06 and REQ-089-07 reworded) and to `plan`: the Agreements API must be startable standalone on a throwaway data root for Playwright.

## Approval

| | |
|---|---|
| Approved by | Yaron Levy (human operator) |
| Date | 2026-10-09 |
| Notes | Approved by "continue to plan" after answering the six open questions (Decisions above). Same day the human confirmed that agreement cancel / complete / reopen are ledger events (one `יצירה` event per component). |
