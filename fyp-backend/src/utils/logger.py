from __future__ import annotations

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

from ..settings import settings


def _ensure_utf8_stdout() -> None:
    if sys.platform != "win32":
        return

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def setup_logger(name: str = "fyp", level: int = logging.DEBUG) -> logging.Logger:
    settings.RESOLVED_LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if logger.handlers:
        return logger

    detailed_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    log_filename = settings.RESOLVED_LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = RotatingFileHandler(
        log_filename,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)

    _ensure_utf8_stdout()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str = "fyp") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    return setup_logger(name)


logger = setup_logger()


def debug(msg: str, *args, **kwargs) -> None:
    logger.debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs) -> None:
    logger.info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs) -> None:
    logger.warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs) -> None:
    logger.error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs) -> None:
    logger.critical(msg, *args, **kwargs)
