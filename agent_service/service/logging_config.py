"""agent_service 应用级日志：格式与 web/backend 一致，可通过环境变量调整。"""

from __future__ import annotations

import logging
import os
from logging.config import dictConfig

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
    http_level = (
        logging.INFO
        if os.getenv("LOG_HTTP", "").strip().lower() in ("1", "true", "yes")
        else logging.WARNING
    )

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
                "agent_service": {"level": level, "handlers": [], "propagate": True},
                "agent_service.http": {"level": level, "handlers": [], "propagate": True},
                "agent_service.explore": {"level": level, "handlers": [], "propagate": True},
                "agent_service.func_agent": {"level": level, "handlers": [], "propagate": True},
                "agent_service.midscene": {"level": level, "handlers": [], "propagate": True},
                "agent_service.tree": {"level": level, "handlers": [], "propagate": True},
                "agent_service.analysis": {"level": level, "handlers": [], "propagate": True},
                "langchain_platform": {"level": level, "handlers": [], "propagate": True},
                "analysis_agent": {"level": level, "handlers": [], "propagate": True},
                "autoglm_phone_tech": {"level": level, "handlers": [], "propagate": True},
                "httpx": {"level": http_level, "handlers": [], "propagate": True},
                "httpcore": {"level": http_level, "handlers": [], "propagate": True},
            },
        },
    )

    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "fastapi",
        "starlette",
        "agent_service",
        "agent_service.http",
        "langchain_platform",
        "analysis_agent",
        "autoglm_phone_tech",
    ):
        logging.getLogger(name).setLevel(level)

    logging.getLogger(__name__).info(
        "日志已初始化 level=%s format=%s LOG_HTTP=%s",
        logging.getLevelName(level),
        "detailed" if log_format == DEFAULT_LOG_FORMAT else "custom",
        http_level == logging.INFO,
    )
