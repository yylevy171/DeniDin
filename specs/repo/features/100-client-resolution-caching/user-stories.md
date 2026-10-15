# User Stories: Client Resolution Cache

**Feature Branch**: `feature/100-bugfix-073-client-resolution` (built together with bugfix-073)
**Related Spec**: `feature-100-caching.md` (same directory)
**Status**: BACKLOG 2026-10-15 - product owner moved this back to the backlog. Stories below are an unapproved draft; no plan, no code.

**Why it is not being built now (2026-10-15 analysis):** the "210 redundant calls" in the original
spec text is wrong (the trace has 2 real `resolve_client_name` calls; the rest are the tool's
description repeated in every prompt). Across the logged billed runs of 19 test files, runs on 067
code (teammate2 on `feature/067` 2026-10-11..15, plus runs after the merge) re-resolve a name
**0.45** extra times per client conversation vs **0.65** before 067 (-31%); document/invoice creation
flows dropped to ~0. What remains is concentrated in the update-client flow (2 repeats per run) and
the allocation-ID flow (~1.6 per client) - one Morning search each, no wrong outcomes found. Revisit
only if those two flows become a measured cost or a correctness problem.

---

## Evidence that the problem is still real (checked 2026-10-15, after 067 merged)

Billed runs against the dev sandbox, tool calls read from the test logs:

- `test_godfather_update_client_resolves_ambiguous_family_name_prefix_after_confirmation` (passed):
  the user answered a "which client?" question with the exact full name -> the bot called
  `resolve_client_name` again for that name; a later "details on X" request resolved it a third time.
- `test_create_document_for_new_client_full_flow_happy_path` (failed later, for an unrelated
  reason): the same name was resolved 3 times in the first 3 turns, answering "ambiguous" each time
  (the third on the "add this client" turn). After the client was created, the bot did NOT
  re-resolve (it went straight to `create_invoice` with `name_resolved: true`) - the pre-067 runs of
  the same test re-resolved 3-4 more times at that stage.

So repeated lookups of a name the bot already holds still happen; they are fewer after the client exists.

---

## Model of operation (all stories)

```
resolve_client_name ends definitively  ->  the app records {what the user typed, the exact Morning name}
every model call                       ->  the recorded pairs are shown to the model (stateless: the
                                            model is told, the app does not act on the pair by itself)
user later writes a name that is an EXACT verbatim match of a recorded "typed" or "exact" value
                                       ->  the model uses the exact name directly, no new lookup
any other name                         ->  resolved normally, as today
```

The app never fills in a client on the model's behalf. The cache only removes the model's need to
look up a name it was already given an answer for.

---

### User Story 1 - A shorthand the user already settled is not looked up again (P1)

The user asks about "יהושע", the bot lists candidates, the user picks "רביבו".

1. **Given** the user picked one candidate and the bot continued with that client, **When** the user
   later in the same chat writes the same shorthand or the full name, **Then** the bot goes straight
   to the requested action without a new `resolve_client_name` call.
2. **Given** that action needs approval (invoice, receipt), **Then** the approval prompt still names
   the full exact client name, and nothing is created before the user approves.

### User Story 2 - A new or different name is still resolved normally (P1)

1. **Given** a recorded pair for one client, **When** the user names a different client, or a
   spelling that is not an exact match of a recorded value, **Then** `resolve_client_name` runs as
   today.
2. **Given** the user sends an image or a request "for Hadas" right after talking about Noa,
   **Then** nothing is attributed to Noa: the cache only matches names the user wrote.

### User Story 3 - A near-miss spelling is never treated as settled by itself (P1, ties to bugfix-073)

Bugfix-073 now surfaces "מור פלימבו" as a candidate for the typo "מור פלומבו".

1. **Given** the lookup returned the near-match only as a candidate, **Then** no pair is recorded
   until the user confirms it.
2. **Given** the user confirmed it, **Then** the pair ("מור פלומבו" -> "מור פלימבו") is recorded, and
   a later "מור פלומבו" in the same chat skips the lookup.

### User Story 4 - The cache never hides a change in Morning (P2)

1. **Given** a recorded pair, **When** the client is renamed or the pair no longer matches what
   Morning returns, **Then** the pair is dropped and the name is resolved again.
2. **Given** a tool call fails because the client was not found, **Then** the pair is dropped and the
   bot resolves again instead of retrying with the stale name.

### User Story 5 - Safe by default (P2)

1. **Given** the cache is empty, unavailable, or damaged, **Then** the bot behaves exactly as it does
   today (full resolution every time).
2. **Given** the user is in a group, **Then** pairs belong to that chat only and never leak into
   another chat.

---

## Acceptance scenarios (plain language - test code is written later, run once at the end)

Each is a real end-to-end `billed` run through the WhatsApp entry point, checking the tool calls
the bot made and what it said.

- **A1 - Pick then reuse.** The user names a first name that matches several clients; the bot asks
  which one; the user answers with a shorthand; the bot continues. The user then asks for a document
  for the same shorthand. *Expected:* exactly one `resolve_client_name` call for that client in the
  whole conversation after the pick; the document approval names the full exact name; nothing
  created before "כן".
- **A2 - Different client, no carry-over.** Same chat; the user asks about another client.
  *Expected:* a normal lookup for the new name; the first client is never used for it.
- **A3 - Typo, confirm, reuse.** The user types a name one letter off from a real client; the bot
  offers the real name; the user confirms; later the user types the same typo again.
  *Expected:* one lookup in total; the second request proceeds directly with the real name.
- **A4 - Unconfirmed near-match is not remembered.** The bot offers a near-match and the user says
  no. *Expected:* a later request with the same text resolves again from scratch.
- **A5 - Stale entry.** A client recorded in the cache is renamed (by the test, directly in Morning),
  then the user asks for a document for the old name. *Expected:* the bot resolves again and does not
  use the old name for a write.
- **A6 - Baseline unchanged.** A conversation with a brand-new name (no prior resolution) behaves as
  it does today: one lookup, same prompts, same approval texts.

---

## Open design questions for the product owner (answers needed before `speckit.plan`)

1. **Where do pairs live?** Per chat session (survives restarts, recommended) or in memory only?
2. **What counts as "definitive"?** Only a `resolved` answer, or also a candidate the user confirmed
   (needed for the shorthand case in Story 1 and Story 3)? Recommended: both.
3. **How long does a pair live?** Until the client changes (Story 4) only, or also a time limit
   (for example 24 hours, or the capability reset in `capabilities_reset_minutes`)?
4. **Size limit?** Recommended: the 20 most recent pairs per chat, oldest dropped first.
5. **"Exact verbatim" match:** exactly the characters, or ignoring case and extra spaces? Recommended:
   ignoring case and surrounding/repeated spaces only, nothing fuzzier.
6. **Where is it shown to the model?** As part of the instructions the backbone rebuilds on every
   call (consistent with how loaded capabilities are handled), not in the chat history.
7. **Feature flag?** Per CONSTITUTION §VI a flag is opt-in and needs your decision. Recommended:
   no flag (empty cache = today's behavior), rollback is the previous release.
