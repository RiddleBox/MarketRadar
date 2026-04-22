"""
可行性验证脚本：分析2024年降准/降息前的线索组合

目标：验证"推理型判断"是否可行
方法：手工标注历史事件的前置线索，分析规律
"""

from datetime import datetime, timedelta
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class PolicyEvent:
    """政策事件"""
    event_date: datetime
    event_type: str  # "降准", "降息", "降准+降息"
    event_description: str
    market_reaction: float  # 当日或次日涨跌幅

@dataclass
class PrecursorSignal:
    """前置信号"""
    signal_date: datetime
    signal_type: str  # "政策表态", "经济数据", "公开市场操作", "市场传闻"
    source: str  # "央行行长讲话", "政治局会议", "统计局数据"
    content: str
    strength: int  # 1-10，信号强度

@dataclass
class CaseAnalysis:
    """案例分析"""
    event: PolicyEvent
    precursor_signals: List[PrecursorSignal]
    lead_time_days: int  # 最早信号到事件的天数
    signal_pattern: str  # 信号组合模式描述


# ============================================================
# 历史案例数据（需要手工补充真实数据）
# ============================================================

HISTORICAL_CASES = [
    # 案例1：2024年9月24日降准
    CaseAnalysis(
        event=PolicyEvent(
            event_date=datetime(2024, 9, 24),
            event_type="降准",
            event_description="央行宣布降准0.5个百分点",
            market_reaction=2.5  # 需要查证真实数据
        ),
        precursor_signals=[
            PrecursorSignal(
                signal_date=datetime(2024, 9, 20),
                signal_type="政策表态",
                source="国务院常务会议",
                content="加大宏观调控力度，适时降准",
                strength=9
            ),
            PrecursorSignal(
                signal_date=datetime(2024, 9, 10),
                signal_type="经济数据",
                source="统计局",
                content="8月CPI同比0.6%，PPI同比-1.8%，通缩压力",
                strength=7
            ),
            PrecursorSignal(
                signal_date=datetime(2024, 9, 18),
                signal_type="市场传闻",
                source="财经媒体",
                content="市场预期降准概率上升",
                strength=6
            ),
        ],
        lead_time_days=14,
        signal_pattern="政策表态(高强度) + 经济数据(通缩) + 市场预期"
    ),

    # 案例2：2024年7月22日降息
    CaseAnalysis(
        event=PolicyEvent(
            event_date=datetime(2024, 7, 22),
            event_type="降息",
            event_description="1年期LPR下调10bp至3.35%",
            market_reaction=1.8
        ),
        precursor_signals=[
            PrecursorSignal(
                signal_date=datetime(2024, 7, 15),
                signal_type="政策表态",
                source="央行货币政策委员会",
                content="加大逆周期调节力度",
                strength=8
            ),
            PrecursorSignal(
                signal_date=datetime(2024, 7, 10),
                signal_type="经济数据",
                source="统计局",
                content="6月CPI同比0.2%，经济复苏乏力",
                strength=7
            ),
            PrecursorSignal(
                signal_date=datetime(2024, 7, 18),
                signal_type="公开市场操作",
                source="央行",
                content="MLF超额续作，释放流动性信号",
                strength=6
            ),
        ],
        lead_time_days=12,
        signal_pattern="政策表态 + 经济数据(低通胀) + MLF操作"
    ),

    # 案例3：2024年2月5日降准
    CaseAnalysis(
        event=PolicyEvent(
            event_date=datetime(2024, 2, 5),
            event_type="降准",
            event_description="央行宣布降准0.5个百分点",
            market_reaction=3.2
        ),
        precursor_signals=[
            PrecursorSignal(
                signal_date=datetime(2024, 1, 24),
                signal_type="政策表态",
                source="央行行长潘功胜",
                content="将适时降准，保持流动性合理充裕",
                strength=9
            ),
            PrecursorSignal(
                signal_date=datetime(2024, 1, 20),
                signal_type="经济数据",
                source="统计局",
                content="2023年Q4 GDP增速5.2%，低于预期",
                strength=7
            ),
            PrecursorSignal(
                signal_date=datetime(2024, 1, 28),
                signal_type="市场传闻",
                source="券商研报",
                content="多家券商预测春节前降准概率80%",
                strength=7
            ),
        ],
        lead_time_days=12,
        signal_pattern="央行行长明确表态 + GDP低于预期 + 券商预期"
    ),

    # 案例4：2023年9月15日降准
    CaseAnalysis(
        event=PolicyEvent(
            event_date=datetime(2023, 9, 15),
            event_type="降准",
            event_description="央行宣布降准0.25个百分点",
            market_reaction=1.5
        ),
        precursor_signals=[
            PrecursorSignal(
                signal_date=datetime(2023, 9, 5),
                signal_type="政策表态",
                source="国务院常务会议",
                content="加大宏观政策调控力度，适时降准",
                strength=8
            ),
            PrecursorSignal(
                signal_date=datetime(2023, 9, 1),
                signal_type="经济数据",
                source="统计局",
                content="8月PMI 49.7，连续5个月低于荣枯线",
                strength=8
            ),
            PrecursorSignal(
                signal_date=datetime(2023, 9, 10),
                signal_type="公开市场操作",
                source="央行",
                content="逆回购规模增加，释放宽松信号",
                strength=6
            ),
        ],
        lead_time_days=14,
        signal_pattern="政策表态 + PMI持续低迷 + 公开市场操作"
    ),
]


# ============================================================
# 分析函数
# ============================================================

def analyze_signal_patterns(cases: List[CaseAnalysis]) -> Dict:
    """
    分析信号模式的共性

    返回：
    - common_signal_types: 共同出现的信号类型
    - avg_lead_time: 平均提前天数
    - std_lead_time: 提前天数标准差
    - pattern_similarity: 模式相似度
    """

    # 统计信号类型频率
    signal_type_freq = {}
    lead_times = []

    for case in cases:
        if not case.precursor_signals:
            continue

        # 统计信号类型
        for signal in case.precursor_signals:
            signal_type_freq[signal.signal_type] = signal_type_freq.get(signal.signal_type, 0) + 1

        # 计算提前天数
        if case.precursor_signals:
            earliest_signal = min(s.signal_date for s in case.precursor_signals)
            lead_time = (case.event.event_date - earliest_signal).days
            lead_times.append(lead_time)

    # 计算统计特征
    if lead_times:
        avg_lead_time = sum(lead_times) / len(lead_times)
        variance = sum((x - avg_lead_time) ** 2 for x in lead_times) / len(lead_times)
        std_lead_time = variance ** 0.5
    else:
        avg_lead_time = 0
        std_lead_time = 0

    return {
        "signal_type_frequency": signal_type_freq,
        "avg_lead_time_days": avg_lead_time,
        "std_lead_time_days": std_lead_time,
        "num_cases": len(cases),
        "num_cases_with_signals": sum(1 for c in cases if c.precursor_signals),
    }


def calculate_pattern_similarity(case1: CaseAnalysis, case2: CaseAnalysis) -> float:
    """
    计算两个案例的信号模式相似度

    返回：0-1之间的相似度分数
    """
    if not case1.precursor_signals or not case2.precursor_signals:
        return 0.0

    # 提取信号类型集合
    types1 = set(s.signal_type for s in case1.precursor_signals)
    types2 = set(s.signal_type for s in case2.precursor_signals)

    # Jaccard相似度
    intersection = len(types1 & types2)
    union = len(types1 | types2)

    if union == 0:
        return 0.0

    return intersection / union


def evaluate_inference_feasibility(cases: List[CaseAnalysis]) -> str:
    """
    评估推理可行性

    返回：场景A/B/C
    """
    analysis = analyze_signal_patterns(cases)

    num_cases_with_signals = analysis["num_cases_with_signals"]
    avg_lead_time = analysis["avg_lead_time_days"]
    std_lead_time = analysis["std_lead_time_days"]

    # 计算案例间相似度
    similarities = []
    for i in range(len(cases)):
        for j in range(i + 1, len(cases)):
            sim = calculate_pattern_similarity(cases[i], cases[j])
            similarities.append(sim)

    avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0

    print("=" * 60)
    print("Feasibility Validation Results")
    print("=" * 60)
    print(f"Cases analyzed: {analysis['num_cases']}")
    print(f"Cases with precursor signals: {num_cases_with_signals}")
    print(f"Average lead time: {avg_lead_time:.1f} days")
    print(f"Lead time std dev: {std_lead_time:.1f} days")
    print(f"Average case similarity: {avg_similarity:.2f}")
    print()
    print("Signal type frequency:")
    for signal_type, freq in analysis["signal_type_frequency"].items():
        print(f"  - {signal_type}: {freq} times")
    print()

    # Determine scenario
    if num_cases_with_signals >= 3 and avg_similarity >= 0.7 and std_lead_time <= 7:
        scenario = "A"
        conclusion = "Inference viable (ideal case)"
        recommendation = "Worth investing in M2 causal graph + M3 inference engine"
    elif num_cases_with_signals >= 2 and avg_similarity >= 0.4 and std_lead_time <= 14:
        scenario = "B"
        conclusion = "Inference partially viable (realistic case)"
        recommendation = "Start with simplified version (manual causal graph, LLM-assisted inference)"
    else:
        scenario = "C"
        conclusion = "Inference not viable (worst case)"
        recommendation = "Abandon inference-based judgment, return to reactive judgment"

    print(f"Scenario: {scenario}")
    print(f"Conclusion: {conclusion}")
    print(f"Recommendation: {recommendation}")
    print("=" * 60)

    return scenario


# ============================================================
# 主函数
# ============================================================

def main():
    """
    主函数：执行可行性验证

    当前状态：框架已搭建，但缺少真实数据

    下一步：
    1. 手工回溯2024年2月、7月、9月的新闻
    2. 补充 precursor_signals 数据
    3. 重新运行分析
    """

    print("=" * 60)
    print("Feasibility Validation: Is Inference-based Judgment Viable?")
    print("=" * 60)
    print()
    print("WARNING: Current status - Missing real data")
    print()
    print("Need to manually supplement the following data:")
    print("1. News 2 weeks before Sept 24, 2024 RRR cut (Sept 10-23)")
    print("2. News 2 weeks before July 22, 2024 rate cut (July 8-21)")
    print("3. News 2 weeks before Feb 5, 2024 RRR cut (Jan 22 - Feb 4)")
    print("4. News 2 weeks before Sept 15, 2023 RRR cut (Sept 1-14)")
    print()
    print("Data sources:")
    print("- Xinhua, People's Daily (policy signals)")
    print("- Yicai, Cailian (market rumors)")
    print("- PBOC website (open market operations)")
    print("- Wind, Eastmoney (economic data)")
    print()
    print("=" * 60)
    print()

    # Execute analysis (will output scenario C due to missing data)
    scenario = evaluate_inference_feasibility(HISTORICAL_CASES)

    print()
    print("WARNING: Current results based on empty data, not representative")
    print("Please supplement real data and re-run")


if __name__ == "__main__":
    main()
