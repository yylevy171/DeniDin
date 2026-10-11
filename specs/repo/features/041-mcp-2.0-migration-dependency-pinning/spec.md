# Feature Specification: MCP 2.0 Migration & Dependency Upper-Bound Pinning

**Feature Branch**: `feature/041-mcp-2.0-migration-dependency-pinning`
**Feature ID**: 041-mcp-2.0-migration-dependency-pinning
**Priority**: P2
**Created**: August 5, 2026
**Status**: Draft
**Input**: Follow-up from Feature 038 incident — see Origin below

---

**MANDATORY REQUIREMENT MET**: See `user-stories.md` (this directory) for
Given-When-Then user stories, per METHODOLOGY.md §I/§II.

**This spec complies with**:
- **CONSTITUTION.md** §I (config/dependency handling), §III (feature
  branch workflow).
- **METHODOLOGY.md** §I (user stories mandatory), §II (template
  structure).

---

## Origin

While rebuilding `morning-mcp-app-dev` during Feature 038's session
(2026-08-05), the container failed to start:

```
File "/app/src/denidin_mcp_morning/server.py", line 21, in <module>
    from mcp.server.fastmcp import FastMCP
ModuleNotFoundError: No module named 'mcp.server.fastmcp'
```

**Root cause (confirmed, not guessed)**: `apps/morning-mcp-app/requirements.txt`
pins `mcp>=1.0.0` with no upper bound. The `Dockerfile`'s layer order is
`COPY requirements.txt .` → `RUN pip install -r requirements.txt` →
`COPY . .` — so the `pip install` layer is cached as long as
`requirements.txt`'s content doesn't change. Feature 038's own commit
`2d1aafc` added `tiktoken>=0.5.0` to `requirements.txt`, which invalidated
that cache layer for the first time in a long while. The resulting fresh
`pip install` re-resolved **every** unpinned dependency in the file, not
just `tiktoken` — and `mcp` resolved to the newest available release,
`2.0.0`, which renamed `FastMCP` (`mcp.server.fastmcp`) to `MCPServer`
(`mcp.server.mcpserver`) — a breaking class rename `server.py` wasn't
written against.

The previously-running container had been up for days on an old image
built before `2d1aafc`, whose cached `pip install` layer had resolved
`mcp` to a pre-2.0 version at build time and never re-resolved since —
masking the missing upper bound until the next cache-invalidating
`requirements.txt` change forced a fresh resolve.

**Immediate mitigation (already applied, out of scope for this feature)**:
`requirements.txt` pinned to `mcp>=1.0.0,<2.0.0` to restore known-working
behavior and unblock Feature 038's billed E2E tests. This feature is the
tracked follow-up for the two things intentionally deferred at that time.

## Problem Statement

Two related but separable problems surfaced by this incident:

1. **`mcp` is pinned below 2.0 indefinitely with no migration plan.**
   `mcp` 2.0's `MCPServer` API is presumably where the SDK's development
   continues; staying on `<2.0.0` forever means missing fixes/features and
   accumulating migration debt.
2. **Every other unpinned dependency in `apps/morning-mcp-app/requirements.txt`
   (and possibly `apps/denidin-app/requirements.txt`) carries the same
   latent risk**: a routine, unrelated `requirements.txt` edit can silently
   invalidate the Docker build cache and pull in an untested new major
   version of some other dependency, with no signal until the next rebuild
   breaks in production or dev.

## Scope

### In scope
- Investigate `mcp` 2.0's `MCPServer` API surface (tool registration,
  streamable-HTTP mounting, auth/middleware wiring) against
  `apps/morning-mcp-app/src/denidin_mcp_morning/server.py`'s current usage
  of `FastMCP`.
- Migrate `server.py` (and any other `mcp`-importing code) to `mcp>=2.0.0`,
  with full regression coverage (`apps/morning-mcp-app`'s existing
  integration suite + at least one real dev-environment smoke run) before
  the pin is raised.
- Audit `apps/morning-mcp-app/requirements.txt` and
  `apps/denidin-app/requirements.txt` for unpinned dependencies; decide and
  apply a consistent upper-bound pinning convention (e.g. pin major
  versions, `~=` compatible-release pins, or a resolved lockfile
  mechanism) to prevent this failure mode recurring for any dependency.

### Out of scope
- Re-litigating the `mcp<2.0.0` mitigation already applied under Feature
  038 — that stays as-is until this feature's migration lands.
- Any other Feature 038 work (list_invoices pagination/token-budget fix,
  billed E2E test suite split) — unrelated, already delivered separately.

## Success Criteria

- `apps/morning-mcp-app` runs on `mcp>=2.0.0` in dev, with its full test
  suite green and a real dev-environment smoke run (tunnel + `/health` +
  at least one real tool call) confirmed working.
- Both apps' `requirements.txt` files have an explicit, documented pinning
  convention applied consistently, such that a future unrelated
  `requirements.txt` edit cannot silently pull in an unvetted new major
  version of an unrelated dependency.
