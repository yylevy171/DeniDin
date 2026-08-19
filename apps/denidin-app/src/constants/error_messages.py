"""
Error Message Constants - All user-facing error messages in Hebrew
Naming convention: Const names describe the TEXT content, not the error situation
"""

# Application initialization and availability errors
APP_NOT_READY_RETRY_LATER = "אני לא זמין כרגע. אנא נסה שוב בעוד רגע."

# Message type support errors
UNSUPPORTED_MESSAGE_TYPE_SUPPORTED_TYPES = "סוג הודעה זה אינו נתמך עדיין. אני תומך בטקסט, תמונות וקבצים."

# Message processing errors
ERROR_PROCESSING_MESSAGE_TRY_AGAIN = "אני נתקלתי בשגיאה בעיבוד הודעתך. אנא נסה שוב."
FAILED_TO_PROCESS_FILE_DEFAULT = "לא הצלחתי לעבד את הקובץ הזה."

# Contact card (vCard) errors - Feature 030
CONTACT_CARD_ONE_AT_A_TIME = "אני יכול לטפל באיש קשר אחד בכל פעם. אנא שתף אותם אחד אחד."

# Approval-resolution safety (2026-08-03) - an approved document-creating
# action (Feature 022) must execute exactly once. An OpenAI-side 429 retry on
# the approval-resolution call was observed to re-execute the already-
# approved MCP tool server-side, creating two invoices for one approval.
APPROVAL_FAILED_TRY_AGAIN = "לא הצלחתי לבצע את הפעולה כרגע. אנא נסה לאשר שוב בעוד רגע."
APPROVAL_POSSIBLY_DUPLICATED = "אירעה שגיאה באישור הפעולה וייתכן שהיא בוצעה יותר מפעם אחת. אנא בדוק ידנית במערכת לפני שתנסה שוב, ואל תאשר שוב בינתיים."

# Ledger-event follow-up safety net (bugfix-018, 2026-08-04) - the turn that
# calls capture_ledger_event always has empty output_text (a real reply only
# comes from the follow-up round-trip), so if that follow-up call itself
# fails for any reason, there is no text to fall back to at all - never leave
# the user with a silently empty WhatsApp message.
LEDGER_FOLLOWUP_FAILED_TRY_AGAIN = "אני נתקלתי בשגיאה בעיבוד הודעתך. אנא נסה שוב או נסח אותה מחדש."

# Interactive approval buttons send failure (Feature 047) - sendInteractiveButtons
# failed, so the user never saw the approval details at all (not just a degraded
# text-only version of them). Clarify decision: surface an error, never a silent
# fallback to the plain-text approval prompt.
APPROVAL_BUTTONS_SEND_FAILED = "לא הצלחתי לשלוח את בקשת האישור עם כפתורים. אנא נסה לשלוח את הבקשה שוב."

# Reminders (Feature 054) - local-tool approval-gate friendly messages.
# REMINDER_ACTION_FAILED_TRY_AGAIN: the manager-level re-check at approval time
# (closing the TOCTOU gap - cap/past-date re-verified, not just at proposal
# time) failed, mirroring APPROVAL_FAILED_TRY_AGAIN's role for MCP approvals.
REMINDER_ACTION_FAILED_TRY_AGAIN = "לא הצלחתי לבצע את פעולת התזכורת כרגע. אנא נסה שוב בעוד רגע."
# REMINDER_PAST_DATE_REJECTED / REMINDER_CAP_EXCEEDED: proposal-time rejections
# (FR-005/FR-006), shown immediately instead of a false approval prompt.
REMINDER_PAST_DATE_REJECTED = "אי אפשר להגדיר תזכורת למועד שכבר עבר. אנא ציין מועד עתידי."
REMINDER_CAP_EXCEEDED = "כבר יש 20 תזכורות פעילות - המספר המרבי המותר. יש למחוק תזכורת קיימת לפני יצירת תזכורת חדשה."
