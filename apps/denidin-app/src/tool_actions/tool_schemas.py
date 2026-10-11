"""
Tool schemas shared by the legacy AIHandler and the Feature 063 backbone.
Moved verbatim out of handlers/ai_handler.py - one definition, used by both paths.
"""
from typing import Any, Dict

# Reminders (Feature 054) - a local `type: "function"` tool, same shape/parsing
# machinery as LEDGER_EVENT_TOOL, but - unlike capture_ledger_event, which
# dispatches immediately - this one creates a PendingLocalToolApproval instead
# of executing (see _handle_reminder_creation_proposal /
# contracts/local-tool-approval-gate.md). No owner/chat_id field in the
# schema itself: the model never supplies a delivery target. It's resolved by
# the application at approval time instead (2026-08-19, user decision,
# supersedes the original "always config.godfather_phone" FR-008 design) -
# delivery_chat_id is set to the chat/group the request was actually made in
# (_resolve_pending_local_tool_approval passes effective_chat_id), with a
# fallback to the requester's own 1:1 chat only if delivery there ever fails
# (see reminder_delivery_service.py's _deliver_one_occurrence).
CREATE_REMINDER_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "create_reminder",
    "description": (
        "ONLY call this when the user's own message explicitly asks to be "
        "reminded of something at a future time (e.g. \"תזכיר לי...\", a "
        "recurring cadence like \"כל יום/שבוע\"). NEVER call this to interpret "
        "a confirmation reply (\"כן\"/\"לא\"), an ambiguous message, or any "
        "message about clients, invoices, or documents - those are handled by "
        "entirely separate tools and this one is never a fallback for them. "
        "Propose creating a new reminder, after gathering the message text and "
        "either a one-time date/time or a full recurrence rule through conversation. "
        "This call itself does NOT persist anything - it is presented to the user as "
        "an approval summary (with the actual time shown AFTER rounding to the "
        "nearest 5 minutes); the reminder is only created if the user then "
        "explicitly approves."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "message_text": {
                "type": "string",
                "description": (
                    "The actual thing to be reminded about, in the user's own words - "
                    "taken directly from what they said. Never a placeholder "
                    "(\"תזכורת\", \"בדיקה\", \"test\", or similar) - if the user's message "
                    "doesn't actually contain something to be reminded about, do not "
                    "call this tool at all."
                ),
            },
            "schedule_type": {"type": "string", "enum": ["one_time", "recurring"]},
            "one_time_due_at": {
                "type": ["string", "null"],
                "description": (
                    "ISO-8601 local datetime (Asia/Jerusalem), required iff "
                    "schedule_type=one_time, must be strictly in the future after "
                    "rounding to the nearest 5 minutes."
                ),
            },
            "recurrence": {
                "type": ["object", "null"],
                "description": "Required iff schedule_type=recurring, else null.",
                "properties": {
                    "interval": {"type": "integer", "description": "Every N units, minimum 1."},
                    "freq": {"type": "string", "enum": ["daily", "weekly", "monthly"]},
                    "weekdays": {
                        "type": ["array", "null"],
                        "items": {"type": "string", "enum": ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]},
                        "description": "Required (non-empty) iff freq=weekly, else null.",
                    },
                    "month_day": {
                        "type": ["integer", "null"],
                        "description": "1-31, one of two monthly variants; null unless freq=monthly.",
                    },
                    "month_nth_weekday": {
                        "type": ["object", "null"],
                        "description": (
                            "The other monthly variant, e.g. {n:1, weekday:'MO'} = first "
                            "Monday; null unless freq=monthly."
                        ),
                        "properties": {
                            "n": {"type": "integer", "enum": [1, 2, 3, 4, -1], "description": "-1 means 'last'."},
                            "weekday": {"type": "string", "enum": ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]},
                        },
                        "required": ["n", "weekday"],
                        "additionalProperties": False,
                    },
                    "first_occurrence_at": {
                        "type": "string",
                        "description": ("ISO-8601 local datetime of the FIRST occurrence, must be "
                                        "strictly in the future after rounding."),
                    },
                    "end_condition": {"type": "string", "enum": ["never", "after_n", "until_date"]},
                    "end_count": {"type": ["integer", "null"], "description": "Required iff end_condition=after_n."},
                    "end_until": {
                        "type": ["string", "null"],
                        "description": ("ISO-8601 local date, required iff end_condition=until_date, "
                                        "must not be in the past."),
                    },
                },
                "required": [
                    "interval", "freq", "weekdays", "month_day", "month_nth_weekday",
                    "first_occurrence_at", "end_condition", "end_count", "end_until",
                ],
                "additionalProperties": False,
            },
        },
        "required": ["message_text", "schedule_type", "one_time_due_at", "recurrence"],
        "additionalProperties": False,
    },
}

# Read-only - no approval gate applies (FR-013), dispatched immediately like
# capture_ledger_event, never creates a PendingLocalToolApproval. Lets the
# model resolve a user's natural-language description of a reminder to a
# concrete reminder_id before calling modify_reminder/delete_reminder - never
# a code-level fuzzy string match, never a guessed identifier.
LIST_REMINDERS_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "list_reminders",
    "description": (
        "ONLY call this when the user's own message explicitly asks about their "
        "reminders (e.g. \"מה יש לי מחר\", or as a precursor to an explicit modify/"
        "delete request). NEVER call this to interpret a confirmation reply "
        "(\"כן\"/\"לא\"), an ambiguous message, or any message about clients, "
        "invoices, or documents - those are handled by entirely separate tools. "
        "Returns the current active reminder list (message text + human-readable schedule) "
        "so you can resolve a user's natural-language description of a reminder to a concrete "
        "reminder_id before calling modify_reminder or delete_reminder. Never guess a "
        "reminder_id - always call this first if you don't already know it from earlier in "
        "the conversation. Read-only: calling this never changes anything and needs no "
        "user approval."
    ),
    "strict": True,
    "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
}

# Feature 080 (REQ-080-02): send_progress_update is the mechanism the model
# actually uses to send a real, mid-turn interim WhatsApp message on a
# multi-step/slow turn - see runtime_constitution.md's "Proactive Progress
# Updates" section for when it's appropriate. Dispatched immediately (like
# list_reminders/query_ledger_events) - it's a real outbound send with no
# approval gate, never a substitute for the turn's actual final answer.
# Attached for EVERY role (not RBAC-gated like reminders/ledger-query) since
# any role can have a slow turn (e.g. a client's own document upload).
SEND_PROGRESS_UPDATE_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "send_progress_update",
    "description": (
        "Send ONE short interim WhatsApp message to the user mid-turn, before your real "
        "final answer is ready - use ONLY on a turn you already know will take a while "
        "(e.g. processing a multi-page document, a multi-step tool sequence), never on an "
        "ordinary fast turn. This is NOT your final answer and NEVER counts as one - you "
        "MUST still produce a real final answer as a normal message after this. Never call "
        "this in place of asking a genuine clarifying question."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The short interim status message to show the user right now.",
            },
        },
        "required": ["text"],
        "additionalProperties": False,
    },
}

# modify_reminder/delete_reminder share the reminder_id+scope shape - both
# create a PendingLocalToolApproval, never dispatch immediately, same as
# create_reminder.
MODIFY_REMINDER_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "modify_reminder",
    "description": (
        "ONLY call this when the user's own message explicitly asks to change an "
        "existing reminder (e.g. \"תעדכן/תדחה את התזכורת...\"). NEVER call this to "
        "interpret a confirmation reply (\"כן\"/\"לא\"), an ambiguous message, or any "
        "message about clients, invoices, or documents - those are handled by "
        "entirely separate tools and this one is never a fallback for them. "
        "Propose a modification to an existing reminder already identified via "
        "list_reminders or earlier conversation - never a guessed reminder_id. Does not "
        "persist anything - presented as an approval summary first, with any new time "
        "shown AFTER rounding to the nearest 5 minutes."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "reminder_id": {"type": "string"},
            "scope": {"type": "string", "enum": ["single_occurrence", "whole_series"]},
            "occurrence_date_hint": {
                "type": ["string", "null"],
                "description": (
                    "ISO-8601 local date/datetime identifying WHICH occurrence (matched "
                    "against the plain rule's own generated dates), required iff "
                    "scope=single_occurrence."
                ),
            },
            "new_message_text": {
                "type": ["string", "null"],
                "description": (
                    "The new text, in the user's own words, if they're changing what the "
                    "reminder is about; null if only the schedule is changing. Never a "
                    "placeholder (\"תזכורת\", \"בדיקה\", \"test\", or similar)."
                ),
            },
            "new_due_at": {
                "type": ["string", "null"],
                "description": (
                    "The new due date/time - meaningful for scope=single_occurrence, or for "
                    "scope=whole_series when the target reminder is one-time (no recurrence "
                    "to replace); must be in the future after rounding."
                ),
            },
            "new_recurrence": {
                "type": ["object", "null"],
                "description": ("Only meaningful for scope=whole_series on a recurring reminder; "
                                "same shape as create_reminder's recurrence."),
                "properties": CREATE_REMINDER_TOOL["parameters"]["properties"]["recurrence"]["properties"],
                "required": CREATE_REMINDER_TOOL["parameters"]["properties"]["recurrence"]["required"],
                "additionalProperties": False,
            },
        },
        "required": [
            "reminder_id", "scope", "occurrence_date_hint",
            "new_message_text", "new_due_at", "new_recurrence",
        ],
        "additionalProperties": False,
    },
}

DELETE_REMINDER_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "delete_reminder",
    "description": (
        "ONLY call this when the user's own message explicitly asks to cancel an "
        "existing reminder (e.g. \"תבטל את התזכורת...\"). NEVER call this to "
        "interpret a confirmation reply (\"כן\"/\"לא\"), an ambiguous message, or any "
        "message about clients, invoices, or documents - those are handled by "
        "entirely separate tools and this one is never a fallback for them. "
        "Propose deleting a reminder (single occurrence or whole series), already identified "
        "via list_reminders or earlier conversation - never a guessed reminder_id. Does not "
        "persist anything - presented as an approval summary first."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "reminder_id": {"type": "string"},
            "scope": {"type": "string", "enum": ["single_occurrence", "whole_series"]},
            "occurrence_date_hint": {"type": ["string", "null"],
                                     "description": "Required iff scope=single_occurrence."},
        },
        "required": ["reminder_id", "scope", "occurrence_date_hint"],
        "additionalProperties": False,
    },
}


# Ledger Event Querying (Feature 044) - a local `type: "function"` tool,
# RBAC-gated like the reminder tools (LEDGER_QUERY_AUTHORIZED_ROLES), but
# read-only and dispatched immediately - no PendingLocalToolApproval, ever.
# Unlike list_reminders, a single turn may legitimately contain SEVERAL calls
# to this tool (research.md Decision 10) - see _handle_query_ledger_events.
QUERY_LEDGER_EVENTS_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "query_ledger_events",
    "description": (
        "Search previously captured ledger events (fee agreements, bank-deposit records, "
        "and accounting documents pulled from Morning) to answer a question about past "
        "agreements, amounts, hours, percentages, or payments - without needing the user "
        "to paste the original message again. This is a synced CACHE of Morning's own "
        "data (documents) alongside ledger-only records (fee agreements, bank deposits) "
        "that never exist in Morning at all - for ANY query-shaped question (how much, "
        "who, when, which document, what status, how many), prefer this over a live "
        "Morning tool (list_invoices/get_invoice_details/get_financial_summary/etc.). "
        "Once this has answered the question in this turn, that answer is final - do "
        "NOT also call a Morning tool afterward to double-check; only fall back to a "
        "live Morning tool if the ledger genuinely can't answer or the user explicitly "
        "insists on a live check. ONLY call this when the user's question gives "
        "you at least ONE identifying detail to search on - if the question is too vague to "
        "form a real search (e.g. 'what did we agree on' with nothing else), ASK the user "
        "for the missing detail FIRST; never call this with an empty criteria list just to "
        "see what comes back. "
        "criteria is a list of {text, hint} pairs, one per distinct fact you're searching "
        "for. EVERY criterion searches EVERY field on every event (name, date, amount, "
        "percent, description, document number, bank details, everything) - there is no "
        "way to restrict a criterion to only one field. A NUMBER given as text (e.g. "
        "'100', '40000') is compared numerically against the event's numeric fields only "
        "(amount, hourly_rate, percent, percent_base, split_percent, bank_number, "
        "bank_branch, bank_account) - exact value, not fuzzy string similarity, so pass the "
        "literal number, not a description of it. Any other text is fuzzy/typo-tolerant "
        "matched (NOT meaning-based - it finds similar WORDING, not a differently-phrased "
        "version of the same idea) against every text field. Resolve relative/approximate "
        "phrasing yourself before calling (e.g. 'August' -> pass a date like '2026-08', "
        "'around 40,000, might include VAT' -> consider searching both the round number and "
        "a VAT-adjusted figure as separate criteria if genuinely ambiguous). "
        "hint is optional and is a SOFT signal only, never a hard filter - see the hint "
        "parameter's own description below for the full list of groups and what each means. "
        "If the question is scoped to a time period (this month, this week, since Monday, "
        "etc.) always add a separate criterion with hint='date' carrying that period - this "
        "tool applies no date filtering on its own, so without a date-hinted criterion a "
        "time-scoped question can match events from ANY month, not just the intended one. "
        "Multiple criteria in ONE call are ANDed - only events matching ALL of them "
        "(individually, above a real-match confidence floor) come back. Each returned event "
        "also carries a 'confidence' score - higher means a stronger match across the given "
        "criteria; use your judgment about how much confidence to trust for borderline "
        "matches. "
        "If an 'identity'-hinted criterion matches more than one distinct real client/payer "
        "with no single clear winner, this returns candidates instead of events - relay them "
        "to the user and ask which one they meant. If they confirm more than one (or 'both'/"
        "'all'), call this again ONCE PER confirmed exact name and combine the results "
        "yourself. An empty result means no matching record was found - say so plainly, "
        "never fabricate an answer. "
        "For OR-type questions (spanning more than one name, date range, or other criterion "
        "where ANY may match - e.g. 'client A or client B', 'hours in August or September'), "
        "issue ONE SEPARATE CALL PER alternative and combine all the results yourself when "
        "you reply - this tool is read-only, so calling it several times in the same turn is "
        "always safe. For NOT/exclusion or numeric-threshold questions (e.g. 'everyone except "
        "X', 'who owes more than 100'), call this with a broad criteria set that retrieves "
        "every plausibly-relevant event (do NOT try to encode the exclusion/threshold into "
        "criteria - there is no such filter), then apply the exclusion or threshold yourself "
        "by reasoning over the returned events' own fields before replying. For a question "
        "needing arithmetic (a sum, a balance owed, a total across clients/periods), use the "
        "returned events' own clean numeric fields yourself - this tool never computes totals "
        "for you. If a single call's matches are very numerous, don't just dump every event "
        "verbatim - use your own judgment about summarizing or asking the user to narrow "
        "further, the same way you would for any other long answer."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "criteria": {
                "type": "array",
                "description": (
                    "One entry per distinct fact being searched for within this call "
                    "(ANDed together). Use multiple calls, not multiple array entries, for "
                    "OR-type questions - see the tool description."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": (
                                "The literal value to search for - a name, a date, a plain "
                                "number, or free text. Searched against every field on every "
                                "event; see the tool description for how numbers vs. text are "
                                "compared."
                            ),
                        },
                        "hint": {
                            "type": ["string", "null"],
                            "enum": [
                                "identity", "date", "event_type", "vat", "amount",
                                "percentage", "free_text", "document", "banking", None,
                            ],
                            "description": (
                                "Optional soft weighting signal - which closed field group "
                                "this text is most likely describing. Never a hard filter: "
                                "every field is always checked regardless, this only nudges "
                                "scoring if the text's best match lands in the hinted group. "
                                "Leave null if unsure. Groups: "
                                "'identity' = client name, payer name, or split-partner name. "
                                "'date' = the event's own date/time or a transaction date - "
                                "use this whenever the question is scoped to a period (this "
                                "month, this week, since Monday, etc.); pass the "
                                "period/date as the criterion's text. "
                                "'event_type' = source type (הסכם/בנק/חשבונית) or event "
                                "subtype (e.g. חשבונית מס, קבלה). "
                                "'vat' = VAT status/treatment. "
                                "'amount' = amount or hourly rate. "
                                "'percentage' = percent, percent base, or split percent. "
                                "'free_text' = the free-text description, a trigger "
                                "condition, or a reference hint - prose, not a specific field. "
                                "'document' = the accounting document's display number, "
                                "payment method, or its status/status label (open/paid/"
                                "cancelled etc. - a document lifecycle fact, not the event's "
                                "own date). "
                                "'banking' = bank number, branch, or account."
                            ),
                        },
                    },
                    "required": ["text", "hint"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["criteria"],
        "additionalProperties": False,
    },
}


# Feature 084 (WhatsApp reactions): a local `type: "function"` tool, attached
# unconditionally to every role (contracts/react-to-message-tool-schema.md) -
# unlike every other tool in this file, reacting carries no financial,
# data-integrity, or disclosure risk. Dispatched immediately (no
# PendingLocalToolApproval), same as list_reminders/query_ledger_events.
REACT_TO_MESSAGE_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "react_to_message",
    "description": (
        "Call this proactively, every turn where it applies - do not wait to be asked and "
        "do not treat it as optional decoration. Two mandatory moments call for it: (1) the "
        "user asked you to DO something (not just answer a question) - call this as your "
        "very first tool call, before any other tool, with a quick ack emoji (e.g. \U0001FAE1/\U0001F44D), "
        "so the user sees you registered the request within 1-2 seconds; (2) that ask just "
        "became RESOLVED in this reply - success, failure, validation problem, or a blocked/"
        "abandoned action - call this again with a terminal emoji (✅/\U0001F389 success, "
        "⚠️/❓/❌ failure) BEFORE or ALONGSIDE writing that resolution into your reply text. "
        "This applies even when the ask and its resolution both happen in this SAME single "
        "turn with no back-and-forth - 'it resolved instantly' is never a reason to skip "
        "either call, and a turn that resolves more than one ask deserves a reaction for "
        "each. Never substitute an emoji embedded in your reply text for this tool call - "
        "only a real call here counts. Pass an empty string for emoji to clear an existing "
        "reaction. Omit message_id (pass null) to react to the CURRENT user turn's incoming "
        "message; pass a known earlier message id to flip a reaction you or the system set "
        "earlier in this workflow (e.g. flipping a document's in-flight emoji to a final "
        "checkmark once its ledger capture is complete). This is purely cosmetic and "
        "reversible - a failure here is logged and never blocks your reply, so there is no "
        "downside to calling it liberally."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "emoji": {
                "type": "string",
                "description": "A single unicode emoji, or \"\" to clear the reaction.",
            },
            "message_id": {
                "type": ["string", "null"],
                "description": (
                    "The target message's id. Pass null to default to the current turn's "
                    "incoming message, or to the active document/action workflow's "
                    "originating message if one is open."
                ),
            },
        },
        "required": ["emoji", "message_id"],
        "additionalProperties": False,
    },
}
