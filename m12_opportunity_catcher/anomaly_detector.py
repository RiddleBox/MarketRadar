"""
m12_opportunity_catcher/anomaly_detector.py — 价格异动检测

设计原则（见 PRINCIPLES.md）：
  1. 价格是最终验证 — 统计显著异动才是信号
  2. 双重条件：ATR + σ + 量比，缺一不可
  3. 市场差异化 — A股/港股/美股不同扫描模式
  4. 涨停不入场 — 标记观察池，不追高

异动判定条件：
  条件A: N日涨幅 > 2σ  （统计显著性）
  条件B: 日涨幅 > 2×ATR （波动率自适应）
  条件C: 成交量 > 1.5×均量 （量价配合）
  通过条件: A AND B AND C
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

from core.schemas import (
    AnomalyType,
    Market,
    PriceAnomaly,
)

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """价格异动检测器"""

    def __init__(
        self,
        atr_period: int = 14,
        lookback_days: int = 20,
        sigma_threshold: float = 2.0,
        atr_threshold: float = 2.0,
        volume_threshold: float = 1.5,
        min_price: float = 1.0,
    ):
        self.atr_period = atr_period
        self.lookback_days = lookback_days
        self.sigma_threshold = sigma_threshold
        self.atr_threshold = atr_threshold
        self.volume_threshold = volume_threshold
        self.min_price = min_price

    def scan_daily(
        self,
        market: Market,
        price_feed=None,
        stock_list: Optional[List[str]] = None,
        scan_date: Optional[date] = None,
    ) -> List[PriceAnomaly]:
        """盘后全量扫描（A股 15:30，港股 16:30，美股次日早晨）

        Args:
            market: 目标市场
            price_feed: 价格数据源（需支持历史日线）
            stock_list: 股票列表，None则扫描全市场
            scan_date: 扫描日期，默认今天

        Returns:
            检测到的异动列表
        """
        if scan_date is None:
            scan_date = date.today()

        anomalies = []

        if stock_list is None:
            stock_list = self._get_default_stock_list(market)

        for instrument in stock_list:
            try:
                anomaly = self._check_instrument(
                    instrument, market, price_feed, scan_date
                )
                if anomaly is not None:
                    anomalies.append(anomaly)
            except Exception as e:
                logger.debug(f"[AnomalyDetector] skip {instrument}: {e}")
                continue

        logger.info(
            f"[AnomalyDetector] scan_daily {market.value} {scan_date}: "
            f"{len(anomalies)} anomalies from {len(stock_list)} stocks"
        )
        return anomalies

    def scan_intraday(
        self,
        market: Market,
        price_feed=None,
        stock_list: Optional[List[str]] = None,
        min_change_pct: float = 5.0,
        min_volume_ratio: float = 2.0,
    ) -> List[PriceAnomaly]:
        """盘中快速扫描（每30分钟触发一次）

        Args:
            market: 目标市场
            price_feed: 实时价格数据源
            stock_list: 股票列表
            min_change_pct: 最小日内涨幅百分比（默认5%）
            min_volume_ratio: 最小量比（默认2倍）

        Returns:
            检测到的盘中异动列表
        """
        anomalies = []

        if stock_list is None:
            stock_list = self._get_default_stock_list(market)

        for instrument in stock_list:
            try:
                anomaly = self._check_intraday(
                    instrument, market, price_feed,
                    min_change_pct=min_change_pct,
                    min_volume_ratio=min_volume_ratio,
                )
                if anomaly is not None:
                    anomalies.append(anomaly)
            except Exception as e:
                logger.debug(f"[AnomalyDetector] intraday skip {instrument}: {e}")
                continue

        logger.info(
            f"[AnomalyDetector] scan_intraday {market.value}: "
            f"{len(anomalies)} anomalies from {len(stock_list)} stocks"
        )
        return anomalies

    def _check_instrument(
        self,
        instrument: str,
        market: Market,
        price_feed,
        scan_date: date,
    ) -> Optional[PriceAnomaly]:
        """检查单只股票是否异动（盘后模式）"""
        if price_feed is None:
            return None

        hist_data = self._get_historical_prices(
            instrument, market, price_feed, scan_date
        )
        if hist_data is None or len(hist_data) < self.lookback_days:
            return None

        prices, volumes = hist_data

        current_price = prices[-1]
        if current_price < self.min_price:
            return None

        baseline_stats = self._compute_baseline(prices[:-1], volumes[:-1])
        if baseline_stats is None:
            return None

        mu, sigma, atr, avg_vol = baseline_stats

        n_day_change_pct = (current_price - prices[0]) / prices[0] * 100
        daily_change_pct = (current_price - prices[-2]) / prices[-2] * 100 if len(prices) > 1 else 0
        current_vol = volumes[-1] if len(volumes) > 0 else 1
        volume_ratio = current_vol / avg_vol if avg_vol > 0 else 0

        if sigma == 0 or atr == 0:
            return None

        sigma_multiple = abs(daily_change_pct) / (sigma) if sigma > 0 else 0
        atr_multiple = abs(current_price - prices[-2]) / atr if atr > 0 else 0

        daily_sigma = prices[-1] - mu if len(prices) > 1 else 0

        condition_a = sigma_multiple >= self.sigma_threshold
        condition_b = atr_multiple >= self.atr_threshold
        condition_c = volume_ratio >= self.volume_threshold

        if not (condition_a and condition_b and condition_c):
            return None

        is_limit_up = self._is_limit_up(current_price, prices[-2], market)
        is_limit_down = self._is_limit_down(current_price, prices[-2], market)

        anomaly_type = self._classify_anomaly(
            n_day_change_pct, daily_change_pct, volume_ratio, is_limit_up
        )

        return PriceAnomaly(
            instrument=instrument,
            market=market,
            anomaly_type=anomaly_type.value,
            anomaly_date=scan_date,
            price_change_pct=round(daily_change_pct, 2),
            atr_multiple=round(atr_multiple, 2),
            sigma_multiple=round(sigma_multiple, 2),
            volume_ratio=round(volume_ratio, 2),
            baseline_price=round(prices[-2], 3),
            anomaly_price=round(current_price, 3),
            n_days=1,
            is_limit_up=is_limit_up,
            is_limit_down=is_limit_down,
        )

    def _check_intraday(
        self,
        instrument: str,
        market: Market,
        price_feed,
        min_change_pct: float = 5.0,
        min_volume_ratio: float = 2.0,
    ) -> Optional[PriceAnomaly]:
        """检查单只股票是否盘中异动"""
        if price_feed is None:
            return None

        snap = price_feed.get_price(instrument)
        if snap is None or snap.price <= 0:
            return None

        current_price = snap.price
        prev_close = snap.prev_close if snap.prev_close and snap.prev_close > 0 else None

        if prev_close is None or prev_close <= 0:
            return None

        change_pct = (current_price - prev_close) / prev_close * 100

        if abs(change_pct) < min_change_pct:
            return None

        is_limit_up = self._is_limit_up(current_price, prev_close, market)

        anomaly_type = AnomalyType.INTRADAY_SPIKE
        if is_limit_up:
            anomaly_type = AnomalyType.LIMIT_UP
        elif change_pct > 0:
            anomaly_type = AnomalyType.DAILY_SURGE

        return PriceAnomaly(
            instrument=instrument,
            market=market,
            anomaly_type=anomaly_type.value,
            anomaly_date=date.today(),
            price_change_pct=round(change_pct, 2),
            atr_multiple=0.0,
            sigma_multiple=0.0,
            volume_ratio=0.0,
            baseline_price=round(prev_close, 3),
            anomaly_price=round(current_price, 3),
            n_days=1,
            is_limit_up=is_limit_up,
            is_limit_down=not is_limit_up and change_pct < -(9 if market == Market.A_SHARE else 5),
        )

    def _compute_baseline(
        self, prices: np.ndarray, volumes: np.ndarray
    ) -> Optional[Tuple[float, float, float, float]]:
        """计算统计基线：均值μ、标准差σ、ATR、均量"""
        if len(prices) < 5:
            return None

        daily_returns = np.diff(prices) / prices[:-1] * 100
        mu = float(np.mean(daily_returns))
        sigma = float(np.std(daily_returns))

        high_low = np.abs(np.diff(prices))
        atr = float(np.mean(high_low[-self.atr_period:])) if len(high_low) >= self.atr_period else float(np.mean(high_low))

        avg_vol = float(np.mean(volumes[-self.lookback_days:])) if len(volumes) >= self.lookback_days else float(np.mean(volumes))

        return (mu, sigma, atr, avg_vol)

    def _is_limit_up(self, current: float, prev: float, market: Market) -> bool:
        """判断是否涨停"""
        if prev <= 0:
            return False
        change_pct = (current - prev) / prev * 100

        if market == Market.A_SHARE:
            return change_pct >= 9.9 or change_pct >= 19.9 or change_pct >= 4.9
        return False

    def _is_limit_down(self, current: float, prev: float, market: Market) -> bool:
        """判断是否跌停"""
        if prev <= 0:
            return False
        change_pct = (current - prev) / prev * 100

        if market == Market.A_SHARE:
            return change_pct <= -9.9 or change_pct <= -19.9 or change_pct <= -4.9
        return False

    def _classify_anomaly(
        self,
        n_day_change: float,
        daily_change: float,
        volume_ratio: float,
        is_limit_up: bool,
    ) -> AnomalyType:
        """分类异动类型"""
        if is_limit_up:
            return AnomalyType.LIMIT_UP
        if abs(n_day_change) > abs(daily_change) * 1.5:
            return AnomalyType.N_DAY_BREAKOUT
        if volume_ratio >= 3.0:
            return AnomalyType.VOLUME_SURGE
        return AnomalyType.DAILY_SURGE

    def _get_historical_prices(
        self,
        instrument: str,
        market: Market,
        price_feed,
        end_date: date,
    ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """获取历史价格数据，返回 (prices, volumes)"""
        start_date = end_date - timedelta(days=self.lookback_days * 2)

        prices_list = []
        volumes_list = []

        for i in range(self.lookback_days * 2):
            d = start_date + timedelta(days=i)
            if d > end_date:
                break

            snap = price_feed.get_price(instrument, dt=d)
            if snap is not None and snap.price > 0:
                prices_list.append(snap.price)
                volumes_list.append(snap.volume if snap.volume > 0 else 0)

        if len(prices_list) < self.lookback_days:
            return None

        return (np.array(prices_list), np.array(volumes_list, dtype=float))

    def _get_default_stock_list(self, market: Market) -> List[str]:
        """获取默认股票列表（主要指数成分股）"""
        if market == Market.A_SHARE:
            return [
                "000001.SZ", "000002.SZ", "000063.SZ", "000333.SZ",
                "000338.SZ", "000425.SZ", "000568.SZ", "000625.SZ",
                "000651.SZ", "000725.SZ", "000776.SZ", "000858.SZ",
                "600000.SH", "600009.SH", "600010.SH", "600016.SH",
                "600019.SH", "600025.SH", "600028.SH", "600029.SH",
                "600030.SH", "600031.SH", "600036.SH", "600048.SH",
                "600050.SH", "600104.SH", "600519.SH", "600585.SH",
                "600887.SH", "601012.SH", "601088.SH", "601111.SH",
                "601166.SH", "601211.SH", "601225.SH", "601288.SH",
                "601318.SH", "601336.SH", "601398.SH", "601601.SH",
                "601628.SH", "601688.SH", "601728.SH", "601766.SH",
                "601857.SH", "601888.SH", "601899.SH", "601919.SH",
                "601985.SH", "601988.SH", "603259.SH",
                "510050.SH", "510300.SH", "510500.SH", "159915.SZ",
            ]
        elif market == Market.HK:
            return [
                "00700.HK", "00005.HK", "00941.HK", "01299.HK",
                "02318.HK", "02382.HK", "03988.HK", "09988.HK",
            ]
        elif market == Market.US:
            return [
                "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
                "META", "TSLA", "BRK-B", "JPM", "V",
            ]
        return []