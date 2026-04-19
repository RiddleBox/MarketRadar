"""
pipeline/audit_store.py — 审计日志持久化

SQLite 存储 AuditEntry，支持：
  - log()        : 写入一条审计记录
  - query()      : 按条件查询
  - get_recent() : 最近 N 条
  - get_stats()  : 统计摘要
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from .audit_log import ActionType, Actor, AuditResult, AuditEntry

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "audit" / "audit_log.db"


class AuditStore:
    """审计日志数据库"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_entries (
                    entry_id        TEXT PRIMARY KEY,
                    timestamp       TEXT NOT NULL,
                    action_type     TEXT NOT NULL,
                    actor           TEXT,
                    actor_id        TEXT,
                    target_type     TEXT,
                    target_id       TEXT,
                    description     TEXT,
                    parameters_json TEXT,
                    result          TEXT,
                    error_message   TEXT,
                    session_id      TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                ON audit_entries(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_action_type
                ON audit_entries(action_type)
            """)
            conn.commit()

    def log(self, entry: AuditEntry) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO audit_entries
                    (entry_id, timestamp, action_type, actor, actor_id,
                     target_type, target_id, description, parameters_json,
                     result, error_message, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.entry_id,
                entry.timestamp.isoformat(),
                entry.action_type.value,
                entry.actor.value,
                entry.actor_id,
                entry.target_type,
                entry.target_id,
                entry.description,
                json.dumps(entry.parameters, ensure_ascii=False, default=str),
                entry.result.value,
                entry.error_message,
                entry.session_id,
            ))
            conn.commit()

    def get_recent(self, n: int = 100) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM audit_entries ORDER BY timestamp DESC LIMIT ?",
                (n,),
            ).fetchall()
        return [dict(r) for r in rows]

    def query(
        self,
        action_type: Optional[str] = None,
        actor: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        target_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict]:
        clauses = []
        params = []
        if action_type:
            clauses.append("action_type = ?")
            params.append(action_type)
        if actor:
            clauses.append("actor = ?")
            params.append(actor)
        if start:
            clauses.append("timestamp >= ?")
            params.append(start.isoformat())
        if end:
            clauses.append("timestamp <= ?")
            params.append(end.isoformat())
        if target_id:
            clauses.append("target_id = ?")
            params.append(target_id)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT * FROM audit_entries WHERE {where} ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self, days: int = 7) -> Dict:
        since = (datetime.now() - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM audit_entries WHERE timestamp >= ?", (since,)
            ).fetchone()[0]
            by_type_rows = conn.execute(
                "SELECT action_type, COUNT(*) as cnt FROM audit_entries WHERE timestamp >= ? GROUP BY action_type",
                (since,),
            ).fetchall()
            by_actor_rows = conn.execute(
                "SELECT actor, COUNT(*) as cnt FROM audit_entries WHERE timestamp >= ? GROUP BY actor",
                (since,),
            ).fetchall()
            failures = conn.execute(
                "SELECT COUNT(*) FROM audit_entries WHERE result = 'failure' AND timestamp >= ?",
                (since,),
            ).fetchone()[0]

        return {
            "period_days": days,
            "total_entries": total,
            "failure_count": failures,
            "by_action_type": {r[0]: r[1] for r in by_type_rows},
            "by_actor": {r[0]: r[1] for r in by_actor_rows},
        }

    def cleanup(self, retention_days: int = 90) -> int:
        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM audit_entries WHERE timestamp < ?", (cutoff,)
            )
            conn.commit()
            deleted = cur.rowcount
        if deleted:
            logger.info(f"[AuditStore] 清理 {deleted} 条超过 {retention_days} 天的记录")
        return deleted
