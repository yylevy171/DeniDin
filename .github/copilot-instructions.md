# GitHub Copilot Workspace Instructions

## Critical Project Documents

**ALWAYS read these documents at the start of every chat session:**

1. **`.github/quick-ref-constitution.md`** - Quick reference for core constraints (THIS IS LOADED INTO CONTEXT)
2. **`.github/CONSTITUTION.md`** (**CONST**) - Complete coding standards, technical constraints, feature flags, UTC timestamps, version control
3. **`.github/METHODOLOGY.md`** (**METH**) - Development workflow, TDD process, Bug-Driven Development (BDD), agent collaboration
4. **`.github/ARCHITECTURE.md`** - System architecture, components, data flow, integration points
5. **`README.md`** - Project overview, setup instructions, configuration guide

**Use "CONST" to refer to CONSTITUTION.md and "METH" to refer to METHODOLOGY.md in your prompts.**

## Quick Reference

### Methodology (HOW we work)
- Spec-first development with templates
- Phased planning (Research → Design → Tasks → Implementation)
- Strict TDD: Write tests FIRST, get approval, then implement
- Bug-Driven Development: Root cause → Human approval → Test gap analysis → Write failing tests → Approval → Fix

### Constitution (WHAT we enforce)
- **NO environment variables** - all config in `config/config.json`
- **UTC timestamps ALWAYS** - use `datetime.now(timezone.utc)`
- **Feature branches ONLY** - never work on master
- **Feature flags** for new features - backward compatibility required
- Branch naming: `feature/###-description` or `bugfix/###-description`

## When Starting Work

1. Check current branch: `git branch --show-current`
2. If on master, create feature branch immediately
3. Read relevant spec from `specs/` directory
4. Follow BDD workflow for bugs, TDD for features
5. Get human approval at mandatory gates (🚨)

## File Locations

- Specs: `specs/in-progress/###-feature-name/`
- Bugfixes: `specs/bugfixes/bugfix-###-description.md`
- Config: `denidin-app/config/config.json`
- Tests: `denidin-app/tests/unit/` and `denidin-app/tests/integration/`
