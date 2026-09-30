# Wire trace

Each numbered section below is one wire-crossing event, in strict chronological order (the number always goes up by 1, regardless of which boundary/direction it is). Click a section to expand it. Each has exactly two sub-sections, marked `↳` - Audit (concise) and Debug (full, verbatim) - and, inside Debug only, the long `instructions` text nests one level deeper, marked `↳↳`.

<details>
<summary>1. [2026-09-30 15:03:37] USER → APP — context=webhook</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "typeWebhook": "incomingMessageReceived",
  "timestamp": 1790769817,
  "idMessage": "E2E_CREATE_TAP_ASK_1790769817",
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
      "textMessage": "תפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לא כולל מע\"מ עבור ייעוץ"
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
  "timestamp": 1790769817,
  "idMessage": "E2E_CREATE_TAP_ASK_1790769817",
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
      "textMessage": "תפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לא כולל מע\"מ עבור ייעוץ"
    }
  }
}
```

</details>

</details>

<details>
<summary>2. [2026-09-30 15:03:39] APP → MODEL — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

```json
{"role": "user", "content": "תפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לא כולל מע\"מ עבור ייעוץ"}
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
{"role": "user", "content": "תפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לא כולל מע\"מ עבור ייעוץ"}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19640 chars)</summary>

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

**Timing of outcome reactions.** An outcome reaction (✅ 🎉 ⚠️ ❌) reports the
result of an action, so send it only once that action's result is actually back
and says so - never in the same response as the tool call that performs the
action (the call hasn't returned yet, and it may still fail). Acknowledgment
reactions (👍 🫡 👀 ❓ 🙏 ❤️) are not affected: they say you saw the message or
are on it, and can go out at any point, including alongside a call.

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

Record an action as done only after its result is back and confirms it. In the same
response as the call that performs it, the action is still in progress, not completed.


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

THE CURRENT DATE AND TIME IS 2026-09-30 15:03 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>3. [2026-09-30 15:03:42] MODEL → APP — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f1f214793d52681006abcfa9c24a487d1a9931ee631331e64`
- status: `completed`
- usage: `{"input_tokens": 6097, "input_tokens_details": {"cache_write_tokens": 6094, "cached_tokens": 0}, "output_tokens": 80, "output_tokens_details": {"reasoning_tokens": 52}, "total_tokens": 6177}`
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_z3USK0HP5CfpBY37T55hWxh1`
```json
{
  "emoji": "🫡",
  "message_id": null
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f1f214793d52681006abcfa9c24a487d1a9931ee631331e64`
- status: `completed`
- usage: `{"input_tokens": 6097, "input_tokens_details": {"cache_write_tokens": 6094, "cached_tokens": 0}, "output_tokens": 80, "output_tokens_details": {"reasoning_tokens": 52}, "total_tokens": 6177}`
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_z3USK0HP5CfpBY37T55hWxh1`
```json
{
  "emoji": "🫡",
  "message_id": null
}
```

</details>

</details>

<details>
<summary>4. [2026-09-30 15:03:42] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `react_to_message` (call_id=`call_z3USK0HP5CfpBY37T55hWxh1`):
```text
{
  "status": "failed"
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0f1f214793d52681006abcfa9c24a487d1a9931ee631331e64'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `react_to_message` (call_id=`call_z3USK0HP5CfpBY37T55hWxh1`):
```text
{
  "status": "failed"
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0f1f214793d52681006abcfa9c24a487d1a9931ee631331e64'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19640 chars)</summary>

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

**Timing of outcome reactions.** An outcome reaction (✅ 🎉 ⚠️ ❌) reports the
result of an action, so send it only once that action's result is actually back
and says so - never in the same response as the tool call that performs the
action (the call hasn't returned yet, and it may still fail). Acknowledgment
reactions (👍 🫡 👀 ❓ 🙏 ❤️) are not affected: they say you saw the message or
are on it, and can go out at any point, including alongside a call.

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

Record an action as done only after its result is back and confirms it. In the same
response as the call that performs it, the action is still in progress, not completed.


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

THE CURRENT DATE AND TIME IS 2026-09-30 15:03 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>5. [2026-09-30 15:03:46] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f1f214793d52681006abcfa9edff887d184070de5ce9de034`
- status: `completed`
- usage: `{"input_tokens": 6195, "input_tokens_details": {"cache_write_tokens": 98, "cached_tokens": 6094}, "output_tokens": 36, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6231}`
- function_call: `send_progress_update` call_id=`call_2ZtI9vhiU6iHe4LYyK8ESgGq`
```json
{
  "text": "מטפל בהפקת החשבונית ובודק את פרטי הלקוח."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f1f214793d52681006abcfa9edff887d184070de5ce9de034`
- status: `completed`
- usage: `{"input_tokens": 6195, "input_tokens_details": {"cache_write_tokens": 98, "cached_tokens": 6094}, "output_tokens": 36, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6231}`
- function_call: `send_progress_update` call_id=`call_2ZtI9vhiU6iHe4LYyK8ESgGq`
```json
{
  "text": "מטפל בהפקת החשבונית ובודק את פרטי הלקוח."
}
```

</details>

</details>

<details>
<summary>6. [2026-09-30 15:03:46] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "מטפל בהפקת החשבונית ובודק את פרטי הלקוח."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "מטפל בהפקת החשבונית ובודק את פרטי הלקוח."
}
```

</details>

</details>

<details>
<summary>7. [2026-09-30 15:03:46] USER ← APP (send result) — context=progress_update</summary>

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
<summary>8. [2026-09-30 15:03:46] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `send_progress_update` (call_id=`call_2ZtI9vhiU6iHe4LYyK8ESgGq`):
```text
{
  "sent": true
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0f1f214793d52681006abcfa9edff887d184070de5ce9de034'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `send_progress_update` (call_id=`call_2ZtI9vhiU6iHe4LYyK8ESgGq`):
```text
{
  "sent": true
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0f1f214793d52681006abcfa9edff887d184070de5ce9de034'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19640 chars)</summary>

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

**Timing of outcome reactions.** An outcome reaction (✅ 🎉 ⚠️ ❌) reports the
result of an action, so send it only once that action's result is actually back
and says so - never in the same response as the tool call that performs the
action (the call hasn't returned yet, and it may still fail). Acknowledgment
reactions (👍 🫡 👀 ❓ 🙏 ❤️) are not affected: they say you saw the message or
are on it, and can go out at any point, including alongside a call.

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

Record an action as done only after its result is back and confirms it. In the same
response as the call that performs it, the action is still in progress, not completed.


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

THE CURRENT DATE AND TIME IS 2026-09-30 15:03 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>9. [2026-09-30 15:03:49] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f1f214793d52681006abcfaa2e32487d18d86117b36a85077`
- status: `completed`
- usage: `{"input_tokens": 6248, "input_tokens_details": {"cache_write_tokens": 53, "cached_tokens": 6192}, "output_tokens": 149, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6397}`
- function_call: `record_planning_status` call_id=`call_XWTJUM5wYm5HcTLucEOF90Z5`
```json
{
  "where_i_was": "הבקשה היא להפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לפני מעמ עבור ייעוץ. טרם בוצעה בדיקה במערכת.",
  "this_turns_purpose": "להפעיל את תהליך הפקת חשבונית עבור תשלום שטרם התקבל, לאתר את הלקוח, לאסוף את פרטי החשבונית ולבקש אישור לפני יצירה.",
  "expectation": "אבדוק את הלקוח ואת הפרטים הנדרשים; אם הכל ברור, אציג אישור מפורט לפני ההפקה."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f1f214793d52681006abcfaa2e32487d18d86117b36a85077`
- status: `completed`
- usage: `{"input_tokens": 6248, "input_tokens_details": {"cache_write_tokens": 53, "cached_tokens": 6192}, "output_tokens": 149, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6397}`
- function_call: `record_planning_status` call_id=`call_XWTJUM5wYm5HcTLucEOF90Z5`
```json
{
  "where_i_was": "הבקשה היא להפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לפני מעמ עבור ייעוץ. טרם בוצעה בדיקה במערכת.",
  "this_turns_purpose": "להפעיל את תהליך הפקת חשבונית עבור תשלום שטרם התקבל, לאתר את הלקוח, לאסוף את פרטי החשבונית ולבקש אישור לפני יצירה.",
  "expectation": "אבדוק את הלקוח ואת הפרטים הנדרשים; אם הכל ברור, אציג אישור מפורט לפני ההפקה."
}
```

</details>

</details>

<details>
<summary>10. [2026-09-30 15:03:49] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `record_planning_status` (call_id=`call_XWTJUM5wYm5HcTLucEOF90Z5`):
```text
recorded
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0f1f214793d52681006abcfaa2e32487d18d86117b36a85077'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `record_planning_status` (call_id=`call_XWTJUM5wYm5HcTLucEOF90Z5`):
```text
recorded
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0f1f214793d52681006abcfaa2e32487d18d86117b36a85077'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19640 chars)</summary>

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

**Timing of outcome reactions.** An outcome reaction (✅ 🎉 ⚠️ ❌) reports the
result of an action, so send it only once that action's result is actually back
and says so - never in the same response as the tool call that performs the
action (the call hasn't returned yet, and it may still fail). Acknowledgment
reactions (👍 🫡 👀 ❓ 🙏 ❤️) are not affected: they say you saw the message or
are on it, and can go out at any point, including alongside a call.

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

Record an action as done only after its result is back and confirms it. In the same
response as the call that performs it, the action is still in progress, not completed.


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

THE CURRENT DATE AND TIME IS 2026-09-30 15:03 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>11. [2026-09-30 15:03:51] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f1f214793d52681006abcfaa5eab087d1b6acc76e79f231c2`
- status: `completed`
- usage: `{"input_tokens": 6412, "input_tokens_details": {"cache_write_tokens": 164, "cached_tokens": 6245}, "output_tokens": 25, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6437}`
- function_call: `load_flows` call_id=`call_YMRYwtnqcIkZ9m5lNpFiZW6h`
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

- response.id: `resp_0f1f214793d52681006abcfaa5eab087d1b6acc76e79f231c2`
- status: `completed`
- usage: `{"input_tokens": 6412, "input_tokens_details": {"cache_write_tokens": 164, "cached_tokens": 6245}, "output_tokens": 25, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 6437}`
- function_call: `load_flows` call_id=`call_YMRYwtnqcIkZ9m5lNpFiZW6h`
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
<summary>12. [2026-09-30 15:03:51] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_issue_invoice_for_payment_due

- capabilities: (none - plain backbone)

**input:**

- app's reply to `load_flows` (call_id=`call_YMRYwtnqcIkZ9m5lNpFiZW6h`):
```text
loaded flows: flow_issue_invoice_for_payment_due. Loaded flows now: flow_issue_invoice_for_payment_due. Loaded capabilities now: (none). Their blueprint text is attached starting now.
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0f1f214793d52681006abcfaa5eab087d1b6acc76e79f231c2'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_issue_invoice_for_payment_due, capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_issue_invoice_for_payment_due

- capabilities: (none - plain backbone)

**input:**

- app's reply to `load_flows` (call_id=`call_YMRYwtnqcIkZ9m5lNpFiZW6h`):
```text
loaded flows: flow_issue_invoice_for_payment_due. Loaded flows now: flow_issue_invoice_for_payment_due. Loaded capabilities now: (none). Their blueprint text is attached starting now.
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0f1f214793d52681006abcfaa5eab087d1b6acc76e79f231c2'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (21822 chars)</summary>

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

**Timing of outcome reactions.** An outcome reaction (✅ 🎉 ⚠️ ❌) reports the
result of an action, so send it only once that action's result is actually back
and says so - never in the same response as the tool call that performs the
action (the call hasn't returned yet, and it may still fail). Acknowledgment
reactions (👍 🫡 👀 ❓ 🙏 ❤️) are not affected: they say you saw the message or
are on it, and can go out at any point, including alongside a call.

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

Record an action as done only after its result is back and confirms it. In the same
response as the call that performs it, the action is still in progress, not completed.


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

# Flow: Issue invoice for payment due

Goal: issue a new tax invoice (305) for a client, for money that is still owed.

Capabilities: `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

1. This flow is only for money NOT yet received. If it turns out the money has already arrived, stop and use `flow_issue_invoice_receipt_combo` instead, or `flow_issue_payment_received_with_reference_doc` if an existing document already covers it.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. Issuing the invoice MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
5. On a yes, issue the invoice. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome — no download link is required in this report. Then unload `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


## Loaded flows

flow_issue_invoice_for_payment_due

## Loaded capabilities

(none - plain backbone)

---

THE CURRENT DATE AND TIME IS 2026-09-30 15:03 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>13. [2026-09-30 15:03:52] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f1f214793d52681006abcfaa7799c87d1a44cdcebb6d39320`
- status: `completed`
- usage: `{"input_tokens": 7004, "input_tokens_details": {"cache_write_tokens": 7001, "cached_tokens": 0}, "output_tokens": 35, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7039}`
- function_call: `load_capabilities` call_id=`call_JzuZWNaR1xJNpnM5M343tU54`
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

- response.id: `resp_0f1f214793d52681006abcfaa7799c87d1a44cdcebb6d39320`
- status: `completed`
- usage: `{"input_tokens": 7004, "input_tokens_details": {"cache_write_tokens": 7001, "cached_tokens": 0}, "output_tokens": 35, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7039}`
- function_call: `load_capabilities` call_id=`call_JzuZWNaR1xJNpnM5M343tU54`
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
<summary>14. [2026-09-30 15:03:52] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `load_capabilities` (call_id=`call_JzuZWNaR1xJNpnM5M343tU54`):
```text
loaded capabilitys: cap_client_read, cap_invoicing_write, cap_approval_with_buttons. Loaded flows now: flow_issue_invoice_for_payment_due. Loaded capabilities now: cap_client_read, cap_invoicing_write, cap_approval_with_buttons. Their instructions and tools are attached starting now.
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp']

- previous_response_id: `'resp_0f1f214793d52681006abcfaa7799c87d1a44cdcebb6d39320'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_issue_invoice_for_payment_due, capabilities=cap_invoicing_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `load_capabilities` (call_id=`call_JzuZWNaR1xJNpnM5M343tU54`):
```text
loaded capabilitys: cap_client_read, cap_invoicing_write, cap_approval_with_buttons. Loaded flows now: flow_issue_invoice_for_payment_due. Loaded capabilities now: cap_client_read, cap_invoicing_write, cap_approval_with_buttons. Their instructions and tools are attached starting now.
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp']

- previous_response_id: `'resp_0f1f214793d52681006abcfaa7799c87d1a44cdcebb6d39320'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (35257 chars)</summary>

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

**Timing of outcome reactions.** An outcome reaction (✅ 🎉 ⚠️ ❌) reports the
result of an action, so send it only once that action's result is actually back
and says so - never in the same response as the tool call that performs the
action (the call hasn't returned yet, and it may still fail). Acknowledgment
reactions (👍 🫡 👀 ❓ 🙏 ❤️) are not affected: they say you saw the message or
are on it, and can go out at any point, including alongside a call.

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

Record an action as done only after its result is back and confirms it. In the same
response as the call that performs it, the action is still in progress, not completed.


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

# Flow: Issue invoice for payment due

Goal: issue a new tax invoice (305) for a client, for money that is still owed.

Capabilities: `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

1. This flow is only for money NOT yet received. If it turns out the money has already arrived, stop and use `flow_issue_invoice_receipt_combo` instead, or `flow_issue_payment_received_with_reference_doc` if an existing document already covers it.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. Issuing the invoice MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
5. On a yes, issue the invoice. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome — no download link is required in this report. Then unload `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Invoicing — Write (godfather/admin only)

**Use this capability from within a flow (the flow that issues or cancels the document (flow_issue_*, flow_cancel_*, flow_payment_received_*)), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

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

- `create_invoice` — an ordinary tax invoice (חשבונית מס, 305): a request for
  payment NOT yet received. Default only when the user asks for an invoice
  for money still owed; never for a payment already made.
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
    Only the user explicitly stating the opposite overrides this.
  - `payment_date` is the date the money **actually moved** — never today's
    date unless that's genuinely when it arrived, never a future date. If
    the source doesn't state it clearly, **ask**.
  - `payment_method` records how it arrived — **`bank_transfer` is the
    default** for a deposit/transfer; use `bit`/`paybox`/`cash`/
    `credit_card`/`cheque`/`paypal` when the user says so. Bank details
    (`bank_number`, `bank_branch`, `bank_account`) go with a bank transfer;
    the אסמכתה (`transaction_reference`) with a payment app or PayPal.
    🚨 `bank_number` is the bank's NUMBER (e.g. "31"), never its name —
    never guess or invent a bank name.
  - Take **every** field from the extracted text of the screenshot the user
    sent. Anything not there, or illegible, is something to **ask about** —
    never invent or default it.
- `create_credit_note` — a credit note (חשבונית זיכוי, 330) against an
  existing document — direct ("תפיק לי חשבונית זיכוי") or indirect ("בטל את
  זה").
- `create_receipt` — a receipt (קבלה, 400) against an existing type-305
  document — direct or indirect ("סמן כשולם"). Rejects a type-300 original —
  use `create_combo_document_as_reference` for those.
  🚨 **`payment_date` is required and has no default** — a verbal "mark as
  paid" request has nothing to read a date from, so always ask if the
  conversation doesn't already state one. "Today" is an acceptable answer
  here, but only once the user has actually confirmed it.
- `create_combo_document_as_reference` — a combo document (320) that
  explicitly closes an existing type-300 document — direct or indirect.
  Rejects any original that isn't type 300. Requires `vat_included` — same
  unconditional rule as `create_combo_document`: ALWAYS `true`, never ask.
- `cancel_transaction_account` — cancels an open type-300 account directly
  (no document of any kind is created); rejects any other type. If the
  account is already non-open, this is a no-op that returns the same
  confirmation without calling Morning again — never claim it was "paid".

`create_credit_note`, `create_receipt`, `create_combo_document_as_reference`,
and `cancel_transaction_account` all require an original/reference document
id, taken from the most recent tool result that actually returned it; never ask the
user for it, never guess it.

## The client name

Every write tool that needs one specific client (`create_invoice`,
`create_transaction_account`, `create_combo_document`) takes the EXACT name
Morning has stored, together with `name_resolved=true`; they refuse immediately
if `name_resolved` isn't `true`. Only pass `name_resolved=true` with a name
that has actually been confirmed as Morning's stored name — never with the
user's loose wording. Gather any other still-missing required fields (amount,
description, VAT treatment, dates) one question at a time. Every mutating tool also needs the
user's approval first (see the approval data points below).

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
  client, amount, and purpose (description). **VAT:** required for a transaction account (300), an invoice (305), a combo
  document (320, including combo-as-reference) and a receipt (400) — state it.
  For 320 and 400 it is "included" unless the user explicitly says otherwise. For
  300 and 305 there is NO default: if the user hasn't said, ask. A credit note
  (330) is attached to an existing document and takes its VAT from it — show
  that, never ask. Cancelling a transaction account has no VAT.
  **Plus, whenever known:** transaction date, payment method, bank
  details, transaction reference, linked invoice number.
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

flow_issue_invoice_for_payment_due

## Loaded capabilities

cap_invoicing_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-09-30 15:03 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>15. [2026-09-30 15:04:01] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 1/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f1f214793d52681006abcfaa912bc87d195f3a47296cbcd7d`
- status: `completed`
- usage: `{"input_tokens": 13416, "input_tokens_details": {"cache_write_tokens": 13290, "cached_tokens": 0}, "output_tokens": 390, "output_tokens_details": {"reasoning_tokens": 202}, "total_tokens": 13806}`
- mcp_list_tools (morning-invoices): ['create_invoice', 'create_transaction_account', 'create_combo_document', 'create_credit_note', 'create_receipt', 'create_combo_document_as_reference', 'cancel_transaction_account', 'list_clients', 'resolve_client_name', 'get_client_details']
- reasoning item (content not user-visible)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f1f214793d52681006abcfaa912bc87d195f3a47296cbcd7d`
- status: `completed`
- usage: `{"input_tokens": 13416, "input_tokens_details": {"cache_write_tokens": 13290, "cached_tokens": 0}, "output_tokens": 390, "output_tokens_details": {"reasoning_tokens": 202}, "total_tokens": 13806}`
- mcp_list_tools (morning-invoices): ['create_invoice', 'create_transaction_account', 'create_combo_document', 'create_credit_note', 'create_receipt', 'create_combo_document_as_reference', 'cancel_transaction_account', 'list_clients', 'resolve_client_name', 'get_client_details']
- reasoning item (content not user-visible)

</details>

</details>

<details>
<summary>16. [2026-09-30 15:04:01] MODEL → MORNING MCP — resolve_client_name</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- tool name: `resolve_client_name`
- server_label: `'morning-invoices'`

arguments:
```json
{
  "name": "דמיטרי נוביקסקי"
}
```

</details>

</details>

<details>
<summary>17. [2026-09-30 15:04:01] MORNING MCP → MODEL — resolve_client_name</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

output:
```json
{
  "status": "resolved",
  "name": "דמיטרי נוביקסקי"
}
```

</details>

</details>

<details>
<summary>18. [2026-09-30 15:04:01] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 2/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f1f214793d52681006abcfaa912bc87d195f3a47296cbcd7d`
- status: `completed`
- usage: `{"input_tokens": 13416, "input_tokens_details": {"cache_write_tokens": 13290, "cached_tokens": 0}, "output_tokens": 390, "output_tokens_details": {"reasoning_tokens": 202}, "total_tokens": 13806}`
- reasoning item (content not user-visible)
- function_call: `record_planning_status` call_id=`call_cV8beJANPgZ7bXDtXyTIogSg`
```json
{
  "where_i_was": "בתהליך flow_issue_invoice_for_payment_due, שלב איתור הלקוח הושלם. שם הלקוח המדויק במערכת הוא דמיטרי נוביקסקי. הפרטים שנאספו: חשבונית מס חדשה, 70 שח לפני מעמ, עבור ייעוץ; לא נמסר מועד פירעון ולכן לא אגדיר אותו.",
  "this_turns_purpose": "לבקש אישור מפורט לפני יצירת החשבונית.",
  "expectation": "ממתין לתשובת כן או לא. אם יאושר, אצור את החשבונית; אם לא, לא אבצע יצירה."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f1f214793d52681006abcfaa912bc87d195f3a47296cbcd7d`
- status: `completed`
- usage: `{"input_tokens": 13416, "input_tokens_details": {"cache_write_tokens": 13290, "cached_tokens": 0}, "output_tokens": 390, "output_tokens_details": {"reasoning_tokens": 202}, "total_tokens": 13806}`
- reasoning item (content not user-visible)
- function_call: `record_planning_status` call_id=`call_cV8beJANPgZ7bXDtXyTIogSg`
```json
{
  "where_i_was": "בתהליך flow_issue_invoice_for_payment_due, שלב איתור הלקוח הושלם. שם הלקוח המדויק במערכת הוא דמיטרי נוביקסקי. הפרטים שנאספו: חשבונית מס חדשה, 70 שח לפני מעמ, עבור ייעוץ; לא נמסר מועד פירעון ולכן לא אגדיר אותו.",
  "this_turns_purpose": "לבקש אישור מפורט לפני יצירת החשבונית.",
  "expectation": "ממתין לתשובת כן או לא. אם יאושר, אצור את החשבונית; אם לא, לא אבצע יצירה."
}
```

</details>

</details>

<details>
<summary>19. [2026-09-30 15:04:01] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `record_planning_status` (call_id=`call_cV8beJANPgZ7bXDtXyTIogSg`):
```text
recorded
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp']

- previous_response_id: `'resp_0f1f214793d52681006abcfaa912bc87d195f3a47296cbcd7d'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_issue_invoice_for_payment_due, capabilities=cap_invoicing_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `record_planning_status` (call_id=`call_cV8beJANPgZ7bXDtXyTIogSg`):
```text
recorded
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp']

- previous_response_id: `'resp_0f1f214793d52681006abcfaa912bc87d195f3a47296cbcd7d'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (35257 chars)</summary>

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

**Timing of outcome reactions.** An outcome reaction (✅ 🎉 ⚠️ ❌) reports the
result of an action, so send it only once that action's result is actually back
and says so - never in the same response as the tool call that performs the
action (the call hasn't returned yet, and it may still fail). Acknowledgment
reactions (👍 🫡 👀 ❓ 🙏 ❤️) are not affected: they say you saw the message or
are on it, and can go out at any point, including alongside a call.

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

Record an action as done only after its result is back and confirms it. In the same
response as the call that performs it, the action is still in progress, not completed.


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

# Flow: Issue invoice for payment due

Goal: issue a new tax invoice (305) for a client, for money that is still owed.

Capabilities: `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

1. This flow is only for money NOT yet received. If it turns out the money has already arrived, stop and use `flow_issue_invoice_receipt_combo` instead, or `flow_issue_payment_received_with_reference_doc` if an existing document already covers it.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. Issuing the invoice MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
5. On a yes, issue the invoice. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome — no download link is required in this report. Then unload `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Invoicing — Write (godfather/admin only)

**Use this capability from within a flow (the flow that issues or cancels the document (flow_issue_*, flow_cancel_*, flow_payment_received_*)), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

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

- `create_invoice` — an ordinary tax invoice (חשבונית מס, 305): a request for
  payment NOT yet received. Default only when the user asks for an invoice
  for money still owed; never for a payment already made.
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
    Only the user explicitly stating the opposite overrides this.
  - `payment_date` is the date the money **actually moved** — never today's
    date unless that's genuinely when it arrived, never a future date. If
    the source doesn't state it clearly, **ask**.
  - `payment_method` records how it arrived — **`bank_transfer` is the
    default** for a deposit/transfer; use `bit`/`paybox`/`cash`/
    `credit_card`/`cheque`/`paypal` when the user says so. Bank details
    (`bank_number`, `bank_branch`, `bank_account`) go with a bank transfer;
    the אסמכתה (`transaction_reference`) with a payment app or PayPal.
    🚨 `bank_number` is the bank's NUMBER (e.g. "31"), never its name —
    never guess or invent a bank name.
  - Take **every** field from the extracted text of the screenshot the user
    sent. Anything not there, or illegible, is something to **ask about** —
    never invent or default it.
- `create_credit_note` — a credit note (חשבונית זיכוי, 330) against an
  existing document — direct ("תפיק לי חשבונית זיכוי") or indirect ("בטל את
  זה").
- `create_receipt` — a receipt (קבלה, 400) against an existing type-305
  document — direct or indirect ("סמן כשולם"). Rejects a type-300 original —
  use `create_combo_document_as_reference` for those.
  🚨 **`payment_date` is required and has no default** — a verbal "mark as
  paid" request has nothing to read a date from, so always ask if the
  conversation doesn't already state one. "Today" is an acceptable answer
  here, but only once the user has actually confirmed it.
- `create_combo_document_as_reference` — a combo document (320) that
  explicitly closes an existing type-300 document — direct or indirect.
  Rejects any original that isn't type 300. Requires `vat_included` — same
  unconditional rule as `create_combo_document`: ALWAYS `true`, never ask.
- `cancel_transaction_account` — cancels an open type-300 account directly
  (no document of any kind is created); rejects any other type. If the
  account is already non-open, this is a no-op that returns the same
  confirmation without calling Morning again — never claim it was "paid".

`create_credit_note`, `create_receipt`, `create_combo_document_as_reference`,
and `cancel_transaction_account` all require an original/reference document
id, taken from the most recent tool result that actually returned it; never ask the
user for it, never guess it.

## The client name

Every write tool that needs one specific client (`create_invoice`,
`create_transaction_account`, `create_combo_document`) takes the EXACT name
Morning has stored, together with `name_resolved=true`; they refuse immediately
if `name_resolved` isn't `true`. Only pass `name_resolved=true` with a name
that has actually been confirmed as Morning's stored name — never with the
user's loose wording. Gather any other still-missing required fields (amount,
description, VAT treatment, dates) one question at a time. Every mutating tool also needs the
user's approval first (see the approval data points below).

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
  client, amount, and purpose (description). **VAT:** required for a transaction account (300), an invoice (305), a combo
  document (320, including combo-as-reference) and a receipt (400) — state it.
  For 320 and 400 it is "included" unless the user explicitly says otherwise. For
  300 and 305 there is NO default: if the user hasn't said, ask. A credit note
  (330) is attached to an existing document and takes its VAT from it — show
  that, never ask. Cancelling a transaction account has no VAT.
  **Plus, whenever known:** transaction date, payment method, bank
  details, transaction reference, linked invoice number.
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

flow_issue_invoice_for_payment_due

## Loaded capabilities

cap_invoicing_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-09-30 15:03 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>20. [2026-09-30 15:04:03] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f1f214793d52681006abcfab1d0a887d1a5408a4d90437978`
- status: `completed`
- usage: `{"input_tokens": 13776, "input_tokens_details": {"cache_write_tokens": 13773, "cached_tokens": 0}, "output_tokens": 91, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 13867}`
- function_call: `approval_with_yes_no_buttons` call_id=`call_L9TYAhAmsncTgItdBUp79JdM`
```json
{
  "text": "📋 לאישור — חשבונית מס:\nלקוח: דמיטרי נוביקסקי\nסכום: 70 שח לפני מעמ\nמעמ: לא כלול\nתאריך החשבונית: 30.09.2026\nמטרה: ייעוץ\nלאישור — כן/לא?"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f1f214793d52681006abcfab1d0a887d1a5408a4d90437978`
- status: `completed`
- usage: `{"input_tokens": 13776, "input_tokens_details": {"cache_write_tokens": 13773, "cached_tokens": 0}, "output_tokens": 91, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 13867}`
- function_call: `approval_with_yes_no_buttons` call_id=`call_L9TYAhAmsncTgItdBUp79JdM`
```json
{
  "text": "📋 לאישור — חשבונית מס:\nלקוח: דמיטרי נוביקסקי\nסכום: 70 שח לפני מעמ\nמעמ: לא כלול\nתאריך החשבונית: 30.09.2026\nמטרה: ייעוץ\nלאישור — כן/לא?"
}
```

</details>

</details>

<details>
<summary>21. [2026-09-30 15:04:03] APP → USER — context=buttons</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "📋 לאישור — חשבונית מס:\nלקוח: דמיטרי נוביקסקי\nסכום: 70 שח לפני מעמ\nמעמ: לא כלול\nתאריך החשבונית: 30.09.2026\nמטרה: ייעוץ\nלאישור — כן/לא?"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "📋 לאישור — חשבונית מס:\nלקוח: דמיטרי נוביקסקי\nסכום: 70 שח לפני מעמ\nמעמ: לא כלול\nתאריך החשבונית: 30.09.2026\nמטרה: ייעוץ\nלאישור — כן/לא?"
}
```

</details>

</details>

<details>
<summary>22. [2026-09-30 15:04:03] APP → MODEL — context=recognize_ledger_event</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

**input:**

```json
{"role": "user", "content": "THE CONVERSATION WINDOW (the last 1h, oldest first) - '<message_id> [<role>] <content>':\nd6d1a4a8-2cbf-47b6-9455-0fa41a26ea22 [godfather] תפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לא כולל מע\"מ עבור ייעוץ\n02d71cd5-ecd5-4d09-816d-e5b8b60cceaa [assistant] מטפל בהפקת החשבונית ובודק את פרטי הלקוח.\n9a04cc7c-d6d7-49dd-96ef-bdbf94ec85c9 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: הבקשה היא להפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לפני מעמ עבור ייעוץ. טרם בוצעה בדיקה במערכת.\nTHIS TURN'S PURPOSE: להפעיל את תהליך הפקת חשבונית עבור תשלום שטרם התקבל, לאתר את הלקוח, לאסוף את פרטי החשבונית ולבקש אישור לפני יצירה.\nEXPECTATION: אבדוק את הלקוח ואת הפרטים הנדרשים; אם הכל ברור, אציג אישור מפורט לפני ההפקה.\n42eaa5de-e154-44a0-8035-4f17f11be01a [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך flow_issue_invoice_for_payment_due, שלב איתור הלקוח הושלם. שם הלקוח המדויק במערכת הוא דמיטרי נוביקסקי. הפרטים שנאספו: חשבונית מס חדשה, 70 שח לפני מעמ, עבור ייעוץ; לא נמסר מועד פירעון ולכן לא אגדיר אותו.\nTHIS TURN'S PURPOSE: לבקש אישור מפורט לפני יצירת החשבונית.\nEXPECTATION: ממתין לתשובת כן או לא. אם יאושר, אצור את החשבונית; אם לא, לא אבצע יצירה.\n10ca1394-3266-4cf5-b0f6-850b510991cc [assistant] 📋 לאישור — חשבונית מס:\nלקוח: דמיטרי נוביקסקי\nסכום: 70 שח לפני מעמ\nמעמ: לא כלול\nתאריך החשבונית: 30.09.2026\nמטרה: ייעוץ\nלאישור — כן/לא?\n    (morning MCP call on this message's turn) {\"name\": \"resolve_client_name\", \"error\": null, \"arguments\": \"{\\\"name\\\":\\\"דמיטרי נוביקסקי\\\"}\", \"output\": \"{\\\"status\\\": \\\"resolved\\\", \\\"name\\\": \\\"\\\\u05d3\\\\u05de\\\\u05d9\\\\u05d8\\\\u05e8\\\\u05d9 \\\\u05e0\\\\u05d5\\\\u05d1\\\\u05d9\\\\u05e7\\\\u05e1\\\\u05e7\\\\u05d9\\\"}\"}\n\nTHE REPLY JUST SENT TO THE OPERATOR THIS ROUND:\n📋 לאישור — חשבונית מס:\nלקוח: דמיטרי נוביקסקי\nסכום: 70 שח לפני מעמ\nמעמ: לא כלול\nתאריך החשבונית: 30.09.2026\nמטרה: ייעוץ\nלאישור — כן/לא?\n\nMORNING MCP TOOL CALLS MADE THIS TURN (verbatim, each with its arguments and its real result):\n[\n  {\n    \"name\": \"resolve_client_name\",\n    \"error\": null,\n    \"arguments\": \"{\\\"name\\\":\\\"דמיטרי נוביקסקי\\\"}\",\n    \"output\": \"{\\\"status\\\": \\\"resolved\\\", \\\"name\\\": \\\"\\\\u05d3\\\\u05de\\\\u05d9\\\\u05d8\\\\u05e8\\\\u05d9 \\\\u05e0\\\\u05d5\\\\u05d1\\\\u05d9\\\\u05e7\\\\u05e1\\\\u05e7\\\\u05d9\\\"}\"\n  }\n]\n\nFollow the recognition prompt above: query the client's ledger history first when the round concerns a client, then call report_ledger_recognition exactly once with the verdict for THIS round."}
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
{"role": "user", "content": "THE CONVERSATION WINDOW (the last 1h, oldest first) - '<message_id> [<role>] <content>':\nd6d1a4a8-2cbf-47b6-9455-0fa41a26ea22 [godfather] תפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לא כולל מע\"מ עבור ייעוץ\n02d71cd5-ecd5-4d09-816d-e5b8b60cceaa [assistant] מטפל בהפקת החשבונית ובודק את פרטי הלקוח.\n9a04cc7c-d6d7-49dd-96ef-bdbf94ec85c9 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: הבקשה היא להפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לפני מעמ עבור ייעוץ. טרם בוצעה בדיקה במערכת.\nTHIS TURN'S PURPOSE: להפעיל את תהליך הפקת חשבונית עבור תשלום שטרם התקבל, לאתר את הלקוח, לאסוף את פרטי החשבונית ולבקש אישור לפני יצירה.\nEXPECTATION: אבדוק את הלקוח ואת הפרטים הנדרשים; אם הכל ברור, אציג אישור מפורט לפני ההפקה.\n42eaa5de-e154-44a0-8035-4f17f11be01a [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך flow_issue_invoice_for_payment_due, שלב איתור הלקוח הושלם. שם הלקוח המדויק במערכת הוא דמיטרי נוביקסקי. הפרטים שנאספו: חשבונית מס חדשה, 70 שח לפני מעמ, עבור ייעוץ; לא נמסר מועד פירעון ולכן לא אגדיר אותו.\nTHIS TURN'S PURPOSE: לבקש אישור מפורט לפני יצירת החשבונית.\nEXPECTATION: ממתין לתשובת כן או לא. אם יאושר, אצור את החשבונית; אם לא, לא אבצע יצירה.\n10ca1394-3266-4cf5-b0f6-850b510991cc [assistant] 📋 לאישור — חשבונית מס:\nלקוח: דמיטרי נוביקסקי\nסכום: 70 שח לפני מעמ\nמעמ: לא כלול\nתאריך החשבונית: 30.09.2026\nמטרה: ייעוץ\nלאישור — כן/לא?\n    (morning MCP call on this message's turn) {\"name\": \"resolve_client_name\", \"error\": null, \"arguments\": \"{\\\"name\\\":\\\"דמיטרי נוביקסקי\\\"}\", \"output\": \"{\\\"status\\\": \\\"resolved\\\", \\\"name\\\": \\\"\\\\u05d3\\\\u05de\\\\u05d9\\\\u05d8\\\\u05e8\\\\u05d9 \\\\u05e0\\\\u05d5\\\\u05d1\\\\u05d9\\\\u05e7\\\\u05e1\\\\u05e7\\\\u05d9\\\"}\"}\n\nTHE REPLY JUST SENT TO THE OPERATOR THIS ROUND:\n📋 לאישור — חשבונית מס:\nלקוח: דמיטרי נוביקסקי\nסכום: 70 שח לפני מעמ\nמעמ: לא כלול\nתאריך החשבונית: 30.09.2026\nמטרה: ייעוץ\nלאישור — כן/לא?\n\nMORNING MCP TOOL CALLS MADE THIS TURN (verbatim, each with its arguments and its real result):\n[\n  {\n    \"name\": \"resolve_client_name\",\n    \"error\": null,\n    \"arguments\": \"{\\\"name\\\":\\\"דמיטרי נוביקסקי\\\"}\",\n    \"output\": \"{\\\"status\\\": \\\"resolved\\\", \\\"name\\\": \\\"\\\\u05d3\\\\u05de\\\\u05d9\\\\u05d8\\\\u05e8\\\\u05d9 \\\\u05e0\\\\u05d5\\\\u05d1\\\\u05d9\\\\u05e7\\\\u05e1\\\\u05e7\\\\u05d9\\\"}\"\n  }\n]\n\nFollow the recognition prompt above: query the client's ledger history first when the round concerns a client, then call report_ledger_recognition exactly once with the verdict for THIS round."}
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
<summary>23. [2026-09-30 15:04:06] MODEL → APP — context=recognize_ledger_event</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0cabe27f79db0c56006abcfab4415c87d1b5f9eecb49d755a4`
- status: `completed`
- usage: `{"input_tokens": 8890, "input_tokens_details": {"cache_write_tokens": 951, "cached_tokens": 7936}, "output_tokens": 107, "output_tokens_details": {"reasoning_tokens": 70}, "total_tokens": 8997}`
- reasoning item (content not user-visible)
- function_call: `query_ledger_events` call_id=`call_QIs77bVaSr3i5VJzlsAe3bV2`
```json
{
  "criteria": [
    {
      "text": "דמיטרי נוביקסקי",
      "hint": "identity"
    }
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0cabe27f79db0c56006abcfab4415c87d1b5f9eecb49d755a4`
- status: `completed`
- usage: `{"input_tokens": 8890, "input_tokens_details": {"cache_write_tokens": 951, "cached_tokens": 7936}, "output_tokens": 107, "output_tokens_details": {"reasoning_tokens": 70}, "total_tokens": 8997}`
- reasoning item (content not user-visible)
- function_call: `query_ledger_events` call_id=`call_QIs77bVaSr3i5VJzlsAe3bV2`
```json
{
  "criteria": [
    {
      "text": "דמיטרי נוביקסקי",
      "hint": "identity"
    }
  ]
}
```

</details>

</details>

<details>
<summary>24. [2026-09-30 15:04:06] APP → MODEL — context=recognize_ledger_event (query round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

**input:**

- app's reply to `query_ledger_events` (call_id=`call_QIs77bVaSr3i5VJzlsAe3bV2`):
```text
{
  "matches": [],
  "count": 0
}
```

- tools (2): ['report_ledger_recognition', 'query_ledger_events']

- previous_response_id: `'resp_0cabe27f79db0c56006abcfab4415c87d1b5f9eecb49d755a4'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: ledger recognition prompt

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

**input:**

- app's reply to `query_ledger_events` (call_id=`call_QIs77bVaSr3i5VJzlsAe3bV2`):
```text
{
  "matches": [],
  "count": 0
}
```

- tools (2): ['report_ledger_recognition', 'query_ledger_events']

- previous_response_id: `'resp_0cabe27f79db0c56006abcfab4415c87d1b5f9eecb49d755a4'`

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
<summary>25. [2026-09-30 15:04:08] MODEL → APP — context=recognize_ledger_event (query round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0cabe27f79db0c56006abcfab6d2a887d1a41767ed342c1920`
- status: `completed`
- usage: `{"input_tokens": 9020, "input_tokens_details": {"cache_write_tokens": 130, "cached_tokens": 8887}, "output_tokens": 41, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9061}`
- function_call: `report_ledger_recognition` call_id=`call_tfXiMYhpNLU6vj0bulUBe8qu`
```json
{
  "verdict": "none",
  "none_reason": "חשבונית ממתינה לאישור ולא נוצרה במסנג'ר"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0cabe27f79db0c56006abcfab6d2a887d1a41767ed342c1920`
- status: `completed`
- usage: `{"input_tokens": 9020, "input_tokens_details": {"cache_write_tokens": 130, "cached_tokens": 8887}, "output_tokens": 41, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 9061}`
- function_call: `report_ledger_recognition` call_id=`call_tfXiMYhpNLU6vj0bulUBe8qu`
```json
{
  "verdict": "none",
  "none_reason": "חשבונית ממתינה לאישור ולא נוצרה במסנג'ר"
}
```

</details>

</details>

<details>
<summary>26. [2026-09-30 15:04:08] USER → APP — context=webhook</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "typeWebhook": "incomingMessageReceived",
  "timestamp": 1790769848,
  "idMessage": "E2E_CREATE_TAP_APPROVE_1790769848",
  "instanceData": {
    "idInstance": 7103000000,
    "wid": "972501234567@c.us",
    "typeInstance": "whatsapp"
  },
  "senderData": {
    "chatId": "972500000021@c.us",
    "sender": "972500000021@c.us",
    "senderName": "E2E Godfather",
    "senderContactName": "E2E Godfather"
  },
  "messageData": {
    "typeMessage": "interactiveButtonsResponse",
    "interactiveButtonsResponse": {
      "stanzaId": "TEST_BUTTONS_E2E_CREATE_TAP_ASK_1790769817_1",
      "selectedIndex": 0,
      "selectedId": "denidin_approve",
      "selectedDisplayText": "כן"
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
  "timestamp": 1790769848,
  "idMessage": "E2E_CREATE_TAP_APPROVE_1790769848",
  "instanceData": {
    "idInstance": 7103000000,
    "wid": "972501234567@c.us",
    "typeInstance": "whatsapp"
  },
  "senderData": {
    "chatId": "972500000021@c.us",
    "sender": "972500000021@c.us",
    "senderName": "E2E Godfather",
    "senderContactName": "E2E Godfather"
  },
  "messageData": {
    "typeMessage": "interactiveButtonsResponse",
    "interactiveButtonsResponse": {
      "stanzaId": "TEST_BUTTONS_E2E_CREATE_TAP_ASK_1790769817_1",
      "selectedIndex": 0,
      "selectedId": "denidin_approve",
      "selectedDisplayText": "כן"
    }
  }
}
```

</details>

</details>

<details>
<summary>27. [2026-09-30 15:04:08] APP → MODEL — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

```json
{"role": "user", "content": "תפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לא כולל מע\"מ עבור ייעוץ"}
```
```json
{"role": "assistant", "content": "מטפל בהפקת החשבונית ובודק את פרטי הלקוח."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: הבקשה היא להפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לפני מעמ עבור ייעוץ. טרם בוצעה בדיקה במערכת.\nTHIS TURN'S PURPOSE: להפעיל את תהליך הפקת חשבונית עבור תשלום שטרם התקבל, לאתר את הלקוח, לאסוף את פרטי החשבונית ולבקש אישור לפני יצירה.\nEXPECTATION: אבדוק את הלקוח ואת הפרטים הנדרשים; אם הכל ברור, אציג אישור מפורט לפני ההפקה."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך flow_issue_invoice_for_payment_due, שלב איתור הלקוח הושלם. שם הלקוח המדויק במערכת הוא דמיטרי נוביקסקי. הפרטים שנאספו: חשבונית מס חדשה, 70 שח לפני מעמ, עבור ייעוץ; לא נמסר מועד פירעון ולכן לא אגדיר אותו.\nTHIS TURN'S PURPOSE: לבקש אישור מפורט לפני יצירת החשבונית.\nEXPECTATION: ממתין לתשובת כן או לא. אם יאושר, אצור את החשבונית; אם לא, לא אבצע יצירה."}
```
```json
{"role": "assistant", "content": "📋 לאישור — חשבונית מס:\nלקוח: דמיטרי נוביקסקי\nסכום: 70 שח לפני מעמ\nמעמ: לא כלול\nתאריך החשבונית: 30.09.2026\nמטרה: ייעוץ\nלאישור — כן/לא?"}
```
```json
{"role": "user", "content": "כן"}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_issue_invoice_for_payment_due, capabilities=cap_invoicing_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

```json
{"role": "user", "content": "תפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לא כולל מע\"מ עבור ייעוץ"}
```
```json
{"role": "assistant", "content": "מטפל בהפקת החשבונית ובודק את פרטי הלקוח."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: הבקשה היא להפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לפני מעמ עבור ייעוץ. טרם בוצעה בדיקה במערכת.\nTHIS TURN'S PURPOSE: להפעיל את תהליך הפקת חשבונית עבור תשלום שטרם התקבל, לאתר את הלקוח, לאסוף את פרטי החשבונית ולבקש אישור לפני יצירה.\nEXPECTATION: אבדוק את הלקוח ואת הפרטים הנדרשים; אם הכל ברור, אציג אישור מפורט לפני ההפקה."}
```
```json
{"role": "assistant", "content": "[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך flow_issue_invoice_for_payment_due, שלב איתור הלקוח הושלם. שם הלקוח המדויק במערכת הוא דמיטרי נוביקסקי. הפרטים שנאספו: חשבונית מס חדשה, 70 שח לפני מעמ, עבור ייעוץ; לא נמסר מועד פירעון ולכן לא אגדיר אותו.\nTHIS TURN'S PURPOSE: לבקש אישור מפורט לפני יצירת החשבונית.\nEXPECTATION: ממתין לתשובת כן או לא. אם יאושר, אצור את החשבונית; אם לא, לא אבצע יצירה."}
```
```json
{"role": "assistant", "content": "📋 לאישור — חשבונית מס:\nלקוח: דמיטרי נוביקסקי\nסכום: 70 שח לפני מעמ\nמעמ: לא כלול\nתאריך החשבונית: 30.09.2026\nמטרה: ייעוץ\nלאישור — כן/לא?"}
```
```json
{"role": "user", "content": "כן"}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp']

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (35257 chars)</summary>

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

**Timing of outcome reactions.** An outcome reaction (✅ 🎉 ⚠️ ❌) reports the
result of an action, so send it only once that action's result is actually back
and says so - never in the same response as the tool call that performs the
action (the call hasn't returned yet, and it may still fail). Acknowledgment
reactions (👍 🫡 👀 ❓ 🙏 ❤️) are not affected: they say you saw the message or
are on it, and can go out at any point, including alongside a call.

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

Record an action as done only after its result is back and confirms it. In the same
response as the call that performs it, the action is still in progress, not completed.


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

# Flow: Issue invoice for payment due

Goal: issue a new tax invoice (305) for a client, for money that is still owed.

Capabilities: `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

1. This flow is only for money NOT yet received. If it turns out the money has already arrived, stop and use `flow_issue_invoice_receipt_combo` instead, or `flow_issue_payment_received_with_reference_doc` if an existing document already covers it.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. Issuing the invoice MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
5. On a yes, issue the invoice. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome — no download link is required in this report. Then unload `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Invoicing — Write (godfather/admin only)

**Use this capability from within a flow (the flow that issues or cancels the document (flow_issue_*, flow_cancel_*, flow_payment_received_*)), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

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

- `create_invoice` — an ordinary tax invoice (חשבונית מס, 305): a request for
  payment NOT yet received. Default only when the user asks for an invoice
  for money still owed; never for a payment already made.
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
    Only the user explicitly stating the opposite overrides this.
  - `payment_date` is the date the money **actually moved** — never today's
    date unless that's genuinely when it arrived, never a future date. If
    the source doesn't state it clearly, **ask**.
  - `payment_method` records how it arrived — **`bank_transfer` is the
    default** for a deposit/transfer; use `bit`/`paybox`/`cash`/
    `credit_card`/`cheque`/`paypal` when the user says so. Bank details
    (`bank_number`, `bank_branch`, `bank_account`) go with a bank transfer;
    the אסמכתה (`transaction_reference`) with a payment app or PayPal.
    🚨 `bank_number` is the bank's NUMBER (e.g. "31"), never its name —
    never guess or invent a bank name.
  - Take **every** field from the extracted text of the screenshot the user
    sent. Anything not there, or illegible, is something to **ask about** —
    never invent or default it.
- `create_credit_note` — a credit note (חשבונית זיכוי, 330) against an
  existing document — direct ("תפיק לי חשבונית זיכוי") or indirect ("בטל את
  זה").
- `create_receipt` — a receipt (קבלה, 400) against an existing type-305
  document — direct or indirect ("סמן כשולם"). Rejects a type-300 original —
  use `create_combo_document_as_reference` for those.
  🚨 **`payment_date` is required and has no default** — a verbal "mark as
  paid" request has nothing to read a date from, so always ask if the
  conversation doesn't already state one. "Today" is an acceptable answer
  here, but only once the user has actually confirmed it.
- `create_combo_document_as_reference` — a combo document (320) that
  explicitly closes an existing type-300 document — direct or indirect.
  Rejects any original that isn't type 300. Requires `vat_included` — same
  unconditional rule as `create_combo_document`: ALWAYS `true`, never ask.
- `cancel_transaction_account` — cancels an open type-300 account directly
  (no document of any kind is created); rejects any other type. If the
  account is already non-open, this is a no-op that returns the same
  confirmation without calling Morning again — never claim it was "paid".

`create_credit_note`, `create_receipt`, `create_combo_document_as_reference`,
and `cancel_transaction_account` all require an original/reference document
id, taken from the most recent tool result that actually returned it; never ask the
user for it, never guess it.

## The client name

Every write tool that needs one specific client (`create_invoice`,
`create_transaction_account`, `create_combo_document`) takes the EXACT name
Morning has stored, together with `name_resolved=true`; they refuse immediately
if `name_resolved` isn't `true`. Only pass `name_resolved=true` with a name
that has actually been confirmed as Morning's stored name — never with the
user's loose wording. Gather any other still-missing required fields (amount,
description, VAT treatment, dates) one question at a time. Every mutating tool also needs the
user's approval first (see the approval data points below).

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
  client, amount, and purpose (description). **VAT:** required for a transaction account (300), an invoice (305), a combo
  document (320, including combo-as-reference) and a receipt (400) — state it.
  For 320 and 400 it is "included" unless the user explicitly says otherwise. For
  300 and 305 there is NO default: if the user hasn't said, ask. A credit note
  (330) is attached to an existing document and takes its VAT from it — show
  that, never ask. Cancelling a transaction account has no VAT.
  **Plus, whenever known:** transaction date, payment method, bank
  details, transaction reference, linked invoice number.
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

flow_issue_invoice_for_payment_due

## Loaded capabilities

cap_invoicing_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-09-30 15:04 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>28. [2026-09-30 15:04:12] MODEL → APP — context=_run_resolution_loop (first round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f33672b8730130f006abcfab91f4487d198bc496a25197a87`
- status: `completed`
- usage: `{"input_tokens": 13197, "input_tokens_details": {"cache_write_tokens": 13194, "cached_tokens": 0}, "output_tokens": 84, "output_tokens_details": {"reasoning_tokens": 58}, "total_tokens": 13281}`
- mcp_list_tools (morning-invoices): ['create_invoice', 'create_transaction_account', 'create_combo_document', 'create_credit_note', 'create_receipt', 'create_combo_document_as_reference', 'cancel_transaction_account', 'list_clients', 'resolve_client_name', 'get_client_details']
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_aC0CqZJjuemRqWvOgF97ajkn`
```json
{
  "emoji": "👍",
  "message_id": null
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f33672b8730130f006abcfab91f4487d198bc496a25197a87`
- status: `completed`
- usage: `{"input_tokens": 13197, "input_tokens_details": {"cache_write_tokens": 13194, "cached_tokens": 0}, "output_tokens": 84, "output_tokens_details": {"reasoning_tokens": 58}, "total_tokens": 13281}`
- mcp_list_tools (morning-invoices): ['create_invoice', 'create_transaction_account', 'create_combo_document', 'create_credit_note', 'create_receipt', 'create_combo_document_as_reference', 'cancel_transaction_account', 'list_clients', 'resolve_client_name', 'get_client_details']
- reasoning item (content not user-visible)
- function_call: `react_to_message` call_id=`call_aC0CqZJjuemRqWvOgF97ajkn`
```json
{
  "emoji": "👍",
  "message_id": null
}
```

</details>

</details>

<details>
<summary>29. [2026-09-30 15:04:12] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `react_to_message` (call_id=`call_aC0CqZJjuemRqWvOgF97ajkn`):
```text
{
  "status": "failed"
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp']

- previous_response_id: `'resp_0f33672b8730130f006abcfab91f4487d198bc496a25197a87'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_issue_invoice_for_payment_due, capabilities=cap_invoicing_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `react_to_message` (call_id=`call_aC0CqZJjuemRqWvOgF97ajkn`):
```text
{
  "status": "failed"
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp']

- previous_response_id: `'resp_0f33672b8730130f006abcfab91f4487d198bc496a25197a87'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (35257 chars)</summary>

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

**Timing of outcome reactions.** An outcome reaction (✅ 🎉 ⚠️ ❌) reports the
result of an action, so send it only once that action's result is actually back
and says so - never in the same response as the tool call that performs the
action (the call hasn't returned yet, and it may still fail). Acknowledgment
reactions (👍 🫡 👀 ❓ 🙏 ❤️) are not affected: they say you saw the message or
are on it, and can go out at any point, including alongside a call.

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

Record an action as done only after its result is back and confirms it. In the same
response as the call that performs it, the action is still in progress, not completed.


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

# Flow: Issue invoice for payment due

Goal: issue a new tax invoice (305) for a client, for money that is still owed.

Capabilities: `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

1. This flow is only for money NOT yet received. If it turns out the money has already arrived, stop and use `flow_issue_invoice_receipt_combo` instead, or `flow_issue_payment_received_with_reference_doc` if an existing document already covers it.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. Issuing the invoice MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
5. On a yes, issue the invoice. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome — no download link is required in this report. Then unload `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Invoicing — Write (godfather/admin only)

**Use this capability from within a flow (the flow that issues or cancels the document (flow_issue_*, flow_cancel_*, flow_payment_received_*)), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

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

- `create_invoice` — an ordinary tax invoice (חשבונית מס, 305): a request for
  payment NOT yet received. Default only when the user asks for an invoice
  for money still owed; never for a payment already made.
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
    Only the user explicitly stating the opposite overrides this.
  - `payment_date` is the date the money **actually moved** — never today's
    date unless that's genuinely when it arrived, never a future date. If
    the source doesn't state it clearly, **ask**.
  - `payment_method` records how it arrived — **`bank_transfer` is the
    default** for a deposit/transfer; use `bit`/`paybox`/`cash`/
    `credit_card`/`cheque`/`paypal` when the user says so. Bank details
    (`bank_number`, `bank_branch`, `bank_account`) go with a bank transfer;
    the אסמכתה (`transaction_reference`) with a payment app or PayPal.
    🚨 `bank_number` is the bank's NUMBER (e.g. "31"), never its name —
    never guess or invent a bank name.
  - Take **every** field from the extracted text of the screenshot the user
    sent. Anything not there, or illegible, is something to **ask about** —
    never invent or default it.
- `create_credit_note` — a credit note (חשבונית זיכוי, 330) against an
  existing document — direct ("תפיק לי חשבונית זיכוי") or indirect ("בטל את
  זה").
- `create_receipt` — a receipt (קבלה, 400) against an existing type-305
  document — direct or indirect ("סמן כשולם"). Rejects a type-300 original —
  use `create_combo_document_as_reference` for those.
  🚨 **`payment_date` is required and has no default** — a verbal "mark as
  paid" request has nothing to read a date from, so always ask if the
  conversation doesn't already state one. "Today" is an acceptable answer
  here, but only once the user has actually confirmed it.
- `create_combo_document_as_reference` — a combo document (320) that
  explicitly closes an existing type-300 document — direct or indirect.
  Rejects any original that isn't type 300. Requires `vat_included` — same
  unconditional rule as `create_combo_document`: ALWAYS `true`, never ask.
- `cancel_transaction_account` — cancels an open type-300 account directly
  (no document of any kind is created); rejects any other type. If the
  account is already non-open, this is a no-op that returns the same
  confirmation without calling Morning again — never claim it was "paid".

`create_credit_note`, `create_receipt`, `create_combo_document_as_reference`,
and `cancel_transaction_account` all require an original/reference document
id, taken from the most recent tool result that actually returned it; never ask the
user for it, never guess it.

## The client name

Every write tool that needs one specific client (`create_invoice`,
`create_transaction_account`, `create_combo_document`) takes the EXACT name
Morning has stored, together with `name_resolved=true`; they refuse immediately
if `name_resolved` isn't `true`. Only pass `name_resolved=true` with a name
that has actually been confirmed as Morning's stored name — never with the
user's loose wording. Gather any other still-missing required fields (amount,
description, VAT treatment, dates) one question at a time. Every mutating tool also needs the
user's approval first (see the approval data points below).

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
  client, amount, and purpose (description). **VAT:** required for a transaction account (300), an invoice (305), a combo
  document (320, including combo-as-reference) and a receipt (400) — state it.
  For 320 and 400 it is "included" unless the user explicitly says otherwise. For
  300 and 305 there is NO default: if the user hasn't said, ask. A credit note
  (330) is attached to an existing document and takes its VAT from it — show
  that, never ask. Cancelling a transaction account has no VAT.
  **Plus, whenever known:** transaction date, payment method, bank
  details, transaction reference, linked invoice number.
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

flow_issue_invoice_for_payment_due

## Loaded capabilities

cap_invoicing_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-09-30 15:04 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>30. [2026-09-30 15:04:15] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f33672b8730130f006abcfabd3ab887d18c3728483d5c5e3e`
- status: `completed`
- usage: `{"input_tokens": 13304, "input_tokens_details": {"cache_write_tokens": 13301, "cached_tokens": 0}, "output_tokens": 46, "output_tokens_details": {"reasoning_tokens": 13}, "total_tokens": 13350}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_D6gGT5NvpQwSiJ2aYvUIyX9C`
```json
{
  "text": "יוצר עכשיו את החשבונית המאושרת במערכת."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f33672b8730130f006abcfabd3ab887d18c3728483d5c5e3e`
- status: `completed`
- usage: `{"input_tokens": 13304, "input_tokens_details": {"cache_write_tokens": 13301, "cached_tokens": 0}, "output_tokens": 46, "output_tokens_details": {"reasoning_tokens": 13}, "total_tokens": 13350}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_D6gGT5NvpQwSiJ2aYvUIyX9C`
```json
{
  "text": "יוצר עכשיו את החשבונית המאושרת במערכת."
}
```

</details>

</details>

<details>
<summary>31. [2026-09-30 15:04:15] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "יוצר עכשיו את החשבונית המאושרת במערכת."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "יוצר עכשיו את החשבונית המאושרת במערכת."
}
```

</details>

</details>

<details>
<summary>32. [2026-09-30 15:04:15] USER ← APP (send result) — context=progress_update</summary>

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
<summary>33. [2026-09-30 15:04:15] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `send_progress_update` (call_id=`call_D6gGT5NvpQwSiJ2aYvUIyX9C`):
```text
{
  "sent": true
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp']

- previous_response_id: `'resp_0f33672b8730130f006abcfabd3ab887d18c3728483d5c5e3e'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_issue_invoice_for_payment_due, capabilities=cap_invoicing_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `send_progress_update` (call_id=`call_D6gGT5NvpQwSiJ2aYvUIyX9C`):
```text
{
  "sent": true
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp']

- previous_response_id: `'resp_0f33672b8730130f006abcfabd3ab887d18c3728483d5c5e3e'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (35257 chars)</summary>

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

**Timing of outcome reactions.** An outcome reaction (✅ 🎉 ⚠️ ❌) reports the
result of an action, so send it only once that action's result is actually back
and says so - never in the same response as the tool call that performs the
action (the call hasn't returned yet, and it may still fail). Acknowledgment
reactions (👍 🫡 👀 ❓ 🙏 ❤️) are not affected: they say you saw the message or
are on it, and can go out at any point, including alongside a call.

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

Record an action as done only after its result is back and confirms it. In the same
response as the call that performs it, the action is still in progress, not completed.


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

# Flow: Issue invoice for payment due

Goal: issue a new tax invoice (305) for a client, for money that is still owed.

Capabilities: `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

1. This flow is only for money NOT yet received. If it turns out the money has already arrived, stop and use `flow_issue_invoice_receipt_combo` instead, or `flow_issue_payment_received_with_reference_doc` if an existing document already covers it.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. Issuing the invoice MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
5. On a yes, issue the invoice. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome — no download link is required in this report. Then unload `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Invoicing — Write (godfather/admin only)

**Use this capability from within a flow (the flow that issues or cancels the document (flow_issue_*, flow_cancel_*, flow_payment_received_*)), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

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

- `create_invoice` — an ordinary tax invoice (חשבונית מס, 305): a request for
  payment NOT yet received. Default only when the user asks for an invoice
  for money still owed; never for a payment already made.
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
    Only the user explicitly stating the opposite overrides this.
  - `payment_date` is the date the money **actually moved** — never today's
    date unless that's genuinely when it arrived, never a future date. If
    the source doesn't state it clearly, **ask**.
  - `payment_method` records how it arrived — **`bank_transfer` is the
    default** for a deposit/transfer; use `bit`/`paybox`/`cash`/
    `credit_card`/`cheque`/`paypal` when the user says so. Bank details
    (`bank_number`, `bank_branch`, `bank_account`) go with a bank transfer;
    the אסמכתה (`transaction_reference`) with a payment app or PayPal.
    🚨 `bank_number` is the bank's NUMBER (e.g. "31"), never its name —
    never guess or invent a bank name.
  - Take **every** field from the extracted text of the screenshot the user
    sent. Anything not there, or illegible, is something to **ask about** —
    never invent or default it.
- `create_credit_note` — a credit note (חשבונית זיכוי, 330) against an
  existing document — direct ("תפיק לי חשבונית זיכוי") or indirect ("בטל את
  זה").
- `create_receipt` — a receipt (קבלה, 400) against an existing type-305
  document — direct or indirect ("סמן כשולם"). Rejects a type-300 original —
  use `create_combo_document_as_reference` for those.
  🚨 **`payment_date` is required and has no default** — a verbal "mark as
  paid" request has nothing to read a date from, so always ask if the
  conversation doesn't already state one. "Today" is an acceptable answer
  here, but only once the user has actually confirmed it.
- `create_combo_document_as_reference` — a combo document (320) that
  explicitly closes an existing type-300 document — direct or indirect.
  Rejects any original that isn't type 300. Requires `vat_included` — same
  unconditional rule as `create_combo_document`: ALWAYS `true`, never ask.
- `cancel_transaction_account` — cancels an open type-300 account directly
  (no document of any kind is created); rejects any other type. If the
  account is already non-open, this is a no-op that returns the same
  confirmation without calling Morning again — never claim it was "paid".

`create_credit_note`, `create_receipt`, `create_combo_document_as_reference`,
and `cancel_transaction_account` all require an original/reference document
id, taken from the most recent tool result that actually returned it; never ask the
user for it, never guess it.

## The client name

Every write tool that needs one specific client (`create_invoice`,
`create_transaction_account`, `create_combo_document`) takes the EXACT name
Morning has stored, together with `name_resolved=true`; they refuse immediately
if `name_resolved` isn't `true`. Only pass `name_resolved=true` with a name
that has actually been confirmed as Morning's stored name — never with the
user's loose wording. Gather any other still-missing required fields (amount,
description, VAT treatment, dates) one question at a time. Every mutating tool also needs the
user's approval first (see the approval data points below).

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
  client, amount, and purpose (description). **VAT:** required for a transaction account (300), an invoice (305), a combo
  document (320, including combo-as-reference) and a receipt (400) — state it.
  For 320 and 400 it is "included" unless the user explicitly says otherwise. For
  300 and 305 there is NO default: if the user hasn't said, ask. A credit note
  (330) is attached to an existing document and takes its VAT from it — show
  that, never ask. Cancelling a transaction account has no VAT.
  **Plus, whenever known:** transaction date, payment method, bank
  details, transaction reference, linked invoice number.
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

flow_issue_invoice_for_payment_due

## Loaded capabilities

cap_invoicing_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-09-30 15:04 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>34. [2026-09-30 15:04:17] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f33672b8730130f006abcfabf71e087d1b8edb08601e08721`
- status: `completed`
- usage: `{"input_tokens": 13362, "input_tokens_details": {"cache_write_tokens": 165, "cached_tokens": 13194}, "output_tokens": 101, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 13463}`
- function_call: `record_planning_status` call_id=`call_BYIQVQw1z5fX7gXSXV4L7CjL`
```json
{
  "where_i_was": "בתהליך הפקת חשבונית מס עבור דמיטרי נוביקסקי. המשתמש אישר את הפרטים: 70 שח לפני מעמ עבור ייעוץ.",
  "this_turns_purpose": "ליצור את החשבונית במערכת לאחר האישור.",
  "expectation": "אמתין לתוצאת היצירה ואדווח במספר החשבונית או בכשל."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f33672b8730130f006abcfabf71e087d1b8edb08601e08721`
- status: `completed`
- usage: `{"input_tokens": 13362, "input_tokens_details": {"cache_write_tokens": 165, "cached_tokens": 13194}, "output_tokens": 101, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 13463}`
- function_call: `record_planning_status` call_id=`call_BYIQVQw1z5fX7gXSXV4L7CjL`
```json
{
  "where_i_was": "בתהליך הפקת חשבונית מס עבור דמיטרי נוביקסקי. המשתמש אישר את הפרטים: 70 שח לפני מעמ עבור ייעוץ.",
  "this_turns_purpose": "ליצור את החשבונית במערכת לאחר האישור.",
  "expectation": "אמתין לתוצאת היצירה ואדווח במספר החשבונית או בכשל."
}
```

</details>

</details>

<details>
<summary>35. [2026-09-30 15:04:17] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `record_planning_status` (call_id=`call_BYIQVQw1z5fX7gXSXV4L7CjL`):
```text
recorded
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp']

- previous_response_id: `'resp_0f33672b8730130f006abcfabf71e087d1b8edb08601e08721'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_issue_invoice_for_payment_due, capabilities=cap_invoicing_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `record_planning_status` (call_id=`call_BYIQVQw1z5fX7gXSXV4L7CjL`):
```text
recorded
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp']

- previous_response_id: `'resp_0f33672b8730130f006abcfabf71e087d1b8edb08601e08721'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (35257 chars)</summary>

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

**Timing of outcome reactions.** An outcome reaction (✅ 🎉 ⚠️ ❌) reports the
result of an action, so send it only once that action's result is actually back
and says so - never in the same response as the tool call that performs the
action (the call hasn't returned yet, and it may still fail). Acknowledgment
reactions (👍 🫡 👀 ❓ 🙏 ❤️) are not affected: they say you saw the message or
are on it, and can go out at any point, including alongside a call.

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

Record an action as done only after its result is back and confirms it. In the same
response as the call that performs it, the action is still in progress, not completed.


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

# Flow: Issue invoice for payment due

Goal: issue a new tax invoice (305) for a client, for money that is still owed.

Capabilities: `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

1. This flow is only for money NOT yet received. If it turns out the money has already arrived, stop and use `flow_issue_invoice_receipt_combo` instead, or `flow_issue_payment_received_with_reference_doc` if an existing document already covers it.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. Issuing the invoice MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
5. On a yes, issue the invoice. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome — no download link is required in this report. Then unload `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Invoicing — Write (godfather/admin only)

**Use this capability from within a flow (the flow that issues or cancels the document (flow_issue_*, flow_cancel_*, flow_payment_received_*)), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

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

- `create_invoice` — an ordinary tax invoice (חשבונית מס, 305): a request for
  payment NOT yet received. Default only when the user asks for an invoice
  for money still owed; never for a payment already made.
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
    Only the user explicitly stating the opposite overrides this.
  - `payment_date` is the date the money **actually moved** — never today's
    date unless that's genuinely when it arrived, never a future date. If
    the source doesn't state it clearly, **ask**.
  - `payment_method` records how it arrived — **`bank_transfer` is the
    default** for a deposit/transfer; use `bit`/`paybox`/`cash`/
    `credit_card`/`cheque`/`paypal` when the user says so. Bank details
    (`bank_number`, `bank_branch`, `bank_account`) go with a bank transfer;
    the אסמכתה (`transaction_reference`) with a payment app or PayPal.
    🚨 `bank_number` is the bank's NUMBER (e.g. "31"), never its name —
    never guess or invent a bank name.
  - Take **every** field from the extracted text of the screenshot the user
    sent. Anything not there, or illegible, is something to **ask about** —
    never invent or default it.
- `create_credit_note` — a credit note (חשבונית זיכוי, 330) against an
  existing document — direct ("תפיק לי חשבונית זיכוי") or indirect ("בטל את
  זה").
- `create_receipt` — a receipt (קבלה, 400) against an existing type-305
  document — direct or indirect ("סמן כשולם"). Rejects a type-300 original —
  use `create_combo_document_as_reference` for those.
  🚨 **`payment_date` is required and has no default** — a verbal "mark as
  paid" request has nothing to read a date from, so always ask if the
  conversation doesn't already state one. "Today" is an acceptable answer
  here, but only once the user has actually confirmed it.
- `create_combo_document_as_reference` — a combo document (320) that
  explicitly closes an existing type-300 document — direct or indirect.
  Rejects any original that isn't type 300. Requires `vat_included` — same
  unconditional rule as `create_combo_document`: ALWAYS `true`, never ask.
- `cancel_transaction_account` — cancels an open type-300 account directly
  (no document of any kind is created); rejects any other type. If the
  account is already non-open, this is a no-op that returns the same
  confirmation without calling Morning again — never claim it was "paid".

`create_credit_note`, `create_receipt`, `create_combo_document_as_reference`,
and `cancel_transaction_account` all require an original/reference document
id, taken from the most recent tool result that actually returned it; never ask the
user for it, never guess it.

## The client name

Every write tool that needs one specific client (`create_invoice`,
`create_transaction_account`, `create_combo_document`) takes the EXACT name
Morning has stored, together with `name_resolved=true`; they refuse immediately
if `name_resolved` isn't `true`. Only pass `name_resolved=true` with a name
that has actually been confirmed as Morning's stored name — never with the
user's loose wording. Gather any other still-missing required fields (amount,
description, VAT treatment, dates) one question at a time. Every mutating tool also needs the
user's approval first (see the approval data points below).

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
  client, amount, and purpose (description). **VAT:** required for a transaction account (300), an invoice (305), a combo
  document (320, including combo-as-reference) and a receipt (400) — state it.
  For 320 and 400 it is "included" unless the user explicitly says otherwise. For
  300 and 305 there is NO default: if the user hasn't said, ask. A credit note
  (330) is attached to an existing document and takes its VAT from it — show
  that, never ask. Cancelling a transaction account has no VAT.
  **Plus, whenever known:** transaction date, payment method, bank
  details, transaction reference, linked invoice number.
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

flow_issue_invoice_for_payment_due

## Loaded capabilities

cap_invoicing_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-09-30 15:04 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>36. [2026-09-30 15:04:24] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 1/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f33672b8730130f006abcfac246f487d18098242a69439647`
- status: `completed`
- usage: `{"input_tokens": 13917, "input_tokens_details": {"cache_write_tokens": 116, "cached_tokens": 13359}, "output_tokens": 214, "output_tokens_details": {"reasoning_tokens": 129}, "total_tokens": 14131}`

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f33672b8730130f006abcfac246f487d18098242a69439647`
- status: `completed`
- usage: `{"input_tokens": 13917, "input_tokens_details": {"cache_write_tokens": 116, "cached_tokens": 13359}, "output_tokens": 214, "output_tokens_details": {"reasoning_tokens": 129}, "total_tokens": 14131}`
- (no output items in this part)

</details>

</details>

<details>
<summary>37. [2026-09-30 15:04:24] MODEL → MORNING MCP — create_invoice</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- tool name: `create_invoice`
- server_label: `'morning-invoices'`

arguments:
```json
{
  "client_name": "דמיטרי נוביקסקי",
  "amount": 70,
  "description": "ייעוץ",
  "due_date": null,
  "vat_included": false,
  "name_resolved": true
}
```

</details>

</details>

<details>
<summary>38. [2026-09-30 15:04:24] MORNING MCP → MODEL — create_invoice</summary>

<details>
<summary>↳ Debug (full, verbatim)</summary>

output:
```json
{
  "display_number": "52567",
  "internal_morning_id": "c90d9eb8-1b38-400d-9c3d-3dbf55107f5c",
  "type": 305,
  "type_name": "חשבונית מס",
  "status": "unpaid",
  "status_code": 0,
  "status_label": "מסמך פתוח",
  "client_name": "דמיטרי נוביקסקי",
  "description": "ייעוץ",
  "amount": 82.6,
  "amount_excl_vat": 70.0,
  "vat_amount": 12.6,
  "vat_rate": 0.18,
  "currency": "ILS",
  "document_date": "2026-09-30",
  "due_date": null,
  "creation_date": "2026-09-30T15:04:21+03:00",
  "payment": null,
  "line_items": [
    {
      "description": "ייעוץ",
      "quantity": 1,
      "price": 70,
      "amount": 82.6
    }
  ],
  "linked_document": null
}
```

</details>

</details>

<details>
<summary>39. [2026-09-30 15:04:24] MODEL → APP — context=_run_resolution_loop (follow-up) (response part 2/2)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f33672b8730130f006abcfac246f487d18098242a69439647`
- status: `completed`
- usage: `{"input_tokens": 13917, "input_tokens_details": {"cache_write_tokens": 116, "cached_tokens": 13359}, "output_tokens": 214, "output_tokens_details": {"reasoning_tokens": 129}, "total_tokens": 14131}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_llsN6E6bE5KiDG3kA7JED5TO`
```json
{
  "text": "החשבונית נוצרה בהצלחה."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f33672b8730130f006abcfac246f487d18098242a69439647`
- status: `completed`
- usage: `{"input_tokens": 13917, "input_tokens_details": {"cache_write_tokens": 116, "cached_tokens": 13359}, "output_tokens": 214, "output_tokens_details": {"reasoning_tokens": 129}, "total_tokens": 14131}`
- reasoning item (content not user-visible)
- function_call: `send_progress_update` call_id=`call_llsN6E6bE5KiDG3kA7JED5TO`
```json
{
  "text": "החשבונית נוצרה בהצלחה."
}
```

</details>

</details>

<details>
<summary>40. [2026-09-30 15:04:24] APP → USER — context=progress_update</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "החשבונית נוצרה בהצלחה."
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "החשבונית נוצרה בהצלחה."
}
```

</details>

</details>

<details>
<summary>41. [2026-09-30 15:04:24] USER ← APP (send result) — context=progress_update</summary>

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
<summary>42. [2026-09-30 15:04:24] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `send_progress_update` (call_id=`call_llsN6E6bE5KiDG3kA7JED5TO`):
```text
{
  "sent": true
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp']

- previous_response_id: `'resp_0f33672b8730130f006abcfac246f487d18098242a69439647'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=flow_issue_invoice_for_payment_due, capabilities=cap_invoicing_write, cap_client_read, cap_approval_with_buttons)

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: flow_issue_invoice_for_payment_due

- capabilities: cap_invoicing_write, cap_client_read, cap_approval_with_buttons

**input:**

- app's reply to `send_progress_update` (call_id=`call_llsN6E6bE5KiDG3kA7JED5TO`):
```text
{
  "sent": true
}
```

- tools (11): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message', 'approval_with_yes_no_buttons', 'mcp']

- previous_response_id: `'resp_0f33672b8730130f006abcfac246f487d18098242a69439647'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (35257 chars)</summary>

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

**Timing of outcome reactions.** An outcome reaction (✅ 🎉 ⚠️ ❌) reports the
result of an action, so send it only once that action's result is actually back
and says so - never in the same response as the tool call that performs the
action (the call hasn't returned yet, and it may still fail). Acknowledgment
reactions (👍 🫡 👀 ❓ 🙏 ❤️) are not affected: they say you saw the message or
are on it, and can go out at any point, including alongside a call.

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

Record an action as done only after its result is back and confirms it. In the same
response as the call that performs it, the action is still in progress, not completed.


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

# Flow: Issue invoice for payment due

Goal: issue a new tax invoice (305) for a client, for money that is still owed.

Capabilities: `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

1. This flow is only for money NOT yet received. If it turns out the money has already arrived, stop and use `flow_issue_invoice_receipt_combo` instead, or `flow_issue_payment_received_with_reference_doc` if an existing document already covers it.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. Issuing the invoice MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
5. On a yes, issue the invoice. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome — no download link is required in this report. Then unload `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.


# Capability: Invoicing — Write (godfather/admin only)

**Use this capability from within a flow (the flow that issues or cancels the document (flow_issue_*, flow_cancel_*, flow_payment_received_*)), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

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

- `create_invoice` — an ordinary tax invoice (חשבונית מס, 305): a request for
  payment NOT yet received. Default only when the user asks for an invoice
  for money still owed; never for a payment already made.
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
    Only the user explicitly stating the opposite overrides this.
  - `payment_date` is the date the money **actually moved** — never today's
    date unless that's genuinely when it arrived, never a future date. If
    the source doesn't state it clearly, **ask**.
  - `payment_method` records how it arrived — **`bank_transfer` is the
    default** for a deposit/transfer; use `bit`/`paybox`/`cash`/
    `credit_card`/`cheque`/`paypal` when the user says so. Bank details
    (`bank_number`, `bank_branch`, `bank_account`) go with a bank transfer;
    the אסמכתה (`transaction_reference`) with a payment app or PayPal.
    🚨 `bank_number` is the bank's NUMBER (e.g. "31"), never its name —
    never guess or invent a bank name.
  - Take **every** field from the extracted text of the screenshot the user
    sent. Anything not there, or illegible, is something to **ask about** —
    never invent or default it.
- `create_credit_note` — a credit note (חשבונית זיכוי, 330) against an
  existing document — direct ("תפיק לי חשבונית זיכוי") or indirect ("בטל את
  זה").
- `create_receipt` — a receipt (קבלה, 400) against an existing type-305
  document — direct or indirect ("סמן כשולם"). Rejects a type-300 original —
  use `create_combo_document_as_reference` for those.
  🚨 **`payment_date` is required and has no default** — a verbal "mark as
  paid" request has nothing to read a date from, so always ask if the
  conversation doesn't already state one. "Today" is an acceptable answer
  here, but only once the user has actually confirmed it.
- `create_combo_document_as_reference` — a combo document (320) that
  explicitly closes an existing type-300 document — direct or indirect.
  Rejects any original that isn't type 300. Requires `vat_included` — same
  unconditional rule as `create_combo_document`: ALWAYS `true`, never ask.
- `cancel_transaction_account` — cancels an open type-300 account directly
  (no document of any kind is created); rejects any other type. If the
  account is already non-open, this is a no-op that returns the same
  confirmation without calling Morning again — never claim it was "paid".

`create_credit_note`, `create_receipt`, `create_combo_document_as_reference`,
and `cancel_transaction_account` all require an original/reference document
id, taken from the most recent tool result that actually returned it; never ask the
user for it, never guess it.

## The client name

Every write tool that needs one specific client (`create_invoice`,
`create_transaction_account`, `create_combo_document`) takes the EXACT name
Morning has stored, together with `name_resolved=true`; they refuse immediately
if `name_resolved` isn't `true`. Only pass `name_resolved=true` with a name
that has actually been confirmed as Morning's stored name — never with the
user's loose wording. Gather any other still-missing required fields (amount,
description, VAT treatment, dates) one question at a time. Every mutating tool also needs the
user's approval first (see the approval data points below).

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
  client, amount, and purpose (description). **VAT:** required for a transaction account (300), an invoice (305), a combo
  document (320, including combo-as-reference) and a receipt (400) — state it.
  For 320 and 400 it is "included" unless the user explicitly says otherwise. For
  300 and 305 there is NO default: if the user hasn't said, ask. A credit note
  (330) is attached to an existing document and takes its VAT from it — show
  that, never ask. Cancelling a transaction account has no VAT.
  **Plus, whenever known:** transaction date, payment method, bank
  details, transaction reference, linked invoice number.
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

flow_issue_invoice_for_payment_due

## Loaded capabilities

cap_invoicing_write, cap_client_read, cap_approval_with_buttons

---

THE CURRENT DATE AND TIME IS 2026-09-30 15:04 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>43. [2026-09-30 15:04:28] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f33672b8730130f006abcfac8ee0487d1823dd48abfaaab3b`
- status: `completed`
- usage: `{"input_tokens": 14085, "input_tokens_details": {"cache_write_tokens": 607, "cached_tokens": 13475}, "output_tokens": 215, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 14300}`
- function_call: `react_to_message` call_id=`call_ltCweTLuXc0ncjSpMjObXeAG`
```json
{
  "emoji": "✅",
  "message_id": null
}
```
- function_call: `record_planning_status` call_id=`call_S35X0ZGbkWP86GJI6jO75u2J`
```json
{
  "where_i_was": "החשבונית נוצרה בהצלחה במערכת עבור דמיטרי נוביקסקי. מספר החשבונית: 52567. הסכום הכולל כולל מעמ הוא 82.60 שח, מתוכם 70 שח לפני מעמ ו-12.60 שח מעמ. הסטטוס פתוח.",
  "this_turns_purpose": "לדווח למשתמש על הצלחת ההפקה ולסיים את התהליך.",
  "expectation": "אין פעולה נוספת נדרשת."
}
```
- function_call: `unload_flows` call_id=`call_WEBA7xwMeJu2WNOBhwSzMu9X`
```json
{
  "flows": [
    "flow_issue_invoice_for_payment_due"
  ]
}
```
- function_call: `unload_capabilities` call_id=`call_buUcEGRlDe3UuNol0iXdieRc`
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

- response.id: `resp_0f33672b8730130f006abcfac8ee0487d1823dd48abfaaab3b`
- status: `completed`
- usage: `{"input_tokens": 14085, "input_tokens_details": {"cache_write_tokens": 607, "cached_tokens": 13475}, "output_tokens": 215, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 14300}`
- function_call: `react_to_message` call_id=`call_ltCweTLuXc0ncjSpMjObXeAG`
```json
{
  "emoji": "✅",
  "message_id": null
}
```
- function_call: `record_planning_status` call_id=`call_S35X0ZGbkWP86GJI6jO75u2J`
```json
{
  "where_i_was": "החשבונית נוצרה בהצלחה במערכת עבור דמיטרי נוביקסקי. מספר החשבונית: 52567. הסכום הכולל כולל מעמ הוא 82.60 שח, מתוכם 70 שח לפני מעמ ו-12.60 שח מעמ. הסטטוס פתוח.",
  "this_turns_purpose": "לדווח למשתמש על הצלחת ההפקה ולסיים את התהליך.",
  "expectation": "אין פעולה נוספת נדרשת."
}
```
- function_call: `unload_flows` call_id=`call_WEBA7xwMeJu2WNOBhwSzMu9X`
```json
{
  "flows": [
    "flow_issue_invoice_for_payment_due"
  ]
}
```
- function_call: `unload_capabilities` call_id=`call_buUcEGRlDe3UuNol0iXdieRc`
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
<summary>44. [2026-09-30 15:04:28] APP → MODEL — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `record_planning_status` (call_id=`call_S35X0ZGbkWP86GJI6jO75u2J`):
```text
recorded
```
- app's reply to `unload_flows` (call_id=`call_WEBA7xwMeJu2WNOBhwSzMu9X`):
```text
unloaded flows: flow_issue_invoice_for_payment_due. Loaded flows now: (none). Loaded capabilities now: cap_client_read, cap_invoicing_write, cap_approval_with_buttons.
```
- app's reply to `unload_capabilities` (call_id=`call_buUcEGRlDe3UuNol0iXdieRc`):
```text
unloaded capabilitys: cap_client_read, cap_invoicing_write, cap_approval_with_buttons. Loaded flows now: (none). Loaded capabilities now: (none).
```
- app's reply to `react_to_message` (call_id=`call_ltCweTLuXc0ncjSpMjObXeAG`):
```text
{
  "status": "failed"
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0f33672b8730130f006abcfac8ee0487d1823dd48abfaaab3b'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: backbone (flows=(none), capabilities=(none - plain backbone))

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- flows: (none)

- capabilities: (none - plain backbone)

**input:**

- app's reply to `record_planning_status` (call_id=`call_S35X0ZGbkWP86GJI6jO75u2J`):
```text
recorded
```
- app's reply to `unload_flows` (call_id=`call_WEBA7xwMeJu2WNOBhwSzMu9X`):
```text
unloaded flows: flow_issue_invoice_for_payment_due. Loaded flows now: (none). Loaded capabilities now: cap_client_read, cap_invoicing_write, cap_approval_with_buttons.
```
- app's reply to `unload_capabilities` (call_id=`call_buUcEGRlDe3UuNol0iXdieRc`):
```text
unloaded capabilitys: cap_client_read, cap_invoicing_write, cap_approval_with_buttons. Loaded flows now: (none). Loaded capabilities now: (none).
```
- app's reply to `react_to_message` (call_id=`call_ltCweTLuXc0ncjSpMjObXeAG`):
```text
{
  "status": "failed"
}
```

- tools (9): ['load_flows', 'unload_flows', 'load_capabilities', 'unload_capabilities', 'reset_to_backbone', 'record_planning_status', 'send_to_user', 'send_progress_update', 'react_to_message']

- previous_response_id: `'resp_0f33672b8730130f006abcfac8ee0487d1823dd48abfaaab3b'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

<details>
<summary>↳↳ instructions (19640 chars)</summary>

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

**Timing of outcome reactions.** An outcome reaction (✅ 🎉 ⚠️ ❌) reports the
result of an action, so send it only once that action's result is actually back
and says so - never in the same response as the tool call that performs the
action (the call hasn't returned yet, and it may still fail). Acknowledgment
reactions (👍 🫡 👀 ❓ 🙏 ❤️) are not affected: they say you saw the message or
are on it, and can go out at any point, including alongside a call.

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

Record an action as done only after its result is back and confirms it. In the same
response as the call that performs it, the action is still in progress, not completed.


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

THE CURRENT DATE AND TIME IS 2026-09-30 15:04 (Asia/Jerusalem, Israel local time). Treat this as the authoritative "now" when resolving any relative or partial date/time the user gives (a day/month with no year, "היום", "אתמול", "בעוד שעה", "בעוד חצי שעה", etc.) — never fall back on a year from your training data, and never ask the user what time it is now.
YOUR CURRENT VERSION IS 0.7.8. If asked what version you are running (in any language), state this exact value.
```

</details>

</details>

</details>

<details>
<summary>45. [2026-09-30 15:04:30] MODEL → APP — context=_run_resolution_loop (follow-up)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_0f33672b8730130f006abcfacc616487d18a5f0a9c40bca2c1`
- status: `completed`
- usage: `{"input_tokens": 7725, "input_tokens_details": {"cache_write_tokens": 7722, "cached_tokens": 0}, "output_tokens": 95, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7820}`
- function_call: `send_to_user` call_id=`call_DeNpy06PSu6xYilcld0leAGr`
```json
{
  "text": "החשבונית הופקה בהצלחה ✅\n\nמספר חשבונית: 52567\nלקוח: דמיטרי נוביקסקי\nסכום לפני מעמ: 70 שח\nמעמ: 12.60 שח\nסכום כולל: 82.60 שח\nעבור: ייעוץ\nסטטוס: פתוחה"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_0f33672b8730130f006abcfacc616487d18a5f0a9c40bca2c1`
- status: `completed`
- usage: `{"input_tokens": 7725, "input_tokens_details": {"cache_write_tokens": 7722, "cached_tokens": 0}, "output_tokens": 95, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 7820}`
- function_call: `send_to_user` call_id=`call_DeNpy06PSu6xYilcld0leAGr`
```json
{
  "text": "החשבונית הופקה בהצלחה ✅\n\nמספר חשבונית: 52567\nלקוח: דמיטרי נוביקסקי\nסכום לפני מעמ: 70 שח\nמעמ: 12.60 שח\nסכום כולל: 82.60 שח\nעבור: ייעוץ\nסטטוס: פתוחה"
}
```

</details>

</details>

<details>
<summary>46. [2026-09-30 15:04:30] APP → USER — context=text</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "החשבונית הופקה בהצלחה ✅\n\nמספר חשבונית: 52567\nלקוח: דמיטרי נוביקסקי\nסכום לפני מעמ: 70 שח\nמעמ: 12.60 שח\nסכום כולל: 82.60 שח\nעבור: ייעוץ\nסטטוס: פתוחה"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

```json
{
  "chat_id": "972500000021@c.us",
  "message": "החשבונית הופקה בהצלחה ✅\n\nמספר חשבונית: 52567\nלקוח: דמיטרי נוביקסקי\nסכום לפני מעמ: 70 שח\nמעמ: 12.60 שח\nסכום כולל: 82.60 שח\nעבור: ייעוץ\nסטטוס: פתוחה"
}
```

</details>

</details>

<details>
<summary>47. [2026-09-30 15:04:30] APP → MODEL — context=recognize_ledger_event</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

**input:**

```json
{"role": "user", "content": "THE CONVERSATION WINDOW (the last 1h, oldest first) - '<message_id> [<role>] <content>':\nd6d1a4a8-2cbf-47b6-9455-0fa41a26ea22 [godfather] תפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לא כולל מע\"מ עבור ייעוץ\n02d71cd5-ecd5-4d09-816d-e5b8b60cceaa [assistant] מטפל בהפקת החשבונית ובודק את פרטי הלקוח.\n9a04cc7c-d6d7-49dd-96ef-bdbf94ec85c9 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: הבקשה היא להפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לפני מעמ עבור ייעוץ. טרם בוצעה בדיקה במערכת.\nTHIS TURN'S PURPOSE: להפעיל את תהליך הפקת חשבונית עבור תשלום שטרם התקבל, לאתר את הלקוח, לאסוף את פרטי החשבונית ולבקש אישור לפני יצירה.\nEXPECTATION: אבדוק את הלקוח ואת הפרטים הנדרשים; אם הכל ברור, אציג אישור מפורט לפני ההפקה.\n42eaa5de-e154-44a0-8035-4f17f11be01a [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך flow_issue_invoice_for_payment_due, שלב איתור הלקוח הושלם. שם הלקוח המדויק במערכת הוא דמיטרי נוביקסקי. הפרטים שנאספו: חשבונית מס חדשה, 70 שח לפני מעמ, עבור ייעוץ; לא נמסר מועד פירעון ולכן לא אגדיר אותו.\nTHIS TURN'S PURPOSE: לבקש אישור מפורט לפני יצירת החשבונית.\nEXPECTATION: ממתין לתשובת כן או לא. אם יאושר, אצור את החשבונית; אם לא, לא אבצע יצירה.\n10ca1394-3266-4cf5-b0f6-850b510991cc [assistant] 📋 לאישור — חשבונית מס:\nלקוח: דמיטרי נוביקסקי\nסכום: 70 שח לפני מעמ\nמעמ: לא כלול\nתאריך החשבונית: 30.09.2026\nמטרה: ייעוץ\nלאישור — כן/לא?\n    (morning MCP call on this message's turn) {\"name\": \"resolve_client_name\", \"error\": null, \"arguments\": \"{\\\"name\\\":\\\"דמיטרי נוביקסקי\\\"}\", \"output\": \"{\\\"status\\\": \\\"resolved\\\", \\\"name\\\": \\\"\\\\u05d3\\\\u05de\\\\u05d9\\\\u05d8\\\\u05e8\\\\u05d9 \\\\u05e0\\\\u05d5\\\\u05d1\\\\u05d9\\\\u05e7\\\\u05e1\\\\u05e7\\\\u05d9\\\"}\"}\n21cbaa81-b69d-442d-b9b1-9055016a86b4 [godfather] כן\ndfc8cd43-b717-469f-8584-0a268e73bb6d [assistant] יוצר עכשיו את החשבונית המאושרת במערכת.\n7a120115-b954-4636-b96d-cca904e46619 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך הפקת חשבונית מס עבור דמיטרי נוביקסקי. המשתמש אישר את הפרטים: 70 שח לפני מעמ עבור ייעוץ.\nTHIS TURN'S PURPOSE: ליצור את החשבונית במערכת לאחר האישור.\nEXPECTATION: אמתין לתוצאת היצירה ואדווח במספר החשבונית או בכשל.\n8f0d3ee3-14ab-4d5a-a91c-a2a5c0547e64 [assistant] החשבונית נוצרה בהצלחה.\n6a727d7b-a34e-487f-9b76-c08e47ca099a [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: החשבונית נוצרה בהצלחה במערכת עבור דמיטרי נוביקסקי. מספר החשבונית: 52567. הסכום הכולל כולל מעמ הוא 82.60 שח, מתוכם 70 שח לפני מעמ ו-12.60 שח מעמ. הסטטוס פתוח.\nTHIS TURN'S PURPOSE: לדווח למשתמש על הצלחת ההפקה ולסיים את התהליך.\nEXPECTATION: אין פעולה נוספת נדרשת.\n33d8c69c-1913-4646-bca6-8be68afda624 [assistant] החשבונית הופקה בהצלחה ✅\n\nמספר חשבונית: 52567\nלקוח: דמיטרי נוביקסקי\nסכום לפני מעמ: 70 שח\nמעמ: 12.60 שח\nסכום כולל: 82.60 שח\nעבור: ייעוץ\nסטטוס: פתוחה\n    (morning MCP call on this message's turn) {\"name\": \"create_invoice\", \"error\": null, \"arguments\": \"{\\\"client_name\\\":\\\"דמיטרי נוביקסקי\\\",\\\"amount\\\":70,\\\"description\\\":\\\"ייעוץ\\\",\\\"due_date\\\":null,\\\"vat_included\\\":false,\\\"name_resolved\\\":true}\", \"output\": \"{\\\"display_number\\\": \\\"52567\\\", \\\"internal_morning_id\\\": \\\"c90d9eb8-1b38-400d-9c3d-3dbf55107f5c\\\", \\\"type\\\": 305, \\\"type_name\\\": \\\"\\\\u05d7\\\\u05e9\\\\u05d1\\\\u05d5\\\\u05e0\\\\u05d9\\\\u05ea \\\\u05de\\\\u05e1\\\", \\\"status\\\": \\\"unpaid\\\", \\\"status_code\\\": 0, \\\"status_label\\\": \\\"\\\\u05de\\\\u05e1\\\\u05de\\\\u05da \\\\u05e4\\\\u05ea\\\\u05d5\\\\u05d7\\\", \\\"client_name\\\": \\\"\\\\u05d3\\\\u05de\\\\u05d9\\\\u05d8\\\\u05e8\\\\u05d9 \\\\u05e0\\\\u05d5\\\\u05d1\\\\u05d9\\\\u05e7\\\\u05e1\\\\u05e7\\\\u05d9\\\", \\\"description\\\": \\\"\\\\u05d9\\\\u05d9\\\\u05e2\\\\u05d5\\\\u05e5\\\", \\\"amount\\\": 82.6, \\\"amount_excl_vat\\\": 70.0, \\\"vat_amount\\\": 12.6, \\\"vat_rate\\\": 0.18, \\\"currency\\\": \\\"ILS\\\", \\\"document_date\\\": \\\"2026-09-30\\\", \\\"due_date\\\": null, \\\"creation_date\\\": \\\"2026-09-30T15:04:21+03:00\\\", \\\"payment\\\": null, \\\"line_items\\\": [{\\\"description\\\": \\\"\\\\u05d9\\\\u05d9\\\\u05e2\\\\u05d5\\\\u05e5\\\", \\\"quantity\\\": 1, \\\"price\\\": 70, \\\"amount\\\": 82.6}], \\\"linked_document\\\": null}\"}\n\nTHE REPLY JUST SENT TO THE OPERATOR THIS ROUND:\nהחשבונית הופקה בהצלחה ✅\n\nמספר חשבונית: 52567\nלקוח: דמיטרי נוביקסקי\nסכום לפני מעמ: 70 שח\nמעמ: 12.60 שח\nסכום כולל: 82.60 שח\nעבור: ייעוץ\nסטטוס: פתוחה\n\nMORNING MCP TOOL CALLS MADE THIS TURN (verbatim, each with its arguments and its real result):\n[\n  {\n    \"name\": \"create_invoice\",\n    \"error\": null,\n    \"arguments\": \"{\\\"client_name\\\":\\\"דמיטרי נוביקסקי\\\",\\\"amount\\\":70,\\\"description\\\":\\\"ייעוץ\\\",\\\"due_date\\\":null,\\\"vat_included\\\":false,\\\"name_resolved\\\":true}\",\n    \"output\": \"{\\\"display_number\\\": \\\"52567\\\", \\\"internal_morning_id\\\": \\\"c90d9eb8-1b38-400d-9c3d-3dbf55107f5c\\\", \\\"type\\\": 305, \\\"type_name\\\": \\\"\\\\u05d7\\\\u05e9\\\\u05d1\\\\u05d5\\\\u05e0\\\\u05d9\\\\u05ea \\\\u05de\\\\u05e1\\\", \\\"status\\\": \\\"unpaid\\\", \\\"status_code\\\": 0, \\\"status_label\\\": \\\"\\\\u05de\\\\u05e1\\\\u05de\\\\u05da \\\\u05e4\\\\u05ea\\\\u05d5\\\\u05d7\\\", \\\"client_name\\\": \\\"\\\\u05d3\\\\u05de\\\\u05d9\\\\u05d8\\\\u05e8\\\\u05d9 \\\\u05e0\\\\u05d5\\\\u05d1\\\\u05d9\\\\u05e7\\\\u05e1\\\\u05e7\\\\u05d9\\\", \\\"description\\\": \\\"\\\\u05d9\\\\u05d9\\\\u05e2\\\\u05d5\\\\u05e5\\\", \\\"amount\\\": 82.6, \\\"amount_excl_vat\\\": 70.0, \\\"vat_amount\\\": 12.6, \\\"vat_rate\\\": 0.18, \\\"currency\\\": \\\"ILS\\\", \\\"document_date\\\": \\\"2026-09-30\\\", \\\"due_date\\\": null, \\\"creation_date\\\": \\\"2026-09-30T15:04:21+03:00\\\", \\\"payment\\\": null, \\\"line_items\\\": [{\\\"description\\\": \\\"\\\\u05d9\\\\u05d9\\\\u05e2\\\\u05d5\\\\u05e5\\\", \\\"quantity\\\": 1, \\\"price\\\": 70, \\\"amount\\\": 82.6}], \\\"linked_document\\\": null}\"\n  }\n]\n\nFollow the recognition prompt above: query the client's ledger history first when the round concerns a client, then call report_ledger_recognition exactly once with the verdict for THIS round."}
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
{"role": "user", "content": "THE CONVERSATION WINDOW (the last 1h, oldest first) - '<message_id> [<role>] <content>':\nd6d1a4a8-2cbf-47b6-9455-0fa41a26ea22 [godfather] תפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לא כולל מע\"מ עבור ייעוץ\n02d71cd5-ecd5-4d09-816d-e5b8b60cceaa [assistant] מטפל בהפקת החשבונית ובודק את פרטי הלקוח.\n9a04cc7c-d6d7-49dd-96ef-bdbf94ec85c9 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: הבקשה היא להפיק חשבונית חדשה עבור דמיטרי נוביקסקי על סך 70 שח לפני מעמ עבור ייעוץ. טרם בוצעה בדיקה במערכת.\nTHIS TURN'S PURPOSE: להפעיל את תהליך הפקת חשבונית עבור תשלום שטרם התקבל, לאתר את הלקוח, לאסוף את פרטי החשבונית ולבקש אישור לפני יצירה.\nEXPECTATION: אבדוק את הלקוח ואת הפרטים הנדרשים; אם הכל ברור, אציג אישור מפורט לפני ההפקה.\n42eaa5de-e154-44a0-8035-4f17f11be01a [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך flow_issue_invoice_for_payment_due, שלב איתור הלקוח הושלם. שם הלקוח המדויק במערכת הוא דמיטרי נוביקסקי. הפרטים שנאספו: חשבונית מס חדשה, 70 שח לפני מעמ, עבור ייעוץ; לא נמסר מועד פירעון ולכן לא אגדיר אותו.\nTHIS TURN'S PURPOSE: לבקש אישור מפורט לפני יצירת החשבונית.\nEXPECTATION: ממתין לתשובת כן או לא. אם יאושר, אצור את החשבונית; אם לא, לא אבצע יצירה.\n10ca1394-3266-4cf5-b0f6-850b510991cc [assistant] 📋 לאישור — חשבונית מס:\nלקוח: דמיטרי נוביקסקי\nסכום: 70 שח לפני מעמ\nמעמ: לא כלול\nתאריך החשבונית: 30.09.2026\nמטרה: ייעוץ\nלאישור — כן/לא?\n    (morning MCP call on this message's turn) {\"name\": \"resolve_client_name\", \"error\": null, \"arguments\": \"{\\\"name\\\":\\\"דמיטרי נוביקסקי\\\"}\", \"output\": \"{\\\"status\\\": \\\"resolved\\\", \\\"name\\\": \\\"\\\\u05d3\\\\u05de\\\\u05d9\\\\u05d8\\\\u05e8\\\\u05d9 \\\\u05e0\\\\u05d5\\\\u05d1\\\\u05d9\\\\u05e7\\\\u05e1\\\\u05e7\\\\u05d9\\\"}\"}\n21cbaa81-b69d-442d-b9b1-9055016a86b4 [godfather] כן\ndfc8cd43-b717-469f-8584-0a268e73bb6d [assistant] יוצר עכשיו את החשבונית המאושרת במערכת.\n7a120115-b954-4636-b96d-cca904e46619 [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: בתהליך הפקת חשבונית מס עבור דמיטרי נוביקסקי. המשתמש אישר את הפרטים: 70 שח לפני מעמ עבור ייעוץ.\nTHIS TURN'S PURPOSE: ליצור את החשבונית במערכת לאחר האישור.\nEXPECTATION: אמתין לתוצאת היצירה ואדווח במספר החשבונית או בכשל.\n8f0d3ee3-14ab-4d5a-a91c-a2a5c0547e64 [assistant] החשבונית נוצרה בהצלחה.\n6a727d7b-a34e-487f-9b76-c08e47ca099a [assistant] [[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: החשבונית נוצרה בהצלחה במערכת עבור דמיטרי נוביקסקי. מספר החשבונית: 52567. הסכום הכולל כולל מעמ הוא 82.60 שח, מתוכם 70 שח לפני מעמ ו-12.60 שח מעמ. הסטטוס פתוח.\nTHIS TURN'S PURPOSE: לדווח למשתמש על הצלחת ההפקה ולסיים את התהליך.\nEXPECTATION: אין פעולה נוספת נדרשת.\n33d8c69c-1913-4646-bca6-8be68afda624 [assistant] החשבונית הופקה בהצלחה ✅\n\nמספר חשבונית: 52567\nלקוח: דמיטרי נוביקסקי\nסכום לפני מעמ: 70 שח\nמעמ: 12.60 שח\nסכום כולל: 82.60 שח\nעבור: ייעוץ\nסטטוס: פתוחה\n    (morning MCP call on this message's turn) {\"name\": \"create_invoice\", \"error\": null, \"arguments\": \"{\\\"client_name\\\":\\\"דמיטרי נוביקסקי\\\",\\\"amount\\\":70,\\\"description\\\":\\\"ייעוץ\\\",\\\"due_date\\\":null,\\\"vat_included\\\":false,\\\"name_resolved\\\":true}\", \"output\": \"{\\\"display_number\\\": \\\"52567\\\", \\\"internal_morning_id\\\": \\\"c90d9eb8-1b38-400d-9c3d-3dbf55107f5c\\\", \\\"type\\\": 305, \\\"type_name\\\": \\\"\\\\u05d7\\\\u05e9\\\\u05d1\\\\u05d5\\\\u05e0\\\\u05d9\\\\u05ea \\\\u05de\\\\u05e1\\\", \\\"status\\\": \\\"unpaid\\\", \\\"status_code\\\": 0, \\\"status_label\\\": \\\"\\\\u05de\\\\u05e1\\\\u05de\\\\u05da \\\\u05e4\\\\u05ea\\\\u05d5\\\\u05d7\\\", \\\"client_name\\\": \\\"\\\\u05d3\\\\u05de\\\\u05d9\\\\u05d8\\\\u05e8\\\\u05d9 \\\\u05e0\\\\u05d5\\\\u05d1\\\\u05d9\\\\u05e7\\\\u05e1\\\\u05e7\\\\u05d9\\\", \\\"description\\\": \\\"\\\\u05d9\\\\u05d9\\\\u05e2\\\\u05d5\\\\u05e5\\\", \\\"amount\\\": 82.6, \\\"amount_excl_vat\\\": 70.0, \\\"vat_amount\\\": 12.6, \\\"vat_rate\\\": 0.18, \\\"currency\\\": \\\"ILS\\\", \\\"document_date\\\": \\\"2026-09-30\\\", \\\"due_date\\\": null, \\\"creation_date\\\": \\\"2026-09-30T15:04:21+03:00\\\", \\\"payment\\\": null, \\\"line_items\\\": [{\\\"description\\\": \\\"\\\\u05d9\\\\u05d9\\\\u05e2\\\\u05d5\\\\u05e5\\\", \\\"quantity\\\": 1, \\\"price\\\": 70, \\\"amount\\\": 82.6}], \\\"linked_document\\\": null}\"}\n\nTHE REPLY JUST SENT TO THE OPERATOR THIS ROUND:\nהחשבונית הופקה בהצלחה ✅\n\nמספר חשבונית: 52567\nלקוח: דמיטרי נוביקסקי\nסכום לפני מעמ: 70 שח\nמעמ: 12.60 שח\nסכום כולל: 82.60 שח\nעבור: ייעוץ\nסטטוס: פתוחה\n\nMORNING MCP TOOL CALLS MADE THIS TURN (verbatim, each with its arguments and its real result):\n[\n  {\n    \"name\": \"create_invoice\",\n    \"error\": null,\n    \"arguments\": \"{\\\"client_name\\\":\\\"דמיטרי נוביקסקי\\\",\\\"amount\\\":70,\\\"description\\\":\\\"ייעוץ\\\",\\\"due_date\\\":null,\\\"vat_included\\\":false,\\\"name_resolved\\\":true}\",\n    \"output\": \"{\\\"display_number\\\": \\\"52567\\\", \\\"internal_morning_id\\\": \\\"c90d9eb8-1b38-400d-9c3d-3dbf55107f5c\\\", \\\"type\\\": 305, \\\"type_name\\\": \\\"\\\\u05d7\\\\u05e9\\\\u05d1\\\\u05d5\\\\u05e0\\\\u05d9\\\\u05ea \\\\u05de\\\\u05e1\\\", \\\"status\\\": \\\"unpaid\\\", \\\"status_code\\\": 0, \\\"status_label\\\": \\\"\\\\u05de\\\\u05e1\\\\u05de\\\\u05da \\\\u05e4\\\\u05ea\\\\u05d5\\\\u05d7\\\", \\\"client_name\\\": \\\"\\\\u05d3\\\\u05de\\\\u05d9\\\\u05d8\\\\u05e8\\\\u05d9 \\\\u05e0\\\\u05d5\\\\u05d1\\\\u05d9\\\\u05e7\\\\u05e1\\\\u05e7\\\\u05d9\\\", \\\"description\\\": \\\"\\\\u05d9\\\\u05d9\\\\u05e2\\\\u05d5\\\\u05e5\\\", \\\"amount\\\": 82.6, \\\"amount_excl_vat\\\": 70.0, \\\"vat_amount\\\": 12.6, \\\"vat_rate\\\": 0.18, \\\"currency\\\": \\\"ILS\\\", \\\"document_date\\\": \\\"2026-09-30\\\", \\\"due_date\\\": null, \\\"creation_date\\\": \\\"2026-09-30T15:04:21+03:00\\\", \\\"payment\\\": null, \\\"line_items\\\": [{\\\"description\\\": \\\"\\\\u05d9\\\\u05d9\\\\u05e2\\\\u05d5\\\\u05e5\\\", \\\"quantity\\\": 1, \\\"price\\\": 70, \\\"amount\\\": 82.6}], \\\"linked_document\\\": null}\"\n  }\n]\n\nFollow the recognition prompt above: query the client's ledger history first when the round concerns a client, then call report_ledger_recognition exactly once with the verdict for THIS round."}
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
<summary>48. [2026-09-30 15:04:32] MODEL → APP — context=recognize_ledger_event</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_04ee4248632e5ac4006abcfaceb44c87d19503a8be9aafddc1`
- status: `completed`
- usage: `{"input_tokens": 10185, "input_tokens_details": {"cache_write_tokens": 2246, "cached_tokens": 7936}, "output_tokens": 122, "output_tokens_details": {"reasoning_tokens": 85}, "total_tokens": 10307}`
- reasoning item (content not user-visible)
- function_call: `query_ledger_events` call_id=`call_bVEGhbCIixG7CrBJGUxJixEr`
```json
{
  "criteria": [
    {
      "text": "דמיטרי נוביקסקי",
      "hint": "identity"
    }
  ]
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_04ee4248632e5ac4006abcfaceb44c87d19503a8be9aafddc1`
- status: `completed`
- usage: `{"input_tokens": 10185, "input_tokens_details": {"cache_write_tokens": 2246, "cached_tokens": 7936}, "output_tokens": 122, "output_tokens_details": {"reasoning_tokens": 85}, "total_tokens": 10307}`
- reasoning item (content not user-visible)
- function_call: `query_ledger_events` call_id=`call_bVEGhbCIixG7CrBJGUxJixEr`
```json
{
  "criteria": [
    {
      "text": "דמיטרי נוביקסקי",
      "hint": "identity"
    }
  ]
}
```

</details>

</details>

<details>
<summary>49. [2026-09-30 15:04:32] APP → MODEL — context=recognize_ledger_event (query round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

**input:**

- app's reply to `query_ledger_events` (call_id=`call_bVEGhbCIixG7CrBJGUxJixEr`):
```text
{
  "matches": [],
  "count": 0
}
```

- tools (2): ['report_ledger_recognition', 'query_ledger_events']

- previous_response_id: `'resp_04ee4248632e5ac4006abcfaceb44c87d19503a8be9aafddc1'`

- max_output_tokens: `20000`

- model: `'gpt-5.6-luna'`

- instructions: ledger recognition prompt

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

**input:**

- app's reply to `query_ledger_events` (call_id=`call_bVEGhbCIixG7CrBJGUxJixEr`):
```text
{
  "matches": [],
  "count": 0
}
```

- tools (2): ['report_ledger_recognition', 'query_ledger_events']

- previous_response_id: `'resp_04ee4248632e5ac4006abcfaceb44c87d19503a8be9aafddc1'`

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
<summary>50. [2026-09-30 15:04:36] MODEL → APP — context=recognize_ledger_event (query round)</summary>

<details>
<summary>↳ Audit (concise, INFO-level - what prod actually logs)</summary>

- response.id: `resp_04ee4248632e5ac4006abcfad0c77487d18515fa7ab7af9844`
- status: `completed`
- usage: `{"input_tokens": 10330, "input_tokens_details": {"cache_write_tokens": 145, "cached_tokens": 10182}, "output_tokens": 412, "output_tokens_details": {"reasoning_tokens": 53}, "total_tokens": 10742}`
- reasoning item (content not user-visible)
- function_call: `report_ledger_recognition` call_id=`call_dIzQrIs0y14URnQR6RJW7n1M`
```json
{
  "verdict": "complete",
  "event": {
    "source_type": "חשבונית",
    "event_subtype": "הפקה",
    "client_name": "דמיטרי נוביקסקי",
    "payer_name": null,
    "agreement_id": null,
    "reference_hint": null,
    "bank_number": null,
    "bank_branch": null,
    "bank_account": null,
    "accounting_document_json": "{\"display_number\": \"52567\", \"internal_morning_id\": \"c90d9eb8-1b38-400d-9c3d-3dbf55107f5c\", \"type\": 305, \"type_name\": \"חשבונית מס\", \"status\": \"unpaid\", \"status_code\": 0, \"status_label\": \"מסמך פתוח\", \"client_name\": \"דמיטרי נוביקסקי\", \"description\": \"ייעוץ\", \"amount\": 82.6, \"amount_excl_vat\": 70.0, \"vat_amount\": 12.6, \"vat_rate\": 0.18, \"currency\": \"ILS\", \"document_date\": \"2026-09-30\", \"due_date\": null, \"creation_date\": \"2026-09-30T15:04:21+03:00\", \"payment\": null, \"line_items\": [{\"description\": \"ייעוץ\", \"quantity\": 1, \"price\": 70, \"amount\": 82.6}], \"linked_document\": null}",
    "component_count": 0,
    "components": []
  },
  "trigger_message_id": "d6d1a4a8-2cbf-47b6-9455-0fa41a26ea22"
}
```

</details>

<details>
<summary>↳ Debug (full, verbatim)</summary>

- response.id: `resp_04ee4248632e5ac4006abcfad0c77487d18515fa7ab7af9844`
- status: `completed`
- usage: `{"input_tokens": 10330, "input_tokens_details": {"cache_write_tokens": 145, "cached_tokens": 10182}, "output_tokens": 412, "output_tokens_details": {"reasoning_tokens": 53}, "total_tokens": 10742}`
- reasoning item (content not user-visible)
- function_call: `report_ledger_recognition` call_id=`call_dIzQrIs0y14URnQR6RJW7n1M`
```json
{
  "verdict": "complete",
  "event": {
    "source_type": "חשבונית",
    "event_subtype": "הפקה",
    "client_name": "דמיטרי נוביקסקי",
    "payer_name": null,
    "agreement_id": null,
    "reference_hint": null,
    "bank_number": null,
    "bank_branch": null,
    "bank_account": null,
    "accounting_document_json": "{\"display_number\": \"52567\", \"internal_morning_id\": \"c90d9eb8-1b38-400d-9c3d-3dbf55107f5c\", \"type\": 305, \"type_name\": \"חשבונית מס\", \"status\": \"unpaid\", \"status_code\": 0, \"status_label\": \"מסמך פתוח\", \"client_name\": \"דמיטרי נוביקסקי\", \"description\": \"ייעוץ\", \"amount\": 82.6, \"amount_excl_vat\": 70.0, \"vat_amount\": 12.6, \"vat_rate\": 0.18, \"currency\": \"ILS\", \"document_date\": \"2026-09-30\", \"due_date\": null, \"creation_date\": \"2026-09-30T15:04:21+03:00\", \"payment\": null, \"line_items\": [{\"description\": \"ייעוץ\", \"quantity\": 1, \"price\": 70, \"amount\": 82.6}], \"linked_document\": null}",
    "component_count": 0,
    "components": []
  },
  "trigger_message_id": "d6d1a4a8-2cbf-47b6-9455-0fa41a26ea22"
}
```

</details>

</details>

