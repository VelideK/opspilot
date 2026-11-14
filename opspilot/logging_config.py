"""JSON logging for container log collection."""

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in (
            "event",
            "check_name",
            "healthy",
            "status_code",
            "latency_ms",
            "error",
        ):
            if hasattr(record, field):
                entry[field] = getattr(record, field)
        return json.dumps(entry, ensure_ascii=True)


def _configure_logger() -> logging.Logger:
    configured_logger = logging.getLogger("opspilot")
    configured_logger.setLevel(logging.INFO)
    configured_logger.propagate = False
    if configured_logger.handlers:
        return configured_logger

    formatter = JsonFormatter()
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    configured_logger.addHandler(stream_handler)

    log_file = os.getenv("OPSPILOT_LOG_FILE")
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        configured_logger.addHandler(file_handler)

    return configured_logger


logger = _configure_logger()
