"""
backtest/seed_opportunities.py — 历史机会种子数据（带 ground truth）

20 个精选历史机会，覆盖 A股 2018~2025 典型行情节点。
每条记录包含：
  - opportunity_id / title / thesis
  - signal_date: 信号出现日（进场参考日）
  - instrument: 回测标的（代码）
  - direction: BULLISH / BEARISH
  - entry_price: 进场参考价（signal_date 收盘）
  - exit_price: 结算参考价（holding_days 后收盘）
  - holding_days: 持有天数
  - actual_pnl_pct: 实际盈亏%（ground truth）
  - outcome: WIN / LOSS / NEUTRAL
  - event_type: macro / policy / industry / capital_flow / technical
  - notes: 事件背景说明

数据来源：
  - 510300.SH 价格参考 AKShare 历史复权数据
  - 其余标的为近似估算（用于验证信号质量分层逻辑）
  - 关键节点（2024-09-24 / 2024-10-08）数据已在 seed_data.py 精确校验

⚠️ 仅用于回测框架功能验证，不构成投资建议。
"""
from __future__ import annotations
from typing import Literal

# ──────────────────────────────────────────────────────────────────
# 数据结构 TypedDict（Python 3.14 兼容）
# ──────────────────────────────────────────────────────────────────
SEED_OPPORTUNITIES: list[dict] = [

    # ════════════════════════════════════════════════════════════════
    # GROUP 1: M11 内置校准事件（最高可信度，seed_data.py 价格精确）
    # ════════════════════════════════════════════════════════════════

    {
        "opportunity_id": "hist_001",
        "opportunity_title": "2024-09-24 央行超预期降准降息",
        "signal_date": "2024-09-24",
        "instrument": "510300.SH",
        "direction": "BULLISH",
        "event_type": "macro",
        "intensity_score": 10,
        "entry_price": 3.545,   # 2024-09-24 收盘（seed_data.py 数据）
        "exit_price": 4.122,    # 2024-09-30 收盘（+5日）
        "holding_days": 5,
        "actual_pnl_pct": 16.28,
        "outcome": "WIN",
        "notes": "央行单次最大降息幅度+降准，政策×情绪双共振，5日涨幅16.3%，是系统最强信号案例",
        "signal_tags": ["policy_shock", "bullish_resonance", "m11_calibrated"],
    },
    {
        "opportunity_id": "hist_002",
        "opportunity_title": "2024-10-08 国庆高开低走",
        "signal_date": "2024-10-08",
        "instrument": "510300.SH",
        "direction": "BEARISH",
        "event_type": "technical",
        "intensity_score": 8,
        "entry_price": 4.185,   # 高开后收盘
        "exit_price": 3.892,    # 2024-10-14 收盘（+5日）
        "holding_days": 5,
        "actual_pnl_pct": -7.00,
        "outcome": "WIN",       # 做空方向正确
        "notes": "国庆后开盘高开21%后冲高回落，5日均回调7%，FG极端贪婪+技术背离，利好出尽",
        "signal_tags": ["bearish_resonance", "policy_panic", "m11_calibrated"],
    },
    {
        "opportunity_id": "hist_003",
        "opportunity_title": "2025-02-17 DeepSeek科技浪潮",
        "signal_date": "2025-02-17",
        "instrument": "588000.SH",  # 科创50 ETF
        "direction": "BULLISH",
        "event_type": "industry",
        "intensity_score": 9,
        "entry_price": 0.882,   # 近似估算
        "exit_price": 1.025,
        "holding_days": 15,
        "actual_pnl_pct": 16.21,
        "outcome": "WIN",
        "notes": "DeepSeek R1 发布引发AI+科技板块持续大涨，科创50连续强势，政策+产业催化双共振",
        "signal_tags": ["industry_catalyst", "ai_theme", "m11_calibrated"],
    },
    {
        "opportunity_id": "hist_004",
        "opportunity_title": "2025-04-07 关税冲击暴跌",
        "signal_date": "2025-04-07",
        "instrument": "510300.SH",
        "direction": "BEARISH",
        "event_type": "macro",
        "intensity_score": 10,
        "entry_price": 3.558,   # 4月7日收盘（seed_data.py 数据）
        "exit_price": 3.285,    # 约+3日底部估算（极端下行）
        "holding_days": 3,
        "actual_pnl_pct": -7.67,
        "outcome": "WIN",       # 做空方向正确
        "notes": "特朗普对华加征145%关税，开盘跌停，FG极度恐惧，系统触发policy_panic信号",
        "signal_tags": ["policy_panic", "tariff_shock", "m11_calibrated"],
    },

    # ════════════════════════════════════════════════════════════════
    # GROUP 2: 2018 中美贸易战历史事件（A股熊市）
    # ════════════════════════════════════════════════════════════════

    {
        "opportunity_id": "hist_005",
        "opportunity_title": "2018-03-22 特朗普对华加征关税第一枪",
        "signal_date": "2018-03-22",
        "instrument": "510300.SH",
        "direction": "BEARISH",
        "event_type": "macro",
        "intensity_score": 9,
        "entry_price": 3.82,    # 近似估算
        "exit_price": 3.42,
        "holding_days": 15,
        "actual_pnl_pct": -10.47,
        "outcome": "WIN",
        "notes": "特朗普签署备忘录对华征税500亿美元，A股开始系统性下跌通道，贸易战第一阶段",
        "signal_tags": ["tariff_shock", "macro_bearish", "us_china_trade"],
    },
    {
        "opportunity_id": "hist_006",
        "opportunity_title": "2018-07-06 中美贸易战正式开打",
        "signal_date": "2018-07-06",
        "instrument": "510300.SH",
        "direction": "BEARISH",
        "event_type": "macro",
        "intensity_score": 10,
        "entry_price": 3.35,
        "exit_price": 2.98,
        "holding_days": 20,
        "actual_pnl_pct": -11.04,
        "outcome": "WIN",
        "notes": "500亿美元关税正式生效，中方同步反制，A股加速下跌，沪深300跌破3000点",
        "signal_tags": ["tariff_shock", "macro_bearish", "us_china_trade"],
    },
    {
        "opportunity_id": "hist_007",
        "opportunity_title": "2018-10-19 国家队护盘前低",
        "signal_date": "2018-10-19",
        "instrument": "510300.SH",
        "direction": "BULLISH",
        "event_type": "policy",
        "intensity_score": 8,
        "entry_price": 2.72,
        "exit_price": 2.98,
        "holding_days": 15,
        "actual_pnl_pct": 9.56,
        "outcome": "WIN",
        "notes": "证监会/财政部/央行/银保监会联合发声护盘，FG极度恐惧，出现政策底+情绪底共振",
        "signal_tags": ["policy_bottom", "bullish_resonance", "national_team"],
    },

    # ════════════════════════════════════════════════════════════════
    # GROUP 3: 2020 疫情冲击与修复
    # ════════════════════════════════════════════════════════════════

    {
        "opportunity_id": "hist_008",
        "opportunity_title": "2020-02-03 疫情冲击开盘暴跌",
        "signal_date": "2020-02-03",
        "instrument": "510300.SH",
        "direction": "BEARISH",
        "event_type": "macro",
        "intensity_score": 9,
        "entry_price": 3.52,
        "exit_price": 3.18,
        "holding_days": 5,
        "actual_pnl_pct": -9.66,
        "outcome": "WIN",
        "notes": "春节后首个交易日，疫情冲击跌停开盘，短线做空信号明确，央行同步降准托底",
        "signal_tags": ["event_driven", "covid_shock", "macro_bearish"],
    },
    {
        "opportunity_id": "hist_009",
        "opportunity_title": "2020-03-23 全球底部反弹",
        "signal_date": "2020-03-23",
        "instrument": "510300.SH",
        "direction": "BULLISH",
        "event_type": "technical",
        "intensity_score": 7,
        "entry_price": 3.22,
        "exit_price": 3.68,
        "holding_days": 20,
        "actual_pnl_pct": 14.29,
        "outcome": "WIN",
        "notes": "美联储无限QE，全球股市触底反弹，A股科技股领涨，FG极度恐惧后修复共振",
        "signal_tags": ["recovery_signal", "global_bottom", "fed_qe"],
    },
    {
        "opportunity_id": "hist_010",
        "opportunity_title": "2020-07-06 A股情绪过热",
        "signal_date": "2020-07-06",
        "instrument": "510300.SH",
        "direction": "BEARISH",
        "event_type": "technical",
        "intensity_score": 7,
        "entry_price": 4.52,
        "exit_price": 4.12,
        "holding_days": 10,
        "actual_pnl_pct": -8.85,
        "outcome": "WIN",
        "notes": "《人民日报》点评牛市，成交额连续破万亿，FG极度贪婪85+，历史上此类情绪过热均回调",
        "signal_tags": ["bearish_resonance", "sentiment_extreme", "media_hype"],
    },

    # ════════════════════════════════════════════════════════════════
    # GROUP 4: 2022 下跌与反弹
    # ════════════════════════════════════════════════════════════════

    {
        "opportunity_id": "hist_011",
        "opportunity_title": "2022-03-15 俄乌冲突+疫情双重压力底部",
        "signal_date": "2022-03-15",
        "instrument": "510300.SH",
        "direction": "BULLISH",
        "event_type": "policy",
        "intensity_score": 8,
        "entry_price": 3.68,
        "exit_price": 4.02,
        "holding_days": 20,
        "actual_pnl_pct": 9.24,
        "outcome": "WIN",
        "notes": "国常会定调稳市场，外资连续流出后止步，FG极度恐惧20，政策底确认",
        "signal_tags": ["policy_bottom", "bullish_resonance", "recovery_signal"],
    },
    {
        "opportunity_id": "hist_012",
        "opportunity_title": "2022-10-31 二十大后政策预期修复",
        "signal_date": "2022-10-31",
        "instrument": "510300.SH",
        "direction": "BULLISH",
        "event_type": "policy",
        "intensity_score": 8,
        "entry_price": 3.42,
        "exit_price": 3.85,
        "holding_days": 15,
        "actual_pnl_pct": 12.57,
        "outcome": "WIN",
        "notes": "二十大结束后市场预期修复，疫情管控边际放松预期+房地产救市预期，FG从恐惧区间反弹",
        "signal_tags": ["policy_bottom", "sentiment_recovery", "reopening"],
    },
    {
        "opportunity_id": "hist_013",
        "opportunity_title": "2022-12-05 防疫优化政策发布",
        "signal_date": "2022-12-05",
        "instrument": "510300.SH",
        "direction": "BULLISH",
        "event_type": "policy",
        "intensity_score": 9,
        "entry_price": 3.78,
        "exit_price": 4.12,
        "holding_days": 15,
        "actual_pnl_pct": 8.99,
        "outcome": "WIN",
        "notes": "国家公布优化防疫20条，北向资金大幅流入，港股+A股消费/医疗/出行板块暴涨",
        "signal_tags": ["policy_bullish", "recovery_signal", "northbound_inflow"],
    },

    # ════════════════════════════════════════════════════════════════
    # GROUP 5: 2023~2024 反弹与分化
    # ════════════════════════════════════════════════════════════════

    {
        "opportunity_id": "hist_014",
        "opportunity_title": "2023-01-05 外资大幅回流开门红",
        "signal_date": "2023-01-05",
        "instrument": "510300.SH",
        "direction": "BULLISH",
        "event_type": "capital_flow",
        "intensity_score": 8,
        "entry_price": 3.92,
        "exit_price": 4.38,
        "holding_days": 20,
        "actual_pnl_pct": 11.73,
        "outcome": "WIN",
        "notes": "疫情管控放开后外资强势回流，1月北向净买入超800亿，消费/金融领涨，A股强势开门红",
        "signal_tags": ["capital_flow", "northbound_inflow", "recovery_signal"],
    },
    {
        "opportunity_id": "hist_015",
        "opportunity_title": "2023-05-10 A股春季行情结束",
        "signal_date": "2023-05-10",
        "instrument": "510300.SH",
        "direction": "BEARISH",
        "event_type": "technical",
        "intensity_score": 6,
        "entry_price": 4.18,
        "exit_price": 3.82,
        "holding_days": 20,
        "actual_pnl_pct": -8.61,
        "outcome": "WIN",
        "notes": "PMI不及预期，北向资金持续流出，经济复苏预期落空，A股从高位开始回调",
        "signal_tags": ["macro_bearish", "northbound_outflow", "technical_breakdown"],
    },
    {
        "opportunity_id": "hist_016",
        "opportunity_title": "2024-02-06 春节前后极度恐惧底部",
        "signal_date": "2024-02-06",
        "instrument": "510300.SH",
        "direction": "BULLISH",
        "event_type": "policy",
        "intensity_score": 8,
        "entry_price": 2.98,
        "exit_price": 3.42,
        "holding_days": 20,
        "actual_pnl_pct": 14.77,
        "outcome": "WIN",
        "notes": "A股2024年初加速下跌，FG达到历史极值区间，证监会换帅+国家队护盘，触发政策底+情绪底共振",
        "signal_tags": ["policy_bottom", "bullish_resonance", "national_team"],
    },

    # ════════════════════════════════════════════════════════════════
    # GROUP 6: 失败案例（LOSS）——用于校验系统不会100%过拟合
    # ════════════════════════════════════════════════════════════════

    {
        "opportunity_id": "hist_017",
        "opportunity_title": "2019-04-08 科创板开板预期炒作（追高失败）",
        "signal_date": "2019-04-08",
        "instrument": "510300.SH",
        "direction": "BULLISH",
        "event_type": "policy",
        "intensity_score": 6,
        "entry_price": 3.88,
        "exit_price": 3.62,
        "holding_days": 10,
        "actual_pnl_pct": -6.70,
        "outcome": "LOSS",
        "notes": "科创板开板消息驱动短期上涨后，市场定价过于乐观，随后快速回调。追热点不等同于系统性信号",
        "signal_tags": ["policy_bullish", "false_breakout", "lesson"],
    },
    {
        "opportunity_id": "hist_018",
        "opportunity_title": "2021-02-19 白马股高估值崩塌",
        "signal_date": "2021-02-19",
        "instrument": "510300.SH",
        "direction": "BULLISH",
        "event_type": "technical",
        "intensity_score": 5,
        "entry_price": 5.62,
        "exit_price": 4.85,
        "holding_days": 15,
        "actual_pnl_pct": -13.70,
        "outcome": "LOSS",
        "notes": "抱团股估值极端，茅台/宁德/美的估值泡沫崩塌，FG贪婪区间追多被套，系统强度信号不足（5分）应保守",
        "signal_tags": ["valuation_bubble", "crowded_trade", "lesson"],
    },
    {
        "opportunity_id": "hist_019",
        "opportunity_title": "2024-11-12 特朗普再胜利好出尽",
        "signal_date": "2024-11-12",
        "instrument": "510300.SH",
        "direction": "BULLISH",
        "event_type": "macro",
        "intensity_score": 6,
        "entry_price": 3.98,
        "exit_price": 3.72,
        "holding_days": 10,
        "actual_pnl_pct": -6.53,
        "outcome": "LOSS",
        "notes": "特朗普胜选初期A股短暂上涨后快速下跌，市场担忧关税政策不确定性，利好出尽效应",
        "signal_tags": ["macro_uncertainty", "false_bullish", "lesson"],
    },

    # ════════════════════════════════════════════════════════════════
    # GROUP 7: 2025 最新行情节点
    # ════════════════════════════════════════════════════════════════

    {
        "opportunity_id": "hist_020",
        "opportunity_title": "2025-04-09 关税冲击后政策护盘反弹",
        "signal_date": "2025-04-09",
        "instrument": "510300.SH",
        "direction": "BULLISH",
        "event_type": "policy",
        "intensity_score": 8,
        "entry_price": 3.612,   # seed_data.py 数据
        "exit_price": 3.658,    # seed_data.py 2025-04-10 数据
        "holding_days": 1,
        "actual_pnl_pct": 1.27,
        "outcome": "WIN",
        "notes": "关税冲击后政策快速响应，央行表态支持，市场出现技术反弹，但持续性待验证",
        "signal_tags": ["recovery_signal", "policy_support", "tariff_rebound"],
    },
]


def get_seed_opportunities() -> list[dict]:
    """返回所有历史机会种子数据"""
    return SEED_OPPORTUNITIES


def get_by_outcome(outcome: Literal["WIN", "LOSS", "NEUTRAL"]) -> list[dict]:
    """按结果筛选"""
    return [o for o in SEED_OPPORTUNITIES if o["outcome"] == outcome]


def get_by_event_type(event_type: str) -> list[dict]:
    """按事件类型筛选"""
    return [o for o in SEED_OPPORTUNITIES if o["event_type"] == event_type]


def get_by_direction(direction: Literal["BULLISH", "BEARISH"]) -> list[dict]:
    """按方向筛选"""
    return [o for o in SEED_OPPORTUNITIES if o["direction"] == direction]


def get_statistics() -> dict:
    """汇总统计"""
    total = len(SEED_OPPORTUNITIES)
    wins = sum(1 for o in SEED_OPPORTUNITIES if o["outcome"] == "WIN")
    losses = sum(1 for o in SEED_OPPORTUNITIES if o["outcome"] == "LOSS")
    pnl_list = [o["actual_pnl_pct"] for o in SEED_OPPORTUNITIES]
    win_pnl = [o["actual_pnl_pct"] for o in SEED_OPPORTUNITIES if o["outcome"] == "WIN"]
    loss_pnl = [o["actual_pnl_pct"] for o in SEED_OPPORTUNITIES if o["outcome"] == "LOSS"]

    # 按强度分组
    high_intensity = [o for o in SEED_OPPORTUNITIES if o["intensity_score"] >= 8]
    hi_wins = sum(1 for o in high_intensity if o["outcome"] == "WIN")

    return {
        "total": total,
        "win_count": wins,
        "loss_count": losses,
        "win_rate": round(wins / total * 100, 1),
        "avg_pnl_pct": round(sum(pnl_list) / total, 2),
        "avg_win_pct": round(sum(win_pnl) / len(win_pnl), 2) if win_pnl else 0,
        "avg_loss_pct": round(sum(loss_pnl) / len(loss_pnl), 2) if loss_pnl else 0,
        "high_intensity_win_rate": round(hi_wins / len(high_intensity) * 100, 1) if high_intensity else 0,
        "by_direction": {
            "BULLISH": len(get_by_direction("BULLISH")),
            "BEARISH": len(get_by_direction("BEARISH")),
        },
        "by_event_type": {
            et: len(get_by_event_type(et))
            for et in ["macro", "policy", "industry", "capital_flow", "technical"]
        },
    }


if __name__ == "__main__":
    stats = get_statistics()
    print("=== 历史机会种子数据统计 ===")
    print(f"总案例: {stats['total']}")
    print(f"胜率: {stats['win_rate']}%  ({stats['win_count']}胜/{stats['loss_count']}败)")
    print(f"平均盈亏: {stats['avg_pnl_pct']:+.2f}%")
    print(f"平均盈利: {stats['avg_win_pct']:+.2f}% | 平均亏损: {stats['avg_loss_pct']:+.2f}%")
    print(f"高强度信号(≥8分)胜率: {stats['high_intensity_win_rate']}%")
    print(f"多空分布: {stats['by_direction']}")
    print(f"事件类型: {stats['by_event_type']}")
    print()
    print("M11校准事件（前4条）:")
    for o in get_seed_opportunities()[:4]:
        tag = "✓" if o["outcome"] == "WIN" else "✗"
        print(f"  {tag} [{o['signal_date']}] {o['opportunity_title'][:25]:<25} "
              f"{o['actual_pnl_pct']:+.2f}% ({o['holding_days']}日)")
