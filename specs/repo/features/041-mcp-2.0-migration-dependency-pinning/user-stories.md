# User Stories: MCP 2.0 Migration & Dependency Upper-Bound Pinning

Feature ID: 041-mcp-2.0-migration-dependency-pinning

---

## US1: Migrate to `mcp` 2.0's `MCPServer` API

**As** a developer maintaining `apps/morning-mcp-app`,
**I want** `server.py` to run on `mcp>=2.0.0` using its `MCPServer` API,
**so that** the app stays current with the SDK instead of being pinned
below 2.0 indefinitely.

**Given** `apps/morning-mcp-app/src/denidin_mcp_morning/server.py` currently
imports `FastMCP` from `mcp.server.fastmcp` (an API removed in `mcp` 2.0.0),
**When** the migration is complete,
**Then** `server.py` imports and uses `MCPServer` from
`mcp.server.mcpserver` (or whatever the confirmed 2.0-era equivalent is)
with feature parity — all 11 tools registered, streamable-HTTP transport,
`BearerTokenMiddleware` auth, and the unauthenticated `/health` route all
still working exactly as before.

**Given** the migration is applied to a dev build,
**When** `apps/morning-mcp-app`'s full test suite is run and a real
dev-environment smoke test is performed (start the container, confirm the
ngrok tunnel status file shows `"status": "running"`, hit `/health`, and
make one real tool call end-to-end),
**Then** all tests pass and the smoke test succeeds before `requirements.txt`'s
pin is raised to `mcp>=2.0.0`.

## US2: Consistent dependency upper-bound pinning

**As** a developer relying on Docker layer caching for fast, predictable
builds,
**I want** every dependency in `apps/morning-mcp-app/requirements.txt` and
`apps/denidin-app/requirements.txt` to have an explicit, intentional upper
bound (or an equivalent lockfile-based guarantee),
**so that** an unrelated `requirements.txt` edit can never silently
invalidate the Docker build cache and pull in an untested new major version
of some other, unrelated dependency.

**Given** `requirements.txt` in either app currently has one or more
dependencies pinned with only a lower bound (e.g. `requests>=2.31.0`),
**When** this story is complete,
**Then** every such dependency has a documented upper bound consistent
with whatever convention is chosen (e.g. `~=`, an explicit `<N.0.0` per
dependency, or a resolved/locked requirements file), with a comment
explaining why for any pin that isn't self-evident.

**Given** the new pinning convention is in place,
**When** a future `requirements.txt` edit adds or changes one dependency
(as Feature 038's `tiktoken>=0.5.0` addition did),
**Then** rebuilding the image does not silently re-resolve any *other*
dependency to an untested new major version — the exact failure mode this
feature exists to close off (see `spec.md`'s Origin section for the
concrete 2026-08-05 incident this reproduces).
