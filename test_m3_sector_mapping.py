"""
测试M3的板块→股票代码映射功能
"""

import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from core.schemas import MarketSignal, SignalType, Direction, Market, TimeHorizon, SourceType, SignalLogicFrame
from m3_judgment.judgment_engine import JudgmentEngine
from core.llm_client import LLMClient


def create_test_signal():
    """创建一个测试信号：涉及新能源板块"""
    return MarketSignal(
        signal_id="test_signal_001",
        signal_type=SignalType.POLICY,
        signal_label="中沙签署新能源合作备忘录",
        description="中国与沙特阿拉伯签署新能源领域合作备忘录，涉及光伏、储能等多个领域的技术合作和项目投资",
        evidence_text="据新华社报道，中沙两国在能源领域达成多项合作协议...",
        signal_direction=Direction.BULLISH,
        affected_markets=[Market.A_SHARE],
        affected_instruments=["新能源", "光伏", "储能"],  # 板块名称，不是股票代码
        event_time=datetime.now(),
        collected_time=datetime.now(),
        time_horizon=TimeHorizon.MEDIUM,
        intensity_score=8,
        confidence_score=9,
        timeliness_score=9,
        source_type=SourceType.NEWS,
        source_ref="新华社",
        logic_frame=SignalLogicFrame(
            what_changed="中沙签署新能源合作备忘录",
            change_direction=Direction.BULLISH,
            affects=["新能源产业链", "光伏企业", "储能企业"]
        ),
        tags=["sector:新能源", "sector:光伏", "sector:储能"],
        metadata={}
    )


def main():
    print("=" * 60)
    print("测试M3的板块→股票代码映射功能")
    print("=" * 60)

    # 1. 创建测试信号
    print("\n[1] 创建测试信号...")
    signal = create_test_signal()
    print(f"   信号标签: {signal.signal_label}")
    print(f"   affected_instruments: {signal.affected_instruments}")
    print("   [!] 注意：这些是板块名称，不是股票代码")

    # 2. 初始化M3判断引擎
    print("\n[2] 初始化M3判断引擎...")
    llm_client = LLMClient()
    engine = JudgmentEngine(llm_client=llm_client)
    print("   [OK] M3引擎已初始化（包含板块知识库）")

    # 3. 测试板块知识库
    print("\n[3] 测试板块知识库...")
    sectors = engine.sector_knowledge.extract_sectors_from_signals([signal])
    print(f"   提取的板块: {sectors}")

    sector_info = engine.sector_knowledge.get_leading_stocks(sectors, top_n=3)
    print("   板块对应的龙头股:")
    for sector, stocks in sector_info.items():
        print(f"     {sector}:")
        for stock in stocks:
            print(f"       - {stock['name']}({stock['code']})")

    # 4. 执行M3判断
    print("\n[4] 执行M3判断...")
    print("   调用LLM进行机会判断（这会消耗API调用）...")

    try:
        opportunities = engine.judge(signals=[signal])

        if not opportunities:
            print("   [!] M3判断：不构成机会")
        else:
            print(f"   [OK] M3识别出 {len(opportunities)} 个机会")

            for i, opp in enumerate(opportunities, 1):
                print(f"\n   === 机会 {i} ===")
                print(f"   标题: {opp.opportunity_title}")
                print(f"   target_instruments: {opp.target_instruments}")
                print(f"   优先级: {opp.priority_level}")
                print(f"   综合评分: {opp.opportunity_score.overall_score:.1f}/10")
                print(f"   置信度: {opp.opportunity_score.confidence_score:.2f}")

                # 检查target_instruments是否是股票代码
                print("\n   [验证] 检查target_instruments格式:")
                for inst in opp.target_instruments:
                    is_stock_code = engine.sector_knowledge.is_stock_code(inst)
                    status = "[OK]" if is_stock_code else "[X]"
                    print(f"     {status} {inst} - {'股票代码' if is_stock_code else '非股票代码（板块/ETF名称）'}")

                # 检查优先级
                print(f"\n   [验证] 优先级是否达到position:")
                if opp.priority_level == "position":
                    print("     [OK] 优先级为position，可以执行交易")
                elif opp.priority_level == "research":
                    print("     [!] 优先级为research，需要进一步研究")
                    print(f"     原因: overall_score={opp.opportunity_score.overall_score:.1f} (需要>=8)")
                    print(f"           confidence={opp.opportunity_score.confidence_score:.2f} (需要>=0.8)")
                else:
                    print(f"     [!] 优先级为{opp.priority_level}")

    except Exception as e:
        print(f"   [ERROR] M3判断失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
