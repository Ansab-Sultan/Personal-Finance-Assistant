import logging
import sys
from typing import Optional

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_LEVEL_COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[1;31m",
}
_RESET = "\033[0m"


class _ColorFormatter(logging.Formatter):
    """Console formatter that prefixes each log level with an ANSI color code."""

    def format(self, record: logging.LogRecord) -> str:
        """Apply the color corresponding to the record's log level."""
        color = _LEVEL_COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{_RESET}"
        return super().format(record)


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Return a named logger scoped to the given module name.

    The logger is configured with a colored console handler on first call.
    Subsequent calls for the same name return the cached logger from Python's
    logging registry without adding duplicate handlers.

    Args:
        name: Typically ``__name__`` of the calling module.
        level: Optional override for the log level (defaults to ``logging.DEBUG``).

    Returns:
        A configured :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    resolved_level = level if level is not None else logging.DEBUG
    logger.setLevel(resolved_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(resolved_level)
    handler.setFormatter(
        _ColorFormatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
    )

    logger.addHandler(handler)
    logger.propagate = False

    return logger
