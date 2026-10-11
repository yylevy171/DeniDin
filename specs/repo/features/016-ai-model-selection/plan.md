# Implementation Plan: Per-Task AI Model Selection

**Branch**: `feature/016-ai-model-selection` | **Date**: 2026-07-07 | **Spec**: `specs/P1/016-ai-model-selection/spec.md`
**Input**: Feature specification from `specs/P1/016-ai-model-selection/spec.md`

---

**IMPORTANT**: This plan complies with:
- **CONSTITUTION.md** (§I, §IV, §XIII, §XV): Config-driven behavior (no env vars), code quality standards, data validation at config load, JSON format standards
- **METHODOLOGY.md** (§II, §IV, §VII): Template structure, phased planning, Integration Contracts

---

## Summary

`ai_model` (text) and `ai_vision_model` (image/PDF) already exist as top-level `AppConfiguration` fields and are already correctly wired per-flow (`AIHandler` for text, `ImageExtractor`/`PDFExtractor` for vision, `DOCXExtractor` for text-only doc analysis). The embedding model exists but is buried at `config.memory.longterm.embedding_model`. This feature:

1. Promotes the embedding model to a top-level `ai_embedding_model` field (with legacy-nested-field fallback), and adds a provenance field (`embedding_model`) to every ChromaDB write.
2. Changes two defaults: `ai_vision_model` from `gpt-4o` → `gpt-4o-mini` (~17x cheaper, same multimodal family); `ai_embedding_model` defaults to `text-embedding-3-large` (better multilingual/Hebrew semantic capture).
3. Adds config validation for all three model fields, and updates `config.example.json` + `config.test.json`.

No new code paths, no new dependencies, no feature flag (per spec Clarifications — this is a config-value/tuning change on existing paths, not new behavior). No data migration needed — production ChromaDB currently has 0 stored embeddings (verified directly).

## Technical Context

**Language/Version**: Python 3.11 (existing `apps/denidin-app` codebase)
**Primary Dependencies**: `openai` (existing), `chromadb` (existing) — no new dependencies
**Storage**: `config/config.json` (schema change only: +1 top-level field); ChromaDB (`data/memory/`) — metadata schema gains one field, no migration
**Testing**: `pytest` — unit tests (`tests/unit/test_config.py`, `tests/unit/test_memory_manager.py`, `tests/unit/test_ai_handler_memory.py`) + component-integration tests for the AIHandler→MemoryManager wiring; no new integration/E2E test file needed since existing dispatcher/routing tests already cover the text/image/PDF/docx paths end-to-end and don't assert on model strings today (this feature adds those assertions, it doesn't add new routes)
**Target Platform**: Linux server (existing deployment), Docker (existing `Dockerfile`)
**Project Type**: Single project (`apps/denidin-app`)
**Performance Goals**: N/A (config/model-selection change, not a performance feature)
**Constraints**: Must not change on-disk config schema in a backward-incompatible way — existing `config.json` deployments without `ai_embedding_model` must continue working unchanged (REQ-CONFIG-004 fallback)
**Scale/Scope**: 3 config fields, 1 metadata field, ~4 source files touched (`config.py`, `ai_handler.py`, `memory_manager.py`, plus the two config JSON files), no schema migration

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- ✅ **§I No environment variables**: All three model fields sourced from `config.json` only; no `os.getenv()` introduced.
- ✅ **§I Feature flags**: Explicitly NOT required — this changes config *values* on an existing code path, not new behavior/new code path. Confirmed in spec Clarifications.
- ✅ **§III Version control**: Work happens on `feature/016-ai-model-selection` (already created), never on `master`.
- ✅ **§IV Code quality**: New/changed functions keep type hints + Google-style docstrings; 120-char line limit.
- ✅ **§V Integration tests**: No new external entry points/routers are added by this feature, so no new E2E integration test is required; existing E2E tests for text/image/PDF/docx already exercise the routing layer. This feature ADDS model-string assertions to those flows (component-level checks), which is compatible with — not a replacement for — existing E2E coverage.
- ✅ **§XIII Data validation**: New `AppConfiguration.validate()` checks for the three model fields (non-empty strings), following the existing `data_root` validation pattern.
- ✅ **§XV JSON/File formats**: `config.example.json`/`config.test.json` edits keep 2-space indent, alphabetical keys, UTF-8.
- ✅ **No monkey-patching**: No runtime patching involved; this is plain config plumbing + one new dataclass field.
- ✅ **Zero mocking policy in integration tests**: No integration tests are modified/added that would require mocking; unit/component tests may construct real `AppConfiguration`/`MemoryManager` objects from test config, per existing patterns in `tests/unit/test_memory_manager.py`.

**Result**: PASS — no violations, no Complexity Tracking entries needed.

## Integration Contracts

### AppConfiguration ↔ AIHandler Contract

**AIHandler MUST**:
- Read `config.ai_model` for all text-completion calls (no change from today).
- Read `config.ai_vision_model` when passing vision-model configuration through to `ImageExtractor`/`PDFExtractor` (no change from today — only the *value* changes).
- When constructing `MemoryManager`, resolve the embedding model as: `config.ai_embedding_model` if present and non-empty, **else** `config.memory.get('longterm', {}).get('embedding_model', 'text-embedding-3-large')` (legacy fallback, but with the new default already updated — see Edge Case: a legacy config with the nested field set to the *old* `text-embedding-3-small` value is still honored verbatim, since it's explicit).

**AppConfiguration PROVIDES**:
- `ai_model: str` (default `'gpt-4o-mini'`, unchanged)
- `ai_vision_model: str` (default now `'gpt-4o-mini'`, changed from `'gpt-4o'`)
- `ai_embedding_model: str` (NEW, default `'text-embedding-3-large'`)
- `.validate()` raises `ValueError` if any of the three fields is empty/whitespace-only

**AppConfiguration EXPECTS**:
- Callers use `getattr(config, 'ai_embedding_model', None)` defensively only if supporting configs loaded via a path other than `from_file()` (e.g., hand-built `AppConfiguration(...)` in tests) — `from_file()` itself always populates the field via defaults merge, so production code loaded via `from_file()` can access `config.ai_embedding_model` directly without `getattr`.

### AIHandler ↔ MemoryManager Contract

**AIHandler MUST**:
- Pass the resolved embedding model string (per resolution rule above) as `MemoryManager(embedding_model=...)` at construction time — unchanged signature, only the *source* of the value changes (from `longterm_config.get('embedding_model', 'text-embedding-3-small')` to the new resolution rule above with new default `text-embedding-3-large`).

**MemoryManager PROVIDES**:
- `remember()` stores a new `embedding_model` key in each entry's metadata dict, set to `self.embedding_model` (the value it was constructed with) — this is the REQ-DATA-001 provenance field. No new constructor parameter needed; it reuses the already-stored `self.embedding_model`.

**MemoryManager EXPECTS**:
- `embedding_model` constructor arg is a valid OpenAI embedding model string; invalid strings surface as a 4xx from the OpenAI API at first `_create_embedding()` call, which is not retried (Constitution §XI) and propagates as `RuntimeError` per existing `ERR-MEMORY-002` behavior — no new error handling needed.

## Project Structure

### Documentation (this feature)

```text
specs/P1/016-ai-model-selection/
├── plan.md              # This file
├── spec.md              # Already written (previous session)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by this plan)
```

No `research.md`, `data-model.md`, `contracts/`, or `quickstart.md` are needed as separate files — Technology Choice research already lives in `spec.md` (per METHODOLOGY §IX, already satisfied there), the "data model" change is a single metadata-field addition documented inline above (Integration Contracts), and there are no new API contracts (no new endpoints/routes). Producing empty placeholder files for these would violate the "don't add unused scaffolding" principle — they're omitted, not deferred.

### Source Code (repository root)

```text
apps/denidin-app/
├── src/
│   ├── models/
│   │   └── config.py                  # MODIFIED: +ai_embedding_model field, ai_vision_model default change, validate() additions
│   ├── handlers/
│   │   └── ai_handler.py              # MODIFIED: embedding-model resolution logic (top-level field, legacy fallback)
│   └── managers/
│       └── memory_manager.py          # MODIFIED: remember() writes embedding_model into metadata
├── config/
│   ├── config.example.json            # MODIFIED: +ai_embedding_model, ai_vision_model value updated
│   └── config.test.json               # MODIFIED: +ai_embedding_model, ai_vision_model value updated
└── tests/
    └── unit/
        ├── test_config.py             # MODIFIED (new tests appended, existing tests untouched): validate() rejects empty model fields
        ├── test_memory_manager.py     # MODIFIED (new tests appended): remember() metadata includes embedding_model
        └── test_ai_handler_memory.py  # MODIFIED (new tests appended): AIHandler resolves ai_embedding_model with correct precedence/fallback
```

**Structure Decision**: Single project, `apps/denidin-app/` only (per repo layout — `morning-mcp-app` is untouched, unaffected by this feature). All changes are surgical edits to 3 existing source files + 2 config files + additive unit tests in 3 existing test files. No new modules, no new test files — new test *cases* only, following Constitution §VIII (test immutability: existing tests are appended to, never modified/rewritten).

## Phase 0: Research

**Status**: Complete — folded into `spec.md`'s "Technology Choice" sections (per METHODOLOGY §IX) during the specification session:
- Vision model choice (`gpt-4o` → `gpt-4o-mini`): pricing comparison, multimodal capability confirmation, alternatives considered (`gpt-4.1-mini` rejected for now due to conflicting vision-support documentation).
- Embedding model choice (`text-embedding-3-small` → `text-embedding-3-large`): MIRACL multilingual benchmark comparison, cost delta analysis, alternatives considered (open-source multilingual models rejected to avoid new infra dependency).
- Migration-risk investigation: direct inspection of `data/memory/chroma.sqlite3` confirmed 0 stored embeddings today, resolving the only open question from the spec session.

**Checkpoint**: All `[NEEDS CLARIFICATION]` markers resolved in `spec.md` prior to this plan — ready for Phase 1.

## Phase 1: Design

### Data Model Change

`AppConfiguration` (dataclass, `src/models/config.py`):

```python
ai_embedding_model: str = 'text-embedding-3-large'  # NEW field, alongside ai_model/ai_vision_model
ai_vision_model: str = 'gpt-4o-mini'                # CHANGED default (was 'gpt-4o')
```

`from_file()` defaults dict gains `'ai_embedding_model': 'text-embedding-3-large'` and updates `'ai_vision_model': 'gpt-4o-mini'`.

`validate()` gains:
```python
for field_name in ('ai_model', 'ai_vision_model', 'ai_embedding_model'):
    value = getattr(self, field_name)
    if not value or not value.strip():
        raise ValueError(f"{field_name} must not be empty")
```

ChromaDB metadata (`MemoryManager.remember()`), one new key added alongside existing `type`/`scope`/`created_at` defaults:
```python
metadata.setdefault('embedding_model', self.embedding_model)
```

### Embedding-Model Resolution Logic (`AIHandler.__init__`)

Replaces the current line:
```python
embedding_model=longterm_config.get('embedding_model', 'text-embedding-3-small'),
```
with:
```python
embedding_model=getattr(config, 'ai_embedding_model', None) or longterm_config.get('embedding_model', 'text-embedding-3-large'),
```
This gives top-level-field precedence (REQ-CONFIG-004), falls back to the legacy nested field if the top-level one is falsy/unset, and updates the ultimate hardcoded default from `text-embedding-3-small` to `text-embedding-3-large` (REQ-CONFIG-001).

### Config File Changes

`config/config.example.json` and `config/config.test.json` (both `apps/denidin-app/config/`):
```json
"ai_model": "gpt-4o-mini",
"ai_vision_model": "gpt-4o-mini",
"ai_embedding_model": "text-embedding-3-large",
```
(2-space indent, existing alphabetical-ish key ordering preserved per file's current style — verify against Constitution §XV during implementation.)

### Validation / Checkpoint

- All 3 config fields load correctly via `AppConfiguration.from_file()` with and without explicit values (defaults path).
- `validate()` rejects empty-string values for all 3 fields (new unit tests).
- `AIHandler` resolves `ai_embedding_model` with correct precedence: top-level set → used; top-level unset + legacy nested set → legacy used; neither set → new default (`text-embedding-3-large`) used.
- `MemoryManager.remember()` metadata includes `embedding_model` matching the constructed instance's model.
- Manual verification (per this repo's "test the golden path in a browser/app, don't just claim success from typecheck" norm, adapted here since there's no UI): send one real text message, one real image, and if feasible one real Hebrew-language message through a locally running bot instance and confirm no regressions and correct model routing via logs (`AIHandler initialized with model: ...` log line at `ai_handler.py:118`, extend if needed to also log vision/embedding model choices at startup for operator visibility).

**Checkpoint**: Config schema + resolution logic + metadata provenance field design complete — ready for Phase 2 (`/speckit.tasks`).

## Phase 2: Task Generation

Deferred to `/speckit.tasks` (not part of this plan) — will produce `tasks.md` with TDD-split tasks (Task A: tests, Task B: implementation, B blocked until A approved) grouped by the 3 user stories in `spec.md`:
- US1 (text model wiring — already correct, needs verification tests only)
- US2 (vision model wiring + default change — needs verification tests + config default change)
- US3 (embedding model promotion + fallback + provenance field — needs new field, resolution logic, tests)

## Phase 3: Implementation

Deferred to `/speckit.implement`, gated on approved `tasks.md` and the TDD approval gates in METHODOLOGY §VI.

## Complexity Tracking

*No entries — Constitution Check above passed with no violations requiring justification.*
