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

## Recent Changes
- 019-env-separation: Added Python 3.11 (denidin-app), Python 3.10+ (morning-mcp-app) — unchanged, no application code logic changes beyond config plumbing + Docker + Docker Compose (v2, `docker compose` CLI), ngrok CLI (now baked into the morning-mcp-app image), existing app dependencies unchanged
