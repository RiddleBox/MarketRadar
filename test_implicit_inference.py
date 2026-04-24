"""
测试M1.5隐性信号推理完整流程
"""

import sys
sys.path.insert(0, '.')

from m1_5_implicit_reasoner.llm_client import create_llm_client
from m1_5_implicit_reasoner.inferencer import LLMImplicitSignalInferencer
from m2_knowledge_base.graph_loader import load_core_industry_graph


def test_implicit_signal_inference():
    """测试隐性信号推理"""
    print("=" * 60)
    print("测试M1.5隐性信号推理")
    print("=" * 60)

    # 1. 创建LLM客户端（使用Mock）
    print("\n1. 创建LLM客户端...")
    llm_client = create_llm_client(provider="mock")
    print("   使用Mock LLM客户端")

    # 2. 加载产业链图谱
    print("\n2. 加载产业链图谱...")
    industry_graph = load_core_industry_graph()
    print(f"   加载成功: {len(industry_graph.nodes)}个节点")

    # 3. 创建推理器
    print("\n3. 创建隐性信号推理器...")
    inferencer = LLMImplicitSignalInferencer(
        llm_client=llm_client,
        industry_graph=industry_graph
    )
    print("   推理器创建成功")

    # 4. 准备测试数据
    print("\n4. 准备测试数据...")
    raw_data = {
        'source': 'xinhua',
        'category': 'world',
        'title': '沙特王储访华，签署新能源合作协议',
        'content': '沙特王储穆罕默德访问中国，双方签署多项新能源领域合作协议，涉及光伏、风电等清洁能源项目。',
        'published_at': '2026-04-24'
    }
    print(f"   标题: {raw_data['title']}")
    print(f"   类别: {raw_data['category']}")

    # 5. 执行推理
    print("\n5. 执行隐性信号推理...")
    try:
        implicit_signals = inferencer.infer(raw_data)
        print(f"   推理成功，生成 {len(implicit_signals)} 个隐性信号")

        # 6. 展示结果
        print("\n6. 推理结果:")
        print("-" * 60)
        for i, signal in enumerate(implicit_signals, 1):
            print(f"\n隐性信号 #{i}:")
            print(f"  信号ID: {signal.signal_id}")
            print(f"  信号类型: {signal.signal_type}")
            print(f"  产业板块: {signal.industry_sector}")
            print(f"  潜在标的: {', '.join(signal.target_symbols)}")
            print(f"  机会描述: {signal.opportunity_description}")
            print(f"  先验置信度: {signal.prior_confidence:.3f}")
            print(f"  影响时间: {signal.expected_impact_timeframe}")

            print(f"\n  推理链:")
            print(f"    链ID: {signal.reasoning_chain.chain_id}")
            print(f"    源事件: {signal.reasoning_chain.source_event}")
            print(f"    目标机会: {signal.reasoning_chain.target_opportunity}")
            print(f"    因果环节数: {len(signal.reasoning_chain.causal_links)}")

            for j, link in enumerate(signal.reasoning_chain.causal_links, 1):
                print(f"\n    环节 {j}:")
                print(f"      {link.from_concept} → {link.to_concept}")
                print(f"      关系: {link.relation_type}")
                print(f"      置信度: {link.confidence:.2f}")
                print(f"      推理: {link.reasoning}")

            print(f"\n  推理链强度: {signal.reasoning_chain.get_chain_strength():.3f}")
            print(f"  整体置信度: {signal.reasoning_chain.overall_confidence:.2f}")

    except Exception as e:
        print(f"   推理失败: {e}")
        import traceback
        traceback.print_exc()


def test_reasoning_chain_generation():
    """测试推理链生成"""
    print("\n" + "=" * 60)
    print("测试推理链生成")
    print("=" * 60)

    llm_client = create_llm_client(provider="mock")
    industry_graph = load_core_industry_graph()
    inferencer = LLMImplicitSignalInferencer(llm_client, industry_graph)

    print("\n生成推理链...")
    try:
        chain = inferencer.generate_reasoning_chain(
            source_event="国家发布碳中和行动方案",
            target_opportunity="光伏产业链投资机会",
            context={"policy": "碳中和", "industry": "光伏"}
        )

        if chain:
            print(f"推理链ID: {chain.chain_id}")
            print(f"源事件: {chain.source_event}")
            print(f"目标机会: {chain.target_opportunity}")
            print(f"因果环节数: {len(chain.causal_links)}")
            print(f"推理链强度: {chain.get_chain_strength():.3f}")
        else:
            print("推理链生成失败")

    except Exception as e:
        print(f"错误: {e}")


def test_target_identification():
    """测试标的识别"""
    print("\n" + "=" * 60)
    print("测试标的识别")
    print("=" * 60)

    llm_client = create_llm_client(provider="mock")
    industry_graph = load_core_industry_graph()
    inferencer = LLMImplicitSignalInferencer(llm_client, industry_graph)

    print("\n识别标的...")
    try:
        targets = inferencer.identify_targets(
            industry_sector="光伏中游",
            opportunity_type="出口订单",
            context={"region": "中东", "product": "组件"}
        )

        print(f"识别到 {len(targets)} 个标的:")
        for target in targets:
            print(f"  - {target}")

    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    test_implicit_signal_inference()
    test_reasoning_chain_generation()
    test_target_identification()

    print("\n" + "=" * 60)
    print("所有测试完成")
    print("=" * 60)
