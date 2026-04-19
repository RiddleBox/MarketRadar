"""
pipeline/confirmation_store.py — 确认请求持久化

SQLite 存储 ConfirmationRequest，支持：
  - create()     : 创建待确认请求
  - get_pending(): 获取所有待确认请求
  - approve()    : 批准
  - reject()     : 拒绝
  - expire()     : 过期处理
  - list_history(): 历史查询
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .confirmation import ConfirmationRequest, ConfirmationStatus, RiskLevel

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "confirmation" / "confirmation_requests.db"


class ConfirmationStore:
    """确认请求数据库"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS confirmation_requests (
                    request_id      TEXT PRIMARY KEY,
                    created_at      TEXT NOT NULL,
                    action_type     TEXT NOT NULL,
                    description     TEXT,
                    parameters_json TEXT,
                    risk_level      TEXT,
                    status          TEXT DEFAULT 'pending',
                    reviewed_by     TEXT,
                    reviewed_at     TEXT,
                    review_note     TEXT,
                    expires_at      TEXT,
                    session_id      TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cfm_status
                ON confirmation_requests(status)
            """)
            conn.commit()

    def create(self, req: ConfirmationRequest) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO confirmation_requests
                    (request_id, created_at, action_type, description,
                     parameters_json, risk_level, status, reviewed_by,
                     reviewed_at, review_note, expires_at, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                req.request_id,
                req.created_at.isoformat(),
                req.action_type,
                req.description,
                json.dumps(req.parameters, ensure_ascii=False, default=str),
                req.risk_level.value,
                req.status.value,
                req.reviewed_by,
                req.reviewed_at.isoformat() if req.reviewed_at else None,
                req.review_note,
                req.expires_at.isoformat() if req.expires_at else None,
                req.session_id,
            ))
            conn.commit()
        logger.info(f"[ConfirmationStore] 创建确认请求: {req.request_id} ({req.action_type})")

    def get_pending(self) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM confirmation_requests WHERE status = 'pending' "
                "ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def approve(self, request_id: str, reviewed_by: str = "", note: str = "") -> bool:
        return self._update_status(request_id, ConfirmationStatus.APPROVED, reviewed_by, note)

    def reject(self, request_id: str, reviewed_by: str = "", note: str = "") -> bool:
        return self._update_status(request_id, ConfirmationStatus.REJECTED, reviewed_by, note)

    def expire_old(self) -> int:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE confirmation_requests SET status = 'expired' "
                "WHERE status = 'pending' AND expires_at IS NOT NULL AND expires_at < ?",
                (now,),
            )
            conn.commit()
            return cur.rowcount

    def list_history(self, limit: int = 50) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM confirmation_requests ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _update_status(
        self,
        request_id: str,
        status: ConfirmationStatus,
        reviewed_by: str = "",
        note: str = "",
    ) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE confirmation_requests SET status = ?, reviewed_by = ?, "
                "reviewed_at = ?, review_note = ? WHERE request_id = ? AND status = 'pending'",
                (status.value, reviewed_by, datetime.now().isoformat(), note, request_id),
            )
            conn.commit()
            return cur.rowcount > 0
