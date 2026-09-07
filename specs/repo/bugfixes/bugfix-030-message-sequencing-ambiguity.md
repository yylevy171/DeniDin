# Bugfix Spec: Replies don't say which message they answer

## Bug ID
bugfix-030-message-sequencing-ambiguity

## Title
DeniDin's replies carry no reference to the message they are answering. Benign in
conversation, **materially unsafe at an approval gate**, where the user cannot tell which
pending action a `כן` will authorise.

## Priority
**P2** — real and user-facing, but it degrades clarity rather than corrupting data. Raises the
cost of every other approval-gate defect.

## Status
**Open — backlogged.** No fix designed. Per Bug-Driven Development (METHODOLOGY.md §VII), next
step is human approval of the root cause before test-gap analysis.

## Date Opened
2026-08-09

## Reported By
yaronlev171, from the 7–9 Aug 2026 production review
([`docs/production-analysis/2026-08-09-aug7-9-review.md`](../../docs/production-analysis/2026-08-09-aug7-9-review.md), P2-1).

> **Shared session context** — how this review was run, the read-only access paths, the full
> map of bugfix-028…037, the triage decisions (including what was closed as *not* a bug), and
> the open verification items:
> [`bugfix-028` § Session Context](../done/v0.4.1/bugfix-028-invoicing-and-approval-gate-p0-cluster/bugfix-028-invoicing-and-approval-gate-p0-cluster.md#session-context-2026-08-09-production-review) (now in `specs/done/v0.4.1/`).
> All ten bugs in that set are **fix-forward only** — existing production documents are being
> left as they are by explicit user decision.

## Affected Area
- `apps/denidin-app/src/handlers/whatsapp_handler.py` — `send_response` (no quoted-reply
  support; sends a bare message)
- `apps/denidin-app/src/handlers/ai_handler.py` — `_finalize_response`,
  `_build_pending_approval_fallback_text`

## Description
WhatsApp turns arrive faster than DeniDin answers, and every reply is sent as a **new
standalone message** rather than a reply to a specific one. When two or three threads are open
at once, the user cannot tell what any given answer refers to.

Observed live, session `12e158e2`:

| Time (UTC) | Event |
|---|---|
| 03:21:24 | Pending approval created — `update_client` (טלאל קרעאן phone) |
| 03:22:31 | User sends a **bank screenshot** (new thread) |
| 03:22:40 | User: *"תןציא לו חשבונית"* (third thread) |

Three live threads, none labelled. The pending approval from 03:21:24 was still open, so a
bare `כן` at that point was genuinely ambiguous — to the user *and* to the handler.

This compounds bugfix-028 B3: when the same generic confirmation prompt is re-sent several
times, quoting the message being answered is what would let the user tell attempt #1 from
attempt #4.

## Expected
Replies — at minimum every approval prompt and every tool-result confirmation — should quote
or otherwise reference the specific user message they answer.

## Related Work
- **`specs/in-progress/032-whatsapp-reply-reference-resolution/`** — already scoped for
  resolving inbound WhatsApp reply references. This bug is the **outbound** half; the two
  should be designed together and may collapse into one feature.
- `specs/done/v0.4.1/bugfix-028-invoicing-and-approval-gate-p0-cluster.md` — B3 (approval prompt
  says nothing specific) is the defect this most amplifies.
