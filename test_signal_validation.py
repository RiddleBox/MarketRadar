"""
测试M3隐性信号验证
"""

import sys
sys.path.insert(0, '.')

import json
from pathlib import Path
from m3_reasoning_engine.signal_validator import (
    CaseLibrary,
    ImplicitSignalValidator,
    HistoricalCase
)
from m1_5_implicit_reasoner.llm_client import create_llm_client
from m1_5_implicit_reasoner.inferencer import LLMImplicitSignalInferencer
from m2_knowledge_base.graph_loader import load_core_industry_graph


def test_case_library():
    """测试历史案例库"""
    print("=" * 60)
    print("测试历史案例库")
    print("=" * 60)

    # 加载历史案例
    case_library = CaseLibrary()
    data_path = Path(__file__).parent / "data" / "historical_cases.json"

    with open(data_path, 'r', encoding='utf-8') as f:
        cases_data = json.load(f)

    case_library.load_from_dict(cases_data)

    print(f"\n加载 {len(case_library.cases)} 个历史案例")

    # 测试查询
    print("\n" + "-" * 60)
    print("测试1: 查询外交事件案例")
    print("-" * 60)

    similar_cases = case_library.query_similar_cases(
        signal_type="diplomatic_event",
        keywords=["沙特", "新能源", "光伏"],
        limit=5
    )

    print(f"\n找到 {len(similar_cases)} 个相似案例:")
    for case in similar_cases:
        print(f"\n  案例ID: {case.case_id}")
        print(f"  事件: {case.event_description}")
        print(f"  预测: {case.predicted_outcome}")
        print(f"  实际: {case.actual_outcome}")
        print(f"  成功: {'是' if case.success else '否'}")

    # 测试成功率计算
    print("\n" + "-" * 60)
    print("测试2: 计算历史成功率")
    print("-" * 60)

    success_rate = case_library.calculate_success_rate(
        signal_type="diplomatic_event",
        keywords=["沙特", "新能源"]
    )
    print(f"\n外交事件（沙特+新能源）历史成功率: {success_rate:.2%}")

    success_rate = case_library.calculate_success_rate(
        signal_type="policy_driven",
        keywords=["碳中和", "光伏"]
    )
    print(f"政策驱动（碳中和+光伏）历史成功率: {success_rate:.2%}")

    success_rate = case_library.calculate_success_rate(
        signal_type="tech_breakthrough",
        keywords=["电池", "商业化"]
    )
    print(f"技术突破（电池+商业化）历史成功率: {success_rate:.2%}")


def test_signal_validation():
    """测试信号验证"""
    print("\n" + "=" * 60)
    print("测试隐性信号验证")
    print("=" * 60)

    # 1. 加载案例库
    print("\n1. 加载历史案例库...")
    case_library = CaseLibrary()
    data_path = Path(__file__).parent / "data" / "historical_cases.json"

    with open(data_path, 'r', encoding='utf-8') as f:
        cases_data = json.load(f)

    case_library.load_from_dict(cases_data)
    print(f"   加载 {len(case_library.cases)} 个案例")

    # 2. 创建验证器
    print("\n2. 创建信号验证器...")
    validator = ImplicitSignalValidator(case_library)
    print("   验证器创建成功")

    # 3. 生成隐性信号
    print("\n3. 生成隐性信号...")
    llm_client = create_llm_client(provider="mock")
    industry_graph = load_core_industry_graph()
    inferencer = LLMImplicitSignalInferencer(llm_client, industry_graph)

    raw_data = {
        'source': 'xinhua',
        'category': 'world',
        'title': '沙特王储访华，签署新能源合作协议',
        'content': '沙特王储穆罕默德访问中国，双方签署多项新能源领域合作协议。',
        'published_at': '2026-04-24'
    }

    implicit_signals = inferencer.infer(raw_data)
    print(f"   生成 {len(implicit_signals)} 个隐性信号")

    # 4. 验证信号
    print("\n4. 验证隐性信号...")
    print("-" * 60)

    for i, signal in enumerate(implicit_signals, 1):
        print(f"\n信号 #{i}:")
        print(f"  信号类型: {signal.signal_type}")
        print(f"  机会描述: {signal.opportunity_description}")
        print(f"  先验置信度: {signal.prior_confidence:.3f}")

        # 验证
        posterior_confidence = validator.validate(signal)
        print(f"  后验置信度: {posterior_confidence:.3f}")

        # 计算变化
        change = posterior_confidence - signal.prior_confidence
        change_pct = (change / signal.prior_confidence * 100) if signal.prior_confidence > 0 else 0
        print(f"  置信度变化: {change:+.3f} ({change_pct:+.1f}%)")

        # 查询相似案例
        keywords = validator._extract_keywords(signal)
        similar_cases = case_library.query_similar_cases(
            signal_type=signal.signal_type,
            keywords=keywords[:3],
            limit=3
        )

        if similar_cases:
            print(f"\n  参考案例 ({len(similar_cases)}个):")
            for case in similar_cases:
                print(f"    - {case.event_description[:30]}... ({'成功' if case.success else '失败'})")


def test_batch_validation():
    """测试批量验证"""
    print("\n" + "=" * 60)
    print("测试批量验证和过滤")
    print("=" * 60)

    # 加载案例库
    case_library = CaseLibrary()
    data_path = Path(__file__).parent / "data" / "historical_cases.json"

    with open(data_path, 'r', encoding='utf-8') as f:
        cases_data = json.load(f)

    case_library.load_from_dict(cases_data)

    # 创建验证器
    validator = ImplicitSignalValidator(case_library)

    # 生成信号
    llm_client = create_llm_client(provider="mock")
    industry_graph = load_core_industry_graph()
    inferencer = LLMImplicitSignalInferencer(llm_client, industry_graph)

    raw_data = {
        'source': 'xinhua',
        'category': 'world',
        'title': '沙特王储访华，签署新能源合作协议',
        'content': '沙特王储穆罕默德访问中国，双方签署多项新能源领域合作协议。',
        'published_at': '2026-04-24'
    }

    implicit_signals = inferencer.infer(raw_data)

    print(f"\n原始信号数: {len(implicit_signals)}")

    # 批量验证
    validated_signals = validator.batch_validate(implicit_signals)
    print(f"验证后信号数: {len(validated_signals)}")

    # 过滤低置信度信号
    threshold = 0.5
    filtered_signals = validator.filter_by_confidence(validated_signals, threshold)
    print(f"过滤后信号数 (阈值={threshold}): {len(filtered_signals)}")

    print("\n过滤后的信号:")
    for i, signal in enumerate(filtered_signals, 1):
        print(f"  {i}. {signal.opportunity_description[:40]}... (置信度: {signal.prior_confidence:.3f})")


if __name__ == "__main__":
    test_case_library()
    test_signal_validation()
    test_batch_validation()

    print("\n" + "=" * 60)
    print("所有测试完成")
    print("=" * 60)
