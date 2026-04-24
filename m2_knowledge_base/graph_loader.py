"""
产业链图谱数据加载工具
"""

import json
from pathlib import Path
from m2_knowledge_base.industry_graph import IndustryGraph


def load_core_industry_graph() -> IndustryGraph:
    """
    加载核心产业链图谱数据

    Returns:
        IndustryGraph实例
    """
    data_path = Path(__file__).parent.parent / "data" / "industry_graph_core.json"

    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return IndustryGraph.from_dict(data)


def save_industry_graph(graph: IndustryGraph, filename: str = "industry_graph_core.json"):
    """
    保存产业链图谱数据

    Args:
        graph: IndustryGraph实例
        filename: 保存文件名
    """
    data_path = Path(__file__).parent.parent / "data" / filename
    data_path.parent.mkdir(parents=True, exist_ok=True)

    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(graph.to_dict(), f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # 测试加载
    graph = load_core_industry_graph()
    print(f"加载产业链图谱:")
    print(f"  节点数: {len(graph.nodes)}")
    print(f"  关系数: {len(graph.relations)}")
    print(f"  政策映射数: {len(graph.policy_mappings)}")
    print(f"  事件映射数: {len(graph.event_mappings)}")

    # 测试查询
    print("\n测试政策查询:")
    results = graph.find_industries_by_policy("支持光伏产业发展", threshold=0.5)
    for node, confidence in results[:3]:
        print(f"  {node.name} (置信度: {confidence:.2f})")

    print("\n测试事件查询:")
    results = graph.find_industries_by_event(
        "tech_breakthrough",
        "钙钛矿电池效率突破",
        threshold=0.5
    )
    for node, confidence, template in results[:3]:
        print(f"  {node.name} (置信度: {confidence:.2f})")
