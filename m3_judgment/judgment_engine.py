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
from typing import List, Optional

from core.schemas import (
    MarketSignal,
    OpportunityObject,
    PriorityLevel,
    Direction,
    TimeWindow,
)
from core.llm_client import LLMClient
from m3_judgment.prompt_templates import (
    STEP_A_SYSTEM_PROMPT,
    STEP_A_USER_PROMPT,
    STEP_B_SYSTEM_PROMPT,
    STEP_B_USER_PROMPT,
)

logger = logging.getLogger(__name__)

SMALL_BATCH_THRESHOLD = 10  # 小批次直接全量送 Step B


class JudgmentEngine:
    """机会判断引擎

    流程：
      1. 小批次（≤SMALL_BATCH_THRESHOLD）：跳过 Step A，直接 Step B
      2. 大批次：Step A 先识别场景，再对每个场景跑 Step B

    "不构成机会"是合法输出，返回空列表，不抛异常。
    """

    def __init__(self, llm_client: Optional[LLMClient] = None, version: str = "v1.0"):
        self.llm = llm_client or LLMClient()
        self.version = version

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

        # Step B：对每个场景判断是否构成机会
        opportunities = []
        for scenario in scenarios:
            result = self._judge_opportunity(scenario, all_signals, batch_id)
            if result is not None:
                opportunities.append(result)

        logger.info(f"[M3] 判断完成 | 识别机会={len(opportunities)} 个")
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
            scenarios = self._parse_json_response(raw, expected_key="scenarios")
            logger.info(f"[M3 Step A] 识别场景数={len(scenarios)}")
            return scenarios
        except Exception as e:
            logger.error(f"[M3 Step A] LLM 调用失败: {e}")
            return []

    # ------------------------------------------------------------------
    # Step B：机会升级判断
    # ------------------------------------------------------------------

    def _judge_opportunity(
        self,
        scenario: dict,
        all_signals: List[MarketSignal],
        batch_id: str,
    ) -> Optional[OpportunityObject]:
        """Step B：判断一个场景是否构成机会

        Returns:
            OpportunityObject（构成机会）或 None（不构成）
        """
        # 获取场景关联信号
        scenario_signal_ids = set(scenario.get("signal_ids", []))
        scenario_signals = [s for s in all_signals if s.signal_id in scenario_signal_ids] or all_signals

        signals_detail = self._signals_to_detail(scenario_signals)

        messages = [
            {"role": "system", "content": STEP_B_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": STEP_B_USER_PROMPT.format(
                    scenario_description=scenario.get("description", ""),
                    signals_detail=signals_detail,
                ),
            },
        ]

        try:
            raw = self.llm.chat_completion(messages, module_name="m3_judgment")
            data = self._parse_json_response(raw, expected_key=None)

            # LLM 明确判断不构成机会
            if data.get("is_opportunity") is False:
                reason = data.get("reason", "LLM 判断信号不足以构成机会")
                logger.info(f"[M3 Step B] 场景不构成机会 | reason={reason}")
                return None

            return self._build_opportunity(data, scenario_signals, batch_id)

        except Exception as e:
            logger.error(f"[M3 Step B] LLM 调用或解析失败: {e}")
            return None

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    def _build_opportunity(
        self,
        data: dict,
        signals: List[MarketSignal],
        batch_id: str,
    ) -> OpportunityObject:
        """从 LLM 输出构建 OpportunityObject"""
        now = datetime.now()

        # 处理时间窗口
        window_data = data.get("opportunity_window", {})
        opportunity_window = TimeWindow(
            start=datetime.fromisoformat(window_data["start"]) if "start" in window_data else now,
            end=datetime.fromisoformat(window_data["end"]) if "end" in window_data else None,
            confidence_level=float(window_data.get("confidence_level", 0.6)),
        )

        return OpportunityObject(
            opportunity_id=f"opp_{uuid.uuid4().hex[:8]}",
            opportunity_title=data.get("opportunity_title", "未命名机会"),
            opportunity_thesis=data.get("opportunity_thesis", ""),
            target_markets=data.get("target_markets", []),
            target_instruments=data.get("target_instruments", []),
            trade_direction=data.get("trade_direction", Direction.NEUTRAL),
            instrument_types=data.get("instrument_types", []),
            opportunity_window=opportunity_window,
            why_now=data.get("why_now", ""),
            related_signals=[s.signal_id for s in signals],
            supporting_evidence=data.get("supporting_evidence", []),
            counter_evidence=data.get("counter_evidence", []),
            key_assumptions=data.get("key_assumptions", []),
            uncertainty_map=data.get("uncertainty_map", []),
            priority_level=PriorityLevel(data.get("priority_level", "watch")),
            risk_reward_profile=data.get("risk_reward_profile", ""),
            next_validation_questions=data.get("next_validation_questions", []),
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
事件时间: {s.event_time.isoformat() if s.event_time else '未知'}"""
            )
        return "\n".join(lines)

    def _parse_json_response(self, raw: str, expected_key: Optional[str] = None):
        """解析 LLM JSON 输出，兼容 markdown 代码块包裹"""
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # 去掉首行 ```json 和末行 ```
            start = 1
            end = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
            text = "\n".join(lines[start:end])
        data = json.loads(text)
        if expected_key:
            if expected_key not in data:
                raise ValueError(f"LLM 输出缺少期望字段 '{expected_key}'，实际字段: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            return data[expected_key]  # 直接返回对应的列表/对象
        return data
