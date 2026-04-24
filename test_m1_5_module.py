"""
测试M1.5隐性信号推理模块
"""

import sys
sys.path.insert(0, '.')

from m1_5_implicit_reasoner.models import (
    ImplicitSignal,
    ReasoningChain,
    CausalLink,
    ReasoningStage
)
from m2_knowledge_base.graph_loader import load_core_industry_graph
from datetime import datetime


def test_industry_graph():
    """测试产业链图谱"""
    print("=" * 60)
    print("测试产业链图谱")
    print("=" * 60)

    graph = load_core_industry_graph()
    print(f"\n加载成功:")
    print(f"  节点数: {len(graph.nodes)}")
    print(f"  关系数: {len(graph.relations)}")
    print(f"  政策映射数: {len(graph.policy_mappings)}")
    print(f"  事件映射数: {len(graph.event_mappings)}")

    # 测试政策查询
    print("\n" + "-" * 60)
    print("测试1: 政策-产业映射查询")
    print("-" * 60)
    policy_text = "国家支持光伏产业发展，推动碳中和目标"
    results = graph.find_industries_by_policy(policy_text, threshold=0.5)
    print(f"\n政策文本: {policy_text}")
    print(f"匹配产业 (前5个):")
    for node, confidence in results[:5]:
        print(f"  - {node.name} ({node.sector}) [置信度: {confidence:.2f}]")
        if node.related_symbols:
            print(f"    相关标的: {', '.join(node.related_symbols[:3])}")

    # 测试事件查询
    print("\n" + "-" * 60)
    print("测试2: 事件-产业映射查询")
    print("-" * 60)
    event_text = "钙钛矿电池效率突破25%"
    results = graph.find_industries_by_event(
        "tech_breakthrough",
        event_text,
        threshold=0.5
    )
    print(f"\n事件文本: {event_text}")
    print(f"匹配产业:")
    for node, confidence, template in results:
        print(f"  - {node.name} ({node.sector}) [置信度: {confidence:.2f}]")
        print(f"    推理模板: {template}")
        if node.related_symbols:
            print(f"    相关标的: {', '.join(node.related_symbols[:3])}")

    # 测试上下游查询
    print("\n" + "-" * 60)
    print("测试3: 产业链上下游查询")
    print("-" * 60)
    node_id = "ev_midstream_battery_cell"
    print(f"\n查询节点: {graph.nodes[node_id].name}")

    upstream = graph.get_upstream_industries(node_id, max_depth=1)
    print(f"\n上游产业:")
    for node in upstream:
        print(f"  - {node.name} ({node.sector})")

    downstream = graph.get_downstream_industries(node_id, max_depth=1)
    print(f"\n下游产业:")
    for node in downstream:
        print(f"  - {node.name} ({node.sector})")


def test_reasoning_chain():
    """测试推理链模型"""
    print("\n" + "=" * 60)
    print("测试推理链数据模型")
    print("=" * 60)

    # 构建示例推理链
    links = [
        CausalLink(
            from_concept="国家推动碳中和政策",
            to_concept="光伏装机需求增长",
            relation_type="policy_drives",
            confidence=0.9,
            reasoning="碳中和目标要求大幅增加可再生能源占比",
            supporting_facts=["2030年碳达峰", "2060年碳中和"]
        ),
        CausalLink(
            from_concept="光伏装机需求增长",
            to_concept="光伏组件需求增长",
            relation_type="demand_shifts",
            confidence=0.95,
            reasoning="装机增长直接带动组件需求",
            supporting_facts=["组件是光伏电站核心部件"]
        ),
        CausalLink(
            from_concept="光伏组件需求增长",
            to_concept="硅片需求增长",
            relation_type="demand_shifts",
            confidence=0.9,
            reasoning="组件生产需要大量硅片",
            supporting_facts=["硅片是组件上游原料"]
        )
    ]

    chain = ReasoningChain(
        chain_id="test_chain_001",
        source_event="国家发布碳中和行动方案",
        target_opportunity="光伏产业链投资机会",
        causal_links=links,
        reasoning_stages={
            ReasoningStage.EVENT_ANALYSIS: "政策事件，重要性高",
            ReasoningStage.CAUSAL_INFERENCE: "政策→需求→产业链传导",
            ReasoningStage.INDUSTRY_IMPACT: "光伏全产业链受益",
            ReasoningStage.TARGET_IDENTIFICATION: "重点关注硅片和组件环节"
        },
        overall_confidence=0.85
    )

    print(f"\n推理链ID: {chain.chain_id}")
    print(f"源事件: {chain.source_event}")
    print(f"目标机会: {chain.target_opportunity}")
    print(f"\n因果链条:")
    for i, link in enumerate(chain.causal_links, 1):
        print(f"  {i}. {link.from_concept} → {link.to_concept}")
        print(f"     关系: {link.relation_type}, 置信度: {link.confidence:.2f}")
        print(f"     推理: {link.reasoning}")

    print(f"\n推理链强度: {chain.get_chain_strength():.3f}")
    print(f"整体置信度: {chain.overall_confidence:.2f}")


def test_implicit_signal():
    """测试隐性信号模型"""
    print("\n" + "=" * 60)
    print("测试隐性信号数据模型")
    print("=" * 60)

    # 构建示例推理链
    links = [
        CausalLink(
            from_concept="中东国家领导人访华",
            to_concept="能源合作协议签署",
            relation_type="policy_drives",
            confidence=0.85,
            reasoning="外交访问通常伴随能源合作",
            supporting_facts=["历史访问记录"]
        ),
        CausalLink(
            from_concept="能源合作协议签署",
            to_concept="光伏项目出口增长",
            relation_type="demand_shifts",
            confidence=0.8,
            reasoning="中东地区光伏资源丰富，合作重点在新能源",
            supporting_facts=["中东光照条件优越"]
        )
    ]

    chain = ReasoningChain(
        chain_id="signal_chain_001",
        source_event="沙特王储访华",
        target_opportunity="光伏组件出口机会",
        causal_links=links,
        reasoning_stages={
            ReasoningStage.EVENT_ANALYSIS: "外交事件，涉及能源合作",
            ReasoningStage.CAUSAL_INFERENCE: "外交→能源合作→光伏出口",
            ReasoningStage.INDUSTRY_IMPACT: "光伏组件厂商受益",
            ReasoningStage.TARGET_IDENTIFICATION: "关注出口型组件企业"
        },
        overall_confidence=0.68
    )

    signal = ImplicitSignal(
        signal_id="implicit_001",
        signal_type="diplomatic_event",
        source_info={
            "source": "xinhua",
            "category": "world",
            "title": "沙特王储访华，签署多项能源合作协议",
            "published_at": "2026-04-24"
        },
        reasoning_chain=chain,
        industry_sector="光伏中游",
        target_symbols=["601012.SH", "688599.SH"],
        opportunity_description="中东市场光伏组件出口机会",
        prior_confidence=chain.get_chain_strength(),
        expected_impact_timeframe="mid_term"
    )

    print(f"\n隐性信号ID: {signal.signal_id}")
    print(f"信号类型: {signal.signal_type}")
    print(f"产业板块: {signal.industry_sector}")
    print(f"潜在标的: {', '.join(signal.target_symbols)}")
    print(f"机会描述: {signal.opportunity_description}")
    print(f"先验置信度: {signal.prior_confidence:.3f}")
    print(f"影响时间: {signal.expected_impact_timeframe}")
    print(f"需要M3验证: {signal.requires_m3_validation}")

    # 测试序列化
    print("\n" + "-" * 60)
    print("测试序列化:")
    signal_dict = signal.to_dict()
    print(f"序列化成功，字段数: {len(signal_dict)}")


if __name__ == "__main__":
    test_industry_graph()
    test_reasoning_chain()
    test_implicit_signal()

    print("\n" + "=" * 60)
    print("所有测试完成")
    print("=" * 60)
