"""
PillSafe — Logging Utility
Configures a project-wide logger with file and console handlers.
"""

import logging
import os
from utils.config import get_config


def setup_logger(name: str = "pillsafe") -> logging.Logger:
    """Create and configure the PillSafe logger."""
    cfg = get_config()
    log_file = cfg.system.log_file
    log_level = getattr(logging, cfg.system.log_level.upper(), logging.INFO)

    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(log_level)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(log_file)
    fh.setLevel(log_level)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    import io
    import sys
    # Prefer a UTF-8 console stream so emoji/box-drawing characters in log
    # messages don't crash on Windows (cp1252). Fall back to the raw stdout
    # when its file descriptor isn't available (e.g. notebooks / pytest capture).
    try:
        console_stream = open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
    except (AttributeError, OSError, ValueError, io.UnsupportedOperation):
        console_stream = sys.stdout
    ch = logging.StreamHandler(stream=console_stream)
    ch.setLevel(log_level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger
