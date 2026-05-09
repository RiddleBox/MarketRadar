"""
端到端测试：模拟信号 → M1 → M2 → M3 → M4 → M9
验证整个流程是否打通
"""
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from core.schemas import Market, SourceType, Direction
from core.llm_client import LLMClient
from m1_decoder.decoder import SignalDecoder
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine
from m4_action.action_designer import ActionDesigner
from m9_paper_trader.paper_trader import PaperTrader

print("=" * 60)
print("端到端测试：信号 → 机会 → 行动 → 持仓")
print("=" * 60)

# 模拟新闻文本 - 设计为高确定性、高时效性的重大利好
test_news = """
【财联社】隆基绿能发布重大利好公告 - 百亿美元订单+技术突破

隆基绿能（601012.SH）今日发布公告，公司与沙特阿拉伯签署100亿美元光伏组件订单，
这是公司历史上最大的单笔订单，也是全球光伏行业有史以来最大的单笔订单。
订单将在未来3年内交付，预计将为公司带来超过15亿美元的净利润，相当于公司去年全年净利润的3倍。

同时，公司宣布新一代BC电池技术取得重大突破，转换效率达到26.5%，领先行业平均水平2个百分点，
打破了此前由日本企业保持的世界纪录。该技术已通过第三方认证，将在今年Q3开始量产，
预计将进一步巩固公司在光伏行业的全球龙头地位。

受此消息影响，隆基绿能股价盘中一度涨停，成交量放大至平时的8倍，换手率达到15%。
多家券商紧急上调评级至"买入"，目标价从28元上调至40元，上调幅度超过40%。
分析师普遍认为，这一订单将显著改善公司未来3年的业绩预期，公司估值有望重估。

行业方面，国家能源局刚刚发布《2026年光伏产业发展规划》，明确提出今年新增装机目标200GW，
同比增长50%，政策支持力度空前。隆基绿能作为行业龙头，将直接受益于行业高景气度。
"""

# Step 1: M1解码
print("\n[Step 1] M1解码...")
llm_client = LLMClient()
decoder = SignalDecoder(llm_client=llm_client)

signals = decoder.decode(
    raw_text=test_news,
    source_ref="test_e2e",
    source_type=SourceType.NEWS,
    batch_id="test_e2e_001"
)

print(f"[OK] 解码出 {len(signals)} 个信号")
for sig in signals:
    print(f"  - {sig.signal_label} | {sig.signal_direction} | 强度:{sig.intensity_score}")

# Step 2: M2存储
print("\n[Step 2] M2存储...")
store = SignalStore()
store.save(signals)
print(f"[OK] 保存 {len(signals)} 个信号到数据库")

# Step 3: M3判断
print("\n[Step 3] M3判断...")
engine = JudgmentEngine(llm_client=llm_client)
opportunities = engine.judge(signals=signals, batch_id="test_e2e_001")

print(f"[OK] 生成 {len(opportunities)} 个机会")
for opp in opportunities:
    score = opp.opportunity_score
    print(f"  - {opp.opportunity_title}")
    print(f"    优先级: {opp.priority_level}")
    print(f"    评分: {score.overall_score:.1f}/10")
    print(f"    置信度: {score.confidence_score:.2f}")
    print(f"    标的: {opp.target_instruments[:3]}")

# Step 4: M4行动设计
print("\n[Step 4] M4行动设计...")
designer = ActionDesigner(llm_client=llm_client)

action_plans = []
for opp in opportunities:
    plan = designer.design(opp)
    action_plans.append(plan)
    print(f"[OK] 生成行动计划: {plan.plan_id}")
    print(f"  - 止损: {plan.stop_loss.stop_loss_value}%")
    print(f"  - 止盈: {plan.take_profit.take_profit_value}%")
    print(f"  - 仓位: {plan.position_sizing.suggested_allocation}")

# Step 5: M9模拟交易（自动执行）
print("\n[Step 5] M9模拟交易...")
trader = PaperTrader()

# 检查是否应该开仓
for i, (opp, plan) in enumerate(zip(opportunities, action_plans)):
    print(f"\n机会 {i+1}: {opp.opportunity_title}")
    print(f"  优先级: {opp.priority_level}")
    print(f"  评分: {opp.opportunity_score.overall_score:.1f}/10")
    print(f"  置信度: {opp.opportunity_score.confidence_score:.2f}")

    # 只有position和urgent级别才开仓
    if opp.priority_level.value in ['position', 'urgent']:
        print(f"  -> 应该开仓")

        # 获取第一个标的
        if opp.target_instruments:
            instrument = opp.target_instruments[0]
            print(f"  -> 标的: {instrument}")
            print(f"  -> 方向: {opp.trade_direction}")
            print(f"  -> 建议仓位: {plan.position_sizing.suggested_allocation}")

            # 尝试获取实时价格并开仓
            try:
                from m9_paper_trader.feed_factory import get_factory
                factory = get_factory()
                feed = factory.get_feed(Market.A_SHARE)
                current_price = feed.get_current_price(instrument)

                if current_price:
                    position = trader.open_from_plan(
                        action_plan=plan,
                        entry_price=current_price,
                        notes=f"Test E2E: {opp.opportunity_title}"
                    )
                    print(f"  [OK] 开仓成功: {position.position_id}")
                    print(f"      入场价: {current_price}")
                    print(f"      止损价: {position.stop_loss_price}")
                    print(f"      止盈价: {position.take_profit_price}")
                else:
                    print(f"  [!] 无法获取实时价格")
            except Exception as e:
                print(f"  [X] 开仓失败: {e}")
        else:
            print(f"  [X] 没有具体标的")
    else:
        print(f"  -> 优先级不足，不开仓（{opp.priority_level}）")

# 检查当前持仓
print("\n[当前持仓]")
open_positions = trader.list_open()
print(f"持仓数量: {len(open_positions)}")
for pos in open_positions:
    print(f"  - {pos.instrument} | {pos.direction} | 入场价:{pos.entry_price}")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)
