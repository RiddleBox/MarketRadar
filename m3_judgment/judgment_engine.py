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
PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
                return self._build_opportunity(data, scenario_signals, batch_id)
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
            supporting_evidence=supporting_evidence,
            counter_evidence=data.get("counter_evidence", []),
            key_assumptions=key_assumptions,
            uncertainty_map=uncertainty_map,
            priority_level=clean_priority,
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
            if not candidate:
                raise
            data = json.loads(candidate)

        if expected_key:
            if not isinstance(data, dict) or expected_key not in data:
                raise ValueError(f"LLM 输出缺少期望字段 '{expected_key}'，实际字段: {list(data.keys()) if isinstance(data, dict) else type(data)}")
            return data[expected_key]
        return data
