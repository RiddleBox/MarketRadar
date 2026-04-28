"""
pipeline/opportunity_to_position.py — 机会到模拟盘的桥接

将 M12 补牢机会 或 M3 判断机会 传递给 M4 设计行动计划，
然后由 M9 模拟开仓，完成闭环：

  M12 RetroOpportunity  ─┐
                         ├─→ M4 ActionDesigner ─→ M9 PaperTrader
  M3 OpportunityObject  ─┘

数据全流程保留，不删除任何模拟数据，供复盘使用。
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Tuple

from core.schemas import (
    ActionPlan,
    Direction,
    Market,
    OpportunityObject,
    PriorityLevel,
    RetroOpportunity,
)

from pipeline.decision_log import DecisionLog

logger = logging.getLogger(__name__)

OPPORTUNITY_ARCHIVE = Path("data/opportunities")

_decision_log = DecisionLog()


def opportunities_to_positions(
    opportunities: list,
    feed_cls=None,
    market: Optional[Market] = None,
    max_positions: int = 3,
    min_priority: PriorityLevel = PriorityLevel.RESEARCH,
    dry_run: bool = False,
) -> List[dict]:
    """将机会列表转为模拟持仓（核心桥接函数）。

    Args:
        opportunities: M3 OpportunityObject 或 M12 RetroOpportunity 列表
        feed_cls: 数据源类（用于获取当前价格）
        market: 覆盖机会中的市场
        max_positions: 单次最多开仓数
        min_priority: 最低优先级（低于此级别不开仓）
        dry_run: True则只打印不做实际开仓

    Returns:
        每个开仓结果的摘要列表
    """
    from m4_action.action_designer import ActionDesigner
    from m9_paper_trader.paper_trader import PaperTrader

    designer = ActionDesigner()
    trader = PaperTrader()

    PRIORITY_ORDER = {
        PriorityLevel.WATCH: 0,
        PriorityLevel.RESEARCH: 1,
        PriorityLevel.POSITION: 2,
        PriorityLevel.URGENT: 3,
    }

    filtered = []
    for opp in opportunities:
        if isinstance(opp, RetroOpportunity):
            obj = opp.opportunity
        elif isinstance(opp, OpportunityObject):
            obj = opp
        else:
            logger.warning(f"[Bridge] 未知类型 {type(opp)}, 跳过")
            continue

        pri = obj.priority_level
        level = PRIORITY_ORDER.get(pri, 0)
        min_level = PRIORITY_ORDER.get(min_priority, 1)
        if level < min_level:
            logger.info(f"[Bridge] {obj.opportunity_id} 优先级={pri}, 低于{min_priority}, 仅观察")
            continue

        filtered.append((opp, obj))

    filtered.sort(key=lambda x: PRIORITY_ORDER.get(x[1].priority_level, 0), reverse=True)
    filtered = filtered[:max_positions]

    results = []
    for orig, obj in filtered:
        try:
            result = _process_single_opportunity(orig, obj, designer, trader, feed_cls, market, dry_run)
            results.append(result)
        except Exception as e:
            logger.error(f"[Bridge] 处理 {obj.opportunity_id} 失败: {e}")
            results.append({
                "opportunity_id": obj.opportunity_id,
                "instrument": obj.target_instruments[0] if obj.target_instruments else "unknown",
                "status": "error",
                "error": str(e),
            })

    trader._save()

    _archive_opportunities(opportunities)

    return results


def _process_single_opportunity(
    orig, obj: OpportunityObject,
    designer: ActionDesigner,
    trader: PaperTrader,
    feed_cls=None,
    market: Optional[Market] = None,
    dry_run: bool = False,
) -> dict:
    """处理单个机会：M4设计 → M9开仓"""

    instrument = obj.target_instruments[0] if obj.target_instruments else None
    if not instrument:
        return {"opportunity_id": obj.opportunity_id, "status": "no_instrument"}

    mkt = market or (obj.target_markets[0] if obj.target_markets else Market.A_SHARE)
    if isinstance(mkt, str):
        mkt = Market(mkt)

    logger.info(f"[Bridge] processing opportunity: {obj.opportunity_id} | {instrument} | priority={obj.priority_level.value}")

    plan = designer.design(obj)
    logger.info(f"[Bridge] 行动计划: {plan.plan_id} | SL={plan.stop_loss.stop_loss_value}% | TP={plan.take_profit.take_profit_value}%")

    _archive_plan(plan)

    if plan.opportunity_priority == PriorityLevel.WATCH:
        logger.info(f"[Bridge] WATCH级别，仅观察不开仓: {instrument}")
        return {
            "opportunity_id": obj.opportunity_id,
            "instrument": instrument,
            "plan_id": plan.plan_id,
            "status": "watch_only",
            "priority": plan.opportunity_priority.value,
        }

    entry_price = 0.0
    prev_close = 0.0
    signal_intensity = 0.0
    signal_confidence = 0.0
    signal_ids = []
    signal_type = ""

    if isinstance(orig, RetroOpportunity):
        anomaly = orig.anomaly
        entry_price = anomaly.anomaly_price or 0.0
        prev_close = anomaly.baseline_price or entry_price
        signal_intensity = anomaly.price_change_pct if anomaly.price_change_pct else 0.0
        causation = orig.causation
        signal_confidence = causation.confidence if causation.confidence else 0.0
        signal_ids = [f"m12_{anomaly.instrument}_{anomaly.anomaly_date.isoformat()}"]
        signal_type = "opportunity_catcher"
    else:
        signal_ids = obj.signal_ids if obj.signal_ids else [obj.opportunity_id]
        signal_type = obj.opportunity_thesis[:50] if obj.opportunity_thesis else ""

    if entry_price <= 0 and feed_cls is not None:
        try:
            feed = feed_cls() if callable(feed_cls) else feed_cls
            snap = feed.get_price(instrument)
            if snap and snap.price > 0:
                entry_price = snap.price
                prev_close = snap.prev_close or entry_price
        except Exception as e:
            logger.warning(f"[Bridge] 获取 {instrument} 价格失败: {e}")

    if entry_price <= 0:
        logger.warning(f"[Bridge] {instrument} 无法获取入场价，跳过开仓")
        return {
            "opportunity_id": obj.opportunity_id,
            "instrument": instrument,
            "plan_id": plan.plan_id,
            "status": "no_price",
        }

    if dry_run:
        logger.info(f"[Bridge] DRY RUN: {instrument} @ {entry_price:.2f} | SL={plan.stop_loss.stop_loss_value}% | TP={plan.take_profit.take_profit_value}%")
        return {
            "opportunity_id": obj.opportunity_id,
            "instrument": instrument,
            "plan_id": plan.plan_id,
            "status": "dry_run",
            "entry_price": entry_price,
            "stop_loss_pct": plan.stop_loss.stop_loss_value,
            "take_profit_pct": plan.take_profit.take_profit_value,
        }

    opened = trader.open_from_plan(
        plan=plan,
        signal_ids=signal_ids,
        opportunity_id=obj.opportunity_id,
        entry_price=entry_price,
        prev_close=prev_close,
        signal_intensity=signal_intensity,
        signal_confidence=signal_confidence,
        signal_type=signal_type,
    )

    if not opened:
        logger.warning(f"[Bridge] {instrument} 开仓被风控拒绝或校验失败")
        return {
            "opportunity_id": obj.opportunity_id,
            "instrument": instrument,
            "plan_id": plan.plan_id,
            "status": "rejected",
        }

    pos = opened[0]
    logger.info(
        f"[Bridge] opened: {pos.instrument} | dir={pos.direction} | "
        f"entry={pos.entry_price:.2f} | SL={pos.stop_loss_price:.2f} | TP={pos.take_profit_price}"
    )

    # 记录开仓决策到决策日志
    _decision_log.record_action(
        record=_decision_log.record_anomaly(
            instrument=instrument,
            market=mkt.value if isinstance(mkt, Market) else str(mkt),
            anomaly_type="opportunity_action",
            price_change_pct=0.0,
            atr_multiple=0.0,
            sigma_multiple=0.0,
            volume_ratio=0.0,
        ),
        action_taken="OPENED",
        reason=f"M4 plan SL={plan.stop_loss.stop_loss_value}% TP={plan.take_profit.take_profit_value}%",
        plan_id=plan.plan_id,
        stop_loss_pct=plan.stop_loss.stop_loss_value,
        take_profit_pct=plan.take_profit.take_profit_value,
        position_id=pos.paper_position_id,
        entry_price=pos.entry_price,
    )

    return {
        "opportunity_id": obj.opportunity_id,
        "instrument": pos.instrument,
        "plan_id": plan.plan_id,
        "position_id": pos.paper_position_id,
        "status": "opened",
        "direction": pos.direction,
        "entry_price": pos.entry_price,
        "stop_loss_price": pos.stop_loss_price,
        "take_profit_price": pos.take_profit_price,
        "quantity": pos.quantity,
    }


def _archive_plan(plan: ActionPlan):
    """持久化ActionPlan到data/opportunities/"""
    OPPORTUNITY_ARCHIVE.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OPPORTUNITY_ARCHIVE / f"plan_{plan.plan_id}_{ts}.json"
    try:
        path.write_text(
            json.dumps(plan.model_dump(), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info(f"[Bridge] ActionPlan archived: {path.name}")
    except Exception as e:
        logger.warning(f"[Bridge] archive plan failed: {e}")


def _archive_opportunities(opportunities: list):
    """将机会原始数据存档，供复盘查阅。"""
    OPPORTUNITY_ARCHIVE.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OPPORTUNITY_ARCHIVE / f"opportunities_{ts}.json"
    try:
        data = []
        for opp in opportunities:
            if isinstance(opp, RetroOpportunity):
                data.append(opp.model_dump())
            elif isinstance(opp, OpportunityObject):
                data.append(opp.model_dump())
            else:
                continue
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info(f"[Bridge] Opportunities archived: {path.name} ({len(data)} items)")
    except Exception as e:
        logger.warning(f"[Bridge] archive opportunities failed: {e}")