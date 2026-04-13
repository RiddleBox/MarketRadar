"""
backtest/ablation_study.py — 模块消融实验（Ablation Study）

量化三个核心模块对交易系统的边际贡献：
  - 机会预判（Opportunity Signal）
  - 情绪面指数（Sentiment: FG + 北向 + ADR）
  - M11 Agent 情绪模拟（AgentNetwork）

6 种策略 × 2 种 filter_mode = 完整对比矩阵
─────────────────────────────────────────────────────
策略1: Baseline       机会预判（基准线）
策略2: +Sentiment     机会 × 情绪面
策略3: +Agent         机会 × M11 Agent
策略4: Sent×Agent     情绪面 × Agent 融合（不依赖机会方向）
策略5: Full           机会 × 情绪面 × Agent

filter_mode:
  hard — 方向/置信不符直接过滤（可能减少案例）
  soft — 用分数加权仓位（保留全部案例，影响盈亏）

使用方法：
  python backtest/ablation_study.py
  python backtest/ablation_study.py --mode hard
  python backtest/ablation_study.py --mode both   # 默认
  python backtest/ablation_study.py --save
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from backtest.seed_opportunities import get_seed_opportunities

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.WARNING)


# ══════════════════════════════════════════════════════════════════
# 情绪面种子数据（与历史机会对应的模拟情绪快照）
# 实际使用时可接入 SentimentStore.latest() 或 AKShare 实时数据
# ══════════════════════════════════════════════════════════════════

# 格式: signal_date → {fg, northbound_flow, adr, label}
SENTIMENT_SEED: dict[str, dict] = {
    # M11 校准事件
    "2024-09-24": {"fg": 18, "northbound": 85.0, "adr": 68.0, "label": "极度恐惧→反转"},
    "2024-10-08": {"fg": 88, "northbound": -45.0, "adr": 28.0, "label": "极度贪婪"},
    "2025-02-17": {"fg": 72, "northbound": 62.0, "adr": 71.0, "label": "贪婪"},
    "2025-04-07": {"fg": 12, "northbound": -120.0, "adr": 15.0, "label": "极度恐惧"},

    # 2018 贸易战
    "2018-03-22": {"fg": 28, "northbound": -18.0, "adr": 32.0, "label": "恐惧"},
    "2018-07-06": {"fg": 15, "northbound": -52.0, "adr": 22.0, "label": "极度恐惧"},
    "2018-10-19": {"fg": 10, "northbound": -85.0, "adr": 18.0, "label": "极度恐惧→底部"},

    # 2020 疫情
    "2020-02-03": {"fg": 8,  "northbound": -95.0, "adr": 8.0,  "label": "极度恐惧"},
    "2020-03-23": {"fg": 5,  "northbound": -62.0, "adr": 12.0, "label": "极度恐惧→底部"},
    "2020-07-06": {"fg": 85, "northbound": 45.0,  "adr": 78.0, "label": "极度贪婪"},

    # 2022
    "2022-03-15": {"fg": 14, "northbound": -88.0, "adr": 16.0, "label": "极度恐惧"},
    "2022-10-31": {"fg": 22, "northbound": -35.0, "adr": 28.0, "label": "恐惧"},
    "2022-12-05": {"fg": 30, "northbound": 55.0,  "adr": 45.0, "label": "中性→偏多"},

    # 2023~2024
    "2023-01-05": {"fg": 35, "northbound": 82.0,  "adr": 58.0, "label": "中性偏多"},
    "2023-05-10": {"fg": 60, "northbound": -28.0, "adr": 42.0, "label": "中性偏空"},
    "2024-02-06": {"fg": 8,  "northbound": -42.0, "adr": 14.0, "label": "极度恐惧"},
    "2024-11-12": {"fg": 58, "northbound": -15.0, "adr": 45.0, "label": "中性"},

    # 失败案例
    "2019-04-08": {"fg": 68, "northbound": 12.0,  "adr": 62.0, "label": "贪婪"},
    "2021-02-19": {"fg": 82, "northbound": -8.0,  "adr": 55.0, "label": "极度贪婪"},

    # 2025 最新
    "2025-04-09": {"fg": 15, "northbound": 35.0,  "adr": 42.0, "label": "极度恐惧→回流"},
}

# ══════════════════════════════════════════════════════════════════
# 情绪面评分器
# ══════════════════════════════════════════════════════════════════

# 阈值常量（与 m3_judgment/sentiment_resonance.py 一致）
FG_EXTREME_FEAR = 20
FG_FEAR = 35
FG_GREED = 65
FG_EXTREME_GREED = 80
NORTHBOUND_RECOVERY = 30.0  # 亿
NORTHBOUND_STRONG_OUTFLOW = -80.0

def sentiment_score(snap: dict, expected_direction: str) -> tuple[float, str]:
    """
    计算情绪面对预期方向的支持分数。

    返回:
        (score, reason)
        score: -1.0 ~ +1.0
          +1.0 = 强力支持
           0.0 = 中性/无信号
          -1.0 = 强力反对
    """
    fg = snap["fg"]
    nb = snap["northbound"]
    adr = snap.get("adr", 50.0)

    score = 0.0
    reasons = []

    if expected_direction == "BULLISH":
        # 极度恐惧 → 逆向多头信号
        if fg <= FG_EXTREME_FEAR:
            score += 0.5
            reasons.append(f"FG极度恐惧({fg})")
        elif fg <= FG_FEAR:
            score += 0.2
            reasons.append(f"FG恐惧区间({fg})")
        elif fg >= FG_EXTREME_GREED:
            score -= 0.5
            reasons.append(f"FG极度贪婪({fg}),多头不利")
        elif fg >= FG_GREED:
            score -= 0.2
            reasons.append(f"FG贪婪({fg}),多头偏不利")

        # 北向资金
        if nb >= NORTHBOUND_RECOVERY:
            score += 0.35
            reasons.append(f"北向回流{nb:.0f}亿")
        elif nb <= NORTHBOUND_STRONG_OUTFLOW:
            score -= 0.35
            reasons.append(f"北向强流出{nb:.0f}亿")

        # ADR
        if adr >= 60:
            score += 0.15
            reasons.append(f"ADR强势({adr:.0f}%)")
        elif adr <= 25:
            score -= 0.15
            reasons.append(f"ADR弱势({adr:.0f}%)")

    elif expected_direction == "BEARISH":
        # 极度贪婪 → 逆向空头信号
        if fg >= FG_EXTREME_GREED:
            score += 0.5
            reasons.append(f"FG极度贪婪({fg})")
        elif fg >= FG_GREED:
            score += 0.2
            reasons.append(f"FG贪婪区间({fg})")
        elif fg <= FG_EXTREME_FEAR:
            score -= 0.5
            reasons.append(f"FG极度恐惧({fg}),空头不利")

        # 北向强流出支持空头
        if nb <= NORTHBOUND_STRONG_OUTFLOW:
            score += 0.35
            reasons.append(f"北向强流出{nb:.0f}亿")
        elif nb >= NORTHBOUND_RECOVERY:
            score -= 0.35
            reasons.append(f"北向回流{nb:.0f}亿,空头不利")

        if adr <= 25:
            score += 0.15
            reasons.append(f"ADR弱势({adr:.0f}%)")
        elif adr >= 60:
            score -= 0.15
            reasons.append(f"ADR强势({adr:.0f}%)")

    score = max(-1.0, min(1.0, score))
    return score, " | ".join(reasons) if reasons else "无情绪信号"


# ══════════════════════════════════════════════════════════════════
# M11 Agent 调用
# ══════════════════════════════════════════════════════════════════

_agent_network_cache: dict = {}

def _get_agent_network(market: str = "a_share"):
    if market not in _agent_network_cache:
        try:
            from m11_agent_sim.agent_network import AgentNetwork
            net = AgentNetwork.from_config_file(market)
            _agent_network_cache[market] = net
        except Exception as e:
            logger.warning(f"[Ablation] AgentNetwork 加载失败: {e}")
            _agent_network_cache[market] = None
    return _agent_network_cache[market]


def run_agent_sim(opp: dict, snap: dict | None) -> dict | None:
    """运行 M11 AgentNetwork，返回 SentimentDistribution 关键字段"""
    net = _get_agent_network("a_share")
    if net is None:
        return None
    try:
        from m11_agent_sim.schemas import MarketInput
        inp = MarketInput(
            event_description=opp["opportunity_title"],
            market_date=opp["signal_date"],
            fg_index=snap["fg"] if snap else 50,
            northbound_flow=snap["northbound"] if snap else 0.0,
            adr_ratio=snap.get("adr", 50.0) if snap else 50.0,
        )
        dist = net.run(inp)
        return {
            "direction": dist.direction,
            "bullish_prob": dist.bullish_prob,
            "bearish_prob": dist.bearish_prob,
            "neutral_prob": dist.neutral_prob,
            "intensity": dist.intensity,
            "confidence": dist.confidence,
        }
    except Exception as e:
        logger.warning(f"[Ablation] Agent 模拟失败: {e}")
        return None


def agent_score(agent_result: dict, expected_direction: str) -> tuple[float, str]:
    """
    将 Agent 输出转换为方向支持分数。
    返回 (score, reason), score: -1.0 ~ +1.0
    """
    if agent_result is None:
        return 0.0, "Agent不可用"

    agent_dir = agent_result["direction"]
    bull_p = agent_result["bullish_prob"]
    bear_p = agent_result["bearish_prob"]
    conf = agent_result["confidence"]

    if expected_direction == "BULLISH":
        # 多头概率优势，加置信度权重
        prob_score = (bull_p - bear_p) * conf * 2  # [-2, +2] → 归一化
        score = max(-1.0, min(1.0, prob_score))
        dir_match = agent_dir == "BULLISH"
    else:
        prob_score = (bear_p - bull_p) * conf * 2
        score = max(-1.0, min(1.0, prob_score))
        dir_match = agent_dir == "BEARISH"

    reason = (
        f"Agent:{agent_dir} 多{bull_p:.0%}/空{bear_p:.0%} "
        f"置信{conf:.0%} {'✓方向一致' if dir_match else '✗方向相反'}"
    )
    return score, reason


# ══════════════════════════════════════════════════════════════════
# 单案例评估
# ══════════════════════════════════════════════════════════════════

@dataclass
class CaseResult:
    opportunity_id: str
    signal_date: str
    direction: str
    event_type: str
    intensity_score: int
    actual_pnl_pct: float
    actual_outcome: str  # WIN/LOSS

    # 各策略结果: None=被过滤, float=加权后有效盈亏
    baseline_pnl: float | None = None
    sent_pnl: float | None = None
    agent_pnl: float | None = None
    sent_x_agent_pnl: float | None = None
    full_pnl: float | None = None

    # 调试信息
    sent_score: float = 0.0
    sent_reason: str = ""
    agent_score_val: float = 0.0
    agent_reason: str = ""
    agent_direction: str = ""
    sent_x_agent_consensus: str = ""


def evaluate_case(opp: dict, filter_mode: str, precomputed_agent: dict | None) -> CaseResult:
    """对单个机会评估所有5条策略"""
    direction = opp["direction"]
    pnl = opp["actual_pnl_pct"]
    outcome = opp["outcome"]
    snap = SENTIMENT_SEED.get(opp["signal_date"])

    # 情绪面分数
    s_score, s_reason = sentiment_score(snap, direction) if snap else (0.0, "无情绪数据")

    # Agent 分数
    a_result = precomputed_agent
    a_score, a_reason = agent_score(a_result, direction)
    a_dir = a_result["direction"] if a_result else "N/A"

    res = CaseResult(
        opportunity_id=opp["opportunity_id"],
        signal_date=opp["signal_date"],
        direction=direction,
        event_type=opp["event_type"],
        intensity_score=opp["intensity_score"],
        actual_pnl_pct=pnl,
        actual_outcome=outcome,
        sent_score=s_score,
        sent_reason=s_reason,
        agent_score_val=a_score,
        agent_reason=a_reason,
        agent_direction=a_dir,
    )

    # ── 策略1: Baseline（纯机会预判）─────────────────────────────
    res.baseline_pnl = pnl  # 永不过滤，全量

    # ── 策略2: +Sentiment ────────────────────────────────────────
    if filter_mode == "hard":
        # 情绪面分数 > 0 才开仓
        if s_score > 0:
            res.sent_pnl = pnl
        # else: 过滤（None）
    else:  # soft
        # 分数加权：[-1,+1] → 仓位 [0, 1.5]，中性(0)=1.0基准
        weight = 1.0 + s_score * 0.5  # 情绪强支持时最多加50%仓位
        weight = max(0.1, weight)      # 最低保留10%
        res.sent_pnl = pnl * weight

    # ── 策略3: +Agent ────────────────────────────────────────────
    if filter_mode == "hard":
        if a_score > 0:
            res.agent_pnl = pnl
    else:
        weight = 1.0 + a_score * 0.5
        weight = max(0.1, weight)
        res.agent_pnl = pnl * weight

    # ── 策略4: Sent×Agent（不依赖机会方向）──────────────────────
    # 情绪面和Agent共同给出方向，看是否命中实际 outcome
    if snap and a_result:
        combined_score = s_score * 0.5 + a_score * 0.5  # 均权融合
        # 融合方向
        if combined_score > 0.1:
            consensus_dir = direction  # 情绪+Agent 双向多
        elif combined_score < -0.1:
            consensus_dir = "BEARISH" if direction == "BULLISH" else "BULLISH"
        else:
            consensus_dir = "NEUTRAL"
        res.sent_x_agent_consensus = f"{consensus_dir}(score={combined_score:.2f})"

        if filter_mode == "hard":
            if consensus_dir == direction and abs(combined_score) > 0.15:
                res.sent_x_agent_pnl = pnl
            # else: 过滤
        else:
            weight = 1.0 + combined_score * 0.6
            weight = max(0.05, weight)
            res.sent_x_agent_pnl = pnl * weight
    else:
        res.sent_x_agent_pnl = None  # 缺数据时过滤

    # ── 策略5: Full（三合一）────────────────────────────────────
    if snap and a_result:
        full_score = s_score * 0.4 + a_score * 0.4 + 0.2  # +0.2 机会方向基础分
        full_score = max(-1.0, min(1.0, full_score))
        if filter_mode == "hard":
            if s_score > 0 and a_score > 0:
                res.full_pnl = pnl
            # else: 过滤
        else:
            weight = 1.0 + full_score * 0.6
            weight = max(0.1, weight)
            res.full_pnl = pnl * weight
    elif snap:
        # 只有情绪面，无Agent
        if filter_mode == "hard":
            res.full_pnl = pnl if s_score > 0 else None
        else:
            res.full_pnl = pnl * (1.0 + s_score * 0.4)
    else:
        res.full_pnl = res.baseline_pnl  # 完全无情绪数据，退化为基准

    return res


# ══════════════════════════════════════════════════════════════════
# 策略统计
# ══════════════════════════════════════════════════════════════════

@dataclass
class StrategyStats:
    name: str
    filter_mode: str
    total_in: int           # 输入案例数
    traded: int             # 实际开仓数
    filter_rate: float      # 过滤率
    win_count: int
    loss_count: int
    win_rate: float
    avg_pnl: float
    avg_win_pnl: float
    avg_loss_pnl: float
    max_loss: float
    profit_factor: float
    expected_value: float   # win_rate * avg_win + (1-win_rate) * avg_loss


def compute_stats(name: str, filter_mode: str, pnl_list_raw: list[float | None],
                  outcomes: list[str]) -> StrategyStats:
    """
    pnl_list_raw: None = 被过滤, float = 实际盈亏（可能加权）
    outcomes: 对应的原始 WIN/LOSS（用于判断胜负）
    """
    total_in = len(pnl_list_raw)
    traded_pairs = [(p, o) for p, o in zip(pnl_list_raw, outcomes) if p is not None]
    traded = len(traded_pairs)
    filter_rate = (total_in - traded) / total_in if total_in > 0 else 0.0

    if traded == 0:
        return StrategyStats(
            name=name, filter_mode=filter_mode,
            total_in=total_in, traded=0, filter_rate=1.0,
            win_count=0, loss_count=0, win_rate=0.0,
            avg_pnl=0.0, avg_win_pnl=0.0, avg_loss_pnl=0.0,
            max_loss=0.0, profit_factor=0.0, expected_value=0.0,
        )

    # 对 soft 模式，盈亏已加权，但胜负判断用原始 outcome
    wins = [(p, o) for p, o in traded_pairs if o == "WIN"]
    losses = [(p, o) for p, o in traded_pairs if o == "LOSS"]

    win_pnls = [p for p, _ in wins]
    loss_pnls = [p for p, _ in losses]  # 加权后可能为负数

    win_count = len(wins)
    loss_count = len(losses)
    win_rate = win_count / traded if traded > 0 else 0.0

    avg_pnl = sum(p for p, _ in traded_pairs) / traded
    avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0.0
    avg_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0.0
    max_loss = min(loss_pnls) if loss_pnls else 0.0

    gross_profit = sum(p for p in win_pnls if p > 0)
    gross_loss = abs(sum(p for p in loss_pnls if p < 0))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    ev = win_rate * avg_win + (1 - win_rate) * avg_loss

    return StrategyStats(
        name=name, filter_mode=filter_mode,
        total_in=total_in, traded=traded, filter_rate=filter_rate,
        win_count=win_count, loss_count=loss_count, win_rate=win_rate,
        avg_pnl=avg_pnl, avg_win_pnl=avg_win, avg_loss_pnl=avg_loss,
        max_loss=max_loss, profit_factor=profit_factor, expected_value=ev,
    )


# ══════════════════════════════════════════════════════════════════
# 主消融实验
# ══════════════════════════════════════════════════════════════════

class AblationStudy:
    STRATEGY_NAMES = ["Baseline", "+Sentiment", "+Agent", "Sent×Agent", "Full"]
    STRATEGY_PNL_FIELDS = [
        "baseline_pnl", "sent_pnl", "agent_pnl",
        "sent_x_agent_pnl", "full_pnl",
    ]

    def __init__(self, opportunities: list[dict], filter_mode: str = "both",
                 run_agent: bool = True):
        self.opportunities = opportunities
        self.filter_mode = filter_mode  # "hard" | "soft" | "both"
        self.run_agent = run_agent
        self.case_results: list[CaseResult] = []
        self.stats_table: list[StrategyStats] = []

    def run(self) -> "AblationStudy":
        print(f"\n{'='*65}")
        print(f"  模块消融实验  共 {len(self.opportunities)} 个历史案例")
        modes = ["hard", "soft"] if self.filter_mode == "both" else [self.filter_mode]
        print(f"  filter_mode: {self.filter_mode}  |  M11 Agent: {'开启' if self.run_agent else '关闭（规则模式）'}")
        print(f"{'='*65}\n")

        # 预先加载 AgentNetwork（避免重复初始化）
        if self.run_agent:
            print("  [加载 M11 AgentNetwork...]")
            _get_agent_network("a_share")

        # 逐案例评估
        agent_cache: dict[str, dict | None] = {}
        outcomes = [o["outcome"] for o in self.opportunities]

        print(f"  {'ID':<10} {'日期':<12} {'方向':<6} {'强度':<4} {'实际盈亏':<8} {'情绪得分':<8} {'Agent方向':<10}")
        print(f"  {'-'*65}")

        for opp in self.opportunities:
            sid = opp["signal_date"]
            snap = SENTIMENT_SEED.get(sid)

            # Agent 模拟（每个日期只跑一次）
            if sid not in agent_cache:
                if self.run_agent:
                    agent_cache[sid] = run_agent_sim(opp, snap)
                else:
                    agent_cache[sid] = None

            cr = evaluate_case(opp, "hard", agent_cache[sid])
            self.case_results.append(cr)

            print(
                f"  {opp['opportunity_id']:<10} {sid:<12} "
                f"{opp['direction']:<6} {opp['intensity_score']:<4} "
                f"{opp['actual_pnl_pct']:+.1f}%{'':<3} "
                f"{cr.sent_score:+.2f}{'':>4} "
                f"{cr.agent_direction:<10}"
            )

        # 计算各策略统计（hard / soft / both）
        for mode in modes:
            # 重新用指定 mode 计算（soft 需要不同权重）
            case_results_mode: list[CaseResult] = []
            for opp in self.opportunities:
                sid = opp["signal_date"]
                snap = SENTIMENT_SEED.get(sid)
                cr_m = evaluate_case(opp, mode, agent_cache.get(sid))
                case_results_mode.append(cr_m)

            for sname, sfield in zip(self.STRATEGY_NAMES, self.STRATEGY_PNL_FIELDS):
                pnl_list = [getattr(cr, sfield) for cr in case_results_mode]
                stats = compute_stats(sname, mode, pnl_list, outcomes)
                self.stats_table.append(stats)

        return self

    def report(self) -> str:
        lines = []
        lines.append(f"\n{'='*75}")
        lines.append("  消融实验报告 — 各模块对交易系统的边际贡献")
        lines.append(f"{'='*75}")

        modes = sorted(set(s.filter_mode for s in self.stats_table))

        for mode in modes:
            lines.append(f"\n── filter_mode: {mode.upper()} ({'方向不符直接过滤' if mode=='hard' else '概率加权仓位'}) ──")
            lines.append(
                f"  {'策略':<14} {'案例':>4} {'过滤率':>6} {'胜率':>7} {'均盈亏':>8} "
                f"{'均盈利':>8} {'均亏损':>8} {'盈亏比':>6} {'期望值':>7}"
            )
            lines.append(f"  {'-'*75}")

            mode_stats = [s for s in self.stats_table if s.filter_mode == mode]
            baseline = next((s for s in mode_stats if s.name == "Baseline"), None)

            for s in mode_stats:
                # 相对基准的增量
                wr_delta = (s.win_rate - baseline.win_rate) * 100 if baseline and s.name != "Baseline" else 0.0
                pnl_delta = s.avg_pnl - baseline.avg_pnl if baseline and s.name != "Baseline" else 0.0
                delta_str = f" ({wr_delta:+.1f}pp胜率 {pnl_delta:+.2f}%均盈亏)" if s.name != "Baseline" else ""

                pf_str = f"{s.profit_factor:.2f}" if s.profit_factor != float("inf") else "∞"
                lines.append(
                    f"  {s.name:<14} {s.traded:>4} {s.filter_rate:>5.0%}  "
                    f"{s.win_rate:>6.1%} {s.avg_pnl:>+7.2f}% "
                    f"{s.avg_win_pnl:>+7.2f}% {s.avg_loss_pnl:>+7.2f}% "
                    f"{pf_str:>6} {s.expected_value:>+6.2f}%"
                    f"{delta_str}"
                )

        # ── 边际贡献热力图（ASCII）────────────────────────────────
        lines.append(f"\n── 边际贡献分析（相对 Baseline，hard 模式）──")
        hard_stats = {s.name: s for s in self.stats_table if s.filter_mode == "hard"}
        base = hard_stats.get("Baseline")
        if base:
            metrics = {
                "胜率提升": lambda s: (s.win_rate - base.win_rate) * 100,
                "均盈亏提升": lambda s: s.avg_pnl - base.avg_pnl,
                "期望值提升": lambda s: s.expected_value - base.expected_value,
            }
            strategies_order = ["+Sentiment", "+Agent", "Sent×Agent", "Full"]

            header = f"  {'指标':<12}" + "".join(f"{n:>14}" for n in strategies_order)
            lines.append(header)
            lines.append(f"  {'-'*68}")

            for metric_name, fn in metrics.items():
                row = f"  {metric_name:<12}"
                for sname in strategies_order:
                    s = hard_stats.get(sname)
                    if s and s.traded > 0:
                        val = fn(s)
                        bar = _mini_bar(val)
                        row += f"  {val:>+5.1f}  {bar:<5}"
                    else:
                        row += f"  {'N/A':>12}"
                lines.append(row)

        # ── 关键结论 ──────────────────────────────────────────────
        lines.append(f"\n── 关键结论 ──")
        hard_stats_list = [s for s in self.stats_table if s.filter_mode == "hard"]
        best_wr = max(hard_stats_list, key=lambda s: s.win_rate if s.traded > 0 else 0)
        best_pnl = max(hard_stats_list, key=lambda s: s.avg_pnl if s.traded > 0 else -999)
        best_ev = max(hard_stats_list, key=lambda s: s.expected_value if s.traded > 0 else -999)

        lines.append(f"  最高胜率策略:   {best_wr.name:<14} → {best_wr.win_rate:.1%} "
                     f"(过滤率{best_wr.filter_rate:.0%}, {best_wr.traded}案例)")
        lines.append(f"  最高均盈亏策略: {best_pnl.name:<14} → {best_pnl.avg_pnl:+.2f}%/案例")
        lines.append(f"  最高期望值策略: {best_ev.name:<14} → {best_ev.expected_value:+.2f}%/案例")

        # 模块贡献排名
        contribs = []
        if base:
            for nm in ["+Sentiment", "+Agent", "Sent×Agent"]:
                s = hard_stats.get(nm)
                if s and s.traded > 0:
                    contribs.append((nm, s.win_rate - base.win_rate, s.avg_pnl - base.avg_pnl))
        if contribs:
            contribs_sorted = sorted(contribs, key=lambda x: x[1], reverse=True)
            lines.append(f"\n  单模块胜率贡献排名:")
            for rank, (nm, wr_d, pnl_d) in enumerate(contribs_sorted, 1):
                lines.append(f"    {rank}. {nm:<14} 胜率{wr_d*100:+.1f}pp  均盈亏{pnl_d:+.2f}%")

        lines.append(f"\n{'='*75}")
        return "\n".join(lines)

    def save(self, path: Path | None = None) -> Path:
        if path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = ROOT / "data" / "backtest" / f"ablation_{ts}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        output = {
            "run_time": datetime.now().isoformat(),
            "total_cases": len(self.opportunities),
            "filter_mode": self.filter_mode,
            "stats": [asdict(s) for s in self.stats_table],
            "cases": [asdict(c) for c in self.case_results],
        }
        path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def _mini_bar(val: float, scale: float = 10.0) -> str:
    """简单 ASCII 条形图，正负各5格"""
    filled = int(abs(val) / scale * 5)
    filled = min(5, filled)
    if val >= 0:
        return "+" + "█" * filled
    else:
        return "-" + "█" * filled


# ══════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="模块消融实验")
    parser.add_argument("--mode", choices=["hard", "soft", "both"], default="both")
    parser.add_argument("--no-agent", action="store_true", help="不运行 M11 Agent（更快）")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    opps = get_seed_opportunities()
    study = AblationStudy(opps, filter_mode=args.mode, run_agent=not args.no_agent)
    study.run()

    report = study.report()
    print(report)

    if args.save:
        p = study.save()
        print(f"\n结果已保存: {p}")

    return study


if __name__ == "__main__":
    main()
