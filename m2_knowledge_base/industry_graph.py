"""
产业链图谱数据模型和查询接口
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from enum import Enum


class RelationType(Enum):
    """产业链关系类型"""
    UPSTREAM = "upstream"  # 上游供应
    DOWNSTREAM = "downstream"  # 下游需求
    SUBSTITUTE = "substitute"  # 替代关系
    COMPLEMENT = "complement"  # 互补关系
    POLICY_DRIVEN = "policy_driven"  # 政策驱动
    TECH_ENABLED = "tech_enabled"  # 技术赋能


@dataclass
class IndustryNode:
    """产业节点"""
    node_id: str
    name: str  # 产业名称
    sector: str  # 所属板块
    keywords: List[str] = field(default_factory=list)  # 关键词
    related_symbols: List[str] = field(default_factory=list)  # 相关标的
    description: str = ""


@dataclass
class IndustryRelation:
    """产业关系"""
    from_node: str  # 起始节点ID
    to_node: str  # 目标节点ID
    relation_type: RelationType
    strength: float  # 关系强度 [0-1]
    description: str = ""
    supporting_facts: List[str] = field(default_factory=list)


@dataclass
class PolicyIndustryMapping:
    """政策-产业映射"""
    policy_keywords: List[str]  # 政策关键词
    target_industries: List[str]  # 目标产业节点ID
    impact_type: str  # 影响类型: direct_support, indirect_benefit, regulatory_change
    confidence: float  # 映射置信度


@dataclass
class EventIndustryMapping:
    """事件-产业映射"""
    event_type: str  # 事件类型: tech_breakthrough, diplomatic_visit, social_trend
    event_keywords: List[str]
    target_industries: List[str]
    reasoning_template: str  # 推理模板
    confidence: float


class IndustryGraph:
    """
    产业链图谱

    功能:
    1. 存储产业节点和关系
    2. 查询上下游关系
    3. 政策-产业映射
    4. 事件-产业映射
    5. 标的识别
    """

    def __init__(self):
        self.nodes: Dict[str, IndustryNode] = {}
        self.relations: List[IndustryRelation] = []
        self.policy_mappings: List[PolicyIndustryMapping] = []
        self.event_mappings: List[EventIndustryMapping] = []

    def add_node(self, node: IndustryNode):
        """添加产业节点"""
        self.nodes[node.node_id] = node

    def add_relation(self, relation: IndustryRelation):
        """添加产业关系"""
        self.relations.append(relation)

    def add_policy_mapping(self, mapping: PolicyIndustryMapping):
        """添加政策映射"""
        self.policy_mappings.append(mapping)

    def add_event_mapping(self, mapping: EventIndustryMapping):
        """添加事件映射"""
        self.event_mappings.append(mapping)

    def get_upstream_industries(
        self,
        node_id: str,
        max_depth: int = 2
    ) -> List[IndustryNode]:
        """获取上游产业"""
        result = []
        visited = set()
        self._traverse_relations(
            node_id,
            RelationType.UPSTREAM,
            max_depth,
            result,
            visited
        )
        return result

    def get_downstream_industries(
        self,
        node_id: str,
        max_depth: int = 2
    ) -> List[IndustryNode]:
        """获取下游产业"""
        result = []
        visited = set()
        self._traverse_relations(
            node_id,
            RelationType.DOWNSTREAM,
            max_depth,
            result,
            visited
        )
        return result

    def find_industries_by_policy(
        self,
        policy_text: str,
        threshold: float = 0.5
    ) -> List[tuple[IndustryNode, float]]:
        """
        根据政策文本查找相关产业

        Args:
            policy_text: 政策文本
            threshold: 置信度阈值

        Returns:
            (产业节点, 置信度) 列表
        """
        results = []
        policy_lower = policy_text.lower()

        for mapping in self.policy_mappings:
            # 关键词匹配
            match_count = sum(
                1 for kw in mapping.policy_keywords
                if kw.lower() in policy_lower
            )

            if match_count > 0:
                match_score = match_count / len(mapping.policy_keywords)
                confidence = mapping.confidence * match_score

                if confidence >= threshold:
                    for industry_id in mapping.target_industries:
                        if industry_id in self.nodes:
                            results.append((self.nodes[industry_id], confidence))

        # 按置信度排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def find_industries_by_event(
        self,
        event_type: str,
        event_text: str,
        threshold: float = 0.5
    ) -> List[tuple[IndustryNode, float, str]]:
        """
        根据事件查找相关产业

        Args:
            event_type: 事件类型
            event_text: 事件文本
            threshold: 置信度阈值

        Returns:
            (产业节点, 置信度, 推理模板) 列表
        """
        results = []
        event_lower = event_text.lower()

        for mapping in self.event_mappings:
            if mapping.event_type != event_type:
                continue

            # 关键词匹配
            match_count = sum(
                1 for kw in mapping.event_keywords
                if kw.lower() in event_lower
            )

            if match_count > 0:
                match_score = match_count / len(mapping.event_keywords)
                confidence = mapping.confidence * match_score

                if confidence >= threshold:
                    for industry_id in mapping.target_industries:
                        if industry_id in self.nodes:
                            results.append((
                                self.nodes[industry_id],
                                confidence,
                                mapping.reasoning_template
                            ))

        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def get_industry_symbols(self, node_id: str) -> List[str]:
        """获取产业相关标的"""
        if node_id in self.nodes:
            return self.nodes[node_id].related_symbols
        return []

    def find_impact_path(
        self,
        from_node_id: str,
        to_node_id: str,
        max_depth: int = 3
    ) -> Optional[List[IndustryRelation]]:
        """
        查找产业影响路径

        Args:
            from_node_id: 起始产业
            to_node_id: 目标产业
            max_depth: 最大深度

        Returns:
            关系路径 (如果存在)
        """
        # BFS查找最短路径
        from collections import deque

        queue = deque([(from_node_id, [])])
        visited = {from_node_id}

        while queue:
            current_id, path = queue.popleft()

            if len(path) >= max_depth:
                continue

            # 查找所有出边
            for relation in self.relations:
                if relation.from_node != current_id:
                    continue

                next_id = relation.to_node
                new_path = path + [relation]

                if next_id == to_node_id:
                    return new_path

                if next_id not in visited:
                    visited.add(next_id)
                    queue.append((next_id, new_path))

        return None

    def _traverse_relations(
        self,
        node_id: str,
        relation_type: RelationType,
        max_depth: int,
        result: List[IndustryNode],
        visited: Set[str],
        current_depth: int = 0
    ):
        """递归遍历关系"""
        if current_depth >= max_depth or node_id in visited:
            return

        visited.add(node_id)

        for relation in self.relations:
            if relation.relation_type != relation_type:
                continue

            if relation.from_node == node_id:
                target_id = relation.to_node
                if target_id in self.nodes and target_id not in visited:
                    result.append(self.nodes[target_id])
                    self._traverse_relations(
                        target_id,
                        relation_type,
                        max_depth,
                        result,
                        visited,
                        current_depth + 1
                    )

    def to_dict(self) -> Dict:
        """导出为字典格式"""
        return {
            'nodes': [
                {
                    'node_id': node.node_id,
                    'name': node.name,
                    'sector': node.sector,
                    'keywords': node.keywords,
                    'related_symbols': node.related_symbols,
                    'description': node.description
                }
                for node in self.nodes.values()
            ],
            'relations': [
                {
                    'from': rel.from_node,
                    'to': rel.to_node,
                    'type': rel.relation_type.value,
                    'strength': rel.strength,
                    'description': rel.description
                }
                for rel in self.relations
            ],
            'policy_mappings': [
                {
                    'policy_keywords': mapping.policy_keywords,
                    'target_industries': mapping.target_industries,
                    'impact_type': mapping.impact_type,
                    'confidence': mapping.confidence
                }
                for mapping in self.policy_mappings
            ],
            'event_mappings': [
                {
                    'event_type': mapping.event_type,
                    'event_keywords': mapping.event_keywords,
                    'target_industries': mapping.target_industries,
                    'reasoning_template': mapping.reasoning_template,
                    'confidence': mapping.confidence
                }
                for mapping in self.event_mappings
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'IndustryGraph':
        """从字典加载"""
        graph = cls()

        # 加载节点
        for node_data in data.get('nodes', []):
            node = IndustryNode(
                node_id=node_data['node_id'],
                name=node_data['name'],
                sector=node_data['sector'],
                keywords=node_data.get('keywords', []),
                related_symbols=node_data.get('related_symbols', []),
                description=node_data.get('description', '')
            )
            graph.add_node(node)

        # 加载关系
        for rel_data in data.get('relations', []):
            relation = IndustryRelation(
                from_node=rel_data['from'],
                to_node=rel_data['to'],
                relation_type=RelationType(rel_data['type']),
                strength=rel_data['strength'],
                description=rel_data.get('description', '')
            )
            graph.add_relation(relation)

        # 加载政策映射
        for mapping_data in data.get('policy_mappings', []):
            mapping = PolicyIndustryMapping(
                policy_keywords=mapping_data['policy_keywords'],
                target_industries=mapping_data['target_industries'],
                impact_type=mapping_data['impact_type'],
                confidence=mapping_data['confidence']
            )
            graph.add_policy_mapping(mapping)

        # 加载事件映射
        for mapping_data in data.get('event_mappings', []):
            mapping = EventIndustryMapping(
                event_type=mapping_data['event_type'],
                event_keywords=mapping_data['event_keywords'],
                target_industries=mapping_data['target_industries'],
                reasoning_template=mapping_data['reasoning_template'],
                confidence=mapping_data['confidence']
            )
            graph.add_event_mapping(mapping)

        return graph

    @classmethod
    def load_from_file(cls, filepath: str) -> 'IndustryGraph':
        """从JSON文件加载图谱"""
        import json
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)
