"""User model for role-based access control."""

from enum import Enum
from dataclasses import dataclass


class Role(str, Enum):
    """User roles with different permission levels."""

    ADMIN = "ADMIN"  # Full system control
    GODFATHER = "GODFATHER"  # Trusted power user with elevated limits
    CLIENT = "CLIENT"  # Regular user with standard limits
    BLOCKED = "BLOCKED"  # Access denied


class MemoryScope(str, Enum):
    """Memory access scope levels."""

    PUBLIC = "PUBLIC"  # Visible to all roles (CLIENT, GODFATHER, ADMIN)
    PRIVATE = "PRIVATE"  # Only GODFATHER and ADMIN (default for now)
    SYSTEM = "SYSTEM"  # ADMIN only


@dataclass
class User:
    """Represents a user with role-based permissions."""

    phone: str
    role: Role

    def __post_init__(self):
        """Validate user data."""
        if not self.phone:
            raise ValueError("Phone number cannot be empty")
        if not isinstance(self.role, Role):
            raise ValueError(f"Invalid role: {self.role}")

    @property
    def token_limit(self) -> int:
        """Get token limit based on role."""
        limits = {
            Role.CLIENT: 4_000,
            Role.GODFATHER: 100_000,
            Role.ADMIN: 100_000,
            Role.BLOCKED: 0
        }
        return limits.get(self.role, 0)

    @property
    def allowed_memory_scopes(self) -> list[MemoryScope]:
        """Get allowed memory scopes based on role."""
        scopes = {
            Role.CLIENT: [MemoryScope.PUBLIC, MemoryScope.PRIVATE],  # Public + their own memories
            Role.GODFATHER: [MemoryScope.PUBLIC, MemoryScope.PRIVATE],  # Public + all private memories
            Role.ADMIN: [MemoryScope.PUBLIC, MemoryScope.PRIVATE, MemoryScope.SYSTEM]
        }
        return scopes.get(self.role, [])

    @property
    def can_access_system(self) -> bool:
        """Check if user has system-level access."""
        return self.role == Role.ADMIN

    @property
    def can_see_all_memories(self) -> bool:
        """Check if user can see memories from all users."""
        return self.role in [Role.GODFATHER, Role.ADMIN]

    @property
    def is_blocked(self) -> bool:
        """Check if user is blocked."""
        return self.role == Role.BLOCKED
