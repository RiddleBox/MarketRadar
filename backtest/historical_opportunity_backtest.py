"""
backtest/historical_opportunity_backtest.py — 历史机会回测主程序

基于 seed_opportunities.py 的 20 个历史案例，对接：
  - core/schemas.py 的 MarketSignal / Opportunity 结构
  - m11_agent_sim/agent_network.py 的 AgentNetwork
  - backtest/seed_data.py 的 510300 价格数据
  - backtest/backtest_engine.py 的回测引擎

输出三类报告：
  1. 整体统计（胜率/盈亏比/信号质量分层）
  2. M11 Agent 判断 vs 实际结果对比
  3. 强度分层分析（intensity_score 8+/6-7/5以下）

使用方法：
  python backtest/historical_opportunity_backtest.py
  python backtest/historical_opportunity_backtest.py --group m11   # 只跑M11校准事件
  python backtest/historical_opportunity_backtest.py --group all   # 全部20个
  python backtest/historical_opportunity_backtest.py --m11-sim     # 对每条机会跑M11 Agent
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

# ── 项目根路径 ──────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from backtest.seed_opportunities import (
    SEED_OPPORTUNITIES,
    get_seed_opportunities,
    get_statistics as get_seed_stats,
)
from backtest.seed_data import SEED_510300


# ──────────────────────────────────────────────────────────────
# 辅助：查价格
# ──────────────────────────────────────────────────────────────

def _get_price(date_str: str, field: str = "close") -> float | None:
    """从 seed_data + price_cache 查价格"""
    # 先查 seed_data
    if date_str in SEED_510300:
        return SEED_510300[date_str][field]
    # 再查 price_cache
    cache_file = ROOT / "data" / "price_cache" / "510300_SH.json"
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if date_str in data:
                return data[date_str][field]
        except Exception:
            pass
    return None


def _nearest_trading_day(date_str: str, forward: bool = True) -> str:
    """找最近交易日（在 seed_data 或 price_cache 中存在的日期）"""
    cache_file = ROOT / "data" / "price_cache" / "510300_SH.json"
    available = set(SEED_510300.keys())
    if cache_file.exists():
        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            available.update(data.keys())
        except Exception:
            pass
    sorted_dates = sorted(available)

    dt = datetime.strptime(date_str, "%Y-%m-%d")
    for i in range(30):
        delta = i if forward else -i
        candidate = (dt + timedelta(days=delta)).strftime("%Y-%m-%d")
        if candidate in available:
            return candidate
    return date_str


# ──────────────────────────────────────────────────────────────
# M11 Agent 模拟（可选）
# ──────────────────────────────────────────────────────────────

def _run_m11_simulation(opp: dict) -> dict | None:
    """对单个机会运行 M11 AgentNetwork 模拟"""
    try:
        from m11_agent_sim.agent_network import AgentNetwork, AgentNetworkConfig

        config = AgentNetworkConfig.from_yaml(
            ROOT / "m11_agent_sim" / "configs" / "a_share.yaml"
        )
        network = AgentNetwork(config)

        # 构造简单市场数据
        event_desc = opp["opportunity_title"]
        direction_hint = opp["direction"]
        intensity = opp["intensity_score"]

        result = network.run(
            event_description=event_desc,
            market_context={
                "date": opp["signal_date"],
                "hint_direction": direction_hint,
                "intensity": intensity,
            },
        )
        return {
            "direction": result.final_direction,
            "bullish_prob": round(result.bullish_prob, 3),
            "bearish_prob": round(result.bearish_prob, 3),
            "neutral_prob": round(result.neutral_prob, 3),
            "intensity": round(result.intensity_score, 1),
            "confidence": round(result.confidence, 3),
        }
    except Exception as e:
        return {"error": str(e)}


# ──────────────────────────────────────────────────────────────
# 回测核心
# ──────────────────────────────────────────────────────────────

class HistoricalOpportunityBacktest:
    def __init__(self, opportunities: list[dict], run_m11: bool = False):
        self.opportunities = opportunities
        self.run_m11 = run_m11
        self.results: list[dict] = []

    def run(self) -> "HistoricalOpportunityBacktest":
        print(f"\n{'='*60}")
        print(f"历史机会回测  共 {len(self.opportunities)} 个案例")
        if self.run_m11:
            print("  [M11 Agent 模式已开启]")
        print(f"{'='*60}\n")

        for i, opp in enumerate(self.opportunities, 1):
            result = self._backtest_one(opp, i)
            self.results.append(result)

        return self

    def _backtest_one(self, opp: dict, idx: int) -> dict:
        oid = opp["opportunity_id"]
        title = opp["opportunity_title"][:35]
        signal_date = opp["signal_date"]
        direction = opp["direction"]
        intensity = opp["intensity_score"]
        ground_truth_pnl = opp["actual_pnl_pct"]
        ground_truth_outcome = opp["outcome"]

        # 获取价格
        entry_price = opp.get("entry_price") or _get_price(signal_date)
        exit_date_est = (
            datetime.strptime(signal_date, "%Y-%m-%d")
            + timedelta(days=opp["holding_days"] + 2)  # +2 for weekends
        ).strftime("%Y-%m-%d")
        exit_date = _nearest_trading_day(exit_date_est)
        exit_price = opp.get("exit_price") or _get_price(exit_date)

        # 验证价格逻辑
        price_verified = False
        if entry_price and exit_price:
            raw_pnl = (
                (exit_price - entry_price) / entry_price * 100
                if direction == "BULLISH"
                else (entry_price - exit_price) / entry_price * 100
            )
            price_verified = abs(raw_pnl - abs(ground_truth_pnl)) < 3.0  # 允许3%误差

        # M11 模拟
        m11_result = None
        m11_match = None
        if self.run_m11:
            m11_result = _run_m11_simulation(opp)
            if m11_result and "error" not in m11_result:
                m11_dir = m11_result["direction"]
                m11_match = (m11_dir == direction) == (ground_truth_outcome == "WIN")

        # 强度分级
        if intensity >= 9:
            intensity_grade = "S"
        elif intensity >= 8:
            intensity_grade = "A"
        elif intensity >= 7:
            intensity_grade = "B"
        elif intensity >= 6:
            intensity_grade = "C"
        else:
            intensity_grade = "D"

        result = {
            "idx": idx,
            "opportunity_id": oid,
            "title": title,
            "signal_date": signal_date,
            "direction": direction,
            "event_type": opp["event_type"],
            "intensity_score": intensity,
            "intensity_grade": intensity_grade,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "holding_days": opp["holding_days"],
            "actual_pnl_pct": ground_truth_pnl,
            "outcome": ground_truth_outcome,
            "price_verified": price_verified,
            "m11_result": m11_result,
            "m11_match": m11_match,
            "tags": opp.get("signal_tags", []),
            "notes": opp.get("notes", ""),
        }

        # 打印进度
        icon = "✓" if ground_truth_outcome == "WIN" else "✗"
        m11_tag = ""
        if m11_result and "error" not in m11_result:
            m11_tag = f"  M11:{m11_result['direction']}({m11_result['bullish_prob']:.0%})"
        price_tag = " [price✓]" if price_verified else " [est]"

        print(
            f"  {icon} [{idx:02d}] {title:<35} "
            f"{ground_truth_pnl:+.1f}% {direction[:4]:<4} "
            f"强度{intensity}({intensity_grade}){price_tag}{m11_tag}"
        )

        return result

    # ──────────────────────────────────────────────────────────
    # 报告生成
    # ──────────────────────────────────────────────────────────

    def report(self) -> str:
        if not self.results:
            return "无回测结果"

        lines = []
        lines.append("\n" + "=" * 70)
        lines.append("  历史机会回测报告")
        lines.append("=" * 70)

        total = len(self.results)
        wins = [r for r in self.results if r["outcome"] == "WIN"]
        losses = [r for r in self.results if r["outcome"] == "LOSS"]
        win_rate = len(wins) / total * 100

        all_pnl = [r["actual_pnl_pct"] for r in self.results]
        win_pnl = [r["actual_pnl_pct"] for r in wins]
        loss_pnl = [abs(r["actual_pnl_pct"]) for r in losses]

        avg_win = sum(win_pnl) / len(win_pnl) if win_pnl else 0
        avg_loss = sum(loss_pnl) / len(loss_pnl) if loss_pnl else 0
        profit_factor = (avg_win * len(wins)) / (avg_loss * len(losses) + 0.001)

        lines.append(f"\n【总体统计】")
        lines.append(f"  案例数:     {total}  (胜{len(wins)}/败{len(losses)})")
        lines.append(f"  胜率:       {win_rate:.1f}%")
        lines.append(f"  平均盈利:   {avg_win:+.2f}%")
        lines.append(f"  平均亏损:   {-avg_loss:+.2f}%")
        lines.append(f"  盈亏比:     {avg_win/avg_loss:.2f}x" if avg_loss > 0 else "  盈亏比:     ∞")
        lines.append(f"  利润因子:   {profit_factor:.2f}")
        lines.append(f"  期望值:     {sum(all_pnl)/total:+.2f}%/案例")

        # 强度分层
        lines.append(f"\n【信号强度分层（核心指标）】")
        for grade, min_i, label in [
            ("S", 9, "极强(9-10)"),
            ("A", 8, "强(8分)  "),
            ("B", 7, "中强(7分)"),
            ("C", 6, "中(6分)  "),
            ("D", 0, "弱(≤5分) "),
        ]:
            grade_results = [r for r in self.results if r["intensity_grade"] == grade]
            if not grade_results:
                continue
            g_wins = sum(1 for r in grade_results if r["outcome"] == "WIN")
            g_pnl = [r["actual_pnl_pct"] for r in grade_results]
            lines.append(
                f"  {label}: {len(grade_results):2d}案例 "
                f"胜率{g_wins/len(grade_results)*100:5.1f}% "
                f"均盈亏{sum(g_pnl)/len(g_pnl):+.2f}%"
            )

        # 事件类型分层
        lines.append(f"\n【事件类型分层】")
        for et in ["macro", "policy", "industry", "capital_flow", "technical"]:
            et_results = [r for r in self.results if r["event_type"] == et]
            if not et_results:
                continue
            et_wins = sum(1 for r in et_results if r["outcome"] == "WIN")
            et_pnl = [r["actual_pnl_pct"] for r in et_results]
            lines.append(
                f"  {et:<14}: {len(et_results):2d}案例 "
                f"胜率{et_wins/len(et_results)*100:5.1f}% "
                f"均盈亏{sum(et_pnl)/len(et_results):+.2f}%"
            )

        # M11 对比
        m11_done = [r for r in self.results if r.get("m11_match") is not None]
        if m11_done:
            m11_acc = sum(1 for r in m11_done if r["m11_match"]) / len(m11_done) * 100
            lines.append(f"\n【M11 Agent 判断准确率】")
            lines.append(f"  验证案例: {len(m11_done)}")
            lines.append(f"  方向准确率: {m11_acc:.1f}%")

        # 关键结论
        lines.append(f"\n【关键结论】")
        if win_rate >= 75:
            lines.append(f"  ✓ 整体胜率 {win_rate:.1f}% ≥ 75%，信号系统质量达标")
        else:
            lines.append(f"  ⚠ 整体胜率 {win_rate:.1f}% < 75%，需审查低强度信号")

        hi_results = [r for r in self.results if r["intensity_score"] >= 8]
        if hi_results:
            hi_wr = sum(1 for r in hi_results if r["outcome"] == "WIN") / len(hi_results) * 100
            if hi_wr >= 80:
                lines.append(f"  ✓ 高强度信号(≥8分)胜率 {hi_wr:.1f}%，建议开仓阈值设为8分")
            else:
                lines.append(f"  ⚠ 高强度信号(≥8分)胜率 {hi_wr:.1f}%，强度分层效果待优化")

        if avg_win > 0 and avg_loss > 0:
            rr = avg_win / avg_loss
            if rr >= 1.5:
                lines.append(f"  ✓ 盈亏比 {rr:.2f}x ≥ 1.5x，风险回报合理")

        loss_cases = [r for r in losses]
        if loss_cases:
            lines.append(f"\n【失败案例复盘】")
            for r in loss_cases:
                lines.append(f"  ✗ [{r['signal_date']}] {r['title'][:30]} "
                             f"{r['actual_pnl_pct']:+.1f}% 强度{r['intensity_score']}")
                lines.append(f"    → {r['notes'][:60]}...")

        lines.append("\n" + "=" * 70)
        return "\n".join(lines)

    def save(self, output_path: Path | None = None) -> Path:
        """保存回测结果"""
        if output_path is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = ROOT / "data" / "backtest" / f"hist_bt_{ts}.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        summary = {
            "batch_id": output_path.stem,
            "run_time": datetime.now().isoformat(),
            "total_cases": len(self.results),
            "win_count": sum(1 for r in self.results if r["outcome"] == "WIN"),
            "loss_count": sum(1 for r in self.results if r["outcome"] == "LOSS"),
            "win_rate": round(
                sum(1 for r in self.results if r["outcome"] == "WIN") / len(self.results) * 100, 1
            ) if self.results else 0,
            "avg_pnl_pct": round(
                sum(r["actual_pnl_pct"] for r in self.results) / len(self.results), 2
            ) if self.results else 0,
            "results": self.results,
        }
        output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return output_path


# ──────────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="历史机会回测")
    parser.add_argument(
        "--group",
        choices=["all", "m11", "wins", "losses"],
        default="all",
        help="案例组别",
    )
    parser.add_argument(
        "--m11-sim",
        action="store_true",
        help="对每条机会运行 M11 Agent 模拟",
    )
    parser.add_argument("--save", action="store_true", help="保存结果到文件")
    args = parser.parse_args()

    # 选案例
    all_opps = get_seed_opportunities()
    if args.group == "m11":
        opps = [o for o in all_opps if "m11_calibrated" in o.get("signal_tags", [])]
        print(f"[M11校准事件组] {len(opps)} 个案例")
    elif args.group == "wins":
        opps = [o for o in all_opps if o["outcome"] == "WIN"]
    elif args.group == "losses":
        opps = [o for o in all_opps if o["outcome"] == "LOSS"]
    else:
        opps = all_opps

    # 运行
    bt = HistoricalOpportunityBacktest(opps, run_m11=args.m11_sim)
    bt.run()

    # 报告
    report = bt.report()
    print(report)

    # 保存
    if args.save:
        path = bt.save()
        print(f"\n结果已保存: {path}")

    return bt


if __name__ == "__main__":
    main()
