<!--
Sync Impact Report - Constitution Update
═════════════════════════════════════════
Version: Initial → 1.0.0
Status: Initial ratification
Type: MAJOR (new constitution establishment)

Modified Principles:
  - [NEW] Specification-First Development
  - [NEW] Template-Driven Consistency
  - [NEW] AI-Agent Collaboration
  - [NEW] Phased Planning & Execution
  - [NEW] Documentation as Single Source of Truth

Added Sections:
  - Core Principles (5 principles established)
  - Development Workflow Standards
  - Template & Artifact Requirements
  - Governance

Templates Status:
  ✅ plan-template.md - Constitution Check section aligns with principles
  ✅ spec-template.md - User story prioritization aligns with Principle I
  ✅ tasks-template.md - Phased execution aligns with Principle IV
  ⚠️  Future: Monitor agent files for alignment as constitution evolves

Follow-up TODOs:
  - None (all placeholders filled)

Rationale:
  MAJOR bump justified as this is the initial constitution establishment,
  defining the foundational governance model for the DeniDin SpecKit project.
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
- **Phase 3: Implementation** - Incremental delivery per user story priority
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

**Version**: 1.0.0 | **Ratified**: 2026-01-15 | **Last Amended**: 2026-01-15
