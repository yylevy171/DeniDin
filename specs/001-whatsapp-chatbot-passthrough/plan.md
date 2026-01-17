# Implementation Plan: WhatsApp AI Chatbot Passthrough

**Branch**: `001-whatsapp-chatbot-passthrough` | **Date**: 2026-01-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-whatsapp-chatbot-passthrough/spec.md`

## Summary

Build a WhatsApp chatbot (DeniDin) that acts as a passthrough relay between WhatsApp Business account and AI chat services (initially ChatGPT). The bot receives messages via Green API polling mechanism, forwards them to the AI service sequentially, and returns responses back to WhatsApp. Phase 1 focuses on getting the Green API demo running locally, then customizing it into a stateless message relay system with proper error handling, JSON/YAML configuration management, and truncation of long AI responses.

**Technical Approach**: Clone and build upon the official Green API Python demo chatbot, which already integrates whatsapp-chatbot-python library with ChatGPT. Customize the demo to strip out menu navigation and focus solely on message passthrough functionality while maintaining robust error handling and credential management.

## Clarifications Applied

The following technical decisions were made during specification clarification (Session 2026-01-15) and are reflected throughout this plan:

1. **Configuration Storage**: JSON/YAML config file (gitignored) instead of environment variables - enables structured configuration with polling interval and log level settings
2. **Message Reception**: Polling via Green API `receiveNotification` API with configurable interval (default: 5 seconds) - simpler than webhooks for Phase 1
3. **Concurrency Model**: Sequential processing via single-threaded queue - maintains strict message ordering, simpler implementation, sufficient for ~100 msg/hr capacity
4. **Logging Strategy**: INFO level for application events (messages, errors), DEBUG level for detailed flow (parsing, state, API details)
5. **Long Message Handling**: Truncate AI responses at 4000 characters and append "..." indicator - defers multi-message splitting to Phase 2

These clarifications have been incorporated into: Technical Context, Project Structure (config file format), BotConfiguration entity (polling_interval, log_level attributes), and AIResponse entity (is_truncated flag, truncate_for_whatsapp() method).

## Technical Context

**Language/Version**: Python 3.8+ (Python 3.11 recommended for optimal compatibility)  
**Primary Dependencies**: 
- `whatsapp-chatbot-python` (Green API chatbot framework)
- `whatsapp-api-client-python` (Green API client library)
- `openai` (ChatGPT API client)
- `pyyaml` (JSON/YAML configuration file parsing)
- `pytest` (testing framework)

**Storage**: 
- JSON/YAML config file (gitignored) for credentials, polling interval, log level
- File-based state persistence for last processed message ID (prevents duplicate processing on restart)
- No database required for Phase 1

**Testing**: pytest for unit/integration tests; manual end-to-end testing via WhatsApp messages  
**Target Platform**: Local development machine (macOS/Linux/Windows) with potential deployment to cloud VM (Linux server)  
**Project Type**: Single Python application (CLI/daemon)  
**Performance Goals**: 
- Respond to WhatsApp messages within 30 seconds (excluding AI service latency)
- Process messages sequentially via single-threaded queue to maintain strict ordering
- Handle up to 100 messages/hour (sequential processing capacity)
- Poll Green API at configurable interval (default: every 5 seconds)

**Constraints**: 
- Green API rate limits (varies by subscription tier)
- OpenAI API rate limits and token quotas
- WhatsApp Business API message size limits (4096 characters for text - truncate at 4000 chars + "...")
- Polling-based message reception (not webhook-based for Phase 1)
- Sequential message processing (single-threaded queue)
- Logging levels: INFO (application events, messages, errors), DEBUG (parsing, state, API details)

**Scale/Scope**: 
- Phase 1: Single WhatsApp business account
- Single bot instance (no multi-tenancy)
- Stateless per-message processing (no conversation memory in Phase 1)
- ~500 lines of Python code (based on demo size)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Specification-First Development ✅

- ✅ Complete spec.md with prioritized user stories (P1-P4)
- ✅ Each user story independently testable (P1: demo works, P2: passthrough, P3: error handling, P4: config)
- ✅ Given-When-Then acceptance criteria provided
- ✅ Edge cases documented (long messages, rate limits, group chats, etc.)
- ✅ Each story deliverable as standalone MVP increment

**Status**: COMPLIANT

### Principle II: Template-Driven Consistency ✅

- ✅ spec.md follows `.specify/templates/spec-template.md` structure
- ✅ plan.md follows `.specify/templates/plan-template.md` structure
- ✅ All placeholder tokens being replaced with concrete values
- ✅ Mandatory sections present (User Scenarios, Requirements, Success Criteria)

**Status**: COMPLIANT

### Principle III: AI-Agent Collaboration ✅

- ✅ Following speckit.plan agent workflow
- ✅ Human approval gate at specification completion (spec.md reviewed)
- ✅ Human approval gate will be enforced at plan completion
- ✅ Agent scope respected (plan.md generation only, no implementation yet)

**Status**: COMPLIANT

### Principle IV: Phased Planning & Execution ✅

- ✅ Phase 0 (Research): Completed - Green API demo analyzed, dependencies identified, constraints documented
- ⏳ Phase 1 (Design): In progress - will generate data-model.md, contracts/, quickstart.md
- ⏳ Phase 2 (Task Generation): Pending - tasks.md via speckit.tasks
- ⏳ Phase 3 (Implementation): Pending - incremental delivery by user story priority
- ✅ Constitution Check passing before Phase 0

**Status**: COMPLIANT (phases progressing correctly)

### Principle V: Documentation as Single Source of Truth ✅

- ✅ All artifacts in `specs/001-whatsapp-chatbot-passthrough/` directory
- ✅ plan.md will be technical authority
- ✅ spec.md is functional authority
- ✅ tasks.md will be execution authority (not yet created)
- ✅ No "NEEDS CLARIFICATION" markers in spec (all clarifications resolved)

**Status**: COMPLIANT

### Principle VI: Test-Driven Development (TDD) ✅

- ✅ Two-tier testing strategy will be applied per CONSTITUTION:
  - **Tier 1 (Mocked Tests)**: Fast unit/integration tests with mocked APIs for development
  - **Tier 2 (Real API Tests)**: Actual API connectivity tests for deployment validation
- ✅ All tests written and approved BEFORE implementation (a-tasks before b-tasks)
- ✅ Real API tests will validate: Green API connection, OpenAI API calls, complete E2E flow
- ✅ Tests must pass before PR creation

**Status**: COMPLIANT

### Principle VII: Version Control Workflow ✅

- ✅ Feature branch workflow enforced per CONSTITUTION
- ✅ ALL work done on feature branches (NEVER push directly to master)
- ✅ Each phase has dedicated feature branch (001-phase#-description)
- ✅ Branch created BEFORE starting work on each phase
- ✅ All changes merged via Pull Request with review
- ✅ Master branch is protected (requires PR)

**Status**: COMPLIANT

### Principle VI: Test-Driven Development (TDD) ✅

- ✅ tasks.md will split implementation into test tasks (T###a) and implementation tasks (T###b)
- ✅ Human approval gate will be enforced between test writing and implementation
- ✅ Tests will be immutable once approved (no changes without re-approval)
- ✅ All acceptance criteria from spec.md will be covered by tests before implementation

**Status**: COMPLIANT (will be enforced in Phase 2 task generation)

**Overall Gate Status**: ✅ PASS - Ready for Phase 1 Design

## Project Structure

### Documentation (this feature)

```text
specs/001-whatsapp-chatbot-passthrough/
├── spec.md              # Feature specification (completed)
├── plan.md              # This file (in progress)
├── research.md          # Phase 0: Green API integration research
├── data-model.md        # Phase 1: Message and configuration entities
├── quickstart.md        # Phase 1: Setup and test scenarios
├── contracts/           # Phase 1: API interaction patterns
│   ├── green-api.md     # WhatsApp API contract
│   └── openai-api.md    # ChatGPT API contract
└── tasks.md             # Phase 2: Implementation task list (via speckit.tasks)
```

### Source Code (repository root)

```text
denidin-bot/                 # Root project directory
├── config.example.json      # Example configuration file (template)
├── .gitignore              # Git ignore rules (exclude config.json, config.yaml, __pycache__, etc.)
├── README.md               # Setup instructions and usage guide
├── requirements.txt        # Python dependencies
├── bot.py                  # Main entry point (customized from demo)
├── config/                 # Configuration management
│   ├── config.json         # Actual credentials & settings (gitignored, JSON or YAML format)
│   └── settings.py        # Configuration loader (supports JSON/YAML)
├── src/                   # Source code
│   ├── __init__.py
│   ├── handlers/          # Message handlers
│   │   ├── __init__.py
│   │   ├── whatsapp_handler.py    # WhatsApp message processing
│   │   └── ai_handler.py          # AI service integration
│   ├── models/            # Data models
│   │   ├── __init__.py
│   │   ├── message.py     # WhatsAppMessage, AIRequest, AIResponse
│   │   └── config.py      # BotConfiguration
│   └── utils/             # Utility functions
│       ├── __init__.py
│       ├── logger.py      # Logging configuration
│       └── state.py       # State persistence (last message ID)
├── tests/                 # Test suite
│   ├── __init__.py
│   ├── unit/              # Unit tests
│   │   ├── test_handlers.py
│   │   └── test_models.py
│   ├── integration/       # Integration tests
│   │   ├── test_green_api.py
│   │   └── test_openai.py
│   └── fixtures/          # Test fixtures and mocks
│       └── sample_messages.json
└── logs/                  # Application logs (gitignored)
    └── denidin.log
```

**Structure Decision**: Single Python project (Option 1) chosen because:
- Monolithic bot application (no frontend/backend split)
- All logic in one process (message relay + AI integration)
- Simple deployment model (single script execution)
- Green API demo uses similar flat structure with `bot.py` entry point

**Differences from Demo**: 
- Demo has minimal structure (bot.py + config/ + internal/)
- DeniDin adds explicit `src/` organization for better modularity
- Separates handlers, models, and utils for testability
- Adds comprehensive test structure (demo has no tests)

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations. All constitutional principles are satisfied.

---

## Phase 1 Completion Summary

**Artifacts Generated**:
- ✅ `research.md` - Green API and OpenAI integration research, technical decisions
- ✅ `data-model.md` - Five core entities (WhatsAppMessage, AIRequest, AIResponse, BotConfiguration, MessageState)
- ✅ `contracts/green-api.md` - Green API notification and sending API contracts
- ✅ `contracts/openai-api.md` - OpenAI Chat Completions API contract
- ✅ `quickstart.md` - Step-by-step setup guide with test scenarios

**Technical Decisions**:
1. Use Green API demo libraries (not direct code copy due to CC BY-ND license)
2. Polling-based message receiving (simpler for Phase 1)
3. Stateless message processing (no conversation history)
4. Exponential backoff retry strategy for API errors
5. Python logging with file rotation

**Ready for Phase 2**: Task generation via `speckit.tasks` command

---

## Post-Phase 1 Constitution Re-Check

### Principle I: Specification-First Development ✅

No changes from initial check. Spec remains complete and unchanged.

### Principle II: Template-Driven Consistency ✅

- ✅ plan.md fully populated (no placeholders remaining)
- ✅ All Phase 1 artifacts follow expected structure
- ✅ data-model.md includes entity diagrams and Python representations
- ✅ contracts/ contains detailed API specifications
- ✅ quickstart.md provides executable setup instructions

### Principle III: AI-Agent Collaboration ✅

- ✅ Phase 0 and Phase 1 completed by speckit.plan agent
- ⏳ Awaiting human approval before Phase 2 (tasks.md generation)
- ✅ No files modified outside designated scope (only specs/001-*/)

### Principle IV: Phased Planning & Execution ✅

- ✅ Phase 0: Research completed (Green API integration analysis)
- ✅ Phase 1: Design completed (data models, contracts, quickstart)
- ⏳ Phase 2: Pending - tasks.md generation
- ⏳ Phase 3: Pending - implementation

### Principle V: Documentation as Single Source of Truth ✅

- ✅ All artifacts in `specs/001-whatsapp-chatbot-passthrough/`
- ✅ plan.md is technical authority (complete with clarifications)
- ✅ spec.md is functional authority (5 clarifications incorporated)
- ✅ No undocumented assumptions (all decisions in research.md and clarifications)

### Principle VI: Test-Driven Development (TDD) ✅

- ✅ Phase 2 tasks.md will enforce TDD task pairs (T###a tests, T###b implementation)
- ✅ Human approval gates will be documented in tasks.md
- ✅ Test immutability will be enforced through version control and review process
- ✅ Acceptance criteria from spec.md provide clear test requirements

**Overall Gate Status**: ✅ PASS - Ready for Human Approval & Phase 2

---

## Human Approval Gate

**Required Actions**:
1. Review `plan.md` technical context and decisions
2. Review `research.md` for Green API integration approach
3. Verify `data-model.md` entities match requirements
4. Validate `contracts/` API specifications
5. Test `quickstart.md` setup instructions (optional before approval)

**Approval Options**:
- ✅ **Approve**: Proceed to Phase 2 (run `speckit.tasks` to generate tasks.md)
- 🔄 **Request Changes**: Identify specific sections to revise
- ❌ **Reject**: Return to spec.md for requirements clarification

**Once Approved**: Execute `@speckit.tasks` to generate dependency-ordered implementation tasks.
