"""Unit tests for UserManager - role assignment and permission checking."""

import pytest
from src.models.user import User, Role, MemoryScope
from src.managers.user_manager import UserManager


class TestUserManagerInitialization:
    """Test UserManager creation and configuration."""
    
    def test_create_user_manager_with_godfather(self):
        """Test creating UserManager with godfather phone configured."""
        manager = UserManager(godfather_phone="+972507654321")
        assert manager.godfather_phone == "+972507654321"
    
    def test_create_user_manager_without_godfather(self):
        """Test creating UserManager without godfather phone."""
        manager = UserManager()
        assert manager.godfather_phone is None
    
    def test_create_user_manager_with_admin_phones(self):
        """Test creating UserManager with admin phones list."""
        admin_phones = ["+972509999999", "+972508888888"]
        manager = UserManager(admin_phones=admin_phones)
        assert manager.admin_phones == admin_phones
    
    def test_create_user_manager_without_admin_phones(self):
        """Test creating UserManager without admin phones."""
        manager = UserManager()
        assert manager.admin_phones == []
    
    def test_create_user_manager_with_blocked_phones(self):
        """Test creating UserManager with blocked phones list."""
        blocked_phones = ["+972501111111", "+972502222222"]
        manager = UserManager(blocked_phones=blocked_phones)
        assert manager.blocked_phones == blocked_phones
    
    def test_create_user_manager_without_blocked_phones(self):
        """Test creating UserManager without blocked phones."""
        manager = UserManager()
        assert manager.blocked_phones == []


class TestUserManagerRoleAssignment:
    """Test role assignment logic based on phone numbers."""
    
    def test_get_user_returns_admin_for_admin_phone(self):
        """Test that admin phone number gets ADMIN role."""
        manager = UserManager(admin_phones=["+972509999999"])
        user = manager.get_user("+972509999999")
        assert user.role == Role.ADMIN
        assert user.phone == "+972509999999"
    
    def test_get_user_returns_godfather_for_godfather_phone(self):
        """Test that godfather phone number gets GODFATHER role."""
        manager = UserManager(godfather_phone="+972507654321")
        user = manager.get_user("+972507654321")
        assert user.role == Role.GODFATHER
        assert user.phone == "+972507654321"
    
    def test_get_user_returns_blocked_for_blocked_phone(self):
        """Test that blocked phone number gets BLOCKED role."""
        manager = UserManager(blocked_phones=["+972501111111"])
        user = manager.get_user("+972501111111")
        assert user.role == Role.BLOCKED
        assert user.phone == "+972501111111"
    
    def test_get_user_returns_client_for_unknown_phone(self):
        """Test that unknown phone number gets CLIENT role (default)."""
        manager = UserManager()
        user = manager.get_user("+972501234567")
        assert user.role == Role.CLIENT
        assert user.phone == "+972501234567"
    
    def test_admin_takes_precedence_over_godfather(self):
        """Test that ADMIN role takes precedence if phone is in both lists."""
        manager = UserManager(
            admin_phones=["+972509999999"],
            godfather_phone="+972509999999"
        )
        user = manager.get_user("+972509999999")
        assert user.role == Role.ADMIN
    
    def test_admin_takes_precedence_over_blocked(self):
        """Test that ADMIN role takes precedence over BLOCKED."""
        manager = UserManager(
            admin_phones=["+972509999999"],
            blocked_phones=["+972509999999"]
        )
        user = manager.get_user("+972509999999")
        assert user.role == Role.ADMIN
    
    def test_godfather_takes_precedence_over_blocked(self):
        """Test that GODFATHER role takes precedence over BLOCKED."""
        manager = UserManager(
            godfather_phone="+972507654321",
            blocked_phones=["+972507654321"]
        )
        user = manager.get_user("+972507654321")
        assert user.role == Role.GODFATHER


class TestUserManagerPermissionChecks:
    """Test permission checking methods."""
    
    def test_is_blocked_returns_true_for_blocked_user(self):
        """Test that blocked phone is identified as blocked."""
        manager = UserManager(blocked_phones=["+972501111111"])
        assert manager.is_blocked("+972501111111") is True
    
    def test_is_blocked_returns_false_for_client(self):
        """Test that client phone is not blocked."""
        manager = UserManager()
        assert manager.is_blocked("+972501234567") is False
    
    def test_is_blocked_returns_false_for_godfather(self):
        """Test that godfather phone is not blocked."""
        manager = UserManager(godfather_phone="+972507654321")
        assert manager.is_blocked("+972507654321") is False
    
    def test_is_blocked_returns_false_for_admin(self):
        """Test that admin phone is not blocked."""
        manager = UserManager(admin_phones=["+972509999999"])
        assert manager.is_blocked("+972509999999") is False
    
    def test_can_access_system_returns_true_for_admin(self):
        """Test that admin can access system-level features."""
        manager = UserManager(admin_phones=["+972509999999"])
        assert manager.can_access_system("+972509999999") is True
    
    def test_can_access_system_returns_false_for_godfather(self):
        """Test that godfather cannot access system-level features."""
        manager = UserManager(godfather_phone="+972507654321")
        assert manager.can_access_system("+972507654321") is False
    
    def test_can_access_system_returns_false_for_client(self):
        """Test that client cannot access system-level features."""
        manager = UserManager()
        assert manager.can_access_system("+972501234567") is False
    
    def test_can_see_all_memories_returns_true_for_admin(self):
        """Test that admin can see all user memories."""
        manager = UserManager(admin_phones=["+972509999999"])
        assert manager.can_see_all_memories("+972509999999") is True
    
    def test_can_see_all_memories_returns_true_for_godfather(self):
        """Test that godfather can see all user memories."""
        manager = UserManager(godfather_phone="+972507654321")
        assert manager.can_see_all_memories("+972507654321") is True
    
    def test_can_see_all_memories_returns_false_for_client(self):
        """Test that client can only see their own memories."""
        manager = UserManager()
        assert manager.can_see_all_memories("+972501234567") is False
    
    def test_get_token_limit_returns_correct_limit_for_client(self):
        """Test that client gets 4K token limit."""
        manager = UserManager()
        assert manager.get_token_limit("+972501234567") == 4_000
    
    def test_get_token_limit_returns_correct_limit_for_godfather(self):
        """Test that godfather gets 100K token limit."""
        manager = UserManager(godfather_phone="+972507654321")
        assert manager.get_token_limit("+972507654321") == 100_000
    
    def test_get_token_limit_returns_correct_limit_for_admin(self):
        """Test that admin gets 100K token limit."""
        manager = UserManager(admin_phones=["+972509999999"])
        assert manager.get_token_limit("+972509999999") == 100_000
    
    def test_get_token_limit_returns_zero_for_blocked(self):
        """Test that blocked user gets 0 token limit."""
        manager = UserManager(blocked_phones=["+972501111111"])
        assert manager.get_token_limit("+972501111111") == 0
    
    def test_get_allowed_scopes_returns_correct_scopes_for_client(self):
        """Test that client gets PUBLIC and PRIVATE scopes."""
        manager = UserManager()
        scopes = manager.get_allowed_scopes("+972501234567")
        assert scopes == [MemoryScope.PUBLIC, MemoryScope.PRIVATE]
    
    def test_get_allowed_scopes_returns_correct_scopes_for_godfather(self):
        """Test that godfather gets PUBLIC and PRIVATE scopes."""
        manager = UserManager(godfather_phone="+972507654321")
        scopes = manager.get_allowed_scopes("+972507654321")
        assert scopes == [MemoryScope.PUBLIC, MemoryScope.PRIVATE]
    
    def test_get_allowed_scopes_returns_all_scopes_for_admin(self):
        """Test that admin gets all scopes."""
        manager = UserManager(admin_phones=["+972509999999"])
        scopes = manager.get_allowed_scopes("+972509999999")
        assert MemoryScope.PUBLIC in scopes
        assert MemoryScope.PRIVATE in scopes
        assert MemoryScope.SYSTEM in scopes


class TestUserManagerEdgeCases:
    """Test edge cases and error handling."""
    
    def test_get_user_with_empty_phone_raises_error(self):
        """Test that empty phone number raises ValueError."""
        manager = UserManager()
        with pytest.raises(ValueError, match="Phone number cannot be empty"):
            manager.get_user("")
    
    def test_multiple_admin_phones_all_get_admin_role(self):
        """Test that all phones in admin list get ADMIN role."""
        admin_phones = ["+972509999999", "+972508888888", "+972507777777"]
        manager = UserManager(admin_phones=admin_phones)
        
        for phone in admin_phones:
            user = manager.get_user(phone)
            assert user.role == Role.ADMIN
    
    def test_multiple_blocked_phones_all_get_blocked_role(self):
        """Test that all phones in blocked list get BLOCKED role."""
        blocked_phones = ["+972501111111", "+972502222222", "+972503333333"]
        manager = UserManager(blocked_phones=blocked_phones)
        
        for phone in blocked_phones:
            user = manager.get_user(phone)
            assert user.role == Role.BLOCKED
    
    def test_get_user_caches_user_objects(self):
        """Test that calling get_user twice returns the same User object."""
        manager = UserManager()
        user1 = manager.get_user("+972501234567")
        user2 = manager.get_user("+972501234567")
        assert user1 is user2  # Same object reference


class TestUserManagerMultipleGodfathers:
    """Feature 055 (Multi-Tenancy), tasks.md T015a: multi-godfather-per-tenant support
    (REQ-ROLE / US2). `godfather_phones` is a NEW, additive parameter - checked in
    addition to (never instead of) the existing singular `godfather_phone`, per
    contracts/tenant-scoped-data-managers.md and research.md SS8's correction (one
    UserManager instance per tenant already scopes RBAC correctly; the one real gap
    was that today's `godfather_phone` field is genuinely singular)."""

    def test_create_user_manager_with_godfather_phones(self):
        """Test creating UserManager with the new plural godfather_phones list."""
        manager = UserManager(godfather_phones=["+972501111111", "+972502222222"])
        assert manager.godfather_phones == ["+972501111111", "+972502222222"]

    def test_create_user_manager_without_godfather_phones_defaults_empty(self):
        """Test creating UserManager without godfather_phones defaults to an empty
        list, matching admin_phones/blocked_phones's existing default convention."""
        manager = UserManager()
        assert manager.godfather_phones == []

    def test_first_godfather_phone_in_list_resolves_to_godfather_role(self):
        manager = UserManager(godfather_phones=["+972501111111", "+972502222222"])
        user = manager.get_user("+972501111111")
        assert user.role == Role.GODFATHER

    def test_second_godfather_phone_in_list_also_resolves_to_godfather_role(self):
        """The actual point of this feature: BOTH numbers get full godfather-level
        access, not just the first one in the list."""
        manager = UserManager(godfather_phones=["+972501111111", "+972502222222"])
        user = manager.get_user("+972502222222")
        assert user.role == Role.GODFATHER

    def test_three_godfather_phones_all_resolve_to_godfather_role(self):
        phones = ["+972501111111", "+972502222222", "+972503333333"]
        manager = UserManager(godfather_phones=phones)
        for phone in phones:
            assert manager.get_user(phone).role == Role.GODFATHER

    def test_singular_godfather_phone_and_plural_godfather_phones_both_apply_together(self):
        """The two parameters are additive, not mutually exclusive - a tenant
        migrated from the old singular field plus a newly-added second godfather
        both resolve correctly from the same UserManager instance."""
        manager = UserManager(
            godfather_phone="+972501111111", godfather_phones=["+972502222222"]
        )
        assert manager.get_user("+972501111111").role == Role.GODFATHER
        assert manager.get_user("+972502222222").role == Role.GODFATHER

    def test_admin_role_still_takes_precedence_over_a_godfather_phones_entry(self):
        """Role precedence (ADMIN > GODFATHER > BLOCKED > CLIENT) is unchanged by
        this addition - a number listed in both stays ADMIN."""
        manager = UserManager(
            admin_phones=["+972501111111"], godfather_phones=["+972501111111"]
        )
        assert manager.get_user("+972501111111").role == Role.ADMIN

    def test_phone_not_in_godfather_phones_list_is_not_a_godfather(self):
        manager = UserManager(godfather_phones=["+972501111111"])
        user = manager.get_user("+972509999999")
        assert user.role != Role.GODFATHER
        assert user.role == Role.CLIENT

    def test_godfather_phones_entry_matches_a_whatsapp_jid_via_existing_normalization(self):
        """Same JID-vs-bare-digits normalization that already applies to the
        singular godfather_phone/admin_phones/blocked_phones fields."""
        manager = UserManager(godfather_phones=["972501111111"])
        user = manager.get_user("972501111111@c.us")
        assert user.role == Role.GODFATHER


class TestUserManagerPreExistingSingularGodfatherPhoneUnaffected:
    """REQ-PARITY-001: every pre-existing test in this file constructs UserManager
    with only the singular godfather_phone and must keep passing byte-for-byte
    unchanged - this class re-runs the same core assertions explicitly, as a
    regression tripwire tied directly to this feature's parity requirement (rather
    than relying solely on the rest of this file staying untouched, which it also
    is)."""

    def test_singular_godfather_phone_alone_still_resolves_godfather_role(self):
        manager = UserManager(godfather_phone="+972507654321")
        user = manager.get_user("+972507654321")
        assert user.role == Role.GODFATHER

    def test_no_godfather_configured_at_all_still_defaults_to_client(self):
        manager = UserManager()
        user = manager.get_user("+972501234567")
        assert user.role == Role.CLIENT
