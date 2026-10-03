# Wire trace

Each numbered section below is one wire-crossing event, in strict chronological order (the number always goes up by 1, regardless of which boundary/direction it is). Click a section to expand it. Each has exactly two sub-sections, marked `↳` - Audit (concise) and Debug (full, verbatim) - and, inside Debug only, the long `instructions` text nests one level deeper, marked `↳↳`.

<details>
<summary>1. [2026-10-01 17:42:47] USER → APP — context=webhook</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "typeWebhook": "incomingMessageReceived",
  "timestamp": 1790865767,
  "idMessage": "E2E_DETAILS_1790865767",
  "instanceData": {
    "idInstance": 7103000000,
    "wid": "972501234567@c.us",
    "typeInstance": "whatsapp"
  },
  "senderData": {
    "chatId": "972500000021@c.us",
    "sender": "972500000021@c.us",
    "senderName": "E2E Godfather"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {
      "textMessage": "מה הסטטוס והפרטים המלאים של החשבונית של רימונה כהן מהשנים עשר באוגוסט?"
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
  "timestamp": 1790865767,
  "idMessage": "E2E_DETAILS_1790865767",
  "instanceData": {
    "idInstance": 7103000000,
    "wid": "972501234567@c.us",
    "typeInstance": "whatsapp"
  },
  "senderData": {
    "chatId": "972500000021@c.us",
    "sender": "972500000021@c.us",
    "senderName": "E2E Godfather"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {
      "textMessage": "מה הסטטוס והפרטים המלאים של החשבונית של רימונה כהן מהשנים עשר באוגוסט?"
    }
  }
}
```

</details>

</details>

<details>
<summary>2. [2026-10-01 17:42:47] APP → MODEL — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

```json
{"role": "user", "content": "מה הסטטוס והפרטים המלאים של החשבונית של רימונה כהן מהשנים עשר באוגוסט?"}
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
{"role": "user", "content": "מה הסטטוס והפרטים המלאים של החשבונית של רימונה כהן מהשנים עשר באוגוסט?"}
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

THE CURRENT DATE AND TIME IS 2026-10-01 17:42 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>3. [2026-10-01 17:42:49] MODEL → APP — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_08f2933df9ad87e6006abe7167e87087d18f15d70471d39f3a`
- status: `completed`
- usage: `{"input_tokens": 5907, "input_tokens_details": {"cache_write_tokens": 5904, "cached_tokens": 0}, "output_tokens": 79, "output_tokens_details": {"reasoning_tokens": 51}, "total_tokens": 5986}`
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_p4fAYmfAnElimSDmCbqFBCeZ`
```json
{
  "emoji": "🫡",
  "message_id": null
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_08f2933df9ad87e6006abe7167e87087d18f15d70471d39f3a`
- status: `completed`
- usage: `{"input_tokens": 5907, "input_tokens_details": {"cache_write_tokens": 5904, "cached_tokens": 0}, "output_tokens": 79, "output_tokens_details": {"reasoning_tokens": 51}, "total_tokens": 5986}`
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_p4fAYmfAnElimSDmCbqFBCeZ`
```json
{
  "emoji": "🫡",
  "message_id": null
}
```

</details>

</details>

<details>
<summary>4. [2026-10-01 17:42:49] APP → USER — context=reaction — 🫡 — NOT SENT (no WhatsApp bot in this run)</summary>

```text
[084] react_to_message call 'call_p4fAYmfAnElimSDmCbqFBCeZ': nothing to react through (target_id='E2E_DETAILS_1790865767', chat_id='972500000021@c.us', green_api_bot_set=False)
```

</details>

<details>
<summary>5. [2026-10-01 17:42:49] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `react_to_message` (call_id=`call_p4fAYmfAnElimSDmCbqFBCeZ`):
```text
{
  "status": "failed"
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_08f2933df9ad87e6006abe7167e87087d18f15d70471d39f3a'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `react_to_message` (call_id=`call_p4fAYmfAnElimSDmCbqFBCeZ`):
```text
{
  "status": "failed"
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_08f2933df9ad87e6006abe7167e87087d18f15d70471d39f3a'`

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

THE CURRENT DATE AND TIME IS 2026-10-01 17:42 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>6. [2026-10-01 17:42:51] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_08f2933df9ad87e6006abe7169cb3487d188412130c9b42c0a`
- status: `completed`
- usage: `{"input_tokens": 6004, "input_tokens_details": {"cache_write_tokens": 97, "cached_tokens": 5904}, "output_tokens": 38, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6042}`
- function_call: `send_progress_update` call_id=`call_9UOEis1ZfEistZZm27nWpMVg`
```json
{
  "text": "בודק את החשבונית של רימונה כהן מתאריך 12 באוגוסט."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_08f2933df9ad87e6006abe7169cb3487d188412130c9b42c0a`
- status: `completed`
- usage: `{"input_tokens": 6004, "input_tokens_details": {"cache_write_tokens": 97, "cached_tokens": 5904}, "output_tokens": 38, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6042}`
- function_call: `send_progress_update` call_id=`call_9UOEis1ZfEistZZm27nWpMVg`
```json
{
  "text": "בודק את החשבונית של רימונה כהן מתאריך 12 באוגוסט."
}
```

</details>

</details>

<details>
<summary>7. [2026-10-01 17:42:51] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "בודק את החשבונית של רימונה כהן מתאריך 12 באוגוסט."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "בודק את החשבונית של רימונה כהן מתאריך 12 באוגוסט."
}
```

</details>

</details>

<details>
<summary>8. [2026-10-01 17:42:51] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000021@c.us",
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
<summary>9. [2026-10-01 17:42:51] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `send_progress_update` (call_id=`call_9UOEis1ZfEistZZm27nWpMVg`):
```text
{
  "sent": true
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_08f2933df9ad87e6006abe7169cb3487d188412130c9b42c0a'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `send_progress_update` (call_id=`call_9UOEis1ZfEistZZm27nWpMVg`):
```text
{
  "sent": true
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_08f2933df9ad87e6006abe7169cb3487d188412130c9b42c0a'`

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

THE CURRENT DATE AND TIME IS 2026-10-01 17:42 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>10. [2026-10-01 17:42:53] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_08f2933df9ad87e6006abe716b998087d1959db6aad8215983`
- status: `completed`
- usage: `{"input_tokens": 6059, "input_tokens_details": {"cache_write_tokens": 55, "cached_tokens": 6001}, "output_tokens": 138, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6197}`
- function_call: `record_planning_status` call_id=`call_5VX4TDK3a5a2M863MNnV9pjR`
```json
{
  "where_i_was": "המשתמש ביקש סטטוס ופרטים מלאים של חשבונית עבור רימונה כהן מתאריך 12 באוגוסט.",
  "this_turns_purpose": "להפעיל את זרימת בירור החשבוניות, לזהות את הלקוחה ואת החשבונית המדויקת, ואז להציג את פרטיה וסטטוסה.",
  "expectation": "אטען את זרימת בירור החשבוניות ואת יכולות קריאת הלקוחות והחשבוניות, ולאחר מכן אחפש את החשבונית לפי הלקוחה והתאריך."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_08f2933df9ad87e6006abe716b998087d1959db6aad8215983`
- status: `completed`
- usage: `{"input_tokens": 6059, "input_tokens_details": {"cache_write_tokens": 55, "cached_tokens": 6001}, "output_tokens": 138, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6197}`
- function_call: `record_planning_status` call_id=`call_5VX4TDK3a5a2M863MNnV9pjR`
```json
{
  "where_i_was": "המשתמש ביקש סטטוס ופרטים מלאים של חשבונית עבור רימונה כהן מתאריך 12 באוגוסט.",
  "this_turns_purpose": "להפעיל את זרימת בירור החשבוניות, לזהות את הלקוחה ואת החשבונית המדויקת, ואז להציג את פרטיה וסטטוסה.",
  "expectation": "אטען את זרימת בירור החשבוניות ואת יכולות קריאת הלקוחות והחשבוניות, ולאחר מכן אחפש את החשבונית לפי הלקוחה והתאריך."
}
```

</details>

</details>

<details>
<summary>11. [2026-10-01 17:42:53] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `record_planning_status` (call_id=`call_5VX4TDK3a5a2M863MNnV9pjR`):
```text
recorded
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_08f2933df9ad87e6006abe716b998087d1959db6aad8215983'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `record_planning_status` (call_id=`call_5VX4TDK3a5a2M863MNnV9pjR`):
```text
recorded
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_08f2933df9ad87e6006abe716b998087d1959db6aad8215983'`

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

THE CURRENT DATE AND TIME IS 2026-10-01 17:42 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>12. [2026-10-01 17:42:55] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_08f2933df9ad87e6006abe716e3c8087d194fa44b9e33b9ac3`
- status: `completed`
- usage: `{"input_tokens": 6212, "input_tokens_details": {"cache_write_tokens": 153, "cached_tokens": 6056}, "output_tokens": 24, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6236}`
- function_call: `load_flows` call_id=`call_HXUPq0mnJ6sTDigLqQaJbinA`
```json
{
  "flows": [
    "flow_invoicing_query"
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_08f2933df9ad87e6006abe716e3c8087d194fa44b9e33b9ac3`
- status: `completed`
- usage: `{"input_tokens": 6212, "input_tokens_details": {"cache_write_tokens": 153, "cached_tokens": 6056}, "output_tokens": 24, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6236}`
- function_call: `load_flows` call_id=`call_HXUPq0mnJ6sTDigLqQaJbinA`
```json
{
  "flows": [
    "flow_invoicing_query"
  ]
}
```

</details>

</details>

<details>
<summary>13. [2026-10-01 17:42:55] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_invoicing_query

- capabilities: (none - plain backbone)

**input:**

- app's reply to `load_flows` (call_id=`call_HXUPq0mnJ6sTDigLqQaJbinA`):
```text
loaded flows: flow_invoicing_query. Loaded flows now: flow_invoicing_query. Loaded capabilities now: (none). Their blueprint text is attached starting now.
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_08f2933df9ad87e6006abe716e3c8087d194fa44b9e33b9ac3'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_invoicing_query, capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_invoicing_query

- capabilities: (none - plain backbone)

**input:**

- app's reply to `load_flows` (call_id=`call_HXUPq0mnJ6sTDigLqQaJbinA`):
```text
loaded flows: flow_invoicing_query. Loaded flows now: flow_invoicing_query. Loaded capabilities now: (none). Their blueprint text is attached starting now.
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_08f2933df9ad87e6006abe716e3c8087d194fa44b9e33b9ac3'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (20749 chars)</summary>

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

# Flow: Invoicing query

Goal: read a client's documents or a document's status from the invoicing system (Morning), for the client the user means.

Capabilities: `cap_client_read`, `cap_invoicing_read`.

Follow these steps in order, to the letter.

1. Look at the conversation window first. If a **prior** turn in this SAME conversation already resolved this exact client — a `resolve_client_name`/`get_client_details` result, or a match you already confirmed with the user — treat that stored name as still resolved, even if that turn already ended and even if `cap_client_read` is no longer loaded. Do **not** re-resolve or re-verify it again "just to be sure" — skip straight to step 3 with it. The same applies to a document id you already hold. Only go to step 2 when the user names a client (or document) you have no such record of in the window, or names a different one.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   - An exact stored name: use it as is.
   - A single close match: use `cap_send_to_user` to confirm it with the user before going on.
   - Several candidates: use `cap_send_to_user` to list them and ask which one is meant. Never pick one silently.
   - No match: use `cap_send_to_user` to say the client was not found and stop. Looking something up never creates a client.
3. Load `cap_invoicing_read` and read what was asked, giving it the exact stored client name you resolved (or the document id you hold).
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Hand the result to whoever asked: a flow that loaded this one continues with it; a question from the user is answered with `cap_send_to_user`. Then unload `cap_client_read`, `cap_invoicing_read` and this flow, keeping any that other work still in progress needs.


## Loaded flows

flow_invoicing_query

## Loaded capabilities

(none - plain backbone)

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:42 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>14. [2026-10-01 17:42:57] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_08f2933df9ad87e6006abe717033d887d1b2592568ea5f3810`
- status: `completed`
- usage: `{"input_tokens": 6730, "input_tokens_details": {"cache_write_tokens": 6727, "cached_tokens": 0}, "output_tokens": 29, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6759}`
- function_call: `load_capabilities` call_id=`call_bt83mCIG4irbtlD02qvQxlEN`
```json
{
  "capabilities": [
    "cap_client_read",
    "cap_invoicing_read"
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_08f2933df9ad87e6006abe717033d887d1b2592568ea5f3810`
- status: `completed`
- usage: `{"input_tokens": 6730, "input_tokens_details": {"cache_write_tokens": 6727, "cached_tokens": 0}, "output_tokens": 29, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6759}`
- function_call: `load_capabilities` call_id=`call_bt83mCIG4irbtlD02qvQxlEN`
```json
{
  "capabilities": [
    "cap_client_read",
    "cap_invoicing_read"
  ]
}
```

</details>

</details>

<details>
<summary>15. [2026-10-01 17:42:57] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_invoicing_query

- capabilities: cap_invoicing_read, cap_client_read

**input:**

- app's reply to `load_capabilities` (call_id=`call_bt83mCIG4irbtlD02qvQxlEN`):
```text
loaded capabilitys: cap_client_read, cap_invoicing_read. Loaded flows now: flow_invoicing_query. Loaded capabilities now: cap_client_read, cap_invoicing_read. Their instructions and tools are attached starting now.
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp', 'mcp']

- previous_response_id: `'resp_08f2933df9ad87e6006abe717033d887d1b2592568ea5f3810'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_invoicing_query, capabilities=cap_invoicing_read, cap_client_read)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_invoicing_query

- capabilities: cap_invoicing_read, cap_client_read

**input:**

- app's reply to `load_capabilities` (call_id=`call_bt83mCIG4irbtlD02qvQxlEN`):
```text
loaded capabilitys: cap_client_read, cap_invoicing_read. Loaded flows now: flow_invoicing_query. Loaded capabilities now: cap_client_read, cap_invoicing_read. Their instructions and tools are attached starting now.
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp', 'mcp']

- previous_response_id: `'resp_08f2933df9ad87e6006abe717033d887d1b2592568ea5f3810'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24788 chars)</summary>

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

# Flow: Invoicing query

Goal: read a client's documents or a document's status from the invoicing system (Morning), for the client the user means.

Capabilities: `cap_client_read`, `cap_invoicing_read`.

Follow these steps in order, to the letter.

1. Look at the conversation window first. If a **prior** turn in this SAME conversation already resolved this exact client — a `resolve_client_name`/`get_client_details` result, or a match you already confirmed with the user — treat that stored name as still resolved, even if that turn already ended and even if `cap_client_read` is no longer loaded. Do **not** re-resolve or re-verify it again "just to be sure" — skip straight to step 3 with it. The same applies to a document id you already hold. Only go to step 2 when the user names a client (or document) you have no such record of in the window, or names a different one.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   - An exact stored name: use it as is.
   - A single close match: use `cap_send_to_user` to confirm it with the user before going on.
   - Several candidates: use `cap_send_to_user` to list them and ask which one is meant. Never pick one silently.
   - No match: use `cap_send_to_user` to say the client was not found and stop. Looking something up never creates a client.
3. Load `cap_invoicing_read` and read what was asked, giving it the exact stored client name you resolved (or the document id you hold).
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Hand the result to whoever asked: a flow that loaded this one continues with it; a question from the user is answered with `cap_send_to_user`. Then unload `cap_client_read`, `cap_invoicing_read` and this flow, keeping any that other work still in progress needs.


# Capability: Invoicing — Read (godfather/admin only)

You have the Morning MCP server's read-only tools attached (`list_invoices`,
`get_invoice_details`, `get_financial_summary`,
`download_invoice_pdf`). All read-only tools need no confirmation — call them
immediately, in the same turn, as soon as you have what they need; none of
them creates or changes a record. Never call a write tool here — this
capability is read-only.

A search by client name takes the client's exact stored name, already resolved by
whoever loaded this capability, passed with `name_resolved=true`. This capability
only reads from the invoicing system; it never resolves names itself.

The visible invoice number is NOT the `internal_morning_id`; that is a display label
only. The id a tool needs is the UUID from a tool result. **Never ask for or mention
`internal_morning_id`** to the user.

## Understanding Morning's document model — never double-count linked documents

`list_invoices` returns every document type Morning has for a client in one
flat list — real invoices, receipts, and cancellations all mixed together. A
receipt or credit invoice is never an independent charge of its own — it's
evidence attached to one specific real invoice, and its amount is the SAME
money as (part of) that invoice's amount. Summing a list naively
double-counts.

**The document types and how they relate:**
1. **חשבונית מס/קבלה (combo, 320)** — already fully paid by definition.
2. **חשבונית מס (305)** — unpaid until a **קבלה (400)** is later issued
   against it.
3. **חשבון עסקה (300)** — closed by a חשבונית מס/קבלה combo (320) when paid,
   not a plain קבלה.
4. **חשבונית זיכוי (330)** — cancels a 300/305/320 document; never itself a
   new charge.

**To compute what's paid or owed per real invoice** (a 300/305/320 document,
never a receipt/credit note on its own):
1. Call `get_invoice_details` on its `internal_morning_id` — only the detail
   view includes the **מסמכים מקושרים** (linked documents) section.
2. `paid` = the sum of its linked receipts/closing combo documents (a 320 is
   always fully paid on its own, no linked lookup needed).
3. `owed` = invoice amount − (linked receipts/closing docs) − (linked credit
   invoices).
4. When answering across MULTIPLE invoices, do this resolution **per
   invoice**, then sum only the resolved paid/owed figures — never sum raw
   `list_invoices` amounts directly, since receipts/credits already appear
   there as their own separate-looking lines.

## Analytical/aggregate questions

Some requests ask you to rank, total, count, or filter across multiple
invoices/clients ("who owes me the most", "total unpaid per client") — no
single tool returns this shape directly. Call `list_invoices` (filtered as
the request implies), then group/sum/sort/filter yourself. **Never say you
lack access when a tool that can supply the underlying data is actually
attached** — only say a tool is unavailable when it genuinely isn't attached
or a call actually failed.

Results are already in Hebrew; keep your reply in Hebrew too.


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


## Loaded flows

flow_invoicing_query

## Loaded capabilities

cap_invoicing_read, cap_client_read

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:42 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>16. [2026-10-01 17:43:03] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 1/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_08f2933df9ad87e6006abe7171e2c487d186eafefe48bdfcdd`
- status: `completed`
- usage: `{"input_tokens": 9095, "input_tokens_details": {"cache_write_tokens": 8991, "cached_tokens": 0}, "output_tokens": 162, "output_tokens_details": {"reasoning_tokens": 86}, "total_tokens": 9257}`
- mcp_list_tools (morning-invoices-client-read): ['list_clients', 'resolve_client_name', 'get_client_details']
- mcp_list_tools (morning-invoices-invoicing-read): ['list_invoices', 'get_invoice_details', 'get_financial_summary', 'download_invoice_pdf']
- reasoning item (content not user-visible)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_08f2933df9ad87e6006abe7171e2c487d186eafefe48bdfcdd`
- status: `completed`
- usage: `{"input_tokens": 9095, "input_tokens_details": {"cache_write_tokens": 8991, "cached_tokens": 0}, "output_tokens": 162, "output_tokens_details": {"reasoning_tokens": 86}, "total_tokens": 9257}`
- mcp_list_tools (morning-invoices-client-read): ['list_clients', 'resolve_client_name', 'get_client_details']
- mcp_list_tools (morning-invoices-invoicing-read): ['list_invoices', 'get_invoice_details', 'get_financial_summary', 'download_invoice_pdf']
- reasoning item (content not user-visible)

</details>

</details>

<details>
<summary>17. [2026-10-01 17:43:03] MODEL → MORNING MCP — resolve_client_name</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- tool name: `resolve_client_name`
- server_label: `'morning-invoices-client-read'`

arguments:
```json
{
  "name": "רימונה כהן"
}
```

</details>

</details>

<details>
<summary>18. [2026-10-01 17:43:03] MORNING MCP → MODEL — resolve_client_name</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

output:
```json
{
  "status": "resolved",
  "name": "רימונה כהן"
}
```

</details>

</details>

<details>
<summary>19. [2026-10-01 17:43:03] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 2/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_08f2933df9ad87e6006abe7171e2c487d186eafefe48bdfcdd`
- status: `completed`
- usage: `{"input_tokens": 9095, "input_tokens_details": {"cache_write_tokens": 8991, "cached_tokens": 0}, "output_tokens": 162, "output_tokens_details": {"reasoning_tokens": 86}, "total_tokens": 9257}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_P2wh8cS8jR4SnTjMtydA9dxl`
```json
{
  "text": "מצאתי את הלקוחה; עכשיו מאתר את החשבונית מתאריך 12 באוגוסט 2026."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_08f2933df9ad87e6006abe7171e2c487d186eafefe48bdfcdd`
- status: `completed`
- usage: `{"input_tokens": 9095, "input_tokens_details": {"cache_write_tokens": 8991, "cached_tokens": 0}, "output_tokens": 162, "output_tokens_details": {"reasoning_tokens": 86}, "total_tokens": 9257}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_P2wh8cS8jR4SnTjMtydA9dxl`
```json
{
  "text": "מצאתי את הלקוחה; עכשיו מאתר את החשבונית מתאריך 12 באוגוסט 2026."
}
```

</details>

</details>

<details>
<summary>20. [2026-10-01 17:43:03] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "מצאתי את הלקוחה; עכשיו מאתר את החשבונית מתאריך 12 באוגוסט 2026."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "מצאתי את הלקוחה; עכשיו מאתר את החשבונית מתאריך 12 באוגוסט 2026."
}
```

</details>

</details>

<details>
<summary>21. [2026-10-01 17:43:03] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000021@c.us",
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
<summary>22. [2026-10-01 17:43:03] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_invoicing_query

- capabilities: cap_invoicing_read, cap_client_read

**input:**

- app's reply to `send_progress_update` (call_id=`call_P2wh8cS8jR4SnTjMtydA9dxl`):
```text
{
  "sent": true
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp', 'mcp']

- previous_response_id: `'resp_08f2933df9ad87e6006abe7171e2c487d186eafefe48bdfcdd'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_invoicing_query, capabilities=cap_invoicing_read, cap_client_read)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_invoicing_query

- capabilities: cap_invoicing_read, cap_client_read

**input:**

- app's reply to `send_progress_update` (call_id=`call_P2wh8cS8jR4SnTjMtydA9dxl`):
```text
{
  "sent": true
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp', 'mcp']

- previous_response_id: `'resp_08f2933df9ad87e6006abe7171e2c487d186eafefe48bdfcdd'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24788 chars)</summary>

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

# Flow: Invoicing query

Goal: read a client's documents or a document's status from the invoicing system (Morning), for the client the user means.

Capabilities: `cap_client_read`, `cap_invoicing_read`.

Follow these steps in order, to the letter.

1. Look at the conversation window first. If a **prior** turn in this SAME conversation already resolved this exact client — a `resolve_client_name`/`get_client_details` result, or a match you already confirmed with the user — treat that stored name as still resolved, even if that turn already ended and even if `cap_client_read` is no longer loaded. Do **not** re-resolve or re-verify it again "just to be sure" — skip straight to step 3 with it. The same applies to a document id you already hold. Only go to step 2 when the user names a client (or document) you have no such record of in the window, or names a different one.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   - An exact stored name: use it as is.
   - A single close match: use `cap_send_to_user` to confirm it with the user before going on.
   - Several candidates: use `cap_send_to_user` to list them and ask which one is meant. Never pick one silently.
   - No match: use `cap_send_to_user` to say the client was not found and stop. Looking something up never creates a client.
3. Load `cap_invoicing_read` and read what was asked, giving it the exact stored client name you resolved (or the document id you hold).
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Hand the result to whoever asked: a flow that loaded this one continues with it; a question from the user is answered with `cap_send_to_user`. Then unload `cap_client_read`, `cap_invoicing_read` and this flow, keeping any that other work still in progress needs.


# Capability: Invoicing — Read (godfather/admin only)

You have the Morning MCP server's read-only tools attached (`list_invoices`,
`get_invoice_details`, `get_financial_summary`,
`download_invoice_pdf`). All read-only tools need no confirmation — call them
immediately, in the same turn, as soon as you have what they need; none of
them creates or changes a record. Never call a write tool here — this
capability is read-only.

A search by client name takes the client's exact stored name, already resolved by
whoever loaded this capability, passed with `name_resolved=true`. This capability
only reads from the invoicing system; it never resolves names itself.

The visible invoice number is NOT the `internal_morning_id`; that is a display label
only. The id a tool needs is the UUID from a tool result. **Never ask for or mention
`internal_morning_id`** to the user.

## Understanding Morning's document model — never double-count linked documents

`list_invoices` returns every document type Morning has for a client in one
flat list — real invoices, receipts, and cancellations all mixed together. A
receipt or credit invoice is never an independent charge of its own — it's
evidence attached to one specific real invoice, and its amount is the SAME
money as (part of) that invoice's amount. Summing a list naively
double-counts.

**The document types and how they relate:**
1. **חשבונית מס/קבלה (combo, 320)** — already fully paid by definition.
2. **חשבונית מס (305)** — unpaid until a **קבלה (400)** is later issued
   against it.
3. **חשבון עסקה (300)** — closed by a חשבונית מס/קבלה combo (320) when paid,
   not a plain קבלה.
4. **חשבונית זיכוי (330)** — cancels a 300/305/320 document; never itself a
   new charge.

**To compute what's paid or owed per real invoice** (a 300/305/320 document,
never a receipt/credit note on its own):
1. Call `get_invoice_details` on its `internal_morning_id` — only the detail
   view includes the **מסמכים מקושרים** (linked documents) section.
2. `paid` = the sum of its linked receipts/closing combo documents (a 320 is
   always fully paid on its own, no linked lookup needed).
3. `owed` = invoice amount − (linked receipts/closing docs) − (linked credit
   invoices).
4. When answering across MULTIPLE invoices, do this resolution **per
   invoice**, then sum only the resolved paid/owed figures — never sum raw
   `list_invoices` amounts directly, since receipts/credits already appear
   there as their own separate-looking lines.

## Analytical/aggregate questions

Some requests ask you to rank, total, count, or filter across multiple
invoices/clients ("who owes me the most", "total unpaid per client") — no
single tool returns this shape directly. Call `list_invoices` (filtered as
the request implies), then group/sum/sort/filter yourself. **Never say you
lack access when a tool that can supply the underlying data is actually
attached** — only say a tool is unavailable when it genuinely isn't attached
or a call actually failed.

Results are already in Hebrew; keep your reply in Hebrew too.


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


## Loaded flows

flow_invoicing_query

## Loaded capabilities

cap_invoicing_read, cap_client_read

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:42 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>23. [2026-10-01 17:43:09] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 1/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_08f2933df9ad87e6006abe7177994087d1857022ec1ea43d61`
- status: `completed`
- usage: `{"input_tokens": 10036, "input_tokens_details": {"cache_write_tokens": 230, "cached_tokens": 8991}, "output_tokens": 151, "output_tokens_details": {"reasoning_tokens": 43}, "total_tokens": 10187}`

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_08f2933df9ad87e6006abe7177994087d1857022ec1ea43d61`
- status: `completed`
- usage: `{"input_tokens": 10036, "input_tokens_details": {"cache_write_tokens": 230, "cached_tokens": 8991}, "output_tokens": 151, "output_tokens_details": {"reasoning_tokens": 43}, "total_tokens": 10187}`
- (no output items in this part)

</details>

</details>

<details>
<summary>24. [2026-10-01 17:43:09] MODEL → MORNING MCP — list_invoices</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- tool name: `list_invoices`
- server_label: `'morning-invoices-invoicing-read'`

arguments:
```json
{
  "from_date": "2026-08-12",
  "to_date": "2026-08-12",
  "client_name": "רימונה כהן",
  "name_resolved": true
}
```

</details>

</details>

<details>
<summary>25. [2026-10-01 17:43:09] MORNING MCP → MODEL — list_invoices</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

output:
```json
{
  "total_matched": 2,
  "shown": 2,
  "documents": [
    {
      "display_number": "80591",
      "internal_morning_id": "9027b3c2-6a10-43a6-a371-55a0c8f956ef",
      "type": 400,
      "type_name": "קבלה",
      "status": "paid",
      "status_code": 1,
      "status_label": "מסמך סגור",
      "client_name": "רימונה כהן",
      "description": "תשלום עבור חשבונית מספר 52046",
      "amount": 156.75,
      "amount_excl_vat": 0.0,
      "vat_amount": 0.0,
      "vat_rate": 0.0,
      "currency": "ILS",
      "document_date": "2026-08-12",
      "due_date": null,
      "creation_date": "2026-08-12T14:59:16+03:00",
      "payment": {
        "method": "מזומן",
        "type": 1,
        "date": "2026-08-12",
        "amount": 156.75,
        "bank_number": null,
        "bank_branch": null,
        "bank_account": null
      },
      "line_items": [],
      "linked_document": null
    },
    {
      "display_number": "52046",
      "internal_morning_id": "00053961-4f4c-4301-aa8c-a00ee3512b23",
      "type": 305,
      "type_name": "חשבונית מס",
      "status": "paid",
      "status_code": 1,
      "status_label": "מסמך סגור",
      "client_name": "רימונה כהן",
      "description": "Ground truth fixture invoice",
      "amount": 156.75,
      "amount_excl_vat": 156.75,
      "vat_amount": 0.0,
      "vat_rate": 0.0,
      "currency": "ILS",
      "document_date": "2026-08-12",
      "due_date": null,
      "creation_date": "2026-08-12T14:59:03+03:00",
      "payment": null,
      "line_items": [
        {
          "description": "Ground truth fixture invoice",
          "quantity": 1,
          "price": 156.75,
          "amount": 156.75
        }
      ],
      "linked_document": null
    }
  ]
}
```

</details>

</details>

<details>
<summary>26. [2026-10-01 17:43:09] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 2/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_08f2933df9ad87e6006abe7177994087d1857022ec1ea43d61`
- status: `completed`
- usage: `{"input_tokens": 10036, "input_tokens_details": {"cache_write_tokens": 230, "cached_tokens": 8991}, "output_tokens": 151, "output_tokens_details": {"reasoning_tokens": 43}, "total_tokens": 10187}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_Yfr7tlSzzoNpkFad9Tm6uV4C`
```json
{
  "text": "מצאתי חשבונית מס 52046 וקבלה מקושרת; טוען עכשיו את הפרטים המלאים של החשבונית."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_08f2933df9ad87e6006abe7177994087d1857022ec1ea43d61`
- status: `completed`
- usage: `{"input_tokens": 10036, "input_tokens_details": {"cache_write_tokens": 230, "cached_tokens": 8991}, "output_tokens": 151, "output_tokens_details": {"reasoning_tokens": 43}, "total_tokens": 10187}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_Yfr7tlSzzoNpkFad9Tm6uV4C`
```json
{
  "text": "מצאתי חשבונית מס 52046 וקבלה מקושרת; טוען עכשיו את הפרטים המלאים של החשבונית."
}
```

</details>

</details>

<details>
<summary>27. [2026-10-01 17:43:09] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "מצאתי חשבונית מס 52046 וקבלה מקושרת; טוען עכשיו את הפרטים המלאים של החשבונית."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "מצאתי חשבונית מס 52046 וקבלה מקושרת; טוען עכשיו את הפרטים המלאים של החשבונית."
}
```

</details>

</details>

<details>
<summary>28. [2026-10-01 17:43:09] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000021@c.us",
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
<summary>29. [2026-10-01 17:43:09] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_invoicing_query

- capabilities: cap_invoicing_read, cap_client_read

**input:**

- app's reply to `send_progress_update` (call_id=`call_Yfr7tlSzzoNpkFad9Tm6uV4C`):
```text
{
  "sent": true
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp', 'mcp']

- previous_response_id: `'resp_08f2933df9ad87e6006abe7177994087d1857022ec1ea43d61'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_invoicing_query, capabilities=cap_invoicing_read, cap_client_read)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_invoicing_query

- capabilities: cap_invoicing_read, cap_client_read

**input:**

- app's reply to `send_progress_update` (call_id=`call_Yfr7tlSzzoNpkFad9Tm6uV4C`):
```text
{
  "sent": true
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp', 'mcp']

- previous_response_id: `'resp_08f2933df9ad87e6006abe7177994087d1857022ec1ea43d61'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24788 chars)</summary>

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

# Flow: Invoicing query

Goal: read a client's documents or a document's status from the invoicing system (Morning), for the client the user means.

Capabilities: `cap_client_read`, `cap_invoicing_read`.

Follow these steps in order, to the letter.

1. Look at the conversation window first. If a **prior** turn in this SAME conversation already resolved this exact client — a `resolve_client_name`/`get_client_details` result, or a match you already confirmed with the user — treat that stored name as still resolved, even if that turn already ended and even if `cap_client_read` is no longer loaded. Do **not** re-resolve or re-verify it again "just to be sure" — skip straight to step 3 with it. The same applies to a document id you already hold. Only go to step 2 when the user names a client (or document) you have no such record of in the window, or names a different one.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   - An exact stored name: use it as is.
   - A single close match: use `cap_send_to_user` to confirm it with the user before going on.
   - Several candidates: use `cap_send_to_user` to list them and ask which one is meant. Never pick one silently.
   - No match: use `cap_send_to_user` to say the client was not found and stop. Looking something up never creates a client.
3. Load `cap_invoicing_read` and read what was asked, giving it the exact stored client name you resolved (or the document id you hold).
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Hand the result to whoever asked: a flow that loaded this one continues with it; a question from the user is answered with `cap_send_to_user`. Then unload `cap_client_read`, `cap_invoicing_read` and this flow, keeping any that other work still in progress needs.


# Capability: Invoicing — Read (godfather/admin only)

You have the Morning MCP server's read-only tools attached (`list_invoices`,
`get_invoice_details`, `get_financial_summary`,
`download_invoice_pdf`). All read-only tools need no confirmation — call them
immediately, in the same turn, as soon as you have what they need; none of
them creates or changes a record. Never call a write tool here — this
capability is read-only.

A search by client name takes the client's exact stored name, already resolved by
whoever loaded this capability, passed with `name_resolved=true`. This capability
only reads from the invoicing system; it never resolves names itself.

The visible invoice number is NOT the `internal_morning_id`; that is a display label
only. The id a tool needs is the UUID from a tool result. **Never ask for or mention
`internal_morning_id`** to the user.

## Understanding Morning's document model — never double-count linked documents

`list_invoices` returns every document type Morning has for a client in one
flat list — real invoices, receipts, and cancellations all mixed together. A
receipt or credit invoice is never an independent charge of its own — it's
evidence attached to one specific real invoice, and its amount is the SAME
money as (part of) that invoice's amount. Summing a list naively
double-counts.

**The document types and how they relate:**
1. **חשבונית מס/קבלה (combo, 320)** — already fully paid by definition.
2. **חשבונית מס (305)** — unpaid until a **קבלה (400)** is later issued
   against it.
3. **חשבון עסקה (300)** — closed by a חשבונית מס/קבלה combo (320) when paid,
   not a plain קבלה.
4. **חשבונית זיכוי (330)** — cancels a 300/305/320 document; never itself a
   new charge.

**To compute what's paid or owed per real invoice** (a 300/305/320 document,
never a receipt/credit note on its own):
1. Call `get_invoice_details` on its `internal_morning_id` — only the detail
   view includes the **מסמכים מקושרים** (linked documents) section.
2. `paid` = the sum of its linked receipts/closing combo documents (a 320 is
   always fully paid on its own, no linked lookup needed).
3. `owed` = invoice amount − (linked receipts/closing docs) − (linked credit
   invoices).
4. When answering across MULTIPLE invoices, do this resolution **per
   invoice**, then sum only the resolved paid/owed figures — never sum raw
   `list_invoices` amounts directly, since receipts/credits already appear
   there as their own separate-looking lines.

## Analytical/aggregate questions

Some requests ask you to rank, total, count, or filter across multiple
invoices/clients ("who owes me the most", "total unpaid per client") — no
single tool returns this shape directly. Call `list_invoices` (filtered as
the request implies), then group/sum/sort/filter yourself. **Never say you
lack access when a tool that can supply the underlying data is actually
attached** — only say a tool is unavailable when it genuinely isn't attached
or a call actually failed.

Results are already in Hebrew; keep your reply in Hebrew too.


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


## Loaded flows

flow_invoicing_query

## Loaded capabilities

cap_invoicing_read, cap_client_read

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:42 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>30. [2026-10-01 17:43:17] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 1/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_08f2933df9ad87e6006abe717dcbd887d1b4f4aa8a0a702173`
- status: `completed`
- usage: `{"input_tokens": 10547, "input_tokens_details": {"cache_write_tokens": 10132, "cached_tokens": 0}, "output_tokens": 298, "output_tokens_details": {"reasoning_tokens": 106}, "total_tokens": 10845}`

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_08f2933df9ad87e6006abe717dcbd887d1b4f4aa8a0a702173`
- status: `completed`
- usage: `{"input_tokens": 10547, "input_tokens_details": {"cache_write_tokens": 10132, "cached_tokens": 0}, "output_tokens": 298, "output_tokens_details": {"reasoning_tokens": 106}, "total_tokens": 10845}`
- (no output items in this part)

</details>

</details>

<details>
<summary>31. [2026-10-01 17:43:17] MODEL → MORNING MCP — get_invoice_details</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- tool name: `get_invoice_details`
- server_label: `'morning-invoices-invoicing-read'`

arguments:
```json
{
  "internal_morning_id": "00053961-4f4c-4301-aa8c-a00ee3512b23"
}
```

</details>

</details>

<details>
<summary>32. [2026-10-01 17:43:17] MORNING MCP → MODEL — get_invoice_details</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

output:
```json
{
  "display_number": "52046",
  "internal_morning_id": "00053961-4f4c-4301-aa8c-a00ee3512b23",
  "type": 305,
  "type_name": "חשבונית מס",
  "status": "paid",
  "status_code": 1,
  "status_label": "מסמך סגור",
  "client_name": "רימונה כהן",
  "description": "Ground truth fixture invoice",
  "amount": 156.75,
  "amount_excl_vat": 156.75,
  "vat_amount": 0.0,
  "vat_rate": 0.0,
  "currency": "ILS",
  "document_date": "2026-08-12",
  "due_date": null,
  "creation_date": "2026-08-12T14:59:03+03:00",
  "payment": null,
  "line_items": [
    {
      "description": "Ground truth fixture invoice",
      "quantity": 1,
      "price": 156.75,
      "amount": 156.75
    }
  ],
  "linked_document": {
    "number": "80591",
    "type": 400,
    "type_name": "קבלה"
  }
}
```

</details>

</details>

<details>
<summary>33. [2026-10-01 17:43:17] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 2/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_08f2933df9ad87e6006abe717dcbd887d1b4f4aa8a0a702173`
- status: `completed`
- usage: `{"input_tokens": 10547, "input_tokens_details": {"cache_write_tokens": 10132, "cached_tokens": 0}, "output_tokens": 298, "output_tokens_details": {"reasoning_tokens": 106}, "total_tokens": 10845}`
- reasoning item (content not user-visible)
- function_call: `record_planning_status` call_id=`call_T8uqsCOjsxSrtNQ1WIShWdda`
```json
{
  "where_i_was": "הושלם בירור החשבונית בזרימת בירור חשבוניות. החשבונית 52046 של רימונה כהן מתאריך 12.08.2026 נמצאה כסגורה ומשולמת, עם קבלה 80591 מקושרת.",
  "this_turns_purpose": "להציג למשתמש את הסטטוס ואת כל הפרטים הזמינים של החשבונית והקבלה המקושרת.",
  "expectation": "אשלח תשובה מסודרת בעברית, אסמן הצלחה, ואז אסיים את הזרימה."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_08f2933df9ad87e6006abe717dcbd887d1b4f4aa8a0a702173`
- status: `completed`
- usage: `{"input_tokens": 10547, "input_tokens_details": {"cache_write_tokens": 10132, "cached_tokens": 0}, "output_tokens": 298, "output_tokens_details": {"reasoning_tokens": 106}, "total_tokens": 10845}`
- reasoning item (content not user-visible)
- function_call: `record_planning_status` call_id=`call_T8uqsCOjsxSrtNQ1WIShWdda`
```json
{
  "where_i_was": "הושלם בירור החשבונית בזרימת בירור חשבוניות. החשבונית 52046 של רימונה כהן מתאריך 12.08.2026 נמצאה כסגורה ומשולמת, עם קבלה 80591 מקושרת.",
  "this_turns_purpose": "להציג למשתמש את הסטטוס ואת כל הפרטים הזמינים של החשבונית והקבלה המקושרת.",
  "expectation": "אשלח תשובה מסודרת בעברית, אסמן הצלחה, ואז אסיים את הזרימה."
}
```

</details>

</details>

<details>
<summary>34. [2026-10-01 17:43:17] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_invoicing_query

- capabilities: cap_invoicing_read, cap_client_read

**input:**

- app's reply to `record_planning_status` (call_id=`call_T8uqsCOjsxSrtNQ1WIShWdda`):
```text
recorded
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp', 'mcp']

- previous_response_id: `'resp_08f2933df9ad87e6006abe717dcbd887d1b4f4aa8a0a702173'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_invoicing_query, capabilities=cap_invoicing_read, cap_client_read)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_invoicing_query

- capabilities: cap_invoicing_read, cap_client_read

**input:**

- app's reply to `record_planning_status` (call_id=`call_T8uqsCOjsxSrtNQ1WIShWdda`):
```text
recorded
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp', 'mcp']

- previous_response_id: `'resp_08f2933df9ad87e6006abe717dcbd887d1b4f4aa8a0a702173'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24788 chars)</summary>

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

# Flow: Invoicing query

Goal: read a client's documents or a document's status from the invoicing system (Morning), for the client the user means.

Capabilities: `cap_client_read`, `cap_invoicing_read`.

Follow these steps in order, to the letter.

1. Look at the conversation window first. If a **prior** turn in this SAME conversation already resolved this exact client — a `resolve_client_name`/`get_client_details` result, or a match you already confirmed with the user — treat that stored name as still resolved, even if that turn already ended and even if `cap_client_read` is no longer loaded. Do **not** re-resolve or re-verify it again "just to be sure" — skip straight to step 3 with it. The same applies to a document id you already hold. Only go to step 2 when the user names a client (or document) you have no such record of in the window, or names a different one.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   - An exact stored name: use it as is.
   - A single close match: use `cap_send_to_user` to confirm it with the user before going on.
   - Several candidates: use `cap_send_to_user` to list them and ask which one is meant. Never pick one silently.
   - No match: use `cap_send_to_user` to say the client was not found and stop. Looking something up never creates a client.
3. Load `cap_invoicing_read` and read what was asked, giving it the exact stored client name you resolved (or the document id you hold).
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Hand the result to whoever asked: a flow that loaded this one continues with it; a question from the user is answered with `cap_send_to_user`. Then unload `cap_client_read`, `cap_invoicing_read` and this flow, keeping any that other work still in progress needs.


# Capability: Invoicing — Read (godfather/admin only)

You have the Morning MCP server's read-only tools attached (`list_invoices`,
`get_invoice_details`, `get_financial_summary`,
`download_invoice_pdf`). All read-only tools need no confirmation — call them
immediately, in the same turn, as soon as you have what they need; none of
them creates or changes a record. Never call a write tool here — this
capability is read-only.

A search by client name takes the client's exact stored name, already resolved by
whoever loaded this capability, passed with `name_resolved=true`. This capability
only reads from the invoicing system; it never resolves names itself.

The visible invoice number is NOT the `internal_morning_id`; that is a display label
only. The id a tool needs is the UUID from a tool result. **Never ask for or mention
`internal_morning_id`** to the user.

## Understanding Morning's document model — never double-count linked documents

`list_invoices` returns every document type Morning has for a client in one
flat list — real invoices, receipts, and cancellations all mixed together. A
receipt or credit invoice is never an independent charge of its own — it's
evidence attached to one specific real invoice, and its amount is the SAME
money as (part of) that invoice's amount. Summing a list naively
double-counts.

**The document types and how they relate:**
1. **חשבונית מס/קבלה (combo, 320)** — already fully paid by definition.
2. **חשבונית מס (305)** — unpaid until a **קבלה (400)** is later issued
   against it.
3. **חשבון עסקה (300)** — closed by a חשבונית מס/קבלה combo (320) when paid,
   not a plain קבלה.
4. **חשבונית זיכוי (330)** — cancels a 300/305/320 document; never itself a
   new charge.

**To compute what's paid or owed per real invoice** (a 300/305/320 document,
never a receipt/credit note on its own):
1. Call `get_invoice_details` on its `internal_morning_id` — only the detail
   view includes the **מסמכים מקושרים** (linked documents) section.
2. `paid` = the sum of its linked receipts/closing combo documents (a 320 is
   always fully paid on its own, no linked lookup needed).
3. `owed` = invoice amount − (linked receipts/closing docs) − (linked credit
   invoices).
4. When answering across MULTIPLE invoices, do this resolution **per
   invoice**, then sum only the resolved paid/owed figures — never sum raw
   `list_invoices` amounts directly, since receipts/credits already appear
   there as their own separate-looking lines.

## Analytical/aggregate questions

Some requests ask you to rank, total, count, or filter across multiple
invoices/clients ("who owes me the most", "total unpaid per client") — no
single tool returns this shape directly. Call `list_invoices` (filtered as
the request implies), then group/sum/sort/filter yourself. **Never say you
lack access when a tool that can supply the underlying data is actually
attached** — only say a tool is unavailable when it genuinely isn't attached
or a call actually failed.

Results are already in Hebrew; keep your reply in Hebrew too.


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


## Loaded flows

flow_invoicing_query

## Loaded capabilities

cap_invoicing_read, cap_client_read

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:42 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>35. [2026-10-01 17:43:18] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_08f2933df9ad87e6006abe7185632c87d196d4b06bd2a974c9`
- status: `completed`
- usage: `{"input_tokens": 10797, "input_tokens_details": {"cache_write_tokens": 1573, "cached_tokens": 9221}, "output_tokens": 24, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 10821}`
- function_call: `react_to_message` call_id=`call_XwYoneZizshfCuVfzf2FzLE8`
```json
{
  "emoji": "✅",
  "message_id": null
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_08f2933df9ad87e6006abe7185632c87d196d4b06bd2a974c9`
- status: `completed`
- usage: `{"input_tokens": 10797, "input_tokens_details": {"cache_write_tokens": 1573, "cached_tokens": 9221}, "output_tokens": 24, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 10821}`
- function_call: `react_to_message` call_id=`call_XwYoneZizshfCuVfzf2FzLE8`
```json
{
  "emoji": "✅",
  "message_id": null
}
```

</details>

</details>

<details>
<summary>36. [2026-10-01 17:43:18] APP → USER — context=reaction — ✅ — NOT SENT (no WhatsApp bot in this run)</summary>

```text
[084] react_to_message call 'call_XwYoneZizshfCuVfzf2FzLE8': nothing to react through (target_id='E2E_DETAILS_1790865767', chat_id='972500000021@c.us', green_api_bot_set=False)
```

</details>

<details>
<summary>37. [2026-10-01 17:43:18] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_invoicing_query

- capabilities: cap_invoicing_read, cap_client_read

**input:**

- app's reply to `react_to_message` (call_id=`call_XwYoneZizshfCuVfzf2FzLE8`):
```text
{
  "status": "failed"
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp', 'mcp']

- previous_response_id: `'resp_08f2933df9ad87e6006abe7185632c87d196d4b06bd2a974c9'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_invoicing_query, capabilities=cap_invoicing_read, cap_client_read)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_invoicing_query

- capabilities: cap_invoicing_read, cap_client_read

**input:**

- app's reply to `react_to_message` (call_id=`call_XwYoneZizshfCuVfzf2FzLE8`):
```text
{
  "status": "failed"
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp', 'mcp']

- previous_response_id: `'resp_08f2933df9ad87e6006abe7185632c87d196d4b06bd2a974c9'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24788 chars)</summary>

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

# Flow: Invoicing query

Goal: read a client's documents or a document's status from the invoicing system (Morning), for the client the user means.

Capabilities: `cap_client_read`, `cap_invoicing_read`.

Follow these steps in order, to the letter.

1. Look at the conversation window first. If a **prior** turn in this SAME conversation already resolved this exact client — a `resolve_client_name`/`get_client_details` result, or a match you already confirmed with the user — treat that stored name as still resolved, even if that turn already ended and even if `cap_client_read` is no longer loaded. Do **not** re-resolve or re-verify it again "just to be sure" — skip straight to step 3 with it. The same applies to a document id you already hold. Only go to step 2 when the user names a client (or document) you have no such record of in the window, or names a different one.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   - An exact stored name: use it as is.
   - A single close match: use `cap_send_to_user` to confirm it with the user before going on.
   - Several candidates: use `cap_send_to_user` to list them and ask which one is meant. Never pick one silently.
   - No match: use `cap_send_to_user` to say the client was not found and stop. Looking something up never creates a client.
3. Load `cap_invoicing_read` and read what was asked, giving it the exact stored client name you resolved (or the document id you hold).
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Hand the result to whoever asked: a flow that loaded this one continues with it; a question from the user is answered with `cap_send_to_user`. Then unload `cap_client_read`, `cap_invoicing_read` and this flow, keeping any that other work still in progress needs.


# Capability: Invoicing — Read (godfather/admin only)

You have the Morning MCP server's read-only tools attached (`list_invoices`,
`get_invoice_details`, `get_financial_summary`,
`download_invoice_pdf`). All read-only tools need no confirmation — call them
immediately, in the same turn, as soon as you have what they need; none of
them creates or changes a record. Never call a write tool here — this
capability is read-only.

A search by client name takes the client's exact stored name, already resolved by
whoever loaded this capability, passed with `name_resolved=true`. This capability
only reads from the invoicing system; it never resolves names itself.

The visible invoice number is NOT the `internal_morning_id`; that is a display label
only. The id a tool needs is the UUID from a tool result. **Never ask for or mention
`internal_morning_id`** to the user.

## Understanding Morning's document model — never double-count linked documents

`list_invoices` returns every document type Morning has for a client in one
flat list — real invoices, receipts, and cancellations all mixed together. A
receipt or credit invoice is never an independent charge of its own — it's
evidence attached to one specific real invoice, and its amount is the SAME
money as (part of) that invoice's amount. Summing a list naively
double-counts.

**The document types and how they relate:**
1. **חשבונית מס/קבלה (combo, 320)** — already fully paid by definition.
2. **חשבונית מס (305)** — unpaid until a **קבלה (400)** is later issued
   against it.
3. **חשבון עסקה (300)** — closed by a חשבונית מס/קבלה combo (320) when paid,
   not a plain קבלה.
4. **חשבונית זיכוי (330)** — cancels a 300/305/320 document; never itself a
   new charge.

**To compute what's paid or owed per real invoice** (a 300/305/320 document,
never a receipt/credit note on its own):
1. Call `get_invoice_details` on its `internal_morning_id` — only the detail
   view includes the **מסמכים מקושרים** (linked documents) section.
2. `paid` = the sum of its linked receipts/closing combo documents (a 320 is
   always fully paid on its own, no linked lookup needed).
3. `owed` = invoice amount − (linked receipts/closing docs) − (linked credit
   invoices).
4. When answering across MULTIPLE invoices, do this resolution **per
   invoice**, then sum only the resolved paid/owed figures — never sum raw
   `list_invoices` amounts directly, since receipts/credits already appear
   there as their own separate-looking lines.

## Analytical/aggregate questions

Some requests ask you to rank, total, count, or filter across multiple
invoices/clients ("who owes me the most", "total unpaid per client") — no
single tool returns this shape directly. Call `list_invoices` (filtered as
the request implies), then group/sum/sort/filter yourself. **Never say you
lack access when a tool that can supply the underlying data is actually
attached** — only say a tool is unavailable when it genuinely isn't attached
or a call actually failed.

Results are already in Hebrew; keep your reply in Hebrew too.


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


## Loaded flows

flow_invoicing_query

## Loaded capabilities

cap_invoicing_read, cap_client_read

---

THE CURRENT DATE AND TIME IS 2026-10-01 17:42 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>38. [2026-10-01 17:43:22] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_08f2933df9ad87e6006abe7187228087d1a587d8d8c3fd20bd`
- status: `completed`
- usage: `{"input_tokens": 10839, "input_tokens_details": {"cache_write_tokens": 42, "cached_tokens": 10794}, "output_tokens": 211, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 11050}`
- function_call: `send_to_user` call_id=`call_ehETty8xD8g5YDVZnFcIaO97`
```json
{
  "text": "פרטי החשבונית של רימונה כהן מ־12 באוגוסט 2026:\n\n• סוג: חשבונית מס\n• מספר: 52046\n• סטטוס: סגורה ומשולמת\n• סכום כולל: 156.75 ₪\n• לפני מע״מ: 156.75 ₪\n• מע״מ: 0 ₪, בשיעור 0%\n• תאריך הפקה: 12.08.2026 בשעה 14:59\n• תאריך פירעון: לא צוין\n• פריט: חשבונית מס, כמות 1, מחיר 156.75 ₪\n\nהחשבונית נסגרה באמצעות קבלה מספר 80591:\n• אמצעי תשלום: מזומן\n• תאריך תשלום: 12.08.2026\n• סכום: 156.75 ₪"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_08f2933df9ad87e6006abe7187228087d1a587d8d8c3fd20bd`
- status: `completed`
- usage: `{"input_tokens": 10839, "input_tokens_details": {"cache_write_tokens": 42, "cached_tokens": 10794}, "output_tokens": 211, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 11050}`
- function_call: `send_to_user` call_id=`call_ehETty8xD8g5YDVZnFcIaO97`
```json
{
  "text": "פרטי החשבונית של רימונה כהן מ־12 באוגוסט 2026:\n\n• סוג: חשבונית מס\n• מספר: 52046\n• סטטוס: סגורה ומשולמת\n• סכום כולל: 156.75 ₪\n• לפני מע״מ: 156.75 ₪\n• מע״מ: 0 ₪, בשיעור 0%\n• תאריך הפקה: 12.08.2026 בשעה 14:59\n• תאריך פירעון: לא צוין\n• פריט: חשבונית מס, כמות 1, מחיר 156.75 ₪\n\nהחשבונית נסגרה באמצעות קבלה מספר 80591:\n• אמצעי תשלום: מזומן\n• תאריך תשלום: 12.08.2026\n• סכום: 156.75 ₪"
}
```

</details>

</details>

<details>
<summary>39. [2026-10-01 17:43:22] APP → USER — context=text</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "פרטי החשבונית של רימונה כהן מ־12 באוגוסט 2026:\n\n• סוג: חשבונית מס\n• מספר: 52046\n• סטטוס: סגורה ומשולמת\n• סכום כולל: 156.75 ₪\n• לפני מע״מ: 156.75 ₪\n• מע״מ: 0 ₪, בשיעור 0%\n• תאריך הפקה: 12.08.2026 בשעה 14:59\n• תאריך פירעון: לא צוין\n• פריט: חשבונית מס, כמות 1, מחיר 156.75 ₪\n\nהחשבונית נסגרה באמצעות קבלה מספר 80591:\n• אמצעי תשלום: מזומן\n• תאריך תשלום: 12.08.2026\n• סכום: 156.75 ₪"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "פרטי החשבונית של רימונה כהן מ־12 באוגוסט 2026:\n\n• סוג: חשבונית מס\n• מספר: 52046\n• סטטוס: סגורה ומשולמת\n• סכום כולל: 156.75 ₪\n• לפני מע״מ: 156.75 ₪\n• מע״מ: 0 ₪, בשיעור 0%\n• תאריך הפקה: 12.08.2026 בשעה 14:59\n• תאריך פירעון: לא צוין\n• פריט: חשבונית מס, כמות 1, מחיר 156.75 ₪\n\nהחשבונית נסגרה באמצעות קבלה מספר 80591:\n• אמצעי תשלום: מזומן\n• תאריך תשלום: 12.08.2026\n• סכום: 156.75 ₪"
}
```

</details>

</details>

<details>
<summary>40. [2026-10-01 17:43:22] APP → MODEL — context=recognize_ledger_event</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

**input:**

```json
{"role": "user", "content": "THE CONVERSATION WINDOW (the last 1h, oldest first) - '<message_id> [<role>] <content>':\nbe052cbb-b6d3-4acd-b758-8553a77dfd04 [godfather] מה הסטטוס והפרטים המלאים של החשבונית של רימונה כהן מהשנים עשר באוגוסט?\ndf4aa56a-7280-4cd6-917a-f946be869979 [assistant] בודק את החשבונית של רימונה כהן מתאריך 12 באוגוסט.\nda5fb7c4-9719-4a82-bd1e-1e7c0b03392e [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: המשתמש ביקש סטטוס ופרטים מלאים של חשבונית עבור רימונה כהן מתאריך 12 באוגוסט.\nTHIS TURN'S PURPOSE: להפעיל את זרימת בירור החשבוניות, לזהות את הלקוחה ואת החשבונית המדויקת, ואז להציג את פרטיה וסטטוסה.\nEXPECTATION: אטען את זרימת בירור החשבוניות ואת יכולות קריאת הלקוחות והחשבוניות, ולאחר מכן אחפש את החשבונית לפי הלקוחה והתאריך.\nc34893e5-f799-486a-82de-f3d0716f2afd [assistant] מצאתי את הלקוחה; עכשיו מאתר את החשבונית מתאריך 12 באוגוסט 2026.\n05c522d2-4724-4410-ad83-652a59c76fd3 [assistant] מצאתי חשבונית מס 52046 וקבלה מקושרת; טוען עכשיו את הפרטים המלאים של החשבונית.\n36a3f04e-0c34-46fc-939d-cf579eb6f2e8 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: הושלם בירור החשבונית בזרימת בירור חשבוניות. החשבונית 52046 של רימונה כהן מתאריך 12.08.2026 נמצאה כסגורה ומשולמת, עם קבלה 80591 מקושרת.\nTHIS TURN'S PURPOSE: להציג למשתמש את הסטטוס ואת כל הפרטים הזמינים של החשבונית והקבלה המקושרת.\nEXPECTATION: אשלח תשובה מסודרת בעברית, אסמן הצלחה, ואז אסיים את הזרימה.\nb2a75309-a294-4a51-80b3-4b399d82d19a [assistant] פרטי החשבונית של רימונה כהן מ־12 באוגוסט 2026:\n\n• סוג: חשבונית מס\n• מספר: 52046\n• סטטוס: סגורה ומשולמת\n• סכום כולל: 156.75 ₪\n• לפני מע״מ: 156.75 ₪\n• מע״מ: 0 ₪, בשיעור 0%\n• תאריך הפקה: 12.08.2026 בשעה 14:59\n• תאריך פירעון: לא צוין\n• פריט: חשבונית מס, כמות 1, מחיר 156.75 ₪\n\nהחשבונית נסגרה באמצעות קבלה מספר 80591:\n• אמצעי תשלום: מזומן\n• תאריך תשלום: 12.08.2026\n• סכום: 156.75 ₪\n    (morning MCP call on this message's turn) {\"name\": \"resolve_client_name\", \"error\": null, \"arguments\": \"{\\\"name\\\":\\\"רימונה כהן\\\"}\", \"output\": \"{\\\"status\\\": \\\"resolved\\\", \\\"name\\\": \\\"\\\\u05e8\\\\u05d9\\\\u05de\\\\u05d5\\\\u05e0\\\\u05d4 \\\\u05db\\\\u05d4\\\\u05df\\\"}\"}\n    (morning MCP call on this message's turn) {\"name\": \"list_invoices\", \"error\": null, \"arguments\": \"{\\\"from_date\\\":\\\"2026-08-12\\\",\\\"to_date\\\":\\\"2026-08-12\\\",\\\"client_name\\\":\\\"רימונה כהן\\\",\\\"name_resolved\\\":true}\", \"output\": \"{\\\"total_matched\\\": 2, \\\"shown\\\": 2, \\\"documents\\\": [{\\\"display_number\\\": \\\"80591\\\", \\\"internal_morning_id\\\": \\\"9027b3c2-6a10-43a6-a371-55a0c8f956ef\\\", \\\"type\\\": 400, \\\"type_name\\\": \\\"\\\\u05e7\\\\u05d1\\\\u05dc\\\\u05d4\\\", \\\"status\\\": \\\"paid\\\", \\\"status_code\\\": 1, \\\"status_label\\\": \\\"\\\\u05de\\\\u05e1\\\\u05de\\\\u05da \\\\u05e1\\\\u05d2\\\\u05d5\\\\u05e8\\\", \\\"client_name\\\": \\\"\\\\u05e8\\\\u05d9\\\\u05de\\\\u05d5\\\\u05e0\\\\u05d4 \\\\u05db\\\\u05d4\\\\u05df\\\", \\\"description\\\": \\\"\\\\u05ea\\\\u05e9\\\\u05dc\\\\u05d5\\\\u05dd \\\\u05e2\\\\u05d1\\\\u05d5\\\\u05e8 \\\\u05d7\\\\u05e9\\\\u05d1\\\\u05d5\\\\u05e0\\\\u05d9\\\\u05ea \\\\u05de\\\\u05e1\\\\u05e4\\\\u05e8 52046\\\", \\\"amount\\\": 156.75, \\\"amount_excl_vat\\\": 0.0, \\\"vat_amount\\\": 0.0, \\\"vat_rate\\\": 0.0, \\\"currency\\\": \\\"ILS\\\", \\\"document_date\\\": \\\"2026-08-12\\\", \\\"due_date\\\": null, \\\"creation_date\\\": \\\"2026-08-12T14:59:16+03:00\\\", \\\"payment\\\": {\\\"method\\\": \\\"\\\\u05de\\\\u05d6\\\\u05d5\\\\u05de\\\\u05df\\\", \\\"type\\\": 1, \\\"date\\\": \\\"2026-08-12\\\", \\\"amount\\\": 156.75, \\\"bank_number\\\": null, \\\"bank_branch\\\": null, \\\"bank_account\\\": null}, \\\"line_items\\\": [], \\\"linked_document\\\": null}, {\\\"display_number\\\": \\\"52046\\\", \\\"internal_morning_id\\\": \\\"00053961-4f4c-4301-aa8c-a00ee3512b23\\\", \\\"type\\\": 305, \\\"type_name\\\": \\\"\\\\u05d7\\\\u05e9\\\\u05d1\\\\u05d5\\\\u05e0\\\\u05d9\\\\u05ea \\\\u05de\\\\u05e1\\\", \\\"status\\\": \\\"paid\\\", \\\"status_code\\\": 1, \\\"status_label\\\": \\\"\\\\u05de\\\\u05e1\\\\u05de\\\\u05da \\\\u05e1\\\\u05d2\\\\u05d5\\\\u05e8\\\", \\\"client_name\\\": \\\"\\\\u05e8\\\\u05d9\\\\u05de\\\\u05d5\\\\u05e0\\\\u05d4 \\\\u05db\\\\u05d4\\\\u05df\\\", \\\"description\\\": \\\"Ground truth fixture invoice\\\", \\\"amount\\\": 156.75, \\\"amount_excl_vat\\\": 156.75, \\\"vat_amount\\\": 0.0, \\\"vat_rate\\\": 0.0, \\\"currency\\\": \\\"ILS\\\", \\\"document_date\\\": \\\"2026-08-12\\\", \\\"due_date\\\": null, \\\"creation_date\\\": \\\"2026-08-12T14:59:03+03:00\\\", \\\"payment\\\": null, \\\"line_items\\\": [{\\\"description\\\": \\\"Ground truth fixture invoice\\\", \\\"quantity\\\": 1, \\\"price\\\": 156.75, \\\"amount\\\": 156.75}], \\\"linked_document\\\": null}]}\"}\n    (morning MCP call on this message's turn) {\"name\": \"get_invoice_details\", \"error\": null, \"arguments\": \"{\\\"internal_morning_id\\\":\\\"00053961-4f4c-4301-aa8c-a00ee3512b23\\\"}\", \"output\": \"{\\\"display_number\\\": \\\"52046\\\", \\\"internal_morning_id\\\": \\\"00053961-4f4c-4301-aa8c-a00ee3512b23\\\", \\\"type\\\": 305, \\\"type_name\\\": \\\"\\\\u05d7\\\\u05e9\\\\u05d1\\\\u05d5\\\\u05e0\\\\u05d9\\\\u05ea \\\\u05de\\\\u05e1\\\", \\\"status\\\": \\\"paid\\\", \\\"status_code\\\": 1, \\\"status_label\\\": \\\"\\\\u05de\\\\u05e1\\\\u05de\\\\u05da \\\\u05e1\\\\u05d2\\\\u05d5\\\\u05e8\\\", \\\"client_name\\\": \\\"\\\\u05e8\\\\u05d9\\\\u05de\\\\u05d5\\\\u05e0\\\\u05d4 \\\\u05db\\\\u05d4\\\\u05df\\\", \\\"description\\\": \\\"Ground truth fixture invoice\\\", \\\"amount\\\": 156.75, \\\"amount_excl_vat\\\": 156.75, \\\"vat_amount\\\": 0.0, \\\"vat_rate\\\": 0.0, \\\"currency\\\": \\\"ILS\\\", \\\"document_date\\\": \\\"2026-08-12\\\", \\\"due_date\\\": null, \\\"creation_date\\\": \\\"2026-08-12T14:59:03+03:00\\\", \\\"payment\\\": null, \\\"line_items\\\": [{\\\"description\\\": \\\"Ground truth fixture invoice\\\", \\\"quantity\\\": 1, \\\"price\\\": 156.75, \\\"amount\\\": 156.75}], \\\"linked_document\\\": {\\\"number\\\": \\\"80591\\\", \\\"type\\\": 400, \\\"type_name\\\": \\\"\\\\u05e7\\\\u05d1\\\\u05dc\\\\u05d4\\\"}}\"}\n\nTHE REPLY JUST SENT TO THE OPERATOR THIS ROUND:\nפרטי החשבונית של רימונה כהן מ־12 באוגוסט 2026:\n\n• סוג: חשבונית מס\n• מספר: 52046\n• סטטוס: סגורה ומשולמת\n• סכום כולל: 156.75 ₪\n• לפני מע״מ: 156.75 ₪\n• מע״מ: 0 ₪, בשיעור 0%\n• תאריך הפקה: 12.08.2026 בשעה 14:59\n• תאריך פירעון: לא צוין\n• פריט: חשבונית מס, כמות 1, מחיר 156.75 ₪\n\nהחשבונית נסגרה באמצעות קבלה מספר 80591:\n• אמצעי תשלום: מזומן\n• תאריך תשלום: 12.08.2026\n• סכום: 156.75 ₪\n\nMORNING MCP TOOL CALLS MADE THIS TURN (verbatim, each with its arguments and its real result):\n[\n  {\n    \"name\": \"resolve_client_name\",\n    \"error\": null,\n    \"arguments\": \"{\\\"name\\\":\\\"רימונה כהן\\\"}\",\n    \"output\": \"{\\\"status\\\": \\\"resolved\\\", \\\"name\\\": \\\"\\\\u05e8\\\\u05d9\\\\u05de\\\\u05d5\\\\u05e0\\\\u05d4 \\\\u05db\\\\u05d4\\\\u05df\\\"}\"\n  },\n  {\n    \"name\": \"list_invoices\",\n    \"error\": null,\n    \"arguments\": \"{\\\"from_date\\\":\\\"2026-08-12\\\",\\\"to_date\\\":\\\"2026-08-12\\\",\\\"client_name\\\":\\\"רימונה כהן\\\",\\\"name_resolved\\\":true}\",\n    \"output\": \"{\\\"total_matched\\\": 2, \\\"shown\\\": 2, \\\"documents\\\": [{\\\"display_number\\\": \\\"80591\\\", \\\"internal_morning_id\\\": \\\"9027b3c2-6a10-43a6-a371-55a0c8f956ef\\\", \\\"type\\\": 400, \\\"type_name\\\": \\\"\\\\u05e7\\\\u05d1\\\\u05dc\\\\u05d4\\\", \\\"status\\\": \\\"paid\\\", \\\"status_code\\\": 1, \\\"status_label\\\": \\\"\\\\u05de\\\\u05e1\\\\u05de\\\\u05da \\\\u05e1\\\\u05d2\\\\u05d5\\\\u05e8\\\", \\\"client_name\\\": \\\"\\\\u05e8\\\\u05d9\\\\u05de\\\\u05d5\\\\u05e0\\\\u05d4 \\\\u05db\\\\u05d4\\\\u05df\\\", \\\"description\\\": \\\"\\\\u05ea\\\\u05e9\\\\u05dc\\\\u05d5\\\\u05dd \\\\u05e2\\\\u05d1\\\\u05d5\\\\u05e8 \\\\u05d7\\\\u05e9\\\\u05d1\\\\u05d5\\\\u05e0\\\\u05d9\\\\u05ea \\\\u05de\\\\u05e1\\\\u05e4\\\\u05e8 52046\\\", \\\"amount\\\": 156.75, \\\"amount_excl_vat\\\": 0.0, \\\"vat_amount\\\": 0.0, \\\"vat_rate\\\": 0.0, \\\"currency\\\": \\\"ILS\\\", \\\"document_date\\\": \\\"2026-08-12\\\", \\\"due_date\\\": null, \\\"creation_date\\\": \\\"2026-08-12T14:59:16+03:00\\\", \\\"payment\\\": {\\\"method\\\": \\\"\\\\u05de\\\\u05d6\\\\u05d5\\\\u05de\\\\u05df\\\", \\\"type\\\": 1, \\\"date\\\": \\\"2026-08-12\\\", \\\"amount\\\": 156.75, \\\"bank_number\\\": null, \\\"bank_branch\\\": null, \\\"bank_account\\\": null}, \\\"line_items\\\": [], \\\"linked_document\\\": null}, {\\\"display_number\\\": \\\"52046\\\", \\\"internal_morning_id\\\": \\\"00053961-4f4c-4301-aa8c-a00ee3512b23\\\", \\\"type\\\": 305, \\\"type_name\\\": \\\"\\\\u05d7\\\\u05e9\\\\u05d1\\\\u05d5\\\\u05e0\\\\u05d9\\\\u05ea \\\\u05de\\\\u05e1\\\", \\\"status\\\": \\\"paid\\\", \\\"status_code\\\": 1, \\\"status_label\\\": \\\"\\\\u05de\\\\u05e1\\\\u05de\\\\u05da \\\\u05e1\\\\u05d2\\\\u05d5\\\\u05e8\\\", \\\"client_name\\\": \\\"\\\\u05e8\\\\u05d9\\\\u05de\\\\u05d5\\\\u05e0\\\\u05d4 \\\\u05db\\\\u05d4\\\\u05df\\\", \\\"description\\\": \\\"Ground truth fixture invoice\\\", \\\"amount\\\": 156.75, \\\"amount_excl_vat\\\": 156.75, \\\"vat_amount\\\": 0.0, \\\"vat_rate\\\": 0.0, \\\"currency\\\": \\\"ILS\\\", \\\"document_date\\\": \\\"2026-08-12\\\", \\\"due_date\\\": null, \\\"creation_date\\\": \\\"2026-08-12T14:59:03+03:00\\\", \\\"payment\\\": null, \\\"line_items\\\": [{\\\"description\\\": \\\"Ground truth fixture invoice\\\", \\\"quantity\\\": 1, \\\"price\\\": 156.75, \\\"amount\\\": 156.75}], \\\"linked_document\\\": null}]}\"\n  },\n  {\n    \"name\": \"get_invoice_details\",\n    \"error\": null,\n    \"arguments\": \"{\\\"internal_morning_id\\\":\\\"00053961-4f4c-4301-aa8c-a00ee3512b23\\\"}\",\n    \"output\": \"{\\\"display_number\\\": \\\"52046\\\", \\\"internal_morning_id\\\": \\\"00053961-4f4c-4301-aa8c-a00ee3512b23\\\", \\\"type\\\": 305, \\\"type_name\\\": \\\"\\\\u05d7\\\\u05e9\\\\u05d1\\\\u05d5\\\\u05e0\\\\u05d9\\\\u05ea \\\\u05de\\\\u05e1\\\", \\\"status\\\": \\\"paid\\\", \\\"status_code\\\": 1, \\\"status_label\\\": \\\"\\\\u05de\\\\u05e1\\\\u05de\\\\u05da \\\\u05e1\\\\u05d2\\\\u05d5\\\\u05e8\\\", \\\"client_name\\\": \\\"\\\\u05e8\\\\u05d9\\\\u05de\\\\u05d5\\\\u05e0\\\\u05d4 \\\\u05db\\\\u05d4\\\\u05df\\\", \\\"description\\\": \\\"Ground truth fixture invoice\\\", \\\"amount\\\": 156.75, \\\"amount_excl_vat\\\": 156.75, \\\"vat_amount\\\": 0.0, \\\"vat_rate\\\": 0.0, \\\"currency\\\": \\\"ILS\\\", \\\"document_date\\\": \\\"2026-08-12\\\", \\\"due_date\\\": null, \\\"creation_date\\\": \\\"2026-08-12T14:59:03+03:00\\\", \\\"payment\\\": null, \\\"line_items\\\": [{\\\"description\\\": \\\"Ground truth fixture invoice\\\", \\\"quantity\\\": 1, \\\"price\\\": 156.75, \\\"amount\\\": 156.75}], \\\"linked_document\\\": {\\\"number\\\": \\\"80591\\\", \\\"type\\\": 400, \\\"type_name\\\": \\\"\\\\u05e7\\\\u05d1\\\\u05dc\\\\u05d4\\\"}}\"\n  }\n]\n\nFollow the recognition prompt above: query the client's ledger history first when the round concerns a client, then call report_ledger_recognition exactly once with the verdict for THIS round."}
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
{"role": "user", "content": "THE CONVERSATION WINDOW (the last 1h, oldest first) - '<message_id> [<role>] <content>':\nbe052cbb-b6d3-4acd-b758-8553a77dfd04 [godfather] מה הסטטוס והפרטים המלאים של החשבונית של רימונה כהן מהשנים עשר באוגוסט?\ndf4aa56a-7280-4cd6-917a-f946be869979 [assistant] בודק את החשבונית של רימונה כהן מתאריך 12 באוגוסט.\nda5fb7c4-9719-4a82-bd1e-1e7c0b03392e [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: המשתמש ביקש סטטוס ופרטים מלאים של חשבונית עבור רימונה כהן מתאריך 12 באוגוסט.\nTHIS TURN'S PURPOSE: להפעיל את זרימת בירור החשבוניות, לזהות את הלקוחה ואת החשבונית המדויקת, ואז להציג את פרטיה וסטטוסה.\nEXPECTATION: אטען את זרימת בירור החשבוניות ואת יכולות קריאת הלקוחות והחשבוניות, ולאחר מכן אחפש את החשבונית לפי הלקוחה והתאריך.\nc34893e5-f799-486a-82de-f3d0716f2afd [assistant] מצאתי את הלקוחה; עכשיו מאתר את החשבונית מתאריך 12 באוגוסט 2026.\n05c522d2-4724-4410-ad83-652a59c76fd3 [assistant] מצאתי חשבונית מס 52046 וקבלה מקושרת; טוען עכשיו את הפרטים המלאים של החשבונית.\n36a3f04e-0c34-46fc-939d-cf579eb6f2e8 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: הושלם בירור החשבונית בזרימת בירור חשבוניות. החשבונית 52046 של רימונה כהן מתאריך 12.08.2026 נמצאה כסגורה ומשולמת, עם קבלה 80591 מקושרת.\nTHIS TURN'S PURPOSE: להציג למשתמש את הסטטוס ואת כל הפרטים הזמינים של החשבונית והקבלה המקושרת.\nEXPECTATION: אשלח תשובה מסודרת בעברית, אסמן הצלחה, ואז אסיים את הזרימה.\nb2a75309-a294-4a51-80b3-4b399d82d19a [assistant] פרטי החשבונית של רימונה כהן מ־12 באוגוסט 2026:\n\n• סוג: חשבונית מס\n• מספר: 52046\n• סטטוס: סגורה ומשולמת\n• סכום כולל: 156.75 ₪\n• לפני מע״מ: 156.75 ₪\n• מע״מ: 0 ₪, בשיעור 0%\n• תאריך הפקה: 12.08.2026 בשעה 14:59\n• תאריך פירעון: לא צוין\n• פריט: חשבונית מס, כמות 1, מחיר 156.75 ₪\n\nהחשבונית נסגרה באמצעות קבלה מספר 80591:\n• אמצעי תשלום: מזומן\n• תאריך תשלום: 12.08.2026\n• סכום: 156.75 ₪\n    (morning MCP call on this message's turn) {\"name\": \"resolve_client_name\", \"error\": null, \"arguments\": \"{\\\"name\\\":\\\"רימונה כהן\\\"}\", \"output\": \"{\\\"status\\\": \\\"resolved\\\", \\\"name\\\": \\\"\\\\u05e8\\\\u05d9\\\\u05de\\\\u05d5\\\\u05e0\\\\u05d4 \\\\u05db\\\\u05d4\\\\u05df\\\"}\"}\n    (morning MCP call on this message's turn) {\"name\": \"list_invoices\", \"error\": null, \"arguments\": \"{\\\"from_date\\\":\\\"2026-08-12\\\",\\\"to_date\\\":\\\"2026-08-12\\\",\\\"client_name\\\":\\\"רימונה כהן\\\",\\\"name_resolved\\\":true}\", \"output\": \"{\\\"total_matched\\\": 2, \\\"shown\\\": 2, \\\"documents\\\": [{\\\"display_number\\\": \\\"80591\\\", \\\"internal_morning_id\\\": \\\"9027b3c2-6a10-43a6-a371-55a0c8f956ef\\\", \\\"type\\\": 400, \\\"type_name\\\": \\\"\\\\u05e7\\\\u05d1\\\\u05dc\\\\u05d4\\\", \\\"status\\\": \\\"paid\\\", \\\"status_code\\\": 1, \\\"status_label\\\": \\\"\\\\u05de\\\\u05e1\\\\u05de\\\\u05da \\\\u05e1\\\\u05d2\\\\u05d5\\\\u05e8\\\", \\\"client_name\\\": \\\"\\\\u05e8\\\\u05d9\\\\u05de\\\\u05d5\\\\u05e0\\\\u05d4 \\\\u05db\\\\u05d4\\\\u05df\\\", \\\"description\\\": \\\"\\\\u05ea\\\\u05e9\\\\u05dc\\\\u05d5\\\\u05dd \\\\u05e2\\\\u05d1\\\\u05d5\\\\u05e8 \\\\u05d7\\\\u05e9\\\\u05d1\\\\u05d5\\\\u05e0\\\\u05d9\\\\u05ea \\\\u05de\\\\u05e1\\\\u05e4\\\\u05e8 52046\\\", \\\"amount\\\": 156.75, \\\"amount_excl_vat\\\": 0.0, \\\"vat_amount\\\": 0.0, \\\"vat_rate\\\": 0.0, \\\"currency\\\": \\\"ILS\\\", \\\"document_date\\\": \\\"2026-08-12\\\", \\\"due_date\\\": null, \\\"creation_date\\\": \\\"2026-08-12T14:59:16+03:00\\\", \\\"payment\\\": {\\\"method\\\": \\\"\\\\u05de\\\\u05d6\\\\u05d5\\\\u05de\\\\u05df\\\", \\\"type\\\": 1, \\\"date\\\": \\\"2026-08-12\\\", \\\"amount\\\": 156.75, \\\"bank_number\\\": null, \\\"bank_branch\\\": null, \\\"bank_account\\\": null}, \\\"line_items\\\": [], \\\"linked_document\\\": null}, {\\\"display_number\\\": \\\"52046\\\", \\\"internal_morning_id\\\": \\\"00053961-4f4c-4301-aa8c-a00ee3512b23\\\", \\\"type\\\": 305, \\\"type_name\\\": \\\"\\\\u05d7\\\\u05e9\\\\u05d1\\\\u05d5\\\\u05e0\\\\u05d9\\\\u05ea \\\\u05de\\\\u05e1\\\", \\\"status\\\": \\\"paid\\\", \\\"status_code\\\": 1, \\\"status_label\\\": \\\"\\\\u05de\\\\u05e1\\\\u05de\\\\u05da \\\\u05e1\\\\u05d2\\\\u05d5\\\\u05e8\\\", \\\"client_name\\\": \\\"\\\\u05e8\\\\u05d9\\\\u05de\\\\u05d5\\\\u05e0\\\\u05d4 \\\\u05db\\\\u05d4\\\\u05df\\\", \\\"description\\\": \\\"Ground truth fixture invoice\\\", \\\"amount\\\": 156.75, \\\"amount_excl_vat\\\": 156.75, \\\"vat_amount\\\": 0.0, \\\"vat_rate\\\": 0.0, \\\"currency\\\": \\\"ILS\\\", \\\"document_date\\\": \\\"2026-08-12\\\", \\\"due_date\\\": null, \\\"creation_date\\\": \\\"2026-08-12T14:59:03+03:00\\\", \\\"payment\\\": null, \\\"line_items\\\": [{\\\"description\\\": \\\"Ground truth fixture invoice\\\", \\\"quantity\\\": 1, \\\"price\\\": 156.75, \\\"amount\\\": 156.75}], \\\"linked_document\\\": null}]}\"}\n    (morning MCP call on this message's turn) {\"name\": \"get_invoice_details\", \"error\": null, \"arguments\": \"{\\\"internal_morning_id\\\":\\\"00053961-4f4c-4301-aa8c-a00ee3512b23\\\"}\", \"output\": \"{\\\"display_number\\\": \\\"52046\\\", \\\"internal_morning_id\\\": \\\"00053961-4f4c-4301-aa8c-a00ee3512b23\\\", \\\"type\\\": 305, \\\"type_name\\\": \\\"\\\\u05d7\\\\u05e9\\\\u05d1\\\\u05d5\\\\u05e0\\\\u05d9\\\\u05ea \\\\u05de\\\\u05e1\\\", \\\"status\\\": \\\"paid\\\", \\\"status_code\\\": 1, \\\"status_label\\\": \\\"\\\\u05de\\\\u05e1\\\\u05de\\\\u05da \\\\u05e1\\\\u05d2\\\\u05d5\\\\u05e8\\\", \\\"client_name\\\": \\\"\\\\u05e8\\\\u05d9\\\\u05de\\\\u05d5\\\\u05e0\\\\u05d4 \\\\u05db\\\\u05d4\\\\u05df\\\", \\\"description\\\": \\\"Ground truth fixture invoice\\\", \\\"amount\\\": 156.75, \\\"amount_excl_vat\\\": 156.75, \\\"vat_amount\\\": 0.0, \\\"vat_rate\\\": 0.0, \\\"currency\\\": \\\"ILS\\\", \\\"document_date\\\": \\\"2026-08-12\\\", \\\"due_date\\\": null, \\\"creation_date\\\": \\\"2026-08-12T14:59:03+03:00\\\", \\\"payment\\\": null, \\\"line_items\\\": [{\\\"description\\\": \\\"Ground truth fixture invoice\\\", \\\"quantity\\\": 1, \\\"price\\\": 156.75, \\\"amount\\\": 156.75}], \\\"linked_document\\\": {\\\"number\\\": \\\"80591\\\", \\\"type\\\": 400, \\\"type_name\\\": \\\"\\\\u05e7\\\\u05d1\\\\u05dc\\\\u05d4\\\"}}\"}\n\nTHE REPLY JUST SENT TO THE OPERATOR THIS ROUND:\nפרטי החשבונית של רימונה כהן מ־12 באוגוסט 2026:\n\n• סוג: חשבונית מס\n• מספר: 52046\n• סטטוס: סגורה ומשולמת\n• סכום כולל: 156.75 ₪\n• לפני מע״מ: 156.75 ₪\n• מע״מ: 0 ₪, בשיעור 0%\n• תאריך הפקה: 12.08.2026 בשעה 14:59\n• תאריך פירעון: לא צוין\n• פריט: חשבונית מס, כמות 1, מחיר 156.75 ₪\n\nהחשבונית נסגרה באמצעות קבלה מספר 80591:\n• אמצעי תשלום: מזומן\n• תאריך תשלום: 12.08.2026\n• סכום: 156.75 ₪\n\nMORNING MCP TOOL CALLS MADE THIS TURN (verbatim, each with its arguments and its real result):\n[\n  {\n    \"name\": \"resolve_client_name\",\n    \"error\": null,\n    \"arguments\": \"{\\\"name\\\":\\\"רימונה כהן\\\"}\",\n    \"output\": \"{\\\"status\\\": \\\"resolved\\\", \\\"name\\\": \\\"\\\\u05e8\\\\u05d9\\\\u05de\\\\u05d5\\\\u05e0\\\\u05d4 \\\\u05db\\\\u05d4\\\\u05df\\\"}\"\n  },\n  {\n    \"name\": \"list_invoices\",\n    \"error\": null,\n    \"arguments\": \"{\\\"from_date\\\":\\\"2026-08-12\\\",\\\"to_date\\\":\\\"2026-08-12\\\",\\\"client_name\\\":\\\"רימונה כהן\\\",\\\"name_resolved\\\":true}\",\n    \"output\": \"{\\\"total_matched\\\": 2, \\\"shown\\\": 2, \\\"documents\\\": [{\\\"display_number\\\": \\\"80591\\\", \\\"internal_morning_id\\\": \\\"9027b3c2-6a10-43a6-a371-55a0c8f956ef\\\", \\\"type\\\": 400, \\\"type_name\\\": \\\"\\\\u05e7\\\\u05d1\\\\u05dc\\\\u05d4\\\", \\\"status\\\": \\\"paid\\\", \\\"status_code\\\": 1, \\\"status_label\\\": \\\"\\\\u05de\\\\u05e1\\\\u05de\\\\u05da \\\\u05e1\\\\u05d2\\\\u05d5\\\\u05e8\\\", \\\"client_name\\\": \\\"\\\\u05e8\\\\u05d9\\\\u05de\\\\u05d5\\\\u05e0\\\\u05d4 \\\\u05db\\\\u05d4\\\\u05df\\\", \\\"description\\\": \\\"\\\\u05ea\\\\u05e9\\\\u05dc\\\\u05d5\\\\u05dd \\\\u05e2\\\\u05d1\\\\u05d5\\\\u05e8 \\\\u05d7\\\\u05e9\\\\u05d1\\\\u05d5\\\\u05e0\\\\u05d9\\\\u05ea \\\\u05de\\\\u05e1\\\\u05e4\\\\u05e8 52046\\\", \\\"amount\\\": 156.75, \\\"amount_excl_vat\\\": 0.0, \\\"vat_amount\\\": 0.0, \\\"vat_rate\\\": 0.0, \\\"currency\\\": \\\"ILS\\\", \\\"document_date\\\": \\\"2026-08-12\\\", \\\"due_date\\\": null, \\\"creation_date\\\": \\\"2026-08-12T14:59:16+03:00\\\", \\\"payment\\\": {\\\"method\\\": \\\"\\\\u05de\\\\u05d6\\\\u05d5\\\\u05de\\\\u05df\\\", \\\"type\\\": 1, \\\"date\\\": \\\"2026-08-12\\\", \\\"amount\\\": 156.75, \\\"bank_number\\\": null, \\\"bank_branch\\\": null, \\\"bank_account\\\": null}, \\\"line_items\\\": [], \\\"linked_document\\\": null}, {\\\"display_number\\\": \\\"52046\\\", \\\"internal_morning_id\\\": \\\"00053961-4f4c-4301-aa8c-a00ee3512b23\\\", \\\"type\\\": 305, \\\"type_name\\\": \\\"\\\\u05d7\\\\u05e9\\\\u05d1\\\\u05d5\\\\u05e0\\\\u05d9\\\\u05ea \\\\u05de\\\\u05e1\\\", \\\"status\\\": \\\"paid\\\", \\\"status_code\\\": 1, \\\"status_label\\\": \\\"\\\\u05de\\\\u05e1\\\\u05de\\\\u05da \\\\u05e1\\\\u05d2\\\\u05d5\\\\u05e8\\\", \\\"client_name\\\": \\\"\\\\u05e8\\\\u05d9\\\\u05de\\\\u05d5\\\\u05e0\\\\u05d4 \\\\u05db\\\\u05d4\\\\u05df\\\", \\\"description\\\": \\\"Ground truth fixture invoice\\\", \\\"amount\\\": 156.75, \\\"amount_excl_vat\\\": 156.75, \\\"vat_amount\\\": 0.0, \\\"vat_rate\\\": 0.0, \\\"currency\\\": \\\"ILS\\\", \\\"document_date\\\": \\\"2026-08-12\\\", \\\"due_date\\\": null, \\\"creation_date\\\": \\\"2026-08-12T14:59:03+03:00\\\", \\\"payment\\\": null, \\\"line_items\\\": [{\\\"description\\\": \\\"Ground truth fixture invoice\\\", \\\"quantity\\\": 1, \\\"price\\\": 156.75, \\\"amount\\\": 156.75}], \\\"linked_document\\\": null}]}\"\n  },\n  {\n    \"name\": \"get_invoice_details\",\n    \"error\": null,\n    \"arguments\": \"{\\\"internal_morning_id\\\":\\\"00053961-4f4c-4301-aa8c-a00ee3512b23\\\"}\",\n    \"output\": \"{\\\"display_number\\\": \\\"52046\\\", \\\"internal_morning_id\\\": \\\"00053961-4f4c-4301-aa8c-a00ee3512b23\\\", \\\"type\\\": 305, \\\"type_name\\\": \\\"\\\\u05d7\\\\u05e9\\\\u05d1\\\\u05d5\\\\u05e0\\\\u05d9\\\\u05ea \\\\u05de\\\\u05e1\\\", \\\"status\\\": \\\"paid\\\", \\\"status_code\\\": 1, \\\"status_label\\\": \\\"\\\\u05de\\\\u05e1\\\\u05de\\\\u05da \\\\u05e1\\\\u05d2\\\\u05d5\\\\u05e8\\\", \\\"client_name\\\": \\\"\\\\u05e8\\\\u05d9\\\\u05de\\\\u05d5\\\\u05e0\\\\u05d4 \\\\u05db\\\\u05d4\\\\u05df\\\", \\\"description\\\": \\\"Ground truth fixture invoice\\\", \\\"amount\\\": 156.75, \\\"amount_excl_vat\\\": 156.75, \\\"vat_amount\\\": 0.0, \\\"vat_rate\\\": 0.0, \\\"currency\\\": \\\"ILS\\\", \\\"document_date\\\": \\\"2026-08-12\\\", \\\"due_date\\\": null, \\\"creation_date\\\": \\\"2026-08-12T14:59:03+03:00\\\", \\\"payment\\\": null, \\\"line_items\\\": [{\\\"description\\\": \\\"Ground truth fixture invoice\\\", \\\"quantity\\\": 1, \\\"price\\\": 156.75, \\\"amount\\\": 156.75}], \\\"linked_document\\\": {\\\"number\\\": \\\"80591\\\", \\\"type\\\": 400, \\\"type_name\\\": \\\"\\\\u05e7\\\\u05d1\\\\u05dc\\\\u05d4\\\"}}\"\n  }\n]\n\nFollow the recognition prompt above: query the client's ledger history first when the round concerns a client, then call report_ledger_recognition exactly once with the verdict for THIS round."}
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
Today's date (Israel local): 01/10/2026

POST-TURN LEDGER RECOGNITION: the operator's reply for this round has already been sent. Do not produce a reply. Your only task is to call report_ledger_recognition exactly once with the verdict for this round, after any ledger-history lookups the prompt calls for. When in doubt, verdict='none'.
```

</details>

</details>

</details>

<details>
<summary>41. [2026-10-01 17:43:24] MODEL → APP — context=recognize_ledger_event</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_00063b4b78499e03006abe718ae2c487d19c15a533a5307491`
- status: `completed`
- usage: `{"input_tokens": 11751, "input_tokens_details": {"cache_write_tokens": 3812, "cached_tokens": 7936}, "output_tokens": 60, "output_tokens_details": {"reasoning_tokens": 26}, "total_tokens": 11811}`
- reasoning item (content not user-visible)
- function_call: `query_ledger_events` call_id=`call_2vBeuV3pAuncBfMQbNuIofrr`
```json
{
  "criteria": [
    {
      "text": "רימונה כהן",
      "hint": "identity"
    }
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_00063b4b78499e03006abe718ae2c487d19c15a533a5307491`
- status: `completed`
- usage: `{"input_tokens": 11751, "input_tokens_details": {"cache_write_tokens": 3812, "cached_tokens": 7936}, "output_tokens": 60, "output_tokens_details": {"reasoning_tokens": 26}, "total_tokens": 11811}`
- reasoning item (content not user-visible)
- function_call: `query_ledger_events` call_id=`call_2vBeuV3pAuncBfMQbNuIofrr`
```json
{
  "criteria": [
    {
      "text": "רימונה כהן",
      "hint": "identity"
    }
  ]
}
```

</details>

</details>

<details>
<summary>42. [2026-10-01 17:43:24] APP → MODEL — context=recognize_ledger_event (query round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

**input:**

- app's reply to `query_ledger_events` (call_id=`call_2vBeuV3pAuncBfMQbNuIofrr`):
```text
{
  "matches": [],
  "count": 0
}
```

- tools (2): ['report_ledger_recognition', 'query_ledger_events']

- previous_response_id: `'resp_00063b4b78499e03006abe718ae2c487d19c15a533a5307491'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: ledger recognition prompt

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

**input:**

- app's reply to `query_ledger_events` (call_id=`call_2vBeuV3pAuncBfMQbNuIofrr`):
```text
{
  "matches": [],
  "count": 0
}
```

- tools (2): ['report_ledger_recognition', 'query_ledger_events']

- previous_response_id: `'resp_00063b4b78499e03006abe718ae2c487d19c15a533a5307491'`

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
Today's date (Israel local): 01/10/2026

POST-TURN LEDGER RECOGNITION: the operator's reply for this round has already been sent. Do not produce a reply. Your only task is to call report_ledger_recognition exactly once with the verdict for this round, after any ledger-history lookups the prompt calls for. When in doubt, verdict='none'.
```

</details>

</details>

</details>

<details>
<summary>43. [2026-10-01 17:43:26] MODEL → APP — context=recognize_ledger_event (query round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_00063b4b78499e03006abe718cd58087d185c2138e948bdf6f`
- status: `completed`
- usage: `{"input_tokens": 11834, "input_tokens_details": {"cache_write_tokens": 83, "cached_tokens": 11748}, "output_tokens": 45, "output_tokens_details": {"reasoning_tokens": 10}, "total_tokens": 11879}`
- reasoning item (content not user-visible)
- function_call: `report_ledger_recognition` call_id=`call_Yx7jAoGaijb1JX9V6wRXXolv`
```json
{
  "verdict": "none",
  "none_reason": "read-only Morning invoice status/details question"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_00063b4b78499e03006abe718cd58087d185c2138e948bdf6f`
- status: `completed`
- usage: `{"input_tokens": 11834, "input_tokens_details": {"cache_write_tokens": 83, "cached_tokens": 11748}, "output_tokens": 45, "output_tokens_details": {"reasoning_tokens": 10}, "total_tokens": 11879}`
- reasoning item (content not user-visible)
- function_call: `report_ledger_recognition` call_id=`call_Yx7jAoGaijb1JX9V6wRXXolv`
```json
{
  "verdict": "none",
  "none_reason": "read-only Morning invoice status/details question"
}
```

</details>

</details>

