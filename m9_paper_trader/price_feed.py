"""
m9_paper_trader/price_feed.py — 价格数据源

支持：
  1. AKShare 实时行情（A股/港股）
  2. AKShare 历史日线（回填用）
  3. CSV 静态文件（离线测试用）

统一返回 PriceSnapshot 对象，与具体数据源解耦。
"""
from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PriceSnapshot:
    """单标的价格快照"""
    instrument: str
    price: float
    open_price: float
    high: float
    low: float
    volume: float          # 成交量（手）
    amount: float          # 成交额（元）
    timestamp: datetime
    source: str            # "akshare_realtime" | "akshare_daily" | "csv"


class PriceFeed:
    """价格数据源基类 / 工厂"""

    def get_price(self, instrument: str, dt: Optional[date] = None) -> Optional[PriceSnapshot]:
        """
        获取价格快照。
          dt=None  → 最新实时价格
          dt=<date> → 当日收盘价（日线）

        Returns None 如果获取失败。
        """
        raise NotImplementedError


# ─────────────────────────────────────────────────────────────
# AKShare 实时行情
# ─────────────────────────────────────────────────────────────

class AKShareRealtimeFeed(PriceFeed):
    """
    A股实时行情，使用 akshare.stock_zh_a_spot_em()
    港股使用 akshare.stock_hk_spot_em()
    """

    def __init__(self):
        self._cache: dict[str, PriceSnapshot] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_sec = 60  # 1分钟缓存

    def get_price(self, instrument: str, dt: Optional[date] = None) -> Optional[PriceSnapshot]:
        if dt is not None:
            return self._get_daily(instrument, dt)
        return self._get_realtime(instrument)

    def _get_realtime(self, instrument: str) -> Optional[PriceSnapshot]:
        try:
            import akshare as ak
            from datetime import timezone
            now = datetime.now()

            # 判断市场
            code = instrument.split(".")[0]
            suffix = instrument.split(".")[-1].upper() if "." in instrument else ""

            if suffix in ("HK",):
                df = ak.stock_hk_spot_em()
                row = df[df["代码"] == code]
                if row.empty:
                    return None
                row = row.iloc[0]
                return PriceSnapshot(
                    instrument=instrument,
                    price=float(row.get("最新价", 0)),
                    open_price=float(row.get("今开", 0)),
                    high=float(row.get("最高", 0)),
                    low=float(row.get("最低", 0)),
                    volume=float(row.get("成交量", 0)),
                    amount=float(row.get("成交额", 0)),
                    timestamp=now,
                    source="akshare_realtime_hk",
                )
            else:
                # A股（沪深）
                df = ak.stock_zh_a_spot_em()
                row = df[df["代码"] == code]
                if row.empty:
                    return None
                row = row.iloc[0]
                return PriceSnapshot(
                    instrument=instrument,
                    price=float(row.get("最新价", 0)),
                    open_price=float(row.get("今开", 0)),
                    high=float(row.get("最高", 0)),
                    low=float(row.get("最低", 0)),
                    volume=float(row.get("成交量", 0)),
                    amount=float(row.get("成交额", 0)),
                    timestamp=now,
                    source="akshare_realtime_a",
                )
        except Exception as e:
            logger.warning(f"[PriceFeed] 实时行情获取失败 {instrument}: {e}")
            return None

    def _get_daily(self, instrument: str, dt: date) -> Optional[PriceSnapshot]:
        """获取某日收盘价（历史日线）"""
        try:
            import akshare as ak
            code = instrument.split(".")[0]
            suffix = instrument.split(".")[-1].upper() if "." in instrument else ""
            dt_str = dt.strftime("%Y%m%d")

            if suffix in ("HK",):
                df = ak.stock_hk_daily(symbol=code, adjust="qfq")
            elif code.startswith(("51", "15", "16")):
                # ETF
                df = ak.fund_etf_hist_em(symbol=code, adjust="qfq")
                df = df.rename(columns={"日期": "date", "收盘": "close", "开盘": "open",
                                        "最高": "high", "最低": "low",
                                        "成交量": "volume", "成交额": "amount"})
            else:
                df = ak.stock_zh_a_hist(symbol=code, adjust="qfq",
                                        start_date=dt_str, end_date=dt_str)

            if df is None or df.empty:
                return None

            row = df.iloc[-1]
            return PriceSnapshot(
                instrument=instrument,
                price=float(row.get("收盘", row.get("close", 0))),
                open_price=float(row.get("开盘", row.get("open", 0))),
                high=float(row.get("最高", row.get("high", 0))),
                low=float(row.get("最低", row.get("low", 0))),
                volume=float(row.get("成交量", row.get("volume", 0))),
                amount=float(row.get("成交额", row.get("amount", 0))),
                timestamp=datetime.combine(dt, datetime.min.time()),
                source="akshare_daily",
            )
        except Exception as e:
            logger.warning(f"[PriceFeed] 历史日线获取失败 {instrument} {dt}: {e}")
            return None


# ─────────────────────────────────────────────────────────────
# CSV 静态文件（离线测试 / 回填）
# ─────────────────────────────────────────────────────────────

class CSVPriceFeed(PriceFeed):
    """
    从 CSV 文件读取价格数据（用于离线测试）。
    CSV 格式：date,instrument,open,high,low,close,volume,amount
    """

    def __init__(self, csv_path: str):
        self._data: dict[tuple, PriceSnapshot] = {}
        self._load(csv_path)

    def _load(self, path: str):
        try:
            with open(path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    dt = date.fromisoformat(row["date"])
                    inst = row["instrument"]
                    self._data[(inst, dt)] = PriceSnapshot(
                        instrument=inst,
                        price=float(row.get("close", 0)),
                        open_price=float(row.get("open", 0)),
                        high=float(row.get("high", 0)),
                        low=float(row.get("low", 0)),
                        volume=float(row.get("volume", 0)),
                        amount=float(row.get("amount", 0)),
                        timestamp=datetime.combine(dt, datetime.min.time()),
                        source="csv",
                    )
            logger.info(f"[CSVPriceFeed] 加载 {len(self._data)} 条记录")
        except Exception as e:
            logger.error(f"[CSVPriceFeed] 加载失败: {e}")

    def get_price(self, instrument: str, dt: Optional[date] = None) -> Optional[PriceSnapshot]:
        if dt is None:
            dt = date.today()
        return self._data.get((instrument, dt))


# ─────────────────────────────────────────────────────────────
# 工厂函数
# ─────────────────────────────────────────────────────────────

def make_price_feed(mode: str = "akshare", csv_path: str = "") -> PriceFeed:
    """
    mode: "akshare" | "csv"
    """
    if mode == "csv":
        return CSVPriceFeed(csv_path)
    return AKShareRealtimeFeed()
