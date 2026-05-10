"""
m3_judgment/judgment_engine.py — 机会判断引擎

核心逻辑：
  Step A（信号场景识别）→ Step B（机会升级判断）
  输出 List[OpportunityObject]，空列表是合法输出。

设计原则见 PRINCIPLES.md。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.schemas import (
    MarketSignal,
    OpportunityObject,
    OpportunityScore,
    PriorityLevel,
    Direction,
    TimeWindow,
    InferredEvent,
    CaseRecord,
)
from core.llm_client import LLMClient
from m2_storage.signal_store import SignalStore
from m3_judgment.prompt_templates import (
    STEP_A_SYSTEM_PROMPT,
    STEP_A_USER_PROMPT,
    STEP_B_SYSTEM_PROMPT,
    STEP_B_USER_PROMPT,
)
from m3_judgment.sector_knowledge import SectorKnowledgeBase

# Phase 3.5: Import ImplicitSignal adapter
try:
    from m3_judgment.implicit_signal_adapter import ImplicitSignalAdapter
    from m1_5_implicit_reasoner.models import ImplicitSignal
    IMPLICIT_SIGNAL_SUPPORT = True
except ImportError:
    IMPLICIT_SIGNAL_SUPPORT = False
    ImplicitSignalAdapter = None
    ImplicitSignal = None

logger = logging.getLogger(__name__)

SMALL_BATCH_THRESHOLD = 10  # 小批次直接全量送 Step B
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class JudgmentEngine:
    """机会判断引擎

    流程：
      1. 小批次（≤SMALL_BATCH_THRESHOLD）：跳过 Step A，直接 Step B
      2. 大批次：Step A 先识别场景，再对每个场景跑 Step B

    "不构成机会"是合法输出，返回空列表，不抛异常。
    """

    def __init__(self, llm_client: Optional[LLMClient] = None, signal_store: Optional[SignalStore] = None, version: str = "v1.0", m13_agent=None):
        self.llm = llm_client or LLMClient()
        self.signal_store = signal_store or SignalStore()
        self.version = version
        self.m13_agent = m13_agent  # M13调研代理
        self.sector_knowledge = SectorKnowledgeBase()  # 板块知识库

    def judge(
        self,
        signals: List[MarketSignal],
        historical_signals: Optional[List[MarketSignal]] = None,
        batch_id: Optional[str] = None,
    ) -> List[OpportunityObject]:
        """主入口：信号列表 → 机会列表（可为空）

        Args:
            signals: 当前批次信号
            historical_signals: 从 M2 Signal Store 检索的历史相关信号（可选）
            batch_id: 批次标识

        Returns:
            List[OpportunityObject]，空列表表示当前批次不构成机会
        """
        if not signals:
            logger.info("[M3] 空信号列表，跳过判断")
            return []

        all_signals = signals + (historical_signals or [])
        batch_id = batch_id or f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(
            f"[M3] 开始判断 | 当前批次={len(signals)} 历史信号={len(historical_signals or [])} "
            f"合计={len(all_signals)} | batch_id={batch_id}"
        )

        # 小批次快速路径
        if len(all_signals) <= SMALL_BATCH_THRESHOLD:
            logger.info(f"[M3] 小批次（{len(all_signals)}条），跳过 Step A 直接 Step B")
            scenarios = [{"scenario_id": "direct", "description": "全量信号直接判断", "signal_ids": [s.signal_id for s in all_signals]}]
        else:
            scenarios = self._identify_scenarios(all_signals)
            if not scenarios:
                logger.info("[M3] Step A 未识别出有效场景，不构成机会")
                return []

        # Inference Engine: 推理未来事件和检索相似案例
        inferred_events = self._infer_future_events(all_signals)
        similar_cases = self._retrieve_similar_cases(all_signals, limit=5)

        # Step B：对每个场景判断是否构成机会
        opportunities = []
        for scenario in scenarios:
            result = self._judge_opportunity(scenario, all_signals, batch_id, inferred_events, similar_cases)
            if result is not None:
                # M13深度验证（如果生成了机会且置信度中等）
                if self.m13_agent and hasattr(result, 'opportunity_score') and result.opportunity_score.confidence_score > 0.5:
                    try:
                        # 对机会中的每个标的进行深度调研
                        for instrument in result.target_instruments[:2]:  # 限制前2个标的
                            research = self.m13_agent.deep_research(
                                symbol=instrument,
                                context=result.opportunity_thesis
                            )

                            # 调整置信度（限制调整幅度，避免过度降低）
                            # confidence_delta范围：-0.3 ~ +0.3，我们限制为 -0.15 ~ +0.15
                            adjusted_delta = max(-0.15, min(0.15, research.confidence_delta))
                            result.opportunity_score.confidence_score += adjusted_delta

                            # 如果发现重大利空，降低置信度并添加到warnings
                            if research.has_major_negative:
                                result.opportunity_score.confidence_score *= 0.7

                                # 将重大利空信息添加到warnings
                                if not result.warnings:
                                    result.warnings = []
                                result.warnings.append(
                                    f"⚠️ M13调研发现重大利空 ({instrument}): {research.summary[:100]}"
                                )

                                logger.warning(
                                    f"[M3+M13] 发现重大利空: {instrument} - {research.summary}"
                                )

                            # 确保置信度在有效范围内 [0, 1]
                            result.opportunity_score.confidence_score = max(0.0, min(1.0, result.opportunity_score.confidence_score))

                            # 添加M13风险因素到counter_evidence
                            if research.risk_factors:
                                if not result.counter_evidence:
                                    result.counter_evidence = []
                                for risk in research.risk_factors[:3]:  # 最多添加3个风险
                                    result.counter_evidence.append(f"[M13] {risk}")

                            # 添加调研摘要到机会描述
                            if research.summary and hasattr(result, 'opportunity_thesis'):
                                result.opportunity_thesis += f"\n\n【M13调研】{research.summary}"

                            logger.info(
                                f"[M3+M13] 深度调研完成: {instrument} "
                                f"- 置信度调整: {result.opportunity_score.confidence_score:.2f}"
                            )

                    except Exception as e:
                        # M13失败不影响主流程
                        logger.warning(f"[M3+M13] 调研失败: {e}")

                # 无条件钳制置信度到有效范围 [0, 1]（防止LLM输出异常值）
                result.opportunity_score.confidence_score = max(0.0, min(1.0, result.opportunity_score.confidence_score))

                opportunities.append(result)

        logger.info(f"[M3] 判断完成 | 识别机会={len(opportunities)} 个")
        return opportunities

    def judge_implicit_signals(
        self,
        implicit_signals: List,
        batch_id: Optional[str] = None,
        lookback_days: int = 90,
    ) -> List[OpportunityObject]:
        """判断隐性信号是否构成机会 (Phase 3.5)

        流程:
        1. 转换ImplicitSignal为MarketSignal格式
        2. 从M2查询相关历史隐性信号（同板块、同类型）
        3. 调用现有的judge()方法
        4. 返回OpportunityObject列表

        Args:
            implicit_signals: ImplicitSignal对象列表
            batch_id: 批次标识
            lookback_days: 历史信号回溯天数

        Returns:
            List[OpportunityObject]，空列表表示不构成机会
        """
        if not IMPLICIT_SIGNAL_SUPPORT:
            logger.error("[M3] ImplicitSignal支持未启用，无法处理隐性信号")
            return []

        if not implicit_signals:
            logger.info("[M3] 空隐性信号列表，跳过判断")
            return []

        batch_id = batch_id or f"implicit_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(
            f"[M3] 开始判断隐性信号 | 当前批次={len(implicit_signals)} | batch_id={batch_id}"
        )

        # 1. 转换为MarketSignal格式
        market_signals = []
        signal_id_map = {}  # 保存原始signal_id映射

        for imp_sig in implicit_signals:
            try:
                market_sig = ImplicitSignalAdapter.to_market_signal(imp_sig)
                market_signals.append(market_sig)
                signal_id_map[market_sig.signal_id] = imp_sig.signal_id
            except Exception as e:
                logger.error(f"[M3] 转换隐性信号失败 {imp_sig.signal_id}: {e}")

        if not market_signals:
            logger.warning("[M3] 所有隐性信号转换失败")
            return []

        logger.info(f"[M3] 成功转换 {len(market_signals)} 个隐性信号")

        # 2. 查询历史隐性信号作为上下文
        from datetime import timedelta
        historical_implicit = []

        for imp_sig in implicit_signals:
            try:
                hist = self.signal_store.query_implicit_signals(
                    start_time=datetime.now() - timedelta(days=lookback_days),
                    end_time=datetime.now(),
                    industry_sector=imp_sig.industry_sector,
                    signal_type=imp_sig.signal_type,
                    min_confidence=0.6,
                    limit=20,
                )
                historical_implicit.extend(hist)
            except Exception as e:
                logger.warning(f"[M3] 查询历史隐性信号失败: {e}")

        # 去重
        seen_ids = set()
        unique_historical = []
        for sig in historical_implicit:
            if sig.signal_id not in seen_ids:
                seen_ids.add(sig.signal_id)
                unique_historical.append(sig)

        logger.info(f"[M3] 查询到 {len(unique_historical)} 条历史隐性信号")

        # 转换历史信号
        historical_market_signals = []
        for hist_sig in unique_historical:
            try:
                hist_market = ImplicitSignalAdapter.to_market_signal(hist_sig)
                historical_market_signals.append(hist_market)
            except Exception as e:
                logger.warning(f"[M3] 转换历史信号失败: {e}")

        # 3. 调用现有判断逻辑
        opportunities = self.judge(
            signals=market_signals,
            historical_signals=historical_market_signals,
            batch_id=batch_id,
        )

        # 4. 在metadata中添加原始signal_id追溯
        for opp in opportunities:
            if not opp.metadata:
                opp.metadata = {}
            opp.metadata["source_signal_ids"] = [
                signal_id_map.get(sig_id, sig_id)
                for sig_id in opp.signal_ids
            ]
            opp.metadata["signal_source"] = "implicit"

        logger.info(
            f"[M3] 隐性信号判断完成 | 识别机会={len(opportunities)} 个"
        )

        return opportunities

    # ------------------------------------------------------------------
    # Step A：场景识别
    # ------------------------------------------------------------------

    def _identify_scenarios(self, signals: List[MarketSignal]) -> List[dict]:
        """Step A：识别信号中可能形成机会的场景组合

        Returns:
            [{"scenario_id": str, "description": str, "signal_ids": List[str]}, ...]
        """
        signals_summary = self._signals_to_summary(signals)

        messages = [
            {"role": "system", "content": STEP_A_SYSTEM_PROMPT},
            {"role": "user", "content": STEP_A_USER_PROMPT.format(signals_summary=signals_summary)},
        ]

        try:
            raw = self.llm.chat_completion(messages, module_name="m3_judgment")
            try:
                scenarios = self._parse_json_response(raw, expected_key="scenarios")
            except Exception as parse_err:
                logger.warning(f"[M3 Step A] 首次 JSON 解析失败，尝试修复重试: {parse_err}")
                # 重试：要求LLM返回纯JSON
                repair_messages = messages + [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": (
                            "你上一条回复不是合法 JSON。请只返回一个 JSON 对象，格式为：\n"
                            '{"scenarios": [{"scenario_id": "...", "description": "...", "signal_ids": [...]}]}\n'
                            "不要 markdown、不要解释、不要前后缀文本。"
                        ),
                    },
                ]
                repaired_raw = self.llm.chat_completion(repair_messages, module_name="m3_judgment")
                scenarios = self._parse_json_response(repaired_raw, expected_key="scenarios")

            logger.info(f"[M3 Step A] 识别场景数={len(scenarios)}")
            return scenarios
        except Exception as e:
            logger.error(f"[M3 Step A] LLM 调用失败: {e}")
            return []

    # ------------------------------------------------------------------
    # Inference Engine (新增)
    # ------------------------------------------------------------------

    def _infer_future_events(self, signals: List[MarketSignal]) -> List[InferredEvent]:
        """推理未来事件（基于因果图谱和历史案例）

        流程：
          1. 从M2查询匹配的因果模式
          2. 用LLM评估当前信号与历史模式的相似度
          3. 计算未来事件的发生概率和时间窗口

        Returns:
            List[InferredEvent]，可能为空
        """
        if not signals:
            return []

        # Query causal patterns from M2
        patterns = self.signal_store.query_causal_patterns(min_probability=0.5, min_confidence=0.5)
        if not patterns:
            logger.info("[M3 Inference] 因果图谱为空，跳过推理")
            return []

        # Build signal summary for LLM
        signal_features = []
        for s in signals:
            signal_features.append(f"- {s.signal_type.value}: {s.signal_label} ({s.description[:100]})")
        signal_summary = "\n".join(signal_features)

        # Build pattern summary
        pattern_summary = []
        for p in patterns:
            pattern_summary.append(
                f"模式ID: {p.pattern_id}\n"
                f"前置信号: {', '.join(p.precursor_signals)}\n"
                f"后续事件: {p.consequent_event}\n"
                f"概率: {p.probability:.0%}\n"
                f"平均提前时间: {p.avg_lead_time_days}天\n"
                f"置信度: {p.confidence:.0%}\n"
            )
        patterns_text = "\n---\n".join(pattern_summary)

        # LLM inference prompt
        inference_prompt = f"""你是一个因果推理引擎。基于当前信号和历史因果模式，推断未来可能发生的事件。

当前信号：
{signal_summary}

历史因果模式：
{patterns_text}

任务：
1. 识别当前信号与哪些历史模式匹配（相似度>60%）
2. 对于匹配的模式，推断未来事件的发生概率和时间窗口
3. 输出JSON格式：

{{
  "inferred_events": [
    {{
      "event_description": "事件描述",
      "probability": 0.75,
      "time_window": "2周内",
      "reasoning": "推理依据",
      "supporting_pattern_ids": ["pattern_id1", "pattern_id2"],
      "confidence": 0.80
    }}
  ]
}}

如果没有匹配的模式，返回空数组。只返回JSON，不要解释。"""

        try:
            messages = [
                {"role": "system", "content": "你是因果推理专家，基于历史模式推断未来事件。"},
                {"role": "user", "content": inference_prompt}
            ]
            raw = self.llm.chat_completion(messages, module_name="m3_inference")
            data = self._parse_json_response(raw, expected_key="inferred_events")

            # Build InferredEvent objects
            inferred_events = []
            for item in data:
                event = InferredEvent(
                    event_id=f"inferred_{uuid.uuid4().hex[:8]}",
                    event_description=item.get("event_description", ""),
                    probability=float(item.get("probability", 0.5)),
                    time_window=item.get("time_window", "未知"),
                    reasoning=item.get("reasoning", ""),
                    supporting_pattern_ids=item.get("supporting_pattern_ids", []),
                    supporting_cases=[],
                    inferred_at=datetime.now(),
                    confidence=float(item.get("confidence", 0.5)),
                )
                inferred_events.append(event)

            logger.info(f"[M3 Inference] 推理未来事件数={len(inferred_events)}")
            return inferred_events

        except Exception as e:
            logger.error(f"[M3 Inference] 推理失败: {e}")
            return []

    def _retrieve_similar_cases(self, signals: List[MarketSignal], limit: int = 5) -> List[CaseRecord]:
        """检索相似历史案例

        Args:
            signals: 当前信号列表
            limit: 返回数量

        Returns:
            List[CaseRecord]，可能为空
        """
        if not signals:
            return []

        # Tag synonym mapping for better matching
        TAG_SYNONYMS = {
            "降准": ["降准", "货币政策", "流动性"],
            "降息": ["降息", "货币政策", "利率", "LPR"],
            "政策宽松": ["政策宽松", "货币政策", "政策利好"],
            "通缩压力": ["通缩压力", "CPI", "通缩"],
            "新能源": ["新能源", "政策利好", "补贴"],
            "半导体": ["半导体", "芯片", "技术突破"],
            "业绩": ["业绩预增", "业绩爆雷", "超预期"],
            "地缘政治": ["地缘政治", "避险", "黄金"],
            "北向资金": ["北向资金", "外资", "白马股"],
            "监管": ["监管政策", "风险规避"],
            "并购": ["并购重组", "资产注入", "小盘股"],
            "技术突破": ["技术突破", "放量", "趋势跟踪"],
        }

        # Extract tags from signals with synonym expansion
        tags = set()
        for s in signals:
            text = s.signal_label + " " + s.description

            # Check each keyword and add synonyms
            for keyword, synonyms in TAG_SYNONYMS.items():
                if keyword in text:
                    tags.update(synonyms)

            # Direct keyword extraction (fallback)
            for keyword in ["降准", "降息", "政策", "CPI", "新能源", "半导体", "业绩",
                           "地缘", "北向", "监管", "并购", "技术"]:
                if keyword in text:
                    tags.add(keyword)

        if not tags:
            logger.info("[M3 Case Retrieval] 无法提取标签，跳过案例检索")
            return []

        tags_list = list(tags)
        logger.info(f"[M3 Case Retrieval] 提取标签: {tags_list[:10]}...")

        # Query similar cases from M2
        try:
            cases = self.signal_store.query_similar_cases(tags=tags_list, limit=limit)
            logger.info(f"[M3 Case Retrieval] 检索相似案例数={len(cases)}")
            return cases
        except Exception as e:
            logger.error(f"[M3 Case Retrieval] 检索失败: {e}")
            return []

    # ------------------------------------------------------------------
    # Step B：机会升级判断
    # ------------------------------------------------------------------

    def _judge_opportunity(
        self,
        scenario: dict,
        all_signals: List[MarketSignal],
        batch_id: str,
        inferred_events: Optional[List[InferredEvent]] = None,
        similar_cases: Optional[List[CaseRecord]] = None,
    ) -> Optional[OpportunityObject]:
        """Step B：判断一个场景是否构成机会

        Args:
            scenario: 场景描述
            all_signals: 所有信号
            batch_id: 批次ID
            inferred_events: 推理的未来事件（新增）
            similar_cases: 相似历史案例（新增）

        Returns:
            OpportunityObject（构成机会）或 None（不构成）
        """
        # 获取场景关联信号
        scenario_signal_ids = set(scenario.get("signal_ids", []))
        scenario_signals = [s for s in all_signals if s.signal_id in scenario_signal_ids] or all_signals

        signals_detail = self._signals_to_detail(scenario_signals)

        # 提取板块/概念/公司名称，查询知识库
        sectors = self.sector_knowledge.extract_sectors_from_signals(scenario_signals)
        sector_stocks_info = self.sector_knowledge.get_leading_stocks(sectors, top_n=5)
        sector_knowledge_text = self.sector_knowledge.format_for_prompt(sector_stocks_info)

        # 同时提取所有affected_instruments，预先解析为股票代码（供LLM参考）
        all_instruments = []
        for sig in scenario_signals:
            all_instruments.extend(sig.affected_instruments)
        resolved_instruments = self.sector_knowledge.resolve_instruments(all_instruments)

        if resolved_instruments:
            sector_knowledge_text += f"\n\n**信号中直接提到的标的（已解析为股票代码）**: {', '.join(resolved_instruments[:10])}"

        # Build inference context
        inference_context = ""

        # 注入板块知识库信息
        if sector_knowledge_text:
            inference_context += "\n\n" + sector_knowledge_text
        if inferred_events:
            inference_context += "\n\n## 推理的未来事件\n\n"
            for event in inferred_events:
                inference_context += (
                    f"- **{event.event_description}**\n"
                    f"  - 概率: {event.probability:.0%}\n"
                    f"  - 时间窗口: {event.time_window}\n"
                    f"  - 推理依据: {event.reasoning}\n"
                    f"  - 置信度: {event.confidence:.0%}\n\n"
                )

        if similar_cases:
            inference_context += "\n\n## 相似历史案例\n\n"
            for case in similar_cases:
                inference_context += (
                    f"- **{case.case_id}** ({case.date_range_start.date()} ~ {case.date_range_end.date()})\n"
                    f"  - 信号序列: {', '.join(case.signal_sequence[:3])}...\n"
                    f"  - 演化: {case.evolution[:100]}...\n"
                    f"  - 结果: {case.outcome.get('event_occurred', 'N/A')}\n"
                    f"  - 经验教训: {case.lessons[:100]}...\n\n"
                )

        messages = [
            {"role": "system", "content": STEP_B_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": STEP_B_USER_PROMPT.format(
                    scenario_description=scenario.get("description", ""),
                    signals_detail=signals_detail,
                ) + inference_context,
            },
        ]

        try:
            raw = self.llm.chat_completion(messages, module_name="m3_judgment")
            try:
                data = self._parse_json_response(raw, expected_key=None)
            except Exception as parse_err:
                logger.warning(f"[M3 Step B] 首次 JSON 解析失败，尝试定向修复重试: {parse_err}")
                self._write_debug_anchor(batch_id, scenario, raw, parse_err)
                repair_messages = messages + [
                    {"role": "assistant", "content": raw},
                    {
                        "role": "user",
                        "content": (
                            "你上一条回复不是合法 JSON。请只返回一个 JSON 对象，不要 markdown、不要解释、不要前后缀文本。"
                            "必须包含 is_opportunity 字段；如果为 true，请补全构造机会所需字段。"
                        ),
                    },
                ]
                repaired_raw = self.llm.chat_completion(repair_messages, module_name="m3_judgment")
                data = self._parse_json_response(repaired_raw, expected_key=None)
                raw = repaired_raw

            # LLM 明确判断不构成机会
            if data.get("is_opportunity") is False:
                reason = data.get("reason", "LLM 判断信号不足以构成机会")
                logger.info(f"[M3 Step B] 场景不构成机会 | reason={reason}")
                return None

            try:
                return self._build_opportunity(data, scenario_signals, batch_id, inferred_events, similar_cases)
            except Exception as build_err:
                logger.error(
                    "[M3 Step B] LLM 已返回机会对象，但构建 OpportunityObject 失败 | "
                    f"title={data.get('opportunity_title')} | error={build_err} | raw_keys={list(data.keys())}"
                )
                self._write_debug_anchor(batch_id, scenario, raw, build_err)
                return None

        except Exception as e:
            logger.error(f"[M3 Step B] LLM 调用或解析失败: {e}")
            self._write_debug_anchor(batch_id, scenario, None, e)
            return None

    # ------------------------------------------------------------------
    # 评分→优先级映射
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_sentiment_context(signals: List[MarketSignal]) -> Optional[dict]:
        """从信号列表中提取情绪信号上下文。

        Returns:
            {"fear_greed_index": float, "sentiment_label": str, "signal_ids": [str]}
            或 None（无情绪信号时）
        """
        sentiment_signals = [s for s in signals if s.signal_type.value == "sentiment"]
        if not sentiment_signals:
            return None

        fg_indices = []
        label = "neutral"
        sig_ids = []
        for s in sentiment_signals:
            sig_ids.append(s.signal_id)
            desc = s.description or ""
            if "恐贪指数" in desc:
                import re
                m = re.search(r"恐贪指数\D*(\d+\.?\d*)", desc)
                if m:
                    fg_indices.append(float(m.group(1)))
            label_text = s.signal_label or ""
            for candidate in ["极度贪婪", "贪婪", "极度恐惧", "恐惧", "中性"]:
                if candidate in label_text:
                    label = candidate
                    break

        fg = fg_indices[0] if fg_indices else 50.0
        return {
            "fear_greed_index": fg,
            "sentiment_label": label,
            "signal_ids": sig_ids,
        }

    @staticmethod
    def _calibrate_priority(llm_priority: str, score: OpportunityScore, sentiment_context: Optional[dict] = None) -> str:
        """基于评分校准 LLM 给出的优先级。

        规则：
          - overall >= 7.5 且 confidence >= 0.7 → position 或 urgent
          - overall >= 6 且 execution_readiness >= 0.6 → research 或更高
          - overall < 4 → watch（不论 LLM 给什么）
          - 其余保持 LLM 输出
        """
        try:
            p = PriorityLevel(llm_priority)
        except ValueError:
            p = PriorityLevel.WATCH

        if score.overall_score >= 7.5 and score.confidence_score >= 0.7:
            if score.timeliness >= 9:
                return PriorityLevel.URGENT.value
            return PriorityLevel.POSITION.value

        if score.overall_score >= 6 and score.execution_readiness >= 0.6:
            if p in (PriorityLevel.POSITION, PriorityLevel.URGENT):
                return p.value
            return PriorityLevel.RESEARCH.value

        if score.overall_score < 4:
            return PriorityLevel.WATCH.value

        if sentiment_context:
            fg = sentiment_context["fear_greed_index"]
            if fg <= 20 and score.overall_score >= 5:
                if p.value in ("watch", "research"):
                    logger.info(
                        f"[M3] 情绪校准: 极度恐惧(FG={fg:.0f}) + 利好信号 → 优先级提升 "
                        f"{p.value} → position"
                    )
                    return PriorityLevel.POSITION.value
            elif fg >= 80 and p.value in ("position", "urgent"):
                logger.info(
                    f"[M3] 情绪校准: 极度贪婪(FG={fg:.0f}) + 利好信号 → 优先级降低 "
                    f"{p.value} → research（短期过热风险）"
                )
                return PriorityLevel.RESEARCH.value

        return p.value

    @staticmethod
    def _validate_invalidation_conditions(
        invalidation_conditions: List[str],
        kill_switch_signals: List[str],
        title: str,
    ) -> tuple:
        """结构化验证失效条件与 kill_switch 信号。

        规则：
          1. is_opportunity=true 时，invalidation_conditions 不能为空
          2. 每条条件长度 >= 4 字符（过滤"下跌"等过于模糊的表述）
          3. kill_switch_signals 不能与 invalidation_conditions 完全重复
          4. 模糊条件追加日志提醒但不删除（LLM 可能给出简短但有效的条件）
        """
        if not invalidation_conditions:
            invalidation_conditions = ["核心假设被证伪"]
            logger.info(f"[M3] invalidation_conditions 为空，已补充默认条件 | title={title}")

        vague_conditions = [c for c in invalidation_conditions if len(c) < 4]
        if vague_conditions:
            logger.warning(
                f"[M3] 存在过于模糊的 invalidation_conditions: {vague_conditions} | title={title}"
            )

        if not kill_switch_signals:
            kill_switch_signals = ["核心假设被证伪", "市场出现显著反向宏观冲击"]
            logger.info(f"[M3] kill_switch_signals 为空，已补充默认信号 | title={title}")

        overlap = set(invalidation_conditions) & set(kill_switch_signals)
        if overlap and len(kill_switch_signals) > 1:
            kill_switch_signals = [s for s in kill_switch_signals if s not in overlap]
            kill_switch_signals.append(list(overlap)[0])
            logger.info(f"[M3] kill_switch_signals 与 invalidation_conditions 去重 | title={title}")

        return invalidation_conditions, kill_switch_signals

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _build_opportunity(
        self,
        data: dict,
        signals: List[MarketSignal],
        batch_id: str,
        inferred_events: Optional[List[InferredEvent]] = None,
        similar_cases: Optional[List[CaseRecord]] = None,
    ) -> OpportunityObject:
        """从 LLM 输出构建 OpportunityObject"""
        now = datetime.now()

        # LLM 常见字段/枚举容错归一化
        instrument_aliases = {
            "BONDS": "BOND",
            "BOND": "BOND",
            "BOND_ETF": "ETF",
            "STOCKS": "STOCK",
            "STOCK": "STOCK",
            "EQUITY": "STOCK",
            "EQUITIES": "STOCK",
            "ETFS": "ETF",
            "ETF": "ETF",
            "FUTURE": "FUTURES",
            "FUTURES": "FUTURES",
            "INDEX_FUTURE": "FUTURES",
            "INDEX_FUTURES": "FUTURES",
            "STOCK_INDEX_FUTURES": "FUTURES",
            "OPTION": "OPTIONS",
            "OPTIONS": "OPTIONS",
            "INDEX_OPTION": "OPTIONS",
            "INDEX_OPTIONS": "OPTIONS",
            "INDEX": "INDEX",
            "INDICES": "INDEX",
        }
        market_aliases = {
            "A": "A_SHARE",
            "ASHARE": "A_SHARE",
            "A_SHARE": "A_SHARE",
            "A-SHARE": "A_SHARE",
            "CN": "A_SHARE",
            "CHINA": "A_SHARE",
            "HK": "HK",
            "HONGKONG": "HK",
            "US": "US",
            "USA": "US",
            "A_FUTURES": "A_FUTURES",
            "HK_FUTURES": "HK_FUTURES",
            "US_FUTURES": "US_FUTURES",
        }
        priority_aliases = {
            "WATCH": "watch",
            "RESEARCH": "research",
            "POSITION": "position",
            "URGENT": "urgent",
        }
        direction_aliases = {
            "LONG": "BULLISH",
            "SHORT": "BEARISH",
            "BUY": "BULLISH",
            "SELL": "BEARISH",
            "BULLISH": "BULLISH",
            "BEARISH": "BEARISH",
            "NEUTRAL": "NEUTRAL",
            "UNCERTAIN": "UNCERTAIN",
        }

        raw_types = data.get("instrument_types") or ["STOCK"]
        clean_types = []
        for t in raw_types:
            normalized = instrument_aliases.get(str(t).upper(), str(t).upper())
            if normalized in {"STOCK", "ETF", "FUTURES", "OPTIONS", "INDEX", "BOND"}:
                clean_types.append(normalized)
            else:
                logger.warning(f"[M3] 忽略未知 instrument_type: {t}")
        if not clean_types:
            clean_types = ["STOCK"]

        raw_markets = data.get("target_markets") or ["A_SHARE"]
        clean_markets = []
        for m in raw_markets:
            key = str(m).upper().replace(" ", "").replace("-", "_")
            normalized = market_aliases.get(key, str(m).upper())
            if normalized in {"A_SHARE", "HK", "US", "A_FUTURES", "HK_FUTURES", "US_FUTURES"}:
                clean_markets.append(normalized)
            else:
                logger.warning(f"[M3] 忽略未知 target_market: {m}")
        if not clean_markets:
            clean_markets = ["A_SHARE"]

        raw_direction = str(data.get("trade_direction", "NEUTRAL")).upper()
        clean_direction = direction_aliases.get(raw_direction, raw_direction)

        raw_priority = str(data.get("priority_level", "watch"))
        clean_priority = priority_aliases.get(raw_priority.upper(), raw_priority.lower())

        # 处理时间窗口
        window_data = data.get("opportunity_window") or {}
        start = datetime.fromisoformat(window_data["start"]) if window_data.get("start") else now
        end = datetime.fromisoformat(window_data["end"]) if window_data.get("end") else now
        if end <= start:
            from datetime import timedelta
            end = start + timedelta(days=14)
        opportunity_window = TimeWindow(
            start=start,
            end=end,
            confidence_level=float(window_data.get("confidence_level", 0.6)),
        )

        supporting_evidence = data.get("supporting_evidence") or [s.signal_label for s in signals[:3]] or ["LLM 未显式给出 supporting_evidence"]
        key_assumptions = data.get("key_assumptions") or ["政策宽松将继续传导至流动性和风险偏好"]
        uncertainty_map = data.get("uncertainty_map") or ["政策效果兑现节奏存在不确定性"]
        next_validation_questions = data.get("next_validation_questions") or ["市场是否出现量价配合验证"]
        invalidation_conditions = data.get("invalidation_conditions") or ["核心政策宽松预期被证伪"]
        must_watch_indicators = data.get("must_watch_indicators") or ["成交量是否放大", "风险偏好是否持续修复"]
        kill_switch_signals = data.get("kill_switch_signals") or ["核心假设被证伪", "市场出现显著反向宏观冲击"]

        invalidation_conditions, kill_switch_signals = self._validate_invalidation_conditions(
            invalidation_conditions, kill_switch_signals, data.get("opportunity_title", "")
        )

        # 评分卡属于 M3 的解释层输出：用于解释判断、供后续模块消费，
        # 不作为独立的二次裁决器去反向覆盖 is_opportunity / priority_level。
        score_data = data.get("opportunity_score") or {}
        catalyst_strength = int(score_data.get("catalyst_strength", max((getattr(s, 'intensity_score', 6) for s in signals), default=6)))
        timeliness = int(score_data.get("timeliness", max((getattr(s, 'timeliness_score', 6) for s in signals), default=6)))
        signal_consistency = int(score_data.get("signal_consistency", min(10, max(5, len(signals) + 5))))
        market_confirmation = int(score_data.get("market_confirmation", 6))
        tradability = int(score_data.get("tradability", 7 if clean_types else 5))
        risk_clarity = int(score_data.get("risk_clarity", 6))
        consensus_gap = int(score_data.get("consensus_gap", 6))
        overall_score = float(score_data.get(
            "overall_score",
            round((catalyst_strength + timeliness + signal_consistency + market_confirmation + tradability + risk_clarity + consensus_gap) / 7, 2),
        ))
        confidence_score = float(score_data.get("confidence_score", min(1.0, round(sum(getattr(s, 'confidence_score', 7) for s in signals) / max(len(signals), 1) / 10, 2))))
        execution_readiness = float(score_data.get("execution_readiness", min(1.0, round((timeliness + tradability + risk_clarity) / 30, 2))))
        opportunity_score = OpportunityScore(
            catalyst_strength=catalyst_strength,
            timeliness=timeliness,
            market_confirmation=market_confirmation,
            tradability=tradability,
            risk_clarity=risk_clarity,
            consensus_gap=consensus_gap,
            signal_consistency=signal_consistency,
            overall_score=overall_score,
            confidence_score=confidence_score,
            execution_readiness=execution_readiness,
        )

        # 评分→优先级映射：当 LLM 给出的 priority 与评分不匹配时校准
        sentiment_context = self._extract_sentiment_context(signals)
        calibrated_priority = self._calibrate_priority(clean_priority, opportunity_score, sentiment_context)
        if calibrated_priority != clean_priority:
            logger.info(
                f"[M3] priority 校准: {clean_priority} → {calibrated_priority} "
                f"(overall={overall_score}, confidence={confidence_score})"
            )
            clean_priority = calibrated_priority

        return OpportunityObject(
            opportunity_id=f"opp_{uuid.uuid4().hex[:8]}",
            opportunity_title=data.get("opportunity_title", "未命名机会"),
            opportunity_thesis=data.get("opportunity_thesis") or data.get("reason", ""),
            target_markets=clean_markets,
            target_instruments=data.get("target_instruments", []),
            trade_direction=clean_direction,
            instrument_types=clean_types,
            opportunity_window=opportunity_window,
            why_now=data.get("why_now") or data.get("reason", ""),
            related_signals=[s.signal_id for s in signals],
            inferred_events=[e.event_id for e in (inferred_events or [])],
            supporting_cases=[c.case_id for c in (similar_cases or [])],
            supporting_evidence=supporting_evidence,
            counter_evidence=data.get("counter_evidence", []),
            key_assumptions=key_assumptions,
            uncertainty_map=uncertainty_map,
            priority_level=calibrated_priority,
            opportunity_score=opportunity_score,
            risk_reward_profile=data.get("risk_reward_profile", "待进一步量化"),
            next_validation_questions=next_validation_questions,
            invalidation_conditions=invalidation_conditions,
            must_watch_indicators=must_watch_indicators,
            kill_switch_signals=kill_switch_signals,
            warnings=data.get("warnings"),
            judgment_version=self.version,
            created_at=now,
            batch_id=batch_id,
        )

    def _signals_to_summary(self, signals: List[MarketSignal]) -> str:
        """信号列表 → 简洁摘要文本（供 Step A 使用）"""
        lines = []
        for s in signals:
            markets = "/".join([m.value for m in s.affected_markets])
            lines.append(
                f"[{s.signal_id}] [{s.signal_type.value}] [{markets}] "
                f"{s.signal_label} | 强度={s.intensity_score} 置信={s.confidence_score} "
                f"时效={s.timeliness_score} | {s.description[:80]}"
            )
        return "\n".join(lines)

    def _signals_to_detail(self, signals: List[MarketSignal]) -> str:
        """信号列表 → 详细文本（供 Step B 使用）"""
        lines = []
        for s in signals:
            markets = "/".join([m.value for m in s.affected_markets])
            instruments = ", ".join(s.affected_instruments) if s.affected_instruments else "未指定"
            extra = ""
            if s.signal_type.value == "sentiment":
                extra = "\n⚠️ 【情绪信号】此信号来自 M10 情绪面系统，恐贪指数反映市场整体情绪状态"
            lines.append(
                f"""---
信号ID: {s.signal_id}
类型: {s.signal_type.value} | 市场: {markets} | 方向: {s.signal_direction.value}
标签: {s.signal_label}
描述: {s.description}
证据原文: {s.evidence_text}
关联品种: {instruments}
逻辑框架: {s.logic_frame.what_changed} → {s.logic_frame.change_direction} → 影响 {', '.join(s.logic_frame.affects)}
评分: 强度={s.intensity_score}/10 置信={s.confidence_score}/10 时效={s.timeliness_score}/10
事件时间: {s.event_time.isoformat() if s.event_time else '未知'}{extra}"""
            )
        return "\n".join(lines)

    def _write_debug_anchor(self, batch_id: str, scenario: dict, raw: Optional[str], error: Exception) -> None:
        """把关键失败信息落到 docs/anchors，便于下一轮排障。"""
        try:
            anchor_dir = PROJECT_ROOT / "docs" / "anchors"
            anchor_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = anchor_dir / f"m3-stepb-parse-failure-{ts}.md"
            content = (
                f"# M3 Step B parse failure anchor\n\n"
                f"- batch_id: {batch_id}\n"
                f"- scenario: {json.dumps(scenario, ensure_ascii=False)}\n"
                f"- error: {type(error).__name__}: {error}\n\n"
                f"## Raw response\n\n```text\n{(raw or '').strip()}\n```\n"
            )
            path.write_text(content, encoding="utf-8")
        except Exception as anchor_err:
            logger.warning(f"[M3] 写调试锚点失败: {anchor_err}")

    def _parse_json_response(self, raw: str, expected_key: Optional[str] = None):
        """解析 LLM JSON 输出，兼容 markdown 代码块、前后解释文字与轻微脏输出。"""
        text = (raw or "").strip()
        if not text:
            raise ValueError("LLM 输出为空")

        if text.startswith("```"):
            lines = text.split("\n")
            start = 1
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[start:end]).strip()
        if text.startswith("json\n"):
            text = text[5:].strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            candidate = None
            if expected_key:
                obj_start = text.find("{")
                obj_end = text.rfind("}")
                if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
                    candidate = text[obj_start:obj_end + 1]
            else:
                obj_start = text.find("{")
                obj_end = text.rfind("}")
                arr_start = text.find("[")
                arr_end = text.rfind("]")
                obj_candidate = text[obj_start:obj_end + 1] if obj_start != -1 and obj_end != -1 and obj_end > obj_start else None
                arr_candidate = text[arr_start:arr_end + 1] if arr_start != -1 and arr_end != -1 and arr_end > arr_start else None
                candidate = obj_candidate or arr_candidate
            if candidate:
                try:
                    data = json.loads(candidate)
                except json.JSONDecodeError:
                    repaired = self._repair_partial_json_object(candidate)
                    if repaired is None:
                        raise
                    data = json.loads(repaired)
            else:
                repaired = self._repair_partial_json_object(text)
                if repaired is None:
                    raise
                data = json.loads(repaired)

        if expected_key:
            if not isinstance(data, dict) or expected_key not in data:
                raise ValueError(f"LLM 输出缺少期望字段 '{expected_key}'，实际字段: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            return data[expected_key]
        return data

    def _repair_partial_json_object(self, text: str) -> Optional[str]:
        """针对 Step B 常见的截断对象做最小修复。

        仅处理“对象已开始、后段在某个长数组字段中截断”的场景，
        目标是尽量保住前面已完整输出的关键字段，供 OpportunityObject 构建继续进行。
        """
        if not text:
            return None

        candidate = text.strip()
        obj_start = candidate.find("{")
        if obj_start == -1:
            return None
        candidate = candidate[obj_start:]

        repair_fields = [
            '"warnings"',
            '"kill_switch_signals"',
            '"must_watch_indicators"',
            '"invalidation_conditions"',
            '"next_validation_questions"',
            '"risk_reward_profile"',
        ]
        for field in repair_fields:
            idx = candidate.find(field)
            if idx != -1:
                prefix = candidate[:idx].rstrip()
                if prefix.endswith(','):
                    prefix = prefix[:-1].rstrip()
                return prefix + "\n}"

        safe_tail_fields = [
            '"execution_readiness"',
            '"confidence_score"',
            '"overall_score"',
            '"signal_consistency"',
            '"consensus_gap"',
            '"risk_clarity"',
            '"tradability"',
            '"market_confirmation"',
            '"timeliness"',
            '"catalyst_strength"',
        ]
        for field in safe_tail_fields:
            idx = candidate.rfind(field)
            if idx != -1:
                line_end = candidate.find("\n", idx)
                if line_end != -1:
                    prefix = candidate[:line_end].rstrip()
                    if prefix.endswith(','):
                        prefix = prefix[:-1].rstrip()
                    return prefix + "\n  }\n}"

        return None
