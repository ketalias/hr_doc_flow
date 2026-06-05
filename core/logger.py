"""Logging configuration. Call get_logger() once at startup; reuse it everywhere."""

import logging
import os
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

# Shared Console instance — import this in ui.py so all output goes to one stream.
console = Console()

_LOG_DIR = Path("logs")


def get_logger(name: str = "hr_doc_flow") -> logging.Logger:
    """
    Return a configured logger backed by Rich (console) and a plain-text file.

    Safe to call multiple times — handlers are added only on the first call.
    Log level is read from the LOG_LEVEL environment variable (default: INFO).
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)

    # ── Console handler (Rich) ─────────────────────────────────────────────
    rich_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        markup=True,           # allows [bold], [green], etc. in log messages
        show_path=False,
        log_time_format="[%H:%M:%S]",
    )
    rich_handler.setLevel(level)
    logger.addHandler(rich_handler)

    # ── File handler (plain UTF-8) ─────────────────────────────────────────
    _LOG_DIR.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(
        _LOG_DIR / "hr_doc_flow.log", encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(file_handler)

    return logger
