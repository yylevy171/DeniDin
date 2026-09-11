# User Stories: Instinct Worker

## Stories

### User Story 1 - Proactive Background Analysis (Priority: P1)
**Given** the user sends a complex request requiring research
**When** the bot processes the message
**Then** an asynchronous "Instinct" worker MUST be able to spawn in the background to gather additional context or perform heavy processing without blocking the immediate WhatsApp response.
**Integration Requirement**: Must integrate with APScheduler or a new background task queue.

### User Story 2 - Instinct Notifications (Priority: P2)
**Given** the Instinct worker completes its background analysis
**When** the result is ready
**Then** it MUST proactively send a follow-up WhatsApp message to the user with the findings.
