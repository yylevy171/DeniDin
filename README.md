# DeniDin

A WhatsApp AI assistant with semantic memory, role-based access control, and conversation management.

## Overview

DeniDin is a production WhatsApp application powered by OpenAI GPT-4o-mini with an advanced two-tier memory system: short-term conversation history (SessionManager) and long-term semantic memory (ChromaDB). The application maintains context across conversations, recalls relevant information automatically, and enforces role-based permissions for different user types.

## Current Status

**Version**: 1.0 (Production)

### Code Quality
- 📊 **Pylint Score**: 9.81/10 (improved from 6.55/10)
- ✅ **Test Coverage**: 90% (1,092 statements, 110 missed)
- ✅ **Tests Passing**: 391 tests, 4 skipped
- 🧹 **Code Standards**: Trailing whitespace removed, imports organized, encoding specified
- 📧 **CI/CD**: Email notifications reduced (CI only runs on PRs)

### Production Features
- ✅ WhatsApp integration via Green API
- ✅ AI responses via OpenAI GPT-4o-mini
- ✅ Session management with UUID-based conversations
- ✅ ChromaDB semantic memory with automatic recall
- ✅ Role-Based Access Control (RBAC) with 4 user roles
- ✅ Token-based session limits per role
- ✅ Memory scope filtering (public, private, system)
- ✅ Startup recovery for orphaned sessions
- ✅ Automatic session cleanup and archival (24h expiration)
- ✅ Background thread for session transfer to long-term memory
- ✅ Data root configuration for test/prod separation
- ✅ Sender/recipient tracking for proper message attribution
- ✅ Application management scripts (run, stop, restart)
- 🚀 Application deployed and running in production

### Feature Implementation Status

**✅ Completed Features** (in `specs/done/`):
1. ✅ **001 - WhatsApp Chatbot Passthrough** - Core messaging infrastructure
2. ✅ **002 - Chat Session Management** - UUID-based session tracking
3. ✅ **006 - RBAC User Roles** - 4-tier role system (Admin, Godfather, Client, Blocked)
4. ✅ **007 - Persistent Context Memory** - ChromaDB long-term semantic memory
5. ✅ **010 - Rename OpenAI to AI** - Generic AI handler abstraction
6. ✅ **011 - Rename BotConfiguration to AppConfiguration** - Terminology cleanup
7. ✅ **012 - Update Bot Terminology to App** - Consistent naming across codebase
8. ✅ **002-007 - Memory System** - Complete two-tier memory architecture

**🚧 In Progress** (in `specs/in-progress/`):
- **003 - Media Document Processing** - Image and document handling

**📋 Planned** (in `specs/in-definition/`, `specs/P0/`, `specs/P1/`, `specs/P2/`):
- 013 - Proactive WhatsApp Messaging Core
- 014 - Entity Extraction Group Messages
- 015 - Topic-Based Access Control
- 005 - MCP Morning Green Receipt
- 008 - Scheduled Proactive Chats
- 009 - Agentic Workflow Builder

## Architecture

### Memory System

DeniDin implements a sophisticated two-tier memory architecture:

**Tier 1: Session Manager (Short-term)**
- UUID-based conversation tracking
- Per-user message history with role-based token limits
- Automatic token pruning to stay within limits
- 24-hour session expiration with archival
- Message persistence in JSON format

**Tier 2: Memory Manager (Long-term)**
- ChromaDB vector database for semantic search
- Per-entity collection architecture
- OpenAI embeddings (text-embedding-3-small)
- Memory scopes: PUBLIC, PRIVATE, SYSTEM
- Automatic session transfer on expiration

**Background Processing**
- SessionCleanupThread monitors expired sessions
- 4-step atomic cleanup process:
  1. Archive session files to `expired/YYYY-MM-DD/`
  2. Transfer to ChromaDB via AI handler
  3. Remove from active index
  4. Mark as transferred

### Role-Based Access Control (RBAC)

Four user roles with different permissions and limits:

| Role | Token Limit | Memory Access | System Access |
|------|-------------|---------------|---------------|
| **Admin** | Unlimited | ALL (public, private, system) | ✅ Yes |
| **Godfather** | 100,000 | ALL private + public | ❌ No |
| **Client** | 4,000 | Own private + public | ❌ No |
| **Blocked** | 0 | None | ❌ No |

### Test Coverage Details

**100% Coverage** (7 modules):
- ✅ config/media_config.py
- ✅ models/document.py, message.py, state.py, user.py
- ✅ utils/state.py, user_manager.py

**90%+ Coverage** (4 modules):
- ⭐ models/config.py (97%)
- ⭐ memory/memory_manager.py (96%)
- ⭐ memory/session_manager.py (93%)
- ⭐ utils/logger.py (93%)

**80%+ Coverage** (1 module):
- 🔶 handlers/ai_handler.py (88%)

**Needs Improvement** (2 modules):
- ⚠️ handlers/whatsapp_handler.py (70%)
- ⚠️ background_threads.py (66%)

## Governance

This project is governed by the [Constitution](.specify/memory/constitution.md), which defines the core principles, workflow standards, and quality gates for all development work.

### Core Principles

1. **Specification-First Development** - Every feature begins with a complete spec
2. **Template-Driven Consistency** - All artifacts follow standardized templates
3. **AI-Agent Collaboration** - Clear agent boundaries with validation checkpoints
4. **Phased Planning & Execution** - Structured progression with quality gates
5. **Documentation as Single Source of Truth** - Centralized feature context

## Workflow

The standard feature development flow:

```text
User Request
    ↓
speckit.specify → spec.md (APPROVAL GATE)
    ↓
speckit.clarify (if needed)
    ↓
speckit.plan → plan.md + research.md (APPROVAL GATE)
    ↓
speckit.plan (Phase 1) → data-model.md + contracts/ + quickstart.md
    ↓
speckit.tasks → tasks.md
    ↓
speckit.analyze (optional)
    ↓
speckit.implement → Incremental delivery by user story
```

## Getting Started

### Prerequisites

- Python 3.9+
- WhatsApp account with Green API credentials
- OpenAI API key
- ChromaDB (installed via requirements.txt)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yylevy171/DeniDin.git
   cd DeniDin/denidin-app
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure the application:
   ```bash
   cp config/config.example.json config/config.json
   # Edit config.json with your API credentials
   ```

4. Run the application:
   ```bash
   ./run_denidin.sh
   ```

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=term-missing --cov-report=html

# Run pylint
python -m pylint src/
```

### Creating a New Feature

1. Initialize the feature structure:
   ```bash
   .specify/scripts/bash/create-new-feature.sh
   ```

2. Create the specification using the `speckit.specify` agent

3. Follow the workflow progression through planning, task generation, and implementation

### Templates

All templates are located in `.specify/templates/`:
- `spec-template.md` - Feature specifications
- `plan-template.md` - Technical planning and design
- `tasks-template.md` - Implementation task lists
- `agent-file-template.md` - Agent command structure
- `checklist-template.md` - Validation checklists

## Available Agents

- **speckit.specify** - Create feature specifications
- **speckit.clarify** - Resolve specification ambiguities
- **speckit.plan** - Generate technical plans and design artifacts
- **speckit.tasks** - Create dependency-ordered task lists
- **speckit.implement** - Execute incremental implementation
- **speckit.analyze** - Validate consistency across artifacts
- **speckit.constitution** - Update project constitution
- **speckit.checklist** - Generate domain checklists
- **speckit.taskstoissues** - Convert tasks to GitHub issues

## Project Structure

```
DeniDin/
├── .specify/
│   ├── memory/
│   │   └── constitution.md       # Project governance
│   ├── templates/                # All document templates
│   └── scripts/                  # Automation scripts
├── .github/
│   └── agents/                   # AI agent definitions
└── specs/                        # Feature specifications
    └── ###-feature-name/
        ├── spec.md
        ├── plan.md
        ├── tasks.md
        └── [design artifacts]
```

## License

[Add license information]
