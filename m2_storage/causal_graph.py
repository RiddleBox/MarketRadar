"""
m2_storage/causal_graph.py — 因果图谱管理（M2 Phase 2）

存储和检索因果模式（CausalPattern），支持M3判断引擎进行因果链推理。

设计原则：
1. 模式是手工标注的领域知识，不是机器学习的结果
2. 每个模式定义：触发条件 → 因果链 → 预期结果
3. 支持按触发条件检索匹配的模式
4. 支持从M6复盘中提取新模式（未来）
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any

from core.schemas import CausalPattern

logger = logging.getLogger(__name__)

DB_FILE = Path(__file__).parent.parent / "data" / "signals" / "signal_store.db"


class CausalGraphManager:
    """因果图谱管理器
    
    功能：
    - 添加/更新/删除因果模式
    - 按pattern_id查询
    - 按触发条件关键词检索
    - 列出所有模式
    """

    def __init__(self, db_file: Optional[Path] = None):
        self.db_file = db_file or DB_FILE
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化因果图谱表"""
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS causal_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    precursor_signals TEXT NOT NULL,    -- JSON array
                    consequent_event TEXT NOT NULL,
                    probability REAL NOT NULL,
                    avg_lead_time_days INTEGER NOT NULL,
                    std_lead_time_days REAL,
                    supporting_cases TEXT,              -- JSON array
                    confidence REAL NOT NULL,
                    last_updated TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    notes TEXT,
                    raw_json TEXT NOT NULL
                )
            """)
            conn.commit()

    def _conn(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_file)

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def add_pattern(
        self,
        pattern_id: str,
        name: str,
        trigger_conditions: List[str],
        causal_chain: List[str],
        expected_outcomes: List[str],
        time_lag: str = "",
        confidence: float = 0.7,
        **kwargs,
    ) -> bool:
        """添加新的因果模式（简化接口）
        
        注意：这是简化接口，实际CausalPattern需要更多字段。
        完整字段请参考core/schemas.py中的CausalPattern定义。
        
        Args:
            pattern_id: 模式唯一标识
            name: 模式名称（用作precursor_signals的简化描述）
            trigger_conditions: 触发条件列表（映射到precursor_signals）
            causal_chain: 因果链条列表（暂存在notes）
            expected_outcomes: 预期结果列表（暂存在notes）
            time_lag: 时间滞后（映射到avg_lead_time_days）
            confidence: 置信度
        
        Returns:
            是否成功添加（False表示已存在）
        """
        # 解析time_lag为天数
        import re
        match = re.search(r'(\d+)', time_lag)
        avg_days = int(match.group(1)) if match else 7
        
        # 构建完整的CausalPattern对象
        from datetime import datetime, timezone
        pattern = CausalPattern(
            pattern_id=pattern_id,
            precursor_signals=trigger_conditions,
            consequent_event=name,
            probability=confidence,
            avg_lead_time_days=avg_days,
            std_lead_time_days=kwargs.get('std_lead_time_days', 2.0),
            supporting_cases=kwargs.get('supporting_cases', []),
            confidence=confidence,
            last_updated=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            notes=f"因果链: {' → '.join(causal_chain)}\n预期结果: {', '.join(expected_outcomes)}",
        )

        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO causal_patterns
                      (pattern_id, precursor_signals, consequent_event,
                       probability, avg_lead_time_days, std_lead_time_days,
                       supporting_cases, confidence, last_updated, created_at,
                       notes, raw_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        pattern.pattern_id,
                        json.dumps(pattern.precursor_signals, ensure_ascii=False),
                        pattern.consequent_event,
                        pattern.probability,
                        pattern.avg_lead_time_days,
                        pattern.std_lead_time_days,
                        json.dumps(pattern.supporting_cases, ensure_ascii=False),
                        pattern.confidence,
                        pattern.last_updated.isoformat(),
                        pattern.created_at.isoformat(),
                        pattern.notes,
                        pattern.model_dump_json(ensure_ascii=False),
                    ),
                )
                conn.commit()
            logger.info(f"[M2] 添加因果模式: {pattern_id}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"[M2] 因果模式已存在: {pattern_id}")
            return False

    def update_pattern(
        self,
        pattern_id: str,
        **updates: Any,
    ) -> bool:
        """更新现有模式的字段
        
        Args:
            pattern_id: 模式ID
            **updates: 要更新的字段
        
        Returns:
            是否成功更新
        """
        pattern = self.get_pattern(pattern_id)
        if not pattern:
            logger.warning(f"[M2] 模式不存在: {pattern_id}")
            return False

        # 更新字段
        for key, value in updates.items():
            if hasattr(pattern, key):
                setattr(pattern, key, value)

        # 更新last_updated
        from datetime import datetime, timezone
        pattern.last_updated = datetime.now(timezone.utc)

        with self._conn() as conn:
            conn.execute(
                """
                UPDATE causal_patterns
                SET precursor_signals=?, consequent_event=?,
                    probability=?, avg_lead_time_days=?, std_lead_time_days=?,
                    supporting_cases=?, confidence=?, last_updated=?,
                    notes=?, raw_json=?
                WHERE pattern_id=?
                """,
                (
                    json.dumps(pattern.precursor_signals, ensure_ascii=False),
                    pattern.consequent_event,
                    pattern.probability,
                    pattern.avg_lead_time_days,
                    pattern.std_lead_time_days,
                    json.dumps(pattern.supporting_cases, ensure_ascii=False),
                    pattern.confidence,
                    pattern.last_updated.isoformat(),
                    pattern.notes,
                    pattern.model_dump_json(ensure_ascii=False),
                    pattern_id,
                ),
            )
            conn.commit()

        logger.info(f"[M2] 更新因果模式: {pattern_id}")
        return True

    def delete_pattern(self, pattern_id: str) -> bool:
        """删除模式"""
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM causal_patterns WHERE pattern_id=?", (pattern_id,)
            )
            conn.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"[M2] 删除因果模式: {pattern_id}")
        else:
            logger.warning(f"[M2] 模式不存在: {pattern_id}")

        return deleted

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------

    def get_pattern(self, pattern_id: str) -> Optional[CausalPattern]:
        """按ID获取单个模式"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT raw_json FROM causal_patterns WHERE pattern_id=?",
                (pattern_id,),
            ).fetchone()

        if row:
            return CausalPattern.model_validate_json(row[0])
        return None

    def list_patterns(self) -> List[Dict[str, Any]]:
        """列出所有模式（简化版，用于统计）"""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT pattern_id, consequent_event, confidence, avg_lead_time_days
                FROM causal_patterns
                ORDER BY pattern_id
                """
            ).fetchall()

        return [
            {
                "pattern_id": row[0],
                "name": row[1],
                "confidence": row[2],
                "time_lag": f"{row[3]}天",
            }
            for row in rows
        ]

    def search_patterns(self, keywords: List[str]) -> List[CausalPattern]:
        """按关键词检索模式
        
        在precursor_signals、consequent_event、notes中搜索关键词
        
        Args:
            keywords: 关键词列表（如 ["降息", "股市"]）
        
        Returns:
            匹配的模式列表
        """
        if not keywords:
            return []

        # 构建SQL查询：任意字段包含任意关键词
        conditions = []
        params = []
        for kw in keywords:
            pattern = f"%{kw}%"
            conditions.append(
                "(precursor_signals LIKE ? OR consequent_event LIKE ? OR notes LIKE ?)"
            )
            params.extend([pattern, pattern, pattern])

        sql = f"""
            SELECT raw_json FROM causal_patterns
            WHERE {' OR '.join(conditions)}
            ORDER BY confidence DESC
        """

        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()

        patterns = [CausalPattern.model_validate_json(row[0]) for row in rows]
        logger.info(f"[M2] 检索到 {len(patterns)} 个匹配模式（关键词: {keywords}）")
        return patterns

    def get_all_patterns(self) -> List[CausalPattern]:
        """获取所有完整模式对象"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT raw_json FROM causal_patterns ORDER BY pattern_id"
            ).fetchall()

        return [CausalPattern.model_validate_json(row[0]) for row in rows]
