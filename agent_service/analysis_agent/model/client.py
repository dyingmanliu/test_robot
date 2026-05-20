"""OpenAI 兼容非流式客户端（用例 JSON 生成）。"""

from __future__ import annotations

import logging
import os
import socket
import time
from urllib.parse import urlparse

import httpx
from openai import APIConnectionError, APITimeoutError, OpenAI

from agent_service.analysis_agent.config import AnalysisAgentConfig
from agent_service.analysis_agent.errors import AnalysisAgentError

log = logging.getLogger(__name__)

# SDK 内置重试后仍失败时，再额外退避重试（应对偶发网络抖动）
_EXTRA_RETRIES = 3
_RETRY_BASE_SEC = 1.0

_DNS_HINT_MARKERS = (
    "nodename nor servname",
    "Name or service not known",
    "getaddrinfo failed",
    "EAI_NONAME",
)


def _connection_error_message(config: AnalysisAgentConfig, err: Exception) -> str:
    cause = getattr(err, "__cause__", None) or getattr(err, "__context__", None)
    cause_s = repr(cause) if cause else str(err)
    host_hint = (config.base_url or "").replace("https://", "").replace("http://", "").split("/")[0]
    if any(m in cause_s for m in _DNS_HINT_MARKERS):
        return (
            f"无法解析模型服务域名（{host_hint or config.base_url}），DNS 查询失败。"
            f"请在本机终端执行 nslookup {host_hint} 检查；可尝试更换 DNS（如 114.114.114.114）、"
            f"关闭 VPN/代理，或暂时改用 DeepSeek/智谱等其它 CASE_GEN_BASE_URL。"
            f"详情：{cause or err}"
        )
    return (
        f"无法连接模型服务（{config.base_url}，模型 {config.model_name}）。"
        f"请检查本机网络、代理/VPN 能否访问该地址后重试；若为偶发故障可直接再点「生成」。"
        f"详情：{err}"
    )


def _api_host(base_url: str) -> str:
    return (urlparse(base_url).hostname or "").strip()


def _preflight_dns(host: str) -> None:
    """请求前解析域名；失败时尽早给出 DNS 提示（与 httpx 报错一致）。"""
    if not host:
        return
    socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)


def _http_trust_env() -> bool:
    """默认不读系统 HTTP_PROXY，避免本机代理配置错误导致 Connection error。"""
    return os.getenv("CASE_GEN_HTTP_TRUST_ENV", "").strip().lower() in ("1", "true", "yes")


class AnalysisModelClient:
    def __init__(self, config: AnalysisAgentConfig) -> None:
        self.config = config
        timeout = httpx.Timeout(config.timeout_sec, connect=min(30.0, config.timeout_sec))
        http_client = httpx.Client(trust_env=_http_trust_env(), timeout=timeout)
        self._client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout_sec,
            max_retries=2,
            http_client=http_client,
        )

    def chat(self, messages: list[dict[str, str]]) -> str:
        log.debug(
            "chat.completions model=%s messages=%s",
            self.config.model_name,
            len(messages),
        )
        host = _api_host(self.config.base_url)
        last_err: Exception | None = None
        for attempt in range(_EXTRA_RETRIES):
            try:
                try:
                    _preflight_dns(host)
                except OSError as dns_err:
                    raise AnalysisAgentError(
                        _connection_error_message(self.config, dns_err)
                    ) from dns_err
                resp = self._client.chat.completions.create(
                    model=self.config.model_name,
                    messages=messages,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    timeout=self.config.timeout_sec,
                )
                last_err = None
                break
            except (APIConnectionError, APITimeoutError) as e:
                last_err = e
                cause = getattr(e, "__cause__", None) or getattr(e, "__context__", None)
                log.warning(
                    "analysis_agent LLM connection attempt %s/%s failed: %s%s",
                    attempt + 1,
                    _EXTRA_RETRIES,
                    e,
                    f" | cause={cause!r}" if cause else "",
                )
                if attempt < _EXTRA_RETRIES - 1:
                    time.sleep(_RETRY_BASE_SEC * (2**attempt))
            except Exception as e:
                log.warning("analysis_agent LLM call failed: %s", e)
                raise AnalysisAgentError(f"调用大模型失败：{e}") from e
        if last_err is not None:
            log.warning("analysis_agent LLM call failed after retries: %s", last_err)
            raise AnalysisAgentError(_connection_error_message(self.config, last_err)) from last_err
        content = resp.choices[0].message.content if resp.choices else None
        if not content or not str(content).strip():
            raise AnalysisAgentError("模型返回为空")
        return str(content)
