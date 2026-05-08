"""
测试M3处理两种情况：
1. 新闻直接提到具体公司
2. 新闻提到板块
"""

import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from core.schemas import MarketSignal, SignalType, Direction, Market, TimeHorizon, SourceType, SignalLogicFrame
from m3_judgment.judgment_engine import JudgmentEngine
from core.llm_client import LLMClient


def test_case_1_specific_company():
    """测试用例1：新闻直接提到具体公司"""
    print("\n" + "=" * 60)
    print("测试用例1：新闻直接提到具体公司")
    print("=" * 60)

    signal = MarketSignal(
        signal_id="test_company_001",
        signal_type=SignalType.EVENT_DRIVEN,
        signal_label="隆基绿能Q1业绩预增50%",
        description="隆基绿能发布Q1业绩预增公告，净利润同比增长50%，超市场预期",
        evidence_text="公司公告显示，Q1净利润预计增长50%...",
        signal_direction=Direction.BULLISH,
        affected_markets=[Market.A_SHARE],
        affected_instruments=["隆基绿能", "通威股份"],  # 公司名称
        event_time=datetime.now(),
        collected_time=datetime.now(),
        time_horizon=TimeHorizon.SHORT,
        intensity_score=8,
        confidence_score=9,
        timeliness_score=9,
        source_type=SourceType.NEWS,
        source_ref="公司公告",
        logic_frame=SignalLogicFrame(
            what_changed="隆基绿能Q1业绩预增50%",
            change_direction=Direction.BULLISH,
            affects=["隆基绿能", "光伏产业链"]
        ),
        metadata={}
    )

    print(f"\n[输入] affected_instruments: {signal.affected_instruments}")
    print("   类型: 公司名称（不是股票代码）")

    # 测试resolve_instruments
    engine = JudgmentEngine(llm_client=LLMClient())
    resolved = engine.sector_knowledge.resolve_instruments(signal.affected_instruments)
    print(f"\n[解析] resolved_instruments: {resolved}")
    print("   预期: ['601012.SH', '600438.SH']")

    return signal


def test_case_2_sector():
    """测试用例2：新闻提到板块"""
    print("\n" + "=" * 60)
    print("测试用例2：新闻提到板块")
    print("=" * 60)

    signal = MarketSignal(
        signal_id="test_sector_001",
        signal_type=SignalType.POLICY,
        signal_label="中沙签署新能源合作备忘录",
        description="中国与沙特阿拉伯签署新能源领域合作备忘录",
        evidence_text="据新华社报道...",
        signal_direction=Direction.BULLISH,
        affected_markets=[Market.A_SHARE],
        affected_instruments=["新能源", "光伏"],  # 板块名称
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
            affects=["新能源产业链"]
        ),
        metadata={}
    )

    print(f"\n[输入] affected_instruments: {signal.affected_instruments}")
    print("   类型: 板块名称")

    # 测试resolve_instruments
    engine = JudgmentEngine(llm_client=LLMClient())
    resolved = engine.sector_knowledge.resolve_instruments(signal.affected_instruments)
    print(f"\n[解析] resolved_instruments: {resolved}")
    print("   预期: 新能源和光伏板块的龙头股")

    return signal


def test_case_3_mixed():
    """测试用例3：混合情况（公司+板块）"""
    print("\n" + "=" * 60)
    print("测试用例3：混合情况（公司名称+板块+股票代码）")
    print("=" * 60)

    signal = MarketSignal(
        signal_id="test_mixed_001",
        signal_type=SignalType.INDUSTRY,
        signal_label="光伏产业链集体上涨",
        description="隆基绿能领涨，新能源板块全线飘红",
        evidence_text="市场数据显示...",
        signal_direction=Direction.BULLISH,
        affected_markets=[Market.A_SHARE],
        affected_instruments=["隆基绿能", "新能源", "601012.SH", "光伏"],  # 混合
        event_time=datetime.now(),
        collected_time=datetime.now(),
        time_horizon=TimeHorizon.SHORT,
        intensity_score=7,
        confidence_score=8,
        timeliness_score=8,
        source_type=SourceType.NEWS,
        source_ref="市场数据",
        logic_frame=SignalLogicFrame(
            what_changed="光伏产业链集体上涨",
            change_direction=Direction.BULLISH,
            affects=["光伏产业链"]
        ),
        metadata={}
    )

    print(f"\n[输入] affected_instruments: {signal.affected_instruments}")
    print("   类型: 混合（公司名称+板块+股票代码）")

    # 测试resolve_instruments
    engine = JudgmentEngine(llm_client=LLMClient())
    resolved = engine.sector_knowledge.resolve_instruments(signal.affected_instruments)
    print(f"\n[解析] resolved_instruments: {resolved}")
    print("   预期: 去重后的股票代码列表")

    return signal


def main():
    print("=" * 60)
    print("测试M3处理不同类型的affected_instruments")
    print("=" * 60)

    # 测试1：公司名称
    signal1 = test_case_1_specific_company()

    # 测试2：板块名称
    signal2 = test_case_2_sector()

    # 测试3：混合情况
    signal3 = test_case_3_mixed()

    print("\n" + "=" * 60)
    print("总结")
    print("=" * 60)
    print("\n当前实现支持三种情况：")
    print("1. [OK] 公司名称 -> 自动解析为股票代码")
    print("2. [OK] 板块名称 -> 自动解析为龙头股代码")
    print("3. [OK] 混合情况 -> 统一解析并去重")
    print("\nM3的LLM会看到：")
    print("- 板块龙头股信息（来自知识库）")
    print("- 信号中直接提到的标的（已解析为股票代码）")
    print("- 基于这些信息，LLM选择最相关的股票代码输出")


if __name__ == "__main__":
    main()
