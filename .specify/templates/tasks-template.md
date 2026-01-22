---

description: "Task list template for feature implementation"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

---

**IMPORTANT**: This task list MUST comply with:
- **CONSTITUTION.md** (§I-III): Config-only (NO env vars), UTC timestamps, Git workflow with feature branches
- **METHODOLOGY.md** (§VI): TDD with human approval gates - Tests MUST be approved before implementation

**Critical TDD Requirements** (METHODOLOGY.md §VI):
- ⚠️ **EVERY TEST task requires HUMAN APPROVAL before proceeding to CODE task**
- ⚠️ **Once approved, tests are IMMUTABLE without explicit human re-approval**
- ✅ Test coverage MUST include: happy path, edge cases, error scenarios, boundary conditions

**Git Workflow** (CONSTITUTION.md §III):
- Feature branch per phase: `feature/###-feature-name-phaseX`
- Conventional commits with CHK/REQ references
- Merge commits (NOT squash) to preserve history
- See CONSTITUTION.md §III for complete workflow

---

**Tests**: Test-Driven Development (TDD) - ALL tests written and approved BEFORE implementation (per METHODOLOGY.md §VI)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- **[T###a]**: Write tests (REQUIRES HUMAN APPROVAL before T###b)
- **[T###b]**: Implement code (BLOCKED until T###a approved, tests are IMMUTABLE)
- Include exact file paths in descriptions

## TDD Workflow (Per Constitution Principle VI)

1. **Task A (Tests)**: Write comprehensive tests covering acceptance criteria
2. **👤 HUMAN APPROVAL GATE**: Review and approve tests
3. **Task B (Implementation)**: Write code to pass approved tests (tests frozen)
4. **Validation**: Run tests to verify implementation
5. **Next task**: Repeat TDD cycle

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- **Web app**: `backend/src/`, `frontend/src/`
- **Mobile**: `api/src/`, `ios/src/` or `android/src/`
- Paths shown below assume single project - adjust based on plan.md structure

<!-- 
  ============================================================================
  IMPORTANT: The tasks below are SAMPLE TASKS for illustration purposes only.
  
  The /speckit.tasks command MUST replace these with actual tasks based on:
  - User stories from spec.md (with their priorities P1, P2, P3...)
  - Feature requirements from plan.md
  - Entities from data-model.md
  - Endpoints from contracts/
  
  Tasks MUST be organized by user story so each story can be:
  - Implemented independently
  - Tested independently
  - Delivered as an MVP increment
  
  DO NOT keep these sample tasks in the generated tasks.md file.
  ============================================================================
-->

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project structure per implementation plan
- [ ] T002 Initialize [language] project with [framework] dependencies
- [ ] T003 [P] Configure linting and formatting tools

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

Examples of foundational TDD pairs (adjust based on your project):

- [ ] T004a [P] Write tests for database schema in tests/unit/test_db_schema.py: Test migrations run successfully, test table creation, test relationships, test constraints
- [ ] T004b [P] Setup database schema and migrations framework (BLOCKED until T004a approved)

- [ ] T005a [P] Write tests for auth framework in tests/unit/test_auth.py: Test user authentication, test token generation/validation, test permission checks
- [ ] T005b [P] Implement authentication/authorization framework (BLOCKED until T005a approved)

- [ ] T006a [P] Write tests for API routing in tests/integration/test_routing.py: Test route registration, test middleware execution order, test error handlers
- [ ] T006b [P] Setup API routing and middleware structure (BLOCKED until T006a approved)

- [ ] T007a [P] Write tests for base models in tests/unit/test_base_models.py: Test entity creation, test validation, test serialization
- [ ] T007b [P] Create base models/entities that all stories depend on (BLOCKED until T007a approved)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - [Title] (Priority: P1) 🎯 MVP

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Implementation for User Story 1 (TDD Pattern)

- [ ] T008a [P] [US1] Write tests for [Entity1] in tests/unit/test_[entity1].py: Test creation, test validation, test business logic methods
- [ ] T008b [P] [US1] Create [Entity1] model in src/models/[entity1].py (BLOCKED until T008a approved)

- [ ] T009a [P] [US1] Write tests for [Entity2] in tests/unit/test_[entity2].py: Test creation, test relationships to Entity1, test edge cases
- [ ] T009b [P] [US1] Create [Entity2] model in src/models/[entity2].py (BLOCKED until T009a approved)

- [ ] T010a [US1] Write tests for [Service] in tests/unit/test_[service].py: Test service methods, test error handling, mock dependencies
- [ ] T010b [US1] Implement [Service] in src/services/[service].py (BLOCKED until T010a approved, depends on T008b, T009b)

- [ ] T011a [US1] Write integration tests for [endpoint] in tests/integration/test_[endpoint].py: Test API endpoint, test request/response format, test error cases
- [ ] T011b [US1] Implement [endpoint/feature] in src/[location]/[file].py (BLOCKED until T011a approved)

- [ ] T012 [US1] 👤 **MANUAL APPROVAL GATE**: [Describe end-to-end test that you will perform to accept this user story]

**Checkpoint**: User Story 1 fully functional and independently testable

---

## Phase 4: User Story 2 - [Title] (Priority: P2)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Implementation for User Story 2 (TDD Pattern)

- [ ] T013a [P] [US2] Write tests for [Entity] in tests/unit/test_[entity].py: Test creation, test validation, test business logic
- [ ] T013b [P] [US2] Create [Entity] model in src/models/[entity].py (BLOCKED until T013a approved)

- [ ] T014a [US2] Write tests for [Service] in tests/unit/test_[service].py: Test service methods, mock external dependencies
- [ ] T014b [US2] Implement [Service] in src/services/[service].py (BLOCKED until T014a approved)

- [ ] T015a [US2] Write integration tests for [feature] in tests/integration/test_[feature].py: Test integration with US1 components
- [ ] T015b [US2] Implement [endpoint/feature] in src/[location]/[file].py (BLOCKED until T015a approved)

- [ ] T016 [US2] 👤 **MANUAL APPROVAL GATE**: [Describe end-to-end test for US2]

**Checkpoint**: User Stories 1 AND 2 both work independently

---

## Phase 5: User Story 3 - [Title] (Priority: P3)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Implementation for User Story 3 (TDD Pattern)

- [ ] T024 [P] [US3] Contract test for [endpoint] in tests/contract/test_[name].py
- [ ] T025 [P] [US3] Integration test for [user journey] in tests/integration/test_[name].py

### Implementation for User Story 3

- [ ] T026 [P] [US3] Create [Entity] model in src/models/[entity].py
- [ ] T027 [US3] Implement [Service] in src/services/[service].py
- [ ] T028 [US3] Implement [endpoint/feature] in src/[location]/[file].py

**Checkpoint**: All user stories should now be independently functional

---

[Add more user story phases as needed, following the same pattern]

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] TXXX [P] Documentation updates in docs/
- [ ] TXXX Code cleanup and refactoring
- [ ] TXXX Performance optimization across all stories
- [ ] TXXX [P] Additional unit tests (if requested) in tests/unit/
- [ ] TXXX Security hardening
- [ ] TXXX Run quickstart.md validation

---

## Dependencies & Execution Order (TDD-Aware)

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately (no TDD pairs, infrastructure only)
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
  - All "a" test tasks can run in parallel
  - **👤 APPROVAL GATE**: Human reviews all foundation tests
  - All "b" implementation tasks can run in parallel (after approval)
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories proceed sequentially in priority order (P1 → P2 → P3)
  - Within each user story, TDD pairs follow dependencies
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### TDD Workflow Per User Story

**For each user story (US1, US2, US3...)**:
1. Write all "a" test tasks (can parallelize if testing different components)
2. **👤 APPROVAL GATE**: Human reviews tests for that story
3. Implement all "b" tasks (parallelizable if no dependencies)
4. Run tests to validate
5. **👤 MANUAL APPROVAL GATE**: Human performs end-to-end acceptance test
6. Proceed to next user story

### Within Each User Story (TDD Pairs)

**Critical TDD Rules**:
- Every T###a (test) MUST be approved before T###b (implementation)
- Tests MUST be written to FAIL initially (no implementation exists yet)
- Once approved, tests are IMMUTABLE without re-approval
- Models before services (T008a/b → T010a/b)
- Services before endpoints (T010a/b → T011a/b)
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together (if tests requested):
Task: "Contract test for [endpoint] in tests/contract/test_[name].py"
Task: "Integration test for [user journey] in tests/integration/test_[name].py"

# Launch all models for User Story 1 together:
Task: "Create [Entity1] model in src/models/[entity1].py"
Task: "Create [Entity2] model in src/models/[entity2].py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1
   - Developer B: User Story 2
   - Developer C: User Story 3
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
