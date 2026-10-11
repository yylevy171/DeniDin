# Integration Contracts: Group RBAC Resolution

**Feature**: 039-group-conversation-support · Per METHODOLOGY.md §VII format.

---

### `denidin.py` ↔ `GroupMembershipResolver` (new component) Contract

**`denidin.py` (`_process_conversational_message`) MUST**:
- Call this resolution step only when `message.is_group` is `True` — 1:1 turns are unaffected
  and MUST continue resolving RBAC from `message.sender_id` alone (US2 regression guard).
- Pass the group's `chat_id` (from `message.chat_id`).
- Use the returned `resolved_phone` as the `user_phone=` argument to both
  `AIHandler.create_request` and `AIHandler.get_response` for this turn — never pass
  `resolved_role` directly to `AIHandler` (it only accepts phone numbers, from which it
  resolves its own `User`/`Role`, per its existing `UserManager.get_user` contract).
- Continue passing `sender=message.sender_id` to `AIHandler.get_response` unchanged — the
  resolved (most-permissive) phone governs turn limits/tools; the real sender's own identity
  still flows through for message persistence (US3).
- Tolerate resolution failure gracefully: if `GroupMembershipResolver` cannot resolve (Green
  API error, empty/unreachable group data), fall back to `message.sender_id` as if it were a
  1:1 turn — never block or drop the message because group-membership lookup failed.

**`GroupMembershipResolver` PROVIDES**:
- `resolve(chat_id: str) -> Optional[GroupResolution]` (or equivalent — exact method signature
  is a `speckit.tasks` decision) — on success, returns the most-permissive member's phone
  number and resolved `Role`, per data-model.md's "Group Membership Resolution" entity. Returns
  `None` on any failure (network, malformed response, empty participant list) — never raises,
  so callers can uniformly fall back per the contract above.
- Internally calls `bot.api.groups.getGroupData(groupId)` (Green API, injected — not a new
  global — per research.md §1/§3) and `UserManager.get_user(phone).role` for each participant,
  applying `UserManager`'s existing ADMIN > GODFATHER > CLIENT > BLOCKED precedence unchanged.
- Caches per `chat_id` in-process (exact TTL/invalidation: `speckit.tasks` decision) — MUST NOT
  make a live Green API call on every single group turn.

**`GroupMembershipResolver` EXPECTS**:
- `chat_id` is a real group chat id (`...@g.us`) — caller's responsibility to only invoke this
  for `message.is_group` turns (this component does not itself re-validate that).
- `UserManager` is available and behaves per its existing contract (`get_user(phone) -> User`,
  never raises for an unrecognized phone — falls back to CLIENT role, per current behavior).

---

### `denidin.py` ↔ `AIHandler` Contract (extension of existing contract)

**`denidin.py` MUST**:
- For group turns, supply `user_phone=resolved_phone` explicitly to `create_request`/
  `get_response`, overriding their existing default (`user_phone or sender`/`message.sender_id`)
  — this is additive use of an existing parameter, not a new one; `AIHandler`'s own code is
  unchanged (research.md §3).
- For 1:1 turns, continue omitting `user_phone` (or passing `None`) exactly as today, so
  `AIHandler` falls back to resolving from `sender` — no behavior change for 1:1.

**`AIHandler` PROVIDES** (unchanged): `create_request(message, user_phone=...)` /
`get_response(request, sender=..., user_phone=...)` already resolve `User`/`max_tokens`/tool
attachment from whichever phone `user_phone` (or its `sender` fallback) names — this contract
was already implicit in the existing signature; Feature 039 is the first caller to actually
exercise the override path.

**`AIHandler` EXPECTS** (unchanged): `user_phone`, when provided, is a valid phone/JID string
resolvable by `UserManager.get_user` — same expectation as today's `sender`-based default.
