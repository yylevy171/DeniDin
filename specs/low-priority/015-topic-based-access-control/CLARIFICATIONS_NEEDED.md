# Feature 015: Clarifications Needed - Topic-Based Access Control

**Created**: January 22, 2026  
**Status**: PENDING - Awaiting Human Input

---

## Critical Questions (Blocking Plan Creation)

### 1. Classification Confidence Threshold
**Question**: When AI classifies message topic, what confidence threshold should be used?

**Options**:
- A) >80% confidence required (strict, more false positives = business queries rejected)
- B) >60% confidence required (moderate, balanced)
- C) >40% confidence required (lenient, fewer false positives)
- D) Binary decision (no confidence score, just classification)

**Follow-up**: If confidence is low (<threshold), should DeniDin:
- Ask client for clarification: "I'm not sure what you're asking about. Is this related to your work with Godfather?"
- Default to business-relevant (benefit of the doubt)
- Default to off-topic (strict filtering)

**Context**: Affects false positive rate (legitimate business queries rejected).

**Decision**: PENDING

---

### 2. Embedded Topic Handling
**Question**: When query mixes off-topic with business ("What's the weather for our meeting tomorrow?"), how should DeniDin respond?

**Options**:
- A) Reject entire query (treat as off-topic because primary intent is weather)
- B) Extract business part only, ignore off-topic: "I see you're asking about tomorrow's meeting. What would you like to know about it?"
- C) Respond to business part, acknowledge but don't answer off-topic: "I can help with the meeting, but not the weather. What do you need to know about the meeting?"
- D) Split response: Answer business part, decline off-topic part separately

**Context**: Determines user experience when queries blend topics.

**Decision**: PENDING

---

### 3. Topic Filtering Scope by Role
**Question**: Which roles should topic filtering apply to?

**Proposed Policy**:
- **Godfather**: Exempt (no topic filtering, process all messages)
- **CLIENT**: Apply filtering (business-only)
- **ASSISTANT**: ??? (need decision)
- **ADMIN**: ??? (need decision)
- **BLOCKED**: Already blocked entirely (no change)

**Options for ASSISTANT/ADMIN**:
- A) Apply same restrictions as CLIENT (business-only)
- B) Exempt like Godfather (no filtering)
- C) Configurable per-role in RBAC settings
- D) ASSISTANT exempt, ADMIN applies filtering

**Decision**: PENDING

---

### 4. Meta Query Allowlist
**Question**: Confirm which meta/informational queries should be allowed (bypass topic filtering).

**Proposed Allowlist**:
- "What can you do?" → Allowed ✓
- "Who are you?" → Allowed ✓
- "Help" → Allowed ✓
- "How do I use this?" → Allowed? (decision needed)
- "What's your phone number?" → Allowed? (decision needed)
- "How do I contact Godfather?" → Allowed? (decision needed)
- "What are your capabilities?" → Allowed ✓

**Options**:
- A) Use proposed allowlist as-is
- B) Expand allowlist (specify additional queries)
- C) Use AI to classify "meta" vs. "off-topic" dynamically (no hardcoded list)

**Decision**: PENDING

---

### 5. Classification Monitoring and Feedback
**Question**: Should DeniDin track classification accuracy for improvement?

**Options**:
- A) No monitoring (simple, no overhead)
- B) Log all classifications at DEBUG level (review later)
- C) Log all classifications at INFO level + flag ambiguous cases (confidence <70%)
- D) Periodic report to Godfather: "This week I rejected 15 off-topic queries from clients"
- E) Interactive feedback: After rejecting query, ask client "Was this actually business-related? (yes/no)" to improve

**Context**: Helps identify false positives and improve classification over time.

**Decision**: PENDING

---

### 6. Rejection Message Customization
**Question**: Is the standard rejection message final, or should it be customizable?

**Current Proposed Message**:
"Sorry, I am authorized to only interact on matters related to Godfather"

**Alternative Messages**:
- "I can only help with business matters related to Godfather. Is there something work-related I can assist you with?"
- "I'm designed to assist with Godfather's business matters. For other topics, please contact Godfather directly."
- "I focus on business-related queries about your work with Godfather. How can I help with that?"

**Options**:
- A) Use current message as-is
- B) Use alternative message (specify which)
- C) Make it configurable in config.json: `topic_control.rejection_message`
- D) Different messages for different contexts (first rejection vs. repeated, ambiguous vs. clear off-topic)

**Decision**: PENDING

---

### 7. Godfather Notification on Repeated Rejections
**Question**: Should Godfather be notified if a client repeatedly sends off-topic queries?

**Scenarios**:
- Client sends 5+ off-topic queries in 1 hour
- Client sends 10+ off-topic queries in 1 day

**Options**:
- A) Never notify Godfather (avoid spam)
- B) Notify after threshold (e.g., 5 rejections in 1 hour)
- C) Daily summary: "Peter attempted 8 off-topic queries today"
- D) Only notify if client asks meta question: "Why won't you answer?" (signals confusion)

**Decision**: PENDING

---

### 8. Business-Relevant Keyword Customization
**Question**: Should the business-relevant keyword list be customizable per deployment?

**Current Keywords** (guidance for AI):
- Payment, invoice, contract, agreement, signature, meeting, deliverable, project, deadline, VAT, amount, owe, due, signed, pending

**Options**:
- A) Hardcoded in system prompt (current approach)
- B) Configurable in config.json: `topic_control.business_keywords`
- C) AI learns from Godfather's conversation patterns (no explicit keywords)
- D) Hybrid: Base keywords + Godfather can add custom ones

**Context**: Different businesses have different terminology.

**Decision**: PENDING

---

## Research Tasks

1. **OpenAI Classification Capabilities**: Test GPT-4o-mini accuracy for topic classification with sample queries
2. **Confidence Scoring**: Verify if OpenAI returns confidence scores or only classifications
3. **False Positive Examples**: Collect edge cases where business queries might be misclassified

---

**Total Questions**: 8 critical questions + 3 research tasks  
**Blocking**: All plan.md creation until resolved  
**Next Step**: Human input required for all decisions
