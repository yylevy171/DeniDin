# Feature Specification: Higher Verbosity and Speed

**Feature Branch**: `080-higher-verbosity-speed`  
**Created**: 2026-09-11
**Status**: Draft  
**Input**: User description: "Higher verbosoty and speed, multiple replies per user message."

---

**CRITICAL - MANDATORY REQUIREMENT**:
🚨 **This feature MUST have a separate `user-stories.md` file** before spec approval:
- ✅ **`user-stories.md`** exists.

---

## User Stories Reference
See **`user-stories.md`** for full Given-When-Then criteria.
- **User Story 1**: Multi-Message Replies (P1)
- **User Story 2**: Streaming/Chunked Processing (P2)

### Edge Cases
- If the AI generates 10 paragraphs, sending 10 messages might trigger WhatsApp rate limits or annoy the user. Needs smart chunking.
- Out of order delivery if messages are dispatched too quickly concurrently.

## Requirements *(mandatory)*

### Functional Requirements
- **REQ-080-01**: The system MUST override the current "Be concise and direct" constraint in `runtime_constitution.md` to allow the AI to be more verbose when appropriate.
- **REQ-080-02**: The `AIHandler` MUST be able to split long generated text into logical chunks (e.g., by paragraph or thought boundary).
- **REQ-080-03**: The `WhatsAppHandler` MUST support dispatching multiple separate messages sequentially for a single incoming webhook.
- **REQ-080-04**: The system SHOULD explore streaming the response (if supported by Green API) or dispatching chunks as soon as they are generated to improve TTFB (Time To First Byte) perceived speed.

### Key Entities
- **ChunkingEngine**: Logic to parse the AI output stream into logical message boundaries.

## Success Criteria *(mandatory)*

### Measurable Outcomes
- **SC-001**: AI responses longer than 500 characters are automatically split into multiple readable WhatsApp messages.
- **SC-002**: Perceived response time (first message arrival) is reduced by at least 30% for verbose queries.
