"""
M1.5 隐性信号推理器接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from m1_5_implicit_reasoner.models import ImplicitSignal, ReasoningChain, CausalLink


class ImplicitSignalInferencer(ABC):
    """
    隐性信号推理器抽象接口

    职责:
    1. 接收M0非财经信息
    2. 执行多阶因果推理
    3. 生成可追溯的推理链
    4. 计算初始置信度
    5. 输出结构化隐性信号供M3验证
    """

    @abstractmethod
    def infer(self, raw_data: Dict) -> List[ImplicitSignal]:
        """
        从原始数据推理隐性信号

        Args:
            raw_data: M0采集的原始数据
                {
                    'source': 'xinhua',
                    'category': 'politics',
                    'title': '...',
                    'content': '...',
                    'published_at': '...'
                }

        Returns:
            隐性信号列表 (可能一条信息产生多个信号)
        """
        pass

    @abstractmethod
    def generate_reasoning_chain(
        self,
        source_event: str,
        target_opportunity: str,
        context: Dict
    ) -> ReasoningChain:
        """
        生成推理链

        Args:
            source_event: 源事件描述
            target_opportunity: 目标机会描述
            context: 上下文信息 (产业链知识、历史案例等)

        Returns:
            完整推理链
        """
        pass

    @abstractmethod
    def calculate_confidence(self, reasoning_chain: ReasoningChain) -> float:
        """
        计算推理链置信度 (先验概率)

        Args:
            reasoning_chain: 推理链

        Returns:
            置信度 [0-1]
        """
        pass

    @abstractmethod
    def identify_targets(
        self,
        industry_sector: str,
        opportunity_type: str,
        context: Dict
    ) -> List[str]:
        """
        识别潜在标的

        Args:
            industry_sector: 产业板块
            opportunity_type: 机会类型
            context: 上下文信息

        Returns:
            标的代码列表
        """
        pass


class LLMImplicitSignalInferencer(ImplicitSignalInferencer):
    """
    基于LLM的隐性信号推理器实现

    使用LLM进行多阶推理:
    1. 事件分析: 提取关键信息
    2. 因果推断: 构建因果链条
    3. 产业影响: 分析产业链影响
    4. 标的识别: 识别具体标的
    """

    def __init__(
        self,
        llm_client,
        industry_graph,
        prompt_template: Optional[str] = None
    ):
        """
        初始化

        Args:
            llm_client: LLM客户端 (OpenAI/Anthropic/本地模型)
            industry_graph: 产业链图谱
            prompt_template: 推理提示词模板
        """
        self.llm_client = llm_client
        self.industry_graph = industry_graph
        self.prompt_template = prompt_template or self._default_prompt_template()

    def infer(self, raw_data: Dict) -> List[ImplicitSignal]:
        """实现推理逻辑"""
        from m1_5_implicit_reasoner.prompts import ImplicitReasoningPrompts
        from m1_5_implicit_reasoner.models import ReasoningStage
        from datetime import datetime
        import uuid

        # 1. 构建推理提示词
        category = raw_data.get('category', 'general')
        prompt_template = ImplicitReasoningPrompts.get_prompt_by_category(category)

        prompt = prompt_template.format(
            source=raw_data.get('source', ''),
            category=category,
            title=raw_data.get('title', ''),
            content=raw_data.get('content', ''),
            published_at=raw_data.get('published_at', '')
        )

        # 2. 调用LLM生成推理
        try:
            llm_response = self.llm_client.chat_json(prompt, temperature=0.7, max_tokens=2000)
        except Exception as e:
            print(f"LLM调用失败: {e}")
            return []

        # 3. 解析LLM输出
        if not llm_response:
            return []

        # 4. 构建ImplicitSignal对象
        implicit_signals = []

        # 提取因果链
        causal_chain_data = llm_response.get('causal_chain', [])
        causal_links = []
        for link_data in causal_chain_data:
            link = CausalLink(
                from_concept=link_data.get('from_concept', ''),
                to_concept=link_data.get('to_concept', ''),
                relation_type=link_data.get('relation_type', ''),
                confidence=link_data.get('confidence', 0.5),
                reasoning=link_data.get('reasoning', ''),
                supporting_facts=link_data.get('supporting_facts', [])
            )
            causal_links.append(link)

        # 构建推理链
        event_analysis = llm_response.get('event_analysis', {})
        industry_impact = llm_response.get('industry_impact', {})
        target_identification = llm_response.get('target_identification', {})
        overall_assessment = llm_response.get('overall_assessment', {})

        reasoning_stages = {
            ReasoningStage.EVENT_ANALYSIS: str(event_analysis),
            ReasoningStage.CAUSAL_INFERENCE: f"{len(causal_links)}个因果环节",
            ReasoningStage.INDUSTRY_IMPACT: str(industry_impact),
            ReasoningStage.TARGET_IDENTIFICATION: str(target_identification)
        }

        # 为每个机会创建隐性信号
        opportunities = target_identification.get('opportunities', [])
        for opp in opportunities:
            chain_id = f"chain_{uuid.uuid4().hex[:8]}"

            reasoning_chain = ReasoningChain(
                chain_id=chain_id,
                source_event=raw_data.get('title', ''),
                target_opportunity=opp.get('opportunity_description', ''),
                causal_links=causal_links,
                reasoning_stages=reasoning_stages,
                overall_confidence=opp.get('confidence', 0.5)
            )

            signal_id = f"implicit_{uuid.uuid4().hex[:8]}"

            signal = ImplicitSignal(
                signal_id=signal_id,
                signal_type=overall_assessment.get('signal_type', 'unknown'),
                source_info=raw_data,
                reasoning_chain=reasoning_chain,
                industry_sector=opp.get('industry_sector', ''),
                target_symbols=opp.get('target_symbols', []),
                opportunity_description=opp.get('opportunity_description', ''),
                prior_confidence=reasoning_chain.get_chain_strength(),
                expected_impact_timeframe=industry_impact.get('affected_sectors', [{}])[0].get('timeframe', 'mid_term') if industry_impact.get('affected_sectors') else 'mid_term'
            )

            implicit_signals.append(signal)

        return implicit_signals

    def generate_reasoning_chain(
        self,
        source_event: str,
        target_opportunity: str,
        context: Dict
    ) -> ReasoningChain:
        """生成推理链"""
        from m1_5_implicit_reasoner.models import ReasoningStage
        from datetime import datetime
        import uuid

        # 构建推理提示词
        prompt = f"""
分析以下事件并生成推理链:

源事件: {source_event}
目标机会: {target_opportunity}

上下文信息:
{context}

请生成从源事件到目标机会的完整因果推理链，输出JSON格式:
{{
    "causal_links": [
        {{
            "from_concept": "...",
            "to_concept": "...",
            "relation_type": "policy_drives/tech_enables/demand_shifts/supply_constrains",
            "reasoning": "...",
            "confidence": 0.0-1.0,
            "supporting_facts": ["...", "..."]
        }}
    ],
    "overall_confidence": 0.0-1.0
}}
"""

        try:
            llm_response = self.llm_client.chat_json(prompt, temperature=0.7)
        except Exception as e:
            print(f"LLM调用失败: {e}")
            return None

        # 解析响应
        causal_links_data = llm_response.get('causal_links', [])
        causal_links = []
        for link_data in causal_links_data:
            link = CausalLink(
                from_concept=link_data.get('from_concept', ''),
                to_concept=link_data.get('to_concept', ''),
                relation_type=link_data.get('relation_type', ''),
                confidence=link_data.get('confidence', 0.5),
                reasoning=link_data.get('reasoning', ''),
                supporting_facts=link_data.get('supporting_facts', [])
            )
            causal_links.append(link)

        chain_id = f"chain_{uuid.uuid4().hex[:8]}"

        reasoning_chain = ReasoningChain(
            chain_id=chain_id,
            source_event=source_event,
            target_opportunity=target_opportunity,
            causal_links=causal_links,
            reasoning_stages={
                ReasoningStage.CAUSAL_INFERENCE: f"{len(causal_links)}个因果环节"
            },
            overall_confidence=llm_response.get('overall_confidence', 0.5)
        )

        return reasoning_chain

    def calculate_confidence(self, reasoning_chain: ReasoningChain) -> float:
        """计算置信度"""
        # 使用推理链强度作为先验概率
        return reasoning_chain.get_chain_strength()

    def identify_targets(
        self,
        industry_sector: str,
        opportunity_type: str,
        context: Dict
    ) -> List[str]:
        """识别标的"""
        # 1. 查询产业链图谱
        if self.industry_graph:
            # 根据产业板块查找节点
            matching_nodes = [
                node for node in self.industry_graph.nodes.values()
                if industry_sector.lower() in node.sector.lower() or
                   industry_sector.lower() in node.name.lower()
            ]

            # 收集所有相关标的
            targets = []
            for node in matching_nodes:
                targets.extend(node.related_symbols)

            if targets:
                return targets[:5]  # 返回前5个

        # 2. 如果图谱查询无结果，使用LLM推理
        prompt = f"""
识别以下投资机会的潜在标的:

产业板块: {industry_sector}
机会类型: {opportunity_type}

上下文信息:
{context}

请列出3-5个最相关的A股标的代码（格式: 600000.SH 或 000000.SZ），输出JSON格式:
{{
    "targets": ["600000.SH", "000000.SZ", ...],
    "reasoning": "..."
}}
"""

        try:
            llm_response = self.llm_client.chat_json(prompt, temperature=0.5)
            return llm_response.get('targets', [])
        except Exception as e:
            print(f"标的识别失败: {e}")
            return []

    def _default_prompt_template(self) -> str:
        """默认推理提示词模板"""
        return """
你是一个专业的投资机会分析师，擅长从非财经信息中识别隐性投资机会。

任务: 分析以下信息，识别潜在的投资机会

信息来源: {source}
信息类别: {category}
标题: {title}
内容: {content}

请按以下步骤进行推理:

1. 事件分析
   - 提取关键信息
   - 识别事件类型 (政策、技术、社会趋势等)
   - 评估事件重要性

2. 因果推断
   - 构建因果链条: 事件 → 直接影响 → 间接影响 → 产业机会
   - 每个因果环节需要说明推理依据
   - 评估每个环节的置信度

3. 产业影响
   - 识别受影响的产业板块
   - 分析影响路径 (上游/下游/替代/互补)
   - 评估影响时间窗口

4. 标的识别
   - 列出潜在受益标的
   - 说明受益逻辑
   - 评估机会确定性

输出格式 (JSON):
{{
    "event_analysis": {{
        "key_points": [...],
        "event_type": "...",
        "importance": 0-1
    }},
    "causal_chain": [
        {{
            "from": "...",
            "to": "...",
            "relation": "...",
            "reasoning": "...",
            "confidence": 0-1
        }}
    ],
    "industry_impact": {{
        "sectors": [...],
        "impact_path": "...",
        "timeframe": "immediate/short_term/mid_term/long_term"
    }},
    "target_identification": {{
        "symbols": [...],
        "opportunity_description": "...",
        "confidence": 0-1
    }}
}}
"""


class RuleBasedImplicitSignalInferencer(ImplicitSignalInferencer):
    """
    基于规则的隐性信号推理器 (简化版本)

    使用预定义规则进行推理:
    - 政策事件 → 产业映射规则
    - 技术突破 → 下游产业规则
    - 社会趋势 → 消费板块规则
    """

    def __init__(self, rule_config: Dict, industry_graph):
        """
        初始化

        Args:
            rule_config: 规则配置
            industry_graph: 产业链图谱
        """
        self.rules = rule_config
        self.industry_graph = industry_graph

    def infer(self, raw_data: Dict) -> List[ImplicitSignal]:
        """基于规则推理"""
        # TODO: 实现规则匹配逻辑
        raise NotImplementedError("待实现")

    def generate_reasoning_chain(
        self,
        source_event: str,
        target_opportunity: str,
        context: Dict
    ) -> ReasoningChain:
        """生成规则推理链"""
        # TODO: 实现规则推理链
        raise NotImplementedError("待实现")

    def calculate_confidence(self, reasoning_chain: ReasoningChain) -> float:
        """计算规则置信度"""
        return reasoning_chain.get_chain_strength()

    def identify_targets(
        self,
        industry_sector: str,
        opportunity_type: str,
        context: Dict
    ) -> List[str]:
        """基于规则识别标的"""
        # TODO: 实现规则标的识别
        raise NotImplementedError("待实现")
