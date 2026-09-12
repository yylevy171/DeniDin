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

## User Experience Testing Scenarios (UAT)

To ensure the "silent void" is effectively eliminated, the developers must manually verify the following timeline-based UX scenarios.

### Scenario A: The 45-Second Heavy Workflow (Document Upload)
**Goal**: Verify continuous typing indicator and proactive AI progress text during a long tool execution.
- **T=0s**: User sends a multi-page PDF document to DeniDin.
- **T+1s**: The bot attaches the fast-path "👀" reaction (Feature 084 logic). The WhatsApp `typing...` indicator appears on the user's screen.
- **T+5s**: The AI determines that OCR and analysis will take significant time. It autonomously dispatches a brief text: *"קיבלתי את המסמך, מתחיל לקרוא ולחלץ נתונים..."*
- **T+20s**: Behind the scenes, the system re-pings the Green API presence endpoint. The `typing...` indicator continues seamlessly without dropping.
- **T+35s**: The system pings the Green API presence endpoint again.
- **T+45s**: The internal pipeline finishes. DeniDin dispatches the final comprehensive analysis as a single cohesive message. The `typing...` indicator naturally stops. The initial "👀" reaction flips to "✅".

### Scenario B: The Multi-Step Lookup (Conversational)
**Goal**: Verify the AI constitution correctly instructs the bot to send an intermediate update when doing multi-tool research.
- **T=0s**: User asks: *"כמה הלקוח יוסי כהן שילם לנו השנה בסך הכל?"*
- **T+1s**: Bot attaches a "👍" reaction. `typing...` indicator appears.
- **T+8s**: The AI queries the client database, finds Yossi Cohen, and realizes it now needs to scan the ledger. It autonomously texts: *"שניה, אני בודק את היסטוריית התשלומים שלו ביומן..."*
- **T+20s**: The system re-pings the presence endpoint. `typing...` is maintained.
- **T+28s**: The final total is calculated and sent as a single message. `typing...` stops, and the "👍" flips to "✅".

### Scenario C: Telemetry Data Validation (Backend)
**Goal**: Verify the metrics plumbing captures the breakdown of where time was spent during Scenario A or B.
- **T=0**: Admin/Developer completes either Scenario A or B.
- **T+1**: Admin queries the new metrics log/database.
- **Expectation**: A distinct row/record exists for the processed message containing:
  - `total_duration_ms`: e.g., 28000
  - `llm_inference_ms`: e.g., 8500
  - `tool_execution_ms`: e.g., 18500
  - `tool_breakdown`: A breakdown showing exactly which tools took how long.
