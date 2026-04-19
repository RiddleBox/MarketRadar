"""
pipeline/confirmation.py — 人工确认机制

关键动作（大额开仓、urgent 机会执行等）需经人工确认后方可执行。
定义确认请求模型、风险等级和需确认的动作注册表。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConfirmationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ConfirmationRequest(BaseModel):
    """确认请求"""
    request_id: str = Field(default_factory=lambda: f"cfm_{uuid.uuid4().hex[:12]}")
    created_at: datetime = Field(default_factory=datetime.now)
    action_type: str = ""
    description: str = ""
    parameters: Dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.MEDIUM
    status: ConfirmationStatus = ConfirmationStatus.PENDING
    reviewed_by: str = ""
    reviewed_at: Optional[datetime] = None
    review_note: str = ""
    expires_at: Optional[datetime] = None
    session_id: str = ""


CONFIRMABLE_ACTIONS = {
    "position_open_large": RiskLevel.HIGH,
    "position_close_large": RiskLevel.MEDIUM,
    "urgent_opportunity_execute": RiskLevel.HIGH,
    "pipeline_batch_large": RiskLevel.LOW,
    "config_change": RiskLevel.CRITICAL,
}


def requires_confirmation(action_type: str, parameters: Dict[str, Any] = None) -> bool:
    """判断某个动作是否需要人工确认"""
    if action_type not in CONFIRMABLE_ACTIONS:
        return False
    parameters = parameters or {}
    risk = CONFIRMABLE_ACTIONS[action_type]

    if action_type == "position_open_large":
        allocation_pct = parameters.get("allocation_pct", 0)
        return allocation_pct > 0.05
    if action_type == "position_close_large":
        realized_pct = parameters.get("realized_pnl_pct", 0)
        return abs(realized_pct) > 0.03
    if action_type == "urgent_opportunity_execute":
        return True
    if action_type == "config_change":
        return True
    if action_type == "pipeline_batch_large":
        batch_size = parameters.get("batch_size", 0)
        return batch_size > 20

    return risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)
