"""
M12 Scan Logger - 统一持久化层
负责记录所有M12扫描结果（盘中/盘前/盘后）
"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Literal, Union

from core.schemas import OpportunityObject, RetroOpportunity


ScanType = Literal["intraday", "premarket", "postmarket"]


class M12ScanLogger:
    """M12扫描结果统一持久化"""

    def __init__(self, base_dir: str = "data/m12_scans"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        for scan_type in ["intraday", "premarket", "postmarket"]:
            (self.base_dir / scan_type).mkdir(exist_ok=True)

    def log_scan(
        self,
        scan_type: ScanType,
        market: str,
        opportunities: List[Any],
        metadata: Dict[str, Any] = None
    ) -> Path:
        """
        记录扫描结果

        Args:
            scan_type: 扫描类型 (intraday/premarket/postmarket)
            market: 市场标识 (a_share/hk/us)
            opportunities: 机会列表 (OpportunityObject 或 RetroOpportunity)
            metadata: 额外元数据

        Returns:
            保存的文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{market}_{timestamp}.json"
        filepath = self.base_dir / scan_type / filename

        # 构建记录
        record = {
            "scan_type": scan_type,
            "market": market,
            "timestamp": datetime.now().isoformat(),
            "total_opportunities": len(opportunities),
            "opportunities": self._serialize_opportunities(opportunities, scan_type),
            "metadata": metadata or {}
        }

        # 写入文件
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)

        return filepath

    def _serialize_opportunities(
        self,
        opportunities: List[Any],
        scan_type: ScanType
    ) -> List[Dict[str, Any]]:
        """序列化机会对象"""
        if not opportunities:
            return []

        # 根据扫描类型选择序列化方法
        if scan_type == "premarket":
            return [self._serialize_premarket_opportunity(opp) for opp in opportunities]
        else:
            return [self._serialize_retro_opportunity(opp) for opp in opportunities]

    def _serialize_premarket_opportunity(self, opp: OpportunityObject) -> Dict[str, Any]:
        """序列化盘前机会（OpportunityObject）"""
        return {
            "instrument": opp.instrument,
            "signal_type": opp.signal_type,
            "signal_strength": opp.signal_strength,
            "signal_timestamp": opp.signal_timestamp.isoformat() if opp.signal_timestamp else None,
            "signal_source": opp.signal_source,
            "signal_content": opp.signal_content,
            "context": opp.context,
            "metadata": opp.metadata
        }

    def _serialize_retro_opportunity(self, opp: RetroOpportunity) -> Dict[str, Any]:
        """序列化盘中/盘后机会（RetroOpportunity）"""
        return {
            "instrument": opp.instrument,
            "detected_at": opp.detected_at.isoformat(),
            "anomaly_type": opp.anomaly_type,
            "price_change_pct": opp.price_change_pct,
            "volume_ratio": opp.volume_ratio,
            "current_price": opp.current_price,
            "prev_close": opp.prev_close,
            "volume": opp.volume,
            "avg_volume": opp.avg_volume,
            "sigma_score": opp.sigma_score,
            "atr_score": opp.atr_score,
            "metadata": opp.metadata
        }

    def get_recent_scans(
        self,
        scan_type: ScanType,
        market: str = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        获取最近的扫描记录

        Args:
            scan_type: 扫描类型
            market: 市场标识（可选，None表示所有市场）
            limit: 返回数量限制

        Returns:
            扫描记录列表（按时间倒序）
        """
        scan_dir = self.base_dir / scan_type
        if not scan_dir.exists():
            return []

        # 获取所有JSON文件
        files = list(scan_dir.glob("*.json"))

        # 按市场过滤
        if market:
            files = [f for f in files if f.name.startswith(f"{market}_")]

        # 按修改时间排序（最新的在前）
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        # 读取文件内容
        records = []
        for filepath in files[:limit]:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    records.append(json.load(f))
            except Exception as e:
                print(f"[WARN] 读取扫描记录失败: {filepath}, 错误: {e}")
                continue

        return records

    def get_scan_stats(self, scan_type: ScanType, days: int = 7) -> Dict[str, Any]:
        """
        获取扫描统计信息

        Args:
            scan_type: 扫描类型
            days: 统计天数

        Returns:
            统计信息字典
        """
        scan_dir = self.base_dir / scan_type
        if not scan_dir.exists():
            return {
                "total_scans": 0,
                "total_opportunities": 0,
                "scans_with_opportunities": 0,
                "avg_opportunities_per_scan": 0.0
            }

        # 获取指定天数内的文件
        cutoff_time = datetime.now().timestamp() - (days * 86400)
        files = [
            f for f in scan_dir.glob("*.json")
            if f.stat().st_mtime >= cutoff_time
        ]

        total_scans = len(files)
        total_opportunities = 0
        scans_with_opportunities = 0

        for filepath in files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    record = json.load(f)
                    count = record.get("total_opportunities", 0)
                    total_opportunities += count
                    if count > 0:
                        scans_with_opportunities += 1
            except Exception:
                continue

        return {
            "total_scans": total_scans,
            "total_opportunities": total_opportunities,
            "scans_with_opportunities": scans_with_opportunities,
            "avg_opportunities_per_scan": (
                total_opportunities / total_scans if total_scans > 0 else 0.0
            )
        }
