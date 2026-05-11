"""应用级日志：默认 INFO，可通过环境变量 LOG_LEVEL 调整。"""

from __future__ import annotations

import logging
import os
import sys


def configure_logging() -> None:
    raw = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, raw, logging.INFO)

    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
    else:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            stream=sys.stdout,
        )

    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
        "starlette",
        "app",
    ):
        logging.getLogger(name).setLevel(level)

    # SQL 语句默认不因 INFO 刷屏；需要时可设 LOG_LEVEL=DEBUG 或单独提高 sqlalchemy.engine
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
