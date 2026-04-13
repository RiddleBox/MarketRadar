"""
backtest/backtest_engine.py — 历史信号回测引擎

核心逻辑：
  1. 读取 M3 产出的历史机会列表（OpportunityObject + ActionPlan）
  2. 对每个机会，从历史日线中模拟持仓生命周期
  3. 检查止损/止盈触发，计算 realized_pnl
  4. 写入模拟持仓（PaperPosition 格式）供 SignalEvaluator 分析
  5. 输出综合回测报告

回测规则：
  - 以机会创建日 +1 个交易日的 open 价格作为入场价（T+1 开盘入）
  - 逐日更新价格，高/低点判断止损止盈（日内可能触发）
  - 最多持有 time_horizon 对应的天数（超时强制平仓）
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Tuple

from backtest.history_price import HistoryPriceFeed
from m9_paper_trader.paper_trader import PaperPosition
from m9_paper_trader.evaluator import SignalEvaluator

logger = logging.getLogger(__name__)

BACKTEST_DIR = Path(__file__).parent.parent / "data" / "backtest"

# time_horizon → 最大持仓天数（日历日，覆盖约 N 个交易日）
HORIZON_MAX_DAYS = {
    "intraday":  3,
    "short":    30,
    "medium":   90,
    "long":    180,
}


@dataclass
class BacktestCase:
    """单个回测案例 — 一个机会 + 对应行动计划"""
    opportunity_id: str
    opportunity_title: str
    signal_ids: List[str]
    signal_type: str
    signal_intensity: float
    signal_confidence: float
    signal_direction: str          # BULLISH / BEARISH
    instrument: str
    market: str
    time_horizon: str
    created_date: date             # 机会发现日
    entry_price: Optional[float]   # 实际入场价（T+1 开盘）
    stop_loss_pct: float           # 止损比例（如 0.05 = 5%）
    take_profit_pct: Optional[float]  # 止盈比例（None = 不设）
    batch_id: str = ""

    # 回测结果字段（填充后）
    status: str = "PENDING"        # PENDING / HIT / MISS / STOP_LOSS / TAKE_PROFIT / TIMEOUT
    realized_pnl_pct: Optional[float] = None
    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0
    days_held: int = 0
    exit_date: Optional[date] = None
    exit_price: Optional[float] = None
    price_path: List[Tuple[str, float]] = field(default_factory=list)   # [(date_str, close)]


@dataclass
class BacktestReport:
    """回测汇总报告"""
    batch_id: str
    start_date: date
    end_date: date
    total_cases: int
    completed: int
    skipped: int          # 无价格数据跳过
    win_rate: float
    avg_pnl_pct: float
    profit_factor: float
    avg_holding_days: float
    timeout_rate: float
    stop_loss_rate: float
    take_profit_rate: float
    by_signal_type: dict = field(default_factory=dict)
    by_horizon: dict = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    cases: List[BacktestCase] = field(default_factory=list)


class BacktestEngine:
    """
    历史信号回测引擎。

    用法：
      engine = BacktestEngine()
      # 方式1：直接传入 BacktestCase 列表
      report = engine.run(cases)
      # 方式2：从 M3/M4 输出文件加载
      cases = engine.load_cases_from_files("data/opportunities/", "data/action_plans/")
      report = engine.run(cases)
    """

    def __init__(self, price_feed: Optional[HistoryPriceFeed] = None):
        self.price_feed = price_feed or HistoryPriceFeed()
        BACKTEST_DIR.mkdir(parents=True, exist_ok=True)

    # ── 加载回测案例 ─────────────────────────────────────────

    def load_cases_from_files(
        self,
        opp_dir: str,
        plan_dir: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[BacktestCase]:
        """
        从 M3/M4 输出 JSON 文件加载回测案例。

        期望文件格式：
          data/opportunities/*.json  — OpportunityObject JSON
          data/action_plans/*.json   — ActionPlan JSON（含 opportunity_id 关联）
        """
        opp_path = Path(opp_dir)
        plan_path = Path(plan_dir)
        cases = []

        # 加载 ActionPlan 索引（plan.opportunity_id → plan dict）
        plans_by_opp: Dict[str, dict] = {}
        if plan_path.exists():
            for f in plan_path.glob("*.json"):
                try:
                    plan = json.loads(f.read_text(encoding="utf-8"))
                    opp_id = plan.get("opportunity_id", "")
                    if opp_id:
                        plans_by_opp[opp_id] = plan
                except Exception as e:
                    logger.warning(f"[Backtest] 加载 ActionPlan 失败: {f.name} | {e}")

        # 加载 OpportunityObject
        if not opp_path.exists():
            logger.warning(f"[Backtest] opportunities 目录不存在: {opp_path}")
            return []

        for f in sorted(opp_path.glob("*.json")):
            try:
                opp = json.loads(f.read_text(encoding="utf-8"))
                opp_id = opp.get("opportunity_id", "")
                if not opp_id:
                    continue

                # 解析创建日期
                created_str = opp.get("created_at", "")
                created_dt = self._parse_date(created_str) if created_str else None
                if not created_dt:
                    continue

                # 日期范围过滤
                if start_date and created_dt < start_date:
                    continue
                if end_date and created_dt > end_date:
                    continue

                # 取对应的 ActionPlan
                plan = plans_by_opp.get(opp_id, {})
                if not plan:
                    continue

                instruments = plan.get("instruments", [])
                if not instruments:
                    continue

                # 每个标的生成一个 BacktestCase
                for inst in instruments:
                    cases.append(BacktestCase(
                        opportunity_id=opp_id,
                        opportunity_title=opp.get("opportunity_title", ""),
                        signal_ids=opp.get("signal_ids", []),
                        signal_type=opp.get("signal_type", "unknown"),
                        signal_intensity=float(opp.get("signal_intensity_avg", 5.0)),
                        signal_confidence=float(opp.get("signal_confidence_avg", 5.0)),
                        signal_direction=plan.get("direction", "BULLISH"),
                        instrument=inst,
                        market=plan.get("target_market", "A_SHARE"),
                        time_horizon=plan.get("time_horizon", "short"),
                        created_date=created_dt,
                        entry_price=None,
                        stop_loss_pct=self._get_sl_pct(plan),
                        take_profit_pct=self._get_tp_pct(plan),
                        batch_id=opp.get("batch_id", ""),
                    ))

            except Exception as e:
                logger.warning(f"[Backtest] 加载 Opportunity 失败: {f.name} | {e}")

        logger.info(f"[Backtest] 加载 {len(cases)} 个回测案例")
        return cases

    def load_cases_from_signals(
        self,
        signals: list,
        default_instruments: List[str] = None,
        stop_loss_pct: float = 0.05,
        take_profit_pct: float = 0.10,
        time_horizon: str = "short",
    ) -> List[BacktestCase]:
        """
        直接从 MarketSignal 列表构建回测案例（不需要 M3/M4 完整链路）。

        适用于快速验证：信号本身是否有预测力。
        entry = 信号发现日 +1，signal_direction 决定多空。
        """
        cases = []
        instruments = default_instruments or ["510300.SH"]  # 默认用沪深300ETF

        for sig in signals:
            if hasattr(sig, "__dict__"):
                sig = sig.__dict__ if not hasattr(sig, "model_dump") else sig.model_dump()

            sig_id = sig.get("signal_id", str(uuid.uuid4()))
            direction = sig.get("signal_direction", "BULLISH")
            if direction not in ("BULLISH", "BEARISH"):
                direction = "BULLISH"

            created_str = sig.get("event_time") or sig.get("collected_time")
            if not created_str:
                continue
            created_dt = self._parse_date(str(created_str))
            if not created_dt:
                continue

            for inst in instruments:
                cases.append(BacktestCase(
                    opportunity_id=f"sig_{sig_id}",
                    opportunity_title=sig.get("signal_label", "")[:80],
                    signal_ids=[sig_id],
                    signal_type=sig.get("signal_type", "unknown"),
                    signal_intensity=float(sig.get("intensity_score", 5.0)),
                    signal_confidence=float(sig.get("confidence_score", 5.0)),
                    signal_direction=direction,
                    instrument=inst,
                    market=sig.get("affected_markets", ["A_SHARE"])[0] if sig.get("affected_markets") else "A_SHARE",
                    time_horizon=sig.get("time_horizon", time_horizon),
                    created_date=created_dt,
                    entry_price=None,
                    stop_loss_pct=stop_loss_pct,
                    take_profit_pct=take_profit_pct,
                    batch_id=sig.get("batch_id", ""),
                ))

        logger.info(f"[Backtest] 从信号生成 {len(cases)} 个回测案例")
        return cases

    # ── 运行回测 ─────────────────────────────────────────────

    def run(self, cases: List[BacktestCase]) -> BacktestReport:
        """
        运行回测。

        逻辑：
          T+0: 信号发现日
          T+1: 以下一交易日 open 作为入场价
          每日用 high/low 判断止损止盈（日内可能触发）
          超过 HORIZON_MAX_DAYS[time_horizon] 强制平仓（用当日 close）
        """
        if not cases:
            return self._empty_report()

        # 预加载价格
        instruments = list(set(c.instrument for c in cases))
        self.price_feed.preload(instruments)

        completed = []
        skipped = 0

        for case in cases:
            result = self._run_one(case)
            if result == "skipped":
                skipped += 1
            else:
                completed.append(case)

        report = self._build_report(cases, completed, skipped)
        self._save_report(report)
        return report

    def _run_one(self, case: BacktestCase) -> str:
        """运行单个回测案例，填充 case 的结果字段"""
        inst = case.instrument
        feed = self.price_feed

        # 找 T+1 入场日（信号日之后第一个有数据的交易日）
        entry_date, entry_price = self._find_entry(inst, case.created_date)
        if entry_price is None or entry_price <= 0:
            case.status = "NO_DATA"
            return "skipped"

        case.entry_price = entry_price

        # 计算止损/止盈价格
        if case.signal_direction == "BULLISH":
            sl_price = entry_price * (1 - case.stop_loss_pct)
            tp_price = entry_price * (1 + case.take_profit_pct) if case.take_profit_pct else None
        else:
            sl_price = entry_price * (1 + case.stop_loss_pct)
            tp_price = entry_price * (1 - case.take_profit_pct) if case.take_profit_pct else None

        max_hold_days = HORIZON_MAX_DAYS.get(case.time_horizon, 30)
        max_fav = 0.0
        max_adv = 0.0

        cur = entry_date + timedelta(days=1)
        days_held = 0

        while days_held < max_hold_days * 2:  # 日历日上限
            day_data = feed._cache.get(inst, {}).get(cur.strftime("%Y-%m-%d"))
            if day_data:
                high = day_data.get("high", 0) or 0
                low = day_data.get("low", 0) or 0
                close = day_data.get("close", 0) or 0

                case.price_path.append((cur.strftime("%Y-%m-%d"), close))
                days_held += 1

                if close > 0:
                    if case.signal_direction == "BULLISH":
                        pnl = (close - entry_price) / entry_price
                    else:
                        pnl = (entry_price - close) / entry_price
                    max_fav = max(max_fav, pnl)
                    max_adv = min(max_adv, pnl)

                # 日内止损检查（用 low/high 判断是否触及）
                hit_sl = (
                    (case.signal_direction == "BULLISH" and low > 0 and low <= sl_price) or
                    (case.signal_direction == "BEARISH" and high > 0 and high >= sl_price)
                )
                hit_tp = tp_price and (
                    (case.signal_direction == "BULLISH" and high >= tp_price) or
                    (case.signal_direction == "BEARISH" and low > 0 and low <= tp_price)
                )

                if hit_tp:
                    case.status = "TAKE_PROFIT"
                    case.exit_price = tp_price
                    case.exit_date = cur
                    case.realized_pnl_pct = case.take_profit_pct if case.signal_direction == "BULLISH" else case.take_profit_pct
                    break
                elif hit_sl:
                    case.status = "STOP_LOSS"
                    case.exit_price = sl_price
                    case.exit_date = cur
                    if case.signal_direction == "BULLISH":
                        case.realized_pnl_pct = -case.stop_loss_pct
                    else:
                        case.realized_pnl_pct = -case.stop_loss_pct
                    break

                # 超时平仓
                if days_held >= max_hold_days:
                    case.status = "TIMEOUT"
                    case.exit_price = close
                    case.exit_date = cur
                    if close > 0 and entry_price > 0:
                        if case.signal_direction == "BULLISH":
                            case.realized_pnl_pct = (close - entry_price) / entry_price
                        else:
                            case.realized_pnl_pct = (entry_price - close) / entry_price
                    break

            cur += timedelta(days=1)
            # 防止无限循环（数据截止）
            if (cur - entry_date).days > max_hold_days * 3:
                case.status = "NO_DATA"
                return "skipped"

        case.days_held = days_held
        case.max_favorable_excursion = max_fav
        case.max_adverse_excursion = max_adv

        if case.realized_pnl_pct is None:
            case.status = "NO_DATA"
            return "skipped"

        return "ok"

    def _find_entry(
        self, instrument: str, signal_date: date, max_lookahead: int = 5
    ) -> Tuple[date, Optional[float]]:
        """找 T+1 入场日（下一个有数据的交易日），返回 (entry_date, open_price)"""
        cache = self.price_feed._cache.get(instrument, {})
        cur = signal_date + timedelta(days=1)
        for _ in range(max_lookahead):
            ds = cur.strftime("%Y-%m-%d")
            if ds in cache:
                price = cache[ds].get("open") or cache[ds].get("close")
                return cur, price
            cur += timedelta(days=1)
        return signal_date + timedelta(days=1), None

    # ── 报告构建 ─────────────────────────────────────────────

    def _build_report(
        self, all_cases: List[BacktestCase], completed: List[BacktestCase], skipped: int
    ) -> BacktestReport:
        from collections import defaultdict

        if not completed:
            return BacktestReport(
                batch_id=f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                start_date=date.today(), end_date=date.today(),
                total_cases=len(all_cases), completed=0, skipped=skipped,
                win_rate=0, avg_pnl_pct=0, profit_factor=0,
                avg_holding_days=0, timeout_rate=0,
                stop_loss_rate=0, take_profit_rate=0,
            )

        pnls = [c.realized_pnl_pct for c in completed if c.realized_pnl_pct is not None]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        win_rate = len(wins) / len(pnls) if pnls else 0
        avg_pnl = sum(pnls) / len(pnls) if pnls else 0
        pf = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else float("inf")

        statuses = [c.status for c in completed]
        timeout_rate = statuses.count("TIMEOUT") / len(statuses)
        sl_rate = statuses.count("STOP_LOSS") / len(statuses)
        tp_rate = statuses.count("TAKE_PROFIT") / len(statuses)
        avg_hold = sum(c.days_held for c in completed) / len(completed)

        # 按信号类型分组
        by_type: Dict[str, list] = defaultdict(list)
        for c in completed:
            if c.realized_pnl_pct is not None:
                by_type[c.signal_type].append(c.realized_pnl_pct)

        by_type_stats = {}
        for k, vals in by_type.items():
            ws = [v for v in vals if v > 0]
            by_type_stats[k] = {
                "count": len(vals),
                "win_rate": round(len(ws) / len(vals) * 100, 1) if vals else 0,
                "avg_pnl_pct": round(sum(vals) / len(vals) * 100, 2) if vals else 0,
            }

        # 按 time_horizon 分组
        by_horizon: Dict[str, list] = defaultdict(list)
        for c in completed:
            if c.realized_pnl_pct is not None:
                by_horizon[c.time_horizon].append(c.realized_pnl_pct)

        by_horizon_stats = {}
        for k, vals in by_horizon.items():
            ws = [v for v in vals if v > 0]
            by_horizon_stats[k] = {
                "count": len(vals),
                "win_rate": round(len(ws) / len(vals) * 100, 1) if vals else 0,
                "avg_pnl_pct": round(sum(vals) / len(vals) * 100, 2) if vals else 0,
            }

        dates = [c.created_date for c in all_cases]

        report = BacktestReport(
            batch_id=f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            start_date=min(dates),
            end_date=max(dates),
            total_cases=len(all_cases),
            completed=len(completed),
            skipped=skipped,
            win_rate=round(win_rate * 100, 1),
            avg_pnl_pct=round(avg_pnl * 100, 2),
            profit_factor=round(pf, 2) if pf != float("inf") else 999.0,
            avg_holding_days=round(avg_hold, 1),
            timeout_rate=round(timeout_rate * 100, 1),
            stop_loss_rate=round(sl_rate * 100, 1),
            take_profit_rate=round(tp_rate * 100, 1),
            by_signal_type=by_type_stats,
            by_horizon=by_horizon_stats,
            cases=completed,
        )

        # 加入 SignalEvaluator 的改进建议
        evaluator = SignalEvaluator()
        pos_dicts = self._cases_to_pos_dicts(completed)
        if pos_dicts:
            eval_report = evaluator.evaluate(pos_dicts, min_closed=3)
            report.recommendations = eval_report.get("recommendations", [])

        return report

    def _cases_to_pos_dicts(self, cases: List[BacktestCase]) -> List[dict]:
        """BacktestCase → PaperPosition 兼容 dict，供 SignalEvaluator 分析"""
        result = []
        for c in cases:
            if c.realized_pnl_pct is None:
                continue
            result.append({
                "paper_position_id": f"bt_{c.opportunity_id[:8]}_{c.instrument}",
                "instrument": c.instrument,
                "market": c.market,
                "direction": c.signal_direction,
                "signal_type": c.signal_type,
                "signal_intensity": c.signal_intensity,
                "signal_confidence": c.signal_confidence,
                "time_horizon": c.time_horizon,
                "entry_price": c.entry_price or 0,
                "status": c.status,
                "realized_pnl_pct": c.realized_pnl_pct,
                "max_favorable_excursion": c.max_favorable_excursion,
                "max_adverse_excursion": c.max_adverse_excursion,
            })
        return result

    def _save_report(self, report: BacktestReport) -> Path:
        """保存回测报告（不含 cases 详情，避免文件过大）"""
        d = {
            "batch_id": report.batch_id,
            "start_date": str(report.start_date),
            "end_date": str(report.end_date),
            "total_cases": report.total_cases,
            "completed": report.completed,
            "skipped": report.skipped,
            "win_rate": report.win_rate,
            "avg_pnl_pct": report.avg_pnl_pct,
            "profit_factor": report.profit_factor,
            "avg_holding_days": report.avg_holding_days,
            "timeout_rate": report.timeout_rate,
            "stop_loss_rate": report.stop_loss_rate,
            "take_profit_rate": report.take_profit_rate,
            "by_signal_type": report.by_signal_type,
            "by_horizon": report.by_horizon,
            "recommendations": report.recommendations,
        }
        path = BACKTEST_DIR / f"{report.batch_id}.json"
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        logger.info(f"[Backtest] 报告保存: {path}")
        return path

    # ── 工具 ─────────────────────────────────────────────────

    def _empty_report(self) -> BacktestReport:
        return BacktestReport(
            batch_id=f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            start_date=date.today(), end_date=date.today(),
            total_cases=0, completed=0, skipped=0,
            win_rate=0, avg_pnl_pct=0, profit_factor=0,
            avg_holding_days=0, timeout_rate=0,
            stop_loss_rate=0, take_profit_rate=0,
        )

    def _parse_date(self, s: str) -> Optional[date]:
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(s[:len(fmt)], fmt).date()
            except Exception:
                pass
        return None

    def _get_sl_pct(self, plan: dict) -> float:
        sl = plan.get("stop_loss", {}) or {}
        return float(sl.get("loss_limit_pct", 0.05) or 0.05)

    def _get_tp_pct(self, plan: dict) -> Optional[float]:
        tp = plan.get("take_profit", {}) or {}
        return float(tp.get("target_pct", 0.10) or 0.10) if tp else None
