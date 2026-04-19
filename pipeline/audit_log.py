"""
pipeline/audit_log.py — 审计日志模型

审计日志记录系统中所有关键动作（开仓/平仓/管道运行/工作流/确认/配置变更），
供复盘、合规和异常排查使用。

设计原则：
  - 每条记录不可变（append-only）
  - 至少保留 90 天
  - 支持按动作类型、时间范围、执行者查询
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    PIPELINE_RUN = "pipeline_run"
    POSITION_OPEN = "position_open"
    POSITION_CLOSE = "position_close"
    WORKFLOW_START = "workflow_start"
    WORKFLOW_STEP = "workflow_step"
    CONFIRMATION_APPROVE = "confirmation_approve"
    CONFIRMATION_REJECT = "confirmation_reject"
    MANUAL_ACTION = "manual_action"
    CONFIG_CHANGE = "config_change"
    SIGNAL_INJECT = "signal_inject"
    SENTIMENT_COLLECT = "sentiment_collect"


class Actor(str, Enum):
    USER = "user"
    SCHEDULER = "scheduler"
    SYSTEM = "system"


class AuditResult(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"


class AuditEntry(BaseModel):
    """审计日志条目"""
    entry_id: str = Field(default_factory=lambda: f"aud_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = Field(default_factory=datetime.now)
    action_type: ActionType
    actor: Actor = Actor.SYSTEM
    actor_id: str = ""
    target_type: str = ""
    target_id: str = ""
    description: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    result: AuditResult = AuditResult.SUCCESS
    error_message: str = ""
    session_id: str = ""
