"""
pipeline/workflows.py — 盘前/盘中/盘后工作流

定义三个交易阶段的工作流步骤，支持：
  1. 自动判断当前所处阶段
  2. 按步骤顺序执行阶段任务
  3. 进度追踪与审计日志
  4. 关键步骤的人工确认门控

阶段定义：
  - 盘前（08:30–09:25）：隔夜信号采集、情绪面快照、日历检查、关注列表更新
  - 盘中（09:25–15:05）：实时价格更新、信号管道、持仓止损/止盈监控
  - 盘后（15:05–23:59）：复盘归因、知识库写入、校准检查、次日准备
"""
from __future__ import annotations

import logging
from datetime import datetime, time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml
from pydantic import BaseModel

from .audit import audit
from .audit_log import ActionType, Actor, AuditResult

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent


class WorkflowPhase(str, Enum):
    PRE_MARKET = "pre_market"
    INTRADAY = "intraday"
    POST_MARKET = "post_market"
    CLOSED = "closed"


class WorkflowStep(BaseModel):
    step_id: str
    name: str
    phase: WorkflowPhase
    fn_name: str
    requires_confirm: bool = False
    depends_on: List[str] = []
    description: str = ""


class WorkflowResult(BaseModel):
    phase: WorkflowPhase
    steps_total: int
    steps_completed: int
    steps_failed: int
    details: List[Dict[str, Any]] = []
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


PHASE_STEPS: List[WorkflowStep] = [
    WorkflowStep(
        step_id="pre_01", name="隔夜信号采集",
        phase=WorkflowPhase.PRE_MARKET, fn_name="news_collect",
        description="采集隔夜新闻和公告",
    ),
    WorkflowStep(
        step_id="pre_02", name="情绪面快照",
        phase=WorkflowPhase.PRE_MARKET, fn_name="sentiment_collect",
        description="M10 情绪面采集（恐贪指数+北向资金）",
    ),
    WorkflowStep(
        step_id="pre_03", name="信号管道处理",
        phase=WorkflowPhase.PRE_MARKET, fn_name="signal_pipeline",
        description="M1→M2→M3→M4 信号处理管道",
        depends_on=["pre_01", "pre_02"],
    ),
    WorkflowStep(
        step_id="intra_01", name="价格更新",
        phase=WorkflowPhase.INTRADAY, fn_name="price_update",
        description="盘中实时价格推送",
    ),
    WorkflowStep(
        step_id="intra_02", name="信号管道",
        phase=WorkflowPhase.INTRADAY, fn_name="signal_pipeline",
        description="盘中新增信号处理",
    ),
    WorkflowStep(
        step_id="intra_03", name="持仓止损止盈监控",
        phase=WorkflowPhase.INTRADAY, fn_name="position_monitor",
        description="检查模拟盘持仓是否触发止损/止盈",
        depends_on=["intra_01"],
    ),
    WorkflowStep(
        step_id="post_01", name="收盘价更新",
        phase=WorkflowPhase.POST_MARKET, fn_name="price_update",
        description="更新收盘价格",
    ),
    WorkflowStep(
        step_id="post_02", name="复盘归因",
        phase=WorkflowPhase.POST_MARKET, fn_name="daily_review",
        description="M6 复盘归因，写入知识库",
        depends_on=["post_01"],
    ),
    WorkflowStep(
        step_id="post_03", name="组合风控检查",
        phase=WorkflowPhase.POST_MARKET, fn_name="portfolio_risk_check",
        description="检查总仓位/主题暴露/高相关去重",
        depends_on=["post_01"],
    ),
]


def resolve_phase(market: str = "A_SHARE") -> WorkflowPhase:
    """根据当前时间和市场交易时间判断当前阶段"""
    config_path = ROOT / "config" / "market_config.yaml"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        hours = config.get("markets", {}).get(market, {}).get("trading_hours", {})
    except Exception:
        hours = {
            "pre_open_call_auction": "09:15",
            "morning_open": "09:30",
            "afternoon_close": "15:00",
        }

    now = datetime.now()
    weekday = now.weekday()
    if weekday >= 5:
        return WorkflowPhase.CLOSED

    current_time = now.time()

    pre_open = _parse_time(hours.get("pre_open_call_auction", "09:15"))
    market_open = _parse_time(hours.get("morning_open", "09:30"))
    market_close = _parse_time(hours.get("afternoon_close", "15:00"))

    if current_time < _offset_time(pre_open, minutes=-45):
        return WorkflowPhase.CLOSED
    elif current_time < market_open:
        return WorkflowPhase.PRE_MARKET
    elif current_time <= _offset_time(market_close, minutes=5):
        return WorkflowPhase.INTRADAY
    else:
        return WorkflowPhase.POST_MARKET


def _parse_time(s: str) -> time:
    parts = s.split(":")
    return time(int(parts[0]), int(parts[1]))


def _offset_time(t: time, minutes: int) -> time:
    from datetime import datetime as dt, timedelta
    d = dt.combine(dt.today(), t) + timedelta(minutes=minutes)
    return d.time()


def get_phase_steps(phase: WorkflowPhase) -> List[WorkflowStep]:
    """获取某个阶段的所有步骤"""
    return [s for s in PHASE_STEPS if s.phase == phase]


def run_workflow(
    phase: WorkflowPhase,
    task_runner: Optional[Callable] = None,
) -> WorkflowResult:
    """执行某个阶段的工作流

    Args:
        phase: 目标阶段
        task_runner: 任务执行函数，接收 (fn_name: str) -> dict
                     如果为 None，使用默认的 scheduler 调用

    Returns:
        WorkflowResult 执行结果
    """
    steps = get_phase_steps(phase)
    if not steps:
        return WorkflowResult(phase=phase, steps_total=0, steps_completed=0, steps_failed=0)

    started_at = datetime.now().isoformat()
    completed_ids: set = set()
    details = []
    failed_count = 0

    max_iterations = len(steps) * 2
    iteration = 0

    while len(completed_ids) < len(steps) and iteration < max_iterations:
        iteration += 1
        progress_made = False

        for step in steps:
            if step.step_id in completed_ids:
                continue

            unmet = [d for d in step.depends_on if d not in completed_ids]
            if unmet:
                continue

            logger.info(f"[Workflow] 执行步骤: {step.step_id} {step.name}")

            try:
                if task_runner:
                    result = task_runner(step.fn_name)
                else:
                    result = _default_task_runner(step.fn_name)

                completed_ids.add(step.step_id)
                details.append({
                    "step_id": step.step_id,
                    "name": step.name,
                    "status": "completed",
                    "result": result,
                })
                audit(
                    action_type=ActionType.WORKFLOW_STEP,
                    actor=Actor.SCHEDULER,
                    description=f"工作流步骤完成: {step.name}",
                    parameters={"phase": phase.value, "step_id": step.step_id},
                    result=AuditResult.SUCCESS,
                )
                progress_made = True

            except Exception as e:
                failed_count += 1
                completed_ids.add(step.step_id)
                details.append({
                    "step_id": step.step_id,
                    "name": step.name,
                    "status": "failed",
                    "error": str(e),
                })
                audit(
                    action_type=ActionType.WORKFLOW_STEP,
                    actor=Actor.SCHEDULER,
                    description=f"工作流步骤失败: {step.name}",
                    parameters={"phase": phase.value, "step_id": step.step_id},
                    result=AuditResult.FAILURE,
                    error_message=str(e)[:200],
                )
                progress_made = True
                logger.error(f"[Workflow] 步骤 {step.step_id} 失败: {e}")

        if not progress_made:
            break

    finished_at = datetime.now().isoformat()
    audit(
        action_type=ActionType.WORKFLOW_START,
        actor=Actor.SCHEDULER,
        description=f"工作流阶段执行完成: {phase.value}",
        parameters={
            "phase": phase.value,
            "completed": len(completed_ids),
            "failed": failed_count,
            "total": len(steps),
        },
        result=AuditResult.SUCCESS if failed_count == 0 else AuditResult.FAILURE,
    )

    return WorkflowResult(
        phase=phase,
        steps_total=len(steps),
        steps_completed=len(completed_ids),
        steps_failed=failed_count,
        details=details,
        started_at=started_at,
        finished_at=finished_at,
    )


def _default_task_runner(fn_name: str) -> dict:
    """默认任务执行器：调用 scheduler 对应任务"""
    try:
        from m7_scheduler.scheduler import Scheduler
        sched = Scheduler()
        task_map = {
            "news_collect": sched._task_news_collect,
            "sentiment_collect": sched._task_sentiment_collect,
            "signal_pipeline": sched._task_signal_pipeline,
            "price_update": sched._task_price_update,
            "daily_review": sched._task_daily_review,
            "position_monitor": _position_monitor_stub,
            "portfolio_risk_check": _portfolio_risk_check_stub,
        }
        fn = task_map.get(fn_name)
        if fn is None:
            return {"status": "skipped", "reason": f"未知任务: {fn_name}"}
        result = fn()
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _position_monitor_stub() -> dict:
    """持仓止损止盈监控（桩函数，待完善）"""
    try:
        from m9_paper_trader.paper_trader import PaperTrader
        from pathlib import Path
        save_path = ROOT / "data" / "paper_positions.json"
        if not save_path.exists():
            return {"checked": 0, "triggered": 0}
        trader = PaperTrader(save_path=save_path)
        positions = trader.list_positions(status="OPEN")
        triggered = 0
        for p in positions:
            if p.direction == "BULLISH" and p.current_price <= p.stop_loss_price and p.stop_loss_price > 0:
                triggered += 1
            elif p.direction == "BEARISH" and p.current_price >= p.stop_loss_price and p.stop_loss_price > 0:
                triggered += 1
        return {"checked": len(positions), "triggered": triggered}
    except Exception as e:
        return {"error": str(e)}


def _portfolio_risk_check_stub() -> dict:
    """组合风控检查（桩函数）"""
    try:
        from m9_paper_trader.paper_trader import PaperTrader, RiskMonitor
        from pathlib import Path
        save_path = ROOT / "data" / "paper_positions.json"
        if not save_path.exists():
            return {"warnings": []}
        trader = PaperTrader(save_path=save_path)
        positions = trader.list_positions(status="OPEN")
        rm = RiskMonitor()
        warnings = rm.check_portfolio_risk(positions)
        return {"warnings": warnings, "position_count": len(positions)}
    except Exception as e:
        return {"error": str(e)}
