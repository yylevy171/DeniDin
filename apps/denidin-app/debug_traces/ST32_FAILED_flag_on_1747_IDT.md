# Wire trace

Each numbered section below is one wire-crossing event, in strict chronological order (the number always goes up by 1, regardless of which boundary/direction it is). Click a section to expand it. Each has exactly two sub-sections, marked `↳` - Audit (concise) and Debug (full, verbatim) - and, inside Debug only, the long `instructions` text nests one level deeper, marked `↳↳`.

<details>
<summary>1. [2026-10-01 17:47:30] USER → APP — context=webhook</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "typeWebhook": "incomingMessageReceived",
  "timestamp": 1790866050,
  "idMessage": "stage1b-4_SEED_A1_1790866050",
  "instanceData": {
    "idInstance": 7103000000,
    "wid": "972501234567@c.us",
    "typeInstance": "whatsapp"
  },
  "senderData": {
    "chatId": "+972501234567@c.us",
    "sender": "+972501234567@c.us",
    "senderName": "E2E Godfather"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {
      "textMessage": "תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"
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
  "timestamp": 1790866050,
  "idMessage": "stage1b-4_SEED_A1_1790866050",
  "instanceData": {
    "idInstance": 7103000000,
    "wid": "972501234567@c.us",
    "typeInstance": "whatsapp"
  },
  "senderData": {
    "chatId": "+972501234567@c.us",
    "sender": "+972501234567@c.us",
    "senderName": "E2E Godfather"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {
      "textMessage": "תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"
    }
  }
}
```

</details>

</details>

<details>
<summary>2. [2026-10-01 17:47:31] APP → MODEL — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

```json
{"role": "user", "content": "תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"}
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
{"role": "user", "content": "תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (18854 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
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

THE CURRENT DATE AND TIME IS 2026-10-01 17:47 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>3. [2026-10-01 17:47:33] MODEL → APP — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_081312889a8ed190006abe7283ba9c87d19e4378b1be29cd04`
- status: `completed`
- usage: `{"input_tokens": 5913, "input_tokens_details": {"cache_write_tokens": 5910, "cached_tokens": 0}, "output_tokens": 81, "output_tokens_details": {"reasoning_tokens": 53}, "total_tokens": 5994}`
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_LiPysLKqn7JakBoDswAO4goE`
```json
{
  "emoji": "🫡",
  "message_id": null
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_081312889a8ed190006abe7283ba9c87d19e4378b1be29cd04`
- status: `completed`
- usage: `{"input_tokens": 5913, "input_tokens_details": {"cache_write_tokens": 5910, "cached_tokens": 0}, "output_tokens": 81, "output_tokens_details": {"reasoning_tokens": 53}, "total_tokens": 5994}`
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_LiPysLKqn7JakBoDswAO4goE`
```json
{
  "emoji": "🫡",
  "message_id": null
}
```

</details>

</details>

<details>
<summary>4. [2026-10-01 17:47:33] APP → USER — context=reaction — 🫡 — NOT SENT (no WhatsApp bot in this run)</summary>

```text
[084] react_to_message call 'call_LiPysLKqn7JakBoDswAO4goE': nothing to react through (target_id='stage1b-4_SEED_A1_1790866050', chat_id='+972501234567@c.us', green_api_bot_set=False)
```

</details>

<details>
<summary>5. [2026-10-01 17:47:33] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `react_to_message` (call_id=`call_LiPysLKqn7JakBoDswAO4goE`):
```text
{
  "status": "failed"
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_081312889a8ed190006abe7283ba9c87d19e4378b1be29cd04'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `react_to_message` (call_id=`call_LiPysLKqn7JakBoDswAO4goE`):
```text
{
  "status": "failed"
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_081312889a8ed190006abe7283ba9c87d19e4378b1be29cd04'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (18854 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
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

THE CURRENT DATE AND TIME IS 2026-10-01 17:47 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>6. [2026-10-01 17:47:35] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_081312889a8ed190006abe7285d28487d192b7b7d300fe0e29`
- status: `completed`
- usage: `{"input_tokens": 6012, "input_tokens_details": {"cache_write_tokens": 99, "cached_tokens": 5910}, "output_tokens": 33, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6045}`
- function_call: `send_progress_update` call_id=`call_90JFhXYGzGYNVv4fpoY8RT7t`
```json
{
  "text": "בודק אם הלקוחה כבר קיימת לפני יצירת הרשומה."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_081312889a8ed190006abe7285d28487d192b7b7d300fe0e29`
- status: `completed`
- usage: `{"input_tokens": 6012, "input_tokens_details": {"cache_write_tokens": 99, "cached_tokens": 5910}, "output_tokens": 33, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6045}`
- function_call: `send_progress_update` call_id=`call_90JFhXYGzGYNVv4fpoY8RT7t`
```json
{
  "text": "בודק אם הלקוחה כבר קיימת לפני יצירת הרשומה."
}
```

</details>

</details>

<details>
<summary>7. [2026-10-01 17:47:35] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "בודק אם הלקוחה כבר קיימת לפני יצירת הרשומה."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "בודק אם הלקוחה כבר קיימת לפני יצירת הרשומה."
}
```

</details>

</details>

<details>
<summary>8. [2026-10-01 17:47:35] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
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
<summary>9. [2026-10-01 17:47:35] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `send_progress_update` (call_id=`call_90JFhXYGzGYNVv4fpoY8RT7t`):
```text
{
  "sent": true
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_081312889a8ed190006abe7285d28487d192b7b7d300fe0e29'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `send_progress_update` (call_id=`call_90JFhXYGzGYNVv4fpoY8RT7t`):
```text
{
  "sent": true
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_081312889a8ed190006abe7285d28487d192b7b7d300fe0e29'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (18854 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
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

THE CURRENT DATE AND TIME IS 2026-10-01 17:47 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>10. [2026-10-01 17:47:38] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_081312889a8ed190006abe728819b487d198e992af6f3659ae`
- status: `completed`
- usage: `{"input_tokens": 6062, "input_tokens_details": {"cache_write_tokens": 50, "cached_tokens": 6009}, "output_tokens": 102, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6164}`
- function_call: `record_planning_status` call_id=`call_w7UBdIGSJNDKHSPDhrN1a11R`
```json
{
  "where_i_was": "התחלת טיפול בבקשה להוספת לקוחה חדשה.",
  "this_turns_purpose": "לבדוק כפילויות, לאסוף את פרטי הלקוחה, לקבל אישור וליצור את הרשומה.",
  "expectation": "אטעין את תהליך הוספת הלקוח ואת יכולות חיפוש וכתיבה, ואז אבקש אישור לפני היצירה."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_081312889a8ed190006abe728819b487d198e992af6f3659ae`
- status: `completed`
- usage: `{"input_tokens": 6062, "input_tokens_details": {"cache_write_tokens": 50, "cached_tokens": 6009}, "output_tokens": 102, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6164}`
- function_call: `record_planning_status` call_id=`call_w7UBdIGSJNDKHSPDhrN1a11R`
```json
{
  "where_i_was": "התחלת טיפול בבקשה להוספת לקוחה חדשה.",
  "this_turns_purpose": "לבדוק כפילויות, לאסוף את פרטי הלקוחה, לקבל אישור וליצור את הרשומה.",
  "expectation": "אטעין את תהליך הוספת הלקוח ואת יכולות חיפוש וכתיבה, ואז אבקש אישור לפני היצירה."
}
```

</details>

</details>

<details>
<summary>11. [2026-10-01 17:47:38] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `record_planning_status` (call_id=`call_w7UBdIGSJNDKHSPDhrN1a11R`):
```text
recorded
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_081312889a8ed190006abe728819b487d198e992af6f3659ae'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `record_planning_status` (call_id=`call_w7UBdIGSJNDKHSPDhrN1a11R`):
```text
recorded
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_081312889a8ed190006abe728819b487d198e992af6f3659ae'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (18854 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
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

THE CURRENT DATE AND TIME IS 2026-10-01 17:47 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>12. [2026-10-01 17:47:40] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_081312889a8ed190006abe728aad7487d184ab495abfc806f4`
- status: `completed`
- usage: `{"input_tokens": 6179, "input_tokens_details": {"cache_write_tokens": 117, "cached_tokens": 6059}, "output_tokens": 22, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6201}`
- function_call: `load_flows` call_id=`call_ea5iefmSNMPzsl5Y6ZEvtk3u`
```json
{
  "flows": [
    "flow_add_client"
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_081312889a8ed190006abe728aad7487d184ab495abfc806f4`
- status: `completed`
- usage: `{"input_tokens": 6179, "input_tokens_details": {"cache_write_tokens": 117, "cached_tokens": 6059}, "output_tokens": 22, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6201}`
- function_call: `load_flows` call_id=`call_ea5iefmSNMPzsl5Y6ZEvtk3u`
```json
{
  "flows": [
    "flow_add_client"
  ]
}
```

</details>

</details>

<details>
<summary>13. [2026-10-01 17:47:40] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: (none - plain backbone)

**input:**

- app's reply to `load_flows` (call_id=`call_ea5iefmSNMPzsl5Y6ZEvtk3u`):
```text
loaded flows: flow_add_client. Loaded flows now: flow_add_client. Loaded capabilities now: (none). Their blueprint text is attached starting now.
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_081312889a8ed190006abe728aad7487d184ab495abfc806f4'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: (none - plain backbone)

**input:**

- app's reply to `load_flows` (call_id=`call_ea5iefmSNMPzsl5Y6ZEvtk3u`):
```text
loaded flows: flow_add_client. Loaded flows now: flow_add_client. Loaded capabilities now: (none). Their blueprint text is attached starting now.
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_081312889a8ed190006abe728aad7487d184ab495abfc806f4'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (20773 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


## Loaded flows

flow_add_client

## Loaded capabilities

(none - plain backbone)

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:47 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>14. [2026-10-01 17:47:42] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_081312889a8ed190006abe728c7d1487d1a895de1b2389d381`
- status: `completed`
- usage: `{"input_tokens": 6695, "input_tokens_details": {"cache_write_tokens": 6692, "cached_tokens": 0}, "output_tokens": 30, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6725}`
- function_call: `send_progress_update` call_id=`call_QNbrBgPQ2ZvO7vl0TSi3uyeg`
```json
{
  "text": "טוען את כלי הבדיקה הנדרשים."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_081312889a8ed190006abe728c7d1487d1a895de1b2389d381`
- status: `completed`
- usage: `{"input_tokens": 6695, "input_tokens_details": {"cache_write_tokens": 6692, "cached_tokens": 0}, "output_tokens": 30, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6725}`
- function_call: `send_progress_update` call_id=`call_QNbrBgPQ2ZvO7vl0TSi3uyeg`
```json
{
  "text": "טוען את כלי הבדיקה הנדרשים."
}
```

</details>

</details>

<details>
<summary>15. [2026-10-01 17:47:42] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "טוען את כלי הבדיקה הנדרשים."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "טוען את כלי הבדיקה הנדרשים."
}
```

</details>

</details>

<details>
<summary>16. [2026-10-01 17:47:42] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
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
<summary>17. [2026-10-01 17:47:42] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: (none - plain backbone)

**input:**

- app's reply to `send_progress_update` (call_id=`call_QNbrBgPQ2ZvO7vl0TSi3uyeg`):
```text
{
  "sent": true
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_081312889a8ed190006abe728c7d1487d1a895de1b2389d381'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: (none - plain backbone)

**input:**

- app's reply to `send_progress_update` (call_id=`call_QNbrBgPQ2ZvO7vl0TSi3uyeg`):
```text
{
  "sent": true
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_081312889a8ed190006abe728c7d1487d1a895de1b2389d381'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (20773 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


## Loaded flows

flow_add_client

## Loaded capabilities

(none - plain backbone)

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:47 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>18. [2026-10-01 17:47:43] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_081312889a8ed190006abe728e84c487d18a886e473d27cbcb`
- status: `completed`
- usage: `{"input_tokens": 6742, "input_tokens_details": {"cache_write_tokens": 47, "cached_tokens": 6692}, "output_tokens": 33, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6775}`
- function_call: `load_capabilities` call_id=`call_DTx7tC356IOpgm2T4I3mg1vM`
```json
{
  "capabilities": [
    "cap_client_read",
    "cap_client_write",
    "cap_approval_with_buttons"
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_081312889a8ed190006abe728e84c487d18a886e473d27cbcb`
- status: `completed`
- usage: `{"input_tokens": 6742, "input_tokens_details": {"cache_write_tokens": 47, "cached_tokens": 6692}, "output_tokens": 33, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6775}`
- function_call: `load_capabilities` call_id=`call_DTx7tC356IOpgm2T4I3mg1vM`
```json
{
  "capabilities": [
    "cap_client_read",
    "cap_client_write",
    "cap_approval_with_buttons"
  ]
}
```

</details>

</details>

<details>
<summary>19. [2026-10-01 17:47:43] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `load_capabilities` (call_id=`call_DTx7tC356IOpgm2T4I3mg1vM`):
```text
loaded capabilitys: cap_client_read, cap_client_write, cap_approval_with_buttons. Loaded flows now: flow_add_client. Loaded capabilities now: cap_client_read, cap_client_write, cap_approval_with_buttons. Their instructions and tools are attached starting now.
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_081312889a8ed190006abe728e84c487d18a886e473d27cbcb'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `load_capabilities` (call_id=`call_DTx7tC356IOpgm2T4I3mg1vM`):
```text
loaded capabilitys: cap_client_read, cap_client_write, cap_approval_with_buttons. Loaded flows now: flow_add_client. Loaded capabilities now: cap_client_read, cap_client_write, cap_approval_with_buttons. Their instructions and tools are attached starting now.
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_081312889a8ed190006abe728e84c487d18a886e473d27cbcb'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24959 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:47 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>20. [2026-10-01 17:47:48] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_081312889a8ed190006abe729024c087d1881456a00a8e7f6d`
- status: `completed`
- usage: `{"input_tokens": 8591, "input_tokens_details": {"cache_write_tokens": 8588, "cached_tokens": 0}, "output_tokens": 90, "output_tokens_details": {"reasoning_tokens": 56}, "total_tokens": 8681}`
- mcp_list_tools (morning-invoices-client-read): ['list_clients', 'resolve_client_name', 'get_client_details']
- mcp_list_tools (morning-invoices-client-write): ['add_client', 'update_client']
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_xINZ38Vo86qMkpo8DfQPqMYe`
```json
{
  "text": "מחפש לקוחה קיימת או דומה בשם שסיפקת."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_081312889a8ed190006abe729024c087d1881456a00a8e7f6d`
- status: `completed`
- usage: `{"input_tokens": 8591, "input_tokens_details": {"cache_write_tokens": 8588, "cached_tokens": 0}, "output_tokens": 90, "output_tokens_details": {"reasoning_tokens": 56}, "total_tokens": 8681}`
- mcp_list_tools (morning-invoices-client-read): ['list_clients', 'resolve_client_name', 'get_client_details']
- mcp_list_tools (morning-invoices-client-write): ['add_client', 'update_client']
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_xINZ38Vo86qMkpo8DfQPqMYe`
```json
{
  "text": "מחפש לקוחה קיימת או דומה בשם שסיפקת."
}
```

</details>

</details>

<details>
<summary>21. [2026-10-01 17:47:48] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "מחפש לקוחה קיימת או דומה בשם שסיפקת."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "מחפש לקוחה קיימת או דומה בשם שסיפקת."
}
```

</details>

</details>

<details>
<summary>22. [2026-10-01 17:47:48] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
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
<summary>23. [2026-10-01 17:47:48] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `send_progress_update` (call_id=`call_xINZ38Vo86qMkpo8DfQPqMYe`):
```text
{
  "sent": true
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_081312889a8ed190006abe729024c087d1881456a00a8e7f6d'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `send_progress_update` (call_id=`call_xINZ38Vo86qMkpo8DfQPqMYe`):
```text
{
  "sent": true
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_081312889a8ed190006abe729024c087d1881456a00a8e7f6d'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24959 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:47 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>24. [2026-10-01 17:47:54] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 1/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_081312889a8ed190006abe72946ab487d1b5895e4b035cad1b`
- status: `completed`
- usage: `{"input_tokens": 8758, "input_tokens_details": {"cache_write_tokens": 8697, "cached_tokens": 0}, "output_tokens": 183, "output_tokens_details": {"reasoning_tokens": 29}, "total_tokens": 8941}`

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_081312889a8ed190006abe72946ab487d1b5895e4b035cad1b`
- status: `completed`
- usage: `{"input_tokens": 8758, "input_tokens_details": {"cache_write_tokens": 8697, "cached_tokens": 0}, "output_tokens": 183, "output_tokens_details": {"reasoning_tokens": 29}, "total_tokens": 8941}`
- (no output items in this part)

</details>

</details>

<details>
<summary>25. [2026-10-01 17:47:54] MODEL → MORNING MCP — list_clients</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- tool name: `list_clients`
- server_label: `'morning-invoices-client-read'`

arguments:
```json
{
  "name": "ג'סיקה סוקולוביץ'"
}
```

</details>

</details>

<details>
<summary>26. [2026-10-01 17:47:54] MORNING MCP → MODEL — list_clients</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

output:
```json
{
  "count": 0,
  "clients": []
}
```

</details>

</details>

<details>
<summary>27. [2026-10-01 17:47:54] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 2/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_081312889a8ed190006abe72946ab487d1b5895e4b035cad1b`
- status: `completed`
- usage: `{"input_tokens": 8758, "input_tokens_details": {"cache_write_tokens": 8697, "cached_tokens": 0}, "output_tokens": 183, "output_tokens_details": {"reasoning_tokens": 29}, "total_tokens": 8941}`
- reasoning item (content not user-visible)
- function_call: `record_planning_status` call_id=`call_gAlTtC7OBF1TxsiIhIpeyei9`
```json
{
  "where_i_was": "בתהליך הוספת לקוחה חדשה. חיפוש במערכת הסתיים ללא לקוחות קיימים או דומים בשם ג'סיקה סוקולוביץ'. הפרטים המלאים זמינים.",
  "this_turns_purpose": "לבקש אישור מפורש ליצירת הלקוחה החדשה.",
  "expectation": "לאחר תשובה חיובית אצור את הרשומה; לאחר תשובה שלילית לא אבצע יצירה ואבקש מה לשנות."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_081312889a8ed190006abe72946ab487d1b5895e4b035cad1b`
- status: `completed`
- usage: `{"input_tokens": 8758, "input_tokens_details": {"cache_write_tokens": 8697, "cached_tokens": 0}, "output_tokens": 183, "output_tokens_details": {"reasoning_tokens": 29}, "total_tokens": 8941}`
- reasoning item (content not user-visible)
- function_call: `record_planning_status` call_id=`call_gAlTtC7OBF1TxsiIhIpeyei9`
```json
{
  "where_i_was": "בתהליך הוספת לקוחה חדשה. חיפוש במערכת הסתיים ללא לקוחות קיימים או דומים בשם ג'סיקה סוקולוביץ'. הפרטים המלאים זמינים.",
  "this_turns_purpose": "לבקש אישור מפורש ליצירת הלקוחה החדשה.",
  "expectation": "לאחר תשובה חיובית אצור את הרשומה; לאחר תשובה שלילית לא אבצע יצירה ואבקש מה לשנות."
}
```

</details>

</details>

<details>
<summary>28. [2026-10-01 17:47:54] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `record_planning_status` (call_id=`call_gAlTtC7OBF1TxsiIhIpeyei9`):
```text
recorded
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_081312889a8ed190006abe72946ab487d1b5895e4b035cad1b'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `record_planning_status` (call_id=`call_gAlTtC7OBF1TxsiIhIpeyei9`):
```text
recorded
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_081312889a8ed190006abe72946ab487d1b5895e4b035cad1b'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24959 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:47 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>29. [2026-10-01 17:47:56] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_081312889a8ed190006abe729a9a4487d186c92a4b0efe86b9`
- status: `completed`
- usage: `{"input_tokens": 8915, "input_tokens_details": {"cache_write_tokens": 215, "cached_tokens": 8697}, "output_tokens": 74, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 8989}`
- function_call: `approval_with_yes_no_buttons` call_id=`call_MwZkeNPrSJNfsMr8FYqI8kMv`
```json
{
  "text": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_081312889a8ed190006abe729a9a4487d186c92a4b0efe86b9`
- status: `completed`
- usage: `{"input_tokens": 8915, "input_tokens_details": {"cache_write_tokens": 215, "cached_tokens": 8697}, "output_tokens": 74, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 8989}`
- function_call: `approval_with_yes_no_buttons` call_id=`call_MwZkeNPrSJNfsMr8FYqI8kMv`
```json
{
  "text": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"
}
```

</details>

</details>

<details>
<summary>30. [2026-10-01 17:47:56] APP → USER — context=buttons</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"
}
```

</details>

</details>

<details>
<summary>31. [2026-10-01 17:47:56] USER → APP — context=webhook</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "typeWebhook": "incomingMessageReceived",
  "timestamp": 1790866076,
  "idMessage": "stage1b-4_FORCE_NEW_A1_1790866076",
  "instanceData": {
    "idInstance": 7103000000,
    "wid": "972501234567@c.us",
    "typeInstance": "whatsapp"
  },
  "senderData": {
    "chatId": "+972501234567@c.us",
    "sender": "+972501234567@c.us",
    "senderName": "E2E Godfather"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {
      "textMessage": "לא, תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"
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
  "timestamp": 1790866076,
  "idMessage": "stage1b-4_FORCE_NEW_A1_1790866076",
  "instanceData": {
    "idInstance": 7103000000,
    "wid": "972501234567@c.us",
    "typeInstance": "whatsapp"
  },
  "senderData": {
    "chatId": "+972501234567@c.us",
    "sender": "+972501234567@c.us",
    "senderName": "E2E Godfather"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {
      "textMessage": "לא, תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"
    }
  }
}
```

</details>

</details>

<details>
<summary>32. [2026-10-01 17:47:57] APP → MODEL — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

```json
{"role": "user", "content": "תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"}
```
```json
{"role": "assistant", "content": "בודק אם הלקוחה כבר קיימת לפני יצירת הרשומה."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: התחלת טיפול בבקשה להוספת לקוחה חדשה.\nTHIS TURN'S PURPOSE: לבדוק כפילויות, לאסוף את פרטי הלקוחה, לקבל אישור וליצור את הרשומה.\nEXPECTATION: אטעין את תהליך הוספת הלקוח ואת יכולות חיפוש וכתיבה, ואז אבקש אישור לפני היצירה."}
```
```json
{"role": "assistant", "content": "טוען את כלי הבדיקה הנדרשים."}
```
```json
{"role": "assistant", "content": "מחפש לקוחה קיימת או דומה בשם שסיפקת."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך הוספת לקוחה חדשה. חיפוש במערכת הסתיים ללא לקוחות קיימים או דומים בשם ג'סיקה סוקולוביץ'. הפרטים המלאים זמינים.\nTHIS TURN'S PURPOSE: לבקש אישור מפורש ליצירת הלקוחה החדשה.\nEXPECTATION: לאחר תשובה חיובית אצור את הרשומה; לאחר תשובה שלילית לא אבצע יצירה ואבקש מה לשנות."}
```
```json
{"role": "assistant", "content": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"}
```
```json
{"role": "user", "content": "לא, תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

```json
{"role": "user", "content": "תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"}
```
```json
{"role": "assistant", "content": "בודק אם הלקוחה כבר קיימת לפני יצירת הרשומה."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: התחלת טיפול בבקשה להוספת לקוחה חדשה.\nTHIS TURN'S PURPOSE: לבדוק כפילויות, לאסוף את פרטי הלקוחה, לקבל אישור וליצור את הרשומה.\nEXPECTATION: אטעין את תהליך הוספת הלקוח ואת יכולות חיפוש וכתיבה, ואז אבקש אישור לפני היצירה."}
```
```json
{"role": "assistant", "content": "טוען את כלי הבדיקה הנדרשים."}
```
```json
{"role": "assistant", "content": "מחפש לקוחה קיימת או דומה בשם שסיפקת."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך הוספת לקוחה חדשה. חיפוש במערכת הסתיים ללא לקוחות קיימים או דומים בשם ג'סיקה סוקולוביץ'. הפרטים המלאים זמינים.\nTHIS TURN'S PURPOSE: לבקש אישור מפורש ליצירת הלקוחה החדשה.\nEXPECTATION: לאחר תשובה חיובית אצור את הרשומה; לאחר תשובה שלילית לא אבצע יצירה ואבקש מה לשנות."}
```
```json
{"role": "assistant", "content": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"}
```
```json
{"role": "user", "content": "לא, תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24959 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:47 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>33. [2026-10-01 17:48:01] MODEL → APP — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0a82368eccc4c16d006abe729d496887d1a018acba2f6a6a31`
- status: `completed`
- usage: `{"input_tokens": 8487, "input_tokens_details": {"cache_write_tokens": 411, "cached_tokens": 8073}, "output_tokens": 130, "output_tokens_details": {"reasoning_tokens": 102}, "total_tokens": 8617}`
- mcp_list_tools (morning-invoices-client-read): ['list_clients', 'resolve_client_name', 'get_client_details']
- mcp_list_tools (morning-invoices-client-write): ['add_client', 'update_client']
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_AuXSgbKNr9L0Ju5bECqVuyyh`
```json
{
  "emoji": "🫡",
  "message_id": null
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0a82368eccc4c16d006abe729d496887d1a018acba2f6a6a31`
- status: `completed`
- usage: `{"input_tokens": 8487, "input_tokens_details": {"cache_write_tokens": 411, "cached_tokens": 8073}, "output_tokens": 130, "output_tokens_details": {"reasoning_tokens": 102}, "total_tokens": 8617}`
- mcp_list_tools (morning-invoices-client-read): ['list_clients', 'resolve_client_name', 'get_client_details']
- mcp_list_tools (morning-invoices-client-write): ['add_client', 'update_client']
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_AuXSgbKNr9L0Ju5bECqVuyyh`
```json
{
  "emoji": "🫡",
  "message_id": null
}
```

</details>

</details>

<details>
<summary>34. [2026-10-01 17:48:01] APP → USER — context=reaction — 🫡 — NOT SENT (no WhatsApp bot in this run)</summary>

```text
[084] react_to_message call 'call_AuXSgbKNr9L0Ju5bECqVuyyh': nothing to react through (target_id='stage1b-4_FORCE_NEW_A1_1790866076', chat_id='+972501234567@c.us', green_api_bot_set=False)
```

</details>

<details>
<summary>35. [2026-10-01 17:48:01] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `react_to_message` (call_id=`call_AuXSgbKNr9L0Ju5bECqVuyyh`):
```text
{
  "status": "failed"
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0a82368eccc4c16d006abe729d496887d1a018acba2f6a6a31'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `react_to_message` (call_id=`call_AuXSgbKNr9L0Ju5bECqVuyyh`):
```text
{
  "status": "failed"
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0a82368eccc4c16d006abe729d496887d1a018acba2f6a6a31'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24959 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:47 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>36. [2026-10-01 17:48:04] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0a82368eccc4c16d006abe72a1f7e887d18f1ae6e2e15a4d9c`
- status: `completed`
- usage: `{"input_tokens": 8637, "input_tokens_details": {"cache_write_tokens": 559, "cached_tokens": 8075}, "output_tokens": 102, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 8739}`
- function_call: `record_planning_status` call_id=`call_TB1KQNIOEPYaLLJyY458bztW`
```json
{
  "where_i_was": "בתהליך הוספת לקוחה חדשה, והאישור הקודם נדחה. המשתמש חזר על בקשת ההוספה עם אותם פרטים.",
  "this_turns_purpose": "לוודא אם זו בקשה חדשה לאישור או ביטול של היצירה.",
  "expectation": "אבקש אישור מפורש מחדש, בלי ליצור את הרשומה לפני תשובה חיובית."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0a82368eccc4c16d006abe72a1f7e887d18f1ae6e2e15a4d9c`
- status: `completed`
- usage: `{"input_tokens": 8637, "input_tokens_details": {"cache_write_tokens": 559, "cached_tokens": 8075}, "output_tokens": 102, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 8739}`
- function_call: `record_planning_status` call_id=`call_TB1KQNIOEPYaLLJyY458bztW`
```json
{
  "where_i_was": "בתהליך הוספת לקוחה חדשה, והאישור הקודם נדחה. המשתמש חזר על בקשת ההוספה עם אותם פרטים.",
  "this_turns_purpose": "לוודא אם זו בקשה חדשה לאישור או ביטול של היצירה.",
  "expectation": "אבקש אישור מפורש מחדש, בלי ליצור את הרשומה לפני תשובה חיובית."
}
```

</details>

</details>

<details>
<summary>37. [2026-10-01 17:48:04] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `record_planning_status` (call_id=`call_TB1KQNIOEPYaLLJyY458bztW`):
```text
recorded
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0a82368eccc4c16d006abe72a1f7e887d18f1ae6e2e15a4d9c'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `record_planning_status` (call_id=`call_TB1KQNIOEPYaLLJyY458bztW`):
```text
recorded
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0a82368eccc4c16d006abe72a1f7e887d18f1ae6e2e15a4d9c'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24959 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:47 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>38. [2026-10-01 17:48:06] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0a82368eccc4c16d006abe72a4e77887d1acdea0031f8c77a2`
- status: `completed`
- usage: `{"input_tokens": 8752, "input_tokens_details": {"cache_write_tokens": 265, "cached_tokens": 8484}, "output_tokens": 74, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 8826}`
- function_call: `approval_with_yes_no_buttons` call_id=`call_d0yhoyhvn1Ik7PQBDFTXtLqD`
```json
{
  "text": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0a82368eccc4c16d006abe72a4e77887d1acdea0031f8c77a2`
- status: `completed`
- usage: `{"input_tokens": 8752, "input_tokens_details": {"cache_write_tokens": 265, "cached_tokens": 8484}, "output_tokens": 74, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 8826}`
- function_call: `approval_with_yes_no_buttons` call_id=`call_d0yhoyhvn1Ik7PQBDFTXtLqD`
```json
{
  "text": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"
}
```

</details>

</details>

<details>
<summary>39. [2026-10-01 17:48:06] APP → USER — context=buttons</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"
}
```

</details>

</details>

<details>
<summary>40. [2026-10-01 17:48:06] USER → APP — context=webhook</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "typeWebhook": "incomingMessageReceived",
  "timestamp": 1790866086,
  "idMessage": "stage1b-4_APPROVE_A1_1790866086",
  "instanceData": {
    "idInstance": 7103000000,
    "wid": "972501234567@c.us",
    "typeInstance": "whatsapp"
  },
  "senderData": {
    "chatId": "+972501234567@c.us",
    "sender": "+972501234567@c.us",
    "senderName": "E2E Godfather"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {
      "textMessage": "כן"
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
  "timestamp": 1790866086,
  "idMessage": "stage1b-4_APPROVE_A1_1790866086",
  "instanceData": {
    "idInstance": 7103000000,
    "wid": "972501234567@c.us",
    "typeInstance": "whatsapp"
  },
  "senderData": {
    "chatId": "+972501234567@c.us",
    "sender": "+972501234567@c.us",
    "senderName": "E2E Godfather"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {
      "textMessage": "כן"
    }
  }
}
```

</details>

</details>

<details>
<summary>41. [2026-10-01 17:48:07] APP → MODEL — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

```json
{"role": "user", "content": "תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"}
```
```json
{"role": "assistant", "content": "בודק אם הלקוחה כבר קיימת לפני יצירת הרשומה."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: התחלת טיפול בבקשה להוספת לקוחה חדשה.\nTHIS TURN'S PURPOSE: לבדוק כפילויות, לאסוף את פרטי הלקוחה, לקבל אישור וליצור את הרשומה.\nEXPECTATION: אטעין את תהליך הוספת הלקוח ואת יכולות חיפוש וכתיבה, ואז אבקש אישור לפני היצירה."}
```
```json
{"role": "assistant", "content": "טוען את כלי הבדיקה הנדרשים."}
```
```json
{"role": "assistant", "content": "מחפש לקוחה קיימת או דומה בשם שסיפקת."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך הוספת לקוחה חדשה. חיפוש במערכת הסתיים ללא לקוחות קיימים או דומים בשם ג'סיקה סוקולוביץ'. הפרטים המלאים זמינים.\nTHIS TURN'S PURPOSE: לבקש אישור מפורש ליצירת הלקוחה החדשה.\nEXPECTATION: לאחר תשובה חיובית אצור את הרשומה; לאחר תשובה שלילית לא אבצע יצירה ואבקש מה לשנות."}
```
```json
{"role": "assistant", "content": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"}
```
```json
{"role": "user", "content": "לא, תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך הוספת לקוחה חדשה, והאישור הקודם נדחה. המשתמש חזר על בקשת ההוספה עם אותם פרטים.\nTHIS TURN'S PURPOSE: לוודא אם זו בקשה חדשה לאישור או ביטול של היצירה.\nEXPECTATION: אבקש אישור מפורש מחדש, בלי ליצור את הרשומה לפני תשובה חיובית."}
```
```json
{"role": "assistant", "content": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"}
```
```json
{"role": "user", "content": "כן"}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

```json
{"role": "user", "content": "תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"}
```
```json
{"role": "assistant", "content": "בודק אם הלקוחה כבר קיימת לפני יצירת הרשומה."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: התחלת טיפול בבקשה להוספת לקוחה חדשה.\nTHIS TURN'S PURPOSE: לבדוק כפילויות, לאסוף את פרטי הלקוחה, לקבל אישור וליצור את הרשומה.\nEXPECTATION: אטעין את תהליך הוספת הלקוח ואת יכולות חיפוש וכתיבה, ואז אבקש אישור לפני היצירה."}
```
```json
{"role": "assistant", "content": "טוען את כלי הבדיקה הנדרשים."}
```
```json
{"role": "assistant", "content": "מחפש לקוחה קיימת או דומה בשם שסיפקת."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך הוספת לקוחה חדשה. חיפוש במערכת הסתיים ללא לקוחות קיימים או דומים בשם ג'סיקה סוקולוביץ'. הפרטים המלאים זמינים.\nTHIS TURN'S PURPOSE: לבקש אישור מפורש ליצירת הלקוחה החדשה.\nEXPECTATION: לאחר תשובה חיובית אצור את הרשומה; לאחר תשובה שלילית לא אבצע יצירה ואבקש מה לשנות."}
```
```json
{"role": "assistant", "content": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"}
```
```json
{"role": "user", "content": "לא, תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך הוספת לקוחה חדשה, והאישור הקודם נדחה. המשתמש חזר על בקשת ההוספה עם אותם פרטים.\nTHIS TURN'S PURPOSE: לוודא אם זו בקשה חדשה לאישור או ביטול של היצירה.\nEXPECTATION: אבקש אישור מפורש מחדש, בלי ליצור את הרשומה לפני תשובה חיובית."}
```
```json
{"role": "assistant", "content": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"}
```
```json
{"role": "user", "content": "כן"}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24959 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:48 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>42. [2026-10-01 17:48:11] MODEL → APP — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_02f4e5a07ea17168006abe72a75c8c87d194d89c8df0754167`
- status: `completed`
- usage: `{"input_tokens": 8646, "input_tokens_details": {"cache_write_tokens": 8643, "cached_tokens": 0}, "output_tokens": 139, "output_tokens_details": {"reasoning_tokens": 113}, "total_tokens": 8785}`
- mcp_list_tools (morning-invoices-client-read): ['list_clients', 'resolve_client_name', 'get_client_details']
- mcp_list_tools (morning-invoices-client-write): ['add_client', 'update_client']
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_AWHxmQ15xv9iHJ688xpLc8ne`
```json
{
  "emoji": "👍",
  "message_id": null
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_02f4e5a07ea17168006abe72a75c8c87d194d89c8df0754167`
- status: `completed`
- usage: `{"input_tokens": 8646, "input_tokens_details": {"cache_write_tokens": 8643, "cached_tokens": 0}, "output_tokens": 139, "output_tokens_details": {"reasoning_tokens": 113}, "total_tokens": 8785}`
- mcp_list_tools (morning-invoices-client-read): ['list_clients', 'resolve_client_name', 'get_client_details']
- mcp_list_tools (morning-invoices-client-write): ['add_client', 'update_client']
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_AWHxmQ15xv9iHJ688xpLc8ne`
```json
{
  "emoji": "👍",
  "message_id": null
}
```

</details>

</details>

<details>
<summary>43. [2026-10-01 17:48:11] APP → USER — context=reaction — 👍 — NOT SENT (no WhatsApp bot in this run)</summary>

```text
[084] react_to_message call 'call_AWHxmQ15xv9iHJ688xpLc8ne': nothing to react through (target_id='stage1b-4_APPROVE_A1_1790866086', chat_id='+972501234567@c.us', green_api_bot_set=False)
```

</details>

<details>
<summary>44. [2026-10-01 17:48:11] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `react_to_message` (call_id=`call_AWHxmQ15xv9iHJ688xpLc8ne`):
```text
{
  "status": "failed"
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_02f4e5a07ea17168006abe72a75c8c87d194d89c8df0754167'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `react_to_message` (call_id=`call_AWHxmQ15xv9iHJ688xpLc8ne`):
```text
{
  "status": "failed"
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_02f4e5a07ea17168006abe72a75c8c87d194d89c8df0754167'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24959 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:48 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>45. [2026-10-01 17:48:15] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_02f4e5a07ea17168006abe72ac0a1c87d19c353cca0c4b0426`
- status: `completed`
- usage: `{"input_tokens": 8803, "input_tokens_details": {"cache_write_tokens": 157, "cached_tokens": 8643}, "output_tokens": 56, "output_tokens_details": {"reasoning_tokens": 24}, "total_tokens": 8859}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_8N8xZ5Pz16qQmPxPyupk6hMP`
```json
{
  "text": "מבצע עכשיו את יצירת הלקוחה במערכת."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_02f4e5a07ea17168006abe72ac0a1c87d19c353cca0c4b0426`
- status: `completed`
- usage: `{"input_tokens": 8803, "input_tokens_details": {"cache_write_tokens": 157, "cached_tokens": 8643}, "output_tokens": 56, "output_tokens_details": {"reasoning_tokens": 24}, "total_tokens": 8859}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_8N8xZ5Pz16qQmPxPyupk6hMP`
```json
{
  "text": "מבצע עכשיו את יצירת הלקוחה במערכת."
}
```

</details>

</details>

<details>
<summary>46. [2026-10-01 17:48:15] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "מבצע עכשיו את יצירת הלקוחה במערכת."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "מבצע עכשיו את יצירת הלקוחה במערכת."
}
```

</details>

</details>

<details>
<summary>47. [2026-10-01 17:48:15] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
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
<summary>48. [2026-10-01 17:48:15] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `send_progress_update` (call_id=`call_8N8xZ5Pz16qQmPxPyupk6hMP`):
```text
{
  "sent": true
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_02f4e5a07ea17168006abe72ac0a1c87d19c353cca0c4b0426'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `send_progress_update` (call_id=`call_8N8xZ5Pz16qQmPxPyupk6hMP`):
```text
{
  "sent": true
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_02f4e5a07ea17168006abe72ac0a1c87d19c353cca0c4b0426'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24959 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:48 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>49. [2026-10-01 17:48:21] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 1/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_02f4e5a07ea17168006abe72af8c0087d1a841866c65f2a650`
- status: `completed`
- usage: `{"input_tokens": 9051, "input_tokens_details": {"cache_write_tokens": 8875, "cached_tokens": 0}, "output_tokens": 160, "output_tokens_details": {"reasoning_tokens": 17}, "total_tokens": 9211}`

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_02f4e5a07ea17168006abe72af8c0087d1a841866c65f2a650`
- status: `completed`
- usage: `{"input_tokens": 9051, "input_tokens_details": {"cache_write_tokens": 8875, "cached_tokens": 0}, "output_tokens": 160, "output_tokens_details": {"reasoning_tokens": 17}, "total_tokens": 9211}`
- (no output items in this part)

</details>

</details>

<details>
<summary>50. [2026-10-01 17:48:21] MODEL → MORNING MCP — add_client</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- tool name: `add_client`
- server_label: `'morning-invoices-client-write'`

arguments:
```json
{
  "name": "ג'סיקה סוקולוביץ'",
  "email": "e2e-client-545352@example.com",
  "phone": "050-1234567",
  "tax_id": null
}
```

</details>

</details>

<details>
<summary>51. [2026-10-01 17:48:21] MORNING MCP → MODEL — add_client</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

output:
```json
{
  "status": "created",
  "client": {
    "name": "ג'סיקה סוקולוביץ'",
    "email": "e2e-client-545352@example.com",
    "phone": "050-1234567",
    "tax_id": null
  }
}
```

</details>

</details>

<details>
<summary>52. [2026-10-01 17:48:21] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 2/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_02f4e5a07ea17168006abe72af8c0087d1a841866c65f2a650`
- status: `completed`
- usage: `{"input_tokens": 9051, "input_tokens_details": {"cache_write_tokens": 8875, "cached_tokens": 0}, "output_tokens": 160, "output_tokens_details": {"reasoning_tokens": 17}, "total_tokens": 9211}`
- reasoning item (content not user-visible)
- function_call: `record_planning_status` call_id=`call_EQeZ6ivp9FhAzGMkA7ZH2eie`
```json
{
  "where_i_was": "תהליך הוספת הלקוחה הושלם לאחר אישור מפורש. הרשומה נוצרה בהצלחה במערכת.",
  "this_turns_purpose": "לדווח למשתמש על הצלחת יצירת הלקוחה.",
  "expectation": "אין פעולה נוספת נדרשת עבור בקשה זו."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_02f4e5a07ea17168006abe72af8c0087d1a841866c65f2a650`
- status: `completed`
- usage: `{"input_tokens": 9051, "input_tokens_details": {"cache_write_tokens": 8875, "cached_tokens": 0}, "output_tokens": 160, "output_tokens_details": {"reasoning_tokens": 17}, "total_tokens": 9211}`
- reasoning item (content not user-visible)
- function_call: `record_planning_status` call_id=`call_EQeZ6ivp9FhAzGMkA7ZH2eie`
```json
{
  "where_i_was": "תהליך הוספת הלקוחה הושלם לאחר אישור מפורש. הרשומה נוצרה בהצלחה במערכת.",
  "this_turns_purpose": "לדווח למשתמש על הצלחת יצירת הלקוחה.",
  "expectation": "אין פעולה נוספת נדרשת עבור בקשה זו."
}
```

</details>

</details>

<details>
<summary>53. [2026-10-01 17:48:21] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `record_planning_status` (call_id=`call_EQeZ6ivp9FhAzGMkA7ZH2eie`):
```text
recorded
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_02f4e5a07ea17168006abe72af8c0087d1a841866c65f2a650'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `record_planning_status` (call_id=`call_EQeZ6ivp9FhAzGMkA7ZH2eie`):
```text
recorded
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_02f4e5a07ea17168006abe72af8c0087d1a841866c65f2a650'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24959 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:48 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>54. [2026-10-01 17:48:23] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_02f4e5a07ea17168006abe72b5e35087d1bf3784af5c7a3ba1`
- status: `completed`
- usage: `{"input_tokens": 9160, "input_tokens_details": {"cache_write_tokens": 282, "cached_tokens": 8875}, "output_tokens": 24, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9184}`
- function_call: `react_to_message` call_id=`call_P58c5JdU5Ljy5Ip8BIQ0T0mQ`
```json
{
  "emoji": "✅",
  "message_id": null
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_02f4e5a07ea17168006abe72b5e35087d1bf3784af5c7a3ba1`
- status: `completed`
- usage: `{"input_tokens": 9160, "input_tokens_details": {"cache_write_tokens": 282, "cached_tokens": 8875}, "output_tokens": 24, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9184}`
- function_call: `react_to_message` call_id=`call_P58c5JdU5Ljy5Ip8BIQ0T0mQ`
```json
{
  "emoji": "✅",
  "message_id": null
}
```

</details>

</details>

<details>
<summary>55. [2026-10-01 17:48:23] APP → USER — context=reaction — ✅ — NOT SENT (no WhatsApp bot in this run)</summary>

```text
[084] react_to_message call 'call_P58c5JdU5Ljy5Ip8BIQ0T0mQ': nothing to react through (target_id='stage1b-4_APPROVE_A1_1790866086', chat_id='+972501234567@c.us', green_api_bot_set=False)
```

</details>

<details>
<summary>56. [2026-10-01 17:48:23] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `react_to_message` (call_id=`call_P58c5JdU5Ljy5Ip8BIQ0T0mQ`):
```text
{
  "status": "failed"
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_02f4e5a07ea17168006abe72b5e35087d1bf3784af5c7a3ba1'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `react_to_message` (call_id=`call_P58c5JdU5Ljy5Ip8BIQ0T0mQ`):
```text
{
  "status": "failed"
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_02f4e5a07ea17168006abe72b5e35087d1bf3784af5c7a3ba1'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24959 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:48 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>57. [2026-10-01 17:48:25] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_02f4e5a07ea17168006abe72b7b79487d19473f0f207fe6501`
- status: `completed`
- usage: `{"input_tokens": 9202, "input_tokens_details": {"cache_write_tokens": 42, "cached_tokens": 9157}, "output_tokens": 58, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9260}`
- function_call: `send_to_user` call_id=`call_ltqNMvnAm5yAHirUhrYs8SQB`
```json
{
  "text": "הלקוחה ג'סיקה סוקולוביץ' נוספה בהצלחה.\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_02f4e5a07ea17168006abe72b7b79487d19473f0f207fe6501`
- status: `completed`
- usage: `{"input_tokens": 9202, "input_tokens_details": {"cache_write_tokens": 42, "cached_tokens": 9157}, "output_tokens": 58, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9260}`
- function_call: `send_to_user` call_id=`call_ltqNMvnAm5yAHirUhrYs8SQB`
```json
{
  "text": "הלקוחה ג'סיקה סוקולוביץ' נוספה בהצלחה.\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567"
}
```

</details>

</details>

<details>
<summary>58. [2026-10-01 17:48:25] APP → USER — context=text</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "הלקוחה ג'סיקה סוקולוביץ' נוספה בהצלחה.\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "הלקוחה ג'סיקה סוקולוביץ' נוספה בהצלחה.\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567"
}
```

</details>

</details>

<details>
<summary>59. [2026-10-01 17:48:28] USER → APP — context=webhook</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "typeWebhook": "incomingMessageReceived",
  "idMessage": "billed_stage1b-4_67240bd0",
  "senderData": {
    "chatId": "+972501234567@c.us",
    "sender": "+972501234567",
    "senderName": "Test Godfather"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {
      "textMessage": "תכין הסכם עבור ג'סיקה סוקולוביץ', בתביעה כספית נגד שכנו. שכר הטרחה: הגשת התביעה - 5,000 ש\"ח כולל מע\"מ; דיון הוכחות אם יידרש - 4,000 ש\"ח כולל מע\"מ; ניהול ההליך עד להחלטה - 8,000 ש\"ח כולל מע\"מ; ערעור אם יוגש - 6,000 ש\"ח כולל מע\"מ."
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
  "idMessage": "billed_stage1b-4_67240bd0",
  "senderData": {
    "chatId": "+972501234567@c.us",
    "sender": "+972501234567",
    "senderName": "Test Godfather"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {
      "textMessage": "תכין הסכם עבור ג'סיקה סוקולוביץ', בתביעה כספית נגד שכנו. שכר הטרחה: הגשת התביעה - 5,000 ש\"ח כולל מע\"מ; דיון הוכחות אם יידרש - 4,000 ש\"ח כולל מע\"מ; ניהול ההליך עד להחלטה - 8,000 ש\"ח כולל מע\"מ; ערעור אם יוגש - 6,000 ש\"ח כולל מע\"מ."
    }
  }
}
```

</details>

</details>

<details>
<summary>60. [2026-10-01 17:48:29] APP → MODEL — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

```json
{"role": "user", "content": "תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"}
```
```json
{"role": "assistant", "content": "בודק אם הלקוחה כבר קיימת לפני יצירת הרשומה."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: התחלת טיפול בבקשה להוספת לקוחה חדשה.\nTHIS TURN'S PURPOSE: לבדוק כפילויות, לאסוף את פרטי הלקוחה, לקבל אישור וליצור את הרשומה.\nEXPECTATION: אטעין את תהליך הוספת הלקוח ואת יכולות חיפוש וכתיבה, ואז אבקש אישור לפני היצירה."}
```
```json
{"role": "assistant", "content": "טוען את כלי הבדיקה הנדרשים."}
```
```json
{"role": "assistant", "content": "מחפש לקוחה קיימת או דומה בשם שסיפקת."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך הוספת לקוחה חדשה. חיפוש במערכת הסתיים ללא לקוחות קיימים או דומים בשם ג'סיקה סוקולוביץ'. הפרטים המלאים זמינים.\nTHIS TURN'S PURPOSE: לבקש אישור מפורש ליצירת הלקוחה החדשה.\nEXPECTATION: לאחר תשובה חיובית אצור את הרשומה; לאחר תשובה שלילית לא אבצע יצירה ואבקש מה לשנות."}
```
```json
{"role": "assistant", "content": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"}
```
```json
{"role": "user", "content": "לא, תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך הוספת לקוחה חדשה, והאישור הקודם נדחה. המשתמש חזר על בקשת ההוספה עם אותם פרטים.\nTHIS TURN'S PURPOSE: לוודא אם זו בקשה חדשה לאישור או ביטול של היצירה.\nEXPECTATION: אבקש אישור מפורש מחדש, בלי ליצור את הרשומה לפני תשובה חיובית."}
```
```json
{"role": "assistant", "content": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"}
```
```json
{"role": "user", "content": "כן"}
```
```json
{"role": "assistant", "content": "מבצע עכשיו את יצירת הלקוחה במערכת."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: תהליך הוספת הלקוחה הושלם לאחר אישור מפורש. הרשומה נוצרה בהצלחה במערכת.\nTHIS TURN'S PURPOSE: לדווח למשתמש על הצלחת יצירת הלקוחה.\nEXPECTATION: אין פעולה נוספת נדרשת עבור בקשה זו."}
```
```json
{"role": "assistant", "content": "הלקוחה ג'סיקה סוקולוביץ' נוספה בהצלחה.\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567"}
```
```json
{"role": "user", "content": "תכין הסכם עבור ג'סיקה סוקולוביץ', בתביעה כספית נגד שכנו. שכר הטרחה: הגשת התביעה - 5,000 ש\"ח כולל מע\"מ; דיון הוכחות אם יידרש - 4,000 ש\"ח כולל מע\"מ; ניהול ההליך עד להחלטה - 8,000 ש\"ח כולל מע\"מ; ערעור אם יוגש - 6,000 ש\"ח כולל מע\"מ."}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

```json
{"role": "user", "content": "תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"}
```
```json
{"role": "assistant", "content": "בודק אם הלקוחה כבר קיימת לפני יצירת הרשומה."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: התחלת טיפול בבקשה להוספת לקוחה חדשה.\nTHIS TURN'S PURPOSE: לבדוק כפילויות, לאסוף את פרטי הלקוחה, לקבל אישור וליצור את הרשומה.\nEXPECTATION: אטעין את תהליך הוספת הלקוח ואת יכולות חיפוש וכתיבה, ואז אבקש אישור לפני היצירה."}
```
```json
{"role": "assistant", "content": "טוען את כלי הבדיקה הנדרשים."}
```
```json
{"role": "assistant", "content": "מחפש לקוחה קיימת או דומה בשם שסיפקת."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך הוספת לקוחה חדשה. חיפוש במערכת הסתיים ללא לקוחות קיימים או דומים בשם ג'סיקה סוקולוביץ'. הפרטים המלאים זמינים.\nTHIS TURN'S PURPOSE: לבקש אישור מפורש ליצירת הלקוחה החדשה.\nEXPECTATION: לאחר תשובה חיובית אצור את הרשומה; לאחר תשובה שלילית לא אבצע יצירה ואבקש מה לשנות."}
```
```json
{"role": "assistant", "content": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"}
```
```json
{"role": "user", "content": "לא, תוסיף לקוח חדש בשם ג'סיקה סוקולוביץ', מייל e2e-client-545352@example.com, טלפון 050-1234567"}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך הוספת לקוחה חדשה, והאישור הקודם נדחה. המשתמש חזר על בקשת ההוספה עם אותם פרטים.\nTHIS TURN'S PURPOSE: לוודא אם זו בקשה חדשה לאישור או ביטול של היצירה.\nEXPECTATION: אבקש אישור מפורש מחדש, בלי ליצור את הרשומה לפני תשובה חיובית."}
```
```json
{"role": "assistant", "content": "📋 לאישור — לקוחה חדשה:\nשם: ג'סיקה סוקולוביץ'\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567\nלאישור — כן/לא?"}
```
```json
{"role": "user", "content": "כן"}
```
```json
{"role": "assistant", "content": "מבצע עכשיו את יצירת הלקוחה במערכת."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: תהליך הוספת הלקוחה הושלם לאחר אישור מפורש. הרשומה נוצרה בהצלחה במערכת.\nTHIS TURN'S PURPOSE: לדווח למשתמש על הצלחת יצירת הלקוחה.\nEXPECTATION: אין פעולה נוספת נדרשת עבור בקשה זו."}
```
```json
{"role": "assistant", "content": "הלקוחה ג'סיקה סוקולוביץ' נוספה בהצלחה.\nמייל: e2e-client-545352@example.com\nטלפון: 050-1234567"}
```
```json
{"role": "user", "content": "תכין הסכם עבור ג'סיקה סוקולוביץ', בתביעה כספית נגד שכנו. שכר הטרחה: הגשת התביעה - 5,000 ש\"ח כולל מע\"מ; דיון הוכחות אם יידרש - 4,000 ש\"ח כולל מע\"מ; ניהול ההליך עד להחלטה - 8,000 ש\"ח כולל מע\"מ; ערעור אם יוגש - 6,000 ש\"ח כולל מע\"מ."}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24959 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:48 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>61. [2026-10-01 17:48:35] MODEL → APP — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72bdd0cc87d182bac82cc2715a8a`
- status: `completed`
- usage: `{"input_tokens": 8897, "input_tokens_details": {"cache_write_tokens": 251, "cached_tokens": 8643}, "output_tokens": 79, "output_tokens_details": {"reasoning_tokens": 51}, "total_tokens": 8976}`
- mcp_list_tools (morning-invoices-client-read): ['list_clients', 'resolve_client_name', 'get_client_details']
- mcp_list_tools (morning-invoices-client-write): ['add_client', 'update_client']
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_X2Tg5U8D1pEb0zA2NttnXfwy`
```json
{
  "emoji": "🫡",
  "message_id": null
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72bdd0cc87d182bac82cc2715a8a`
- status: `completed`
- usage: `{"input_tokens": 8897, "input_tokens_details": {"cache_write_tokens": 251, "cached_tokens": 8643}, "output_tokens": 79, "output_tokens_details": {"reasoning_tokens": 51}, "total_tokens": 8976}`
- mcp_list_tools (morning-invoices-client-read): ['list_clients', 'resolve_client_name', 'get_client_details']
- mcp_list_tools (morning-invoices-client-write): ['add_client', 'update_client']
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_X2Tg5U8D1pEb0zA2NttnXfwy`
```json
{
  "emoji": "🫡",
  "message_id": null
}
```

</details>

</details>

<details>
<summary>62. [2026-10-01 17:48:35] APP → USER — context=reaction — 🫡 — NOT SENT (no WhatsApp bot in this run)</summary>

```text
[084] react_to_message call 'call_X2Tg5U8D1pEb0zA2NttnXfwy': nothing to react through (target_id='billed_stage1b-4_67240bd0', chat_id='+972501234567@c.us', green_api_bot_set=False)
```

</details>

<details>
<summary>63. [2026-10-01 17:48:35] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `react_to_message` (call_id=`call_X2Tg5U8D1pEb0zA2NttnXfwy`):
```text
{
  "status": "failed"
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72bdd0cc87d182bac82cc2715a8a'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `react_to_message` (call_id=`call_X2Tg5U8D1pEb0zA2NttnXfwy`):
```text
{
  "status": "failed"
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72bdd0cc87d182bac82cc2715a8a'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24959 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:48 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>64. [2026-10-01 17:48:38] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72c40ed887d181f7b54679b38975`
- status: `completed`
- usage: `{"input_tokens": 8994, "input_tokens_details": {"cache_write_tokens": 97, "cached_tokens": 8894}, "output_tokens": 70, "output_tokens_details": {"reasoning_tokens": 28}, "total_tokens": 9064}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_xyRHAdRsVhDsfrXwYtS2y47U`
```json
{
  "text": "מכין את טיוטת הסכם שכר הטרחה לפי הפרטים שמסרת."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72c40ed887d181f7b54679b38975`
- status: `completed`
- usage: `{"input_tokens": 8994, "input_tokens_details": {"cache_write_tokens": 97, "cached_tokens": 8894}, "output_tokens": 70, "output_tokens_details": {"reasoning_tokens": 28}, "total_tokens": 9064}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_xyRHAdRsVhDsfrXwYtS2y47U`
```json
{
  "text": "מכין את טיוטת הסכם שכר הטרחה לפי הפרטים שמסרת."
}
```

</details>

</details>

<details>
<summary>65. [2026-10-01 17:48:38] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "מכין את טיוטת הסכם שכר הטרחה לפי הפרטים שמסרת."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "מכין את טיוטת הסכם שכר הטרחה לפי הפרטים שמסרת."
}
```

</details>

</details>

<details>
<summary>66. [2026-10-01 17:48:38] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
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
<summary>67. [2026-10-01 17:48:38] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `send_progress_update` (call_id=`call_xyRHAdRsVhDsfrXwYtS2y47U`):
```text
{
  "sent": true
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72c40ed887d181f7b54679b38975'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `send_progress_update` (call_id=`call_xyRHAdRsVhDsfrXwYtS2y47U`):
```text
{
  "sent": true
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72c40ed887d181f7b54679b38975'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24959 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:48 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>68. [2026-10-01 17:48:42] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72c6ec0087d1860e981127011538`
- status: `completed`
- usage: `{"input_tokens": 9083, "input_tokens_details": {"cache_write_tokens": 1005, "cached_tokens": 8075}, "output_tokens": 149, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9232}`
- function_call: `record_planning_status` call_id=`call_KmFe3w9GHG6B2bLNyRdkayXk`
```json
{
  "where_i_was": "המשתמש ביקש להכין הסכם שכר טרחה עבור ג'סיקה סוקולוביץ' בתביעה כספית נגד שכנו, עם ארבעה רכיבי שכר טרחה.",
  "this_turns_purpose": "להפעיל את תהליך יצירת הסכם שכר הטרחה, להכין את המסמך ולבקש אישור לפני יצירתו או שליחתו לפי התהליך.",
  "expectation": "אטען את תהליך יצירת ההסכם ואת יכולת יצירת מסמכי וורד, ואז אפעל לפי שלבי איסוף הפרטים והאישור."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72c6ec0087d1860e981127011538`
- status: `completed`
- usage: `{"input_tokens": 9083, "input_tokens_details": {"cache_write_tokens": 1005, "cached_tokens": 8075}, "output_tokens": 149, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9232}`
- function_call: `record_planning_status` call_id=`call_KmFe3w9GHG6B2bLNyRdkayXk`
```json
{
  "where_i_was": "המשתמש ביקש להכין הסכם שכר טרחה עבור ג'סיקה סוקולוביץ' בתביעה כספית נגד שכנו, עם ארבעה רכיבי שכר טרחה.",
  "this_turns_purpose": "להפעיל את תהליך יצירת הסכם שכר הטרחה, להכין את המסמך ולבקש אישור לפני יצירתו או שליחתו לפי התהליך.",
  "expectation": "אטען את תהליך יצירת ההסכם ואת יכולת יצירת מסמכי וורד, ואז אפעל לפי שלבי איסוף הפרטים והאישור."
}
```

</details>

</details>

<details>
<summary>69. [2026-10-01 17:48:42] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `record_planning_status` (call_id=`call_KmFe3w9GHG6B2bLNyRdkayXk`):
```text
recorded
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72c6ec0087d1860e981127011538'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `record_planning_status` (call_id=`call_KmFe3w9GHG6B2bLNyRdkayXk`):
```text
recorded
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72c6ec0087d1860e981127011538'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24959 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:48 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>70. [2026-10-01 17:48:44] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72caa96c87d19eb51f49448df3d5`
- status: `completed`
- usage: `{"input_tokens": 9247, "input_tokens_details": {"cache_write_tokens": 164, "cached_tokens": 9080}, "output_tokens": 47, "output_tokens_details": {"reasoning_tokens": 13}, "total_tokens": 9294}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_iKmjmXkCIquI5ufC61oQpdiv`
```json
{
  "text": "טוען את כלי יצירת ההסכם והמסמך."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72caa96c87d19eb51f49448df3d5`
- status: `completed`
- usage: `{"input_tokens": 9247, "input_tokens_details": {"cache_write_tokens": 164, "cached_tokens": 9080}, "output_tokens": 47, "output_tokens_details": {"reasoning_tokens": 13}, "total_tokens": 9294}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_iKmjmXkCIquI5ufC61oQpdiv`
```json
{
  "text": "טוען את כלי יצירת ההסכם והמסמך."
}
```

</details>

</details>

<details>
<summary>71. [2026-10-01 17:48:44] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "טוען את כלי יצירת ההסכם והמסמך."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "טוען את כלי יצירת ההסכם והמסמך."
}
```

</details>

</details>

<details>
<summary>72. [2026-10-01 17:48:44] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
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
<summary>73. [2026-10-01 17:48:44] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `send_progress_update` (call_id=`call_iKmjmXkCIquI5ufC61oQpdiv`):
```text
{
  "sent": true
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72caa96c87d19eb51f49448df3d5'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `send_progress_update` (call_id=`call_iKmjmXkCIquI5ufC61oQpdiv`):
```text
{
  "sent": true
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72caa96c87d19eb51f49448df3d5'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24959 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:48 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>74. [2026-10-01 17:48:47] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72cd27a487d1a8097a2e8b059699`
- status: `completed`
- usage: `{"input_tokens": 9311, "input_tokens_details": {"cache_write_tokens": 64, "cached_tokens": 9244}, "output_tokens": 26, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9337}`
- function_call: `load_flows` call_id=`call_dy5GHKsAIWBuuFYyU073Ah9X`
```json
{
  "flows": [
    "flow_generate_fee_agreement_docx"
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72cd27a487d1a8097a2e8b059699`
- status: `completed`
- usage: `{"input_tokens": 9311, "input_tokens_details": {"cache_write_tokens": 64, "cached_tokens": 9244}, "output_tokens": 26, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9337}`
- function_call: `load_flows` call_id=`call_dy5GHKsAIWBuuFYyU073Ah9X`
```json
{
  "flows": [
    "flow_generate_fee_agreement_docx"
  ]
}
```

</details>

</details>

<details>
<summary>75. [2026-10-01 17:48:47] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client, flow_generate_fee_agreement_docx

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `load_flows` (call_id=`call_dy5GHKsAIWBuuFYyU073Ah9X`):
```text
loaded flows: flow_generate_fee_agreement_docx. Loaded flows now: flow_add_client, flow_generate_fee_agreement_docx. Loaded capabilities now: cap_client_read, cap_client_write, cap_approval_with_buttons. Their blueprint text is attached starting now.
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72cd27a487d1a8097a2e8b059699'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, flow_generate_fee_agreement_docx, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client, flow_generate_fee_agreement_docx

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `load_flows` (call_id=`call_dy5GHKsAIWBuuFYyU073Ah9X`):
```text
loaded flows: flow_generate_fee_agreement_docx. Loaded flows now: flow_add_client, flow_generate_fee_agreement_docx. Loaded capabilities now: cap_client_read, cap_client_write, cap_approval_with_buttons. Their blueprint text is attached starting now.
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72cd27a487d1a8097a2e8b059699'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (26010 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Flow: Generate fee agreement docx

Goal: compose a fee agreement (הסכם שכר טרחה) for the user and send it as a .docx file. It is a pre-signing document, so no client needs to exist.

Capabilities: `cap_docx_write`.

Follow these steps in order, to the letter.

1. Load `cap_docx_write`. Gather what the agreement needs from the user. Anything they did not state is something to ask about with `cap_send_to_user`, one question at a time; never invent a financial or legal term.
2. Compose, check and send the document as `cap_docx_write` directs. This flow needs no approval step and no client lookup.
3. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_docx_write` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client, flow_generate_fee_agreement_docx

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:48 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>76. [2026-10-01 17:48:49] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72cffcec87d1bd2069c3b81ac2ca`
- status: `completed`
- usage: `{"input_tokens": 9654, "input_tokens_details": {"cache_write_tokens": 9651, "cached_tokens": 0}, "output_tokens": 45, "output_tokens_details": {"reasoning_tokens": 10}, "total_tokens": 9699}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_kN3k4JYBIdyifMBD7SNKlKsy`
```json
{
  "text": "טוען את יכולת יצירת קובץ ההסכם."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72cffcec87d1bd2069c3b81ac2ca`
- status: `completed`
- usage: `{"input_tokens": 9654, "input_tokens_details": {"cache_write_tokens": 9651, "cached_tokens": 0}, "output_tokens": 45, "output_tokens_details": {"reasoning_tokens": 10}, "total_tokens": 9699}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_kN3k4JYBIdyifMBD7SNKlKsy`
```json
{
  "text": "טוען את יכולת יצירת קובץ ההסכם."
}
```

</details>

</details>

<details>
<summary>77. [2026-10-01 17:48:49] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "טוען את יכולת יצירת קובץ ההסכם."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "טוען את יכולת יצירת קובץ ההסכם."
}
```

</details>

</details>

<details>
<summary>78. [2026-10-01 17:48:49] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
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
<summary>79. [2026-10-01 17:48:49] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client, flow_generate_fee_agreement_docx

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `send_progress_update` (call_id=`call_kN3k4JYBIdyifMBD7SNKlKsy`):
```text
{
  "sent": true
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72cffcec87d1bd2069c3b81ac2ca'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, flow_generate_fee_agreement_docx, capabilities=cap_client_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client, flow_generate_fee_agreement_docx

- capabilities: cap_client_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `send_progress_update` (call_id=`call_kN3k4JYBIdyifMBD7SNKlKsy`):
```text
{
  "sent": true
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72cffcec87d1bd2069c3b81ac2ca'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (26010 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Flow: Generate fee agreement docx

Goal: compose a fee agreement (הסכם שכר טרחה) for the user and send it as a .docx file. It is a pre-signing document, so no client needs to exist.

Capabilities: `cap_docx_write`.

Follow these steps in order, to the letter.

1. Load `cap_docx_write`. Gather what the agreement needs from the user. Anything they did not state is something to ask about with `cap_send_to_user`, one question at a time; never invent a financial or legal term.
2. Compose, check and send the document as `cap_docx_write` directs. This flow needs no approval step and no client lookup.
3. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_docx_write` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client, flow_generate_fee_agreement_docx

## Loaded capabilities

cap_client_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:48 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>80. [2026-10-01 17:48:52] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72d2356487d1b962d45c2423dadc`
- status: `completed`
- usage: `{"input_tokens": 9716, "input_tokens_details": {"cache_write_tokens": 62, "cached_tokens": 9651}, "output_tokens": 24, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9740}`
- function_call: `load_capabilities` call_id=`call_xMa4cQcCKLdxcKJbD4m68Uk8`
```json
{
  "capabilities": [
    "cap_docx_write"
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72d2356487d1b962d45c2423dadc`
- status: `completed`
- usage: `{"input_tokens": 9716, "input_tokens_details": {"cache_write_tokens": 62, "cached_tokens": 9651}, "output_tokens": 24, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9740}`
- function_call: `load_capabilities` call_id=`call_xMa4cQcCKLdxcKJbD4m68Uk8`
```json
{
  "capabilities": [
    "cap_docx_write"
  ]
}
```

</details>

</details>

<details>
<summary>81. [2026-10-01 17:48:52] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client, flow_generate_fee_agreement_docx

- capabilities: cap_client_write, cap_client_read, cap_docx_write, cap_approval_with_buttons

**input:**

- app's reply to `load_capabilities` (call_id=`call_xMa4cQcCKLdxcKJbD4m68Uk8`):
```text
loaded capabilitys: cap_docx_write. Loaded flows now: flow_add_client, flow_generate_fee_agreement_docx. Loaded capabilities now: cap_client_read, cap_client_write, cap_approval_with_buttons, cap_docx_write. Their instructions and tools are attached starting now.
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72d2356487d1b962d45c2423dadc'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, flow_generate_fee_agreement_docx, capabilities=cap_client_write, cap_client_read, cap_docx_write, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client, flow_generate_fee_agreement_docx

- capabilities: cap_client_write, cap_client_read, cap_docx_write, cap_approval_with_buttons

**input:**

- app's reply to `load_capabilities` (call_id=`call_xMa4cQcCKLdxcKJbD4m68Uk8`):
```text
loaded capabilitys: cap_docx_write. Loaded flows now: flow_add_client, flow_generate_fee_agreement_docx. Loaded capabilities now: cap_client_read, cap_client_write, cap_approval_with_buttons, cap_docx_write. Their instructions and tools are attached starting now.
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72d2356487d1b962d45c2423dadc'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (27674 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Flow: Generate fee agreement docx

Goal: compose a fee agreement (הסכם שכר טרחה) for the user and send it as a .docx file. It is a pre-signing document, so no client needs to exist.

Capabilities: `cap_docx_write`.

Follow these steps in order, to the letter.

1. Load `cap_docx_write`. Gather what the agreement needs from the user. Anything they did not state is something to ask about with `cap_send_to_user`, one question at a time; never invent a financial or legal term.
2. Compose, check and send the document as `cap_docx_write` directs. This flow needs no approval step and no client lookup.
3. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_docx_write` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


# Capability: Docx Write — Fee Agreement Documents (godfather/admin only)

**Use this capability from within a flow (flow_generate_fee_agreement_docx), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

Composing and sending a fee agreement document (הסכם שכר טרחה) as a .docx file over
WhatsApp. It is a pre-signing document, so there may be no client record for it yet.

## How it works
This capability gives you four tools: `get_fee_agreement_template`,
`render_fee_agreement_document`, `verify_fee_agreement_document`, and
`send_fee_agreement_document`. You are the document's actual author — the
firm's letterhead (logo/header/footer, title, date, signature block) is
applied automatically by code; you write only the substantive body: scope of
work, every fee/payment clause, any conditions.

Typical flow: `get_fee_agreement_template` (classify which variant fits, per
its own selection guide) → compose the full body text yourself → `render_...`
→ `verify_...` (read back the real facts — you still judge whether it's
correct/complete/one-page) → revise and re-render if needed → `send_...` once
you're satisfied. No human approval step on any of these four — your own
verification is the sole gate.

## Never
- Never invent, guess, or default a financial or legal detail the human did
  not explicitly give you — ask instead.
- Never leave a literal `{{...}}`-shaped placeholder token in what you send.
- Never call `send_fee_agreement_document` before a clean
  `verify_fee_agreement_document` result on the same document_id.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client, flow_generate_fee_agreement_docx

## Loaded capabilities

cap_client_write, cap_client_read, cap_docx_write, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:48 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>82. [2026-10-01 17:48:54] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72d495f087d18b0665815d832220`
- status: `completed`
- usage: `{"input_tokens": 10203, "input_tokens_details": {"cache_write_tokens": 10200, "cached_tokens": 0}, "output_tokens": 72, "output_tokens_details": {"reasoning_tokens": 35}, "total_tokens": 10275}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_HgOmpIOIQ7QF4adu1RaptfmC`
```json
{
  "text": "בודק את תבנית ההסכם המתאימה לפני ניסוחו."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72d495f087d18b0665815d832220`
- status: `completed`
- usage: `{"input_tokens": 10203, "input_tokens_details": {"cache_write_tokens": 10200, "cached_tokens": 0}, "output_tokens": 72, "output_tokens_details": {"reasoning_tokens": 35}, "total_tokens": 10275}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_HgOmpIOIQ7QF4adu1RaptfmC`
```json
{
  "text": "בודק את תבנית ההסכם המתאימה לפני ניסוחו."
}
```

</details>

</details>

<details>
<summary>83. [2026-10-01 17:48:54] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "בודק את תבנית ההסכם המתאימה לפני ניסוחו."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "בודק את תבנית ההסכם המתאימה לפני ניסוחו."
}
```

</details>

</details>

<details>
<summary>84. [2026-10-01 17:48:54] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
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
<summary>85. [2026-10-01 17:48:54] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client, flow_generate_fee_agreement_docx

- capabilities: cap_client_write, cap_client_read, cap_docx_write, cap_approval_with_buttons

**input:**

- app's reply to `send_progress_update` (call_id=`call_HgOmpIOIQ7QF4adu1RaptfmC`):
```text
{
  "sent": true
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72d495f087d18b0665815d832220'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, flow_generate_fee_agreement_docx, capabilities=cap_client_write, cap_client_read, cap_docx_write, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client, flow_generate_fee_agreement_docx

- capabilities: cap_client_write, cap_client_read, cap_docx_write, cap_approval_with_buttons

**input:**

- app's reply to `send_progress_update` (call_id=`call_HgOmpIOIQ7QF4adu1RaptfmC`):
```text
{
  "sent": true
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72d495f087d18b0665815d832220'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (27674 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Flow: Generate fee agreement docx

Goal: compose a fee agreement (הסכם שכר טרחה) for the user and send it as a .docx file. It is a pre-signing document, so no client needs to exist.

Capabilities: `cap_docx_write`.

Follow these steps in order, to the letter.

1. Load `cap_docx_write`. Gather what the agreement needs from the user. Anything they did not state is something to ask about with `cap_send_to_user`, one question at a time; never invent a financial or legal term.
2. Compose, check and send the document as `cap_docx_write` directs. This flow needs no approval step and no client lookup.
3. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_docx_write` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


# Capability: Docx Write — Fee Agreement Documents (godfather/admin only)

**Use this capability from within a flow (flow_generate_fee_agreement_docx), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

Composing and sending a fee agreement document (הסכם שכר טרחה) as a .docx file over
WhatsApp. It is a pre-signing document, so there may be no client record for it yet.

## How it works
This capability gives you four tools: `get_fee_agreement_template`,
`render_fee_agreement_document`, `verify_fee_agreement_document`, and
`send_fee_agreement_document`. You are the document's actual author — the
firm's letterhead (logo/header/footer, title, date, signature block) is
applied automatically by code; you write only the substantive body: scope of
work, every fee/payment clause, any conditions.

Typical flow: `get_fee_agreement_template` (classify which variant fits, per
its own selection guide) → compose the full body text yourself → `render_...`
→ `verify_...` (read back the real facts — you still judge whether it's
correct/complete/one-page) → revise and re-render if needed → `send_...` once
you're satisfied. No human approval step on any of these four — your own
verification is the sole gate.

## Never
- Never invent, guess, or default a financial or legal detail the human did
  not explicitly give you — ask instead.
- Never leave a literal `{{...}}`-shaped placeholder token in what you send.
- Never call `send_fee_agreement_document` before a clean
  `verify_fee_agreement_document` result on the same document_id.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client, flow_generate_fee_agreement_docx

## Loaded capabilities

cap_client_write, cap_client_read, cap_docx_write, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:48 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>86. [2026-10-01 17:48:57] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72d707ec87d19778b2d24efc70be`
- status: `completed`
- usage: `{"input_tokens": 10292, "input_tokens_details": {"cache_write_tokens": 89, "cached_tokens": 10200}, "output_tokens": 132, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 10424}`
- function_call: `record_planning_status` call_id=`call_3feZ1KUTiVn4OXme9rKLvzZk`
```json
{
  "where_i_was": "בתהליך יצירת הסכם שכר הטרחה, לאחר טעינת היכולת המתאימה. הפרטים הכספיים והיקף ההליך נמסרו.",
  "this_turns_purpose": "לבחור תבנית מתאימה ולבדוק אם חסר פרט מהותי לפני ניסוח המסמך.",
  "expectation": "אקבל את הנחיות התבנית, אנוסח את גוף ההסכם ללא המצאת תנאים משפטיים או כספיים, ואבקש רק פרטים שחסרים באמת."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72d707ec87d19778b2d24efc70be`
- status: `completed`
- usage: `{"input_tokens": 10292, "input_tokens_details": {"cache_write_tokens": 89, "cached_tokens": 10200}, "output_tokens": 132, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 10424}`
- function_call: `record_planning_status` call_id=`call_3feZ1KUTiVn4OXme9rKLvzZk`
```json
{
  "where_i_was": "בתהליך יצירת הסכם שכר הטרחה, לאחר טעינת היכולת המתאימה. הפרטים הכספיים והיקף ההליך נמסרו.",
  "this_turns_purpose": "לבחור תבנית מתאימה ולבדוק אם חסר פרט מהותי לפני ניסוח המסמך.",
  "expectation": "אקבל את הנחיות התבנית, אנוסח את גוף ההסכם ללא המצאת תנאים משפטיים או כספיים, ואבקש רק פרטים שחסרים באמת."
}
```

</details>

</details>

<details>
<summary>87. [2026-10-01 17:48:57] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client, flow_generate_fee_agreement_docx

- capabilities: cap_client_write, cap_client_read, cap_docx_write, cap_approval_with_buttons

**input:**

- app's reply to `record_planning_status` (call_id=`call_3feZ1KUTiVn4OXme9rKLvzZk`):
```text
recorded
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72d707ec87d19778b2d24efc70be'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, flow_generate_fee_agreement_docx, capabilities=cap_client_write, cap_client_read, cap_docx_write, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client, flow_generate_fee_agreement_docx

- capabilities: cap_client_write, cap_client_read, cap_docx_write, cap_approval_with_buttons

**input:**

- app's reply to `record_planning_status` (call_id=`call_3feZ1KUTiVn4OXme9rKLvzZk`):
```text
recorded
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72d707ec87d19778b2d24efc70be'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (27674 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Flow: Generate fee agreement docx

Goal: compose a fee agreement (הסכם שכר טרחה) for the user and send it as a .docx file. It is a pre-signing document, so no client needs to exist.

Capabilities: `cap_docx_write`.

Follow these steps in order, to the letter.

1. Load `cap_docx_write`. Gather what the agreement needs from the user. Anything they did not state is something to ask about with `cap_send_to_user`, one question at a time; never invent a financial or legal term.
2. Compose, check and send the document as `cap_docx_write` directs. This flow needs no approval step and no client lookup.
3. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_docx_write` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


# Capability: Docx Write — Fee Agreement Documents (godfather/admin only)

**Use this capability from within a flow (flow_generate_fee_agreement_docx), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

Composing and sending a fee agreement document (הסכם שכר טרחה) as a .docx file over
WhatsApp. It is a pre-signing document, so there may be no client record for it yet.

## How it works
This capability gives you four tools: `get_fee_agreement_template`,
`render_fee_agreement_document`, `verify_fee_agreement_document`, and
`send_fee_agreement_document`. You are the document's actual author — the
firm's letterhead (logo/header/footer, title, date, signature block) is
applied automatically by code; you write only the substantive body: scope of
work, every fee/payment clause, any conditions.

Typical flow: `get_fee_agreement_template` (classify which variant fits, per
its own selection guide) → compose the full body text yourself → `render_...`
→ `verify_...` (read back the real facts — you still judge whether it's
correct/complete/one-page) → revise and re-render if needed → `send_...` once
you're satisfied. No human approval step on any of these four — your own
verification is the sole gate.

## Never
- Never invent, guess, or default a financial or legal detail the human did
  not explicitly give you — ask instead.
- Never leave a literal `{{...}}`-shaped placeholder token in what you send.
- Never call `send_fee_agreement_document` before a clean
  `verify_fee_agreement_document` result on the same document_id.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client, flow_generate_fee_agreement_docx

## Loaded capabilities

cap_client_write, cap_client_read, cap_docx_write, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:48 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>88. [2026-10-01 17:49:03] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72d9c59887d1a128ba59421f0831`
- status: `completed`
- usage: `{"input_tokens": 10437, "input_tokens_details": {"cache_write_tokens": 10434, "cached_tokens": 0}, "output_tokens": 247, "output_tokens_details": {"reasoning_tokens": 220}, "total_tokens": 10684}`
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_z8rikVBcoB9wpI7H7imuHhUD`
```json
{
  "emoji": "❓",
  "message_id": null
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72d9c59887d1a128ba59421f0831`
- status: `completed`
- usage: `{"input_tokens": 10437, "input_tokens_details": {"cache_write_tokens": 10434, "cached_tokens": 0}, "output_tokens": 247, "output_tokens_details": {"reasoning_tokens": 220}, "total_tokens": 10684}`
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_z8rikVBcoB9wpI7H7imuHhUD`
```json
{
  "emoji": "❓",
  "message_id": null
}
```

</details>

</details>

<details>
<summary>89. [2026-10-01 17:49:03] APP → USER — context=reaction — ❓ — NOT SENT (no WhatsApp bot in this run)</summary>

```text
[084] react_to_message call 'call_z8rikVBcoB9wpI7H7imuHhUD': nothing to react through (target_id='billed_stage1b-4_67240bd0', chat_id='+972501234567@c.us', green_api_bot_set=False)
```

</details>

<details>
<summary>90. [2026-10-01 17:49:03] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_add_client, flow_generate_fee_agreement_docx

- capabilities: cap_client_write, cap_client_read, cap_docx_write, cap_approval_with_buttons

**input:**

- app's reply to `react_to_message` (call_id=`call_z8rikVBcoB9wpI7H7imuHhUD`):
```text
{
  "status": "failed"
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72d9c59887d1a128ba59421f0831'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_add_client, flow_generate_fee_agreement_docx, capabilities=cap_client_write, cap_client_read, cap_docx_write, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_add_client, flow_generate_fee_agreement_docx

- capabilities: cap_client_write, cap_client_read, cap_docx_write, cap_approval_with_buttons

**input:**

- app's reply to `react_to_message` (call_id=`call_z8rikVBcoB9wpI7H7imuHhUD`):
```text
{
  "status": "failed"
}
```

- tools (12): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp', 'mcp']

- previous_response_id: `'resp_0bbf0c1a4a6cf8d7006abe72d9c59887d1a128ba59421f0831'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (27674 chars)</summary>

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
4. If a loaded prompt names a tool you don't currently have, that tool belongs
   to a capability you have not loaded yet: load it yourself.

## Core Identity
You are DeniDin, a helpful AI assistant operating via WhatsApp.

## Behavioral Guidelines
- **ALWAYS respond in Hebrew only** — every word of every response, no other
  language or script mixed in anywhere, ever (never Arabic, never English
  words). This covers EVERY string you produce, not just the reply text: an
  approval question, a planning note, and every free-text tool argument
  (e.g. a reminder's `message_text`) too. Digits, standard punctuation, and ₪
  are fine; a genuinely foreign proper name may be transliterated into Hebrew
  letters where natural.
- **Never use ניקוד** (Hebrew vowel points/diacritics) in any response — plain
  Hebrew letters only, including inside a quoted name.
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

- Pass the literal text `[[NO_REPLY]]` to deliberately say nothing this turn. Use
  it only as the "Group Conversation Etiquette" section says (present only in a
  group chat).
- For a yes/no sign-off, use `cap_approval_with_buttons` instead; it gives the
  user tappable buttons.
- Reply in Hebrew only, concisely, without filler. End on the substantive answer.
  Ask a focused question only when you genuinely need the answer to act correctly.


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


## Flows

- flow_add_client: Adding a brand-new client record to Morning ("תוסיף לקוח חדש", or a shared contact card the user wants saved). Checks for an existing or similar client first so a duplicate is never created by accident, tells the user about similar candidates, and creates the record only with approval. Other flows load it whenever a client turns out not to exist yet.
- flow_modify_client: Changing an existing client's own details (name, email, phone) in Morning. Resolves which real client is meant, relaying candidates when the match is not exact, and updates it with approval. Not for creating a client and not for documents.
- flow_issue_invoice_for_payment_due: Issuing a new tax invoice (305) for a client, for money that is still owed ("תפיק חשבונית ללקוח X"). Never for money that has already arrived. Money that has already arrived belongs to flow_issue_invoice_receipt_combo instead.
- flow_issue_invoice_receipt_combo: Issuing a combined tax invoice/receipt (320) for a payment that has already been received and that no earlier document covers - the most common way to record incoming money, whether reported verbally or shown in a bank slip or payment screenshot. Money that an existing document already covers belongs to flow_issue_payment_received_with_reference_doc.
- flow_issue_transaction_account: Issuing a transaction account (חשבון עסקה, 300) for a client - only when the user's own wording names this document type. Ordinary requests for an invoice belong to flow_issue_invoice_for_payment_due.
- flow_issue_receipt_without_invoice: Recording a standalone receipt (400) with no invoice behind it, for example a refundable deposit. A receipt against an existing invoice belongs to flow_issue_payment_received_with_reference_doc.
- flow_payment_received_by_bank_slip_image: A bank slip or payment screenshot arrived. Reads it, records the payer, and gets the payment recorded in Morning the right way: a new combo document when nothing covers it, or a document against an existing one.
- flow_issue_payment_received_with_reference_doc: Recording a payment received against an existing Morning document: a receipt (400) for an existing invoice (305), or a combo document (320) closing an existing transaction account (300) ("סמן כשולם"). Money that no document covers belongs to flow_issue_invoice_receipt_combo.
- flow_cancel_document_with_credit_note: Cancelling an existing Morning document with a credit note (330) ("בטל את החשבונית"). Finds the one real document and shows its real data in the approval before writing.
- flow_cancel_transaction_account: Cancelling an open transaction account (300) directly. No document of any kind is created. Cancelling any other kind of document belongs to flow_cancel_document_with_credit_note.
- flow_fee_agreement_provided_by_user: The user reports or forwards a fee agreement (הסכם) - as text or as an image - made with a client. An agreement must never belong to a client Morning does not manage, so this makes sure the client exists first. Recording the agreement in the ledger happens automatically after the turn.
- flow_deposit_provided_by_user: The user reports or forwards a bank deposit (text or a bank slip image). Makes sure the payer exists as a client in Morning first. Recording the deposit in the ledger happens automatically after the turn.
- flow_user_question: Answering a question about the user's clients, past agreements, deposits, or amounts owed and paid. Decides where the answer lives (the ledger first, Morning when it may hold it), and never answers that nothing exists before checking Morning where Morning could hold it.
- flow_invoicing_query: Reading from the invoicing system for a client the user names: resolves the client's exact stored name first, then reads the documents or status. Other flows load it whenever they need to look up documents in Morning.
- flow_generate_fee_agreement_docx: Generating a fee agreement document (הסכם שכר טרחה) as a .docx file to send to a prospective client. The client does not exist yet, so no client lookup is involved. Recording an agreement the user reports belongs to flow_fee_agreement_provided_by_user.
- flow_create_reminder: Creating a new reminder, one-time or recurring ("תזכיר לי בעוד שעתיים", "תזכיר לי כל יום ראשון"). Confirms the text and the schedule, and creates the reminder only with approval. Use this flow, not cap_reminders_write directly, whenever a reminder is added.
- flow_modify_reminder: Changing or cancelling an existing reminder ("תזיז את התזכורת", "תבטל את התזכורת"). Looks up the user's real reminders to identify the exact one before modifying or deleting it, with approval. Adding a brand-new reminder belongs to flow_create_reminder. Use the reminder flows, not cap_reminders_write directly.

## Capabilities

- cap_invoicing_write: Creating a Morning DOCUMENT for a client - an invoice, a receipt, a transaction account, a credit note, or a combo tax-invoice/receipt - or cancelling a transaction account. Writes only: finding the client or the existing document, and getting approval, are the calling flow's job, so load it only through that flow (flow_issue_*, flow_cancel_*, flow_payment_received_*), never directly. Not for creating or updating a client record - see cap_client_write.
- cap_invoicing_read: Reading from the invoicing system (Morning): a specific document's own status and details, recent documents, a financial summary, a download link. It is given an already-resolved client name or document id. Not for a client's own details - see cap_client_read - and not the first choice for a general owed/paid amount question - see cap_ledger_query.
- cap_client_write: Creating a new client record, or updating an existing client's own details (name/email/phone) in Morning. Writes only: load it only through flow_add_client or flow_modify_client, never directly. Never for producing any document - see cap_invoicing_write.
- cap_client_read: Looking up an existing client's own details (name/email/phone/id), listing clients, and resolving a client name to its exact stored Morning spelling. Never for a client's financial history - see cap_ledger_query and cap_invoicing_read.
- cap_ledger_query: Answering questions about PAST fee agreements or bank deposits already recorded, including how much a client/payer owes or has paid - whether or not a formal Morning invoice exists. The ledger is a fast cache over Morning and covers agreement-level amounts Morning cannot see at all.
- cap_reminders_write: Creating, changing, or cancelling a reminder (one-time or recurring) for the user. Writes only: load it only through flow_create_reminder or flow_modify_reminder, never directly.
- cap_reminders_read: Looking up the user's own existing reminders - what's scheduled, for when.
- cap_media_analysis: Reading/extracting the content of an image or document the user sent. Used inside a larger flow, or on its own to work out what a piece of media is for.
- cap_docx_write: Composing and sending a fee agreement document (הסכם שכר טרחה) to a client as a .docx file. Never for invoices/receipts/transaction accounts or reminders. Load it only through flow_generate_fee_agreement_docx, never directly.
- cap_approval_with_buttons: Asking the user for an explicit yes/no sign-off with tappable buttons, before a write. Domain-agnostic: it just asks; the write capability defines which details the approval must state.

# Flow: Add client

Goal: add a brand-new client to Morning if it does not exist.

Capabilities: `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and look up the client by the name the user gave.
2. Handle what you find:
   - The client already exists: use `cap_send_to_user` to tell the user plainly that it does. Do not modify it and do not offer to. The flow is complete.
   - Similar clients exist but none matches exactly: use `cap_send_to_user` to list each similar client by name and offer, as its own explicit choice, to create a new client under the exact name they gave. Wait for their choice. If they pick an existing client, the flow is complete. A plain "add client X" is not by itself the user asking for a new one; only wording that concedes a similar client may exist and wants a new record anyway means you may skip the question. Once that is clear, don't ask again.
   - No such client: continue.
3. Load `cap_client_write` and prepare the client from what the user gave. If something is missing, use `cap_send_to_user` to ask the user for it; don't guess.
4. Creating a client MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Create the client only on a clear yes. On a no, create nothing, and use `cap_send_to_user` to ask what to change.
5. If the creation fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, create nothing and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_client_read`, `cap_client_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Flow: Generate fee agreement docx

Goal: compose a fee agreement (הסכם שכר טרחה) for the user and send it as a .docx file. It is a pre-signing document, so no client needs to exist.

Capabilities: `cap_docx_write`.

Follow these steps in order, to the letter.

1. Load `cap_docx_write`. Gather what the agreement needs from the user. Anything they did not state is something to ask about with `cap_send_to_user`, one question at a time; never invent a financial or legal term.
2. Compose, check and send the document as `cap_docx_write` directs. This flow needs no approval step and no client lookup.
3. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_docx_write` and this flow, keeping any that other work still in progress needs.


# Capability: Client — Write (godfather/admin only)

**Use this capability from within a flow (flow_add_client / flow_modify_client), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating or changing a client is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `add_client` and `update_client`, which create or change a client record in
Morning. They are real, persisted writes.

**Approval data points.** Whoever raises the approval must show the user:
- `add_client`: the new client's name, email and phone (and the tax id, if given).
- `update_client`: the ACTUAL resolved client (never the user's loose wording) and
  the specific field(s) changing, with their new values.

## Creating a client

`add_client` needs a name, an email AND a phone; all three are required, and none
may be guessed or omitted. `tax_id` is the only optional field. If Morning rejects a
tax id as invalid, relay that and ask for a corrected one.

**Never alter the spelling of a name you are creating.** Use it exactly as the user
wrote it, character for character; never "correct" it, even if you are confident
which spelling was meant. Morning stores it verbatim, and a silently altered name
means every later search for the real name fails.

## Updating a client

`update_client` needs `name_resolved=true` together with the EXACT name Morning has
stored. Pass `name_resolved=true` only for a name that has actually been confirmed as
Morning's stored name, never for the user's loose wording.


# Capability: Client — Read (godfather/admin only)

Attaches the Morning client-lookup tools: `list_clients`, `resolve_client_name`,
`get_client_details`. All read-only; call them right away, in the same turn, as soon
as you have what they need. None of them creates or changes a record.

This capability answers "who is this client", "what are their details", and "which
clients exist". It knows nothing about a client's amounts owed or paid.

## What resolving a name returns

`resolve_client_name` confirms the exact stored spelling of a name. A single-word
name is a genuine partial/substring search. It returns one of:
- an exact name: the stored spelling, to use verbatim;
- a confirmation question: a single close match, to relay to the user as-is;
- a candidates list: to relay to the user as-is;
- no match at all.

What to do with each result is the calling flow's business; this capability just
reports it faithfully and never picks a candidate on its own.


# Capability: Docx Write — Fee Agreement Documents (godfather/admin only)

**Use this capability from within a flow (flow_generate_fee_agreement_docx), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

Composing and sending a fee agreement document (הסכם שכר טרחה) as a .docx file over
WhatsApp. It is a pre-signing document, so there may be no client record for it yet.

## How it works
This capability gives you four tools: `get_fee_agreement_template`,
`render_fee_agreement_document`, `verify_fee_agreement_document`, and
`send_fee_agreement_document`. You are the document's actual author — the
firm's letterhead (logo/header/footer, title, date, signature block) is
applied automatically by code; you write only the substantive body: scope of
work, every fee/payment clause, any conditions.

Typical flow: `get_fee_agreement_template` (classify which variant fits, per
its own selection guide) → compose the full body text yourself → `render_...`
→ `verify_...` (read back the real facts — you still judge whether it's
correct/complete/one-page) → revise and re-render if needed → `send_...` once
you're satisfied. No human approval step on any of these four — your own
verification is the sole gate.

## Never
- Never invent, guess, or default a financial or legal detail the human did
  not explicitly give you — ask instead.
- Never leave a literal `{{...}}`-shaped placeholder token in what you send.
- Never call `send_fee_agreement_document` before a clean
  `verify_fee_agreement_document` result on the same document_id.


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
- End the text with EXACTLY this closed question, verbatim, every single time:
  `לאישור — כן/לא?`. Never paraphrase it (not `אישור — כן/לא?`, not `האם לאשר...`,
  not any other wording) and never let a competing question follow it — this exact
  string is a fixed contract other code relies on to recognize a real approval gate.
- Ask once per action. Act only on a clear affirmative to THAT specific action,
  exactly once. On "לא", do not act: acknowledge and ask what to change.
- Reply in Hebrew only.


## Loaded flows

flow_add_client, flow_generate_fee_agreement_docx

## Loaded capabilities

cap_client_write, cap_client_read, cap_docx_write, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:48 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>91. [2026-10-01 17:49:05] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72df659887d19fb75351d4a0af70`
- status: `completed`
- usage: `{"input_tokens": 10702, "input_tokens_details": {"cache_write_tokens": 265, "cached_tokens": 10434}, "output_tokens": 39, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 10741}`
- function_call: `send_to_user` call_id=`call_NIzMtQLRRD7g2m4GDhBkEw5k`
```json
{
  "text": "כדי להכין את ההסכם, מהו שמו המלא של השכן הנתבע?"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0bbf0c1a4a6cf8d7006abe72df659887d19fb75351d4a0af70`
- status: `completed`
- usage: `{"input_tokens": 10702, "input_tokens_details": {"cache_write_tokens": 265, "cached_tokens": 10434}, "output_tokens": 39, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 10741}`
- function_call: `send_to_user` call_id=`call_NIzMtQLRRD7g2m4GDhBkEw5k`
```json
{
  "text": "כדי להכין את ההסכם, מהו שמו המלא של השכן הנתבע?"
}
```

</details>

</details>

<details>
<summary>92. [2026-10-01 17:49:05] APP → USER — context=text</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "כדי להכין את ההסכם, מהו שמו המלא של השכן הנתבע?"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "+972501234567@c.us",
  "message": "כדי להכין את ההסכם, מהו שמו המלא של השכן הנתבע?"
}
```

</details>

</details>

