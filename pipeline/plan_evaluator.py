"""
pipeline/plan_evaluator.py — 开盘检查计划储备

在开盘时读取已保存的 ActionPlan，评估结构化入场条件是否满足，
对满足条件的计划执行开仓。

流程:
  data/action_plans/*.json  →  加载 + 过滤  →  条件评估  →  开仓执行
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.schemas import (
    ActionPlan,
    EntryCondition,
    EntryConditionType,
    Market,
    PriorityLevel,
)

logger = logging.getLogger(__name__)

PLANS_DIR = Path("data/action_plans")


# ── 评估结果 ──────────────────────────────────────────────────

class EvalResult:
    """单个计划的评估结果"""
    def __init__(
        self,
        plan_id: str,
        opportunity_id: str,
        eligible: bool,
        passed: Optional[List[str]] = None,
        failed: Optional[List[str]] = None,
        unevaluable: Optional[List[str]] = None,
    ):
        self.plan_id = plan_id
        self.opportunity_id = opportunity_id
        self.eligible = eligible
        self.passed = passed or []
        self.failed = failed or []
        self.unevaluable = unevaluable or []

    def __repr__(self) -> str:
        status = "✓" if self.eligible else "✗"
        return (
            f"EvalResult({status} {self.plan_id[:12]} | "
            f"passed={len(self.passed)} failed={len(self.failed)} "
            f"unevaluable={len(self.unevaluable)})"
        )


# ── 加载已保存的计划 ──────────────────────────────────────────

def load_saved_plans(
    market: Market,
    min_priority: PriorityLevel = PriorityLevel.RESEARCH,
) -> List[ActionPlan]:
    """从 data/action_plans/ 加载有效的 ActionPlan。

    Args:
        market: 目标市场（A_SHARE / HK / US）
        min_priority: 最低优先级（低于此级别的直接跳过）

    Returns:
        未过期、符合市场/优先级的 ActionPlan 列表
    """
    if not PLANS_DIR.exists():
        logger.info(f"[PlanEvaluator] 计划目录不存在: {PLANS_DIR}")
        return []

    now = datetime.now()
    plans: List[ActionPlan] = []

    for fpath in sorted(PLANS_DIR.glob("*.json")):
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
            plan = ActionPlan(**data)
        except Exception as e:
            logger.warning(f"[PlanEvaluator] 加载失败 {fpath.name}: {e}")
            continue

        # 市场过滤
        plan_market = plan.market
        if hasattr(plan_market, "value"):
            plan_market = plan_market.value
        if str(plan_market) != market.value:
            continue

        # 优先级过滤
        prio = plan.opportunity_priority
        if hasattr(prio, "value"):
            prio = PriorityLevel(prio.value)
        if prio.value < min_priority.value:
            continue

        # 过期检查
        if plan.valid_until < now:
            logger.info(f"[PlanEvaluator] 计划已过期: {plan.plan_id[:12]} (expired={plan.valid_until})")
            continue

        plans.append(plan)

    logger.info(
        f"[PlanEvaluator] 加载 {len(plans)} 个有效计划 (market={market.value}, "
        f"min_priority={min_priority.value})"
    )
    return plans


# ── 条件评估 ──────────────────────────────────────────────────

def evaluate_plan(plan: ActionPlan, feed) -> EvalResult:
    """评估单个计划的入场条件是否满足。

    使用 Phase 1 的结构化 entry_conditions，通过 feed 获取实时行情来判断。
    没有结构化条件的计划视为 "无法评估"（eligible=False, 记录到 unevaluable）。

    Args:
        plan: 待评估的 ActionPlan
        feed: 价格数据源（需实现 get_price(instrument) -> PriceSnapshot）

    Returns:
        EvalResult
    """
    if not plan.phases:
        return EvalResult(
            plan_id=plan.plan_id,
            opportunity_id=plan.opportunity_id,
            eligible=False,
            unevaluable=["计划无 phases"],
        )

    phase1 = plan.phases[0]
    conditions = phase1.entry_conditions

    if not conditions:
        return EvalResult(
            plan_id=plan.plan_id,
            opportunity_id=plan.opportunity_id,
            eligible=False,
            unevaluable=["Phase 1 无结构化 entry_conditions，需人工判断"],
        )

    # 获取首选标的的实时数据
    instrument = plan.primary_instruments[0] if plan.primary_instruments else None
    if not instrument:
        return EvalResult(
            plan_id=plan.plan_id,
            opportunity_id=plan.opportunity_id,
            eligible=False,
            failed=["计划无 primary_instruments"],
        )

    snapshot = None
    try:
        snapshot = feed.get_price(instrument)
    except Exception as e:
        logger.warning(f"[PlanEvaluator] 获取 {instrument} 价格失败: {e}")

    if snapshot is None or snapshot.price <= 0:
        return EvalResult(
            plan_id=plan.plan_id,
            opportunity_id=plan.opportunity_id,
            eligible=False,
            failed=[f"无法获取 {instrument} 实时价格"],
        )

    passed: List[str] = []
    failed: List[str] = []

    for ec in conditions:
        ok, reason = _evaluate_single_condition(ec, snapshot, plan.created_at)
        if ok:
            passed.append(reason or str(ec.condition_type.value))
        else:
            failed.append(reason or str(ec.condition_type.value))

    eligible = len(failed) == 0
    return EvalResult(
        plan_id=plan.plan_id,
        opportunity_id=plan.opportunity_id,
        eligible=eligible,
        passed=passed,
        failed=failed,
    )


def _evaluate_single_condition(
    ec: EntryCondition,
    snapshot,
    plan_created_at: Optional[datetime] = None,
) -> tuple[bool, str]:
    """评估单个 EntryCondition 是否成立。

    Args:
        ec: 结构化入场条件
        snapshot: PriceSnapshot 实时行情
        plan_created_at: 计划创建时间（用于 TIME_SINCE_CREATED）

    Returns:
        (是否满足, 描述字符串)
    """
    price = snapshot.price
    volume = snapshot.volume
    prev_close = snapshot.prev_close or price

    if ec.condition_type == EntryConditionType.PRICE_ABOVE:
        ok = price > ec.value
        return ok, f"价格 {price:.2f} {'>' if ok else '≤'} {ec.value}"

    elif ec.condition_type == EntryConditionType.PRICE_BELOW:
        ok = price < ec.value
        return ok, f"价格 {price:.2f} {'<' if ok else '≥'} {ec.value}"

    elif ec.condition_type == EntryConditionType.PRICE_BETWEEN:
        low = ec.value
        high = ec.value_high if ec.value_high is not None else float("inf")
        ok = low <= price <= high
        return ok, f"价格 {price:.2f} 在区间 [{low}, {high}] 内" if ok else \
            f"价格 {price:.2f} 超出区间 [{low}, {high}]"

    elif ec.condition_type == EntryConditionType.VOLUME_ABOVE:
        ok = volume > ec.value
        return ok, f"成交量 {volume:.0f} {'>' if ok else '≤'} {ec.value}"

    elif ec.condition_type == EntryConditionType.VOLUME_ABOVE_MA:
        # 需要额外的 avg_volume 数据，当前 snapshot 无法直接提供
        # 先用价格变化率做近似，标记为无法评估
        return False, f"VOLUME_ABOVE_MA({ec.period}) 需要历史均量数据，暂不支持"

    elif ec.condition_type == EntryConditionType.PRICE_ABOVE_MA:
        # 需要 MA 计算，当前 snapshot 无法直接提供
        pct_change = ((price / prev_close) - 1) * 100
        ratio = price / prev_close
        if ec.period == 20:
            ok = ratio > 1.0  # 粗略近似：价格高于昨收
            return ok, f"价格/昨收={ratio:.4f} {'>' if ok else '≤'} 1.0 (近似MA{ec.period})"
        return False, f"PRICE_ABOVE_MA({ec.period}) 需历史K线，暂不支持"

    elif ec.condition_type == EntryConditionType.PRICE_BELOW_MA:
        pct_change = ((price / prev_close) - 1) * 100
        ratio = price / prev_close
        if ec.period == 20:
            ok = ratio < 1.0
            return ok, f"价格/昨收={ratio:.4f} {'<' if ok else '≥'} 1.0 (近似MA{ec.period})"
        return False, f"PRICE_BELOW_MA({ec.period}) 需历史K线，暂不支持"

    elif ec.condition_type == EntryConditionType.TIME_SINCE_CREATED:
        if plan_created_at:
            days_since = (datetime.now() - plan_created_at).days
            ok = days_since >= ec.value
            return ok, f"创建距今 {days_since} 天 {'≥' if ok else '<'} {ec.value}"
        return False, "TIME_SINCE_CREATED 缺少 created_at"

    return False, f"未知条件类型: {ec.condition_type}"


# ── 执行开仓 ──────────────────────────────────────────────────

def execute_eligible_plans(
    plans: List[ActionPlan],
    trader,
    feed,
    signal_ids: Optional[List[str]] = None,
) -> List[dict]:
    """执行符合条件的计划的模拟开仓。

    Args:
        plans: 符合条件的 ActionPlan 列表
        trader: PaperTrader 实例
        feed: 价格数据源
        signal_ids: 可选的信号ID列表（用于记录来源）

    Returns:
        每个计划的执行结果 dict 列表
    """
    results = []
    for plan in plans:
        instrument = plan.primary_instruments[0] if plan.primary_instruments else None
        if not instrument:
            results.append({"plan_id": plan.plan_id, "status": "no_instrument"})
            continue

        try:
            snapshot = feed.get_price(instrument)
            if snapshot is None or snapshot.price <= 0:
                logger.warning(f"[PlanEvaluator] {instrument} 无有效价格，跳过")
                results.append({"plan_id": plan.plan_id, "status": "no_price", "instrument": instrument})
                continue
        except Exception as e:
            logger.warning(f"[PlanEvaluator] {instrument} 获取价格失败: {e}")
            results.append({"plan_id": plan.plan_id, "status": "price_error", "error": str(e)})
            continue

        try:
            positions = trader.open_from_plan(
                plan=plan,
                signal_ids=signal_ids or [f"open_check_{plan.opportunity_id}"],
                opportunity_id=plan.opportunity_id,
                entry_price=snapshot.price,
                prev_close=snapshot.prev_close or snapshot.price,
            )
            if positions:
                for pos in positions:
                    logger.info(
                        f"[PlanEvaluator] 开仓成功: {pos.paper_position_id} | "
                        f"{instrument} @ {snapshot.price:.2f}"
                    )
                results.append({
                    "plan_id": plan.plan_id,
                    "status": "opened",
                    "instrument": instrument,
                    "price": snapshot.price,
                    "position_ids": [p.paper_position_id for p in positions],
                })
            else:
                logger.info(f"[PlanEvaluator] 开仓被风控拒绝: {instrument}")
                results.append({"plan_id": plan.plan_id, "status": "rejected", "instrument": instrument})
        except Exception as e:
            logger.error(f"[PlanEvaluator] 开仓异常 {plan.plan_id}: {e}")
            results.append({"plan_id": plan.plan_id, "status": "error", "error": str(e)})

    opened = sum(1 for r in results if r.get("status") == "opened")
    logger.info(f"[PlanEvaluator] 开仓完成: {opened}/{len(plans)} 成功")
    return results
