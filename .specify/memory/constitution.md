<!--
Sync Impact Report - Constitution Update
═════════════════════════════════════════
Version: 1.1.0 → 1.2.0
Status: Amendment ratified
Type: MINOR (additive change - 10 new principles)

Modified Principles:
  - [NEW] Principle VII: Feature Flags for Safe Deployment
  - [NEW] Principle VIII: UTC Timestamp Requirement
  - [NEW] Principle IX: Version Control Workflow
  - [NEW] Principle X: Code Quality Standards
  - [NEW] Principle XI: Documentation Requirements
  - [NEW] Principle XII: Dependency Management
  - [NEW] Principle XIII: Configuration & Secrets Management
  - [NEW] Principle XIV: Error Handling & Resilience
  - [NEW] Principle XV: Manual Testing Requirements
  - [NEW] Principle XVI: Command-Line Development Workflow

Added Sections:
  - Unified SpecKit constitution with DeniDin project constitution
  - All implementation-level requirements now part of specification process

Templates Status:
  ⚠️  spec-template.md - REQUIRES UPDATE: Add deployment strategy, error handling strategy
  ⚠️  plan-template.md - REQUIRES UPDATE: Constitution Check now validates 16 principles
  ⚠️  tasks-template.md - REQUIRES UPDATE: Add feature flag, testing, documentation tasks

Follow-up TODOs:
  - Update all templates to reflect 16 principles
  - Add UTC timezone checks to code review checklist
  - Add feature flag checklist to deployment template
  - Add dependency review process to plan template

Rationale:
  MINOR bump justified as this is an additive change (new principles added).
  Unified SpecKit and DeniDin constitutions to provide single source of truth.
  All implementation requirements now embedded in specification process.
  
  Benefits:
  - Single constitution governs entire development lifecycle
  - Specification and implementation standards aligned
  - No confusion about which rules apply when
  - Complete governance from planning through deployment
═════════════════════════════════════════
-->

# DeniDin SpecKit Constitution

## Core Principles

### I. Specification-First Development

Every feature MUST begin with a complete specification before any implementation starts.

**Non-negotiable requirements:**
- User scenarios with prioritized user stories (P1, P2, P3...) that are independently testable
- Functional requirements with clear acceptance criteria (Given-When-Then format)
- Edge cases and error scenarios explicitly documented
- Each user story MUST be deliverable as a standalone MVP increment

**Rationale:** Specification-first development prevents scope creep, ensures stakeholder
alignment before costly implementation, and enables parallel work streams by clearly
defining deliverable increments.

### II. Template-Driven Consistency

All artifacts MUST follow standardized templates to ensure uniform structure and completeness.

**Non-negotiable requirements:**
- `spec.md` MUST use `.specify/templates/spec-template.md` structure
- `plan.md` MUST use `.specify/templates/plan-template.md` structure
- `tasks.md` MUST use `.specify/templates/tasks-template.md` structure
- Templates MUST include all mandatory sections; optional sections clearly marked
- Placeholder tokens (e.g., `[FEATURE]`, `[DATE]`) MUST be replaced with concrete values
- No deviation from template structure without explicit constitution amendment

**Rationale:** Templates enforce consistency across features, reduce cognitive load for
reviewers, enable automated validation, and ensure critical sections are never omitted.

### III. AI-Agent Collaboration

Development workflow integrates AI agents as first-class collaborators with clearly
defined responsibilities and handoff protocols.

**Non-negotiable requirements:**
- Each agent (`speckit.specify`, `speckit.plan`, `speckit.tasks`, `speckit.implement`,
  `speckit.analyze`, `speckit.clarify`) MUST have documented scope and inputs/outputs
- Agent handoffs MUST be explicit with validation checkpoints
- Human approval REQUIRED at specification and plan completion gates
- Agents MUST NOT modify files outside their designated scope
- Agent guidance files MUST be updated when tech stack changes

**Rationale:** Clear agent boundaries prevent conflicts, enable reliable automation,
and maintain human oversight at critical decision points while maximizing AI leverage
for repetitive tasks.

### IV. Phased Planning & Execution

Feature implementation MUST follow a structured phase progression with validation gates.

**Non-negotiable requirements:**
- **Phase 0: Research** - Technical feasibility, dependency analysis, constraints
- **Phase 1: Design** - Data models, API contracts, quickstart scenarios
- **Phase 2: Task Generation** - Dependency-ordered, user-story-grouped task list
- **Phase 3: Implementation** - Test-Driven Development (TDD) per user story priority
- **Constitution Check** MUST pass before Phase 0; re-check after Phase 1
- No phase may begin until predecessor phase artifacts are complete and approved

**Rationale:** Phased execution reduces rework by catching issues early, enables
incremental delivery, and ensures architecture decisions precede implementation details.

### V. Documentation as Single Source of Truth

All feature context MUST reside in structured markdown documents; code comments are
supplementary only.

**Non-negotiable requirements:**
- `specs/[###-feature]/` directory MUST contain all feature artifacts
- `plan.md` is the technical authority for implementation decisions
- `spec.md` is the functional authority for requirements and acceptance criteria
- `tasks.md` is the execution authority for implementation sequence
- Code MUST NOT contain undocumented assumptions or requirements
- All "NEEDS CLARIFICATION" markers MUST be resolved before implementation

**Rationale:** Centralized documentation prevents knowledge silos, enables onboarding
without code archaeology, and provides durable context beyond transient conversations.

### VI. Test-Driven Development (TDD)

All implementation MUST follow strict test-first methodology with human approval gates.

**Non-negotiable requirements:**
- Every implementation task MUST be split into two sub-tasks:
  - **Task A (Tests)**: Write comprehensive tests covering all acceptance criteria
  - **Task B (Implementation)**: Implement code to pass tests (BLOCKED until Task A approved)
- Tests MUST be reviewed and approved by human before implementation begins
- Once approved, tests are IMMUTABLE without explicit human re-approval
- Test coverage MUST include: happy path, edge cases, error scenarios, boundary conditions
- Manual test checkpoints (acceptance testing) serve as user story approval gates
- No implementation code may be written until its corresponding tests exist and are approved

**Rationale:** TDD ensures code correctness by design, prevents rework from misunderstood
requirements, enables confident refactoring, and provides living documentation of expected
behavior. Human approval of tests before implementation guarantees alignment on acceptance
criteria before costly coding begins.

### VII. Feature Flags for Safe Deployment

All significant new features MUST be deployed behind feature flags to enable safe,
incremental rollouts and quick rollbacks without code redeployment.

**Non-negotiable requirements:**
- Every feature specification MUST include a deployment strategy section
- New features MUST be configurable via feature flags (default: disabled)
- Feature flags MUST be documented in configuration files with clear purpose
- Specifications MUST describe gradual rollout plan (e.g., test env → godfather → all users)
- Code MUST check feature flag state before executing new functionality
- Feature flags SHOULD be removed after feature is stable and fully adopted
- Quick rollback procedure MUST be documented (disable flag without redeployment)

**Rationale:** Feature flags reduce deployment risk by allowing code to reach production
in a disabled state, enable controlled A/B testing and gradual rollouts, provide instant
rollback capability, and separate deployment from feature activation.

### VIII. UTC Timestamp Requirement

All timestamps in code MUST use UTC timezone to prevent time-related bugs and ensure consistency.

**Non-negotiable requirements:**
- ALWAYS use `datetime.now(timezone.utc)` - NEVER `datetime.now()` without timezone
- ALWAYS use `datetime.now(timezone.utc).timestamp()` for Unix timestamps
- Store datetime objects with UTC timezone information
- ISO format logs must include timezone
- Code review must verify all datetime operations use UTC explicitly
- Test fixtures must use `datetime.now(timezone.utc)`

**Rationale:** Consistent timezone usage prevents time-related bugs, simplifies debugging
across distributed systems, and ensures accurate message tracking and log correlation.

### IX. Version Control Workflow

All work MUST be done on feature branches with proper review process.

**Non-negotiable requirements:**
- NEVER push directly to master/main - ALL work on feature branches
- Branch naming: `###-feature-name` or `###-phase#-description`
- Feature branch must match feature directory name
- All tests must pass before creating PR
- PR title format: "Phase X: [Description] Complete"
- Require approval before merge
- Tag releases with semantic versioning: `git tag v1.0.0`
- Use CLI tools (git, gh) for all version control operations

**Rationale:** Feature branches enable proper code review, maintain stable main branch,
enable parallel development, and provide clear audit trail of all changes.

### X. Code Quality Standards

All code MUST maintain high quality and consistency standards.

**Non-negotiable requirements:**
- Linting: Code must pass linting checks (pylint minimum 9.0/10)
- Type Hints: All functions must have type annotations
- Docstrings: All modules, classes, and functions must have Google-style docstrings
- PEP 8 Compliance: Follow Python style guide (120 char line limit)
- Error Handling: All external API calls must have proper error handling
- Logging: Appropriate logging at INFO and DEBUG levels

**Rationale:** Consistent code quality reduces technical debt, improves maintainability,
enables team collaboration, and prevents subtle bugs through type safety and proper documentation.

### XI. Documentation Requirements

Code without documentation is incomplete - all features MUST be properly documented.

**Non-negotiable requirements:**
- README.md - Setup, installation, and basic usage
- DEPLOYMENT.md - Production deployment guide
- CONTRIBUTING.md - How to contribute, coding standards
- API Documentation - For all public interfaces
- Inline Comments - For complex logic or non-obvious code
- Changelog - Track all notable changes between versions

**Rationale:** Complete documentation enables onboarding, reduces knowledge silos,
provides deployment guidance, and ensures long-term maintainability.

### XII. Dependency Management

Dependencies MUST be minimal, secure, and properly managed.

**Non-negotiable requirements:**
- Lock dependency versions in requirements.txt
- Review dependencies for security vulnerabilities
- Minimize external dependencies
- Document why each dependency is needed
- Regular dependency updates (monthly security patches)

**Rationale:** Controlled dependencies reduce security risks, prevent version conflicts,
improve build reproducibility, and minimize supply chain vulnerabilities.

### XIII. Configuration & Secrets Management

Secrets MUST NEVER be committed - all configuration must be externalized.

**Non-negotiable requirements:**
- All secrets in environment variables or external config files
- config.json and similar files must be in .gitignore
- Provide config.example.json with placeholder values
- Validate all configuration at startup
- Log configuration (mask sensitive values)

**Rationale:** Proper secrets management prevents credential leaks, enables environment-specific
configuration, and maintains security compliance.

### XIV. Error Handling & Resilience

Systems MUST fail gracefully and recover automatically when possible.

**Non-negotiable requirements:**
- All API calls must have timeout and retry logic
- Network errors: Retry ONCE on 5xx errors only (1 second wait)
- 4xx client errors are NOT retried
- User-friendly error messages (not stack traces)
- Full error logging with context (DEBUG level)
- Application must never crash from unhandled exceptions
- Only exit on explicit signals (SIGINT, SIGTERM) or startup failures

**Rationale:** Graceful error handling improves user experience, enables automatic recovery
from transient failures, and prevents catastrophic crashes in production.

### XV. Manual Testing Requirements

Automated tests are necessary but not sufficient - manual validation is required.

**Non-negotiable requirements:**
- Manual approval gates at end of each user story phase
- Test with real APIs and services
- Verify user-facing behavior
- Document test scenarios and results
- Real API testing checklist must be completed for external service integrations

**Rationale:** Manual testing catches usability issues, validates real-world behavior,
verifies API integrations, and ensures features meet user expectations.

### XVI. Command-Line Development Workflow

All code management MUST be done via command-line tools for reproducibility.

**Non-negotiable requirements:**
- Git operations via CLI: git add, git commit, git push, git checkout -b
- Pull request management via gh CLI: gh pr create, gh pr merge
- Testing via CLI: pytest commands
- Environment management via CLI: pip, venv
- All code-modifying operations must use CLI tools

**Rationale:** CLI operations are scriptable, automatable, reproducible, and work
consistently across all platforms and CI/CD environments.

## Development Workflow Standards

### Feature Initialization

1. Run `.specify/scripts/bash/create-new-feature.sh` to generate feature directory
   and branch structure
2. Feature directories MUST follow naming: `specs/###-feature-name/`
3. Branch names MUST follow: `###-feature-name` (matching directory)
4. Spec MUST be created via `speckit.specify` agent with user input validation

### Workflow Progression

```text
User Request
    ↓
speckit.specify → spec.md (USER APPROVAL GATE)
    ↓
speckit.clarify (if ambiguities detected)
    ↓
speckit.plan → plan.md + research.md (USER APPROVAL GATE)
    ↓
speckit.plan (Phase 1) → data-model.md + contracts/ + quickstart.md
    ↓
speckit.tasks → tasks.md
    ↓
speckit.analyze (optional validation)
    ↓
speckit.implement → Incremental code delivery by user story
```

### Quality Gates

- Specification complete: All `[NEEDS CLARIFICATION]` resolved
- Constitution compliance: All principles verified in "Constitution Check" section
- Plan approval: Technical stack, architecture, constraints documented
- Tasks ready: Dependency order verified, parallelization marked with `[P]`
- Implementation checkpoint: Each user story independently testable

## Template & Artifact Requirements

### Mandatory Template Sections

**spec.md:**
- User Scenarios & Testing (with priorities)
- Requirements (functional, non-functional)
- Edge Cases

**plan.md:**
- Summary
- Technical Context (language, dependencies, platform, performance goals)
- Constitution Check
- Project Structure (documentation + source code layout)
- Complexity Tracking (only if violations exist)

**tasks.md:**
- Format specification (`[ID] [P?] [Story] Description`)
- Path conventions (adjusted per project type)
- Phases: Setup → Foundational → User Story N (by priority)

### Artifact Consistency Rules

- File paths in `tasks.md` MUST match structure defined in `plan.md`
- Entities in `tasks.md` MUST derive from `data-model.md`
- Endpoints in `tasks.md` MUST derive from `contracts/`
- User stories in `tasks.md` MUST map 1:1 to stories in `spec.md`

## Governance

### Constitution Authority

This constitution is the supreme governing document for the DeniDin SpecKit project.
In any conflict between this constitution and other practices, templates, or
documentation, the constitution prevails.

### Amendment Procedure

1. Proposed changes MUST be documented with:
   - Rationale for change
   - Impact analysis on existing templates and workflows
   - Version bump justification (MAJOR/MINOR/PATCH)
2. Amendments require:
   - Sync Impact Report identifying affected artifacts
   - Update to all dependent templates and agent files
   - Migration plan for in-flight features if applicable
3. Version semantics:
   - **MAJOR**: Backward-incompatible changes (principle removal/redefinition)
   - **MINOR**: Additive changes (new principles, expanded sections)
   - **PATCH**: Clarifications, wording improvements, non-semantic fixes

### Compliance & Review

- All specifications, plans, and task lists MUST undergo "Constitution Check"
- Violations MUST be either corrected or explicitly justified in "Complexity Tracking"
- Unjustified violations block progression to next phase
- Agent files (`.github/agents/*.agent.md`) MUST reference constitution for validation
- Template updates MUST maintain backward compatibility or increment MAJOR version

### Version History

**Version**: 1.2.0 | **Ratified**: 2026-01-15 | **Last Amended**: 2026-01-17

**Changelog**:
- v1.2.0 (2026-01-17): Added Principles VII-XVI (Feature Flags, UTC Timestamps, Version Control, Code Quality, Documentation, Dependencies, Secrets, Error Handling, Manual Testing, CLI Workflow) - unified with DeniDin project constitution
- v1.1.0 (2026-01-15): Added Principle VI (Test-Driven Development), updated Principle IV Phase 3
- v1.0.0 (2026-01-15): Initial constitution ratified with 5 core principles
