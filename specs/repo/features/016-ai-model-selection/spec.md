# Feature Spec: Per-Task AI Model Selection

**Feature Branch**: `feature/016-ai-model-selection`
**Created**: 2026-07-07
**Status**: Done - Merged to master (PR #88, 2026-07-07)
**Input**: User description: "separate the ai model into 2 or 3 separate models based on the action they need to perform: default text model, image/PDF/docx extraction model, and a text-embedding model that captures Hebrew semantics well for session search. All models should be relatively cheap but good quality, and driven entirely by config."

---

**IMPORTANT**: This spec complies with:
- **CONSTITUTION.md** (§I, §IV, §XIII, §XV): Config-driven behavior (no env vars), code quality standards, data validation at config load, JSON format standards
- **METHODOLOGY.md** (§I, §II, §VIII, §IX, §X): Specification-first development, user stories mandatory, terminology glossary, technology-choice documentation, requirement IDs

## Terminology Glossary

- **`ai_model`**: The default text-completion model, used for plain-text WhatsApp conversations and DOCX text analysis. Already exists in `AppConfiguration`.
- **`ai_vision_model`**: The multimodal model used to extract/analyze content from images and PDF pages (PDF pages are rendered to images and delegated to the same vision path). Already exists in `AppConfiguration`.
- **`ai_embedding_model`** (NEW top-level field): The embedding model used by `MemoryManager` for ChromaDB long-term memory storage and semantic recall. Currently exists only as a nested field `memory.longterm.embedding_model` — this spec promotes it to a top-level config field for consistency and discoverability alongside `ai_model`/`ai_vision_model`.
- **REMOVED: `memory.longterm.embedding_model`** — superseded by top-level `ai_embedding_model`. During implementation (2026-07-07), the "fallback" design was simplified: since `ai_embedding_model` always has a dataclass default, "top-level absent" is unreachable, so the legacy nested field was removed entirely from all config files and from `AppConfiguration.from_file()`'s defaults, rather than kept as dead/misleading fallback code (see Clarifications).
- **Model role**: One of three purposes a configured model string serves — `text`, `vision`, or `embedding`. Each role is independently configurable and independently swappable.

## Clarifications

### Session 2026-07-07

- Q: Who should be able to choose/switch the AI model, and how? → A: This is not a runtime/user-facing chooser. It's a config-level decision — pick the best model *per task type* (text/vision/embedding) and wire the code to already use the right one per flow. (Discovered during investigation: `ai_model` and `ai_vision_model` already exist and are already wired correctly per flow; `embedding_model` already exists but is buried in `memory.longterm`.)
- Q: Scope — text model only, or also vision? → A: All three roles: text, vision, embedding.
- Q: Should the choice persist per-user/session/global? → A: N/A — not applicable, this is a static config value, not a per-user runtime preference.
- Q: Vision model — keep `gpt-4o` or switch default to `gpt-4o-mini`? → A: Switch to `gpt-4o-mini` (~17x cheaper: $0.15/$0.60 per 1M tokens vs. gpt-4o's $2.50/$10; same multimodal family already used for text, so no new integration risk).
- Q: Should `embedding_model` be promoted to a top-level config field or stay nested under `memory.longterm`? → A: Promote to top-level `ai_embedding_model`, alongside `ai_model`/`ai_vision_model`, for consistency and discoverability. Nested field becomes a deprecated fallback.
- Q: Should the vision-model default change ship behind a feature flag? → A: No — this is a config-value tuning change on an existing code path (not new behavior), so it doesn't meet the Constitution's feature-flag bar (§I: flags gate new behavior/code paths, not model-string tuning).
- Q: What are the recommended concrete model values? → A (research-backed, see Technology Choice sections below):
  - `ai_model` (text): keep `gpt-4o-mini` ($0.15/$0.60 per 1M) — cheapest capable option, no change.
  - `ai_vision_model` (vision): change default from `gpt-4o` to `gpt-4o-mini` ($0.15/$0.60 per 1M) — same family, ~17x cheaper.
  - `ai_embedding_model` (embedding): change default from `text-embedding-3-small` ($0.02/1M) to `text-embedding-3-large` ($0.13/1M) — materially better multilingual/Hebrew semantic capture (MIRACL multilingual benchmark: 31.4% → 54.9% over ada-002), and the absolute cost delta is trivial at this project's scale.
- Q: How should the embedding-model dimensionality migration risk be handled? → A: Investigated production data directly — `data/memory/chroma.sqlite3` currently has 3 collections (`memory_123`, `memory_972522968679`, `memory_test`) but **0 stored embeddings** (empty/dev artifacts). Since there is no real data to strand, ship the `text-embedding-3-large` default directly with no migration tooling. Note for future maintainers: this was safe *because* the store was empty at ship time — if embeddings accumulate before this change merges, re-verify before merging.
- Q: Should a startup validation warning (detect embedding-model mismatch against an existing collection) be built? → A: No, out of scope for this feature (no current data to protect, adds scope). Instead: add an `embedding_model` provenance field to the long-term memory data model, populated on every write to ChromaDB, so any *future* model change has the information needed to detect/handle mismatches without needing to build the detection logic now.

### Session 2026-07-07 (implementation-time findings)

- Q: Given `ai_embedding_model` always has a dataclass default, is the "fall back to legacy nested field when top-level absent" design (original REQ-CONFIG-004) actually reachable? → A: No — confirmed during implementation that a dataclass default always populates the field, so "top-level absent" never occurs in practice. Simplified: `ai_embedding_model` always wins; the legacy `memory.longterm.embedding_model` field was removed entirely (from `config.py`, `config.json`, `config.example.json`, `config.test.json`, and all fixtures referencing it), rather than kept as unreachable/misleading fallback code. Verified against real production `config.json`: its legacy value already matched the old default (no deliberate customization to lose).
- Q: While implementing, was there any other place `ai_vision_model`/`ai_embedding_model` needed to flow through that the original plan missed? → A: Yes — found and fixed a **pre-existing bug**: `denidin.py`'s `__main__` block (and `test_media_webhook_routing.py`'s config fixture) manually rebuild a `config_dict` for `initialize_app()`, and that manual key list never included `ai_vision_model` — meaning any custom vision model in production `config.json` was already being silently discarded before this feature (masked because the discarded value happened to match the default). Fixed by adding `ai_vision_model` and `ai_embedding_model` to that list in both places.
- Q: After implementing, `tests/integration/test_session_transfer.py::test_session_transfer_and_recall_after_expiration` failed on its pre-existing PHASE 7 assertion ("system remembers Mike") after adding the new PHASE 6.5 provenance assertion (which itself passed). Root cause? → A: **Confirmed via direct investigation** (one trivial real embedding API call against the actual stored ChromaDB data from the failed run, not a guess): the real similarity score between the query "What's my name?" and the stored "Mike" memory was **0.1858** under `text-embedding-3-large` — just below the `min_similarity: 0.2` threshold (test config) / `0.7` (production), both of which were tuned against `text-embedding-3-small`'s different cosine-similarity distribution. `text-embedding-3-large` produces materially lower absolute similarity scores for the same semantic relationship, so a threshold that was fine for the old model silently filters out clearly-relevant matches under the new one. This is a second, distinct migration risk beyond the dimensionality one already documented in Edge Cases — **similarity thresholds are also model-specific, not just vector dimensionality**.
  - Resolution: `min_similarity` lowered from `0.7` → `0.15` in `config.json`, `config.example.json`, `config.test.json`, and the test fixture's override (was `0.2`, now `0.15`, safely below the confirmed real-positive score of `0.1858`). This is a provisional, single-data-point calibration — flagged as needing further real-world validation as more genuine recall cases accumulate (see Open Questions).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Text conversations use the configured default text model (Priority: P1)

A WhatsApp user sends a plain-text message. The system MUST use `config.ai_model` end-to-end for the OpenAI completion call, with no hardcoded model string anywhere in the text path.

**Why this priority**: This is the primary, highest-volume code path (`AIHandler`) — it must never silently diverge from config.

**Independent Test**: Set `ai_model` to a distinct test value in `config.test.json`, send a text webhook through `bot.router`, and assert (via a real API call in an `@pytest.mark.expensive` test, or via request-payload inspection in a non-expensive test using a local HTTP fixture standing in for the OpenAI endpoint) that the outbound request's `model` field equals the configured value.

**Acceptance Scenarios**:

1. **Given** `config.ai_model = "gpt-4o-mini"`, **When** a text message webhook arrives and is routed through `@bot.router.message(type_message='textMessage')` → `WhatsAppHandler` → `AIHandler`, **Then** the OpenAI chat completion request uses `model="gpt-4o-mini"`.
2. **Given** `config.ai_model` is changed to a different valid model string, **When** the app is restarted with the new config, **Then** all subsequent text completions use the new model with no code changes required.

---

### User Story 2 - Image/PDF/DOCX extraction uses the configured vision model (Priority: P1)

A user sends an image, PDF, or Word document. The system MUST use `config.ai_vision_model` for the vision-capable extraction call (image analysis, and PDF-pages-as-images via the same path). DOCX text-only analysis continues to use `config.ai_model` (it has no image content).

**Why this priority**: Media extraction is the second major cost/quality-sensitive path; the default is changing (`gpt-4o` → `gpt-4o-mini`) as part of this feature, so correct wiring must be verified, not assumed.

**Independent Test**: Send an imageMessage webhook through `bot.router`, verify (via request-payload inspection against a local fixture, or an approved `@pytest.mark.expensive` real-API test) that `ImageExtractor`/`PDFExtractor` calls use `model=config.ai_vision_model`.

**Acceptance Scenarios**:

1. **Given** `config.ai_vision_model = "gpt-4o-mini"`, **When** an imageMessage webhook is routed to `WhatsAppHandler.handle_media_message()` → `MediaHandler` → `ImageExtractor`, **Then** the vision API call uses `model="gpt-4o-mini"`.
2. **Given** a PDF document webhook, **When** `PDFExtractor` renders pages to images and delegates to the image-analysis path, **Then** each page's analysis call uses `config.ai_vision_model`, not `config.ai_model`.
3. **Given** a DOCX document webhook, **When** `DOCXExtractor` performs AI text analysis, **Then** the call uses `config.ai_model` (text model), confirming vision/text separation is preserved for non-image formats.

---

### User Story 3 - Long-term memory embeddings use the configured, promoted embedding model (Priority: P2)

When a session expires and transfers to long-term memory (or when semantic recall runs), `MemoryManager` MUST use the model configured at the new top-level `config.ai_embedding_model` field, falling back to the legacy nested `config.memory.longterm.embedding_model` only if the top-level field is absent (backward compatibility for configs not yet migrated).

**Why this priority**: Lower traffic than text/vision paths, but directly affects semantic search quality (including Hebrew-language recall), and requires a config-shape migration (nested → top-level) that must not break existing deployments mid-flight.

**Independent Test**: Component-integration test constructing `AIHandler`/`MemoryManager` directly from a test config with `ai_embedding_model` set, verifying the ChromaDB embedding call in `memory_manager.py:424` uses the configured model string. A second test verifies the fallback: omit `ai_embedding_model`, set only the legacy nested field, and confirm it's still honored.

**Acceptance Scenarios**:

1. **Given** `config.ai_embedding_model = "text-embedding-3-large"`, **When** a session is transferred to long-term memory, **Then** `MemoryManager`'s embedding call uses `model="text-embedding-3-large"`.
2. **Given** a config with no top-level `ai_embedding_model` but a legacy `memory.longterm.embedding_model` value set, **When** `AIHandler` constructs `MemoryManager`, **Then** the legacy value is used (no crash, no silent default override).
3. **Given** neither field is set, **When** config loads, **Then** the system defaults to `text-embedding-3-large` (the new recommended default, not the old `text-embedding-3-small`).

---

### Edge Cases

- What happens if `ai_model`, `ai_vision_model`, or `ai_embedding_model` is set to an unknown/invalid model string? → OpenAI API returns a 4xx error; per Constitution §XI, this is NOT retried, and the existing friendly-error path (`"Sorry, I'm having trouble connecting to my AI service..."`) surfaces to the user, with the technical 4xx logged at ERROR level including the invalid model string.
- What happens to existing ChromaDB collections embedded with `text-embedding-3-small` if the config is switched to `text-embedding-3-large`? → Embedding vectors from different models are NOT interchangeable (different dimensionality: 1536 vs 3072). **Resolved**: verified directly against the production `data/memory/chroma.sqlite3` — 3 collections exist but contain 0 stored embeddings (dev/test artifacts only), so there is nothing to strand. No migration tooling is needed for this feature. This is a point-in-time judgment call, not a general guarantee — see REQ-DATA-001 for the forward-looking safeguard (provenance field) that makes any *future* model change safely detectable.
- What happens for `config.example.json` and `config.test.json`? → Both MUST be updated to include the new fields with the recommended defaults, per Constitution §I ("Always maintain `config/config.example.json` with safe placeholder values").
- What happens to `min_similarity` recall thresholds when the embedding model changes? → **Confirmed regression, resolved during implementation** (2026-07-07): thresholds tuned for `text-embedding-3-small` (0.7 prod, 0.2 test) do not carry over to `text-embedding-3-large`, which produces materially lower absolute similarity scores for the same semantic relationship (measured real score for a genuinely relevant match: 0.1858). Thresholds lowered to 0.15 across all config files as a provisional recalibration — see Clarifications (implementation-time findings) and Open Questions.

## Requirements *(mandatory)*

### Functional Requirements

- **REQ-CONFIG-001**: `AppConfiguration` MUST gain a new top-level field `ai_embedding_model: str = 'text-embedding-3-large'`, following the same pattern as existing `ai_model`/`ai_vision_model` fields (dataclass field + `from_file()` default + `.example.json`/`.test.json` entries).
- **REQ-CONFIG-002**: `AppConfiguration.ai_vision_model` default MUST change from `'gpt-4o'` to `'gpt-4o-mini'`.
- **REQ-CONFIG-003**: `AppConfiguration.ai_model` default remains `'gpt-4o-mini'` (no change — already optimal for cost/quality).
- **REQ-CONFIG-004** *(superseded during implementation)*: `AIHandler`'s construction of `MemoryManager` uses `config.ai_embedding_model` directly. The originally-planned legacy-nested-field fallback was found to be unreachable (dataclass defaults always populate the top-level field) and was removed rather than kept as dead code — see Clarifications (implementation-time findings).
- **REQ-CONFIG-005** *(superseded during implementation)*: `memory.longterm.embedding_model` was removed entirely (from `config.py`'s nested defaults and from all three config JSON files), not merely marked deprecated, once REQ-CONFIG-004's fallback was found to be unreachable.
- **REQ-VALIDATE-001**: `AppConfiguration.validate()` MUST reject empty/whitespace-only strings for `ai_model`, `ai_vision_model`, and `ai_embedding_model` (mirroring the existing pattern for `data_root`).
- **REQ-DOC-001**: `config/config.example.json` and `apps/denidin-app/config/config.test.json` MUST both be updated with the three model fields set to their recommended defaults.
- **REQ-DATA-001**: The long-term memory data model (whatever record/metadata structure `MemoryManager` writes per stored memory into ChromaDB) MUST gain an `embedding_model` provenance field, populated with the exact model string used to generate that entry's embedding at write time. This is a forward-looking safeguard only (no backfill needed — see Edge Cases); it enables a future feature to detect/handle embedding-model mismatches without needing to build that detection logic now.
- **REQ-CONFIG-006** *(added during implementation)*: `memory.longterm.min_similarity` in `config.json`, `config.example.json`, and `config.test.json` MUST be recalibrated for `text-embedding-3-large` (lowered from 0.7/0.2 to 0.15), since similarity thresholds are model-specific and the old values were tuned for `text-embedding-3-small`. See Edge Cases and Open Questions for the provisional nature of this value.
- **REQ-BUGFIX-001** *(found during implementation, fixed in-scope)*: `denidin.py`'s `__main__` block and `test_media_webhook_routing.py`'s config fixture MUST include `ai_vision_model` and `ai_embedding_model` when rebuilding the `config_dict` passed to `initialize_app()` — a pre-existing gap silently discarded any custom `ai_vision_model` value in production before this feature.

### Key Entities

- **AppConfiguration** (`src/models/config.py`): Gains `ai_embedding_model` field; `ai_vision_model` default value changes.
- **MemoryManager** (`src/managers/memory_manager.py`): No structural change to its embedding call itself — already accepts `embedding_model` as a constructor parameter (line 49); the *caller* (`AIHandler`) changes which config field it reads. Its ChromaDB write path gains one new metadata field (`embedding_model`, REQ-DATA-001).

## Technology Choice: Vision Model (`ai_vision_model`)

- **Decision Date**: 2026-07-07
- **Rationale**: `gpt-4o-mini` is multimodal (accepts image input) and already the model family used for text completions, at $0.15/$0.60 per 1M tokens vs. `gpt-4o`'s $2.50/$10 (grandfathered pricing) — roughly a 17x cost reduction for image/PDF extraction with no new model family to validate against.
- **Alternatives Considered**:
  - `gpt-4o` (current default): proven quality, but ~17x more expensive; no cost justification found for the document-extraction use case.
  - `gpt-4.1-mini` ($0.40/$1.60 per 1M): documentation on vision-input support is conflicting/unclear per current vendor docs; not selected due to that ambiguity, but worth revisiting if `gpt-4o-mini` quality proves insufficient on real documents.
- **Migration Path**: If extraction quality regresses on real Hebrew/mixed-language documents (to be validated manually post-implementation, per this repo's UI/feature verification norms), fall back to `gpt-4o` or evaluate `gpt-4.1-mini` — both are drop-in via config only.

## Technology Choice: Embedding Model (`ai_embedding_model`)

- **Decision Date**: 2026-07-07
- **Rationale**: `text-embedding-3-large` shows materially better multilingual semantic capture than `text-embedding-3-small` (MIRACL multilingual benchmark: 31.4% → 54.9% vs. the older ada-002 baseline), directly relevant to Hebrew-language session content and search-by-embedding accuracy. The cost difference ($0.13/1M vs. $0.02/1M) is negligible in absolute terms at this project's memory-storage volume.
- **Alternatives Considered**:
  - `text-embedding-3-small` (current default): cheaper, but weaker multilingual/semantic capture — directly conflicts with the stated Hebrew-quality goal.
  - Open-source multilingual embedding models (e.g., multilingual-e5): would require self-hosting or a new API dependency; rejected to keep the project's zero-infrastructure OpenAI-only embedding approach (consistent with the ChromaDB technology choice already on record for this project).
- **Migration Path**: Switching embedding models changes vector dimensionality (1536 → 3072), which would normally strand or degrade recall quality for any long-term memories already embedded under the old model. **Resolved for this feature**: verified directly against `data/memory/chroma.sqlite3` — 0 embeddings currently stored, so there is nothing to migrate today. No re-embedding tooling is built as part of this feature. Forward-looking safeguard: REQ-DATA-001 adds an `embedding_model` provenance field to every future write, so if this situation recurs (model change with real data present), a future feature has the metadata needed to detect and handle mismatches deliberately, rather than silently degrading recall.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of text-completion calls (verified via test assertions on outbound request payloads) use `config.ai_model`; zero hardcoded model strings remain in `ai_handler.py`.
- **SC-002**: 100% of vision/extraction calls use `config.ai_vision_model`; DOCX text-only analysis continues using `config.ai_model` (verified by acceptance scenario 3 in User Story 2).
- **SC-003**: `MemoryManager` embedding calls use `config.ai_embedding_model` when set, with correct fallback behavior when only the legacy nested field is present (verified by both acceptance scenarios in User Story 3).
- **SC-004**: Estimated per-1000-image-message cost drops by ~90%+ (gpt-4o-mini vs. gpt-4o pricing) with no unresolved quality regression identified during manual verification on real sample documents (including at least one Hebrew-language sample).
- **SC-005**: `config.example.json` and `config.test.json` both contain all three model fields with the recommended defaults; a fresh `AppConfiguration.from_file()` load with neither model field explicitly set produces `ai_model="gpt-4o-mini"`, `ai_vision_model="gpt-4o-mini"`, `ai_embedding_model="text-embedding-3-large"`.
- **SC-006**: Every new record written to ChromaDB by `MemoryManager` includes an `embedding_model` metadata field matching the model string actually used for that write (REQ-DATA-001).

## Open Questions

- Both original open questions were resolved in the 2026-07-07 clarification session: the embedding-migration risk was resolved by direct inspection of production data (0 embeddings currently stored, so no migration tooling needed), and the validation-warning nice-to-have was descoped in favor of the lighter-weight forward-looking `embedding_model` provenance field (REQ-DATA-001).
- **New, carried forward**: `min_similarity: 0.15` (REQ-CONFIG-006) is a provisional recalibration based on a single confirmed data point (0.1858 similarity for one genuinely relevant match). It has not been validated against a broader set of real recall scenarios. Recommend revisiting this value once real production usage accumulates more long-term memories, to confirm 0.15 isn't now too permissive (returning irrelevant matches) or still occasionally too strict.
