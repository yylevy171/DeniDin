# Bugfix Spec: `list_reminders` discloses a private 1:1 reminder's text into a group chat

## Bug ID
bugfix-051-list-reminders-cross-chat-disclosure

## Title
On a GODFATHER turn **in a group chat** asking a vague "what did you remind me about ~2 weeks
ago?" question, the model called `list_reminders` (Feature 054) and read the **full text of a
reminder that belongs to the godfather's private 1:1 chat** back into the group — where a third
party (another group member) can see it. `ReminderManager.list_active()` returns every active
reminder with no filter on the current chat or creator, and `AIHandler._handle_list_reminders`
strips `delivery_chat_id` / `created_by_phone` out of the summary it hands the model, so the
model has no signal that the reminder is private to a different chat and nothing tells it not to
surface it in a group.

## Priority
P1 — a confidentiality / information-disclosure defect: private reminder content (which could be
anything — medical, financial, personal) reaching an unintended audience in a shared group,
triggered by an ordinary vague question, with no error and no indication to the godfather that a
leak occurred. Not data loss, and partly masked by the model often getting it right on a more
specific follow-up question (see "Reproduction"), but the failure mode is a silent privacy
breach on a shared surface — same severity class as the reminders/tool-boundary bugs found
around it (bugfix-041, bugfix-042).

## Status
Open — root cause investigated from real dev-environment logs (see "Reproduction"); no fix
designed or implemented yet. Per Bug-Driven Development (METHODOLOGY.md §VII), the next step is
human approval of this root cause before test-gap analysis or fix design begins.

## Date Opened
2026-09-04

## Reported By
yaronlev171 — surfaced during Feature 070 (rolling-memory-window) Phase 9 dev-environment
verification. The user sent a deliberately vague reminder question into the dev group chat to
test daily-summary recall and noticed the reply quoted a reminder he had set in his **private
1:1** chat: *"something is wrong though - i asked in the group about a reminder 2 weeks ago, but
got a reply about a personal reminder that I set in the 1:1 chat."* Asking again, more
specifically, produced a correct reply — so the model can do the right thing when prompted
well; the vague-question path is what leaks.

## Affected Area
- `apps/denidin-app/src/managers/reminder_manager.py`
  - `list_active()` (~line 385): `SELECT reminder_id, message_text, rrule, dtstart,
    created_by_phone, created_by_role, delivery_chat_id FROM reminders WHERE status = 'active'
    ORDER BY dtstart` — **no `WHERE` clause on `delivery_chat_id` or `created_by_phone`**. Every
    active reminder in the one godfather-owned list is returned regardless of which chat the
    request came from. This is consistent with Feature 054's spec (FR-013: "the one
    godfather-owned reminder list"), which framed `list_active()` purely as a *disambiguation*
    lookup for `modify_reminder`/`delete_reminder`, not as the answer to a user-facing "what
    reminders do I have?" question asked from an arbitrary chat.
- `apps/denidin-app/src/handlers/ai_handler.py`
  - `_handle_list_reminders` (~line 2465): builds the summary passed back to the model as
    `{reminder_id, message_text, schedule}` for each reminder — it **drops `delivery_chat_id`
    and `created_by_phone`**. So even if the model wanted to scope its answer to the current
    chat, it has no field to scope on. The one active reminder in the repro
    (`message_text="בוקר טוב אדון גוטה"`, `delivery_chat_id="972522968679@c.us"`) reached the
    model looking identical to a reminder created in the group.
  - `LIST_REMINDERS_TOOL` (~line 987) / `_reminder_tools_for_role` (~line 1784): the tool is
    attached on every GODFATHER/ADMIN turn (RBAC-gated only), 1:1 or group alike, with no
    per-chat scoping of what it can see.
- `apps/denidin-app/config/runtime_constitution.md` — "Reminder Management" section
  - Has "When these tools apply" (topic scoping) but **nothing about the chat-scope of the
    answer**: no instruction that a "what reminders do I have?" question asked *in a group*
    should surface only that group's reminders, nor that a reminder whose delivery target is a
    private 1:1 chat must never have its text read aloud in a group (the model should say
    something like "that's from our private chat" or ask, rather than quoting it).

## Reproduction

Real `denidin-app-dev` logs, 2026-09-04 00:12:31–00:13:04 +03:00 (`v0.5.3`), chat
`120363410226011645@g.us` ("קבוצה נסיונית עם דנידין" — a 2-person group: the godfather
`972522968679@c.us` and one other member), GODFATHER role.

1. `00:12:31` (AUDIT-IN) — godfather sends, **in the group**:
   `ערב טוב. זוכר שהזכרת לי משהו לפני שבועיים בערך? מה זה היה?`
   ("Good evening. Remember you reminded me of something about two weeks ago? What was it?")
2. `00:12:33` — `INFO - Added 10 recalled memories to system prompt` (Feature 070 recall fired
   correctly — the group's own collection contains the backfilled Aug-19 `daily_summary`; that
   is **not** the source of the leak).
3. `00:12:53`–`00:13:00` — model's first response carries a single `function_call`:
   `list_reminders` with `arguments_raw='{}'`
   (`[054] _call_openai_list_reminders_followup_api: call_id='call_mxoP5KlgwmtedLiTd9bQLoLC'`).
4. `_handle_list_reminders` → `ReminderManager.list_active()` → the follow-up submits this as
   the tool output:
   ```json
   {"reminders": [{"reminder_id": "248a4b50-f54f-44ea-bb86-5c4fe9980b1a",
     "message_text": "בוקר טוב אדון גוטה",
     "schedule": "שבועי, בימים א,ב,ג,ד,ה,ו, החל מ-20/08/2026 09:00"}]}
   ```
   The reminder DB row for `248a4b50`:
   `status=active  created_by_phone=972522968679@c.us  delivery_chat_id=972522968679@c.us`
   — i.e. a reminder **created in, and delivered to, the godfather's private 1:1 chat**, not
   the group. `delivery_chat_id` is present in the DB row `list_active()` reads, but is dropped
   before the model sees it.
5. `00:13:03` — model's reply (`_finalize_response`, `output_text=`), and `00:13:04`
   (AUDIT-OUT, `chat='120363410226011645@g.us'`, i.e. sent **to the group**):
   `ערב טוב. לפני כשבועיים היתה לך תזכורת שבועית בנוסח: **"בוקר טוב אדון גוטה"**, בכל יום בשעה 09:00.`
   ("Good evening. About two weeks ago you had a weekly reminder worded: **"בוקר טוב אדון גוטה"**,
   every day at 09:00.")

**Net effect**: the verbatim text of a reminder the godfather set in his private 1:1 chat was
posted into a group where another person can read it, in response to a vague question, with no
error and nothing telling the godfather a private item had been disclosed.

**Contrast — the more-specific re-ask worked**: when the user re-phrased the question with more
context, the model produced a correct, non-leaking reply (user: *"I asked again more
specifically and got a good reply!"*). So the model *can* answer these correctly; the defect is
that the tool hands it un-scoped data and nothing in the constitution constrains how it may use
that data by chat.

## Not a Feature 070 (memory) bug

Feature 070's rolling window and daily-summary recall behaved correctly on this turn:
- the group turn's rolling window was the group session's own messages;
- `Added 10 recalled memories` included the group's own backfilled `daily_summary`;
- the leak came entirely from the `list_reminders` tool call and the un-scoped list it returns.
This bug is pre-existing Feature 054 behaviour that Feature 070's Phase 9 dev test happened to
expose. It should be fixed on its own `bugfix/051-…` branch, not on `feature/070`.

## Related Work
- `specs/bugfixes/bugfix-042-reminders-invading-unrelated-turns.md` — same family (a reminders
  tool-boundary not holding up under a real turn). 042: `list_reminders` fires when it
  shouldn't and breaks the turn. 051: `list_reminders` fires appropriately but returns
  cross-chat data the model then discloses.
- `specs/done/v0.5.0/054-reminders-functionality-mgmt/spec.md` — FR-013 defines `list_reminders`
  as a *disambiguation* lookup over "the one godfather-owned reminder list", and lines 44–45 /
  270–272 establish `delivery_chat_id` (the chat a reminder was created from) as a real
  per-reminder property. The gap is that neither the tool's summary nor the constitution
  connects `delivery_chat_id` to *where the reminder's contents may be spoken*.
- CLAUDE.md — "EVERY NEW TOOL-BEARING FEATURE NEEDS EXPLICIT CONSTITUTION BOUNDARIES". As with
  bugfix-042, a boundary exists for *topic* scope but not for this *chat-visibility* scope; the
  fix likely needs both a constitution rule and a structural change (carry `delivery_chat_id`
  into the model-visible summary, and/or scope `list_active()` by the requesting chat for the
  user-facing "what reminders do I have" path while keeping the full list available for
  id-resolution).

## Next Steps (per Bug-Driven Development, METHODOLOGY.md §VII)
1. **Human approval of this root cause** (this document).
2. Test-gap analysis — there is no test asserting `list_reminders`' behaviour by requesting
   chat, nor any asserting that a private-chat reminder is not quoted in a group reply. Needs a
   unit test on `list_active()`/`_handle_list_reminders` scoping and (likely) a `billed`
   acceptance test for the group-vs-1:1 disclosure behaviour.
3. Design a fix — open questions, not yet decided:
   - Should `list_active()` gain an optional `chat_id` filter, with `_handle_list_reminders`
     passing the turn's `effective_chat_id` for the user-facing "what reminders do I have?"
     path, while `modify_reminder`/`delete_reminder` disambiguation keeps access to the full
     list?
   - Or keep `list_active()` global but include `delivery_chat_id` (and a derived
     "this chat" / "your private 1:1" label) in `_handle_list_reminders`' summary, and add a
     constitution rule: in a group, only surface reminders whose `delivery_chat_id` is that
     group; never quote a private-1:1 reminder's text in a group — say it exists in the private
     chat, or ask.
   - Both, most likely: the constitution rule is the durable behavioural boundary; the
     summary/scoping change is what makes it enforceable.
4. Failing test written, approved, minimal fix implemented, verified.
