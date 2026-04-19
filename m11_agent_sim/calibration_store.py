"""
m11_agent_sim/calibration_store.py — 校准历史持久化

SQLite 存储 CalibrationRun 记录，支持：
  - save_run()    : 保存一次校准运行
  - load_run()    : 按 run_id 加载
  - list_runs()   : 列出历史运行
  - latest()      : 最近一次运行
  - compare()     : 对比两次运行的关键指标
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .schemas import CalibrationRun, CalibrationScore, ValidationCase

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "m11" / "calibration_history.db"


class CalibrationStore:
    """校准历史数据库"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS calibration_runs (
                    run_id          TEXT PRIMARY KEY,
                    run_timestamp   TEXT NOT NULL,
                    market          TEXT,
                    topology        TEXT,
                    n_events        INTEGER,
                    direction_accuracy REAL,
                    prob_calibration_err REAL,
                    extreme_recall  REAL,
                    composite_score REAL,
                    pass_threshold  INTEGER,
                    cases_json      TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_run_timestamp
                ON calibration_runs(run_timestamp)
            """)
            conn.commit()

    def save_run(self, run: CalibrationRun) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cases_json = json.dumps(
                [c.model_dump() for c in run.cases],
                ensure_ascii=False, default=str,
            )
            conn.execute("""
                INSERT OR REPLACE INTO calibration_runs
                    (run_id, run_timestamp, market, topology, n_events,
                     direction_accuracy, prob_calibration_err, extreme_recall,
                     composite_score, pass_threshold, cases_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run.run_id,
                run.run_timestamp.isoformat(),
                run.market,
                run.topology,
                run.n_events,
                run.score.direction_accuracy,
                run.score.prob_calibration_err,
                run.score.extreme_recall,
                run.score.composite_score,
                1 if run.score.pass_threshold else 0,
                cases_json,
            ))
            conn.commit()
        logger.info(f"[CalibrationStore] 已保存 run_id={run.run_id} n_events={run.n_events}")

    def load_run(self, run_id: str) -> Optional[CalibrationRun]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM calibration_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_run(row)

    def list_runs(self, limit: int = 20) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT run_id, run_timestamp, n_events, direction_accuracy, "
                "composite_score, pass_threshold FROM calibration_runs "
                "ORDER BY run_timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def latest(self) -> Optional[CalibrationRun]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM calibration_runs ORDER BY run_timestamp DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        return self._row_to_run(row)

    def compare(self, run_id_a: str, run_id_b: str) -> Optional[Dict]:
        a = self.load_run(run_id_a)
        b = self.load_run(run_id_b)
        if not a or not b:
            return None
        return {
            "run_a": run_id_a,
            "run_b": run_id_b,
            "direction_accuracy_delta": b.score.direction_accuracy - a.score.direction_accuracy,
            "composite_score_delta": b.score.composite_score - a.score.composite_score,
            "prob_err_delta": b.score.prob_calibration_err - a.score.prob_calibration_err,
            "extreme_recall_delta": b.score.extreme_recall - a.score.extreme_recall,
            "n_events_delta": b.n_events - a.n_events,
        }

    def _row_to_run(self, row) -> CalibrationRun:
        cases_data = json.loads(row["cases_json"]) if row["cases_json"] else []
        cases = [ValidationCase(**c) for c in cases_data]
        return CalibrationRun(
            run_id=row["run_id"],
            run_timestamp=datetime.fromisoformat(row["run_timestamp"]),
            market=row["market"],
            topology=row["topology"],
            n_events=row["n_events"],
            score=CalibrationScore(
                total_events=row["n_events"],
                direction_accuracy=row["direction_accuracy"],
                prob_calibration_err=row["prob_calibration_err"],
                extreme_recall=row["extreme_recall"],
                composite_score=row["composite_score"],
                pass_threshold=bool(row["pass_threshold"]),
            ),
            cases=cases,
        )
