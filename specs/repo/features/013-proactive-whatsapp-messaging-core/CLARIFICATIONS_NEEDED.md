# Feature 013: Clarifications Needed - Proactive WhatsApp Messaging Core

**Created**: January 22, 2026  
**Status**: PENDING - Awaiting Human Input

---

## Critical Questions (Blocking Plan Creation)

### 1. OpenAI Function Calling
**Question**: Does GPT-4o-mini support tools/function calling? Should we use OpenAI's native function calling or custom prompt parsing?

**Context**: Need to determine how AI will trigger the "send message" action.

**Options**:
- A) Use OpenAI function calling (if supported)
- B) Custom prompt parsing ("SEND_MESSAGE: recipient=Benny, message=...")
- C) Structured system prompt with JSON response

**Decision**: PENDING

---

### 2. Green API SendMessage Endpoint
**Question**: What is the exact Green API endpoint for sending messages? What parameters are required? What are the rate limits?

**Action Required**: Research Green API documentation for:
- Endpoint URL format
- Required parameters (chat_id, message, other?)
- Rate limits
- Response format
- Error codes

**Decision**: PENDING - Needs API documentation research

---

### 3. Contact Resolution Fallback Strategy
**Question**: Should contact resolution use:
- A) Semantic memory search ONLY (ask Godfather if not found)
- B) Semantic memory first, then Green API GetContacts as fallback, then ask Godfather
- C) Green API GetContacts first, then semantic memory fallback

**Context**: Determines complexity and reliability of contact lookup.

**Decision**: PENDING

---

### 4. Message Composition Rules
**Question**: When should DeniDin use AI to compose vs. send Godfather's exact words?

**Examples**:
- Godfather: "Send Benny: Call me ASAP" → Send exact text "Call me ASAP"?
- Godfather: "Remind Benny about the payment" → AI composes reminder with context?

**Options**:
- A) Always use AI composition with context
- B) Detect explicit quotes/instructions ("Send X: ...") and send verbatim
- C) Always ask for confirmation before sending

**Decision**: PENDING

---

## Scope Questions (Affects Phase 1 Definition)

### 5. Group Messaging Support
**Question**: Should Phase 1 include sending messages to WhatsApp groups, or defer to Phase 2?

**Impact**: 
- Phase 1 with groups: Additional group resolution logic needed
- Phase 1 without groups: Simpler, faster delivery

**Decision**: PENDING

---

### 6. Permission Model
**Question**: Should proactive messaging be:
- A) Godfather-only (hardcoded permission check)
- B) Role-based from start (any role with permission can send)
- C) Godfather-only in Phase 1, role-based in Phase 2

**Context**: Affects security validation and future extensibility.

**Decision**: PENDING

---

### 7. Context Mixing Strategy
**Question**: When recipient (e.g., Benny) replies to a proactive message, should DeniDin use:
- A) Only Benny's session history (existing behavior)
- B) Only Godfather's memories about Benny
- C) Both combined (Benny's session + Godfather's context)

**Context**: Determines response quality and information sharing between contexts.

**Decision**: PENDING

---

### 8. Feature Flag Configuration
**Question**: Feature flag name and default value?

**Proposed**:
- Flag name: `enable_proactive_messaging`
- Default: `false` (disabled until production-ready)

**Confirm**: Is this acceptable or should it be different?

**Decision**: PENDING

---

### 9. Error Handling Strategy
**Question**: If Green API send fails (5xx, network error), should DeniDin:
- A) Retry once (per CONSTITUTION XI retry policy), then inform Godfather
- B) Retry once, inform Godfather, store for manual retry
- C) No retry, immediate failure notification

**Context**: Balances reliability vs. avoiding spam if persistent issues.

**Decision**: PENDING

---

### 10. Message Confirmation Format
**Question**: Should DeniDin always confirm to Godfather after sending? What format?

**Options**:
- A) Always: "Message sent to {name} ({phone})"
- B) Always: "Sent ✓"
- C) Only on failure (silent success)
- D) Configurable per message or globally

**Decision**: PENDING

---

## Research Tasks

1. **Green API Documentation**: Research SendMessage endpoint, parameters, rate limits
2. **OpenAI Function Calling**: Verify GPT-4o-mini support for tools/function calling
3. **Green API GetContacts**: Research contact retrieval capabilities (for fallback strategy)
4. **Error Codes**: Document Green API error codes for blocked users, invalid numbers, rate limits

---

**Total Questions**: 10 critical questions + 4 research tasks  
**Blocking**: All plan.md creation until resolved  
**Next Step**: Human input required for all decisions
