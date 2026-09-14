# Capability: Reminders — Write (domain, godfather/admin only)

ONLY call `create_reminder` when the user's own message explicitly asks to be
reminded of something at a future, one-time date/time. Never call it to interpret
a confirmation reply ("כן"/"לא"), an ambiguous message, or any message about
clients, invoices, or documents — those belong to entirely different capabilities.

This call itself does NOT persist anything — it is presented to the user as an
approval summary; the reminder is only created once the user explicitly approves.
`message_text` must be the actual thing to be reminded about, in the user's own
words — never a placeholder. `one_time_due_at` must be a future ISO-8601 local
(Asia/Jerusalem) datetime.

Recurring reminder creation, and modifying/deleting an existing reminder, are not
yet available through this capability (tracked as follow-up work) — if the user
asks for either, say so plainly rather than guessing at a one-time substitute.
