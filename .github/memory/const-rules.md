---
id: const-rules
title: CONST - Constitution Rules
created: 2026-02-02T00:00:00Z
updated: 2026-02-02T00:00:00Z
tags: [constitution, standards, rules]
---

# Constitution (CONST) - Core Rules

**NO environment variables** — all configuration in `config/config.json` only.

**UTC timestamps ALWAYS** — use `datetime.now(timezone.utc)` for all time operations. Never use local time or implicit timezones.

**Feature branches ONLY** — never commit or work on `master`. Always create a feature branch: `feature/###-description` or `bugfix/###-description`.

**Feature flags** — new features must be backward compatible and gated behind feature flags. No breaking changes without migration path.

**Branch naming convention:**
- Feature: `feature/###-description` (e.g., `feature/010-proactive-messaging`)
- Bugfix: `bugfix/###-description` (e.g., `bugfix/005-media-file-empty`)

**Config locations:**
- Main: `denidin-app/config/config.json`
- Test: `denidin-app/config/config.test.json`
- Never include `.env`, `.env.local`, or env var references in code.

For the complete constitution, see `.github/CONSTITUTION.md` (CONST).
