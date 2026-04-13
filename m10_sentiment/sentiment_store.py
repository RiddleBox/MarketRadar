"""
m10_sentiment/sentiment_store.py — 情绪历史数据库

基于 SQLite，记录每次情绪采集快照的关键指标。
支持：
  - 时序查询（按日期范围）
  - 极值检测（找历史情绪极值）
  - 情绪趋势计算（近 N 次均值/斜率）
  - 与价格数据对比（验证情绪反转有效性）
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "sentiment" / "sentiment_history.db"


class SentimentStore:
    """
    情绪历史数据库。

    表结构：
        sentiment_snapshots (
            id              INTEGER PRIMARY KEY,
            snapshot_time   TEXT NOT NULL,
            batch_id        TEXT,
            fear_greed      REAL,          -- 0~100
            label           TEXT,          -- 极度贪婪/贪婪/...
            direction       TEXT,          -- BULLISH/NEUTRAL/BEARISH
            northbound_flow REAL,          -- 北向净流入（亿）
            adr             REAL,          -- 涨跌比
            avg_score       REAL,          -- 均综合得分
            high_score_cnt  INTEGER,
            is_extreme      INTEGER,       -- 0/1
            raw_json        TEXT           -- 完整原始数据
        )
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sentiment_snapshots (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_time   TEXT NOT NULL,
                    batch_id        TEXT,
                    fear_greed      REAL,
                    label           TEXT,
                    direction       TEXT,
                    northbound_flow REAL,
                    adr             REAL,
                    avg_score       REAL,
                    high_score_cnt  INTEGER,
                    is_extreme      INTEGER DEFAULT 0,
                    raw_json        TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_snapshot_time
                ON sentiment_snapshots(snapshot_time)
            """)
            conn.commit()

    def save(self, snapshot_data: dict) -> int:
        """保存一条情绪快照，返回 id"""
        fg = float(snapshot_data.get("fear_greed_score", 50))
        is_extreme = 1 if fg >= 80 or fg <= 20 else 0
        row = (
            snapshot_data.get("snapshot_time", datetime.now().isoformat()),
            snapshot_data.get("batch_id", ""),
            fg,
            snapshot_data.get("sentiment_label", ""),
            snapshot_data.get("direction", "NEUTRAL"),
            float(snapshot_data.get("northbound_net_flow", 0)),
            float(snapshot_data.get("advance_decline_ratio", 0)),
            float(snapshot_data.get("avg_comprehensive_score", 50)),
            int(snapshot_data.get("high_score_count", 0)),
            is_extreme,
            json.dumps(snapshot_data, ensure_ascii=False),
        )
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("""
                INSERT INTO sentiment_snapshots
                    (snapshot_time, batch_id, fear_greed, label, direction,
                     northbound_flow, adr, avg_score, high_score_cnt, is_extreme, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, row)
            conn.commit()
            return cur.lastrowid

    def latest(self, n: int = 1) -> List[dict]:
        """最近 n 条快照"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM sentiment_snapshots ORDER BY snapshot_time DESC LIMIT ?",
                (n,)
            ).fetchall()
        return [dict(r) for r in rows]

    def query_range(self, start: datetime, end: datetime) -> List[dict]:
        """按时间范围查询"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM sentiment_snapshots WHERE snapshot_time BETWEEN ? AND ? "
                "ORDER BY snapshot_time",
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        return [dict(r) for r in rows]

    def find_extremes(self, threshold_high: float = 80, threshold_low: float = 20) -> List[dict]:
        """找历史极值点"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM sentiment_snapshots "
                "WHERE fear_greed >= ? OR fear_greed <= ? "
                "ORDER BY snapshot_time DESC LIMIT 50",
                (threshold_high, threshold_low),
            ).fetchall()
        return [dict(r) for r in rows]

    def trend(self, n: int = 10) -> dict:
        """
        计算最近 n 次情绪趋势。

        Returns:
            {
                "avg_score": float,
                "slope": float,      # >0 趋势向上，<0 向下
                "current": float,
                "prev": float,
                "is_rising": bool,
                "count": int,
            }
        """
        rows = self.latest(n)
        if not rows:
            return {"avg_score": 50.0, "slope": 0.0, "current": 50.0, "prev": 50.0,
                    "is_rising": False, "count": 0}

        scores = [r["fear_greed"] for r in rows]
        scores.reverse()  # 按时间正序
        avg = sum(scores) / len(scores)
        slope = 0.0
        if len(scores) >= 2:
            # 简单线性回归斜率
            n_pts = len(scores)
            x_mean = (n_pts - 1) / 2
            num = sum((i - x_mean) * (s - avg) for i, s in enumerate(scores))
            den = sum((i - x_mean) ** 2 for i in range(n_pts))
            slope = num / den if den > 0 else 0.0

        return {
            "avg_score": round(avg, 2),
            "slope": round(slope, 3),
            "current": round(scores[-1], 2),
            "prev": round(scores[-2] if len(scores) >= 2 else scores[-1], 2),
            "is_rising": slope > 0,
            "count": len(scores),
        }

    def stats(self) -> dict:
        """数据库统计信息"""
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM sentiment_snapshots").fetchone()[0]
            extremes = conn.execute("SELECT COUNT(*) FROM sentiment_snapshots WHERE is_extreme=1").fetchone()[0]
            avg_fg = conn.execute("SELECT AVG(fear_greed) FROM sentiment_snapshots").fetchone()[0] or 50.0
            latest_time = conn.execute(
                "SELECT snapshot_time FROM sentiment_snapshots ORDER BY snapshot_time DESC LIMIT 1"
            ).fetchone()
        return {
            "total_snapshots": total,
            "extreme_count": extremes,
            "avg_fear_greed": round(avg_fg, 1),
            "latest_snapshot": latest_time[0] if latest_time else None,
        }
