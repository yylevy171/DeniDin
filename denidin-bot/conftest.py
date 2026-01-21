"""
Pytest configuration for DeniDin test suite.

Provides fixtures for consistent test logging:
- All test logs go to logs/test_logs/{test_file_name}.log
"""
import sys
import pytest
from pathlib import Path

# Add src directory to Python path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))


@pytest.fixture(scope="session", autouse=True)
def setup_test_logging():
    """
    Configure logging for test session.
    Creates logs/test_logs directory for all test logs.
    """
    test_logs_dir = project_root / "logs" / "test_logs"
    test_logs_dir.mkdir(parents=True, exist_ok=True)
    yield
    # Cleanup happens automatically via .gitignore


@pytest.fixture(scope="module")
def test_logger_config(request):
    """
    Provide logger configuration for each test module.
    Returns a dict with log_filename set to 'test_logs/{module_name}.log'
    
    Usage in tests:
        def test_something(test_logger_config):
            logger = get_logger(__name__, **test_logger_config)
    """
    # Get the test module filename (e.g., 'test_ai_handler.py' -> 'test_ai_handler')
    module_name = Path(request.module.__file__).stem
    
    return {
        'logs_dir': 'logs',
        'log_filename': f'test_logs/{module_name}.log',
        'log_level': 'DEBUG'  # Use DEBUG for tests to capture more detail
    }

