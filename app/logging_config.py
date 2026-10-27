"""集中式日志配置。"""

from __future__ import annotations

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    """配置根日志器，避免重复添加 handler。"""

    root = logging.getLogger()
    root.setLevel(level.upper())

    if any(getattr(handler, "_a2ui_backend", False) for handler in root.handlers):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler._a2ui_backend = True
    root.addHandler(handler)

    # 降低第三方库噪音
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
