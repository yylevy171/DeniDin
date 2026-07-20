"""UserManager for role assignment and permission checking."""

import re
from typing import Optional
from src.models.user import User, Role, MemoryScope


def _normalize_phone(phone: str) -> str:
    """Normalize a phone number for role comparison.

    Real Green API webhooks populate the sender as a WhatsApp JID (e.g.
    "972522968679@c.us" or "...@g.us"), while godfather_phone/admin_phones/
    blocked_phones are configured as bare digit strings. Stripping the JID
    suffix and any non-digit characters (e.g. a leading "+") lets both sides
    compare equal regardless of which format either one uses.
    """
    if not phone:
        return phone
    local_part = phone.split('@', 1)[0]
    return re.sub(r'\D', '', local_part)


class UserManager:
    """Manages user roles and permissions based on phone numbers."""

    def __init__(
        self,
        godfather_phone: Optional[str] = None,
        admin_phones: Optional[list[str]] = None,
        blocked_phones: Optional[list[str]] = None
    ):
        """Initialize UserManager with role configuration.

        Args:
            godfather_phone: Phone number of the godfather (power user)
            admin_phones: List of admin phone numbers
            blocked_phones: List of blocked phone numbers
        """
        self.godfather_phone = godfather_phone
        self.admin_phones = admin_phones if admin_phones is not None else []
        self.blocked_phones = blocked_phones if blocked_phones is not None else []
        self._godfather_phone_normalized = _normalize_phone(godfather_phone) if godfather_phone else None
        self._admin_phones_normalized = {_normalize_phone(p) for p in self.admin_phones}
        self._blocked_phones_normalized = {_normalize_phone(p) for p in self.blocked_phones}
        self._user_cache: dict[str, User] = {}

    def get_user(self, phone: str) -> User:
        """Get User object with appropriate role for given phone number.

        Role precedence: ADMIN > GODFATHER > BLOCKED > CLIENT (default)

        Args:
            phone: Phone number to look up

        Returns:
            User object with assigned role

        Raises:
            ValueError: If phone is empty
        """
        if not phone:
            raise ValueError("Phone number cannot be empty")

        # Return cached user if exists
        if phone in self._user_cache:
            return self._user_cache[phone]

        # Determine role based on precedence (normalized: strips WhatsApp JID
        # suffix and non-digit characters so "972522968679@c.us" and
        # "972522968679" compare equal - see _normalize_phone)
        normalized = _normalize_phone(phone)
        if normalized in self._admin_phones_normalized:
            role = Role.ADMIN
        elif normalized == self._godfather_phone_normalized:
            role = Role.GODFATHER
        elif normalized in self._blocked_phones_normalized:
            role = Role.BLOCKED
        else:
            role = Role.CLIENT

        # Create and cache user
        user = User(phone=phone, role=role)
        self._user_cache[phone] = user
        return user

    def is_blocked(self, phone: str) -> bool:
        """Check if user is blocked.

        Args:
            phone: Phone number to check

        Returns:
            True if user is blocked, False otherwise
        """
        user = self.get_user(phone)
        return user.is_blocked

    def can_access_system(self, phone: str) -> bool:
        """Check if user has system-level access.

        Args:
            phone: Phone number to check

        Returns:
            True if user can access system features, False otherwise
        """
        user = self.get_user(phone)
        return user.can_access_system

    def can_see_all_memories(self, phone: str) -> bool:
        """Check if user can see memories from all users.

        Args:
            phone: Phone number to check

        Returns:
            True if user can see all memories, False if only their own
        """
        user = self.get_user(phone)
        return user.can_see_all_memories

    def get_token_limit(self, phone: str) -> int:
        """Get token limit for user.

        Args:
            phone: Phone number to check

        Returns:
            Token limit for user's role
        """
        user = self.get_user(phone)
        return user.token_limit

    def get_allowed_scopes(self, phone: str) -> list[MemoryScope]:
        """Get allowed memory scopes for user.

        Args:
            phone: Phone number to check

        Returns:
            List of allowed memory scopes
        """
        user = self.get_user(phone)
        return user.allowed_memory_scopes
