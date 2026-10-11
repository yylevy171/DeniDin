# Feature Specification: Instinct Worker

**Feature Branch**: `079-instinct-worker`  
**Created**: 2026-09-11
**Status**: Draft  
**Input**: User description: "Use "Instinct" as a "worker" - research and implications"

---

**CRITICAL - MANDATORY REQUIREMENT**:
🚨 **This feature MUST have a separate `user-stories.md` file** before spec approval:
- ✅ **`user-stories.md`** exists.

---

## User Stories Reference
See **`user-stories.md`** for full Given-When-Then criteria.
- **User Story 1**: Proactive Background Analysis (P1)
- **User Story 2**: Instinct Notifications (P2)

### Edge Cases
- What happens if the Instinct worker encounters an infinite loop of research? (Needs hard timeout/token limits).
- How do we handle race conditions if the user sends another message while Instinct is researching?

## Requirements *(mandatory)*

### Functional Requirements
- **REQ-079-01**: System MUST support spawning asynchronous "Instinct" tasks that run in the background (via APScheduler or similar queue) without blocking the primary WhatsApp webhook.
- **REQ-079-02**: The Instinct worker MUST be able to perform autonomous research (e.g., web scraping, deep document analysis, cross-referencing ChromaDB).
- **REQ-079-03**: The worker MUST be able to inject its findings back into the user's `SessionManager` so the context is preserved.
- **REQ-079-04**: The worker MUST have the ability to proactively dispatch a WhatsApp message with its findings once complete.

### Key Entities
- **InstinctWorker**: A background agent orchestrator.
- **BackgroundQueue**: A mechanism to queue and execute heavy tasks.

## Success Criteria *(mandatory)*

### Measurable Outcomes
- **SC-001**: Immediate WhatsApp webhook response time remains under 2 seconds even when a heavy Instinct task is triggered.
- **SC-002**: Instinct worker can successfully complete a 60-second research task and report back.
