"""
Unit tests for GroupMembershipResolver (Feature 039, US4).
"""
from unittest.mock import Mock

import pytest

from src.managers.group_membership_resolver import GroupMembershipResolver
from src.managers.user_manager import UserManager


def _fake_response(code, data):
    response = Mock()
    response.code = code
    response.data = data
    return response


@pytest.fixture
def user_manager():
    return UserManager(
        godfather_phone="972501111111",
        admin_phones=["972502222222"],
        blocked_phones=["972503333333"]
    )


class TestGroupMembershipResolverSuccess:
    def test_resolves_most_permissive_member_admin_over_client(self, user_manager):
        groups_client = Mock()
        groups_client.getGroupData.return_value = _fake_response(200, {
            'participants': [
                {'id': '972502222222@c.us', 'isAdmin': False},  # our ADMIN
                {'id': '972509999999@c.us', 'isAdmin': True},  # unknown -> CLIENT
            ]
        })
        resolver = GroupMembershipResolver(groups_client, user_manager)

        resolution = resolver.resolve('120363012345678901@g.us')

        assert resolution is not None
        assert resolution.phone == '972502222222@c.us'
        assert resolution.role.value == 'ADMIN'

    def test_godfather_and_admin_are_equivalent(self, user_manager):
        """research.md SS2: GODFATHER and ADMIN have identical token_limit - either
        may be returned as "most permissive" when both are present."""
        groups_client = Mock()
        groups_client.getGroupData.return_value = _fake_response(200, {
            'participants': [
                {'id': '972501111111@c.us'},  # GODFATHER
                {'id': '972502222222@c.us'},  # ADMIN
            ]
        })
        resolver = GroupMembershipResolver(groups_client, user_manager)

        resolution = resolver.resolve('120363012345678901@g.us')

        assert resolution.role.value in ('GODFATHER', 'ADMIN')

    def test_client_only_group_resolves_to_client(self, user_manager):
        groups_client = Mock()
        groups_client.getGroupData.return_value = _fake_response(200, {
            'participants': [{'id': '972509999999@c.us'}]
        })
        resolver = GroupMembershipResolver(groups_client, user_manager)

        resolution = resolver.resolve('120363012345678901@g.us')

        assert resolution.role.value == 'CLIENT'

    def test_caches_result_no_second_api_call(self, user_manager):
        groups_client = Mock()
        groups_client.getGroupData.return_value = _fake_response(200, {
            'participants': [{'id': '972502222222@c.us'}]
        })
        resolver = GroupMembershipResolver(groups_client, user_manager)

        resolver.resolve('120363012345678901@g.us')
        resolver.resolve('120363012345678901@g.us')

        assert groups_client.getGroupData.call_count == 1


class TestGroupMembershipResolverFailure:
    def test_returns_none_on_exception(self, user_manager):
        groups_client = Mock()
        groups_client.getGroupData.side_effect = Exception("network error")
        resolver = GroupMembershipResolver(groups_client, user_manager)

        assert resolver.resolve('120363012345678901@g.us') is None

    def test_returns_none_on_non_200(self, user_manager):
        groups_client = Mock()
        groups_client.getGroupData.return_value = _fake_response(500, None)
        resolver = GroupMembershipResolver(groups_client, user_manager)

        assert resolver.resolve('120363012345678901@g.us') is None

    def test_returns_none_on_empty_participants(self, user_manager):
        groups_client = Mock()
        groups_client.getGroupData.return_value = _fake_response(200, {'participants': []})
        resolver = GroupMembershipResolver(groups_client, user_manager)

        assert resolver.resolve('120363012345678901@g.us') is None

    def test_failure_not_cached(self, user_manager):
        """A failed resolution should not poison the cache - the next call should
        try the real API again, not silently keep returning None forever."""
        groups_client = Mock()
        groups_client.getGroupData.side_effect = [
            Exception("transient error"),
            _fake_response(200, {'participants': [{'id': '972502222222@c.us'}]})
        ]
        resolver = GroupMembershipResolver(groups_client, user_manager)

        assert resolver.resolve('120363012345678901@g.us') is None
        assert resolver.resolve('120363012345678901@g.us') is not None
