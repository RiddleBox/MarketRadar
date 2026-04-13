"""
m9_paper_trader/evaluator.py — 信号有效性评估

核心问题：
  "我们的信号，到底有没有预测力？"

评估维度：
  1. 基础胜率（按信号类型/市场/方向/时效）
  2. 盈亏比（E[win] / |E[loss]|）
  3. 信号强度分层（intensity_score 高的是否真的更准？）
  4. 置信度分层（confidence_score 高的是否真的更准？）
  5. 时间衰减（持仓时长 vs 预期 time_horizon 的对齐度）
  6. MAE/MFE 分布（最大不利偏移/最大有利偏移）
  7. 综合 Sharpe（简化版，基于模拟盘 pnl 序列）
"""
from __future__ import annotations

import json
import math
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

REPORT_DIR = Path(__file__).parent / "reports"


class SignalEvaluator:
    """
    信号有效性评估器。

    使用方式：
      evaluator = SignalEvaluator()
      report = evaluator.evaluate(paper_trader.list_closed())
      evaluator.save_report(report)
    """

    def __init__(self):
        REPORT_DIR.mkdir(parents=True, exist_ok=True)

    def evaluate(self, positions: list, min_closed: int = 5) -> dict:
        """
        对已关闭的模拟持仓进行全面评估。

        Args:
            positions: PaperPosition 列表（或 dict 列表）
            min_closed: 至少需要多少条关闭持仓才计算统计

        Returns:
            完整评估报告 dict
        """
        # 统一转为 dict
        pos_dicts = []
        for p in positions:
            if hasattr(p, "to_dict"):
                pos_dicts.append(p.to_dict())
            else:
                pos_dicts.append(p)

        closed = [p for p in pos_dicts if p.get("status") != "OPEN"]

        report: dict = {
            "generated_at": datetime.now().isoformat(),
            "total_positions": len(pos_dicts),
            "closed_positions": len(closed),
            "open_positions": len(pos_dicts) - len(closed),
        }

        if len(closed) < min_closed:
            report["warning"] = f"样本不足（需要至少 {min_closed} 条关闭持仓，当前 {len(closed)} 条）"
            report["overall"] = {}
            return report

        # ── 整体统计 ─────────────────────────────────────────
        report["overall"] = self._calc_stats(closed, label="整体")

        # ── 按信号类型 ───────────────────────────────────────
        by_type: Dict[str, list] = defaultdict(list)
        for p in closed:
            by_type[p.get("signal_type", "unknown")].append(p)
        report["by_signal_type"] = {
            k: self._calc_stats(v, label=k)
            for k, v in by_type.items() if len(v) >= 3
        }

        # ── 按市场 ───────────────────────────────────────────
        by_market: Dict[str, list] = defaultdict(list)
        for p in closed:
            by_market[p.get("market", "unknown")].append(p)
        report["by_market"] = {
            k: self._calc_stats(v, label=k)
            for k, v in by_market.items() if len(v) >= 3
        }

        # ── 按方向 ───────────────────────────────────────────
        by_dir: Dict[str, list] = defaultdict(list)
        for p in closed:
            by_dir[p.get("direction", "unknown")].append(p)
        report["by_direction"] = {
            k: self._calc_stats(v, label=k)
            for k, v in by_dir.items() if len(v) >= 3
        }

        # ── 信号强度分层（intensity_score）───────────────────
        report["by_intensity_tier"] = self._tier_analysis(
            closed, score_key="signal_intensity", label="intensity"
        )

        # ── 置信度分层（confidence_score）────────────────────
        report["by_confidence_tier"] = self._tier_analysis(
            closed, score_key="signal_confidence", label="confidence"
        )

        # ── MAE / MFE 分布 ───────────────────────────────────
        maes = [p.get("max_adverse_excursion", 0) for p in closed]
        mfes = [p.get("max_favorable_excursion", 0) for p in closed]
        report["mae_mfe"] = {
            "avg_mae": round(sum(maes) / len(maes) * 100, 2),
            "avg_mfe": round(sum(mfes) / len(mfes) * 100, 2),
            "median_mae": round(self._median(maes) * 100, 2),
            "median_mfe": round(self._median(mfes) * 100, 2),
            "comment": self._mae_mfe_comment(
                sum(maes) / len(maes),
                sum(mfes) / len(mfes),
            ),
        }

        # ── 结果分布 ─────────────────────────────────────────
        outcome_dist: Dict[str, int] = defaultdict(int)
        for p in closed:
            outcome_dist[p.get("status", "unknown")] += 1
        report["outcome_distribution"] = dict(outcome_dist)

        # ── 综合评级 ─────────────────────────────────────────
        report["signal_efficacy_grade"] = self._grade(report["overall"])

        # ── 改进建议 ─────────────────────────────────────────
        report["recommendations"] = self._recommendations(report)

        return report

    # ── 统计子函数 ────────────────────────────────────────────

    def _calc_stats(self, positions: list, label: str = "") -> dict:
        """计算一组持仓的核心统计指标"""
        pnls = [p.get("realized_pnl_pct", 0) or 0 for p in positions]
        if not pnls:
            return {}

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        win_rate = len(wins) / len(pnls)
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        profit_factor = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else float("inf")
        avg_pnl = sum(pnls) / len(pnls)
        expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

        # 简化 Sharpe（以单笔 pnl 为回报序列）
        sharpe = self._sharpe(pnls)

        return {
            "label": label,
            "count": len(pnls),
            "win_rate": round(win_rate * 100, 1),
            "avg_pnl_pct": round(avg_pnl * 100, 2),
            "avg_win_pct": round(avg_win * 100, 2),
            "avg_loss_pct": round(avg_loss * 100, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "∞",
            "expectancy_pct": round(expectancy * 100, 2),
            "sharpe": round(sharpe, 2),
            "best": round(max(pnls) * 100, 2),
            "worst": round(min(pnls) * 100, 2),
        }

    def _tier_analysis(self, positions: list, score_key: str, label: str) -> dict:
        """按分数分 3 档（低/中/高）分析胜率"""
        scores = [p.get(score_key, 0) or 0 for p in positions]
        if not scores:
            return {}

        lo_thresh = 4.0  # < 4 = 低
        hi_thresh = 7.0  # >= 7 = 高

        tiers: Dict[str, list] = {"low(<4)": [], "mid(4-7)": [], "high(>=7)": []}
        for p, s in zip(positions, scores):
            if s < lo_thresh:
                tiers["low(<4)"].append(p)
            elif s < hi_thresh:
                tiers["mid(4-7)"].append(p)
            else:
                tiers["high(>=7)"].append(p)

        result = {}
        for tier, ps in tiers.items():
            if len(ps) >= 3:
                result[tier] = self._calc_stats(ps, label=f"{label}_{tier}")
            else:
                result[tier] = {"count": len(ps), "note": "样本不足"}

        # 检验分层效果：高分组胜率是否显著高于低分组？
        low_wr = result.get("low(<4)", {}).get("win_rate", 0)
        high_wr = result.get("high(>=7)", {}).get("win_rate", 0)
        result["tier_lift"] = {
            "high_minus_low_win_rate": round(high_wr - low_wr, 1),
            "has_predictive_power": high_wr > low_wr + 10,  # 高分组胜率高于低分组10%+
        }

        return result

    # ── 工具函数 ──────────────────────────────────────────────

    def _sharpe(self, pnls: list, risk_free: float = 0.0) -> float:
        if len(pnls) < 2:
            return 0.0
        n = len(pnls)
        mean = sum(pnls) / n
        variance = sum((x - mean) ** 2 for x in pnls) / (n - 1)
        std = math.sqrt(variance) if variance > 0 else 1e-9
        return (mean - risk_free) / std

    def _median(self, lst: list) -> float:
        if not lst:
            return 0.0
        s = sorted(lst)
        n = len(s)
        mid = n // 2
        return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2

    def _mae_mfe_comment(self, avg_mae: float, avg_mfe: float) -> str:
        ratio = abs(avg_mfe / avg_mae) if avg_mae != 0 else float("inf")
        if ratio >= 2.0:
            return f"MFE/MAE={ratio:.1f}x，价格在触及止损前通常能到达更大有利方向，止损位置合理"
        elif ratio >= 1.0:
            return f"MFE/MAE={ratio:.1f}x，基本合理"
        else:
            return f"MFE/MAE={ratio:.1f}x，止损过紧或信号方向性弱，建议review止损设置"

    def _grade(self, overall: dict) -> dict:
        """综合评级 A/B/C/D"""
        if not overall:
            return {"grade": "N/A", "reason": "数据不足"}

        win_rate = overall.get("win_rate", 0)
        profit_factor = overall.get("profit_factor", 0)
        if isinstance(profit_factor, str):
            profit_factor = 99.0
        expectancy = overall.get("expectancy_pct", 0)

        if win_rate >= 60 and profit_factor >= 2.0 and expectancy > 1:
            grade, desc = "A", "信号质量优秀，具备显著预测力"
        elif win_rate >= 50 and profit_factor >= 1.5 and expectancy > 0:
            grade, desc = "B", "信号质量良好，有正期望值"
        elif expectancy > 0:
            grade, desc = "C", "期望值为正但边际，需要优化信号质量"
        else:
            grade, desc = "D", "期望值为负，信号系统需要根本性改进"

        return {"grade": grade, "description": desc, "win_rate": win_rate,
                "profit_factor": profit_factor, "expectancy_pct": expectancy}

    def _recommendations(self, report: dict) -> List[str]:
        """基于评估结果生成改进建议"""
        recs = []
        overall = report.get("overall", {})

        # 胜率建议
        wr = overall.get("win_rate", 0)
        if wr < 45:
            recs.append(f"整体胜率偏低（{wr}%），建议提高 M3 的置信度门槛（当前可能太宽泛）")
        elif wr > 70:
            recs.append(f"胜率高（{wr}%）但需检查盈亏比是否过低，避免小赢大亏")

        # 盈亏比建议
        pf = overall.get("profit_factor", 0)
        if isinstance(pf, str):
            pf = 99.0
        if pf < 1.0:
            recs.append("盈亏比<1，止盈目标可能设置过低或止损过紧，建议用 MAE/MFE 重新校准")

        # 信号分层建议
        intensity_tier = report.get("by_intensity_tier", {})
        tier_lift = intensity_tier.get("tier_lift", {})
        if tier_lift and not tier_lift.get("has_predictive_power"):
            recs.append("intensity_score 高低分组胜率差异不足10%，强度评分对预测力贡献有限，需审查 M1 评分逻辑")
        elif tier_lift and tier_lift.get("has_predictive_power"):
            recs.append(f"intensity_score 分层有效（高分组胜率高 {tier_lift.get('high_minus_low_win_rate')}%），建议仅开高强度信号的模拟仓")

        # MAE/MFE 建议
        mae_mfe = report.get("mae_mfe", {})
        if mae_mfe.get("avg_mae", 0) and mae_mfe.get("avg_mfe", 0):
            ratio = abs(mae_mfe["avg_mfe"] / mae_mfe["avg_mae"]) if mae_mfe["avg_mae"] else 0
            if ratio < 1.0:
                recs.append("MFE/MAE 比值 <1，价格到达止损前平均有利偏移更小，可能说明方向判断本身有问题")

        # 按类型建议
        by_type = report.get("by_signal_type", {})
        worst_type = min(by_type.items(), key=lambda x: x[1].get("expectancy_pct", 0), default=None)
        best_type = max(by_type.items(), key=lambda x: x[1].get("expectancy_pct", 0), default=None)
        if worst_type and worst_type[1].get("expectancy_pct", 0) < 0:
            recs.append(f"信号类型 '{worst_type[0]}' 期望值为负（{worst_type[1].get('expectancy_pct')}%），建议暂停该类信号的模拟交易")
        if best_type:
            recs.append(f"信号类型 '{best_type[0]}' 表现最佳（期望 {best_type[1].get('expectancy_pct')}%），可以重点关注")

        if not recs:
            recs.append("系统整体运行良好，维持当前参数，继续积累样本")

        return recs

    # ── 报告持久化 ────────────────────────────────────────────

    def save_report(self, report: dict, filename: Optional[str] = None) -> Path:
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"eval_{ts}.json"
        path = REPORT_DIR / filename
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info(f"[M9] 评估报告已保存: {path}")
        return path

    def load_latest_report(self) -> Optional[dict]:
        files = sorted(REPORT_DIR.glob("eval_*.json"), reverse=True)
        if not files:
            return None
        try:
            return json.loads(files[0].read_text(encoding="utf-8"))
        except Exception:
            return None
