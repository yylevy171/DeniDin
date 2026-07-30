# Feature Spec: Client Creation via Shared Contact Card (vCard/.vcf)

**Feature ID**: 030-vcf-contact-card-client-creation
**Priority**: P2
**Status**: Draft
**Created**: July 30, 2026

---

## Problem Statement

Godfather/admin users manage Morning clients today only by describing them in
natural language to the model, which then calls the `add_client` MCP tool
(`name`/`email`/`phone`/`tax_id`/`address`, see
`apps/morning-mcp-app/src/denidin_mcp_morning/server.py:278-286`). WhatsApp
lets a user share a device contact directly as a **contact card message**
(vCard/.vcf) instead of typing the details — Green API surfaces this as its
own notification `typeMessage` (not one of the four media types DeniDin
currently handles). `denidin.py` registers routers only for `textMessage`/
`extendedTextMessage`, `imageMessage`, `documentMessage`, `videoMessage`,
`audioMessage`, plus a catch-all (`denidin.py:292-450`) — a shared contact
card today falls through to the catch-all, which does not extract or act on
it. There is no vCard parsing anywhere in the codebase currently
(`grep -ri vcf/vcard/contact.*card` across `apps/denidin-app/src` returns
nothing).

**Goal**: let a godfather/admin share a WhatsApp contact card and have DeniDin
offer to create (or route to) an `add_client` call using the card's
name/phone (and email if present), instead of requiring the details to be
typed out by hand.

## Open Questions (not yet clarified)

- **What does Green API's webhook actually send for a shared contact?**
  Needs live/sandbox investigation — likely a `contactMessage`
  (`typeMessage: "contactMessage"`) notification with vCard-formatted text
  (`displayName`, `vcard` fields per Green API's docs) rather than a
  downloadable file the way `documentMessage` works. Confirm the exact
  notification shape before deciding whether this reuses
  `MediaHandler`'s extractor pipeline (`handlers/media_handler.py` +
  `handlers/extractors/`) or needs its own lightweight parser (no file
  download involved, just inline vCard text — likely closer to the
  `textMessage` router than the media one).
- **RBAC scope.** Should mirror the existing Morning-tool gating (godfather/
  admin only, per `AIHandler`'s remote-tool attachment) — a client (non-
  godfather) sharing a contact card should presumably get the same "no
  Morning access" friendly response as any other Morning-related ask, not a
  silent no-op or an error.
- **Multi-contact cards.** WhatsApp allows sharing multiple contacts in one
  message; decide whether v1 handles only single-contact cards and gives a
  friendly "one at a time" message for multi-contact shares, or handles the
  full list.
- **Confirmation flow.** Should DeniDin auto-create the client from the vCard
  immediately, or (more consistent with how conversational `add_client` calls
  already work — the model proposes, then calls the tool as part of a natural
  reply) surface the parsed name/phone/email back to the godfather for
  confirmation before calling `add_client`? Needs a decision, ideally
  consistent with whatever confirmation pattern (if any) existing
  conversational client-creation already uses.
- **Missing/malformed vCard fields.** A shared contact card may have no email,
  multiple phone numbers, or no name — needs friendly fallback behavior
  (matching the project's user-facing-error style) rather than a raw
  `add_client` validation failure surfaced to the user.

## References

- `apps/denidin-app/denidin.py:292-450` — existing `@bot.router.message(type_message=...)` registrations and catch-all; a new `contactMessage` (name TBD after confirming Green API's actual type) router would be added here.
- `apps/denidin-app/src/handlers/whatsapp_handler.py`, `handlers/media_handler.py` — existing message-type validation/dispatch pattern to follow for consistency.
- `apps/morning-mcp-app/src/denidin_mcp_morning/server.py:278-286` (`add_client` tool) and `tools.py`'s `add_client` implementation — the eventual call target.
- CLAUDE.md's "Morning MCP integration" section — RBAC-gating precedent (godfather/admin only) this feature should follow.
