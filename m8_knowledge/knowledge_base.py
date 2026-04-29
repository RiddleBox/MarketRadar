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

    def get_stock_history(self, stock_code: str, market: str) -> Optional[dict]:
        """
        获取标的历史表现（用于BranchManager）。

        Args:
            stock_code: 股票代码（如 "000651.SZ"）
            market: 市场（A_SHARE / HK / US）

        Returns:
            {
                "stock_code": str,
                "total_trades": int,
                "win_rate": float,  # 0.0~1.0
                "avg_return": float,  # 平均收益率
                "max_drawdown": float,  # 最大回撤
                "last_trade_date": str,
            }
            或 None（无历史数据）
        """
        # 搜索该标的的历史交易记录
        results = self.search(
            query=stock_code,
            filters={"market": market, "content_type": "case_record"},
            top_k=100,
            min_trust_level=1,
        )

        if not results:
            return None

        # 解析交易记录，计算统计数据
        trades = []
        for doc in results:
            content = doc["content"]
            # 简单解析：假设content包含 "收益率: +5.2%" 或 "收益率: -3.1%"
            if "收益率" in content:
                try:
                    # 提取收益率数字
                    import re
                    match = re.search(r"收益率[：:]\s*([+-]?\d+\.?\d*)%", content)
                    if match:
                        return_pct = float(match.group(1))
                        trades.append({
                            "return": return_pct,
                            "date": doc["metadata"].get("created_at", ""),
                        })
                except Exception:
                    continue

        if not trades:
            return None

        # 计算统计指标
        total_trades = len(trades)
        win_count = sum(1 for t in trades if t["return"] > 0)
        win_rate = win_count / total_trades if total_trades > 0 else 0.0
        avg_return = sum(t["return"] for t in trades) / total_trades if total_trades > 0 else 0.0
        max_drawdown = min((t["return"] for t in trades), default=0.0)
        last_trade_date = max((t["date"] for t in trades), default="")

        return {
            "stock_code": stock_code,
            "total_trades": total_trades,
            "win_rate": win_rate,
            "avg_return": avg_return,
            "max_drawdown": max_drawdown,
            "last_trade_date": last_trade_date,
        }

    def query_lessons(
        self,
        signal_type: str = None,
        instrument: str = None,
        limit: int = 5
    ) -> List[dict]:
        """
        查询历史教训（用于BranchManager）。

        Args:
            signal_type: 信号类型（如 "policy_change", "price_surge"）
            instrument: 标的代码（如 "000001.SZ"）
            limit: 返回数量

        Returns:
            [
                {
                    "signal_type": str,
                    "win_rate": float,  # 0.0~1.0
                    "avg_pnl": float,  # 平均盈亏
                    "sample_size": int,
                    "recommendation": str,
                },
                ...
            ]
        """
        # 构建查询
        query_parts = []
        if signal_type:
            query_parts.append(signal_type)
        if instrument:
            query_parts.append(instrument)

        if not query_parts:
            return []

        query = " ".join(query_parts)

        # 搜索相关案例
        results = self.search(
            query=query,
            filters={"content_type": "mini_review"},
            top_k=limit * 5,  # 多取一些，后续聚合
            min_trust_level=1,
        )

        if not results:
            return []

        # 按signal_type聚合统计
        stats_by_type: Dict[str, List[float]] = {}

        for doc in results:
            try:
                # 解析JSON内容
                content = json.loads(doc["content"])
                sig_type = content.get("signal_type", "unknown")
                pnl = content.get("realized_pnl_pct", 0.0)

                if sig_type not in stats_by_type:
                    stats_by_type[sig_type] = []
                stats_by_type[sig_type].append(pnl)

            except Exception as e:
                logger.warning(f"[M8] 解析教训失败: {e}")
                continue

        # 生成教训列表
        lessons = []
        for sig_type, pnls in stats_by_type.items():
            sample_size = len(pnls)
            if sample_size == 0:
                continue

            win_count = sum(1 for p in pnls if p > 0)
            win_rate = win_count / sample_size
            avg_pnl = sum(pnls) / sample_size

            # 生成建议
            if win_rate < 0.4:
                recommendation = f"此类信号({sig_type})胜率低({win_rate:.1%})，建议降低权重或观察"
            elif win_rate > 0.6:
                recommendation = f"此类信号({sig_type})胜率高({win_rate:.1%})，可继续使用"
            else:
                recommendation = f"此类信号({sig_type})胜率中等({win_rate:.1%})，谨慎使用"

            lessons.append({
                "signal_type": sig_type,
                "win_rate": win_rate,
                "avg_pnl": avg_pnl,
                "sample_size": sample_size,
                "recommendation": recommendation,
            })

        # 按样本量排序，返回top N
        lessons.sort(key=lambda x: x["sample_size"], reverse=True)
        return lessons[:limit]

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
