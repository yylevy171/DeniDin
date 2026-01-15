# Feature Specification: WhatsApp AI Chatbot Passthrough

**Feature Branch**: `001-whatsapp-chatbot-passthrough`  
**Created**: 2026-01-15  
**Status**: Draft  
**Input**: User description: "I want to create an whatsapp bot which is essentially a passthrough to an AI chat of my choice. The whatsapp is a business account which I have the credentials to, using a phone number I possess. Example: the chatbot (named DeniDin) is joined to a chat with another whatsapp user A. User A sends a message in the chat and DeniDin sends it to an AI chat, for example ChatGPT. DeniDin then sends back on whatsapp the response that was received from ChatGPT. This is phase 1. Next phases will be adding contexts for DeniDin which can be used via the whatsapp integration. For the integration with whatsapp use https://green-api.com/en/docs/chatbots/python/chatbot-demo/chatbot-demo-gpt-py/ as your source reference to build on. Copy or clone the code as a starting point. Preliminary task should be to be able to run this demo locally as a starting point, and then building on top of it the next phases"

## Clarifications

### Session 2026-01-15

- Q: How should DeniDin store and load sensitive credentials (API keys, tokens)? → A: JSON/YAML config file with gitignored secrets
- Q: How should DeniDin receive incoming WhatsApp messages from Green API? → A: Polling (receiveNotification API) with configurable interval
- Q: How should DeniDin handle multiple incoming messages while processing a previous message? → A: Sequential processing (single-threaded queue)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run Green API Demo Locally (Priority: P1)

Set up and run the existing Green API ChatGPT demo locally as a foundation for the DeniDin chatbot.

**Why this priority**: Establishing a working baseline is critical before any customization. This validates the development environment, credentials, and basic WhatsApp-to-AI integration flow.

**Independent Test**: Can be fully tested by running the demo script, sending a WhatsApp message to the business number, and receiving a ChatGPT response back. Delivers a working proof-of-concept.

**Acceptance Scenarios**:

1. **Given** the Green API demo code is cloned/copied locally, **When** the developer configures credentials and runs the script, **Then** the bot starts listening for WhatsApp messages
2. **Given** the bot is running, **When** a user sends "Hello" via WhatsApp to the business number, **Then** the bot forwards it to ChatGPT and returns the AI response to WhatsApp
3. **Given** the bot is running, **When** the developer stops the script, **Then** the bot gracefully shuts down without errors

---

### User Story 2 - Basic Message Passthrough (Priority: P2)

User A sends a message to DeniDin via WhatsApp, and DeniDin relays it to an AI chat service (ChatGPT) and returns the response.

**Why this priority**: This is the core functionality of Phase 1 - a simple, stateless message relay. Once P1 validates the demo works, P2 customizes it into the DeniDin bot.

**Independent Test**: Can be tested by sending any text message to DeniDin on WhatsApp and verifying the AI response is received within a reasonable timeframe (e.g., < 30 seconds).

**Acceptance Scenarios**:

1. **Given** DeniDin bot is active in a WhatsApp chat with User A, **When** User A sends "What is the capital of France?", **Then** DeniDin forwards the question to ChatGPT and replies with the AI's answer
2. **Given** DeniDin bot receives a message, **When** ChatGPT returns a response, **Then** DeniDin sends the full response back to the same WhatsApp chat
3. **Given** User A sends multiple messages in quick succession, **When** each is processed, **Then** DeniDin maintains the correct order of responses
4. **Given** DeniDin is in a group chat, **When** User A mentions DeniDin or sends a message, **Then** DeniDin responds only when explicitly addressed (to avoid spam)

---

### User Story 3 - Error Handling & Resilience (Priority: P3)

DeniDin gracefully handles errors from WhatsApp API, AI service, or network issues.

**Why this priority**: While critical for production reliability, basic error handling can be implemented after core functionality is proven. Allows iteration on P1 and P2 first.

**Independent Test**: Can be tested by simulating failures (e.g., invalid API credentials, AI service timeout, network disconnect) and verifying DeniDin responds appropriately.

**Acceptance Scenarios**:

1. **Given** the AI service (ChatGPT) is unreachable or times out, **When** DeniDin attempts to forward a message, **Then** DeniDin sends a fallback message to the user: "Sorry, I'm having trouble connecting to my AI service. Please try again later."
2. **Given** the WhatsApp API returns an error (e.g., rate limit), **When** DeniDin tries to send a message, **Then** DeniDin logs the error and retries with exponential backoff
3. **Given** DeniDin receives a malformed or unsupported message type (e.g., voice note, image), **When** processing the message, **Then** DeniDin replies: "I currently only support text messages."
4. **Given** the bot is running, **When** an unexpected exception occurs, **Then** the bot logs the error details and continues running (does not crash)

---

### User Story 4 - Configuration & Deployment (Priority: P4)

DeniDin can be configured with different WhatsApp credentials and AI service endpoints via environment variables or config files.

**Why this priority**: Essential for portability and security (credentials not hardcoded), but can be implemented after proving the core logic works.

**Independent Test**: Can be tested by changing credentials in a config file, restarting the bot, and verifying it connects to the new WhatsApp business account.

**Acceptance Scenarios**:

1. **Given** a `.env` file or config with Green API credentials, **When** the bot starts, **Then** it loads credentials from the config (not hardcoded)
2. **Given** the config specifies a different AI service endpoint (e.g., switching from ChatGPT to another AI), **When** a message is received, **Then** DeniDin routes to the configured AI service
3. **Given** credentials are missing or invalid, **When** the bot starts, **Then** it displays a clear error message and exits gracefully
4. **Given** the bot is deployed to a server (e.g., cloud VM), **When** it runs as a background service, **Then** it automatically restarts on failure and logs to a persistent location

---

### Edge Cases

- What happens when a user sends an extremely long message (> 4096 characters)?
  - AI service may truncate or reject it; DeniDin should handle gracefully
- What happens when ChatGPT returns a response longer than WhatsApp's message limit?
  - DeniDin should split the response into multiple messages or summarize
- What happens if the same user sends multiple messages before the first response arrives?
  - DeniDin should queue messages and process them in order, or inform the user to wait
- What happens if DeniDin is added to a group chat?
  - DeniDin should only respond when mentioned/tagged to avoid spamming
- What happens if the WhatsApp business account is logged out or credentials expire?
  - DeniDin should detect this and alert the admin (e.g., via logs or notification)
- What happens if the AI service changes its API structure or rate limits?
  - DeniDin should have abstracted AI integration to swap providers easily
- What happens if a user sends emojis, special characters, or non-English text?
  - DeniDin should pass them through to the AI service without corruption

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST clone or copy the Green API ChatGPT demo code as a starting point
- **FR-002**: System MUST allow running the demo locally with valid Green API and ChatGPT credentials
- **FR-003**: DeniDin bot MUST receive WhatsApp messages via Green API polling mechanism (receiveNotification API) with configurable poll interval
- **FR-004**: DeniDin bot MUST forward received messages to a configurable AI chat service (default: ChatGPT)
- **FR-005**: DeniDin bot MUST send the AI service's response back to the originating WhatsApp chat
- **FR-006**: System MUST support configuration via JSON/YAML config file (gitignored) containing:
  - Green API instance ID and token
  - ChatGPT API key
  - AI service endpoint URL
  - Polling interval (seconds)
- **FR-007**: System MUST handle text messages; image, voice, and video handling can be deferred to future phases
- **FR-008**: System MUST log all incoming messages, outgoing messages, and errors for debugging
- **FR-009**: System MUST gracefully handle AI service timeouts (e.g., > 30 seconds) and notify the user
- **FR-010**: System MUST detect and handle Green API rate limits or quota errors
- **FR-011**: System MUST only respond to messages in chats where DeniDin is a participant
- **FR-012**: System MUST identify itself as "DeniDin" when responding (e.g., in bot profile or message signature)
- **FR-013**: System MUST persist minimal state (e.g., last processed message ID) to avoid duplicate processing on restart
- **FR-014**: System MUST process incoming messages sequentially (single-threaded queue) to maintain strict ordering and simplify Phase 1 implementation

### Non-Functional Requirements

- **NFR-001**: System MUST respond to WhatsApp messages within 30 seconds under normal conditions
- **NFR-002**: System MUST be resilient to transient network failures (auto-retry with backoff)
- **NFR-003**: System MUST NOT expose API credentials in logs or error messages; config file MUST be gitignored
- **NFR-004**: System MUST be deployable on a single server or local machine (no complex infrastructure required for Phase 1)
- **NFR-005**: Code MUST be written in Python (to align with Green API demo reference)
- **NFR-006**: System MUST provide clear setup instructions (README) for running locally
- **NFR-007**: System MUST handle maximum throughput of ~100 messages/hour with sequential processing (sufficient for Phase 1 testing and small user base)

### Key Entities

- **WhatsAppMessage**: Represents an incoming message from a WhatsApp user
  - Attributes: sender ID, chat ID, message text, timestamp, message type
- **AIRequest**: Represents a request sent to the AI service
  - Attributes: prompt text, timestamp, user context (optional for Phase 1)
- **AIResponse**: Represents a response received from the AI service
  - Attributes: response text, timestamp, token count (optional)
- **BotConfiguration**: Represents the bot's runtime configuration
  - Attributes: Green API credentials, AI service credentials, polling interval, logging settings
  - Loaded from: JSON/YAML config file (e.g., `config.json` or `config.yaml`, gitignored)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Developer can run the Green API demo locally and receive a ChatGPT response to a WhatsApp message within 10 minutes of setup
- **SC-002**: DeniDin bot responds to 95% of text messages within 30 seconds (excluding AI service delays)
- **SC-003**: DeniDin bot operates continuously for 24 hours without crashing or requiring manual intervention
- **SC-004**: All credentials are loaded from config files (zero hardcoded secrets in source code)
- **SC-005**: Error logs capture sufficient detail to diagnose 100% of message failures (timestamps, message IDs, error codes)
- **SC-006**: README documentation allows a new developer to run the bot locally in < 30 minutes
