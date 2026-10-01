# Wire trace

Each numbered section below is one wire-crossing event, in strict chronological order (the number always goes up by 1, regardless of which boundary/direction it is). Click a section to expand it. Each has exactly two sub-sections, marked `↳` - Audit (concise) and Debug (full, verbatim) - and, inside Debug only, the long `instructions` text nests one level deeper, marked `↳↳`.

<details>
<summary>1. [2026-10-01 16:45:24] USER → APP — context=webhook</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "typeWebhook": "incomingMessageReceived",
  "timestamp": 1790862324,
  "idMessage": "LEDGER_E2E_F3_PROBE_A1_1790862324",
  "instanceData": {
    "idInstance": 7103000000,
    "wid": "972501234567@c.us",
    "typeInstance": "whatsapp"
  },
  "senderData": {
    "chatId": "972501234567@c.us",
    "sender": "972501234567@c.us",
    "senderName": "E2E Godfather"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {
      "textMessage": "פרטים על הלקוח שחר פישר"
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
  "timestamp": 1790862324,
  "idMessage": "LEDGER_E2E_F3_PROBE_A1_1790862324",
  "instanceData": {
    "idInstance": 7103000000,
    "wid": "972501234567@c.us",
    "typeInstance": "whatsapp"
  },
  "senderData": {
    "chatId": "972501234567@c.us",
    "sender": "972501234567@c.us",
    "senderName": "E2E Godfather"
  },
  "messageData": {
    "typeMessage": "textMessage",
    "textMessageData": {
      "textMessage": "פרטים על הלקוח שחר פישר"
    }
  }
}
```

</details>

</details>

<details>
<summary>2. [2026-10-01 16:45:27] APP → MODEL — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

```json
{"role": "user", "content": "פרטים על הלקוח שחר פישר"}
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
{"role": "user", "content": "פרטים על הלקוח שחר פישר"}
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

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>3. [2026-10-01 16:45:30] MODEL → APP — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0b2ffa107df043ce006abe63f796f887d1ba8dc4a26300f147`
- status: `completed`
- usage: `{"input_tokens": 5888, "input_tokens_details": {"cache_write_tokens": 5885, "cached_tokens": 0}, "output_tokens": 123, "output_tokens_details": {"reasoning_tokens": 96}, "total_tokens": 6011}`
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_94ZEZbeA64M2VZVQzjdRYR91`
```json
{
  "emoji": "👀",
  "message_id": null
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0b2ffa107df043ce006abe63f796f887d1ba8dc4a26300f147`
- status: `completed`
- usage: `{"input_tokens": 5888, "input_tokens_details": {"cache_write_tokens": 5885, "cached_tokens": 0}, "output_tokens": 123, "output_tokens_details": {"reasoning_tokens": 96}, "total_tokens": 6011}`
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_94ZEZbeA64M2VZVQzjdRYR91`
```json
{
  "emoji": "👀",
  "message_id": null
}
```

</details>

</details>

<details>
<summary>4. [2026-10-01 16:45:30] APP → USER — context=reaction — 👀 — NOT SENT (no WhatsApp bot in this run)</summary>

```text
[084] react_to_message call 'call_94ZEZbeA64M2VZVQzjdRYR91': nothing to react through (target_id='LEDGER_E2E_F3_PROBE_A1_1790862324', chat_id='972501234567@c.us', green_api_bot_set=False)
```

</details>

<details>
<summary>5. [2026-10-01 16:45:30] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `react_to_message` (call_id=`call_94ZEZbeA64M2VZVQzjdRYR91`):
```text
{
  "status": "failed"
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0b2ffa107df043ce006abe63f796f887d1ba8dc4a26300f147'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `react_to_message` (call_id=`call_94ZEZbeA64M2VZVQzjdRYR91`):
```text
{
  "status": "failed"
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0b2ffa107df043ce006abe63f796f887d1ba8dc4a26300f147'`

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

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>6. [2026-10-01 16:45:31] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0b2ffa107df043ce006abe63fa619c87d199446dc6efb057ce`
- status: `completed`
- usage: `{"input_tokens": 6029, "input_tokens_details": {"cache_write_tokens": 141, "cached_tokens": 5885}, "output_tokens": 29, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6058}`
- function_call: `send_progress_update` call_id=`call_1H23G1ddlrYrFLn8DO3Wdgou`
```json
{
  "text": "בודק את פרטי הלקוח במערכת."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0b2ffa107df043ce006abe63fa619c87d199446dc6efb057ce`
- status: `completed`
- usage: `{"input_tokens": 6029, "input_tokens_details": {"cache_write_tokens": 141, "cached_tokens": 5885}, "output_tokens": 29, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6058}`
- function_call: `send_progress_update` call_id=`call_1H23G1ddlrYrFLn8DO3Wdgou`
```json
{
  "text": "בודק את פרטי הלקוח במערכת."
}
```

</details>

</details>

<details>
<summary>7. [2026-10-01 16:45:31] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972501234567@c.us",
  "message": "בודק את פרטי הלקוח במערכת."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "972501234567@c.us",
  "message": "בודק את פרטי הלקוח במערכת."
}
```

</details>

</details>

<details>
<summary>8. [2026-10-01 16:45:31] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972501234567@c.us",
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
<summary>9. [2026-10-01 16:45:31] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `send_progress_update` (call_id=`call_1H23G1ddlrYrFLn8DO3Wdgou`):
```text
{
  "sent": true
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0b2ffa107df043ce006abe63fa619c87d199446dc6efb057ce'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `send_progress_update` (call_id=`call_1H23G1ddlrYrFLn8DO3Wdgou`):
```text
{
  "sent": true
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0b2ffa107df043ce006abe63fa619c87d199446dc6efb057ce'`

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

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>10. [2026-10-01 16:45:33] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0b2ffa107df043ce006abe63fbe4fc87d1859caf69877bcde2`
- status: `completed`
- usage: `{"input_tokens": 6075, "input_tokens_details": {"cache_write_tokens": 46, "cached_tokens": 6026}, "output_tokens": 113, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6188}`
- function_call: `record_planning_status` call_id=`call_SE4MFp6scuDyfuxjOv33ibb1`
```json
{
  "where_i_was": "הבקשה היא לאחזר את פרטי הלקוח שחר פישר. עדיין לא בוצע חיפוש.",
  "this_turns_purpose": "לאתר את הלקוח המדויק במערכת ולהחזיר את פרטיו האישיים בלבד.",
  "expectation": "אטען יכולת לקריאת לקוחות, אחפש את הלקוח, ואז אחזיר את התוצאה או אבקש הבהרה אם יש כמה התאמות."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0b2ffa107df043ce006abe63fbe4fc87d1859caf69877bcde2`
- status: `completed`
- usage: `{"input_tokens": 6075, "input_tokens_details": {"cache_write_tokens": 46, "cached_tokens": 6026}, "output_tokens": 113, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6188}`
- function_call: `record_planning_status` call_id=`call_SE4MFp6scuDyfuxjOv33ibb1`
```json
{
  "where_i_was": "הבקשה היא לאחזר את פרטי הלקוח שחר פישר. עדיין לא בוצע חיפוש.",
  "this_turns_purpose": "לאתר את הלקוח המדויק במערכת ולהחזיר את פרטיו האישיים בלבד.",
  "expectation": "אטען יכולת לקריאת לקוחות, אחפש את הלקוח, ואז אחזיר את התוצאה או אבקש הבהרה אם יש כמה התאמות."
}
```

</details>

</details>

<details>
<summary>11. [2026-10-01 16:45:33] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `record_planning_status` (call_id=`call_SE4MFp6scuDyfuxjOv33ibb1`):
```text
recorded
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0b2ffa107df043ce006abe63fbe4fc87d1859caf69877bcde2'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `record_planning_status` (call_id=`call_SE4MFp6scuDyfuxjOv33ibb1`):
```text
recorded
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0b2ffa107df043ce006abe63fbe4fc87d1859caf69877bcde2'`

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

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>12. [2026-10-01 16:45:35] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0b2ffa107df043ce006abe63fe35c087d1a8f5f1eedc259154`
- status: `completed`
- usage: `{"input_tokens": 6203, "input_tokens_details": {"cache_write_tokens": 128, "cached_tokens": 6072}, "output_tokens": 23, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6226}`
- function_call: `load_capabilities` call_id=`call_6SeBYjqM1ondTcVx1HqkoFRi`
```json
{
  "capabilities": [
    "cap_client_read"
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0b2ffa107df043ce006abe63fe35c087d1a8f5f1eedc259154`
- status: `completed`
- usage: `{"input_tokens": 6203, "input_tokens_details": {"cache_write_tokens": 128, "cached_tokens": 6072}, "output_tokens": 23, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6226}`
- function_call: `load_capabilities` call_id=`call_6SeBYjqM1ondTcVx1HqkoFRi`
```json
{
  "capabilities": [
    "cap_client_read"
  ]
}
```

</details>

</details>

<details>
<summary>13. [2026-10-01 16:45:36] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

- app's reply to `load_capabilities` (call_id=`call_6SeBYjqM1ondTcVx1HqkoFRi`):
```text
loaded capabilitys: cap_client_read. Loaded flows now: (none). Loaded capabilities now: cap_client_read. Their instructions and tools are attached starting now.
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_0b2ffa107df043ce006abe63fe35c087d1a8f5f1eedc259154'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=cap_client_read)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

- app's reply to `load_capabilities` (call_id=`call_6SeBYjqM1ondTcVx1HqkoFRi`):
```text
loaded capabilitys: cap_client_read. Loaded flows now: (none). Loaded capabilities now: cap_client_read. Their instructions and tools are attached starting now.
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_0b2ffa107df043ce006abe63fe35c087d1a8f5f1eedc259154'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19816 chars)</summary>

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

(none)

## Loaded capabilities

cap_client_read

---

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>14. [2026-10-01 16:45:39] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0b2ffa107df043ce006abe64004a6c87d1bd55295cdaa40859`
- status: `completed`
- usage: `{"input_tokens": 6842, "input_tokens_details": {"cache_write_tokens": 6839, "cached_tokens": 0}, "output_tokens": 59, "output_tokens_details": {"reasoning_tokens": 24}, "total_tokens": 6901}`
- mcp_list_tools (morning-invoices-client-read): ['list_clients', 'resolve_client_name', 'get_client_details']
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_jRi6Y31OtgJUpDbHlQCu6izs`
```json
{
  "text": "מאתר את השם המדויק כפי שהוא שמור במערכת."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0b2ffa107df043ce006abe64004a6c87d1bd55295cdaa40859`
- status: `completed`
- usage: `{"input_tokens": 6842, "input_tokens_details": {"cache_write_tokens": 6839, "cached_tokens": 0}, "output_tokens": 59, "output_tokens_details": {"reasoning_tokens": 24}, "total_tokens": 6901}`
- mcp_list_tools (morning-invoices-client-read): ['list_clients', 'resolve_client_name', 'get_client_details']
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_jRi6Y31OtgJUpDbHlQCu6izs`
```json
{
  "text": "מאתר את השם המדויק כפי שהוא שמור במערכת."
}
```

</details>

</details>

<details>
<summary>15. [2026-10-01 16:45:39] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972501234567@c.us",
  "message": "מאתר את השם המדויק כפי שהוא שמור במערכת."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "972501234567@c.us",
  "message": "מאתר את השם המדויק כפי שהוא שמור במערכת."
}
```

</details>

</details>

<details>
<summary>16. [2026-10-01 16:45:39] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972501234567@c.us",
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
<summary>17. [2026-10-01 16:45:39] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

- app's reply to `send_progress_update` (call_id=`call_jRi6Y31OtgJUpDbHlQCu6izs`):
```text
{
  "sent": true
}
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_0b2ffa107df043ce006abe64004a6c87d1bd55295cdaa40859'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=cap_client_read)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

- app's reply to `send_progress_update` (call_id=`call_jRi6Y31OtgJUpDbHlQCu6izs`):
```text
{
  "sent": true
}
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_0b2ffa107df043ce006abe64004a6c87d1bd55295cdaa40859'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19816 chars)</summary>

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

(none)

## Loaded capabilities

cap_client_read

---

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>18. [2026-10-01 16:45:43] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 1/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0b2ffa107df043ce006abe64039d0c87d1bb04996557ca6c56`
- status: `completed`
- usage: `{"input_tokens": 7004, "input_tokens_details": {"cache_write_tokens": 6916, "cached_tokens": 0}, "output_tokens": 79, "output_tokens_details": {"reasoning_tokens": 12}, "total_tokens": 7083}`

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0b2ffa107df043ce006abe64039d0c87d1bb04996557ca6c56`
- status: `completed`
- usage: `{"input_tokens": 7004, "input_tokens_details": {"cache_write_tokens": 6916, "cached_tokens": 0}, "output_tokens": 79, "output_tokens_details": {"reasoning_tokens": 12}, "total_tokens": 7083}`
- (no output items in this part)

</details>

</details>

<details>
<summary>19. [2026-10-01 16:45:43] MODEL → MORNING MCP — resolve_client_name</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- tool name: `resolve_client_name`
- server_label: `'morning-invoices-client-read'`

arguments:
```json
{
  "name": "שחר פישר"
}
```

</details>

</details>

<details>
<summary>20. [2026-10-01 16:45:43] MORNING MCP → MODEL — resolve_client_name</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

output:
```json
{
  "status": "resolved",
  "name": "שחר פישר"
}
```

</details>

</details>

<details>
<summary>21. [2026-10-01 16:45:43] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 2/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0b2ffa107df043ce006abe64039d0c87d1bb04996557ca6c56`
- status: `completed`
- usage: `{"input_tokens": 7004, "input_tokens_details": {"cache_write_tokens": 6916, "cached_tokens": 0}, "output_tokens": 79, "output_tokens_details": {"reasoning_tokens": 12}, "total_tokens": 7083}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_Jpno5XpN5KJvJRyAcTAsxhrN`
```json
{
  "text": "מצאתי את הלקוח. עכשיו אני שולף את הפרטים השמורים."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0b2ffa107df043ce006abe64039d0c87d1bb04996557ca6c56`
- status: `completed`
- usage: `{"input_tokens": 7004, "input_tokens_details": {"cache_write_tokens": 6916, "cached_tokens": 0}, "output_tokens": 79, "output_tokens_details": {"reasoning_tokens": 12}, "total_tokens": 7083}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_Jpno5XpN5KJvJRyAcTAsxhrN`
```json
{
  "text": "מצאתי את הלקוח. עכשיו אני שולף את הפרטים השמורים."
}
```

</details>

</details>

<details>
<summary>22. [2026-10-01 16:45:43] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972501234567@c.us",
  "message": "מצאתי את הלקוח. עכשיו אני שולף את הפרטים השמורים."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "972501234567@c.us",
  "message": "מצאתי את הלקוח. עכשיו אני שולף את הפרטים השמורים."
}
```

</details>

</details>

<details>
<summary>23. [2026-10-01 16:45:43] USER ← APP (send result) — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972501234567@c.us",
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
<summary>24. [2026-10-01 16:45:43] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

- app's reply to `send_progress_update` (call_id=`call_Jpno5XpN5KJvJRyAcTAsxhrN`):
```text
{
  "sent": true
}
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_0b2ffa107df043ce006abe64039d0c87d1bb04996557ca6c56'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=cap_client_read)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

- app's reply to `send_progress_update` (call_id=`call_Jpno5XpN5KJvJRyAcTAsxhrN`):
```text
{
  "sent": true
}
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_0b2ffa107df043ce006abe64039d0c87d1bb04996557ca6c56'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19816 chars)</summary>

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

(none)

## Loaded capabilities

cap_client_read

---

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>25. [2026-10-01 16:45:49] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 1/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0b2ffa107df043ce006abe6408465887d1853c55ce209206d8`
- status: `completed`
- usage: `{"input_tokens": 7184, "input_tokens_details": {"cache_write_tokens": 218, "cached_tokens": 6839}, "output_tokens": 144, "output_tokens_details": {"reasoning_tokens": 18}, "total_tokens": 7328}`

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0b2ffa107df043ce006abe6408465887d1853c55ce209206d8`
- status: `completed`
- usage: `{"input_tokens": 7184, "input_tokens_details": {"cache_write_tokens": 218, "cached_tokens": 6839}, "output_tokens": 144, "output_tokens_details": {"reasoning_tokens": 18}, "total_tokens": 7328}`
- (no output items in this part)

</details>

</details>

<details>
<summary>26. [2026-10-01 16:45:49] MODEL → MORNING MCP — get_client_details</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- tool name: `get_client_details`
- server_label: `'morning-invoices-client-read'`

arguments:
```json
{
  "name": "שחר פישר",
  "name_resolved": true
}
```

</details>

</details>

<details>
<summary>27. [2026-10-01 16:45:49] MORNING MCP → MODEL — get_client_details</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

output:
```json
{
  "client": {
    "name": "שחר פישר",
    "email": "e2e-client-843832@example.com",
    "phone": "050-1234567",
    "tax_id": ""
  },
  "exact_match": true
}
```

</details>

</details>

<details>
<summary>28. [2026-10-01 16:45:49] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 2/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0b2ffa107df043ce006abe6408465887d1853c55ce209206d8`
- status: `completed`
- usage: `{"input_tokens": 7184, "input_tokens_details": {"cache_write_tokens": 218, "cached_tokens": 6839}, "output_tokens": 144, "output_tokens_details": {"reasoning_tokens": 18}, "total_tokens": 7328}`
- reasoning item (content not user-visible)
- function_call: `record_planning_status` call_id=`call_pTylHGK6j9b75ZV6msmLMpM2`
```json
{
  "where_i_was": "נמצא הלקוח שחר פישר ונשלפו פרטיו המדויקים ממערכת מורנינג.",
  "this_turns_purpose": "להחזיר למשתמש את פרטי הלקוח בעברית ובקיצור.",
  "expectation": "המשימה הושלמה בהצלחה; אין צורך בשאלה נוספת."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0b2ffa107df043ce006abe6408465887d1853c55ce209206d8`
- status: `completed`
- usage: `{"input_tokens": 7184, "input_tokens_details": {"cache_write_tokens": 218, "cached_tokens": 6839}, "output_tokens": 144, "output_tokens_details": {"reasoning_tokens": 18}, "total_tokens": 7328}`
- reasoning item (content not user-visible)
- function_call: `record_planning_status` call_id=`call_pTylHGK6j9b75ZV6msmLMpM2`
```json
{
  "where_i_was": "נמצא הלקוח שחר פישר ונשלפו פרטיו המדויקים ממערכת מורנינג.",
  "this_turns_purpose": "להחזיר למשתמש את פרטי הלקוח בעברית ובקיצור.",
  "expectation": "המשימה הושלמה בהצלחה; אין צורך בשאלה נוספת."
}
```

</details>

</details>

<details>
<summary>29. [2026-10-01 16:45:49] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

- app's reply to `record_planning_status` (call_id=`call_pTylHGK6j9b75ZV6msmLMpM2`):
```text
recorded
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_0b2ffa107df043ce006abe6408465887d1853c55ce209206d8'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=cap_client_read)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

- app's reply to `record_planning_status` (call_id=`call_pTylHGK6j9b75ZV6msmLMpM2`):
```text
recorded
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_0b2ffa107df043ce006abe6408465887d1853c55ce209206d8'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19816 chars)</summary>

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

(none)

## Loaded capabilities

cap_client_read

---

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>30. [2026-10-01 16:45:50] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0b2ffa107df043ce006abe640d679c87d1b39f8285d37d90e0`
- status: `completed`
- usage: `{"input_tokens": 7298, "input_tokens_details": {"cache_write_tokens": 238, "cached_tokens": 7057}, "output_tokens": 24, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7322}`
- function_call: `react_to_message` call_id=`call_9NZMsveV433wHDmKx3m8ltQi`
```json
{
  "emoji": "✅",
  "message_id": null
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0b2ffa107df043ce006abe640d679c87d1b39f8285d37d90e0`
- status: `completed`
- usage: `{"input_tokens": 7298, "input_tokens_details": {"cache_write_tokens": 238, "cached_tokens": 7057}, "output_tokens": 24, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7322}`
- function_call: `react_to_message` call_id=`call_9NZMsveV433wHDmKx3m8ltQi`
```json
{
  "emoji": "✅",
  "message_id": null
}
```

</details>

</details>

<details>
<summary>31. [2026-10-01 16:45:50] APP → USER — context=reaction — ✅ — NOT SENT (no WhatsApp bot in this run)</summary>

```text
[084] react_to_message call 'call_9NZMsveV433wHDmKx3m8ltQi': nothing to react through (target_id='LEDGER_E2E_F3_PROBE_A1_1790862324', chat_id='972501234567@c.us', green_api_bot_set=False)
```

</details>

<details>
<summary>32. [2026-10-01 16:45:50] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

- app's reply to `react_to_message` (call_id=`call_9NZMsveV433wHDmKx3m8ltQi`):
```text
{
  "status": "failed"
}
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_0b2ffa107df043ce006abe640d679c87d1b39f8285d37d90e0'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=cap_client_read)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

- app's reply to `react_to_message` (call_id=`call_9NZMsveV433wHDmKx3m8ltQi`):
```text
{
  "status": "failed"
}
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_0b2ffa107df043ce006abe640d679c87d1b39f8285d37d90e0'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19816 chars)</summary>

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

(none)

## Loaded capabilities

cap_client_read

---

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>33. [2026-10-01 16:45:53] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0b2ffa107df043ce006abe640f417c87d1aa482c355ab99427`
- status: `completed`
- usage: `{"input_tokens": 7340, "input_tokens_details": {"cache_write_tokens": 42, "cached_tokens": 7295}, "output_tokens": 74, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7414}`
- function_call: `send_to_user` call_id=`call_hiBvQvvBPqqspA9UcgVyHpFg`
```json
{
  "text": "פרטי הלקוח שחר פישר:\n\nשם: שחר פישר\nדוא״ל: e2e-client-843832@example.com\nטלפון: 050-1234567\nמספר עוסק או חברה: לא שמור"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0b2ffa107df043ce006abe640f417c87d1aa482c355ab99427`
- status: `completed`
- usage: `{"input_tokens": 7340, "input_tokens_details": {"cache_write_tokens": 42, "cached_tokens": 7295}, "output_tokens": 74, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7414}`
- function_call: `send_to_user` call_id=`call_hiBvQvvBPqqspA9UcgVyHpFg`
```json
{
  "text": "פרטי הלקוח שחר פישר:\n\nשם: שחר פישר\nדוא״ל: e2e-client-843832@example.com\nטלפון: 050-1234567\nמספר עוסק או חברה: לא שמור"
}
```

</details>

</details>

<details>
<summary>34. [2026-10-01 16:45:53] APP → USER — context=text</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972501234567@c.us",
  "message": "פרטי הלקוח שחר פישר:\n\nשם: שחר פישר\nדוא״ל: e2e-client-843832@example.com\nטלפון: 050-1234567\nמספר עוסק או חברה: לא שמור"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "972501234567@c.us",
  "message": "פרטי הלקוח שחר פישר:\n\nשם: שחר פישר\nדוא״ל: e2e-client-843832@example.com\nטלפון: 050-1234567\nמספר עוסק או חברה: לא שמור"
}
```

</details>

</details>

<details>
<summary>35. [2026-10-01 16:45:53] APP → MODEL — context=recognize_ledger_event</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

**input:**

```json
{"role": "user", "content": "THE CONVERSATION WINDOW (the last 1h, oldest first) - '<message_id> [<role>] <content>':\n9d7a9609-333f-41d3-85ff-dc79af1ef735 [godfather] פרטים על הלקוח שחר פישר\n36d3142d-63a2-4ae8-93d3-62a8f559cb26 [assistant] בודק את פרטי הלקוח במערכת.\n763eaa3c-b8d1-4997-a37b-fd2b616aabdc [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: הבקשה היא לאחזר את פרטי הלקוח שחר פישר. עדיין לא בוצע חיפוש.\nTHIS TURN'S PURPOSE: לאתר את הלקוח המדויק במערכת ולהחזיר את פרטיו האישיים בלבד.\nEXPECTATION: אטען יכולת לקריאת לקוחות, אחפש את הלקוח, ואז אחזיר את התוצאה או אבקש הבהרה אם יש כמה התאמות.\nada30b46-ba49-491e-b5a9-55b7853934ca [assistant] מאתר את השם המדויק כפי שהוא שמור במערכת.\ndd20e6ed-fa19-4e07-966d-e6739d89f615 [assistant] מצאתי את הלקוח. עכשיו אני שולף את הפרטים השמורים.\nfa4d2b8b-5ed2-4d2c-b9e3-019838928f64 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: נמצא הלקוח שחר פישר ונשלפו פרטיו המדויקים ממערכת מורנינג.\nTHIS TURN'S PURPOSE: להחזיר למשתמש את פרטי הלקוח בעברית ובקיצור.\nEXPECTATION: המשימה הושלמה בהצלחה; אין צורך בשאלה נוספת.\n297c0b0c-a2fa-4784-ad37-e9555685798e [assistant] פרטי הלקוח שחר פישר:\n\nשם: שחר פישר\nדוא״ל: e2e-client-843832@example.com\nטלפון: 050-1234567\nמספר עוסק או חברה: לא שמור\n    (morning MCP call on this message's turn) {\"name\": \"resolve_client_name\", \"error\": null, \"arguments\": \"{\\\"name\\\":\\\"שחר פישר\\\"}\", \"output\": \"{\\\"status\\\": \\\"resolved\\\", \\\"name\\\": \\\"\\\\u05e9\\\\u05d7\\\\u05e8 \\\\u05e4\\\\u05d9\\\\u05e9\\\\u05e8\\\"}\"}\n    (morning MCP call on this message's turn) {\"name\": \"get_client_details\", \"error\": null, \"arguments\": \"{\\\"name\\\":\\\"שחר פישר\\\",\\\"name_resolved\\\":true}\", \"output\": \"{\\\"client\\\": {\\\"name\\\": \\\"\\\\u05e9\\\\u05d7\\\\u05e8 \\\\u05e4\\\\u05d9\\\\u05e9\\\\u05e8\\\", \\\"email\\\": \\\"e2e-client-843832@example.com\\\", \\\"phone\\\": \\\"050-1234567\\\", \\\"tax_id\\\": \\\"\\\"}, \\\"exact_match\\\": true}\"}\n\nTHE REPLY JUST SENT TO THE OPERATOR THIS ROUND:\nפרטי הלקוח שחר פישר:\n\nשם: שחר פישר\nדוא״ל: e2e-client-843832@example.com\nטלפון: 050-1234567\nמספר עוסק או חברה: לא שמור\n\nMORNING MCP TOOL CALLS MADE THIS TURN (verbatim, each with its arguments and its real result):\n[\n  {\n    \"name\": \"resolve_client_name\",\n    \"error\": null,\n    \"arguments\": \"{\\\"name\\\":\\\"שחר פישר\\\"}\",\n    \"output\": \"{\\\"status\\\": \\\"resolved\\\", \\\"name\\\": \\\"\\\\u05e9\\\\u05d7\\\\u05e8 \\\\u05e4\\\\u05d9\\\\u05e9\\\\u05e8\\\"}\"\n  },\n  {\n    \"name\": \"get_client_details\",\n    \"error\": null,\n    \"arguments\": \"{\\\"name\\\":\\\"שחר פישר\\\",\\\"name_resolved\\\":true}\",\n    \"output\": \"{\\\"client\\\": {\\\"name\\\": \\\"\\\\u05e9\\\\u05d7\\\\u05e8 \\\\u05e4\\\\u05d9\\\\u05e9\\\\u05e8\\\", \\\"email\\\": \\\"e2e-client-843832@example.com\\\", \\\"phone\\\": \\\"050-1234567\\\", \\\"tax_id\\\": \\\"\\\"}, \\\"exact_match\\\": true}\"\n  }\n]\n\nFollow the recognition prompt above: query the client's ledger history first when the round concerns a client, then call report_ledger_recognition exactly once with the verdict for THIS round."}
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
{"role": "user", "content": "THE CONVERSATION WINDOW (the last 1h, oldest first) - '<message_id> [<role>] <content>':\n9d7a9609-333f-41d3-85ff-dc79af1ef735 [godfather] פרטים על הלקוח שחר פישר\n36d3142d-63a2-4ae8-93d3-62a8f559cb26 [assistant] בודק את פרטי הלקוח במערכת.\n763eaa3c-b8d1-4997-a37b-fd2b616aabdc [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: הבקשה היא לאחזר את פרטי הלקוח שחר פישר. עדיין לא בוצע חיפוש.\nTHIS TURN'S PURPOSE: לאתר את הלקוח המדויק במערכת ולהחזיר את פרטיו האישיים בלבד.\nEXPECTATION: אטען יכולת לקריאת לקוחות, אחפש את הלקוח, ואז אחזיר את התוצאה או אבקש הבהרה אם יש כמה התאמות.\nada30b46-ba49-491e-b5a9-55b7853934ca [assistant] מאתר את השם המדויק כפי שהוא שמור במערכת.\ndd20e6ed-fa19-4e07-966d-e6739d89f615 [assistant] מצאתי את הלקוח. עכשיו אני שולף את הפרטים השמורים.\nfa4d2b8b-5ed2-4d2c-b9e3-019838928f64 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: נמצא הלקוח שחר פישר ונשלפו פרטיו המדויקים ממערכת מורנינג.\nTHIS TURN'S PURPOSE: להחזיר למשתמש את פרטי הלקוח בעברית ובקיצור.\nEXPECTATION: המשימה הושלמה בהצלחה; אין צורך בשאלה נוספת.\n297c0b0c-a2fa-4784-ad37-e9555685798e [assistant] פרטי הלקוח שחר פישר:\n\nשם: שחר פישר\nדוא״ל: e2e-client-843832@example.com\nטלפון: 050-1234567\nמספר עוסק או חברה: לא שמור\n    (morning MCP call on this message's turn) {\"name\": \"resolve_client_name\", \"error\": null, \"arguments\": \"{\\\"name\\\":\\\"שחר פישר\\\"}\", \"output\": \"{\\\"status\\\": \\\"resolved\\\", \\\"name\\\": \\\"\\\\u05e9\\\\u05d7\\\\u05e8 \\\\u05e4\\\\u05d9\\\\u05e9\\\\u05e8\\\"}\"}\n    (morning MCP call on this message's turn) {\"name\": \"get_client_details\", \"error\": null, \"arguments\": \"{\\\"name\\\":\\\"שחר פישר\\\",\\\"name_resolved\\\":true}\", \"output\": \"{\\\"client\\\": {\\\"name\\\": \\\"\\\\u05e9\\\\u05d7\\\\u05e8 \\\\u05e4\\\\u05d9\\\\u05e9\\\\u05e8\\\", \\\"email\\\": \\\"e2e-client-843832@example.com\\\", \\\"phone\\\": \\\"050-1234567\\\", \\\"tax_id\\\": \\\"\\\"}, \\\"exact_match\\\": true}\"}\n\nTHE REPLY JUST SENT TO THE OPERATOR THIS ROUND:\nפרטי הלקוח שחר פישר:\n\nשם: שחר פישר\nדוא״ל: e2e-client-843832@example.com\nטלפון: 050-1234567\nמספר עוסק או חברה: לא שמור\n\nMORNING MCP TOOL CALLS MADE THIS TURN (verbatim, each with its arguments and its real result):\n[\n  {\n    \"name\": \"resolve_client_name\",\n    \"error\": null,\n    \"arguments\": \"{\\\"name\\\":\\\"שחר פישר\\\"}\",\n    \"output\": \"{\\\"status\\\": \\\"resolved\\\", \\\"name\\\": \\\"\\\\u05e9\\\\u05d7\\\\u05e8 \\\\u05e4\\\\u05d9\\\\u05e9\\\\u05e8\\\"}\"\n  },\n  {\n    \"name\": \"get_client_details\",\n    \"error\": null,\n    \"arguments\": \"{\\\"name\\\":\\\"שחר פישר\\\",\\\"name_resolved\\\":true}\",\n    \"output\": \"{\\\"client\\\": {\\\"name\\\": \\\"\\\\u05e9\\\\u05d7\\\\u05e8 \\\\u05e4\\\\u05d9\\\\u05e9\\\\u05e8\\\", \\\"email\\\": \\\"e2e-client-843832@example.com\\\", \\\"phone\\\": \\\"050-1234567\\\", \\\"tax_id\\\": \\\"\\\"}, \\\"exact_match\\\": true}\"\n  }\n]\n\nFollow the recognition prompt above: query the client's ledger history first when the round concerns a client, then call report_ledger_recognition exactly once with the verdict for THIS round."}
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
<summary>36. [2026-10-01 16:45:55] MODEL → APP — context=recognize_ledger_event</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0a374ab599da6cbf006abe6412235c87d1bb7bf434888d3d12`
- status: `completed`
- usage: `{"input_tokens": 8993, "input_tokens_details": {"cache_write_tokens": 1054, "cached_tokens": 7936}, "output_tokens": 53, "output_tokens_details": {"reasoning_tokens": 19}, "total_tokens": 9046}`
- reasoning item (content not user-visible)
- function_call: `query_ledger_events` call_id=`call_cWh5YNsxmbnhhixvkEULmmVs`
```json
{
  "criteria": [
    {
      "text": "שחר פישר",
      "hint": "identity"
    }
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0a374ab599da6cbf006abe6412235c87d1bb7bf434888d3d12`
- status: `completed`
- usage: `{"input_tokens": 8993, "input_tokens_details": {"cache_write_tokens": 1054, "cached_tokens": 7936}, "output_tokens": 53, "output_tokens_details": {"reasoning_tokens": 19}, "total_tokens": 9046}`
- reasoning item (content not user-visible)
- function_call: `query_ledger_events` call_id=`call_cWh5YNsxmbnhhixvkEULmmVs`
```json
{
  "criteria": [
    {
      "text": "שחר פישר",
      "hint": "identity"
    }
  ]
}
```

</details>

</details>

<details>
<summary>37. [2026-10-01 16:45:55] APP → MODEL — context=recognize_ledger_event (query round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

**input:**

- app's reply to `query_ledger_events` (call_id=`call_cWh5YNsxmbnhhixvkEULmmVs`):
```text
{
  "matches": [],
  "count": 0
}
```

- tools (2): ['report_ledger_recognition', 'query_ledger_events']

- previous_response_id: `'resp_0a374ab599da6cbf006abe6412235c87d1bb7bf434888d3d12'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: ledger recognition prompt

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

**input:**

- app's reply to `query_ledger_events` (call_id=`call_cWh5YNsxmbnhhixvkEULmmVs`):
```text
{
  "matches": [],
  "count": 0
}
```

- tools (2): ['report_ledger_recognition', 'query_ledger_events']

- previous_response_id: `'resp_0a374ab599da6cbf006abe6412235c87d1bb7bf434888d3d12'`

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
<summary>38. [2026-10-01 16:45:57] MODEL → APP — context=recognize_ledger_event (query round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0a374ab599da6cbf006abe64142aa887d1aeaa7cfdd804659e`
- status: `completed`
- usage: `{"input_tokens": 9069, "input_tokens_details": {"cache_write_tokens": 76, "cached_tokens": 8990}, "output_tokens": 42, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9111}`
- function_call: `report_ledger_recognition` call_id=`call_gpTmPW5D46RLxvgTf7oKnuBd`
```json
{
  "verdict": "none",
  "none_reason": "ordinary client-details lookup; no fee agreement, deposit, or Morning accounting document created"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0a374ab599da6cbf006abe64142aa887d1aeaa7cfdd804659e`
- status: `completed`
- usage: `{"input_tokens": 9069, "input_tokens_details": {"cache_write_tokens": 76, "cached_tokens": 8990}, "output_tokens": 42, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9111}`
- function_call: `report_ledger_recognition` call_id=`call_gpTmPW5D46RLxvgTf7oKnuBd`
```json
{
  "verdict": "none",
  "none_reason": "ordinary client-details lookup; no fee agreement, deposit, or Morning accounting document created"
}
```

</details>

</details>

<details>
<summary>39. [2026-10-01 16:45:57] USER → APP — context=webhook</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "typeWebhook": "incomingMessageReceived",
  "timestamp": 1790862357,
  "idMessage": "LEDGER_E2E_IMAGE_AGREEMENT_MULTI_IMG",
  "instanceData": {
    "idInstance": 7103000000,
    "wid": "972501234567@c.us",
    "typeInstance": "whatsapp"
  },
  "senderData": {
    "chatId": "972501234567@c.us",
    "sender": "972501234567@c.us",
    "senderName": "E2E Godfather"
  },
  "messageData": {
    "typeMessage": "imageMessage",
    "fileMessageData": {
      "downloadUrl": "http://127.0.0.1:8766/Agreement-test-image.jpg",
      "fileName": "Agreement-test-image.jpg",
      "mimeType": "image/jpeg",
      "caption": "ההסכם החתום, תרשום ביומן",
      "jpegThumbnail": "",
      "isForwarded": false,
      "forwardingScore": 0
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
  "timestamp": 1790862357,
  "idMessage": "LEDGER_E2E_IMAGE_AGREEMENT_MULTI_IMG",
  "instanceData": {
    "idInstance": 7103000000,
    "wid": "972501234567@c.us",
    "typeInstance": "whatsapp"
  },
  "senderData": {
    "chatId": "972501234567@c.us",
    "sender": "972501234567@c.us",
    "senderName": "E2E Godfather"
  },
  "messageData": {
    "typeMessage": "imageMessage",
    "fileMessageData": {
      "downloadUrl": "http://127.0.0.1:8766/Agreement-test-image.jpg",
      "fileName": "Agreement-test-image.jpg",
      "mimeType": "image/jpeg",
      "caption": "ההסכם החתום, תרשום ביומן",
      "jpegThumbnail": "",
      "isForwarded": false,
      "forwardingScore": 0
    }
  }
}
```

</details>

</details>

<details>
<summary>40. [2026-10-01 16:45:58] APP → MODEL — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

```json
{"role": "user", "content": "פרטים על הלקוח שחר פישר"}
```
```json
{"role": "assistant", "content": "בודק את פרטי הלקוח במערכת."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: הבקשה היא לאחזר את פרטי הלקוח שחר פישר. עדיין לא בוצע חיפוש.\nTHIS TURN'S PURPOSE: לאתר את הלקוח המדויק במערכת ולהחזיר את פרטיו האישיים בלבד.\nEXPECTATION: אטען יכולת לקריאת לקוחות, אחפש את הלקוח, ואז אחזיר את התוצאה או אבקש הבהרה אם יש כמה התאמות."}
```
```json
{"role": "assistant", "content": "מאתר את השם המדויק כפי שהוא שמור במערכת."}
```
```json
{"role": "assistant", "content": "מצאתי את הלקוח. עכשיו אני שולף את הפרטים השמורים."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: נמצא הלקוח שחר פישר ונשלפו פרטיו המדויקים ממערכת מורנינג.\nTHIS TURN'S PURPOSE: להחזיר למשתמש את פרטי הלקוח בעברית ובקיצור.\nEXPECTATION: המשימה הושלמה בהצלחה; אין צורך בשאלה נוספת."}
```
```json
{"role": "assistant", "content": "פרטי הלקוח שחר פישר:\n\nשם: שחר פישר\nדוא״ל: e2e-client-843832@example.com\nטלפון: 050-1234567\nמספר עוסק או חברה: לא שמור"}
```
```json
{"role": "user", "content": "[מדיה מצורפת: תמונה, קובץ: Agreement-test-image.jpg]\nההסכם החתום, תרשום ביומן"}
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=cap_client_read)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

```json
{"role": "user", "content": "פרטים על הלקוח שחר פישר"}
```
```json
{"role": "assistant", "content": "בודק את פרטי הלקוח במערכת."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: הבקשה היא לאחזר את פרטי הלקוח שחר פישר. עדיין לא בוצע חיפוש.\nTHIS TURN'S PURPOSE: לאתר את הלקוח המדויק במערכת ולהחזיר את פרטיו האישיים בלבד.\nEXPECTATION: אטען יכולת לקריאת לקוחות, אחפש את הלקוח, ואז אחזיר את התוצאה או אבקש הבהרה אם יש כמה התאמות."}
```
```json
{"role": "assistant", "content": "מאתר את השם המדויק כפי שהוא שמור במערכת."}
```
```json
{"role": "assistant", "content": "מצאתי את הלקוח. עכשיו אני שולף את הפרטים השמורים."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: נמצא הלקוח שחר פישר ונשלפו פרטיו המדויקים ממערכת מורנינג.\nTHIS TURN'S PURPOSE: להחזיר למשתמש את פרטי הלקוח בעברית ובקיצור.\nEXPECTATION: המשימה הושלמה בהצלחה; אין צורך בשאלה נוספת."}
```
```json
{"role": "assistant", "content": "פרטי הלקוח שחר פישר:\n\nשם: שחר פישר\nדוא״ל: e2e-client-843832@example.com\nטלפון: 050-1234567\nמספר עוסק או חברה: לא שמור"}
```
```json
{"role": "user", "content": "[מדיה מצורפת: תמונה, קובץ: Agreement-test-image.jpg]\nההסכם החתום, תרשום ביומן"}
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19816 chars)</summary>

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

(none)

## Loaded capabilities

cap_client_read

---

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>41. [2026-10-01 16:46:02] MODEL → APP — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_02af3c800d02aa1a006abe6416ffe887d1a32b0d26f32ff990`
- status: `completed`
- usage: `{"input_tokens": 6814, "input_tokens_details": {"cache_write_tokens": 369, "cached_tokens": 6442}, "output_tokens": 78, "output_tokens_details": {"reasoning_tokens": 50}, "total_tokens": 6892}`
- mcp_list_tools (morning-invoices-client-read): ['list_clients', 'resolve_client_name', 'get_client_details']
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_MuugPv0K06AwURwgysDnvMYR`
```json
{
  "emoji": "🫡",
  "message_id": null
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_02af3c800d02aa1a006abe6416ffe887d1a32b0d26f32ff990`
- status: `completed`
- usage: `{"input_tokens": 6814, "input_tokens_details": {"cache_write_tokens": 369, "cached_tokens": 6442}, "output_tokens": 78, "output_tokens_details": {"reasoning_tokens": 50}, "total_tokens": 6892}`
- mcp_list_tools (morning-invoices-client-read): ['list_clients', 'resolve_client_name', 'get_client_details']
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_MuugPv0K06AwURwgysDnvMYR`
```json
{
  "emoji": "🫡",
  "message_id": null
}
```

</details>

</details>

<details>
<summary>42. [2026-10-01 16:46:02] APP → USER — context=reaction — 🫡 — NOT SENT (no WhatsApp bot in this run)</summary>

```text
[084] react_to_message call 'call_MuugPv0K06AwURwgysDnvMYR': nothing to react through (target_id='LEDGER_E2E_IMAGE_AGREEMENT_MULTI_IMG', chat_id='972501234567@c.us', green_api_bot_set=False)
```

</details>

<details>
<summary>43. [2026-10-01 16:46:02] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

- app's reply to `react_to_message` (call_id=`call_MuugPv0K06AwURwgysDnvMYR`):
```text
{
  "status": "failed"
}
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_02af3c800d02aa1a006abe6416ffe887d1a32b0d26f32ff990'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=cap_client_read)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

- app's reply to `react_to_message` (call_id=`call_MuugPv0K06AwURwgysDnvMYR`):
```text
{
  "status": "failed"
}
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_02af3c800d02aa1a006abe6416ffe887d1a32b0d26f32ff990'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19816 chars)</summary>

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

(none)

## Loaded capabilities

cap_client_read

---

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>44. [2026-10-01 16:46:04] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_02af3c800d02aa1a006abe641afe9c87d18ad4d6712b1a8842`
- status: `completed`
- usage: `{"input_tokens": 6910, "input_tokens_details": {"cache_write_tokens": 96, "cached_tokens": 6811}, "output_tokens": 55, "output_tokens_details": {"reasoning_tokens": 13}, "total_tokens": 6965}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_wLCoHjwOhVAOUbNINqsztdTQ`
```json
{
  "text": "בודק את ההסכם החתום ואת פרטי הלקוח לפני הרישום ביומן."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_02af3c800d02aa1a006abe641afe9c87d18ad4d6712b1a8842`
- status: `completed`
- usage: `{"input_tokens": 6910, "input_tokens_details": {"cache_write_tokens": 96, "cached_tokens": 6811}, "output_tokens": 55, "output_tokens_details": {"reasoning_tokens": 13}, "total_tokens": 6965}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_wLCoHjwOhVAOUbNINqsztdTQ`
```json
{
  "text": "בודק את ההסכם החתום ואת פרטי הלקוח לפני הרישום ביומן."
}
```

</details>

</details>

<details>
<summary>45. [2026-10-01 16:46:04] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

- app's reply to `send_progress_update` (call_id=`call_wLCoHjwOhVAOUbNINqsztdTQ`):
```text
{
  "sent": false
}
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_02af3c800d02aa1a006abe641afe9c87d18ad4d6712b1a8842'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=cap_client_read)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

- app's reply to `send_progress_update` (call_id=`call_wLCoHjwOhVAOUbNINqsztdTQ`):
```text
{
  "sent": false
}
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_02af3c800d02aa1a006abe641afe9c87d18ad4d6712b1a8842'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19816 chars)</summary>

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

(none)

## Loaded capabilities

cap_client_read

---

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>46. [2026-10-01 16:46:06] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_02af3c800d02aa1a006abe641ca3b487d193449d201febe081`
- status: `completed`
- usage: `{"input_tokens": 6982, "input_tokens_details": {"cache_write_tokens": 72, "cached_tokens": 6907}, "output_tokens": 138, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7120}`
- function_call: `record_planning_status` call_id=`call_UA7pmbrLPFSjHBR7LJ6gbgvs`
```json
{
  "where_i_was": "המשתמש שלח תמונת הסכם חתום וביקש לרשום אותו ביומן. טרם נקרא תוכן התמונה.",
  "this_turns_purpose": "לקרוא את ההסכם, לזהות את הלקוח והפרטים הנדרשים, ולאחר מכן לרשום את ההסכם ביומן לפי הזרימה המתאימה.",
  "expectation": "אטען את זרימת רישום הסכם ואת יכולת ניתוח המדיה, אקרא את התמונה, ואז אפעל לפי תוצאת הניתוח."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_02af3c800d02aa1a006abe641ca3b487d193449d201febe081`
- status: `completed`
- usage: `{"input_tokens": 6982, "input_tokens_details": {"cache_write_tokens": 72, "cached_tokens": 6907}, "output_tokens": 138, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7120}`
- function_call: `record_planning_status` call_id=`call_UA7pmbrLPFSjHBR7LJ6gbgvs`
```json
{
  "where_i_was": "המשתמש שלח תמונת הסכם חתום וביקש לרשום אותו ביומן. טרם נקרא תוכן התמונה.",
  "this_turns_purpose": "לקרוא את ההסכם, לזהות את הלקוח והפרטים הנדרשים, ולאחר מכן לרשום את ההסכם ביומן לפי הזרימה המתאימה.",
  "expectation": "אטען את זרימת רישום הסכם ואת יכולת ניתוח המדיה, אקרא את התמונה, ואז אפעל לפי תוצאת הניתוח."
}
```

</details>

</details>

<details>
<summary>47. [2026-10-01 16:46:07] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

- app's reply to `record_planning_status` (call_id=`call_UA7pmbrLPFSjHBR7LJ6gbgvs`):
```text
recorded
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_02af3c800d02aa1a006abe641ca3b487d193449d201febe081'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=cap_client_read)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: cap_client_read

**input:**

- app's reply to `record_planning_status` (call_id=`call_UA7pmbrLPFSjHBR7LJ6gbgvs`):
```text
recorded
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_02af3c800d02aa1a006abe641ca3b487d193449d201febe081'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19816 chars)</summary>

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

(none)

## Loaded capabilities

cap_client_read

---

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>48. [2026-10-01 16:46:08] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_02af3c800d02aa1a006abe641f46d087d1bddb5c5a301af70c`
- status: `completed`
- usage: `{"input_tokens": 7136, "input_tokens_details": {"cache_write_tokens": 690, "cached_tokens": 6443}, "output_tokens": 27, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7163}`
- function_call: `load_flows` call_id=`call_gC7n6rw0UZKhn2hwSQFwBck5`
```json
{
  "flows": [
    "flow_fee_agreement_provided_by_user"
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_02af3c800d02aa1a006abe641f46d087d1bddb5c5a301af70c`
- status: `completed`
- usage: `{"input_tokens": 7136, "input_tokens_details": {"cache_write_tokens": 690, "cached_tokens": 6443}, "output_tokens": 27, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7163}`
- function_call: `load_flows` call_id=`call_gC7n6rw0UZKhn2hwSQFwBck5`
```json
{
  "flows": [
    "flow_fee_agreement_provided_by_user"
  ]
}
```

</details>

</details>

<details>
<summary>49. [2026-10-01 16:46:08] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_fee_agreement_provided_by_user

- capabilities: cap_client_read

**input:**

- app's reply to `load_flows` (call_id=`call_gC7n6rw0UZKhn2hwSQFwBck5`):
```text
loaded flows: flow_fee_agreement_provided_by_user. Loaded flows now: flow_fee_agreement_provided_by_user. Loaded capabilities now: cap_client_read. Their blueprint text is attached starting now.
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_02af3c800d02aa1a006abe641f46d087d1bddb5c5a301af70c'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_fee_agreement_provided_by_user, capabilities=cap_client_read)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_fee_agreement_provided_by_user

- capabilities: cap_client_read

**input:**

- app's reply to `load_flows` (call_id=`call_gC7n6rw0UZKhn2hwSQFwBck5`):
```text
loaded flows: flow_fee_agreement_provided_by_user. Loaded flows now: flow_fee_agreement_provided_by_user. Loaded capabilities now: cap_client_read. Their blueprint text is attached starting now.
```

- tools (10): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'mcp']

- previous_response_id: `'resp_02af3c800d02aa1a006abe641f46d087d1bddb5c5a301af70c'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (22007 chars)</summary>

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

# Flow: Fee agreement provided by the user

Goal: the user provided a fee agreement, as text or as an image: make sure its client exists in Morning.

Capabilities: `cap_media_analysis`, `cap_client_read`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

1. If the agreement came as an image or document, it must have been read with `cap_media_analysis`'s `analyze_media` (load it and read it now if it was not). Use `cap_send_to_user` to report what it contains so the user can see what you understood. If its `missing_required_fields` is not empty, ask the user for exactly those details and wait for them.
2. The client must be resolved by its exact stored name before moving to the next step - either
   from the recent conversation history if it was already resolved there, or, if not, by loading
   `cap_client_read` and resolving it now. Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Recording the agreement itself happens after the turn ends, from what is in the conversation. There is nothing to load or call for it, so do not try. Your job is only to get the client resolved (or created), so the recorded agreement refers to a real client. It can be recorded only once the conversation holds the client and every payment component's amount; if any is missing, ask the user for it. Never tell the user the agreement was or will be recorded while any of it is missing.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_media_analysis`, `cap_client_read` and this flow, keeping any that other work still in progress needs.


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

flow_fee_agreement_provided_by_user

## Loaded capabilities

cap_client_read

---

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>50. [2026-10-01 16:46:10] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_02af3c800d02aa1a006abe6420e5cc87d1a4f74d7516cd6cdd`
- status: `completed`
- usage: `{"input_tokens": 7717, "input_tokens_details": {"cache_write_tokens": 7714, "cached_tokens": 0}, "output_tokens": 23, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7740}`
- function_call: `load_capabilities` call_id=`call_5D3AyC8RLFIIIUe7EqACXmf0`
```json
{
  "capabilities": [
    "cap_media_analysis"
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_02af3c800d02aa1a006abe6420e5cc87d1a4f74d7516cd6cdd`
- status: `completed`
- usage: `{"input_tokens": 7717, "input_tokens_details": {"cache_write_tokens": 7714, "cached_tokens": 0}, "output_tokens": 23, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7740}`
- function_call: `load_capabilities` call_id=`call_5D3AyC8RLFIIIUe7EqACXmf0`
```json
{
  "capabilities": [
    "cap_media_analysis"
  ]
}
```

</details>

</details>

<details>
<summary>51. [2026-10-01 16:46:10] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_fee_agreement_provided_by_user

- capabilities: cap_client_read, cap_media_analysis

**input:**

- app's reply to `load_capabilities` (call_id=`call_5D3AyC8RLFIIIUe7EqACXmf0`):
```text
loaded capabilitys: cap_media_analysis. Loaded flows now: flow_fee_agreement_provided_by_user. Loaded capabilities now: cap_client_read, cap_media_analysis. Their instructions and tools are attached starting now.
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'analyze_media', 'mcp']

- previous_response_id: `'resp_02af3c800d02aa1a006abe6420e5cc87d1a4f74d7516cd6cdd'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_fee_agreement_provided_by_user, capabilities=cap_client_read, cap_media_analysis)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_fee_agreement_provided_by_user

- capabilities: cap_client_read, cap_media_analysis

**input:**

- app's reply to `load_capabilities` (call_id=`call_5D3AyC8RLFIIIUe7EqACXmf0`):
```text
loaded capabilitys: cap_media_analysis. Loaded flows now: flow_fee_agreement_provided_by_user. Loaded capabilities now: cap_client_read, cap_media_analysis. Their instructions and tools are attached starting now.
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'analyze_media', 'mcp']

- previous_response_id: `'resp_02af3c800d02aa1a006abe6420e5cc87d1a4f74d7516cd6cdd'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24051 chars)</summary>

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

# Flow: Fee agreement provided by the user

Goal: the user provided a fee agreement, as text or as an image: make sure its client exists in Morning.

Capabilities: `cap_media_analysis`, `cap_client_read`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

1. If the agreement came as an image or document, it must have been read with `cap_media_analysis`'s `analyze_media` (load it and read it now if it was not). Use `cap_send_to_user` to report what it contains so the user can see what you understood. If its `missing_required_fields` is not empty, ask the user for exactly those details and wait for them.
2. The client must be resolved by its exact stored name before moving to the next step - either
   from the recent conversation history if it was already resolved there, or, if not, by loading
   `cap_client_read` and resolving it now. Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Recording the agreement itself happens after the turn ends, from what is in the conversation. There is nothing to load or call for it, so do not try. Your job is only to get the client resolved (or created), so the recorded agreement refers to a real client. It can be recorded only once the conversation holds the client and every payment component's amount; if any is missing, ask the user for it. Never tell the user the agreement was or will be recorded while any of it is missing.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_media_analysis`, `cap_client_read` and this flow, keeping any that other work still in progress needs.


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


# Capability: Media Analysis

You are reading an image, PDF, or DOCX the user sent. Loading this capability attaches one tool, `analyze_media` (no arguments): call it to read the media attached to this turn. Read it before loading any flow for it.

`analyze_media` returns JSON:
- `extracted_text`: the text read off the document.
- `doc_type` (images and PDFs; a DOCX fee agreement also comes back as `agreement`): `bank` (a bank transfer/deposit confirmation), `agreement` (a fee agreement / quote / engagement letter), or `unknown`.
- `fields`: the details read for that `doc_type` - for `bank`: `payer_name`, `amount`, `txn_date`, `bank_number`, `bank_branch`, `bank_account` (and optionally `bank_name`, `reference`, `note`); for `agreement`: `client_name`, `components`.
- `missing_required_fields`: required details that are absent or unreadable in the document.
- `document_analysis` (DOCX): its document type and summary.

What to do with the result:
1. `doc_type` is `bank`: load `flow_payment_received_by_bank_slip_image`.
2. `doc_type` is `agreement`: load `flow_fee_agreement_provided_by_user`.
3. `doc_type` is `unknown`, or there is none: use `cap_send_to_user` to report what the document says and ask the user what it is and what they want done with it. Never guess its type.
4. `missing_required_fields` is not empty: ask the user for exactly those details (in the flow you loaded, or on their own). Never fill them in yourself.
5. When reporting what the document says, report what it actually says: names, dates, amounts, account details, in Hebrew. Nothing it does not say. Reading and stating these details is the task, not something to hold back. Format the report:
   - Start with `סיכום:` followed by a brief Hebrew summary of the content.
   - Then bullets (•) with: the document type (סוג מסמך); key dates, if present; the main parties/entities, if identifiable; important numbers/amounts, if present.
   - End with the facts, not with questions - except the question step 3 or step 4 requires.


## Loaded flows

flow_fee_agreement_provided_by_user

## Loaded capabilities

cap_client_read, cap_media_analysis

---

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>52. [2026-10-01 16:46:12] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_02af3c800d02aa1a006abe6422b10487d1be355bb12df84f47`
- status: `completed`
- usage: `{"input_tokens": 8355, "input_tokens_details": {"cache_write_tokens": 8352, "cached_tokens": 0}, "output_tokens": 47, "output_tokens_details": {"reasoning_tokens": 15}, "total_tokens": 8402}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_CPc1hgbkS2gYfjbDpNQil7vE`
```json
{
  "text": "קורא עכשיו את פרטי ההסכם שבתמונה."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_02af3c800d02aa1a006abe6422b10487d1be355bb12df84f47`
- status: `completed`
- usage: `{"input_tokens": 8355, "input_tokens_details": {"cache_write_tokens": 8352, "cached_tokens": 0}, "output_tokens": 47, "output_tokens_details": {"reasoning_tokens": 15}, "total_tokens": 8402}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_CPc1hgbkS2gYfjbDpNQil7vE`
```json
{
  "text": "קורא עכשיו את פרטי ההסכם שבתמונה."
}
```

</details>

</details>

<details>
<summary>53. [2026-10-01 16:46:12] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_fee_agreement_provided_by_user

- capabilities: cap_client_read, cap_media_analysis

**input:**

- app's reply to `send_progress_update` (call_id=`call_CPc1hgbkS2gYfjbDpNQil7vE`):
```text
{
  "sent": false
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'analyze_media', 'mcp']

- previous_response_id: `'resp_02af3c800d02aa1a006abe6422b10487d1be355bb12df84f47'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_fee_agreement_provided_by_user, capabilities=cap_client_read, cap_media_analysis)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_fee_agreement_provided_by_user

- capabilities: cap_client_read, cap_media_analysis

**input:**

- app's reply to `send_progress_update` (call_id=`call_CPc1hgbkS2gYfjbDpNQil7vE`):
```text
{
  "sent": false
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'analyze_media', 'mcp']

- previous_response_id: `'resp_02af3c800d02aa1a006abe6422b10487d1be355bb12df84f47'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24051 chars)</summary>

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

# Flow: Fee agreement provided by the user

Goal: the user provided a fee agreement, as text or as an image: make sure its client exists in Morning.

Capabilities: `cap_media_analysis`, `cap_client_read`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

1. If the agreement came as an image or document, it must have been read with `cap_media_analysis`'s `analyze_media` (load it and read it now if it was not). Use `cap_send_to_user` to report what it contains so the user can see what you understood. If its `missing_required_fields` is not empty, ask the user for exactly those details and wait for them.
2. The client must be resolved by its exact stored name before moving to the next step - either
   from the recent conversation history if it was already resolved there, or, if not, by loading
   `cap_client_read` and resolving it now. Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Recording the agreement itself happens after the turn ends, from what is in the conversation. There is nothing to load or call for it, so do not try. Your job is only to get the client resolved (or created), so the recorded agreement refers to a real client. It can be recorded only once the conversation holds the client and every payment component's amount; if any is missing, ask the user for it. Never tell the user the agreement was or will be recorded while any of it is missing.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_media_analysis`, `cap_client_read` and this flow, keeping any that other work still in progress needs.


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


# Capability: Media Analysis

You are reading an image, PDF, or DOCX the user sent. Loading this capability attaches one tool, `analyze_media` (no arguments): call it to read the media attached to this turn. Read it before loading any flow for it.

`analyze_media` returns JSON:
- `extracted_text`: the text read off the document.
- `doc_type` (images and PDFs; a DOCX fee agreement also comes back as `agreement`): `bank` (a bank transfer/deposit confirmation), `agreement` (a fee agreement / quote / engagement letter), or `unknown`.
- `fields`: the details read for that `doc_type` - for `bank`: `payer_name`, `amount`, `txn_date`, `bank_number`, `bank_branch`, `bank_account` (and optionally `bank_name`, `reference`, `note`); for `agreement`: `client_name`, `components`.
- `missing_required_fields`: required details that are absent or unreadable in the document.
- `document_analysis` (DOCX): its document type and summary.

What to do with the result:
1. `doc_type` is `bank`: load `flow_payment_received_by_bank_slip_image`.
2. `doc_type` is `agreement`: load `flow_fee_agreement_provided_by_user`.
3. `doc_type` is `unknown`, or there is none: use `cap_send_to_user` to report what the document says and ask the user what it is and what they want done with it. Never guess its type.
4. `missing_required_fields` is not empty: ask the user for exactly those details (in the flow you loaded, or on their own). Never fill them in yourself.
5. When reporting what the document says, report what it actually says: names, dates, amounts, account details, in Hebrew. Nothing it does not say. Reading and stating these details is the task, not something to hold back. Format the report:
   - Start with `סיכום:` followed by a brief Hebrew summary of the content.
   - Then bullets (•) with: the document type (סוג מסמך); key dates, if present; the main parties/entities, if identifiable; important numbers/amounts, if present.
   - End with the facts, not with questions - except the question step 3 or step 4 requires.


## Loaded flows

flow_fee_agreement_provided_by_user

## Loaded capabilities

cap_client_read, cap_media_analysis

---

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>54. [2026-10-01 16:46:13] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_02af3c800d02aa1a006abe642478e887d188a67aab876ad63f`
- status: `completed`
- usage: `{"input_tokens": 8419, "input_tokens_details": {"cache_write_tokens": 64, "cached_tokens": 8352}, "output_tokens": 15, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 8434}`
- function_call: `analyze_media` call_id=`call_UmFMIWmEhImdG2BEY6oK4TJF`
```json
{}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_02af3c800d02aa1a006abe642478e887d188a67aab876ad63f`
- status: `completed`
- usage: `{"input_tokens": 8419, "input_tokens_details": {"cache_write_tokens": 64, "cached_tokens": 8352}, "output_tokens": 15, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 8434}`
- function_call: `analyze_media` call_id=`call_UmFMIWmEhImdG2BEY6oK4TJF`
```json
{}
```

</details>

</details>

<details>
<summary>55. [2026-10-01 16:46:13] APP → VISION MODEL — context=ImageExtractor._vision_extract</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

**input:**

- message (role=user):
```text
נתח תמונה זו וחלץ את כל המידע.

**חשוב: כל התוכן בעברית בלבד - ללא טקסט באנגלית כלל** (פרט לשמות השדות עצמם ב-JSON).

🚨 **לעולם אל תוסיף ניקוד** - לא בטקסט המחולץ, לא בשם, לא בשום שדה. אותיות
עבריות רגילות בלבד. מסמך מקור אינו מנוקד, וניקוד שנוסף על ידך אינו קיים
בפועל במקור - הוא ישבש כל השוואה מדויקת של שמות וערכים בהמשך המערכת.

## 1. חילוץ טקסט
- חלץ את כל הטקסט תוך שמירה על פריסה, פסקאות וקטעי שורה
- שמור על כיוון RTL לטקסט עברי
- **דיוק מוחלט בסכומים, אחוזים ומספרים**: כל סכום, אחוז או מספר המופיע
  במסמך חייב להיות מועתק בדיוק כפי שהוא כתוב. אם המסמך מפרט כמה סכומים
  **שונים במהותם** (למשל תלויים בתנאים, שלבים או מסלולים שונים), רשום כל
  אחד מהם בנפרד יחד עם התנאי/ההקשר המדויק שלו - לעולם אל תמזג, תסכם, או
  תבחר סכום אחד "מייצג" מתוך כמה סכומים שונים שמופיעים בפועל בטקסט.
  **שים לב**: זוג מספרים המתאר סכום בסיס + מע"מ לאותו סעיף/שלב (למשל
  "20,000 ₪ + מע"מ = 23,600 ₪") הוא מספר אחד בלבד עם הקשר מע"מ - אינו שני
  סכומים שונים, ואינו דוגמה למה שיש להפריד. הפרדה נדרשת רק כאשר מדובר
  בשני סעיפים/שלבים/תנאים מהותית שונים במסמך.
- **אי-ודאות מפורשת עדיפה על ניחוש**: אם קטע טקסט אינו קריא בבירור (טשטוש,
  זווית צילום, איכות תמונה נמוכה וכו'), סמן אותו כ"[לא קריא]" במקום להשלים
  מילים או משפטים שנשמעים סבירים בעברית אך אינם מבוססים בפועל על מה שכתוב
  בתמונה. **אבל**: "לא קריא" נאמר רק על מה שבאמת לא ניתן לקרוא. מסמך חד
  ומודפס אינו "מטושטש", וקושי לקרוא ערך אחד אינו סיבה לסמן אותו כלא ודאי אם
  הוא מופיע במקום נוסף וברור במסמך.
- 🚨 **אימות צולב - ערך שמופיע יותר מפעם אחת**: במסמכים בנקאיים אותו נתון
  (במיוחד שם בעל החשבון, הסכום והתאריך) מופיע לרוב **גם** בכותרת החופשית
  **וגם** בשורת שדה מתויגת בטבלת הפרטים. **חובה להשוות ביניהם ולוודא
  התאמה מדויקת, אות באות.** אם הם נבדלים - העתק את הערך מ**השורה
  המתויגת** (למשל "שם חשבון מחויב: ..."), שהיא המקור המהימן, ולא מהכותרת
  החופשית שבה השם עלול להיות דבוק לתחילית (למשל "העברה מ**עטיה** רועי
  מאיר" - התחילית "מ" אינה חלק מהשם).
  שמות פרטיים בעברית נבדלים לעיתים באות אחת בלבד (עטיה/עטה, שרי/שרית) -
  קרא אות אחר אות, ואל תשמיט או תוסיף אותיות.

## 2. סיווג המסמך - `doc_type`

יש בדיוק שלוש אפשרויות. אין אחרות:

- **`bank`** - אישור העברה/הפקדה בנקאית: צילום מסך מאפליקציה או מאתר בנק,
  או אישור העברה מודפס. מסמך כזה מציג תמיד תנועה כספית שכבר בוצעה, ומכיל
  שם המעביר/המשלם, סכום, תאריך ביצוע, ופרטי חשבון (בנק, סניף, מספר חשבון).
- **`agreement`** - הסכם שכר טרחה / הצעת מחיר / מכתב התקשרות: מסמך טקסטואלי,
  לרוב על נייר מכתבים של משרד עורכי דין, המפרט שירות ותנאי תשלום.
- **`unknown`** - כל דבר אחר, **וגם כל מקרה שבו אינך בטוח לחלוטין**.

🚨 **כללי סיווג מחייבים:**
- `bank` ו-`agreement` הם שני סוגי מסמכים שונים לחלוטין במראה ובתוכן. אם
  המסמך אינו בבירור אחד מהם - הסיווג הוא `unknown`. **לעולם אל תנחש.**
- **הימצאות או היעדר טקסט מלווה מהמשתמש אינה רלוונטית לסיווג.** צילום מסך של
  העברה בנקאית שנשלח ללא מילה אחת הוא `bank` בדיוק כמו אחד שנשלח עם הסבר.
  סווג את **המסמך**, לא את כוונת ההודעה.
- טשטוש מקומי או קטע לא קריא **אינם** הופכים מסמך ברור ל-`unknown`. אם סוג
  המסמך ברור אך פרט מסוים אינו קריא - הסיווג נשאר, והפרט החסר נרשם ב-
  `missing_required_fields`.
- **פתק בכתב יד על נייר מחברת/פנקס, ללא נייר מכתבים ובלי תנאי תשלום כתובים,
  אינו `agreement`.** רשימה של שם אחד או כמה שמות עם סכומים לצידם, בכתב יד,
  בלי תיאור שירות, בלי צדדים/היקף/תנאים ובלי חתימה - היא פתק עבודה אישי,
  לא הסכם שכר טרחה. הסיווג: `unknown`.
- 🚨 **בספק - `unknown`, ותן למערכת לשאול.** אם עולה בך ולו שאלה אחת לגבי
  סוג המסמך, או שהיית רוצה לברר עם המשתמש לפני שתחליט - זו בדיוק המשמעות של
  `unknown`. עדיף להחזיר `unknown` ולתת למערכת לשאול את המשתמש, מאשר לבחור
  סוג ולטעות. שאילת שאלה היא מעלה ולא כישלון; ניחוש שגוי הוא הכישלון.

## 3. שדות לפי סוג - `fields`

**עבור `bank`** (כל אלה נדרשים):
`payer_name` (שם המעביר/המשלם), `amount` (מספר בלבד, ללא ₪ ופסיקים),
`txn_date` (תאריך ביצוע ההעברה בפורמט DD/MM/YYYY), ושלושת **המספרים** של
החשבון: `bank_number` (מספר הבנק - **המספר, לא השם**), `bank_branch`
(מספר הסניף), `bank_account` (מספר החשבון).
**שים לב**: לרוב מופיעים גם שם הבנק וגם מספרו (למשל "בנק הפועלים 12" או
"12-613-123456"). הנדרש הוא **המספר**. אם שם הבנק מופיע גם הוא, אפשר לרשום
אותו בנוסף ב-`bank_name`, אך הוא אינו תחליף ל-`bank_number`.
אופציונלי: `bank_name` (שם הבנק), `reference` (מספר אסמכתה),
`note` (הערת הלקוח/תיאור).

**עבור `agreement`** (כל אלה נדרשים):
`client_name`, `components` - מערך, פריט אחד לכל רכיב תשלום נפרד, כל אחד עם
`amount`, `description`, ו-`vat_status` ("כולל"/"לא כולל"/"לא צוין").
אופציונלי: `agreement_date`.

**עבור `unknown`**: אובייקט ריק.

כל שדה נדרש שאינו קיים או אינו קריא במסמך - רשום את שמו ב-
`missing_required_fields` ו**אל תמציא לו ערך**.

## 4. מה לא לעשות
אל תנסח הודעה למשתמש ואל תוסיף פרשנות, המלצה או שאלה. תפקידך כאן הוא **חילוץ
וסיווג בלבד** - הניסוח למשתמש נבנה בשלב מאוחר יותר מתוך הטקסט שחילצת.
 addressing the user's question, focusing on what the user asked about


User's question/message: ההסכם החתום, תרשום ביומן

## פורמט התשובה

החזר **JSON תקין בלבד** - ללא הסברים לפניו או אחריו, וללא סימוני קוד:

{
  "doc_type": "bank",
  "extracted_text": "כל הטקסט שחולץ מהתמונה, עם שורות ומבנה",
  "fields": {
    "payer_name": "ישראל ישראלי",
    "amount": 1500,
    "txn_date": "12/07/2026",
    "bank_number": "12",
    "bank_branch": "613",
    "bank_account": "123456",
    "bank_name": "בנק הפועלים",
    "reference": "0169116729",
    "note": "ייעוץ משפטי"
  },
  "missing_required_fields": []
}

```
  - image: `<redacted data URL, 96187 chars>` detail=`high`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

**input:**

- message (role=user):
```text
נתח תמונה זו וחלץ את כל המידע.

**חשוב: כל התוכן בעברית בלבד - ללא טקסט באנגלית כלל** (פרט לשמות השדות עצמם ב-JSON).

🚨 **לעולם אל תוסיף ניקוד** - לא בטקסט המחולץ, לא בשם, לא בשום שדה. אותיות
עבריות רגילות בלבד. מסמך מקור אינו מנוקד, וניקוד שנוסף על ידך אינו קיים
בפועל במקור - הוא ישבש כל השוואה מדויקת של שמות וערכים בהמשך המערכת.

## 1. חילוץ טקסט
- חלץ את כל הטקסט תוך שמירה על פריסה, פסקאות וקטעי שורה
- שמור על כיוון RTL לטקסט עברי
- **דיוק מוחלט בסכומים, אחוזים ומספרים**: כל סכום, אחוז או מספר המופיע
  במסמך חייב להיות מועתק בדיוק כפי שהוא כתוב. אם המסמך מפרט כמה סכומים
  **שונים במהותם** (למשל תלויים בתנאים, שלבים או מסלולים שונים), רשום כל
  אחד מהם בנפרד יחד עם התנאי/ההקשר המדויק שלו - לעולם אל תמזג, תסכם, או
  תבחר סכום אחד "מייצג" מתוך כמה סכומים שונים שמופיעים בפועל בטקסט.
  **שים לב**: זוג מספרים המתאר סכום בסיס + מע"מ לאותו סעיף/שלב (למשל
  "20,000 ₪ + מע"מ = 23,600 ₪") הוא מספר אחד בלבד עם הקשר מע"מ - אינו שני
  סכומים שונים, ואינו דוגמה למה שיש להפריד. הפרדה נדרשת רק כאשר מדובר
  בשני סעיפים/שלבים/תנאים מהותית שונים במסמך.
- **אי-ודאות מפורשת עדיפה על ניחוש**: אם קטע טקסט אינו קריא בבירור (טשטוש,
  זווית צילום, איכות תמונה נמוכה וכו'), סמן אותו כ"[לא קריא]" במקום להשלים
  מילים או משפטים שנשמעים סבירים בעברית אך אינם מבוססים בפועל על מה שכתוב
  בתמונה. **אבל**: "לא קריא" נאמר רק על מה שבאמת לא ניתן לקרוא. מסמך חד
  ומודפס אינו "מטושטש", וקושי לקרוא ערך אחד אינו סיבה לסמן אותו כלא ודאי אם
  הוא מופיע במקום נוסף וברור במסמך.
- 🚨 **אימות צולב - ערך שמופיע יותר מפעם אחת**: במסמכים בנקאיים אותו נתון
  (במיוחד שם בעל החשבון, הסכום והתאריך) מופיע לרוב **גם** בכותרת החופשית
  **וגם** בשורת שדה מתויגת בטבלת הפרטים. **חובה להשוות ביניהם ולוודא
  התאמה מדויקת, אות באות.** אם הם נבדלים - העתק את הערך מ**השורה
  המתויגת** (למשל "שם חשבון מחויב: ..."), שהיא המקור המהימן, ולא מהכותרת
  החופשית שבה השם עלול להיות דבוק לתחילית (למשל "העברה מ**עטיה** רועי
  מאיר" - התחילית "מ" אינה חלק מהשם).
  שמות פרטיים בעברית נבדלים לעיתים באות אחת בלבד (עטיה/עטה, שרי/שרית) -
  קרא אות אחר אות, ואל תשמיט או תוסיף אותיות.

## 2. סיווג המסמך - `doc_type`

יש בדיוק שלוש אפשרויות. אין אחרות:

- **`bank`** - אישור העברה/הפקדה בנקאית: צילום מסך מאפליקציה או מאתר בנק,
  או אישור העברה מודפס. מסמך כזה מציג תמיד תנועה כספית שכבר בוצעה, ומכיל
  שם המעביר/המשלם, סכום, תאריך ביצוע, ופרטי חשבון (בנק, סניף, מספר חשבון).
- **`agreement`** - הסכם שכר טרחה / הצעת מחיר / מכתב התקשרות: מסמך טקסטואלי,
  לרוב על נייר מכתבים של משרד עורכי דין, המפרט שירות ותנאי תשלום.
- **`unknown`** - כל דבר אחר, **וגם כל מקרה שבו אינך בטוח לחלוטין**.

🚨 **כללי סיווג מחייבים:**
- `bank` ו-`agreement` הם שני סוגי מסמכים שונים לחלוטין במראה ובתוכן. אם
  המסמך אינו בבירור אחד מהם - הסיווג הוא `unknown`. **לעולם אל תנחש.**
- **הימצאות או היעדר טקסט מלווה מהמשתמש אינה רלוונטית לסיווג.** צילום מסך של
  העברה בנקאית שנשלח ללא מילה אחת הוא `bank` בדיוק כמו אחד שנשלח עם הסבר.
  סווג את **המסמך**, לא את כוונת ההודעה.
- טשטוש מקומי או קטע לא קריא **אינם** הופכים מסמך ברור ל-`unknown`. אם סוג
  המסמך ברור אך פרט מסוים אינו קריא - הסיווג נשאר, והפרט החסר נרשם ב-
  `missing_required_fields`.
- **פתק בכתב יד על נייר מחברת/פנקס, ללא נייר מכתבים ובלי תנאי תשלום כתובים,
  אינו `agreement`.** רשימה של שם אחד או כמה שמות עם סכומים לצידם, בכתב יד,
  בלי תיאור שירות, בלי צדדים/היקף/תנאים ובלי חתימה - היא פתק עבודה אישי,
  לא הסכם שכר טרחה. הסיווג: `unknown`.
- 🚨 **בספק - `unknown`, ותן למערכת לשאול.** אם עולה בך ולו שאלה אחת לגבי
  סוג המסמך, או שהיית רוצה לברר עם המשתמש לפני שתחליט - זו בדיוק המשמעות של
  `unknown`. עדיף להחזיר `unknown` ולתת למערכת לשאול את המשתמש, מאשר לבחור
  סוג ולטעות. שאילת שאלה היא מעלה ולא כישלון; ניחוש שגוי הוא הכישלון.

## 3. שדות לפי סוג - `fields`

**עבור `bank`** (כל אלה נדרשים):
`payer_name` (שם המעביר/המשלם), `amount` (מספר בלבד, ללא ₪ ופסיקים),
`txn_date` (תאריך ביצוע ההעברה בפורמט DD/MM/YYYY), ושלושת **המספרים** של
החשבון: `bank_number` (מספר הבנק - **המספר, לא השם**), `bank_branch`
(מספר הסניף), `bank_account` (מספר החשבון).
**שים לב**: לרוב מופיעים גם שם הבנק וגם מספרו (למשל "בנק הפועלים 12" או
"12-613-123456"). הנדרש הוא **המספר**. אם שם הבנק מופיע גם הוא, אפשר לרשום
אותו בנוסף ב-`bank_name`, אך הוא אינו תחליף ל-`bank_number`.
אופציונלי: `bank_name` (שם הבנק), `reference` (מספר אסמכתה),
`note` (הערת הלקוח/תיאור).

**עבור `agreement`** (כל אלה נדרשים):
`client_name`, `components` - מערך, פריט אחד לכל רכיב תשלום נפרד, כל אחד עם
`amount`, `description`, ו-`vat_status` ("כולל"/"לא כולל"/"לא צוין").
אופציונלי: `agreement_date`.

**עבור `unknown`**: אובייקט ריק.

כל שדה נדרש שאינו קיים או אינו קריא במסמך - רשום את שמו ב-
`missing_required_fields` ו**אל תמציא לו ערך**.

## 4. מה לא לעשות
אל תנסח הודעה למשתמש ואל תוסיף פרשנות, המלצה או שאלה. תפקידך כאן הוא **חילוץ
וסיווג בלבד** - הניסוח למשתמש נבנה בשלב מאוחר יותר מתוך הטקסט שחילצת.
 addressing the user's question, focusing on what the user asked about


User's question/message: ההסכם החתום, תרשום ביומן

## פורמט התשובה

החזר **JSON תקין בלבד** - ללא הסברים לפניו או אחריו, וללא סימוני קוד:

{
  "doc_type": "bank",
  "extracted_text": "כל הטקסט שחולץ מהתמונה, עם שורות ומבנה",
  "fields": {
    "payer_name": "ישראל ישראלי",
    "amount": 1500,
    "txn_date": "12/07/2026",
    "bank_number": "12",
    "bank_branch": "613",
    "bank_account": "123456",
    "bank_name": "בנק הפועלים",
    "reference": "0169116729",
    "note": "ייעוץ משפטי"
  },
  "missing_required_fields": []
}

```
  - image: `<redacted data URL, 96187 chars>` detail=`high`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

</details>

</details>

<details>
<summary>56. [2026-10-01 16:46:23] VISION MODEL → APP — context=ImageExtractor._vision_extract</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_08b1be9aaead2e4b006abe6425da8487d1a6de092e714ee6fe`
- status: `completed`
- usage: `{"input_tokens": 3549, "input_tokens_details": {"cache_write_tokens": 3546, "cached_tokens": 0}, "output_tokens": 1150, "output_tokens_details": {"reasoning_tokens": 516}, "total_tokens": 4699}`
- reasoning item (content not user-visible)
- message (role=assistant): '{\n  "doc_type": "agreement",\n  "extracted_text": "אילה הוניגמן\\nעורכת דין\\n\\n27.1.253\\n\\nהצעת שכר טרחה\\n\\nבין מר שחר פישר (להלן - הלקוח)\\nלבין\\nעו״ד אילה הוניגמן (להלן - עוה״ד)\\n\\n1. שכר הטרחה בגין הייצוג המשפטי (להלן - ״שכר הטרחה״):\\n\\nבעבור ייצוג הלקוח על ידי עוה״ד, בתביעה שהוגשה כנגדו לבית הדין האזורי לעבודה, ישלם הלקוח בהתאם למתווה הבא:\\n\\nא. הכנת והגשת כתב הגנה כמו גם ייצוג בשלבים מקדמיים (טרם תחילת הוכחות כולל קדם משפט ולא כולל גישור, ככל שיהיה) – 10,000 ₪ לא כולל מע״מ.\\n\\nב. גישור (ככל שיהיה) – תשלום שעתי, בתעריף של 800 ₪ לשעה, לא כולל מע״מ וזאת עד לתקרה של 10 שעות.\\n\\nג. הוכחות – 15,000 ₪ לא כולל מע״מ.\\n\\nד. סיכומים – 5,000 ₪ לא כולל מע״מ.\\n\\nשכר הטרחה המפורט לעיל אינו כולל ייצוג בערכאות ערעור.\\n\\n2. הוצאות:\\n\\nא. שכר הטרחה של עוה״ד לא כולל הוצאות כגון צילום חומרים, אגרות וכיוב׳. הלקוח ישא באופן בלעדי בהוצאות אשר ישולמו מיד בעת המצאת חשבונית.\\n\\nתאריך: ______________\\n\\nשם וחתימה: ______________",\n  "fields": {\n    "client_name": "מר שחר פישר",\n    "components": [\n      {\n        "amount": "10,000",\n        "description": "הכנת והגשת כתב הגנה כמו גם ייצוג בשלבים מקדמיים, טרם תחילת הוכחות, כולל קדם משפט ולא כולל גישור, ככל שיהיה",\n        "vat_status": "לא כולל"\n      },\n      {\n        "amount": "800",\n        "description": "גישור, ככל שיהיה, תשלום שעתי בתעריף של 800 ₪ לשעה, עד לתקרה של 10 שעות",\n        "vat_status": "לא כולל"\n      },\n      {\n        "amount": "15,000",\n        "description": "הוכחות",\n        "vat_status": "לא כולל"\n      },\n      {\n        "amount": "5,000",\n        "description": "סיכומים",\n        "vat_status": "לא כולל"\n      }\n    ],\n    "agreement_date": "27.1.253"\n  },\n  "missing_required_fields": []\n}'

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_08b1be9aaead2e4b006abe6425da8487d1a6de092e714ee6fe`
- status: `completed`
- usage: `{"input_tokens": 3549, "input_tokens_details": {"cache_write_tokens": 3546, "cached_tokens": 0}, "output_tokens": 1150, "output_tokens_details": {"reasoning_tokens": 516}, "total_tokens": 4699}`
- reasoning item (content not user-visible)
- message (role=assistant): '{\n  "doc_type": "agreement",\n  "extracted_text": "אילה הוניגמן\\nעורכת דין\\n\\n27.1.253\\n\\nהצעת שכר טרחה\\n\\nבין מר שחר פישר (להלן - הלקוח)\\nלבין\\nעו״ד אילה הוניגמן (להלן - עוה״ד)\\n\\n1. שכר הטרחה בגין הייצוג המשפטי (להלן - ״שכר הטרחה״):\\n\\nבעבור ייצוג הלקוח על ידי עוה״ד, בתביעה שהוגשה כנגדו לבית הדין האזורי לעבודה, ישלם הלקוח בהתאם למתווה הבא:\\n\\nא. הכנת והגשת כתב הגנה כמו גם ייצוג בשלבים מקדמיים (טרם תחילת הוכחות כולל קדם משפט ולא כולל גישור, ככל שיהיה) – 10,000 ₪ לא כולל מע״מ.\\n\\nב. גישור (ככל שיהיה) – תשלום שעתי, בתעריף של 800 ₪ לשעה, לא כולל מע״מ וזאת עד לתקרה של 10 שעות.\\n\\nג. הוכחות – 15,000 ₪ לא כולל מע״מ.\\n\\nד. סיכומים – 5,000 ₪ לא כולל מע״מ.\\n\\nשכר הטרחה המפורט לעיל אינו כולל ייצוג בערכאות ערעור.\\n\\n2. הוצאות:\\n\\nא. שכר הטרחה של עוה״ד לא כולל הוצאות כגון צילום חומרים, אגרות וכיוב׳. הלקוח ישא באופן בלעדי בהוצאות אשר ישולמו מיד בעת המצאת חשבונית.\\n\\nתאריך: ______________\\n\\nשם וחתימה: ______________",\n  "fields": {\n    "client_name": "מר שחר פישר",\n    "components": [\n      {\n        "amount": "10,000",\n        "description": "הכנת והגשת כתב הגנה כמו גם ייצוג בשלבים מקדמיים, טרם תחילת הוכחות, כולל קדם משפט ולא כולל גישור, ככל שיהיה",\n        "vat_status": "לא כולל"\n      },\n      {\n        "amount": "800",\n        "description": "גישור, ככל שיהיה, תשלום שעתי בתעריף של 800 ₪ לשעה, עד לתקרה של 10 שעות",\n        "vat_status": "לא כולל"\n      },\n      {\n        "amount": "15,000",\n        "description": "הוכחות",\n        "vat_status": "לא כולל"\n      },\n      {\n        "amount": "5,000",\n        "description": "סיכומים",\n        "vat_status": "לא כולל"\n      }\n    ],\n    "agreement_date": "27.1.253"\n  },\n  "missing_required_fields": []\n}'

</details>

</details>

<details>
<summary>57. [2026-10-01 16:46:23] APP-INTERNAL: tool dispatch outcome</summary>

```text
[CAPABILITY-AUDIT] capability='cap_media_analysis' outcome='success' note='analyze_media({})' detail='{\n  "extracted_text": "אילה הוניגמן\\nעורכת דין\\n\\n27.1.253\\n\\nהצעת שכר טרחה\\n\\nבין מר שחר פישר (להלן - הלקוח)\\nלבין\\nעו״ד אילה הוניגמן (להלן - עוה״ד)\\n\\n1. שכר הטרחה בגין הייצוג המשפטי (להלן - ״שכר הטרחה״):\\n\\nבעבור ייצוג הלקוח על ידי עוה״ד, בתביעה שהוגשה כנגדו לבית הדין האזורי לעבודה, ישלם הלקוח בהתאם למתווה הבא:\\n\\nא. הכנת והגשת כתב הגנה כמו גם ייצוג בשלבים מקדמיים (טרם תחילת הוכחות כולל קדם משפט ולא כולל גישור, ככל שיהיה) – 10,000 ₪ לא כולל מע״מ.\\n\\nב. גישור (ככל שיהיה) – תשלום שעתי, בתעריף של 800 ₪ לשעה, לא כולל מע״מ וזאת עד לתקרה של 10 שעות.\\n\\nג. הוכחות – 15,000 ₪ לא כולל מע״מ.\\n\\nד. סיכומים – 5,000 ₪ לא כולל מע״מ.\\n\\nשכר הטרחה המפורט לעיל אינו כולל ייצוג בערכאות ערעור.\\n\\n2. הוצאות:\\n\\nא. שכר הטרחה של עוה״ד לא כולל הוצאות כגון צילום חומרים, אגרות וכיוב׳. הלקוח ישא באופן בלעדי בהוצאות אשר ישולמו מיד בעת המצאת חשבונית.\\n\\nתאריך: ______________\\n\\nשם וחתימה: ______________",\n  "doc_type": "agreement",\n  "fields": {\n    "client_name": "מר שחר פישר",\n    "components": [\n      {\n        "amount": "10,000",\n        "description": "הכנת והגשת כתב הגנה כמו גם ייצוג בשלבים מקדמיים, טרם תחילת הוכחות, כולל קדם משפט ולא כולל גישור, ככל שיהיה",\n        "vat_status": "לא כולל"\n      },\n      {\n        "amount": "800",\n        "description": "גישור, ככל שיהיה, תשלום שעתי בתעריף של 800 ₪ לשעה, עד לתקרה של 10 שעות",\n        "vat_status": "לא כולל"\n      },\n      {\n        "amount": "15,000",\n        "description": "הוכחות",\n        "vat_status": "לא כולל"\n      },\n      {\n        "amount": "5,000",\n        "description": "סיכומים",\n        "vat_status": "לא כולל"\n      }\n    ],\n    "agreement_date": "27.1.253"\n  }\n}'
```

</details>

<details>
<summary>58. [2026-10-01 16:46:23] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_fee_agreement_provided_by_user

- capabilities: cap_client_read, cap_media_analysis

**input:**

- app's reply to `analyze_media` (call_id=`call_UmFMIWmEhImdG2BEY6oK4TJF`):
```text
{
  "extracted_text": "אילה הוניגמן\nעורכת דין\n\n27.1.253\n\nהצעת שכר טרחה\n\nבין מר שחר פישר (להלן - הלקוח)\nלבין\nעו״ד אילה הוניגמן (להלן - עוה״ד)\n\n1. שכר הטרחה בגין הייצוג המשפטי (להלן - ״שכר הטרחה״):\n\nבעבור ייצוג הלקוח על ידי עוה״ד, בתביעה שהוגשה כנגדו לבית הדין האזורי לעבודה, ישלם הלקוח בהתאם למתווה הבא:\n\nא. הכנת והגשת כתב הגנה כמו גם ייצוג בשלבים מקדמיים (טרם תחילת הוכחות כולל קדם משפט ולא כולל גישור, ככל שיהיה) – 10,000 ₪ לא כולל מע״מ.\n\nב. גישור (ככל שיהיה) – תשלום שעתי, בתעריף של 800 ₪ לשעה, לא כולל מע״מ וזאת עד לתקרה של 10 שעות.\n\nג. הוכחות – 15,000 ₪ לא כולל מע״מ.\n\nד. סיכומים – 5,000 ₪ לא כולל מע״מ.\n\nשכר הטרחה המפורט לעיל אינו כולל ייצוג בערכאות ערעור.\n\n2. הוצאות:\n\nא. שכר הטרחה של עוה״ד לא כולל הוצאות כגון צילום חומרים, אגרות וכיוב׳. הלקוח ישא באופן בלעדי בהוצאות אשר ישולמו מיד בעת המצאת חשבונית.\n\nתאריך: ______________\n\nשם וחתימה: ______________",
  "doc_type": "agreement",
  "fields": {
    "client_name": "מר שחר פישר",
    "components": [
      {
        "amount": "10,000",
        "description": "הכנת והגשת כתב הגנה כמו גם ייצוג בשלבים מקדמיים, טרם תחילת הוכחות, כולל קדם משפט ולא כולל גישור, ככל שיהיה",
        "vat_status": "לא כולל"
      },
      {
        "amount": "800",
        "description": "גישור, ככל שיהיה, תשלום שעתי בתעריף של 800 ₪ לשעה, עד לתקרה של 10 שעות",
        "vat_status": "לא כולל"
      },
      {
        "amount": "15,000",
        "description": "הוכחות",
        "vat_status": "לא כולל"
      },
      {
        "amount": "5,000",
        "description": "סיכומים",
        "vat_status": "לא כולל"
      }
    ],
    "agreement_date": "27.1.253"
  }
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'analyze_media', 'mcp']

- previous_response_id: `'resp_02af3c800d02aa1a006abe642478e887d188a67aab876ad63f'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_fee_agreement_provided_by_user, capabilities=cap_client_read, cap_media_analysis)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_fee_agreement_provided_by_user

- capabilities: cap_client_read, cap_media_analysis

**input:**

- app's reply to `analyze_media` (call_id=`call_UmFMIWmEhImdG2BEY6oK4TJF`):
```text
{
  "extracted_text": "אילה הוניגמן\nעורכת דין\n\n27.1.253\n\nהצעת שכר טרחה\n\nבין מר שחר פישר (להלן - הלקוח)\nלבין\nעו״ד אילה הוניגמן (להלן - עוה״ד)\n\n1. שכר הטרחה בגין הייצוג המשפטי (להלן - ״שכר הטרחה״):\n\nבעבור ייצוג הלקוח על ידי עוה״ד, בתביעה שהוגשה כנגדו לבית הדין האזורי לעבודה, ישלם הלקוח בהתאם למתווה הבא:\n\nא. הכנת והגשת כתב הגנה כמו גם ייצוג בשלבים מקדמיים (טרם תחילת הוכחות כולל קדם משפט ולא כולל גישור, ככל שיהיה) – 10,000 ₪ לא כולל מע״מ.\n\nב. גישור (ככל שיהיה) – תשלום שעתי, בתעריף של 800 ₪ לשעה, לא כולל מע״מ וזאת עד לתקרה של 10 שעות.\n\nג. הוכחות – 15,000 ₪ לא כולל מע״מ.\n\nד. סיכומים – 5,000 ₪ לא כולל מע״מ.\n\nשכר הטרחה המפורט לעיל אינו כולל ייצוג בערכאות ערעור.\n\n2. הוצאות:\n\nא. שכר הטרחה של עוה״ד לא כולל הוצאות כגון צילום חומרים, אגרות וכיוב׳. הלקוח ישא באופן בלעדי בהוצאות אשר ישולמו מיד בעת המצאת חשבונית.\n\nתאריך: ______________\n\nשם וחתימה: ______________",
  "doc_type": "agreement",
  "fields": {
    "client_name": "מר שחר פישר",
    "components": [
      {
        "amount": "10,000",
        "description": "הכנת והגשת כתב הגנה כמו גם ייצוג בשלבים מקדמיים, טרם תחילת הוכחות, כולל קדם משפט ולא כולל גישור, ככל שיהיה",
        "vat_status": "לא כולל"
      },
      {
        "amount": "800",
        "description": "גישור, ככל שיהיה, תשלום שעתי בתעריף של 800 ₪ לשעה, עד לתקרה של 10 שעות",
        "vat_status": "לא כולל"
      },
      {
        "amount": "15,000",
        "description": "הוכחות",
        "vat_status": "לא כולל"
      },
      {
        "amount": "5,000",
        "description": "סיכומים",
        "vat_status": "לא כולל"
      }
    ],
    "agreement_date": "27.1.253"
  }
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'analyze_media', 'mcp']

- previous_response_id: `'resp_02af3c800d02aa1a006abe642478e887d188a67aab876ad63f'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (24051 chars)</summary>

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

# Flow: Fee agreement provided by the user

Goal: the user provided a fee agreement, as text or as an image: make sure its client exists in Morning.

Capabilities: `cap_media_analysis`, `cap_client_read`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

1. If the agreement came as an image or document, it must have been read with `cap_media_analysis`'s `analyze_media` (load it and read it now if it was not). Use `cap_send_to_user` to report what it contains so the user can see what you understood. If its `missing_required_fields` is not empty, ask the user for exactly those details and wait for them.
2. The client must be resolved by its exact stored name before moving to the next step - either
   from the recent conversation history if it was already resolved there, or, if not, by loading
   `cap_client_read` and resolving it now. Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Recording the agreement itself happens after the turn ends, from what is in the conversation. There is nothing to load or call for it, so do not try. Your job is only to get the client resolved (or created), so the recorded agreement refers to a real client. It can be recorded only once the conversation holds the client and every payment component's amount; if any is missing, ask the user for it. Never tell the user the agreement was or will be recorded while any of it is missing.
4. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
5. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_media_analysis`, `cap_client_read` and this flow, keeping any that other work still in progress needs.


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


# Capability: Media Analysis

You are reading an image, PDF, or DOCX the user sent. Loading this capability attaches one tool, `analyze_media` (no arguments): call it to read the media attached to this turn. Read it before loading any flow for it.

`analyze_media` returns JSON:
- `extracted_text`: the text read off the document.
- `doc_type` (images and PDFs; a DOCX fee agreement also comes back as `agreement`): `bank` (a bank transfer/deposit confirmation), `agreement` (a fee agreement / quote / engagement letter), or `unknown`.
- `fields`: the details read for that `doc_type` - for `bank`: `payer_name`, `amount`, `txn_date`, `bank_number`, `bank_branch`, `bank_account` (and optionally `bank_name`, `reference`, `note`); for `agreement`: `client_name`, `components`.
- `missing_required_fields`: required details that are absent or unreadable in the document.
- `document_analysis` (DOCX): its document type and summary.

What to do with the result:
1. `doc_type` is `bank`: load `flow_payment_received_by_bank_slip_image`.
2. `doc_type` is `agreement`: load `flow_fee_agreement_provided_by_user`.
3. `doc_type` is `unknown`, or there is none: use `cap_send_to_user` to report what the document says and ask the user what it is and what they want done with it. Never guess its type.
4. `missing_required_fields` is not empty: ask the user for exactly those details (in the flow you loaded, or on their own). Never fill them in yourself.
5. When reporting what the document says, report what it actually says: names, dates, amounts, account details, in Hebrew. Nothing it does not say. Reading and stating these details is the task, not something to hold back. Format the report:
   - Start with `סיכום:` followed by a brief Hebrew summary of the content.
   - Then bullets (•) with: the document type (סוג מסמך); key dates, if present; the main parties/entities, if identifiable; important numbers/amounts, if present.
   - End with the facts, not with questions - except the question step 3 or step 4 requires.


## Loaded flows

flow_fee_agreement_provided_by_user

## Loaded capabilities

cap_client_read, cap_media_analysis

---

THE CURRENT DATE AND TIME IS 2026-10-01 16:45 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>59. [2026-10-01 16:46:29] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_02af3c800d02aa1a006abe642fb38887d188067e11dd4034c3`
- status: `completed`
- usage: `{"input_tokens": 9067, "input_tokens_details": {"cache_write_tokens": 648, "cached_tokens": 8416}, "output_tokens": 441, "output_tokens_details": {"reasoning_tokens": 247}, "total_tokens": 9508}`
- reasoning item (content not user-visible)
- function_call: `send_to_user` call_id=`call_mlKVXcBM4aJYFKYPbHGu1PAw`
```json
{
  "text": "סיכום: נמצא הסכם שכר טרחה חתום עבור שחר פישר, בנוגע לייצוג בתביעה בבית הדין האזורי לעבודה.\n\n• סוג מסמך: הצעת שכר טרחה חתומה\n• תאריך שמופיע במסמך: 27.1.253\n• שלבים וסכומים: כתב הגנה ושלבים מקדמיים – 10,000 ₪; גישור – 800 ₪ לשעה, עד 10 שעות; הוכחות – 15,000 ₪; סיכומים – 5,000 ₪\n• כל הסכומים אינם כוללים מע״מ\n• הוצאות נלוות אינן כלולות\n\nהלקוח שחר פישר מזוהה במערכת, ולכן ההסכם מוכן לרישום ביומן."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_02af3c800d02aa1a006abe642fb38887d188067e11dd4034c3`
- status: `completed`
- usage: `{"input_tokens": 9067, "input_tokens_details": {"cache_write_tokens": 648, "cached_tokens": 8416}, "output_tokens": 441, "output_tokens_details": {"reasoning_tokens": 247}, "total_tokens": 9508}`
- reasoning item (content not user-visible)
- function_call: `send_to_user` call_id=`call_mlKVXcBM4aJYFKYPbHGu1PAw`
```json
{
  "text": "סיכום: נמצא הסכם שכר טרחה חתום עבור שחר פישר, בנוגע לייצוג בתביעה בבית הדין האזורי לעבודה.\n\n• סוג מסמך: הצעת שכר טרחה חתומה\n• תאריך שמופיע במסמך: 27.1.253\n• שלבים וסכומים: כתב הגנה ושלבים מקדמיים – 10,000 ₪; גישור – 800 ₪ לשעה, עד 10 שעות; הוכחות – 15,000 ₪; סיכומים – 5,000 ₪\n• כל הסכומים אינם כוללים מע״מ\n• הוצאות נלוות אינן כלולות\n\nהלקוח שחר פישר מזוהה במערכת, ולכן ההסכם מוכן לרישום ביומן."
}
```

</details>

</details>

<details>
<summary>60. [2026-10-01 16:46:29] APP → USER — context=text</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972501234567@c.us",
  "message": "סיכום: נמצא הסכם שכר טרחה חתום עבור שחר פישר, בנוגע לייצוג בתביעה בבית הדין האזורי לעבודה.\n\n• סוג מסמך: הצעת שכר טרחה חתומה\n• תאריך שמופיע במסמך: 27.1.253\n• שלבים וסכומים: כתב הגנה ושלבים מקדמיים – 10,000 ₪; גישור – 800 ₪ לשעה, עד 10 שעות; הוכחות – 15,000 ₪; סיכומים – 5,000 ₪\n• כל הסכומים אינם כוללים מע״מ\n• הוצאות נלוות אינן כלולות\n\nהלקוח שחר פישר מזוהה במערכת, ולכן ההסכם מוכן לרישום ביומן."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "972501234567@c.us",
  "message": "סיכום: נמצא הסכם שכר טרחה חתום עבור שחר פישר, בנוגע לייצוג בתביעה בבית הדין האזורי לעבודה.\n\n• סוג מסמך: הצעת שכר טרחה חתומה\n• תאריך שמופיע במסמך: 27.1.253\n• שלבים וסכומים: כתב הגנה ושלבים מקדמיים – 10,000 ₪; גישור – 800 ₪ לשעה, עד 10 שעות; הוכחות – 15,000 ₪; סיכומים – 5,000 ₪\n• כל הסכומים אינם כוללים מע״מ\n• הוצאות נלוות אינן כלולות\n\nהלקוח שחר פישר מזוהה במערכת, ולכן ההסכם מוכן לרישום ביומן."
}
```

</details>

</details>

<details>
<summary>61. [2026-10-01 16:46:29] APP → MODEL — context=recognize_ledger_event</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

**input:**

```json
{"role": "user", "content": "THE CONVERSATION WINDOW (the last 1h, oldest first) - '<message_id> [<role>] <content>':\n9d7a9609-333f-41d3-85ff-dc79af1ef735 [godfather] פרטים על הלקוח שחר פישר\n36d3142d-63a2-4ae8-93d3-62a8f559cb26 [assistant] בודק את פרטי הלקוח במערכת.\n763eaa3c-b8d1-4997-a37b-fd2b616aabdc [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: הבקשה היא לאחזר את פרטי הלקוח שחר פישר. עדיין לא בוצע חיפוש.\nTHIS TURN'S PURPOSE: לאתר את הלקוח המדויק במערכת ולהחזיר את פרטיו האישיים בלבד.\nEXPECTATION: אטען יכולת לקריאת לקוחות, אחפש את הלקוח, ואז אחזיר את התוצאה או אבקש הבהרה אם יש כמה התאמות.\nada30b46-ba49-491e-b5a9-55b7853934ca [assistant] מאתר את השם המדויק כפי שהוא שמור במערכת.\ndd20e6ed-fa19-4e07-966d-e6739d89f615 [assistant] מצאתי את הלקוח. עכשיו אני שולף את הפרטים השמורים.\nfa4d2b8b-5ed2-4d2c-b9e3-019838928f64 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: נמצא הלקוח שחר פישר ונשלפו פרטיו המדויקים ממערכת מורנינג.\nTHIS TURN'S PURPOSE: להחזיר למשתמש את פרטי הלקוח בעברית ובקיצור.\nEXPECTATION: המשימה הושלמה בהצלחה; אין צורך בשאלה נוספת.\n297c0b0c-a2fa-4784-ad37-e9555685798e [assistant] פרטי הלקוח שחר פישר:\n\nשם: שחר פישר\nדוא״ל: e2e-client-843832@example.com\nטלפון: 050-1234567\nמספר עוסק או חברה: לא שמור\n    (morning MCP call on this message's turn) {\"name\": \"resolve_client_name\", \"error\": null, \"arguments\": \"{\\\"name\\\":\\\"שחר פישר\\\"}\", \"output\": \"{\\\"status\\\": \\\"resolved\\\", \\\"name\\\": \\\"\\\\u05e9\\\\u05d7\\\\u05e8 \\\\u05e4\\\\u05d9\\\\u05e9\\\\u05e8\\\"}\"}\n    (morning MCP call on this message's turn) {\"name\": \"get_client_details\", \"error\": null, \"arguments\": \"{\\\"name\\\":\\\"שחר פישר\\\",\\\"name_resolved\\\":true}\", \"output\": \"{\\\"client\\\": {\\\"name\\\": \\\"\\\\u05e9\\\\u05d7\\\\u05e8 \\\\u05e4\\\\u05d9\\\\u05e9\\\\u05e8\\\", \\\"email\\\": \\\"e2e-client-843832@example.com\\\", \\\"phone\\\": \\\"050-1234567\\\", \\\"tax_id\\\": \\\"\\\"}, \\\"exact_match\\\": true}\"}\nb769debe-6940-445c-ba79-f99c75ef967d [godfather] ההסכם החתום, תרשום ביומן\n    (extracted from attachment) אילה הוניגמן\nעורכת דין\n\n27.1.253\n\nהצעת שכר טרחה\n\nבין מר שחר פישר (להלן - הלקוח)\nלבין\nעו״ד אילה הוניגמן (להלן - עוה״ד)\n\n1. שכר הטרחה בגין הייצוג המשפטי (להלן - ״שכר הטרחה״):\n\nבעבור ייצוג הלקוח על ידי עוה״ד, בתביעה שהוגשה כנגדו לבית הדין האזורי לעבודה, ישלם הלקוח בהתאם למתווה הבא:\n\nא. הכנת והגשת כתב הגנה כמו גם ייצוג בשלבים מקדמיים (טרם תחילת הוכחות כולל קדם משפט ולא כולל גישור, ככל שיהיה) – 10,000 ₪ לא כולל מע״מ.\n\nב. גישור (ככל שיהיה) – תשלום שעתי, בתעריף של 800 ₪ לשעה, לא כולל מע״מ וזאת עד לתקרה של 10 שעות.\n\nג. הוכחות – 15,000 ₪ לא כולל מע״מ.\n\nד. סיכומים – 5,000 ₪ לא כולל מע״מ.\n\nשכר הטרחה המפורט לעיל אינו כולל ייצוג בערכאות ערעור.\n\n2. הוצאות:\n\nא. שכר הטרחה של עוה״ד לא כולל הוצאות כגון צילום חומרים, אגרות וכיוב׳. הלקוח ישא באופן בלעדי בהוצאות אשר ישולמו מיד בעת המצאת חשבונית.\n\nתאריך: ______________\n\nשם וחתימה: ______________\nb0fcadd2-4e26-4f7e-b1d8-bd98051be2b8 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: המשתמש שלח תמונת הסכם חתום וביקש לרשום אותו ביומן. טרם נקרא תוכן התמונה.\nTHIS TURN'S PURPOSE: לקרוא את ההסכם, לזהות את הלקוח והפרטים הנדרשים, ולאחר מכן לרשום את ההסכם ביומן לפי הזרימה המתאימה.\nEXPECTATION: אטען את זרימת רישום הסכם ואת יכולת ניתוח המדיה, אקרא את התמונה, ואז אפעל לפי תוצאת הניתוח.\n79b68e42-001b-4b1b-9e56-76814ebed42b [assistant] סיכום: נמצא הסכם שכר טרחה חתום עבור שחר פישר, בנוגע לייצוג בתביעה בבית הדין האזורי לעבודה.\n\n• סוג מסמך: הצעת שכר טרחה חתומה\n• תאריך שמופיע במסמך: 27.1.253\n• שלבים וסכומים: כתב הגנה ושלבים מקדמיים – 10,000 ₪; גישור – 800 ₪ לשעה, עד 10 שעות; הוכחות – 15,000 ₪; סיכומים – 5,000 ₪\n• כל הסכומים אינם כוללים מע״מ\n• הוצאות נלוות אינן כלולות\n\nהלקוח שחר פישר מזוהה במערכת, ולכן ההסכם מוכן לרישום ביומן.\n\nTHE REPLY JUST SENT TO THE OPERATOR THIS ROUND:\nסיכום: נמצא הסכם שכר טרחה חתום עבור שחר פישר, בנוגע לייצוג בתביעה בבית הדין האזורי לעבודה.\n\n• סוג מסמך: הצעת שכר טרחה חתומה\n• תאריך שמופיע במסמך: 27.1.253\n• שלבים וסכומים: כתב הגנה ושלבים מקדמיים – 10,000 ₪; גישור – 800 ₪ לשעה, עד 10 שעות; הוכחות – 15,000 ₪; סיכומים – 5,000 ₪\n• כל הסכומים אינם כוללים מע״מ\n• הוצאות נלוות אינן כלולות\n\nהלקוח שחר פישר מזוהה במערכת, ולכן ההסכם מוכן לרישום ביומן.\n\nNO Morning MCP tools were called this turn.\n\nFollow the recognition prompt above: query the client's ledger history first when the round concerns a client, then call report_ledger_recognition exactly once with the verdict for THIS round."}
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
{"role": "user", "content": "THE CONVERSATION WINDOW (the last 1h, oldest first) - '<message_id> [<role>] <content>':\n9d7a9609-333f-41d3-85ff-dc79af1ef735 [godfather] פרטים על הלקוח שחר פישר\n36d3142d-63a2-4ae8-93d3-62a8f559cb26 [assistant] בודק את פרטי הלקוח במערכת.\n763eaa3c-b8d1-4997-a37b-fd2b616aabdc [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: הבקשה היא לאחזר את פרטי הלקוח שחר פישר. עדיין לא בוצע חיפוש.\nTHIS TURN'S PURPOSE: לאתר את הלקוח המדויק במערכת ולהחזיר את פרטיו האישיים בלבד.\nEXPECTATION: אטען יכולת לקריאת לקוחות, אחפש את הלקוח, ואז אחזיר את התוצאה או אבקש הבהרה אם יש כמה התאמות.\nada30b46-ba49-491e-b5a9-55b7853934ca [assistant] מאתר את השם המדויק כפי שהוא שמור במערכת.\ndd20e6ed-fa19-4e07-966d-e6739d89f615 [assistant] מצאתי את הלקוח. עכשיו אני שולף את הפרטים השמורים.\nfa4d2b8b-5ed2-4d2c-b9e3-019838928f64 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: נמצא הלקוח שחר פישר ונשלפו פרטיו המדויקים ממערכת מורנינג.\nTHIS TURN'S PURPOSE: להחזיר למשתמש את פרטי הלקוח בעברית ובקיצור.\nEXPECTATION: המשימה הושלמה בהצלחה; אין צורך בשאלה נוספת.\n297c0b0c-a2fa-4784-ad37-e9555685798e [assistant] פרטי הלקוח שחר פישר:\n\nשם: שחר פישר\nדוא״ל: e2e-client-843832@example.com\nטלפון: 050-1234567\nמספר עוסק או חברה: לא שמור\n    (morning MCP call on this message's turn) {\"name\": \"resolve_client_name\", \"error\": null, \"arguments\": \"{\\\"name\\\":\\\"שחר פישר\\\"}\", \"output\": \"{\\\"status\\\": \\\"resolved\\\", \\\"name\\\": \\\"\\\\u05e9\\\\u05d7\\\\u05e8 \\\\u05e4\\\\u05d9\\\\u05e9\\\\u05e8\\\"}\"}\n    (morning MCP call on this message's turn) {\"name\": \"get_client_details\", \"error\": null, \"arguments\": \"{\\\"name\\\":\\\"שחר פישר\\\",\\\"name_resolved\\\":true}\", \"output\": \"{\\\"client\\\": {\\\"name\\\": \\\"\\\\u05e9\\\\u05d7\\\\u05e8 \\\\u05e4\\\\u05d9\\\\u05e9\\\\u05e8\\\", \\\"email\\\": \\\"e2e-client-843832@example.com\\\", \\\"phone\\\": \\\"050-1234567\\\", \\\"tax_id\\\": \\\"\\\"}, \\\"exact_match\\\": true}\"}\nb769debe-6940-445c-ba79-f99c75ef967d [godfather] ההסכם החתום, תרשום ביומן\n    (extracted from attachment) אילה הוניגמן\nעורכת דין\n\n27.1.253\n\nהצעת שכר טרחה\n\nבין מר שחר פישר (להלן - הלקוח)\nלבין\nעו״ד אילה הוניגמן (להלן - עוה״ד)\n\n1. שכר הטרחה בגין הייצוג המשפטי (להלן - ״שכר הטרחה״):\n\nבעבור ייצוג הלקוח על ידי עוה״ד, בתביעה שהוגשה כנגדו לבית הדין האזורי לעבודה, ישלם הלקוח בהתאם למתווה הבא:\n\nא. הכנת והגשת כתב הגנה כמו גם ייצוג בשלבים מקדמיים (טרם תחילת הוכחות כולל קדם משפט ולא כולל גישור, ככל שיהיה) – 10,000 ₪ לא כולל מע״מ.\n\nב. גישור (ככל שיהיה) – תשלום שעתי, בתעריף של 800 ₪ לשעה, לא כולל מע״מ וזאת עד לתקרה של 10 שעות.\n\nג. הוכחות – 15,000 ₪ לא כולל מע״מ.\n\nד. סיכומים – 5,000 ₪ לא כולל מע״מ.\n\nשכר הטרחה המפורט לעיל אינו כולל ייצוג בערכאות ערעור.\n\n2. הוצאות:\n\nא. שכר הטרחה של עוה״ד לא כולל הוצאות כגון צילום חומרים, אגרות וכיוב׳. הלקוח ישא באופן בלעדי בהוצאות אשר ישולמו מיד בעת המצאת חשבונית.\n\nתאריך: ______________\n\nשם וחתימה: ______________\nb0fcadd2-4e26-4f7e-b1d8-bd98051be2b8 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: המשתמש שלח תמונת הסכם חתום וביקש לרשום אותו ביומן. טרם נקרא תוכן התמונה.\nTHIS TURN'S PURPOSE: לקרוא את ההסכם, לזהות את הלקוח והפרטים הנדרשים, ולאחר מכן לרשום את ההסכם ביומן לפי הזרימה המתאימה.\nEXPECTATION: אטען את זרימת רישום הסכם ואת יכולת ניתוח המדיה, אקרא את התמונה, ואז אפעל לפי תוצאת הניתוח.\n79b68e42-001b-4b1b-9e56-76814ebed42b [assistant] סיכום: נמצא הסכם שכר טרחה חתום עבור שחר פישר, בנוגע לייצוג בתביעה בבית הדין האזורי לעבודה.\n\n• סוג מסמך: הצעת שכר טרחה חתומה\n• תאריך שמופיע במסמך: 27.1.253\n• שלבים וסכומים: כתב הגנה ושלבים מקדמיים – 10,000 ₪; גישור – 800 ₪ לשעה, עד 10 שעות; הוכחות – 15,000 ₪; סיכומים – 5,000 ₪\n• כל הסכומים אינם כוללים מע״מ\n• הוצאות נלוות אינן כלולות\n\nהלקוח שחר פישר מזוהה במערכת, ולכן ההסכם מוכן לרישום ביומן.\n\nTHE REPLY JUST SENT TO THE OPERATOR THIS ROUND:\nסיכום: נמצא הסכם שכר טרחה חתום עבור שחר פישר, בנוגע לייצוג בתביעה בבית הדין האזורי לעבודה.\n\n• סוג מסמך: הצעת שכר טרחה חתומה\n• תאריך שמופיע במסמך: 27.1.253\n• שלבים וסכומים: כתב הגנה ושלבים מקדמיים – 10,000 ₪; גישור – 800 ₪ לשעה, עד 10 שעות; הוכחות – 15,000 ₪; סיכומים – 5,000 ₪\n• כל הסכומים אינם כוללים מע״מ\n• הוצאות נלוות אינן כלולות\n\nהלקוח שחר פישר מזוהה במערכת, ולכן ההסכם מוכן לרישום ביומן.\n\nNO Morning MCP tools were called this turn.\n\nFollow the recognition prompt above: query the client's ledger history first when the round concerns a client, then call report_ledger_recognition exactly once with the verdict for THIS round."}
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
<summary>62. [2026-10-01 16:46:31] MODEL → APP — context=recognize_ledger_event</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0a6b7e1f3935bb9c006abe64354a0087d1a76b1e3080be39a0`
- status: `completed`
- usage: `{"input_tokens": 9634, "input_tokens_details": {"cache_write_tokens": 1695, "cached_tokens": 7936}, "output_tokens": 70, "output_tokens_details": {"reasoning_tokens": 36}, "total_tokens": 9704}`
- reasoning item (content not user-visible)
- function_call: `query_ledger_events` call_id=`call_r0qDdCATJxp17U5JI7veNxBe`
```json
{
  "criteria": [
    {
      "text": "שחר פישר",
      "hint": "identity"
    }
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0a6b7e1f3935bb9c006abe64354a0087d1a76b1e3080be39a0`
- status: `completed`
- usage: `{"input_tokens": 9634, "input_tokens_details": {"cache_write_tokens": 1695, "cached_tokens": 7936}, "output_tokens": 70, "output_tokens_details": {"reasoning_tokens": 36}, "total_tokens": 9704}`
- reasoning item (content not user-visible)
- function_call: `query_ledger_events` call_id=`call_r0qDdCATJxp17U5JI7veNxBe`
```json
{
  "criteria": [
    {
      "text": "שחר פישר",
      "hint": "identity"
    }
  ]
}
```

</details>

</details>

<details>
<summary>63. [2026-10-01 16:46:31] APP → MODEL — context=recognize_ledger_event (query round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

**input:**

- app's reply to `query_ledger_events` (call_id=`call_r0qDdCATJxp17U5JI7veNxBe`):
```text
{
  "matches": [],
  "count": 0
}
```

- tools (2): ['report_ledger_recognition', 'query_ledger_events']

- previous_response_id: `'resp_0a6b7e1f3935bb9c006abe64354a0087d1a76b1e3080be39a0'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: ledger recognition prompt

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

**input:**

- app's reply to `query_ledger_events` (call_id=`call_r0qDdCATJxp17U5JI7veNxBe`):
```text
{
  "matches": [],
  "count": 0
}
```

- tools (2): ['report_ledger_recognition', 'query_ledger_events']

- previous_response_id: `'resp_0a6b7e1f3935bb9c006abe64354a0087d1a76b1e3080be39a0'`

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
<summary>64. [2026-10-01 16:46:38] MODEL → APP — context=recognize_ledger_event (query round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0a6b7e1f3935bb9c006abe6437a5dc87d197989b1dd117e96f`
- status: `completed`
- usage: `{"input_tokens": 9727, "input_tokens_details": {"cache_write_tokens": 93, "cached_tokens": 9631}, "output_tokens": 717, "output_tokens_details": {"reasoning_tokens": 282}, "total_tokens": 10444}`
- reasoning item (content not user-visible)
- function_call: `report_ledger_recognition` call_id=`call_Yhx6SZBUFRZlGP3qgVPsDkAV`
```json
{
  "verdict": "complete",
  "event": {
    "source_type": "הסכם",
    "event_subtype": "יצירה",
    "client_name": "שחר פישר",
    "payer_name": null,
    "agreement_id": null,
    "reference_hint": null,
    "bank_number": null,
    "bank_branch": null,
    "bank_account": null,
    "accounting_document_json": null,
    "component_count": 4,
    "components": [
      {
        "component_label": "כתב הגנה ושלבים מקדמיים",
        "description": "ייצוג בתביעה שהוגשה נגד הלקוח בבית הדין האזורי לעבודה; הכנת והגשת כתב הגנה וייצוג בשלבים מקדמיים, כולל קדם משפט וללא גישור",
        "amount": "10000",
        "percent": null,
        "percent_base": null,
        "hours": null,
        "hourly_rate": null,
        "txn_date": null,
        "vat_status": "לא כולל",
        "trigger_condition": null
      },
      {
        "component_label": "גישור",
        "description": "גישור במסגרת הייצוג בתביעה בבית הדין האזורי לעבודה, בתשלום שעתי עד תקרה של 10 שעות",
        "amount": "800",
        "percent": null,
        "percent_base": null,
        "hours": "עד 10",
        "hourly_rate": "800",
        "txn_date": null,
        "vat_status": "לא כולל",
        "trigger_condition": "ככל שיהיה גישור"
      },
      {
        "component_label": "הוכחות",
        "description": "ייצוג בשלב ההוכחות בתביעה בבית הדין האזורי לעבודה",
        "amount": "15000",
        "percent": null,
        "percent_base": null,
        "hours": null,
        "hourly_rate": null,
        "txn_date": null,
        "vat_status": "לא כולל",
        "trigger_condition": null
      },
      {
        "component_label": "סיכומים",
        "description": "ייצוג בשלב הסיכומים בתביעה בבית הדין האזורי לעבודה",
        "amount": "5000",
        "percent": null,
        "percent_base": null,
        "hours": null,
        "hourly_rate": null,
        "txn_date": null,
        "vat_status": "לא כולל",
        "trigger_condition": null
      }
    ]
  },
  "trigger_message_id": "b769debe-6940-445c-ba79-f99c75ef967d"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0a6b7e1f3935bb9c006abe6437a5dc87d197989b1dd117e96f`
- status: `completed`
- usage: `{"input_tokens": 9727, "input_tokens_details": {"cache_write_tokens": 93, "cached_tokens": 9631}, "output_tokens": 717, "output_tokens_details": {"reasoning_tokens": 282}, "total_tokens": 10444}`
- reasoning item (content not user-visible)
- function_call: `report_ledger_recognition` call_id=`call_Yhx6SZBUFRZlGP3qgVPsDkAV`
```json
{
  "verdict": "complete",
  "event": {
    "source_type": "הסכם",
    "event_subtype": "יצירה",
    "client_name": "שחר פישר",
    "payer_name": null,
    "agreement_id": null,
    "reference_hint": null,
    "bank_number": null,
    "bank_branch": null,
    "bank_account": null,
    "accounting_document_json": null,
    "component_count": 4,
    "components": [
      {
        "component_label": "כתב הגנה ושלבים מקדמיים",
        "description": "ייצוג בתביעה שהוגשה נגד הלקוח בבית הדין האזורי לעבודה; הכנת והגשת כתב הגנה וייצוג בשלבים מקדמיים, כולל קדם משפט וללא גישור",
        "amount": "10000",
        "percent": null,
        "percent_base": null,
        "hours": null,
        "hourly_rate": null,
        "txn_date": null,
        "vat_status": "לא כולל",
        "trigger_condition": null
      },
      {
        "component_label": "גישור",
        "description": "גישור במסגרת הייצוג בתביעה בבית הדין האזורי לעבודה, בתשלום שעתי עד תקרה של 10 שעות",
        "amount": "800",
        "percent": null,
        "percent_base": null,
        "hours": "עד 10",
        "hourly_rate": "800",
        "txn_date": null,
        "vat_status": "לא כולל",
        "trigger_condition": "ככל שיהיה גישור"
      },
      {
        "component_label": "הוכחות",
        "description": "ייצוג בשלב ההוכחות בתביעה בבית הדין האזורי לעבודה",
        "amount": "15000",
        "percent": null,
        "percent_base": null,
        "hours": null,
        "hourly_rate": null,
        "txn_date": null,
        "vat_status": "לא כולל",
        "trigger_condition": null
      },
      {
        "component_label": "סיכומים",
        "description": "ייצוג בשלב הסיכומים בתביעה בבית הדין האזורי לעבודה",
        "amount": "5000",
        "percent": null,
        "percent_base": null,
        "hours": null,
        "hourly_rate": null,
        "txn_date": null,
        "vat_status": "לא כולל",
        "trigger_condition": null
      }
    ]
  },
  "trigger_message_id": "b769debe-6940-445c-ba79-f99c75ef967d"
}
```

</details>

</details>

