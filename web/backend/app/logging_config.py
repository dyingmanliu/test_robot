"""应用级日志：默认 INFO，含毫秒时间戳；可通过环境变量调整级别与格式。"""

from __future__ import annotations

import logging
import os
from logging.config import dictConfig

# 详细格式：时间(毫秒) | 级别 | 模块 | 文件:行号 | 消息
DEFAULT_LOG_FORMAT = (
    "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | "
    "%(filename)s:%(lineno)d | %(message)s"
)
SIMPLE_LOG_FORMAT = "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | %(message)s"


def _resolve_level() -> int:
    raw = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    return getattr(logging, raw, logging.INFO)


def _resolve_format() -> str:
    mode = (os.getenv("LOG_FORMAT", "detailed") or "detailed").strip().lower()
    if mode in ("simple", "brief"):
        return SIMPLE_LOG_FORMAT
    if mode == "custom" and (custom := os.getenv("LOG_FORMAT_TEMPLATE", "").strip()):
        return custom
    return DEFAULT_LOG_FORMAT


def configure_logging() -> None:
    level = _resolve_level()
    log_format = _resolve_format()
    sql_level = logging.INFO if os.getenv("LOG_SQL", "").strip().lower() in ("1", "true", "yes") else logging.WARNING

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": log_format,
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": level,
                "handlers": ["console"],
            },
            "loggers": {
                "uvicorn": {"level": level, "handlers": [], "propagate": True},
                "uvicorn.error": {"level": level, "handlers": [], "propagate": True},
                "uvicorn.access": {"level": level, "handlers": [], "propagate": True},
                "fastapi": {"level": level, "handlers": [], "propagate": True},
                "starlette": {"level": level, "handlers": [], "propagate": True},
                "app": {"level": level, "handlers": [], "propagate": True},
                "app.http": {"level": level, "handlers": [], "propagate": True},
                "app.executor": {"level": level, "handlers": [], "propagate": True},
                "app.case_generation": {"level": level, "handlers": [], "propagate": True},
                "analysis_agent": {"level": level, "handlers": [], "propagate": True},
                "autoglm_phone_tech": {"level": level, "handlers": [], "propagate": True},
                "sqlalchemy.engine": {"level": sql_level, "handlers": [], "propagate": True},
            },
        },
    )

    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
        "starlette",
        "app",
        "app.llm",
        "mai_ui.llm",
    ):
        logging.getLogger(name).setLevel(level)

    logging.getLogger(__name__).info(
        "日志已初始化 level=%s format=%s LOG_SQL=%s",
        logging.getLevelName(level),
        "detailed" if log_format == DEFAULT_LOG_FORMAT else "custom",
        sql_level == logging.INFO,
    )
