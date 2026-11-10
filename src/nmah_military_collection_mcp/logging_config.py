"""Configure only the project's stderr logger."""

import logging
import os
import sys
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        return True


def configure_project_logging() -> None:
    """Read LOG_LEVEL once at startup, defaulting to INFO."""
    raw_level = os.getenv("LOG_LEVEL", "").strip().upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    level = raw_level if raw_level in valid_levels else "INFO"

    logger = logging.getLogger(__package__)
    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(RequestIDFilter())
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: request_id=%(request_id)s %(message)s"
        )
    )
    logger.handlers[:] = [handler]
    logger.setLevel(level)
    logger.propagate = False
    if raw_level and raw_level not in valid_levels:
        logger.warning("Invalid LOG_LEVEL; using INFO.")
