"""Web 用例 KB Retriever（HTTP internal API）。"""
from __future__ import annotations

import logging

import httpx
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import Field

from agent_service.langchain_platform.config import web_internal_api_url, web_service_token

log = logging.getLogger(__name__)


class WebCaseKbRetriever(BaseRetriever):
    """通过 Web internal API 检索用例 KB。"""

    project_id: int | None = None
    owner_scope_ids: str | None = Field(
        default=None,
        description="逗号分隔 owner_id，供 internal API 租户过滤",
    )
    limit: int = 3

    def _get_relevant_documents(self, query: str, *, run_manager=None) -> list[Document]:
        q = (query or "").strip()
        if not q:
            return []

        token = web_service_token()
        if not token:
            log.debug("WEB_SERVICE_TOKEN 未配置，跳过 KB Retriever")
            return []

        url = f"{web_internal_api_url()}/api/internal/knowledge/cases/search"
        headers = {"Authorization": f"Bearer {token}"}
        params: dict = {"q": q, "limit": self.limit}
        if self.project_id is not None:
            params["project_id"] = self.project_id
        if self.owner_scope_ids:
            params["owner_scope_ids"] = self.owner_scope_ids

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            log.warning("WebCaseKbRetriever 请求失败: %s", exc)
            return []

        docs: list[Document] = []
        for item in data.get("items") or []:
            title = item.get("title") or ""
            snippet = (item.get("snippet") or title or "")[:600]
            body = f"【参考用例 {title}】\n{snippet}" if title else snippet
            docs.append(
                Document(
                    page_content=body,
                    metadata={"case_id": item.get("case_id"), "project_id": item.get("project_id")},
                )
            )
        return docs
