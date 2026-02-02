---
id: project-structure
title: DeniDin Project Structure & Key Locations
created: 2026-02-02T00:00:00Z
updated: 2026-02-02T00:00:00Z
tags: [project, structure, layout, locations]
---

# Project Structure

**Root Directories**
- `denidin-app/` — main application code, config, tests, data.
- `specs/` — requirements, specs, and design docs.
- `.github/` — GitHub-specific config, workflows, agents, memory bank.

**App Structure** (`denidin-app/`)
- `src/` — Python source code (handlers, managers, services, models, utils, constants).
- `tests/` — unit and integration tests.
  - `tests/unit/` — unit tests.
  - `tests/integration/` — integration tests.
  - `tests/fixtures/` — test fixtures.
- `config/` — configuration files.
  - `config.json` — production config (no env vars).
  - `config.test.json` — test config.
- `data/` — runtime data.
  - `data/memory/` — Chroma vector DB and session memory.
  - `data/media/` — media files.
  - `data/sessions/` — session state.

**Specs Structure** (`specs/`)
- `in-progress/` — active feature specs.
- `bugfixes/` — bug fix specs and tracking.
- `done/` — completed feature specs.
- `P0/`, `P1/`, `P2/` — priority-tagged specs.

**GitHub Config** (`.github/`)
- `CONSTITUTION.md` (CONST) — coding standards.
- `METHODOLOGY.md` (METH) — development workflow.
- `agents/` — Copilot custom agents.
- `memory/` — knowledge bank (this folder).
- `workflows/` — GitHub Actions CI/CD.

**Key Files**
- `denidin-app/denidin.py` — main entry point.
- `denidin-app/requirements.txt` — Python dependencies.
- `denidin-app/pytest.ini` — pytest config.
- `README.md` — project overview.
