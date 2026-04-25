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

from core.schemas import MarketSignal, Market, SignalType, CausalPattern, CaseRecord

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
                            sig.collected_time.isoformat()
                            if sig.collected_time
                            else None,
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
                s
                for s in signals
                if any(m.value in market_values for m in s.affected_markets)
            ]

        logger.info(f"[M2] 检索 {start.date()}~{end.date()} | 结果={len(signals)} 条")
        return signals

    # ------------------------------------------------------------------
    # Causal Pattern Storage
    # ------------------------------------------------------------------

    def save_causal_pattern(self, pattern: CausalPattern) -> bool:
        """保存因果模式"""
        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO causal_patterns
                      (pattern_id, precursor_signals, consequent_event, probability,
                       avg_lead_time_days, std_lead_time_days, supporting_cases,
                       confidence, last_updated, created_at, notes, raw_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        pattern.pattern_id,
                        json.dumps(pattern.precursor_signals),
                        pattern.consequent_event,
                        pattern.probability,
                        pattern.avg_lead_time_days,
                        pattern.std_lead_time_days,
                        json.dumps(pattern.supporting_cases),
                        pattern.confidence,
                        pattern.last_updated.isoformat(),
                        pattern.created_at.isoformat(),
                        pattern.notes,
                        pattern.model_dump_json(),
                    ),
                )
            logger.info(f"[M2] 保存因果模式 {pattern.pattern_id}")
            return True
        except Exception as e:
            logger.error(f"[M2] 保存因果模式失败: {e}")
            return False

    def query_causal_patterns(
        self,
        consequent_event: Optional[str] = None,
        min_probability: float = 0.0,
        min_confidence: float = 0.0,
    ) -> List[CausalPattern]:
        """查询因果模式

        Args:
            consequent_event: 过滤后续事件（模糊匹配）
            min_probability: 最低概率
            min_confidence: 最低置信度
        """
        query = """
            SELECT raw_json FROM causal_patterns
            WHERE probability >= ? AND confidence >= ?
        """
        params: list = [min_probability, min_confidence]

        if consequent_event:
            query += " AND consequent_event LIKE ?"
            params.append(f"%{consequent_event}%")

        query += " ORDER BY probability DESC, confidence DESC"

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()

        patterns = [CausalPattern.model_validate_json(r[0]) for r in rows]
        logger.info(f"[M2] 查询因果模式 | 结果={len(patterns)} 条")
        return patterns

    # ------------------------------------------------------------------
    # Case Record Storage
    # ------------------------------------------------------------------

    def save_case_record(self, case: CaseRecord) -> bool:
        """保存案例记录"""
        try:
            with self._conn() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO case_records
                      (case_id, date_range_start, date_range_end, market,
                       signal_sequence, evolution, outcome, lessons, tags,
                       created_at, source, notes, raw_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        case.case_id,
                        case.date_range_start.isoformat(),
                        case.date_range_end.isoformat(),
                        case.market.value,
                        json.dumps(case.signal_sequence),
                        case.evolution,
                        json.dumps(case.outcome),
                        case.lessons,
                        json.dumps(case.tags),
                        case.created_at.isoformat(),
                        case.source,
                        case.notes,
                        case.model_dump_json(),
                    ),
                )
            logger.info(f"[M2] 保存案例记录 {case.case_id}")
            return True
        except Exception as e:
            logger.error(f"[M2] 保存案例记录失败: {e}")
            return False

    def query_similar_cases(
        self,
        tags: Optional[List[str]] = None,
        market: Optional[Market] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 10,
    ) -> List[CaseRecord]:
        """查询相似案例

        Args:
            tags: 标签过滤（任一匹配）
            market: 市场过滤
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回数量
        """
        query = "SELECT raw_json FROM case_records WHERE 1=1"
        params: list = []

        if market:
            query += " AND market = ?"
            params.append(market.value)

        if start_date:
            query += " AND date_range_start >= ?"
            params.append(start_date.isoformat())

        if end_date:
            query += " AND date_range_end <= ?"
            params.append(end_date.isoformat())

        query += " ORDER BY date_range_start DESC LIMIT ?"
        params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()

        cases = [CaseRecord.model_validate_json(r[0]) for r in rows]

        # Tag filtering in Python (JSON array)
        if tags:
            tag_set = set(tags)
            cases = [c for c in cases if any(t in tag_set for t in c.tags)]

        logger.info(f"[M2] 查询相似案例 | 结果={len(cases)} 条")
        return cases

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

    def query(
        self,
        markets: Optional[List[Market]] = None,
        limit: int = 100,
        lookback_days: int = 7,
    ) -> List[MarketSignal]:
        """按市场和最近N天检索信号（M3判断用）

        Args:
            markets: 过滤市场（None = 全部）
            limit: 返回数量
            lookback_days: 回溯天数
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(days=lookback_days)
        query_sql = """
            SELECT raw_json FROM signals
            WHERE event_time >= ?
            ORDER BY event_time DESC
            LIMIT ?
        """
        params: list = [cutoff.isoformat(), limit]

        with self._conn() as conn:
            rows = conn.execute(query_sql, params).fetchall()

        signals = [MarketSignal.model_validate_json(r[0]) for r in rows]

        # 市场过滤
        if markets:
            market_values = {m.value for m in markets}
            signals = [
                s
                for s in signals
                if any(m.value in market_values for m in s.affected_markets)
            ]

        logger.info(
            f"[M2] query | markets={[m.value for m in markets] if markets else 'all'} | lookback={lookback_days}d | results={len(signals)}"
        )
        return signals

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
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_event_time ON signals(event_time)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_batch_id ON signals(batch_id)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_signal_type ON signals(signal_type)"
            )

            # Causal patterns table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS causal_patterns (
                    pattern_id TEXT PRIMARY KEY,
                    precursor_signals TEXT,
                    consequent_event TEXT,
                    probability REAL,
                    avg_lead_time_days INTEGER,
                    std_lead_time_days REAL,
                    supporting_cases TEXT,
                    confidence REAL,
                    last_updated TEXT,
                    created_at TEXT,
                    notes TEXT,
                    raw_json TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_consequent_event ON causal_patterns(consequent_event)"
            )

            # Case records table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS case_records (
                    case_id TEXT PRIMARY KEY,
                    date_range_start TEXT,
                    date_range_end TEXT,
                    market TEXT,
                    signal_sequence TEXT,
                    evolution TEXT,
                    outcome TEXT,
                    lessons TEXT,
                    tags TEXT,
                    created_at TEXT,
                    source TEXT,
                    notes TEXT,
                    raw_json TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_case_date ON case_records(date_range_start)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_case_market ON case_records(market)"
            )

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_file))
