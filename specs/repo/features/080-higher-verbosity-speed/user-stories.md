# User Stories: Higher Verbosity, Active Feedback, and Latency Telemetry

## Stories

### User Story 1 - The Patient Waiter (Keep-Alive) (Priority: P1)
**Given** the user submits a request that requires 40 seconds to process (e.g., heavy OCR and summarization)
**When** 20 seconds elapse since the last message
**Then** the bot MUST ensure the WhatsApp "typing..." indicator remains visible on the user's device by sending periodic presence updates to the Green API
**And** the indicator MUST only disappear once the processing is fully complete or a message is sent.

### User Story 2 - AI-Driven Progress Updates (Priority: P1)
**Given** the user asks a complex question requiring multiple internal tool calls
**When** the AI decides the task will take multiple steps (e.g., retrieving client details, then searching ledger, then drafting a response)
**Then** the AI MUST autonomously generate and send a brief, natural language update (e.g., "I'm checking the ledger for you right now...") to keep the user engaged
**And** this behavior MUST be driven generically by the system prompt/constitution rather than hardcoded edge-case handlers.

### User Story 3 - Consolidated Final Delivery (Priority: P2)
**Given** the AI has finished its internal processing and generated a substantial, 3-paragraph summary
**When** the response is dispatched to the user
**Then** it MUST be delivered as a single cohesive WhatsApp message rather than being artificially split into multiple partial messages.

### User Story 4 - Telemetry & Metrics Plumbing (Priority: P1)
**Given** a user message is fully processed by the system
**When** the execution cycle concludes
**Then** the system MUST record concrete, structured telemetry data
**And** the data MUST include end-to-end duration, total LLM inference time, and total tool execution time, stored in a queryable log or database for future performance audits.
