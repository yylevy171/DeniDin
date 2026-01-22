# Feature Spec: Entity Extraction from Group Messages

**Feature ID**: 014-entity-extraction-group-messages  
**Priority**: P1 (High)  
**Status**: Draft - Needs Clarification  
**Created**: January 22, 2026

---

## Problem Statement

DeniDin currently has no mechanism for Godfather to quickly capture business transactions. When Godfather closes a deal and wants to record it, he must either manually enter data into a system or have a full conversation with DeniDin.

**Current Limitation:**
- Godfather closes a deal with new client "Claire from Mizrahi for 5000 Shekel"
- To record this, Godfather must either: manually enter data into a system, or have a full conversation with DeniDin
- No quick capture mechanism for structured business events

**Desired Behavior:**
- Godfather sends shorthand message in group: "Claire from Mizrahi 5000"
- DeniDin automatically extracts: Client name, Company, Amount, Currency
- DeniDin stores structured transaction in memory with metadata
- DeniDin confirms extraction and prompts for additional details (phone, due date, contract)
- Godfather can optionally provide more info, which DeniDin merges into transaction

---

## Terminology Glossary

- **Entity Extraction**: AI-based parsing of shorthand business messages to extract structured data (client name, company, amount, currency)
- **Transaction Memory**: Structured memory entry storing business transaction with JSON metadata
- **Confirmation Prompt**: DeniDin's reply after extracting entities, confirming capture and requesting additional details
- **Shorthand Pattern**: Message format like "{Client} from {Company} {Amount}" for rapid data capture
- **Follow-up Details**: Additional information (phone, due date, contract) provided by Godfather to enrich transaction

---

## User Scenarios & Testing

### 🔒 Test Immutability Principle

**Per CONSTITUTION Section VIII: Once tests for a phase are working and approved, they are IMMUTABLE.**

- Tests from completed phases **MUST NOT be changed** without **EXPLICIT HUMAN APPROVAL**
- New phases should **ADD new tests**, not modify existing ones
- Any test modification requires clear justification and human approval

---

### User Story - Learning from Group Messages (Priority: P1)

**As** the Godfather  
**I want to** share business updates in groups and have DeniDin automatically extract and store structured information  
**So that** I can build a knowledge base without manual data entry

**Independent Test**: Can be tested by sending a structured message to a group containing DeniDin, verifying DeniDin extracts key entities (client name, amount, context), stores in memory with proper structure, and replies with confirmation + prompt for additional details.

**Acceptance Scenarios**:

1. **Given** Godfather sends message in group chat: "Claire from Mizrahi 5000"  
   **When** DeniDin processes the message  
   **Then** DeniDin:
   - Extracts entities: Client name ("Claire"), Company ("Mizrahi"), Amount (5000 Shekel)
   - Stores structured memory: "Claire from Mizrahi is a new client who owes 5000 Shekel"
   - Metadata: `{"type": "client_transaction", "client_name": "Claire", "company": "Mizrahi", "amount": 5000, "currency": "Shekel", "status": "pending"}`
   - Replies: "Congratulations for closing with Claire - a new client, who now owes you 5000 Shekel. Feel free to add more information for future reference, like Claire's phone number, date to expect the money, or the contract you signed"
   - Awaits additional details from Godfather

2. **Given** DeniDin has stored initial transaction for Claire  
   **When** Godfather replies "Claire's phone is 972509998877, payment due Feb 15"  
   **Then** DeniDin:
   - Updates existing memory entry with new fields
   - Extracts: phone ("972509998877@c.us"), due_date ("2026-02-15")
   - Updated metadata: `{"client_name": "Claire", "phone": "972509998877@c.us", "amount": 5000, "due_date": "2026-02-15"}`
   - Confirms: "Updated Claire's information with phone and payment due date ✓"

3. **Given** Godfather sends message in unknown format: "Meeting tomorrow at 3pm"  
   **When** DeniDin cannot extract structured business data  
   **Then** DeniDin:
   - Stores as general conversation memory (existing behavior)
   - Does NOT reply with entity extraction prompt
   - Normal chat response only

---

## 🚨 NEEDS CLARIFICATION

Before proceeding to plan.md, the following questions MUST be answered:

### User Story 2 Specific Questions:

1. **Entity Extraction Trigger**:
   - Should entity extraction only trigger in GROUP chats, or also in 1:1 Godfather chats?
   - What patterns should trigger extraction? Only "{Name} from {Company} {Amount}"?
   - Should DeniDin extract entities from partial patterns (e.g., "Claire 5000" without company)?
   - **DECISION NEEDED**: Extraction scope and pattern flexibility

2. **Currency Detection**:
   - When amount has no currency ("Claire from Mizrahi 5000"), what's the default?
   - Options: Default to Shekel, ask Godfather, or require explicit currency
   - **DECISION NEEDED**: Default currency handling

3. **Transaction Update Strategy**:
   - When Godfather provides additional info ("Claire's phone is..."), should DeniDin:
     - Update existing memory entry's metadata (merge fields)?
     - Create new memory entry and link to original transaction?
     - Both (create new entry + update metadata)?
   - **DECISION NEEDED**: Memory update architecture

4. **Confirmation Reply Behavior**:
   - Should confirmation reply ONLY happen in group chats where transaction was mentioned?
   - Or also in 1:1 follow-ups with Godfather?
   - What if Godfather wants silent extraction (no confirmation)?
   - **DECISION NEEDED**: When to send extraction confirmation

5. **Duplicate Transaction Window**:
   - Edge case EC2 suggests 24-hour window for duplicate detection. Is this correct?
   - Should it be configurable? Different for different clients?
   - **CONFIRM**: Duplicate detection time window

---

## Functional Requirements

### FR1: Structured Data Extraction from Group Messages

**Priority**: P1

**Description**: DeniDin must extract structured business entities from Godfather's group messages and store them with proper metadata.

**Acceptance Criteria**:
- Given Godfather sends message matching pattern: "{Client Name} from {Company} {Amount}"
- When DeniDin processes the message
- Then entities are extracted, stored with structured metadata, and confirmation reply prompts for additional details

**Implementation Notes**:
- Pattern detection: Use AI to identify client transaction messages
- Entity extraction: Client name, company, amount, currency
- Storage format: Memory entry with JSON metadata `{"type": "client_transaction", "client_name": "...", "company": "...", "amount": ..., "currency": "...", "status": "pending"}`
- Reply template: "Congratulations for closing with {client} - a new client, who now owes you {amount} {currency}. Feel free to add more information for future reference, like {client}'s phone number, date to expect the money, or the contract you signed"
- Follow-up handling: Listen for Godfather's additional details (phone, date, notes) and update existing memory entry
- Store under Godfather's user_phone with correlation to original transaction

**Pattern Examples**:
- "Claire from Mizrahi 5000" → Client: Claire, Company: Mizrahi, Amount: 5000 Shekel
- "David Tech Corp $3000" → Client: David, Company: Tech Corp, Amount: 3000 USD
- "Sarah 2500 EUR" → Client: Sarah, Company: null, Amount: 2500 EUR

---

### FR2: Transaction Metadata Management

**Priority**: P1

**Description**: DeniDin must maintain structured metadata for each transaction and support updates.

**Acceptance Criteria**:
- Given initial transaction stored with basic metadata
- When Godfather provides additional details
- Then metadata is enriched without losing original information

**Implementation Notes**:
- Core metadata fields: `client_name`, `company`, `amount`, `currency`, `status`
- Optional fields: `phone`, `due_date`, `contract_path`, `notes`
- All updates timestamped: `created_at`, `updated_at`
- Unique transaction ID: UUID for linking related memories
- Support partial updates (add phone without changing amount)

---

### FR3: Follow-up Detail Capture

**Priority**: P2

**Description**: DeniDin must recognize and capture follow-up details about existing transactions.

**Acceptance Criteria**:
- Given Godfather mentions client name from recent transaction
- When Godfather provides new information (phone, date, notes)
- Then DeniDin links information to existing transaction

**Implementation Notes**:
- Context window: Look for transactions mentioned in last 5 messages
- Entity recognition: Phone numbers, dates, monetary amounts
- Confirmation: "Updated {client}'s information with {fields} ✓"
- If ambiguous match: Ask "Did you mean the Claire from Mizrahi transaction?"

---

## Edge Cases & Error Scenarios

### EC1: Ambiguous Entity Extraction Pattern

**Scenario**: Godfather sends group message that partially matches transaction pattern: "Meeting Claire tomorrow 5pm"

**Expected Behavior**:
- AI determines message does NOT represent a business transaction (no amount/company)
- Store as general conversation memory (existing behavior)
- Do NOT trigger entity extraction confirmation reply
- Respond normally to conversation context

---

### EC2: Duplicate Transaction Detection

**Scenario**: Godfather sends "Claire from Mizrahi 5000" multiple times in different group chats

**Expected Behavior**:
- Check existing memories for recent transaction with same client name + company (within 24 hours)
- If duplicate found, ask: "I already recorded a transaction for Claire from Mizrahi (5000 Shekel). Is this a new transaction or the same one?"
- If new: Create separate memory entry with timestamp differentiation
- If same: Do NOT create duplicate, respond "Got it, already tracking this transaction ✓"

---

### EC3: Mixed Currency in Updates

**Scenario**: Initial transaction in Shekel, Godfather later mentions "$500 deposit"

**Expected Behavior**:
- Detect currency mismatch
- Ask for clarification: "The original transaction was 5000 Shekel. Is the $500 deposit part of this, or a separate transaction?"
- Do NOT automatically convert currencies
- Store both amounts if confirmed as same transaction

---

### EC4: Unlinked Follow-up Details

**Scenario**: Godfather provides phone/date without clear context: "972509998877, payment due Feb 15"

**Expected Behavior**:
- Search recent transaction memories (last 24 hours)
- If single match: "I'll add this to the Claire from Mizrahi transaction, correct?"
- If multiple matches: "Which transaction is this for? 1) Claire from Mizrahi, 2) David from Tech Corp"
- If no matches: "I don't see a recent transaction. Which client is this for?"

---

## Dependencies

### Existing Features (Required):
- **Feature 002+007**: ChromaDB Memory System
  - Structured metadata storage
  - Semantic search for duplicate detection
  - Used by: Transaction storage, follow-up linking

- **Feature 006**: RBAC (Role-Based Access Control)
  - Godfather permission validation
  - Used by: Permission checks before extraction

- **OpenAI GPT-4o-mini**: AI capabilities
  - Entity extraction from shorthand
  - Pattern recognition
  - Used by: Transaction parsing, follow-up detection

### New Dependencies:
- None (reuses all existing infrastructure)

---

## Configuration Requirements

### Feature Flag

```json
{
  "feature_flags": {
    "enable_entity_extraction": false
  }
}
```

**Default**: `false` (disabled until production-ready)

**Behavior when disabled**:
- DeniDin treats all group messages as normal conversation
- No entity extraction or confirmation replies
- No changes to existing receive-and-respond flow

---

## Success Metrics

- ✅ Extract client, company, amount from shorthand message
- ✅ Store structured transaction in memory with metadata
- ✅ Update transaction with follow-up details (phone, date)
- ✅ No false positives (ignore non-transaction messages)
- ✅ Handle duplicates without creating redundant entries
- ✅ Confirmation messages are clear and actionable

---

## Security & Privacy Considerations

1. **Data Validation**: Sanitize all extracted entities before storage
2. **Permission Check**: Only extract from Godfather's messages, not other group members
3. **Sensitive Data**: Transaction amounts and client names logged at DEBUG level only
4. **Metadata Integrity**: Validate JSON schema before storage to prevent corruption

---

## Open Questions

*(See "NEEDS CLARIFICATION" section above - 5 critical questions requiring human input before proceeding to plan.md)*

---

**Next Steps**:
1. ✅ **COMPLETE**: Initial spec created per METHODOLOGY template
2. ⏳ **PENDING**: Clarify all open questions (human input required)
3. ⏳ **BLOCKED**: Create `plan.md` (blocked on clarifications)
4. ⏳ **BLOCKED**: Create `tasks.md` (blocked on plan)
5. ⏳ **BLOCKED**: Implementation (blocked on tasks)

---

**Status**: 📋 **DRAFT - AWAITING CLARIFICATIONS**

**Created**: January 22, 2026  
**Author**: AI Agent (speckit.specify)  
**Approval**: PENDING human review and clarification responses
