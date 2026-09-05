"""Unit tests for webapp_backend.auth (Story 1A)."""
from datetime import timedelta

import pytest

from webapp_backend.auth import PasswordVerifier, SessionStore, hash_password

SALT = "denidin-pw"


def test_hash_password_is_stable_sha256_of_salt_plus_password():
    # sha256("denidin-pw" + "hunter2")
    import hashlib

    expected = hashlib.sha256(b"denidin-pwhunter2").hexdigest()
    assert hash_password("hunter2", SALT) == expected
    assert len(hash_password("x", SALT)) == 64


class TestPasswordVerifier:
    def _write(self, tmp_path, contents):
        p = tmp_path / "password.hash"
        p.write_text(contents, encoding="utf-8")
        return p

    def test_correct_password_verifies(self, tmp_path):
        v = PasswordVerifier(self._write(tmp_path, hash_password("right", SALT)), SALT)
        assert v.usable
        assert v.verify("right") is True

    def test_wrong_password_rejected(self, tmp_path):
        v = PasswordVerifier(self._write(tmp_path, hash_password("right", SALT)), SALT)
        assert v.verify("wrong") is False

    def test_missing_file_is_not_fatal_but_unusable(self, tmp_path):
        v = PasswordVerifier(tmp_path / "does-not-exist.hash", SALT)
        assert v.usable is False
        assert v.load_error is not None
        assert v.verify("anything") is False

    def test_malformed_file_is_not_fatal_but_unusable(self, tmp_path):
        v = PasswordVerifier(self._write(tmp_path, "not-a-hash"), SALT)
        assert v.usable is False
        assert v.verify("anything") is False

    def test_comparison_is_literal_no_whitespace_trimming(self, tmp_path):
        v = PasswordVerifier(self._write(tmp_path, hash_password("secret", SALT)), SALT)
        assert v.verify("secret") is True
        assert v.verify(" secret ") is False
        assert v.verify("secret\n") is False

    def test_trailing_newline_in_hash_file_is_tolerated(self, tmp_path):
        v = PasswordVerifier(self._write(tmp_path, hash_password("p", SALT) + "\n"), SALT)
        assert v.usable
        assert v.verify("p") is True


class TestSessionStore:
    def test_issue_then_validate(self):
        store = SessionStore()
        token = store.issue()
        assert store.validate(token) is True
        assert token in store

    def test_unknown_token_is_unknown(self):
        store = SessionStore()
        assert store.check("nope") == "unknown"
        assert store.validate("nope") is False

    def test_logout_invalidates_only_that_token(self):
        store = SessionStore()
        a, b = store.issue(), store.issue()
        store.invalidate(a)
        assert store.validate(a) is False
        assert store.validate(b) is True
        assert store.active_count == 1

    def test_concurrent_sessions_are_independent(self):
        store = SessionStore()
        tokens = [store.issue() for _ in range(4)]
        assert all(store.validate(t) for t in tokens)
        assert len({*tokens}) == 4

    def test_stale_last_activity_expires_the_token(self):
        # Logic-only check (not the real 168h wait, which is manual per the 2026-09-05
        # decision): force last_active_at into the past and confirm check() drops it.
        store = SessionStore(expiry_hours=168.0)
        token = store.issue()
        store._tokens[token] = store._tokens[token] - timedelta(hours=169)
        assert store.check(token) == "expired"
        assert token not in store

    def test_activity_refreshes_last_active_at(self):
        store = SessionStore(expiry_hours=168.0)
        token = store.issue()
        store._tokens[token] = store._tokens[token] - timedelta(hours=100)
        assert store.check(token) == "ok"
        # refreshed to ~now, so a further 100h-old shift is still fine
        assert store.check(token) == "ok"
