"""
m4_action/action_designer.py — 行动设计模块

输入：OpportunityObject（来自 M3）
输出：ActionPlan（止损/止盈/仓位/分阶段计划）

设计原则见 PRINCIPLES.md。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from core.schemas import (
    ActionPlan,
    ActionPhase,
    ActionType,
    Direction,
    InstrumentType,
    OpportunityObject,
    PositionSizing,
    PriorityLevel,
    StopLossConfig,
    TakeProfitConfig,
)
from core.llm_client import LLMClient

logger = logging.getLogger(__name__)


# 按优先级定义最大风险预算（占总资金 %）
RISK_BUDGET_BY_PRIORITY = {
    PriorityLevel.watch: 0.0,
    PriorityLevel.research: 0.01,   # 1%
    PriorityLevel.position: 0.05,   # 5%
    PriorityLevel.urgent: 0.08,     # 8%
}

# 行动计划有效期（天）
PLAN_VALIDITY_DAYS = {
    PriorityLevel.watch: 30,
    PriorityLevel.research: 21,
    PriorityLevel.position: 14,
    PriorityLevel.urgent: 7,
}


class ActionDesigner:
    """行动设计器：把机会转化为可执行的行动计划"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def design(self, opportunity: OpportunityObject) -> ActionPlan:
        """主入口：OpportunityObject → ActionPlan

        Args:
            opportunity: M3 输出的机会对象

        Returns:
            ActionPlan，包含止损/止盈/仓位/分阶段计划
        """
        logger.info(
            f"[M4] 设计行动计划 | opportunity_id={opportunity.opportunity_id} "
            f"priority={opportunity.priority_level} direction={opportunity.trade_direction}"
        )

        # watch 级别不生成执行计划，只生成观察计划
        if opportunity.priority_level == PriorityLevel.watch:
            return self._build_watch_plan(opportunity)

        # 通过 LLM 生成具体行动细节
        action_detail = self._generate_action_detail(opportunity)

        return self._build_action_plan(opportunity, action_detail)

    # ------------------------------------------------------------------
    # watch 级别：纯观察计划
    # ------------------------------------------------------------------

    def _build_watch_plan(self, opportunity: OpportunityObject) -> ActionPlan:
        """构建 watch 级别的观察计划（不入场）"""
        instrument = opportunity.target_instruments[0] if opportunity.target_instruments else "待定"
        now = datetime.now()

        return ActionPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            opportunity_id=opportunity.opportunity_id,
            action_type=ActionType.WATCH,
            instrument=instrument,
            direction=opportunity.trade_direction,
            position_sizing=PositionSizing(
                method="FIXED_PERCENT",
                value=0.0,
                notes="watch 阶段不入场，仓位为 0",
            ),
            entry_conditions=[
                f"优先级升级至 research 或以上",
                f"核实以下假设成立：{'; '.join(opportunity.key_assumptions[:2])}",
            ],
            stop_loss=StopLossConfig(
                stop_price=None,
                stop_condition="watch 阶段无持仓，无需止损",
                trigger_type="NONE",
            ),
            take_profit=TakeProfitConfig(
                target_price=None,
                partial_exits=[],
                trailing_stop=None,
            ),
            phases=[
                ActionPhase(
                    phase_name="观察期",
                    trigger_condition="持续",
                    action_description=f"持续跟踪：{'; '.join(opportunity.next_validation_questions[:3])}",
                )
            ],
            created_at=now,
            expires_at=now + timedelta(days=PLAN_VALIDITY_DAYS[PriorityLevel.watch]),
        )

    # ------------------------------------------------------------------
    # 通过 LLM 生成行动细节
    # ------------------------------------------------------------------

    def _generate_action_detail(self, opportunity: OpportunityObject) -> dict:
        """调用 LLM 生成具体的入场/止损/止盈细节"""
        prompt = self._build_prompt(opportunity)

        messages = [
            {
                "role": "system",
                "content": """你是一位专业的交易行动规划师，负责把市场机会转化为具体的可执行行动计划。

你的核心职责：
1. 设计具体的入场条件（不是"看情况"，是明确的价格/事件/时间触发）
2. 设计止损位（基于技术结构或关键假设失效条件）
3. 设计止盈目标（分批止盈或移动止盈）
4. 设计分阶段仓位计划

原则：
- 止损必须具体，不允许"根据情况调整"
- 仓位建议必须有上限，不允许"满仓"或"重仓"
- 分阶段计划中，Phase 1 永远是侦察仓（≤总仓位 30%）
""",
            },
            {"role": "user", "content": prompt},
        ]

        try:
            raw = self.llm.chat_completion(messages, module_name="m4_action")
            return self._parse_json(raw)
        except Exception as e:
            logger.error(f"[M4] LLM 生成行动细节失败: {e}，使用默认模板")
            return self._default_action_detail(opportunity)

    def _build_prompt(self, opportunity: OpportunityObject) -> str:
        instruments = ", ".join(opportunity.target_instruments) if opportunity.target_instruments else "待定品种"
        markets = "/".join([m.value for m in opportunity.target_markets])
        assumptions = "\n".join([f"- {a}" for a in opportunity.key_assumptions])
        uncertainties = "\n".join([f"- {u}" for u in opportunity.uncertainty_map])

        return f"""请为以下机会设计行动计划：

## 机会信息
标题：{opportunity.opportunity_title}
论点：{opportunity.opportunity_thesis}
目标品种：{instruments}
市场：{markets}
方向：{opportunity.trade_direction.value}
优先级：{opportunity.priority_level.value}
时机：{opportunity.why_now}
风险回报：{opportunity.risk_reward_profile}

## 关键假设
{assumptions}

## 主要不确定性
{uncertainties}

## 请输出 JSON：
```json
{{
  "instrument": "主要操作品种（代码或名称）",
  "entry_conditions": ["入场条件1", "入场条件2"],
  "stop_loss": {{
    "stop_price_description": "止损位描述（如：跌破250日均线）",
    "stop_condition": "触发止损的具体条件",
    "trigger_type": "PRICE_LEVEL 或 CONDITION_BASED"
  }},
  "take_profit": {{
    "target_price_description": "目标价描述",
    "partial_exits": ["第一批止盈条件（%仓位）", "第二批止盈条件"],
    "trailing_stop": "移动止盈描述（可选）"
  }},
  "phases": [
    {{
      "phase_name": "Phase 1 侦察仓",
      "trigger_condition": "入场触发条件",
      "action_description": "具体操作：买入/卖出 XX 品种，仓位 XX%"
    }},
    {{
      "phase_name": "Phase 2 主仓",
      "trigger_condition": "Phase 1 浮盈 X% 后",
      "action_description": "加仓操作"
    }}
  ],
  "notes": "其他注意事项"
}}
```"""

    def _default_action_detail(self, opportunity: OpportunityObject) -> dict:
        """LLM 失败时的兜底默认模板"""
        instrument = opportunity.target_instruments[0] if opportunity.target_instruments else "待定"
        return {
            "instrument": instrument,
            "entry_conditions": ["等待机会窗口开启", "确认关键假设成立"],
            "stop_loss": {
                "stop_price_description": "关键支撑位下方2%",
                "stop_condition": "收盘价跌破关键支撑",
                "trigger_type": "PRICE_LEVEL",
            },
            "take_profit": {
                "target_price_description": "前期阻力位附近",
                "partial_exits": ["到达目标价50%时平仓一半", "剩余仓位移动止盈"],
                "trailing_stop": "浮盈超过5%后，止损上移至成本价",
            },
            "phases": [
                {
                    "phase_name": "Phase 1 侦察仓",
                    "trigger_condition": "入场条件满足",
                    "action_description": f"买入 {instrument}，仓位 30%",
                },
                {
                    "phase_name": "Phase 2 主仓",
                    "trigger_condition": "Phase 1 浮盈 3% 后",
                    "action_description": f"加仓 {instrument}，追加 70%",
                },
            ],
        }

    # ------------------------------------------------------------------
    # 构建 ActionPlan 对象
    # ------------------------------------------------------------------

    def _build_action_plan(self, opportunity: OpportunityObject, detail: dict) -> ActionPlan:
        now = datetime.now()
        priority = opportunity.priority_level
        risk_budget = RISK_BUDGET_BY_PRIORITY[priority]

        # 止损配置
        sl_data = detail.get("stop_loss", {})
        stop_loss = StopLossConfig(
            stop_price=None,  # 由 M5 根据实际入场价更新
            stop_condition=sl_data.get("stop_condition", "关键假设失效"),
            trigger_type=sl_data.get("trigger_type", "CONDITION_BASED"),
            description=sl_data.get("stop_price_description", ""),
        )

        # 止盈配置
        tp_data = detail.get("take_profit", {})
        take_profit = TakeProfitConfig(
            target_price=None,
            partial_exits=tp_data.get("partial_exits", []),
            trailing_stop=tp_data.get("trailing_stop"),
            description=tp_data.get("target_price_description", ""),
        )

        # 仓位建议
        position_sizing = PositionSizing(
            method="FIXED_PERCENT",
            value=risk_budget,
            notes=f"优先级={priority.value}，最大风险预算={risk_budget*100:.0f}%总资金",
        )

        # 分阶段计划
        phases = []
        for p in detail.get("phases", []):
            phases.append(ActionPhase(
                phase_name=p.get("phase_name", ""),
                trigger_condition=p.get("trigger_condition", ""),
                action_description=p.get("action_description", ""),
            ))

        if not phases:
            phases = [ActionPhase(
                phase_name="Phase 1",
                trigger_condition="入场条件满足时",
                action_description="建立初始仓位",
            )]

        return ActionPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            opportunity_id=opportunity.opportunity_id,
            action_type=ActionType.OPEN,
            instrument=detail.get("instrument", opportunity.target_instruments[0] if opportunity.target_instruments else "待定"),
            direction=opportunity.trade_direction,
            position_sizing=position_sizing,
            entry_conditions=detail.get("entry_conditions", ["等待入场信号"]),
            stop_loss=stop_loss,
            take_profit=take_profit,
            phases=phases,
            created_at=now,
            expires_at=now + timedelta(days=PLAN_VALIDITY_DAYS[priority]),
        )

    def _parse_json(self, raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
        return json.loads(text)
