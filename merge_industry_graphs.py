"""
合并产业链图谱数据
"""

import json
from pathlib import Path


def merge_industry_graphs():
    """合并核心图谱和扩展图谱"""

    # 读取核心图谱
    core_path = Path(__file__).parent / "data" / "industry_graph_core.json"
    with open(core_path, 'r', encoding='utf-8') as f:
        core_data = json.load(f)

    # 读取扩展图谱
    extended_path = Path(__file__).parent / "data" / "industry_graph_extended.json"
    with open(extended_path, 'r', encoding='utf-8') as f:
        extended_data = json.load(f)

    # 合并
    merged_data = {
        'nodes': core_data['nodes'] + extended_data['nodes'],
        'relations': core_data['relations'] + extended_data['relations'],
        'policy_mappings': core_data['policy_mappings'] + extended_data['policy_mappings'],
        'event_mappings': core_data['event_mappings'] + extended_data['event_mappings']
    }

    # 保存合并后的图谱
    merged_path = Path(__file__).parent / "data" / "industry_graph_full.json"
    with open(merged_path, 'w', encoding='utf-8') as f:
        json.dump(merged_data, f, ensure_ascii=False, indent=2)

    print(f"合并完成:")
    print(f"  节点数: {len(merged_data['nodes'])}")
    print(f"  关系数: {len(merged_data['relations'])}")
    print(f"  政策映射数: {len(merged_data['policy_mappings'])}")
    print(f"  事件映射数: {len(merged_data['event_mappings'])}")
    print(f"\n保存到: {merged_path}")


if __name__ == "__main__":
    merge_industry_graphs()
