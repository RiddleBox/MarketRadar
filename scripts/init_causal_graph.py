"""
初始化因果图谱

基于可行性验证结果，手工标注10个常见因果模式
数据来源：docs/feasibility_validation_results.md
"""

from datetime import datetime
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.schemas import CausalPattern, Market
from m2_storage.signal_store import SignalStore


def create_initial_patterns() -> list[CausalPattern]:
    """创建初始因果模式（基于2023-2024年降准/降息案例分析）"""

    patterns = [
        # Pattern 1: 降准预测（核心模式）
        CausalPattern(
            pattern_id="pattern_rrr_cut_001",
            precursor_signals=[
                "政策表态：明确提到'适时降准'或'加大逆周期调节'",
                "经济数据：CPI<1%或PMI<50连续3个月"
            ],
            consequent_event="央行降准",
            probability=0.80,
            avg_lead_time_days=14,
            std_lead_time_days=1.4,
            supporting_cases=["case_2024_02_05", "case_2024_09_24", "case_2023_09_15"],
            confidence=0.85,
            last_updated=datetime(2026, 4, 18),
            created_at=datetime(2026, 4, 18),
            notes="核心信号：政策表态+经济数据差。4个案例中3个符合此模式，时间窗口非常稳定（标准差1.4天）"
        ),

        # Pattern 2: 降息预测
        CausalPattern(
            pattern_id="pattern_rate_cut_001",
            precursor_signals=[
                "政策表态：央行货币政策委员会提到'加大逆周期调节'",
                "经济数据：CPI<0.5%，经济复苏乏力",
                "公开市场操作：MLF超额续作"
            ],
            consequent_event="LPR下调",
            probability=0.75,
            avg_lead_time_days=12,
            std_lead_time_days=0.0,
            supporting_cases=["case_2024_07_22"],
            confidence=0.60,
            last_updated=datetime(2026, 4, 18),
            created_at=datetime(2026, 4, 18),
            notes="仅1个案例，置信度较低。需要更多案例验证"
        ),

        # Pattern 3: 高置信度降准（有市场预期）
        CausalPattern(
            pattern_id="pattern_rrr_cut_002",
            precursor_signals=[
                "政策表态：明确提到'适时降准'",
                "经济数据：CPI<1%或PMI<50",
                "市场传闻：券商研报预测降准概率>70%"
            ],
            consequent_event="央行降准",
            probability=0.90,
            avg_lead_time_days=13,
            std_lead_time_days=1.4,
            supporting_cases=["case_2024_02_05", "case_2024_09_24"],
            confidence=0.75,
            last_updated=datetime(2026, 4, 18),
            created_at=datetime(2026, 4, 18),
            notes="增强版模式：核心信号+市场预期。概率从80%提升至90%"
        ),

        # Pattern 4: 政治局会议后的政策宽松
        CausalPattern(
            pattern_id="pattern_policy_easing_001",
            precursor_signals=[
                "政策表态：政治局会议提到'加大宏观政策调控力度'",
                "经济数据：GDP增速低于预期或PMI连续低于荣枯线"
            ],
            consequent_event="货币政策宽松（降准或降息）",
            probability=0.70,
            avg_lead_time_days=15,
            std_lead_time_days=3.0,
            supporting_cases=["case_2024_09_24", "case_2023_09_15"],
            confidence=0.70,
            last_updated=datetime(2026, 4, 18),
            created_at=datetime(2026, 4, 18),
            notes="政治局会议是重要前置信号，但具体措施（降准/降息）需结合其他信号判断"
        ),

        # Pattern 5: 通缩压力下的政策响应
        CausalPattern(
            pattern_id="pattern_deflation_response_001",
            precursor_signals=[
                "经济数据：CPI同比<0.5%且PPI同比<-1.5%，持续2个月以上",
                "政策表态：央行或国务院提到'通缩风险'或'加大逆周期调节'"
            ],
            consequent_event="货币政策宽松",
            probability=0.85,
            avg_lead_time_days=10,
            std_lead_time_days=2.0,
            supporting_cases=["case_2024_09_24"],
            confidence=0.65,
            last_updated=datetime(2026, 4, 18),
            created_at=datetime(2026, 4, 18),
            notes="通缩压力是触发宽松政策的强信号。时间窗口较短（10天）"
        ),

        # Pattern 6: 财政货币政策协同
        CausalPattern(
            pattern_id="pattern_fiscal_monetary_coordination_001",
            precursor_signals=[
                "财政政策：财政部提前发行特别国债或地方债",
                "政策表态：国务院常务会议提到'财政货币政策协同发力'",
                "经济数据：固定资产投资增速低于预期"
            ],
            consequent_event="央行降准（配合财政发力）",
            probability=0.75,
            avg_lead_time_days=14,
            std_lead_time_days=2.5,
            supporting_cases=["case_2024_02_05"],
            confidence=0.65,
            last_updated=datetime(2026, 4, 18),
            created_at=datetime(2026, 4, 18),
            notes="财政货币协同是中国特色。财政发力通常伴随货币宽松"
        ),

        # Pattern 7: 北向资金流出压力下的政策对冲
        CausalPattern(
            pattern_id="pattern_northbound_outflow_policy_001",
            precursor_signals=[
                "资金流向：北向资金连续5个交易日净流出，累计>100亿",
                "市场表现：上证指数跌破关键支撑位（如3000点）",
                "政策表态：证监会或央行表态'维护市场稳定'"
            ],
            consequent_event="政策利好（降准、降息或其他稳市场措施）",
            probability=0.65,
            avg_lead_time_days=7,
            std_lead_time_days=3.0,
            supporting_cases=[],
            confidence=0.50,
            last_updated=datetime(2026, 4, 18),
            created_at=datetime(2026, 4, 18),
            notes="A股特有模式。政策对市场下跌的容忍度有限，但响应时间不确定。需要更多案例验证"
        ),

        # Pattern 8: 房地产政策宽松信号
        CausalPattern(
            pattern_id="pattern_property_easing_001",
            precursor_signals=[
                "政策表态：住建部或央行提到'支持刚性和改善性住房需求'",
                "经济数据：房地产销售面积同比下降>20%",
                "政策动作：一线城市放松限购或降低首付比例"
            ],
            consequent_event="货币政策宽松（降准或降低房贷利率）",
            probability=0.70,
            avg_lead_time_days=20,
            std_lead_time_days=5.0,
            supporting_cases=[],
            confidence=0.55,
            last_updated=datetime(2026, 4, 18),
            created_at=datetime(2026, 4, 18),
            notes="房地产是中国经济重要支柱。房地产政策宽松通常先于货币政策。时间窗口较长"
        ),

        # Pattern 9: 美联储降息后的跟随效应
        CausalPattern(
            pattern_id="pattern_fed_rate_cut_follow_001",
            precursor_signals=[
                "国际政策：美联储降息",
                "汇率：人民币兑美元汇率升值压力缓解",
                "经济数据：中国经济数据偏弱"
            ],
            consequent_event="央行降息（跟随美联储）",
            probability=0.60,
            avg_lead_time_days=30,
            std_lead_time_days=10.0,
            supporting_cases=[],
            confidence=0.50,
            last_updated=datetime(2026, 4, 18),
            created_at=datetime(2026, 4, 18),
            notes="美联储降息打开中国货币政策空间，但不是必然跟随。需要国内经济数据配合"
        ),

        # Pattern 10: 季末流动性紧张下的降准
        CausalPattern(
            pattern_id="pattern_quarter_end_liquidity_001",
            precursor_signals=[
                "资金面：银行间市场利率（DR007）持续高于政策利率20bp以上",
                "时间：季末（3月、6月、9月、12月）前2周",
                "政策表态：央行提到'保持流动性合理充裕'"
            ],
            consequent_event="央行降准（缓解季末流动性压力）",
            probability=0.55,
            avg_lead_time_days=10,
            std_lead_time_days=3.0,
            supporting_cases=[],
            confidence=0.45,
            last_updated=datetime(2026, 4, 18),
            created_at=datetime(2026, 4, 18),
            notes="季节性模式。季末流动性紧张是常态，但不一定触发降准。需要配合其他信号"
        ),
    ]

    return patterns


def main():
    """初始化因果图谱"""
    print("=" * 60)
    print("初始化因果图谱")
    print("=" * 60)
    print()

    # Create patterns
    patterns = create_initial_patterns()
    print(f"创建 {len(patterns)} 个因果模式")
    print()

    # Save to M2
    store = SignalStore()
    saved_count = 0

    for pattern in patterns:
        if store.save_causal_pattern(pattern):
            saved_count += 1
            print(f"[OK] {pattern.pattern_id}: {pattern.consequent_event} (概率={pattern.probability:.0%})")
        else:
            print(f"[FAIL] {pattern.pattern_id}: 保存失败")

    print()
    print("=" * 60)
    print(f"完成：{saved_count}/{len(patterns)} 个模式已保存")
    print("=" * 60)
    print()

    # Verify
    print("验证：查询所有因果模式")
    all_patterns = store.query_causal_patterns()
    print(f"数据库中共有 {len(all_patterns)} 个因果模式")
    print()

    # Show high-confidence patterns
    print("高置信度模式（概率≥75%，置信度≥70%）：")
    high_conf = store.query_causal_patterns(min_probability=0.75, min_confidence=0.70)
    for p in high_conf:
        print(f"  - {p.pattern_id}: {p.consequent_event} (概率={p.probability:.0%}, 置信度={p.confidence:.0%})")
    print()


if __name__ == "__main__":
    main()
