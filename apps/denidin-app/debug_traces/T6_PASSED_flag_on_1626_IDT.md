# Wire trace

Each numbered section below is one wire-crossing event, in strict chronological order (the number always goes up by 1, regardless of which boundary/direction it is). Click a section to expand it. Each has exactly two sub-sections, marked `↳` - Audit (concise) and Debug (full, verbatim) - and, inside Debug only, the long `instructions` text nests one level deeper, marked `↳↳`.

<details>
<summary>1. [2026-09-30 16:26:30] USER → APP — context=webhook</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "typeWebhook": "incomingMessageReceived",
  "idMessage": "billed_lq_t010_hours_client_2f05b555",
  "timestamp": 1790774790,
  "senderData": {
    "chatId": "+972501234567_t010_hours_client_e3cbe0@c.us",
    "sender": "+972501234567",
    "senderName": "Test Godfather"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {
      "textMessage": "כמה שעות אני צריך לחייב את מיכל רוזן בחודש שעבר?"
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
  "idMessage": "billed_lq_t010_hours_client_2f05b555",
  "timestamp": 1790774790,
  "senderData": {
    "chatId": "+972501234567_t010_hours_client_e3cbe0@c.us",
    "sender": "+972501234567",
    "senderName": "Test Godfather"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {
      "textMessage": "כמה שעות אני צריך לחייב את מיכל רוזן בחודש שעבר?"
    }
  }
}
```

</details>

</details>

<details>
<summary>2. [2026-09-30 16:26:33] APP → MODEL — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

```json
{"role": "user", "content": "כמה שעות אני צריך לחייב את מיכל רוזן בחודש שעבר?"}
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
{"role": "user", "content": "כמה שעות אני צריך לחייב את מיכל רוזן בחודש שעבר?"}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19015 chars)</summary>

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
content yet, only that it exists. Before answering anything about it, load
`cap_media_analysis` and call its `analyze_media` tool to read it; any text after
the marker is the user's caption. Never describe, guess at, or act on the file's
content without having read it this way.

## Group Conversation Etiquette
DeniDin is addressed by default in a group, same as a 1:1 chat. When a message
clearly names someone else and isn't meant for you, reply with the literal
sentinel `[[NO_REPLY]]` instead of a substantive answer — never guess when it's
genuinely ambiguous whether you were addressed.

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
  it in a group when a message clearly names someone else and is not meant for
  you. When it is genuinely unclear whether you were addressed, do not guess.
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

THE CURRENT DATE AND TIME IS 2026-09-30 16:26 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>3. [2026-09-30 16:26:38] MODEL → APP — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e0a390887d1bd9674747edbce88`
- status: `completed`
- usage: `{"input_tokens": 5929, "input_tokens_details": {"cache_write_tokens": 5926, "cached_tokens": 0}, "output_tokens": 213, "output_tokens_details": {"reasoning_tokens": 81}, "total_tokens": 6142}`
- reasoning item (content not user-visible)
- function_call: `record_planning_status` call_id=`call_nC19j6ywkC5kODCrBmH3dvFQ`
```json
{
  "where_i_was": "התקבלה שאלה על מספר השעות לחיוב של מיכל רוזן בחודש שעבר. עדיין לא בוצעה בדיקה.",
  "this_turns_purpose": "לבדוק את הנתונים הקיימים לגבי מיכל רוזן ולחשב כמה שעות יש לחייב עבור החודש הקודם.",
  "expectation": "אטען את זרימת שאלות המשתמש ואת יכולות הנתונים הדרושות, אבדוק את הרשומות ואחזיר מספר שעות או אציין אם חסר מידע."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e0a390887d1bd9674747edbce88`
- status: `completed`
- usage: `{"input_tokens": 5929, "input_tokens_details": {"cache_write_tokens": 5926, "cached_tokens": 0}, "output_tokens": 213, "output_tokens_details": {"reasoning_tokens": 81}, "total_tokens": 6142}`
- reasoning item (content not user-visible)
- function_call: `record_planning_status` call_id=`call_nC19j6ywkC5kODCrBmH3dvFQ`
```json
{
  "where_i_was": "התקבלה שאלה על מספר השעות לחיוב של מיכל רוזן בחודש שעבר. עדיין לא בוצעה בדיקה.",
  "this_turns_purpose": "לבדוק את הנתונים הקיימים לגבי מיכל רוזן ולחשב כמה שעות יש לחייב עבור החודש הקודם.",
  "expectation": "אטען את זרימת שאלות המשתמש ואת יכולות הנתונים הדרושות, אבדוק את הרשומות ואחזיר מספר שעות או אציין אם חסר מידע."
}
```

</details>

</details>

<details>
<summary>4. [2026-09-30 16:26:38] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `record_planning_status` (call_id=`call_nC19j6ywkC5kODCrBmH3dvFQ`):
```text
recorded
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e0a390887d1bd9674747edbce88'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `record_planning_status` (call_id=`call_nC19j6ywkC5kODCrBmH3dvFQ`):
```text
recorded
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e0a390887d1bd9674747edbce88'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19015 chars)</summary>

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
content yet, only that it exists. Before answering anything about it, load
`cap_media_analysis` and call its `analyze_media` tool to read it; any text after
the marker is the user's caption. Never describe, guess at, or act on the file's
content without having read it this way.

## Group Conversation Etiquette
DeniDin is addressed by default in a group, same as a 1:1 chat. When a message
clearly names someone else and isn't meant for you, reply with the literal
sentinel `[[NO_REPLY]]` instead of a substantive answer — never guess when it's
genuinely ambiguous whether you were addressed.

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
  it in a group when a message clearly names someone else and is not meant for
  you. When it is genuinely unclear whether you were addressed, do not guess.
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

THE CURRENT DATE AND TIME IS 2026-09-30 16:26 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>5. [2026-09-30 16:26:40] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e0edea487d1a9766f52f2c336a0`
- status: `completed`
- usage: `{"input_tokens": 6157, "input_tokens_details": {"cache_write_tokens": 228, "cached_tokens": 5926}, "output_tokens": 36, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6193}`
- function_call: `send_progress_update` call_id=`call_xFsT7rUYggpQSRFHLGWCiyZ3`
```json
{
  "text": "בודק את הרשומות של מיכל רוזן עבור החודש שעבר."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e0edea487d1a9766f52f2c336a0`
- status: `completed`
- usage: `{"input_tokens": 6157, "input_tokens_details": {"cache_write_tokens": 228, "cached_tokens": 5926}, "output_tokens": 36, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6193}`
- function_call: `send_progress_update` call_id=`call_xFsT7rUYggpQSRFHLGWCiyZ3`
```json
{
  "text": "בודק את הרשומות של מיכל רוזן עבור החודש שעבר."
}
```

</details>

</details>

<details>
<summary>6. [2026-09-30 16:26:40] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567_t010_hours_client_e3cbe0@c.us",
  "message": "בודק את הרשומות של מיכל רוזן עבור החודש שעבר."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "+972501234567_t010_hours_client_e3cbe0@c.us",
  "message": "בודק את הרשומות של מיכל רוזן עבור החודש שעבר."
}
```

</details>

</details>

<details>
<summary>7. [2026-09-30 16:26:40] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567_t010_hours_client_e3cbe0@c.us",
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
<summary>8. [2026-09-30 16:26:40] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `send_progress_update` (call_id=`call_xFsT7rUYggpQSRFHLGWCiyZ3`):
```text
{
  "sent": true
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e0edea487d1a9766f52f2c336a0'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `send_progress_update` (call_id=`call_xFsT7rUYggpQSRFHLGWCiyZ3`):
```text
{
  "sent": true
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e0edea487d1a9766f52f2c336a0'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19015 chars)</summary>

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
content yet, only that it exists. Before answering anything about it, load
`cap_media_analysis` and call its `analyze_media` tool to read it; any text after
the marker is the user's caption. Never describe, guess at, or act on the file's
content without having read it this way.

## Group Conversation Etiquette
DeniDin is addressed by default in a group, same as a 1:1 chat. When a message
clearly names someone else and isn't meant for you, reply with the literal
sentinel `[[NO_REPLY]]` instead of a substantive answer — never guess when it's
genuinely ambiguous whether you were addressed.

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
  it in a group when a message clearly names someone else and is not meant for
  you. When it is genuinely unclear whether you were addressed, do not guess.
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

THE CURRENT DATE AND TIME IS 2026-09-30 16:26 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>9. [2026-09-30 16:26:42] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e10f00887d19117d71d099be2f9`
- status: `completed`
- usage: `{"input_tokens": 6210, "input_tokens_details": {"cache_write_tokens": 53, "cached_tokens": 6154}, "output_tokens": 22, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6232}`
- function_call: `load_flows` call_id=`call_q85n0ZIHHK5e3FWiFawLjhtW`
```json
{
  "flows": [
    "flow_user_question"
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e10f00887d19117d71d099be2f9`
- status: `completed`
- usage: `{"input_tokens": 6210, "input_tokens_details": {"cache_write_tokens": 53, "cached_tokens": 6154}, "output_tokens": 22, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6232}`
- function_call: `load_flows` call_id=`call_q85n0ZIHHK5e3FWiFawLjhtW`
```json
{
  "flows": [
    "flow_user_question"
  ]
}
```

</details>

</details>

<details>
<summary>10. [2026-09-30 16:26:42] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_user_question

- capabilities: (none - plain backbone)

**input:**

- app's reply to `load_flows` (call_id=`call_q85n0ZIHHK5e3FWiFawLjhtW`):
```text
loaded flows: flow_user_question. Loaded flows now: flow_user_question. Loaded capabilities now: (none). Their blueprint text is attached starting now.
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e10f00887d19117d71d099be2f9'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_user_question, capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_user_question

- capabilities: (none - plain backbone)

**input:**

- app's reply to `load_flows` (call_id=`call_q85n0ZIHHK5e3FWiFawLjhtW`):
```text
loaded flows: flow_user_question. Loaded flows now: flow_user_question. Loaded capabilities now: (none). Their blueprint text is attached starting now.
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e10f00887d19117d71d099be2f9'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (20895 chars)</summary>

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
content yet, only that it exists. Before answering anything about it, load
`cap_media_analysis` and call its `analyze_media` tool to read it; any text after
the marker is the user's caption. Never describe, guess at, or act on the file's
content without having read it this way.

## Group Conversation Etiquette
DeniDin is addressed by default in a group, same as a 1:1 chat. When a message
clearly names someone else and isn't meant for you, reply with the literal
sentinel `[[NO_REPLY]]` instead of a substantive answer — never guess when it's
genuinely ambiguous whether you were addressed.

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
  it in a group when a message clearly names someone else and is not meant for
  you. When it is genuinely unclear whether you were addressed, do not guess.
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

# Flow: User question

Goal: answer the user's question about their clients, past agreements, deposits, or amounts owed and paid, using the read capabilities.

Capabilities: `cap_ledger_query`, `cap_client_read`.
Flows it may load: `flow_invoicing_query`.

Follow these steps in order, to the letter.

1. Decide where the answer lives, and load only what you need:
   - Questions about past agreements, deposits, or how much a client or payer owes or has paid: start with `cap_ledger_query`. It is a fast cache over Morning and also covers agreement-level amounts that Morning cannot see.
   - A live document's own status, recent documents, a download link, or a financial summary: go straight to `flow_invoicing_query`. Skip the ledger for anything only Morning holds.
   - A client's own details or a list of clients: `cap_client_read`.
2. A ledger search that finds nothing is not proof that nothing exists; it may be a cache miss. If the question is about something Morning could hold (an invoice, receipt or other document), check Morning through `flow_invoicing_query` before saying nothing was found. This does NOT apply to agreements and bank events, which never exist in Morning; for those, no match is a real "not found".
3. If the name matches several clients or events, use `cap_send_to_user` to say so and ask which one; never pick one silently.
4. Aggregation (sums, owed against received) is your own work over the returned data. Say which items you counted, and keep the reply usable: prefer counts, groups and a total over a long list.
5. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
6. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_ledger_query`, `flow_invoicing_query`, `cap_client_read` and this flow, keeping any that other work still in progress needs.


## Loaded flows

flow_user_question

## Loaded capabilities

(none - plain backbone)

---

THE CURRENT DATE AND TIME IS 2026-09-30 16:26 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>11. [2026-09-30 16:26:45] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e12d1b887d18b74e6b4aa0b7e13`
- status: `completed`
- usage: `{"input_tokens": 6696, "input_tokens_details": {"cache_write_tokens": 6693, "cached_tokens": 0}, "output_tokens": 81, "output_tokens_details": {"reasoning_tokens": 51}, "total_tokens": 6777}`
- reasoning item (content not user-visible)
- function_call: `load_capabilities` call_id=`call_KKXFFrq9j9zs7nVgQmNfQs0E`
```json
{
  "capabilities": [
    "cap_ledger_query",
    "cap_client_read"
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e12d1b887d18b74e6b4aa0b7e13`
- status: `completed`
- usage: `{"input_tokens": 6696, "input_tokens_details": {"cache_write_tokens": 6693, "cached_tokens": 0}, "output_tokens": 81, "output_tokens_details": {"reasoning_tokens": 51}, "total_tokens": 6777}`
- reasoning item (content not user-visible)
- function_call: `load_capabilities` call_id=`call_KKXFFrq9j9zs7nVgQmNfQs0E`
```json
{
  "capabilities": [
    "cap_ledger_query",
    "cap_client_read"
  ]
}
```

</details>

</details>

<details>
<summary>12. [2026-09-30 16:26:45] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_user_question

- capabilities: cap_client_read, cap_ledger_query

**input:**

- app's reply to `load_capabilities` (call_id=`call_KKXFFrq9j9zs7nVgQmNfQs0E`):
```text
loaded capabilitys: cap_ledger_query, cap_client_read. Loaded flows now: flow_user_question. Loaded capabilities now: cap_ledger_query, cap_client_read. Their instructions and tools are attached starting now.
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'query_ledger_events', 'mcp']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e12d1b887d18b74e6b4aa0b7e13'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_user_question, capabilities=cap_client_read, cap_ledger_query)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_user_question

- capabilities: cap_client_read, cap_ledger_query

**input:**

- app's reply to `load_capabilities` (call_id=`call_KKXFFrq9j9zs7nVgQmNfQs0E`):
```text
loaded capabilitys: cap_ledger_query, cap_client_read. Loaded flows now: flow_user_question. Loaded capabilities now: cap_ledger_query, cap_client_read. Their instructions and tools are attached starting now.
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'query_ledger_events', 'mcp']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e12d1b887d18b74e6b4aa0b7e13'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (26147 chars)</summary>

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
content yet, only that it exists. Before answering anything about it, load
`cap_media_analysis` and call its `analyze_media` tool to read it; any text after
the marker is the user's caption. Never describe, guess at, or act on the file's
content without having read it this way.

## Group Conversation Etiquette
DeniDin is addressed by default in a group, same as a 1:1 chat. When a message
clearly names someone else and isn't meant for you, reply with the literal
sentinel `[[NO_REPLY]]` instead of a substantive answer — never guess when it's
genuinely ambiguous whether you were addressed.

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
  it in a group when a message clearly names someone else and is not meant for
  you. When it is genuinely unclear whether you were addressed, do not guess.
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

# Flow: User question

Goal: answer the user's question about their clients, past agreements, deposits, or amounts owed and paid, using the read capabilities.

Capabilities: `cap_ledger_query`, `cap_client_read`.
Flows it may load: `flow_invoicing_query`.

Follow these steps in order, to the letter.

1. Decide where the answer lives, and load only what you need:
   - Questions about past agreements, deposits, or how much a client or payer owes or has paid: start with `cap_ledger_query`. It is a fast cache over Morning and also covers agreement-level amounts that Morning cannot see.
   - A live document's own status, recent documents, a download link, or a financial summary: go straight to `flow_invoicing_query`. Skip the ledger for anything only Morning holds.
   - A client's own details or a list of clients: `cap_client_read`.
2. A ledger search that finds nothing is not proof that nothing exists; it may be a cache miss. If the question is about something Morning could hold (an invoice, receipt or other document), check Morning through `flow_invoicing_query` before saying nothing was found. This does NOT apply to agreements and bank events, which never exist in Morning; for those, no match is a real "not found".
3. If the name matches several clients or events, use `cap_send_to_user` to say so and ask which one; never pick one silently.
4. Aggregation (sums, owed against received) is your own work over the returned data. Say which items you counted, and keep the reply usable: prefer counts, groups and a total over a long list.
5. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
6. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_ledger_query`, `flow_invoicing_query`, `cap_client_read` and this flow, keeping any that other work still in progress needs.


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


# Capability: Ledger Query (godfather/admin only)

You have one read-only tool, `query_ledger_events`, over previously captured ledger
events (fee agreements, bank deposits, and synced Morning accounting documents). The
ledger is a **cache over Morning**, not a second source of truth: some things exist
only in Morning (a download link or PDF, live status), and agreement and bank events
exist only in the ledger.

## Searching: one unified `criteria` list, always broad, never a hard filter

`criteria` is a list of `{text, hint}` pairs, one per distinct fact. Every
criterion searches every field — there's no way to restrict to one field. A
number is compared as a real number (exact); other text is typo-tolerant,
not meaning-based — resolve obvious fuzziness yourself first (a month name
becomes "2026-08"). `hint` is a soft nudge only, never a filter: `identity`,
`date`, `event_type`, `vat`, `amount`, `percentage`, `free_text`, `document`,
`banking`. **Any time-scoped question always needs a separate `date`-hinted
criterion** — the tool applies no date filtering of its own. Multiple
criteria in one call are ANDed.

## Multi-round search: look, then look again

You may call the tool more than once per turn. When a question names a
specific client, search by that name FIRST (a plain `identity`-hinted
criterion, nothing else added speculatively), then let what comes back tell
you whether a follow-up call is needed and what it should narrow by.

## Ambiguous names, OR, NOT, and threshold questions

A search can genuinely match more than one distinct `client_name`/
`payer_name` — recognizing that and deciding what to do is your own
judgment: if nothing resolves which is meant, ask; if the user's own message
already resolves it, proceed; if they confirm more than one applies, combine
the results yourself.

**OR** ("X or Y"): call the tool once per alternative in the same turn and
combine the results yourself. **NOT/exclusion/threshold** ("everyone except
X", "above 50%"): there's no criteria syntax for this — call with a broad
criteria set, then apply the exclusion/threshold yourself over the returned
events' clean fields.

## Arithmetic is your job, not the tool's

The tool never sums or computes a balance — only returns raw matching
events with clean numeric fields. Do all arithmetic yourself.

## What counts as "owed" vs. "received"

Each is made up of more than one event type — never guess a single type.
Join everything **by `client_name`**.

**Owed (debit) signals** (non-exclusive — the same debt can show up as some
or all of these):
1. **Agreement** (`הסכם`) — a client can have more than one over time
   (modified/cancelled) — read the sequence and work out what's CURRENTLY
   agreed, never sum every historical one blindly.
2. **Transaction account request** (`חשבונית`, subtype חשבון עסקה, type 300).
3. **Tax invoice** (`חשבונית`, subtype חשבונית מס, type 305).

When these look like the same money (similar amount, close in time, same
client), count it **once**. When they genuinely diverge, ask the user which
figure they mean.

**Received (credit) signals** (also non-exclusive):
- **Bank deposit** (`בנק`, subtype הפקדה).
- **Receipt** (`חשבונית`, subtype 320 or 400).

The same payment normally produces BOTH — same client + same amount means
the same payment; dedup to one before subtracting from owed.

**Cancellations**: a later `הסכם` cancelling/modifying an earlier one
(handled per point 1); a **credit note** (type 330) issued against a 320/400
receipt **subtracts from the received side**.

`Net owed per client = dedup'd(owed) − dedup'd(received, net of credit
notes)`.

## Output shape

The tool never truncates — a broad search can return hundreds of events.
Your reply must stay usable: prefer summarizing (counts, groupings, a total)
over enumerating a long list, when the result set is large.

## Scope

Never call this as your answer to an unclear/ambiguous reply that was
actually responding to something else — a bare "כן"/"לא" answers whatever
you most recently asked; re-ask in that same context instead. Never call this for a message REPORTING a new agreement or deposit; this capability only reads.
Never call with an empty `criteria` list — ask the user for the missing
identifying detail first.


## Loaded flows

flow_user_question

## Loaded capabilities

cap_client_read, cap_ledger_query

---

THE CURRENT DATE AND TIME IS 2026-09-30 16:26 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>13. [2026-09-30 16:26:49] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e15b36c87d1a8877a946f3054ad`
- status: `completed`
- usage: `{"input_tokens": 9810, "input_tokens_details": {"cache_write_tokens": 9807, "cached_tokens": 0}, "output_tokens": 64, "output_tokens_details": {"reasoning_tokens": 15}, "total_tokens": 9874}`
- mcp_list_tools (morning-invoices): ['list_clients', 'resolve_client_name', 'get_client_details']
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_XUcFBe1kEQOawHJt2Pfjx694`
```json
{
  "text": "מצאתי את זרימת הבדיקה המתאימה, ומחפש עכשיו את הרשומות הקשורות למיכל רוזן."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e15b36c87d1a8877a946f3054ad`
- status: `completed`
- usage: `{"input_tokens": 9810, "input_tokens_details": {"cache_write_tokens": 9807, "cached_tokens": 0}, "output_tokens": 64, "output_tokens_details": {"reasoning_tokens": 15}, "total_tokens": 9874}`
- mcp_list_tools (morning-invoices): ['list_clients', 'resolve_client_name', 'get_client_details']
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_XUcFBe1kEQOawHJt2Pfjx694`
```json
{
  "text": "מצאתי את זרימת הבדיקה המתאימה, ומחפש עכשיו את הרשומות הקשורות למיכל רוזן."
}
```

</details>

</details>

<details>
<summary>14. [2026-09-30 16:26:49] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567_t010_hours_client_e3cbe0@c.us",
  "message": "מצאתי את זרימת הבדיקה המתאימה, ומחפש עכשיו את הרשומות הקשורות למיכל רוזן."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "+972501234567_t010_hours_client_e3cbe0@c.us",
  "message": "מצאתי את זרימת הבדיקה המתאימה, ומחפש עכשיו את הרשומות הקשורות למיכל רוזן."
}
```

</details>

</details>

<details>
<summary>15. [2026-09-30 16:26:49] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567_t010_hours_client_e3cbe0@c.us",
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
<summary>16. [2026-09-30 16:26:49] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_user_question

- capabilities: cap_client_read, cap_ledger_query

**input:**

- app's reply to `send_progress_update` (call_id=`call_XUcFBe1kEQOawHJt2Pfjx694`):
```text
{
  "sent": true
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'query_ledger_events', 'mcp']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e15b36c87d1a8877a946f3054ad'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_user_question, capabilities=cap_client_read, cap_ledger_query)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_user_question

- capabilities: cap_client_read, cap_ledger_query

**input:**

- app's reply to `send_progress_update` (call_id=`call_XUcFBe1kEQOawHJt2Pfjx694`):
```text
{
  "sent": true
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'query_ledger_events', 'mcp']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e15b36c87d1a8877a946f3054ad'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (26147 chars)</summary>

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
content yet, only that it exists. Before answering anything about it, load
`cap_media_analysis` and call its `analyze_media` tool to read it; any text after
the marker is the user's caption. Never describe, guess at, or act on the file's
content without having read it this way.

## Group Conversation Etiquette
DeniDin is addressed by default in a group, same as a 1:1 chat. When a message
clearly names someone else and isn't meant for you, reply with the literal
sentinel `[[NO_REPLY]]` instead of a substantive answer — never guess when it's
genuinely ambiguous whether you were addressed.

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
  it in a group when a message clearly names someone else and is not meant for
  you. When it is genuinely unclear whether you were addressed, do not guess.
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

# Flow: User question

Goal: answer the user's question about their clients, past agreements, deposits, or amounts owed and paid, using the read capabilities.

Capabilities: `cap_ledger_query`, `cap_client_read`.
Flows it may load: `flow_invoicing_query`.

Follow these steps in order, to the letter.

1. Decide where the answer lives, and load only what you need:
   - Questions about past agreements, deposits, or how much a client or payer owes or has paid: start with `cap_ledger_query`. It is a fast cache over Morning and also covers agreement-level amounts that Morning cannot see.
   - A live document's own status, recent documents, a download link, or a financial summary: go straight to `flow_invoicing_query`. Skip the ledger for anything only Morning holds.
   - A client's own details or a list of clients: `cap_client_read`.
2. A ledger search that finds nothing is not proof that nothing exists; it may be a cache miss. If the question is about something Morning could hold (an invoice, receipt or other document), check Morning through `flow_invoicing_query` before saying nothing was found. This does NOT apply to agreements and bank events, which never exist in Morning; for those, no match is a real "not found".
3. If the name matches several clients or events, use `cap_send_to_user` to say so and ask which one; never pick one silently.
4. Aggregation (sums, owed against received) is your own work over the returned data. Say which items you counted, and keep the reply usable: prefer counts, groups and a total over a long list.
5. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
6. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_ledger_query`, `flow_invoicing_query`, `cap_client_read` and this flow, keeping any that other work still in progress needs.


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


# Capability: Ledger Query (godfather/admin only)

You have one read-only tool, `query_ledger_events`, over previously captured ledger
events (fee agreements, bank deposits, and synced Morning accounting documents). The
ledger is a **cache over Morning**, not a second source of truth: some things exist
only in Morning (a download link or PDF, live status), and agreement and bank events
exist only in the ledger.

## Searching: one unified `criteria` list, always broad, never a hard filter

`criteria` is a list of `{text, hint}` pairs, one per distinct fact. Every
criterion searches every field — there's no way to restrict to one field. A
number is compared as a real number (exact); other text is typo-tolerant,
not meaning-based — resolve obvious fuzziness yourself first (a month name
becomes "2026-08"). `hint` is a soft nudge only, never a filter: `identity`,
`date`, `event_type`, `vat`, `amount`, `percentage`, `free_text`, `document`,
`banking`. **Any time-scoped question always needs a separate `date`-hinted
criterion** — the tool applies no date filtering of its own. Multiple
criteria in one call are ANDed.

## Multi-round search: look, then look again

You may call the tool more than once per turn. When a question names a
specific client, search by that name FIRST (a plain `identity`-hinted
criterion, nothing else added speculatively), then let what comes back tell
you whether a follow-up call is needed and what it should narrow by.

## Ambiguous names, OR, NOT, and threshold questions

A search can genuinely match more than one distinct `client_name`/
`payer_name` — recognizing that and deciding what to do is your own
judgment: if nothing resolves which is meant, ask; if the user's own message
already resolves it, proceed; if they confirm more than one applies, combine
the results yourself.

**OR** ("X or Y"): call the tool once per alternative in the same turn and
combine the results yourself. **NOT/exclusion/threshold** ("everyone except
X", "above 50%"): there's no criteria syntax for this — call with a broad
criteria set, then apply the exclusion/threshold yourself over the returned
events' clean fields.

## Arithmetic is your job, not the tool's

The tool never sums or computes a balance — only returns raw matching
events with clean numeric fields. Do all arithmetic yourself.

## What counts as "owed" vs. "received"

Each is made up of more than one event type — never guess a single type.
Join everything **by `client_name`**.

**Owed (debit) signals** (non-exclusive — the same debt can show up as some
or all of these):
1. **Agreement** (`הסכם`) — a client can have more than one over time
   (modified/cancelled) — read the sequence and work out what's CURRENTLY
   agreed, never sum every historical one blindly.
2. **Transaction account request** (`חשבונית`, subtype חשבון עסקה, type 300).
3. **Tax invoice** (`חשבונית`, subtype חשבונית מס, type 305).

When these look like the same money (similar amount, close in time, same
client), count it **once**. When they genuinely diverge, ask the user which
figure they mean.

**Received (credit) signals** (also non-exclusive):
- **Bank deposit** (`בנק`, subtype הפקדה).
- **Receipt** (`חשבונית`, subtype 320 or 400).

The same payment normally produces BOTH — same client + same amount means
the same payment; dedup to one before subtracting from owed.

**Cancellations**: a later `הסכם` cancelling/modifying an earlier one
(handled per point 1); a **credit note** (type 330) issued against a 320/400
receipt **subtracts from the received side**.

`Net owed per client = dedup'd(owed) − dedup'd(received, net of credit
notes)`.

## Output shape

The tool never truncates — a broad search can return hundreds of events.
Your reply must stay usable: prefer summarizing (counts, groupings, a total)
over enumerating a long list, when the result set is large.

## Scope

Never call this as your answer to an unclear/ambiguous reply that was
actually responding to something else — a bare "כן"/"לא" answers whatever
you most recently asked; re-ask in that same context instead. Never call this for a message REPORTING a new agreement or deposit; this capability only reads.
Never call with an empty `criteria` list — ask the user for the missing
identifying detail first.


## Loaded flows

flow_user_question

## Loaded capabilities

cap_client_read, cap_ledger_query

---

THE CURRENT DATE AND TIME IS 2026-09-30 16:26 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>17. [2026-09-30 16:26:50] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e1960ac87d19eaf76b45d123506`
- status: `completed`
- usage: `{"input_tokens": 9892, "input_tokens_details": {"cache_write_tokens": 9889, "cached_tokens": 0}, "output_tokens": 33, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9925}`
- function_call: `query_ledger_events` call_id=`call_UaxpqGeXeAhVELez8SDKIgcl`
```json
{
  "criteria": [
    {
      "text": "מיכל רוזן",
      "hint": "identity"
    }
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e1960ac87d19eaf76b45d123506`
- status: `completed`
- usage: `{"input_tokens": 9892, "input_tokens_details": {"cache_write_tokens": 9889, "cached_tokens": 0}, "output_tokens": 33, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9925}`
- function_call: `query_ledger_events` call_id=`call_UaxpqGeXeAhVELez8SDKIgcl`
```json
{
  "criteria": [
    {
      "text": "מיכל רוזן",
      "hint": "identity"
    }
  ]
}
```

</details>

</details>

<details>
<summary>18. [2026-09-30 16:26:50] APP-INTERNAL: tool dispatch outcome</summary>

```text
[CAPABILITY-AUDIT] capability='cap_ledger_query' outcome='success' note="query_ledger_events({'criteria': [{'text': 'מיכל רוזן', 'hint': 'identity'}]})" detail='{"matches": [{"event_id": "A03082609001", "event_datetime": "03/08/2026 09:00", "source_type": "הסכם", "event_subtype": "יצירה", "client_name": "מיכל רוזן", "payer_name": null, "description": "תיאור", "amount": null, "reference": null, "agreement_id": null, "component_id": "None-בסיס", "component_label": "בסיס", "trigger_condition": null, "percent": null, "percent_base": null, "hours": 3.0, "hourly_rate": null, "txn_date": "03/08/2026", "vat_status": "לא צוין", "split_partner": null, "split_percent": null, "accounting_document_display_number": null, "accounting_document_status": null, "accounting_document_status_code": null, "accounting_document_status_label": null, "accounting_document_payment_method": null, "session_id": "s", "message_id": "t010_hc_1", "captured_at": "30/09/2026 16:26", "reference_hint": null, "bank_number": null, "bank_branch": null, "bank_account": null, "schema_version": 2, "confidence": 100.0}, {"event_id": "A14082609000", "event_datetime": "14/08/2026 09:00", "source_type": "הסכם", "event_subtype": "יצירה", "client_name": "מיכל רוזן", "payer_name": null, "description": "תיאור", "amount": null, "reference": null, "agreement_id": null, "component_id": "None-בסיס", "component_label": "בסיס", "trigger_condition": null, "percent": null, "percent_base": null, "hours": 4.0, "hourly_rate": null, "txn_date": "14/08/2026", "vat_status": "לא צוין", "split_partner": null, "split_percent": null, "accounting_document_display_number": null, "accounting_document_status": null, "accounting_document_status_code": null, "accounting_document_status_label": null, "accounting_document_payment_method": null, "session_id": "s", "message_id": "t010_hc_2", "captured_at": "30/09/2026 16:26", "reference_hint": null, "bank_number": null, "bank_branch": null, "bank_account": null, "schema_version": 2, "confidence": 100.0}, {"event_id": "A10072609000", "event_datetime": "10/07/2026 09:00", "source_type": "הסכם", "event_subtype": "יצירה", "client_name": "מיכל רוזן", "payer_name": null, "description": "תיאור", "amount": null, "reference": null, "agreement_id": null, "component_id": "None-בסיס", "component_label": "בסיס", "trigger_condition": null, "percent": null, "percent_base": null, "hours": 99.0, "hourly_rate": null, "txn_date": "10/07/2026", "vat_status": "לא צוין", "split_partner": null, "split_percent": null, "accounting_document_display_number": null, "accounting_document_status": null, "accounting_document_status_code": null, "accounting_document_status_label": null, "accounting_document_payment_method": null, "session_id": "s", "message_id": "t010_hc_decoy", "captured_at": "30/09/2026 16:26", "reference_hint": null, "bank_number": null, "bank_branch": null, "bank_account": null, "schema_version": 2, "confidence": 100.0}], "count": 3}'
```

</details>

<details>
<summary>19. [2026-09-30 16:26:50] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_user_question

- capabilities: cap_client_read, cap_ledger_query

**input:**

- app's reply to `query_ledger_events` (call_id=`call_UaxpqGeXeAhVELez8SDKIgcl`):
```text
{
  "matches": [
    {
      "event_id": "A03082609001",
      "event_datetime": "03/08/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 3.0,
      "hourly_rate": null,
      "txn_date": "03/08/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_1",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 100.0
    },
    {
      "event_id": "A14082609000",
      "event_datetime": "14/08/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 4.0,
      "hourly_rate": null,
      "txn_date": "14/08/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_2",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 100.0
    },
    {
      "event_id": "A10072609000",
      "event_datetime": "10/07/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 99.0,
      "hourly_rate": null,
      "txn_date": "10/07/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_decoy",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 100.0
    }
  ],
  "count": 3
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'query_ledger_events', 'mcp']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e1960ac87d19eaf76b45d123506'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_user_question, capabilities=cap_client_read, cap_ledger_query)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_user_question

- capabilities: cap_client_read, cap_ledger_query

**input:**

- app's reply to `query_ledger_events` (call_id=`call_UaxpqGeXeAhVELez8SDKIgcl`):
```text
{
  "matches": [
    {
      "event_id": "A03082609001",
      "event_datetime": "03/08/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 3.0,
      "hourly_rate": null,
      "txn_date": "03/08/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_1",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 100.0
    },
    {
      "event_id": "A14082609000",
      "event_datetime": "14/08/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 4.0,
      "hourly_rate": null,
      "txn_date": "14/08/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_2",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 100.0
    },
    {
      "event_id": "A10072609000",
      "event_datetime": "10/07/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 99.0,
      "hourly_rate": null,
      "txn_date": "10/07/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_decoy",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 100.0
    }
  ],
  "count": 3
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'query_ledger_events', 'mcp']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e1960ac87d19eaf76b45d123506'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (26147 chars)</summary>

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
content yet, only that it exists. Before answering anything about it, load
`cap_media_analysis` and call its `analyze_media` tool to read it; any text after
the marker is the user's caption. Never describe, guess at, or act on the file's
content without having read it this way.

## Group Conversation Etiquette
DeniDin is addressed by default in a group, same as a 1:1 chat. When a message
clearly names someone else and isn't meant for you, reply with the literal
sentinel `[[NO_REPLY]]` instead of a substantive answer — never guess when it's
genuinely ambiguous whether you were addressed.

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
  it in a group when a message clearly names someone else and is not meant for
  you. When it is genuinely unclear whether you were addressed, do not guess.
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

# Flow: User question

Goal: answer the user's question about their clients, past agreements, deposits, or amounts owed and paid, using the read capabilities.

Capabilities: `cap_ledger_query`, `cap_client_read`.
Flows it may load: `flow_invoicing_query`.

Follow these steps in order, to the letter.

1. Decide where the answer lives, and load only what you need:
   - Questions about past agreements, deposits, or how much a client or payer owes or has paid: start with `cap_ledger_query`. It is a fast cache over Morning and also covers agreement-level amounts that Morning cannot see.
   - A live document's own status, recent documents, a download link, or a financial summary: go straight to `flow_invoicing_query`. Skip the ledger for anything only Morning holds.
   - A client's own details or a list of clients: `cap_client_read`.
2. A ledger search that finds nothing is not proof that nothing exists; it may be a cache miss. If the question is about something Morning could hold (an invoice, receipt or other document), check Morning through `flow_invoicing_query` before saying nothing was found. This does NOT apply to agreements and bank events, which never exist in Morning; for those, no match is a real "not found".
3. If the name matches several clients or events, use `cap_send_to_user` to say so and ask which one; never pick one silently.
4. Aggregation (sums, owed against received) is your own work over the returned data. Say which items you counted, and keep the reply usable: prefer counts, groups and a total over a long list.
5. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
6. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_ledger_query`, `flow_invoicing_query`, `cap_client_read` and this flow, keeping any that other work still in progress needs.


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


# Capability: Ledger Query (godfather/admin only)

You have one read-only tool, `query_ledger_events`, over previously captured ledger
events (fee agreements, bank deposits, and synced Morning accounting documents). The
ledger is a **cache over Morning**, not a second source of truth: some things exist
only in Morning (a download link or PDF, live status), and agreement and bank events
exist only in the ledger.

## Searching: one unified `criteria` list, always broad, never a hard filter

`criteria` is a list of `{text, hint}` pairs, one per distinct fact. Every
criterion searches every field — there's no way to restrict to one field. A
number is compared as a real number (exact); other text is typo-tolerant,
not meaning-based — resolve obvious fuzziness yourself first (a month name
becomes "2026-08"). `hint` is a soft nudge only, never a filter: `identity`,
`date`, `event_type`, `vat`, `amount`, `percentage`, `free_text`, `document`,
`banking`. **Any time-scoped question always needs a separate `date`-hinted
criterion** — the tool applies no date filtering of its own. Multiple
criteria in one call are ANDed.

## Multi-round search: look, then look again

You may call the tool more than once per turn. When a question names a
specific client, search by that name FIRST (a plain `identity`-hinted
criterion, nothing else added speculatively), then let what comes back tell
you whether a follow-up call is needed and what it should narrow by.

## Ambiguous names, OR, NOT, and threshold questions

A search can genuinely match more than one distinct `client_name`/
`payer_name` — recognizing that and deciding what to do is your own
judgment: if nothing resolves which is meant, ask; if the user's own message
already resolves it, proceed; if they confirm more than one applies, combine
the results yourself.

**OR** ("X or Y"): call the tool once per alternative in the same turn and
combine the results yourself. **NOT/exclusion/threshold** ("everyone except
X", "above 50%"): there's no criteria syntax for this — call with a broad
criteria set, then apply the exclusion/threshold yourself over the returned
events' clean fields.

## Arithmetic is your job, not the tool's

The tool never sums or computes a balance — only returns raw matching
events with clean numeric fields. Do all arithmetic yourself.

## What counts as "owed" vs. "received"

Each is made up of more than one event type — never guess a single type.
Join everything **by `client_name`**.

**Owed (debit) signals** (non-exclusive — the same debt can show up as some
or all of these):
1. **Agreement** (`הסכם`) — a client can have more than one over time
   (modified/cancelled) — read the sequence and work out what's CURRENTLY
   agreed, never sum every historical one blindly.
2. **Transaction account request** (`חשבונית`, subtype חשבון עסקה, type 300).
3. **Tax invoice** (`חשבונית`, subtype חשבונית מס, type 305).

When these look like the same money (similar amount, close in time, same
client), count it **once**. When they genuinely diverge, ask the user which
figure they mean.

**Received (credit) signals** (also non-exclusive):
- **Bank deposit** (`בנק`, subtype הפקדה).
- **Receipt** (`חשבונית`, subtype 320 or 400).

The same payment normally produces BOTH — same client + same amount means
the same payment; dedup to one before subtracting from owed.

**Cancellations**: a later `הסכם` cancelling/modifying an earlier one
(handled per point 1); a **credit note** (type 330) issued against a 320/400
receipt **subtracts from the received side**.

`Net owed per client = dedup'd(owed) − dedup'd(received, net of credit
notes)`.

## Output shape

The tool never truncates — a broad search can return hundreds of events.
Your reply must stay usable: prefer summarizing (counts, groupings, a total)
over enumerating a long list, when the result set is large.

## Scope

Never call this as your answer to an unclear/ambiguous reply that was
actually responding to something else — a bare "כן"/"לא" answers whatever
you most recently asked; re-ask in that same context instead. Never call this for a message REPORTING a new agreement or deposit; this capability only reads.
Never call with an empty `criteria` list — ask the user for the missing
identifying detail first.


## Loaded flows

flow_user_question

## Loaded capabilities

cap_client_read, cap_ledger_query

---

THE CURRENT DATE AND TIME IS 2026-09-30 16:26 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>20. [2026-09-30 16:26:54] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e1b4b6487d187bd2a79a8feeb71`
- status: `completed`
- usage: `{"input_tokens": 10810, "input_tokens_details": {"cache_write_tokens": 1000, "cached_tokens": 9807}, "output_tokens": 183, "output_tokens_details": {"reasoning_tokens": 130}, "total_tokens": 10993}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_o9dLvc5b6LSqCJIwPtcu6eOg`
```json
{
  "text": "נמצאו כמה הסכמים, ולכן אני מצמצם את הבדיקה לאוגוסט 2026 כדי לא לכלול רשומות מחודשים אחרים."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e1b4b6487d187bd2a79a8feeb71`
- status: `completed`
- usage: `{"input_tokens": 10810, "input_tokens_details": {"cache_write_tokens": 1000, "cached_tokens": 9807}, "output_tokens": 183, "output_tokens_details": {"reasoning_tokens": 130}, "total_tokens": 10993}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_o9dLvc5b6LSqCJIwPtcu6eOg`
```json
{
  "text": "נמצאו כמה הסכמים, ולכן אני מצמצם את הבדיקה לאוגוסט 2026 כדי לא לכלול רשומות מחודשים אחרים."
}
```

</details>

</details>

<details>
<summary>21. [2026-09-30 16:26:54] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567_t010_hours_client_e3cbe0@c.us",
  "message": "נמצאו כמה הסכמים, ולכן אני מצמצם את הבדיקה לאוגוסט 2026 כדי לא לכלול רשומות מחודשים אחרים."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "+972501234567_t010_hours_client_e3cbe0@c.us",
  "message": "נמצאו כמה הסכמים, ולכן אני מצמצם את הבדיקה לאוגוסט 2026 כדי לא לכלול רשומות מחודשים אחרים."
}
```

</details>

</details>

<details>
<summary>22. [2026-09-30 16:26:54] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567_t010_hours_client_e3cbe0@c.us",
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
<summary>23. [2026-09-30 16:26:54] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_user_question

- capabilities: cap_client_read, cap_ledger_query

**input:**

- app's reply to `send_progress_update` (call_id=`call_o9dLvc5b6LSqCJIwPtcu6eOg`):
```text
{
  "sent": true
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'query_ledger_events', 'mcp']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e1b4b6487d187bd2a79a8feeb71'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_user_question, capabilities=cap_client_read, cap_ledger_query)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_user_question

- capabilities: cap_client_read, cap_ledger_query

**input:**

- app's reply to `send_progress_update` (call_id=`call_o9dLvc5b6LSqCJIwPtcu6eOg`):
```text
{
  "sent": true
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'query_ledger_events', 'mcp']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e1b4b6487d187bd2a79a8feeb71'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (26147 chars)</summary>

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
content yet, only that it exists. Before answering anything about it, load
`cap_media_analysis` and call its `analyze_media` tool to read it; any text after
the marker is the user's caption. Never describe, guess at, or act on the file's
content without having read it this way.

## Group Conversation Etiquette
DeniDin is addressed by default in a group, same as a 1:1 chat. When a message
clearly names someone else and isn't meant for you, reply with the literal
sentinel `[[NO_REPLY]]` instead of a substantive answer — never guess when it's
genuinely ambiguous whether you were addressed.

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
  it in a group when a message clearly names someone else and is not meant for
  you. When it is genuinely unclear whether you were addressed, do not guess.
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

# Flow: User question

Goal: answer the user's question about their clients, past agreements, deposits, or amounts owed and paid, using the read capabilities.

Capabilities: `cap_ledger_query`, `cap_client_read`.
Flows it may load: `flow_invoicing_query`.

Follow these steps in order, to the letter.

1. Decide where the answer lives, and load only what you need:
   - Questions about past agreements, deposits, or how much a client or payer owes or has paid: start with `cap_ledger_query`. It is a fast cache over Morning and also covers agreement-level amounts that Morning cannot see.
   - A live document's own status, recent documents, a download link, or a financial summary: go straight to `flow_invoicing_query`. Skip the ledger for anything only Morning holds.
   - A client's own details or a list of clients: `cap_client_read`.
2. A ledger search that finds nothing is not proof that nothing exists; it may be a cache miss. If the question is about something Morning could hold (an invoice, receipt or other document), check Morning through `flow_invoicing_query` before saying nothing was found. This does NOT apply to agreements and bank events, which never exist in Morning; for those, no match is a real "not found".
3. If the name matches several clients or events, use `cap_send_to_user` to say so and ask which one; never pick one silently.
4. Aggregation (sums, owed against received) is your own work over the returned data. Say which items you counted, and keep the reply usable: prefer counts, groups and a total over a long list.
5. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
6. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_ledger_query`, `flow_invoicing_query`, `cap_client_read` and this flow, keeping any that other work still in progress needs.


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


# Capability: Ledger Query (godfather/admin only)

You have one read-only tool, `query_ledger_events`, over previously captured ledger
events (fee agreements, bank deposits, and synced Morning accounting documents). The
ledger is a **cache over Morning**, not a second source of truth: some things exist
only in Morning (a download link or PDF, live status), and agreement and bank events
exist only in the ledger.

## Searching: one unified `criteria` list, always broad, never a hard filter

`criteria` is a list of `{text, hint}` pairs, one per distinct fact. Every
criterion searches every field — there's no way to restrict to one field. A
number is compared as a real number (exact); other text is typo-tolerant,
not meaning-based — resolve obvious fuzziness yourself first (a month name
becomes "2026-08"). `hint` is a soft nudge only, never a filter: `identity`,
`date`, `event_type`, `vat`, `amount`, `percentage`, `free_text`, `document`,
`banking`. **Any time-scoped question always needs a separate `date`-hinted
criterion** — the tool applies no date filtering of its own. Multiple
criteria in one call are ANDed.

## Multi-round search: look, then look again

You may call the tool more than once per turn. When a question names a
specific client, search by that name FIRST (a plain `identity`-hinted
criterion, nothing else added speculatively), then let what comes back tell
you whether a follow-up call is needed and what it should narrow by.

## Ambiguous names, OR, NOT, and threshold questions

A search can genuinely match more than one distinct `client_name`/
`payer_name` — recognizing that and deciding what to do is your own
judgment: if nothing resolves which is meant, ask; if the user's own message
already resolves it, proceed; if they confirm more than one applies, combine
the results yourself.

**OR** ("X or Y"): call the tool once per alternative in the same turn and
combine the results yourself. **NOT/exclusion/threshold** ("everyone except
X", "above 50%"): there's no criteria syntax for this — call with a broad
criteria set, then apply the exclusion/threshold yourself over the returned
events' clean fields.

## Arithmetic is your job, not the tool's

The tool never sums or computes a balance — only returns raw matching
events with clean numeric fields. Do all arithmetic yourself.

## What counts as "owed" vs. "received"

Each is made up of more than one event type — never guess a single type.
Join everything **by `client_name`**.

**Owed (debit) signals** (non-exclusive — the same debt can show up as some
or all of these):
1. **Agreement** (`הסכם`) — a client can have more than one over time
   (modified/cancelled) — read the sequence and work out what's CURRENTLY
   agreed, never sum every historical one blindly.
2. **Transaction account request** (`חשבונית`, subtype חשבון עסקה, type 300).
3. **Tax invoice** (`חשבונית`, subtype חשבונית מס, type 305).

When these look like the same money (similar amount, close in time, same
client), count it **once**. When they genuinely diverge, ask the user which
figure they mean.

**Received (credit) signals** (also non-exclusive):
- **Bank deposit** (`בנק`, subtype הפקדה).
- **Receipt** (`חשבונית`, subtype 320 or 400).

The same payment normally produces BOTH — same client + same amount means
the same payment; dedup to one before subtracting from owed.

**Cancellations**: a later `הסכם` cancelling/modifying an earlier one
(handled per point 1); a **credit note** (type 330) issued against a 320/400
receipt **subtracts from the received side**.

`Net owed per client = dedup'd(owed) − dedup'd(received, net of credit
notes)`.

## Output shape

The tool never truncates — a broad search can return hundreds of events.
Your reply must stay usable: prefer summarizing (counts, groupings, a total)
over enumerating a long list, when the result set is large.

## Scope

Never call this as your answer to an unclear/ambiguous reply that was
actually responding to something else — a bare "כן"/"לא" answers whatever
you most recently asked; re-ask in that same context instead. Never call this for a message REPORTING a new agreement or deposit; this capability only reads.
Never call with an empty `criteria` list — ask the user for the missing
identifying detail first.


## Loaded flows

flow_user_question

## Loaded capabilities

cap_client_read, cap_ledger_query

---

THE CURRENT DATE AND TIME IS 2026-09-30 16:26 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>24. [2026-09-30 16:26:56] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e1f14a087d1b3c144b0c0a2384c`
- status: `completed`
- usage: `{"input_tokens": 11011, "input_tokens_details": {"cache_write_tokens": 1119, "cached_tokens": 9889}, "output_tokens": 44, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 11055}`
- function_call: `query_ledger_events` call_id=`call_uSePbgX4UaNMs8xIfiCjfoAa`
```json
{
  "criteria": [
    {
      "text": "מיכל רוזן",
      "hint": "identity"
    },
    {
      "text": "2026-08",
      "hint": "date"
    }
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e1f14a087d1b3c144b0c0a2384c`
- status: `completed`
- usage: `{"input_tokens": 11011, "input_tokens_details": {"cache_write_tokens": 1119, "cached_tokens": 9889}, "output_tokens": 44, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 11055}`
- function_call: `query_ledger_events` call_id=`call_uSePbgX4UaNMs8xIfiCjfoAa`
```json
{
  "criteria": [
    {
      "text": "מיכל רוזן",
      "hint": "identity"
    },
    {
      "text": "2026-08",
      "hint": "date"
    }
  ]
}
```

</details>

</details>

<details>
<summary>25. [2026-09-30 16:26:56] APP-INTERNAL: tool dispatch outcome</summary>

```text
[CAPABILITY-AUDIT] capability='cap_ledger_query' outcome='success' note="query_ledger_events({'criteria': [{'text': 'מיכל רוזן', 'hint': 'identity'}, {'text': '2026-08', 'hint': 'date'}]})" detail='{"matches": [{"event_id": "A03082609001", "event_datetime": "03/08/2026 09:00", "source_type": "הסכם", "event_subtype": "יצירה", "client_name": "מיכל רוזן", "payer_name": null, "description": "תיאור", "amount": null, "reference": null, "agreement_id": null, "component_id": "None-בסיס", "component_label": "בסיס", "trigger_condition": null, "percent": null, "percent_base": null, "hours": 3.0, "hourly_rate": null, "txn_date": "03/08/2026", "vat_status": "לא צוין", "split_partner": null, "split_percent": null, "accounting_document_display_number": null, "accounting_document_status": null, "accounting_document_status_code": null, "accounting_document_status_label": null, "accounting_document_payment_method": null, "session_id": "s", "message_id": "t010_hc_1", "captured_at": "30/09/2026 16:26", "reference_hint": null, "bank_number": null, "bank_branch": null, "bank_account": null, "schema_version": 2, "confidence": 89.6}, {"event_id": "A14082609000", "event_datetime": "14/08/2026 09:00", "source_type": "הסכם", "event_subtype": "יצירה", "client_name": "מיכל רוזן", "payer_name": null, "description": "תיאור", "amount": null, "reference": null, "agreement_id": null, "component_id": "None-בסיס", "component_label": "בסיס", "trigger_condition": null, "percent": null, "percent_base": null, "hours": 4.0, "hourly_rate": null, "txn_date": "14/08/2026", "vat_status": "לא צוין", "split_partner": null, "split_percent": null, "accounting_document_display_number": null, "accounting_document_status": null, "accounting_document_status_code": null, "accounting_document_status_label": null, "accounting_document_payment_method": null, "session_id": "s", "message_id": "t010_hc_2", "captured_at": "30/09/2026 16:26", "reference_hint": null, "bank_number": null, "bank_branch": null, "bank_account": null, "schema_version": 2, "confidence": 89.6}, {"event_id": "A10072609000", "event_datetime": "10/07/2026 09:00", "source_type": "הסכם", "event_subtype": "יצירה", "client_name": "מיכל רוזן", "payer_name": null, "description": "תיאור", "amount": null, "reference": null, "agreement_id": null, "component_id": "None-בסיס", "component_label": "בסיס", "trigger_condition": null, "percent": null, "percent_base": null, "hours": 99.0, "hourly_rate": null, "txn_date": "10/07/2026", "vat_status": "לא צוין", "split_partner": null, "split_percent": null, "accounting_document_display_number": null, "accounting_document_status": null, "accounting_document_status_code": null, "accounting_document_status_label": null, "accounting_document_payment_method": null, "session_id": "s", "message_id": "t010_hc_decoy", "captured_at": "30/09/2026 16:26", "reference_hint": null, "bank_number": null, "bank_branch": null, "bank_account": null, "schema_version": 2, "confidence": 89.6}], "count": 3}'
```

</details>

<details>
<summary>26. [2026-09-30 16:26:56] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_user_question

- capabilities: cap_client_read, cap_ledger_query

**input:**

- app's reply to `query_ledger_events` (call_id=`call_uSePbgX4UaNMs8xIfiCjfoAa`):
```text
{
  "matches": [
    {
      "event_id": "A03082609001",
      "event_datetime": "03/08/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 3.0,
      "hourly_rate": null,
      "txn_date": "03/08/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_1",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 89.6
    },
    {
      "event_id": "A14082609000",
      "event_datetime": "14/08/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 4.0,
      "hourly_rate": null,
      "txn_date": "14/08/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_2",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 89.6
    },
    {
      "event_id": "A10072609000",
      "event_datetime": "10/07/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 99.0,
      "hourly_rate": null,
      "txn_date": "10/07/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_decoy",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 89.6
    }
  ],
  "count": 3
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'query_ledger_events', 'mcp']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e1f14a087d1b3c144b0c0a2384c'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_user_question, capabilities=cap_client_read, cap_ledger_query)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_user_question

- capabilities: cap_client_read, cap_ledger_query

**input:**

- app's reply to `query_ledger_events` (call_id=`call_uSePbgX4UaNMs8xIfiCjfoAa`):
```text
{
  "matches": [
    {
      "event_id": "A03082609001",
      "event_datetime": "03/08/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 3.0,
      "hourly_rate": null,
      "txn_date": "03/08/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_1",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 89.6
    },
    {
      "event_id": "A14082609000",
      "event_datetime": "14/08/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 4.0,
      "hourly_rate": null,
      "txn_date": "14/08/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_2",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 89.6
    },
    {
      "event_id": "A10072609000",
      "event_datetime": "10/07/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 99.0,
      "hourly_rate": null,
      "txn_date": "10/07/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_decoy",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 89.6
    }
  ],
  "count": 3
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'query_ledger_events', 'mcp']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e1f14a087d1b3c144b0c0a2384c'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (26147 chars)</summary>

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
content yet, only that it exists. Before answering anything about it, load
`cap_media_analysis` and call its `analyze_media` tool to read it; any text after
the marker is the user's caption. Never describe, guess at, or act on the file's
content without having read it this way.

## Group Conversation Etiquette
DeniDin is addressed by default in a group, same as a 1:1 chat. When a message
clearly names someone else and isn't meant for you, reply with the literal
sentinel `[[NO_REPLY]]` instead of a substantive answer — never guess when it's
genuinely ambiguous whether you were addressed.

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
  it in a group when a message clearly names someone else and is not meant for
  you. When it is genuinely unclear whether you were addressed, do not guess.
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

# Flow: User question

Goal: answer the user's question about their clients, past agreements, deposits, or amounts owed and paid, using the read capabilities.

Capabilities: `cap_ledger_query`, `cap_client_read`.
Flows it may load: `flow_invoicing_query`.

Follow these steps in order, to the letter.

1. Decide where the answer lives, and load only what you need:
   - Questions about past agreements, deposits, or how much a client or payer owes or has paid: start with `cap_ledger_query`. It is a fast cache over Morning and also covers agreement-level amounts that Morning cannot see.
   - A live document's own status, recent documents, a download link, or a financial summary: go straight to `flow_invoicing_query`. Skip the ledger for anything only Morning holds.
   - A client's own details or a list of clients: `cap_client_read`.
2. A ledger search that finds nothing is not proof that nothing exists; it may be a cache miss. If the question is about something Morning could hold (an invoice, receipt or other document), check Morning through `flow_invoicing_query` before saying nothing was found. This does NOT apply to agreements and bank events, which never exist in Morning; for those, no match is a real "not found".
3. If the name matches several clients or events, use `cap_send_to_user` to say so and ask which one; never pick one silently.
4. Aggregation (sums, owed against received) is your own work over the returned data. Say which items you counted, and keep the reply usable: prefer counts, groups and a total over a long list.
5. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
6. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_ledger_query`, `flow_invoicing_query`, `cap_client_read` and this flow, keeping any that other work still in progress needs.


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


# Capability: Ledger Query (godfather/admin only)

You have one read-only tool, `query_ledger_events`, over previously captured ledger
events (fee agreements, bank deposits, and synced Morning accounting documents). The
ledger is a **cache over Morning**, not a second source of truth: some things exist
only in Morning (a download link or PDF, live status), and agreement and bank events
exist only in the ledger.

## Searching: one unified `criteria` list, always broad, never a hard filter

`criteria` is a list of `{text, hint}` pairs, one per distinct fact. Every
criterion searches every field — there's no way to restrict to one field. A
number is compared as a real number (exact); other text is typo-tolerant,
not meaning-based — resolve obvious fuzziness yourself first (a month name
becomes "2026-08"). `hint` is a soft nudge only, never a filter: `identity`,
`date`, `event_type`, `vat`, `amount`, `percentage`, `free_text`, `document`,
`banking`. **Any time-scoped question always needs a separate `date`-hinted
criterion** — the tool applies no date filtering of its own. Multiple
criteria in one call are ANDed.

## Multi-round search: look, then look again

You may call the tool more than once per turn. When a question names a
specific client, search by that name FIRST (a plain `identity`-hinted
criterion, nothing else added speculatively), then let what comes back tell
you whether a follow-up call is needed and what it should narrow by.

## Ambiguous names, OR, NOT, and threshold questions

A search can genuinely match more than one distinct `client_name`/
`payer_name` — recognizing that and deciding what to do is your own
judgment: if nothing resolves which is meant, ask; if the user's own message
already resolves it, proceed; if they confirm more than one applies, combine
the results yourself.

**OR** ("X or Y"): call the tool once per alternative in the same turn and
combine the results yourself. **NOT/exclusion/threshold** ("everyone except
X", "above 50%"): there's no criteria syntax for this — call with a broad
criteria set, then apply the exclusion/threshold yourself over the returned
events' clean fields.

## Arithmetic is your job, not the tool's

The tool never sums or computes a balance — only returns raw matching
events with clean numeric fields. Do all arithmetic yourself.

## What counts as "owed" vs. "received"

Each is made up of more than one event type — never guess a single type.
Join everything **by `client_name`**.

**Owed (debit) signals** (non-exclusive — the same debt can show up as some
or all of these):
1. **Agreement** (`הסכם`) — a client can have more than one over time
   (modified/cancelled) — read the sequence and work out what's CURRENTLY
   agreed, never sum every historical one blindly.
2. **Transaction account request** (`חשבונית`, subtype חשבון עסקה, type 300).
3. **Tax invoice** (`חשבונית`, subtype חשבונית מס, type 305).

When these look like the same money (similar amount, close in time, same
client), count it **once**. When they genuinely diverge, ask the user which
figure they mean.

**Received (credit) signals** (also non-exclusive):
- **Bank deposit** (`בנק`, subtype הפקדה).
- **Receipt** (`חשבונית`, subtype 320 or 400).

The same payment normally produces BOTH — same client + same amount means
the same payment; dedup to one before subtracting from owed.

**Cancellations**: a later `הסכם` cancelling/modifying an earlier one
(handled per point 1); a **credit note** (type 330) issued against a 320/400
receipt **subtracts from the received side**.

`Net owed per client = dedup'd(owed) − dedup'd(received, net of credit
notes)`.

## Output shape

The tool never truncates — a broad search can return hundreds of events.
Your reply must stay usable: prefer summarizing (counts, groupings, a total)
over enumerating a long list, when the result set is large.

## Scope

Never call this as your answer to an unclear/ambiguous reply that was
actually responding to something else — a bare "כן"/"לא" answers whatever
you most recently asked; re-ask in that same context instead. Never call this for a message REPORTING a new agreement or deposit; this capability only reads.
Never call with an empty `criteria` list — ask the user for the missing
identifying detail first.


## Loaded flows

flow_user_question

## Loaded capabilities

cap_client_read, cap_ledger_query

---

THE CURRENT DATE AND TIME IS 2026-09-30 16:26 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>27. [2026-09-30 16:27:01] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e20d4a887d196a4402336a9c541`
- status: `completed`
- usage: `{"input_tokens": 11940, "input_tokens_details": {"cache_write_tokens": 1130, "cached_tokens": 10807}, "output_tokens": 280, "output_tokens_details": {"reasoning_tokens": 136}, "total_tokens": 12220}`
- reasoning item (content not user-visible)
- function_call: `record_planning_status` call_id=`call_431lBX5Y1kDow1VPzcCigWiz`
```json
{
  "where_i_was": "בזרימת שאלת משתמש, בוצעו שתי בדיקות ביומן עבור מיכל רוזן. נמצאו שתי רשומות באוגוסט 2026 עם 3 ו-4 שעות, ורשומה מיולי עם 99 שעות שלא שייכת לחודש המבוקש.",
  "this_turns_purpose": "לסכם את החישוב ולהחזיר למשתמש את מספר השעות לחיוב.",
  "expectation": "אדווח על 7 שעות, תוך ציון שהחישוב מבוסס על שתי הרשומות שנמצאו באוגוסט."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e20d4a887d196a4402336a9c541`
- status: `completed`
- usage: `{"input_tokens": 11940, "input_tokens_details": {"cache_write_tokens": 1130, "cached_tokens": 10807}, "output_tokens": 280, "output_tokens_details": {"reasoning_tokens": 136}, "total_tokens": 12220}`
- reasoning item (content not user-visible)
- function_call: `record_planning_status` call_id=`call_431lBX5Y1kDow1VPzcCigWiz`
```json
{
  "where_i_was": "בזרימת שאלת משתמש, בוצעו שתי בדיקות ביומן עבור מיכל רוזן. נמצאו שתי רשומות באוגוסט 2026 עם 3 ו-4 שעות, ורשומה מיולי עם 99 שעות שלא שייכת לחודש המבוקש.",
  "this_turns_purpose": "לסכם את החישוב ולהחזיר למשתמש את מספר השעות לחיוב.",
  "expectation": "אדווח על 7 שעות, תוך ציון שהחישוב מבוסס על שתי הרשומות שנמצאו באוגוסט."
}
```

</details>

</details>

<details>
<summary>28. [2026-09-30 16:27:01] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_user_question

- capabilities: cap_client_read, cap_ledger_query

**input:**

- app's reply to `record_planning_status` (call_id=`call_431lBX5Y1kDow1VPzcCigWiz`):
```text
recorded
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'query_ledger_events', 'mcp']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e20d4a887d196a4402336a9c541'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_user_question, capabilities=cap_client_read, cap_ledger_query)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_user_question

- capabilities: cap_client_read, cap_ledger_query

**input:**

- app's reply to `record_planning_status` (call_id=`call_431lBX5Y1kDow1VPzcCigWiz`):
```text
recorded
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'query_ledger_events', 'mcp']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e20d4a887d196a4402336a9c541'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (26147 chars)</summary>

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
content yet, only that it exists. Before answering anything about it, load
`cap_media_analysis` and call its `analyze_media` tool to read it; any text after
the marker is the user's caption. Never describe, guess at, or act on the file's
content without having read it this way.

## Group Conversation Etiquette
DeniDin is addressed by default in a group, same as a 1:1 chat. When a message
clearly names someone else and isn't meant for you, reply with the literal
sentinel `[[NO_REPLY]]` instead of a substantive answer — never guess when it's
genuinely ambiguous whether you were addressed.

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
  it in a group when a message clearly names someone else and is not meant for
  you. When it is genuinely unclear whether you were addressed, do not guess.
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

# Flow: User question

Goal: answer the user's question about their clients, past agreements, deposits, or amounts owed and paid, using the read capabilities.

Capabilities: `cap_ledger_query`, `cap_client_read`.
Flows it may load: `flow_invoicing_query`.

Follow these steps in order, to the letter.

1. Decide where the answer lives, and load only what you need:
   - Questions about past agreements, deposits, or how much a client or payer owes or has paid: start with `cap_ledger_query`. It is a fast cache over Morning and also covers agreement-level amounts that Morning cannot see.
   - A live document's own status, recent documents, a download link, or a financial summary: go straight to `flow_invoicing_query`. Skip the ledger for anything only Morning holds.
   - A client's own details or a list of clients: `cap_client_read`.
2. A ledger search that finds nothing is not proof that nothing exists; it may be a cache miss. If the question is about something Morning could hold (an invoice, receipt or other document), check Morning through `flow_invoicing_query` before saying nothing was found. This does NOT apply to agreements and bank events, which never exist in Morning; for those, no match is a real "not found".
3. If the name matches several clients or events, use `cap_send_to_user` to say so and ask which one; never pick one silently.
4. Aggregation (sums, owed against received) is your own work over the returned data. Say which items you counted, and keep the reply usable: prefer counts, groups and a total over a long list.
5. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
6. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_ledger_query`, `flow_invoicing_query`, `cap_client_read` and this flow, keeping any that other work still in progress needs.


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


# Capability: Ledger Query (godfather/admin only)

You have one read-only tool, `query_ledger_events`, over previously captured ledger
events (fee agreements, bank deposits, and synced Morning accounting documents). The
ledger is a **cache over Morning**, not a second source of truth: some things exist
only in Morning (a download link or PDF, live status), and agreement and bank events
exist only in the ledger.

## Searching: one unified `criteria` list, always broad, never a hard filter

`criteria` is a list of `{text, hint}` pairs, one per distinct fact. Every
criterion searches every field — there's no way to restrict to one field. A
number is compared as a real number (exact); other text is typo-tolerant,
not meaning-based — resolve obvious fuzziness yourself first (a month name
becomes "2026-08"). `hint` is a soft nudge only, never a filter: `identity`,
`date`, `event_type`, `vat`, `amount`, `percentage`, `free_text`, `document`,
`banking`. **Any time-scoped question always needs a separate `date`-hinted
criterion** — the tool applies no date filtering of its own. Multiple
criteria in one call are ANDed.

## Multi-round search: look, then look again

You may call the tool more than once per turn. When a question names a
specific client, search by that name FIRST (a plain `identity`-hinted
criterion, nothing else added speculatively), then let what comes back tell
you whether a follow-up call is needed and what it should narrow by.

## Ambiguous names, OR, NOT, and threshold questions

A search can genuinely match more than one distinct `client_name`/
`payer_name` — recognizing that and deciding what to do is your own
judgment: if nothing resolves which is meant, ask; if the user's own message
already resolves it, proceed; if they confirm more than one applies, combine
the results yourself.

**OR** ("X or Y"): call the tool once per alternative in the same turn and
combine the results yourself. **NOT/exclusion/threshold** ("everyone except
X", "above 50%"): there's no criteria syntax for this — call with a broad
criteria set, then apply the exclusion/threshold yourself over the returned
events' clean fields.

## Arithmetic is your job, not the tool's

The tool never sums or computes a balance — only returns raw matching
events with clean numeric fields. Do all arithmetic yourself.

## What counts as "owed" vs. "received"

Each is made up of more than one event type — never guess a single type.
Join everything **by `client_name`**.

**Owed (debit) signals** (non-exclusive — the same debt can show up as some
or all of these):
1. **Agreement** (`הסכם`) — a client can have more than one over time
   (modified/cancelled) — read the sequence and work out what's CURRENTLY
   agreed, never sum every historical one blindly.
2. **Transaction account request** (`חשבונית`, subtype חשבון עסקה, type 300).
3. **Tax invoice** (`חשבונית`, subtype חשבונית מס, type 305).

When these look like the same money (similar amount, close in time, same
client), count it **once**. When they genuinely diverge, ask the user which
figure they mean.

**Received (credit) signals** (also non-exclusive):
- **Bank deposit** (`בנק`, subtype הפקדה).
- **Receipt** (`חשבונית`, subtype 320 or 400).

The same payment normally produces BOTH — same client + same amount means
the same payment; dedup to one before subtracting from owed.

**Cancellations**: a later `הסכם` cancelling/modifying an earlier one
(handled per point 1); a **credit note** (type 330) issued against a 320/400
receipt **subtracts from the received side**.

`Net owed per client = dedup'd(owed) − dedup'd(received, net of credit
notes)`.

## Output shape

The tool never truncates — a broad search can return hundreds of events.
Your reply must stay usable: prefer summarizing (counts, groupings, a total)
over enumerating a long list, when the result set is large.

## Scope

Never call this as your answer to an unclear/ambiguous reply that was
actually responding to something else — a bare "כן"/"לא" answers whatever
you most recently asked; re-ask in that same context instead. Never call this for a message REPORTING a new agreement or deposit; this capability only reads.
Never call with an empty `criteria` list — ask the user for the missing
identifying detail first.


## Loaded flows

flow_user_question

## Loaded capabilities

cap_client_read, cap_ledger_query

---

THE CURRENT DATE AND TIME IS 2026-09-30 16:26 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>29. [2026-09-30 16:27:03] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e25c7f887d1929742f0c81e0866`
- status: `completed`
- usage: `{"input_tokens": 12236, "input_tokens_details": {"cache_write_tokens": 1225, "cached_tokens": 11008}, "output_tokens": 24, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 12260}`
- function_call: `react_to_message` call_id=`call_H98GgGJOUJp4jPop831kGxRJ`
```json
{
  "emoji": "✅",
  "message_id": null
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e25c7f887d1929742f0c81e0866`
- status: `completed`
- usage: `{"input_tokens": 12236, "input_tokens_details": {"cache_write_tokens": 1225, "cached_tokens": 11008}, "output_tokens": 24, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 12260}`
- function_call: `react_to_message` call_id=`call_H98GgGJOUJp4jPop831kGxRJ`
```json
{
  "emoji": "✅",
  "message_id": null
}
```

</details>

</details>

<details>
<summary>30. [2026-09-30 16:27:03] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_user_question

- capabilities: cap_client_read, cap_ledger_query

**input:**

- app's reply to `react_to_message` (call_id=`call_H98GgGJOUJp4jPop831kGxRJ`):
```text
{
  "status": "failed"
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'query_ledger_events', 'mcp']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e25c7f887d1929742f0c81e0866'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_user_question, capabilities=cap_client_read, cap_ledger_query)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_user_question

- capabilities: cap_client_read, cap_ledger_query

**input:**

- app's reply to `react_to_message` (call_id=`call_H98GgGJOUJp4jPop831kGxRJ`):
```text
{
  "status": "failed"
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'query_ledger_events', 'mcp']

- previous_response_id: `'resp_0f2cd07cfcd6b5f2006abd0e25c7f887d1929742f0c81e0866'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (26147 chars)</summary>

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
content yet, only that it exists. Before answering anything about it, load
`cap_media_analysis` and call its `analyze_media` tool to read it; any text after
the marker is the user's caption. Never describe, guess at, or act on the file's
content without having read it this way.

## Group Conversation Etiquette
DeniDin is addressed by default in a group, same as a 1:1 chat. When a message
clearly names someone else and isn't meant for you, reply with the literal
sentinel `[[NO_REPLY]]` instead of a substantive answer — never guess when it's
genuinely ambiguous whether you were addressed.

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
  it in a group when a message clearly names someone else and is not meant for
  you. When it is genuinely unclear whether you were addressed, do not guess.
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

# Flow: User question

Goal: answer the user's question about their clients, past agreements, deposits, or amounts owed and paid, using the read capabilities.

Capabilities: `cap_ledger_query`, `cap_client_read`.
Flows it may load: `flow_invoicing_query`.

Follow these steps in order, to the letter.

1. Decide where the answer lives, and load only what you need:
   - Questions about past agreements, deposits, or how much a client or payer owes or has paid: start with `cap_ledger_query`. It is a fast cache over Morning and also covers agreement-level amounts that Morning cannot see.
   - A live document's own status, recent documents, a download link, or a financial summary: go straight to `flow_invoicing_query`. Skip the ledger for anything only Morning holds.
   - A client's own details or a list of clients: `cap_client_read`.
2. A ledger search that finds nothing is not proof that nothing exists; it may be a cache miss. If the question is about something Morning could hold (an invoice, receipt or other document), check Morning through `flow_invoicing_query` before saying nothing was found. This does NOT apply to agreements and bank events, which never exist in Morning; for those, no match is a real "not found".
3. If the name matches several clients or events, use `cap_send_to_user` to say so and ask which one; never pick one silently.
4. Aggregation (sums, owed against received) is your own work over the returned data. Say which items you counted, and keep the reply usable: prefer counts, groups and a total over a long list.
5. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
6. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_ledger_query`, `flow_invoicing_query`, `cap_client_read` and this flow, keeping any that other work still in progress needs.


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


# Capability: Ledger Query (godfather/admin only)

You have one read-only tool, `query_ledger_events`, over previously captured ledger
events (fee agreements, bank deposits, and synced Morning accounting documents). The
ledger is a **cache over Morning**, not a second source of truth: some things exist
only in Morning (a download link or PDF, live status), and agreement and bank events
exist only in the ledger.

## Searching: one unified `criteria` list, always broad, never a hard filter

`criteria` is a list of `{text, hint}` pairs, one per distinct fact. Every
criterion searches every field — there's no way to restrict to one field. A
number is compared as a real number (exact); other text is typo-tolerant,
not meaning-based — resolve obvious fuzziness yourself first (a month name
becomes "2026-08"). `hint` is a soft nudge only, never a filter: `identity`,
`date`, `event_type`, `vat`, `amount`, `percentage`, `free_text`, `document`,
`banking`. **Any time-scoped question always needs a separate `date`-hinted
criterion** — the tool applies no date filtering of its own. Multiple
criteria in one call are ANDed.

## Multi-round search: look, then look again

You may call the tool more than once per turn. When a question names a
specific client, search by that name FIRST (a plain `identity`-hinted
criterion, nothing else added speculatively), then let what comes back tell
you whether a follow-up call is needed and what it should narrow by.

## Ambiguous names, OR, NOT, and threshold questions

A search can genuinely match more than one distinct `client_name`/
`payer_name` — recognizing that and deciding what to do is your own
judgment: if nothing resolves which is meant, ask; if the user's own message
already resolves it, proceed; if they confirm more than one applies, combine
the results yourself.

**OR** ("X or Y"): call the tool once per alternative in the same turn and
combine the results yourself. **NOT/exclusion/threshold** ("everyone except
X", "above 50%"): there's no criteria syntax for this — call with a broad
criteria set, then apply the exclusion/threshold yourself over the returned
events' clean fields.

## Arithmetic is your job, not the tool's

The tool never sums or computes a balance — only returns raw matching
events with clean numeric fields. Do all arithmetic yourself.

## What counts as "owed" vs. "received"

Each is made up of more than one event type — never guess a single type.
Join everything **by `client_name`**.

**Owed (debit) signals** (non-exclusive — the same debt can show up as some
or all of these):
1. **Agreement** (`הסכם`) — a client can have more than one over time
   (modified/cancelled) — read the sequence and work out what's CURRENTLY
   agreed, never sum every historical one blindly.
2. **Transaction account request** (`חשבונית`, subtype חשבון עסקה, type 300).
3. **Tax invoice** (`חשבונית`, subtype חשבונית מס, type 305).

When these look like the same money (similar amount, close in time, same
client), count it **once**. When they genuinely diverge, ask the user which
figure they mean.

**Received (credit) signals** (also non-exclusive):
- **Bank deposit** (`בנק`, subtype הפקדה).
- **Receipt** (`חשבונית`, subtype 320 or 400).

The same payment normally produces BOTH — same client + same amount means
the same payment; dedup to one before subtracting from owed.

**Cancellations**: a later `הסכם` cancelling/modifying an earlier one
(handled per point 1); a **credit note** (type 330) issued against a 320/400
receipt **subtracts from the received side**.

`Net owed per client = dedup'd(owed) − dedup'd(received, net of credit
notes)`.

## Output shape

The tool never truncates — a broad search can return hundreds of events.
Your reply must stay usable: prefer summarizing (counts, groupings, a total)
over enumerating a long list, when the result set is large.

## Scope

Never call this as your answer to an unclear/ambiguous reply that was
actually responding to something else — a bare "כן"/"לא" answers whatever
you most recently asked; re-ask in that same context instead. Never call this for a message REPORTING a new agreement or deposit; this capability only reads.
Never call with an empty `criteria` list — ask the user for the missing
identifying detail first.


## Loaded flows

flow_user_question

## Loaded capabilities

cap_client_read, cap_ledger_query

---

THE CURRENT DATE AND TIME IS 2026-09-30 16:26 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>31. [2026-09-30 16:27:05] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e279ad487d1aab97492dcda986c`
- status: `completed`
- usage: `{"input_tokens": 12278, "input_tokens_details": {"cache_write_tokens": 42, "cached_tokens": 12233}, "output_tokens": 83, "output_tokens_details": {"reasoning_tokens": 26}, "total_tokens": 12361}`
- reasoning item (content not user-visible)
- function_call: `send_to_user` call_id=`call_L2OELRSRNoCV4C1OKUysadER`
```json
{
  "text": "לפי שתי הרשומות של מיכל רוזן באוגוסט 2026, צריך לחייב 7 שעות בסך הכל: 3 שעות ועוד 4 שעות."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f2cd07cfcd6b5f2006abd0e279ad487d1aab97492dcda986c`
- status: `completed`
- usage: `{"input_tokens": 12278, "input_tokens_details": {"cache_write_tokens": 42, "cached_tokens": 12233}, "output_tokens": 83, "output_tokens_details": {"reasoning_tokens": 26}, "total_tokens": 12361}`
- reasoning item (content not user-visible)
- function_call: `send_to_user` call_id=`call_L2OELRSRNoCV4C1OKUysadER`
```json
{
  "text": "לפי שתי הרשומות של מיכל רוזן באוגוסט 2026, צריך לחייב 7 שעות בסך הכל: 3 שעות ועוד 4 שעות."
}
```

</details>

</details>

<details>
<summary>32. [2026-09-30 16:27:05] APP → USER — context=text</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "+972501234567_t010_hours_client_e3cbe0@c.us",
  "message": "לפי שתי הרשומות של מיכל רוזן באוגוסט 2026, צריך לחייב 7 שעות בסך הכל: 3 שעות ועוד 4 שעות."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "+972501234567_t010_hours_client_e3cbe0@c.us",
  "message": "לפי שתי הרשומות של מיכל רוזן באוגוסט 2026, צריך לחייב 7 שעות בסך הכל: 3 שעות ועוד 4 שעות."
}
```

</details>

</details>

<details>
<summary>33. [2026-09-30 16:27:05] APP → MODEL — context=recognize_ledger_event</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

**input:**

```json
{"role": "user", "content": "THE CONVERSATION WINDOW (the last 1h, oldest first) - '<message_id> [<role>] <content>':\nde85c916-61b5-40c7-a618-a7d4eef22096 [godfather] כמה שעות אני צריך לחייב את מיכל רוזן בחודש שעבר?\n7e299fec-d941-4493-9397-0e21bca71ae3 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: התקבלה שאלה על מספר השעות לחיוב של מיכל רוזן בחודש שעבר. עדיין לא בוצעה בדיקה.\nTHIS TURN'S PURPOSE: לבדוק את הנתונים הקיימים לגבי מיכל רוזן ולחשב כמה שעות יש לחייב עבור החודש הקודם.\nEXPECTATION: אטען את זרימת שאלות המשתמש ואת יכולות הנתונים הדרושות, אבדוק את הרשומות ואחזיר מספר שעות או אציין אם חסר מידע.\n0832a1a9-fb6c-40db-b291-42c4f4e634ef [assistant] בודק את הרשומות של מיכל רוזן עבור החודש שעבר.\nd2f2d2be-ba10-4fb5-8d91-83ed6b62c0b6 [assistant] מצאתי את זרימת הבדיקה המתאימה, ומחפש עכשיו את הרשומות הקשורות למיכל רוזן.\n401da957-d065-49f5-b9d1-86068e0661cb [assistant] נמצאו כמה הסכמים, ולכן אני מצמצם את הבדיקה לאוגוסט 2026 כדי לא לכלול רשומות מחודשים אחרים.\n7dcace4e-a923-42dd-9a73-9b11c14b9d3b [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בזרימת שאלת משתמש, בוצעו שתי בדיקות ביומן עבור מיכל רוזן. נמצאו שתי רשומות באוגוסט 2026 עם 3 ו-4 שעות, ורשומה מיולי עם 99 שעות שלא שייכת לחודש המבוקש.\nTHIS TURN'S PURPOSE: לסכם את החישוב ולהחזיר למשתמש את מספר השעות לחיוב.\nEXPECTATION: אדווח על 7 שעות, תוך ציון שהחישוב מבוסס על שתי הרשומות שנמצאו באוגוסט.\n5b2c421c-b754-4fb1-8034-01a8c11d959a [assistant] לפי שתי הרשומות של מיכל רוזן באוגוסט 2026, צריך לחייב 7 שעות בסך הכל: 3 שעות ועוד 4 שעות.\n\nTHE REPLY JUST SENT TO THE OPERATOR THIS ROUND:\nלפי שתי הרשומות של מיכל רוזן באוגוסט 2026, צריך לחייב 7 שעות בסך הכל: 3 שעות ועוד 4 שעות.\n\nNO Morning MCP tools were called this turn.\n\nFollow the recognition prompt above: query the client's ledger history first when the round concerns a client, then call report_ledger_recognition exactly once with the verdict for THIS round."}
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
{"role": "user", "content": "THE CONVERSATION WINDOW (the last 1h, oldest first) - '<message_id> [<role>] <content>':\nde85c916-61b5-40c7-a618-a7d4eef22096 [godfather] כמה שעות אני צריך לחייב את מיכל רוזן בחודש שעבר?\n7e299fec-d941-4493-9397-0e21bca71ae3 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: התקבלה שאלה על מספר השעות לחיוב של מיכל רוזן בחודש שעבר. עדיין לא בוצעה בדיקה.\nTHIS TURN'S PURPOSE: לבדוק את הנתונים הקיימים לגבי מיכל רוזן ולחשב כמה שעות יש לחייב עבור החודש הקודם.\nEXPECTATION: אטען את זרימת שאלות המשתמש ואת יכולות הנתונים הדרושות, אבדוק את הרשומות ואחזיר מספר שעות או אציין אם חסר מידע.\n0832a1a9-fb6c-40db-b291-42c4f4e634ef [assistant] בודק את הרשומות של מיכל רוזן עבור החודש שעבר.\nd2f2d2be-ba10-4fb5-8d91-83ed6b62c0b6 [assistant] מצאתי את זרימת הבדיקה המתאימה, ומחפש עכשיו את הרשומות הקשורות למיכל רוזן.\n401da957-d065-49f5-b9d1-86068e0661cb [assistant] נמצאו כמה הסכמים, ולכן אני מצמצם את הבדיקה לאוגוסט 2026 כדי לא לכלול רשומות מחודשים אחרים.\n7dcace4e-a923-42dd-9a73-9b11c14b9d3b [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בזרימת שאלת משתמש, בוצעו שתי בדיקות ביומן עבור מיכל רוזן. נמצאו שתי רשומות באוגוסט 2026 עם 3 ו-4 שעות, ורשומה מיולי עם 99 שעות שלא שייכת לחודש המבוקש.\nTHIS TURN'S PURPOSE: לסכם את החישוב ולהחזיר למשתמש את מספר השעות לחיוב.\nEXPECTATION: אדווח על 7 שעות, תוך ציון שהחישוב מבוסס על שתי הרשומות שנמצאו באוגוסט.\n5b2c421c-b754-4fb1-8034-01a8c11d959a [assistant] לפי שתי הרשומות של מיכל רוזן באוגוסט 2026, צריך לחייב 7 שעות בסך הכל: 3 שעות ועוד 4 שעות.\n\nTHE REPLY JUST SENT TO THE OPERATOR THIS ROUND:\nלפי שתי הרשומות של מיכל רוזן באוגוסט 2026, צריך לחייב 7 שעות בסך הכל: 3 שעות ועוד 4 שעות.\n\nNO Morning MCP tools were called this turn.\n\nFollow the recognition prompt above: query the client's ledger history first when the round concerns a client, then call report_ledger_recognition exactly once with the verdict for THIS round."}
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
Today's date (Israel local): 30/09/2026

POST-TURN LEDGER RECOGNITION: the operator's reply for this round has already been sent. Do not produce a reply. Your only task is to call report_ledger_recognition exactly once with the verdict for this round, after any ledger-history lookups the prompt calls for. When in doubt, verdict='none'.
```

</details>

</details>

</details>

<details>
<summary>34. [2026-09-30 16:27:07] MODEL → APP — context=recognize_ledger_event</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_025ce619c78dba84006abd0e2a55e887d18ea1cab9a0b6881e`
- status: `completed`
- usage: `{"input_tokens": 8630, "input_tokens_details": {"cache_write_tokens": 8627, "cached_tokens": 0}, "output_tokens": 61, "output_tokens_details": {"reasoning_tokens": 26}, "total_tokens": 8691}`
- reasoning item (content not user-visible)
- function_call: `query_ledger_events` call_id=`call_GKzvHvzfJUaOUFuUt1X3mWYb`
```json
{
  "criteria": [
    {
      "text": "מיכל רוזן",
      "hint": "identity"
    }
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_025ce619c78dba84006abd0e2a55e887d18ea1cab9a0b6881e`
- status: `completed`
- usage: `{"input_tokens": 8630, "input_tokens_details": {"cache_write_tokens": 8627, "cached_tokens": 0}, "output_tokens": 61, "output_tokens_details": {"reasoning_tokens": 26}, "total_tokens": 8691}`
- reasoning item (content not user-visible)
- function_call: `query_ledger_events` call_id=`call_GKzvHvzfJUaOUFuUt1X3mWYb`
```json
{
  "criteria": [
    {
      "text": "מיכל רוזן",
      "hint": "identity"
    }
  ]
}
```

</details>

</details>

<details>
<summary>35. [2026-09-30 16:27:07] APP → MODEL — context=recognize_ledger_event (query round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

**input:**

- app's reply to `query_ledger_events` (call_id=`call_GKzvHvzfJUaOUFuUt1X3mWYb`):
```text
{
  "matches": [
    {
      "event_id": "A03082609001",
      "event_datetime": "03/08/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 3.0,
      "hourly_rate": null,
      "txn_date": "03/08/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_1",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 100.0
    },
    {
      "event_id": "A14082609000",
      "event_datetime": "14/08/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 4.0,
      "hourly_rate": null,
      "txn_date": "14/08/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_2",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 100.0
    },
    {
      "event_id": "A10072609000",
      "event_datetime": "10/07/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 99.0,
      "hourly_rate": null,
      "txn_date": "10/07/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_decoy",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 100.0
    }
  ],
  "count": 3
}
```

- tools (2): ['report_ledger_recognition', 'query_ledger_events']

- previous_response_id: `'resp_025ce619c78dba84006abd0e2a55e887d18ea1cab9a0b6881e'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: ledger recognition prompt

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

**input:**

- app's reply to `query_ledger_events` (call_id=`call_GKzvHvzfJUaOUFuUt1X3mWYb`):
```text
{
  "matches": [
    {
      "event_id": "A03082609001",
      "event_datetime": "03/08/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 3.0,
      "hourly_rate": null,
      "txn_date": "03/08/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_1",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 100.0
    },
    {
      "event_id": "A14082609000",
      "event_datetime": "14/08/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 4.0,
      "hourly_rate": null,
      "txn_date": "14/08/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_2",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 100.0
    },
    {
      "event_id": "A10072609000",
      "event_datetime": "10/07/2026 09:00",
      "source_type": "הסכם",
      "event_subtype": "יצירה",
      "client_name": "מיכל רוזן",
      "payer_name": null,
      "description": "תיאור",
      "amount": null,
      "reference": null,
      "agreement_id": null,
      "component_id": "None-בסיס",
      "component_label": "בסיס",
      "trigger_condition": null,
      "percent": null,
      "percent_base": null,
      "hours": 99.0,
      "hourly_rate": null,
      "txn_date": "10/07/2026",
      "vat_status": "לא צוין",
      "split_partner": null,
      "split_percent": null,
      "accounting_document_display_number": null,
      "accounting_document_status": null,
      "accounting_document_status_code": null,
      "accounting_document_status_label": null,
      "accounting_document_payment_method": null,
      "session_id": "s",
      "message_id": "t010_hc_decoy",
      "captured_at": "30/09/2026 16:26",
      "reference_hint": null,
      "bank_number": null,
      "bank_branch": null,
      "bank_account": null,
      "schema_version": 2,
      "confidence": 100.0
    }
  ],
  "count": 3
}
```

- tools (2): ['report_ledger_recognition', 'query_ledger_events']

- previous_response_id: `'resp_025ce619c78dba84006abd0e2a55e887d18ea1cab9a0b6881e'`

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
Today's date (Israel local): 30/09/2026

POST-TURN LEDGER RECOGNITION: the operator's reply for this round has already been sent. Do not produce a reply. Your only task is to call report_ledger_recognition exactly once with the verdict for this round, after any ledger-history lookups the prompt calls for. When in doubt, verdict='none'.
```

</details>

</details>

</details>

<details>
<summary>36. [2026-09-30 16:27:09] MODEL → APP — context=recognize_ledger_event (query round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_025ce619c78dba84006abd0e2bf61887d1ab9224674de1de00`
- status: `completed`
- usage: `{"input_tokens": 9577, "input_tokens_details": {"cache_write_tokens": 947, "cached_tokens": 8627}, "output_tokens": 41, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9618}`
- function_call: `report_ledger_recognition` call_id=`call_PDdLZ9RG59eC0n3uJzNxtMZa`
```json
{
  "verdict": "none",
  "none_reason": "read-only ledger question; no new agreement, deposit, or Morning document created"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_025ce619c78dba84006abd0e2bf61887d1ab9224674de1de00`
- status: `completed`
- usage: `{"input_tokens": 9577, "input_tokens_details": {"cache_write_tokens": 947, "cached_tokens": 8627}, "output_tokens": 41, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9618}`
- function_call: `report_ledger_recognition` call_id=`call_PDdLZ9RG59eC0n3uJzNxtMZa`
```json
{
  "verdict": "none",
  "none_reason": "read-only ledger question; no new agreement, deposit, or Morning document created"
}
```

</details>

</details>

