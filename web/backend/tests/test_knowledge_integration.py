"""知识库 ingest / query 单元测试（无 MySQL 依赖）。"""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from app.knowledge.chunk_policy import (
    has_document_chunk_override,
    normalize_document_chunk_policy,
    resolve_chunk_policy,
)
from app.knowledge.ingestion.chunkers import build_embed_text, chunk_text
from app.knowledge.ingestion.parsers import parse_structured_json
from app.knowledge.query import service as query_service


class KnowledgeUnitTest(unittest.TestCase):
    def test_parse_page_model_and_chunk(self) -> None:
        raw = json.dumps(
            {
                "page_name": "购物车",
                "description": "展示已加购商品",
                "elements": [{"name": "结算按钮", "type": "button", "locator": "text=结算"}],
            },
            ensure_ascii=False,
        )
        text = parse_structured_json(raw, "page_model")
        self.assertIn("购物车", text)
        pairs = chunk_text(text, doc_type="page_model")
        self.assertGreaterEqual(len(pairs), 1)

    def test_document_chunk_policy_merge(self) -> None:
        from app.models import KnowledgeDocument, ProjectKnowledgeSettings

        db = MagicMock()
        doc = MagicMock()
        doc.chunk_policy_json = json.dumps({"max_chars": 500, "heading_aware": False})
        doc.project_id = 1
        doc.id = 9
        pks = MagicMock()
        pks.chunk_policy_json = "{}"

        def _query(model):
            m = MagicMock()
            if model is KnowledgeDocument:
                m.filter.return_value.first.return_value = doc
            elif model is ProjectKnowledgeSettings:
                m.filter.return_value.first.return_value = pks
            return m

        db.query.side_effect = _query
        policy = resolve_chunk_policy(db, 1, 9)
        self.assertEqual(policy["max_chars"], 500)
        self.assertFalse(policy["heading_aware"])
        self.assertTrue(has_document_chunk_override(doc.chunk_policy_json))
        stored = normalize_document_chunk_policy({"max_chars": 600, "search_min_score": 0.3})
        self.assertNotIn("search_min_score", stored)

    def test_chunk_by_heading_for_standard(self) -> None:
        text = "前言\n说明\n6.3 条件分支\n当用户点击添加时进入表单。\n6.4 其他\n内容"
        pairs = chunk_text(text, doc_type="standard", heading_aware=True, max_chars=800)
        paths = [p for p, _ in pairs]
        self.assertTrue(any("6.3" in p for p in paths))
        embed = build_embed_text(
            doc_title="测试规范",
            section_path="6.3 条件分支",
            content="当用户点击添加时进入表单。",
            policy={"prefix_title": True, "prefix_section": True},
        )
        self.assertIn("【文档】测试规范", embed)
        self.assertIn("【章节】6.3 条件分支", embed)

    @patch.object(query_service, "get_embed_model")
    @patch("app.knowledge.query.service.search_vectors")
    def test_knowledge_search_maps_chunks(self, mock_search, mock_embed) -> None:
        mock_embed.return_value = MagicMock(get_text_embedding=lambda _q: [0.0] * 4)
        mock_search.return_value = [
            {
                "chunk_id": 99,
                "document_id": 1,
                "collection_id": 2,
                "project_id": 3,
                "doc_type": "standard",
                "title": "登录规范",
                "score": 0.88,
            }
        ]
        db = MagicMock()
        chunk = MagicMock()
        chunk.id = 99
        chunk.document_id = 1
        chunk.content = "用户须先登录"
        chunk.section_path = ""
        doc = MagicMock()
        doc.doc_type = "standard"
        doc.title = "登录规范"

        def _query(model):
            m = MagicMock()
            m.filter.return_value.first.side_effect = [chunk, doc]
            return m

        db.query.side_effect = _query
        result = query_service.knowledge_search(db, query="登录", project_id=3, limit=2)
        self.assertEqual(len(result["items"]), 1)
        self.assertIn("登录", result["items"][0]["snippet"])

    @patch.object(query_service, "effective_search_min_score", return_value=0.6)
    @patch.object(query_service, "resolve_chunk_policy", return_value={})
    @patch.object(query_service, "get_embed_model")
    @patch("app.knowledge.query.service.search_vectors", return_value=[])
    def test_knowledge_search_respects_min_score(
        self, mock_search, mock_embed, _mock_policy, _mock_min_score
    ) -> None:
        mock_embed.return_value = MagicMock(get_text_embedding=lambda _q: [0.0] * 4)
        db = MagicMock()
        result = query_service.knowledge_search(db, query="联系人", project_id=3, limit=10)
        mock_search.assert_called_once()
        self.assertEqual(mock_search.call_args.kwargs["min_score"], 0.6)
        self.assertEqual(result["items"], [])
        self.assertEqual(result["min_score"], 0.6)


if __name__ == "__main__":
    unittest.main()
