"""Unit tests for User model and Role-based access control."""

import pytest
from src.models.user import User, Role, MemoryScope


class TestRole:
    """Test Role enum values."""
    
    def test_role_values_exist(self):
        """Test that all required role values are defined."""
        assert Role.ADMIN == "ADMIN"
        assert Role.GODFATHER == "GODFATHER"
        assert Role.CLIENT == "CLIENT"
        assert Role.BLOCKED == "BLOCKED"
    
    def test_role_is_string_enum(self):
        """Test that Role is a string enum."""
        assert isinstance(Role.CLIENT.value, str)
        assert str(Role.CLIENT) == "Role.CLIENT"


class TestMemoryScope:
    """Test MemoryScope enum values."""
    
    def test_memory_scope_values_exist(self):
        """Test that all memory scope values are defined."""
        assert MemoryScope.PUBLIC == "PUBLIC"
        assert MemoryScope.PRIVATE == "PRIVATE"
        assert MemoryScope.SYSTEM == "SYSTEM"
    
    def test_memory_scope_is_string_enum(self):
        """Test that MemoryScope is a string enum."""
        assert isinstance(MemoryScope.PRIVATE.value, str)


class TestUserModel:
    """Test User model creation and validation."""
    
    def test_create_client_user(self):
        """Test creating a CLIENT user."""
        user = User(phone="+972501234567", role=Role.CLIENT)
        assert user.phone == "+972501234567"
        assert user.role == Role.CLIENT
    
    def test_create_godfather_user(self):
        """Test creating a GODFATHER user."""
        user = User(phone="+972507654321", role=Role.GODFATHER)
        assert user.phone == "+972507654321"
        assert user.role == Role.GODFATHER
    
    def test_create_admin_user(self):
        """Test creating an ADMIN user."""
        user = User(phone="+972509999999", role=Role.ADMIN)
        assert user.role == Role.ADMIN
    
    def test_create_blocked_user(self):
        """Test creating a BLOCKED user."""
        user = User(phone="+972501111111", role=Role.BLOCKED)
        assert user.role == Role.BLOCKED
    
    def test_empty_phone_raises_error(self):
        """Test that empty phone number raises ValueError."""
        with pytest.raises(ValueError, match="Phone number cannot be empty"):
            User(phone="", role=Role.CLIENT)
    
    def test_invalid_role_raises_error(self):
        """Test that invalid role raises ValueError."""
        with pytest.raises(ValueError, match="Invalid role"):
            User(phone="+972501234567", role="INVALID_ROLE")


class TestUserTokenLimits:
    """Test token limits for different roles."""
    
    def test_client_token_limit(self):
        """Test CLIENT has 4K token limit."""
        user = User(phone="+972501234567", role=Role.CLIENT)
        assert user.token_limit == 4_000
    
    def test_godfather_token_limit(self):
        """Test GODFATHER has 100K token limit."""
        user = User(phone="+972507654321", role=Role.GODFATHER)
        assert user.token_limit == 100_000
    
    def test_admin_token_limit(self):
        """Test ADMIN has 100K token limit."""
        user = User(phone="+972509999999", role=Role.ADMIN)
        assert user.token_limit == 100_000
    
    def test_blocked_token_limit(self):
        """Test BLOCKED has 0 token limit."""
        user = User(phone="+972501111111", role=Role.BLOCKED)
        assert user.token_limit == 0


class TestUserMemoryScopes:
    """Test memory scope permissions for different roles."""
    
    def test_client_memory_scopes(self):
        """Test CLIENT can access PUBLIC and PRIVATE scopes (their own memories)."""
        user = User(phone="+972501234567", role=Role.CLIENT)
        assert user.allowed_memory_scopes == [MemoryScope.PUBLIC, MemoryScope.PRIVATE]
    
    def test_godfather_memory_scopes(self):
        """Test GODFATHER can access PUBLIC and PRIVATE scopes (all memories)."""
        user = User(phone="+972507654321", role=Role.GODFATHER)
        assert user.allowed_memory_scopes == [MemoryScope.PUBLIC, MemoryScope.PRIVATE]
    
    def test_admin_memory_scopes(self):
        """Test ADMIN can access all scopes."""
        user = User(phone="+972509999999", role=Role.ADMIN)
        assert MemoryScope.PUBLIC in user.allowed_memory_scopes
        assert MemoryScope.PRIVATE in user.allowed_memory_scopes
        assert MemoryScope.SYSTEM in user.allowed_memory_scopes


class TestUserPermissions:
    """Test permission checks for different roles."""
    
    def test_client_cannot_access_system(self):
        """Test CLIENT cannot access system-level features."""
        user = User(phone="+972501234567", role=Role.CLIENT)
        assert user.can_access_system is False
    
    def test_godfather_cannot_access_system(self):
        """Test GODFATHER cannot access system-level features."""
        user = User(phone="+972507654321", role=Role.GODFATHER)
        assert user.can_access_system is False
    
    def test_admin_can_access_system(self):
        """Test ADMIN can access system-level features."""
        user = User(phone="+972509999999", role=Role.ADMIN)
        assert user.can_access_system is True
    
    def test_client_cannot_see_all_memories(self):
        """Test CLIENT can only see their own memories."""
        user = User(phone="+972501234567", role=Role.CLIENT)
        assert user.can_see_all_memories is False
    
    def test_godfather_can_see_all_memories(self):
        """Test GODFATHER can see all user memories."""
        user = User(phone="+972507654321", role=Role.GODFATHER)
        assert user.can_see_all_memories is True
    
    def test_admin_can_see_all_memories(self):
        """Test ADMIN can see all user memories."""
        user = User(phone="+972509999999", role=Role.ADMIN)
        assert user.can_see_all_memories is True
    
    def test_client_is_not_blocked(self):
        """Test CLIENT is not blocked."""
        user = User(phone="+972501234567", role=Role.CLIENT)
        assert user.is_blocked is False
    
    def test_blocked_user_is_blocked(self):
        """Test BLOCKED user is blocked."""
        user = User(phone="+972501111111", role=Role.BLOCKED)
        assert user.is_blocked is True
    
    def test_godfather_is_not_blocked(self):
        """Test GODFATHER is not blocked."""
        user = User(phone="+972507654321", role=Role.GODFATHER)
        assert user.is_blocked is False
