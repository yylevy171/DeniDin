# Bugfix Spec: A valid Israeli phone number is rejected because it isn't normalised first

## Bug ID
bugfix-032-phone-number-not-normalised

## Title
`add_client` / `update_client` reject an unambiguously valid Israeli mobile number written
without its leading zero (`50-822-5928`), forcing the user to retype it, instead of
normalising it to `050-822-5928`.

## Priority
**P2** — pure friction; no data is corrupted and the user can work around it by retyping.

## Status
**Open — backlogged.** No fix designed. Per Bug-Driven Development (METHODOLOGY.md §VII), next
step is human approval of the root cause before test-gap analysis.

## Date Opened
2026-08-09

## Reported By
yaronlev171, from the 7–9 Aug 2026 production review
([`docs/production-analysis/2026-08-09-aug7-9-review.md`](../../docs/production-analysis/2026-08-09-aug7-9-review.md), P2-4).

> **Shared session context** — how this review was run, the read-only access paths, the full
> map of bugfix-028…037, the triage decisions (including what was closed as *not* a bug), and
> the open verification items:
> [`bugfix-028` § Session Context](../done/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster.md#session-context-2026-08-09-production-review) (now in `specs/done/bugfixes/`).
> All ten bugs in that set are **fix-forward only** — existing production documents are being
> left as they are by explicit user decision.

## Affected Area
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` — `_normalize_israeli_phone`
  (~line 1170), and its callers `add_client` / `update_client`

## Description
`_normalize_israeli_phone` already handles `+972`/`972` prefixes, dashed and undashed local
forms. It rejects anything that doesn't resolve to *"9 or 10 digits starting with 0"* — and a
number typed as `50-822-5928` (9 digits, no leading zero) falls outside that.

This is an **app-level policy choice**, not a Morning constraint — the docstring says so
explicitly: *"No Morning-side format rule exists to mirror (confirmed via the full error-code
catalog)."*

Observed live, session `12e158e2` turns 55–61:

```
55 USER     50-822-5928
58 DENIDIN  ליצור לקוח חדש: עדו דניאל, idodan87@gmail.com, 50-822-5928 — לאשר?
59 USER     כן
60 DENIDIN  לא ניתן היה לפתוח את הכרטיס — מספר הטלפון שסופק (50-822-5928) נדחה כמספר לא תקין.
           נא למסור את המספר בפורמט מלא, למשל: 050-822-5928.
61 USER     הטלפון 0508225928
```

Prod log (`morning-mcp.log`, 2026-08-09 03:27:22):
```
WARNING Validation/business-rule error: Phone number does not resolve to a plausible
        Israeli number: '50-822-5928'
```

Note the wasted round-trip: the number was carried all the way through an **approval prompt**
before being rejected — the user approved creating a client with a number the tool already
knew it would refuse.

## Expected
A 9-digit number beginning with a valid Israeli mobile/landline prefix (`5x`, `2`, `3`, `4`,
`8`, `9`, …) should be normalised by prepending the `0`. If a value will be rejected, reject it
**before** presenting an approval prompt, not after the user approves.

## Related Work
- Feature 026 (`REQ-CLIENT-016`) — introduced `_normalize_israeli_phone`; this extends its
  accepted-input set.
- `specs/done/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster.md` — B3/B5: the
  approve-then-fail sequence here is the same "validate late, tell the user late" pattern.
