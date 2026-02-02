---
id: meth-workflow
title: METH - Development Methodology & Workflow
created: 2026-02-02T00:00:00Z
updated: 2026-02-02T00:00:00Z
tags: [methodology, workflow, tdd, bdd, approval]
---

# Methodology (METH) - Development Workflow

**Spec-First Development**
- Write requirements spec before code. Use templates from `specs/` directory.
- Phased approach: Research → Design → Tasks → Implementation.

**TDD (Test-Driven Development)**
- For features: Write tests FIRST, get approval (🚨 gate), then implement.
- Write failing test → get approval → implement to pass → refactor.

**BDD (Bug-Driven Development)**
- For bugfixes: Root cause analysis → human approval → test gap analysis → write failing tests → approval → fix.
- Document why the bug occurred; ensure test prevents regression.

**Git Workflow**
- Always work on feature branches, never `master`.
- Small, atomic commits with clear messages.
- Create PRs for peer review.

**Mandatory Approval Gates (🚨)**
- Before implementing features, get approval on: spec, test design, and architectural changes.
- Use explicit gates in specs and comments to mark approval requirements.

**Spec locations**
- In-progress features: `specs/in-progress/###-feature-name/`
- Bugfixes: `specs/bugfixes/bugfix-###-description.md`
- Completed: `specs/done/`

For complete methodology, see `.github/METHODOLOGY.md` (METH).
