# Feature 103: Evaluation & Spike — Migrating to a Vanilla Agent SDK (Google ADK, LangChain/LangGraph, etc.)

**Feature Branch**: `feature/103-agent-sdk-migration-evaluation`  
**Status**: Backlog  
**Priority**: P3 (Strategic Architectural Spike / Hygiene)  
**Origin**: CEO Request (2026-10-15) — "consider moving to vanilla agent sdk like google's ADK, langchain, etc."  
**Depends on**: Feature 063 (Dynamic Capability Backbone), Feature 070 (Rolling Memory Window)  

---

## 1. Business & Architectural Goals

### 1.1 The Opportunity
Currently, DeniDin runs on a proprietary, bespoke conversational agent engine:
1. **Legacy Path (`AIHandler`)**: Monolithic state machine, hand-crafted system prompts (`runtime_constitution.md`), raw OpenAI chat completions wrapper, and manual pending-approval managers.
2. **Backbone Path (`Backbone`, Feature 063)**: Dynamic Capability Backbone with model-driven tool loops (`load_flows`, `load_capabilities`), custom session management, Morning MCP discovery, and stateless approval button handlers.

**The Proposal**: Evaluate whether migrating from our custom orchestration to an off-the-shelf, standard agent SDK (e.g., **Google GenAI / Agent Development Kit (ADK)**, **LangChain / LangGraph**, or similar frameworks) would yield:
- **Faster Development**: Standardized multi-agent patterns, tool registries, and conversation memory.
- **Model Agnosticism**: Seamless multi-model routing and fallbacks across OpenAI (GPT-4o), Anthropic (Claude 3.5 Sonnet), and Google (Gemini 1.5 Pro / Flash) without rewriting low-level client adapters.
- **Community & Observability**: Standardized telemetry (LangSmith, Vertex AI Tracing, OpenTelemetry) and off-the-shelf connectors.

---

### 1.2 Pamela's Critical Reality Check (Value vs. Complexity vs. Risk)
As a Product Manager, I must challenge the assumption that moving to a generic framework is a silver bullet. While the idea of "vanilla" is alluring, the engineering reality in specialized production applications often tells a different story:

1. **The "Framework Trap" & Leaky Abstractions**:
   - Frameworks like LangChain are notorious for rapid breaking changes, excessive abstractions, dependency bloat, and opinionated black-box prompt transformations.
   - DeniDin requires **microscopic, deterministic control** over every token, especially in high-stakes legal/accounting operations:
     - Exact statutory compliance (e.g., Feature 098 allocation number rules at 5,000 NIS).
     - Strict Morning MCP server tool schemas (`create_receipt`, `get_client_details`).
     - Post-turn ledger recognition without hallucinated financial transactions.
   - Debugging rogue model behavior through 10 layers of third-party framework middleware is significantly more painful than debugging clean, local code.
2. **Sunk Cost & Proven Stability**:
   - Our team has spent immense effort building, stabilizing, and validating the **Feature 063 Backbone** and **Feature 070 Rolling Memory Window**.
   - The current engine passes over 100 sanity and billed E2E tests, handling real WhatsApp sessions reliably. A blind rip-and-replace risks massive regression for zero immediate customer value.
3. **Approval Flow & WhatsApp UX**:
   - DeniDin's interactive approval buttons (Feature 047) and WhatsApp session mechanics rely on pausing the turn, awaiting a human tap ("כן" / "לא"), and resuming execution deterministically. Most generic agent SDKs assume synchronous, terminal-style, or REST-based agent execution loops that require heavy customization for asynchronous chat apps.

**Conclusion**: This feature must NOT be approached as an immediate rewrite. Instead, it must be executed as an **isolated, rigorous Spike** evaluating candidate frameworks against a clear Go / No-Go Scorecard.

---

## 2. Candidate Frameworks for Evaluation

| Candidate | Strengths | Risks & Disadvantages |
| :--- | :--- | :--- |
| **Google ADK / GenAI SDK** | High throughput, massive context windows (1M+ tokens), native multimodal audio/vision parsing, low token pricing with Gemini 1.5 Pro/Flash. | Tightly coupled to Google Cloud / Vertex ecosystem; Morning MCP server interoperability requires custom client bridging; less community tooling for WhatsApp bot paradigms. |
| **LangGraph (LangChain)** | First-class support for cyclic multi-agent state machines; clear human-in-the-loop breakpoint primitives; vast ecosystem of integrations. | High dependency weight; steep learning curve; historically high frequency of breaking API refactors; token overhead in internal prompt wrappers. |
| **Lightweight Modern Agent SDKs (OpenAI Agents / Anthropic Tool SDK)** | Clean, minimal abstractions; very close to raw API calls; minimal runtime overhead. | Single-provider bias; does not solve multi-model portability cleanly. |

---

## 3. PM Functional Requirements (The Evaluation Spike)

- **REQ-103-01 (Isolated Benchmark Scope)**:
  The evaluation spike must NOT touch production code. Claire's engineering team will create a standalone sandbox module (`experiments/agent_sdk_spike/`) implementing a single representative DeniDin flow:
  - *Target Flow*: Conversational client identification + invoice creation proposal + Morning MCP tool execution + human approval step.
- **REQ-103-02 (MCP Interoperability)**:
  The candidate SDK must natively connect to `apps/morning-mcp-app` via the Model Context Protocol (MCP) or standard JSON-RPC without requiring changes to our existing MCP servers.
- **REQ-103-03 (Human-in-the-Loop Approval Parity)**:
  The candidate SDK must support pausing execution before any financial write tool runs, persisting the suspended state across an arbitrary delay (minutes to days), and resuming seamlessly upon receipt of a WhatsApp button tap or text confirmation ("כן").
- **REQ-103-04 (Latency & Token Benchmarking)**:
  The spike must measure:
  - Time-to-First-Token (TTFT) and total turn latency vs. current Backbone baseline.
  - Injected framework token overhead (measuring unnecessary prompt bloat).
- **REQ-103-05 (Hebrew Language & Instruction Adherence)**:
  The candidate framework must execute Hebrew conversational flows with zero prompt corruption or degradation in extraction accuracy.
- **REQ-103-06 (The Go / No-Go Decision Scorecard)**:
  Before any migration is approved, the candidate must pass the following criteria:
  1. **Test Parity**: Pass 100% of the sample billed test suite covering document creation.
  2. **Zero Framework Prompt Injection**: Framework must allow raw system instructions without forced meta-prompts.
  3. **Dependency Health**: No unpinned or volatile transitive dependencies.
  4. **Engineering ROI**: Demonstrated reduction in future maintenance cost of at least 30% compared to maintaining the Backbone.

---

## 4. User Acceptance Tests (UAT)

### UAT-1: Multi-Step Morning MCP Execution via Candidate SDK
- **Given**: A prototype agent built with the candidate SDK connected to `morning-mcp-app`.
- **When**: The user says *"תוציא חשבונית מס קבלה ללקוח ישראל ישראלי על סך 1,500 ש״ח במזומן"*.
- **Then**: 
  1. The SDK correctly invokes `get_client_details` or search tools.
  2. The SDK drafts the proposal with exact amounts, VAT breakdown, and payment methods.
  3. The SDK correctly maps MCP schemas without serialization errors.

### UAT-2: Human-in-the-Loop State Pause and Resume
- **Given**: An agent reaches a write decision (creating an official invoice).
- **When**: The SDK emits the approval prompt and pauses.
- **Then**:
  1. The agent process does not block or leak memory while awaiting user response.
  2. 24 hours later, when the user replies "כן", the SDK resumes state and executes the write tool idempotently.

### UAT-3: Latency & Cost Parity Verification
- **Given**: A standardized 5-turn conversational benchmark.
- **When**: Run side-by-side between DeniDin Backbone and the candidate SDK.
- **Then**: The candidate SDK's token overhead is within 10% of the Backbone, and latency does not exceed Backbone by more than 300ms.

---

## 5. Handoff & Next Steps for Team Lead (Claire)

1. **Phase 1 (Paper Audit & Feasibility)**: 
   Claire to conduct a 2-day technical review of Google ADK vs. LangGraph specifically focusing on **MCP support** and **async human-in-the-loop state persistence**.
2. **Phase 2 (Prototype Spike)**:
   Build the minimal sandbox prototype under `experiments/` if Phase 1 demonstrates compelling feasibility.
3. **Phase 3 (Executive Decision)**:
   Present the scorecard to Pamela and the CEO. If the framework fails the scorecard, we officially close the ticket and double down on the Backbone.
