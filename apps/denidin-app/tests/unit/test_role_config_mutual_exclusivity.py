"""Regression guard for dev's operator-switchable role mapping (019-env-separation, US5/FR-015).

FR-015: dev's config.dev.json should carry the operator's number in exactly
one of godfather_phone/admin_phones at a time. Software does not enforce
this (it's an operator discipline) - this test documents/pins down what
actually happens if the operator forgets and leaves it in both: UserManager's
existing ADMIN > GODFATHER precedence resolves to ADMIN, not an error and not
GODFATHER. This is existing behavior (not new), captured as a regression test.
"""
from src.managers.user_manager import UserManager
from src.models.user import Role


def test_phone_in_both_admin_and_godfather_resolves_to_admin():
    phone = "972522968679"
    manager = UserManager(godfather_phone=phone, admin_phones=[phone])

    user = manager.get_user(phone)

    assert user.role == Role.ADMIN


def test_phone_in_godfather_only_resolves_to_godfather():
    phone = "972522968679"
    manager = UserManager(godfather_phone=phone, admin_phones=[])

    user = manager.get_user(phone)

    assert user.role == Role.GODFATHER


def test_phone_in_admin_only_resolves_to_admin():
    phone = "972522968679"
    manager = UserManager(godfather_phone=None, admin_phones=[phone])

    user = manager.get_user(phone)

    assert user.role == Role.ADMIN
