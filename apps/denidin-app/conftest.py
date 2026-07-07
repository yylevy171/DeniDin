"""
Pytest configuration for DeniDin test suite.

Automatically configures logging for all tests:
- Production: logs/denidin.log
- Tests: logs/test_logs/{test_file_name}.log (automatic, per test file)
"""
import sys
import pytest
import logging
import warnings
from pathlib import Path

# Suppress SWIG deprecation warnings from ChromaDB before any imports
warnings.filterwarnings("ignore", message=".*builtin type.*has no __module__ attribute")

# Add src directory to Python path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

# Track current test file for logging
_current_test_file = None


def pytest_configure(config):
    """Register custom markers and filter warnings."""
    config.addinivalue_line(
        "markers", 
        "expensive: Tests that use real OpenAI APIs and incur costs (skip by default)"
    )
    
    # Suppress harmless SWIG deprecation warnings from ChromaDB
    warnings.filterwarnings(
        "ignore",
        message=".*builtin type.*has no __module__ attribute",
        category=DeprecationWarning
    )


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
    Clears all existing loggers to ensure test logs go to test_logs directory.
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
    
    # Clear ALL existing loggers and their handlers (including module-level loggers)
    # This ensures that any loggers created during module import are reconfigured
    loggers_to_clear = [logging.getLogger()] + [
        logging.getLogger(name) for name in logging.root.manager.loggerDict
    ]
    
    for logger_obj in loggers_to_clear:
        if isinstance(logger_obj, logging.Logger):
            for handler in logger_obj.handlers[:]:
                handler.close()
                logger_obj.removeHandler(handler)
    
    # Set up root logger with file handler for this test file
    root_logger = logging.getLogger()
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.DEBUG)
    
    # Ensure all child loggers inherit from root
    for name in logging.root.manager.loggerDict:
        logger_obj = logging.getLogger(name)
        if isinstance(logger_obj, logging.Logger):
            logger_obj.propagate = True  # Ensure propagation to root logger


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

