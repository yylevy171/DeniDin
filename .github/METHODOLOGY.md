# DeniDin Development Methodology

**Established**: January 21, 2026  
**Purpose**: SpecKit workflow principles and development methodology

> **Note**: This file defines HOW we work (process, workflow, TDD).
> For WHAT we enforce (coding standards, constraints), see `CONSTITUTION.md`.

---

## I. Specification-First Development

Every feature MUST begin with a complete specification before any implementation starts.

**Requirements:**
- **MANDATORY User Stories** (BLOCKING gate):
  - Feature specification MUST include `user-stories.md` file BEFORE spec can be approved
  - If user stories don't exist: STOP work and ask: "Please provide user stories for this feature in Given-When-Then format"
  - User stories MUST define complete end-to-end flows from external entry point (user action, webhook, API request) through system to response
  - Each story traces: External Input → System Processing → Output/Response
  - Examples of GOOD user stories:
    - "Given user sends imageMessage via WhatsApp → When bot receives webhook → Then router dispatches to media handler → And bot sends response"
    - "Given admin API request arrives with auth header → When request validates → Then endpoint executes → And response returns to client"
  - Examples of BAD (incomplete) user stories:
    - "User sends image → Bot analyzes it" (doesn't specify entry point or routing)
    - "System processes document" (too vague, no Given-When-Then)
  - User stories MUST follow **Given-When-Then** format (Gherkin/BDD style)
  - Acceptance criteria must be independently testable and verifiable
  - User stories with prioritized levels (P1, P2, P3...) that are independently testable
- Functional requirements with clear acceptance criteria matching the user stories
- Edge cases and error scenarios explicitly documented
- Each user story MUST be deliverable as a standalone MVP increment
- Integration test requirements MUST be explicit in user stories (see CONSTITUTION §V)
  - For each user story: Explicitly list "Router/Dispatcher Requirement: [what needs to be routed/dispatched]"
  - Example: "Router Requirement: @bot.router.message(type_message='imageMessage') must route to WhatsAppHandler"

**Critical Validation Gate**:
- ❌ Feature spec WITHOUT user stories = BLOCK - Request them
- ❌ User stories WITHOUT Given-When-Then format = BLOCK - Request proper format
- ❌ User stories that don't trace entry point → processing → response = BLOCK - Request complete E2E flows
- ✅ Only proceed to implementation when user stories define complete end-to-end flows

**Why This Matters**:
Feature 003 (Media Processing) was marked complete but had missing router handlers because:
- ❌ Spec had "use cases" but NO formal user stories in Given-When-Then format
- ❌ Use cases described "what bot does" but NOT "how user request reaches bot"
- ❌ No story explicitly said "When imageMessage webhook arrives, @bot.router.message(imageMessage) must route it"
- ✅ Feature 002+007 had formal user stories → bug would have been caught in review

**Rationale**: Specification-first development prevents scope creep, ensures stakeholder alignment before costly implementation, and enables parallel work streams by clearly defining deliverable increments. User stories trace complete system flows from user perspective, catching routing/integration gaps that component-focused specs miss.

**Third-Party Behavior Claims Require Real Verification (see CONSTITUTION.md "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS")**:
- Any spec/research/plan claim about how a third-party system (Green API, Morning/Green Invoice, OpenAI, or any future integration) actually behaves at runtime — message/payload shape, field contents, response format, timing, error behavior — MUST be backed by a real, observed interaction with that system, not by reading its documentation, an SDK's types, or a schema definition alone.
- A `speckit.clarify`/`speckit.research` entry that settles a behavior question MUST state how it was verified. "Confirmed per the docs/SDK" is not a verification method for this purpose — only "sent/received a real message and inspected the real raw result" is.
- If real verification isn't feasible yet when the spec is written, the claim MUST be flagged explicitly as an **unverified assumption** (not stated as settled fact), and verifying it for real must be an explicit task before the dependent user story can be marked done — not discovered afterward in production.
- Test fixtures that stand in for third-party-sourced data (webhook payloads, API responses, etc.) MUST be derived from a real captured interaction, not hand-typed from what the author expects the shape to be.
- **Why this matters**: Feature 039's `"@Name"` WhatsApp-mention recognition design was built on a spec Decision claiming "a real WhatsApp @-mention inserts visible `@DisplayName` text" — verified only by reading Green API's documented webhook schema, never by sending a real mention. It was wrong: a real native `@`-mention (the primary way users actually mention someone) inserts the mentioned contact's raw phone number, not a display name. The spec, the constitution wording, and the billed tests' hand-typed `"@Name"` fixtures all inherited the same unverified assumption, so nothing in the spec/implementation/test pipeline could have caught it — it was found live, by a human, after deployment. See `specs/bugfixes/bugfix-024-*.md` (once opened) for the fix.

---

## II. Template-Driven Consistency

All artifacts MUST follow standardized templates to ensure uniform structure and completeness.

**Requirements:**
- `user-stories.md` MUST exist for every feature (MANDATORY, blocks spec approval)
  - MUST use Given-When-Then (Gherkin/BDD) format
  - Each story must trace complete end-to-end flow from external entry point to response
  - Each story must explicitly list integration/routing requirements
  - If file doesn't exist: Ask for it, BLOCK spec approval until provided
- `spec.md` MUST use `.specify/templates/spec-template.md` structure
- `plan.md` MUST use `.specify/templates/plan-template.md` structure
- `tasks.md` MUST use `.specify/templates/tasks-template.md` structure
- Templates MUST include all mandatory sections; optional sections clearly marked
- Placeholder tokens (e.g., `[FEATURE]`, `[DATE]`) MUST be replaced with concrete values
- No deviation from template structure without explicit methodology amendment

**Rationale**: Templates enforce consistency across features, reduce cognitive load for reviewers, enable automated validation, and ensure critical sections are never omitted. User stories in Given-When-Then format ensure end-to-end thinking.

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
- **Phase 3: Implementation** - unit/integration test discipline (§VI.b) per user story
  priority, followed by a single Test-Driven Development (TDD, §VI.a) acceptance pass
  (`billed`/`expensive` tests, defined earlier in Phase 2, run once the whole feature is
  code-complete)
- **Constitution & Methodology Check** MUST pass before Phase 0; re-check after Phase 1
- No phase may begin until predecessor phase artifacts are complete and approved

**Rationale**: Phased execution reduces rework by catching issues early, enables incremental delivery, and ensures architecture decisions precede implementation details.

---

## V. Documentation as Single Source of Truth

All feature context MUST reside in structured markdown documents; code comments are supplementary only.

**Requirements:**
- `specs/[###-feature]/` directory MUST contain all feature artifacts
 - `specs/[###-feature]/` directory MUST contain all feature artifacts
 - STORAGE LOCATION POLICY (NEW): All new and updated feature specs, bugfix specs, and any other specification documents MUST be authored and stored under the `specs/in-progress/` hierarchy (for features) or `specs/bugfixes/` (for bugfix specs). The parent `specs/` folder (top-level `specs/` entries such as `specs/005-mcp-morning-green-receipt/`) is deprecated for active authoring and MUST NOT be used to store authoritative specs going forward.
   - Rationale: this eliminates duplication and ensures automation and reviewers always find canonical artifacts in a single location.
   - Enforcement: CI and tooling SHOULD prefer `specs/in-progress/` as the canonical source; reviewers MUST flag PRs that add or modify authoritative spec files outside `specs/in-progress/` or `specs/bugfixes/` and request relocation into the correct folder before merging.
- `plan.md` is the technical authority for implementation decisions
- `spec.md` is the functional authority for requirements and acceptance criteria
- `tasks.md` is the execution authority for implementation sequence
- Code MUST NOT contain undocumented assumptions or requirements
- All "NEEDS CLARIFICATION" markers MUST be resolved before implementation

**Rationale**: Centralized documentation prevents knowledge silos, enables onboarding without code archaeology, and provides durable context beyond transient conversations.

---

## VI. Test-Driven Development (TDD) & Unit/Integration Test Discipline

**Redefined 2026-08-18** (explicit human decision — see Changelog): **"TDD" in this project
now refers specifically to `billed`/`expensive` tests — the acceptance-level tests that
validate a feature from the real **user's perspective**, through the real end-to-end pipeline
(real OpenAI calls, real external services), as opposed to unit/integration tests, which are a
separate, still-mandatory discipline described below but are no longer what "TDD" itself means
in this methodology.** This replaces the prior (2026-01-21–2026-08-18) definition, under which
"TDD" named one unified RED→GREEN workflow applied uniformly across all four test tiers.

**Test tier classification (2026-07-30, Feature 029) MUST be explicit for every test written**,
in every app in this monorepo (each app registers these markers independently in its own
`pytest.ini`/`conftest.py`):
- **unit**: mocked/isolated, fast, no external network calls
- **integration**: real internal components exercised from a real external entry point
  (webhook, HTTP request) — no mocking of internal classes/handlers/managers (§V)
- **billed** (`@pytest.mark.billed`): real, text-only paid OpenAI API calls — cheap per
  run; excluded from the default run but may be run freely, with NO per-run approval
  gate and NO one-at-a-time restriction (see CONSTITUTION.md §VII)
- **expensive** (`@pytest.mark.expensive`): real vision/image/PDF/DOCX paid OpenAI API
  calls — costlier per run; excluded from the default run AND requires explicit human
  approval before every single run, one at a time (see CONSTITUTION.md §VII)

### VI.a — TDD proper: `billed`/`expensive` (user-perspective) tests

These are the tests that actually validate the feature works — end to end, from a real
user's perspective, through the real webhook/router/handler/AI pipeline, exactly as a real
person would trigger it. They are **defined at the start of the feature's task breakdown**
(during `speckit.tasks`/planning, same timing as before) — but "defined" means a **plain-language,
user-experience description** of the scenario, not test code. The actual test code is written,
and run, together, only at the end. Neither the description nor (once it exists) the code blocks
any unit/integration task.

**Workflow:**
1. **DEFINE, at the start, in user-experience terms**: as part of the feature's task list,
   describe each `billed`/`expensive` scenario in plain, user-facing language — what a real
   person does (what they'd type/send), what they should see happen in response, which user
   story/success criterion it validates, and its exact tier (`billed` vs `expensive` — flag
   `expensive` explicitly, since it carries its own separate per-run approval gate). This is a
   **description, not code** — no test file, no pytest function, no assertions are written at
   this stage. It's the same kind of scenario language `quickstart.md`/`user-stories.md`
   Acceptance Scenarios already use, not an implementation artifact.
2. **DO NOT WRITE the actual test code, and DO NOT RUN anything**, while unit/integration tasks
   for the feature are still in progress — the user-experience description from step 1 is the
   only artifact that exists at this point; there is no test file to be blocked on or to skip.
3. **IMPLEMENT AND RUN, together, only at the end** — once the whole feature is code-complete
   (every unit and integration task, §VI.b below, finished and GREEN). At that point, turn each
   step-1 description into real test code and run it immediately, once, against the completed
   implementation. This is the feature's real acceptance pass — fix forward on any failure (same
   "no premature declaring success" bar as any other test).
4. `expensive` tests keep the full existing per-run human-approval gate, one at a time, with
   logs read before any re-run (CONSTITUTION §VII) — this discipline is unchanged by this
   redefinition. `billed` tests keep their existing no-approval-needed, run-freely status.

**Rationale**: a `billed`/`expensive` test proves the feature actually works for a real user;
writing or running one before the feature exists just proves it fails for an obvious reason
(nothing is implemented yet), which adds no information a unit/integration RED phase doesn't
already give more cheaply. Defining the scenario in user-experience terms up front still fixes
the target the implementation is aiming at from day one — without the cost/maintenance burden
of real test code that would otherwise sit unrun (and likely drift stale against the contracts
it was written against) for the entire implementation period.

### VI.b — Unit & integration test discipline (unchanged)

The prior RED→GREEN, human-approval-gated workflow **stays exactly as it was** for `unit` and
`integration` tests — this was explicitly reaffirmed, not touched, by the 2026-08-18
redefinition above.

**Requirements:**
- Every unit/integration implementation task MUST be split into two sub-tasks:
  - **Task A (Tests)**: Write comprehensive tests covering all acceptance criteria
  - **Task B (Implementation)**: Implement code to pass tests (BLOCKED until Task A approved)
- Tests MUST be reviewed and approved by human before implementation begins
- Once approved, tests are IMMUTABLE without explicit human re-approval
- Test coverage MUST include: happy path, edge cases, error scenarios, boundary conditions
- No implementation code may be written until its corresponding tests exist and are approved
- **Test tier classification (2026-07-30, Feature 029) MUST be explicit for every test written**,
  in every app in this monorepo (each app registers these markers independently in its own
  `pytest.ini`/`conftest.py`):
  - **unit**: mocked/isolated, fast, no external network calls
  - **integration**: real internal components exercised from a real external entry point
    (webhook, HTTP request) — no mocking of internal classes/handlers/managers (§V)
  - **billed** (`@pytest.mark.billed`): real, text-only paid OpenAI API calls — cheap per
    run; excluded from the default run but may be run freely, with NO per-run approval
    gate and NO one-at-a-time restriction (see CONSTITUTION.md §VII)
  - **expensive** (`@pytest.mark.expensive`): real vision/image/PDF/DOCX paid OpenAI API
    calls — costlier per run; excluded from the default run AND requires explicit human
    approval before every single run, one at a time (see CONSTITUTION.md §VII)
  - 🚨 **Run every billed/expensive test via `scripts/run_single_test.sh <node_id>`**
    (`apps/denidin-app`, 2026-08-18) — never a raw `pytest ... | tail`/`| grep`, which can
    silently discard the actual assertion/traceback before it's ever read (see CONSTITUTION.md
    §VII and §XVIII below for the incident this closed). For a stop-on-first-failure sequence
    of `billed` tests, use `scripts/run_multiple_billed_tests.sh <node_id> ...` (billed only).
  - The **EXPLAIN Test Plan** step (Step 1 below) MUST state which tier(s) each new test
    belongs to, so the human approval gate can weigh cost/approval implications before any
    test is written — a test plan that omits tier classification is incomplete

**Workflow (6 Steps with Human Gates):**

1. **EXPLAIN Test Plan**
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

Manual test checkpoints (acceptance testing, e.g. `quickstart.md` scenarios) remain user story
approval gates, run alongside or after §VI.a's acceptance pass.

---

## VII. Bug-Driven Development (BDD)

All bug fixes MUST follow a disciplined root-cause analysis and test-first workflow.

**Bug Specification Storage:**
- ALL bugfix specifications MUST be stored in `specs/bugfixes/` directory
- Format: `specs/bugfixes/bugfix-###-description.md` (e.g., `specs/bugfixes/bugfix-001-constitution-not-loaded.md`)
- Prefix: Always start with `bugfix-` to distinguish from features
- Sequential numbering: 001, 002, 003, etc.
- Never store bugfix specs in `specs/in-progress/` or other feature directories
- **Priority (2026-07-24)**: Every bugfix spec MUST declare a `Priority` field (`P0`/`P1`/`P2`), the same scheme used by feature specs (see §XI) — set at spec creation, before the root-cause approval gate, and revisited if severity is reassessed during investigation

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

**Folder Structure (merged 2026-07-24 — `in-definition/` and the old separate `in-progress/`
concept are now ONE folder, `in-progress/`; there is no longer a distinct
"clarifications-only, not yet started" stage as its own folder)**:
```
specs/
├── in-progress/       # Features with open CLARIFICATIONS and/or currently being implemented (active work)
├── backlog/           # Fully-specified features not yet started, any priority (merged P0/P1/P2, 2026-07-21)
├── done/              # Completed features (implemented, tested, merged) + done/bugfixes/
├── obsolete/          # Cancelled/deprecated features and bugfixes, or specs no longer accurate (merged with not-doing, 2026-07-21) + obsolete/bugfixes/
├── bugfixes/          # Open bugfix specs (bugfix-###-description.md)
├── CONSTITUTION.md    # Coding standards and constraints
├── METHODOLOGY.md     # Development process and workflow (this file)
└── ROADMAP.md         # Feature priorities and status tracking
```

**Requirements:**
- **in-progress/**: A feature lives here for its entire active-work lifespan — from initial
  drafting (while it may still have unresolved CLARIFICATIONS in spec.md) through planning,
  implementation, and testing. Covers what used to be two separate folders/stages.
  - Status: "Draft - Needs Clarification", "Implementation in Progress", or "Testing"
  - A brand-new feature starts here directly (not first in some other folder)
  - A feature resumed from `backlog/` also moves back here, right after branch creation,
    before any further planning/implementation work begins
  - Action: Move to `done/` once merged to master (or to `backlog/` if paused before
    completion — see below)

- **backlog/**: Fully specified, clarified, not currently being worked — priority tracked via
  each spec's own `Priority` field (P0/P1/P2), not by folder
  - All clarifications resolved
  - Ready for planning/implementation whenever capacity allows, but no active branch/work
    right now
  - A feature only lands here either fresh out of clarification (never yet started) or when
    active work on it is paused and moved out of `in-progress/`

- **done/**: Completed and merged features (and `done/bugfixes/` for merged bugfixes)
  - Serves as reference and documentation archive
  - Never deleted (historical record)

- **obsolete/**: Cancelled, deprecated, rejected, or no-longer-accurate features and bugfixes (and `obsolete/bugfixes/` for bugfixes specifically)
  - Includes both "decided not to pursue" specs (formerly `not-doing/`) and specs whose described issue no longer applies against current code
  - Superseded by alternative approaches, or the underlying problem was already fixed by unrelated work
  - Serves as historical record of what was considered/reported and why archived
  - Never deleted (prevents re-proposing rejected ideas or re-investigating already-resolved reports)
  - Each archived spec MUST carry a brief status note explaining why it was archived and when

**Folder Movement Rules:**
1. New feature starts in `in-progress/` (drafting, may have open clarifications)
2. Once clarifications answered and the feature is not being actively worked further right
   now → Move to `backlog/`
3. **When a backlog feature is picked up to start/resume work → Move back to `in-progress/`**
   — right after branch creation, before any further planning/implementation work begins
4. When feature merged to master → Move to `done/`
5. When feature cancelled/rejected/found obsolete → Move to `obsolete/` (with rationale documented in spec)
6. Feature folders MUST NOT exist in multiple locations simultaneously

**Rationale**: Organized folder structure provides instant visibility into feature status, prevents stale specs from cluttering active work, enables priority-based planning, and maintains historical archive of completed features.

---

## Development Workflow

### Feature Initialization

1. Run `.specify/scripts/bash/create-new-feature.sh` to generate feature directory and branch structure
2. Feature directories MUST follow naming: `specs/###-feature-name/`
3. Branch names MUST follow: `###-feature-name` (matching directory)
4. Spec MUST be created via `speckit.specify` agent with user input validation
5. New feature starts in `specs/in-progress/` folder (drafting stage, may still have open clarifications)

### Workflow Progression

```text
User Request
    ↓
speckit.specify → spec.md in specs/in-progress/
    ↓
Resolve CLARIFICATIONS (USER APPROVAL GATE)
    ↓
Move to specs/backlog/ (priority tracked in the spec's own Priority field)
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

### Finish-Feature Trigger Phrase ("Haleluya")

🚨 **NEVER RUN HALELUYA ON YOUR OWN.** 🚨 (added 2026-07-31, after the AI agent did exactly this
unprompted while fixing bugfix-019)

Saying **"haleluya"** (or any reasonable spelling variant — "halleluja", "halelluia", etc.) to the AI agent at any point is shorthand for: **first verify a spec file for the current feature/bugfix is actually committed under `specs/`** (if none is found, stop and ask the human rather than proceeding — see "Missing-Spec Verification" below), then **update docs and move the spec to its correct `specs/` folder per the Folder Movement Rules above (as part of the SAME commit as the code, not a separate later commit), commit, push, open a PR, and merge it**. Also available as the `/haleluya` slash command. **Branches are never deleted as part of this flow** — the merged branch is left in place for the human to delete explicitly if they want to. This does not skip any gate elsewhere in this doc (tests still must pass, CONSTITUTION checks still apply) — it's purely a shorthand for the finish-up mechanics once the actual work is already done and approved.

**Missing-Spec Verification (added 2026-07-30):** Feature 024 (Ledger Event Recognition) was fully implemented and merged to `master` with **no spec file ever committed at all** — confirmed via a full `git log --all` history search, which found zero commits touching any `024`-prefixed path anywhere, ever. Spec-first development (see above) is meant to make this structurally impossible, but nothing was actually checking for it at the one moment - "finishing" the feature - where it's cheap to catch and expensive to miss. Haleluya's first step is now to extract the feature/bugfix's numeric ID from the branch name and confirm a matching spec exists under `specs/` (in git, not just the working tree) before touching git state at all; if none is found, it stops and surfaces this to the human instead of silently finishing the merge.

**Single PR, not two (added 2026-08-07).** Earlier practice had the docs/spec-folder-move land as a *separate* follow-up PR after the feature PR merged (e.g. PR #198 for the feature, then a distinct PR #199 titled "docs/...-spec-cleanup"). Don't do that anymore — fold the docs update and spec-folder move into the same commit as the code, so the whole thing ships as one PR. The one wrinkle: the spec's `Status` line traditionally records the PR number, which doesn't exist yet at commit time — write the Status line without it initially, then once `gh pr create` returns the real number, push one small addendum commit onto the *same* branch/PR to fill it in before merging. That still counts as one PR, not two.

**Haleluya never touches `dev`/`prod` (rewritten 2026-08-07 — deploy step removed entirely, not just gated).** Earlier versions of this flow had a "test-deploy" step (rebuild-and-recreate a running environment's container to verify the merged fix) gated behind an explicit human ask-first, added 2026-08-05 after a real incident where a silent test-deploy to `dev` left it running a from-source build that was never actually cut as a release. That gate itself is no longer enough: **haleluya now has no deploy step, scripted or ask-first, at all** — no rebuild, no `run_all.sh`/`stop_all.sh` call, no dev-lock release, nothing that touches a running environment in any way. Which environment(s) run what, and when, is always a separate, fully explicit human decision made outside this flow, on its own request, subject to CLAUDE.md's "never start an environment without approval" rule as always — haleluya's own job stops at "merged to master, docs in order."

**Release prompt (added 2026-08-02, Feature 034 — versioning & release management; scope narrowed 2026-08-07 alongside the deploy-step removal above).** After merging, `haleluya` gains one more mandatory step: for each app the finished work touched, **always ask the human whether to cut a release** — never silently skip this, never decide the answer. If yes, ask for the **exact version string** and wait for it; never suggest, compute, or default one, not even as a "recommended, say yes to accept" suggestion (see CLAUDE.md's "AI AGENTS: VERSION AND RELEASE DECISIONS ARE HUMAN-ONLY" banner — this is the same hard constraint, not a new one). Skipping the release for a given app (e.g. a docs-only change) is a valid answer to the question, but the question itself is never skipped. This step covers cutting a release (`scripts/cut_release.sh`) only, never deploying it anywhere — deploying (`scripts/deploy_release.sh`, to any environment including `dev`) is always its own separate, explicit, freshly-approved request from the human, entirely outside haleluya. **Once approved, that deploy is executed by running `scripts/deploy_release.sh` directly and only that** — no manual pre-flight connectivity/health check first (see CONSTITUTION.md §VII); the script's own built-in verification is the check, and running one manually beforehand is redundant, not extra diligence.

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
- Phases: Setup → Foundational → User Story N (by priority) → **Acceptance** (§VI.a — every
  `billed`/`expensive` scenario described (in user-experience terms, at the earlier phases) for
  the feature gets its real test code written AND run, together, once, as a final pass here,
  after every earlier phase's unit/integration tasks are GREEN; not itself split into a/b, since
  there's no test-code artifact at all until this final phase)
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

**Scope note (2026-08-18)**: this protocol governs §VI.b (unit/integration tests) — the
Task A/Task B, blocked-until-approved pattern. It does NOT apply to §VI.a's `billed`/`expensive`
tests, which are defined up front but deliberately are not a per-task blocking gate; they run
once, as a single acceptance pass, after every unit/integration task below is already GREEN.

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

## XVIII. Sequential-Run Stop Gates

When a human gives an explicit per-iteration instruction for a sequential/repeated task
(most commonly "run all N tests one by one, on pass continue, on fail stop"), each
individual occurrence of the stop condition is its own gate — it MUST be treated exactly
like any other human-approval gate in this document (§VI, §XVII), never bundled with or
inferred from an earlier one.

**Requirements:**
- On EVERY failure in an explicit stop-on-fail sequence, the AI agent MUST halt, report the
  failure in full, and wait for fresh explicit human input before doing anything else —
  investigating, fixing, re-running, or advancing to the next item in the sequence.
- Approval to fix-and-continue past one failure MUST NOT be generalized into standing
  permission for later failures in the same sequence, even ones that look structurally
  identical or trivially fixable.
- Maintaining an accurate run-log/tracking file (recording what happened) is NOT a
  substitute for actually stopping at the gate before acting.

**Enforcement:**
- If an AI agent notices a failure mid-sequence: HALT immediately, report, and wait -
  never reason "the user already approved a similar fix earlier in this run."
- If genuinely uncertain whether a new failure is "similar enough" to a previously-approved
  one to skip the stop: it is not - stop and ask.

**Real incident (2026-08-02)**: during a 48-test sequential billed-test sweep, the human
approved a specific fix for one test's confusing fixture data. On a later, differently-caused
but similarly-shaped failure, an AI agent silently generalized that approval into "fix-and-
continue is now this sweep's standing behavior" - investigating, fixing, re-running, and
committing the fix with no pause to report or ask, then continued through the remaining
tests in the sweep without stopping again. The human's correction: *"you must NEVER
generalize like that. When I say STOP AT FAILURE YOU MUST STOP AT FAILURE."*

**Rationale**: Sequential automated loops create exactly the conditions where approval-gate
discipline erodes without feeling like a violation in the moment - each individual decision
("this looks like the same kind of fix, I'll just continue") seems like reasonable efficiency
rather than a bypassed gate, until the failures compound into a fully unsupervised loop.
Treating every stop condition as its own gate, with no generalization across occurrences,
is what actually preserves human oversight in a sequential context.

**Tooling note (2026-08-18)**: `scripts/run_multiple_billed_tests.sh <node_id> ...`
(`apps/denidin-app`) implements exactly this stop-on-first-failure shape mechanically for a
`billed`-tier sequence - it runs each test one at a time via `scripts/run_single_test.sh`,
announces PASS/FAILED as each completes, and stops (non-zero exit, no further tests run) the
instant one fails. Using it does not relax anything in this section - a failure it reports
still requires a full stop, a report, and fresh explicit human input before touching anything,
exactly as if each test had been run by hand. It exists purely to prevent the OTHER real
incident from this same day (see CONSTITUTION.md §VII): an ad-hoc `pytest ... | tail`
silently discarding the actual assertion/traceback before it could even be read.

---

## XIX. User-Experience-Impacting Changes Require Explicit Approval

Any change that alters what an end user (a WhatsApp conversation participant) sees, receives, or
interacts with — new message formats, new interactive elements (buttons, media), altered wording
of user-facing prompts, changed timing/frequency of proactive messages, etc. — requires the
human's explicit approval before being built or changed, even when it's a small, well-justified,
mechanically obvious fix to existing broken behavior.

**Requirements:**
- Before adding or changing any UX-facing behavior (not purely internal/backend logic), the AI
  agent MUST describe the change and its user-visible effect, and wait for explicit approval,
  before implementing it.
- This applies even when reusing an already-approved pattern from elsewhere in the codebase (e.g.
  extending an existing button-approval mechanism to a new feature) — reuse of the underlying
  mechanism does not itself pre-approve applying it to a new user-facing surface.
- This applies even when fixing a bug in already-built UX-facing behavior — a fix that changes
  what the user experiences is still a UX decision, not a pure internal correctness fix, and
  still needs sign-off before being applied (not just before being merged).

**Real incident (2026-08-18, Feature 054 reminders)**: while running a sequential billed-test
sweep (see §XVIII), a real bug was found: reminder approval prompts sent as WhatsApp interactive
buttons were never wired up so a real tap on them would resolve anything — taps were always
rejected as stale. The AI agent diagnosed the root cause and applied a fix directly to
`denidin.py` without pausing to ask, then kicked off a verification run in the background — a
§XVIII violation in its own right. When asked afterward why reminders used buttons at all, the
human's decision was to keep them, but with a new standing rule volunteered on the spot:
*"anything with this kind of user experience impact requires MY APPROVAL."*

**Rationale**: this project's users interact with DeniDin entirely through WhatsApp — every UX
decision (text vs. buttons, wording, when something gets sent, how an approval is presented) is
directly experienced by a real person on a real device, unlike a purely internal refactor. The
human product owner, not the AI agent, decides these tradeoffs — including when the "fix" is to
restore previously-intended behavior rather than introduce something new.

---

## XX. "Show Me The Full Conversation" Means Verbatim, Both Sides, Nothing Else

When a human asks to see "the conversation," "the full conversation," or equivalent phrasing —
from a test log, a session file, wherever — the response MUST be only the literal turn-by-turn
text both sides actually said, verbatim, in order. Not a summary, not a table, not an
interpretation, not an analysis blended in with it.

**Requirements:**
- Give the exact words of every turn, both the human/user side and the assistant/bot side - no
  paraphrasing, no dropped turns.
- Verify what was actually TRANSMITTED, not an intermediate/logged value that might not match. A
  debug log's `output_text=` (or equivalent pre-finalization snapshot) is not necessarily what the
  user received - an exception handler downstream can silently replace it. Find and use the value
  from the point it was actually sent (e.g. a "sending to user" log line), and confirm this
  distinction BEFORE presenting anything as "what was said," not after being corrected for it.
- Show multi-line replies in full - a naive single-line log-parsing approach that truncates at the
  first `\n` is not acceptable; verify the extraction captures complete multi-line messages before
  presenting them as complete.
- Do not substitute something "close enough" - a bulleted paraphrase, a summarizing table, a
  "here's the gist" - even if it seems more efficient or more informative. Additional analysis, if
  warranted, goes in a clearly separate section AFTER the verbatim transcript, never blended into
  it or offered instead of it.
- If it's genuinely unclear which conversation/log/timeframe is meant, ask - but once established,
  the plain transcript comes first, before anything else.

**Real incident (2026-08-19, Feature 054 reminders investigation)**: asked for "the full
conversation" from a failing test's log while investigating a real bug. Three consecutive
responses each substituted something else instead - a summarized table with editorial framing, a
transcript later found to contain a wrong value (an intermediate debug-log snapshot presented as
what was sent, when the actual sent value was different - only caught because the human separately
asked "why is there an empty reply, that should never happen," forcing a re-check), and a version
that silently truncated multi-line bot replies at their first line break. The human had to ask a
fourth time, explicitly: *"When I ask for the full conversation I mean what was said by both sides,
and ONLY WHAT WAS SAID. Not anything else... you resisted doing that for at least 3 times even
though I asked VERY CLEARLY."*

**Rationale**: a request for the raw transcript is often itself a debugging step - the human wants
to look at the unfiltered evidence themselves, not receive a pre-digested interpretation of it.
Substituting analysis for the actual data undermines exactly the kind of independent verification
the request was for, and doing it repeatedly after being asked plainly is a compliance failure, not
a stylistic choice.

---

## XXI. Every New Tool-Bearing Feature Needs Explicit Constitution Boundaries

A tool's own JSON-schema `description` is sufficient for the model to know it exists and how to
call it mechanically — it is NOT sufficient to keep the model from reaching for it when confused
about something unrelated. Every feature that attaches a new tool (or tool family) to a model turn
MUST also get an explicit section in `config/runtime_constitution.md` (in `apps/denidin-app`, and
the equivalent for any other app that grows a comparable mechanism) stating:

- **When it applies** - the concrete triggering intent, in the user's own words/phrasing where
  possible.
- **When it explicitly does NOT apply** - especially: never as a fallback interpretation of an
  ambiguous or short reply that was actually answering a DIFFERENT pending question; never mid-flow
  in another tool-bearing context; never as a "try something" default when genuinely unsure what
  the user wants.
- **That ambiguity is resolved by asking, never by guessing** - if the model cannot tell what's
  wanted, or which of several plausible tools applies, it must ask the user plainly, exactly like
  the disambiguation rule this project already applies to Invoice Management document-type
  resolution.

**Cross-reference in both directions.** Adding the new feature's own section is not enough -
every OTHER existing tool-bearing section must also be updated to explicitly exclude the new
feature (mirroring the precedent already established by "Ledger Event Recognition"'s own "an
Invoice Management action is automatically 'Neither'" bullet). A one-way boundary leaves every
pre-existing context still able to misfire into the new tool family when its own turns are
ambiguous - which is exactly what happened here.

**Real incident (2026-08-19, Feature 054 reminders)**: reminder tools shipped attached to every
GODFATHER/ADMIN turn with zero mentions anywhere in `runtime_constitution.md` - no scope, no
exclusions, nothing beyond the four tools' own schema descriptions. A real billed E2E test for an
entirely unrelated feature (Morning client management) showed the model repeatedly reaching for
`create_reminder`/`modify_reminder` when confused by an ambiguous mid-flow reply, including
inventing a placeholder `reminder_id='unknown'` rather than asking. The user's own framing, once
this was traced to its actual cause: *"EVERYTHING IS BOUNDED, SO EVERYTHING NEEDS TO BE
WELL-DEFINED in the runtime const. Not just vaguely defined or relying on the tool's hard
definitions - it must be WELL-DEFINED."*

**Rationale**: this project's tool-bearing features generally attach broadly by role (RBAC-gated,
not conversation-topic-gated) - a GODFATHER/ADMIN turn about ANYTHING can have several unrelated
tool families attached simultaneously (Morning invoicing, ledger events, reminders, and whatever
comes next). Without an explicit, mutually-cross-referenced boundary for each one, that breadth of
availability is itself the risk surface - the model has no signal about which tools are actually
relevant to the turn it's on, only which tools it technically COULD call.

---

**Version**: 2.8.0 | **Established**: 2026-01-21 | **Last Updated**: 2026-08-19

**Changelog**:
- v2.8.0 (2026-08-19): Added "Every New Tool-Bearing Feature Needs Explicit Constitution
  Boundaries" (XXI) after Feature 054 (reminders) shipped with no runtime_constitution.md scope at
  all, letting the model reach for reminder tools mid-flow in an unrelated feature's conversation
- v2.7.0 (2026-08-19): Added "'Show Me The Full Conversation' Means Verbatim, Both Sides, Nothing
  Else" (XX) after an AI agent substituted summaries/interpretations/truncated or wrong-value
  transcripts for a plain verbatim conversation request, three times in a row, despite explicit
  clarification each time
- v2.6.0 (2026-08-18): Mandated `scripts/run_single_test.sh`/`scripts/run_multiple_billed_tests.sh` (§VI test-tier section, §XVIII) as the required way to run billed/expensive tests, after an AI agent's ad-hoc `pytest ... | tail -15` silently discarded the actual assertion/traceback, leading to a wrong failure report and an unapproved rerun just to recover it
- v2.5.2 (2026-08-18): Added "User-Experience-Impacting Changes Require Explicit Approval" (XIX) after an AI agent fixed a WhatsApp interactive-button wiring bug unilaterally mid-sweep instead of pausing for approval, given the change altered real user-facing behavior
- v2.5.1 (2026-08-18): Corrected v2.5.0 same-day, per explicit human clarification — "defined at
  the start" for §VI.a `billed`/`expensive` tests means a **plain-language, user-experience
  description** of the scenario (what a real person does/sees), NOT test code. Actual test code
  is written, and run, together, only at the end — v2.5.0's wording had incorrectly said to
  write the real test code early (just not run it), which was never the intent.
- v2.5.0 (2026-08-18): Redefined "TDD" (§VI) per explicit human decision — TDD now refers
  specifically to `billed`/`expensive` (user-perspective, real end-to-end) tests: defined at the
  start of a feature's task breakdown same as before, but no longer run during implementation;
  run once, as a single acceptance pass, only once the whole feature's unit/integration work is
  code-complete. Unit/integration tests keep their prior RED→GREEN, human-approval-gated,
  test-immutable workflow completely unchanged, now named §VI.b to distinguish it from §VI.a
  (the redefined "TDD"). §XVII annotated to clarify its Task A/Task B blocking pattern applies
  to §VI.b only, not §VI.a.
- v2.4.0 (2026-08-02): Added "Sequential-Run Stop Gates" (XVIII) after a real incident where an AI agent generalized one approved test-fix into standing permission to skip the stop-on-fail gate for later failures in the same sweep
- v2.3.0 (2026-07-30): Feature 029 - TDD (§VI) now requires explicit test-tier classification (unit/integration/billed/expensive) as part of the EXPLAIN Test Plan step, in every app
- v2.2.0 (2026-01-21): Added "AI Agent TDD Self-Check Protocol" (XVII) to prevent methodology violations during autonomous work
- v2.1.0 (2026-01-21): Added 10 methodology requirements from existing practice: Integration Contracts (VII), Terminology Glossary (VIII), Technology Choice Documentation (IX), Requirement Identifiers (X), Phase Validation Checkpoints, Clarifications Tracking, Estimated Duration, expanded Template Requirements
- v2.0.0 (2026-01-21): Split from constitution - extracted SpecKit workflow principles into dedicated methodology file
- v1.2.0 (2026-01-17): Previous unified constitution with 16 principles
