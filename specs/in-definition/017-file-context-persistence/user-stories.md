# User Stories: File Context Persistence

**Feature**: 017-file-context-persistence
**Feature Branch**: `feature/017-file-context-persistence`
**Created**: 2026-07-07
**Status**: Draft

All stories require complete Given-When-Then flows tracing external entry point → system processing → response, with explicit router/dispatcher requirements, per `.github/METHODOLOGY.md` §I.

---

## User Story 1 - Follow-up question about a previously sent image (Priority: P1)

A WhatsApp user sends an image, then later in the same session asks a text question about it (e.g., "what color is the shirt in that photo?"), without resending the image.

**Why this priority**: This is the core value of the feature — the exact "+ button" behavior being requested. Without this, the feature delivers nothing.

**Independent Test**: With `enable_responses_api_file_context=true`, send an `imageMessage`, then send a plain `textMessage` follow-up in the same session. Verify the response correctly reflects image content, and verify (via a local HTTP test double standing in for OpenAI's Files/Responses endpoints — no `unittest.mock`/in-process mocks per CONSTITUTION.md's zero-mocking policy) that the image was uploaded once and its `file_id` was referenced, not re-uploaded, on the follow-up call.

**Acceptance Scenarios**:

1. **Given** an active session and `enable_responses_api_file_context=true`, **When** the user sends an `imageMessage`, **Then** the image is uploaded to OpenAI's Files API, the returned `file_id` is stored on the session, and the bot replies with its existing image-analysis summary.
2. **Given** step 1 has completed, **When** the user sends a text follow-up question about the image in the same session, **Then** the AI response is generated via the Responses API referencing the stored `file_id` (chained via `previous_response_id`), and the answer is contextually correct without the image being resent.
3. **Given** the same scenario, **When** the follow-up is sent, **Then** the session's `last_response_id` is updated to the new response's id, ready for the next turn's chaining.

**Router/Dispatcher Requirement**: `@bot.router.message(type_message='imageMessage')` → `WhatsAppHandler.handle_media_message()` → `MediaHandler.process_media_message()` → `ImageExtractor` (uploads via Files API) → `handle_media_message()` MUST additionally persist the resulting `file_id` into `SessionManager`/`Session` (today it only calls `notification.answer()` — this gap is what US-1 closes). The subsequent `@bot.router.message(type_message='textMessage')` handler → `AIHandler.get_response()` MUST read `session.openai_file_ids`/`last_response_id` when building the Responses API request.

---

## User Story 2 - Follow-up question about a previously sent PDF (Priority: P1)

A WhatsApp user sends a PDF document, then asks a follow-up question about its contents in the same session.

**Why this priority**: PDFs are a primary real-world use case (invoices, contracts) already supported for one-shot analysis; making them persist in context is equally core to the feature's value.

**Independent Test**: Send a `documentMessage` with PDF mime type, then a text follow-up. Verify (via local HTTP test double, no in-process mocks) the PDF was uploaded once as a native file and referenced by `file_id` in the follow-up call, and the answer is correct.

**Acceptance Scenarios**:

1. **Given** an active session and the flag enabled, **When** the user sends a PDF `documentMessage`, **Then** the PDF is uploaded directly to OpenAI's Files API (native PDF understanding, not the legacy PyMuPDF-per-page-to-image conversion), and its `file_id` is stored on the session.
2. **Given** step 1, **When** the user asks a follow-up question referencing the PDF's content, **Then** the Responses API call references the PDF's `file_id` and the answer is contextually correct.

**Router/Dispatcher Requirement**: `@bot.router.message(type_message='documentMessage')` (PDF mime type) → `WhatsAppHandler.handle_media_message()` → `MediaHandler.process_media_message()` → `PDFExtractor` (now uploads the PDF file directly rather than rendering pages to images) → same session-persistence requirement as US-1.

---

## User Story 3 - Follow-up question about a previously sent DOCX (Priority: P1)

A WhatsApp user sends a DOCX document, then asks a follow-up question about its contents in the same session.

**Why this priority**: DOCX is a supported file type today; excluding it from persistence would leave an inconsistent user experience across file types, even though the underlying mechanism differs.

**Independent Test**: Send a `documentMessage` with DOCX mime type, then a text follow-up. Verify the extracted text was stored in the session's conversation context (not as an OpenAI file reference — no native DOCX file-reference support exists) and the follow-up answer is correct.

**Acceptance Scenarios**:

1. **Given** an active session and the flag enabled, **When** the user sends a DOCX `documentMessage`, **Then** `DOCXExtractor` extracts the text via python-docx as it does today, and that extracted text is persisted into the session's conversation context (injected as a turn, not uploaded as an OpenAI file).
2. **Given** step 1, **When** the user asks a follow-up question about the document, **Then** the answer is generated correctly using the persisted extracted text, chained via `previous_response_id` alongside the rest of the conversation.

**Router/Dispatcher Requirement**: `@bot.router.message(type_message='documentMessage')` (DOCX mime type) → `WhatsAppHandler.handle_media_message()` → `MediaHandler.process_media_message()` → `DOCXExtractor` → same session-persistence requirement as US-1, but storing text rather than a `file_id`.

---

## User Story 4 - Feature flag disabled preserves current behavior (Priority: P1)

An operator has not enabled the new feature flag; all existing behavior (one-shot file summaries, no cross-turn file context, Chat Completions API) must remain byte-for-byte identical.

**Why this priority**: Required for safe rollout per CONSTITUTION §I feature-flag rules; regressions here would break production for all users immediately, since this feature touches the core AI request path.

**Independent Test**: Run the full existing test suite (`test_session_manager.py`, `test_background_cleanup.py`, all extractor tests, `test_ai_handler.py`) with `enable_responses_api_file_context` absent/false and confirm zero behavioral or assertion differences from pre-feature baseline.

**Acceptance Scenarios**:

1. **Given** `config.feature_flags.enable_responses_api_file_context` is `false` or absent, **When** a user sends an image/PDF/DOCX and then a follow-up question, **Then** the bot behaves exactly as it does today: `client.chat.completions.create` is used, files are summarized once and discarded, no `file_id` is stored, no follow-up has any awareness of the earlier file.
2. **Given** the flag is disabled, **When** any text-only conversation occurs, **Then** `SessionManager.get_conversation_history_for_session` continues to rebuild flat history exactly as today — no `previous_response_id` chaining occurs.

**Router/Dispatcher Requirement**: All existing routers (`imageMessage`, `documentMessage`, `textMessage`) remain unchanged; the flag only branches internal behavior inside `AIHandler`/extractors, never the routing/dispatch layer itself.

---

## User Story 5 - Session expiry cleans up uploaded OpenAI files (Priority: P2)

When a session expires (24h inactivity) and is archived by the background cleanup thread, any files it uploaded to OpenAI are deleted.

**Why this priority**: Prevents unbounded OpenAI-side storage growth and cost; not part of the interactive user-facing flow, so lower priority than US-1/2/3/4, but required before this feature can be considered production-safe.

**Independent Test**: Create a session with 2+ entries in `openai_file_ids`, trigger `cleanup_service._process_session_cleanup` (or the startup/hourly cleanup entry points), and verify (via local HTTP test double for the OpenAI Files delete endpoint) that a delete call is made for every id, and that a simulated delete failure is logged but does not block archival, ChromaDB transfer, index removal, or the `transferred_to_longterm` flag update.

**Acceptance Scenarios**:

1. **Given** a session with one or more `openai_file_ids` has expired, **When** the cleanup thread processes it, **Then** after the existing archive (Step 1) and long-term-memory transfer (Step 2) steps, the system calls the OpenAI Files delete operation for each stored `file_id`.
2. **Given** an OpenAI file delete call fails (e.g., already deleted, network error), **When** cleanup runs, **Then** the failure is logged at WARNING/ERROR level and the remaining cleanup steps (index removal, `transferred_to_longterm=True`) complete normally.

**Router/Dispatcher Requirement**: Not applicable — this story is triggered by the existing hourly `SessionCleanupThread` / `run_startup_cleanup` background processes, not by any WhatsApp webhook or router.

---

## User Story 6 - Multiple files accumulate in one session (Priority: P2)

A user sends several files (e.g., an image, then a PDF, then another image) within the same session, and a later question can reference any/all of them.

**Why this priority**: Validates the persistence mechanism scales beyond a single file per session, matching real usage patterns (e.g., someone sending multiple receipts before asking "what's my total spend?").

**Independent Test**: Send three files of mixed types in one session, then ask a question spanning all three; verify all three `file_id`s (for image/PDF) plus any persisted DOCX text remain part of the session's context, and `Session.openai_file_ids` contains all applicable entries.

**Acceptance Scenarios**:

1. **Given** a session already has 2 files persisted (e.g., one image `file_id`, one PDF `file_id`), **When** the user sends a third file, **Then** all three remain referenceable and `Session.openai_file_ids` reflects all accumulated ids (no overwriting of earlier entries).
2. **Given** this accumulated session, **When** the user asks a question spanning multiple files, **Then** the response correctly draws on all persisted context.
3. **Given** this session eventually expires, **When** cleanup runs, **Then** US-5's cleanup deletes all accumulated `file_id`s, not just the most recently added one.

**Router/Dispatcher Requirement**: Same routers as US-1/US-2/US-3, exercised repeatedly within a single session; no new routing behavior, but validates that repeated invocations of the persistence logic are additive, not destructive.
