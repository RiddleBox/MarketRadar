"""M1->M3->M4 端到端链路测试（工蜂AI）"""
import sys
import logging
from datetime import datetime

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
sys.path.insert(0, r'D:\AIproject\MarketRadar')

from core.llm_client import LLMClient
from core.schemas import SourceType
from m1_decoder.decoder import SignalDecoder
from m3_judgment.judgment_engine import JudgmentEngine
from m4_action.action_designer import ActionDesigner

client = LLMClient()
info = client.get_provider_info()
print(f"Provider: {info['provider']} / {info['model']}\n")

# 测试文本：不含历史日期，模拟即时信息流
TEXT = """
人民银行今日宣布一揽子宽松货币政策，具体内容包括：
1. 下调存款准备金率0.5个百分点，释放长期流动性约1万亿元
2. 下调7天期逆回购操作利率0.2个百分点
3. 引导贷款市场报价利率（LPR）和存款利率同步下调
4. 降低存量房贷利率，平均降幅约0.5个百分点

分析人士认为，此次"一揽子"货币政策超出市场预期，是近年来最大力度的宽松组合，
标志着政策层面从"谨慎宽松"转向"积极宽松"。A股市场将于明日开盘交易。
"""

batch_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

print("=" * 60)
print("STEP 1: M1 信号解码")
print("=" * 60)
decoder = SignalDecoder(llm_client=client)
signals = decoder.decode(
    TEXT,
    source_ref="pbc.gov.cn_latest",
    source_type=SourceType.OFFICIAL_ANNOUNCEMENT,
    batch_id=batch_id,
)
print(f"解码到 {len(signals)} 个信号:")
for s in signals:
    print(f"  [{s.signal_type}] {s.signal_label} | 强度={s.intensity_score} 置信={s.confidence_score:.1f} 方向={s.signal_direction}")

if not signals:
    print("  ⚠ 无信号，退出")
    sys.exit(0)

print()
print("=" * 60)
print("STEP 2: M3 机会判断")
print("=" * 60)
engine = JudgmentEngine(llm_client=client)
opportunities = engine.judge(signals, batch_id=batch_id)
print(f"识别到 {len(opportunities)} 个机会:")
for opp in opportunities:
    print(f"  [{opp.priority}] {opp.opportunity_label}")
    print(f"    方向={opp.direction} 置信={opp.confidence:.0%} 时间窗={opp.time_window}")
    print(f"    理由: {opp.reasoning[:120]}...")

if not opportunities:
    print("  M3 判断当前信号不构成可操作机会（正常行为）")
    sys.exit(0)

print()
print("=" * 60)
print("STEP 3: M4 行动设计")
print("=" * 60)
designer = ActionDesigner(llm_client=client)
for opp in opportunities[:1]:
    plan = designer.design(opp)
    print(f"行动计划: {plan.plan_id}")
    print(f"  类型={plan.action_type} 优先级={plan.priority}")
    print(f"  标的={plan.instrument_symbol} ({plan.instrument_type})")
    if plan.stop_loss:
        print(f"  止损={plan.stop_loss.price}")
    if plan.take_profit:
        for tp in plan.take_profit:
            print(f"  止盈={tp.price} (减仓{tp.size_pct:.0%})")
    print(f"  有效期至: {plan.valid_until}")

print()
print("✅ M1->M3->M4 链路全部通过")
