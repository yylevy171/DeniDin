# Feature Spec: Proactive WhatsApp Messaging Core

**Feature ID**: 013-proactive-whatsapp-messaging-core  
**Priority**: P1 (High)  
**Status**: Draft - Needs Clarification  
**Created**: January 22, 2026

---

## Problem Statement

DeniDin currently cannot proactively send messages - it only responds to incoming messages. Godfather cannot instruct DeniDin to send WhatsApp messages to other contacts.

**Current Limitation:**
- Godfather: "Send Benny a reminder about the payment he owes"
- DeniDin: ❌ Cannot execute - no capability to send proactive messages

**Desired Behavior:**
- Godfather asks DeniDin (via WhatsApp chat) to send a message to someone
- DeniDin uses memory/context to determine recipient identity and phone number
- DeniDin composes message using available context (e.g., payment history)
- DeniDin sends message via Green API
- Recipient receives message and can reply (handled by existing receiver bot)

---

## Terminology Glossary

- **Proactive Message**: Message initiated by DeniDin (not a reply to incoming message)
- **Recipient Resolution**: Process of converting a name (e.g., "Benny") to WhatsApp chat_id (e.g., "972501234567@c.us")
- **chat_id**: WhatsApp identifier format: `{phone_number}@c.us` for individuals, `{group_id}@g.us` for groups
- **Godfather**: Primary user with elevated permissions (phone: configured in config.json)
- **Contact Memory**: Information stored in ChromaDB about individuals including their WhatsApp identifiers
- **Semantic Resolution**: Using AI + memory search to identify who "Benny" is from past interactions

---

## User Scenarios & Testing

### 🔒 Test Immutability Principle

**Per CONSTITUTION Section VIII: Once tests for a phase are working and approved, they are IMMUTABLE.**

- Tests from completed phases **MUST NOT be changed** without **EXPLICIT HUMAN APPROVAL**
- New phases should **ADD new tests**, not modify existing ones
- Any test modification requires clear justification and human approval

---

### User Story 1 - Send Reminder Using Context (Priority: P1)

**As** the Godfather  
**I want to** instruct DeniDin to send payment reminders with historical context  
**So that** I can delegate collection follow-ups without manual lookups

**Independent Test**: Can be tested by having Godfather request a reminder message, verifying DeniDin searches memory for payment context, correctly identifies recipient, composes appropriate message, and sends via Green API.

**Acceptance Scenarios**:

1. **Given** Benny has previous WhatsApp conversations with DeniDin containing payment history  
   **When** Godfather says "Send Benny a reminder that he owes money including VAT"  
   **Then** DeniDin:
   - Searches semantic memory for "Benny" and retrieves chat_id (e.g., "972501234567@c.us")
   - Searches memory for payment context related to Benny
   - Composes reminder message including payment amount and VAT calculation
   - Sends message to Benny's chat_id via Green API
   - Confirms to Godfather: "Message sent to Benny (972501234567)"

2. **Given** Benny has never messaged DeniDin before  
   **When** Godfather says "Send Benny a reminder about the invoice"  
   **Then** DeniDin:
   - Searches memory for "Benny"
   - Finds no chat_id associated with "Benny"
   - Asks Godfather: "I don't have contact information for Benny. What's their phone number?"
   - Waits for Godfather to provide phone number
   - Once provided, sends message and stores contact info in memory for future use

3. **Given** multiple contacts named "Benny" exist in memory  
   **When** Godfather says "Send Benny the meeting notes"  
   **Then** DeniDin:
   - Finds multiple matches: "Benny Cohen (972501111111@c.us)", "Benny Levi (972502222222@c.us)"
   - Asks Godfather: "I found multiple contacts named Benny: Benny Cohen, Benny Levi. Which one?"
   - Waits for clarification
   - Sends to specified contact after disambiguation

---

### User Story 2 - Reply Continuity After Proactive Message (Priority: P2)

**As** a recipient of a DeniDin-initiated message  
**I want to** reply to the message and have DeniDin respond with full context  
**So that** I can have a natural conversation continuation

**Independent Test**: Can be tested by sending a proactive message, having the recipient reply, and verifying DeniDin uses both Godfather's context and recipient's session history in the response.

**Acceptance Scenarios**:

1. **Given** DeniDin sent Benny a payment reminder at Godfather's request  
   **When** Benny replies "How much exactly do I owe?"  
   **Then** DeniDin:
   - Processes incoming message through existing receiver bot
   - Retrieves session history with Benny
   - Retrieves relevant Godfather memories about Benny's debt
   - Responds with specific payment details from memory
   - Uses Benny's role permissions (CLIENT) for token limits

2. **Given** DeniDin sent a group message at Godfather's request  
   **When** multiple group members reply with questions  
   **Then** DeniDin:
   - Handles each reply as separate conversation thread
   - Uses group context + individual member history
   - Responds appropriately to each member

---

## 🚨 NEEDS CLARIFICATION

Before proceeding to plan.md, the following questions MUST be answered:

### Technical Questions:

1. **AI Function Calling**: 
   - Does OpenAI GPT-4o-mini support function calling (tools)?
   - If yes, should we use OpenAI's native function calling or implement custom parsing?
   - **DECISION NEEDED**: Preferred approach for AI to trigger message sending

2. **Green API Send Endpoint**:
   - What is the exact Green API endpoint for sending messages? (`SendMessage` method?)
   - What parameters are required? (chat_id, message text, other?)
   - Are there rate limits we need to handle?
   - **ACTION**: Verify Green API documentation for sending

3. **Contact Resolution Strategy**:
   - Should we ONLY use semantic memory search, or also call Green API's `GetContacts` as fallback?
   - If memory search fails, should we:
     - Option A: Ask Godfather immediately
     - Option B: Try Green API GetContacts first, then ask Godfather
   - **DECISION NEEDED**: Fallback strategy preference

4. **Feature Flag**:
   - Feature flag name: `enable_proactive_messaging`?
   - Default value: `false` (disabled in production until stable)?
   - **CONFIRM**: Naming and default value

5. **Error Handling**:
   - If Green API send fails (5xx, network error), should DeniDin:
     - Retry once (per CONSTITUTION XI retry policy)?
     - Inform Godfather of failure?
     - Store failed message for later retry?
   - **DECISION NEEDED**: Failed send handling strategy

6. **Message Confirmation**:
   - Should DeniDin always confirm to Godfather after sending?
   - Format: "Message sent to {name} ({phone})" or just "Sent ✓"?
   - **DECISION NEEDED**: Confirmation message format

### Functional Questions:

7. **Group Messaging**:
   - Should Phase 1 include group messaging?
   - If yes, how does Godfather specify a group? ("Send to Engineering Team"?)
   - **DECISION NEEDED**: Include groups in Phase 1 or defer to Phase 2?

8. **Message Composition**:
   - Should DeniDin always use AI to compose messages, or sometimes send Godfather's exact words?
   - Example: "Send Benny: 'Call me ASAP'" vs "Remind Benny about the payment"
   - **DECISION NEEDED**: AI composition vs. direct messaging rules

9. **Permission Validation**:
   - Should ONLY Godfather be allowed to request proactive messages?
   - Or should other roles with appropriate permissions also send? (Future consideration)
   - **DECISION NEEDED**: Initial permission model

10. **Conversation Context**:
    - When Benny replies to a proactive message, should DeniDin use:
      - Only Benny's session history? (existing behavior)
      - Only Godfather's context about Benny?
      - Both combined?
    - **DECISION NEEDED**: Context mixing strategy

---

## Functional Requirements

### FR1: Proactive Message Sending

**Priority**: P1

**Description**: DeniDin must be able to send WhatsApp messages to any contact at Godfather's request.

**Acceptance Criteria**:
- Given Godfather requests a message to a known contact
- When DeniDin resolves the recipient and composes message
- Then message is sent via Green API and confirmation returned to Godfather

**Implementation Notes**:
- Use OpenAI function calling (if supported) or system prompt instruction
- Call Green API `SendMessage` endpoint with resolved chat_id
- Follow CONSTITUTION XI retry policy for 5xx errors
- Log all send attempts with message_id correlation

---

### FR2: Recipient Resolution via Semantic Memory

**Priority**: P1

**Description**: DeniDin must resolve contact names (e.g., "Benny") to WhatsApp chat_id using semantic memory search.

**Acceptance Criteria**:
- Given a contact name mentioned in Godfather's request
- When DeniDin searches ChromaDB memories for that contact
- Then chat_id is extracted from memory results or disambiguation/error is returned

**Implementation Notes**:
- Query format: "What is {name}'s WhatsApp phone number or chat ID?"
- Search Godfather's memories only (`user_phone=godfather_phone`)
- Extract chat_id using regex pattern: `\d{10,15}@c\.us`
- Handle multiple matches by asking for disambiguation
- Handle no matches by asking Godfather for phone number

---

### FR3: Contact Information Storage

**Priority**: P1

**Description**: When Godfather provides a new contact's phone number, DeniDin must store it in memory for future retrieval.

**Acceptance Criteria**:
- Given Godfather says "Sarah is 972509876543" or provides number in response to DeniDin's question
- When DeniDin parses and validates the phone number
- Then memory entry is created with standardized format

**Implementation Notes**:
- Memory text format: `"Contact: {name}'s WhatsApp number is {phone}@c.us"`
- Metadata: `{"type": "contact_info", "contact_name": "{name}"}`
- Store under Godfather's user_phone
- Validate phone number format before storing

---

### FR4: Message Composition with Context

**Priority**: P1

**Description**: DeniDin must compose messages using retrieved context from memory.

**Acceptance Criteria**:
- Given Godfather requests "Send Benny reminder about payment including VAT"
- When DeniDin searches memory for payment context
- Then composed message includes specific payment details and VAT calculation

**Implementation Notes**:
- Search memories for context keywords (payment, VAT, amount, invoice)
- Include relevant context in AI prompt for message composition
- Maintain professional tone appropriate for business communications
- Keep messages concise (< 500 characters recommended)

---

### FR5: Disambiguation Handling

**Priority**: P2

**Description**: When multiple contacts match a name, DeniDin must ask Godfather for clarification.

**Acceptance Criteria**:
- Given memory search returns multiple matches for "Benny"
- When DeniDin presents options to Godfather
- Then Godfather selects correct contact and DeniDin proceeds

**Implementation Notes**:
- Format: "I found multiple contacts named {name}: {option1}, {option2}. Which one?"
- Include distinguishing info (last name, phone last 4 digits)
- Wait for Godfather's selection before proceeding
- Store disambiguation choice in conversation context

---

### FR6: Reply Continuity

**Priority**: P2

**Description**: When recipients reply to proactive messages, existing receiver bot must handle with full context.

**Acceptance Criteria**:
- Given recipient replies to a DeniDin-initiated message
- When DeniDin processes the incoming reply
- Then response uses both recipient's session history and relevant Godfather memories

**Implementation Notes**:
- No changes needed to existing receiver bot logic
- Session management automatically creates/continues recipient's session
- Memory search includes Godfather's context about recipient
- RBAC applies recipient's role (CLIENT) for token limits

---

## Edge Cases & Error Scenarios

### EC1: Unknown Contact with No Phone Provided

**Scenario**: Godfather requests message to unknown contact but doesn't provide phone when asked

**Expected Behavior**:
- DeniDin asks: "I don't have contact information for {name}. What's their phone number?"
- If Godfather responds with unrelated message (not a phone), DeniDin repeats question once
- If still no valid response, DeniDin says: "I cannot send the message without {name}'s phone number. Please provide it when ready."
- Do NOT retry indefinitely - bail after 2 attempts

---

### EC2: Green API Send Failure

**Scenario**: Green API returns 5xx error or network timeout when sending

**Expected Behavior**:
- Retry once after 1 second (per CONSTITUTION XI)
- If second attempt fails, inform Godfather: "⚠️ I couldn't send the message to {name} due to a connectivity issue. Please try again later."
- Log full error details at DEBUG level
- Do NOT store message for automatic retry (to avoid spam if issue persists)

---

### EC3: Invalid Phone Number Format

**Scenario**: Godfather provides phone number in invalid format (e.g., "123", "abc", "555-1234")

**Expected Behavior**:
- Validate phone number: 10-15 digits, no letters
- If invalid, respond: "That doesn't look like a valid WhatsApp number. Please provide the full number with country code (e.g., 972501234567)."
- Do NOT attempt to send to invalid number
- Do NOT store invalid number in memory

---

### EC4: Recipient Blocks DeniDin

**Scenario**: Recipient has blocked DeniDin's WhatsApp number

**Expected Behavior**:
- Green API may return specific error code for blocked recipient
- If detected, inform Godfather: "⚠️ {name} has blocked this number. Message could not be delivered."
- If not detectable, message appears sent but never delivers (Green API limitation)
- Log recipient block status if available from API

---

### EC5: Ambiguous Context Request

**Scenario**: Godfather says "Send him the info" without specifying who "him" refers to

**Expected Behavior**:
- DeniDin searches recent conversation context for pronouns/references
- If found in last 3 messages, resolve from context
- If ambiguous or not found, ask: "Who would you like me to send the info to?"
- Do NOT guess - always ask when uncertain

---

## Technology Choice: Semantic Memory for Contact Resolution

**Decision Date**: January 22, 2026 (proposed)

**Rationale**:
- ✅ **Already exists**: ChromaDB memory system with semantic search (Feature 002+007)
- ✅ **Zero new infrastructure**: No additional databases or APIs needed
- ✅ **Learns automatically**: Contact associations built from natural conversations
- ✅ **Semantic matching**: "Benny", "Benjamin", "Benny Cohen" all resolve correctly
- ✅ **Context-aware**: Finds contacts mentioned in past conversations even without direct messaging
- ✅ **Godfather-centric**: Searches Godfather's memories specifically

**Alternatives Considered**:
1. **Green API GetContacts**:
   - ❌ Requires API call overhead
   - ❌ Only knows contacts who've messaged the bot's WhatsApp number
   - ❌ No semantic matching (exact name match only)
   - ✅ Could work as fallback if memory search fails
   
2. **Manual Contact Database** (`config.json`):
   - ❌ Manual maintenance nightmare
   - ❌ Doesn't scale
   - ❌ Gets out of sync with reality
   
3. **Database Table** (SQLite/Postgres):
   - ❌ New infrastructure to maintain
   - ❌ No semantic search capabilities
   - ❌ Doesn't leverage existing memory investment

**Migration Path**:
- If semantic memory proves insufficient (too slow, low accuracy), add Green API GetContacts as secondary lookup layer
- If contact volume exceeds ChromaDB limits (10K+ contacts), evaluate dedicated contact management system

---

## Dependencies

### Existing Features (Required):
- **Feature 002+007**: ChromaDB Memory System
  - Semantic search for contact resolution
  - Used by: Contact lookup, context retrieval

- **Feature 006**: RBAC (Role-Based Access Control)
  - Godfather permission validation
  - Used by: Permission checks before sending messages

- **Green API Integration**: WhatsApp Business API
  - SendMessage endpoint
  - Used by: Actual message delivery

- **OpenAI GPT-4o-mini**: AI capabilities
  - Function calling for message triggers
  - Message composition
  - Used by: Trigger detection, message generation

### New Dependencies:
- None (reuses all existing infrastructure)

---

## Configuration Requirements

### Feature Flag

```json
{
  "feature_flags": {
    "enable_proactive_messaging": false
  }
}
```

**Default**: `false` (disabled until production-ready)

**Behavior when disabled**:
- DeniDin ignores proactive message requests from Godfather
- No changes to existing receive-and-respond flow
- No new AI functions registered

---

## Success Metrics

- ✅ Successfully send message to known contact (chat_id in memory)
- ✅ Successfully ask for and store new contact phone number
- ✅ Successfully handle disambiguation (multiple matches)
- ✅ Recipient replies are handled with combined context
- ✅ Error scenarios (API failures, invalid numbers) handled gracefully

---

## Security & Privacy Considerations

1. **Permission Enforcement**: Only Godfather can initiate proactive messages (validate sender role before processing)
2. **Phone Number Validation**: Sanitize and validate all phone numbers before sending to prevent injection attacks
3. **Sensitive Data Logging**: Mask phone numbers in logs per CONSTITUTION IX: `+972-50-***-1234`
4. **Rate Limiting**: Respect Green API rate limits to avoid account suspension
5. **Message Content**: Do NOT log full message content at INFO level (DEBUG only if needed)

---

## Open Questions

*(See "NEEDS CLARIFICATION" section above - 10 critical questions requiring human input before proceeding to plan.md)*

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
