# DeniDin Development Methodology

**Established**: January 21, 2026  
**Purpose**: SpecKit workflow principles and development methodology

> **Note**: This file defines HOW we work (process, workflow, TDD).
> For WHAT we enforce (coding standards, constraints), see `CONSTITUTION.md`.

---

## I. Specification-First Development

Every feature MUST begin with a complete specification before any implementation starts.

**Requirements:**
- User scenarios with prioritized user stories (P1, P2, P3...) that are independently testable
- Functional requirements with clear acceptance criteria (Given-When-Then format)
- Edge cases and error scenarios explicitly documented
- Each user story MUST be deliverable as a standalone MVP increment

**Rationale**: Specification-first development prevents scope creep, ensures stakeholder alignment before costly implementation, and enables parallel work streams by clearly defining deliverable increments.

---

## II. Template-Driven Consistency

All artifacts MUST follow standardized templates to ensure uniform structure and completeness.

**Requirements:**
- `spec.md` MUST use `.specify/templates/spec-template.md` structure
- `plan.md` MUST use `.specify/templates/plan-template.md` structure
- `tasks.md` MUST use `.specify/templates/tasks-template.md` structure
- Templates MUST include all mandatory sections; optional sections clearly marked
- Placeholder tokens (e.g., `[FEATURE]`, `[DATE]`) MUST be replaced with concrete values
- No deviation from template structure without explicit methodology amendment

**Rationale**: Templates enforce consistency across features, reduce cognitive load for reviewers, enable automated validation, and ensure critical sections are never omitted.

---

## III. AI-Agent Collaboration

Development workflow integrates AI agents as first-class collaborators with clearly defined responsibilities and handoff protocols.

**Requirements:**
- Each agent (`speckit.specify`, `speckit.plan`, `speckit.tasks`, `speckit.implement`, `speckit.analyze`, `speckit.clarify`) MUST have documented scope and inputs/outputs
- Agent handoffs MUST be explicit with validation checkpoints
- Human approval REQUIRED at specification and plan completion gates
- Agents MUST NOT modify files outside their designated scope
- Agent guidance files MUST be updated when tech stack changes

**Rationale**: Clear agent boundaries prevent conflicts, enable reliable automation, and maintain human oversight at critical decision points while maximizing AI leverage for repetitive tasks.

---

## IV. Phased Planning & Execution

Feature implementation MUST follow a structured phase progression with validation gates.

**Phases:**
- **Phase 0: Research** - Technical feasibility, dependency analysis, constraints
- **Phase 1: Design** - Data models, API contracts, quickstart scenarios
- **Phase 2: Task Generation** - Dependency-ordered, user-story-grouped task list
- **Phase 3: Implementation** - Test-Driven Development (TDD) per user story priority
- **Constitution & Methodology Check** MUST pass before Phase 0; re-check after Phase 1
- No phase may begin until predecessor phase artifacts are complete and approved

**Rationale**: Phased execution reduces rework by catching issues early, enables incremental delivery, and ensures architecture decisions precede implementation details.

---

## V. Documentation as Single Source of Truth

All feature context MUST reside in structured markdown documents; code comments are supplementary only.

**Requirements:**
- `specs/[###-feature]/` directory MUST contain all feature artifacts
- `plan.md` is the technical authority for implementation decisions
- `spec.md` is the functional authority for requirements and acceptance criteria
- `tasks.md` is the execution authority for implementation sequence
- Code MUST NOT contain undocumented assumptions or requirements
- All "NEEDS CLARIFICATION" markers MUST be resolved before implementation

**Rationale**: Centralized documentation prevents knowledge silos, enables onboarding without code archaeology, and provides durable context beyond transient conversations.

---

## VI. Test-Driven Development (TDD)

All implementation MUST follow strict test-first methodology with human approval gates.

**Requirements:**
- Every implementation task MUST be split into two sub-tasks:
  - **Task A (Tests)**: Write comprehensive tests covering all acceptance criteria
  - **Task B (Implementation)**: Implement code to pass tests (BLOCKED until Task A approved)
- Tests MUST be reviewed and approved by human before implementation begins
- Once approved, tests are IMMUTABLE without explicit human re-approval
- Test coverage MUST include: happy path, edge cases, error scenarios, boundary conditions
- Manual test checkpoints (acceptance testing) serve as user story approval gates
- No implementation code may be written until its corresponding tests exist and are approved

**TDD Workflow (6 Steps with Human Gates):**

1. **EXPLAIN Test Plan** (NEW MANDATORY STEP)
   - Describe in plain language WHAT will be tested and WHY
   - List all test cases with their purpose
   - Identify CHK requirements each test validates
   - Explain expected behavior and edge cases
   - **Output**: Human-readable test plan explanation
   - **BLOCKING**: Get human approval of test plan before writing tests

2. **🚨 HUMAN APPROVAL GATE - TEST PLAN 🚨**
   - Present: Test plan explanation, test cases, CHK mappings
   - Human reviews and approves test strategy
   - **BLOCKING**: No test writing until approval received
   - If rejected: Revise test plan based on feedback

3. **RED Phase - Write Failing Tests**
   - Write tests based on approved test plan
   - Tests MUST fail initially (no implementation exists yet)
   - Follow test file naming conventions
   - Run tests to verify they fail
   - **Output**: Failing test suite

4. **🚨 HUMAN APPROVAL GATE - TESTS 🚨**
   - Present: Written tests, test results showing failures
   - Human reviews test implementation quality
   - **BLOCKING**: No code implementation until approval received
   - If rejected: Revise tests based on feedback

5. **GREEN Phase - Implement Code**
   - Write minimal code to make tests pass
   - Follow existing code patterns and style
   - Run tests to verify they pass
   - **Output**: Passing test suite

6. **REFACTOR Phase - Clean Up**
   - Improve code quality while keeping tests green
   - Remove duplication, improve naming
   - Run tests after each refactor to ensure they still pass
   - **Output**: Clean, tested code

---

## VII. Bug-Driven Development (BDD)

All bug fixes MUST follow a disciplined root-cause analysis and test-first workflow.

**Bug Specification Storage:**
- ALL bugfix specifications MUST be stored in `specs/bugfixes/` directory
- Format: `specs/bugfixes/bugfix-###-description.md` (e.g., `specs/bugfixes/bugfix-001-constitution-not-loaded.md`)
- Prefix: Always start with `bugfix-` to distinguish from features
- Sequential numbering: 001, 002, 003, etc.
- Never store bugfix specs in `specs/in-progress/` or other feature directories

**Branch Naming:**
- Format: `bugfix/###-issue-description`
- Example: `bugfix/001-constitution-not-loaded`
- Number MUST match the spec file number in `specs/bugfixes/`
- Issue: concise description in kebab-case

**Bug-Fix Workflow (Strict Order):**

1. **Root Cause Investigation**
   - Reproduce the bug in isolation with minimal test case
   - Experiment with code to understand failure mechanism
   - Document observed vs. expected behavior
   - Identify exact code location and logic flaw
   - **Output**: Clear description of root cause

2. **🚨 HUMAN APPROVAL GATE - ROOT CAUSE 🚨**
   - Present: Root cause analysis with proposed fix approach
   - Provide fix options with pros/cons if multiple approaches exist
   - Human reviews and approves root cause diagnosis and fix strategy
   - **BLOCKING**: No test writing until approval received
   - If rejected: Return to step 1 for deeper investigation

3. **Test Gap Analysis**
   - **CRITICAL QUESTION**: Why didn't existing tests catch this bug?
   - Review test suite for coverage gaps
   - Identify missing test scenarios (edge cases, timing, realistic intervals)
   - Document test deficiencies that allowed bug to reach production
   - **Output**: Explanation of test gap + list of missing test cases

4. **Write Failing Tests (Test-First)**
   - Create NEW test(s) that reproduce the bug
   - Tests MUST fail with current buggy code
   - Update EXISTING tests if they were insufficient (e.g., unrealistic test intervals)
   - Tests should use realistic conditions (not overly short timeouts/intervals)
   - Run tests to confirm they FAIL
   - **Output**: Failing test suite that demonstrates the bug

5. **🚨 HUMAN APPROVAL GATE - TESTS 🚨**
   - Present: Test gap explanation, failing tests, test strategy
   - Human reviews and approves test changes
   - **BLOCKING**: No code changes until approval received
   - If rejected: Return to step 3 or 4

6. **Implement Fix**
   - Make MINIMAL code changes to fix root cause
   - Avoid scope creep - fix ONLY the identified bug
   - Follow existing code style and patterns
   - **Output**: Code changes

7. **Verify Fix**
   - Run previously-failing tests - they MUST now pass
   - Run full test suite - all tests MUST pass
   - Verify fix works with actual production data/scenario if applicable
   - **Output**: Passing test suite

8. **Commit & PR**
   - Commit message format: `fix(component): brief description`
   - Example: `fix(session): run cleanup immediately at startup`
   - PR description MUST include:
     - Root cause explanation
     - Why tests didn't catch it
     - Test changes made
     - Code changes made

**Rationale**: Bug fixes without understanding root cause lead to incomplete fixes or regressions. Test-gap analysis prevents the same class of bugs from recurring. Human approval ensures thorough investigation before changes.

**Testing Analysis Protocol:**

When running tests to diagnose issues or verify fixes:

1. **ANALYZE ONLY - DO NOT MODIFY**
   - If tests fail: STOP and analyze the failures
   - Explain WHAT is failing and WHY
   - Identify root cause: Is it a test issue or code issue?
   - Present OPTIONS for fixing (with pros/cons)
   - **CRITICAL**: Do NOT change tests without approval
   - **CRITICAL**: Do NOT change code without approval

2. **SEEK APPROVAL BEFORE ANY CHANGES**
   - Present analysis findings to human
   - Suggest specific changes with rationale
   - Wait for explicit approval: "Yes, do X" or "Option 2"
   - Only after approval: Make the approved changes
   - If rejected: Present alternative options

3. **INTEGRATION TESTS - NEVER MOCK**
   - **CRITICAL**: Integration tests MUST use real application components
   - Do NOT mock internal classes, managers, or handlers in integration tests
   - Integration tests verify real interactions between actual components
   - Use test configurations (e.g., short timeouts) instead of mocking behavior
   - Only mock external services (APIs, databases) when truly necessary
   - Unit tests are for mocking; integration tests are for real usage

4. **LOG FILES - SINGLE SOURCE OF TRUTH**
   - **CRITICAL**: Do NOT re-run tests just to see more log output
   - All test logs are written to `logs/test_logs/` directory
   - Each test module has its own log file (e.g., `test_background_cleanup.log`)
   - Search and analyze existing log files instead of re-executing tests
   - Re-run tests only to verify fixes, not to gather diagnostic information
   - Use `tail`, `grep`, `find` commands to explore logs efficiently

5. **EXAMPLE WORKFLOW**
   ```
   AI: "Tests are failing because X calls Y with parameter Z, but Y now expects A.
        Options:
        1. Update test to pass A instead of Z (if Z was wrong)
        2. Update code to accept Z (if test is correct)
        3. Both are wrong - need different approach
        
        Which option should I proceed with?"
   
   Human: "Option 1 - the test is outdated"
   
   AI: [Makes approved change to test]
   ```

**Rationale**: Test failures require human judgment to determine whether tests or code are incorrect. Premature changes can mask real bugs or break correct tests. Analysis-first approach ensures informed decisions and prevents churn.

**Rationale**: TDD ensures code correctness by design, prevents rework from misunderstood requirements, enables confident refactoring, and provides living documentation of expected behavior. Human approval of tests before implementation guarantees alignment on acceptance criteria before costly coding begins.

---

## VII. Integration Contracts

All component interactions MUST be documented with explicit contracts defining responsibilities and guarantees.

**Requirements:**
- `plan.md` MUST include "Integration Contracts" section for multi-component features
- Each contract MUST document:
  - **Component A MUST**: Caller obligations (what calling component must do)
  - **Component B PROVIDES**: API guarantees (what service returns/guarantees)
  - **Component B EXPECTS**: Input validation requirements (what service requires)
- Contract format: `Component A ↔ Component B Contract`
- Contracts MUST cover: data formats, error handling, null/empty cases, ordering requirements
- Update contracts when component interfaces change

**Example:**
```markdown
### SessionManager ↔ AI Handler Contract

**AI Handler MUST**:
- Call `session_manager.get_conversation_history(whatsapp_chat, user_role)` before generating response
- Pass correct `user_role` for token limit enforcement

**SessionManager PROVIDES**:
- `get_conversation_history()` returns `List[Dict[str, str]]` formatted for OpenAI API
- Order: Chronological by `order_num`

**SessionManager EXPECTS**:
- `whatsapp_chat`: Valid WhatsApp ID (e.g., "1234567890@c.us")
- `role`: Either "user" or "assistant" (strict validation)
```

**Rationale**: Explicit contracts prevent integration bugs, document assumptions, enable independent component development, and serve as acceptance criteria for integration tests.

---

## VIII. Terminology Glossary

All specs MUST define domain-specific terminology in a centralized glossary.

**Requirements:**
- `spec.md` MUST include "Terminology Glossary" section near the top (before detailed requirements)
- Define ALL domain-specific terms used throughout the spec
- Mark deprecated terms explicitly: `DEPRECATED: old_term (use new_term instead)`
- Include format examples for IDs, identifiers, and structured data
- Cross-reference glossary terms in requirements using backticks: `session_id`

**Mandatory for glossary:**
- Primary entity identifiers (IDs, keys)
- Status/state values
- Role names
- Technical terminology with multiple interpretations

**Example:**
```markdown
## Terminology Glossary

- **session_id**: Unique UUID identifier for a conversation session (primary key)
- **whatsapp_chat**: WhatsApp chat identifier (e.g., "1234567890@c.us" for individual)
- **user_role**: User's role - either "client" or "godfather" (determines permissions)
- **DEPRECATED: chat_id** - use `session_id` or `whatsapp_chat` explicitly
```

**Rationale**: Centralized glossary prevents naming confusion, documents evolution of terminology, enables consistent usage across 500+ line specs, and provides onboarding reference.

---

## IX. Technology Choice Documentation

All significant technology decisions MUST be documented with rationale and alternatives.

**Requirements:**
- `spec.md` or `plan.md` MUST include "Technology Choice: [Technology]" sections
- Each technology decision MUST document:
  - **Decision Date**: When choice was made
  - **Rationale**: Why this technology was selected (pros/cons)
  - **Alternatives Considered**: What else was evaluated and why rejected
  - **Migration Path**: Strategy if technology needs replacement later
- Document choices for: databases, frameworks, libraries, protocols, file formats
- Update documentation if technology choice changes

**Example:**
```markdown
**Technology Choice: ChromaDB**
- **Decision Date**: January 18, 2026
- **Rationale**: 
  - Zero infrastructure setup (pip install and done)
  - Free forever (file-based, no cloud costs)
  - Semantic search essential for context retrieval
  - Scales to 1K-10K memories (our Phase 1-2 needs)
- **Alternatives Considered**: 
  - Pinecone ($$, cloud dependency)
  - Qdrant (complex setup)
  - pgvector (no semantic search optimization)
- **Migration Path**: 
  - If exceeding 10K memories, evaluate Qdrant Cloud or Pinecone
  - Abstraction layer allows swapping implementations
```

**Rationale**: Technology decisions are expensive to reverse. Documentation enables informed choices, justifies trade-offs, provides audit trail, and plans for future evolution.

---

## X. Requirement Identifiers

All requirements MUST have unique, traceable identifiers.

**Requirements:**
- Format: `REQ-[CATEGORY]-[###]` (e.g., REQ-CONFIG-001, REQ-ROLE-002)
- Categories: CONFIG, ROLE, API, DATA, SECURITY, PERFORMANCE, etc.
- Sequential numbering within category (001, 002, 003...)
- Requirements with IDs can be referenced from code, tests, tasks
- Update cross-references if requirement ID changes

**Example:**
```markdown
**REQ-ROLE-001**: User role determination
- Godfather: WhatsApp chat ID matches configured godfather phone
- Client: Any other WhatsApp chat ID
- Default: If role cannot be determined, default to "client"

**REQ-CONFIG-001**: Configuration File Structure
- All configuration in `config/config.json`
- Feature flags under `feature_flags` dictionary
- Memory settings under `memory` dictionary
```

**Rationale**: Unique IDs enable traceability from spec to code to tests, facilitate requirement impact analysis, support compliance tracking, and enable automated validation.

---

## XI. Specification Folder Structure

All feature specifications MUST be organized by status and priority in standardized folders.

**Folder Structure:**
```
specs/
├── in-definition/     # Features with open CLARIFICATIONS, not yet ready for planning
├── in-progress/       # Features currently being implemented (active work)
├── P0/                # Priority 0 - Critical features (blocking production)
├── P1/                # Priority 1 - High priority features (next sprint)
├── P2/                # Priority 2 - Medium priority features (backlog)
├── done/              # Completed features (implemented, tested, merged)
├── not-doing/         # Cancelled/deprecated features (not pursuing)
├── CONSTITUTION.md    # Coding standards and constraints
├── METHODOLOGY.md     # Development process and workflow (this file)
└── ROADMAP.md         # Feature priorities and status tracking
```

**Requirements:**
- **in-definition/**: Features with unresolved CLARIFICATIONS in spec.md
  - Status: "Draft - Needs Clarification"
  - Action: Move to priority folder (P0/P1/P2) once clarifications resolved
  
- **in-progress/**: Features actively being developed
  - Status: "Implementation in Progress" or "Testing"
  - Action: Move to `done/` once merged to master
  
- **P0/**: Critical priority - blocking production issues, security fixes
  - Must be addressed before new feature work
  - Example: Critical bugs, production outages
  
- **P1/**: High priority - next planned features
  - Ready for planning and implementation
  - All clarifications resolved
  
- **P2/**: Medium priority - backlog features
  - Fully specified but deferred
  - Can be promoted to P1 as capacity allows
- **done/**: Completed and merged features
  - Serves as reference and documentation archive
  - Never deleted (historical record)
  
- **not-doing/**: Cancelled, deprecated, or rejected features
  - Features decided not to pursue
  - Superseded by alternative approaches
  - Serves as historical record of what was considered and why rejected
  - Never deleted (prevents re-proposing rejected ideas)

**Folder Movement Rules:**
1. New feature starts in `in-definition/` until clarifications resolved
2. Once clarifications answered → Move to `P0/`, `P1/`, or `P2/` based on priority
3. When implementation begins → Move to `in-progress/`
4. When feature merged to master → Move to `done/`
5. When feature cancelled/rejected → Move to `not-doing/` (with rationale documented in spec)
6. Feature folders MUST NOT exist in multiple locations simultaneously
5. Feature folders MUST NOT exist in multiple locations simultaneously

**Rationale**: Organized folder structure provides instant visibility into feature status, prevents stale specs from cluttering active work, enables priority-based planning, and maintains historical archive of completed features.

---

## Development Workflow

### Feature Initialization

1. Run `.specify/scripts/bash/create-new-feature.sh` to generate feature directory and branch structure
2. Feature directories MUST follow naming: `specs/###-feature-name/`
3. Branch names MUST follow: `###-feature-name` (matching directory)
4. Spec MUST be created via `speckit.specify` agent with user input validation
5. New feature starts in `specs/in-definition/` folder until clarifications resolved

### Workflow Progression

```text
User Request
    ↓
speckit.specify → spec.md in specs/in-definition/
    ↓
Resolve CLARIFICATIONS (USER APPROVAL GATE)
    ↓
Move to specs/P0/, specs/P1/, or specs/P2/ based on priority
    ↓
speckit.plan → plan.md (USER APPROVAL GATE)
    ↓
speckit.clarify (if ambiguities detected)
    ↓
speckit.plan → plan.md + research.md (USER APPROVAL GATE)
    ↓
speckit.plan (Phase 1) → data-model.md + contracts/ + quickstart.md
    ↓
speckit.tasks → tasks.md
    ↓
speckit.analyze (validates against METHODOLOGY.md + CONSTITUTION.md)
    ↓
speckit.implement → Incremental code delivery by user story
```

### Quality Gates

- **Specification complete**: All `[NEEDS CLARIFICATION]` resolved
- **Methodology & Constitution compliance**: All principles verified in checks
- **Plan approval**: Technical stack, architecture, constraints documented
- **Tasks ready**: Dependency order verified, parallelization marked with `[P]`
- **Implementation checkpoint**: Each user story independently testable

---

## Template & Artifact Requirements

### Mandatory Template Sections

**spec.md:**
- Feature metadata (Feature ID, Priority, Status, Branch, Dates)
- Terminology Glossary (domain-specific terms, deprecated terms)
- Clarifications (Q&A log with session dates)
- User Scenarios & Testing (with priorities P1, P2, P3...)
- Requirements (functional, non-functional) with REQ-XXX-### identifiers
- Technology Choices (with decision date, rationale, alternatives, migration path)
- Edge Cases

**plan.md:**
- Feature metadata (Feature, Branch, Status, Estimated Duration, Updated date)
- Summary/Overview
- Technical Context:
  - Language/Version
  - Primary Dependencies
  - Storage approach
  - Testing strategy
  - Target Platform
  - Performance Goals
  - Constraints
  - Scale/Scope
- Integration Contracts (Component A ↔ Component B format)
- Methodology & Constitution Compliance Check
- Phase breakdown with Validation/Checkpoint sections
- Project Structure (documentation + source code layout)
- Complexity Tracking (only if violations exist)

**tasks.md:**
- Task ID format: `[T###a/b] [P?] [Story/Phase] Description`
  - `a` = Write tests, `b` = Implementation
  - `[P]` = Can run in parallel
  - `Story` = US1, US2, US3... or Phase = Phase 1, Phase 2...
- Path Conventions section (project structure, relative vs absolute paths)
- TDD Workflow explanation (Task A → APPROVAL → Task B)
- Test Immutability reminder
- Phases: Setup → Foundational → User Story N (by priority)
- Checkpoint markers after each phase
- Version Control steps (VC0-VC5) per phase

### Artifact Consistency Rules

- File paths in `tasks.md` MUST match structure defined in `plan.md`
- Entities in `tasks.md` MUST derive from `data-model.md`
- Endpoints in `tasks.md` MUST derive from `contracts/`
- User stories in `tasks.md` MUST map 1:1 to stories in `spec.md`

### Phase Validation Checkpoints

Each phase MUST include validation checkpoints to gate progression.

**Requirements:**
- **plan.md**: Each phase MUST have "Validation" or "Checkpoint" section
- **tasks.md**: Checkpoint markers after phase completion
- Checkpoint format: `**Checkpoint**: [Summary] - ready for [Next Phase]`
- Validation criteria:
  - Tests passing (with counts)
  - Artifacts created/updated
  - Integration verified
  - Performance validated (if applicable)
- No progression to next phase until checkpoint criteria met

**Example:**
```markdown
### Validation
- All tests pass: `pytest tests/unit/test_session_manager.py -v`
- Code coverage >90%
- Session persistence verified

**Checkpoint**: SessionManager complete and tested - ready for Phase 3 (MemoryManager)
```

**Rationale**: Validation checkpoints prevent cascading failures, ensure quality at each stage, provide clear progress indicators, and enable early detection of issues.

### Clarifications Tracking

All requirement clarifications MUST be logged in spec.md.

**Requirements:**
- `spec.md` MUST include "Clarifications" section after feature metadata
- Format:
  ```markdown
  ### Session [YYYY-MM-DD]
  - Q: [Question about requirement] → A: [Decision made]
  - Q: [Another question] → A: [Another decision]
  ```
- Each clarification session has date stamp
- Questions and answers capture decision rationale
- Update related requirements after clarifications
- Cross-reference clarifications in requirements if needed

**Example:**
```markdown
## Clarifications

### Session 2026-01-15
- Q: How should DeniDin store credentials? → A: JSON config file (gitignored)
- Q: How should DeniDin receive WhatsApp messages? → A: Polling with configurable interval
- Q: How to handle multiple incoming messages? → A: Sequential processing
```

**Rationale**: Clarifications tracking provides audit trail of requirement evolution, prevents re-asking same questions, documents decision context, and enables understanding of why requirements changed.

### Estimated Duration

All plans MUST include time estimates for implementation.

**Requirements:**
- `plan.md` header MUST include: `**Estimated Duration**: [X-Y days]` or `[X weeks]`
- Provide range (pessimistic to optimistic)
- Break down by phase if phases exceed 3 days each
- Update estimate if scope changes significantly
- Track actual vs estimated in retrospectives

**Example:**
```markdown
**Estimated Duration**: 10-12 days

Phase breakdown:
- Phase 1-2 (Foundation + SessionManager): 3 days
- Phase 3 (MemoryManager): 2 days
- Phase 4-6 (Integration): 3 days
- Phase 7-10 (Testing + Docs + Deployment): 4 days
```

**Rationale**: Time estimates enable resource planning, manage stakeholder expectations, improve estimation accuracy over time through retrospectives, and highlight scope creep early.

---

## Governance

### Methodology Authority

This methodology defines the workflow and process standards for the DeniDin project.
Development constraints and coding standards are defined in `CONSTITUTION.md`.

### Amendment Procedure

1. Proposed changes MUST be documented with:
   - Rationale for change
   - Impact analysis on existing templates and workflows
   - Version bump justification (MAJOR/MINOR/PATCH)
2. Amendments require:
   - Update to all dependent templates and agent files
   - Migration plan for in-flight features if applicable
3. Version semantics:
   - **MAJOR**: Backward-incompatible changes (workflow redefinition)
   - **MINOR**: Additive changes (new phases, expanded sections)
   - **PATCH**: Clarifications, wording improvements

### Compliance & Review

- All specifications, plans, and task lists MUST undergo "Methodology & Constitution Check"
- Violations MUST be either corrected or explicitly justified in "Complexity Tracking"
- Unjustified violations block progression to next phase
- Agent files (`.github/agents/*.agent.md`) MUST reference both METHODOLOGY.md and CONSTITUTION.md for validation

---

## XVII. AI Agent TDD Self-Check Protocol

Before creating any implementation task or writing any production code, the AI agent MUST verify:

**Mandatory Pre-Implementation Checklist:**
1. ✅ **Tests exist first**: Corresponding test file created with comprehensive test cases
2. ✅ **Human approval obtained**: Tests have been reviewed and explicitly approved by human
3. ✅ **Task properly labeled**: Todo item clearly marked as "Task B (BLOCKED until Task A approved)"
4. ✅ **No premature implementation**: No production code written before test approval

**Task Creation Pattern:**
```
CORRECT:
- Task A: Write tests for [Component]
- Task B: Implement [Component] (BLOCKED until Task A approved)

VIOLATION:
- Create [Component] with [Feature]  ← Missing test-first split
```

**Enforcement:**
- If AI agent attempts to write production code without approved tests: HALT and request test approval
- If human requests implementation: AI must ask "Should I write tests first for approval?"
- If tests exist but not approved: Wait for explicit human approval before implementation
- Todo lists MUST use "Task A/Task B" pattern for all implementation work

**Rationale**: This self-check prevents methodology violations during autonomous work, ensuring tests-first discipline is maintained even when humans don't explicitly invoke it.

---

**Version**: 2.2.0 | **Established**: 2026-01-21 | **Last Updated**: 2026-01-21

**Changelog**:
- v2.2.0 (2026-01-21): Added "AI Agent TDD Self-Check Protocol" (XVII) to prevent methodology violations during autonomous work
- v2.1.0 (2026-01-21): Added 10 methodology requirements from existing practice: Integration Contracts (VII), Terminology Glossary (VIII), Technology Choice Documentation (IX), Requirement Identifiers (X), Phase Validation Checkpoints, Clarifications Tracking, Estimated Duration, expanded Template Requirements
- v2.0.0 (2026-01-21): Split from constitution - extracted SpecKit workflow principles into dedicated methodology file
- v1.2.0 (2026-01-17): Previous unified constitution with 16 principles
