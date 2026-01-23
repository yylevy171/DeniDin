# DeniDin

A WhatsApp AI assistant with semantic memory and conversation management.

## Overview

DeniDin is a production WhatsApp application powered by OpenAI GPT-4o-mini with an advanced two-tier memory system: short-term conversation history (SessionManager) and long-term semantic memory (ChromaDB). The application maintains context across conversations and recalls relevant information automatically.

## Current Status

**Version**: 1.0 (Production) + Memory System (Phase 6 Complete)
- ✅ WhatsApp integration via Green API
- ✅ AI responses via OpenAI GPT-4o-mini
- ✅ Session management with UUID-based conversations
- ✅ ChromaDB semantic memory with automatic recall
- ✅ Startup recovery for orphaned sessions
- ✅ Automatic session transfer to long-term memory on 24h expiration
- ✅ Data root configuration for test/prod separation
- ✅ Sender/recipient tracking for proper message attribution
- ✅ Application management scripts (run_denidin.sh, stop_denidin.sh)
- ✅ 322 unit tests passing, 4 skipped; 89 integration tests passing
- ✅ Bugfixes 001-004 complete (constitution loading, removed unused config, data_root path construction)
- 🚀 Application deployed and running in production

**Memory System**: Phases 1-6 complete (PR #20 merged to master)
- Feature flag: `enable_memory_system` (default: disabled for safe deployment)
- Next: Phase 7-10 (integration testing, documentation, validation, production enablement)

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
