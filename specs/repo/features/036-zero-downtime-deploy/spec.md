# Feature Spec: Zero-Downtime Deployment

**Feature ID**: 036-zero-downtime-deploy
**Priority**: Unset — not yet triaged against other backlog items
**Status**: Draft - Needs Clarification (placeholder only, per `speckit.specify` convention used
by Feature 034 — see `b89d686`)
**Created**: August 3, 2026
**Updated**: August 3, 2026

---

## Problem Statement

`scripts/deploy_release.sh` and `scripts/windows_prod/deploy_and_verify.sh` both deploy by
`docker compose up -d`, which stops the currently running container, then creates and starts a
new one from the freshly loaded image. There is a real window — typically a few seconds — where
**no container is running** for that service. There is no blue-green swap, no load balancer, no
traffic draining: it is stop-then-start, not zero-downtime.

This was surfaced 2026-08-03 while designing verified-deploy behavior for `scripts/deploy_release.sh`
(see `specs/in-progress/034-versioning-release-mgmt/` follow-on work and
`specs/035-windows-always-on-prod/`) — the operator asked directly how traffic is handed off
during a deploy, and the honest answer was "it isn't; there's a gap."

**Note (2026-08-03, asymmetry update — see `CLAUDE.md`'s "Environments (dev/prod)" section)**:
`dev` and `prod` now have fully separate WhatsApp numbers / Green API instances / ngrok tunnels /
Green Invoice accounts, so this is purely a *same-environment* deploy problem (old container vs.
new container of the same app+env), not a dev/prod interaction concern.

## Why this isn't a trivial "just add blue-green" fix

The two apps have materially different risk profiles for downtime, discovered during the
2026-08-03 discussion:

- **`morning-mcp-app`**: a real HTTP server (FastMCP over streamable-HTTP, reached via ngrok). Any
  request arriving during the stop/start gap is dropped (connection refused / timeout). This app
  is a natural fit for a standard health-gated blue-green swap — stateless, no polling conflict.
- **`denidin-app`**: `GreenAPIBot` **polls** Green API for notifications rather than receiving
  pushed webhooks. Downtime here is actually harmless today — nothing is "in flight" to drop, the
  bot just resumes polling on restart. **But** a naive blue-green swap (start new container,
  health-check it, *then* stop old) would mean **two containers polling the same Green API
  instance concurrently for a window** — which risks both instances picking up and responding to
  the same notification, i.e. duplicate replies to a real user. So `denidin-app` likely needs to
  keep old-stopped-before-new-started semantics even after this feature ships, unless a
  poll-coordination mechanism (e.g. a lock/lease) is designed alongside it.

This means the eventual design is probably **asymmetric per app**, not a single generic
mechanism reused for both — which is exactly the kind of decision this spec/clarify/plan process
exists to work through deliberately, rather than improvising in a deploy script.

## Explicitly out of scope for this placeholder

This file exists only to reserve the feature number and record the problem statement + the
polling-conflict constraint discovered so far, per the operator's instruction
("Open a feature 36 for this - zero downtime... For now we can continue with the required
contingencies and checks that I mentioned before" — i.e., deprioritized in favor of the
step-by-step verified-deploy work already in progress). No `user-stories.md`, `plan.md`, requirements,
or acceptance criteria exist yet — those require a proper `speckit.specify`/`speckit.clarify`
pass with the operator before any implementation work starts (METHODOLOGY.md §I: user stories are
a MANDATORY, BLOCKING gate before a spec can be approved).

## Open questions for the eventual clarify session

- Is a `morning-mcp-app`-only blue-green swap (leaving `denidin-app` as stop-then-start)
  acceptable as a first increment, or does `denidin-app` need equal treatment from day one?
- If `denidin-app` gets a real zero-downtime mechanism eventually, what's the poll-coordination
  design (lease/lock, staggered start, or something else) that prevents duplicate-reply risk?
- Does this apply to both `dev` and `prod`, or is it prod-only (given `dev`'s downtime is lower
  stakes)?
- Interaction with Feature 035 (Windows box deploy) and Feature 034 (release/deploy scripts) —
  does zero-downtime become a new mode of `deploy_release.sh`, a separate script, or a compose-level
  change (e.g. two service definitions swapped via a proxy)?
