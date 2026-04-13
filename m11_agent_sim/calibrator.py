"""
m11_agent_sim/calibrator.py — HistoricalCalibrator

功能：
  1. 从 backtest 种子数据加载历史事件
  2. 构建 MarketInput（从 AKShare 历史价格 + 预设情绪快照）
  3. 运行 AgentNetwork 模拟
  4. 多维度校准评分（D-03）：
     - 方向命中率（目标 ≥ 70%）
     - 概率校准误差（预测概率 vs 实际频率）
     - 极值识别召回率（目标 ≥ 60%）
     - 综合得分（加权）

设计原则：
  - 历史事件中 actual_direction 由实际价格（5日收益率）推断
  - 正向>3% → BULLISH，负向<-3% → BEARISH，其余 NEUTRAL
  - 不追求曲线拟合，追求概率分布收敛（D-03）
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from .agent_network import AgentNetwork
from .schemas import (
    AgentOutput,
    CalibrationScore,
    Direction,
    HistoricalEvent,
    MarketInput,
    PriceContext,
    SentimentContext,
    SignalContext,
    SentimentDistribution,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent


class HistoricalCalibrator:
    """
    历史校准器：用种子数据验证 AgentNetwork 的预测质量

    用法：
        calibrator = HistoricalCalibrator()
        events = calibrator.load_seed_events()
        score = calibrator.calibrate(events)
        print(score)
    """

    # 方向判断阈值
    BULLISH_THRESHOLD = 0.03   # 5日涨幅 > 3% → BULLISH
    BEARISH_THRESHOLD = -0.03  # 5日涨幅 < -3% → BEARISH

    # 综合评分权重
    SCORE_WEIGHTS = {
        "direction_accuracy": 0.50,
        "prob_calibration":   0.30,
        "extreme_recall":     0.20,
    }

    def __init__(
        self,
        network: Optional[AgentNetwork] = None,
        market: str = "a_share",
    ):
        self.network = network or AgentNetwork.from_config_file(market)
        self.market = market

    # ── 事件加载 ─────────────────────────────────────────────

    def load_seed_events(self) -> List[HistoricalEvent]:
        """
        从 backtest 种子数据构建 HistoricalEvent 列表。

        种子数据来源：backtest/seed_data.py 中的历史案例
        价格数据：backtest/history_price.py（AKShare 或磁盘缓存）
        """
        events = []
        try:
            from backtest.seed_data import SEED_SIGNALS
        except ImportError:
            logger.warning("[Calibrator] 无法加载种子数据，使用内置事件")
            return self._builtin_events()

        for sig_dict in SEED_SIGNALS:
            try:
                event = self._signal_to_event(sig_dict)
                if event:
                    events.append(event)
            except Exception as e:
                logger.debug(f"[Calibrator] 跳过事件 {sig_dict.get('signal_id','?')}: {e}")

        logger.info(f"[Calibrator] 加载 {len(events)} 个历史事件")
        return events

    def _signal_to_event(self, sig: dict) -> Optional[HistoricalEvent]:
        """将种子信号转换为 HistoricalEvent"""
        date_str = sig.get("discovered_at", "")[:10]
        if not date_str:
            return None

        instrument = sig.get("instrument", "510300.SH")
        description = sig.get("summary", sig.get("description", ""))

        # 构建 MarketInput（使用种子数据中可用的信息）
        signal_dir = sig.get("direction", "BULLISH")
        intensity = float(sig.get("intensity_score", 5))
        confidence = float(sig.get("confidence_score", 5))
        signal_type = sig.get("signal_type", "market_data")

        market_input = MarketInput(
            timestamp=datetime.fromisoformat(date_str),
            market="A_SHARE",
            event_description=description[:100],
            price=self._load_price_context(instrument, date_str),
            sentiment=self._estimate_sentiment_context(date_str, signal_dir),
            signals=SignalContext(
                bullish_count=1 if signal_dir == "BULLISH" else 0,
                bearish_count=1 if signal_dir == "BEARISH" else 0,
                neutral_count=1 if signal_dir == "NEUTRAL" else 0,
                dominant_signal_type=signal_type,
                avg_intensity=intensity,
                avg_confidence=confidence,
                recent_signals=[{
                    "signal_type": signal_type,
                    "description": description[:40],
                    "intensity_score": intensity,
                    "direction": signal_dir,
                }],
            ),
        )

        # 实际方向：从种子数据推断
        actual_5d = self._load_actual_5d_return(instrument, date_str)
        actual_direction: Direction = (
            "BULLISH" if actual_5d > self.BULLISH_THRESHOLD
            else "BEARISH" if actual_5d < self.BEARISH_THRESHOLD
            else "NEUTRAL"
        )
        actual_is_extreme = abs(actual_5d) > 0.08   # 8% 以上为极值

        return HistoricalEvent(
            event_id=sig.get("signal_id", f"ev_{date_str}"),
            date=date_str,
            description=description[:80],
            market_input=market_input,
            actual_direction=actual_direction,
            actual_5d_return=actual_5d,
            actual_is_extreme=actual_is_extreme,
        )

    def _load_price_context(self, instrument: str, date_str: str) -> PriceContext:
        """从 AKShare 历史价格缓存构建 PriceContext"""
        try:
            from backtest.history_price import HistoryPriceFeed
            feed = HistoryPriceFeed()
            date = datetime.fromisoformat(date_str)
            price = feed.get_price(instrument, date)
            if price is None:
                return PriceContext()

            # 计算均线和涨跌幅（取前后数据点）
            prices_20 = []
            for d in range(1, 22):
                p = feed.get_price(instrument, date - timedelta(days=d))
                if p:
                    prices_20.append(p)
            prices_5 = prices_20[:5]

            ma5 = sum(prices_5) / len(prices_5) if prices_5 else price
            ma20 = sum(prices_20) / len(prices_20) if prices_20 else price
            ret5 = (price - prices_5[-1]) / prices_5[-1] if prices_5 else 0.0
            ret20 = (price - prices_20[-1]) / prices_20[-1] if prices_20 else 0.0

            return PriceContext(
                instrument=instrument,
                current_price=price,
                price_5d_chg_pct=ret5,
                price_20d_chg_pct=ret20,
                ma5=ma5,
                ma20=ma20,
                above_ma5=price > ma5,
                above_ma20=price > ma20,
                volume_ratio=1.0,   # 历史量比暂不可用
            )
        except Exception as e:
            logger.debug(f"[Calibrator] 价格加载失败 {instrument}/{date_str}: {e}")
            return PriceContext()

    def _load_actual_5d_return(self, instrument: str, date_str: str) -> float:
        """计算事件发生后5日的实际收益率"""
        try:
            from backtest.history_price import HistoryPriceFeed
            feed = HistoryPriceFeed()
            date = datetime.fromisoformat(date_str)
            entry = feed.get_price(instrument, date)
            if entry is None:
                return 0.0
            # 找5个交易日后的价格（最多往后查15天）
            for d in range(1, 16):
                exit_p = feed.get_price(instrument, date + timedelta(days=d))
                if exit_p:
                    # 简单计数：找到5个交易日数据
                    pass
            # 用第5~10天的价格作为5日后价格
            exit_price = None
            for d in range(5, 15):
                p = feed.get_price(instrument, date + timedelta(days=d))
                if p:
                    exit_price = p
                    break
            if exit_price is None or entry == 0:
                return 0.0
            return (exit_price - entry) / entry
        except Exception:
            return 0.0

    def _estimate_sentiment_context(self, date_str: str, signal_dir: str) -> SentimentContext:
        """
        估算历史情绪上下文（M10 历史数据暂无存档，用信号方向代理）
        Phase 2：当 M10 积累足够历史后，从数据库查询真实历史快照
        """
        # 用已知的几个关键时间点的情绪估计
        known_contexts = {
            "2024-09-24": SentimentContext(
                fear_greed_index=35.0, sentiment_label="恐惧",
                northbound_flow=120.0, advance_decline_ratio=0.72,
                weibo_sentiment=0.2,
            ),
            "2024-10-08": SentimentContext(
                fear_greed_index=78.0, sentiment_label="贪婪",
                northbound_flow=85.0, advance_decline_ratio=0.85,
                weibo_sentiment=0.7,
            ),
            "2025-02-17": SentimentContext(
                fear_greed_index=55.0, sentiment_label="中性",
                northbound_flow=15.0, advance_decline_ratio=0.52,
                weibo_sentiment=0.1,
            ),
            "2025-04-07": SentimentContext(
                fear_greed_index=22.0, sentiment_label="恐惧",
                northbound_flow=-95.0, advance_decline_ratio=0.28,
                weibo_sentiment=-0.5,
            ),
        }
        if date_str in known_contexts:
            return known_contexts[date_str]
        # 默认：用信号方向估算
        if signal_dir == "BULLISH":
            return SentimentContext(fear_greed_index=55.0, northbound_flow=30.0, advance_decline_ratio=0.55)
        elif signal_dir == "BEARISH":
            return SentimentContext(fear_greed_index=35.0, northbound_flow=-30.0, advance_decline_ratio=0.40)
        return SentimentContext()

    def _builtin_events(self) -> List[HistoricalEvent]:
        """内置的4个关键历史事件（不依赖种子数据文件）"""
        events_raw = [
            {
                "event_id": "ev_20240924",
                "date": "2024-09-24",
                "description": "央行宣布降准50bp+降息，历史性宽松政策组合",
                "signal_dir": "BULLISH",
                "intensity": 9.5,
                "actual_5d_return": 0.165,
                "actual_is_extreme": True,
            },
            {
                "event_id": "ev_20241008",
                "date": "2024-10-08",
                "description": "国庆后首个交易日，市场高开低走，游资出货",
                "signal_dir": "BEARISH",
                "intensity": 7.0,
                "actual_5d_return": -0.112,
                "actual_is_extreme": True,
            },
            {
                "event_id": "ev_20250217",
                "date": "2025-02-17",
                "description": "DeepSeek AI突破，科技股带动行情",
                "signal_dir": "BULLISH",
                "intensity": 8.0,
                "actual_5d_return": 0.042,
                "actual_is_extreme": False,
            },
            {
                "event_id": "ev_20250407",
                "date": "2025-04-07",
                "description": "美国关税冲击，外资大幅流出",
                "signal_dir": "BEARISH",
                "intensity": 8.5,
                "actual_5d_return": -0.045,
                "actual_is_extreme": False,
            },
        ]
        events = []
        for raw in events_raw:
            sent = self._estimate_sentiment_context(raw["date"], raw["signal_dir"])
            direction: Direction = (
                "BULLISH" if raw["actual_5d_return"] > self.BULLISH_THRESHOLD
                else "BEARISH" if raw["actual_5d_return"] < self.BEARISH_THRESHOLD
                else "NEUTRAL"
            )
            market_input = MarketInput(
                timestamp=datetime.fromisoformat(raw["date"]),
                market="A_SHARE",
                event_description=raw["description"],
                sentiment=sent,
                signals=SignalContext(
                    bullish_count=1 if raw["signal_dir"] == "BULLISH" else 0,
                    bearish_count=1 if raw["signal_dir"] == "BEARISH" else 0,
                    avg_intensity=raw["intensity"],
                    avg_confidence=7.0,
                    dominant_signal_type="macro",
                ),
                price=self._load_price_context("510300.SH", raw["date"]),
            )
            events.append(HistoricalEvent(
                event_id=raw["event_id"],
                date=raw["date"],
                description=raw["description"],
                market_input=market_input,
                actual_direction=direction,
                actual_5d_return=raw["actual_5d_return"],
                actual_is_extreme=raw["actual_is_extreme"],
            ))
        return events

    # ── 校准评分 ─────────────────────────────────────────────

    def calibrate(self, events: Optional[List[HistoricalEvent]] = None) -> CalibrationScore:
        """
        对历史事件运行模拟，计算多维度校准评分。
        """
        if events is None:
            events = self.load_seed_events()
        if not events:
            logger.warning("[Calibrator] 无历史事件可校准")
            return CalibrationScore()

        details = []
        direction_hits = 0
        prob_errors = []
        extreme_events = [e for e in events if e.actual_is_extreme]
        extreme_hits = 0

        for event in events:
            dist = self.network.run(event.market_input)
            hit = dist.direction == event.actual_direction
            if hit:
                direction_hits += 1

            # 概率校准误差（预测多方概率 vs 实际方向）
            actual_bull = 1.0 if event.actual_direction == "BULLISH" else 0.0
            prob_error = abs(dist.bullish_prob - actual_bull)
            prob_errors.append(prob_error)

            # 极值识别
            if event.actual_is_extreme:
                sim_extreme = dist.intensity >= 7.0
                if sim_extreme:
                    extreme_hits += 1

            details.append({
                "event_id": event.event_id,
                "date": event.date,
                "description": event.description[:50],
                "actual": event.actual_direction,
                "simulated": dist.direction,
                "hit": hit,
                "bullish_prob": dist.bullish_prob,
                "actual_5d_return": event.actual_5d_return,
                "prob_error": prob_error,
                "intensity": dist.intensity,
                "confidence": dist.confidence,
            })
            logger.info(
                f"[Calibrator] {event.date} {event.description[:30]} | "
                f"实际:{event.actual_direction} 模拟:{dist.direction} {'✓' if hit else '✗'} | "
                f"多概率:{dist.bullish_prob:.0%}"
            )

        n = len(events)
        direction_accuracy = direction_hits / n
        avg_prob_err = sum(prob_errors) / len(prob_errors) if prob_errors else 0.5
        extreme_recall = extreme_hits / len(extreme_events) if extreme_events else 1.0

        # 综合得分（0~100）
        dir_score = direction_accuracy * 100
        prob_score = max(0, (1 - avg_prob_err / 0.5) * 100)   # 误差0→100分，误差0.5→0分
        ext_score = extreme_recall * 100

        composite = (
            dir_score * self.SCORE_WEIGHTS["direction_accuracy"] +
            prob_score * self.SCORE_WEIGHTS["prob_calibration"] +
            ext_score * self.SCORE_WEIGHTS["extreme_recall"]
        )
        pass_threshold = direction_accuracy >= 0.70 and composite >= 55.0

        score = CalibrationScore(
            total_events=n,
            direction_hits=direction_hits,
            direction_accuracy=round(direction_accuracy, 4),
            prob_calibration_err=round(avg_prob_err, 4),
            extreme_recall=round(extreme_recall, 4),
            composite_score=round(composite, 2),
            pass_threshold=pass_threshold,
            details=details,
        )

        logger.info(
            f"[Calibrator] 校准完成 | "
            f"方向命中:{direction_accuracy:.0%} | "
            f"概率误差:{avg_prob_err:.3f} | "
            f"极值召回:{extreme_recall:.0%} | "
            f"综合:{composite:.1f} | "
            f"{'✅ 通过' if pass_threshold else '❌ 未通过'}"
        )
        return score
