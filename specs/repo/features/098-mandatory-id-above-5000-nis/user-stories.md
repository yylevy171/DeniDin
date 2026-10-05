# User Stories: 098 - Mandatory Client ID Above the Allocation Threshold

Threshold = 5,000 ₪ before VAT; VAT 18%. Shekel documents only (non-shekel is not
supported anywhere in the system).

**Actors**
- **User** - a godfather/admin user, on WhatsApp, in Hebrew.
- **DeniDin** - `denidin-app`, the WhatsApp bot.
- **Morning-MCP** - `morning-mcp-app`, the MCP server that talks to Morning.
- **Morning** - the dev Morning **sandbox** (the real external system).

**Acceptance scenarios APPROVED by PM, 2026-10-05** (UAT 1.1-4.1 below, as written; 4.2 later removed with Q3's change).

**Test tiers**: every acceptance scenario below is **`billed`** (real, text-only OpenAI
calls against the real sandbox). None is `expensive`. Stories 1-3 run through DeniDin
(`apps/denidin-app/tests/billed/`); Story 4 runs against Morning-MCP alone
(`apps/morning-mcp-app/tests/billed/`).

**Fixtures common to all stories**: a fresh sandbox client created per test
("Test098 <timestamp>"), with or without an ID as the scenario says.

---

### User Story 1 - DeniDin asks for the ID before issuing a qualifying document (Priority: P1)

**Why this priority**: the regulatory core - without it, non-compliant documents go out.

**Acceptance Scenarios**:

1. **UAT 1.1 - 320 above threshold, client has no ID**
   - **Given** a sandbox client with no ID on file.
   - **Step 1 - User sends** (one WhatsApp text):
     "תוציא חשבונית מס קבלה ל<client> על 12,000 ש"ח כולל מע"מ, שולם בהעברה בנקאית היום".
   - **Step 2 - DeniDin, internally** (not visible to the User): reads the client from
     Morning-MCP, sees no ID, and does **not** call any document-creation tool.
   - **Step 3 - DeniDin sends** exactly one reply, as plain text (**no** approval buttons),
     that:
     - names the client and the amount,
     - says the client's ID (ת.ז / ח.פ) is needed for the allocation number (מספר הקצאה)
       because the amount is above 5,000 ₪ before VAT,
     - asks the User to send it.
   - **Then, in Morning**: no new document exists for the client, and the client record is
     unchanged.

2. **UAT 1.2 - 305 above threshold, client has no ID**
   - Same as 1.1, with **Step 1 - User sends**:
     "תוציא חשבונית מס ל<client> על 8,000 ש"ח לפני מע"מ".
   - Steps 2-3 and the Morning check are identical.

3. **UAT 1.3 - closing a transaction account with a 320 above threshold, client has no ID**
   - **Given** an ID-less sandbox client with an open transaction account (חשבון עסקה, 300)
     of 10,000 ₪, created directly in the sandbox by the test.
   - **Step 1 - User sends**: "<client> שילם את החשבון עסקה במלואו, בהעברה בנקאית היום".
   - **Step 2 - DeniDin, internally**: finds the open transaction account, sees the client
     has no ID, does **not** call the closing tool.
   - **Step 3 - DeniDin sends** one plain-text reply (no buttons), with the same content
     as 1.1's Step 3.
   - **Then, in Morning**: the transaction account is still open, and no 320 exists for
     the client.

---

### User Story 2 - User gives the ID and gets the document (Priority: P1)

Two separate approvals, exactly as the approval gates work today (PM decision Q1 = B):
first the client update, then the document.

**Why this priority**: without it, the block in Story 1 is a dead end.

**Acceptance Scenarios**:

1. **UAT 2.1 - valid ID → save → issue**
   - **Given** the conversation of UAT 1.1, right after DeniDin's Step 3 question.
   - **Step 4 - User sends**: "308253681".
   - **Step 5 - DeniDin sends** an approval prompt **with yes/no buttons**, asking to save
     ID 308253681 on <client>.
   - **Step 6 - User taps** "כן".
   - **Step 7 - DeniDin, internally**: updates the client in Morning with the ID.
   - **Step 8 - DeniDin sends** an approval prompt **with yes/no buttons** for the original
     320 (client, 12,000 ₪ including VAT, bank transfer, today) - the User does not restate
     the request.
   - **Step 9 - User taps** "כן".
   - **Step 10 - DeniDin, internally**: creates the 320.
   - **Step 11 - DeniDin sends** a confirmation of the issued document.
   - **Then, in Morning**: the client record holds ID 308253681, and one 320 for 12,000 ₪
     exists for the client.

2. **UAT 2.2 - wrong format**
   - **Given** the conversation of UAT 1.1, right after DeniDin's Step 3 question.
   - **Step 4 - User sends**: "12345678" (8 digits).
   - **Step 5 - DeniDin sends** one plain-text reply (no buttons) saying an ID must be 9
     digits and asking again.
   - **Then, in Morning**: client unchanged; no document.

3. **UAT 2.3 - User declines**
   - **Given** the conversation of UAT 1.1, right after DeniDin's Step 3 question.
   - **Step 4 - User sends**: "עזוב, לא עכשיו".
   - **Step 5 - DeniDin sends** one plain-text reply confirming nothing was issued.
   - **Then, in Morning**: client unchanged; no document.

---

### User Story 3 - Nothing changes when the rule doesn't apply (Priority: P1)

In every scenario below: **User sends** the request → **DeniDin sends** the usual document
approval prompt with buttons, with **no** ID question → **User taps** "כן" → **DeniDin
sends** the usual confirmation → **in Morning** the document exists.

**Why this priority**: an extra question on everyday documents would be a regression.

**Acceptance Scenarios**:

1. **UAT 3.1 - below threshold**: ID-less client; "חשבונית מס קבלה ל<client> על 4,500 ש"ח
   כולל מע"מ, שולם בהעברה היום".
2. **UAT 3.2 - threshold is before VAT**: ID-less client; 320 for **5,900 ₪ כולל מע"מ**
   (exactly 5,000 ₪ before VAT - not *above* it).
3. **UAT 3.3 - client already has an ID**: client created with ID 308253681; 320 for
   12,000 ₪ כולל מע"מ.
4. **UAT 3.4 - transaction account is out of scope**: ID-less client; "חשבון עסקה ל<client>
   על 12,000 ש"ח".

And the boundary in the other direction:

5. **UAT 3.5 - just above, before VAT**: ID-less client; "חשבונית מס ל<client> על 5,001
   ש"ח לפני מע"מ" → DeniDin behaves as in UAT 1.1 (asks for the ID, no buttons, no document).

---

### User Story 4 - Morning-MCP refuses on its own (Priority: P1)

Morning-MCP is the hard backstop: whatever the caller does, it never creates a qualifying
document for a client with no ID. Its "user" is an AI calling it over MCP, so these
scenarios drive it with a **real OpenAI call** through the real MCP tunnel - no DeniDin
involved.

**Acceptance Scenarios**:

1. **UAT 4.1 - refusal over MCP**
   - **Given** an ID-less sandbox client.
   - **Step 1 - the test sends OpenAI** a prompt instructing it to create a 320 for
     12,000 ₪ for <client> using the Morning-MCP tools.
   - **Step 2 - OpenAI calls** Morning-MCP's 320 creation tool.
   - **Step 3 - Morning-MCP returns** a refusal (not a created document) that says the
     client's ID is required for documents above 5,000 ₪ before VAT.
   - **Then, in Morning**: no document for the client.
*(UAT 4.2 - threshold over MCP - removed 2026-10-05: DeniDin keeps its own copy of the
   threshold, so Morning-MCP no longer exposes it.)*

---

### Below the acceptance tier (unit/integration - not UATs)

**Morning-MCP integration tests** (real sandbox, direct tool calls, no OpenAI) - the full
matrix, cheaper than billed:
- 305 and 320 (fresh), and 320 closing a 300: ID-less client above threshold → refused,
  nothing created; the 300 stays open.
- Same three at/below threshold, or with an ID on file → created as today.
- A client ID stored in Morning that is not 9 digits → treated as missing → refused.
- 300, 400, 330 above threshold, ID-less client → created as today (out of scope).
- Threshold configured to 10,000 → a 7,000 ₪ document for an ID-less client is created.

**Unit** (both apps): pre-VAT derivation, the 9-digit check, threshold comparison
(strictly greater), prompt injection of the threshold value.

### Edge Cases

- The User gives the ID in the original request ("... ח.פ 308253681") → DeniDin goes
  straight to Story 2's Step 5 (approve saving the ID).
- The User approves saving the ID but declines the document → ID saved, no document.
- Feature 086 (one 320 closing several transaction accounts), if it lands, is in scope:
  the combined 320 amount is what's compared.

---

## PM Decisions

- **Q1 (2026-10-05)**: two separate approvals - save the ID, then issue the document.
- **Q2 (2026-10-05)**: non-shekel documents are out of scope - not supported anywhere.
- **Q3 (2026-10-05, revised same day)**: the threshold is a config item in **both** apps -
  Morning-MCP's (drives the hard refusal) and DeniDin's own copy (fills the number into
  its prompts). Chosen for speed; the two must be changed together. DeniDin never reads
  Morning-MCP's config and never calls it directly.
