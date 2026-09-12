# Feature Specification: WhatsApp Reactions

**Feature Branch**: `feature/084-whatsapp-reactions`  
**Created**: 2026-09-11  
**Clarified & Approved**: 2026-09-12 (with CEO)  
**Status**: Done (2026-09-13). `speckit.plan`/`speckit.tasks`/`speckit.implement` complete —
Phases 1-6 (T001-T011) implemented and green; the fast-path mechanism was later removed entirely
per explicit user instruction, with the fast ack now produced solely by the model's own
`react_to_message` tool call. A live-debugging follow-through session found and fixed three real
bugs surfaced by an actual user-reported miss (empty `tools` list on the reminder-followup call;
`REACT_TO_MESSAGE_TOOL`'s schema description needing to be imperative, not just descriptive; a
test fixture never wiring `green_api_bot`) — see `tasks.md`'s session addendum for the full
account. Verified via a real Morning-MCP-backed billed test plus a 15-test sanity-suite spot-check
(32 real `react_to_message` calls observed, correct emoji per outcome, zero dispatch failures).
T012 (further rotation-based tuning rounds) and T013 (live-dev-environment quickstart
verification) remain deliberately out of scope — see `tasks.md`. PR: #314.  
**Input**: User description: "Whatsapp reactions - react to user messages according to your interpretation; reaction can change according to your actions"

---

**CRITICAL - MANDATORY REQUIREMENT**:
🚨 **This feature MUST have a separate `user-stories.md` file** before spec approval:
- ✅ **`user-stories.md`** exists and conforms to Given-When-Then standard.

---

## Terminology Glossary

- **Reaction**: A native WhatsApp emoji attached to a specific user message bubble via Green API's `sendReaction` endpoint.
- **Reaction Flip**: Dynamically replacing an existing emoji reaction on an earlier message with a new emoji (e.g. from in-flight 🫡/👀 to terminal ✅/❌) to reflect workflow resolution.
- **Active Workflow Context**: A coherent business interaction lifecycle (e.g., document upload ➔ client clarification ➔ ledger event persistence) across which the initiating message ID remains accessible for post-resolution reaction flipping.
- **Fast-Path Heuristic**: A lightweight, fuzzy router-level reaction applied within milliseconds of webhook ingestion to give immediate visual feedback before the LLM inference completes.

---

## User Stories Reference

Complete user stories are defined in **[`user-stories.md`](file:///Users/yaron/Projects/DeniDin/teammate3/specs/repo/features/084-whatsapp-reactions/user-stories.md)**.

- **User Story 1**: Immediate Document Acknowledgment with Deferred Resolution Flip (Priority: P1)
- **User Story 2**: Action Request Immediate Receipt & Execution Outcome Flip (Priority: P1)
- **User Story 3**: AI Tool Agency (`react_to_message`) (Priority: P1)
- **User Story 4**: Conversational & Creative Expression (Priority: P2)
- **User Story 5**: Discretionary Silence in 1:1 and Group Chats (Priority: P2)

---

## User Scenarios & Testing *(mandatory UATs)*

### UAT-1: Document Ingestion with Deferred Resolution (Priority: P1)
**Journey**: A user sends an image or PDF of a fee agreement. DeniDin immediately pins a fuzzy in-flight emoji (e.g., 👀, 🔍, ⏳). If client resolution requires clarification (e.g., asking for missing client phone/email), the conversation continues. Once the onboarding/ledger capture is fully finalized, DeniDin navigates back to the *original document message* and flips its reaction to **✅** (or **⚠️/❌** if rejected).
- **Independent Test**: Send a fee agreement document, step through clarification, confirm initial 👀 appears in <1s, and confirm it flips to ✅ upon final ledger record creation.

### UAT-2: Action Request & Tool Outcome Flip (Priority: P1)
**Journey**: A user commands *"Create an invoice for 5,000 ILS for Client Y"*. DeniDin immediately acknowledges with an in-flight reaction (e.g., 🫡 or 👍). As the tool completes:
- Success: Reaction flips to **✅** (or **🎉**).
- Validation Failure / Blocked: Reaction flips to **⚠️** or **❓** alongside the explanatory reply.
- **Independent Test**: Issue an invoice creation command; observe the in-flight reaction flip to ✅ on successful Green Invoice generation.

### UAT-3: Creative & Conversational Sentiment (Priority: P2)
**Journey**: A user sends warm personal messages (e.g., *"Happy Rosh Hashana!"*, *"It's my birthday today"*, or *"You're a lifesaver, thank you"*). DeniDin exercises human-like emotional intelligence and attaches an expressive emoji (e.g., 🍯, 🎁, 🙏) alongside its conversational response.
- **Independent Test**: Send holiday greetings and observe appropriate, non-generic emoji reactions.

### UAT-4: Discretionary Silence (Priority: P2)
**Journey**: 
- In **Group Chats**: Ambient banter between human participants that does not mention DeniDin and does not trigger financial/ledger intent receives **zero reactions**.
- In **1:1 DMs**: Routine conversational turns or simple acknowledgments that do not warrant visual pinning receive **no reaction**.
- **Independent Test**: Verify that ambient group chat messages and low-signal 1:1 turns remain reaction-free.

---

## Edge Cases

- **Message Deleted Prior to Reaction**: If the user retracts or deletes a message before Green API delivers the reaction, the Green API call may return an error. The system MUST catch and suppress this error without interrupting conversational processing.
- **Green API Outage / Reaction Timeout**: Failure to send or flip an emoji MUST NEVER block, degrade, or fail the core conversational turn or ledger persistence.
- **Cross-Session Resumption**: If an active workflow spans across session expiration boundaries, the system SHOULD gracefully fall back to reacting only to the latest user message if the original message ID is no longer reachable in working memory.
- **Rapid Message Bursts**: If a user sends multiple messages in rapid succession, the router must react to the primary actionable message rather than firing duplicate reactions across all parts.

---

## Requirements *(mandatory)*

### Functional Requirements

- **REQ-084-001**: The system MUST integrate Green API's `sendReaction` endpoint (`chatId`, `idMessage`, `reaction`), allowing empty string `""` to clear reactions and new unicode emoji strings to replace existing reactions. *(Payload field corrected 2026-09-12 from `messageId` to `idMessage` — confirmed live via Gate Zero, see `research.md` R1; the endpoint name and behavior otherwise match as originally specified.)*
- **REQ-084-002**: The webhook router MUST provide a fuzzy fast-path reaction mechanism that acknowledges actionable requests and media documents in **under 1000ms**, selecting contextually plausible in-flight emojis (e.g. `["👀", "🔍", "⏳"]` for media; `["👍", "🫡", "👌"]` for tasks).
- **REQ-084-003**: The system MUST expose a dedicated AI tool (`react_to_message(emoji: str, message_id: Optional[str] = None)`) allowing the model to set or flip emoji reactions dynamically during its reasoning cycle. If `message_id` is omitted, it defaults to the current turn's incoming user message.
- **REQ-084-004**: In multi-turn workflows (e.g., document ingestion followed by client clarifications), the `SessionManager` / context pipeline MUST preserve the `originating_message_id` so the AI can flip the reaction on the original trigger message upon workflow resolution.
- **REQ-084-005**: In group chats, the system MUST ONLY react to messages that are actively processed by DeniDin (explicit mentions, direct replies to DeniDin, or recognized bot commands). Ambient group messages MUST be ignored with zero reactions.
- **REQ-084-006**: In 1:1 chats, the AI MUST exercise discretion—trivial remarks, simple acknowledgments, and trailing chatter MUST NOT be forced to have a reaction.
- **REQ-084-007**: Reaction failures (network timeout, invalid message ID, API error) MUST be logged at `WARNING` level and MUST NOT fail the active conversation or transaction.

### Key Entities

- **ReactionManager / GreenAPIClient**: Service handling the HTTP payload to Green API's reaction endpoint with retry/timeout safety.
- **ReactionRouter**: Fast-path heuristic evaluating incoming webhook `typeMessage` and text intent to apply instant in-flight feedback.
- **react_to_message Tool**: AI tool definition enabling dynamic reaction application and flipping.

---

## Success Criteria *(mandatory)*

- **SC-001**: Immediate fast-path reactions for incoming media and action requests are dispatched in **< 1.0s** from webhook arrival.
- **SC-002**: 100% of successful document-to-ledger onboarding flows flip the originating document reaction to ✅ upon completion.
- **SC-003**: Zero reaction webhooks are emitted for ignored ambient group chat messages.
- **SC-004**: Green API reaction errors/timeouts have a 0% failure impact on AI conversation generation and ledger transactions.
