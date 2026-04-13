import os
import sys
from datetime import datetime

sys.path.insert(0, r'D:\AIproject\MarketRadar')
os.environ['DEEPSEEK_API_KEY'] = 'sk-6c899392de5444369b4518e8c64aa940'

from core.llm_client import LLMClient
from core.schemas import SourceType
from m1_decoder.decoder import SignalDecoder
from m3_judgment.judgment_engine import JudgmentEngine
from m4_action.action_designer import ActionDesigner

client = LLMClient()
client._config['default_provider'] = 'deepseek'

info = client.get_provider_info('m1_decoder')
print(f"Provider: {info['provider']} / {info['model']}\n")

TEXT = """
人民银行今日宣布一揽子宽松货币政策，具体内容包括：
1. 下调存款准备金率0.5个百分点，释放长期流动性约1万亿元
2. 下调7天期逆回购操作利率0.2个百分点
3. 引导贷款市场报价利率（LPR）和存款利率同步下调
4. 降低存量房贷利率，平均降幅约0.5个百分点

分析人士认为，此次\"一揽子\"货币政策超出市场预期，是近年来最大力度的宽松组合，
标志着政策层面从\"谨慎宽松\"转向\"积极宽松\"。A股市场将于明日开盘交易。
"""

batch_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

print('=' * 60)
print('STEP 1: M1 信号解码')
print('=' * 60)
decoder = SignalDecoder(llm_client=client)
signals = decoder.decode(
    TEXT,
    source_ref='pbc.gov.cn_latest',
    source_type=SourceType.OFFICIAL_ANNOUNCEMENT,
    batch_id=batch_id,
)
print(f"解码到 {len(signals)} 个信号:")
for s in signals:
    print(f"  [{s.signal_type}] {s.signal_label} | 强度={s.intensity_score} 置信={s.confidence_score:.1f} 方向={s.signal_direction}")

if not signals:
    print('  ⚠ 无信号，退出')
    raise SystemExit(0)

print()
print('=' * 60)
print('STEP 2: M3 机会判断')
print('=' * 60)
engine = JudgmentEngine(llm_client=client)
opportunities = engine.judge(signals, batch_id=batch_id)
print(f"识别到 {len(opportunities)} 个机会:")
for opp in opportunities:
    print(f"  [{opp.priority_level.value}] {opp.opportunity_title}")
    print(f"    方向={opp.trade_direction.value} 时间窗={opp.opportunity_window.start} -> {opp.opportunity_window.end}")
    print(f"    评分: overall={opp.opportunity_score.overall_score} confidence={opp.opportunity_score.confidence_score} execution={opp.opportunity_score.execution_readiness}")
    print(f"    失效条件: {opp.invalidation_conditions[:2]}")
    print(f"    Kill switch: {opp.kill_switch_signals[:2]}")
    print(f"    理由: {opp.opportunity_thesis[:120]}...")

if not opportunities:
    print('  M3 判断当前信号不构成可操作机会（正常行为）')
    raise SystemExit(0)

print()
print('=' * 60)
print('STEP 3: M4 行动设计')
print('=' * 60)
designer = ActionDesigner(llm_client=client)
for opp in opportunities[:1]:
    plan = designer.design(opp)
    print(f"行动计划: {plan.opportunity_id}")
    print(f"  概要={plan.plan_summary} 优先级={plan.opportunity_priority.value}")
    print(f"  标的={', '.join(plan.primary_instruments)} ({plan.instrument_type.value})")
    print(f"  止损={plan.stop_loss.stop_loss_type}:{plan.stop_loss.stop_loss_value}")
    print(f"  止盈={plan.take_profit.take_profit_type}:{plan.take_profit.take_profit_value}")
    print(f"  阶段数={len(plan.phases)} 有效期至: {plan.valid_until}")

print()
print('✅ M1->M3->M4 链路全部通过')
