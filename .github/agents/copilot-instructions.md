---
name: copilot-instructions
description: "Workspace Copilot instructions that prefer the Principal Software Engineer agent for engineering guidance."
applyTo: "**/*"
---

# Workspace Copilot Instructions

This file is loaded as a workspace-level Copilot instruction. When providing software engineering guidance for this repository, prefer the `principal-software-engineer` agent located at `.github/agents/principal-software-engineer.agent.md`.

If the agent list does not show `principal-software-engineer`, use one of the following fallbacks:

- Mention the agent explicitly in chat by starting your message with `@principal-software-engineer`.
- Paste the agent instructions into the chat as a system prompt (copy contents of `.github/agents/principal-software-engineer.agent.md`).

Note: After adding this file, reload your editor window so Copilot can re-index workspace agents and instructions.

## Active Technologies
- Python 3.11 (denidin-app), Python 3.10+ (morning-mcp-app) — unchanged, no application code logic changes beyond config plumbing + Docker + Docker Compose (v2, `docker compose` CLI), ngrok CLI (now baked into the morning-mcp-app image), existing app dependencies unchanged (019-env-separation)
- Filesystem — per-environment `config.<env>.json`, per-environment data root (`data/` prod, `dev_data/` dev for denidin-app), per-environment log directories, per-environment shared bind-mounted status-file directories (019-env-separation)
- Python 3.11 (both apps) — `APScheduler` (`BackgroundScheduler` + `CronTrigger`), ChromaDB, `sqlite3` (roll-marker store + chat index), OpenAI Responses API; rolling 14-day verbatim memory window + nightly 02:00 Israel-local daily-summary roll, one long-lived `Session` per chat, archive-only trimming, `TimedRotatingFileHandler` log retention (070-rolling-memory-window)
- Bash (matching every other `scripts/`/`scripts/windows_prod/`/`scripts/health_monitoring/` script) — `sqlite3` CLI (hot SQLite `.backup`), `tar`/`gzip`, `rsync`/`scp` over the existing `denidin-winprod` SSH alias, `schtasks.exe` via WSL2 (078-prod-daily-backups)
- Filesystem only — `.tgz` archives in `denidin daily backups/`/`denidin monthly backups/` folders per host, no new database or app-level persisted model (078-prod-daily-backups)
- Python 3.11 (matches `apps/morning-mcp-app`'s existing stack) + stdlib `sqlite3` (no new dependency — matches `reminders.db`'s (072-morning-client-name-cache)
- New SQLite file, `apps/morning-mcp-app/data/client_cache.db` (one table, (072-morning-client-name-cache)

## Recent Changes
- 019-env-separation: Added Python 3.11 (denidin-app), Python 3.10+ (morning-mcp-app) — unchanged, no application code logic changes beyond config plumbing + Docker + Docker Compose (v2, `docker compose` CLI), ngrok CLI (now baked into the morning-mcp-app image), existing app dependencies unchanged
