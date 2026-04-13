import os, sys, time
os.environ["DEEPSEEK_API_KEY"] = "sk-6c899392de5444369b4518e8c64aa940"
sys.path.insert(0, r"D:\AIproject\MarketRadar")

from core.llm_client import LLMClient
from core.schemas import SourceType, Market, Direction, SignalType, TimeHorizon
from m1_decoder.decoder import SignalDecoder
from m3_judgment.judgment_engine import JudgmentEngine
from m4_action.action_designer import ActionDesigner

TEST_NEWS = """
【财联社2026年4月13日讯】中国人民银行今日发布公告，决定将7天期逆回购操作利率由此前的1.80%
下调至1.55%，降幅25个基点，为2023年以来首次单次降息幅度超过20bp。

与此同时，沪深港通北向资金当日净流入达到168.7亿元人民币，为近三个月单日最大净流入规模。
其中沪股通净流入102.3亿元，深股通净流入66.4亿元。金融、消费、新能源板块获得主力资金净买入。

Wind数据显示，截至收盘，上证综指上涨2.13%，收于3412点；深证成指涨2.67%；
创业板指涨3.12%，成交额较上个交易日放量41%。

分析人士指出，此次降息力度超出市场预期，叠加北向资金大幅回流，短期内A股有望维持强势格局。
但也需关注后续经济数据是否能配合，若4月PMI数据不及预期，可能对涨幅形成压制。
"""

client = LLMClient()

# ── Step 1: M1 解码（复用上次结果）
print("=== Step 1: M1 解码 ===")
decoder = SignalDecoder(llm_client=client)
t0 = time.time()
signals = decoder.decode(
    raw_text=TEST_NEWS,
    source_ref="smoke_news_001",
    source_type=SourceType.NEWS,
    batch_id="smoke_batch_m3_001",
)
print(f"M1: {len(signals)} signals ({time.time()-t0:.1f}s)")
for s in signals:
    print(f"  [{s.signal_type.value}] {s.signal_label} | {s.signal_direction.value} | 强:{s.intensity_score} 信:{s.confidence_score}")

# ── Step 2: M3 判断
print("\n=== Step 2: M3 机会判断 ===")
engine = JudgmentEngine(llm_client=client)
t1 = time.time()
opportunities = engine.judge(
    signals=signals,
    historical_signals=None,
    batch_id="smoke_batch_m3_001",
)
print(f"M3: {len(opportunities)} opportunities ({time.time()-t1:.1f}s)")

if not opportunities:
    print("  → 未发现机会（合法输出）")
else:
    for i, opp in enumerate(opportunities, 1):
        markets = "/".join([m.value for m in opp.target_markets])
        print(f"\n[{i}] [{opp.priority_level.value.upper()}] {opp.opportunity_title}")
        print(f"     市场: {markets} | 方向: {opp.trade_direction.value}")
        print(f"     论点: {opp.opportunity_thesis}")
        print(f"     为什么是现在: {opp.why_now}")
        print(f"     关键假设: {opp.key_assumptions}")
        print(f"     反向证据: {opp.counter_evidence}")
        print(f"     不确定性: {opp.uncertainty_map}")
        print(f"     风险回报: {opp.risk_reward_profile}")

    # ── Step 3: M4 行动设计
    print("\n=== Step 3: M4 行动设计 ===")
    designer = ActionDesigner(llm_client=client)
    for opp in opportunities:
        t2 = time.time()
        plan = designer.design(opp)
        print(f"\n[{opp.priority_level.value.upper()}] {opp.opportunity_title}")
        print(f"  标的: {plan.primary_instruments} | 仓位: {plan.position_sizing.suggested_allocation}")
        print(f"  止损: 类型={plan.stop_loss.stop_loss_type} 值={plan.stop_loss.stop_loss_value}% | {plan.stop_loss.notes}")
        print(f"  止盈: 类型={plan.take_profit.take_profit_type} 值={plan.take_profit.take_profit_value}% | {plan.take_profit.notes}")
        print(f"  仓位: {plan.position_sizing.suggested_allocation}（上限 {plan.position_sizing.max_allocation}）")
        print(f"  行动阶段:")
        for ph in plan.phases:
            print(f"    [{ph.phase_name}] {ph.timing_description} (仓位比例 {ph.allocation_ratio*100:.0f}%)")
        print(f"  有效期至: {plan.valid_until.strftime('%Y-%m-%d')} | M4耗时: {time.time()-t2:.1f}s")

print(f"\n=== 全流程完成 ===")
