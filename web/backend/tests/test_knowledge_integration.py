"""知识库 ingest / query 单元测试（无 MySQL 依赖）。"""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from app.knowledge.ingestion.chunkers import chunk_text
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


if __name__ == "__main__":
    unittest.main()
