# Feature Specification: WhatsApp Reactions

**Feature Branch**: `084-whatsapp-reactions`  
**Created**: 2026-09-11
**Status**: Draft  
**Input**: User description: "Whatsapp reactions - react to user messages according to your interpretation; reaction can change according to your actions"

---

**CRITICAL - MANDATORY REQUIREMENT**:
🚨 **This feature MUST have a separate `user-stories.md` file** before spec approval:
- ✅ **`user-stories.md`** exists.

---

## User Stories Reference
See **`user-stories.md`** for full Given-When-Then criteria.
- **User Story 1**: Acknowledge Receipt (P1)
- **User Story 2**: Contextual Reaction (P2)

### Edge Cases
- What happens if the Green API reaction endpoint fails or times out? (Should not block AI processing).
- What if the user deletes the message before we react?

## Requirements *(mandatory)*

### Functional Requirements
- **REQ-084-01**: System MUST be able to send emoji reactions to specific user messages via Green API.
- **REQ-084-02**: System MUST react immediately with a processing indicator (e.g. 👀) to confirm receipt before OpenAI generation completes.
- **REQ-084-03**: AIHandler MUST be capable of yielding a contextual reaction (e.g. ❤️, 👍, 👎) based on the user's sentiment or the outcome of an MCP tool call (e.g. reacting with ✅ after an invoice is created).

### Key Entities
- **GreenAPI Client**: Needs extended methods to support the `reaction` endpoint.
- **Message**: Needs to track message ID to apply the reaction correctly.

## Success Criteria *(mandatory)*

### Measurable Outcomes
- **SC-001**: 100% of valid incoming messages receive an immediate receipt reaction within 1 second.
- **SC-002**: Contextual reactions match user sentiment in at least 90% of tested cases.
