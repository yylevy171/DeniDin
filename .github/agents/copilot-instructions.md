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
