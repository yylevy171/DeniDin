# User Stories — Feature 076

## US1 — A user corrects an earlier message (`editedMessage`)

**As** a user (godfather/admin or client) who mistyped something,
**I want** DeniDin to quietly register that I fixed an earlier message,
**so that** its next reply reflects the corrected text and it doesn't spam me with "not
supported".

- **Given** I sent "כמיר כף … 3,000₪" and DeniDin replied,
  **When** I edit that message to "עמיר כץ … 3,000₪",
  **Then** DeniDin sends **no reply**,
  **And** a note `[הודעה קודמת נערכה] עמיר כץ … 3,000₪` is appended to this chat's session,
  dated to the edit's own timestamp.
- **Given** the edit note is in the session,
  **When** I next write "אז מה סיכמנו?",
  **Then** DeniDin's reply uses "עמיר כץ", not "כמיר כף" (both the original and the correction
  are in the 14-day verbatim window; the model reconciles them).
- **Given** I edit a message in a chat DeniDin has never seen before,
  **Then** the session is created and the note is appended; still no reply.
- **Given** Green API redelivers the same `editedMessage` webhook,
  **Then** the note is appended exactly once.

## US2 — A user retracts an earlier message (`deletedMessage`)

**As** a user who sent something by mistake,
**I want** DeniDin to register that I deleted it,
**so that** it doesn't keep treating the retracted content as current.

- **Given** I "delete for everyone" an earlier message,
  **When** the `deletedMessage` webhook arrives,
  **Then** DeniDin sends **no reply**,
  **And** a note `[המשתמש מחק הודעה קודמת]` is appended to the session, dated to the deletion's
  timestamp,
  **And** the deleted message's `stanzaId` appears in the app log.
- **Given** the delete note is in the session,
  **Then** DeniDin never resolves or mutates the original message, and never touches any
  captured ledger event (that is Feature 040).

## US3 — A user sends a type DeniDin can't act on but should acknowledge (`audioMessage`, poll, template, list)

**As** a user who sent a voice note / poll / template / list message,
**I want** a clear, short "not supported" reply,
**so that** I know DeniDin saw it and won't be acting on it.

- **Given** I send a voice note,
  **Then** DeniDin replies with exactly `סוג הודעה לא נתמך` — not a "failed to process the
  file" message, not a longer sentence.
- **Given** I send a poll, a template message, or a list message,
  **Then** same single `סוג הודעה לא נתמך` reply, no AI call, nothing written to the session.

## US4 — A user does something trivial (`reactionMessage`, sticker, location, poll vote, pin, …)

**As** a user who reacted with 👍 / sent a sticker / shared a location,
**I want** DeniDin to stay quiet,
**so that** the conversation isn't cluttered with "not supported" noise.

- **Given** I react to DeniDin's message with 👍,
  **Then** DeniDin sends **nothing**.
- **Given** I send a sticker, a location, cast a poll vote, or pin a message,
  **Then** DeniDin sends **nothing**; the raw webhook is still in the inbound audit log.
- **Given** Green API introduces a brand-new `typeMessage` value DeniDin has never seen,
  **Then** DeniDin sends **nothing** (silent is the new default), and the webhook is still
  audit-logged.

## Acceptance (no billed/expensive — nothing here calls OpenAI)

Unit + integration only. Integration tests dispatching a real Green API webhook JSON through
`dispatch_notification` are **mandatory for `editedMessage` and `deletedMessage`** (US1, US2),
and cover the error-reply (US3) and silent (US4) buckets as well.
