# -*- coding: utf-8 -*-
"""
真实LLM推理测试
使用DeepSeek API进行端到端测试
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from llm_config_loader import create_llm_from_config
from m1_5_implicit_reasoner.inferencer import LLMImplicitSignalInferencer
from m2_knowledge_base.industry_graph import IndustryGraph
from m3_reasoning_engine.signal_validator import ImplicitSignalValidator


def test_real_llm_inference():
    """测试真实LLM推理"""

    print("=" * 80)
    print("真实LLM推理测试")
    print("=" * 80)

    # 1. 加载LLM客户端（自动从config/llm_config.local.yaml加载DeepSeek配置）
    print("\n[步骤1] 加载LLM客户端...")
    llm_client = create_llm_from_config()
    print(f"LLM客户端类型: {type(llm_client).__name__}")

    # 2. 初始化产业链图谱
    print("\n[步骤2] 加载产业链图谱...")
    import json
    graph_path = Path(__file__).parent / "data" / "industry_graph_full.json"
    with open(graph_path, 'r', encoding='utf-8') as f:
        graph_data = json.load(f)
    industry_graph = IndustryGraph.from_dict(graph_data)
    print(f"产业链节点数: {len(industry_graph.nodes)}")

    # 3. 初始化M1.5推理器
    print("\n[步骤3] 初始化M1.5推理器...")
    inferencer = LLMImplicitSignalInferencer(
        llm_client=llm_client,
        industry_graph=industry_graph
    )

    # 4. 初始化M3验证器
    print("\n[步骤4] 初始化M3验证器...")
    from m3_reasoning_engine.signal_validator import CaseLibrary
    case_library = CaseLibrary()
    cases_path = Path(__file__).parent / "data" / "historical_cases_extended.json"
    with open(cases_path, 'r', encoding='utf-8') as f:
        cases_data = json.load(f)
    case_library.load_from_dict(cases_data)
    validator = ImplicitSignalValidator(case_library)
    print(f"历史案例数: {len(case_library.cases)}")

    # 5. 测试案例1: 外交事件
    print("\n" + "=" * 80)
    print("测试案例1: 外交事件 - 沙特王储访华")
    print("=" * 80)

    test_data_1 = {
        'source': '新华社',
        'category': 'world',
        'title': '沙特王储访华 签署新能源合作协议',
        'content': '沙特阿拉伯王储穆罕默德·本·萨勒曼12月15日访问中国，双方签署多项新能源合作协议。根据协议，沙特计划在未来5年内投资500亿美元发展可再生能源，其中光伏发电是重点领域。中国企业将参与沙特多个大型光伏电站项目的建设，涉及光伏组件、逆变器等核心设备供应。此外，双方还将在储能技术、智能电网等领域开展深度合作。沙特能源大臣表示，该国计划到2030年实现50%的电力来自可再生能源，光伏装机容量将达到40GW。',
        'published_at': '2024-12-15'
    }

    print("\n[M1.5推理] 开始推理...")
    signals_1 = inferencer.infer(test_data_1)

    if signals_1:
        signal = signals_1[0]
        print(f"\n识别到隐性信号:")
        print(f"  信号类型: {signal.signal_type}")
        print(f"  产业板块: {signal.industry_sector}")
        print(f"  机会描述: {signal.opportunity_description}")
        print(f"  潜在标的: {', '.join(signal.target_symbols)}")
        print(f"  先验置信度: {signal.prior_confidence:.3f}")
        print(f"  影响时间: {signal.expected_impact_timeframe}")

        print(f"\n推理链:")
        for i, link in enumerate(signal.reasoning_chain.causal_links, 1):
            print(f"  {i}. {link.from_concept} -> {link.to_concept}")
            print(f"     推理: {link.reasoning}")
            print(f"     置信度: {link.confidence:.3f}")

        # M3验证
        print("\n[M3验证] 开始验证...")
        posterior_confidence = validator.validate(signal)

        print(f"\n验证结果:")
        print(f"  后验置信度: {posterior_confidence:.3f}")
        print(f"  置信度变化: {posterior_confidence - signal.prior_confidence:+.3f}")
    else:
        print("未识别到隐性信号")

    # 6. 测试案例2: 政策事件
    print("\n" + "=" * 80)
    print("测试案例2: 政策事件 - 半导体产业扶持政策")
    print("=" * 80)

    test_data_2 = {
        'source': '发改委',
        'category': 'policy',
        'title': '关于支持集成电路产业发展的若干政策',
        'content': '为加快集成电路产业发展，国家将在税收、融资、人才等方面给予重点支持，鼓励企业加大研发投入。',
        'published_at': '2024-12-10'
    }

    print("\n[M1.5推理] 开始推理...")
    signals_2 = inferencer.infer(test_data_2)

    if signals_2:
        signal = signals_2[0]
        print(f"\n识别到隐性信号:")
        print(f"  信号类型: {signal.signal_type}")
        print(f"  产业板块: {signal.industry_sector}")
        print(f"  机会描述: {signal.opportunity_description}")
        print(f"  潜在标的: {', '.join(signal.target_symbols)}")
        print(f"  先验置信度: {signal.prior_confidence:.3f}")

        print(f"\n推理链:")
        for i, link in enumerate(signal.reasoning_chain.causal_links, 1):
            print(f"  {i}. {link.from_concept} -> {link.to_concept}")
            print(f"     推理: {link.reasoning}")
            print(f"     置信度: {link.confidence:.3f}")

        # M3验证
        print("\n[M3验证] 开始验证...")
        posterior_confidence = validator.validate(signal)

        print(f"\n验证结果:")
        print(f"  后验置信度: {posterior_confidence:.3f}")
        print(f"  置信度变化: {posterior_confidence - signal.prior_confidence:+.3f}")
    else:
        print("未识别到隐性信号")

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    test_real_llm_inference()
