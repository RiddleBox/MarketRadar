"""
backtest/history_price.py — 历史价格数据

用 AKShare 拉取 A股/ETF 历史日线，
提供按日期查询收盘价的接口，供回测引擎使用。

缓存策略：
  - 每支标的拉取一次全量数据缓存到内存
  - 支持序列化到 data/price_cache/<instrument>.json（避免重复 API 调用）
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional, List, Tuple

logger = logging.getLogger(__name__)

PRICE_CACHE_DIR = Path(__file__).parent.parent / "data" / "price_cache"


class HistoryPriceFeed:
    """
    历史价格数据源。
    支持 A股（沪深主板）、ETF、指数。
    """

    def __init__(self, cache_dir: Path = PRICE_CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        # instrument → {date_str → {"close": float, "open": float, ...}}
        self._cache: Dict[str, Dict[str, dict]] = {}

    def get_price(
        self,
        instrument: str,
        dt: date,
        price_type: str = "close",
    ) -> Optional[float]:
        """
        获取指定标的在指定日期的价格。

        Args:
            instrument:  标的代码，如 "510300.SH"
            dt:          日期
            price_type:  "close" | "open" | "high" | "low"

        Returns:
            价格（float），不存在返回 None
        """
        self._ensure_loaded(instrument)
        day_data = self._cache.get(instrument, {}).get(dt.strftime("%Y-%m-%d"))
        if not day_data:
            return None
        return day_data.get(price_type) or day_data.get("close")

    def get_price_range(
        self,
        instrument: str,
        start: date,
        end: date,
    ) -> List[Tuple[date, float]]:
        """获取日期范围内的收盘价序列（升序）"""
        self._ensure_loaded(instrument)
        cache = self._cache.get(instrument, {})
        result = []
        cur = start
        from datetime import timedelta
        while cur <= end:
            ds = cur.strftime("%Y-%m-%d")
            if ds in cache:
                result.append((cur, cache[ds].get("close", 0)))
            cur += timedelta(days=1)
        return result

    def get_close_after(
        self,
        instrument: str,
        after: date,
        n_days: int = 30,
    ) -> List[Tuple[date, float]]:
        """
        获取 after 日期之后最多 n_days 个交易日的收盘价。
        用于回测：开仓后 N 日价格走势。
        """
        from datetime import timedelta
        end = after + timedelta(days=n_days * 2)   # 留余量（包含非交易日）
        all_prices = self.get_price_range(instrument, after, end)
        return all_prices[:n_days]

    def _ensure_loaded(self, instrument: str):
        """确保标的数据已加载（先读缓存文件，再调 AKShare）"""
        if instrument in self._cache:
            return

        # 先尝试读磁盘缓存
        cache_file = self.cache_dir / f"{instrument.replace('.', '_')}.json"
        if cache_file.exists():
            try:
                self._cache[instrument] = json.loads(cache_file.read_text(encoding="utf-8"))
                logger.info(f"[PriceFeed] 从缓存读取 {instrument}: {len(self._cache[instrument])} 天")
                return
            except Exception:
                pass

        # 调 AKShare 拉全量日线
        self._fetch_and_cache(instrument)

    def _fetch_and_cache(self, instrument: str):
        """用 AKShare 拉取日线数据并写入缓存"""
        try:
            import akshare as ak
        except ImportError:
            logger.error("请先安装 akshare: pip install akshare")
            self._cache[instrument] = {}
            return

        code = instrument.split(".")[0]
        suffix = instrument.split(".")[-1].upper() if "." in instrument else ""

        try:
            # ETF（以15/51开头）
            if code.startswith(("51", "15", "16", "58")):
                df = ak.fund_etf_hist_em(symbol=code, adjust="qfq", period="daily")
                if df is None or df.empty:
                    self._cache[instrument] = {}
                    return
                day_data = {}
                for _, row in df.iterrows():
                    ds = str(row.get("日期", ""))[:10]
                    if not ds:
                        continue
                    day_data[ds] = {
                        "open":  float(row.get("开盘", 0) or 0),
                        "high":  float(row.get("最高", 0) or 0),
                        "low":   float(row.get("最低", 0) or 0),
                        "close": float(row.get("收盘", 0) or 0),
                        "volume": float(row.get("成交量", 0) or 0),
                    }

            elif suffix in ("HK",):
                df = ak.stock_hk_daily(symbol=code, adjust="qfq")
                if df is None or df.empty:
                    self._cache[instrument] = {}
                    return
                day_data = {}
                for _, row in df.iterrows():
                    ds = str(row.get("date", ""))[:10]
                    day_data[ds] = {
                        "open":  float(row.get("open", 0) or 0),
                        "high":  float(row.get("high", 0) or 0),
                        "low":   float(row.get("low", 0) or 0),
                        "close": float(row.get("close", 0) or 0),
                        "volume": float(row.get("volume", 0) or 0),
                    }

            else:
                # A股主板
                df = ak.stock_zh_a_hist(symbol=code, adjust="qfq", period="daily")
                if df is None or df.empty:
                    self._cache[instrument] = {}
                    return
                day_data = {}
                for _, row in df.iterrows():
                    ds = str(row.get("日期", ""))[:10]
                    if not ds:
                        continue
                    day_data[ds] = {
                        "open":  float(row.get("开盘", 0) or 0),
                        "high":  float(row.get("最高", 0) or 0),
                        "low":   float(row.get("低", row.get("最低", 0)) or 0),
                        "close": float(row.get("收盘", 0) or 0),
                        "volume": float(row.get("成交量", 0) or 0),
                    }

            self._cache[instrument] = day_data
            logger.info(f"[PriceFeed] AKShare 拉取 {instrument}: {len(day_data)} 天")

            # 写磁盘缓存
            cache_file = self.cache_dir / f"{instrument.replace('.', '_')}.json"
            cache_file.write_text(
                json.dumps(day_data, ensure_ascii=False),
                encoding="utf-8",
            )

        except Exception as e:
            logger.error(f"[PriceFeed] 拉取失败 {instrument}: {e}")
            self._cache[instrument] = {}

    def preload(self, instruments: List[str]):
        """批量预加载多个标的，避免回测中逐个等待"""
        for inst in instruments:
            self._ensure_loaded(inst)
            logger.info(f"[PriceFeed] 预加载完成: {inst}")
