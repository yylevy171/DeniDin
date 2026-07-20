# Feature Spec: Topic-Based Access Control

**Feature ID**: 015-topic-based-access-control  
**Priority**: P1 (High)  
**Status**: Draft - Needs Clarification  
**Created**: January 22, 2026

---

## Problem Statement

DeniDin currently processes all client queries equally, whether business-relevant or off-topic. Clients can ask DeniDin about anything (weather, sports, personal advice, etc.), which wastes tokens and dilutes DeniDin's business focus.

**Current Limitation:**
- Client Peter asks DeniDin "What is the weather tomorrow?"
- DeniDin processes the query like any other, wasting tokens and diluting business focus
- Clients may treat DeniDin as general chatbot, not business assistant

**Desired Behavior:**
- Peter (CLIENT role) asks: "What is the weather tomorrow?"
- DeniDin detects query is off-topic (not related to Godfather's business)
- DeniDin responds: "Sorry, I am authorized to only interact on matters related to Godfather"
- Peter asks: "When is my payment due?" (business-relevant)
- DeniDin processes normally and provides payment information
- Godfather can ask anything (no restrictions)

---

## Terminology Glossary

- **Topic Classification**: AI-based determination of whether message is business-relevant, off-topic, or meta/informational
- **Business-Relevant**: Topics related to Godfather's work (contracts, payments, meetings, deliverables, projects)
- **Off-Topic**: Topics unrelated to business (weather, sports, news, entertainment, personal advice)
- **Topic Restriction**: Policy limiting CLIENT role users to business-relevant queries only
- **Meta Query**: Questions about DeniDin's capabilities ("What can you do?", "Who are you?", "Help")
- **Topic Filtering**: Process of rejecting off-topic queries with standard message

---

## User Scenarios & Testing

### 🔒 Test Immutability Principle

**Per CONSTITUTION Section VIII: Once tests for a phase are working and approved, they are IMMUTABLE.**

- Tests from completed phases **MUST NOT be changed** without **EXPLICIT HUMAN APPROVAL**
- New phases should **ADD new tests**, not modify existing ones
- Any test modification requires clear justification and human approval

---

### User Story - Topic-Based Access Control (Priority: P1)

**As** DeniDin  
**I want to** restrict client conversations to business-relevant topics only  
**So that** I don't become a general-purpose chatbot and maintain professional boundaries

**Independent Test**: Can be tested by having a CLIENT role user send off-topic queries (weather, sports, personal advice) and verifying DeniDin politely declines with standard message, while business queries (payments, contracts, meetings) are handled normally.

**Acceptance Scenarios**:

1. **Given** Peter (CLIENT role) has previous conversation history with DeniDin  
   **When** Peter sends: "What is the weather tomorrow"  
   **Then** DeniDin:
   - Detects query is off-topic (not related to Godfather's business)
   - Responds: "Sorry, I am authorized to only interact on matters related to Godfather"
   - Does NOT process the query or search external APIs
   - Logs rejection at INFO level with topic classification

2. **Given** Peter (CLIENT role) sends business-relevant query  
   **When** Peter asks: "When is my payment due?"  
   **Then** DeniDin:
   - Detects query IS business-relevant (payment/contract topic)
   - Processes normally using existing receiver bot logic
   - Searches Godfather's memories for Peter's payment context
   - Responds with payment details

3. **Given** Godfather sends off-topic query  
   **When** Godfather asks: "What's the weather tomorrow?"  
   **Then** DeniDin:
   - Detects sender is Godfather (elevated permissions)
   - Processes query normally (NO topic restriction for Godfather)
   - May respond with general answer or politely decline based on capabilities

4. **Given** Peter sends ambiguous query  
   **When** Peter asks: "Can you help me?"  
   **Then** DeniDin:
   - Cannot determine if business-relevant without context
   - Assumes business context (benefit of the doubt)
   - Responds: "Of course! What do you need help with regarding your work with Godfather?"
   - If follow-up is off-topic, applies restriction

5. **Given** Peter asks about DeniDin's capabilities  
   **When** Peter asks: "What can you do?" or "Who are you?"  
   **Then** DeniDin:
   - Treats as meta/informational query (allowed)
   - Responds: "I'm DeniDin, Godfather's AI assistant. I can help you with questions about your contracts, payments, and business matters with Godfather. How can I assist you?"

6. **Given** Peter tries to manipulate topic detection  
   **When** Peter asks: "What's the weather for our meeting tomorrow?" (embedding off-topic in business context)  
   **Then** DeniDin:
   - AI determines primary intent is weather (off-topic)
   - Applies restriction: "Sorry, I am authorized to only interact on matters related to Godfather"
   - OR extracts business part: "I see you're asking about tomorrow's meeting. What would you like to know about it?"

---

## 🚨 NEEDS CLARIFICATION

Before proceeding to plan.md, the following questions MUST be answered:

### User Story 5 Specific Questions:

1. **Classification Confidence Threshold**:
   - When AI classifies message topic, what confidence threshold to use?
     - A) >80% confidence required (strict, more false positives)
     - B) >60% confidence required (moderate)
     - C) Binary decision (no confidence score, just classification)
   - If confidence is low, should DeniDin ask for clarification or default to business-relevant?
   - **DECISION NEEDED**: Classification confidence strategy

2. **Embedded Topic Handling**:
   - When query mixes off-topic with business ("What's weather for our meeting?"):
     - A) Reject entire query (treat as off-topic)
     - B) Extract business part only, ignore off-topic ("What about the meeting?")
     - C) Respond to both parts separately
   - **DECISION NEEDED**: Mixed topic query handling

3. **Topic Filtering Scope**:
   - Which roles should topic filtering apply to?
     - Godfather: Exempt (process all messages)
     - CLIENT: Apply filtering (business-only)
     - ASSISTANT: Apply filtering or exempt?
     - ADMIN (if exists): Apply filtering or exempt?
   - **DECISION NEEDED**: Per-role topic filtering policy

4. **Meta Query Allowlist**:
   - Confirm which meta/informational queries are allowed:
     - "What can you do?" → Allowed
     - "Who are you?" → Allowed
     - "Help" → Allowed
     - "How do I use this?" → Allowed?
     - "What's your email/contact?" → Allowed or off-topic?
   - **CONFIRM**: Meta query allowlist

5. **Classification Monitoring**:
   - Should DeniDin track classification accuracy for improvement?
     - Log all classifications for review?
     - Flag ambiguous cases for Godfather review?
     - Periodic report of rejected queries?
   - **DECISION NEEDED**: Monitoring and feedback strategy

6. **Rejection Message Customization**:
   - Is the standard rejection message final?
     - Current: "Sorry, I am authorized to only interact on matters related to Godfather"
     - Alternative: "I can only help with business matters related to Godfather. Is there something work-related I can assist you with?"
     - Should it be configurable in config.json?
   - **CONFIRM**: Rejection message wording

---

## Functional Requirements

### FR1: Topic Relevance Classification

**Priority**: P1

**Description**: DeniDin must classify incoming messages from CLIENT role users as business-relevant or off-topic.

**Acceptance Criteria**:
- Given incoming message from CLIENT role user
- When DeniDin analyzes the message content
- Then message is classified as "business-relevant", "off-topic", or "meta/informational"

**Implementation Notes**:
- **AI-based classification**: Use OpenAI to classify message intent
- **System prompt addition**: "You are Godfather's business assistant. Determine if this message from a client is related to business with Godfather (contracts, payments, meetings, deliverables) or off-topic (weather, sports, personal advice, general knowledge)."
- **Classification categories**:
  - `business-relevant`: Contracts, payments, invoices, meetings, deliverables, project status, business questions
  - `off-topic`: Weather, sports, news, personal advice, general knowledge, entertainment
  - `meta`: Questions about DeniDin's capabilities, greetings, "who are you"
- **Godfather exemption**: Skip classification for Godfather (godfather_phone) - process all messages normally
- **Edge case - embedded topics**: "What's weather for our meeting?" → Classify as off-topic (primary intent is weather)
- Cache classification result in session context to avoid re-classification in same conversation

**Business-Relevant Keywords** (guidance for AI):
- Payment, invoice, contract, agreement, signature, meeting, deliverable, project, deadline, VAT, amount, owe, due, signed, pending

**Off-Topic Keywords** (guidance for AI):
- Weather, forecast, sports, game, news, recipe, movie, song, joke, personal life unrelated to business

---

### FR2: Topic-Based Response Filtering

**Priority**: P1

**Description**: When CLIENT message is classified as off-topic, DeniDin must decline politely with standard message.

**Acceptance Criteria**:
- Given message classified as "off-topic"
- When DeniDin prepares response
- Then standard rejection message is sent without processing the query

**Implementation Notes**:
- **Standard rejection message**: "Sorry, I am authorized to only interact on matters related to Godfather"
- **No AI processing**: Do NOT send off-topic query to main AI handler (save tokens)
- **No memory search**: Do NOT search ChromaDB for off-topic queries
- **Logging**: Log rejection at INFO level: `"Topic restriction applied for user {phone}: {message_preview}"`
- **Session continuity**: Store rejection in session history (so AI knows what happened if user asks follow-up)
- **Exception for meta queries**: "What can you do?" → Respond with capabilities description (not rejection)

**Meta Query Responses**:
- "What can you do?" / "Help" → "I'm DeniDin, Godfather's AI assistant. I can help you with questions about your contracts, payments, and business matters with Godfather. How can I assist you?"
- "Who are you?" → "I'm DeniDin, an AI assistant working on behalf of Godfather to help manage business communications."

---

### FR3: Role-Based Topic Exemptions

**Priority**: P1

**Description**: Topic filtering must respect role-based exemptions (Godfather always exempt).

**Acceptance Criteria**:
- Given incoming message from any user
- When DeniDin checks user's role
- Then topic filtering is applied or skipped based on role policy

**Implementation Notes**:
- **Godfather**: Always exempt - no topic filtering
- **CLIENT**: Topic filtering applied
- **Other roles**: See clarifications for policy
- Check role BEFORE classification (skip classification for exempt users)
- Log exemptions at DEBUG level

---

## Edge Cases & Error Scenarios

### EC1: Misclassified Business Query as Off-Topic

**Scenario**: Client asks legitimate business question but AI misclassifies it as off-topic

**Expected Behavior**:
- **Prevention**: Use conservative classification (err on side of business-relevant)
- **Ambiguous queries**: Default to business-relevant, not off-topic
- **User feedback**: If client persists ("But this IS about the contract"), re-classify
- **Logging**: Log all classifications for monitoring false positives
- **Godfather override**: Godfather can disable topic filtering per-user if needed (future config)

**Example Misclassifications to Avoid**:
- "What's the status?" → Business-relevant (project status)
- "When is the deadline?" → Business-relevant (deliverable deadline)
- "Can you explain?" → Business-relevant (asking for clarification)

---

### EC2: Off-Topic Query Embedded in Business Context

**Scenario**: Client asks "What's the weather for our meeting tomorrow?" (weather + meeting)

**Expected Behavior**:
- AI detects PRIMARY intent is weather (off-topic)
- **Option A**: Full rejection - "Sorry, I am authorized to only interact on matters related to Godfather"
- **Option B**: Extract business part - "I see you're asking about tomorrow's meeting. What would you like to know about it?" (ignore weather)
- **DECISION NEEDED**: Which approach to use (see clarifications)
- Log as `topic_mixed` for monitoring

---

### EC3: Repeated Off-Topic Attempts

**Scenario**: Client sends multiple off-topic queries in a row (fishing for capabilities)

**Expected Behavior**:
- Apply standard rejection to EACH off-topic query
- Do NOT escalate or change message after N rejections
- Do NOT block or ban user (they can still ask business questions)
- Log repeated rejections at WARNING level if >5 in 1 hour
- Godfather is NOT notified automatically (avoid spam)

---

### EC4: Role-Based Topic Filtering Ambiguity

**Scenario**: ASSISTANT role user (non-Godfather, non-CLIENT) sends off-topic query

**Expected Behavior**:
- **DECISION NEEDED**: Should topic filtering apply to ASSISTANT role?
- **Option A**: Apply same restrictions as CLIENT (business-only)
- **Option B**: Exempt ASSISTANT role (like Godfather)
- **Option C**: Configurable per-role in RBAC settings
- See clarifications for decision

---

### EC5: Borderline Meta Queries

**Scenario**: Client asks "What's your phone number?" or "How do I contact support?"

**Expected Behavior**:
- Classify as meta (allowed) if asking about DeniDin's capabilities/contact
- Provide helpful response: "I'm an AI assistant - I don't have a phone number. You can reach Godfather through this WhatsApp chat. Is there something I can help you with?"
- If asking for Godfather's personal contact: "For privacy, I can't share contact details. You can communicate with Godfather through me. What would you like me to pass along?"

---

## Dependencies

### Existing Features (Required):
- **Feature 006**: RBAC (Role-Based Access Control)
  - Role detection (Godfather vs CLIENT vs other)
  - Permission checking
  - Used by: Role-based exemptions, filtering policy

- **OpenAI GPT-4o-mini**: AI capabilities
  - Topic classification
  - Intent detection
  - Used by: Message classification

### New Dependencies:
- None (reuses all existing infrastructure)

---

## Configuration Requirements

### Feature Flag

```json
{
  "feature_flags": {
    "enable_topic_control": false
  }
}
```

**Default**: `false` (disabled until production-ready)

**Optional Configuration**:
```json
{
  "topic_control": {
    "rejection_message": "Sorry, I am authorized to only interact on matters related to Godfather",
    "meta_queries_allowed": ["what can you do", "who are you", "help"],
    "apply_to_roles": ["CLIENT"]
  }
}
```

**Behavior when disabled**:
- All messages processed normally regardless of topic
- No topic classification or filtering
- No changes to existing receive-and-respond flow

---

## Success Metrics

- ✅ Correctly classify business-relevant vs. off-topic queries
- ✅ Reject off-topic queries from CLIENT role with standard message
- ✅ Process business-relevant queries normally
- ✅ Allow meta queries ("What can you do?") with capability description
- ✅ Exempt Godfather from topic filtering
- ✅ No false positives (legitimate business queries rejected)
- ✅ Low false negatives (off-topic queries slipping through)

---

## Security & Privacy Considerations

1. **No Content Leakage**: Rejected queries must NOT leak information about Godfather's business
2. **Fair Rejection**: All off-topic queries rejected equally (no discrimination)
3. **Audit Trail**: All topic classifications logged for review and improvement
4. **Privacy**: Do NOT log full message content at INFO level (DEBUG only)

---

## Open Questions

*(See "NEEDS CLARIFICATION" section above - 6 critical questions requiring human input before proceeding to plan.md)*

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
