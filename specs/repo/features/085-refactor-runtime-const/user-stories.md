# User Stories: Refactor Runtime Constitution

## Stories

### User Story 1 - Modular Constitution Loading (Priority: P1)
**Given** the DeniDin application starts up
**When** the AIHandler initializes its system prompt
**Then** it MUST assemble the `runtime_constitution.md` from smaller, modular domain files (e.g., invoice management, ledger rules)
**And** the assembled output MUST maintain byte-for-byte stability for OpenAI prompt caching.
**Integration Requirement**: The file assembly logic must run seamlessly without breaking existing tests.

### User Story 2 - Domain-Specific Editing (Priority: P2)
**Given** a developer wants to update invoice rules
**When** they edit the specific domain markdown file
**Then** they only need to review that specific module, reducing cognitive load and merge conflicts.
