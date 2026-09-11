# Feature Specification: Refactor Runtime Constitution

**Feature Branch**: `078-refactor-runtime-const`  
**Created**: 2026-09-11
**Status**: Draft  
**Input**: User description: "Refactor runtime const into modules."

---

**CRITICAL - MANDATORY REQUIREMENT**:
🚨 **This feature MUST have a separate `user-stories.md` file** before spec approval:
- ✅ **`user-stories.md`** exists.

---

## User Stories Reference
See **`user-stories.md`** for full Given-When-Then criteria.
- **User Story 1**: Modular Constitution Loading (P1)
- **User Story 2**: Domain-Specific Editing (P2)

### Edge Cases
- What happens if the modules fail to load? System must fallback gracefully or fail fast.
- Does chunking the file change the exact byte string sent to OpenAI? (Must maintain prompt caching efficiency).

## Requirements *(mandatory)*

### Functional Requirements
- **REQ-078-01**: The monolithic `apps/denidin-app/config/runtime_constitution.md` (currently ~1700 lines) MUST be split into logical domain modules (e.g., `core_identity.md`, `customer_engagement.md`, `invoice_management.md`, `ledger_events.md`).
- **REQ-078-02**: The `AIHandler` or initialization sequence MUST dynamically concatenate these modules at startup into a single string.
- **REQ-078-03**: The resulting concatenated string MUST be byte-for-byte stable across identical runs to ensure OpenAI Prompt Caching is not invalidated.
- **REQ-078-04**: The modular files MUST be located in `apps/denidin-app/config/runtime_modules/` or a similar dedicated directory.

### Key Entities
- **ConstitutionLoader**: A new utility responsible for reading, ordering, and assembling the markdown modules into a single system prompt.

## Success Criteria *(mandatory)*

### Measurable Outcomes
- **SC-001**: OpenAI API costs and latency remain stable (proving Prompt Caching still works).
- **SC-002**: 100% of existing unit and integration tests pass without modification.
