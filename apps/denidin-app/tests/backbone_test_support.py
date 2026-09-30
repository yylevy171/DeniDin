"""Shared helper for Backbone tests: a real SessionManager on a throwaway
directory (the orchestrator requires one - the app can't run without it)."""
import tempfile

from src.managers.session_manager import SessionManager


def make_session_manager() -> SessionManager:
    return SessionManager(storage_dir=tempfile.mkdtemp(prefix="backbone_sessions_"))
