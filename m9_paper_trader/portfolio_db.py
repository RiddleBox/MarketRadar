"""
m9_paper_trader/portfolio_db.py — 持仓数据库（SQLite）

职责：
  1. 持久化 PaperPosition 到 SQLite
  2. 持久化账户状态（cash, total_value）
  3. 记录交易日志
  4. 支持跨进程恢复持仓

表结构：
  - positions: 持仓记录（包含已平仓）
  - account: 账户状态（单行表）
  - trade_log: 交易日志
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


class PortfolioDB:
    """持仓数据库（SQLite）"""

    def __init__(self, db_path: str = "data/portfolio.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """初始化数据库表结构（含自动迁移）"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # positions 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                position_id TEXT PRIMARY KEY,
                instrument TEXT NOT NULL,
                market TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                quantity REAL NOT NULL,
                entry_time TEXT NOT NULL,
                stop_loss_price REAL,
                take_profit_price REAL,
                current_price REAL,
                status TEXT NOT NULL,
                exit_price REAL,
                exit_time TEXT,
                realized_pnl_pct REAL,
                realized_pnl_after_fees REAL,
                fee_paid REAL DEFAULT 0,
                opportunity_id TEXT,
                plan_id TEXT,
                signal_ids TEXT,
                signal_intensity REAL DEFAULT 0,
                signal_confidence REAL DEFAULT 0,
                signal_type TEXT,
                time_horizon TEXT,
                prev_close REAL DEFAULT 0,
                board TEXT DEFAULT 'main',
                max_adverse_excursion REAL DEFAULT 0,
                max_favorable_excursion REAL DEFAULT 0,
                unrealized_pnl_pct REAL DEFAULT 0,
                entry_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # account 表（单行表）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                cash REAL NOT NULL,
                total_value REAL NOT NULL,
                update_time TEXT NOT NULL
            )
        """)

        # trade_log 表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                position_id TEXT NOT NULL,
                instrument TEXT NOT NULL,
                market TEXT,
                direction TEXT,
                price REAL,
                quantity REAL,
                reason TEXT,
                fee_paid REAL DEFAULT 0,
                realized_pnl_pct REAL,
                realized_pnl_after_fees REAL
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_status 
            ON positions(status)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_positions_instrument 
            ON positions(instrument)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trade_log_timestamp
            ON trade_log(timestamp)
        """)

        # ── 自动迁移：为旧的 positions 表添加缺失列 ──
        cursor.execute("PRAGMA table_info(positions)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        migrations = {
            "stop_loss_price": "REAL",
            "take_profit_price": "REAL",
            "current_price": "REAL",
            "exit_price": "REAL",
            "exit_time": "TEXT",
            "realized_pnl_pct": "REAL",
            "realized_pnl_after_fees": "REAL",
            "fee_paid": "REAL DEFAULT 0",
            "opportunity_id": "TEXT",
            "signal_ids": "TEXT",
            "signal_intensity": "REAL DEFAULT 0",
            "signal_confidence": "REAL DEFAULT 0",
            "signal_type": "TEXT",
            "time_horizon": "TEXT",
            "prev_close": "REAL DEFAULT 0",
            "board": "TEXT DEFAULT 'main'",
            "max_adverse_excursion": "REAL DEFAULT 0",
            "max_favorable_excursion": "REAL DEFAULT 0",
            "unrealized_pnl_pct": "REAL DEFAULT 0",
            "entry_date": "TEXT",
        }
        for col_name, col_type in migrations.items():
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE positions ADD COLUMN {col_name} {col_type}")
                    logger.info(f"[PortfolioDB] 迁移: 添加列 positions.{col_name} {col_type}")
                except Exception as e:
                    logger.warning(f"[PortfolioDB] 迁移失败 {col_name}: {e}")

        conn.commit()
        conn.close()
        logger.info(f"[PortfolioDB] 数据库初始化完成: {self.db_path}")

    def save_position(self, position_dict: dict) -> None:
        """保存或更新持仓

        Args:
            position_dict: PaperPosition.to_dict() 的返回值（也可直接传 PaperPosition 对象）
        """
        # 兼容直接传入 PaperPosition 对象
        if hasattr(position_dict, 'to_dict'):
            position_dict = position_dict.to_dict()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 将 signal_ids 列表转为逗号分隔字符串
        signal_ids_str = ",".join(position_dict.get("signal_ids", []))

        cursor.execute("""
            INSERT OR REPLACE INTO positions (
                position_id, instrument, market, direction,
                entry_price, quantity, entry_time,
                stop_loss_price, take_profit_price, current_price,
                status, exit_price, exit_time,
                realized_pnl_pct, realized_pnl_after_fees, fee_paid,
                opportunity_id, plan_id, signal_ids,
                signal_intensity, signal_confidence, signal_type,
                time_horizon, prev_close, board,
                max_adverse_excursion, max_favorable_excursion,
                unrealized_pnl_pct, entry_date, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            position_dict["paper_position_id"],
            position_dict["instrument"],
            position_dict["market"],
            position_dict["direction"],
            position_dict["entry_price"],
            position_dict["quantity"],
            position_dict["entry_time"],
            position_dict.get("stop_loss_price"),
            position_dict.get("take_profit_price"),
            position_dict.get("current_price", position_dict["entry_price"]),
            position_dict.get("status", "OPEN"),
            position_dict.get("exit_price"),
            position_dict.get("exit_time"),
            position_dict.get("realized_pnl_pct"),
            position_dict.get("realized_pnl_after_fees"),
            position_dict.get("fee_paid", 0),
            position_dict.get("opportunity_id", ""),
            position_dict.get("plan_id", ""),
            signal_ids_str,
            position_dict.get("signal_intensity", 0),
            position_dict.get("signal_confidence", 0),
            position_dict.get("signal_type", ""),
            position_dict.get("time_horizon", ""),
            position_dict.get("prev_close", 0),
            position_dict.get("board", "main"),
            position_dict.get("max_adverse_excursion", 0),
            position_dict.get("max_favorable_excursion", 0),
            position_dict.get("unrealized_pnl_pct", 0),
            position_dict.get("entry_date"),
            datetime.now().isoformat(),
        ))

        conn.commit()
        conn.close()

    def load_open_positions(self) -> List[dict]:
        """加载所有未平仓持仓

        Returns:
            持仓字典列表（可用于 PaperPosition.from_dict()）
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM positions WHERE status = 'OPEN'
            ORDER BY entry_time DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        positions = []
        for row in rows:
            pos_dict = dict(row)
            # 将 signal_ids 字符串转回列表
            signal_ids_str = pos_dict.get("signal_ids", "")
            pos_dict["signal_ids"] = signal_ids_str.split(",") if signal_ids_str else []
            # 重命名字段以匹配 PaperPosition.from_dict() 的期望
            pos_dict["paper_position_id"] = pos_dict.pop("position_id")
            positions.append(pos_dict)

        return positions

    def load_all_positions(self, limit: int = 1000) -> List[dict]:
        """加载所有持仓（包含已平仓）

        Args:
            limit: 最多返回多少条记录

        Returns:
            持仓字典列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM positions
            ORDER BY entry_time DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        positions = []
        for row in rows:
            pos_dict = dict(row)
            signal_ids_str = pos_dict.get("signal_ids", "")
            pos_dict["signal_ids"] = signal_ids_str.split(",") if signal_ids_str else []
            pos_dict["paper_position_id"] = pos_dict.pop("position_id")
            positions.append(pos_dict)

        return positions

    def update_position(self, position_id: str, **kwargs) -> None:
        """更新持仓字段

        Args:
            position_id: 持仓ID
            **kwargs: 要更新的字段（如 current_price=100, status='STOP_LOSS'）
        """
        if not kwargs:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 构建 UPDATE 语句
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        set_clause += ", updated_at = ?"
        values = list(kwargs.values()) + [datetime.now().isoformat(), position_id]

        cursor.execute(f"""
            UPDATE positions
            SET {set_clause}
            WHERE position_id = ?
        """, values)

        conn.commit()
        conn.close()

    def save_account(self, cash: float, total_value: float) -> None:
        """保存账户状态

        Args:
            cash: 可用资金
            total_value: 总资产（含浮盈）
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO account (id, cash, total_value, update_time)
            VALUES (1, ?, ?, ?)
        """, (cash, total_value, datetime.now().isoformat()))

        conn.commit()
        conn.close()

    def load_account(self) -> Tuple[float, float]:
        """加载账户状态

        Returns:
            (cash, total_value)，如果不存在返回 (0, 0)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT cash, total_value FROM account WHERE id = 1")
        row = cursor.fetchone()
        conn.close()

        if row:
            return row[0], row[1]
        return 0.0, 0.0

    def log_trade(
        self,
        action: str,
        position_id: str,
        instrument: str,
        market: str = "",
        direction: str = "",
        price: float = 0.0,
        quantity: float = 0.0,
        reason: str = "",
        fee_paid: float = 0.0,
        realized_pnl_pct: Optional[float] = None,
        realized_pnl_after_fees: Optional[float] = None,
    ) -> None:
        """记录交易日志

        Args:
            action: 操作类型（OPEN, CLOSE, STOP_LOSS, TAKE_PROFIT, MANUAL, EXPIRED）
            position_id: 持仓ID
            instrument: 标的代码
            market: 市场
            direction: 方向
            price: 价格
            quantity: 数量
            reason: 原因说明
            fee_paid: 手续费
            realized_pnl_pct: 实现盈亏百分比
            realized_pnl_after_fees: 扣费后盈亏百分比
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO trade_log (
                timestamp, action, position_id, instrument,
                market, direction, price, quantity, reason,
                fee_paid, realized_pnl_pct, realized_pnl_after_fees
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            action,
            position_id,
            instrument,
            market,
            direction,
            price,
            quantity,
            reason,
            fee_paid,
            realized_pnl_pct,
            realized_pnl_after_fees,
        ))

        conn.commit()
        conn.close()

    def get_trade_log(self, limit: int = 100) -> List[dict]:
        """获取交易日志

        Args:
            limit: 最多返回多少条

        Returns:
            交易日志列表
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM trade_log
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_statistics(self) -> dict:
        """获取统计信息

        Returns:
            统计数据字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 总持仓数
        cursor.execute("SELECT COUNT(*) FROM positions")
        total_positions = cursor.fetchone()[0]

        # 未平仓数
        cursor.execute("SELECT COUNT(*) FROM positions WHERE status = 'OPEN'")
        open_positions = cursor.fetchone()[0]

        # 已平仓数
        cursor.execute("SELECT COUNT(*) FROM positions WHERE status != 'OPEN'")
        closed_positions = cursor.fetchone()[0]

        # 平均盈亏（已平仓）
        cursor.execute("""
            SELECT AVG(realized_pnl_after_fees) 
            FROM positions 
            WHERE status != 'OPEN' AND realized_pnl_after_fees IS NOT NULL
        """)
        avg_pnl = cursor.fetchone()[0] or 0.0

        # 胜率
        cursor.execute("""
            SELECT 
                COUNT(CASE WHEN realized_pnl_after_fees > 0 THEN 1 END) * 1.0 / COUNT(*) 
            FROM positions 
            WHERE status != 'OPEN' AND realized_pnl_after_fees IS NOT NULL
        """)
        win_rate = cursor.fetchone()[0] or 0.0

        # 账户状态
        cursor.execute("SELECT cash, total_value FROM account WHERE id = 1")
        account_row = cursor.fetchone()
        cash = account_row[0] if account_row else 0.0
        total_value = account_row[1] if account_row else 0.0

        conn.close()

        return {
            "total_positions": total_positions,
            "open_positions": open_positions,
            "closed_positions": closed_positions,
            "avg_pnl_pct": avg_pnl * 100,
            "win_rate": win_rate * 100,
            "cash": cash,
            "total_value": total_value,
        }
