"""
m8_knowledge/knowledge_base.py — RAG 知识库

Phase 1：本地 JSON 存储 + 简单关键词检索
Phase 2：接入向量索引（FAISS + sentence-transformers）

设计原则见 PRINCIPLES.md。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

KB_FILE = Path(__file__).parent / "data" / "knowledge_base.json"


class KnowledgeBase:
    """知识库

    初期使用 JSON 文件存储 + 关键词检索。
    接口设计兼容后续向量检索替换。
    """

    def __init__(self, kb_file: Optional[Path] = None):
        self.kb_file = kb_file or KB_FILE
        self.kb_file.parent.mkdir(parents=True, exist_ok=True)
        self._documents: Dict[str, dict] = {}
        self._load()

    def add_document(
        self,
        content: str,
        metadata: dict,
    ) -> str:
        """添加知识文档

        Args:
            content: 文档内容（Markdown 格式）
            metadata: {
                "title": str,
                "market": str,          # A_SHARE / HK / US / CROSS_MARKET
                "category": str,        # valuation / macro / industry / event / ...
                "content_type": str,    # case_record / analytical_framework / ...
                "tags": List[str],
                "trust_level": int,     # 1-5
                "source": str,          # 来源说明
            }

        Returns:
            doc_id
        """
        doc_id = f"kb_{uuid.uuid4().hex[:8]}"
        self._documents[doc_id] = {
            "doc_id": doc_id,
            "content": content,
            "metadata": {
                "title": metadata.get("title", ""),
                "market": metadata.get("market", "CROSS_MARKET"),
                "category": metadata.get("category", ""),
                "content_type": metadata.get("content_type", ""),
                "tags": metadata.get("tags", []),
                "trust_level": metadata.get("trust_level", 3),
                "source": metadata.get("source", ""),
                "created_at": datetime.now().isoformat(),
            },
        }
        self._save()
        logger.info(f"[M8] 添加文档 | id={doc_id} title={metadata.get('title', '')}")
        return doc_id

    def search(
        self,
        query: str,
        filters: Optional[dict] = None,
        top_k: int = 5,
        min_trust_level: int = 1,
    ) -> List[dict]:
        """检索知识文档

        Args:
            query: 检索查询词
            filters: {
                "market": str,          # 过滤市场
                "category": str,        # 过滤类别
                "content_type": str,    # 过滤内容类型
            }
            top_k: 返回最多 N 条
            min_trust_level: 最低信任度（1-5）

        Returns:
            [{"doc_id", "content", "metadata", "score"}, ...]
        """
        candidates = list(self._documents.values())

        # 元数据过滤
        if filters:
            if "market" in filters:
                candidates = [
                    d for d in candidates
                    if d["metadata"].get("market") in (filters["market"], "CROSS_MARKET")
                ]
            if "category" in filters:
                candidates = [
                    d for d in candidates
                    if d["metadata"].get("category") == filters["category"]
                ]
            if "content_type" in filters:
                candidates = [
                    d for d in candidates
                    if d["metadata"].get("content_type") == filters["content_type"]
                ]

        # 信任度过滤
        candidates = [
            d for d in candidates
            if d["metadata"].get("trust_level", 1) >= min_trust_level
        ]

        # 简单关键词评分（Phase 1 实现）
        query_terms = query.lower().split()
        scored = []
        for doc in candidates:
            text = (doc["content"] + " " + " ".join(doc["metadata"].get("tags", []))).lower()
            score = sum(1 for term in query_terms if term in text)
            if score > 0:
                scored.append({**doc, "score": score})

        # 按分数排序
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def get_document(self, doc_id: str) -> Optional[dict]:
        return self._documents.get(doc_id)

    def list_documents(self, filters: Optional[dict] = None) -> List[dict]:
        docs = list(self._documents.values())
        if filters:
            if "market" in filters:
                docs = [d for d in docs if d["metadata"].get("market") == filters["market"]]
            if "content_type" in filters:
                docs = [d for d in docs if d["metadata"].get("content_type") == filters["content_type"]]
        return docs

    def delete_document(self, doc_id: str) -> bool:
        if doc_id in self._documents:
            del self._documents[doc_id]
            self._save()
            return True
        return False

    def stats(self) -> dict:
        total = len(self._documents)
        by_type: Dict[str, int] = {}
        by_market: Dict[str, int] = {}
        for doc in self._documents.values():
            ct = doc["metadata"].get("content_type", "unknown")
            mkt = doc["metadata"].get("market", "unknown")
            by_type[ct] = by_type.get(ct, 0) + 1
            by_market[mkt] = by_market.get(mkt, 0) + 1
        return {"total": total, "by_content_type": by_type, "by_market": by_market}

    def _load(self):
        if self.kb_file.exists():
            try:
                data = json.loads(self.kb_file.read_text(encoding="utf-8"))
                for item in data:
                    self._documents[item["doc_id"]] = item
                logger.info(f"[M8] 加载知识库 {len(self._documents)} 条文档")
            except Exception as e:
                logger.error(f"[M8] 加载知识库失败: {e}")

    def _save(self):
        data = list(self._documents.values())
        self.kb_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
