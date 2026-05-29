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

    import sys
    ch = logging.StreamHandler(stream=open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False))
    ch.setLevel(log_level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger
