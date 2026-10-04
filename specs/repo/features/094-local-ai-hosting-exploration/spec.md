# Feature 094: Local AI Model Hosting Exploration

**Feature Branch**: `feature/094-local-ai-hosting-exploration`
**Status**: Backlog

## 1. Business & Architectural Goals

The current DeniDin app relies entirely on the OpenAI API for its core intelligence. While powerful, this introduces several business risks:
- **Cost**: Per-token billing scales linearly with usage, and with complex features like the Dynamic Capability Backbone (Feature 063) and massive context windows, this overhead is substantial.
- **Privacy & Security**: Financial and accounting data (invoices, client names, ledgers) are currently transmitted to a third party.
- **Reliability & Rate Limits**: We are subject to OpenAI's uptime, latency spikes, and API rate limits.

**The Goal**: Explore, benchmark, and potentially transition to a self-hosted, local Open Source LLM (e.g., Llama 3, Mistral) that can run within our infrastructure.

## 2. PM Requirements (Functional)

- **REQ-094-01 (Model Selection)**: Identify 2-3 leading open-weight models capable of handling complex tool calling (function calling), Hebrew language understanding, and following strict system prompt instructions.
- **REQ-094-02 (Benchmarking Suite)**: Establish a baseline using our existing billed E2E test suite. The local model must be able to pass core UATs (e.g., extracting invoice details, handling morning documents) with at least 95% of the accuracy of the current OpenAI model.
- **REQ-094-03 (Infrastructure Assessment)**: Calculate the hardware requirements (GPU VRAM, compute) necessary to host the model locally with acceptable latency (time-to-first-token < 2s).
- **REQ-094-04 (Architecture Abstraction)**: Ensure the backend LLM client is abstracted so we can easily toggle between OpenAI and the local model via environment variables (e.g., using `litellm` or a standard OpenAI-compatible API wrapper like `vLLM` or `Ollama`).

## 3. User Acceptance Tests (UAT)

Since this is an exploration and infrastructure task, the UATs focus on system capabilities:

- **UAT-1 (Hebrew Comprehension)**:
  - *Given* a local model is active,
  - *When* the user inputs a complex Hebrew query with mixed dates and slang,
  - *Then* the model correctly extracts the intent and arguments without hallucination.
- **UAT-2 (Tool Calling Accuracy)**:
  - *Given* a local model is active,
  - *When* a multi-step ledger query is required,
  - *Then* the model successfully emits the correct JSON schema for the tool call in exactly the format the backend expects.
- **UAT-3 (Latency)**:
  - *Given* a standard production load,
  - *When* a user sends a message,
  - *Then* the model begins streaming its response within 2 seconds.

## 4. Open Questions for CEO / Tech Lead
- Do we want to host this in the cloud (e.g., AWS/GCP with dedicated GPUs) or literally on local on-premise hardware?
- Are we willing to sacrifice a slight percentage of reasoning capability for absolute data privacy and fixed costs?
