"""
端到端真实数据测试
使用真实新闻数据测试完整推理流程: M0 → M1.5 → M3
"""

import sys
sys.path.insert(0, '.')

from m0_collector.providers.xinhua_provider import XinhuaProvider
from m1_5_implicit_reasoner.inferencer import LLMImplicitSignalInferencer
from m2_knowledge_base.industry_graph import IndustryGraph
from m3_reasoning_engine.signal_validator import CaseLibrary, ImplicitSignalValidator
from llm_config_loader import create_llm_from_config
import json
from pathlib import Path


def test_end_to_end_real_data():
    """端到端真实数据测试"""
    print("=" * 60)
    print("端到端真实数据测试")
    print("=" * 60)

    # 1. M0: 采集真实新闻
    print("\n步骤1: M0数据采集")
    print("-" * 60)
    provider = XinhuaProvider()
    articles = provider.fetch(category="world", limit=3)

    if not articles:
        print("未获取到新闻，测试终止")
        return

    print(f"成功获取 {len(articles)} 篇新闻")
    for i, article in enumerate(articles, 1):
        print(f"\n新闻 {i}:")
        print(f"  标题: {article.title}")
        print(f"  来源: {article.source_name}")
        print(f"  时间: {article.raw_published_at}")

    # 选择第一篇新闻进行测试
    test_article = articles[0]
    print(f"\n选择测试新闻: {test_article.title}")

    # 2. 加载产业链图谱
    print("\n步骤2: 加载产业链图谱")
    print("-" * 60)
    graph_path = Path(__file__).parent / "data" / "industry_graph_full.json"
    with open(graph_path, 'r', encoding='utf-8') as f:
        graph_data = json.load(f)
    industry_graph = IndustryGraph.from_dict(graph_data)
    print(f"加载成功: {len(industry_graph.nodes)}个节点, {len(industry_graph.relations)}条关系")

    # 3. 创建LLM客户端
    print("\n步骤3: 创建LLM客户端")
    print("-" * 60)
    llm_client = create_llm_from_config()
    print(f"LLM客户端类型: {type(llm_client).__name__}")

    # 4. M1.5: 隐性信号推理
    print("\n步骤4: M1.5隐性信号推理")
    print("-" * 60)
    inferencer = LLMImplicitSignalInferencer(llm_client, industry_graph)

    raw_data = {
        'source': test_article.source_name,
        'category': 'world',
        'title': test_article.title,
        'content': test_article.content or test_article.title,
        'published_at': test_article.raw_published_at
    }

    try:
        implicit_signals = inferencer.infer(raw_data)
        print(f"推理成功，生成 {len(implicit_signals)} 个隐性信号")

        for i, signal in enumerate(implicit_signals, 1):
            print(f"\n隐性信号 #{i}:")
            print(f"  信号类型: {signal.signal_type}")
            print(f"  产业板块: {signal.industry_sector}")
            print(f"  潜在标的: {', '.join(signal.target_symbols[:3])}")
            print(f"  机会描述: {signal.opportunity_description[:50]}...")
            print(f"  先验置信度: {signal.prior_confidence:.3f}")
            print(f"  推理链环节数: {len(signal.reasoning_chain.causal_links)}")

    except Exception as e:
        print(f"推理失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 5. 加载历史案例库
    print("\n步骤5: 加载历史案例库")
    print("-" * 60)
    case_library = CaseLibrary()
    cases_path = Path(__file__).parent / "data" / "historical_cases_extended.json"
    with open(cases_path, 'r', encoding='utf-8') as f:
        cases_data = json.load(f)
    case_library.load_from_dict(cases_data)
    print(f"加载 {len(case_library.cases)} 个历史案例")

    # 6. M3: 信号验证
    print("\n步骤6: M3信号验证")
    print("-" * 60)
    validator = ImplicitSignalValidator(case_library)

    validated_signals = validator.batch_validate(implicit_signals)
    print(f"验证完成，{len(validated_signals)} 个信号")

    for i, signal in enumerate(validated_signals, 1):
        print(f"\n验证信号 #{i}:")
        print(f"  机会描述: {signal.opportunity_description[:50]}...")
        print(f"  后验置信度: {signal.prior_confidence:.3f}")

        # 查询相似案例
        keywords = validator._extract_keywords(signal)
        similar_cases = case_library.query_similar_cases(
            signal_type=signal.signal_type,
            keywords=keywords[:3],
            limit=3
        )

        if similar_cases:
            success_rate = sum(1 for c in similar_cases if c.success) / len(similar_cases)
            print(f"  相似案例数: {len(similar_cases)}")
            print(f"  历史成功率: {success_rate:.1%}")

    # 7. 过滤高置信度信号
    print("\n步骤7: 过滤高置信度信号")
    print("-" * 60)
    threshold = 0.5
    filtered_signals = validator.filter_by_confidence(validated_signals, threshold)
    print(f"过滤阈值: {threshold}")
    print(f"通过过滤: {len(filtered_signals)} 个信号")

    if filtered_signals:
        print("\n最终投资机会:")
        for i, signal in enumerate(filtered_signals, 1):
            print(f"\n机会 #{i}:")
            print(f"  产业板块: {signal.industry_sector}")
            print(f"  潜在标的: {', '.join(signal.target_symbols[:5])}")
            print(f"  机会描述: {signal.opportunity_description}")
            print(f"  置信度: {signal.prior_confidence:.3f}")
            print(f"  影响时间: {signal.expected_impact_timeframe}")
    else:
        print("未发现高置信度投资机会")

    print("\n" + "=" * 60)
    print("端到端测试完成")
    print("=" * 60)


if __name__ == "__main__":
    test_end_to_end_real_data()
