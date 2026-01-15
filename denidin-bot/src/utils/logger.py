"""
Logging utility for the DeniDin chatbot.
Provides file and console logging with rotation.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(
    name: str,
    logs_dir: str = 'logs',
    log_level: str = 'INFO',
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Set up a logger with file and console handlers.
    
    Args:
        name: Name of the logger
        logs_dir: Directory to store log files
        log_level: Logging level ('INFO' or 'DEBUG')
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        
    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    os.makedirs(logs_dir, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Prevent duplicate handlers if logger already exists
    if logger.handlers:
        return logger
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation
    log_file = os.path.join(logs_dir, 'denidin.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setLevel(getattr(logging, log_level))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler (outputs to stderr)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(
    name: str,
    logs_dir: str = 'logs',
    log_level: str = 'INFO'
) -> logging.Logger:
    """
    Get or create a configured logger.
    
    Args:
        name: Name of the logger
        logs_dir: Directory to store log files
        log_level: Logging level ('INFO' or 'DEBUG')
        
    Returns:
        Configured logger instance
    """
    return setup_logger(name, logs_dir, log_level)
