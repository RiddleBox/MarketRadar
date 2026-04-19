"""
pipeline/audit.py — 审计日志便捷接口

提供快捷函数和装饰器，方便各模块接入审计日志。
"""
from __future__ import annotations

import functools
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from .audit_log import ActionType, Actor, AuditEntry, AuditResult
from .audit_store import AuditStore

logger = logging.getLogger(__name__)

_store: Optional[AuditStore] = None


def _get_store() -> AuditStore:
    global _store
    if _store is None:
        _store = AuditStore()
    return _store


def audit(
    action_type: ActionType,
    actor: Actor = Actor.SYSTEM,
    actor_id: str = "",
    target_type: str = "",
    target_id: str = "",
    description: str = "",
    parameters: Optional[Dict[str, Any]] = None,
    result: AuditResult = AuditResult.SUCCESS,
    error_message: str = "",
    session_id: str = "",
) -> None:
    """写入一条审计日志"""
    entry = AuditEntry(
        timestamp=datetime.now(),
        action_type=action_type,
        actor=actor,
        actor_id=actor_id,
        target_type=target_type,
        target_id=target_id,
        description=description,
        parameters=parameters or {},
        result=result,
        error_message=error_message,
        session_id=session_id,
    )
    try:
        _get_store().log(entry)
    except Exception as e:
        logger.warning(f"[Audit] 写入审计日志失败: {e}")


def audit_action(
    action_type: ActionType,
    actor: Actor = Actor.SYSTEM,
    target_type: str = "",
):
    """装饰器：自动记录函数调用到审计日志"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__qualname__
            desc = f"{func_name}"
            params = {"args_repr": str(args)[:200], "kwargs_repr": str(kwargs)[:200]}
            try:
                result_val = func(*args, **kwargs)
                audit(
                    action_type=action_type,
                    actor=actor,
                    target_type=target_type,
                    description=desc,
                    parameters=params,
                    result=AuditResult.SUCCESS,
                )
                return result_val
            except Exception as e:
                audit(
                    action_type=action_type,
                    actor=actor,
                    target_type=target_type,
                    description=desc,
                    parameters=params,
                    result=AuditResult.FAILURE,
                    error_message=str(e)[:200],
                )
                raise
        return wrapper
    return decorator
