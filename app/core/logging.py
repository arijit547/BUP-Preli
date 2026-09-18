"""Structured JSON logger that prevents secret and traceback leakage."""

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

# Sensitive patterns to redact
SECRET_PATTERNS = [
    re.compile(r"""(?i)(api[_-]?key|secret|token|auth|password)["']?\s*[:=]\s*["']?([^"',\s]+)"""),
    re.compile(r"Bearer\s+([A-Za-z0-9_\-\.~+/=]+)")
]


def redact_secrets(text: str) -> str:
    """Redact sensitive strings matching API keys or auth tokens."""
    if not isinstance(text, str):
        return text
    redacted = text
    for pat in SECRET_PATTERNS:
        redacted = pat.sub(r"\1: [REDACTED]", redacted)
    return redacted


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured observability."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_secrets(record.getMessage())
        }
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            for k, v in record.extra_data.items():
                if isinstance(v, str):
                    log_obj[k] = redact_secrets(v)
                else:
                    log_obj[k] = v
        if record.exc_info:
            # Mask traceback details in output
            log_obj["exception"] = redact_secrets(self.formatException(record.exc_info))
        return json.dumps(log_obj)


def setup_logger(name: str = "gridwise", level: str = "INFO") -> logging.Logger:
    """Create or return structured JSON logger."""
    logger_instance = logging.getLogger(name)
    logger_instance.setLevel(getattr(logging, level.upper(), logging.INFO))
    if not logger_instance.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger_instance.addHandler(handler)
    logger_instance.propagate = False
    return logger_instance


logger = setup_logger()
