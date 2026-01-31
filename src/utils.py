"""
Utility functions for logging, redaction, and formatting.
"""

import re
import logging
from datetime import datetime


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Set up logging with redaction filter."""
    logger = logging.getLogger("support_triage")
    logger.setLevel(level)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        handler.addFilter(RedactionFilter())
        logger.addHandler(handler)
    
    return logger


class RedactionFilter(logging.Filter):
    """Filter to redact sensitive information from logs."""
    
    # Patterns to redact
    patterns = [
        (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL_REDACTED]"),
        (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "[CARD_REDACTED]"),
        (r"\bsk-[a-zA-Z0-9]{32,}\b", "[API_KEY_REDACTED]"),
        (r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[PHONE_REDACTED]"),
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive data from log message."""
        message = record.getMessage()
        for pattern, replacement in self.patterns:
            message = re.sub(pattern, replacement, message)
        record.msg = message
        record.args = ()
        return True


def redact_email(text: str) -> str:
    """Redact email addresses from text."""
    return re.sub(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "[EMAIL_REDACTED]",
        text
    )


def format_timestamp(dt: datetime | None = None) -> str:
    """Format a datetime for display."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to max length with suffix."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_urgency_badge(urgency: str) -> str:
    """Format urgency as a colored badge for terminal output."""
    colors = {
        "P0": "\033[91m",  # Red
        "P1": "\033[93m",  # Yellow
        "P2": "\033[94m",  # Blue
        "P3": "\033[92m",  # Green
    }
    reset = "\033[0m"
    color = colors.get(urgency, "")
    return f"{color}[{urgency}]{reset}"


def format_team_badge(team: str) -> str:
    """Format team name as a badge."""
    return f"[{team.upper()}]"


def print_separator(char: str = "=", length: int = 70):
    """Print a separator line."""
    print(char * length)


def print_section_header(title: str, char: str = "-", length: int = 70):
    """Print a section header."""
    print(f"\n{char * 3} {title} {char * (length - len(title) - 5)}")

