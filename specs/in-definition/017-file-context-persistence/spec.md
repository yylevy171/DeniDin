# Feature Specification: File Context Persistence

**Feature Branch**: `feature/017-file-context-persistence`
**Created**: 2026-07-07
**Status**: Draft
**Input**: User description: "I wish to have any file that is sent in a session to persist in that session's AI context, similar to the '+' button in the OpenAI web interface."

---

**IMPORTANT**: This spec complies with:
- **CONSTITUTION.md** (§I-III, §V): Coding standards, UTC timestamps, version control workflow, NO environment variables, Integration tests as E2E, feature flags for new behavior
- **METHODOLOGY.md** (§I, II, VIII, IX, X): Specification-first development, User stories mandatory, Terminology Glossary, Technology Choices, Requirement IDs

**Required Files**:
- ✅ **`user-stories.md`** — Given-When-Then format, 6 stories (US-1..US-6), router/integration requirements explicit
- ✅ **`spec.md`** (this file)
- ⬜ **`plan.md`** — produced by `speckit.plan` (not yet run)
- ⬜ **`tasks.md`** — produced by `speckit.tasks` (not yet run)

---

## Terminology Glossary

- **Session**: An existing conversation-tracking entity (`Session` dataclass in `session_manager.py`), keyed by `session_id`, scoped to one `whatsapp_chat`, backed by `data/sessions/<session_id>/`.
- **`file_id`**: An OpenAI Files API identifier returned after uploading file bytes; can be referenced in later API calls without resending the bytes.
- **Responses API**: OpenAI's `client.responses.create` endpoint. This feature replaces the current `client.chat.completions.create` integration with this endpoint for all AI conversations.
- **`previous_response_id` chaining**: A Responses API mechanism where each call passes the prior call's response id, letting OpenAI retain conversation context server-side instead of the client resending full history.
- **Active session documents**: The set of `file_id`s (for images/PDFs) and/or previously-injected extracted text (for DOCX) currently associated with a session, available to the AI on any subsequent turn in that session.
- **Native PDF `input_file`**: A Responses API content type that accepts a PDF `file_id` directly, letting the model read the PDF's text and layout without any client-side page-to-image conversion.
- **DEPRECATED (as of this feature): PyMuPDF-per-page pipeline** — the current `PDFExtractor` behavior of rendering each PDF page to a PNG and vision-extracting per page; superseded by native PDF upload when the feature flag is enabled, but retained unchanged for the flag-disabled path.

---

## Clarifications

### Session 2026-07-07

- Q: How should images/PDFs persist across conversation turns? → A: True OpenAI file-reference persistence — upload once via the Files API, reference by `file_id` in later turns via the Responses API's `input_image`/`input_file` content types. No resending of raw bytes each turn.
- Q: How should DOCX files be handled, given OpenAI has no native file-reference mechanism for DOCX? → A: Keep today's approach — extract text via `python-docx` and inject it as text into the session's conversation context. This is not full "+"-button parity for DOCX, but is the best available approximation given the API constraint.
- Q: Should only file-bearing conversations move to the Responses API, or should all AI conversations migrate? → A: All AI conversations migrate to the Responses API with `previous_response_id` chaining, replacing the Chat Completions + manually-replayed-history mechanism entirely, rather than maintaining two parallel code paths.
- Q: When should files uploaded to OpenAI be deleted? → A: Tied to the existing 24-hour session expiration/cleanup process — when a session is archived, its uploaded OpenAI files are deleted, guarded so a delete failure never blocks the rest of cleanup.
- Q: Should this be gated behind a feature flag? → A: Yes — `enable_responses_api_file_context` in `config.feature_flags`, default `false`. When disabled, behavior must be identical to today's, per CONSTITUTION §I.
- Q: Should the existing PyMuPDF-per-page-to-image PDF pipeline be replaced? → A: Yes, when the flag is enabled, PDFs are uploaded directly (native PDF understanding) instead of being converted to per-page images. The existing PyMuPDF pipeline remains unchanged for the flag-disabled path.
- Q: Does the choice of the Responses API affect the planned Morning/Green-Invoice MCP integration (`specs/in-definition/005-mcp-morning-green-receipt/`)? → A: That spec has not yet committed to a specific AI-calling convention (it is unbuilt). The Responses API has a native `mcp` tool type for calling remote MCP servers, which Chat Completions has no equivalent for — this is a documented forward-compatibility rationale for the technology choice below, not a hard dependency of this feature.

---

## User Scenarios Reference

Complete Given-When-Then acceptance criteria live in **`user-stories.md`**. Summary:

| Story | Priority | Summary |
|-------|----------|---------|
| US-1 | P1 | Follow-up question about a previously sent image |
| US-2 | P1 | Follow-up question about a previously sent PDF |
| US-3 | P1 | Follow-up question about a previously sent DOCX |
| US-4 | P1 | Feature flag disabled preserves current behavior |
| US-5 | P2 | Session expiry cleans up uploaded OpenAI files |
| US-6 | P2 | Multiple files accumulate in one session |

### Edge Cases

- What happens when a file exceeds OpenAI's Files API size/token limits? → Existing friendly user-facing error path is reused; technical detail logged, not surfaced to the user.
- What happens when an unsupported file format reaches an extractor? → Unchanged from today — extractors already validate and report unsupported formats.
- What happens when the OpenAI file-delete call fails during session cleanup (already deleted, network error, quota)? → Logged at WARNING/ERROR; cleanup (archival, long-term-memory transfer, index removal, `transferred_to_longterm` flag) proceeds unaffected (see US-5).
- What happens when local session-history pruning (`_prune_until_under_limit`) would remove a message whose file is still part of the active conversation chain? → File references are governed by session-level lifecycle (created at upload, deleted at session expiry), independent of local per-message pruning; pruning a local message row must never invalidate a still-active `file_id` reference before the session itself expires.
- What happens when OpenAI's Files/Responses API rate-limits or times out during upload? → Same retry policy as existing OpenAI calls (retry once on 5xx/timeout, no retry on 4xx).
- What happens to sessions created before this feature was enabled? → They have no `openai_file_ids`/`last_response_id` recorded; the first turn after upgrade simply starts a fresh Responses API conversation state, with no prior files to reference.

---

## Requirements

### Functional Requirements

**Context persistence**

- **REQ-CONTEXT-001**: When `enable_responses_api_file_context` is enabled, the system MUST persist an image or PDF sent during a session by uploading it once to OpenAI's Files API and retaining its `file_id` for the lifetime of that session.
- **REQ-CONTEXT-002**: When `enable_responses_api_file_context` is enabled, the system MUST persist a DOCX file sent during a session by retaining its extracted text as part of that session's conversation context (no file upload, since no native OpenAI file-reference mechanism exists for DOCX).
- **REQ-CONTEXT-003**: When `enable_responses_api_file_context` is enabled, the system MUST answer any subsequent question in the same session using previously persisted files/text, without requiring the user to resend them.
- **REQ-CONTEXT-004**: When `enable_responses_api_file_context` is enabled, the system MUST use OpenAI's Responses API with `previous_response_id` chaining for all AI conversation turns in a session (not only turns involving files), replacing the current Chat Completions + manually-replayed-history mechanism.
- **REQ-CONTEXT-005**: The system MUST support multiple files accumulating within a single session, with each remaining independently referenceable until the session itself expires.
- **REQ-CONTEXT-006**: When `enable_responses_api_file_context` is enabled, the system MUST determine token usage for file-derived context from the API's own reported usage rather than pre-estimating it from local text, since file content is not locally re-counted.

**File lifecycle / cleanup**

- **REQ-CLEANUP-001**: When a session expires and is archived by the existing cleanup process, the system MUST delete every OpenAI file uploaded during that session.
- **REQ-CLEANUP-002**: A failure to delete an OpenAI file during cleanup MUST be logged and MUST NOT block any other step of session cleanup (archival, long-term-memory transfer, index removal, marking transferred).

**Configuration / rollout**

- **REQ-CONFIG-001**: The feature MUST be controlled by a new configuration flag `enable_responses_api_file_context` under `config.feature_flags`, defaulting to `false`.

**Backward compatibility**

- **REQ-COMPAT-001**: When `enable_responses_api_file_context` is disabled (default), the system MUST behave exactly as it does today: files are analyzed once and their content is not retained for future turns, and the AI conversation flow is unchanged.

### Key Entities

- **Session**: Represents one ongoing WhatsApp conversation. Gains two new attributes under this feature: the set of files currently persisted in its context (as OpenAI file references), and a pointer to the most recent AI response for conversation chaining.
- **Active session document**: Represents one file (image/PDF) or one block of extracted text (DOCX) currently available to the AI within a session's context.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: A user who sends an image, PDF, or DOCX and then asks a relevant follow-up question in the same session receives a contextually correct answer without resending the file, in manual and automated acceptance testing.
- **SC-002**: No file uploaded to OpenAI during a session remains on OpenAI's servers after that session has expired and completed its cleanup cycle, except where a logged deletion failure prevented it.
- **SC-003**: With the feature flag disabled, all existing behavior and the full existing automated test suite pass with zero observable differences from before this feature existed.
- **SC-004**: A session can accumulate multiple files (of mixed supported types) and answer questions that draw on more than one of them.
