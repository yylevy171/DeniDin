"""GroupMembershipResolver for Feature 039's most-permissive-role group RBAC.

Resolves, for a WhatsApp group chat_id, which member's phone/Role should govern
a group turn's RBAC (token limit / tool attachment) - the most-permissive role
present among the group's real members, not the individual sender alone (see
research.md SS1/SS2, contracts/group-rbac-resolution.md).

In-memory cache only, same failure-recovery profile as SessionManager.chat_to_session
(research.md SS1: a restart simply re-fetches on next use) - never persisted to disk,
since group membership is Green API's own source of truth, not something to keep in
sync with by hand.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from src.managers.user_manager import UserManager
from src.models.user import Role
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GroupResolution:
    """The result of resolving a group's most-permissive member.

    Attributes:
        phone: The specific phone number that produced `role` - what callers
            pass as AIHandler's `user_phone=` override (AIHandler resolves a
            User from a phone, not a bare Role).
        role: The most-permissive Role among the group's members.
    """
    phone: str
    role: Role


class GroupMembershipResolver:
    """Resolves a WhatsApp group's most-permissive member, via a real Green API
    getGroupData call, cached per chat_id."""

    def __init__(self, groups_client, user_manager: UserManager):
        """
        Args:
            groups_client: Green API's `bot.api.groups` client (constructor-injected,
                per this codebase's DI convention - never a new global).
            user_manager: Existing UserManager, reused for its role-precedence logic
                (this resolver adds no new precedence rule of its own).
        """
        self.groups_client = groups_client
        self.user_manager = user_manager
        self._cache: Dict[str, GroupResolution] = {}

    def resolve(self, chat_id: str) -> Optional[GroupResolution]:
        """Return the most-permissive member's phone/Role for this group, or None
        if resolution fails (Green API error, malformed response, empty participant
        list) - callers fall back to sender-only resolution in that case, never
        blocking the turn.
        """
        if chat_id in self._cache:
            return self._cache[chat_id]

        try:
            response = self.groups_client.getGroupData(chat_id)
        except Exception as e:
            logger.warning(f"GroupMembershipResolver: getGroupData failed for {chat_id}: {e}")
            return None

        if not response or getattr(response, 'code', None) != 200 or not isinstance(response.data, dict):
            logger.warning(
                f"GroupMembershipResolver: getGroupData returned non-success for {chat_id}: "
                f"code={getattr(response, 'code', None)!r}"
            )
            return None

        participants = response.data.get('participants', [])
        member_phones = [p.get('id') for p in participants if p.get('id')]

        if not member_phones:
            logger.warning(f"GroupMembershipResolver: no participants found for {chat_id}")
            return None

        users = [self.user_manager.get_user(phone) for phone in member_phones]
        # Most-permissive = highest token_limit (ADMIN and GODFATHER are equivalent
        # here, per research.md SS2 - both 100_000; BLOCKED is 0; CLIENT is 4_000).
        most_permissive_user = max(users, key=lambda u: u.token_limit)
        most_permissive_phone = member_phones[users.index(most_permissive_user)]

        resolution = GroupResolution(phone=most_permissive_phone, role=most_permissive_user.role)
        self._cache[chat_id] = resolution
        return resolution
