"""
backtest/strategy_backtest.py — 策略级回测引擎

在 BacktestEngine 基础上增加：
  - 按 Strategy 参数过滤案例（信号类型/强度/置信/方向）
  - ComboFilter 的多信号类型 AND 组合逻辑
  - 完整的策略对比报告（多策略并排，胜率/盈亏/最大回撤/盈亏比）

设计原则：
  - 前向隔离：创建日之后才使用的价格数据不参与入场判断
  - 离线优先：优先用种子数据，无数据时尝试磁盘缓存，不阻塞
  - 策略无状态：Strategy 只描述参数，不存储回测结果
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backtest.history_price import HistoryPriceFeed
from backtest.strategies import Strategy, STRATEGIES

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
CACHE_DIR = ROOT / "data" / "price_cache"


# ─────────────────────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────────────────────

@dataclass
class StrategyTrade:
    """策略回测中的单笔交易"""
    strategy_name: str
    instrument: str
    signal_type: str
    signal_direction: str
    signal_intensity: float
    signal_confidence: float
    time_horizon: str
    signal_date: date           # 信号发出日
    entry_date: Optional[date]  # 实际入场日（T+1）
    entry_price: Optional[float]
    exit_date: Optional[date]
    exit_price: Optional[float]
    exit_reason: str            # STOP_LOSS / TAKE_PROFIT / TIMEOUT / NO_DATA
    realized_pnl_pct: Optional[float]
    days_held: int
    max_favorable_excursion: float   # 持仓期间最大浮盈（MFE）
    max_adverse_excursion: float     # 持仓期间最大浮亏（MAE）
    price_path: List[Tuple[str, float]] = field(default_factory=list)
    note: str = ""

    @property
    def is_win(self) -> bool:
        return (self.realized_pnl_pct or 0) > 0

    @property
    def is_completed(self) -> bool:
        return self.exit_reason != "NO_DATA"


@dataclass
class StrategyResult:
    """单个策略的完整回测结果"""
    strategy: Strategy
    trades: List[StrategyTrade]

    @property
    def completed_trades(self) -> List[StrategyTrade]:
        return [t for t in self.trades if t.is_completed]

    @property
    def win_rate(self) -> float:
        ct = self.completed_trades
        if not ct:
            return 0.0
        return sum(1 for t in ct if t.is_win) / len(ct)

    @property
    def avg_pnl(self) -> float:
        ct = self.completed_trades
        if not ct:
            return 0.0
        return sum(t.realized_pnl_pct or 0 for t in ct) / len(ct)

    @property
    def profit_factor(self) -> float:
        """总盈利 / |总亏损|，> 1 = 正期望"""
        gross_profit = sum(t.realized_pnl_pct for t in self.completed_trades
                           if (t.realized_pnl_pct or 0) > 0)
        gross_loss = abs(sum(t.realized_pnl_pct for t in self.completed_trades
                             if (t.realized_pnl_pct or 0) < 0))
        return gross_profit / gross_loss if gross_loss > 0 else float("inf")

    @property
    def max_drawdown(self) -> float:
        """所有交易中 MAE 的最大值（最大不利偏移）"""
        ct = self.completed_trades
        if not ct:
            return 0.0
        return min(t.max_adverse_excursion for t in ct)

    @property
    def avg_holding_days(self) -> float:
        ct = self.completed_trades
        if not ct:
            return 0.0
        return sum(t.days_held for t in ct) / len(ct)

    def summary(self) -> dict:
        ct = self.completed_trades
        wins = [t for t in ct if t.is_win]
        losses = [t for t in ct if not t.is_win]
        stop_losses = [t for t in ct if t.exit_reason == "STOP_LOSS"]
        take_profits = [t for t in ct if t.exit_reason == "TAKE_PROFIT"]
        timeouts = [t for t in ct if t.exit_reason == "TIMEOUT"]
        return {
            "strategy": self.strategy.name,
            "description": self.strategy.description,
            "params": {
                "signal_types": self.strategy.signal_types,
                "require_all": self.strategy.signal_types_require_all,
                "min_intensity": self.strategy.min_intensity,
                "min_confidence": self.strategy.min_confidence,
                "stop_loss_pct": self.strategy.stop_loss_pct,
                "take_profit_pct": self.strategy.take_profit_pct,
                "max_holding_days": self.strategy.max_holding_days,
            },
            "total_cases": len(self.trades),
            "completed": len(ct),
            "skipped_no_data": len(self.trades) - len(ct),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(self.win_rate * 100, 1),
            "avg_pnl_pct": round(self.avg_pnl * 100, 2),
            "avg_win_pct":  round(sum(t.realized_pnl_pct or 0 for t in wins) / len(wins) * 100, 2)  if wins else 0,
            "avg_loss_pct": round(sum(t.realized_pnl_pct or 0 for t in losses) / len(losses) * 100, 2) if losses else 0,
            "profit_factor": round(self.profit_factor, 2),
            "max_drawdown_pct": round(self.max_drawdown * 100, 2),
            "avg_holding_days": round(self.avg_holding_days, 1),
            "stop_loss_rate": round(len(stop_losses) / len(ct) * 100, 1) if ct else 0,
            "take_profit_rate": round(len(take_profits) / len(ct) * 100, 1) if ct else 0,
            "timeout_rate": round(len(timeouts) / len(ct) * 100, 1) if ct else 0,
        }


# ─────────────────────────────────────────────────────────────
# 策略回测引擎
# ─────────────────────────────────────────────────────────────

@dataclass
class SignalEvent:
    """输入信号事件（从历史信号 or 测试数据创建）"""
    instrument: str
    market: str
    signal_type: str
    signal_direction: str
    signal_intensity: float
    signal_confidence: float
    time_horizon: str
    signal_date: date
    note: str = ""


class StrategyBacktester:
    """
    策略级回测器。

    用法：
        bt = StrategyBacktester()
        events = bt.build_events_from_seed()     # 从种子数据构建虚拟事件
        # 或从真实历史机会文件加载：
        # events = bt.load_events_from_opportunities()

        results = bt.run_all(events)             # 所有策略并行回测
        report = bt.compare_strategies(results)  # 生成对比报告
    """

    def __init__(self, cache_dir: Optional[Path] = None, use_seed: bool = True):
        self.feed = HistoryPriceFeed(
            cache_dir=cache_dir or CACHE_DIR,
            use_seed=use_seed,
            seed_merge=True,
        )

    # ── 事件构建 ──────────────────────────────────────────────

    def build_events_from_seed(self) -> List[SignalEvent]:
        """
        从种子价格数据中挑选关键历史事件构建信号。

        这些是 2024Q3~2025Q1 A 股市场的真实宏观/政策驱动节点：
          - 2024-09-24: 央行降准降息+房地产政策组合拳（宏观+政策）
          - 2024-09-25: 政治局会议释放积极信号（宏观）
          - 2024-10-12: 财政部扩大赤字/特别国债公告（宏观+政策）
          - 2024-11-08: 人大批准10万亿化债方案（宏观+政策）
          - 2025-01-03: 新年开市，两会预期驱动（宏观）
          - 2025-02-14: DeepSeek 引发科技板块行情（事件+资金流）
          - 2025-03-05: 两会政府工作报告（政策+宏观）
          - 2024-07-22: LPR意外降息（宏观）
          - 2024-08-09: 资金面偏宽松，北向持续流入（资金流）
        """
        events = [
            # ── 宏观大事件（强度高）──
            SignalEvent(
                instrument="510300.SH", market="A_SHARE",
                signal_type="macro", signal_direction="BULLISH",
                signal_intensity=9.5, signal_confidence=9.0,
                time_horizon="medium",
                signal_date=date(2024, 9, 24),
                note="央行降准50bp+降息25bp+房地产政策组合拳",
            ),
            SignalEvent(
                instrument="510300.SH", market="A_SHARE",
                signal_type="macro", signal_direction="BULLISH",
                signal_intensity=9.0, signal_confidence=8.5,
                time_horizon="medium",
                signal_date=date(2024, 9, 25),
                note="政治局会议：强调扩大内需+稳房市，超预期积极",
            ),
            SignalEvent(
                instrument="510300.SH", market="A_SHARE",
                signal_type="macro", signal_direction="BULLISH",
                signal_intensity=8.5, signal_confidence=8.0,
                time_horizon="medium",
                signal_date=date(2024, 10, 12),
                note="财政部发布会：扩大赤字+发行特别国债+化债方案",
            ),
            SignalEvent(
                instrument="510300.SH", market="A_SHARE",
                signal_type="macro", signal_direction="BULLISH",
                signal_intensity=8.0, signal_confidence=7.5,
                time_horizon="medium",
                signal_date=date(2024, 11, 8),
                note="人大批准10万亿化债决议，财政大招落地",
            ),
            SignalEvent(
                instrument="510300.SH", market="A_SHARE",
                signal_type="macro", signal_direction="BULLISH",
                signal_intensity=7.0, signal_confidence=6.5,
                time_horizon="short",
                signal_date=date(2025, 1, 3),
                note="新年开市+两会预期，A股开门红",
            ),
            SignalEvent(
                instrument="510300.SH", market="A_SHARE",
                signal_type="macro", signal_direction="BULLISH",
                signal_intensity=7.5, signal_confidence=7.0,
                time_horizon="medium",
                signal_date=date(2025, 3, 5),
                note="两会政府工作报告：GDP目标5%，扩大内需超预期",
            ),
            SignalEvent(
                instrument="510300.SH", market="A_SHARE",
                signal_type="macro", signal_direction="BULLISH",
                signal_intensity=6.5, signal_confidence=6.0,
                time_horizon="short",
                signal_date=date(2024, 7, 22),
                note="LPR意外降息10bp，宽松预期强化",
            ),

            # ── 政策/产业事件 ──
            SignalEvent(
                instrument="510300.SH", market="A_SHARE",
                signal_type="policy", signal_direction="BULLISH",
                signal_intensity=8.0, signal_confidence=7.5,
                time_horizon="short",
                signal_date=date(2024, 9, 24),
                note="央行+住建部+金融监管联合政策，救楼市力度空前",
            ),
            SignalEvent(
                instrument="510300.SH", market="A_SHARE",
                signal_type="policy", signal_direction="BULLISH",
                signal_intensity=7.5, signal_confidence=7.0,
                time_horizon="short",
                signal_date=date(2024, 10, 12),
                note="财政政策超预期放量，赤字率突破3%",
            ),
            SignalEvent(
                instrument="510300.SH", market="A_SHARE",
                signal_type="policy", signal_direction="BULLISH",
                signal_intensity=6.5, signal_confidence=6.0,
                time_horizon="short",
                signal_date=date(2025, 3, 5),
                note="两会：新兴产业补贴+绿色转型专项资金",
            ),

            # ── 资金流事件 ──
            SignalEvent(
                instrument="510300.SH", market="A_SHARE",
                signal_type="capital_flow", signal_direction="BULLISH",
                signal_intensity=7.0, signal_confidence=6.5,
                time_horizon="short",
                signal_date=date(2024, 8, 9),
                note="北向资金连续5日净流入，单日超100亿",
            ),
            SignalEvent(
                instrument="510300.SH", market="A_SHARE",
                signal_type="capital_flow", signal_direction="BULLISH",
                signal_intensity=8.5, signal_confidence=8.0,
                time_horizon="short",
                signal_date=date(2024, 9, 25),
                note="节后成交量放大3倍，北向单日净流入150亿",
            ),
            SignalEvent(
                instrument="510300.SH", market="A_SHARE",
                signal_type="capital_flow", signal_direction="BULLISH",
                signal_intensity=7.5, signal_confidence=7.0,
                time_horizon="short",
                signal_date=date(2025, 2, 14),
                note="AI+科技主线资金大幅流入，ETF申购创历史新高",
            ),

            # ── 事件驱动 ──
            SignalEvent(
                instrument="588000.SH", market="A_SHARE",
                signal_type="event_driven", signal_direction="BULLISH",
                signal_intensity=9.0, signal_confidence=8.5,
                time_horizon="short",
                signal_date=date(2025, 2, 14),
                note="DeepSeek R1开源震惊全球，科创50暴力拉升",
            ),
            # ── 看空事件 ──
            SignalEvent(
                instrument="510300.SH", market="A_SHARE",
                signal_type="macro", signal_direction="BEARISH",
                signal_intensity=7.0, signal_confidence=6.5,
                time_horizon="short",
                signal_date=date(2025, 4, 3),
                note="特朗普宣布对华加征额外关税，中美贸易摩擦升级",
            ),
        ]
        return events

    def load_events_from_opportunities(self, opp_dir: Optional[Path] = None) -> List[SignalEvent]:
        """
        从真实历史机会文件（data/opportunities/*.json）加载信号事件。
        用于将真实 M3 产出接入策略回测。

        兼容两类输入：
        1. OpportunityObject 风格（当前主链产物）
        2. 历史/手工导出的较松散 dict
        """
        opp_path = opp_dir or (ROOT / "data" / "opportunities")
        events = []
        if not opp_path.exists():
            logger.warning(f"[StrategyBacktester] 机会目录不存在: {opp_path}")
            return events

        def _pick_signal_type(opp: dict) -> str:
            rel_signals = opp.get("related_signals", [])
            if rel_signals and isinstance(rel_signals[0], dict):
                signal_types = {str(s.get("signal_type", "")).lower() for s in rel_signals if isinstance(s, dict)}
                if {"macro", "capital_flow"}.issubset(signal_types):
                    return "capital_flow"
                for candidate in ["macro", "policy", "industry", "capital_flow", "event_driven"]:
                    if candidate in signal_types:
                        return candidate

            text = " ".join([
                str(opp.get("opportunity_title", "")),
                str(opp.get("opportunity_thesis", "")),
                str(opp.get("why_now", "")),
            ] + [str(x) for x in (opp.get("supporting_evidence") or [])]).lower()
            if any(k in text for k in ["northbound", "北向", "资金流", "净流入", "净流出"]):
                return "capital_flow"
            if any(k in text for k in ["政策", "policy", "监管", "产业"]):
                return "policy"
            if any(k in text for k in ["行业", "板块", "新能源", "半导体", "地产", "银行", "科技"]):
                return "industry"
            if any(k in text for k in ["macro", "央行", "货币", "财政", "降准", "降息"]):
                return "macro"
            return "event_driven"

        def _pick_horizon(opp: dict) -> str:
            window = opp.get("opportunity_window", {})
            if isinstance(window, dict):
                start = str(window.get("start", ""))[:10]
                end = str(window.get("end", ""))[:10]
                if start and end:
                    try:
                        days = (date.fromisoformat(end) - date.fromisoformat(start)).days
                        if days <= 10:
                            return "short"
                        if days <= 45:
                            return "medium"
                        return "long"
                    except Exception:
                        pass
            return "short"

        def _pick_confidence(opp: dict) -> float:
            score = opp.get("opportunity_score") or {}
            if isinstance(score, dict):
                if score.get("confidence_score") is not None:
                    val = float(score.get("confidence_score"))
                    return val * 10 if val <= 1 else val
                if score.get("overall_score") is not None:
                    return float(score.get("overall_score"))
            return float(opp.get("conviction_score", 7.0))

        def _pick_intensity(opp: dict) -> float:
            score = opp.get("opportunity_score") or {}
            if isinstance(score, dict):
                if score.get("catalyst_strength") is not None:
                    return float(score.get("catalyst_strength"))
                if score.get("overall_score") is not None:
                    return float(score.get("overall_score"))
            return float(opp.get("conviction_score", 7.0))

        for f in sorted(opp_path.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                items = data if isinstance(data, list) else [data]
                for opp in items:
                    if not isinstance(opp, dict):
                        continue
                    created = str(opp.get("created_at", ""))[:10]
                    if not created:
                        continue
                    sig_date = date.fromisoformat(created)
                    instruments = opp.get("target_instruments") or opp.get("primary_instruments", [])
                    if not instruments:
                        continue

                    markets = opp.get("target_markets") or ["A_SHARE"]
                    market = markets[0]
                    if isinstance(market, dict):
                        market = market.get("value", "A_SHARE")

                    direction = opp.get("trade_direction", "BULLISH")
                    if isinstance(direction, dict):
                        direction = direction.get("value", "BULLISH")

                    events.append(SignalEvent(
                        instrument=instruments[0],
                        market=str(market),
                        signal_type=_pick_signal_type(opp),
                        signal_direction=str(direction),
                        signal_intensity=_pick_intensity(opp),
                        signal_confidence=_pick_confidence(opp),
                        time_horizon=_pick_horizon(opp),
                        signal_date=sig_date,
                        note=opp.get("opportunity_title", ""),
                    ))
            except Exception as e:
                logger.warning(f"[StrategyBacktester] 解析机会文件失败 {f.name}: {e}")

        logger.info(f"[StrategyBacktester] 从机会文件加载 {len(events)} 个信号事件")
        return events

    # ── 核心回测逻辑 ─────────────────────────────────────────

    def run_strategy(self, strategy: Strategy, events: List[SignalEvent]) -> StrategyResult:
        """对单个策略跑所有事件"""
        trades = []
        for event in events:
            trade = self._simulate_trade(strategy, event)
            if trade:
                trades.append(trade)
        return StrategyResult(strategy=strategy, trades=trades)

    def run_all(self, events: List[SignalEvent],
                strategy_names: Optional[List[str]] = None) -> Dict[str, StrategyResult]:
        """对所有策略（或指定策略）跑回测"""
        names = strategy_names or list(STRATEGIES.keys())
        results = {}
        for name in names:
            strategy = STRATEGIES.get(name)
            if not strategy:
                logger.warning(f"[StrategyBacktester] 未知策略: {name}")
                continue
            results[name] = self.run_strategy(strategy, events)
            logger.info(
                f"[StrategyBacktester] {name}: "
                f"{len(results[name].completed_trades)} 笔, "
                f"胜率 {results[name].win_rate*100:.1f}%, "
                f"均盈亏 {results[name].avg_pnl*100:+.2f}%"
            )
        return results

    def _simulate_trade(self, strategy: Strategy, event: SignalEvent) -> Optional[StrategyTrade]:
        """
        模拟单笔交易生命周期。

        ComboFilter（require_all=True）的特殊处理：
          - 用 signal_type 作为主信号，在 signal_date 前后 ±5 天内
            检查是否还有另一种 signal_type 的事件（作为伴随确认）
          - 本函数已接收的单个 event 代表一组信号的"触发锚点"
          - 简化：只要 event 的 signal_type 在 strategy.signal_types 里即可
        """
        # ── 信号过滤 ──
        if strategy.signal_types_require_all:
            # ComboFilter: event 的 signal_type 必须在列表中
            if event.signal_type not in strategy.signal_types:
                return None
        else:
            if not strategy.matches_signal(
                event.signal_type, event.signal_intensity,
                event.signal_confidence, event.signal_direction,
                event.time_horizon, event.market,
            ):
                return None

        # ── 找 T+1 入场价 ──
        entry_date, entry_price = self._find_entry(
            event.instrument, event.signal_date, strategy.entry_timing
        )
        if entry_price is None or entry_price <= 0:
            return StrategyTrade(
                strategy_name=strategy.name,
                instrument=event.instrument,
                signal_type=event.signal_type,
                signal_direction=event.signal_direction,
                signal_intensity=event.signal_intensity,
                signal_confidence=event.signal_confidence,
                time_horizon=event.time_horizon,
                signal_date=event.signal_date,
                entry_date=None, entry_price=None,
                exit_date=None, exit_price=None,
                exit_reason="NO_DATA",
                realized_pnl_pct=None, days_held=0,
                max_favorable_excursion=0.0, max_adverse_excursion=0.0,
                note=f"[NO_DATA] T+1 入场价不可用 | {event.note}",
            )

        # ── 止损止盈价格 ──
        direction = event.signal_direction
        if direction == "BULLISH":
            sl_price = entry_price * (1 - strategy.stop_loss_pct)
            tp_price = entry_price * (1 + strategy.take_profit_pct) if strategy.take_profit_pct else None
        else:  # BEARISH（做空逻辑）
            sl_price = entry_price * (1 + strategy.stop_loss_pct)
            tp_price = entry_price * (1 - strategy.take_profit_pct) if strategy.take_profit_pct else None

        # ── 逐日模拟 ──
        current_date = entry_date
        mfe = 0.0  # max favorable excursion
        mae = 0.0  # max adverse excursion（负数）
        price_path = []
        exit_reason = "TIMEOUT"
        exit_price = None
        exit_date = None

        for day_offset in range(strategy.max_holding_days + 60):  # 额外 buffer 找交易日
            check_date = current_date + timedelta(days=day_offset)
            if day_offset > strategy.max_holding_days + 30:
                break

            day_open  = self.feed.get_price(event.instrument, check_date, "open")
            day_high  = self.feed.get_price(event.instrument, check_date, "high")
            day_low   = self.feed.get_price(event.instrument, check_date, "low")
            day_close = self.feed.get_price(event.instrument, check_date, "close")

            if day_close is None:
                continue  # 非交易日，跳过

            price_path.append((check_date.isoformat(), day_close))
            days_held = len(price_path)

            # 当日浮盈
            if direction == "BULLISH":
                pnl = (day_close - entry_price) / entry_price
                day_high_pnl = (day_high - entry_price) / entry_price if day_high else pnl
                day_low_pnl  = (day_low  - entry_price) / entry_price if day_low  else pnl
            else:
                pnl = (entry_price - day_close) / entry_price
                day_high_pnl = (entry_price - day_low)  / entry_price if day_low  else pnl
                day_low_pnl  = (entry_price - day_high) / entry_price if day_high else pnl

            mfe = max(mfe, day_high_pnl)
            mae = min(mae, day_low_pnl)

            # 检查超时（达到最大持仓天数）
            if days_held >= strategy.max_holding_days:
                exit_reason = "TIMEOUT"
                exit_price = day_close
                exit_date = check_date
                break

            # 用日内高低点判断止损止盈触发
            if direction == "BULLISH":
                if day_low is not None and day_low <= sl_price:
                    exit_reason = "STOP_LOSS"
                    exit_price = sl_price
                    exit_date = check_date
                    break
                if tp_price and day_high is not None and day_high >= tp_price:
                    exit_reason = "TAKE_PROFIT"
                    exit_price = tp_price
                    exit_date = check_date
                    break
            else:
                if day_high is not None and day_high >= sl_price:
                    exit_reason = "STOP_LOSS"
                    exit_price = sl_price
                    exit_date = check_date
                    break
                if tp_price and day_low is not None and day_low <= tp_price:
                    exit_reason = "TAKE_PROFIT"
                    exit_price = tp_price
                    exit_date = check_date
                    break

        if exit_price is None:
            # 所有数据耗尽前未平仓，用最后收盘价
            if price_path:
                exit_price = price_path[-1][1]
                exit_date = date.fromisoformat(price_path[-1][0])
                exit_reason = "TIMEOUT"
            else:
                return StrategyTrade(
                    strategy_name=strategy.name,
                    instrument=event.instrument,
                    signal_type=event.signal_type,
                    signal_direction=event.signal_direction,
                    signal_intensity=event.signal_intensity,
                    signal_confidence=event.signal_confidence,
                    time_horizon=event.time_horizon,
                    signal_date=event.signal_date,
                    entry_date=entry_date, entry_price=entry_price,
                    exit_date=None, exit_price=None,
                    exit_reason="NO_DATA",
                    realized_pnl_pct=None, days_held=0,
                    max_favorable_excursion=mfe, max_adverse_excursion=mae,
                    note=event.note,
                )

        if direction == "BULLISH":
            pnl_pct = (exit_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - exit_price) / entry_price

        return StrategyTrade(
            strategy_name=strategy.name,
            instrument=event.instrument,
            signal_type=event.signal_type,
            signal_direction=event.signal_direction,
            signal_intensity=event.signal_intensity,
            signal_confidence=event.signal_confidence,
            time_horizon=event.time_horizon,
            signal_date=event.signal_date,
            entry_date=entry_date,
            entry_price=entry_price,
            exit_date=exit_date,
            exit_price=exit_price,
            exit_reason=exit_reason,
            realized_pnl_pct=pnl_pct,
            days_held=len(price_path),
            max_favorable_excursion=mfe,
            max_adverse_excursion=mae,
            price_path=price_path[-10:],  # 只保留最后10天节省内存
            note=event.note,
        )

    def _find_entry(self, instrument: str, signal_date: date,
                    timing: str) -> Tuple[Optional[date], Optional[float]]:
        """找 T+1 入场价（向后最多找 5 个交易日）"""
        price_type = "open" if "open" in timing else "close"
        for offset in range(1, 6):
            check = signal_date + timedelta(days=offset)
            price = self.feed.get_price(instrument, check, price_type)
            if price and price > 0:
                return check, price
        return None, None

    # ── 对比报告 ────────────────────────────────────────────

    def compare_strategies(self, results: Dict[str, StrategyResult]) -> dict:
        """生成策略对比报告"""
        summaries = {name: r.summary() for name, r in results.items()}

        # 按均盈亏排名
        ranked = sorted(
            summaries.values(),
            key=lambda s: (s["avg_pnl_pct"], s["win_rate"]),
            reverse=True,
        )

        # 综合推荐
        recommendations = []
        for s in summaries.values():
            if s["completed"] < 3:
                recommendations.append(f"{s['strategy']}: 样本不足（{s['completed']}笔），结论参考价值有限")
            elif s["win_rate"] >= 70 and s["profit_factor"] >= 2.0:
                recommendations.append(f"✅ {s['strategy']}: 高胜率({s['win_rate']:.0f}%)高盈亏比({s['profit_factor']:.1f})，可考虑实盘")
            elif s["win_rate"] >= 60 and s["avg_pnl_pct"] > 5:
                recommendations.append(f"🟡 {s['strategy']}: 胜率({s['win_rate']:.0f}%)和盈亏({s['avg_pnl_pct']:+.1f}%)尚可，建议扩大样本")
            elif s["avg_pnl_pct"] < 0:
                recommendations.append(f"❌ {s['strategy']}: 负期望({s['avg_pnl_pct']:+.1f}%)，参数需调整")
            else:
                recommendations.append(f"🟠 {s['strategy']}: 期望为正但止损率偏高({s['stop_loss_rate']:.0f}%)，可放宽止损")

        return {
            "strategies_ranked": [s["strategy"] for s in ranked],
            "summaries": summaries,
            "recommendations": recommendations,
            "best_strategy": ranked[0]["strategy"] if ranked else None,
            "best_win_rate": max((s["win_rate"] for s in summaries.values()), default=0),
            "best_avg_pnl": max((s["avg_pnl_pct"] for s in summaries.values()), default=0),
        }

    def print_report(self, results: Dict[str, StrategyResult], verbose: bool = True):
        """打印格式化回测报告"""
        report = self.compare_strategies(results)

        sep = "=" * 72
        print(f"\n{sep}")
        print("  MarketRadar 策略回测报告")
        print(sep)

        for name in report["strategies_ranked"]:
            s = report["summaries"][name]
            print(f"\n{'─' * 60}")
            print(f"  策略：{s['strategy']}")
            print(f"  描述：{s['description'][:60]}")
            print(f"  参数：止损 {s['params']['stop_loss_pct']*100:.0f}% │ "
                  f"止盈 {(s['params']['take_profit_pct'] or 0)*100:.0f}% │ "
                  f"最长持有 {s['params']['max_holding_days']}天")
            print(f"{'─' * 60}")
            print(f"  总案例: {s['total_cases']}  │  完成: {s['completed']}  │  无数据: {s['skipped_no_data']}")
            print(f"  胜率:   {s['win_rate']:.1f}%  │  均盈亏: {s['avg_pnl_pct']:+.2f}%  │  盈亏比: {s['profit_factor']:.2f}")
            print(f"  均盈利: {s['avg_win_pct']:+.2f}%  │  均亏损: {s['avg_loss_pct']:+.2f}%  │  最大回撤: {s['max_drawdown_pct']:+.2f}%")
            print(f"  止损率: {s['stop_loss_rate']:.1f}%  │  止盈率: {s['take_profit_rate']:.1f}%  │  超时率: {s['timeout_rate']:.1f}%  │  均持有: {s['avg_holding_days']:.1f}天")

            if verbose:
                r = results[name]
                print(f"\n  {'日期':<12} {'标的':<14} {'信号':<12} {'入场':<8} {'出场':<8} {'盈亏':>8} {'原因':<12} 备注")
                for t in sorted(r.completed_trades, key=lambda x: x.signal_date):
                    ep = f"{t.entry_price:.3f}" if t.entry_price else "—"
                    xp = f"{t.exit_price:.3f}" if t.exit_price else "—"
                    pnl = f"{t.realized_pnl_pct*100:+.2f}%" if t.realized_pnl_pct is not None else "—"
                    note_short = t.note[:20] if t.note else ""
                    print(f"  {str(t.signal_date):<12} {t.instrument:<14} {t.signal_type:<12} "
                          f"{ep:<8} {xp:<8} {pnl:>8} {t.exit_reason:<12} {note_short}")

        print(f"\n{'─' * 60}")
        print("  📊 策略综合建议")
        print(f"{'─' * 60}")
        for rec in report["recommendations"]:
            print(f"  {rec}")

        print(f"\n  🏆 最佳策略: {report['best_strategy']}")
        print(f"  最高胜率: {report['best_win_rate']:.1f}%  │  最高均盈亏: {report['best_avg_pnl']:+.2f}%")
        print(sep)


# ─────────────────────────────────────────────────────────────
# __main__ 入口
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    bt = StrategyBacktester(use_seed=True)

    print("加载信号事件...")
    events = bt.build_events_from_seed()

    # 尝试加载真实机会文件
    real_events = bt.load_events_from_opportunities()
    if real_events:
        print(f"叠加真实机会事件: {len(real_events)} 个")
        events = events + real_events

    print(f"共 {len(events)} 个信号事件，开始回测...\n")
    results = bt.run_all(events)
    bt.print_report(results, verbose=True)
