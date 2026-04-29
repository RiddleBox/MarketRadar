"""
价格快照记录器 - 记录每次扫描时所有标的的价格数据
用于回测和历史分析
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class PriceSnapshotLogger:
    """记录价格快照到按日期分割的JSON文件"""

    def __init__(self, data_dir: str = "data/price_snapshots"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def log_batch(self, market: str, snapshots: List[Dict]):
        """
        批量记录价格快照

        Args:
            market: 市场名称 (A_SHARE, US, HK)
            snapshots: 价格快照列表，每个包含 {symbol, price, change_pct, volume}
        """
        if not snapshots:
            return

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        file_path = self.data_dir / f"snapshots_{date_str}.json"

        # 读取现有数据
        existing_data = []
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception as e:
                logger.warning(f"[PriceSnapshotLogger] load existing data failed: {e}")

        # 添加新快照
        for snap in snapshots:
            record = {
                "timestamp": now.isoformat(),
                "market": market,
                "symbol": snap.get("symbol"),
                "price": snap.get("price"),
                "change_pct": snap.get("change_pct"),
                "volume": snap.get("volume"),
            }
            existing_data.append(record)

        # 保存
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[PriceSnapshotLogger] save failed: {e}")

    def log_snapshot(self, snapshots: List[Dict[str, Any]], scan_type: str = "intraday"):
        """
        记录一次扫描的价格快照

        Args:
            snapshots: 价格快照列表 [{'instrument': 'AAPL.US', 'price': 269.72, ...}, ...]
            scan_type: 扫描类型 ('intraday' 或 'daily')
        """
        if not snapshots:
            return

        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        file_path = self.data_dir / f"snapshots_{date_str}.json"

        # 构建记录
        record = {
            "timestamp": now.isoformat(),
            "scan_type": scan_type,
            "count": len(snapshots),
            "snapshots": snapshots
        }

        # 追加到文件
        existing_data = []
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except Exception:
                existing_data = []

        existing_data.append(record)

        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2, default=str)

    def get_snapshots(self, date_str: str) -> List[Dict[str, Any]]:
        """获取指定日期的所有快照"""
        file_path = self.data_dir / f"snapshots_{date_str}.json"
        if not file_path.exists():
            return []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []


# 全局单例
_price_snapshot_logger = None


def get_price_snapshot_logger() -> PriceSnapshotLogger:
    """获取全局价格快照记录器单例"""
    global _price_snapshot_logger
    if _price_snapshot_logger is None:
        _price_snapshot_logger = PriceSnapshotLogger()
    return _price_snapshot_logger

