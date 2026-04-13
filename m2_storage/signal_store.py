"""
m2_storage/signal_store.py — 信号存储与检索（M2）

跨批次积累信号，支持时间范围查询和语义检索。
Phase 1：SQLite + 元数据过滤
Phase 2：加入向量索引（FAISS）

信号 Store 是整条 pipeline 的"记忆"：
  - 当批次信号不够时，可以从历史中检索相关信号
  - 回测时可以按时间范围加载特定时段的信号
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.schemas import MarketSignal, Market, SignalType

logger = logging.getLogger(__name__)

DB_FILE = Path(__file__).parent.parent / "data" / "signals" / "signal_store.db"


class SignalStore:
    """信号持久化存储与检索

    存储结构：SQLite，每条信号一行
    检索支持：
      - 按 batch_id 加载批次
      - 按时间范围加载
      - 按市场/信号类型过滤
      - 按信号标签模糊检索
    """

    def __init__(self, db_file: Optional[Path] = None):
        self.db_file = db_file or DB_FILE
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def save(self, signals: List[MarketSignal]) -> int:
        """批量保存信号，返回实际保存数（去重）"""
        saved = 0
        with self._conn() as conn:
            for sig in signals:
                try:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO signals
                          (signal_id, batch_id, signal_type, signal_label, description,
                           affected_markets, affected_instruments, signal_direction,
                           event_time, collected_time, time_horizon,
                           intensity_score, confidence_score, timeliness_score,
                           source_type, source_ref, raw_json)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            sig.signal_id,
                            sig.batch_id or "",
                            sig.signal_type.value,
                            sig.signal_label,
                            sig.description,
                            json.dumps([m.value for m in sig.affected_markets]),
                            json.dumps(sig.affected_instruments),
                            sig.signal_direction.value,
                            sig.event_time.isoformat() if sig.event_time else None,
                            sig.collected_time.isoformat() if sig.collected_time else None,
                            sig.time_horizon.value,
                            sig.intensity_score,
                            sig.confidence_score,
                            sig.timeliness_score,
                            sig.source_type.value,
                            sig.source_ref,
                            sig.model_dump_json(),
                        ),
                    )
                    saved += 1
                except sqlite3.IntegrityError:
                    pass  # 已存在，跳过

        logger.info(f"[M2] 保存信号 {saved}/{len(signals)} 条（去重后）")
        return saved

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------

    def get_by_batch(self, batch_id: str) -> List[MarketSignal]:
        """按批次 ID 加载所有信号"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT raw_json FROM signals WHERE batch_id = ?", (batch_id,)
            ).fetchall()
        return [MarketSignal.model_validate_json(r[0]) for r in rows]

    def get_by_time_range(
        self,
        start: datetime,
        end: datetime,
        markets: Optional[List[Market]] = None,
        signal_types: Optional[List[SignalType]] = None,
        min_intensity: int = 1,
    ) -> List[MarketSignal]:
        """按时间范围检索信号（用于回测和历史参考）

        Args:
            start: 开始时间（含）
            end: 结束时间（含）
            markets: 过滤市场（None = 全部）
            signal_types: 过滤信号类型（None = 全部）
            min_intensity: 最低强度分（默认 1）
        """
        query = """
            SELECT raw_json FROM signals
            WHERE event_time >= ? AND event_time <= ?
              AND intensity_score >= ?
        """
        params: list = [start.isoformat(), end.isoformat(), min_intensity]

        if signal_types:
            placeholders = ",".join(["?" for _ in signal_types])
            query += f" AND signal_type IN ({placeholders})"
            params.extend([st.value for st in signal_types])

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()

        signals = [MarketSignal.model_validate_json(r[0]) for r in rows]

        # 市场过滤（在 Python 层，因为 markets 是 JSON 数组）
        if markets:
            market_values = {m.value for m in markets}
            signals = [
                s for s in signals
                if any(m.value in market_values for m in s.affected_markets)
            ]

        logger.info(f"[M2] 检索 {start.date()}~{end.date()} | 结果={len(signals)} 条")
        return signals

    def search_by_label(self, keyword: str, limit: int = 20) -> List[MarketSignal]:
        """按标签/描述关键词模糊检索"""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT raw_json FROM signals
                WHERE signal_label LIKE ? OR description LIKE ?
                ORDER BY intensity_score DESC
                LIMIT ?
                """,
                (f"%{keyword}%", f"%{keyword}%", limit),
            ).fetchall()
        return [MarketSignal.model_validate_json(r[0]) for r in rows]

    def stats(self) -> dict:
        """信号库统计"""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
            by_type = conn.execute(
                "SELECT signal_type, COUNT(*) FROM signals GROUP BY signal_type"
            ).fetchall()
            by_batch = conn.execute(
                "SELECT batch_id, COUNT(*) FROM signals GROUP BY batch_id ORDER BY rowid DESC LIMIT 10"
            ).fetchall()
        return {
            "total": total,
            "by_signal_type": dict(by_type),
            "recent_batches": dict(by_batch),
        }

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    signal_id TEXT PRIMARY KEY,
                    batch_id TEXT,
                    signal_type TEXT,
                    signal_label TEXT,
                    description TEXT,
                    affected_markets TEXT,
                    affected_instruments TEXT,
                    signal_direction TEXT,
                    event_time TEXT,
                    collected_time TEXT,
                    time_horizon TEXT,
                    intensity_score INTEGER,
                    confidence_score INTEGER,
                    timeliness_score INTEGER,
                    source_type TEXT,
                    source_ref TEXT,
                    raw_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_event_time ON signals(event_time)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_batch_id ON signals(batch_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_signal_type ON signals(signal_type)")

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_file))
