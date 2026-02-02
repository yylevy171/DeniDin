# Copilot Memory Bank

A structured knowledge store for this repository's key facts, standards, and practices. Each entry is a short, focused Markdown file with YAML frontmatter for metadata.

## Usage

Reference this memory bank in your Copilot workflows:

1. **In Copilot Chat** — paste relevant entries from this folder as context or system messages.
2. **In instructions** — reference this folder in `.github/copilot-instructions.md` to load entries as workspace knowledge.
3. **For agents** — agents can read these entries to stay aligned with project standards.
4. **For external tools** — `index.json` provides a manifest for integrations (vector DBs, RAG systems, etc.).

## Adding Entries

Create a new `.md` file in this folder with YAML frontmatter:

```yaml
---
id: unique-id
title: Human-readable title
created: 2026-02-02T00:00:00Z
updated: 2026-02-02T00:00:00Z
tags: [tag1, tag2]
---

# Content here...
```

Then add an entry to `index.json`.

## Current Entries

See `index.json` for the full list and metadata.

- **const-rules.md** — Constitution standards (no env vars, UTC, feature branches, flags).
- **meth-workflow.md** — Methodology (spec-first, TDD/BDD, approval gates).
- **project-structure.md** — Directory layout and key file locations.

## Integration Examples

### Paste into Copilot Chat
Open a Copilot Chat session and paste the relevant entry at the start:

```
System: [paste content from const-rules.md or meth-workflow.md]
```

### Reference in copilot-instructions.md
Add to `.github/copilot-instructions.md`:

```
See the memory bank at `.github/memory/` for CONST rules, METH workflow, and project structure.
```

### Automated Sync (Optional)
Create a script to sync entries to:
- GitHub Gists for sharing.
- A vector DB (e.g., Chroma) for semantic search.
- A wiki or knowledge base tool.

---

This is a local, workspace-level artifact designed to keep project knowledge accessible and in sync with your development workflow.
