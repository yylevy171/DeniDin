# User Stories: WhatsApp Reactions

**Feature ID**: `084-whatsapp-reactions`  
**Feature Branch**: `feature/084-whatsapp-reactions`  

---

## User Stories & Acceptance Criteria

### User Story 1 - Immediate Document Acknowledgment with Deferred Resolution Flip (Priority: P1)
**As a** busy lawyer sending a photo or PDF of a client fee agreement via WhatsApp,  
**I want** DeniDin to immediately pin a "looking/analyzing" emoji on my document and later flip it to a green checkmark once the ledger capture is finalized,  
**So that** I receive instant confirmation that my file is being processed and a clear visual record that it was successfully onboarded.

**Why this priority**: Core value proposition. Visual receipt confirmation saves the user from uncertainty and prevents duplicate uploads.

**Independent Test**: Can be tested by sending an agreement document, going through any needed client name/detail clarifications across multiple turns, and verifying the initial reaction (e.g., 👀) flips to ✅ on the original upload message once the ledger record is saved.

**Acceptance Scenarios**:
1. **Given** a user uploads a PDF or image fee agreement in a 1:1 chat,  
   **When** the Green API webhook reaches the router,  
   **Then** the bot MUST immediately react to the document message with an in-flight emoji (e.g., 👀 or 🔍) in under 1 second,  
   **And** the router MUST preserve the document's `message_id` as the `originating_message_id` in the active workflow context.
2. **Given** an in-flight document upload undergoing client resolution clarification,  
   **When** the user provides the missing details and the ledger event is persisted,  
   **Then** the AI MUST invoke `react_to_message(emoji="✅", message_id=originating_message_id)` to flip the emoji on the original document.
3. **Given** an uploaded document that is unreadable or rejected,  
   **When** the analysis fails,  
   **Then** the bot MUST flip the reaction on the document message to ⚠️ or ❌ alongside an explanatory text message.

**Router/Dispatcher Requirement**: `@bot.router.message(type_message in ['imageMessage', 'documentMessage'])` must trigger the immediate reaction dispatcher prior to delegating to `MediaHandler`.

---

### User Story 2 - Action Request Immediate Receipt & Execution Outcome Flip (Priority: P1)
**As a** user asking DeniDin to perform an administrative action (e.g. create a client, issue an invoice),  
**I want** DeniDin to acknowledge my request with a receipt reaction (e.g., 🫡 or 👍) and flip it to ✅ or ❌ when the tool execution completes,  
**So that** I can see the real-time status of my command directly on my message bubble.

**Why this priority**: Directly replaces spammy "Working on it..." text replies with elegant native status indicators.

**Independent Test**: Send a command like *"Create invoice for 3,000 ILS to Moshe"*; verify initial 👍 appears, followed by ✅ once the Morning API responds with document creation confirmation.

**Acceptance Scenarios**:
1. **Given** a user issues a command to create an invoice or client,  
   **When** the message is parsed as an actionable command,  
   **Then** the system MUST attach an acknowledgment emoji (e.g., 👍, 🫡, or 👌).
2. **Given** the command executes successfully via the Morning MCP tool,  
   **When** the tool returns success,  
   **Then** the reaction MUST flip to ✅.
3. **Given** the command fails due to validation or API error,  
   **When** the tool returns an error,  
   **Then** the reaction MUST flip to ⚠️ or ❌.

**Router/Dispatcher Requirement**: AIHandler reasoning pipeline must support mid-turn and post-tool reaction updates.

---

### User Story 3 - AI Tool Agency (`react_to_message`) (Priority: P1)
**As an** AI agent handling user conversations,  
**I want** a dedicated `react_to_message` tool,  
**So that** I can dynamically apply, update, or flip reactions during my execution based on context and tool outcomes.

**Why this priority**: Foundational architectural capability required for all dynamic and contextual reactions.

**Independent Test**: Verify via unit and integration tests that `react_to_message(emoji="✅")` triggers Green API's `sendReaction` endpoint with the expected parameters.

**Acceptance Scenarios**:
1. **Given** the AI model decides to react to the user's turn,  
   **When** the AI calls `react_to_message(emoji="🙏")`,  
   **Then** the system MUST call Green API `sendReaction` for the current user message ID.
2. **Given** the AI calls `react_to_message` with an explicit `message_id`,  
   **When** that message ID exists in the active workflow context,  
   **Then** the system MUST call Green API `sendReaction` for that specific target message ID.
3. **Given** the Green API reaction call times out or fails,  
   **When** the tool execution finishes,  
   **Then** the error MUST be logged at `WARNING` and MUST NOT terminate the conversational response.

---

### User Story 4 - Conversational & Creative Expression (Priority: P2)
**As a** user sharing a personal sentiment, holiday wish, or birthday greeting with DeniDin,  
**I want** DeniDin to react with culturally and contextually appropriate emoji (e.g., 🍯 for Rosh Hashana, 🎁 for birthdays),  
**So that** interacting with DeniDin feels warm, personal, and human.

**Why this priority**: Enhances brand affinity and relationship building in legal and professional settings.

**Independent Test**: Send greeting *"חג שמח לכולם!"* and observe a warm holiday emoji reaction (e.g. 🍎, 🍯, or ✨) paired with the reply.

**Acceptance Scenarios**:
1. **Given** a user message expressing a holiday greeting or celebration,  
   **When** the AI interprets the sentiment,  
   **Then** the AI SHOULD call `react_to_message` with a contextually creative emoji matching the occasion.
2. **Given** a user expressing gratitude (*"Thank you so much, amazing job"*),  
   **When** the AI processes the praise,  
   **Then** the AI MAY react with an appreciative emoji (e.g., 🙏 or ❤️).

---

### User Story 5 - Discretionary Silence in 1:1 and Group Chats (Priority: P2)
**As a** participant in a WhatsApp group or 1:1 chat,  
**I want** DeniDin to remain silent and NOT react to messages that do not concern it or do not warrant a reaction,  
**So that** the chat is never overwhelmed with noisy, unnecessary reactions.

**Why this priority**: Prevents spam, maintains professional decorum, and avoids annoying users.

**Independent Test**: Simulate an ambient group conversation between two humans not addressing DeniDin; verify 0 reaction API calls are made. In 1:1, simulate simple "ok" or trailing emojis and verify no reaction is forced.

**Acceptance Scenarios**:
1. **Given** an incoming message in a group chat that does NOT mention DeniDin and does NOT trigger a bot command,  
   **When** the webhook router triages the event,  
   **Then** the system MUST discard the message with ZERO reaction API calls.
2. **Given** a routine or trivial turn in a 1:1 chat (e.g., a simple acknowledgement or closing emoji),  
   **When** the AI generates its response,  
   **Then** the AI MUST NOT be forced to react if an emoji is unnecessary.

---

## Acceptance Approach (`billed`/`expensive`) — Human Decision (2026-09-12)

Per METHODOLOGY.md §VI.a/§IV Phase -1, this section normally holds a fixed, human-approved list of
`billed`/`expensive` acceptance scenarios. For this feature, an initial draft of 9 such scenarios
was presented and reviewed — but the human operator explicitly redirected the approach instead:
**reaction/emoji *choice* is a taste judgment, not something a fixed acceptance test should assert
on.** Locking in one "correct" emoji per scenario would test the wrong thing and fight the model's
own legitimate judgment.

**What replaces it**: deterministic plumbing (tool wiring and RBAC attachment, the fast-path hook's
dispatch placement, the group-ambient-silence hard gate, the `message_id` resolution fallback
chain, flip-not-stack targeting correctness) is still covered by ordinary hard-assertion
unit/integration tests, unchanged. Reaction *judgment quality* — which emoji, whether to react at
all — is instead tuned through an iterative, AI-run capture-and-review loop, performed by the
agent itself (not a human watching WhatsApp), covering both billed and, eventually, expensive
(real vision/document) scenarios. Full mechanism: `contracts/reaction-judgment-tuning.md`.

This satisfies Phase -1's intent (the human and the AI aligning on the actual approach and
observable outcome before/alongside technical design) via this explicit decision, rather than via
a fixed scenario list.
