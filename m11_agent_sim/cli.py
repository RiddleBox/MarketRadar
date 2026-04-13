"""
m11_agent_sim/cli.py — M11 命令行接口

用法：
    python -m m11_agent_sim.cli run --event "央行降准50bp" --fg 35 --northbound 120
    python -m m11_agent_sim.cli backtest
    python -m m11_agent_sim.cli calibrate
    python -m m11_agent_sim.cli graph-demo   # 演示图结构模式
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def cmd_run(args):
    """单次情绪模拟预测"""
    from m11_agent_sim.agent_network import AgentNetwork
    from m11_agent_sim.schemas import (
        MarketInput, PriceContext, SentimentContext, SignalContext
    )

    market_input = MarketInput(
        timestamp=datetime.now(),
        market=args.market.upper(),
        event_description=args.event or "",
        sentiment=SentimentContext(
            fear_greed_index=args.fg,
            sentiment_label=_fg_label(args.fg),
            northbound_flow=args.northbound,
            advance_decline_ratio=args.adr,
            weibo_sentiment=args.weibo,
        ),
        signals=SignalContext(
            bullish_count=args.bull_signals,
            bearish_count=args.bear_signals,
            avg_intensity=args.intensity,
            avg_confidence=7.0,
            dominant_signal_type="macro" if args.intensity > 6 else "market_data",
        ),
        price=PriceContext(
            price_5d_chg_pct=args.ret5 / 100,
            price_20d_chg_pct=args.ret20 / 100,
            above_ma5=args.ret5 > 0,
            above_ma20=args.ret20 > 0,
        ),
    )

    topology = "graph" if args.graph else "sequential"
    net = AgentNetwork.from_config_file(
        market=args.market.lower(),
        topology=topology,
        use_llm=args.llm,
    )

    print(f"\n{'='*60}")
    print(f"M11 市场情绪模拟 — {market_input.market} ({topology})")
    print(f"事件：{args.event or '（无特定事件）'}")
    print(f"{'='*60}")

    dist = net.run(market_input)

    # 结果展示
    dir_emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "⚪"}
    print(f"\n{'─'*40}")
    print(f"综合方向：{dir_emoji.get(dist.direction,'')} {dist.direction}")
    print(f"多方概率：{dist.bullish_prob:.1%}  空方概率：{dist.bearish_prob:.1%}  震荡：{dist.neutral_prob:.1%}")
    print(f"95% CI：多方 [{dist.bullish_prob_ci_low:.1%}, {dist.bullish_prob_ci_high:.1%}]")
    print(f"情绪强度：{dist.intensity:.1f}/10  置信度：{dist.confidence:.0%}")
    print(f"耗时：{dist.simulation_ms}ms")
    print(f"\n{'─'*40}")
    print("各 Agent 明细：")
    for out in dist.agent_outputs:
        emoji = dir_emoji.get(out.direction, "")
        print(
            f"  {out.agent_name:12s} {emoji} {out.direction:8s} "
            f"多{out.bullish_prob:.0%}/空{out.bearish_prob:.0%} "
            f"置信{out.confidence:.0%} | {out.reasoning[:40]}"
        )
    print()


def cmd_backtest(args):
    """历史事件回放"""
    from m11_agent_sim.calibrator import HistoricalCalibrator

    print(f"\n{'='*60}")
    print("M11 历史回放")
    print(f"{'='*60}\n")

    cal = HistoricalCalibrator(market=args.market.lower())
    events = cal.load_seed_events()
    if not events:
        print("❌ 无历史事件可回放")
        return

    print(f"加载 {len(events)} 个历史事件\n")

    for event in events:
        dist = cal.network.run(event.market_input)
        hit = dist.direction == event.actual_direction
        mark = "✓" if hit else "✗"
        dir_map = {"BULLISH": "多", "BEARISH": "空", "NEUTRAL": "震"}
        print(
            f"  {event.date} {mark} "
            f"实际:{dir_map.get(event.actual_direction,'?')}({event.actual_5d_return:+.1%}) | "
            f"模拟:{dir_map.get(dist.direction,'?')}(多{dist.bullish_prob:.0%}) | "
            f"{event.description[:35]}"
        )


def cmd_calibrate(args):
    """运行校准报告"""
    from m11_agent_sim.calibrator import HistoricalCalibrator

    print(f"\n{'='*60}")
    print("M11 历史校准报告")
    print(f"{'='*60}\n")

    cal = HistoricalCalibrator(market=args.market.lower())
    score = cal.calibrate()

    print(f"\n{'─'*40}")
    print(f"总事件数：{score.total_events}")
    print(f"方向命中率：{score.direction_accuracy:.0%}  (目标 ≥ 70%)")
    print(f"概率校准误差：{score.prob_calibration_err:.3f}  (目标 < 0.15)")
    print(f"极值识别召回：{score.extreme_recall:.0%}  (目标 ≥ 60%)")
    print(f"综合得分：{score.composite_score:.1f}/100")
    print(f"校准结论：{'✅ 通过' if score.pass_threshold else '❌ 未通过（需调整 Agent 参数）'}")

    if args.detail:
        print(f"\n{'─'*40}")
        print("逐事件明细：")
        for d in score.details:
            mark = "✓" if d["hit"] else "✗"
            print(
                f"  {d['date']} {mark} "
                f"实际:{d['actual']:8s} 模拟:{d['simulated']:8s} "
                f"多概率:{d['bullish_prob']:.0%} "
                f"误差:{d['prob_error']:.2f} | "
                f"{d['description'][:35]}"
            )


def cmd_graph_demo(args):
    """演示图结构模式（Phase 2 骨架）"""
    from m11_agent_sim.agent_network import AgentNetwork
    from m11_agent_sim.schemas import (
        MarketInput, SentimentContext, SignalContext
    )

    print(f"\n{'='*60}")
    print("M11 图结构模式演示（Phase 2 骨架）")
    print(f"{'='*60}\n")

    market_input = MarketInput(
        event_description="2024-09-24 央行降准50bp，政策强刺激",
        sentiment=SentimentContext(
            fear_greed_index=35.0, northbound_flow=120.0,
            advance_decline_ratio=0.72, weibo_sentiment=0.2,
        ),
        signals=SignalContext(
            bullish_count=3, bearish_count=0, avg_intensity=9.5,
            dominant_signal_type="policy_document",
        ),
    )

    print("[ 序列传导模式 ]")
    net_seq = AgentNetwork.from_config_file(topology="sequential")
    dist_seq = net_seq.run(market_input)
    print(f"  {dist_seq.summary()}")

    print("\n[ 图结构模式（经验权重）]")
    net_graph = AgentNetwork.from_config_file(topology="graph")
    dist_graph = net_graph.run(market_input)
    print(f"  {dist_graph.summary()}")

    print(f"\n差异 | 多方概率: {abs(dist_seq.bullish_prob - dist_graph.bullish_prob):.1%}")


def _fg_label(fg: float) -> str:
    if fg >= 80: return "极度贪婪"
    if fg >= 60: return "贪婪"
    if fg >= 40: return "中性"
    if fg >= 20: return "恐惧"
    return "极度恐惧"


def main():
    parser = argparse.ArgumentParser(description="M11 多Agent市场情绪模拟")
    sub = parser.add_subparsers(dest="cmd")

    # run
    p_run = sub.add_parser("run", help="单次情绪模拟")
    p_run.add_argument("--event", default="", help="事件描述")
    p_run.add_argument("--market", default="a_share", help="市场 (a_share/hk)")
    p_run.add_argument("--fg", type=float, default=50.0, help="恐贪指数 0~100")
    p_run.add_argument("--northbound", type=float, default=0.0, help="北向资金净流入（亿）")
    p_run.add_argument("--adr", type=float, default=0.5, help="涨跌比 0~1")
    p_run.add_argument("--weibo", type=float, default=0.0, help="微博情绪 -1~1")
    p_run.add_argument("--bull-signals", type=int, default=0, dest="bull_signals")
    p_run.add_argument("--bear-signals", type=int, default=0, dest="bear_signals")
    p_run.add_argument("--intensity", type=float, default=5.0)
    p_run.add_argument("--ret5", type=float, default=0.0, help="5日涨跌幅 %")
    p_run.add_argument("--ret20", type=float, default=0.0, help="20日涨跌幅 %")
    p_run.add_argument("--graph", action="store_true", help="使用图结构模式")
    p_run.add_argument("--llm", action="store_true", help="使用 LLM 分析（需配置 LLMClient）")

    # backtest
    p_bt = sub.add_parser("backtest", help="历史事件回放")
    p_bt.add_argument("--market", default="a_share")

    # calibrate
    p_cal = sub.add_parser("calibrate", help="校准报告")
    p_cal.add_argument("--market", default="a_share")
    p_cal.add_argument("--detail", action="store_true", help="显示逐事件明细")

    # graph-demo
    p_gd = sub.add_parser("graph-demo", help="图结构模式演示")

    args = parser.parse_args()

    if args.cmd == "run":
        cmd_run(args)
    elif args.cmd == "backtest":
        cmd_backtest(args)
    elif args.cmd == "calibrate":
        cmd_calibrate(args)
    elif args.cmd == "graph-demo":
        cmd_graph_demo(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
