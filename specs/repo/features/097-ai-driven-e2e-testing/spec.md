# Feature 097: AI-Driven E2E Testing Framework

**Feature Branch**: `feature/097-ai-driven-e2e-testing`
**Status**: Backlog

## 1. Business & Architectural Goals

Our current E2E testing methodology (`tests/billed/`) relies on hardcoded string prompts and strict regex/string assertions. Because DeniDin's core intelligence (OpenAI) is non-deterministic by nature, our hardcoded tests frequently stall or break when the LLM slightly alters its conversational phrasing or adds a clarification turn that the test framework didn't expect.

**The Goal**: Transition from rigid, hardcoded string-matching tests to an **AI-Driven Evaluator Testing Framework**. In this novel approach, a secondary "Evaluator LLM" plays the role of the user (generating realistic, varied inputs) and evaluates the final system state (verifying that the correct tool was called or the correct data was extracted) rather than relying on exact string matches.

**Value**: Drastically reduces test flakiness, eliminates the need to constantly update E2E helpers for minor prompt changes, and simulates true, chaotic user interactions in the CI/CD pipeline.

## 2. PM Requirements (Functional)

- **REQ-097-01 (Evaluator Agent)**: Implement an independent "Test Evaluator LLM" (using an affordable model like GPT-4o-mini) that reads the test intent and dynamically generates the conversational input to push the main DeniDin agent toward that goal.
- **REQ-097-02 (Semantic Assertions)**: Replace standard `assert "X" in response` checks with semantic evaluations. The Evaluator LLM must be able to grade the system's output (e.g., `assert evaluator.check(response, "Did the system successfully ask for the missing VAT number?")`).
- **REQ-097-03 (Fixture Abstraction)**: The framework must securely seed the database/ledger state (fixtures) before the Evaluator begins the chat, and then query the final database state to ensure the correct records (Invoices, Clients) were created, rather than relying solely on the chat text.
- **REQ-097-04 (Open Source Assessment)**: Before building from scratch, the Dev team must evaluate existing AI-testing frameworks (e.g., `promptfoo`, `ragas`, `Giskard`, or `pytest-llm` concepts) to see if they can be adapted for stateful, multi-turn conversational agents.

## 3. User Acceptance Tests (UAT)

- **UAT-1 (Handling Unpredictable AI Clarifications)**:
  - *Given* an AI-driven test script intending to create a receipt,
  - *When* the main DeniDin agent randomly asks a clarifying question (e.g., "What was the date?") instead of immediately succeeding,
  - *Then* the Evaluator Agent dynamically answers the question ("It was yesterday") and successfully drives the test to completion without a hardcoded crash.
- **UAT-2 (Semantic Validation)**:
  - *Given* the Evaluator Agent concludes the conversation,
  - *When* checking the final state,
  - *Then* the test queries the mock ledger DB to ensure the `Receipt` object was created perfectly, passing the test regardless of the exact Hebrew wording the main agent used to say goodbye.

## 4. Complexity & Open Questions

- **The "Trust" Leap of Faith**: If an AI evaluates an AI, how do we guarantee the Evaluator doesn't hallucinate a passing grade? We must enforce that the *final* test assertions still validate hard data (e.g., querying the DB for the exact JSON values) rather than just asking the Evaluator if it "thinks" the task succeeded.
- **Cost**: Running an LLM to test an LLM effectively doubles the token cost of our CI/CD pipeline. Is this acceptable in exchange for test stability?
