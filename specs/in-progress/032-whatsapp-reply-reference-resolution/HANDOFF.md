# Handoff: WhatsApp Reply/Quote Reference Resolution (Feature 032)

**As of**: 2026-08-07. Moved `specs/backlog/` → `specs/in-progress/` this same day (this
handoff moved with it). Planning complete (`speckit.specify` → `speckit.clarify` →
`speckit.plan` → `speckit.tasks` → `speckit.analyze`, all done 2026-08-04/05, PR #194 merged
to `master`). **Zero implementation code written.** Next step for whoever picks this up:
`speckit.implement`, starting at `tasks.md`'s Phase 1.

**Session note**: after this feature's planning finished, the same session briefly switched
to scope Feature 027 (Mandatory Reference to an Existing Client for Invoicing) before coming
back to 032. Feature 027 ended up fully implemented and shipped in that detour (PR #201,
merged, spec now in `specs/done/v0.3.0/027-mandatory-client-reference-invoicing/`) — unrelated to
032's design, but explains the gap between 032's planning finishing (2026-08-04/05) and this
handoff/in-progress move (2026-08-07). Nothing about 032 changed during that gap — this
handoff's content is otherwise identical to the version written right after planning
finished.

## What this feature is

Resolve a WhatsApp reply/quote back to the internal DeniDin message it refers to — general
infrastructure, no cancellation/modification behavior (that's Feature 040, which depends on
this). Motivated by a real use case (replying "לבטל" to a message that stated a fee
agreement) but scoped to just the resolution primitive itself. See `spec.md`'s Split History
for why 032 and 040 are two features, not one.

## Where every artifact stands

| File | Status | Key content |
|---|---|---|
| `spec.md` | CLARIFIED | Scope, Q1/Q2/Q9/Q10/Q11 all resolved, Clarifications section has the session log |
| `user-stories.md` | CLARIFIED | US1 (P1, 8 acceptance scenarios) + US2 (P2, regression guard) |
| `plan.md` | Done | Technical Context, Constitution Check (PASS, no violations), Project Structure |
| `research.md` | Done | 5 decisions — no feature flag, incoming-`idMessage`-first, per-session index, prompt-injection position, media full-text handling |
| `data-model.md` | Done, **revised 2026-08-04/05** | `resolved_reference` shape: `content` XOR `ledger_events` (full hydrated `LedgerEvent` records, never bare ids) — see below |
| `contracts/reply-resolution.md` | Done | Internal function signatures (no REST API — this is all in-process) |
| `quickstart.md` | Done | Manual dev verification steps 1–5 |
| `tasks.md` | Done, user-approved test plan | 24 tasks, TDD `a`/`b` pairs — **not yet approved as actual test CODE**, only as a task-description plan |

## The one non-obvious design decision to know before touching code

`resolved_reference.content` and `resolved_reference.ledger_events` are **mutually
exclusive**. Early drafts had the resolved reference always carry the message's raw
text/extracted text, plus bare `ledger_event_ids` as an add-on. That was wrong: a
`LedgerEvent` record already contains `raw_message_excerpt` (the source text/image
description the capture was based on), so carrying both would duplicate the same raw text and
still leave the model with nothing but an opaque id to reason from for anything structured
(amount, client name). The fix (data-model.md, 2026-08-04/05 revision): when a resolved
message has `ledger_event_ids`, fetch the FULL structured `LedgerEvent` record(s) via a new
`LedgerEventManager.get_event(event_id)` method (doesn't exist yet — Foundational task T004)
and surface those instead of `content`. `content` is only populated when there's no ledger
event to defer to. If you're implementing T005b (`resolve_reply`) or T017b (wiring into
`AIHandler`), re-read `data-model.md`'s Validation Rules before writing code — this exclusivity
is easy to accidentally violate.

## Test plan (already negotiated, don't re-litigate without reason)

See `tasks.md`'s "Test Tiers" section for full detail. Summary of what was deliberately
included/excluded and why (this took several rounds with the user — the reasoning matters
more than the conclusion if you need to adjust it):

- **0 mocking** anywhere (CONSTITUTION §I/§V) — real internal paths, real OpenAI for
  `billed`/`expensive` tiers.
- **2 `billed` tests** (T013a/T014a) — text-only real OpenAI calls. One proves a
  text-captured `LedgerEvent`'s structured fields actually reach and are usable by the model
  (not just present in a string somewhere). One is a hallucination-guard baseline: an
  ordinary reply to a non-ledger message must behave exactly like today, with no invented
  agreement data and no spurious `capture_ledger_event` call.
- **2 `expensive` tests** (T015a/T016a) — real vision calls, one for a real agreement image,
  one for a real bank-deposit image. Bank deposits are ALWAYS image-sourced (no text-only
  bank capture path exists in the schema), so the bank one is the only place this path gets
  end-to-end coverage at all. Both require separate per-run approval even after this task
  plan's approval, per CLAUDE.md.
- Everything else (session expiry, cross-chat non-match, no-quote baseline, missing-extraction
  fallback) is unit/integration only — `create_ai_request` only *builds* the request object,
  it doesn't call OpenAI itself, so most assertions just inspect the constructed
  request/stored JSON.
- Explicitly rejected during planning: an adversarial "fooling" test (user replying with
  agreement-sounding language to a non-agreement message) — the user redirected this to a
  plain, non-contrived baseline instead ("just a regular reply, same as today").

## Immediate next step

`speckit.implement`, Phase 1 (trivial) → Phase 2 Foundational (T002–T005, data model +
`resolve_reply` + `LedgerEventManager.get_event`) → Phase 3 (US1, MVP). Every `Xa` test task
still needs a real human approval of the actual test CODE (not just this plan) before its
paired `Xb` implementation task starts — that gate has not happened yet for any task.

## Related

- Feature 040 (`specs/backlog/040-agreement-cancellation-modification/`) depends on this
  feature's `resolved_reference.ledger_events` shape — do not change that shape without
  checking 040's spec for assumptions built on it.
