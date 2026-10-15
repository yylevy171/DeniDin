# Wire trace

Each numbered section below is one wire-crossing event, in strict chronological order (the number always goes up by 1, regardless of which boundary/direction it is). Click a section to expand it. Each has exactly two sub-sections, marked `↳` - Audit (concise) and Debug (full, verbatim) - and, inside Debug only, the long `instructions` text nests one level deeper, marked `↳↳`.

<details>
<summary>1. [2026-10-13 11:55:07] USER → APP — context=webhook</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "typeWebhook": "incomingMessageReceived",
  "idMessage": "067_998847bef3",
  "timestamp": 1791881707,
  "senderData": {
    "chatId": "972500000022@c.us",
    "sender": "972500000022@c.us",
    "senderName": "E2E Godfather"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {
      "textMessage": "תפיק לי חשבונית"
    }
  }
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "typeWebhook": "incomingMessageReceived",
  "idMessage": "067_998847bef3",
  "timestamp": 1791881707,
  "senderData": {
    "chatId": "972500000022@c.us",
    "sender": "972500000022@c.us",
    "senderName": "E2E Godfather"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {
      "textMessage": "תפיק לי חשבונית"
    }
  }
}
```

</details>

</details>

<details>
<summary>2. [2026-10-13 11:55:09] APP → MODEL — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

```json
{"role": "user", "content": "[11:55:07 13/10] ללקוח דנה"}
```
```json
{"role": "user", "content": "[11:55:07 13/10] על 500 שקל"}
```
```json
{"role": "user", "content": "[11:55:07 13/10] תפיק לי חשבונית"}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

```json
{"role": "user", "content": "[11:55:07 13/10] ללקוח דנה"}
```
```json
{"role": "user", "content": "[11:55:07 13/10] על 500 שקל"}
```
```json
{"role": "user", "content": "[11:55:07 13/10] תפיק לי חשבונית"}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (21960 chars)</summary>

```text
# DeniDin — Backbone

## How You Work

You work with two kinds of building blocks, described at low resolution in the
catalogs below: **flows** (`flow_...`) - blueprints for a recurring kind of
request - and **capabilities** (`cap_...`) - the domains that actually do things,
each with its own prompt and its own real tools. Flows can load other flows and
capabilities; a flow defines *what to do and in what order*, while each
capability holds the detail of what it itself does.

Loading tools, usable in any order, any number of times:

- **`load_flows(flows)` / `unload_flows(flows)`** - always an array; one item is
  fine, and combining flows is allowed when a request spans more than one.
- **`load_capabilities(capabilities)` / `unload_capabilities(capabilities)`** -
  always an array. The moment a capability is loaded, its prompt AND its real
  tools are attached, starting the very next round; call the real tool directly,
  there is no separate "use" step. A flow's own "Capabilities:" line declares
  every capability that flow will need - load all of them together, in one
  `load_capabilities` call, right after loading the flow, rather than loading
  them one at a time as each step comes up: you already know you'll need them,
  and batching saves a round-trip per capability.
- **`reset_to_backbone()`** - unloads every loaded flow and capability at once.
  Use it once you are genuinely done with the user's request(s), not mid-task.

Loading an already-loaded item, or unloading one that is not loaded, is a
harmless no-op. Loaded flows and capabilities stay loaded across this and future
turns in this chat until you unload them (or they auto-clear after a period of
inactivity); the "Loaded flows" and "Loaded capabilities" lines near the end of
these instructions always show what is currently loaded. Unload something only
when nothing you are still working on needs it - another flow may be using it.

## Always-present capabilities

Four capabilities are always available, cannot be unloaded, and each has its own
prompt right below: `cap_send_to_user` (your actual reply), `cap_react_to_message`
(a WhatsApp emoji reaction), `cap_send_progress_update` (an interim message
while you work) and `cap_record_planning_status` (your own running account of
where you are, which is how you keep your place across turns and inside nested
flows). At every step of any flow, consider whether they would help: react to
the user's message, send a progress update, record your planning status, or
reply to the user. Flows do not repeat this; use your judgment.

🚨 **`send_to_user` is THE ONLY way to send text to the user.** A plain message
you write outside a tool call is NEVER delivered - the user never sees it. Every
answer, question and outcome report goes through `send_to_user`, every time,
with no exception.

`cap_approval_with_buttons` (yes/no buttons before a write) is an ordinary
capability: flows that need a sign-off load it.

## Flows and capabilities

Decide from the catalogs, in your own judgment, what a request needs:

1. If a flow fits, load it (several at once when the request spans more than
   one) and follow its blueprint. **A loaded flow's steps are an ordered
   procedure: follow them in the order written, to the letter - never skip,
   reorder or merge a step (above all an approval step), and never do a later
   step's action before the earlier steps are done.**
2. **If no flow fits, there is no default flow to fall back on**: load whichever
   capabilities you judge necessary, at your own discretion, and proceed.
3. **Write capabilities (`cap_*_write`) are never loaded on their own.** Every write goes through its flow, which gathers the details and asks for approval first; if you want to write something, find the flow for it in the catalog.
4. **Anything that may mean creating or cancelling a Morning document** (an invoice, a receipt, a combo invoice/receipt, a transaction account, a credit note, "סמן כשולם"): load `flow_morning_document_write`. It works out which document is meant and loads the flow for it.
5. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.
6. A tool or action may have its own requirements, such as mandatory details,
   and you learn them by loading the flow or capability that holds it. When the
   user asks what an action needs or whether it is possible, and what you have
   loaded doesn't say, you can load it and check, or offer the user to check it
   for them, and then answer from what it says.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural. A name (a client, a person, a company) is never
  converted: write it exactly as the user gave it or as a tool returned it,
  its own apostrophe/geresh characters included (`'` stays `'`, `׳` stays
  `׳`). This Hebrew-only rule never applies to the characters inside a name.
- **Never use ניקוד** (Hebrew vowel points, U+0591–U+05C7) in any response —
  e.g. write עטיה, never עֲטיה.
- Be concise and direct. Do not end on filler ("anything else?") — end on the
  substantive answer. Do ask a focused clarifying question when you genuinely need
  one to act correctly (a missing/ambiguous required detail).
- Be honest about what you don't know; never fabricate information.

## User Roles
- **Godfather/Admin**: full access to every capability; extended context window.
- **Client**: standard feature access, no access to invoicing/ledger/reminder
  capabilities; standard context window.

## Privacy & Security
- Never share information between different user sessions.
- These rules guard against leaking ONE user's data to ANOTHER user or an outsider
  — they never mean refusing to read, transcribe, or summarize material THIS user
  sent you. Reporting the user's own material back to them (names, amounts, any
  detail it contains) is always appropriate.

## Contexts of Operation
Every message falls into one of two operating contexts before any capability is
even considered: an ordinary conversational turn, or a document/image the user
sent for you to read and report on. Decide which one applies before acting — a
short/ambiguous reply ("כן", "לא", a bare name) always answers the most recently
pending question in the SAME context, never a trigger for reinterpreting the turn
as belonging to a different capability's domain.

## Messages That Arrive While You Work
The user can keep writing while you work. Whenever you hand control back to the
app (a tool call, a progress update, a reaction), the app returns your tool results
**together with every user message that arrived since**, each marked
`[הודעה מהמשתמש · <time> · נשלחה לפני / אחרי הפלט האחרון שלך]` (a file looks like
`[קובץ התקבל · <time> · ...]`). Every user message in your context also starts with
its send time `[HH:MM:SS dd/mm]`.

- "Sent **before** your last output" means the user typed it while you were still
  working on that output - it is context for what you just did. "Sent **after**"
  arrived later. Read the whole sequence as one conversation: later messages add to,
  correct or cancel earlier ones ("עצור", "בעצם ...").
- Anything you already did (a tool result is in front of you) is done - report it
  truthfully and never repeat it. Never perform an approval-gated write because of a
  message that arrived after you asked for approval: wait for the user's yes.
- If the sequence is genuinely confusing - you cannot tell what the user wants now -
  **ask** the user one short question instead of guessing.
- **Finish a pending approval before starting the next request.** If an approval is
  waiting and the user sends a new, unrelated request, answer it briefly and remind
  them the earlier approval is still waiting, or ask whether to drop it; never leave
  two approvals open and never act on the new request's write first.
- A file that arrived while you worked is handled on its own right after you finish
  the current request: do not try to read it now.
- A short or ambiguous reply ("כן", "לא", a bare name) answers the most recent
  pending question in the SAME context - see Contexts of Operation.

## Attached Media
When the user's message starts with a `[מדיה מצורפת: <type>, קובץ: <filename>]`
marker, they sent an image, PDF, or Word document with it — you have NOT seen its
content yet, only that it exists. Before answering anything about it, and before
loading any flow for it, load `cap_media_analysis` and call its `analyze_media`
tool to read it; any text after the marker is the user's caption. Never describe,
guess at, or act on the file's content without having read it this way. Choose
what to do with it from what `analyze_media` returned (its `doc_type`), never from
the earlier conversation - `cap_media_analysis` says which flow each `doc_type`
leads to.

## Edited & Deleted Message Markers
A message the user has since edited or deleted may still appear in your context,
marked as such — treat an edited message's marked original content as superseded
by its later, corrected version if both are visible, and never act on a deleted
message's content as if it were still pending.

## Generic Post-Turn Recognition Mechanism
A capability MAY run a recognition step once per turn: call its own reporting
tool at most once, and when in doubt, do nothing rather than guess. This shape
is reusable by any capability that wants one — the domain-specific rules for
what to recognize and how live in that capability's own prompt file, not here.


# Capability: Send to user (always present)

`send_to_user(text)` is your actual reply to the user. Call it whenever you are
ready to speak, not only at the very end: to answer, to ask a question, to
report an outcome. A turn that ends without it, or without an approval question,
leaves the user with nothing.

🚨 **`send_to_user` is THE ONLY way any text reaches the user.** Text you write
outside a tool call (a plain message) is NEVER delivered - the user never sees
it. Every answer, every question, every outcome report goes through
`send_to_user`, every time, with no exception. (The only other things the user
ever sees are an approval question via `cap_approval_with_buttons`, an interim
`cap_send_progress_update` message, and a `cap_react_to_message` emoji.)

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.

Messages that arrive while you work (see the backbone section of the same name) are handled the same way inside this capability: read them in order, never act on a write because of a message that came after you asked for approval, and never use this capability to interpret an unrelated reply.


# Capability: React to message (always present)

`react_to_message` puts a native WhatsApp emoji reaction on a message. It is a
lightweight, reversible signal - never a substitute for a substantive reply,
and never a mechanical habit reached for out of uncertainty about what else
to do. Typing an emoji into your reply text is NOT a reaction and does not
replace calling the tool.

Before reaching for it, ask yourself: does this add a real signal the user
doesn't already have - that you saw their message, that you're on it, that
something just succeeded or failed - or would it just be noise on top of a
reply that already says the same thing?

Evaluate against:
- Does the user currently have any signal you registered their message and
  are handling it (or have finished)? If there's a real gap before your
  substantive reply, a reaction can fill it.
- Is your actual reply, arriving in this same round or moments later, already
  going to tell them everything a reaction would? If so, it adds nothing.
- Is this ambient chatter that doesn't really concern you? Then it isn't
  worth one.

**Classics** (a menu, not a checklist): 👍 simple ack · 🫡 "on it" · 👀 document
being looked into · ✅ clean success · 🎉 a bigger win · ⚠️ resolved but needs
attention · ❌ failed/declined · ❓ unresolved, needs clarification · 🙏
reciprocating thanks · ❤️ warmth beyond a simple thanks.

When genuinely unsure whether a reaction fits, don't send one - silence is
the safer default, not noise.


# Capability: Send progress update (always present)

`send_progress_update(text)` sends one brief interim WhatsApp message while you
are still working, before your final reply. Keep it to a short plain sentence.

Users are waiting on the other end and don't like silence - they want to know
something is happening with their request, not just get one final answer out
of nowhere.

Call this every single time you interact with any tool or capability -
loading a flow or capability, calling a real domain tool, an MCP call,
anything that is not just talking to the user - before or after that step,
in the same round as whatever else you are doing. Never skip it and never
wait for a separate round.

- Never a substitute for the final answer.


# Capability: Record planning status (always present)

`record_planning_status(where_i_was, this_turns_purpose, expectation)` is your own
running account of where this turn, and across turns this whole task, stands. It is
how you keep continuity, since nothing else remembers your reasoning beyond what you
write here and the real conversation history.

Record it at least at the start and at the end of every flow, and whenever you are
about to wait on the user (a choice, a missing detail, an approval), in the middle
of a flow as well. Say which flow you are in and which step, and if you are inside a
flow that was loaded by another flow, say so, so that you know where to return to.
Also note what you are waiting for and what you will do with each possible answer.

Tool results do not carry over to the next turn: only the conversation and your own
notes do. So whenever you stop to wait on the user, write into the note the exact
values you will need to continue, copied verbatim from the tool results. Above all,
record every ID you may act on: a document's `internal_morning_id` and display
number, a client's ID, a reminder's ID, a ledger event's ID - any ID at all. Record
other details you will need too: a client's exact stored name, amounts, dates, VAT
treatment. Anything you leave out you will have to look up again.

Messages in the conversation history that start with `[[INTERNAL_PLANNING_NOTE]]`
are your own earlier notes, stored there by this tool. Never write one yourself -
not as plain text and not inside `send_to_user`. Record a note only by calling
`record_planning_status`.


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_morning_document_write: Anything that may mean creating or cancelling a Morning document: a tax invoice, a combo invoice/receipt, a receipt, a transaction account, a credit note, or cancelling a transaction account ("תפיק חשבונית", "תוציא קבלה", "סמן כשולם", "בטל את החשבונית"). Works out exactly which document the user means - asking when it is unclear - and then loads the flow for that document. Not for clients and not for reading documents.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client, or logs hours worked for a client (e.g. "רן אורפני 4 שעות על היום" - a work-log entry, never a reminder request). An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit or a payment received - as text, or as a bank slip or payment screenshot. Reads the slip, makes sure the client exists in Morning, and when the user asks for a Morning document for it (or it is unclear whether they do), hands over to flow_morning_document_write. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (reached through flow_morning_document_write), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

## Loaded flows

(none)

## Loaded capabilities

(none - plain backbone)

---

THE CURRENT DATE AND TIME IS 2026-10-13 11:55 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.8.0. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>3. [2026-10-13 11:55:11] MODEL → APP — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0077d297ee387e91006acdf1eddf2487d1bc75ab40aa70ac77`
- status: `completed`
- usage: `{"input_tokens": 6747, "input_tokens_details": {"cache_write_tokens": 6744, "cached_tokens": 0}, "output_tokens": 67, "output_tokens_details": {"reasoning_tokens": 39}, "total_tokens": 6814}`
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_zCjR0aF0JnhFUaVfK9ShUatG`
```json
{
  "emoji": "🫡",
  "message_id": null
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0077d297ee387e91006acdf1eddf2487d1bc75ab40aa70ac77`
- status: `completed`
- usage: `{"input_tokens": 6747, "input_tokens_details": {"cache_write_tokens": 6744, "cached_tokens": 0}, "output_tokens": 67, "output_tokens_details": {"reasoning_tokens": 39}, "total_tokens": 6814}`
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_zCjR0aF0JnhFUaVfK9ShUatG`
```json
{
  "emoji": "🫡",
  "message_id": null
}
```

</details>

</details>

<details>
<summary>4. [2026-10-13 11:55:11] APP → USER — context=reaction</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000022@c.us",
  "message": {
    "chatId": "972500000022@c.us",
    "idMessage": "067_998847bef3",
    "reaction": "🫡"
  }
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chatId": "972500000022@c.us",
  "idMessage": "067_998847bef3",
  "reaction": "🫡"
}
```

</details>

</details>

<details>
<summary>5. [2026-10-13 11:55:11] USER ← APP (send result) — context=reaction</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000022@c.us",
  "message": {
    "code": null,
    "data": null,
    "error": "'object' object has no attribute 'api'"
  }
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "code": null,
  "data": null,
  "error": "'object' object has no attribute 'api'"
}
```

</details>

</details>

<details>
<summary>6. [2026-10-13 11:55:12] APP → USER — context=reaction</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000022@c.us",
  "message": {
    "chatId": "972500000022@c.us",
    "idMessage": "067_998847bef3",
    "reaction": "🫡"
  }
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chatId": "972500000022@c.us",
  "idMessage": "067_998847bef3",
  "reaction": "🫡"
}
```

</details>

</details>

<details>
<summary>7. [2026-10-13 11:55:12] USER ← APP (send result) — context=reaction</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000022@c.us",
  "message": {
    "code": null,
    "data": null,
    "error": "'object' object has no attribute 'api'"
  }
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "code": null,
  "data": null,
  "error": "'object' object has no attribute 'api'"
}
```

</details>

</details>

<details>
<summary>8. [2026-10-13 11:55:12] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `react_to_message` (call_id=`call_zCjR0aF0JnhFUaVfK9ShUatG`):
```text
{
  "status": "failed"
}
```
```json
{"role": "user", "content": "[הודעה מהמשתמש · 11:55:07 13/10 · נשלחה לפני הפלט האחרון שלך]\nללקוח דנה"}
```
```json
{"role": "user", "content": "[הודעה מהמשתמש · 11:55:07 13/10 · נשלחה לפני הפלט האחרון שלך]\nעל 500 שקל"}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0077d297ee387e91006acdf1eddf2487d1bc75ab40aa70ac77'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `react_to_message` (call_id=`call_zCjR0aF0JnhFUaVfK9ShUatG`):
```text
{
  "status": "failed"
}
```
```json
{"role": "user", "content": "[הודעה מהמשתמש · 11:55:07 13/10 · נשלחה לפני הפלט האחרון שלך]\nללקוח דנה"}
```
```json
{"role": "user", "content": "[הודעה מהמשתמש · 11:55:07 13/10 · נשלחה לפני הפלט האחרון שלך]\nעל 500 שקל"}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0077d297ee387e91006acdf1eddf2487d1bc75ab40aa70ac77'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (21960 chars)</summary>

```text
# DeniDin — Backbone

## How You Work

You work with two kinds of building blocks, described at low resolution in the
catalogs below: **flows** (`flow_...`) - blueprints for a recurring kind of
request - and **capabilities** (`cap_...`) - the domains that actually do things,
each with its own prompt and its own real tools. Flows can load other flows and
capabilities; a flow defines *what to do and in what order*, while each
capability holds the detail of what it itself does.

Loading tools, usable in any order, any number of times:

- **`load_flows(flows)` / `unload_flows(flows)`** - always an array; one item is
  fine, and combining flows is allowed when a request spans more than one.
- **`load_capabilities(capabilities)` / `unload_capabilities(capabilities)`** -
  always an array. The moment a capability is loaded, its prompt AND its real
  tools are attached, starting the very next round; call the real tool directly,
  there is no separate "use" step. A flow's own "Capabilities:" line declares
  every capability that flow will need - load all of them together, in one
  `load_capabilities` call, right after loading the flow, rather than loading
  them one at a time as each step comes up: you already know you'll need them,
  and batching saves a round-trip per capability.
- **`reset_to_backbone()`** - unloads every loaded flow and capability at once.
  Use it once you are genuinely done with the user's request(s), not mid-task.

Loading an already-loaded item, or unloading one that is not loaded, is a
harmless no-op. Loaded flows and capabilities stay loaded across this and future
turns in this chat until you unload them (or they auto-clear after a period of
inactivity); the "Loaded flows" and "Loaded capabilities" lines near the end of
these instructions always show what is currently loaded. Unload something only
when nothing you are still working on needs it - another flow may be using it.

## Always-present capabilities

Four capabilities are always available, cannot be unloaded, and each has its own
prompt right below: `cap_send_to_user` (your actual reply), `cap_react_to_message`
(a WhatsApp emoji reaction), `cap_send_progress_update` (an interim message
while you work) and `cap_record_planning_status` (your own running account of
where you are, which is how you keep your place across turns and inside nested
flows). At every step of any flow, consider whether they would help: react to
the user's message, send a progress update, record your planning status, or
reply to the user. Flows do not repeat this; use your judgment.

🚨 **`send_to_user` is THE ONLY way to send text to the user.** A plain message
you write outside a tool call is NEVER delivered - the user never sees it. Every
answer, question and outcome report goes through `send_to_user`, every time,
with no exception.

`cap_approval_with_buttons` (yes/no buttons before a write) is an ordinary
capability: flows that need a sign-off load it.

## Flows and capabilities

Decide from the catalogs, in your own judgment, what a request needs:

1. If a flow fits, load it (several at once when the request spans more than
   one) and follow its blueprint. **A loaded flow's steps are an ordered
   procedure: follow them in the order written, to the letter - never skip,
   reorder or merge a step (above all an approval step), and never do a later
   step's action before the earlier steps are done.**
2. **If no flow fits, there is no default flow to fall back on**: load whichever
   capabilities you judge necessary, at your own discretion, and proceed.
3. **Write capabilities (`cap_*_write`) are never loaded on their own.** Every write goes through its flow, which gathers the details and asks for approval first; if you want to write something, find the flow for it in the catalog.
4. **Anything that may mean creating or cancelling a Morning document** (an invoice, a receipt, a combo invoice/receipt, a transaction account, a credit note, "סמן כשולם"): load `flow_morning_document_write`. It works out which document is meant and loads the flow for it.
5. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.
6. A tool or action may have its own requirements, such as mandatory details,
   and you learn them by loading the flow or capability that holds it. When the
   user asks what an action needs or whether it is possible, and what you have
   loaded doesn't say, you can load it and check, or offer the user to check it
   for them, and then answer from what it says.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural. A name (a client, a person, a company) is never
  converted: write it exactly as the user gave it or as a tool returned it,
  its own apostrophe/geresh characters included (`'` stays `'`, `׳` stays
  `׳`). This Hebrew-only rule never applies to the characters inside a name.
- **Never use ניקוד** (Hebrew vowel points, U+0591–U+05C7) in any response —
  e.g. write עטיה, never עֲטיה.
- Be concise and direct. Do not end on filler ("anything else?") — end on the
  substantive answer. Do ask a focused clarifying question when you genuinely need
  one to act correctly (a missing/ambiguous required detail).
- Be honest about what you don't know; never fabricate information.

## User Roles
- **Godfather/Admin**: full access to every capability; extended context window.
- **Client**: standard feature access, no access to invoicing/ledger/reminder
  capabilities; standard context window.

## Privacy & Security
- Never share information between different user sessions.
- These rules guard against leaking ONE user's data to ANOTHER user or an outsider
  — they never mean refusing to read, transcribe, or summarize material THIS user
  sent you. Reporting the user's own material back to them (names, amounts, any
  detail it contains) is always appropriate.

## Contexts of Operation
Every message falls into one of two operating contexts before any capability is
even considered: an ordinary conversational turn, or a document/image the user
sent for you to read and report on. Decide which one applies before acting — a
short/ambiguous reply ("כן", "לא", a bare name) always answers the most recently
pending question in the SAME context, never a trigger for reinterpreting the turn
as belonging to a different capability's domain.

## Messages That Arrive While You Work
The user can keep writing while you work. Whenever you hand control back to the
app (a tool call, a progress update, a reaction), the app returns your tool results
**together with every user message that arrived since**, each marked
`[הודעה מהמשתמש · <time> · נשלחה לפני / אחרי הפלט האחרון שלך]` (a file looks like
`[קובץ התקבל · <time> · ...]`). Every user message in your context also starts with
its send time `[HH:MM:SS dd/mm]`.

- "Sent **before** your last output" means the user typed it while you were still
  working on that output - it is context for what you just did. "Sent **after**"
  arrived later. Read the whole sequence as one conversation: later messages add to,
  correct or cancel earlier ones ("עצור", "בעצם ...").
- Anything you already did (a tool result is in front of you) is done - report it
  truthfully and never repeat it. Never perform an approval-gated write because of a
  message that arrived after you asked for approval: wait for the user's yes.
- If the sequence is genuinely confusing - you cannot tell what the user wants now -
  **ask** the user one short question instead of guessing.
- **Finish a pending approval before starting the next request.** If an approval is
  waiting and the user sends a new, unrelated request, answer it briefly and remind
  them the earlier approval is still waiting, or ask whether to drop it; never leave
  two approvals open and never act on the new request's write first.
- A file that arrived while you worked is handled on its own right after you finish
  the current request: do not try to read it now.
- A short or ambiguous reply ("כן", "לא", a bare name) answers the most recent
  pending question in the SAME context - see Contexts of Operation.

## Attached Media
When the user's message starts with a `[מדיה מצורפת: <type>, קובץ: <filename>]`
marker, they sent an image, PDF, or Word document with it — you have NOT seen its
content yet, only that it exists. Before answering anything about it, and before
loading any flow for it, load `cap_media_analysis` and call its `analyze_media`
tool to read it; any text after the marker is the user's caption. Never describe,
guess at, or act on the file's content without having read it this way. Choose
what to do with it from what `analyze_media` returned (its `doc_type`), never from
the earlier conversation - `cap_media_analysis` says which flow each `doc_type`
leads to.

## Edited & Deleted Message Markers
A message the user has since edited or deleted may still appear in your context,
marked as such — treat an edited message's marked original content as superseded
by its later, corrected version if both are visible, and never act on a deleted
message's content as if it were still pending.

## Generic Post-Turn Recognition Mechanism
A capability MAY run a recognition step once per turn: call its own reporting
tool at most once, and when in doubt, do nothing rather than guess. This shape
is reusable by any capability that wants one — the domain-specific rules for
what to recognize and how live in that capability's own prompt file, not here.


# Capability: Send to user (always present)

`send_to_user(text)` is your actual reply to the user. Call it whenever you are
ready to speak, not only at the very end: to answer, to ask a question, to
report an outcome. A turn that ends without it, or without an approval question,
leaves the user with nothing.

🚨 **`send_to_user` is THE ONLY way any text reaches the user.** Text you write
outside a tool call (a plain message) is NEVER delivered - the user never sees
it. Every answer, every question, every outcome report goes through
`send_to_user`, every time, with no exception. (The only other things the user
ever sees are an approval question via `cap_approval_with_buttons`, an interim
`cap_send_progress_update` message, and a `cap_react_to_message` emoji.)

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.

Messages that arrive while you work (see the backbone section of the same name) are handled the same way inside this capability: read them in order, never act on a write because of a message that came after you asked for approval, and never use this capability to interpret an unrelated reply.


# Capability: React to message (always present)

`react_to_message` puts a native WhatsApp emoji reaction on a message. It is a
lightweight, reversible signal - never a substitute for a substantive reply,
and never a mechanical habit reached for out of uncertainty about what else
to do. Typing an emoji into your reply text is NOT a reaction and does not
replace calling the tool.

Before reaching for it, ask yourself: does this add a real signal the user
doesn't already have - that you saw their message, that you're on it, that
something just succeeded or failed - or would it just be noise on top of a
reply that already says the same thing?

Evaluate against:
- Does the user currently have any signal you registered their message and
  are handling it (or have finished)? If there's a real gap before your
  substantive reply, a reaction can fill it.
- Is your actual reply, arriving in this same round or moments later, already
  going to tell them everything a reaction would? If so, it adds nothing.
- Is this ambient chatter that doesn't really concern you? Then it isn't
  worth one.

**Classics** (a menu, not a checklist): 👍 simple ack · 🫡 "on it" · 👀 document
being looked into · ✅ clean success · 🎉 a bigger win · ⚠️ resolved but needs
attention · ❌ failed/declined · ❓ unresolved, needs clarification · 🙏
reciprocating thanks · ❤️ warmth beyond a simple thanks.

When genuinely unsure whether a reaction fits, don't send one - silence is
the safer default, not noise.


# Capability: Send progress update (always present)

`send_progress_update(text)` sends one brief interim WhatsApp message while you
are still working, before your final reply. Keep it to a short plain sentence.

Users are waiting on the other end and don't like silence - they want to know
something is happening with their request, not just get one final answer out
of nowhere.

Call this every single time you interact with any tool or capability -
loading a flow or capability, calling a real domain tool, an MCP call,
anything that is not just talking to the user - before or after that step,
in the same round as whatever else you are doing. Never skip it and never
wait for a separate round.

- Never a substitute for the final answer.


# Capability: Record planning status (always present)

`record_planning_status(where_i_was, this_turns_purpose, expectation)` is your own
running account of where this turn, and across turns this whole task, stands. It is
how you keep continuity, since nothing else remembers your reasoning beyond what you
write here and the real conversation history.

Record it at least at the start and at the end of every flow, and whenever you are
about to wait on the user (a choice, a missing detail, an approval), in the middle
of a flow as well. Say which flow you are in and which step, and if you are inside a
flow that was loaded by another flow, say so, so that you know where to return to.
Also note what you are waiting for and what you will do with each possible answer.

Tool results do not carry over to the next turn: only the conversation and your own
notes do. So whenever you stop to wait on the user, write into the note the exact
values you will need to continue, copied verbatim from the tool results. Above all,
record every ID you may act on: a document's `internal_morning_id` and display
number, a client's ID, a reminder's ID, a ledger event's ID - any ID at all. Record
other details you will need too: a client's exact stored name, amounts, dates, VAT
treatment. Anything you leave out you will have to look up again.

Messages in the conversation history that start with `[[INTERNAL_PLANNING_NOTE]]`
are your own earlier notes, stored there by this tool. Never write one yourself -
not as plain text and not inside `send_to_user`. Record a note only by calling
`record_planning_status`.


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_morning_document_write: Anything that may mean creating or cancelling a Morning document: a tax invoice, a combo invoice/receipt, a receipt, a transaction account, a credit note, or cancelling a transaction account ("תפיק חשבונית", "תוציא קבלה", "סמן כשולם", "בטל את החשבונית"). Works out exactly which document the user means - asking when it is unclear - and then loads the flow for that document. Not for clients and not for reading documents.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client, or logs hours worked for a client (e.g. "רן אורפני 4 שעות על היום" - a work-log entry, never a reminder request). An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit or a payment received - as text, or as a bank slip or payment screenshot. Reads the slip, makes sure the client exists in Morning, and when the user asks for a Morning document for it (or it is unclear whether they do), hands over to flow_morning_document_write. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (reached through flow_morning_document_write), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

## Loaded flows

(none)

## Loaded capabilities

(none - plain backbone)

---

THE CURRENT DATE AND TIME IS 2026-10-13 11:55 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.8.0. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>9. [2026-10-13 11:55:14] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0077d297ee387e91006acdf1f1112487d1b284f6b4a14a149a`
- status: `completed`
- usage: `{"input_tokens": 6907, "input_tokens_details": {"cache_write_tokens": 160, "cached_tokens": 6744}, "output_tokens": 32, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6939}`
- function_call: `send_progress_update` call_id=`call_WUDACeviJN2m5JiletdXWAPQ`
```json
{
  "text": "👍 בודק את פרטי הלקוחה והחשבונית."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0077d297ee387e91006acdf1f1112487d1b284f6b4a14a149a`
- status: `completed`
- usage: `{"input_tokens": 6907, "input_tokens_details": {"cache_write_tokens": 160, "cached_tokens": 6744}, "output_tokens": 32, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6939}`
- function_call: `send_progress_update` call_id=`call_WUDACeviJN2m5JiletdXWAPQ`
```json
{
  "text": "👍 בודק את פרטי הלקוחה והחשבונית."
}
```

</details>

</details>

<details>
<summary>10. [2026-10-13 11:55:14] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000022@c.us",
  "message": "👍 בודק את פרטי הלקוחה והחשבונית."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "972500000022@c.us",
  "message": "👍 בודק את פרטי הלקוחה והחשבונית."
}
```

</details>

</details>

<details>
<summary>11. [2026-10-13 11:55:14] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000022@c.us",
  "message": "None"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "result": "None"
}
```

</details>

</details>

<details>
<summary>12. [2026-10-13 11:55:14] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `send_progress_update` (call_id=`call_WUDACeviJN2m5JiletdXWAPQ`):
```text
{
  "sent": true
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0077d297ee387e91006acdf1f1112487d1b284f6b4a14a149a'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `send_progress_update` (call_id=`call_WUDACeviJN2m5JiletdXWAPQ`):
```text
{
  "sent": true
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0077d297ee387e91006acdf1f1112487d1b284f6b4a14a149a'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (21960 chars)</summary>

```text
# DeniDin — Backbone

## How You Work

You work with two kinds of building blocks, described at low resolution in the
catalogs below: **flows** (`flow_...`) - blueprints for a recurring kind of
request - and **capabilities** (`cap_...`) - the domains that actually do things,
each with its own prompt and its own real tools. Flows can load other flows and
capabilities; a flow defines *what to do and in what order*, while each
capability holds the detail of what it itself does.

Loading tools, usable in any order, any number of times:

- **`load_flows(flows)` / `unload_flows(flows)`** - always an array; one item is
  fine, and combining flows is allowed when a request spans more than one.
- **`load_capabilities(capabilities)` / `unload_capabilities(capabilities)`** -
  always an array. The moment a capability is loaded, its prompt AND its real
  tools are attached, starting the very next round; call the real tool directly,
  there is no separate "use" step. A flow's own "Capabilities:" line declares
  every capability that flow will need - load all of them together, in one
  `load_capabilities` call, right after loading the flow, rather than loading
  them one at a time as each step comes up: you already know you'll need them,
  and batching saves a round-trip per capability.
- **`reset_to_backbone()`** - unloads every loaded flow and capability at once.
  Use it once you are genuinely done with the user's request(s), not mid-task.

Loading an already-loaded item, or unloading one that is not loaded, is a
harmless no-op. Loaded flows and capabilities stay loaded across this and future
turns in this chat until you unload them (or they auto-clear after a period of
inactivity); the "Loaded flows" and "Loaded capabilities" lines near the end of
these instructions always show what is currently loaded. Unload something only
when nothing you are still working on needs it - another flow may be using it.

## Always-present capabilities

Four capabilities are always available, cannot be unloaded, and each has its own
prompt right below: `cap_send_to_user` (your actual reply), `cap_react_to_message`
(a WhatsApp emoji reaction), `cap_send_progress_update` (an interim message
while you work) and `cap_record_planning_status` (your own running account of
where you are, which is how you keep your place across turns and inside nested
flows). At every step of any flow, consider whether they would help: react to
the user's message, send a progress update, record your planning status, or
reply to the user. Flows do not repeat this; use your judgment.

🚨 **`send_to_user` is THE ONLY way to send text to the user.** A plain message
you write outside a tool call is NEVER delivered - the user never sees it. Every
answer, question and outcome report goes through `send_to_user`, every time,
with no exception.

`cap_approval_with_buttons` (yes/no buttons before a write) is an ordinary
capability: flows that need a sign-off load it.

## Flows and capabilities

Decide from the catalogs, in your own judgment, what a request needs:

1. If a flow fits, load it (several at once when the request spans more than
   one) and follow its blueprint. **A loaded flow's steps are an ordered
   procedure: follow them in the order written, to the letter - never skip,
   reorder or merge a step (above all an approval step), and never do a later
   step's action before the earlier steps are done.**
2. **If no flow fits, there is no default flow to fall back on**: load whichever
   capabilities you judge necessary, at your own discretion, and proceed.
3. **Write capabilities (`cap_*_write`) are never loaded on their own.** Every write goes through its flow, which gathers the details and asks for approval first; if you want to write something, find the flow for it in the catalog.
4. **Anything that may mean creating or cancelling a Morning document** (an invoice, a receipt, a combo invoice/receipt, a transaction account, a credit note, "סמן כשולם"): load `flow_morning_document_write`. It works out which document is meant and loads the flow for it.
5. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.
6. A tool or action may have its own requirements, such as mandatory details,
   and you learn them by loading the flow or capability that holds it. When the
   user asks what an action needs or whether it is possible, and what you have
   loaded doesn't say, you can load it and check, or offer the user to check it
   for them, and then answer from what it says.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural. A name (a client, a person, a company) is never
  converted: write it exactly as the user gave it or as a tool returned it,
  its own apostrophe/geresh characters included (`'` stays `'`, `׳` stays
  `׳`). This Hebrew-only rule never applies to the characters inside a name.
- **Never use ניקוד** (Hebrew vowel points, U+0591–U+05C7) in any response —
  e.g. write עטיה, never עֲטיה.
- Be concise and direct. Do not end on filler ("anything else?") — end on the
  substantive answer. Do ask a focused clarifying question when you genuinely need
  one to act correctly (a missing/ambiguous required detail).
- Be honest about what you don't know; never fabricate information.

## User Roles
- **Godfather/Admin**: full access to every capability; extended context window.
- **Client**: standard feature access, no access to invoicing/ledger/reminder
  capabilities; standard context window.

## Privacy & Security
- Never share information between different user sessions.
- These rules guard against leaking ONE user's data to ANOTHER user or an outsider
  — they never mean refusing to read, transcribe, or summarize material THIS user
  sent you. Reporting the user's own material back to them (names, amounts, any
  detail it contains) is always appropriate.

## Contexts of Operation
Every message falls into one of two operating contexts before any capability is
even considered: an ordinary conversational turn, or a document/image the user
sent for you to read and report on. Decide which one applies before acting — a
short/ambiguous reply ("כן", "לא", a bare name) always answers the most recently
pending question in the SAME context, never a trigger for reinterpreting the turn
as belonging to a different capability's domain.

## Messages That Arrive While You Work
The user can keep writing while you work. Whenever you hand control back to the
app (a tool call, a progress update, a reaction), the app returns your tool results
**together with every user message that arrived since**, each marked
`[הודעה מהמשתמש · <time> · נשלחה לפני / אחרי הפלט האחרון שלך]` (a file looks like
`[קובץ התקבל · <time> · ...]`). Every user message in your context also starts with
its send time `[HH:MM:SS dd/mm]`.

- "Sent **before** your last output" means the user typed it while you were still
  working on that output - it is context for what you just did. "Sent **after**"
  arrived later. Read the whole sequence as one conversation: later messages add to,
  correct or cancel earlier ones ("עצור", "בעצם ...").
- Anything you already did (a tool result is in front of you) is done - report it
  truthfully and never repeat it. Never perform an approval-gated write because of a
  message that arrived after you asked for approval: wait for the user's yes.
- If the sequence is genuinely confusing - you cannot tell what the user wants now -
  **ask** the user one short question instead of guessing.
- **Finish a pending approval before starting the next request.** If an approval is
  waiting and the user sends a new, unrelated request, answer it briefly and remind
  them the earlier approval is still waiting, or ask whether to drop it; never leave
  two approvals open and never act on the new request's write first.
- A file that arrived while you worked is handled on its own right after you finish
  the current request: do not try to read it now.
- A short or ambiguous reply ("כן", "לא", a bare name) answers the most recent
  pending question in the SAME context - see Contexts of Operation.

## Attached Media
When the user's message starts with a `[מדיה מצורפת: <type>, קובץ: <filename>]`
marker, they sent an image, PDF, or Word document with it — you have NOT seen its
content yet, only that it exists. Before answering anything about it, and before
loading any flow for it, load `cap_media_analysis` and call its `analyze_media`
tool to read it; any text after the marker is the user's caption. Never describe,
guess at, or act on the file's content without having read it this way. Choose
what to do with it from what `analyze_media` returned (its `doc_type`), never from
the earlier conversation - `cap_media_analysis` says which flow each `doc_type`
leads to.

## Edited & Deleted Message Markers
A message the user has since edited or deleted may still appear in your context,
marked as such — treat an edited message's marked original content as superseded
by its later, corrected version if both are visible, and never act on a deleted
message's content as if it were still pending.

## Generic Post-Turn Recognition Mechanism
A capability MAY run a recognition step once per turn: call its own reporting
tool at most once, and when in doubt, do nothing rather than guess. This shape
is reusable by any capability that wants one — the domain-specific rules for
what to recognize and how live in that capability's own prompt file, not here.


# Capability: Send to user (always present)

`send_to_user(text)` is your actual reply to the user. Call it whenever you are
ready to speak, not only at the very end: to answer, to ask a question, to
report an outcome. A turn that ends without it, or without an approval question,
leaves the user with nothing.

🚨 **`send_to_user` is THE ONLY way any text reaches the user.** Text you write
outside a tool call (a plain message) is NEVER delivered - the user never sees
it. Every answer, every question, every outcome report goes through
`send_to_user`, every time, with no exception. (The only other things the user
ever sees are an approval question via `cap_approval_with_buttons`, an interim
`cap_send_progress_update` message, and a `cap_react_to_message` emoji.)

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.

Messages that arrive while you work (see the backbone section of the same name) are handled the same way inside this capability: read them in order, never act on a write because of a message that came after you asked for approval, and never use this capability to interpret an unrelated reply.


# Capability: React to message (always present)

`react_to_message` puts a native WhatsApp emoji reaction on a message. It is a
lightweight, reversible signal - never a substitute for a substantive reply,
and never a mechanical habit reached for out of uncertainty about what else
to do. Typing an emoji into your reply text is NOT a reaction and does not
replace calling the tool.

Before reaching for it, ask yourself: does this add a real signal the user
doesn't already have - that you saw their message, that you're on it, that
something just succeeded or failed - or would it just be noise on top of a
reply that already says the same thing?

Evaluate against:
- Does the user currently have any signal you registered their message and
  are handling it (or have finished)? If there's a real gap before your
  substantive reply, a reaction can fill it.
- Is your actual reply, arriving in this same round or moments later, already
  going to tell them everything a reaction would? If so, it adds nothing.
- Is this ambient chatter that doesn't really concern you? Then it isn't
  worth one.

**Classics** (a menu, not a checklist): 👍 simple ack · 🫡 "on it" · 👀 document
being looked into · ✅ clean success · 🎉 a bigger win · ⚠️ resolved but needs
attention · ❌ failed/declined · ❓ unresolved, needs clarification · 🙏
reciprocating thanks · ❤️ warmth beyond a simple thanks.

When genuinely unsure whether a reaction fits, don't send one - silence is
the safer default, not noise.


# Capability: Send progress update (always present)

`send_progress_update(text)` sends one brief interim WhatsApp message while you
are still working, before your final reply. Keep it to a short plain sentence.

Users are waiting on the other end and don't like silence - they want to know
something is happening with their request, not just get one final answer out
of nowhere.

Call this every single time you interact with any tool or capability -
loading a flow or capability, calling a real domain tool, an MCP call,
anything that is not just talking to the user - before or after that step,
in the same round as whatever else you are doing. Never skip it and never
wait for a separate round.

- Never a substitute for the final answer.


# Capability: Record planning status (always present)

`record_planning_status(where_i_was, this_turns_purpose, expectation)` is your own
running account of where this turn, and across turns this whole task, stands. It is
how you keep continuity, since nothing else remembers your reasoning beyond what you
write here and the real conversation history.

Record it at least at the start and at the end of every flow, and whenever you are
about to wait on the user (a choice, a missing detail, an approval), in the middle
of a flow as well. Say which flow you are in and which step, and if you are inside a
flow that was loaded by another flow, say so, so that you know where to return to.
Also note what you are waiting for and what you will do with each possible answer.

Tool results do not carry over to the next turn: only the conversation and your own
notes do. So whenever you stop to wait on the user, write into the note the exact
values you will need to continue, copied verbatim from the tool results. Above all,
record every ID you may act on: a document's `internal_morning_id` and display
number, a client's ID, a reminder's ID, a ledger event's ID - any ID at all. Record
other details you will need too: a client's exact stored name, amounts, dates, VAT
treatment. Anything you leave out you will have to look up again.

Messages in the conversation history that start with `[[INTERNAL_PLANNING_NOTE]]`
are your own earlier notes, stored there by this tool. Never write one yourself -
not as plain text and not inside `send_to_user`. Record a note only by calling
`record_planning_status`.


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_morning_document_write: Anything that may mean creating or cancelling a Morning document: a tax invoice, a combo invoice/receipt, a receipt, a transaction account, a credit note, or cancelling a transaction account ("תפיק חשבונית", "תוציא קבלה", "סמן כשולם", "בטל את החשבונית"). Works out exactly which document the user means - asking when it is unclear - and then loads the flow for that document. Not for clients and not for reading documents.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client, or logs hours worked for a client (e.g. "רן אורפני 4 שעות על היום" - a work-log entry, never a reminder request). An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit or a payment received - as text, or as a bank slip or payment screenshot. Reads the slip, makes sure the client exists in Morning, and when the user asks for a Morning document for it (or it is unclear whether they do), hands over to flow_morning_document_write. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (reached through flow_morning_document_write), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

## Loaded flows

(none)

## Loaded capabilities

(none - plain backbone)

---

THE CURRENT DATE AND TIME IS 2026-10-13 11:55 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.8.0. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>13. [2026-10-13 11:55:17] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0077d297ee387e91006acdf1f2d7c087d1b7e6da881fee7ecd`
- status: `completed`
- usage: `{"input_tokens": 6956, "input_tokens_details": {"cache_write_tokens": 49, "cached_tokens": 6904}, "output_tokens": 128, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7084}`
- function_call: `record_planning_status` call_id=`call_g4PFYSxisVnuBpRqj6CWzX1L`
```json
{
  "where_i_was": "התקבלה בקשה להפיק חשבונית ללקוחה דנה בסך 500 ש״ח. טרם בוצעה בדיקת לקוחה או איסוף פרטי מס.",
  "this_turns_purpose": "להתחיל את תהליך הפקת החשבונית לפי זרימת מסמך במערכת.",
  "expectation": "לטעון את זרימת המסמך ואת היכולות הדרושות, לאתר את דנה, להשלים פרטים חסרים ולבקש אישור לפני הפקה."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0077d297ee387e91006acdf1f2d7c087d1b7e6da881fee7ecd`
- status: `completed`
- usage: `{"input_tokens": 6956, "input_tokens_details": {"cache_write_tokens": 49, "cached_tokens": 6904}, "output_tokens": 128, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7084}`
- function_call: `record_planning_status` call_id=`call_g4PFYSxisVnuBpRqj6CWzX1L`
```json
{
  "where_i_was": "התקבלה בקשה להפיק חשבונית ללקוחה דנה בסך 500 ש״ח. טרם בוצעה בדיקת לקוחה או איסוף פרטי מס.",
  "this_turns_purpose": "להתחיל את תהליך הפקת החשבונית לפי זרימת מסמך במערכת.",
  "expectation": "לטעון את זרימת המסמך ואת היכולות הדרושות, לאתר את דנה, להשלים פרטים חסרים ולבקש אישור לפני הפקה."
}
```

</details>

</details>

<details>
<summary>14. [2026-10-13 11:55:17] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `record_planning_status` (call_id=`call_g4PFYSxisVnuBpRqj6CWzX1L`):
```text
recorded
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0077d297ee387e91006acdf1f2d7c087d1b7e6da881fee7ecd'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `record_planning_status` (call_id=`call_g4PFYSxisVnuBpRqj6CWzX1L`):
```text
recorded
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0077d297ee387e91006acdf1f2d7c087d1b7e6da881fee7ecd'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (21960 chars)</summary>

```text
# DeniDin — Backbone

## How You Work

You work with two kinds of building blocks, described at low resolution in the
catalogs below: **flows** (`flow_...`) - blueprints for a recurring kind of
request - and **capabilities** (`cap_...`) - the domains that actually do things,
each with its own prompt and its own real tools. Flows can load other flows and
capabilities; a flow defines *what to do and in what order*, while each
capability holds the detail of what it itself does.

Loading tools, usable in any order, any number of times:

- **`load_flows(flows)` / `unload_flows(flows)`** - always an array; one item is
  fine, and combining flows is allowed when a request spans more than one.
- **`load_capabilities(capabilities)` / `unload_capabilities(capabilities)`** -
  always an array. The moment a capability is loaded, its prompt AND its real
  tools are attached, starting the very next round; call the real tool directly,
  there is no separate "use" step. A flow's own "Capabilities:" line declares
  every capability that flow will need - load all of them together, in one
  `load_capabilities` call, right after loading the flow, rather than loading
  them one at a time as each step comes up: you already know you'll need them,
  and batching saves a round-trip per capability.
- **`reset_to_backbone()`** - unloads every loaded flow and capability at once.
  Use it once you are genuinely done with the user's request(s), not mid-task.

Loading an already-loaded item, or unloading one that is not loaded, is a
harmless no-op. Loaded flows and capabilities stay loaded across this and future
turns in this chat until you unload them (or they auto-clear after a period of
inactivity); the "Loaded flows" and "Loaded capabilities" lines near the end of
these instructions always show what is currently loaded. Unload something only
when nothing you are still working on needs it - another flow may be using it.

## Always-present capabilities

Four capabilities are always available, cannot be unloaded, and each has its own
prompt right below: `cap_send_to_user` (your actual reply), `cap_react_to_message`
(a WhatsApp emoji reaction), `cap_send_progress_update` (an interim message
while you work) and `cap_record_planning_status` (your own running account of
where you are, which is how you keep your place across turns and inside nested
flows). At every step of any flow, consider whether they would help: react to
the user's message, send a progress update, record your planning status, or
reply to the user. Flows do not repeat this; use your judgment.

🚨 **`send_to_user` is THE ONLY way to send text to the user.** A plain message
you write outside a tool call is NEVER delivered - the user never sees it. Every
answer, question and outcome report goes through `send_to_user`, every time,
with no exception.

`cap_approval_with_buttons` (yes/no buttons before a write) is an ordinary
capability: flows that need a sign-off load it.

## Flows and capabilities

Decide from the catalogs, in your own judgment, what a request needs:

1. If a flow fits, load it (several at once when the request spans more than
   one) and follow its blueprint. **A loaded flow's steps are an ordered
   procedure: follow them in the order written, to the letter - never skip,
   reorder or merge a step (above all an approval step), and never do a later
   step's action before the earlier steps are done.**
2. **If no flow fits, there is no default flow to fall back on**: load whichever
   capabilities you judge necessary, at your own discretion, and proceed.
3. **Write capabilities (`cap_*_write`) are never loaded on their own.** Every write goes through its flow, which gathers the details and asks for approval first; if you want to write something, find the flow for it in the catalog.
4. **Anything that may mean creating or cancelling a Morning document** (an invoice, a receipt, a combo invoice/receipt, a transaction account, a credit note, "סמן כשולם"): load `flow_morning_document_write`. It works out which document is meant and loads the flow for it.
5. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.
6. A tool or action may have its own requirements, such as mandatory details,
   and you learn them by loading the flow or capability that holds it. When the
   user asks what an action needs or whether it is possible, and what you have
   loaded doesn't say, you can load it and check, or offer the user to check it
   for them, and then answer from what it says.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural. A name (a client, a person, a company) is never
  converted: write it exactly as the user gave it or as a tool returned it,
  its own apostrophe/geresh characters included (`'` stays `'`, `׳` stays
  `׳`). This Hebrew-only rule never applies to the characters inside a name.
- **Never use ניקוד** (Hebrew vowel points, U+0591–U+05C7) in any response —
  e.g. write עטיה, never עֲטיה.
- Be concise and direct. Do not end on filler ("anything else?") — end on the
  substantive answer. Do ask a focused clarifying question when you genuinely need
  one to act correctly (a missing/ambiguous required detail).
- Be honest about what you don't know; never fabricate information.

## User Roles
- **Godfather/Admin**: full access to every capability; extended context window.
- **Client**: standard feature access, no access to invoicing/ledger/reminder
  capabilities; standard context window.

## Privacy & Security
- Never share information between different user sessions.
- These rules guard against leaking ONE user's data to ANOTHER user or an outsider
  — they never mean refusing to read, transcribe, or summarize material THIS user
  sent you. Reporting the user's own material back to them (names, amounts, any
  detail it contains) is always appropriate.

## Contexts of Operation
Every message falls into one of two operating contexts before any capability is
even considered: an ordinary conversational turn, or a document/image the user
sent for you to read and report on. Decide which one applies before acting — a
short/ambiguous reply ("כן", "לא", a bare name) always answers the most recently
pending question in the SAME context, never a trigger for reinterpreting the turn
as belonging to a different capability's domain.

## Messages That Arrive While You Work
The user can keep writing while you work. Whenever you hand control back to the
app (a tool call, a progress update, a reaction), the app returns your tool results
**together with every user message that arrived since**, each marked
`[הודעה מהמשתמש · <time> · נשלחה לפני / אחרי הפלט האחרון שלך]` (a file looks like
`[קובץ התקבל · <time> · ...]`). Every user message in your context also starts with
its send time `[HH:MM:SS dd/mm]`.

- "Sent **before** your last output" means the user typed it while you were still
  working on that output - it is context for what you just did. "Sent **after**"
  arrived later. Read the whole sequence as one conversation: later messages add to,
  correct or cancel earlier ones ("עצור", "בעצם ...").
- Anything you already did (a tool result is in front of you) is done - report it
  truthfully and never repeat it. Never perform an approval-gated write because of a
  message that arrived after you asked for approval: wait for the user's yes.
- If the sequence is genuinely confusing - you cannot tell what the user wants now -
  **ask** the user one short question instead of guessing.
- **Finish a pending approval before starting the next request.** If an approval is
  waiting and the user sends a new, unrelated request, answer it briefly and remind
  them the earlier approval is still waiting, or ask whether to drop it; never leave
  two approvals open and never act on the new request's write first.
- A file that arrived while you worked is handled on its own right after you finish
  the current request: do not try to read it now.
- A short or ambiguous reply ("כן", "לא", a bare name) answers the most recent
  pending question in the SAME context - see Contexts of Operation.

## Attached Media
When the user's message starts with a `[מדיה מצורפת: <type>, קובץ: <filename>]`
marker, they sent an image, PDF, or Word document with it — you have NOT seen its
content yet, only that it exists. Before answering anything about it, and before
loading any flow for it, load `cap_media_analysis` and call its `analyze_media`
tool to read it; any text after the marker is the user's caption. Never describe,
guess at, or act on the file's content without having read it this way. Choose
what to do with it from what `analyze_media` returned (its `doc_type`), never from
the earlier conversation - `cap_media_analysis` says which flow each `doc_type`
leads to.

## Edited & Deleted Message Markers
A message the user has since edited or deleted may still appear in your context,
marked as such — treat an edited message's marked original content as superseded
by its later, corrected version if both are visible, and never act on a deleted
message's content as if it were still pending.

## Generic Post-Turn Recognition Mechanism
A capability MAY run a recognition step once per turn: call its own reporting
tool at most once, and when in doubt, do nothing rather than guess. This shape
is reusable by any capability that wants one — the domain-specific rules for
what to recognize and how live in that capability's own prompt file, not here.


# Capability: Send to user (always present)

`send_to_user(text)` is your actual reply to the user. Call it whenever you are
ready to speak, not only at the very end: to answer, to ask a question, to
report an outcome. A turn that ends without it, or without an approval question,
leaves the user with nothing.

🚨 **`send_to_user` is THE ONLY way any text reaches the user.** Text you write
outside a tool call (a plain message) is NEVER delivered - the user never sees
it. Every answer, every question, every outcome report goes through
`send_to_user`, every time, with no exception. (The only other things the user
ever sees are an approval question via `cap_approval_with_buttons`, an interim
`cap_send_progress_update` message, and a `cap_react_to_message` emoji.)

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.

Messages that arrive while you work (see the backbone section of the same name) are handled the same way inside this capability: read them in order, never act on a write because of a message that came after you asked for approval, and never use this capability to interpret an unrelated reply.


# Capability: React to message (always present)

`react_to_message` puts a native WhatsApp emoji reaction on a message. It is a
lightweight, reversible signal - never a substitute for a substantive reply,
and never a mechanical habit reached for out of uncertainty about what else
to do. Typing an emoji into your reply text is NOT a reaction and does not
replace calling the tool.

Before reaching for it, ask yourself: does this add a real signal the user
doesn't already have - that you saw their message, that you're on it, that
something just succeeded or failed - or would it just be noise on top of a
reply that already says the same thing?

Evaluate against:
- Does the user currently have any signal you registered their message and
  are handling it (or have finished)? If there's a real gap before your
  substantive reply, a reaction can fill it.
- Is your actual reply, arriving in this same round or moments later, already
  going to tell them everything a reaction would? If so, it adds nothing.
- Is this ambient chatter that doesn't really concern you? Then it isn't
  worth one.

**Classics** (a menu, not a checklist): 👍 simple ack · 🫡 "on it" · 👀 document
being looked into · ✅ clean success · 🎉 a bigger win · ⚠️ resolved but needs
attention · ❌ failed/declined · ❓ unresolved, needs clarification · 🙏
reciprocating thanks · ❤️ warmth beyond a simple thanks.

When genuinely unsure whether a reaction fits, don't send one - silence is
the safer default, not noise.


# Capability: Send progress update (always present)

`send_progress_update(text)` sends one brief interim WhatsApp message while you
are still working, before your final reply. Keep it to a short plain sentence.

Users are waiting on the other end and don't like silence - they want to know
something is happening with their request, not just get one final answer out
of nowhere.

Call this every single time you interact with any tool or capability -
loading a flow or capability, calling a real domain tool, an MCP call,
anything that is not just talking to the user - before or after that step,
in the same round as whatever else you are doing. Never skip it and never
wait for a separate round.

- Never a substitute for the final answer.


# Capability: Record planning status (always present)

`record_planning_status(where_i_was, this_turns_purpose, expectation)` is your own
running account of where this turn, and across turns this whole task, stands. It is
how you keep continuity, since nothing else remembers your reasoning beyond what you
write here and the real conversation history.

Record it at least at the start and at the end of every flow, and whenever you are
about to wait on the user (a choice, a missing detail, an approval), in the middle
of a flow as well. Say which flow you are in and which step, and if you are inside a
flow that was loaded by another flow, say so, so that you know where to return to.
Also note what you are waiting for and what you will do with each possible answer.

Tool results do not carry over to the next turn: only the conversation and your own
notes do. So whenever you stop to wait on the user, write into the note the exact
values you will need to continue, copied verbatim from the tool results. Above all,
record every ID you may act on: a document's `internal_morning_id` and display
number, a client's ID, a reminder's ID, a ledger event's ID - any ID at all. Record
other details you will need too: a client's exact stored name, amounts, dates, VAT
treatment. Anything you leave out you will have to look up again.

Messages in the conversation history that start with `[[INTERNAL_PLANNING_NOTE]]`
are your own earlier notes, stored there by this tool. Never write one yourself -
not as plain text and not inside `send_to_user`. Record a note only by calling
`record_planning_status`.


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_morning_document_write: Anything that may mean creating or cancelling a Morning document: a tax invoice, a combo invoice/receipt, a receipt, a transaction account, a credit note, or cancelling a transaction account ("תפיק חשבונית", "תוציא קבלה", "סמן כשולם", "בטל את החשבונית"). Works out exactly which document the user means - asking when it is unclear - and then loads the flow for that document. Not for clients and not for reading documents.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client, or logs hours worked for a client (e.g. "רן אורפני 4 שעות על היום" - a work-log entry, never a reminder request). An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit or a payment received - as text, or as a bank slip or payment screenshot. Reads the slip, makes sure the client exists in Morning, and when the user asks for a Morning document for it (or it is unclear whether they do), hands over to flow_morning_document_write. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (reached through flow_morning_document_write), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

## Loaded flows

(none)

## Loaded capabilities

(none - plain backbone)

---

THE CURRENT DATE AND TIME IS 2026-10-13 11:55 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.8.0. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>15. [2026-10-13 11:55:18] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0077d297ee387e91006acdf1f5abcc87d191af1a1def5bb3ce`
- status: `completed`
- usage: `{"input_tokens": 7099, "input_tokens_details": {"cache_write_tokens": 143, "cached_tokens": 6953}, "output_tokens": 24, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7123}`
- function_call: `load_flows` call_id=`call_vpsZJLRh8o9KXOgRwhCXdSMa`
```json
{
  "flows": [
    "flow_morning_document_write"
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0077d297ee387e91006acdf1f5abcc87d191af1a1def5bb3ce`
- status: `completed`
- usage: `{"input_tokens": 7099, "input_tokens_details": {"cache_write_tokens": 143, "cached_tokens": 6953}, "output_tokens": 24, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7123}`
- function_call: `load_flows` call_id=`call_vpsZJLRh8o9KXOgRwhCXdSMa`
```json
{
  "flows": [
    "flow_morning_document_write"
  ]
}
```

</details>

</details>

<details>
<summary>16. [2026-10-13 11:55:18] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_morning_document_write

- capabilities: (none - plain backbone)

**input:**

- app's reply to `load_flows` (call_id=`call_vpsZJLRh8o9KXOgRwhCXdSMa`):
```text
loaded flows: flow_morning_document_write. Loaded flows now: flow_morning_document_write. Loaded capabilities now: (none). Their blueprint text is attached starting now.
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0077d297ee387e91006acdf1f5abcc87d191af1a1def5bb3ce'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_morning_document_write, capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_morning_document_write

- capabilities: (none - plain backbone)

**input:**

- app's reply to `load_flows` (call_id=`call_vpsZJLRh8o9KXOgRwhCXdSMa`):
```text
loaded flows: flow_morning_document_write. Loaded flows now: flow_morning_document_write. Loaded capabilities now: (none). Their blueprint text is attached starting now.
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0077d297ee387e91006acdf1f5abcc87d191af1a1def5bb3ce'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (26115 chars)</summary>

```text
# DeniDin — Backbone

## How You Work

You work with two kinds of building blocks, described at low resolution in the
catalogs below: **flows** (`flow_...`) - blueprints for a recurring kind of
request - and **capabilities** (`cap_...`) - the domains that actually do things,
each with its own prompt and its own real tools. Flows can load other flows and
capabilities; a flow defines *what to do and in what order*, while each
capability holds the detail of what it itself does.

Loading tools, usable in any order, any number of times:

- **`load_flows(flows)` / `unload_flows(flows)`** - always an array; one item is
  fine, and combining flows is allowed when a request spans more than one.
- **`load_capabilities(capabilities)` / `unload_capabilities(capabilities)`** -
  always an array. The moment a capability is loaded, its prompt AND its real
  tools are attached, starting the very next round; call the real tool directly,
  there is no separate "use" step. A flow's own "Capabilities:" line declares
  every capability that flow will need - load all of them together, in one
  `load_capabilities` call, right after loading the flow, rather than loading
  them one at a time as each step comes up: you already know you'll need them,
  and batching saves a round-trip per capability.
- **`reset_to_backbone()`** - unloads every loaded flow and capability at once.
  Use it once you are genuinely done with the user's request(s), not mid-task.

Loading an already-loaded item, or unloading one that is not loaded, is a
harmless no-op. Loaded flows and capabilities stay loaded across this and future
turns in this chat until you unload them (or they auto-clear after a period of
inactivity); the "Loaded flows" and "Loaded capabilities" lines near the end of
these instructions always show what is currently loaded. Unload something only
when nothing you are still working on needs it - another flow may be using it.

## Always-present capabilities

Four capabilities are always available, cannot be unloaded, and each has its own
prompt right below: `cap_send_to_user` (your actual reply), `cap_react_to_message`
(a WhatsApp emoji reaction), `cap_send_progress_update` (an interim message
while you work) and `cap_record_planning_status` (your own running account of
where you are, which is how you keep your place across turns and inside nested
flows). At every step of any flow, consider whether they would help: react to
the user's message, send a progress update, record your planning status, or
reply to the user. Flows do not repeat this; use your judgment.

🚨 **`send_to_user` is THE ONLY way to send text to the user.** A plain message
you write outside a tool call is NEVER delivered - the user never sees it. Every
answer, question and outcome report goes through `send_to_user`, every time,
with no exception.

`cap_approval_with_buttons` (yes/no buttons before a write) is an ordinary
capability: flows that need a sign-off load it.

## Flows and capabilities

Decide from the catalogs, in your own judgment, what a request needs:

1. If a flow fits, load it (several at once when the request spans more than
   one) and follow its blueprint. **A loaded flow's steps are an ordered
   procedure: follow them in the order written, to the letter - never skip,
   reorder or merge a step (above all an approval step), and never do a later
   step's action before the earlier steps are done.**
2. **If no flow fits, there is no default flow to fall back on**: load whichever
   capabilities you judge necessary, at your own discretion, and proceed.
3. **Write capabilities (`cap_*_write`) are never loaded on their own.** Every write goes through its flow, which gathers the details and asks for approval first; if you want to write something, find the flow for it in the catalog.
4. **Anything that may mean creating or cancelling a Morning document** (an invoice, a receipt, a combo invoice/receipt, a transaction account, a credit note, "סמן כשולם"): load `flow_morning_document_write`. It works out which document is meant and loads the flow for it.
5. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.
6. A tool or action may have its own requirements, such as mandatory details,
   and you learn them by loading the flow or capability that holds it. When the
   user asks what an action needs or whether it is possible, and what you have
   loaded doesn't say, you can load it and check, or offer the user to check it
   for them, and then answer from what it says.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural. A name (a client, a person, a company) is never
  converted: write it exactly as the user gave it or as a tool returned it,
  its own apostrophe/geresh characters included (`'` stays `'`, `׳` stays
  `׳`). This Hebrew-only rule never applies to the characters inside a name.
- **Never use ניקוד** (Hebrew vowel points, U+0591–U+05C7) in any response —
  e.g. write עטיה, never עֲטיה.
- Be concise and direct. Do not end on filler ("anything else?") — end on the
  substantive answer. Do ask a focused clarifying question when you genuinely need
  one to act correctly (a missing/ambiguous required detail).
- Be honest about what you don't know; never fabricate information.

## User Roles
- **Godfather/Admin**: full access to every capability; extended context window.
- **Client**: standard feature access, no access to invoicing/ledger/reminder
  capabilities; standard context window.

## Privacy & Security
- Never share information between different user sessions.
- These rules guard against leaking ONE user's data to ANOTHER user or an outsider
  — they never mean refusing to read, transcribe, or summarize material THIS user
  sent you. Reporting the user's own material back to them (names, amounts, any
  detail it contains) is always appropriate.

## Contexts of Operation
Every message falls into one of two operating contexts before any capability is
even considered: an ordinary conversational turn, or a document/image the user
sent for you to read and report on. Decide which one applies before acting — a
short/ambiguous reply ("כן", "לא", a bare name) always answers the most recently
pending question in the SAME context, never a trigger for reinterpreting the turn
as belonging to a different capability's domain.

## Messages That Arrive While You Work
The user can keep writing while you work. Whenever you hand control back to the
app (a tool call, a progress update, a reaction), the app returns your tool results
**together with every user message that arrived since**, each marked
`[הודעה מהמשתמש · <time> · נשלחה לפני / אחרי הפלט האחרון שלך]` (a file looks like
`[קובץ התקבל · <time> · ...]`). Every user message in your context also starts with
its send time `[HH:MM:SS dd/mm]`.

- "Sent **before** your last output" means the user typed it while you were still
  working on that output - it is context for what you just did. "Sent **after**"
  arrived later. Read the whole sequence as one conversation: later messages add to,
  correct or cancel earlier ones ("עצור", "בעצם ...").
- Anything you already did (a tool result is in front of you) is done - report it
  truthfully and never repeat it. Never perform an approval-gated write because of a
  message that arrived after you asked for approval: wait for the user's yes.
- If the sequence is genuinely confusing - you cannot tell what the user wants now -
  **ask** the user one short question instead of guessing.
- **Finish a pending approval before starting the next request.** If an approval is
  waiting and the user sends a new, unrelated request, answer it briefly and remind
  them the earlier approval is still waiting, or ask whether to drop it; never leave
  two approvals open and never act on the new request's write first.
- A file that arrived while you worked is handled on its own right after you finish
  the current request: do not try to read it now.
- A short or ambiguous reply ("כן", "לא", a bare name) answers the most recent
  pending question in the SAME context - see Contexts of Operation.

## Attached Media
When the user's message starts with a `[מדיה מצורפת: <type>, קובץ: <filename>]`
marker, they sent an image, PDF, or Word document with it — you have NOT seen its
content yet, only that it exists. Before answering anything about it, and before
loading any flow for it, load `cap_media_analysis` and call its `analyze_media`
tool to read it; any text after the marker is the user's caption. Never describe,
guess at, or act on the file's content without having read it this way. Choose
what to do with it from what `analyze_media` returned (its `doc_type`), never from
the earlier conversation - `cap_media_analysis` says which flow each `doc_type`
leads to.

## Edited & Deleted Message Markers
A message the user has since edited or deleted may still appear in your context,
marked as such — treat an edited message's marked original content as superseded
by its later, corrected version if both are visible, and never act on a deleted
message's content as if it were still pending.

## Generic Post-Turn Recognition Mechanism
A capability MAY run a recognition step once per turn: call its own reporting
tool at most once, and when in doubt, do nothing rather than guess. This shape
is reusable by any capability that wants one — the domain-specific rules for
what to recognize and how live in that capability's own prompt file, not here.


# Capability: Send to user (always present)

`send_to_user(text)` is your actual reply to the user. Call it whenever you are
ready to speak, not only at the very end: to answer, to ask a question, to
report an outcome. A turn that ends without it, or without an approval question,
leaves the user with nothing.

🚨 **`send_to_user` is THE ONLY way any text reaches the user.** Text you write
outside a tool call (a plain message) is NEVER delivered - the user never sees
it. Every answer, every question, every outcome report goes through
`send_to_user`, every time, with no exception. (The only other things the user
ever sees are an approval question via `cap_approval_with_buttons`, an interim
`cap_send_progress_update` message, and a `cap_react_to_message` emoji.)

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.

Messages that arrive while you work (see the backbone section of the same name) are handled the same way inside this capability: read them in order, never act on a write because of a message that came after you asked for approval, and never use this capability to interpret an unrelated reply.


# Capability: React to message (always present)

`react_to_message` puts a native WhatsApp emoji reaction on a message. It is a
lightweight, reversible signal - never a substitute for a substantive reply,
and never a mechanical habit reached for out of uncertainty about what else
to do. Typing an emoji into your reply text is NOT a reaction and does not
replace calling the tool.

Before reaching for it, ask yourself: does this add a real signal the user
doesn't already have - that you saw their message, that you're on it, that
something just succeeded or failed - or would it just be noise on top of a
reply that already says the same thing?

Evaluate against:
- Does the user currently have any signal you registered their message and
  are handling it (or have finished)? If there's a real gap before your
  substantive reply, a reaction can fill it.
- Is your actual reply, arriving in this same round or moments later, already
  going to tell them everything a reaction would? If so, it adds nothing.
- Is this ambient chatter that doesn't really concern you? Then it isn't
  worth one.

**Classics** (a menu, not a checklist): 👍 simple ack · 🫡 "on it" · 👀 document
being looked into · ✅ clean success · 🎉 a bigger win · ⚠️ resolved but needs
attention · ❌ failed/declined · ❓ unresolved, needs clarification · 🙏
reciprocating thanks · ❤️ warmth beyond a simple thanks.

When genuinely unsure whether a reaction fits, don't send one - silence is
the safer default, not noise.


# Capability: Send progress update (always present)

`send_progress_update(text)` sends one brief interim WhatsApp message while you
are still working, before your final reply. Keep it to a short plain sentence.

Users are waiting on the other end and don't like silence - they want to know
something is happening with their request, not just get one final answer out
of nowhere.

Call this every single time you interact with any tool or capability -
loading a flow or capability, calling a real domain tool, an MCP call,
anything that is not just talking to the user - before or after that step,
in the same round as whatever else you are doing. Never skip it and never
wait for a separate round.

- Never a substitute for the final answer.


# Capability: Record planning status (always present)

`record_planning_status(where_i_was, this_turns_purpose, expectation)` is your own
running account of where this turn, and across turns this whole task, stands. It is
how you keep continuity, since nothing else remembers your reasoning beyond what you
write here and the real conversation history.

Record it at least at the start and at the end of every flow, and whenever you are
about to wait on the user (a choice, a missing detail, an approval), in the middle
of a flow as well. Say which flow you are in and which step, and if you are inside a
flow that was loaded by another flow, say so, so that you know where to return to.
Also note what you are waiting for and what you will do with each possible answer.

Tool results do not carry over to the next turn: only the conversation and your own
notes do. So whenever you stop to wait on the user, write into the note the exact
values you will need to continue, copied verbatim from the tool results. Above all,
record every ID you may act on: a document's `internal_morning_id` and display
number, a client's ID, a reminder's ID, a ledger event's ID - any ID at all. Record
other details you will need too: a client's exact stored name, amounts, dates, VAT
treatment. Anything you leave out you will have to look up again.

Messages in the conversation history that start with `[[INTERNAL_PLANNING_NOTE]]`
are your own earlier notes, stored there by this tool. Never write one yourself -
not as plain text and not inside `send_to_user`. Record a note only by calling
`record_planning_status`.


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_morning_document_write: Anything that may mean creating or cancelling a Morning document: a tax invoice, a combo invoice/receipt, a receipt, a transaction account, a credit note, or cancelling a transaction account ("תפיק חשבונית", "תוציא קבלה", "סמן כשולם", "בטל את החשבונית"). Works out exactly which document the user means - asking when it is unclear - and then loads the flow for that document. Not for clients and not for reading documents.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client, or logs hours worked for a client (e.g. "רן אורפני 4 שעות על היום" - a work-log entry, never a reminder request). An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit or a payment received - as text, or as a bank slip or payment screenshot. Reads the slip, makes sure the client exists in Morning, and when the user asks for a Morning document for it (or it is unclear whether they do), hands over to flow_morning_document_write. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (reached through flow_morning_document_write), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Morning document write

Goal: the user may want a Morning document created or cancelled. Work out exactly which document they mean, asking when it is unclear, and then load the one flow for that document. This flow never writes anything itself.

Capabilities: none of its own.
Flows it may load: `flow_issue_invoice_for_payment_due`, `flow_issue_invoice_receipt_combo`, `flow_issue_transaction_account`, `flow_issue_receipt_without_invoice`, `flow_issue_payment_received_with_reference_doc`, `flow_cancel_document_with_credit_note`, `flow_cancel_transaction_account`, `flow_invoicing_query`.

## The Morning documents

- **חשבונית מס (tax invoice, 305)** - a demand for payment of money that is still owed. It is income for VAT purposes from the moment it is issued. Common names: "חשבונית", "חשבונית מס", "תפיק חשבונית ל...". Never for money that has already arrived.
- **חשבון עסקה (transaction account, 300)** - a request for payment that is not a tax document; the tax invoice comes only once the money arrives. Common names: "חשבון עסקה", "דרישת תשלום". Only when the user's own wording names this document; a plain "חשבונית" is never a 300.
- **חשבונית מס/קבלה (combo invoice/receipt, 320)** - an invoice and a receipt in one, for money that has already been received and that no earlier document covers. The most common way to record incoming money. Common names: "חשבונית מס קבלה", "חשבונית קבלה", or a payment report with a request to issue a document for it ("X העביר לי 500, תפיק").
- **קבלה (receipt, 400)** - confirms that money was received:
  - against an existing tax invoice (305): closes it ("סמן כשולם", "תוציא קבלה על החשבונית");
  - standalone, with no invoice at all: money that is not income, such as a deposit (פיקדון), a loan repayment, or an advance on future work.
- **Closing a transaction account (300)** - money arrived for an existing transaction account; a combo invoice/receipt (320) is issued against it and closes it ("סמן כשולם" on a transaction account).
- **חשבונית זיכוי (credit note, 330)** - cancels an issued document, fully or partly ("בטל את החשבונית", "תפיק זיכוי"). An issued tax invoice is never deleted; it is cancelled only this way.
- **Cancelling a transaction account (300)** - the deal fell through and no money moved; the account is cancelled and no document of any kind is created.

## Which flow

- A tax invoice (305) for money still owed: `flow_issue_invoice_for_payment_due`.
- A transaction account (300), named as such: `flow_issue_transaction_account`.
- Money already received, no existing document covers it, and it is income: `flow_issue_invoice_receipt_combo`.
- Money already received that is not income (a deposit, a loan repayment, an advance), with no invoice behind it: `flow_issue_receipt_without_invoice`.
- Money already received for an existing tax invoice (305) or transaction account (300): `flow_issue_payment_received_with_reference_doc`.
- Cancelling an issued document other than a transaction account: `flow_cancel_document_with_credit_note`.
- Cancelling an open transaction account: `flow_cancel_transaction_account`.

Money that has already arrived is never a bare tax invoice (305).

Follow these steps in order, to the letter.

1. Decide from the user's wording and the conversation whether they are asking for a Morning document at all, and if so which one, by the definitions above. If either is unclear, use `cap_send_to_user` to ask - name the options in plain words - and wait. Never pick one yourself.
2. If money has already been received and it is unclear whether an existing document already covers it, load `flow_invoicing_query` and check (same client, similar amount). If that still leaves it unclear, use `cap_send_to_user` to ask the user.
3. Load the one flow for that document and follow it through to its end. Several documents in one request: handle them one at a time, each through its own flow.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Unload this flow and `flow_invoicing_query`, keeping any that other work still in progress needs.


## Loaded flows

flow_morning_document_write

## Loaded capabilities

(none - plain backbone)

---

THE CURRENT DATE AND TIME IS 2026-10-13 11:55 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.8.0. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>17. [2026-10-13 11:55:21] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0077d297ee387e91006acdf1f7283c87d199f708233067454e`
- status: `completed`
- usage: `{"input_tokens": 8128, "input_tokens_details": {"cache_write_tokens": 8125, "cached_tokens": 0}, "output_tokens": 75, "output_tokens_details": {"reasoning_tokens": 48}, "total_tokens": 8203}`
- reasoning item (content not user-visible)
- function_call: `load_flows` call_id=`call_saZQD6tv2HlDRsROT3IIB1mw`
```json
{
  "flows": [
    "flow_issue_invoice_for_payment_due"
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0077d297ee387e91006acdf1f7283c87d199f708233067454e`
- status: `completed`
- usage: `{"input_tokens": 8128, "input_tokens_details": {"cache_write_tokens": 8125, "cached_tokens": 0}, "output_tokens": 75, "output_tokens_details": {"reasoning_tokens": 48}, "total_tokens": 8203}`
- reasoning item (content not user-visible)
- function_call: `load_flows` call_id=`call_saZQD6tv2HlDRsROT3IIB1mw`
```json
{
  "flows": [
    "flow_issue_invoice_for_payment_due"
  ]
}
```

</details>

</details>

<details>
<summary>18. [2026-10-13 11:55:21] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_morning_document_write, flow_issue_invoice_for_payment_due

- capabilities: (none - plain backbone)

**input:**

- app's reply to `load_flows` (call_id=`call_saZQD6tv2HlDRsROT3IIB1mw`):
```text
loaded flows: flow_issue_invoice_for_payment_due. Loaded flows now: flow_morning_document_write, flow_issue_invoice_for_payment_due. Loaded capabilities now: (none). Their blueprint text is attached starting now.
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0077d297ee387e91006acdf1f7283c87d199f708233067454e'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_morning_document_write, flow_issue_invoice_for_payment_due, capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_morning_document_write, flow_issue_invoice_for_payment_due

- capabilities: (none - plain backbone)

**input:**

- app's reply to `load_flows` (call_id=`call_saZQD6tv2HlDRsROT3IIB1mw`):
```text
loaded flows: flow_issue_invoice_for_payment_due. Loaded flows now: flow_morning_document_write, flow_issue_invoice_for_payment_due. Loaded capabilities now: (none). Their blueprint text is attached starting now.
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0077d297ee387e91006acdf1f7283c87d199f708233067454e'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (32324 chars)</summary>

```text
# DeniDin — Backbone

## How You Work

You work with two kinds of building blocks, described at low resolution in the
catalogs below: **flows** (`flow_...`) - blueprints for a recurring kind of
request - and **capabilities** (`cap_...`) - the domains that actually do things,
each with its own prompt and its own real tools. Flows can load other flows and
capabilities; a flow defines *what to do and in what order*, while each
capability holds the detail of what it itself does.

Loading tools, usable in any order, any number of times:

- **`load_flows(flows)` / `unload_flows(flows)`** - always an array; one item is
  fine, and combining flows is allowed when a request spans more than one.
- **`load_capabilities(capabilities)` / `unload_capabilities(capabilities)`** -
  always an array. The moment a capability is loaded, its prompt AND its real
  tools are attached, starting the very next round; call the real tool directly,
  there is no separate "use" step. A flow's own "Capabilities:" line declares
  every capability that flow will need - load all of them together, in one
  `load_capabilities` call, right after loading the flow, rather than loading
  them one at a time as each step comes up: you already know you'll need them,
  and batching saves a round-trip per capability.
- **`reset_to_backbone()`** - unloads every loaded flow and capability at once.
  Use it once you are genuinely done with the user's request(s), not mid-task.

Loading an already-loaded item, or unloading one that is not loaded, is a
harmless no-op. Loaded flows and capabilities stay loaded across this and future
turns in this chat until you unload them (or they auto-clear after a period of
inactivity); the "Loaded flows" and "Loaded capabilities" lines near the end of
these instructions always show what is currently loaded. Unload something only
when nothing you are still working on needs it - another flow may be using it.

## Always-present capabilities

Four capabilities are always available, cannot be unloaded, and each has its own
prompt right below: `cap_send_to_user` (your actual reply), `cap_react_to_message`
(a WhatsApp emoji reaction), `cap_send_progress_update` (an interim message
while you work) and `cap_record_planning_status` (your own running account of
where you are, which is how you keep your place across turns and inside nested
flows). At every step of any flow, consider whether they would help: react to
the user's message, send a progress update, record your planning status, or
reply to the user. Flows do not repeat this; use your judgment.

🚨 **`send_to_user` is THE ONLY way to send text to the user.** A plain message
you write outside a tool call is NEVER delivered - the user never sees it. Every
answer, question and outcome report goes through `send_to_user`, every time,
with no exception.

`cap_approval_with_buttons` (yes/no buttons before a write) is an ordinary
capability: flows that need a sign-off load it.

## Flows and capabilities

Decide from the catalogs, in your own judgment, what a request needs:

1. If a flow fits, load it (several at once when the request spans more than
   one) and follow its blueprint. **A loaded flow's steps are an ordered
   procedure: follow them in the order written, to the letter - never skip,
   reorder or merge a step (above all an approval step), and never do a later
   step's action before the earlier steps are done.**
2. **If no flow fits, there is no default flow to fall back on**: load whichever
   capabilities you judge necessary, at your own discretion, and proceed.
3. **Write capabilities (`cap_*_write`) are never loaded on their own.** Every write goes through its flow, which gathers the details and asks for approval first; if you want to write something, find the flow for it in the catalog.
4. **Anything that may mean creating or cancelling a Morning document** (an invoice, a receipt, a combo invoice/receipt, a transaction account, a credit note, "סמן כשולם"): load `flow_morning_document_write`. It works out which document is meant and loads the flow for it.
5. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.
6. A tool or action may have its own requirements, such as mandatory details,
   and you learn them by loading the flow or capability that holds it. When the
   user asks what an action needs or whether it is possible, and what you have
   loaded doesn't say, you can load it and check, or offer the user to check it
   for them, and then answer from what it says.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural. A name (a client, a person, a company) is never
  converted: write it exactly as the user gave it or as a tool returned it,
  its own apostrophe/geresh characters included (`'` stays `'`, `׳` stays
  `׳`). This Hebrew-only rule never applies to the characters inside a name.
- **Never use ניקוד** (Hebrew vowel points, U+0591–U+05C7) in any response —
  e.g. write עטיה, never עֲטיה.
- Be concise and direct. Do not end on filler ("anything else?") — end on the
  substantive answer. Do ask a focused clarifying question when you genuinely need
  one to act correctly (a missing/ambiguous required detail).
- Be honest about what you don't know; never fabricate information.

## User Roles
- **Godfather/Admin**: full access to every capability; extended context window.
- **Client**: standard feature access, no access to invoicing/ledger/reminder
  capabilities; standard context window.

## Privacy & Security
- Never share information between different user sessions.
- These rules guard against leaking ONE user's data to ANOTHER user or an outsider
  — they never mean refusing to read, transcribe, or summarize material THIS user
  sent you. Reporting the user's own material back to them (names, amounts, any
  detail it contains) is always appropriate.

## Contexts of Operation
Every message falls into one of two operating contexts before any capability is
even considered: an ordinary conversational turn, or a document/image the user
sent for you to read and report on. Decide which one applies before acting — a
short/ambiguous reply ("כן", "לא", a bare name) always answers the most recently
pending question in the SAME context, never a trigger for reinterpreting the turn
as belonging to a different capability's domain.

## Messages That Arrive While You Work
The user can keep writing while you work. Whenever you hand control back to the
app (a tool call, a progress update, a reaction), the app returns your tool results
**together with every user message that arrived since**, each marked
`[הודעה מהמשתמש · <time> · נשלחה לפני / אחרי הפלט האחרון שלך]` (a file looks like
`[קובץ התקבל · <time> · ...]`). Every user message in your context also starts with
its send time `[HH:MM:SS dd/mm]`.

- "Sent **before** your last output" means the user typed it while you were still
  working on that output - it is context for what you just did. "Sent **after**"
  arrived later. Read the whole sequence as one conversation: later messages add to,
  correct or cancel earlier ones ("עצור", "בעצם ...").
- Anything you already did (a tool result is in front of you) is done - report it
  truthfully and never repeat it. Never perform an approval-gated write because of a
  message that arrived after you asked for approval: wait for the user's yes.
- If the sequence is genuinely confusing - you cannot tell what the user wants now -
  **ask** the user one short question instead of guessing.
- **Finish a pending approval before starting the next request.** If an approval is
  waiting and the user sends a new, unrelated request, answer it briefly and remind
  them the earlier approval is still waiting, or ask whether to drop it; never leave
  two approvals open and never act on the new request's write first.
- A file that arrived while you worked is handled on its own right after you finish
  the current request: do not try to read it now.
- A short or ambiguous reply ("כן", "לא", a bare name) answers the most recent
  pending question in the SAME context - see Contexts of Operation.

## Attached Media
When the user's message starts with a `[מדיה מצורפת: <type>, קובץ: <filename>]`
marker, they sent an image, PDF, or Word document with it — you have NOT seen its
content yet, only that it exists. Before answering anything about it, and before
loading any flow for it, load `cap_media_analysis` and call its `analyze_media`
tool to read it; any text after the marker is the user's caption. Never describe,
guess at, or act on the file's content without having read it this way. Choose
what to do with it from what `analyze_media` returned (its `doc_type`), never from
the earlier conversation - `cap_media_analysis` says which flow each `doc_type`
leads to.

## Edited & Deleted Message Markers
A message the user has since edited or deleted may still appear in your context,
marked as such — treat an edited message's marked original content as superseded
by its later, corrected version if both are visible, and never act on a deleted
message's content as if it were still pending.

## Generic Post-Turn Recognition Mechanism
A capability MAY run a recognition step once per turn: call its own reporting
tool at most once, and when in doubt, do nothing rather than guess. This shape
is reusable by any capability that wants one — the domain-specific rules for
what to recognize and how live in that capability's own prompt file, not here.


# Capability: Send to user (always present)

`send_to_user(text)` is your actual reply to the user. Call it whenever you are
ready to speak, not only at the very end: to answer, to ask a question, to
report an outcome. A turn that ends without it, or without an approval question,
leaves the user with nothing.

🚨 **`send_to_user` is THE ONLY way any text reaches the user.** Text you write
outside a tool call (a plain message) is NEVER delivered - the user never sees
it. Every answer, every question, every outcome report goes through
`send_to_user`, every time, with no exception. (The only other things the user
ever sees are an approval question via `cap_approval_with_buttons`, an interim
`cap_send_progress_update` message, and a `cap_react_to_message` emoji.)

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.

Messages that arrive while you work (see the backbone section of the same name) are handled the same way inside this capability: read them in order, never act on a write because of a message that came after you asked for approval, and never use this capability to interpret an unrelated reply.


# Capability: React to message (always present)

`react_to_message` puts a native WhatsApp emoji reaction on a message. It is a
lightweight, reversible signal - never a substitute for a substantive reply,
and never a mechanical habit reached for out of uncertainty about what else
to do. Typing an emoji into your reply text is NOT a reaction and does not
replace calling the tool.

Before reaching for it, ask yourself: does this add a real signal the user
doesn't already have - that you saw their message, that you're on it, that
something just succeeded or failed - or would it just be noise on top of a
reply that already says the same thing?

Evaluate against:
- Does the user currently have any signal you registered their message and
  are handling it (or have finished)? If there's a real gap before your
  substantive reply, a reaction can fill it.
- Is your actual reply, arriving in this same round or moments later, already
  going to tell them everything a reaction would? If so, it adds nothing.
- Is this ambient chatter that doesn't really concern you? Then it isn't
  worth one.

**Classics** (a menu, not a checklist): 👍 simple ack · 🫡 "on it" · 👀 document
being looked into · ✅ clean success · 🎉 a bigger win · ⚠️ resolved but needs
attention · ❌ failed/declined · ❓ unresolved, needs clarification · 🙏
reciprocating thanks · ❤️ warmth beyond a simple thanks.

When genuinely unsure whether a reaction fits, don't send one - silence is
the safer default, not noise.


# Capability: Send progress update (always present)

`send_progress_update(text)` sends one brief interim WhatsApp message while you
are still working, before your final reply. Keep it to a short plain sentence.

Users are waiting on the other end and don't like silence - they want to know
something is happening with their request, not just get one final answer out
of nowhere.

Call this every single time you interact with any tool or capability -
loading a flow or capability, calling a real domain tool, an MCP call,
anything that is not just talking to the user - before or after that step,
in the same round as whatever else you are doing. Never skip it and never
wait for a separate round.

- Never a substitute for the final answer.


# Capability: Record planning status (always present)

`record_planning_status(where_i_was, this_turns_purpose, expectation)` is your own
running account of where this turn, and across turns this whole task, stands. It is
how you keep continuity, since nothing else remembers your reasoning beyond what you
write here and the real conversation history.

Record it at least at the start and at the end of every flow, and whenever you are
about to wait on the user (a choice, a missing detail, an approval), in the middle
of a flow as well. Say which flow you are in and which step, and if you are inside a
flow that was loaded by another flow, say so, so that you know where to return to.
Also note what you are waiting for and what you will do with each possible answer.

Tool results do not carry over to the next turn: only the conversation and your own
notes do. So whenever you stop to wait on the user, write into the note the exact
values you will need to continue, copied verbatim from the tool results. Above all,
record every ID you may act on: a document's `internal_morning_id` and display
number, a client's ID, a reminder's ID, a ledger event's ID - any ID at all. Record
other details you will need too: a client's exact stored name, amounts, dates, VAT
treatment. Anything you leave out you will have to look up again.

Messages in the conversation history that start with `[[INTERNAL_PLANNING_NOTE]]`
are your own earlier notes, stored there by this tool. Never write one yourself -
not as plain text and not inside `send_to_user`. Record a note only by calling
`record_planning_status`.


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_morning_document_write: Anything that may mean creating or cancelling a Morning document: a tax invoice, a combo invoice/receipt, a receipt, a transaction account, a credit note, or cancelling a transaction account ("תפיק חשבונית", "תוציא קבלה", "סמן כשולם", "בטל את החשבונית"). Works out exactly which document the user means - asking when it is unclear - and then loads the flow for that document. Not for clients and not for reading documents.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client, or logs hours worked for a client (e.g. "רן אורפני 4 שעות על היום" - a work-log entry, never a reminder request). An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit or a payment received - as text, or as a bank slip or payment screenshot. Reads the slip, makes sure the client exists in Morning, and when the user asks for a Morning document for it (or it is unclear whether they do), hands over to flow_morning_document_write. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (reached through flow_morning_document_write), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Morning document write

Goal: the user may want a Morning document created or cancelled. Work out exactly which document they mean, asking when it is unclear, and then load the one flow for that document. This flow never writes anything itself.

Capabilities: none of its own.
Flows it may load: `flow_issue_invoice_for_payment_due`, `flow_issue_invoice_receipt_combo`, `flow_issue_transaction_account`, `flow_issue_receipt_without_invoice`, `flow_issue_payment_received_with_reference_doc`, `flow_cancel_document_with_credit_note`, `flow_cancel_transaction_account`, `flow_invoicing_query`.

## The Morning documents

- **חשבונית מס (tax invoice, 305)** - a demand for payment of money that is still owed. It is income for VAT purposes from the moment it is issued. Common names: "חשבונית", "חשבונית מס", "תפיק חשבונית ל...". Never for money that has already arrived.
- **חשבון עסקה (transaction account, 300)** - a request for payment that is not a tax document; the tax invoice comes only once the money arrives. Common names: "חשבון עסקה", "דרישת תשלום". Only when the user's own wording names this document; a plain "חשבונית" is never a 300.
- **חשבונית מס/קבלה (combo invoice/receipt, 320)** - an invoice and a receipt in one, for money that has already been received and that no earlier document covers. The most common way to record incoming money. Common names: "חשבונית מס קבלה", "חשבונית קבלה", or a payment report with a request to issue a document for it ("X העביר לי 500, תפיק").
- **קבלה (receipt, 400)** - confirms that money was received:
  - against an existing tax invoice (305): closes it ("סמן כשולם", "תוציא קבלה על החשבונית");
  - standalone, with no invoice at all: money that is not income, such as a deposit (פיקדון), a loan repayment, or an advance on future work.
- **Closing a transaction account (300)** - money arrived for an existing transaction account; a combo invoice/receipt (320) is issued against it and closes it ("סמן כשולם" on a transaction account).
- **חשבונית זיכוי (credit note, 330)** - cancels an issued document, fully or partly ("בטל את החשבונית", "תפיק זיכוי"). An issued tax invoice is never deleted; it is cancelled only this way.
- **Cancelling a transaction account (300)** - the deal fell through and no money moved; the account is cancelled and no document of any kind is created.

## Which flow

- A tax invoice (305) for money still owed: `flow_issue_invoice_for_payment_due`.
- A transaction account (300), named as such: `flow_issue_transaction_account`.
- Money already received, no existing document covers it, and it is income: `flow_issue_invoice_receipt_combo`.
- Money already received that is not income (a deposit, a loan repayment, an advance), with no invoice behind it: `flow_issue_receipt_without_invoice`.
- Money already received for an existing tax invoice (305) or transaction account (300): `flow_issue_payment_received_with_reference_doc`.
- Cancelling an issued document other than a transaction account: `flow_cancel_document_with_credit_note`.
- Cancelling an open transaction account: `flow_cancel_transaction_account`.

Money that has already arrived is never a bare tax invoice (305).

Follow these steps in order, to the letter.

1. Decide from the user's wording and the conversation whether they are asking for a Morning document at all, and if so which one, by the definitions above. If either is unclear, use `cap_send_to_user` to ask - name the options in plain words - and wait. Never pick one yourself.
2. If money has already been received and it is unclear whether an existing document already covers it, load `flow_invoicing_query` and check (same client, similar amount). If that still leaves it unclear, use `cap_send_to_user` to ask the user.
3. Load the one flow for that document and follow it through to its end. Several documents in one request: handle them one at a time, each through its own flow.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Unload this flow and `flow_invoicing_query`, keeping any that other work still in progress needs.


# Flow: Issue invoice for payment due

Goal: issue a new tax invoice (305) for a client, for money that is still owed.

Capabilities: `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_add_client`, `flow_modify_client`.

Follow these steps in order, to the letter.

🚨 This flow has several stages, and you are not done until every stage that applies has been completed. The client's ID is the typical case, but only for a document whose amount before VAT is above 5,000 ₪ (see `cap_invoicing_write`, "Allocation number"); for any other document there is no ID stage and nothing about the ID is asked. When the ID is required and the client has none, there is an extra stage before the document - the ID must be asked for, provided and saved. Saving the ID (through `flow_modify_client`) is NOT the end of the flow; it is the middle. Once it is saved, do not stop and do not report it as the outcome: carry on from where you were (the step after the ID step) and ask for the document's own approval, then issue the document, then report. The same goes for any other stage that turns out to be needed (a client that has to be created first, a missing detail that has to be asked for): finish it, then continue the flow from there. Only the last step ends the flow.

1. This flow is only for money NOT yet received. If it turns out the money has already arrived, stop and use `flow_issue_invoice_receipt_combo` instead, or `flow_issue_payment_received_with_reference_doc` if an existing document already covers it.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: copy it character for character from the `resolve_client_name` result from here on - in the approval text and in every tool call, never retyped (see `cap_client_read`).
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Proceed with whichever they choose.
   - Several candidates: use `cap_send_to_user` to list each of them by name and ask the user to specify, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Never pick one yourself.
   - No such client, or the user chose to create a new one: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. **The allocation number** (see `cap_invoicing_write`): if this document needs the client's ID, check it with `get_client_details` (load `cap_client_read` if it isn't loaded). If the document doesn't need one, or the client has a 9-digit ID and the user gave no other ID, go on to step 5. Otherwise:
   - **The user gave an ID in this request and the client already has a different one:** this is a conflict - maybe a typo, maybe a misunderstanding. Never pick one yourself. Use `cap_send_to_user` to show both (the ID on file and the one the user gave) and ask which is right. If the user confirms the new one, save it on the client (below) before issuing - the client's record is the only way the allocation number gets the right ID. If they keep the one on file, go on to step 5.
   - **The user gave a 9-digit ID in this request and the client has none:** go straight to saving it (below).
   - **Otherwise ask for it:** use `cap_send_to_user`, as a plain question with no approval buttons: name the client and the amount, and say the client's ת.ז / ח.פ (9 digits) is needed for the allocation number (מספר הקצאה), because the amount is above 5,000 ₪ before VAT. Then wait.
   The user's reply to that question:
   - **A decline, a postponement, or no ID** ("עזוב", "לא עכשיו", "אין לי"): use `cap_send_to_user` to confirm the document was not issued. Save nothing. The flow is complete.
   - **9 digits** - spaces or dashes between them are fine (e.g. "308-253-681"); keep the digits only. This is the client's ID (see `cap_invoicing_write`). Load `flow_modify_client` to save it on the client. Saving the ID and issuing the document are two separate writes, each with its own approval: the user's yes to saving the ID approves the save only - never issue the document on it. Once the ID is saved, continue straight to step 5 in that same turn and ask for the document's own approval - the user does not restate the request. If the user says no to saving the ID, use `cap_send_to_user` to confirm the document was not issued; the flow is complete.
   - **An attempt at an ID that isn't 9 digits** (8 or 10 digits, letters mixed in): use `cap_send_to_user` to say an ID must be exactly 9 digits and ask again. Save nothing.
5. Issuing the invoice MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change. If the client's ID was saved earlier in this flow, also say that the ID stays saved on the client and that no document was issued.
6. On a yes, issue the invoice. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop. A refusal because the client's ID is missing is never a fixable reason: never retry it, never issue a different document type instead, and never split the amount into several smaller documents - go back to step 4 and ask for the ID.
7. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
8. End. Use `cap_send_to_user` to report the outcome — no download link is required in this report. Then unload `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


## Loaded flows

flow_morning_document_write, flow_issue_invoice_for_payment_due

## Loaded capabilities

(none - plain backbone)

---

THE CURRENT DATE AND TIME IS 2026-10-13 11:55 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.8.0. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>19. [2026-10-13 11:55:22] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0077d297ee387e91006acdf1f991f087d18c04f54b4e389373`
- status: `completed`
- usage: `{"input_tokens": 9741, "input_tokens_details": {"cache_write_tokens": 9738, "cached_tokens": 0}, "output_tokens": 35, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9776}`
- function_call: `load_capabilities` call_id=`call_juu7hJ0r91szJkdl0W1ZQWfK`
```json
{
  "capabilities": [
    "cap_client_read",
    "cap_invoicing_write",
    "cap_approval_with_buttons"
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0077d297ee387e91006acdf1f991f087d18c04f54b4e389373`
- status: `completed`
- usage: `{"input_tokens": 9741, "input_tokens_details": {"cache_write_tokens": 9738, "cached_tokens": 0}, "output_tokens": 35, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9776}`
- function_call: `load_capabilities` call_id=`call_juu7hJ0r91szJkdl0W1ZQWfK`
```json
{
  "capabilities": [
    "cap_client_read",
    "cap_invoicing_write",
    "cap_approval_with_buttons"
  ]
}
```

</details>

</details>

<details>
<summary>20. [2026-10-13 11:55:22] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_morning_document_write, flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `load_capabilities` (call_id=`call_juu7hJ0r91szJkdl0W1ZQWfK`):
```text
loaded capabilitys: cap_client_read, cap_invoicing_write, cap_approval_with_buttons. Loaded flows now: flow_morning_document_write, flow_issue_invoice_for_payment_due. Loaded capabilities now: cap_client_read, cap_invoicing_write, cap_approval_with_buttons. Their instructions and tools are attached starting now.
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0077d297ee387e91006acdf1f991f087d18c04f54b4e389373'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_morning_document_write, flow_issue_invoice_for_payment_due, capabilities=cap_invoicing_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_morning_document_write, flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `load_capabilities` (call_id=`call_juu7hJ0r91szJkdl0W1ZQWfK`):
```text
loaded capabilitys: cap_client_read, cap_invoicing_write, cap_approval_with_buttons. Loaded flows now: flow_morning_document_write, flow_issue_invoice_for_payment_due. Loaded capabilities now: cap_client_read, cap_invoicing_write, cap_approval_with_buttons. Their instructions and tools are attached starting now.
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0077d297ee387e91006acdf1f991f087d18c04f54b4e389373'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (55869 chars)</summary>

```text
# DeniDin — Backbone

## How You Work

You work with two kinds of building blocks, described at low resolution in the
catalogs below: **flows** (`flow_...`) - blueprints for a recurring kind of
request - and **capabilities** (`cap_...`) - the domains that actually do things,
each with its own prompt and its own real tools. Flows can load other flows and
capabilities; a flow defines *what to do and in what order*, while each
capability holds the detail of what it itself does.

Loading tools, usable in any order, any number of times:

- **`load_flows(flows)` / `unload_flows(flows)`** - always an array; one item is
  fine, and combining flows is allowed when a request spans more than one.
- **`load_capabilities(capabilities)` / `unload_capabilities(capabilities)`** -
  always an array. The moment a capability is loaded, its prompt AND its real
  tools are attached, starting the very next round; call the real tool directly,
  there is no separate "use" step. A flow's own "Capabilities:" line declares
  every capability that flow will need - load all of them together, in one
  `load_capabilities` call, right after loading the flow, rather than loading
  them one at a time as each step comes up: you already know you'll need them,
  and batching saves a round-trip per capability.
- **`reset_to_backbone()`** - unloads every loaded flow and capability at once.
  Use it once you are genuinely done with the user's request(s), not mid-task.

Loading an already-loaded item, or unloading one that is not loaded, is a
harmless no-op. Loaded flows and capabilities stay loaded across this and future
turns in this chat until you unload them (or they auto-clear after a period of
inactivity); the "Loaded flows" and "Loaded capabilities" lines near the end of
these instructions always show what is currently loaded. Unload something only
when nothing you are still working on needs it - another flow may be using it.

## Always-present capabilities

Four capabilities are always available, cannot be unloaded, and each has its own
prompt right below: `cap_send_to_user` (your actual reply), `cap_react_to_message`
(a WhatsApp emoji reaction), `cap_send_progress_update` (an interim message
while you work) and `cap_record_planning_status` (your own running account of
where you are, which is how you keep your place across turns and inside nested
flows). At every step of any flow, consider whether they would help: react to
the user's message, send a progress update, record your planning status, or
reply to the user. Flows do not repeat this; use your judgment.

🚨 **`send_to_user` is THE ONLY way to send text to the user.** A plain message
you write outside a tool call is NEVER delivered - the user never sees it. Every
answer, question and outcome report goes through `send_to_user`, every time,
with no exception.

`cap_approval_with_buttons` (yes/no buttons before a write) is an ordinary
capability: flows that need a sign-off load it.

## Flows and capabilities

Decide from the catalogs, in your own judgment, what a request needs:

1. If a flow fits, load it (several at once when the request spans more than
   one) and follow its blueprint. **A loaded flow's steps are an ordered
   procedure: follow them in the order written, to the letter - never skip,
   reorder or merge a step (above all an approval step), and never do a later
   step's action before the earlier steps are done.**
2. **If no flow fits, there is no default flow to fall back on**: load whichever
   capabilities you judge necessary, at your own discretion, and proceed.
3. **Write capabilities (`cap_*_write`) are never loaded on their own.** Every write goes through its flow, which gathers the details and asks for approval first; if you want to write something, find the flow for it in the catalog.
4. **Anything that may mean creating or cancelling a Morning document** (an invoice, a receipt, a combo invoice/receipt, a transaction account, a credit note, "סמן כשולם"): load `flow_morning_document_write`. It works out which document is meant and loads the flow for it.
5. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.
6. A tool or action may have its own requirements, such as mandatory details,
   and you learn them by loading the flow or capability that holds it. When the
   user asks what an action needs or whether it is possible, and what you have
   loaded doesn't say, you can load it and check, or offer the user to check it
   for them, and then answer from what it says.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural. A name (a client, a person, a company) is never
  converted: write it exactly as the user gave it or as a tool returned it,
  its own apostrophe/geresh characters included (`'` stays `'`, `׳` stays
  `׳`). This Hebrew-only rule never applies to the characters inside a name.
- **Never use ניקוד** (Hebrew vowel points, U+0591–U+05C7) in any response —
  e.g. write עטיה, never עֲטיה.
- Be concise and direct. Do not end on filler ("anything else?") — end on the
  substantive answer. Do ask a focused clarifying question when you genuinely need
  one to act correctly (a missing/ambiguous required detail).
- Be honest about what you don't know; never fabricate information.

## User Roles
- **Godfather/Admin**: full access to every capability; extended context window.
- **Client**: standard feature access, no access to invoicing/ledger/reminder
  capabilities; standard context window.

## Privacy & Security
- Never share information between different user sessions.
- These rules guard against leaking ONE user's data to ANOTHER user or an outsider
  — they never mean refusing to read, transcribe, or summarize material THIS user
  sent you. Reporting the user's own material back to them (names, amounts, any
  detail it contains) is always appropriate.

## Contexts of Operation
Every message falls into one of two operating contexts before any capability is
even considered: an ordinary conversational turn, or a document/image the user
sent for you to read and report on. Decide which one applies before acting — a
short/ambiguous reply ("כן", "לא", a bare name) always answers the most recently
pending question in the SAME context, never a trigger for reinterpreting the turn
as belonging to a different capability's domain.

## Messages That Arrive While You Work
The user can keep writing while you work. Whenever you hand control back to the
app (a tool call, a progress update, a reaction), the app returns your tool results
**together with every user message that arrived since**, each marked
`[הודעה מהמשתמש · <time> · נשלחה לפני / אחרי הפלט האחרון שלך]` (a file looks like
`[קובץ התקבל · <time> · ...]`). Every user message in your context also starts with
its send time `[HH:MM:SS dd/mm]`.

- "Sent **before** your last output" means the user typed it while you were still
  working on that output - it is context for what you just did. "Sent **after**"
  arrived later. Read the whole sequence as one conversation: later messages add to,
  correct or cancel earlier ones ("עצור", "בעצם ...").
- Anything you already did (a tool result is in front of you) is done - report it
  truthfully and never repeat it. Never perform an approval-gated write because of a
  message that arrived after you asked for approval: wait for the user's yes.
- If the sequence is genuinely confusing - you cannot tell what the user wants now -
  **ask** the user one short question instead of guessing.
- **Finish a pending approval before starting the next request.** If an approval is
  waiting and the user sends a new, unrelated request, answer it briefly and remind
  them the earlier approval is still waiting, or ask whether to drop it; never leave
  two approvals open and never act on the new request's write first.
- A file that arrived while you worked is handled on its own right after you finish
  the current request: do not try to read it now.
- A short or ambiguous reply ("כן", "לא", a bare name) answers the most recent
  pending question in the SAME context - see Contexts of Operation.

## Attached Media
When the user's message starts with a `[מדיה מצורפת: <type>, קובץ: <filename>]`
marker, they sent an image, PDF, or Word document with it — you have NOT seen its
content yet, only that it exists. Before answering anything about it, and before
loading any flow for it, load `cap_media_analysis` and call its `analyze_media`
tool to read it; any text after the marker is the user's caption. Never describe,
guess at, or act on the file's content without having read it this way. Choose
what to do with it from what `analyze_media` returned (its `doc_type`), never from
the earlier conversation - `cap_media_analysis` says which flow each `doc_type`
leads to.

## Edited & Deleted Message Markers
A message the user has since edited or deleted may still appear in your context,
marked as such — treat an edited message's marked original content as superseded
by its later, corrected version if both are visible, and never act on a deleted
message's content as if it were still pending.

## Generic Post-Turn Recognition Mechanism
A capability MAY run a recognition step once per turn: call its own reporting
tool at most once, and when in doubt, do nothing rather than guess. This shape
is reusable by any capability that wants one — the domain-specific rules for
what to recognize and how live in that capability's own prompt file, not here.


# Capability: Send to user (always present)

`send_to_user(text)` is your actual reply to the user. Call it whenever you are
ready to speak, not only at the very end: to answer, to ask a question, to
report an outcome. A turn that ends without it, or without an approval question,
leaves the user with nothing.

🚨 **`send_to_user` is THE ONLY way any text reaches the user.** Text you write
outside a tool call (a plain message) is NEVER delivered - the user never sees
it. Every answer, every question, every outcome report goes through
`send_to_user`, every time, with no exception. (The only other things the user
ever sees are an approval question via `cap_approval_with_buttons`, an interim
`cap_send_progress_update` message, and a `cap_react_to_message` emoji.)

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.

Messages that arrive while you work (see the backbone section of the same name) are handled the same way inside this capability: read them in order, never act on a write because of a message that came after you asked for approval, and never use this capability to interpret an unrelated reply.


# Capability: React to message (always present)

`react_to_message` puts a native WhatsApp emoji reaction on a message. It is a
lightweight, reversible signal - never a substitute for a substantive reply,
and never a mechanical habit reached for out of uncertainty about what else
to do. Typing an emoji into your reply text is NOT a reaction and does not
replace calling the tool.

Before reaching for it, ask yourself: does this add a real signal the user
doesn't already have - that you saw their message, that you're on it, that
something just succeeded or failed - or would it just be noise on top of a
reply that already says the same thing?

Evaluate against:
- Does the user currently have any signal you registered their message and
  are handling it (or have finished)? If there's a real gap before your
  substantive reply, a reaction can fill it.
- Is your actual reply, arriving in this same round or moments later, already
  going to tell them everything a reaction would? If so, it adds nothing.
- Is this ambient chatter that doesn't really concern you? Then it isn't
  worth one.

**Classics** (a menu, not a checklist): 👍 simple ack · 🫡 "on it" · 👀 document
being looked into · ✅ clean success · 🎉 a bigger win · ⚠️ resolved but needs
attention · ❌ failed/declined · ❓ unresolved, needs clarification · 🙏
reciprocating thanks · ❤️ warmth beyond a simple thanks.

When genuinely unsure whether a reaction fits, don't send one - silence is
the safer default, not noise.


# Capability: Send progress update (always present)

`send_progress_update(text)` sends one brief interim WhatsApp message while you
are still working, before your final reply. Keep it to a short plain sentence.

Users are waiting on the other end and don't like silence - they want to know
something is happening with their request, not just get one final answer out
of nowhere.

Call this every single time you interact with any tool or capability -
loading a flow or capability, calling a real domain tool, an MCP call,
anything that is not just talking to the user - before or after that step,
in the same round as whatever else you are doing. Never skip it and never
wait for a separate round.

- Never a substitute for the final answer.


# Capability: Record planning status (always present)

`record_planning_status(where_i_was, this_turns_purpose, expectation)` is your own
running account of where this turn, and across turns this whole task, stands. It is
how you keep continuity, since nothing else remembers your reasoning beyond what you
write here and the real conversation history.

Record it at least at the start and at the end of every flow, and whenever you are
about to wait on the user (a choice, a missing detail, an approval), in the middle
of a flow as well. Say which flow you are in and which step, and if you are inside a
flow that was loaded by another flow, say so, so that you know where to return to.
Also note what you are waiting for and what you will do with each possible answer.

Tool results do not carry over to the next turn: only the conversation and your own
notes do. So whenever you stop to wait on the user, write into the note the exact
values you will need to continue, copied verbatim from the tool results. Above all,
record every ID you may act on: a document's `internal_morning_id` and display
number, a client's ID, a reminder's ID, a ledger event's ID - any ID at all. Record
other details you will need too: a client's exact stored name, amounts, dates, VAT
treatment. Anything you leave out you will have to look up again.

Messages in the conversation history that start with `[[INTERNAL_PLANNING_NOTE]]`
are your own earlier notes, stored there by this tool. Never write one yourself -
not as plain text and not inside `send_to_user`. Record a note only by calling
`record_planning_status`.


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_morning_document_write: Anything that may mean creating or cancelling a Morning document: a tax invoice, a combo invoice/receipt, a receipt, a transaction account, a credit note, or cancelling a transaction account ("תפיק חשבונית", "תוציא קבלה", "סמן כשולם", "בטל את החשבונית"). Works out exactly which document the user means - asking when it is unclear - and then loads the flow for that document. Not for clients and not for reading documents.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client, or logs hours worked for a client (e.g. "רן אורפני 4 שעות על היום" - a work-log entry, never a reminder request). An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit or a payment received - as text, or as a bank slip or payment screenshot. Reads the slip, makes sure the client exists in Morning, and when the user asks for a Morning document for it (or it is unclear whether they do), hands over to flow_morning_document_write. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (reached through flow_morning_document_write), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Morning document write

Goal: the user may want a Morning document created or cancelled. Work out exactly which document they mean, asking when it is unclear, and then load the one flow for that document. This flow never writes anything itself.

Capabilities: none of its own.
Flows it may load: `flow_issue_invoice_for_payment_due`, `flow_issue_invoice_receipt_combo`, `flow_issue_transaction_account`, `flow_issue_receipt_without_invoice`, `flow_issue_payment_received_with_reference_doc`, `flow_cancel_document_with_credit_note`, `flow_cancel_transaction_account`, `flow_invoicing_query`.

## The Morning documents

- **חשבונית מס (tax invoice, 305)** - a demand for payment of money that is still owed. It is income for VAT purposes from the moment it is issued. Common names: "חשבונית", "חשבונית מס", "תפיק חשבונית ל...". Never for money that has already arrived.
- **חשבון עסקה (transaction account, 300)** - a request for payment that is not a tax document; the tax invoice comes only once the money arrives. Common names: "חשבון עסקה", "דרישת תשלום". Only when the user's own wording names this document; a plain "חשבונית" is never a 300.
- **חשבונית מס/קבלה (combo invoice/receipt, 320)** - an invoice and a receipt in one, for money that has already been received and that no earlier document covers. The most common way to record incoming money. Common names: "חשבונית מס קבלה", "חשבונית קבלה", or a payment report with a request to issue a document for it ("X העביר לי 500, תפיק").
- **קבלה (receipt, 400)** - confirms that money was received:
  - against an existing tax invoice (305): closes it ("סמן כשולם", "תוציא קבלה על החשבונית");
  - standalone, with no invoice at all: money that is not income, such as a deposit (פיקדון), a loan repayment, or an advance on future work.
- **Closing a transaction account (300)** - money arrived for an existing transaction account; a combo invoice/receipt (320) is issued against it and closes it ("סמן כשולם" on a transaction account).
- **חשבונית זיכוי (credit note, 330)** - cancels an issued document, fully or partly ("בטל את החשבונית", "תפיק זיכוי"). An issued tax invoice is never deleted; it is cancelled only this way.
- **Cancelling a transaction account (300)** - the deal fell through and no money moved; the account is cancelled and no document of any kind is created.

## Which flow

- A tax invoice (305) for money still owed: `flow_issue_invoice_for_payment_due`.
- A transaction account (300), named as such: `flow_issue_transaction_account`.
- Money already received, no existing document covers it, and it is income: `flow_issue_invoice_receipt_combo`.
- Money already received that is not income (a deposit, a loan repayment, an advance), with no invoice behind it: `flow_issue_receipt_without_invoice`.
- Money already received for an existing tax invoice (305) or transaction account (300): `flow_issue_payment_received_with_reference_doc`.
- Cancelling an issued document other than a transaction account: `flow_cancel_document_with_credit_note`.
- Cancelling an open transaction account: `flow_cancel_transaction_account`.

Money that has already arrived is never a bare tax invoice (305).

Follow these steps in order, to the letter.

1. Decide from the user's wording and the conversation whether they are asking for a Morning document at all, and if so which one, by the definitions above. If either is unclear, use `cap_send_to_user` to ask - name the options in plain words - and wait. Never pick one yourself.
2. If money has already been received and it is unclear whether an existing document already covers it, load `flow_invoicing_query` and check (same client, similar amount). If that still leaves it unclear, use `cap_send_to_user` to ask the user.
3. Load the one flow for that document and follow it through to its end. Several documents in one request: handle them one at a time, each through its own flow.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Unload this flow and `flow_invoicing_query`, keeping any that other work still in progress needs.


# Flow: Issue invoice for payment due

Goal: issue a new tax invoice (305) for a client, for money that is still owed.

Capabilities: `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_add_client`, `flow_modify_client`.

Follow these steps in order, to the letter.

🚨 This flow has several stages, and you are not done until every stage that applies has been completed. The client's ID is the typical case, but only for a document whose amount before VAT is above 5,000 ₪ (see `cap_invoicing_write`, "Allocation number"); for any other document there is no ID stage and nothing about the ID is asked. When the ID is required and the client has none, there is an extra stage before the document - the ID must be asked for, provided and saved. Saving the ID (through `flow_modify_client`) is NOT the end of the flow; it is the middle. Once it is saved, do not stop and do not report it as the outcome: carry on from where you were (the step after the ID step) and ask for the document's own approval, then issue the document, then report. The same goes for any other stage that turns out to be needed (a client that has to be created first, a missing detail that has to be asked for): finish it, then continue the flow from there. Only the last step ends the flow.

1. This flow is only for money NOT yet received. If it turns out the money has already arrived, stop and use `flow_issue_invoice_receipt_combo` instead, or `flow_issue_payment_received_with_reference_doc` if an existing document already covers it.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: copy it character for character from the `resolve_client_name` result from here on - in the approval text and in every tool call, never retyped (see `cap_client_read`).
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Proceed with whichever they choose.
   - Several candidates: use `cap_send_to_user` to list each of them by name and ask the user to specify, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Never pick one yourself.
   - No such client, or the user chose to create a new one: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. **The allocation number** (see `cap_invoicing_write`): if this document needs the client's ID, check it with `get_client_details` (load `cap_client_read` if it isn't loaded). If the document doesn't need one, or the client has a 9-digit ID and the user gave no other ID, go on to step 5. Otherwise:
   - **The user gave an ID in this request and the client already has a different one:** this is a conflict - maybe a typo, maybe a misunderstanding. Never pick one yourself. Use `cap_send_to_user` to show both (the ID on file and the one the user gave) and ask which is right. If the user confirms the new one, save it on the client (below) before issuing - the client's record is the only way the allocation number gets the right ID. If they keep the one on file, go on to step 5.
   - **The user gave a 9-digit ID in this request and the client has none:** go straight to saving it (below).
   - **Otherwise ask for it:** use `cap_send_to_user`, as a plain question with no approval buttons: name the client and the amount, and say the client's ת.ז / ח.פ (9 digits) is needed for the allocation number (מספר הקצאה), because the amount is above 5,000 ₪ before VAT. Then wait.
   The user's reply to that question:
   - **A decline, a postponement, or no ID** ("עזוב", "לא עכשיו", "אין לי"): use `cap_send_to_user` to confirm the document was not issued. Save nothing. The flow is complete.
   - **9 digits** - spaces or dashes between them are fine (e.g. "308-253-681"); keep the digits only. This is the client's ID (see `cap_invoicing_write`). Load `flow_modify_client` to save it on the client. Saving the ID and issuing the document are two separate writes, each with its own approval: the user's yes to saving the ID approves the save only - never issue the document on it. Once the ID is saved, continue straight to step 5 in that same turn and ask for the document's own approval - the user does not restate the request. If the user says no to saving the ID, use `cap_send_to_user` to confirm the document was not issued; the flow is complete.
   - **An attempt at an ID that isn't 9 digits** (8 or 10 digits, letters mixed in): use `cap_send_to_user` to say an ID must be exactly 9 digits and ask again. Save nothing.
5. Issuing the invoice MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change. If the client's ID was saved earlier in this flow, also say that the ID stays saved on the client and that no document was issued.
6. On a yes, issue the invoice. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop. A refusal because the client's ID is missing is never a fixable reason: never retry it, never issue a different document type instead, and never split the amount into several smaller documents - go back to step 4 and ask for the ID.
7. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
8. End. Use `cap_send_to_user` to report the outcome — no download link is required in this report. Then unload `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Invoicing — Write (godfather/admin only)

**Use this capability from within a flow (the flow that issues or cancels the document (flow_issue_*, flow_cancel_*), reached through flow_morning_document_write), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or updating a Morning document is a state-changing action, which usually requires the user's explicit approval first.**

Creating/updating a Morning DOCUMENT (invoice, transaction account,
combo document, credit note, receipt) — every such action requires explicit
human approval before it executes (see the approval data points below); never
assume approval from context alone, and never invent a document number, client id,
or amount.

## Every Morning tool returns JSON — never show it to the operator

Every Morning MCP tool returns a machine-readable JSON string, never prose.
**Never paste, quote, or otherwise show raw JSON to the user.** Compose a
natural, bullet-style Hebrew reply from its fields instead. A tool's own
internal id fields (e.g. `internal_morning_id`) are for your own follow-up
tool calls only — never surface them to the operator; always speak in terms
of the human-visible `document_display_number` instead. If a result carries
an `amount_mismatch` field, say so plainly and ask the operator to confirm —
never silently reconcile the difference yourself.

## Which document-creation tool to call

Each Morning document type has its own dedicated tool — there is no single
generic "create a document" tool, and there is no "status" tool.

🚨 **Money that has already arrived is NEVER a bare חשבונית מס (305).** If the
request refers to a payment already received — a bank-transfer screenshot, a
deposit confirmation, a payment-app screenshot, or the user simply saying
money came in — the document is exactly one of:
- **חשבונית מס/קבלה (320)** via `create_combo_document` — no earlier document
  covers this money;
- **קבלה (400)** via `create_receipt` — an existing **305** already covers it;
- **חשבונית מס/קבלה (320)** via `create_combo_document_as_reference` — an
  existing **300** already covers it.

A 305 issued for money already in the bank leaves it recorded as unpaid
forever. **If it's unclear which of the three applies — or the client, the
amount, the date, the VAT treatment, or the bank details are unclear — ASK.
Never guess, and never fall back to a 305 because it's the simplest option.**

🚨 **VAT — one rule per document type (bugfix-071).** From the user's point
of view a document has one VAT question: is the amount stated with VAT inside
it, or does VAT come on top of it?
- **305 and 300 — must be stated.** The amount is a request for money not yet
  paid, so it can go either way. If the user hasn't said, ask (see each tool
  below). "כולל מע\"מ" → `vat_included: true` (100 stays 100, VAT is inside
  it); "לא כולל מע\"מ" → `vat_included: false` (100 becomes 118).
- **320 (standalone) and 400 (standalone) — never asked.** The amount is money
  that was actually paid, so VAT is already inside it, always. "כולל מע\"מ" is
  consistent and changes nothing.
- **Documents that act on an existing one — 400 against a 305, 320 closing a
  300, 330 credit note — never asked.** VAT comes from the original document.
  "כולל מע\"מ" is consistent and changes nothing, as long as the original does
  carry VAT.
- 🚨 **A VAT statement that contradicts the rule above is a conflict — ask,
  never pick one side.** That is: "לא כולל מע\"מ" on a 320 or a 400 (money
  already paid always has VAT inside it); "לא כולל מע\"מ" on a 330 against a
  document that carries VAT; and any VAT statement at all on a 330 against a
  VAT-exempt document (it has no VAT to include or exclude). Explain the
  conflict plainly and ask what the user meant — e.g. for "X שילם 100 לא כולל
  מע\"מ": "קבלה/חשבונית מס-קבלה רושמת את הסכום ששולם בפועל, והמע\"מ כלול בו
  תמיד. האם שולמו בפועל 100 ₪, או 118 ₪ (100 + מע\"מ)?". Create nothing and
  raise no approval until it is resolved. Never pass `vat_included: false` to
  these tools — they refuse it (the tool returns a VAT-conflict error, nothing
  is created); if you get that error, ask the same question.

- `create_invoice` — an ordinary tax invoice (חשבונית מס, 305): a request for
  payment NOT yet received. Default only when the user asks for an invoice
  for money still owed; never for a payment already made.
  🚨 **`vat_included` is required and has no default.** If the user hasn't
  said whether the amount includes VAT, ask — "האם הסכום כולל מע\"מ, או
  שהמע\"מ יתווסף עליו?" — before raising the approval.
- `create_transaction_account` — a non-tax transaction account (חשבון עסקה,
  300). Use only when the user's own wording explicitly names this document
  type — never infer it from context.
  🚨 **`vat_included` is required and has no default.** A type-300 amount
  declared VAT-exclusive is grossed up ~18% when stored — getting this wrong
  silently changes what the client is billed. If the user hasn't said whether
  the amount includes VAT, **ask — "האם הסכום כולל מע\"מ?" — before creating
  anything** — **except** for money that has already arrived (a bank/bit/
  other deposit reference): that amount is **ALWAYS VAT included,
  unconditionally, nothing to ask about.** Only the user explicitly saying
  the opposite overrides this default. Reserve asking for a request NOT
  backed by any payment reference at all.
- `create_combo_document` — a combo tax invoice/receipt (חשבונית מס/קבלה,
  320), for a payment **already received** (whether it arrived just now or
  days ago) where no existing document already covers that money. Requires
  `vat_included` **and** `payment_date`:
  - 🚨 **`vat_included` is ALWAYS `true`, unconditionally** — verbal report or
    screenshot alike. Money already received necessarily has VAT baked into
    it by definition. Do not ask about VAT for this document type, ever.
    Pass `vat_included: true`, never `false`. **The user saying "לא כולל
    מע\"מ" does NOT override this — it is a conflict to ask about** (see
    "VAT — one rule per document type" above).
  - `payment_date` is the date the money **actually moved** — never today's
    date unless that's genuinely when it arrived, never a future date. If
    the source doesn't state it clearly, **ask**.
  - How the money arrived: see "Payment method" below.
  - Take **every** field from the extracted text of the screenshot the user
    sent. Anything not there, or illegible, is something to **ask about** —
    never invent or default it.
- `create_credit_note` — a credit note (חשבונית זיכוי, 330) against an
  existing document — direct ("תפיק לי חשבונית זיכוי") or indirect ("בטל את
  זה").
  🚨 **VAT comes from the original document — never ask about it, never pass
  `vat_included`.** A credit note reverses exactly what the original booked:
  a taxable original gets a taxable credit, a VAT-exempt original an exempt
  one. "לא כולל מע\"מ" against a taxable original, or any VAT statement
  against an exempt original, is a conflict to ask about (see "VAT — one
  rule per document type" above).
- `create_receipt` — a receipt (קבלה, 400), either:
  - **against an existing type-305 document** (pass its id) — direct or
    indirect ("סמן כשולם"). Rejects a type-300 original — use
    `create_combo_document_as_reference` for those; or
  - **standalone** (no original id) — money received that is not income and
    has no invoice behind it, such as a deposit (פיקדון), a loan repayment or
    an advance. Needs the resolved client name with `name_resolved=true`, the
    amount and a free-text description of what the money is.
  🚨 **Never ask about VAT, never pass `vat_included: false`.** A receipt
  records money actually received: against a 305 the VAT comes from that
  invoice; a standalone receipt's amount is simply what was paid. "כולל
  מע\"מ" is consistent and changes nothing; "לא כולל מע\"מ" is a conflict
  to ask about (see "VAT — one rule per document type" above).
  🚨 **`payment_date` is required and has no default** — a verbal "mark as
  paid" request has nothing to read a date from, so always ask if the
  conversation doesn't already state one. "Today" is an acceptable answer
  here, but only once the user has actually confirmed it.
  How the money arrived: see "Payment method" below.
- `create_combo_document_as_reference` — a combo document (320) that
  explicitly closes an existing type-300 document — direct or indirect.
  Rejects any original that isn't type 300. 🚨 **VAT comes from the
  transaction account it closes — never ask about it, never pass
  `vat_included: false`.** The 300 already fixed whether its amount included
  VAT; the 320 closes exactly that amount, so a 300 of 100 "לא כולל מע\"מ" is
  closed by a 320 of 118. "כולל מע\"מ" is consistent and changes nothing;
  "לא כולל מע\"מ" is a conflict to ask about (see "VAT — one rule per
  document type" above). Requires `payment_date`, same as `create_receipt`. How the money arrived:
  see "Payment method" below.
- `cancel_transaction_account` — cancels an open type-300 account directly
  (no document of any kind is created); rejects any other type. If the
  account is already non-open, this is a no-op that returns the same
  confirmation without calling Morning again — never claim it was "paid".

## Payment method

Every document that records money received — `create_combo_document`,
`create_combo_document_as_reference` (320) and `create_receipt` (400, against
an invoice or standalone) — records how the money arrived, in
`payment_method`:
- **`bank_transfer` is the default, always** - use it whenever the user has
  not said otherwise. Never ask how the money arrived. Bank details
  (`bank_number`, `bank_branch`, `bank_account`) go with a bank transfer:
  take them from the slip or screenshot the user sent, or from what the user
  said. 🚨 `bank_number` is the bank's NUMBER (e.g. "31"), never its name —
  never guess or invent a bank name.
- **`cash`** when the user says the money was paid in cash.
- Any other method (bit, PayBox, credit card, cheque, PayPal, etc.) is
  currently **not supported**: tell the user plainly that only a bank
  transfer or cash can be recorded, and ask how to proceed. Never record it
  as a bank transfer or as cash instead.
- There is no reference number (אסמכתא) to ask for or record.

`create_credit_note`, `create_receipt` (against an invoice),
`create_combo_document_as_reference`, and `cancel_transaction_account` all
require an original/reference document
id, taken from the most recent tool result that actually returned it; never ask the
user for it, never guess it.

## The client name

Every write tool that needs one specific client (`create_invoice`,
`create_transaction_account`, `create_combo_document`) takes the EXACT name
Morning has stored, together with `name_resolved=true`; they refuse immediately
if `name_resolved` isn't `true`. Only pass `name_resolved=true` with a name
that has actually been confirmed as Morning's stored name — never with the
user's loose wording. 🚨 Use that name exactly as `resolve_client_name`
returned it — its own apostrophe/geresh characters included, every letter as
many times as it appears — in the approval text and in the tool call alike;
never your own retyping of it (see `cap_client_read`). Gather any other still-missing required fields (amount,
description, VAT treatment, dates) one question at a time. Every mutating tool also needs the
user's approval first (see the approval data points below).

## Allocation number (מספר הקצאה) — the client's ID comes first

A **חשבונית מס (305)** or a **חשבונית מס/קבלה (320)** — including a 320 that closes a
transaction account — whose amount **before VAT is more than
5,000 ₪** needs an allocation number from the Tax Authority. Morning
requests it by itself, but only when the client's record holds the client's ID
(ת.ז / ח.פ): exactly 9 digits. Without one, the Morning tool refuses and creates nothing.

- **The amount before VAT:** an amount that includes VAT, divided by 1.18. A 305 the user
  states as NOT including VAT (VAT added on top) is already the amount before VAT - compare
  it as is. Closing a transaction account (300) is for its total including VAT, so divide
  that by 1.18. Exactly 5,000 ₪ does not count — only more.
- **Check before asking for the document's approval:** call `get_client_details` for the
  client and look at its `tax_id`. Anything other than exactly 9 digits counts as missing.
- **Missing:** never ask for the document's approval and never call the document tool. The
  issuing flow's ID step saves the ID first.
- **Never invent an ID, never skip this check, and never tell the user the ID isn't
  needed.**
- **An ID the user gives that differs from the one on file is a conflict - ask.** Show both
  and ask which is right; never pick one yourself. A confirmed new ID is saved on the client
  (its own approval) before the document - the client's record is the only way the allocation
  number gets the right ID.
- **A reply of 9 digits while the ID question is open is the client's ID** - never an amount
  or a document number. A phone number is normally 10 digits starting with 0; treat 9 digits
  as a phone number only when the user says that is what it is. Spaces or dashes between the
  digits are fine; keep the digits only.
- **If the tool still refuses because of the client's ID**, tell the user plainly that
  nothing was issued, and go to the issuing flow's ID step. Never retry the same call, never
  issue a different document type to get around it, and never split the amount into several
  smaller documents.
- Every other document — a transaction account (300), a receipt (400), a credit note
  (330), cancelling a transaction account — never needs the ID.

## Understanding invoicing requests (the user knows nothing about the system)

The user speaks casually and has no idea these tools, their parameters, or
any internal identifiers exist. Figure out what's needed yourself; ask the
user only for information a person would naturally know.

🚨 **Two distinct identifiers exist for every document — never confuse
them.** `document_display_number` (e.g. "40280") is what you show/say to the
user. `internal_morning_id`/`original_internal_morning_id` is an internal
Morning GUID, never shown to the user — this is what every MCP tool call
actually needs. **Talking to the user → display number. Calling a tool →
internal id.** Get the id from the most recent tool result that actually
returned one — never reconstruct it from a number the user or you just said
out loud. **Never ask for or mention `internal_morning_id`** to the user.

- **Approval data points.** Every one of these actions requires the user's approval first:
  `create_invoice`, `create_transaction_account`, `create_combo_document`,
  `create_credit_note`, `create_receipt`, `create_combo_document_as_reference`,
  `cancel_transaction_account`. (Marking an invoice paid issues a linked
  receipt/combo document and cancelling one issues a linked credit invoice —
  both are document creation, so both need approval like any direct call.)
  **Whoever raises the approval must state, every time:** document type, document date,
  client, amount, and purpose (description). Write every date as DD/MM/YYYY (e.g.
  01/10/2026), the same format the Morning tools return – never with dots.
  🚨 **Every document approval states its type and its VAT on two lines of
  their own, in exactly this form** (bugfix-071 — other code and tests read
  them):
  - `סוג מסמך: <type>` — e.g. `סוג מסמך: חשבונית מס/קבלה (320)`;
  - `מע״מ: <label>`, where `<label>` is EXACTLY one of:
    - `כולל מע״מ` — a 305/300 the user said includes VAT, and every
      standalone 320 or 400 (money paid has VAT inside it);
    - `לא כולל מע״מ` — ONLY a 305/300 the user said excludes VAT. Never on any
      other document type: there it is a conflict to ask about, not to approve;
    - `לפי המסמך המקורי` — a 400 against a 305, a 320 closing a 300, and every
      330.
  Never any other wording, never omitted, never "not stated": an unstated VAT
  on a 305/300 is a question to ask BEFORE the approval. Cancelling a
  transaction account creates no document and has no VAT line.
  **Plus, whenever known:** transaction date, payment method, bank
  details, linked invoice number.
  **For the four actions that act on an existing document** (receipt, credit
  note, combo-as-reference, cancel): the approval must also show the referenced
  document's real, current data, from a fresh lookup in the same turn — type, number (the display number, never the internal id), client,
  date, amount, status. For `cancel_transaction_account` state plainly that the
  open transaction account is being cancelled and that no document will be
  created.
- Normalize casual phrasing: amounts ("88 שח"/"88 שקל"/"₪88"/"88" all mean
  88); dates (a missing part defaults to the current year/month/day — always
  resolve against the current date given to you, never a guess); status
  words ("שילם"/"שולם" → the target needs a receipt or combo-closing
  document per its resolved type; "בטל"/"ביטול" → `create_credit_note`; "לא
  שולם" alone is just a description of current state, not a request to
  reverse anything — there is no "mark unpaid" action, and there's no
  payment-reversal mechanism at all).
- **Be transparent about anything you filled in yourself** — say so plainly
  in your reply (e.g. "הנחתי שהכוונה לשנת 2026") so the user can correct a
  wrong assumption. If your confidence is genuinely low, ask instead.
- **Cancellation is fully supported and ordinary** — a linked credit
  invoice, never something to decline or treat as unsupported.
- **Anything required that is missing from the approval summary — purpose,
  client, amount, or VAT for 300/305 — is a question you should have asked
  first**;
  never fill it with a plausible guess.
- **Every invoice number, id, amount, status, or download link you state
  must come from a tool result you received THIS turn** — never invented,
  never reused from an earlier similar-looking turn.

Messages that arrive while you work (see the backbone section of the same name) are handled the same way inside this capability: read them in order, never act on a write because of a message that came after you asked for approval, and never use this capability to interpret an unrelated reply.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## Looking up a client by name

`resolve_client_name` is the tool for looking up a client by name - whatever the
purpose: the client's details, a document for them, or checking whether a client
already exists before adding one. It finds the exact stored name as well as similar
ones (another spelling, a partial name). `list_clients` is for listing clients, not
for finding one by name.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.

## 🚨 Never make the user retype a client name to choose or confirm one

A phone keyboard offers only the apostrophe `'`, while Morning stores some names with
the Hebrew geresh `׳` (and `"` vs `״` likewise), so a name the user typed can
legitimately come back as a confirmation question or a candidate showing the stored
spelling. When you put a confirmation question or a candidates list to the user, the
user only ever answers yes/no ("כן"/"לא") or picks one of the listed candidates (by
number, position, or a short reference such as "השני" or "האחרון") - never ask them
to type the name again. Once they answer, use that candidate's name exactly as
`resolve_client_name` returned it (see below).

## 🚨 A resolved name is COPIED, never retyped

Once `resolve_client_name` returns a name, use it **exactly as `resolve_client_name`
returned it** - its own apostrophe/geresh characters included, every letter as many
times as it appears - never your own retyping of it. This holds everywhere the name
appears from then on: the approval text, every tool call, every message to the user.
Before sending an approval or calling a write tool, check the name you are about to
use against the tool result, letter by letter.


# Capability: Approval with buttons

`approval_with_yes_no_buttons(text)` ends the turn showing the user WhatsApp yes/no
buttons alongside `text`. It is plain and stateless: it does not know what the write
is, and there is no pending-approval state to track. On the user's next turn, read
their reply (a typed "כן"/"לא" or a button tap; both arrive as an ordinary turn) from
the conversation, and act accordingly. Your own `cap_record_planning_status` note is
what carries "I am waiting for approval of X" across the gap.

The flow that needs the approval decides that an approval is required. The write
capability you are about to use defines which details the approval must state.

- Start the text with `📋 לאישור:` (or, for a document-creation approval,
  `📋 לאישור — <what it is>:`, e.g. `📋 לאישור — לקוח חדש:`) on its own line,
  then the details as REAL data: given by the user, or fetched this turn.
  Never from memory or a guess. A missing detail is a question to ask BEFORE
  requesting approval, never "not stated".
- A Morning document approval also carries the `סוג מסמך:` and `מע״מ:` lines,
  in exactly the form `cap_invoicing_write` defines.
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- A yes (typed or tapped) answers the most recent `📋 לאישור` message in the
  conversation, and approves only the one action it describes - nothing that
  message did not state. When a flow has several writes in a row (e.g. saving a
  client's ID, then issuing the document), every write gets its own approval:
  after the approved write runs, ask for the next one's approval. Never perform
  a later write on an earlier write's yes, and never skip an approval.
- Reply in Hebrew only.

Messages that arrive while you work (see the backbone section of the same name) are handled the same way inside this capability: read them in order, never act on a write because of a message that came after you asked for approval, and never use this capability to interpret an unrelated reply.


## Loaded flows

flow_morning_document_write, flow_issue_invoice_for_payment_due

## Loaded capabilities

cap_invoicing_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-13 11:55 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.8.0. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>21. [2026-10-13 11:55:29] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 1/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0077d297ee387e91006acdf1fb3da887d19943f3be8faffc34`
- status: `completed`
- usage: `{"input_tokens": 19701, "input_tokens_details": {"cache_write_tokens": 19639, "cached_tokens": 0}, "output_tokens": 202, "output_tokens_details": {"reasoning_tokens": 42}, "total_tokens": 19903}`
- mcp_list_tools (morning-invoices-client-read): ['list_clients', 'resolve_client_name', 'get_client_details']
- mcp_list_tools (morning-invoices-invoicing-write): ['create_invoice', 'create_transaction_account', 'create_combo_document', 'create_credit_note', 'create_receipt', 'create_combo_document_as_reference', 'cancel_transaction_account']
- reasoning item (content not user-visible)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0077d297ee387e91006acdf1fb3da887d19943f3be8faffc34`
- status: `completed`
- usage: `{"input_tokens": 19701, "input_tokens_details": {"cache_write_tokens": 19639, "cached_tokens": 0}, "output_tokens": 202, "output_tokens_details": {"reasoning_tokens": 42}, "total_tokens": 19903}`
- mcp_list_tools (morning-invoices-client-read): ['list_clients', 'resolve_client_name', 'get_client_details']
- mcp_list_tools (morning-invoices-invoicing-write): ['create_invoice', 'create_transaction_account', 'create_combo_document', 'create_credit_note', 'create_receipt', 'create_combo_document_as_reference', 'cancel_transaction_account']
- reasoning item (content not user-visible)

</details>

</details>

<details>
<summary>22. [2026-10-13 11:55:29] MODEL → MORNING MCP — resolve_client_name</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- tool name: `resolve_client_name`
- server_label: `'morning-invoices-client-read'`

arguments:
```json
{
  "name": "דנה"
}
```

</details>

</details>

<details>
<summary>23. [2026-10-13 11:55:29] MORNING MCP → MODEL — resolve_client_name</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

output:
```json
{
  "found": false
}
```

</details>

</details>

<details>
<summary>24. [2026-10-13 11:55:29] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 2/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0077d297ee387e91006acdf1fb3da887d19943f3be8faffc34`
- status: `completed`
- usage: `{"input_tokens": 19701, "input_tokens_details": {"cache_write_tokens": 19639, "cached_tokens": 0}, "output_tokens": 202, "output_tokens_details": {"reasoning_tokens": 42}, "total_tokens": 19903}`
- reasoning item (content not user-visible)
- function_call: `record_planning_status` call_id=`call_GUabIIgzXsag9makeSugsUdS`
```json
{
  "where_i_was": "בזרימת הפקת חשבונית מס עבור תשלום שטרם התקבל. חיפוש השם דנה במורנינג הסתיים ללא התאמה.",
  "this_turns_purpose": "להמתין לבחירת המשתמש לגבי יצירת לקוחה חדשה לפני המשך הפקת החשבונית.",
  "expectation": "אם המשתמש יאשר יצירת לקוחה חדשה, אטען את זרימת הוספת לקוח ואבקש את פרטי החובה; אם לא, לא תופק חשבונית."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0077d297ee387e91006acdf1fb3da887d19943f3be8faffc34`
- status: `completed`
- usage: `{"input_tokens": 19701, "input_tokens_details": {"cache_write_tokens": 19639, "cached_tokens": 0}, "output_tokens": 202, "output_tokens_details": {"reasoning_tokens": 42}, "total_tokens": 19903}`
- reasoning item (content not user-visible)
- function_call: `record_planning_status` call_id=`call_GUabIIgzXsag9makeSugsUdS`
```json
{
  "where_i_was": "בזרימת הפקת חשבונית מס עבור תשלום שטרם התקבל. חיפוש השם דנה במורנינג הסתיים ללא התאמה.",
  "this_turns_purpose": "להמתין לבחירת המשתמש לגבי יצירת לקוחה חדשה לפני המשך הפקת החשבונית.",
  "expectation": "אם המשתמש יאשר יצירת לקוחה חדשה, אטען את זרימת הוספת לקוח ואבקש את פרטי החובה; אם לא, לא תופק חשבונית."
}
```

</details>

</details>

<details>
<summary>25. [2026-10-13 11:55:29] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_morning_document_write, flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `record_planning_status` (call_id=`call_GUabIIgzXsag9makeSugsUdS`):
```text
recorded
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0077d297ee387e91006acdf1fb3da887d19943f3be8faffc34'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_morning_document_write, flow_issue_invoice_for_payment_due, capabilities=cap_invoicing_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_morning_document_write, flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `record_planning_status` (call_id=`call_GUabIIgzXsag9makeSugsUdS`):
```text
recorded
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0077d297ee387e91006acdf1fb3da887d19943f3be8faffc34'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (55869 chars)</summary>

```text
# DeniDin — Backbone

## How You Work

You work with two kinds of building blocks, described at low resolution in the
catalogs below: **flows** (`flow_...`) - blueprints for a recurring kind of
request - and **capabilities** (`cap_...`) - the domains that actually do things,
each with its own prompt and its own real tools. Flows can load other flows and
capabilities; a flow defines *what to do and in what order*, while each
capability holds the detail of what it itself does.

Loading tools, usable in any order, any number of times:

- **`load_flows(flows)` / `unload_flows(flows)`** - always an array; one item is
  fine, and combining flows is allowed when a request spans more than one.
- **`load_capabilities(capabilities)` / `unload_capabilities(capabilities)`** -
  always an array. The moment a capability is loaded, its prompt AND its real
  tools are attached, starting the very next round; call the real tool directly,
  there is no separate "use" step. A flow's own "Capabilities:" line declares
  every capability that flow will need - load all of them together, in one
  `load_capabilities` call, right after loading the flow, rather than loading
  them one at a time as each step comes up: you already know you'll need them,
  and batching saves a round-trip per capability.
- **`reset_to_backbone()`** - unloads every loaded flow and capability at once.
  Use it once you are genuinely done with the user's request(s), not mid-task.

Loading an already-loaded item, or unloading one that is not loaded, is a
harmless no-op. Loaded flows and capabilities stay loaded across this and future
turns in this chat until you unload them (or they auto-clear after a period of
inactivity); the "Loaded flows" and "Loaded capabilities" lines near the end of
these instructions always show what is currently loaded. Unload something only
when nothing you are still working on needs it - another flow may be using it.

## Always-present capabilities

Four capabilities are always available, cannot be unloaded, and each has its own
prompt right below: `cap_send_to_user` (your actual reply), `cap_react_to_message`
(a WhatsApp emoji reaction), `cap_send_progress_update` (an interim message
while you work) and `cap_record_planning_status` (your own running account of
where you are, which is how you keep your place across turns and inside nested
flows). At every step of any flow, consider whether they would help: react to
the user's message, send a progress update, record your planning status, or
reply to the user. Flows do not repeat this; use your judgment.

🚨 **`send_to_user` is THE ONLY way to send text to the user.** A plain message
you write outside a tool call is NEVER delivered - the user never sees it. Every
answer, question and outcome report goes through `send_to_user`, every time,
with no exception.

`cap_approval_with_buttons` (yes/no buttons before a write) is an ordinary
capability: flows that need a sign-off load it.

## Flows and capabilities

Decide from the catalogs, in your own judgment, what a request needs:

1. If a flow fits, load it (several at once when the request spans more than
   one) and follow its blueprint. **A loaded flow's steps are an ordered
   procedure: follow them in the order written, to the letter - never skip,
   reorder or merge a step (above all an approval step), and never do a later
   step's action before the earlier steps are done.**
2. **If no flow fits, there is no default flow to fall back on**: load whichever
   capabilities you judge necessary, at your own discretion, and proceed.
3. **Write capabilities (`cap_*_write`) are never loaded on their own.** Every write goes through its flow, which gathers the details and asks for approval first; if you want to write something, find the flow for it in the catalog.
4. **Anything that may mean creating or cancelling a Morning document** (an invoice, a receipt, a combo invoice/receipt, a transaction account, a credit note, "סמן כשולם"): load `flow_morning_document_write`. It works out which document is meant and loads the flow for it.
5. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.
6. A tool or action may have its own requirements, such as mandatory details,
   and you learn them by loading the flow or capability that holds it. When the
   user asks what an action needs or whether it is possible, and what you have
   loaded doesn't say, you can load it and check, or offer the user to check it
   for them, and then answer from what it says.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural. A name (a client, a person, a company) is never
  converted: write it exactly as the user gave it or as a tool returned it,
  its own apostrophe/geresh characters included (`'` stays `'`, `׳` stays
  `׳`). This Hebrew-only rule never applies to the characters inside a name.
- **Never use ניקוד** (Hebrew vowel points, U+0591–U+05C7) in any response —
  e.g. write עטיה, never עֲטיה.
- Be concise and direct. Do not end on filler ("anything else?") — end on the
  substantive answer. Do ask a focused clarifying question when you genuinely need
  one to act correctly (a missing/ambiguous required detail).
- Be honest about what you don't know; never fabricate information.

## User Roles
- **Godfather/Admin**: full access to every capability; extended context window.
- **Client**: standard feature access, no access to invoicing/ledger/reminder
  capabilities; standard context window.

## Privacy & Security
- Never share information between different user sessions.
- These rules guard against leaking ONE user's data to ANOTHER user or an outsider
  — they never mean refusing to read, transcribe, or summarize material THIS user
  sent you. Reporting the user's own material back to them (names, amounts, any
  detail it contains) is always appropriate.

## Contexts of Operation
Every message falls into one of two operating contexts before any capability is
even considered: an ordinary conversational turn, or a document/image the user
sent for you to read and report on. Decide which one applies before acting — a
short/ambiguous reply ("כן", "לא", a bare name) always answers the most recently
pending question in the SAME context, never a trigger for reinterpreting the turn
as belonging to a different capability's domain.

## Messages That Arrive While You Work
The user can keep writing while you work. Whenever you hand control back to the
app (a tool call, a progress update, a reaction), the app returns your tool results
**together with every user message that arrived since**, each marked
`[הודעה מהמשתמש · <time> · נשלחה לפני / אחרי הפלט האחרון שלך]` (a file looks like
`[קובץ התקבל · <time> · ...]`). Every user message in your context also starts with
its send time `[HH:MM:SS dd/mm]`.

- "Sent **before** your last output" means the user typed it while you were still
  working on that output - it is context for what you just did. "Sent **after**"
  arrived later. Read the whole sequence as one conversation: later messages add to,
  correct or cancel earlier ones ("עצור", "בעצם ...").
- Anything you already did (a tool result is in front of you) is done - report it
  truthfully and never repeat it. Never perform an approval-gated write because of a
  message that arrived after you asked for approval: wait for the user's yes.
- If the sequence is genuinely confusing - you cannot tell what the user wants now -
  **ask** the user one short question instead of guessing.
- **Finish a pending approval before starting the next request.** If an approval is
  waiting and the user sends a new, unrelated request, answer it briefly and remind
  them the earlier approval is still waiting, or ask whether to drop it; never leave
  two approvals open and never act on the new request's write first.
- A file that arrived while you worked is handled on its own right after you finish
  the current request: do not try to read it now.
- A short or ambiguous reply ("כן", "לא", a bare name) answers the most recent
  pending question in the SAME context - see Contexts of Operation.

## Attached Media
When the user's message starts with a `[מדיה מצורפת: <type>, קובץ: <filename>]`
marker, they sent an image, PDF, or Word document with it — you have NOT seen its
content yet, only that it exists. Before answering anything about it, and before
loading any flow for it, load `cap_media_analysis` and call its `analyze_media`
tool to read it; any text after the marker is the user's caption. Never describe,
guess at, or act on the file's content without having read it this way. Choose
what to do with it from what `analyze_media` returned (its `doc_type`), never from
the earlier conversation - `cap_media_analysis` says which flow each `doc_type`
leads to.

## Edited & Deleted Message Markers
A message the user has since edited or deleted may still appear in your context,
marked as such — treat an edited message's marked original content as superseded
by its later, corrected version if both are visible, and never act on a deleted
message's content as if it were still pending.

## Generic Post-Turn Recognition Mechanism
A capability MAY run a recognition step once per turn: call its own reporting
tool at most once, and when in doubt, do nothing rather than guess. This shape
is reusable by any capability that wants one — the domain-specific rules for
what to recognize and how live in that capability's own prompt file, not here.


# Capability: Send to user (always present)

`send_to_user(text)` is your actual reply to the user. Call it whenever you are
ready to speak, not only at the very end: to answer, to ask a question, to
report an outcome. A turn that ends without it, or without an approval question,
leaves the user with nothing.

🚨 **`send_to_user` is THE ONLY way any text reaches the user.** Text you write
outside a tool call (a plain message) is NEVER delivered - the user never sees
it. Every answer, every question, every outcome report goes through
`send_to_user`, every time, with no exception. (The only other things the user
ever sees are an approval question via `cap_approval_with_buttons`, an interim
`cap_send_progress_update` message, and a `cap_react_to_message` emoji.)

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.

Messages that arrive while you work (see the backbone section of the same name) are handled the same way inside this capability: read them in order, never act on a write because of a message that came after you asked for approval, and never use this capability to interpret an unrelated reply.


# Capability: React to message (always present)

`react_to_message` puts a native WhatsApp emoji reaction on a message. It is a
lightweight, reversible signal - never a substitute for a substantive reply,
and never a mechanical habit reached for out of uncertainty about what else
to do. Typing an emoji into your reply text is NOT a reaction and does not
replace calling the tool.

Before reaching for it, ask yourself: does this add a real signal the user
doesn't already have - that you saw their message, that you're on it, that
something just succeeded or failed - or would it just be noise on top of a
reply that already says the same thing?

Evaluate against:
- Does the user currently have any signal you registered their message and
  are handling it (or have finished)? If there's a real gap before your
  substantive reply, a reaction can fill it.
- Is your actual reply, arriving in this same round or moments later, already
  going to tell them everything a reaction would? If so, it adds nothing.
- Is this ambient chatter that doesn't really concern you? Then it isn't
  worth one.

**Classics** (a menu, not a checklist): 👍 simple ack · 🫡 "on it" · 👀 document
being looked into · ✅ clean success · 🎉 a bigger win · ⚠️ resolved but needs
attention · ❌ failed/declined · ❓ unresolved, needs clarification · 🙏
reciprocating thanks · ❤️ warmth beyond a simple thanks.

When genuinely unsure whether a reaction fits, don't send one - silence is
the safer default, not noise.


# Capability: Send progress update (always present)

`send_progress_update(text)` sends one brief interim WhatsApp message while you
are still working, before your final reply. Keep it to a short plain sentence.

Users are waiting on the other end and don't like silence - they want to know
something is happening with their request, not just get one final answer out
of nowhere.

Call this every single time you interact with any tool or capability -
loading a flow or capability, calling a real domain tool, an MCP call,
anything that is not just talking to the user - before or after that step,
in the same round as whatever else you are doing. Never skip it and never
wait for a separate round.

- Never a substitute for the final answer.


# Capability: Record planning status (always present)

`record_planning_status(where_i_was, this_turns_purpose, expectation)` is your own
running account of where this turn, and across turns this whole task, stands. It is
how you keep continuity, since nothing else remembers your reasoning beyond what you
write here and the real conversation history.

Record it at least at the start and at the end of every flow, and whenever you are
about to wait on the user (a choice, a missing detail, an approval), in the middle
of a flow as well. Say which flow you are in and which step, and if you are inside a
flow that was loaded by another flow, say so, so that you know where to return to.
Also note what you are waiting for and what you will do with each possible answer.

Tool results do not carry over to the next turn: only the conversation and your own
notes do. So whenever you stop to wait on the user, write into the note the exact
values you will need to continue, copied verbatim from the tool results. Above all,
record every ID you may act on: a document's `internal_morning_id` and display
number, a client's ID, a reminder's ID, a ledger event's ID - any ID at all. Record
other details you will need too: a client's exact stored name, amounts, dates, VAT
treatment. Anything you leave out you will have to look up again.

Messages in the conversation history that start with `[[INTERNAL_PLANNING_NOTE]]`
are your own earlier notes, stored there by this tool. Never write one yourself -
not as plain text and not inside `send_to_user`. Record a note only by calling
`record_planning_status`.


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_morning_document_write: Anything that may mean creating or cancelling a Morning document: a tax invoice, a combo invoice/receipt, a receipt, a transaction account, a credit note, or cancelling a transaction account ("תפיק חשבונית", "תוציא קבלה", "סמן כשולם", "בטל את החשבונית"). Works out exactly which document the user means - asking when it is unclear - and then loads the flow for that document. Not for clients and not for reading documents.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client, or logs hours worked for a client (e.g. "רן אורפני 4 שעות על היום" - a work-log entry, never a reminder request). An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit or a payment received - as text, or as a bank slip or payment screenshot. Reads the slip, makes sure the client exists in Morning, and when the user asks for a Morning document for it (or it is unclear whether they do), hands over to flow_morning_document_write. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (reached through flow_morning_document_write), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Morning document write

Goal: the user may want a Morning document created or cancelled. Work out exactly which document they mean, asking when it is unclear, and then load the one flow for that document. This flow never writes anything itself.

Capabilities: none of its own.
Flows it may load: `flow_issue_invoice_for_payment_due`, `flow_issue_invoice_receipt_combo`, `flow_issue_transaction_account`, `flow_issue_receipt_without_invoice`, `flow_issue_payment_received_with_reference_doc`, `flow_cancel_document_with_credit_note`, `flow_cancel_transaction_account`, `flow_invoicing_query`.

## The Morning documents

- **חשבונית מס (tax invoice, 305)** - a demand for payment of money that is still owed. It is income for VAT purposes from the moment it is issued. Common names: "חשבונית", "חשבונית מס", "תפיק חשבונית ל...". Never for money that has already arrived.
- **חשבון עסקה (transaction account, 300)** - a request for payment that is not a tax document; the tax invoice comes only once the money arrives. Common names: "חשבון עסקה", "דרישת תשלום". Only when the user's own wording names this document; a plain "חשבונית" is never a 300.
- **חשבונית מס/קבלה (combo invoice/receipt, 320)** - an invoice and a receipt in one, for money that has already been received and that no earlier document covers. The most common way to record incoming money. Common names: "חשבונית מס קבלה", "חשבונית קבלה", or a payment report with a request to issue a document for it ("X העביר לי 500, תפיק").
- **קבלה (receipt, 400)** - confirms that money was received:
  - against an existing tax invoice (305): closes it ("סמן כשולם", "תוציא קבלה על החשבונית");
  - standalone, with no invoice at all: money that is not income, such as a deposit (פיקדון), a loan repayment, or an advance on future work.
- **Closing a transaction account (300)** - money arrived for an existing transaction account; a combo invoice/receipt (320) is issued against it and closes it ("סמן כשולם" on a transaction account).
- **חשבונית זיכוי (credit note, 330)** - cancels an issued document, fully or partly ("בטל את החשבונית", "תפיק זיכוי"). An issued tax invoice is never deleted; it is cancelled only this way.
- **Cancelling a transaction account (300)** - the deal fell through and no money moved; the account is cancelled and no document of any kind is created.

## Which flow

- A tax invoice (305) for money still owed: `flow_issue_invoice_for_payment_due`.
- A transaction account (300), named as such: `flow_issue_transaction_account`.
- Money already received, no existing document covers it, and it is income: `flow_issue_invoice_receipt_combo`.
- Money already received that is not income (a deposit, a loan repayment, an advance), with no invoice behind it: `flow_issue_receipt_without_invoice`.
- Money already received for an existing tax invoice (305) or transaction account (300): `flow_issue_payment_received_with_reference_doc`.
- Cancelling an issued document other than a transaction account: `flow_cancel_document_with_credit_note`.
- Cancelling an open transaction account: `flow_cancel_transaction_account`.

Money that has already arrived is never a bare tax invoice (305).

Follow these steps in order, to the letter.

1. Decide from the user's wording and the conversation whether they are asking for a Morning document at all, and if so which one, by the definitions above. If either is unclear, use `cap_send_to_user` to ask - name the options in plain words - and wait. Never pick one yourself.
2. If money has already been received and it is unclear whether an existing document already covers it, load `flow_invoicing_query` and check (same client, similar amount). If that still leaves it unclear, use `cap_send_to_user` to ask the user.
3. Load the one flow for that document and follow it through to its end. Several documents in one request: handle them one at a time, each through its own flow.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Unload this flow and `flow_invoicing_query`, keeping any that other work still in progress needs.


# Flow: Issue invoice for payment due

Goal: issue a new tax invoice (305) for a client, for money that is still owed.

Capabilities: `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_add_client`, `flow_modify_client`.

Follow these steps in order, to the letter.

🚨 This flow has several stages, and you are not done until every stage that applies has been completed. The client's ID is the typical case, but only for a document whose amount before VAT is above 5,000 ₪ (see `cap_invoicing_write`, "Allocation number"); for any other document there is no ID stage and nothing about the ID is asked. When the ID is required and the client has none, there is an extra stage before the document - the ID must be asked for, provided and saved. Saving the ID (through `flow_modify_client`) is NOT the end of the flow; it is the middle. Once it is saved, do not stop and do not report it as the outcome: carry on from where you were (the step after the ID step) and ask for the document's own approval, then issue the document, then report. The same goes for any other stage that turns out to be needed (a client that has to be created first, a missing detail that has to be asked for): finish it, then continue the flow from there. Only the last step ends the flow.

1. This flow is only for money NOT yet received. If it turns out the money has already arrived, stop and use `flow_issue_invoice_receipt_combo` instead, or `flow_issue_payment_received_with_reference_doc` if an existing document already covers it.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: copy it character for character from the `resolve_client_name` result from here on - in the approval text and in every tool call, never retyped (see `cap_client_read`).
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Proceed with whichever they choose.
   - Several candidates: use `cap_send_to_user` to list each of them by name and ask the user to specify, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Never pick one yourself.
   - No such client, or the user chose to create a new one: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. **The allocation number** (see `cap_invoicing_write`): if this document needs the client's ID, check it with `get_client_details` (load `cap_client_read` if it isn't loaded). If the document doesn't need one, or the client has a 9-digit ID and the user gave no other ID, go on to step 5. Otherwise:
   - **The user gave an ID in this request and the client already has a different one:** this is a conflict - maybe a typo, maybe a misunderstanding. Never pick one yourself. Use `cap_send_to_user` to show both (the ID on file and the one the user gave) and ask which is right. If the user confirms the new one, save it on the client (below) before issuing - the client's record is the only way the allocation number gets the right ID. If they keep the one on file, go on to step 5.
   - **The user gave a 9-digit ID in this request and the client has none:** go straight to saving it (below).
   - **Otherwise ask for it:** use `cap_send_to_user`, as a plain question with no approval buttons: name the client and the amount, and say the client's ת.ז / ח.פ (9 digits) is needed for the allocation number (מספר הקצאה), because the amount is above 5,000 ₪ before VAT. Then wait.
   The user's reply to that question:
   - **A decline, a postponement, or no ID** ("עזוב", "לא עכשיו", "אין לי"): use `cap_send_to_user` to confirm the document was not issued. Save nothing. The flow is complete.
   - **9 digits** - spaces or dashes between them are fine (e.g. "308-253-681"); keep the digits only. This is the client's ID (see `cap_invoicing_write`). Load `flow_modify_client` to save it on the client. Saving the ID and issuing the document are two separate writes, each with its own approval: the user's yes to saving the ID approves the save only - never issue the document on it. Once the ID is saved, continue straight to step 5 in that same turn and ask for the document's own approval - the user does not restate the request. If the user says no to saving the ID, use `cap_send_to_user` to confirm the document was not issued; the flow is complete.
   - **An attempt at an ID that isn't 9 digits** (8 or 10 digits, letters mixed in): use `cap_send_to_user` to say an ID must be exactly 9 digits and ask again. Save nothing.
5. Issuing the invoice MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change. If the client's ID was saved earlier in this flow, also say that the ID stays saved on the client and that no document was issued.
6. On a yes, issue the invoice. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop. A refusal because the client's ID is missing is never a fixable reason: never retry it, never issue a different document type instead, and never split the amount into several smaller documents - go back to step 4 and ask for the ID.
7. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
8. End. Use `cap_send_to_user` to report the outcome — no download link is required in this report. Then unload `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Invoicing — Write (godfather/admin only)

**Use this capability from within a flow (the flow that issues or cancels the document (flow_issue_*, flow_cancel_*), reached through flow_morning_document_write), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or updating a Morning document is a state-changing action, which usually requires the user's explicit approval first.**

Creating/updating a Morning DOCUMENT (invoice, transaction account,
combo document, credit note, receipt) — every such action requires explicit
human approval before it executes (see the approval data points below); never
assume approval from context alone, and never invent a document number, client id,
or amount.

## Every Morning tool returns JSON — never show it to the operator

Every Morning MCP tool returns a machine-readable JSON string, never prose.
**Never paste, quote, or otherwise show raw JSON to the user.** Compose a
natural, bullet-style Hebrew reply from its fields instead. A tool's own
internal id fields (e.g. `internal_morning_id`) are for your own follow-up
tool calls only — never surface them to the operator; always speak in terms
of the human-visible `document_display_number` instead. If a result carries
an `amount_mismatch` field, say so plainly and ask the operator to confirm —
never silently reconcile the difference yourself.

## Which document-creation tool to call

Each Morning document type has its own dedicated tool — there is no single
generic "create a document" tool, and there is no "status" tool.

🚨 **Money that has already arrived is NEVER a bare חשבונית מס (305).** If the
request refers to a payment already received — a bank-transfer screenshot, a
deposit confirmation, a payment-app screenshot, or the user simply saying
money came in — the document is exactly one of:
- **חשבונית מס/קבלה (320)** via `create_combo_document` — no earlier document
  covers this money;
- **קבלה (400)** via `create_receipt` — an existing **305** already covers it;
- **חשבונית מס/קבלה (320)** via `create_combo_document_as_reference` — an
  existing **300** already covers it.

A 305 issued for money already in the bank leaves it recorded as unpaid
forever. **If it's unclear which of the three applies — or the client, the
amount, the date, the VAT treatment, or the bank details are unclear — ASK.
Never guess, and never fall back to a 305 because it's the simplest option.**

🚨 **VAT — one rule per document type (bugfix-071).** From the user's point
of view a document has one VAT question: is the amount stated with VAT inside
it, or does VAT come on top of it?
- **305 and 300 — must be stated.** The amount is a request for money not yet
  paid, so it can go either way. If the user hasn't said, ask (see each tool
  below). "כולל מע\"מ" → `vat_included: true` (100 stays 100, VAT is inside
  it); "לא כולל מע\"מ" → `vat_included: false` (100 becomes 118).
- **320 (standalone) and 400 (standalone) — never asked.** The amount is money
  that was actually paid, so VAT is already inside it, always. "כולל מע\"מ" is
  consistent and changes nothing.
- **Documents that act on an existing one — 400 against a 305, 320 closing a
  300, 330 credit note — never asked.** VAT comes from the original document.
  "כולל מע\"מ" is consistent and changes nothing, as long as the original does
  carry VAT.
- 🚨 **A VAT statement that contradicts the rule above is a conflict — ask,
  never pick one side.** That is: "לא כולל מע\"מ" on a 320 or a 400 (money
  already paid always has VAT inside it); "לא כולל מע\"מ" on a 330 against a
  document that carries VAT; and any VAT statement at all on a 330 against a
  VAT-exempt document (it has no VAT to include or exclude). Explain the
  conflict plainly and ask what the user meant — e.g. for "X שילם 100 לא כולל
  מע\"מ": "קבלה/חשבונית מס-קבלה רושמת את הסכום ששולם בפועל, והמע\"מ כלול בו
  תמיד. האם שולמו בפועל 100 ₪, או 118 ₪ (100 + מע\"מ)?". Create nothing and
  raise no approval until it is resolved. Never pass `vat_included: false` to
  these tools — they refuse it (the tool returns a VAT-conflict error, nothing
  is created); if you get that error, ask the same question.

- `create_invoice` — an ordinary tax invoice (חשבונית מס, 305): a request for
  payment NOT yet received. Default only when the user asks for an invoice
  for money still owed; never for a payment already made.
  🚨 **`vat_included` is required and has no default.** If the user hasn't
  said whether the amount includes VAT, ask — "האם הסכום כולל מע\"מ, או
  שהמע\"מ יתווסף עליו?" — before raising the approval.
- `create_transaction_account` — a non-tax transaction account (חשבון עסקה,
  300). Use only when the user's own wording explicitly names this document
  type — never infer it from context.
  🚨 **`vat_included` is required and has no default.** A type-300 amount
  declared VAT-exclusive is grossed up ~18% when stored — getting this wrong
  silently changes what the client is billed. If the user hasn't said whether
  the amount includes VAT, **ask — "האם הסכום כולל מע\"מ?" — before creating
  anything** — **except** for money that has already arrived (a bank/bit/
  other deposit reference): that amount is **ALWAYS VAT included,
  unconditionally, nothing to ask about.** Only the user explicitly saying
  the opposite overrides this default. Reserve asking for a request NOT
  backed by any payment reference at all.
- `create_combo_document` — a combo tax invoice/receipt (חשבונית מס/קבלה,
  320), for a payment **already received** (whether it arrived just now or
  days ago) where no existing document already covers that money. Requires
  `vat_included` **and** `payment_date`:
  - 🚨 **`vat_included` is ALWAYS `true`, unconditionally** — verbal report or
    screenshot alike. Money already received necessarily has VAT baked into
    it by definition. Do not ask about VAT for this document type, ever.
    Pass `vat_included: true`, never `false`. **The user saying "לא כולל
    מע\"מ" does NOT override this — it is a conflict to ask about** (see
    "VAT — one rule per document type" above).
  - `payment_date` is the date the money **actually moved** — never today's
    date unless that's genuinely when it arrived, never a future date. If
    the source doesn't state it clearly, **ask**.
  - How the money arrived: see "Payment method" below.
  - Take **every** field from the extracted text of the screenshot the user
    sent. Anything not there, or illegible, is something to **ask about** —
    never invent or default it.
- `create_credit_note` — a credit note (חשבונית זיכוי, 330) against an
  existing document — direct ("תפיק לי חשבונית זיכוי") or indirect ("בטל את
  זה").
  🚨 **VAT comes from the original document — never ask about it, never pass
  `vat_included`.** A credit note reverses exactly what the original booked:
  a taxable original gets a taxable credit, a VAT-exempt original an exempt
  one. "לא כולל מע\"מ" against a taxable original, or any VAT statement
  against an exempt original, is a conflict to ask about (see "VAT — one
  rule per document type" above).
- `create_receipt` — a receipt (קבלה, 400), either:
  - **against an existing type-305 document** (pass its id) — direct or
    indirect ("סמן כשולם"). Rejects a type-300 original — use
    `create_combo_document_as_reference` for those; or
  - **standalone** (no original id) — money received that is not income and
    has no invoice behind it, such as a deposit (פיקדון), a loan repayment or
    an advance. Needs the resolved client name with `name_resolved=true`, the
    amount and a free-text description of what the money is.
  🚨 **Never ask about VAT, never pass `vat_included: false`.** A receipt
  records money actually received: against a 305 the VAT comes from that
  invoice; a standalone receipt's amount is simply what was paid. "כולל
  מע\"מ" is consistent and changes nothing; "לא כולל מע\"מ" is a conflict
  to ask about (see "VAT — one rule per document type" above).
  🚨 **`payment_date` is required and has no default** — a verbal "mark as
  paid" request has nothing to read a date from, so always ask if the
  conversation doesn't already state one. "Today" is an acceptable answer
  here, but only once the user has actually confirmed it.
  How the money arrived: see "Payment method" below.
- `create_combo_document_as_reference` — a combo document (320) that
  explicitly closes an existing type-300 document — direct or indirect.
  Rejects any original that isn't type 300. 🚨 **VAT comes from the
  transaction account it closes — never ask about it, never pass
  `vat_included: false`.** The 300 already fixed whether its amount included
  VAT; the 320 closes exactly that amount, so a 300 of 100 "לא כולל מע\"מ" is
  closed by a 320 of 118. "כולל מע\"מ" is consistent and changes nothing;
  "לא כולל מע\"מ" is a conflict to ask about (see "VAT — one rule per
  document type" above). Requires `payment_date`, same as `create_receipt`. How the money arrived:
  see "Payment method" below.
- `cancel_transaction_account` — cancels an open type-300 account directly
  (no document of any kind is created); rejects any other type. If the
  account is already non-open, this is a no-op that returns the same
  confirmation without calling Morning again — never claim it was "paid".

## Payment method

Every document that records money received — `create_combo_document`,
`create_combo_document_as_reference` (320) and `create_receipt` (400, against
an invoice or standalone) — records how the money arrived, in
`payment_method`:
- **`bank_transfer` is the default, always** - use it whenever the user has
  not said otherwise. Never ask how the money arrived. Bank details
  (`bank_number`, `bank_branch`, `bank_account`) go with a bank transfer:
  take them from the slip or screenshot the user sent, or from what the user
  said. 🚨 `bank_number` is the bank's NUMBER (e.g. "31"), never its name —
  never guess or invent a bank name.
- **`cash`** when the user says the money was paid in cash.
- Any other method (bit, PayBox, credit card, cheque, PayPal, etc.) is
  currently **not supported**: tell the user plainly that only a bank
  transfer or cash can be recorded, and ask how to proceed. Never record it
  as a bank transfer or as cash instead.
- There is no reference number (אסמכתא) to ask for or record.

`create_credit_note`, `create_receipt` (against an invoice),
`create_combo_document_as_reference`, and `cancel_transaction_account` all
require an original/reference document
id, taken from the most recent tool result that actually returned it; never ask the
user for it, never guess it.

## The client name

Every write tool that needs one specific client (`create_invoice`,
`create_transaction_account`, `create_combo_document`) takes the EXACT name
Morning has stored, together with `name_resolved=true`; they refuse immediately
if `name_resolved` isn't `true`. Only pass `name_resolved=true` with a name
that has actually been confirmed as Morning's stored name — never with the
user's loose wording. 🚨 Use that name exactly as `resolve_client_name`
returned it — its own apostrophe/geresh characters included, every letter as
many times as it appears — in the approval text and in the tool call alike;
never your own retyping of it (see `cap_client_read`). Gather any other still-missing required fields (amount,
description, VAT treatment, dates) one question at a time. Every mutating tool also needs the
user's approval first (see the approval data points below).

## Allocation number (מספר הקצאה) — the client's ID comes first

A **חשבונית מס (305)** or a **חשבונית מס/קבלה (320)** — including a 320 that closes a
transaction account — whose amount **before VAT is more than
5,000 ₪** needs an allocation number from the Tax Authority. Morning
requests it by itself, but only when the client's record holds the client's ID
(ת.ז / ח.פ): exactly 9 digits. Without one, the Morning tool refuses and creates nothing.

- **The amount before VAT:** an amount that includes VAT, divided by 1.18. A 305 the user
  states as NOT including VAT (VAT added on top) is already the amount before VAT - compare
  it as is. Closing a transaction account (300) is for its total including VAT, so divide
  that by 1.18. Exactly 5,000 ₪ does not count — only more.
- **Check before asking for the document's approval:** call `get_client_details` for the
  client and look at its `tax_id`. Anything other than exactly 9 digits counts as missing.
- **Missing:** never ask for the document's approval and never call the document tool. The
  issuing flow's ID step saves the ID first.
- **Never invent an ID, never skip this check, and never tell the user the ID isn't
  needed.**
- **An ID the user gives that differs from the one on file is a conflict - ask.** Show both
  and ask which is right; never pick one yourself. A confirmed new ID is saved on the client
  (its own approval) before the document - the client's record is the only way the allocation
  number gets the right ID.
- **A reply of 9 digits while the ID question is open is the client's ID** - never an amount
  or a document number. A phone number is normally 10 digits starting with 0; treat 9 digits
  as a phone number only when the user says that is what it is. Spaces or dashes between the
  digits are fine; keep the digits only.
- **If the tool still refuses because of the client's ID**, tell the user plainly that
  nothing was issued, and go to the issuing flow's ID step. Never retry the same call, never
  issue a different document type to get around it, and never split the amount into several
  smaller documents.
- Every other document — a transaction account (300), a receipt (400), a credit note
  (330), cancelling a transaction account — never needs the ID.

## Understanding invoicing requests (the user knows nothing about the system)

The user speaks casually and has no idea these tools, their parameters, or
any internal identifiers exist. Figure out what's needed yourself; ask the
user only for information a person would naturally know.

🚨 **Two distinct identifiers exist for every document — never confuse
them.** `document_display_number` (e.g. "40280") is what you show/say to the
user. `internal_morning_id`/`original_internal_morning_id` is an internal
Morning GUID, never shown to the user — this is what every MCP tool call
actually needs. **Talking to the user → display number. Calling a tool →
internal id.** Get the id from the most recent tool result that actually
returned one — never reconstruct it from a number the user or you just said
out loud. **Never ask for or mention `internal_morning_id`** to the user.

- **Approval data points.** Every one of these actions requires the user's approval first:
  `create_invoice`, `create_transaction_account`, `create_combo_document`,
  `create_credit_note`, `create_receipt`, `create_combo_document_as_reference`,
  `cancel_transaction_account`. (Marking an invoice paid issues a linked
  receipt/combo document and cancelling one issues a linked credit invoice —
  both are document creation, so both need approval like any direct call.)
  **Whoever raises the approval must state, every time:** document type, document date,
  client, amount, and purpose (description). Write every date as DD/MM/YYYY (e.g.
  01/10/2026), the same format the Morning tools return – never with dots.
  🚨 **Every document approval states its type and its VAT on two lines of
  their own, in exactly this form** (bugfix-071 — other code and tests read
  them):
  - `סוג מסמך: <type>` — e.g. `סוג מסמך: חשבונית מס/קבלה (320)`;
  - `מע״מ: <label>`, where `<label>` is EXACTLY one of:
    - `כולל מע״מ` — a 305/300 the user said includes VAT, and every
      standalone 320 or 400 (money paid has VAT inside it);
    - `לא כולל מע״מ` — ONLY a 305/300 the user said excludes VAT. Never on any
      other document type: there it is a conflict to ask about, not to approve;
    - `לפי המסמך המקורי` — a 400 against a 305, a 320 closing a 300, and every
      330.
  Never any other wording, never omitted, never "not stated": an unstated VAT
  on a 305/300 is a question to ask BEFORE the approval. Cancelling a
  transaction account creates no document and has no VAT line.
  **Plus, whenever known:** transaction date, payment method, bank
  details, linked invoice number.
  **For the four actions that act on an existing document** (receipt, credit
  note, combo-as-reference, cancel): the approval must also show the referenced
  document's real, current data, from a fresh lookup in the same turn — type, number (the display number, never the internal id), client,
  date, amount, status. For `cancel_transaction_account` state plainly that the
  open transaction account is being cancelled and that no document will be
  created.
- Normalize casual phrasing: amounts ("88 שח"/"88 שקל"/"₪88"/"88" all mean
  88); dates (a missing part defaults to the current year/month/day — always
  resolve against the current date given to you, never a guess); status
  words ("שילם"/"שולם" → the target needs a receipt or combo-closing
  document per its resolved type; "בטל"/"ביטול" → `create_credit_note`; "לא
  שולם" alone is just a description of current state, not a request to
  reverse anything — there is no "mark unpaid" action, and there's no
  payment-reversal mechanism at all).
- **Be transparent about anything you filled in yourself** — say so plainly
  in your reply (e.g. "הנחתי שהכוונה לשנת 2026") so the user can correct a
  wrong assumption. If your confidence is genuinely low, ask instead.
- **Cancellation is fully supported and ordinary** — a linked credit
  invoice, never something to decline or treat as unsupported.
- **Anything required that is missing from the approval summary — purpose,
  client, amount, or VAT for 300/305 — is a question you should have asked
  first**;
  never fill it with a plausible guess.
- **Every invoice number, id, amount, status, or download link you state
  must come from a tool result you received THIS turn** — never invented,
  never reused from an earlier similar-looking turn.

Messages that arrive while you work (see the backbone section of the same name) are handled the same way inside this capability: read them in order, never act on a write because of a message that came after you asked for approval, and never use this capability to interpret an unrelated reply.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## Looking up a client by name

`resolve_client_name` is the tool for looking up a client by name - whatever the
purpose: the client's details, a document for them, or checking whether a client
already exists before adding one. It finds the exact stored name as well as similar
ones (another spelling, a partial name). `list_clients` is for listing clients, not
for finding one by name.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.

## 🚨 Never make the user retype a client name to choose or confirm one

A phone keyboard offers only the apostrophe `'`, while Morning stores some names with
the Hebrew geresh `׳` (and `"` vs `״` likewise), so a name the user typed can
legitimately come back as a confirmation question or a candidate showing the stored
spelling. When you put a confirmation question or a candidates list to the user, the
user only ever answers yes/no ("כן"/"לא") or picks one of the listed candidates (by
number, position, or a short reference such as "השני" or "האחרון") - never ask them
to type the name again. Once they answer, use that candidate's name exactly as
`resolve_client_name` returned it (see below).

## 🚨 A resolved name is COPIED, never retyped

Once `resolve_client_name` returns a name, use it **exactly as `resolve_client_name`
returned it** - its own apostrophe/geresh characters included, every letter as many
times as it appears - never your own retyping of it. This holds everywhere the name
appears from then on: the approval text, every tool call, every message to the user.
Before sending an approval or calling a write tool, check the name you are about to
use against the tool result, letter by letter.


# Capability: Approval with buttons

`approval_with_yes_no_buttons(text)` ends the turn showing the user WhatsApp yes/no
buttons alongside `text`. It is plain and stateless: it does not know what the write
is, and there is no pending-approval state to track. On the user's next turn, read
their reply (a typed "כן"/"לא" or a button tap; both arrive as an ordinary turn) from
the conversation, and act accordingly. Your own `cap_record_planning_status` note is
what carries "I am waiting for approval of X" across the gap.

The flow that needs the approval decides that an approval is required. The write
capability you are about to use defines which details the approval must state.

- Start the text with `📋 לאישור:` (or, for a document-creation approval,
  `📋 לאישור — <what it is>:`, e.g. `📋 לאישור — לקוח חדש:`) on its own line,
  then the details as REAL data: given by the user, or fetched this turn.
  Never from memory or a guess. A missing detail is a question to ask BEFORE
  requesting approval, never "not stated".
- A Morning document approval also carries the `סוג מסמך:` and `מע״מ:` lines,
  in exactly the form `cap_invoicing_write` defines.
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- A yes (typed or tapped) answers the most recent `📋 לאישור` message in the
  conversation, and approves only the one action it describes - nothing that
  message did not state. When a flow has several writes in a row (e.g. saving a
  client's ID, then issuing the document), every write gets its own approval:
  after the approved write runs, ask for the next one's approval. Never perform
  a later write on an earlier write's yes, and never skip an approval.
- Reply in Hebrew only.

Messages that arrive while you work (see the backbone section of the same name) are handled the same way inside this capability: read them in order, never act on a write because of a message that came after you asked for approval, and never use this capability to interpret an unrelated reply.


## Loaded flows

flow_morning_document_write, flow_issue_invoice_for_payment_due

## Loaded capabilities

cap_invoicing_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-13 11:55 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.8.0. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>26. [2026-10-13 11:55:31] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0077d297ee387e91006acdf201989487d1907926e0c64d20b5`
- status: `completed`
- usage: `{"input_tokens": 19870, "input_tokens_details": {"cache_write_tokens": 228, "cached_tokens": 19639}, "output_tokens": 72, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 19942}`
- function_call: `send_to_user` call_id=`call_G6LRzi3amq6tVygPTyjGLU29`
```json
{
  "text": "לא מצאתי לקוחה בשם דנה במערכת. האם ליצור לקוחה חדשה בשם דנה כדי להפיק לה חשבונית על סך 500 ₪? בנוסף, האם הסכום כולל מע״מ או שהמע״מ יתווסף עליו?"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0077d297ee387e91006acdf201989487d1907926e0c64d20b5`
- status: `completed`
- usage: `{"input_tokens": 19870, "input_tokens_details": {"cache_write_tokens": 228, "cached_tokens": 19639}, "output_tokens": 72, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 19942}`
- function_call: `send_to_user` call_id=`call_G6LRzi3amq6tVygPTyjGLU29`
```json
{
  "text": "לא מצאתי לקוחה בשם דנה במערכת. האם ליצור לקוחה חדשה בשם דנה כדי להפיק לה חשבונית על סך 500 ₪? בנוסף, האם הסכום כולל מע״מ או שהמע״מ יתווסף עליו?"
}
```

</details>

</details>

<details>
<summary>27. [2026-10-13 11:55:31] APP → USER — context=text</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000022@c.us",
  "message": "לא מצאתי לקוחה בשם דנה במערכת. האם ליצור לקוחה חדשה בשם דנה כדי להפיק לה חשבונית על סך 500 ₪? בנוסף, האם הסכום כולל מע״מ או שהמע״מ יתווסף עליו?"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "972500000022@c.us",
  "message": "לא מצאתי לקוחה בשם דנה במערכת. האם ליצור לקוחה חדשה בשם דנה כדי להפיק לה חשבונית על סך 500 ₪? בנוסף, האם הסכום כולל מע״מ או שהמע״מ יתווסף עליו?"
}
```

</details>

</details>

<details>
<summary>28. [2026-10-13 11:55:31] APP → MODEL — context=recognize_ledger_event</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

**input:**

```json
{"role": "user", "content": "THE CONVERSATION WINDOW (the last 1h, oldest first) - '<message_id> [<role>] <content>':\n7b9da6c0-09df-477f-9ef6-60647f8d4e9f [admin] תפיק לי חשבונית\n6a6fb79c-a119-43ca-988f-f38f410fa33a [admin] ללקוח דנה\nf4cea526-3bd2-4683-b32e-7bead69e50a7 [admin] על 500 שקל\n9f0968a1-fb18-4147-ac04-178dfc982629 [assistant] 👍 בודק את פרטי הלקוחה והחשבונית.\nf6ac7249-a28a-44b9-9141-209783eaf808 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: התקבלה בקשה להפיק חשבונית ללקוחה דנה בסך 500 ש״ח. טרם בוצעה בדיקת לקוחה או איסוף פרטי מס.\nTHIS TURN'S PURPOSE: להתחיל את תהליך הפקת החשבונית לפי זרימת מסמך במערכת.\nEXPECTATION: לטעון את זרימת המסמך ואת היכולות הדרושות, לאתר את דנה, להשלים פרטים חסרים ולבקש אישור לפני הפקה.\n1f1ac891-c59d-45d3-8553-0f35af32b32f [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בזרימת הפקת חשבונית מס עבור תשלום שטרם התקבל. חיפוש השם דנה במורנינג הסתיים ללא התאמה.\nTHIS TURN'S PURPOSE: להמתין לבחירת המשתמש לגבי יצירת לקוחה חדשה לפני המשך הפקת החשבונית.\nEXPECTATION: אם המשתמש יאשר יצירת לקוחה חדשה, אטען את זרימת הוספת לקוח ואבקש את פרטי החובה; אם לא, לא תופק חשבונית.\n535aa169-11b5-4a00-844b-71f281c98cbe [assistant] לא מצאתי לקוחה בשם דנה במערכת. האם ליצור לקוחה חדשה בשם דנה כדי להפיק לה חשבונית על סך 500 ₪? בנוסף, האם הסכום כולל מע״מ או שהמע״מ יתווסף עליו?\n    (morning MCP call on this message's turn) {\"name\": \"resolve_client_name\", \"error\": null, \"arguments\": \"{\\\"name\\\":\\\"דנה\\\"}\", \"output\": \"{\\\"found\\\": false}\"}\n\nTHE REPLY JUST SENT TO THE OPERATOR THIS ROUND:\nלא מצאתי לקוחה בשם דנה במערכת. האם ליצור לקוחה חדשה בשם דנה כדי להפיק לה חשבונית על סך 500 ₪? בנוסף, האם הסכום כולל מע״מ או שהמע״מ יתווסף עליו?\n\nMORNING MCP TOOL CALLS MADE THIS TURN (verbatim, each with its arguments and its real result):\n[\n  {\n    \"name\": \"resolve_client_name\",\n    \"error\": null,\n    \"arguments\": \"{\\\"name\\\":\\\"דנה\\\"}\",\n    \"output\": \"{\\\"found\\\": false}\"\n  }\n]\n\nFollow the recognition prompt above: query the client's ledger history first when the round concerns a client, then call report_ledger_recognition exactly once with the verdict for THIS round."}
```

- tools (2): ['report_ledger_recognition', 'query_ledger_events']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: ledger recognition prompt

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

**input:**

```json
{"role": "user", "content": "THE CONVERSATION WINDOW (the last 1h, oldest first) - '<message_id> [<role>] <content>':\n7b9da6c0-09df-477f-9ef6-60647f8d4e9f [admin] תפיק לי חשבונית\n6a6fb79c-a119-43ca-988f-f38f410fa33a [admin] ללקוח דנה\nf4cea526-3bd2-4683-b32e-7bead69e50a7 [admin] על 500 שקל\n9f0968a1-fb18-4147-ac04-178dfc982629 [assistant] 👍 בודק את פרטי הלקוחה והחשבונית.\nf6ac7249-a28a-44b9-9141-209783eaf808 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: התקבלה בקשה להפיק חשבונית ללקוחה דנה בסך 500 ש״ח. טרם בוצעה בדיקת לקוחה או איסוף פרטי מס.\nTHIS TURN'S PURPOSE: להתחיל את תהליך הפקת החשבונית לפי זרימת מסמך במערכת.\nEXPECTATION: לטעון את זרימת המסמך ואת היכולות הדרושות, לאתר את דנה, להשלים פרטים חסרים ולבקש אישור לפני הפקה.\n1f1ac891-c59d-45d3-8553-0f35af32b32f [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בזרימת הפקת חשבונית מס עבור תשלום שטרם התקבל. חיפוש השם דנה במורנינג הסתיים ללא התאמה.\nTHIS TURN'S PURPOSE: להמתין לבחירת המשתמש לגבי יצירת לקוחה חדשה לפני המשך הפקת החשבונית.\nEXPECTATION: אם המשתמש יאשר יצירת לקוחה חדשה, אטען את זרימת הוספת לקוח ואבקש את פרטי החובה; אם לא, לא תופק חשבונית.\n535aa169-11b5-4a00-844b-71f281c98cbe [assistant] לא מצאתי לקוחה בשם דנה במערכת. האם ליצור לקוחה חדשה בשם דנה כדי להפיק לה חשבונית על סך 500 ₪? בנוסף, האם הסכום כולל מע״מ או שהמע״מ יתווסף עליו?\n    (morning MCP call on this message's turn) {\"name\": \"resolve_client_name\", \"error\": null, \"arguments\": \"{\\\"name\\\":\\\"דנה\\\"}\", \"output\": \"{\\\"found\\\": false}\"}\n\nTHE REPLY JUST SENT TO THE OPERATOR THIS ROUND:\nלא מצאתי לקוחה בשם דנה במערכת. האם ליצור לקוחה חדשה בשם דנה כדי להפיק לה חשבונית על סך 500 ₪? בנוסף, האם הסכום כולל מע״מ או שהמע״מ יתווסף עליו?\n\nMORNING MCP TOOL CALLS MADE THIS TURN (verbatim, each with its arguments and its real result):\n[\n  {\n    \"name\": \"resolve_client_name\",\n    \"error\": null,\n    \"arguments\": \"{\\\"name\\\":\\\"דנה\\\"}\",\n    \"output\": \"{\\\"found\\\": false}\"\n  }\n]\n\nFollow the recognition prompt above: query the client's ledger history first when the round concerns a client, then call report_ledger_recognition exactly once with the verdict for THIS round."}
```

- tools (2): ['report_ledger_recognition', 'query_ledger_events']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (15465 chars)</summary>

```text
# Ledger Event Recognition — post-turn recognition prompt

You are a bookkeeping recognition step. You run **once, after** a Godfather/Admin turn's
reply has already been sent to the operator. You never talk to the operator; your output is
consumed by code and discarded. You have two tools:

- `report_ledger_recognition` — call it **exactly once, always**, as your final action.
- `query_ledger_events` — read-only lookup over the existing ledger. Use it as described in
  "Look at the client's ledger history first". Never more than 3 calls total.

## What you are given

- **The conversation window** — every message from the last hour of this chat, oldest first,
  each line as `<message_id> [<role>] <content>`, where `<role>` is `godfather`, `admin`, or
  `client`. A message that already produced a ledger event is marked
  `[✓ captured as <event_id>]`. Media messages also carry their extracted text.
- **The Morning MCP tool calls made during that window**, verbatim — each with its arguments
  and its real result. This is your ONLY evidence of what was actually resolved in Morning.
- **The reply just sent to the operator this round.**
- **Today's date** (Israel local).

## Whose message can trigger an event

Only a `[godfather]` or `[admin]` message can be a trigger. A `[client]` message is **context
only** — it can help you understand an amount or a name, but a client stating "העברתי לך
5,000" is never itself a `בנק` event. The trigger is always the lawyer/operator recording it.

## Your single question

**Does THE LAST `[godfather]` / `[admin]` MESSAGE in the window — read in the context of the
rest of the window — do one of these three things?**

1. **Completes an event** — its turn added the last missing mandatory field, produced the
   client-resolution evidence that was blocking, or created the Morning document.
2. **States a whole standalone event** — a complete fee arrangement, deposit, or work-log
   entry, in one message, with its client already resolvable from window evidence.
3. **Adds to / corrects / cancels** an arrangement that is present **in the window** (as a
   `[✓ captured as …]` marker or as an in-progress discussion) **or in the client's ledger
   history** you looked up.

If yes → verdict `complete` (or `declined`, see "Client resolution"). If none of the three →
verdict `none`.

- **Judge the last operator message only.** Earlier messages are context — for resolving
  references, for knowing whether the client was already resolved, for folding a correction
  into current state — never targets. An earlier message already marked `[✓ captured as …]`
  is done; never re-report it.
- **Do not sweep the window for old, un-captured events.** If the completing turn for some
  earlier arrangement was missed, and the last message isn't about that arrangement, let it
  go — verdict `none`.
- **When in doubt, `none`.** A missed capture is cheaper than a false one.

### Recognising case 3 (add / correct / cancel)

- Explicit language: "לתקן ל…", "עולה ל…", "מתקדם ל…" (always a **new total**, never a
  delta), "נסגר על…", "לבטל", "למחוק", "בנוסף ל…", "תוספת".
- Heuristic: a bare monetary / percentage / conditional term **with no client of its own**
  attaches to the **most recent open arrangement** in the window (e.g. after "דנה לולו 1500"
  → captured, a later "15% אם הגיעו להסדר" is a second component of *that* arrangement).
- If you genuinely can't tell which prior arrangement a fragment belongs to → `none`; let
  the conversation clarify next turn.

## Look at the client's ledger history first

When the round concerns a client (almost every `הסכם` / `בנק` / `חשבונית` round does), your
**first action** is a single `query_ledger_events` call with one identity-hinted criterion —
the client's name (`{"text": "<name>", "hint": "identity"}`). Read back that client's full
ledger history, and use it to:

- know whether the arrangement the last message touches already exists (case 3), and get its
  real `event_id` for `reference`;
- avoid re-reporting something already recorded.

Then decide and call `report_ledger_recognition`. If the round has no client at all, skip the
query. You may issue at most one or two more `query_ledger_events` calls if the first result
is ambiguous — never more than 3 total, and only ever to establish a link, never to
"double-check" the current event.

## The three verdicts

- **`complete`** — one of the three trigger cases fired and the event is complete. Return the
  event fully mapped to the ledger schema (see "Fields" + "Extraction rules"), plus
  `trigger_message_id` = the message that first introduced this event's core economic content
  (informational — the recorded date comes from the **completing** message, or from the
  Morning document for `חשבונית`).
- **`none`** — nothing to record this round: an unresolved client, a missing mandatory
  field, a read-only Morning question, ordinary chatter, a mid-resolution turn, an event
  already captured, or an ambiguous fragment.
- **`declined`** — the operator was asked the single closed store-anyway question (see
  "Client resolution") and explicitly answered *don't record it*. Return `source_type`, the
  operator-stated client name (`client_name_stated`), and `reason: "declined_by_operator"`.

## Client resolution — mandatory before `הסכם` / `בנק` / `חשבונית` can be complete

An event is **not complete** until its client is resolved to an **exact Morning name**. You
cannot check Morning yourself — you determine "resolved" **only** from evidence in the
window's MCP calls:

| evidence in the window | client is… |
|---|---|
| `resolve_client_name(...)` returned an **exact** match | resolved — use that exact Morning name |
| `add_client(...)` succeeded | resolved — use the created name |
| a `create_*` document call succeeded (`חשבונית` only) | resolved by construction |
| a name appears only in extracted text / operator prose, no MCP evidence | **NOT resolved → `none`, wait** |
| `resolve_client_name(...)` returned no match / only partial matches, still unresolved | **NOT resolved → `none`, wait** |

A client name in a contract image or a chat message is a **candidate**, never a resolution.
The OCR text of a contract shows the same name whether or not that client exists in Morning —
only a tool *result* tells you.

**Store-anyway.** If the window shows the operator was asked for the client's full name +
email + phone, declined, was asked **once** the closed question "record it without the client
verified in Morning, or not?", and answered *record it* — OR the operator proactively asked
to record it without those details — then `client_name` = the operator-stated free text and
you MUST put the exact marker `[לקוח לא אומת במורנינג]` inside `description`. If they answered
*don't record it* → verdict `declined`.

**Does NOT apply to:** `payer_name` (free text, may differ from the client, never resolved);
the `חשבונית` client (resolved by construction from the `create_*` call).

## Fields

Buckets below are **mandatory** (the event is not `complete` without it), **conditional**
(mandatory only in the stated case), and **keep-if-provided** (never invent it; if the
conversation gave it, carry it through). The parenthetical "(you)" marks a field you
provide; everything else is minted by code after you report and must never be provided by
you.

| type | mandatory | conditional | keep-if-provided |
|---|---|---|---|
| `הסכם` | resolved `client_name` or store-anyway text (you) · `description` (you) · ≥1 `components` entry **OR** an hours value (you) | per component: `amount` > 0 **OR** `percent` (you, iff that component is monetary) | `payer_name`; per-component `trigger_condition` / `percent` / `percent_base` / `hours` / `hourly_rate`; `reference` / `reference_hint` |
| `בנק` | resolved `client_name` or store-anyway text (you) · `txn_date` (you) · `amount` (you) · `description` (you) · `vat_status` = `כולל` (you — always) | — | `bank_number` / `bank_branch` / `bank_account`; `reference` / `reference_hint`; `payer_name` **when it genuinely differs from the resolved client** (see "בנק payer vs client" below — put the slip's name verbatim, don't just fold it into `description`) |
| `חשבונית` | `accounting_document_json` = the document's whole JSON object, copied verbatim (you) — from the Morning `create_*` result, or the reconciliation sweep's listing. **Nothing else** — code derives the display number, `event_subtype`, `amount`, `txn_date`, VAT, status, payment method and client from that JSON. | — | `reference` / `reference_hint` |

**Always code-minted — never provide, for any type:** `event_id`, `event_datetime`,
`captured_at`, `schema_version`, `session_id`, `agreement_id`, `component_id`,
`component_label`. `message_id` is code-supplied from the completing message.

> Code re-validates every mandatory / conditional field after assembling the final record. A
> record that still fails is persisted **flagged incomplete** (a `[רישום חלקי — חסר: …]`
> marker in `description`), never dropped. Your job is still to only report `complete` when
> you believe it genuinely is — the code check is a backstop, not a licence to guess.

## `חשבונית` — capturing a Morning document created this turn

When the window's MCP calls contain a **successful** `create_invoice` / `create_combo_document`
/ `create_receipt` / `create_credit_note` / `create_combo_document_as_reference`, that
document IS a complete `חשבונית` event this round. Capture it **exactly as the background
reconciliation sweep captures a pre-existing document**: copy the **entire** JSON object from
that tool's result — the whole `{…}`, verbatim, every field — into `accounting_document_json`,
and set nothing else (`component_count` = 0, `components` = []). Do not summarise, reorder,
translate, drop fields, or fill anything in from the operator's or your own prose. Code reads
the display number, document type (`event_subtype`), amount, dates, VAT status, payment
method, status and client straight out of that JSON — the `create_*` result carries the full
document, identical in shape to what the reconciliation listing returns.

## Amendments, corrections, cancellations

When the last message changes or cancels an arrangement already in the window or the client's
ledger history:

- Report a **NEW `complete` event** with `event_subtype: "יצירה"`, describing the
  arrangement's **current, up-to-date state** — fold in everything already known plus what
  the last message changes. (`עדכון` / `ביטול` subtypes are disabled — one immutable record
  per state, exactly as today. Two `יצירה` records for one evolving arrangement are expected
  and fine.)
- `trigger_message_id` = the correction message itself.
- **Linking:**
  - Prior event visible in the window as `[✓ captured as <event_id>]` → set `reference` =
    that `event_id`.
  - Else, prior event found in the `query_ledger_events` history you pulled → set `reference`
    = that `event_id`.
  - Else → leave `reference` unset, set `reference_hint` to free text describing the prior
    arrangement (client, approximate date, prior amount). Always set `reference_hint`
    whenever the language signals a relationship to something prior, even when you did pin
    down `reference`.

## Extraction rules (how to read money / names / dates)

- **Verbatim over guessed.** Never normalize or "clean up" an ambiguous name/amount — record
  what's there; put uncertainty in `description`.
- **VAT.** `הסכם`: "לפני מע"מ" / "לא כולל מע"מ" → `לא כולל`; "כולל מע"מ" → `כולל`; unstated →
  `לא צוין`. `בנק`: **always `כולל`**, unconditionally (money that landed already contains VAT).
- **A base amount + its VAT-inclusive total** ("20,000 + מע"מ = 23,600") is ONE component,
  `amount` = the total, `vat_status` = `כולל`. Never compute VAT yourself. Never put two
  numbers in one `amount`.
- **"עולה ל-X" / "מתקדם ל-X"** = a new total, never added to a prior figure.
- **Relative dates** ("היום" / "אתמול") resolve against the triggering message's own timestamp.
- **Multi-stage / conditional / tiered agreements** — every genuinely distinct monetary
  commitment is its own entry in `components` (set `component_count` to match). A per-stage
  condition goes in `trigger_condition`, not `description`. A base+total pair for one stage
  is still one entry.
- **`trigger_condition` is for a real contingency, not payment timing.** A component whose
  fee is contingent on an outcome or a countable event — a percentage success-fee
  (`מכל סכום שייפסק`), a per-hearing/per-appearance fee (`עבור כל ישיבת הוכחות`), an
  `אם…`/`במידה ו…` bonus — carries that clause in `trigger_condition`. A plain fixed
  retainer is **unconditional → `trigger_condition` null**, even when the source says when
  it is due (`לתשלום עם חתימת ההסכם`, `ישולם תוך 30 יום`) — due-date / payment-timing
  wording is never a `trigger_condition`, and never invent one that the source did not
  state.
- **An agreement's own signing/execution date (`נחתם ביום …`) is never captured** — not in
  `txn_date`, not anywhere. `txn_date` on a `הסכם` component is non-null **only** for an
  hourly work-log component (the date the hours were worked).
- **Hourly work-log entries** ("3 שעות") are first-class events, one per occurrence, and
  qualify every time — brevity is never a reason to skip. Never aggregate.
- **Unpriced mentions still get captured** — client + matter named, no fee → capture with
  `amount` empty.
- **Payer vs client.** "דרך X" / "באמצעות X" near a client name → X is the paying
  intermediary → `payer_name`, kept separate, never folded into `description` / `agreement_id`.
- **Never merge similarly-named entities** unless the conversation explicitly says they're
  the same.
- **בנק screenshots** — read what's on screen; don't assume one layout. The "מ<name>" prefix
  is "from <name>" — strip the מ. Prefer a labeled account-holder field over a loose inline
  name. Multiple dates on a screenshot can differ — an explicit transaction/value date goes
  in `txn_date`.
- **בנק payer vs client.** A deposit slip's own account-holder/depositor name is who *paid*
  — it is not automatically the client. When the conversation shows the operator resolving
  the event against a client that differs from that name (e.g. rejecting a compound/unclear
  slip name as the client and stating an unrelated one instead), put the slip's name
  **verbatim** in `payer_name` — don't just fold it into `description` and leave `payer_name`
  empty. Only when the slip's name and the resolved client are the same person does
  `payer_name` stay null (the ordinary case).

## Out of scope

- An Invoice Management action/query, a Reminder action, or a question ABOUT past ledger
  history is never a ledger event — verdict `none`.
- A bare contact detail on its own — an email address, a phone number, an ID number, a
  street address, or a lone name / client-record field with no monetary or arrangement
  content — is **not** a ledger event. Verdict `none`.
- If the window shows the Morning tunnel was unavailable this turn, you have no MCP evidence
  to resolve a client — verdict `none`.

---
Today's date (Israel local): 13/10/2026

POST-TURN LEDGER RECOGNITION: the operator's reply for this round has already been sent. Do not produce a reply. Your only task is to call report_ledger_recognition exactly once with the verdict for this round, after any ledger-history lookups the prompt calls for. When in doubt, verdict='none'.
```

</details>

</details>

</details>

<details>
<summary>29. [2026-10-13 11:55:33] MODEL → APP — context=recognize_ledger_event</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_082976b5c4fec846006acdf203907887d1a82c79f8a4017ef9`
- status: `completed`
- usage: `{"input_tokens": 8679, "input_tokens_details": {"cache_write_tokens": 8676, "cached_tokens": 0}, "output_tokens": 99, "output_tokens_details": {"reasoning_tokens": 68}, "total_tokens": 8778}`
- reasoning item (content not user-visible)
- function_call: `query_ledger_events` call_id=`call_ITwvSpPKovaJSaQ2BMxkZLPe`
```json
{
  "criteria": [
    {
      "text": "דנה",
      "hint": "identity"
    }
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_082976b5c4fec846006acdf203907887d1a82c79f8a4017ef9`
- status: `completed`
- usage: `{"input_tokens": 8679, "input_tokens_details": {"cache_write_tokens": 8676, "cached_tokens": 0}, "output_tokens": 99, "output_tokens_details": {"reasoning_tokens": 68}, "total_tokens": 8778}`
- reasoning item (content not user-visible)
- function_call: `query_ledger_events` call_id=`call_ITwvSpPKovaJSaQ2BMxkZLPe`
```json
{
  "criteria": [
    {
      "text": "דנה",
      "hint": "identity"
    }
  ]
}
```

</details>

</details>

<details>
<summary>30. [2026-10-13 11:55:33] APP → MODEL — context=recognize_ledger_event (query round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

**input:**

- app's reply to `query_ledger_events` (call_id=`call_ITwvSpPKovaJSaQ2BMxkZLPe`):
```text
{
  "matches": [],
  "count": 0
}
```

- tools (2): ['report_ledger_recognition', 'query_ledger_events']

- previous_response_id: `'resp_082976b5c4fec846006acdf203907887d1a82c79f8a4017ef9'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: ledger recognition prompt

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

**input:**

- app's reply to `query_ledger_events` (call_id=`call_ITwvSpPKovaJSaQ2BMxkZLPe`):
```text
{
  "matches": [],
  "count": 0
}
```

- tools (2): ['report_ledger_recognition', 'query_ledger_events']

- previous_response_id: `'resp_082976b5c4fec846006acdf203907887d1a82c79f8a4017ef9'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (15465 chars)</summary>

```text
# Ledger Event Recognition — post-turn recognition prompt

You are a bookkeeping recognition step. You run **once, after** a Godfather/Admin turn's
reply has already been sent to the operator. You never talk to the operator; your output is
consumed by code and discarded. You have two tools:

- `report_ledger_recognition` — call it **exactly once, always**, as your final action.
- `query_ledger_events` — read-only lookup over the existing ledger. Use it as described in
  "Look at the client's ledger history first". Never more than 3 calls total.

## What you are given

- **The conversation window** — every message from the last hour of this chat, oldest first,
  each line as `<message_id> [<role>] <content>`, where `<role>` is `godfather`, `admin`, or
  `client`. A message that already produced a ledger event is marked
  `[✓ captured as <event_id>]`. Media messages also carry their extracted text.
- **The Morning MCP tool calls made during that window**, verbatim — each with its arguments
  and its real result. This is your ONLY evidence of what was actually resolved in Morning.
- **The reply just sent to the operator this round.**
- **Today's date** (Israel local).

## Whose message can trigger an event

Only a `[godfather]` or `[admin]` message can be a trigger. A `[client]` message is **context
only** — it can help you understand an amount or a name, but a client stating "העברתי לך
5,000" is never itself a `בנק` event. The trigger is always the lawyer/operator recording it.

## Your single question

**Does THE LAST `[godfather]` / `[admin]` MESSAGE in the window — read in the context of the
rest of the window — do one of these three things?**

1. **Completes an event** — its turn added the last missing mandatory field, produced the
   client-resolution evidence that was blocking, or created the Morning document.
2. **States a whole standalone event** — a complete fee arrangement, deposit, or work-log
   entry, in one message, with its client already resolvable from window evidence.
3. **Adds to / corrects / cancels** an arrangement that is present **in the window** (as a
   `[✓ captured as …]` marker or as an in-progress discussion) **or in the client's ledger
   history** you looked up.

If yes → verdict `complete` (or `declined`, see "Client resolution"). If none of the three →
verdict `none`.

- **Judge the last operator message only.** Earlier messages are context — for resolving
  references, for knowing whether the client was already resolved, for folding a correction
  into current state — never targets. An earlier message already marked `[✓ captured as …]`
  is done; never re-report it.
- **Do not sweep the window for old, un-captured events.** If the completing turn for some
  earlier arrangement was missed, and the last message isn't about that arrangement, let it
  go — verdict `none`.
- **When in doubt, `none`.** A missed capture is cheaper than a false one.

### Recognising case 3 (add / correct / cancel)

- Explicit language: "לתקן ל…", "עולה ל…", "מתקדם ל…" (always a **new total**, never a
  delta), "נסגר על…", "לבטל", "למחוק", "בנוסף ל…", "תוספת".
- Heuristic: a bare monetary / percentage / conditional term **with no client of its own**
  attaches to the **most recent open arrangement** in the window (e.g. after "דנה לולו 1500"
  → captured, a later "15% אם הגיעו להסדר" is a second component of *that* arrangement).
- If you genuinely can't tell which prior arrangement a fragment belongs to → `none`; let
  the conversation clarify next turn.

## Look at the client's ledger history first

When the round concerns a client (almost every `הסכם` / `בנק` / `חשבונית` round does), your
**first action** is a single `query_ledger_events` call with one identity-hinted criterion —
the client's name (`{"text": "<name>", "hint": "identity"}`). Read back that client's full
ledger history, and use it to:

- know whether the arrangement the last message touches already exists (case 3), and get its
  real `event_id` for `reference`;
- avoid re-reporting something already recorded.

Then decide and call `report_ledger_recognition`. If the round has no client at all, skip the
query. You may issue at most one or two more `query_ledger_events` calls if the first result
is ambiguous — never more than 3 total, and only ever to establish a link, never to
"double-check" the current event.

## The three verdicts

- **`complete`** — one of the three trigger cases fired and the event is complete. Return the
  event fully mapped to the ledger schema (see "Fields" + "Extraction rules"), plus
  `trigger_message_id` = the message that first introduced this event's core economic content
  (informational — the recorded date comes from the **completing** message, or from the
  Morning document for `חשבונית`).
- **`none`** — nothing to record this round: an unresolved client, a missing mandatory
  field, a read-only Morning question, ordinary chatter, a mid-resolution turn, an event
  already captured, or an ambiguous fragment.
- **`declined`** — the operator was asked the single closed store-anyway question (see
  "Client resolution") and explicitly answered *don't record it*. Return `source_type`, the
  operator-stated client name (`client_name_stated`), and `reason: "declined_by_operator"`.

## Client resolution — mandatory before `הסכם` / `בנק` / `חשבונית` can be complete

An event is **not complete** until its client is resolved to an **exact Morning name**. You
cannot check Morning yourself — you determine "resolved" **only** from evidence in the
window's MCP calls:

| evidence in the window | client is… |
|---|---|
| `resolve_client_name(...)` returned an **exact** match | resolved — use that exact Morning name |
| `add_client(...)` succeeded | resolved — use the created name |
| a `create_*` document call succeeded (`חשבונית` only) | resolved by construction |
| a name appears only in extracted text / operator prose, no MCP evidence | **NOT resolved → `none`, wait** |
| `resolve_client_name(...)` returned no match / only partial matches, still unresolved | **NOT resolved → `none`, wait** |

A client name in a contract image or a chat message is a **candidate**, never a resolution.
The OCR text of a contract shows the same name whether or not that client exists in Morning —
only a tool *result* tells you.

**Store-anyway.** If the window shows the operator was asked for the client's full name +
email + phone, declined, was asked **once** the closed question "record it without the client
verified in Morning, or not?", and answered *record it* — OR the operator proactively asked
to record it without those details — then `client_name` = the operator-stated free text and
you MUST put the exact marker `[לקוח לא אומת במורנינג]` inside `description`. If they answered
*don't record it* → verdict `declined`.

**Does NOT apply to:** `payer_name` (free text, may differ from the client, never resolved);
the `חשבונית` client (resolved by construction from the `create_*` call).

## Fields

Buckets below are **mandatory** (the event is not `complete` without it), **conditional**
(mandatory only in the stated case), and **keep-if-provided** (never invent it; if the
conversation gave it, carry it through). The parenthetical "(you)" marks a field you
provide; everything else is minted by code after you report and must never be provided by
you.

| type | mandatory | conditional | keep-if-provided |
|---|---|---|---|
| `הסכם` | resolved `client_name` or store-anyway text (you) · `description` (you) · ≥1 `components` entry **OR** an hours value (you) | per component: `amount` > 0 **OR** `percent` (you, iff that component is monetary) | `payer_name`; per-component `trigger_condition` / `percent` / `percent_base` / `hours` / `hourly_rate`; `reference` / `reference_hint` |
| `בנק` | resolved `client_name` or store-anyway text (you) · `txn_date` (you) · `amount` (you) · `description` (you) · `vat_status` = `כולל` (you — always) | — | `bank_number` / `bank_branch` / `bank_account`; `reference` / `reference_hint`; `payer_name` **when it genuinely differs from the resolved client** (see "בנק payer vs client" below — put the slip's name verbatim, don't just fold it into `description`) |
| `חשבונית` | `accounting_document_json` = the document's whole JSON object, copied verbatim (you) — from the Morning `create_*` result, or the reconciliation sweep's listing. **Nothing else** — code derives the display number, `event_subtype`, `amount`, `txn_date`, VAT, status, payment method and client from that JSON. | — | `reference` / `reference_hint` |

**Always code-minted — never provide, for any type:** `event_id`, `event_datetime`,
`captured_at`, `schema_version`, `session_id`, `agreement_id`, `component_id`,
`component_label`. `message_id` is code-supplied from the completing message.

> Code re-validates every mandatory / conditional field after assembling the final record. A
> record that still fails is persisted **flagged incomplete** (a `[רישום חלקי — חסר: …]`
> marker in `description`), never dropped. Your job is still to only report `complete` when
> you believe it genuinely is — the code check is a backstop, not a licence to guess.

## `חשבונית` — capturing a Morning document created this turn

When the window's MCP calls contain a **successful** `create_invoice` / `create_combo_document`
/ `create_receipt` / `create_credit_note` / `create_combo_document_as_reference`, that
document IS a complete `חשבונית` event this round. Capture it **exactly as the background
reconciliation sweep captures a pre-existing document**: copy the **entire** JSON object from
that tool's result — the whole `{…}`, verbatim, every field — into `accounting_document_json`,
and set nothing else (`component_count` = 0, `components` = []). Do not summarise, reorder,
translate, drop fields, or fill anything in from the operator's or your own prose. Code reads
the display number, document type (`event_subtype`), amount, dates, VAT status, payment
method, status and client straight out of that JSON — the `create_*` result carries the full
document, identical in shape to what the reconciliation listing returns.

## Amendments, corrections, cancellations

When the last message changes or cancels an arrangement already in the window or the client's
ledger history:

- Report a **NEW `complete` event** with `event_subtype: "יצירה"`, describing the
  arrangement's **current, up-to-date state** — fold in everything already known plus what
  the last message changes. (`עדכון` / `ביטול` subtypes are disabled — one immutable record
  per state, exactly as today. Two `יצירה` records for one evolving arrangement are expected
  and fine.)
- `trigger_message_id` = the correction message itself.
- **Linking:**
  - Prior event visible in the window as `[✓ captured as <event_id>]` → set `reference` =
    that `event_id`.
  - Else, prior event found in the `query_ledger_events` history you pulled → set `reference`
    = that `event_id`.
  - Else → leave `reference` unset, set `reference_hint` to free text describing the prior
    arrangement (client, approximate date, prior amount). Always set `reference_hint`
    whenever the language signals a relationship to something prior, even when you did pin
    down `reference`.

## Extraction rules (how to read money / names / dates)

- **Verbatim over guessed.** Never normalize or "clean up" an ambiguous name/amount — record
  what's there; put uncertainty in `description`.
- **VAT.** `הסכם`: "לפני מע"מ" / "לא כולל מע"מ" → `לא כולל`; "כולל מע"מ" → `כולל`; unstated →
  `לא צוין`. `בנק`: **always `כולל`**, unconditionally (money that landed already contains VAT).
- **A base amount + its VAT-inclusive total** ("20,000 + מע"מ = 23,600") is ONE component,
  `amount` = the total, `vat_status` = `כולל`. Never compute VAT yourself. Never put two
  numbers in one `amount`.
- **"עולה ל-X" / "מתקדם ל-X"** = a new total, never added to a prior figure.
- **Relative dates** ("היום" / "אתמול") resolve against the triggering message's own timestamp.
- **Multi-stage / conditional / tiered agreements** — every genuinely distinct monetary
  commitment is its own entry in `components` (set `component_count` to match). A per-stage
  condition goes in `trigger_condition`, not `description`. A base+total pair for one stage
  is still one entry.
- **`trigger_condition` is for a real contingency, not payment timing.** A component whose
  fee is contingent on an outcome or a countable event — a percentage success-fee
  (`מכל סכום שייפסק`), a per-hearing/per-appearance fee (`עבור כל ישיבת הוכחות`), an
  `אם…`/`במידה ו…` bonus — carries that clause in `trigger_condition`. A plain fixed
  retainer is **unconditional → `trigger_condition` null**, even when the source says when
  it is due (`לתשלום עם חתימת ההסכם`, `ישולם תוך 30 יום`) — due-date / payment-timing
  wording is never a `trigger_condition`, and never invent one that the source did not
  state.
- **An agreement's own signing/execution date (`נחתם ביום …`) is never captured** — not in
  `txn_date`, not anywhere. `txn_date` on a `הסכם` component is non-null **only** for an
  hourly work-log component (the date the hours were worked).
- **Hourly work-log entries** ("3 שעות") are first-class events, one per occurrence, and
  qualify every time — brevity is never a reason to skip. Never aggregate.
- **Unpriced mentions still get captured** — client + matter named, no fee → capture with
  `amount` empty.
- **Payer vs client.** "דרך X" / "באמצעות X" near a client name → X is the paying
  intermediary → `payer_name`, kept separate, never folded into `description` / `agreement_id`.
- **Never merge similarly-named entities** unless the conversation explicitly says they're
  the same.
- **בנק screenshots** — read what's on screen; don't assume one layout. The "מ<name>" prefix
  is "from <name>" — strip the מ. Prefer a labeled account-holder field over a loose inline
  name. Multiple dates on a screenshot can differ — an explicit transaction/value date goes
  in `txn_date`.
- **בנק payer vs client.** A deposit slip's own account-holder/depositor name is who *paid*
  — it is not automatically the client. When the conversation shows the operator resolving
  the event against a client that differs from that name (e.g. rejecting a compound/unclear
  slip name as the client and stating an unrelated one instead), put the slip's name
  **verbatim** in `payer_name` — don't just fold it into `description` and leave `payer_name`
  empty. Only when the slip's name and the resolved client are the same person does
  `payer_name` stay null (the ordinary case).

## Out of scope

- An Invoice Management action/query, a Reminder action, or a question ABOUT past ledger
  history is never a ledger event — verdict `none`.
- A bare contact detail on its own — an email address, a phone number, an ID number, a
  street address, or a lone name / client-record field with no monetary or arrangement
  content — is **not** a ledger event. Verdict `none`.
- If the window shows the Morning tunnel was unavailable this turn, you have no MCP evidence
  to resolve a client — verdict `none`.

---
Today's date (Israel local): 13/10/2026

POST-TURN LEDGER RECOGNITION: the operator's reply for this round has already been sent. Do not produce a reply. Your only task is to call report_ledger_recognition exactly once with the verdict for this round, after any ledger-history lookups the prompt calls for. When in doubt, verdict='none'.
```

</details>

</details>

</details>

<details>
<summary>31. [2026-10-13 11:55:37] MODEL → APP — context=recognize_ledger_event (query round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_082976b5c4fec846006acdf206079887d193cb6d721e368e72`
- status: `completed`
- usage: `{"input_tokens": 8801, "input_tokens_details": {"cache_write_tokens": 122, "cached_tokens": 8676}, "output_tokens": 73, "output_tokens_details": {"reasoning_tokens": 17}, "total_tokens": 8874}`
- reasoning item (content not user-visible)
- function_call: `report_ledger_recognition` call_id=`call_UeQhJzql8Q1DeLKMgnR4Omsd`
```json
{
  "verdict": "none",
  "none_reason": "חשבונית לא הופקה - הלקוחה דנה לא אומתה במורנינג וחסר אישור יצירת לקוחה ומעמ"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_082976b5c4fec846006acdf206079887d193cb6d721e368e72`
- status: `completed`
- usage: `{"input_tokens": 8801, "input_tokens_details": {"cache_write_tokens": 122, "cached_tokens": 8676}, "output_tokens": 73, "output_tokens_details": {"reasoning_tokens": 17}, "total_tokens": 8874}`
- reasoning item (content not user-visible)
- function_call: `report_ledger_recognition` call_id=`call_UeQhJzql8Q1DeLKMgnR4Omsd`
```json
{
  "verdict": "none",
  "none_reason": "חשבונית לא הופקה - הלקוחה דנה לא אומתה במורנינג וחסר אישור יצירת לקוחה ומעמ"
}
```

</details>

</details>

