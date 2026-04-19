"""
tests/test_iter9.py — Iteration 9 测试

覆盖：
  1. 审计日志模型 + 持久化
  2. 确认机制 + 持久化
  3. 工作流阶段判定 + 步骤执行
"""
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from pipeline.audit_log import ActionType, Actor, AuditEntry, AuditResult
from pipeline.audit_store import AuditStore
from pipeline.audit import audit
from pipeline.confirmation import (
    ConfirmationRequest, ConfirmationStatus, RiskLevel, requires_confirmation,
)
from pipeline.confirmation_store import ConfirmationStore
from pipeline.workflows import (
    WorkflowPhase, WorkflowStep, WorkflowResult,
    resolve_phase, get_phase_steps, run_workflow,
)


class TestAuditLog:
    def test_audit_entry_creation(self):
        entry = AuditEntry(
            action_type=ActionType.POSITION_OPEN,
            actor=Actor.USER,
            description="开仓沪深300ETF",
            parameters={"instrument": "510300.SH", "quantity": 1000},
            result=AuditResult.SUCCESS,
        )
        assert entry.action_type == ActionType.POSITION_OPEN
        assert entry.actor == Actor.USER

    def test_audit_store_log_and_query(self):
        db_path = Path(tempfile.mkdtemp()) / "audit1.db"
        store = AuditStore(db_path=db_path)
        entry = AuditEntry(
            action_type=ActionType.PIPELINE_RUN,
            actor=Actor.SCHEDULER,
            description="M1→M4 管道运行",
            result=AuditResult.SUCCESS,
        )
        store.log(entry)

        recent = store.get_recent(10)
        assert len(recent) == 1
        assert recent[0]["action_type"] == "pipeline_run"

    def test_audit_store_query_filters(self):
        db_path = Path(tempfile.mkdtemp()) / "audit2.db"
        store = AuditStore(db_path=db_path)
        for at in [ActionType.POSITION_OPEN, ActionType.POSITION_CLOSE, ActionType.PIPELINE_RUN]:
            store.log(AuditEntry(action_type=at, actor=Actor.USER))

        results = store.query(action_type="position_open")
        assert len(results) == 1
        assert results[0]["action_type"] == "position_open"

    def test_audit_convenience_function(self):
        db_path = Path(tempfile.mkdtemp()) / "audit3.db"
        import pipeline.audit as _audit_mod
        _audit_mod._store = AuditStore(db_path=db_path)
        audit(
            action_type=ActionType.SIGNAL_INJECT,
            actor=Actor.SYSTEM,
            description="注入情绪信号到M2",
            result=AuditResult.SUCCESS,
        )
        store = _audit_mod._store
        recent = store.get_recent(5)
        assert len(recent) >= 1

    def test_audit_stats(self):
        db_path = Path(tempfile.mkdtemp()) / "audit4.db"
        store = AuditStore(db_path=db_path)
        store.log(AuditEntry(action_type=ActionType.POSITION_OPEN, result=AuditResult.SUCCESS))
        store.log(AuditEntry(action_type=ActionType.POSITION_CLOSE, result=AuditResult.FAILURE, error_message="timeout"))
        stats = store.get_stats(days=1)
        assert stats["total_entries"] == 2
        assert stats["failure_count"] == 1


class TestConfirmation:
    def test_requires_confirmation_for_urgent(self):
        assert requires_confirmation("urgent_opportunity_execute") is True

    def test_requires_confirmation_for_large_position(self):
        assert requires_confirmation("position_open_large", {"allocation_pct": 0.08}) is True
        assert requires_confirmation("position_open_large", {"allocation_pct": 0.03}) is False

    def test_requires_confirmation_for_config_change(self):
        assert requires_confirmation("config_change") is True

    def test_no_confirmation_for_unknown_action(self):
        assert requires_confirmation("unknown_action") is False

    def test_confirmation_store_create_and_approve(self):
        db_path = Path(tempfile.mkdtemp()) / "cfm1.db"
        store = ConfirmationStore(db_path=db_path)
        req = ConfirmationRequest(
            action_type="urgent_opportunity_execute",
            description="执行 urgent 机会: 央行降准",
            risk_level=RiskLevel.HIGH,
        )
        store.create(req)

        pending = store.get_pending()
        assert len(pending) == 1
        assert pending[0]["action_type"] == "urgent_opportunity_execute"

        ok = store.approve(req.request_id, reviewed_by="user", note="确认执行")
        assert ok

        pending_after = store.get_pending()
        assert len(pending_after) == 0

    def test_confirmation_store_reject(self):
        db_path = Path(tempfile.mkdtemp()) / "cfm2.db"
        store = ConfirmationStore(db_path=db_path)
        req = ConfirmationRequest(
            action_type="position_open_large",
            description="大额开仓",
            risk_level=RiskLevel.HIGH,
            parameters={"allocation_pct": 0.10},
        )
        store.create(req)
        ok = store.reject(req.request_id, reviewed_by="user", note="仓位过大")
        assert ok

        history = store.list_history()
        assert history[0]["status"] == "rejected"


class TestWorkflows:
    def test_resolve_phase_weekend(self):
        phase = resolve_phase("A_SHARE")
        assert isinstance(phase, WorkflowPhase)

    def test_get_phase_steps(self):
        pre_steps = get_phase_steps(WorkflowPhase.PRE_MARKET)
        assert len(pre_steps) >= 2
        intra_steps = get_phase_steps(WorkflowPhase.INTRADAY)
        assert len(intra_steps) >= 2
        post_steps = get_phase_steps(WorkflowPhase.POST_MARKET)
        assert len(post_steps) >= 2

    def test_workflow_step_dependencies(self):
        pre_steps = get_phase_steps(WorkflowPhase.PRE_MARKET)
        signal_pipeline = [s for s in pre_steps if s.fn_name == "signal_pipeline"]
        assert len(signal_pipeline) == 1
        assert "pre_01" in signal_pipeline[0].depends_on

    def test_run_workflow_with_mock_runner(self):
        def mock_runner(fn_name: str) -> dict:
            return {"status": "ok", "fn": fn_name}

        result = run_workflow(WorkflowPhase.PRE_MARKET, task_runner=mock_runner)
        assert result.steps_total >= 2
        assert result.steps_completed == result.steps_total
        assert result.steps_failed == 0
        assert result.started_at is not None
        assert result.finished_at is not None

    def test_run_workflow_handles_failure(self):
        call_count = 0

        def failing_runner(fn_name: str) -> dict:
            nonlocal call_count
            call_count += 1
            if fn_name == "sentiment_collect":
                raise RuntimeError("采集失败")
            return {"status": "ok"}

        result = run_workflow(WorkflowPhase.PRE_MARKET, task_runner=failing_runner)
        assert result.steps_failed >= 1
