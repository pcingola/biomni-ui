import logging
from pathlib import Path

from biomni_ui.config import config


def setup_session_logger(session_id: str) -> logging.Logger:
    """Set up a logger for a specific session."""
    logger_name = f"biomni_ui.session.{session_id}"
    logger = logging.getLogger(logger_name)
    
    # Avoid adding multiple handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, config.log_level))
    
    # Create session logs directory
    logs_path = config.get_session_logs_path(session_id)
    logs_path.mkdir(parents=True, exist_ok=True)
    
    # File handler for session-specific logs
    log_file = logs_path / "session.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(getattr(logging, config.log_level))
    
    # Formatter
    formatter = logging.Formatter(config.log_format)
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    
    return logger


def get_main_logger() -> logging.Logger:
    """Get the main application logger."""
    return logging.getLogger("biomni_ui")