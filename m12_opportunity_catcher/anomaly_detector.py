"""
m12_opportunity_catcher/anomaly_detector.py — 价格异动检测 v2

设计原则（见 PRINCIPLES.md）：
  1. 价格是最终验证 — 但检测层要灵敏，过滤层（溯因+M3）要精准
  2. 第一道检测宽松（降低阈值+N日累计），宁可错杀不可漏过
  3. 第二道溯因严格（质量关），找不到原因的放弃
  4. 市场差异化 — A股/港股/美股不同扫描模式

异动判定条件 v2（阈值降低 + 新增条件）:
  条件A: 日涨幅 > 1.5σ  （原2.0）
  条件B: 日涨幅 > 1.5×ATR（原2.0）
  条件C: 成交量 > 1.2×均量（原1.5）
  条件D(NEW): N日累计涨幅 > 2σ  （抓连续上涨）
  条件E(NEW): 超额收益(α) > 2σ_α（抓相对强势）

  通过条件: 至少满足2个条件(A/B/C) OR 单日涨幅≥7% OR N日累计异动

  confidence评分: 综合所有条件加权，供M3参考
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
from m12_opportunity_catcher.stock_universe import StockUniverse

logger = logging.getLogger(__name__)

# ── Baostock 连接池（供指数数据获取） ──
_bs = None
def _bs_get():
    global _bs
    if _bs is None:
        import baostock as bs; bs.login(); _bs = bs
    return _bs


class AnomalyDetector:
    """价格异动检测器 v2

    v2 改进:
      - 降低默认阈值 (2.0→1.5, 量比1.5→1.2)
      - 新增 N 日累计异动检测（抓连续上涨的股票）
      - 新增相对强度（α超额收益）检测
      - 新增综合置信度评分
    """

    _INDEX_MAP = {
        Market.A_SHARE: ("000300.SH", "沪深300指数"),
        Market.HK: ("HSI.HK", "恒生指数"),
        Market.US: ("SPY.US", "标普500ETF"),
    }

    def __init__(
        self,
        atr_period: int = 14,
        lookback_days: int = 20,
        sigma_threshold: float = 1.5,
        atr_threshold: float = 1.5,
        volume_threshold: float = 1.2,
        n_day_windows: tuple = (3, 5),
        min_price: float = 1.0,
        stock_universe: Optional[StockUniverse] = None,
    ):
        self.atr_period = atr_period
        self.lookback_days = lookback_days
        self.sigma_threshold = sigma_threshold
        self.atr_threshold = atr_threshold
        self.volume_threshold = volume_threshold
        self.n_day_windows = n_day_windows
        self.min_price = min_price
        self.stock_universe = stock_universe or StockUniverse()

    # ════════════════════════════════════════════════════════════
    # 公开接口
    # ════════════════════════════════════════════════════════════

    def scan_daily(
        self,
        market: Market,
        price_feed=None,
        stock_list: Optional[List[str]] = None,
        scan_date: Optional[date] = None,
    ) -> List[PriceAnomaly]:
        """盘后全量扫描（A股 15:30，港股 16:30，美股次日早晨）

        改进 v2: 自动获取指数数据，检测相对强度异动。
        """
        if scan_date is None:
            scan_date = date.today()

        # 获取指数数据（全市场共用一份）
        index_data = self._get_index_prices(market, scan_date)

        anomalies = []
        if stock_list is None:
            stock_list = self._get_default_stock_list(market)

        for instrument in stock_list:
            try:
                anomaly = self._check_instrument(
                    instrument, market, price_feed, scan_date, index_data
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
        """盘中快速扫描（每30分钟触发一次）"""
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

    # ════════════════════════════════════════════════════════════
    # 核心检测逻辑 v2
    # ════════════════════════════════════════════════════════════

    def _check_instrument(
        self,
        instrument: str,
        market: Market,
        price_feed,
        scan_date: date,
        index_data: Optional[dict] = None,
    ) -> Optional[PriceAnomaly]:
        """检查单只股票是否异动（盘后模式 v2）

        新增:
          - N 日累计异动 (条件 D)
          - 相对强度异动 (条件 E)
          - 综合置信度评分
        """
        if price_feed is None:
            return None

        hist_data = self._get_historical_prices(instrument, market, price_feed, scan_date)
        if hist_data is None:
            return None

        prices, volumes = hist_data

        if len(prices) < self.lookback_days:
            return None

        current_price = prices[-1]
        if current_price < self.min_price:
            return None

        baseline_stats = self._compute_baseline(prices[:-1], volumes[:-1])
        if baseline_stats is None:
            return None

        mu, sigma, atr, avg_vol = baseline_stats

        # ── 基础指标 ──
        daily_change_pct = (current_price - prices[-2]) / prices[-2] * 100 if len(prices) > 1 else 0
        current_vol = volumes[-1] if len(volumes) > 0 else 1
        volume_ratio = current_vol / avg_vol if avg_vol > 0 else 0

        if sigma == 0 or atr == 0:
            return None

        sigma_multiple = abs(daily_change_pct) / sigma
        atr_multiple = abs(current_price - prices[-2]) / atr

        # ── 标准条件 (A/B/C): 单日异动 ──
        cond_a = sigma_multiple >= self.sigma_threshold
        cond_b = atr_multiple >= self.atr_threshold
        cond_c = volume_ratio >= self.volume_threshold
        standard_conditions_met = sum([cond_a, cond_b, cond_c])

        # ── 条件 D: N 日累计异动 ──
        best_n_day_sigma = 0.0
        best_n_day_return = 0.0
        best_n_day_win = 0
        is_n_day_anomaly = False

        for n in self.n_day_windows:
            if len(prices) <= n:
                continue
            cum_return = (prices[-1] - prices[-1-n]) / prices[-1-n] * 100
            rolling_returns = np.array([
                (prices[i+n] - prices[i]) / prices[i] * 100
                for i in range(max(0, len(prices)-self.lookback_days-n), len(prices)-n)
            ])
            if len(rolling_returns) < 5:
                continue
            cum_sigma = float(np.std(rolling_returns))
            if cum_sigma > 0:
                cum_sigma_m = abs(cum_return) / cum_sigma
                if cum_sigma_m > best_n_day_sigma:
                    best_n_day_sigma = cum_sigma_m
                    best_n_day_return = cum_return
                    best_n_day_win = n
                if cum_sigma_m >= 2.0:
                    is_n_day_anomaly = True

        # ── 条件 E: 相对强度 (α超额收益) ──
        alpha = 0.0
        alpha_sigma_m = 0.0
        index_return = 0.0
        is_alpha_anomaly = False

        if index_data is not None:
            alpha_metrics = self._compute_relative_strength(
                prices, index_data["prices"],
                None, index_data.get("dates"),
            )
            if alpha_metrics:
                alpha, alpha_sigma_m, idx_ret = alpha_metrics
                alpha_pct = alpha  # 已算好
                index_return = idx_ret
                is_alpha_anomaly = alpha_sigma_m >= 2.0

        # ── 综合判定 ──
        is_limit_up = self._is_limit_up(current_price, prices[-2], market)
        is_limit_down = self._is_limit_down(current_price, prices[-2], market)
        is_large_move = abs(daily_change_pct) >= 7.0

        # 通过条件: 标准≥2 OR 大涨 OR N日累计异动 OR (相对强度异动 AND 至少1标准条件)
        passed = (
            standard_conditions_met >= 2
            or is_limit_up
            or is_large_move
            or is_n_day_anomaly
            or (is_alpha_anomaly and standard_conditions_met >= 1)
        )

        if not passed:
            return None

        # ── 置信度评分 ──
        anomaly_confidence = self._compute_confidence(
            sigma_multiple, atr_multiple, volume_ratio,
            best_n_day_sigma, alpha_sigma_m,
        )

        # ── 分类 ──
        n_day_change_pct = (current_price - prices[0]) / prices[0] * 100
        anomaly_type = self._classify_anomaly(
            n_day_change_pct, daily_change_pct, volume_ratio, is_limit_up,
            n_days_win=best_n_day_win,
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
            # N日累计
            n_days=best_n_day_win or 1,
            cumulative_return_pct=round(best_n_day_return, 2),
            cumulative_sigma_multiple=round(best_n_day_sigma, 2),
            # 相对强度
            alpha_pct=round(alpha, 2),
            alpha_sigma_multiple=round(alpha_sigma_m, 2),
            index_return_pct=round(index_return, 2),
            # 置信度
            anomaly_confidence=round(anomaly_confidence, 3),
            baseline_price=round(prices[-2], 3) if len(prices) > 1 else round(current_price, 3),
            anomaly_price=round(current_price, 3),
            is_limit_up=is_limit_up,
            is_limit_down=is_limit_down,
        )

    def _check_intraday(self, instrument, market, price_feed,
                        min_change_pct=5.0, min_volume_ratio=2.0) -> Optional[PriceAnomaly]:
        """盘中异动检测（无 v2 变化）"""
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
        is_limit_down = self._is_limit_down(current_price, prev_close, market)

        anomaly_type = AnomalyType.INTRADAY_SPIKE
        if is_limit_up:
            anomaly_type = AnomalyType.LIMIT_UP
        elif change_pct > 0:
            anomaly_type = AnomalyType.DAILY_SURGE

        return PriceAnomaly(
            instrument=instrument, market=market,
            anomaly_type=anomaly_type.value, anomaly_date=date.today(),
            price_change_pct=round(change_pct, 2),
            atr_multiple=0.0, sigma_multiple=0.0, volume_ratio=0.0,
            baseline_price=round(prev_close, 3),
            anomaly_price=round(current_price, 3),
            n_days=1, is_limit_up=is_limit_up,
            is_limit_down=is_limit_down,
        )

    # ════════════════════════════════════════════════════════════
    # 新增: N 日累计异动 + 相对强度 + 置信度评分
    # ════════════════════════════════════════════════════════════

    @staticmethod
    def _compute_confidence(sigma_m: float, atr_m: float, vol_r: float,
                            n_day_sigma_m: float, alpha_sigma_m: float) -> float:
        """计算综合置信度 (0-1)"""
        score = 0.0
        # 单日条件权重
        score += min(sigma_m / 3.0, 1.0) * 0.25
        score += min(atr_m / 3.0, 1.0) * 0.25
        score += min(vol_r / 2.5, 1.0) * 0.15
        # N日累计
        score += min(n_day_sigma_m / 3.0, 1.0) * 0.20
        # 相对强度
        score += min(alpha_sigma_m / 3.0, 1.0) * 0.15
        return min(score, 1.0)

    @staticmethod
    def _compute_relative_strength(
        stock_prices: np.ndarray,
        index_prices: np.ndarray,
        stock_dates: Optional[List[date]] = None,
        index_dates: Optional[List[date]] = None,
    ) -> Optional[Tuple[float, float, float]]:
        """计算相对强度 (α超额收益)

        返回: (alpha_pct, alpha_sigma_multiple, index_return_pct)
              alpha = stock_return - index_return (当日)
              若无法计算返回 None
        """
        if len(stock_prices) < 3 or len(index_prices) < 3:
            return None

        # 尝试时间对齐（如果有日期）
        if stock_dates and index_dates:
            last_date = stock_dates[-1]
            try:
                idx_idx = index_dates.index(last_date)
                aligned_stock = stock_prices[-1]
                aligned_index = index_prices[idx_idx]
                prev_stock = stock_prices[-2]
                prev_idx_idx = max(0, idx_idx - 1)
                prev_index = index_prices[prev_idx_idx]

                stock_ret = (aligned_stock - prev_stock) / prev_stock * 100
                index_ret = (aligned_index - prev_index) / prev_index * 100
                alpha = stock_ret - index_ret

                # 计算 α 的历史标准差
                alpha_list = []
                for i in range(1, min(len(stock_prices)-1, len(index_prices)-1)):
                    try:
                        sd = stock_dates[i]
                        id_ = index_dates[i] if i < len(index_dates) else None
                        if id_ is None:
                            continue
                        sr = (stock_prices[i] - stock_prices[i-1]) / stock_prices[i-1] * 100
                        ir = (index_prices[i] - index_prices[i-1]) / index_prices[i-1] * 100
                        alpha_list.append(sr - ir)
                    except (IndexError, ValueError):
                        continue

                if len(alpha_list) >= 5:
                    alpha_sigma = float(np.std(alpha_list))
                    alpha_sigma_m = abs(alpha) / alpha_sigma if alpha_sigma > 0 else 0
                else:
                    alpha_sigma_m = 0.0

                return (alpha, alpha_sigma_m, index_ret)
            except (ValueError, IndexError):
                return None

        # 无日期：直接取最后一天
        stock_ret = (stock_prices[-1] - stock_prices[-2]) / stock_prices[-2] * 100
        index_ret = (index_prices[-1] - index_prices[-2]) / index_prices[-2] * 100
        alpha = stock_ret - index_ret

        # 粗略估算 α 的 σ（用最近20天）
        n = min(len(stock_prices)-1, 20)
        alpha_list = []
        for i in range(1, n+1):
            sr = (stock_prices[-i] - stock_prices[-i-1]) / stock_prices[-i-1] * 100
            ir = (index_prices[-i] - index_prices[-i-1]) / index_prices[-i-1] * 100
            alpha_list.append(sr - ir)
        alpha_sigma = float(np.std(alpha_list)) if len(alpha_list) >= 5 else 0
        alpha_sigma_m = abs(alpha) / alpha_sigma if alpha_sigma > 0 else 0

        return (alpha, alpha_sigma_m, index_ret)

    # ════════════════════════════════════════════════════════════
    # 指数数据获取
    # ════════════════════════════════════════════════════════════

    def _get_index_prices(self, market: Market, end_date: date) -> Optional[dict]:
        """获取市场指数日线数据（用于相对强度计算）"""
        mapping = self._INDEX_MAP.get(market)
        if mapping is None:
            return None

        index_symbol, _ = mapping
        return self._fetch_baostock_index(index_symbol, end_date)

    @staticmethod
    def _fetch_baostock_index(index_symbol: str, end_date: date) -> Optional[dict]:
        """用 Baostock 获取指数数据 (A股)"""
        if index_symbol.endswith(".SH"):
            bs_code = f"sh.{index_symbol.split('.')[0]}"
        elif index_symbol.endswith(".SZ"):
            bs_code = f"sz.{index_symbol.split('.')[0]}"
        else:
            return None

        try:
            bs = _bs_get()
            start = end_date - timedelta(days=60)
            df = bs.query_history_k_data_plus(
                bs_code, "date,close,volume",
                start_date=start.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
            )
            data = df.get_data()
            if data is None or data.empty:
                return None

            dates, prices, volumes = [], [], []
            for _, r in data.iterrows():
                try:
                    prices.append(float(r["close"]))
                    volumes.append(float(r.get("volume", 0)))
                    dates.append(date.fromisoformat(r["date"]))
                except: continue

            if len(prices) < 10:
                return None
            return {"dates": dates, "prices": np.array(prices), "volumes": np.array(volumes, dtype=float)}
        except Exception as e:
            logger.debug(f"[AnomalyDetector] failed to fetch index {index_symbol}: {e}")
            return None

    # ════════════════════════════════════════════════════════════
    # 原方法（不变或微调）
    # ════════════════════════════════════════════════════════════

    def _compute_baseline(self, prices: np.ndarray, volumes: np.ndarray) -> Optional[Tuple[float, float, float, float]]:
        if len(prices) < 5:
            return None
        daily_returns = np.diff(prices) / prices[:-1] * 100
        mu = float(np.mean(daily_returns))
        sigma = float(np.std(daily_returns))
        high_low = np.abs(np.diff(prices))
        atr = float(np.mean(high_low[-self.atr_period:])) if len(high_low) >= self.atr_period else float(np.mean(high_low))
        avg_vol = float(np.mean(volumes[-self.lookback_days:])) if len(volumes) >= self.lookback_days else float(np.mean(volumes))
        return (mu, sigma, atr, avg_vol)

    @staticmethod
    def _is_limit_up(current: float, prev: float, market: Market) -> bool:
        if prev <= 0: return False
        change_pct = (current - prev) / prev * 100
        if market == Market.A_SHARE:
            return change_pct >= 9.9 or change_pct >= 19.9 or change_pct >= 4.9
        return False

    @staticmethod
    def _is_limit_down(current: float, prev: float, market: Market) -> bool:
        if prev <= 0: return False
        change_pct = (current - prev) / prev * 100
        if market == Market.A_SHARE:
            return change_pct <= -9.9 or change_pct <= -19.9 or change_pct <= -4.9
        return False

    def _classify_anomaly(self, n_day_change: float, daily_change: float,
                          volume_ratio: float, is_limit_up: bool,
                          n_days_win: int = 0) -> AnomalyType:
        if is_limit_up:
            return AnomalyType.LIMIT_UP
        if n_days_win >= 3:
            return AnomalyType.N_DAY_BREAKOUT
        if abs(n_day_change) > abs(daily_change) * 1.5:
            return AnomalyType.N_DAY_BREAKOUT
        if volume_ratio >= 3.0:
            return AnomalyType.VOLUME_SURGE
        return AnomalyType.DAILY_SURGE

    def _get_historical_prices(self, instrument: str, market: Market,
                               price_feed, end_date: date) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        if hasattr(price_feed, 'get_daily_prices') and callable(getattr(price_feed, 'get_daily_prices')):
            result = price_feed.get_daily_prices(instrument, days=self.lookback_days * 2, end_date=end_date)
            if result is not None and 'prices' in result and 'volumes' in result:
                prices = result['prices']
                volumes = result['volumes']
                if len(prices) >= self.lookback_days:
                    return (prices, volumes)

        prices_list, volumes_list = [], []
        start_date = end_date - timedelta(days=self.lookback_days * 3)
        for i in range(self.lookback_days * 3):
            d = start_date + timedelta(days=i)
            if d > end_date: break
            snap = price_feed.get_price(instrument, dt=d)
            if snap is not None and snap.price > 0:
                prices_list.append(snap.price)
                volumes_list.append(snap.volume if snap.volume > 0 else 0)
        if len(prices_list) < self.lookback_days:
            return None
        return (np.array(prices_list), np.array(volumes_list, dtype=float))

    def _get_default_stock_list(self, market: Market) -> List[str]:
        try:
            return self.stock_universe.get_stock_list(market)
        except Exception as e:
            logger.error(f"Failed to get stock list for {market}: {e}")
            return []
