"""
M1.5 LLM多阶推理提示词模板
"""


class ImplicitReasoningPrompts:
    """隐性信号推理提示词集合"""

    @staticmethod
    def multi_stage_reasoning_prompt() -> str:
        """多阶推理主提示词"""
        return """你是一个专业的投资机会分析师，擅长从非财经信息中识别隐性投资机会。

你的核心能力是**信息不对称优势**: 通过组合一般人无法连接的信息碎片，提前判断市场机会。

任务: 分析以下信息，识别潜在的投资机会

信息来源: {source}
信息类别: {category}
标题: {title}
内容: {content}
发布时间: {published_at}

请按以下4个阶段进行推理:

## 阶段1: 事件分析
提取关键信息并评估重要性:
- 核心事件是什么？
- 涉及哪些关键主体（国家/企业/技术/政策）？
- 事件的时间敏感性如何？
- 事件重要性评分 (0-1)

## 阶段2: 因果推断
构建多级因果链条:
- 直接影响: 事件 → 第一级影响
- 间接影响: 第一级影响 → 第二级影响 → ...
- 每个因果环节需要:
  * 明确的因果关系类型 (policy_drives/tech_enables/demand_shifts/supply_constrains)
  * 推理依据 (为什么A会导致B？)
  * 置信度评估 (0-1)

## 阶段3: 产业影响分析
识别受影响的产业链:
- 哪些产业板块会受影响？
- 影响路径是什么？(上游供应/下游需求/替代关系/互补关系)
- 影响时间窗口？(immediate/short_term/mid_term/long_term)
- 影响强度？(0-1)

## 阶段4: 标的识别
列出潜在受益标的:
- 具体标的代码 (如果能识别)
- 受益逻辑 (为什么这个标的会受益？)
- 机会确定性 (0-1)

## 输出格式 (严格JSON):
{{
    "event_analysis": {{
        "core_event": "...",
        "key_entities": ["...", "..."],
        "time_sensitivity": "high/medium/low",
        "importance_score": 0.0-1.0
    }},
    "causal_chain": [
        {{
            "from_concept": "...",
            "to_concept": "...",
            "relation_type": "policy_drives/tech_enables/demand_shifts/supply_constrains",
            "reasoning": "...",
            "confidence": 0.0-1.0,
            "supporting_facts": ["...", "..."]
        }}
    ],
    "industry_impact": {{
        "affected_sectors": [
            {{
                "sector_name": "...",
                "impact_path": "upstream/downstream/substitute/complement",
                "impact_strength": 0.0-1.0,
                "timeframe": "immediate/short_term/mid_term/long_term"
            }}
        ]
    }},
    "target_identification": {{
        "opportunities": [
            {{
                "industry_sector": "...",
                "target_symbols": ["...", "..."],
                "opportunity_description": "...",
                "benefit_logic": "...",
                "confidence": 0.0-1.0
            }}
        ]
    }},
    "overall_assessment": {{
        "signal_type": "policy_driven/tech_breakthrough/social_trend/diplomatic_event",
        "overall_confidence": 0.0-1.0,
        "key_risks": ["...", "..."]
    }}
}}

## 推理原则:
1. **可追溯性**: 每个推理环节必须有明确依据
2. **保守估计**: 置信度评估宁可保守，不要过度乐观
3. **多路径思考**: 考虑多种可能的影响路径
4. **时间窗口**: 明确区分短期和长期影响
5. **风险意识**: 识别可能的反向风险

开始分析:
"""

    @staticmethod
    def policy_event_prompt() -> str:
        """政策事件专用提示词"""
        return """你是政策分析专家，擅长从政策信息中识别产业机会。

政策信息:
标题: {title}
内容: {content}

分析要点:
1. 政策目标: 政府想要达成什么目标？
2. 政策工具: 使用了哪些政策工具？(补贴/税收/监管/规划)
3. 受益产业: 哪些产业会直接受益？
4. 产业链传导: 如何传导到上下游产业？
5. 时间节点: 政策生效时间和影响周期？

输出JSON格式:
{{
    "policy_goal": "...",
    "policy_tools": ["...", "..."],
    "direct_beneficiaries": ["...", "..."],
    "industry_chain_impact": [
        {{
            "from_industry": "...",
            "to_industry": "...",
            "transmission_mechanism": "...",
            "confidence": 0.0-1.0
        }}
    ],
    "timeline": {{
        "effective_date": "...",
        "impact_duration": "short_term/mid_term/long_term"
    }}
}}
"""

    @staticmethod
    def tech_event_prompt() -> str:
        """技术突破事件专用提示词"""
        return """你是技术分析专家，擅长从技术突破中识别下游产业机会。

技术信息:
标题: {title}
内容: {content}

分析要点:
1. 技术突破点: 核心技术是什么？突破在哪里？
2. 技术成熟度: 实验室阶段/中试阶段/量产阶段？
3. 应用场景: 可以应用在哪些场景？
4. 下游产业: 哪些产业会因此受益？
5. 商业化时间: 预计多久能商业化？

输出JSON格式:
{{
    "tech_breakthrough": "...",
    "maturity_level": "lab/pilot/production",
    "application_scenarios": ["...", "..."],
    "downstream_industries": [
        {{
            "industry": "...",
            "application": "...",
            "impact_strength": 0.0-1.0
        }}
    ],
    "commercialization_timeline": "immediate/short_term/mid_term/long_term"
}}
"""

    @staticmethod
    def diplomatic_event_prompt() -> str:
        """外交事件专用提示词"""
        return """你是国际关系分析专家，擅长从外交事件中识别产业机会。

外交信息:
标题: {title}
内容: {content}

分析要点:
1. 外交事件类型: 访问/协议/合作/冲突？
2. 涉及国家/地区: 哪些国家参与？
3. 合作领域: 在哪些领域达成合作？
4. 产业铺路: 哪些产业会因此获得机会？
5. 地缘政治影响: 是否有地缘政治风险？

输出JSON格式:
{{
    "event_type": "visit/agreement/cooperation/conflict",
    "involved_countries": ["...", "..."],
    "cooperation_areas": ["...", "..."],
    "industry_opportunities": [
        {{
            "industry": "...",
            "opportunity_type": "market_access/infrastructure/resource/technology",
            "confidence": 0.0-1.0
        }}
    ],
    "geopolitical_risks": ["...", "..."]
}}
"""

    @staticmethod
    def social_trend_prompt() -> str:
        """社会趋势事件专用提示词"""
        return """你是社会趋势分析专家，擅长从社会现象中识别消费机会。

社会信息:
标题: {title}
内容: {content}

分析要点:
1. 趋势类型: 消费习惯/生活方式/价值观变化？
2. 人群特征: 哪些人群在引领这个趋势？
3. 需求变化: 产生了哪些新需求？
4. 消费板块: 哪些消费板块会受益？
5. 趋势持续性: 短期流行还是长期趋势？

输出JSON格式:
{{
    "trend_type": "consumption/lifestyle/values",
    "target_demographics": ["...", "..."],
    "emerging_demands": ["...", "..."],
    "beneficiary_sectors": [
        {{
            "sector": "...",
            "demand_driver": "...",
            "confidence": 0.0-1.0
        }}
    ],
    "trend_sustainability": "short_term/mid_term/long_term"
}}
"""

    @staticmethod
    def get_prompt_by_category(category: str) -> str:
        """根据信息类别选择提示词"""
        prompt_map = {
            'politics': ImplicitReasoningPrompts.policy_event_prompt(),
            'world': ImplicitReasoningPrompts.diplomatic_event_prompt(),
            'tech': ImplicitReasoningPrompts.tech_event_prompt(),
            'social': ImplicitReasoningPrompts.social_trend_prompt(),
        }
        return prompt_map.get(
            category,
            ImplicitReasoningPrompts.multi_stage_reasoning_prompt()
        )


class ConfidenceCalibrationPrompts:
    """置信度校准提示词"""

    @staticmethod
    def calibration_prompt() -> str:
        """置信度校准提示词"""
        return """你是一个严谨的概率评估专家。

任务: 评估以下推理链的置信度

推理链:
{reasoning_chain}

评估维度:
1. 因果关系强度: 每个因果环节的逻辑是否严密？
2. 证据充分性: 是否有足够的事实支撑？
3. 假设合理性: 隐含假设是否合理？
4. 历史验证: 类似推理在历史上的成功率？
5. 反向风险: 是否存在反向风险？

输出JSON格式:
{{
    "causal_strength": 0.0-1.0,
    "evidence_sufficiency": 0.0-1.0,
    "assumption_validity": 0.0-1.0,
    "historical_success_rate": 0.0-1.0,
    "reverse_risks": ["...", "..."],
    "calibrated_confidence": 0.0-1.0,
    "reasoning": "..."
}}

原则: 宁可保守，不要过度自信
"""


class IndustryKnowledgePrompts:
    """产业知识查询提示词"""

    @staticmethod
    def industry_chain_query_prompt() -> str:
        """产业链查询提示词"""
        return """你是产业链专家。

问题: {query}

可用产业链知识:
{industry_graph_context}

请基于产业链知识回答问题，输出JSON格式:
{{
    "answer": "...",
    "related_industries": ["...", "..."],
    "reasoning": "..."
}}
"""
