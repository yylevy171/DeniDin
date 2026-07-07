"""Pytest configuration for the morning-mcp-app test suite."""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (hit the real Morning sandbox API)"
    )
