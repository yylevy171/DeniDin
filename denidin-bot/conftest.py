"""
Pytest configuration for DeniDin test suite.

Automatically configures logging for all tests:
- Production: logs/denidin.log
- Tests: logs/test_logs/{test_file_name}.log (automatic, per test file)
"""
import sys
import pytest
import logging
from pathlib import Path

# Add src directory to Python path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# Track current test file for logging
_current_test_file = None


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


def pytest_runtest_setup(item):
    """
    Pytest hook: Configure logging before each test runs.
    Automatically sets up per-test-file logging.
    """
    global _current_test_file
    
    # Get the test file name (e.g., 'test_ai_handler.py' -> 'test_ai_handler')
    test_file = Path(item.fspath).stem
    _current_test_file = test_file
    
    # Configure logging for this test file
    log_filename = f'test_logs/{test_file}.log'
    log_path = project_root / "logs" / log_filename
    
    # Ensure the directory exists
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove all existing handlers from root logger and reconfigure
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set up file handler for this test file
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.DEBUG)


@pytest.fixture(scope="module")
def test_logger_config(request):
    """
    Provide logger configuration for each test module.
    
    NOTE: This fixture is now optional - logging is automatically configured
    via pytest_runtest_setup hook. Keep for backward compatibility.
    """
    module_name = Path(request.module.__file__).stem
    
    return {
        'logs_dir': 'logs',
        'log_filename': f'test_logs/{module_name}.log',
        'log_level': 'DEBUG'
    }

