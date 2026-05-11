"""功能测试下发任务写入 Kafka：供 Agent 管理服务消费并分配给「功能测试执行数字机器人」。"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

log = logging.getLogger(__name__)

try:
    from kafka import KafkaProducer
except ImportError:
    KafkaProducer = None  # type: ignore[misc, assignment]

_producer: Any = None


def _get_producer():
    global _producer
    if KafkaProducer is None:
        return None
    brokers = (os.getenv("KAFKA_BOOTSTRAP_SERVERS") or "").strip()
    if not brokers:
        return None
    if _producer is None:
        _producer = KafkaProducer(
            bootstrap_servers=[b.strip() for b in brokers.split(",") if b.strip()],
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
            key_serializer=lambda k: k if isinstance(k, bytes) else str(k).encode("utf-8"),
            acks="all",
            request_timeout_ms=15000,
            retries=3,
        )
    return _producer


def publish_functional_dispatch(
    payload: dict[str, Any],
) -> tuple[bool, Optional[str], Optional[str], Optional[int]]:
    """投递调度消息。返回 (是否投递成功, topic, err_message, partition_offset)。"""
    topic = (os.getenv("KAFKA_FUNCTIONAL_DISPATCH_TOPIC") or "functional-test-dispatch").strip()
    prod = _get_producer()
    if prod is None:
        log.info(
            "Kafka 未配置（未安装 kafka-python 或未设置 KAFKA_BOOTSTRAP_SERVERS），任务仅在库内排队：task_id=%s",
            payload.get("task_id"),
        )
        return False, None, None, None
    key = str(payload.get("task_id", "")).encode("utf-8")
    try:
        fut = prod.send(topic, value=payload, key=key)
        md = fut.get(timeout=15)
        off = int(md.offset) if md is not None else None
        log.info(
            "Kafka 投递成功 topic=%s partition=%s offset=%s task_id=%s",
            md.topic if md else topic,
            getattr(md, "partition", None),
            off,
            payload.get("task_id"),
        )
        return True, topic, None, off
    except Exception as e:
        msg = str(e)
        log.exception("Kafka 投递失败 task_id=%s", payload.get("task_id"))
        return False, topic, msg, None
