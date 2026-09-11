# User Stories: WhatsApp Reactions

## Stories

### User Story 1 - Acknowledge Receipt (Priority: P1)
**Given** the user sends a message to DeniDin via WhatsApp
**When** the bot receives the webhook and begins processing the request
**Then** the bot MUST immediately react to the user's message with an appropriate emoji (e.g., 👀 or 👍) to indicate processing has started.
**Router Requirement**: @bot.router.message() must trigger a reaction action via Green API before AI processing completes.

### User Story 2 - Contextual Reaction (Priority: P2)
**Given** the user sends a message with strong sentiment (e.g., success or frustration)
**When** the AI Handler interprets the intent
**Then** the bot MUST react with a contextually appropriate emoji (e.g., ❤️ for praise) in addition to or instead of the default reaction.
