"""
tests/test_m8.py — M8 知识库测试

覆盖：
  1. 文档写入与检索
  2. 关键词搜索
  3. 元数据过滤
"""
import tempfile
from pathlib import Path

from m8_knowledge.knowledge_base import KnowledgeBase


class TestKnowledgeBase:
    def _make_kb(self, tmpdir):
        return KnowledgeBase(kb_file=Path(tmpdir) / "knowledge_base.json")

    def test_add_and_search(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kb = self._make_kb(tmpdir)
            doc_id = kb.add_document(
                content="半导体行业库存周期约3.5年，当前处于去库存阶段。",
                metadata={
                    "title": "半导体周期判断框架",
                    "category": "industry",
                    "content_type": "analytical_framework",
                    "market": "A_SHARE",
                    "tags": ["半导体", "周期", "库存"],
                    "trust_level": 4,
                    "source": "test",
                },
            )
            assert doc_id is not None

            results = kb.search("半导体")
            assert len(results) >= 1

    def test_metadata_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            kb = self._make_kb(tmpdir)
            kb.add_document(
                content="2015年股灾后证监会出台多项限制性措施",
                metadata={
                    "title": "A股政策干预梳理",
                    "category": "policy",
                    "content_type": "policy_context",
                    "market": "A_SHARE",
                    "tags": ["A股", "政策"],
                    "trust_level": 5,
                    "source": "test",
                },
            )
            kb.add_document(
                content="港股受美联储政策影响显著",
                metadata={
                    "title": "港股外资流动逻辑",
                    "category": "market_structure",
                    "content_type": "market_structure",
                    "market": "HK",
                    "tags": ["港股", "外资"],
                    "trust_level": 4,
                    "source": "test",
                },
            )

            results_a = kb.list_documents(filters={"market": "A_SHARE"})
            results_hk = kb.list_documents(filters={"market": "HK"})
            assert len(results_a) >= 1
            assert len(results_hk) >= 1
