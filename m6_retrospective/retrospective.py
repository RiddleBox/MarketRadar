"""
m6_retrospective/retrospective.py — 复盘归因引擎

对已完结的机会/交易进行结构化归因分析。
结果写入 data/retrospectives/ 目录。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.schemas import OpportunityObject, Position
from core.llm_client import LLMClient

logger = logging.getLogger(__name__)

RETRO_DIR = Path(__file__).parent.parent / "data" / "retrospectives"


class RetrospectiveEngine:
    """复盘归因引擎"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()
        RETRO_DIR.mkdir(parents=True, exist_ok=True)

    def analyze(
        self,
        opportunity: OpportunityObject,
        position: Optional[Position],
        outcome: str,  # "HIT" / "MISS" / "STOP_LOSS" / "TAKE_PROFIT" / "EXPIRED"
        notes: str = "",
    ) -> dict:
        """执行复盘分析

        Args:
            opportunity: 被复盘的机会对象
            position: 关联持仓（如果有）
            outcome: 结果类型
            notes: 人工备注

        Returns:
            复盘报告 dict
        """
        logger.info(f"[M6] 开始复盘 | opp={opportunity.opportunity_id} outcome={outcome}")

        prompt = self._build_prompt(opportunity, position, outcome, notes)
        messages = [
            {
                "role": "system",
                "content": """你是一位专业的交易复盘分析师。
你的任务是对一次机会判断和交易结果进行结构化归因分析。

归因框架：
1. 信号质量评估：M1 提取的信号是否准确、完整？
2. 机会判断评估：M3 的论点是否成立？关键假设是否得到验证？
3. 时机评估：why_now 判断是否正确？
4. 行动执行评估：止损/止盈设置是否合理？

要区分：运气（市场碰巧走对）vs 判断力（因为正确的理由走对）。
提炼一条可操作的系统改进建议。

输出 JSON 格式的复盘报告。""",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            raw = self.llm.chat_completion(messages, module_name="m6_retrospective")
            analysis = self._parse_json(raw)
        except Exception as e:
            logger.error(f"[M6] LLM 分析失败: {e}")
            analysis = {"error": str(e), "fallback": True}

        report = {
            "retro_id": f"retro_{uuid.uuid4().hex[:8]}",
            "opportunity_id": opportunity.opportunity_id,
            "position_id": position.position_id if position else None,
            "outcome": outcome,
            "realized_pnl": position.realized_pnl if position else None,
            "created_at": datetime.now().isoformat(),
            "human_notes": notes,
            "analysis": analysis,
        }

        # 持久化
        out_file = RETRO_DIR / f"{report['retro_id']}.json"
        out_file.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        logger.info(f"[M6] 复盘报告已保存: {out_file}")

        return report

    def _build_prompt(self, opp: OpportunityObject, pos: Optional[Position], outcome: str, notes: str) -> str:
        pnl_str = f"{pos.realized_pnl*100:.2f}%" if pos and pos.realized_pnl is not None else "N/A"
        assumptions_str = "\n".join([f"- {a}" for a in opp.key_assumptions])
        evidence_str = "\n".join([f"- {e}" for e in opp.supporting_evidence])
        counter_str = "\n".join([f"- {e}" for e in opp.counter_evidence])

        return f"""请对以下机会进行复盘分析：

## 机会信息
ID: {opp.opportunity_id}
标题: {opp.opportunity_title}
论点: {opp.opportunity_thesis}
优先级: {opp.priority_level.value}
时机判断: {opp.why_now}
风险回报: {opp.risk_reward_profile}

## 判断时的证据
支持证据:
{evidence_str}

反对证据:
{counter_str}

关键假设:
{assumptions_str}

## 实际结果
结果类型: {outcome}
实现盈亏: {pnl_str}
人工备注: {notes}

## 请输出 JSON 格式复盘报告：
```json
{{
  "signal_quality": "信号质量评估（1-5分）及原因",
  "judgment_quality": "机会判断质量评估（1-5分）及原因",
  "timing_quality": "时机判断评估（1-5分）及原因",
  "luck_vs_skill": "这次结果更多来自运气还是判断力？说明原因",
  "assumption_verification": "关键假设实际验证情况（哪些成立，哪些未成立）",
  "key_lesson": "最重要的一条教训",
  "system_improvement": "一条可操作的系统改进建议（指向具体模块和规则）"
}}
```"""

    def _parse_json(self, raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        return json.loads(text)
