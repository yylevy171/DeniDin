# Implementation Plan: WhatsApp AI Chatbot Passthrough

**Branch**: `001-whatsapp-chatbot-passthrough` | **Date**: 2026-01-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-whatsapp-chatbot-passthrough/spec.md`

## Summary

Build a WhatsApp chatbot (DeniDin) that acts as a passthrough relay between WhatsApp Business account and AI chat services (initially ChatGPT). The bot receives messages via Green API, forwards them to the AI service, and returns responses back to WhatsApp. Phase 1 focuses on getting the Green API demo running locally, then customizing it into a stateless message relay system with proper error handling and configuration management.

**Technical Approach**: Clone and build upon the official Green API Python demo chatbot, which already integrates whatsapp-chatbot-python library with ChatGPT. Customize the demo to strip out menu navigation and focus solely on message passthrough functionality while maintaining robust error handling and credential management.

## Technical Context

**Language/Version**: Python 3.8+ (Python 3.11 recommended for optimal compatibility)  
**Primary Dependencies**: 
- `whatsapp-chatbot-python` (Green API chatbot framework)
- `whatsapp-api-client-python` (Green API client library)
- `openai` (ChatGPT API client)
- `python-dotenv` (environment variable management)
- `pyyaml` (configuration file parsing)

**Storage**: File-based state persistence for last processed message ID (prevents duplicate processing on restart); no database required for Phase 1  
**Testing**: pytest for unit/integration tests; manual end-to-end testing via WhatsApp messages  
**Target Platform**: Local development machine (macOS/Linux/Windows) with potential deployment to cloud VM (Linux server)  
**Project Type**: Single Python application (CLI/daemon)  
**Performance Goals**: 
- Respond to WhatsApp messages within 30 seconds (excluding AI service latency)
- Process messages sequentially to maintain conversation order
- Handle up to 100 messages/hour (single-user MVP scale)

**Constraints**: 
- Green API rate limits (varies by subscription tier)
- OpenAI API rate limits and token quotas
- WhatsApp Business API message size limits (4096 characters for text)
- 5-minute inactivity timeout from demo (will be adjusted or removed)

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
- ✅ No "NEEDS CLARIFICATION" markers in spec (all requirements clear)

**Status**: COMPLIANT

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
├── .env.example             # Example environment configuration
├── .gitignore              # Git ignore rules (exclude .env, __pycache__, etc.)
├── README.md               # Setup instructions and usage guide
├── requirements.txt        # Python dependencies
├── bot.py                  # Main entry point (customized from demo)
├── config/                 # Configuration management
│   ├── .env               # Actual credentials (gitignored)
│   └── settings.py        # Configuration loader
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
- ✅ plan.md is technical authority (complete)
- ✅ spec.md is functional authority (unchanged)
- ✅ No undocumented assumptions (all decisions in research.md)

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
