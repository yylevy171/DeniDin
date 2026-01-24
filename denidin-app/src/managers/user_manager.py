"""UserManager for role assignment and permission checking."""

from typing import Optional
from src.models.user import User, Role, MemoryScope


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

        # Determine role based on precedence
        if phone in self.admin_phones:
            role = Role.ADMIN
        elif phone == self.godfather_phone:
            role = Role.GODFATHER
        elif phone in self.blocked_phones:
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
