# User Stories: 098 - Mandatory Client ID Above the Allocation Threshold

Actor throughout: a **godfather/admin** user talking to DeniDin over WhatsApp, in
Hebrew. "Morning" is the dev Morning **sandbox**. Threshold = 5,000 ₪ before VAT, VAT 18%.

All acceptance scenarios below are **`billed`** (real text-only conversations through
DeniDin against the real sandbox). None is `expensive`.

---

### User Story 1 - Ask for the ID before issuing a qualifying document (Priority: P1)

When I ask for a tax invoice or tax invoice/receipt above 5,000 ₪ (before VAT) for a
client with no ID on file, DeniDin tells me it needs the client's ID for the allocation
number and asks me for it, before asking me to approve anything.

**Why this priority**: the regulatory core - without it, non-compliant documents go out.

**Independent Test**: request a qualifying document for an ID-less sandbox client and
check that DeniDin asks for the ID and that no document was created.

**Acceptance Scenarios**:

1. **UAT 1.1 - 320 above threshold, no ID**
   - **Given** a sandbox client with no ID on file,
   - **When** I write "תוציא חשבונית מס קבלה ל<client> על 12,000 ש"ח כולל מע"מ, שולם
     בהעברה בנקאית היום",
   - **Then** DeniDin replies asking for the client's ת.ז / ח.פ and mentions it is needed
     for the allocation number (מספר הקצאה); it shows **no** approval buttons, and no new
     document exists in Morning for that client.
2. **UAT 1.2 - 305 above threshold, no ID**
   - Same as 1.1, but "חשבונית מס ... על 8,000 ש"ח לפני מע"מ" → same outcome.
3. **UAT 1.3 - closing a transaction account with a 320 above threshold, no ID**
   - **Given** an ID-less client with an open transaction account (חשבון עסקה) of 10,000 ₪,
   - **When** I say the client paid it in full,
   - **Then** DeniDin asks for the ID before proposing the closing document; the
     transaction account stays open and no 320 is created.

---

### User Story 2 - Give the ID and get the document (Priority: P1)

After DeniDin asks, I reply with the ID; DeniDin saves it to the client in Morning and
carries on with the same document, without me repeating the request.

**Why this priority**: without it, the block in Story 1 is a dead end.

**Independent Test**: continue the UAT 1.1 conversation with a valid ID and check the
client record and the issued document in Morning.

**Acceptance Scenarios**:

1. **UAT 2.1 - valid ID, then issue**
   - **Given** DeniDin has just asked for the ID in the UAT 1.1 conversation,
   - **When** I reply with a valid 9-digit ID (e.g. "308253681") and approve what DeniDin
     asks me to approve (see Open Question 1 for whether that is one approval or two),
   - **Then** the client's record in Morning now holds that ID, a 320 for 12,000 ₪ exists
     for that client, and DeniDin reports both.
2. **UAT 2.2 - wrong format**
   - **Given** DeniDin has just asked for the ID,
   - **When** I reply "12345678" (8 digits),
   - **Then** DeniDin says an ID must be 9 digits and asks again; the client record is
     unchanged and no document is created.
3. **UAT 2.3 - Morning rejects the ID**
   - **Given** DeniDin has just asked for the ID,
   - **When** I reply with 9 digits whose check digit is wrong (e.g. "308253682"),
   - **Then** DeniDin tells me the number is not a valid ID and asks again; the client
     record is unchanged and no document is created.
4. **UAT 2.4 - I decline**
   - **Given** DeniDin has just asked for the ID,
   - **When** I reply "עזוב, לא עכשיו",
   - **Then** DeniDin confirms nothing was issued; no document and no client change.

---

### User Story 3 - Nothing changes when the rule doesn't apply (Priority: P1)

Below the threshold, for other document types, or for a client who already has an ID,
DeniDin behaves exactly as it does today.

**Why this priority**: an extra question on everyday documents would be a regression.

**Acceptance Scenarios**:

1. **UAT 3.1 - below threshold**: ID-less client, "חשבונית מס קבלה על 4,500 ש"ח" → the
   usual approval prompt, no ID question; after approval the 320 is created.
2. **UAT 3.2 - threshold is before VAT**: ID-less client, 320 for **5,900 ₪ כולל מע"מ**
   (exactly 5,000 ₪ before VAT - not *above* it) → no ID question; document created.
3. **UAT 3.3 - just above, before VAT**: ID-less client, 305 for **5,001 ₪ לפני מע"מ** →
   DeniDin asks for the ID (as in 1.1).
4. **UAT 3.4 - client already has an ID**: client with a valid ID on file, 320 for
   12,000 ₪ → the usual approval prompt, no ID question; document created.
5. **UAT 3.5 - transaction account is out of scope**: ID-less client, "חשבון עסקה על
   12,000 ש"ח" → the usual approval prompt, no ID question; transaction account created.

---

### Below the acceptance tier (unit/integration, listed for completeness - not UATs)

- **Hard backstop (REQ-098-07)**: calling the 305/320 creation tools directly against the
  sandbox for an ID-less client above the threshold returns a refusal and creates nothing;
  at/below the threshold or with an ID, they work as today. Integration (real sandbox).
- **Configurable threshold (REQ-098-03)**: with the threshold configured to 10,000, a
  7,000 ₪ document for an ID-less client is not refused. Unit/integration with test config.
- **Pre-VAT derivation and 9-digit check**: unit.

### Edge Cases

- A client ID stored in Morning that is not 9 digits (e.g. leading zero dropped) counts as
  missing → DeniDin asks.
- Foreign-currency documents → see Open Question 2.
- The user gives the ID in the original request ("... ח.פ 514xxxxxx") → DeniDin saves it
  and proceeds without asking.
- Feature 086 (one 320 closing several transaction accounts), if it lands, is in scope:
  the combined 320 amount is what's compared.

---

## Open Questions for PM

**Q1 - Approvals after the ID is given.** Updating a client and issuing a document each
need approval today. After I give the ID, should DeniDin:
- **A** - ask once, a single approval covering "save ID + issue document"; or
- **B** - two separate approvals (save ID, then issue document), as the gates work today.

**Q2 - Foreign-currency documents** (e.g. a 320 in USD). The threshold is in ₪.
- **A** - convert at the document's exchange rate and apply the rule;
- **B** - out of scope: only ₪ documents are checked.

**Q3 - Where DeniDin's prompts get the threshold number.**
- **A** - DeniDin's own config carries the same value (two places to change together);
- **B** - DeniDin reads it from morning-mcp-app (e.g. exposed on `/health` or a tool), one
  place to change.
