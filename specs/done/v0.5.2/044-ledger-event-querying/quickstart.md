# Quickstart: Ledger Event Querying via AI

**Feature**: 044-ledger-event-querying · Manual verification walkthrough (godfather/admin,
`denidin-app-dev`, real ledger data already present in `dev_data/events/`).

## 1. Basic single-client lookup (US1)

1. As godfather, in a fresh session (no prior mention of the client), send: "כמה סוכם עם
   [client] על [matter]?"
2. Expect: DeniDin's reply states the agreed amount, sourced from a real captured ledger
   event — not from session memory, not fabricated.
3. Confirm via logs (`logs/dev/denidin.log` or `docker logs`) that `query_ledger_events` was
   actually called with a non-empty `client_name` filter, and the follow-up call's
   `function_call_output` contained the matching event.

## 2. No match found

1. Ask about a client/matter with no captured ledger event at all.
2. Expect: DeniDin states plainly it found no matching record — never a fabricated figure.

## 3. Ambiguous client name

1. Ensure (or seed) two distinct client_name values in the ledger that would both
   fuzzy-match a short/partial query name (e.g. two different clients sharing a first name).
2. Ask a question using only that ambiguous partial name.
3. Expect: DeniDin asks which of the two clients you meant, listing both candidates — never
   silently guesses one.
4. Reply with the disambiguating full name; expect the correct single client's events now
   come back.

## 4. Vague query — no identifying detail at all

1. Ask something with zero identifying detail, e.g. "מה סוכם?" with no name/date/amount.
2. Expect: DeniDin asks what/who you mean BEFORE attempting any search — never calls
   `query_ledger_events` with every filter empty (confirm via logs: no `query_ledger_events`
   function_call at all for this turn).

## 5. Date-ranged / multi-event summary (US2)

1. Ensure at least one client has multiple hours-logged events across a date range (e.g.
   several entries within one calendar month).
2. Ask "כמה שעות אני צריך לחייב את [client] ב[month]?"
3. Expect: DeniDin's reply reflects all matching hours entries for that client/month (it
   will do the summing itself in its reply) and does not include events from other months
   or other clients.

## 6. Owed-balance question (cross-event-type reasoning)

1. Ensure a client has both a fee-agreement event (an agreed amount) and one or more
   bank-deposit events (partial payments).
2. Ask "כמה [client] עוד חייב לי?"
3. Expect: DeniDin's reply reflects both the agreed amount and the payments found, doing the
   subtraction itself (there is no server-side "balance" computation — see research.md
   Decision 5) — confirm the reasoning is visible/sensible, not a made-up number.

## 7. RBAC denial (US3)

1. As a client-role user (not godfather/admin), ask a ledger question that a godfather could
   answer via step 1 above.
2. Expect: `query_ledger_events` is never attached/called for this role (confirm via logs —
   no such tool in the turn's `tools` list at all), and DeniDin does not disclose any
   ledger data.

## 8. Large result set — reply stays readable, no fixed cap

(2026-08-26: this used to assert a hard 20-event cap - dropped after a real `billed` run
showed the model reliably grouping a large result set into date-range buckets while still
naming every client individually, which a strict numeric count can't distinguish from "didn't
summarize at all." The real, strictly-enforced constraint is the reply's own output-token
budget, not a specific event count - see `runtime_constitution.md`'s "Ledger Event Querying"
section.)

1. Seed (or ensure) a broad query would match many events (e.g. many events across a wide date
   range/multiple clients).
2. Ask a deliberately broad question that would match all of them (e.g. "מה כל האירועים
   מהחודש האחרון?").
3. Expect: the tool itself still returns the complete matching set internally (no
   truncation — unchanged, locked at spec time; hundreds of events retrieved is fine). The
   chat reply should stay readable for a WhatsApp conversation — some form of
   summarizing/grouping (counts, by client, by month) or asking you to narrow, rather than a
   long undifferentiated list — but there's no specific number to check the reply against;
   use your own judgment reading it back.

## 9. Startup index load

1. Restart `denidin-app-dev` (real, already-approved restart — do not do this without
   separate explicit approval per CLAUDE.md's environment-start rule).
2. Repeat step 1 above immediately after the restart completes.
3. Expect: the same correct answer — confirms the in-memory index reloads fully from disk
   at startup, not just from same-session writes.
