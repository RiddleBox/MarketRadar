"""
backtest/history_price.py — 历史价格数据

三层数据源（按优先级依次尝试）：
  1. seed_data.py 内嵌种子数据  — 无需网络，离线可用，覆盖 2024Q3~2025Q1
  2. data/price_cache/<inst>.json — 磁盘缓存，AKShare 成功后自动写入
  3. AKShare API               — 联网拉取，支持 A股/ETF/港股

使用方式：
  feed = HistoryPriceFeed()                  # 默认：种子优先，自动尝试 AKShare
  feed = HistoryPriceFeed(use_seed=False)    # 仅磁盘缓存 + AKShare（跳过种子）
  preload_seed_into_feed(feed)               # 测试中手动注入种子（不影响已有数据）

合并规则：
  种子数据 < 磁盘缓存 < AKShare 实时数据（新来源覆盖旧来源同一天数据）
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

PRICE_CACHE_DIR = Path(__file__).parent.parent / "data" / "price_cache"


class HistoryPriceFeed:
    """
    历史价格数据源。
    支持 A股（沪深主板）、ETF、港股。
    三层 fallback：种子数据 → 磁盘缓存 → AKShare API。
    """

    def __init__(
        self,
        cache_dir: Path = PRICE_CACHE_DIR,
        use_seed: bool = True,
        seed_merge: bool = True,
    ):
        """
        Args:
            use_seed:    True = 启动时自动注入内嵌种子数据（离线可用）
            seed_merge:  True = 种子/磁盘/AKShare 三源合并（新源覆盖旧源）
                         False = 各源独立，后加载的完全替换
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.seed_merge = seed_merge
        # instrument → {date_str → {"close": float, "open": float, ...}}
        self._cache: Dict[str, Dict[str, dict]] = {}
        # 已尝试 AKShare 的标的（避免重复请求）
        self._fetched: set = set()

        if use_seed:
            self._load_seed()

    # ── 公开接口 ─────────────────────────────────────────────

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
        """获取 after 日期之后最多 n_days 个交易日的收盘价"""
        end = after + timedelta(days=n_days * 2)
        return self.get_price_range(instrument, after, end)[:n_days]

    def preload(self, instruments: List[str]):
        """批量预加载多个标的"""
        for inst in instruments:
            self._ensure_loaded(inst)

    def data_source_summary(self) -> dict:
        """返回各标的当前数据来源摘要（调试用）"""
        return {
            inst: {
                "days": len(days),
                "min_date": min(days.keys()) if days else None,
                "max_date": max(days.keys()) if days else None,
            }
            for inst, days in self._cache.items()
            if days
        }

    # ── 内部：数据加载 ────────────────────────────────────────

    def _load_seed(self):
        """注入 seed_data.py 中的内嵌历史数据（低优先级，不覆盖已有数据）"""
        try:
            from backtest.seed_data import get_seed_data
            seed = get_seed_data()
            for inst, days in seed.items():
                existing = self._cache.setdefault(inst, {})
                for ds, v in days.items():
                    existing.setdefault(ds, v)  # 种子不覆盖已有（磁盘缓存优先）
            logger.info(f"[PriceFeed] 种子数据注入: {list(seed.keys())}")
        except ImportError:
            logger.debug("[PriceFeed] seed_data 不可用，跳过种子注入")

    def _ensure_loaded(self, instrument: str):
        """
        确保标的数据已加载。
        优先级：种子（已在 __init__ 注入）→ 磁盘缓存 → AKShare
        """
        # 1. 读磁盘缓存（与现有数据合并，磁盘数据更新）
        cache_file = self.cache_dir / f"{instrument.replace('.', '_')}.json"
        if cache_file.exists() and instrument not in self._fetched:
            try:
                disk_data = json.loads(cache_file.read_text(encoding="utf-8"))
                if self.seed_merge:
                    existing = self._cache.setdefault(instrument, {})
                    existing.update(disk_data)  # 磁盘覆盖种子
                else:
                    self._cache[instrument] = disk_data
                logger.info(
                    f"[PriceFeed] 磁盘缓存合并 {instrument}: "
                    f"共 {len(self._cache[instrument])} 天"
                )
                return  # 有磁盘缓存就不再调 AKShare（除非后续主动刷新）
            except Exception as e:
                logger.warning(f"[PriceFeed] 磁盘缓存读取失败 {instrument}: {e}")

        # 2. 已有足够的种子数据时不强制调 AKShare
        if instrument in self._cache and self._cache[instrument]:
            return

        # 3. 调 AKShare 拉全量日线（只在无任何数据时触发）
        if instrument not in self._fetched:
            self._fetch_and_cache(instrument)

    def _fetch_and_cache(self, instrument: str):
        """用 AKShare 拉取日线数据并写入缓存"""
        self._fetched.add(instrument)  # 先标记，避免重复

        try:
            import akshare as ak
        except ImportError:
            logger.warning("[PriceFeed] akshare 未安装，仅使用种子/磁盘数据。pip install akshare")
            self._cache.setdefault(instrument, {})
            return

        code = instrument.split(".")[0]
        suffix = instrument.split(".")[-1].upper() if "." in instrument else ""

        try:
            day_data: dict = {}

            # ETF（510/159/161/588 开头）
            if code.startswith(("51", "15", "16", "58")):
                df = ak.fund_etf_hist_em(symbol=code, adjust="qfq", period="daily")
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        ds = str(row.get("日期", ""))[:10]
                        if ds:
                            day_data[ds] = {
                                "open":   float(row.get("开盘", 0) or 0),
                                "high":   float(row.get("最高", 0) or 0),
                                "low":    float(row.get("最低", 0) or 0),
                                "close":  float(row.get("收盘", 0) or 0),
                                "volume": float(row.get("成交量", 0) or 0),
                            }

            elif suffix == "HK":
                df = ak.stock_hk_daily(symbol=code, adjust="qfq")
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        ds = str(row.get("date", ""))[:10]
                        if ds:
                            day_data[ds] = {
                                "open":   float(row.get("open", 0) or 0),
                                "high":   float(row.get("high", 0) or 0),
                                "low":    float(row.get("low", 0) or 0),
                                "close":  float(row.get("close", 0) or 0),
                                "volume": float(row.get("volume", 0) or 0),
                            }

            else:
                # A股主板
                df = ak.stock_zh_a_hist(symbol=code, adjust="qfq", period="daily")
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        ds = str(row.get("日期", ""))[:10]
                        if ds:
                            day_data[ds] = {
                                "open":   float(row.get("开盘", 0) or 0),
                                "high":   float(row.get("最高", 0) or 0),
                                "low":    float(row.get("最低", row.get("低", 0)) or 0),
                                "close":  float(row.get("收盘", 0) or 0),
                                "volume": float(row.get("成交量", 0) or 0),
                            }

            if not day_data:
                logger.warning(f"[PriceFeed] AKShare 返回空数据: {instrument}")
                self._cache.setdefault(instrument, {})
                return

            # 合并：AKShare 实时数据优先级最高
            if self.seed_merge:
                existing = self._cache.setdefault(instrument, {})
                existing.update(day_data)           # 新数据覆盖种子/磁盘
            else:
                self._cache[instrument] = day_data

            logger.info(
                f"[PriceFeed] AKShare 拉取 {instrument}: {len(day_data)} 天 "
                f"→ 合并后共 {len(self._cache[instrument])} 天"
            )

            # 写磁盘缓存（合并后全量）
            cache_file = self.cache_dir / f"{instrument.replace('.', '_')}.json"
            cache_file.write_text(
                json.dumps(self._cache[instrument], ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info(f"[PriceFeed] 磁盘缓存写入: {cache_file.name}")

        except Exception as e:
            logger.error(f"[PriceFeed] AKShare 拉取失败 {instrument}: {e}")
            self._cache.setdefault(instrument, {})
