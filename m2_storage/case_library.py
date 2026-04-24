"""
m2_storage/case_library.py — 历史案例库管理（M2 Phase 3）

存储和检索历史案例（CaseRecord），支持M3判断引擎进行案例推理。

设计原则：
1. 案例是真实历史事件的完整记录：信号组合 → 演化过程 → 最终结果
2. 每个案例包含归因分析：哪些因素起作用、哪些失效
3. 支持按信号特征检索相似案例
4. 支持从M6复盘中自动生成案例（未来）
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from core.schemas import CaseRecord, Market

logger = logging.getLogger(__name__)

DB_FILE = Path(__file__).parent.parent / "data" / "signals" / "signal_store.db"


class CaseLibraryManager:
    """历史案例库管理器
    
    功能：
    - 添加/更新/删除历史案例
    - 按case_id查询
    - 按信号特征检索相似案例
    - 列出所有案例
    """

    def __init__(self, db_file: Optional[Path] = None):
        self.db_file = db_file or DB_FILE
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化案例库表"""
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS case_records (
                    case_id TEXT PRIMARY KEY,
                    date_range_start TEXT NOT NULL,
                    date_range_end TEXT NOT NULL,
                    market TEXT NOT NULL,
                    signal_sequence TEXT NOT NULL,  -- JSON array
                    evolution TEXT NOT NULL,
                    outcome TEXT NOT NULL,          -- JSON dict
                    lessons TEXT NOT NULL,
                    tags TEXT,                      -- JSON array
                    created_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    notes TEXT,
                    raw_json TEXT NOT NULL
                )
            """)
            # 为tags创建索引，加速检索
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_case_tags
                ON case_records(tags)
            """)
            conn.commit()

    def _conn(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_file)

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def add_case(
        self,
        case_id: str,
        date_range_start: datetime,
        date_range_end: datetime,
        market: Market,
        signal_sequence: List[str],
        evolution: str,
        outcome: dict,
        lessons: str,
        tags: List[str] = None,
        source: str = "manual",
        notes: str = None,
    ) -> bool:
        """添加新的历史案例
        
        Args:
            case_id: 案例唯一标识
            date_range_start: 起始日期
            date_range_end: 结束日期
            market: 相关市场（Market枚举）
            signal_sequence: 信号序列
            evolution: 演化过程描述
            outcome: 结果字典
            lessons: 经验教训
            tags: 标签列表
            source: 来源（manual/m6_retrospective）
            notes: 备注
        
        Returns:
            是否成功添加（False表示已存在）
        """
        case = CaseRecord(
            case_id=case_id,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            market=market,
            signal_sequence=signal_sequence,
            evolution=evolution,
            outcome=outcome,
            lessons=lessons,
            tags=tags or [],
            created_at=datetime.now(),
            source=source,
            notes=notes,
        )

        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT INTO case_records
                      (case_id, date_range_start, date_range_end, market,
                       signal_sequence, evolution, outcome, lessons,
                       tags, created_at, source, notes, raw_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        case.case_id,
                        case.date_range_start.isoformat(),
                        case.date_range_end.isoformat(),
                        case.market.value,
                        json.dumps(case.signal_sequence, ensure_ascii=False),
                        case.evolution,
                        json.dumps(case.outcome, ensure_ascii=False),
                        case.lessons,
                        json.dumps(case.tags, ensure_ascii=False),
                        case.created_at.isoformat(),
                        case.source,
                        case.notes,
                        case.model_dump_json(ensure_ascii=False),
                    ),
                )
                conn.commit()
            logger.info(f"[M2] 添加历史案例: {case_id}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"[M2] 案例已存在: {case_id}")
            return False

    def delete_case(self, case_id: str) -> bool:
        """删除案例"""
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM case_records WHERE case_id=?", (case_id,)
            )
            conn.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"[M2] 删除案例: {case_id}")
        else:
            logger.warning(f"[M2] 案例不存在: {case_id}")

        return deleted

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------

    def get_case(self, case_id: str) -> Optional[CaseRecord]:
        """按ID获取单个案例"""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT raw_json FROM case_records WHERE case_id=?",
                (case_id,),
            ).fetchone()

        if row:
            return CaseRecord.model_validate_json(row[0])
        return None

    def list_cases(self) -> List[Dict[str, Any]]:
        """列出所有案例（简化版，用于统计）"""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT case_id, date_range_start, date_range_end, market
                FROM case_records
                ORDER BY date_range_start DESC
                """
            ).fetchall()

        return [
            {
                "case_id": row[0],
                "date_range": f"{row[1]} ~ {row[2]}",
                "market": row[3],
            }
            for row in rows
        ]

    def search_cases(self, keywords: List[str]) -> List[CaseRecord]:
        """按关键词检索案例
        
        在signal_sequence、evolution、lessons中搜索关键词
        
        Args:
            keywords: 关键词列表（如 ["降息", "股市", "反弹"]）
        
        Returns:
            匹配的案例列表
        """
        if not keywords:
            return []

        # 构建SQL查询：任意字段包含任意关键词
        conditions = []
        params = []
        for kw in keywords:
            pattern = f"%{kw}%"
            conditions.append(
                "(signal_sequence LIKE ? OR evolution LIKE ? OR lessons LIKE ? OR tags LIKE ?)"
            )
            params.extend([pattern, pattern, pattern, pattern])

        sql = f"""
            SELECT raw_json FROM case_records
            WHERE {' OR '.join(conditions)}
            ORDER BY date_range_start DESC
        """

        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()

        cases = [CaseRecord.model_validate_json(row[0]) for row in rows]
        logger.info(f"[M2] 检索到 {len(cases)} 个匹配案例（关键词: {keywords}）")
        return cases

    def get_all_cases(self) -> List[CaseRecord]:
        """获取所有完整案例对象"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT raw_json FROM case_records ORDER BY date_range_start DESC"
            ).fetchall()

        return [CaseRecord.model_validate_json(row[0]) for row in rows]

    def search_by_signals(self, signal_keywords: List[str]) -> List[CaseRecord]:
        """按信号特征检索相似案例
        
        专门在signal_sequence字段中搜索，用于M3判断引擎查找相似历史案例
        
        Args:
            signal_keywords: 信号关键词列表（如 ["央行降息", "流动性宽松"]）
        
        Returns:
            匹配的案例列表，按时间倒序排序
        """
        if not signal_keywords:
            return []

        # 构建SQL查询：signal_sequence包含任意关键词
        conditions = []
        params = []
        for kw in signal_keywords:
            pattern = f"%{kw}%"
            conditions.append("signal_sequence LIKE ?")
            params.append(pattern)

        sql = f"""
            SELECT raw_json FROM case_records
            WHERE {' OR '.join(conditions)}
            ORDER BY date_range_start DESC
        """

        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()

        cases = [CaseRecord.model_validate_json(row[0]) for row in rows]
        logger.info(f"[M2] 按信号检索到 {len(cases)} 个相似案例")
        return cases
