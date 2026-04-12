"""
Centralized logging for Pratibmb.

Both the Python server and CLI write to ~/.pratibmb/logs/pratibmb.log.
The Tauri desktop app writes to ~/.pratibmb/logs/tauri.log.

Users can view logs via:
  - CLI: pratibmb logs
  - Desktop: Help → Export Logs
  - Manual: open ~/.pratibmb/logs/
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def log_dir() -> Path:
    """Return the log directory, creating it if needed."""
    d = Path.home() / ".pratibmb" / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_file() -> Path:
    """Return the main Python log file path."""
    return log_dir() / "pratibmb.log"


def setup_logging(
    name: str = "pratibmb",
    level: int = logging.DEBUG,
    console: bool = True,
) -> logging.Logger:
    """Configure file + optional console logging. Call once at startup.

    Returns the configured logger. Subsequent calls with the same name
    return the existing logger without adding duplicate handlers.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(level)

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler — 5 MB max, keep 3 backups
    try:
        fh = RotatingFileHandler(
            log_file(),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        # Can't write to log file (permissions, disk full, etc.)
        # Fall through to console-only logging
        pass

    # Console handler — INFO and above
    if console:
        ch = logging.StreamHandler(sys.__stderr__)
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

    return logger


def redirect_print_to_log(logger: logging.Logger) -> None:
    """Redirect stdout/stderr so that print() calls also go to the log file.

    Existing print() calls throughout the codebase are captured without
    needing to rewrite them all to use logger.info().
    """
    sys.stdout = _LogStream(logger, logging.INFO, sys.__stdout__)
    sys.stderr = _LogStream(logger, logging.ERROR, sys.__stderr__)


class _LogStream:
    """File-like wrapper that tees writes to both a logger and the original stream."""

    def __init__(self, logger: logging.Logger, level: int, original):
        self.logger = logger
        self.level = level
        self.original = original
        self._buffer = ""

    def write(self, msg: str) -> int:
        # Always pass through to original stream (terminal/console)
        if self.original:
            try:
                self.original.write(msg)
            except (OSError, ValueError):
                pass

        # Buffer until we get a full line, then log it
        self._buffer += msg
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            stripped = line.strip()
            if stripped:
                # Avoid re-logging lines that the logging module itself produced
                if not stripped.startswith("[20"):
                    self.logger.log(self.level, line.rstrip())
        return len(msg)

    def flush(self) -> None:
        if self.original:
            try:
                self.original.flush()
            except (OSError, ValueError):
                pass
        # Flush any remaining buffer
        if self._buffer.strip():
            self.logger.log(self.level, self._buffer.rstrip())
            self._buffer = ""

    def fileno(self) -> int:
        if self.original:
            return self.original.fileno()
        raise OSError("no file descriptor")

    def isatty(self) -> bool:
        return False
