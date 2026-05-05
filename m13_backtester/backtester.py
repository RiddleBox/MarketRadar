"""
m7_backtester/backtester.py — 回测引擎

原则：前向隔离、验证框架、分层统计。
不做参数优化，只做框架验证。

设计原则见 PRINCIPLES.md。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict

import pandas as pd

from core.schemas import (
    ActionPlan,
    Direction,
    MarketSignal,
    OpportunityObject,
    PriorityLevel,
)
from core.data_loader import HistoricalDataLoader

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """单笔模拟交易记录"""
    opportunity_id: str
    instrument: str
    direction: str
    entry_time: datetime
    entry_price: float
    exit_time: Optional[datetime]
    exit_price: Optional[float]
    exit_reason: str  # "STOP_LOSS" / "TAKE_PROFIT" / "EXPIRED" / "END_OF_PERIOD"
    pnl_pct: Optional[float]  # 百分比盈亏
    signal_types: List[str] = field(default_factory=list)
    priority_level: str = "research"
    market: str = ""


@dataclass
class BacktestReport:
    """回测报告"""
    start: datetime
    end: datetime
    total_trades: int
    win_trades: int
    loss_trades: int
    win_rate: float
    avg_profit_pct: float       # 盈利交易平均盈利%
    avg_loss_pct: float         # 亏损交易平均亏损%
    profit_loss_ratio: float    # 盈亏比
    max_drawdown: float         # 最大回撤（基于逐笔）
    total_return: float         # 简单累加（不含复利，用于趋势判断）
    trades: List[BacktestTrade] = field(default_factory=list)
    by_market: Dict[str, dict] = field(default_factory=dict)
    by_signal_type: Dict[str, dict] = field(default_factory=dict)
    by_priority: Dict[str, dict] = field(default_factory=dict)
    by_direction: Dict[str, dict] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"═══════════════ 回测报告 ═══════════════",
            f"区间: {self.start.date()} ~ {self.end.date()}",
            f"总交易: {self.total_trades} | 盈利: {self.win_trades} | 亏损: {self.loss_trades}",
            f"胜率: {self.win_rate*100:.1f}%",
            f"平均盈利: +{self.avg_profit_pct*100:.2f}% | 平均亏损: {self.avg_loss_pct*100:.2f}%",
            f"盈亏比: {self.profit_loss_ratio:.2f}",
            f"最大回撤: {self.max_drawdown*100:.2f}%",
            f"总收益（简单累加）: {self.total_return*100:.2f}%",
        ]
        if self.warnings:
            lines.append("⚠️  警告:")
            for w in self.warnings:
                lines.append(f"  - {w}")
        if self.by_market:
            lines.append("\n── 按市场分层 ──")
            for mkt, stats in self.by_market.items():
                lines.append(f"  {mkt}: 胜率={stats.get('win_rate', 0)*100:.1f}% n={stats.get('n', 0)}")
        return "\n".join(lines)


class Backtester:
    """回测引擎

    使用方法：
        loader = AKShareLoader()
        bt = Backtester()
        report = bt.run(signals, action_plans, opportunities, start, end, loader)
        print(report.summary())
    """

    def __init__(self, slippage: float = 0.001, commission: float = 0.0003):
        """
        Args:
            slippage: 滑点（默认 0.1%）
            commission: 手续费（默认 0.03%，单边）
        """
        self.slippage = slippage
        self.commission = commission

    def run(
        self,
        signals: List[MarketSignal],
        action_plans: List[ActionPlan],
        opportunities: List[OpportunityObject],
        start: datetime,
        end: datetime,
        data_loader: HistoricalDataLoader,
    ) -> BacktestReport:
        """执行回测

        Args:
            signals: 该时间段内的信号列表（必须有 event_time）
            action_plans: 对应的行动计划列表
            opportunities: 对应的机会对象列表
            start: 回测开始时间
            end: 回测结束时间
            data_loader: 历史数据加载器

        Returns:
            BacktestReport
        """
        # 构建 opportunity → plan 的映射
        opp_map = {o.opportunity_id: o for o in opportunities}
        trades: List[BacktestTrade] = []
        warnings = []

        if len(action_plans) < 10:
            warnings.append(f"样本量不足（{len(action_plans)} 笔），结论可靠性有限，建议至少 30 笔")

        for plan in action_plans:
            if plan.action_type.value == "WATCH":
                continue

            opp = opp_map.get(plan.opportunity_id)
            if opp is None:
                logger.warning(f"[M7] 未找到机会对象: {plan.opportunity_id}")
                continue

            # 前向隔离：获取行情时，从 opportunity 创建时间之后开始
            data_start = opp.created_at
            if data_start < start:
                data_start = start

            try:
                ohlcv = data_loader.get_ohlcv(
                    instrument=plan.instrument,
                    start=data_start,
                    end=end,
                    frequency="1d",
                )
            except Exception as e:
                logger.warning(f"[M7] 获取行情失败 {plan.instrument}: {e}")
                warnings.append(f"品种 {plan.instrument} 行情数据获取失败，已跳过")
                continue

            if ohlcv.empty:
                warnings.append(f"品种 {plan.instrument} 在 {data_start.date()}~{end.date()} 无行情数据")
                continue

            trade = self._simulate_trade(plan, opp, ohlcv, signals)
            if trade:
                trades.append(trade)

        return self._build_report(trades, start, end, warnings)

    def _simulate_trade(
        self,
        plan: ActionPlan,
        opp: OpportunityObject,
        ohlcv: pd.DataFrame,
        signals: List[MarketSignal] = None,
    ) -> Optional[BacktestTrade]:
        """模拟单笔交易执行"""
        if ohlcv.empty:
            return None

        # 用第一根 K 线的开盘价入场（含滑点）
        first_row = ohlcv.iloc[0]
        entry_price = first_row.get("open", first_row.get("close", None))
        if entry_price is None:
            return None

        if plan.direction == Direction.BULLISH:
            entry_price *= (1 + self.slippage)
        else:
            entry_price *= (1 - self.slippage)

        entry_time = pd.to_datetime(first_row.name) if hasattr(first_row, 'name') else opp.created_at

        # 止损价
        stop_price = plan.stop_loss.stop_price
        if stop_price is None:
            # 默认止损：入场价的 5%（用于回测，实盘应使用具体止损位）
            if plan.direction == Direction.BULLISH:
                stop_price = entry_price * 0.95
            else:
                stop_price = entry_price * 1.05

        # 止盈价
        take_profit_price = plan.take_profit.target_price
        if take_profit_price is None:
            # 默认止盈：入场价的 15%（盈亏比 3:1）
            if plan.direction == Direction.BULLISH:
                take_profit_price = entry_price * 1.15
            else:
                take_profit_price = entry_price * 0.85

        # 逐根 K 线检查止损/止盈
        exit_time = None
        exit_price = None
        exit_reason = "END_OF_PERIOD"

        for _, row in ohlcv.iterrows():
            low = row.get("low", row.get("close"))
            high = row.get("high", row.get("close"))

            if plan.direction == Direction.BULLISH:
                if low <= stop_price:
                    exit_price = stop_price * (1 - self.slippage)
                    exit_reason = "STOP_LOSS"
                    exit_time = pd.to_datetime(row.name) if hasattr(row, 'name') else None
                    break
                if high >= take_profit_price:
                    exit_price = take_profit_price * (1 - self.slippage)
                    exit_reason = "TAKE_PROFIT"
                    exit_time = pd.to_datetime(row.name) if hasattr(row, 'name') else None
                    break
            else:
                if high >= stop_price:
                    exit_price = stop_price * (1 + self.slippage)
                    exit_reason = "STOP_LOSS"
                    exit_time = pd.to_datetime(row.name) if hasattr(row, 'name') else None
                    break
                if low <= take_profit_price:
                    exit_price = take_profit_price * (1 + self.slippage)
                    exit_reason = "TAKE_PROFIT"
                    exit_time = pd.to_datetime(row.name) if hasattr(row, 'name') else None
                    break

        # 到期未触发，按最后一根收盘价结算
        if exit_price is None:
            last_row = ohlcv.iloc[-1]
            exit_price = last_row.get("close", entry_price)
            exit_time = pd.to_datetime(last_row.name) if hasattr(last_row, 'name') else None

        # 计算盈亏（含手续费）
        if plan.direction == Direction.BULLISH:
            pnl_pct = (exit_price - entry_price) / entry_price - 2 * self.commission
        else:
            pnl_pct = (entry_price - exit_price) / entry_price - 2 * self.commission

        return BacktestTrade(
            opportunity_id=opp.opportunity_id,
            instrument=plan.instrument,
            direction=plan.direction.value,
            entry_time=entry_time if isinstance(entry_time, datetime) else datetime.now(),
            entry_price=entry_price,
            exit_time=exit_time if isinstance(exit_time, datetime) else None,
            exit_price=exit_price,
            exit_reason=exit_reason,
            pnl_pct=pnl_pct,
            signal_types=list({s.signal_type.value for s in signals}) if signals else [],
            priority_level=opp.priority_level.value,
            market="/".join([m.value for m in opp.target_markets]),
        )

    def _build_report(
        self,
        trades: List[BacktestTrade],
        start: datetime,
        end: datetime,
        warnings: List[str],
    ) -> BacktestReport:
        if not trades:
            return BacktestReport(
                start=start, end=end,
                total_trades=0, win_trades=0, loss_trades=0,
                win_rate=0.0, avg_profit_pct=0.0, avg_loss_pct=0.0,
                profit_loss_ratio=0.0, max_drawdown=0.0, total_return=0.0,
                trades=[], warnings=warnings + ["无有效交易记录"],
            )

        wins = [t for t in trades if t.pnl_pct and t.pnl_pct > 0]
        losses = [t for t in trades if t.pnl_pct and t.pnl_pct <= 0]

        win_rate = len(wins) / len(trades)
        avg_profit = sum(t.pnl_pct for t in wins) / len(wins) if wins else 0.0
        avg_loss = sum(t.pnl_pct for t in losses) / len(losses) if losses else 0.0
        pl_ratio = abs(avg_profit / avg_loss) if avg_loss != 0 else float("inf")

        # 最大回撤（简单逐笔累计）
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in trades:
            cumulative += t.pnl_pct or 0
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd

        # 分层统计
        by_market = self._group_stats(trades, key="market")
        by_priority = self._group_stats(trades, key="priority_level")
        by_signal_type = self._group_stats(trades, key="signal_types")
        by_direction = self._group_stats(trades, key="direction")

        return BacktestReport(
            start=start, end=end,
            total_trades=len(trades),
            win_trades=len(wins),
            loss_trades=len(losses),
            win_rate=win_rate,
            avg_profit_pct=avg_profit,
            avg_loss_pct=avg_loss,
            profit_loss_ratio=pl_ratio,
            max_drawdown=max_dd,
            total_return=sum(t.pnl_pct or 0 for t in trades),
            trades=trades,
            by_market=by_market,
            by_priority=by_priority,
            by_signal_type=by_signal_type,
            by_direction=by_direction,
            warnings=warnings,
        )

    def _group_stats(self, trades: List[BacktestTrade], key: str) -> Dict[str, dict]:
        groups: Dict[str, List[BacktestTrade]] = {}
        for t in trades:
            k = getattr(t, key, "unknown")
            groups.setdefault(k, []).append(t)

        result = {}
        for k, group in groups.items():
            wins = [t for t in group if t.pnl_pct and t.pnl_pct > 0]
            result[k] = {
                "n": len(group),
                "win_rate": len(wins) / len(group) if group else 0,
                "avg_pnl": sum(t.pnl_pct or 0 for t in group) / len(group),
            }
        return result
