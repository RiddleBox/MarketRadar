"""
MarketRadar Dashboard V2 - 可复用UI组件
"""
import streamlit as st
from datetime import datetime


# ═══════════════════════════════════════════════════════════════
# 指标卡片
# ═══════════════════════════════════════════════════════════════

def metric_card(label: str, value: str, delta: str = None, delta_color: str = "normal"):
    """显示指标卡片"""
    st.metric(label=label, value=value, delta=delta, delta_color=delta_color)


def status_badge(status: str) -> str:
    """返回状态徽章HTML"""
    colors = {
        "运行中": "#00c851",
        "已停止": "#ff4b4b",
        "等待中": "#ffbb33",
        "已完成": "#33b5e5",
        "失败": "#ff4b4b",
    }
    color = colors.get(status, "#aaaaaa")
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:4px;font-size:12px;">{status}</span>'


def priority_badge(priority: str) -> str:
    """返回优先级徽章HTML"""
    colors = {
        "urgent": "#ff4b4b",
        "position": "#00c851",
        "research": "#ffbb33",
        "watch": "#aaaaaa",
    }
    labels = {
        "urgent": "紧急",
        "position": "持仓",
        "research": "研究",
        "watch": "观察",
    }
    color = colors.get(priority, "#aaaaaa")
    label = labels.get(priority, priority)
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:4px;font-size:12px;">{label}</span>'


# ═══════════════════════════════════════════════════════════════
# 信号方向标识
# ═══════════════════════════════════════════════════════════════

def signal_direction_badge(direction: str) -> str:
    """返回信号方向徽章"""
    mapping = {
        "bullish": ("🟢 看多", "#00c851"),
        "bearish": ("🔴 看空", "#ff4b4b"),
        "neutral": ("⚪ 中性", "#aaaaaa"),
    }
    label, color = mapping.get(direction.lower(), ("❓ 未知", "#aaaaaa"))
    return f'<span style="color:{color};font-weight:bold;">{label}</span>'


# ═══════════════════════════════════════════════════════════════
# 数据表格
# ═══════════════════════════════════════════════════════════════

def format_timestamp(ts: str | datetime) -> str:
    """格式化时间戳"""
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return ts

    if isinstance(ts, datetime):
        return ts.strftime("%Y-%m-%d %H:%M:%S")

    return str(ts)


def format_percentage(value: float, decimals: int = 2) -> str:
    """格式化百分比"""
    if value is None:
        return "-"
    color = "#00c851" if value > 0 else "#ff4b4b" if value < 0 else "#aaaaaa"
    sign = "+" if value > 0 else ""
    return f'<span style="color:{color};">{sign}{value:.{decimals}f}%</span>'


def format_money(value: float, currency: str = "¥") -> str:
    """格式化金额"""
    if value is None:
        return "-"
    color = "#00c851" if value > 0 else "#ff4b4b" if value < 0 else "#aaaaaa"
    sign = "+" if value > 0 else ""
    return f'<span style="color:{color};">{sign}{currency}{value:,.2f}</span>'


# ═══════════════════════════════════════════════════════════════
# 控制按钮
# ═══════════════════════════════════════════════════════════════

def action_button(label: str, key: str, icon: str = "", disabled: bool = False) -> bool:
    """操作按钮"""
    display_label = f"{icon} {label}" if icon else label
    return st.button(display_label, key=key, disabled=disabled, use_container_width=True)


def confirm_button(label: str, key: str, warning: str = None) -> bool:
    """需要确认的按钮"""
    if warning:
        st.warning(warning)
    return st.button(label, key=key, type="primary")


# ═══════════════════════════════════════════════════════════════
# 信息展示
# ═══════════════════════════════════════════════════════════════

def info_card(title: str, content: str, icon: str = "ℹ️"):
    """信息卡片"""
    st.markdown(f"""
    <div style="background:#1e1e2e;border-radius:8px;padding:12px 16px;margin-bottom:8px;border-left:3px solid #33b5e5;">
        <div style="font-weight:bold;margin-bottom:4px;">{icon} {title}</div>
        <div style="color:#aaaaaa;">{content}</div>
    </div>
    """, unsafe_allow_html=True)


def warning_card(title: str, content: str):
    """警告卡片"""
    st.markdown(f"""
    <div style="background:#1e1e2e;border-radius:8px;padding:12px 16px;margin-bottom:8px;border-left:3px solid #ffbb33;">
        <div style="font-weight:bold;margin-bottom:4px;color:#ffbb33;">⚠️ {title}</div>
        <div style="color:#aaaaaa;">{content}</div>
    </div>
    """, unsafe_allow_html=True)


def error_card(title: str, content: str):
    """错误卡片"""
    st.markdown(f"""
    <div style="background:#1e1e2e;border-radius:8px;padding:12px 16px;margin-bottom:8px;border-left:3px solid #ff4b4b;">
        <div style="font-weight:bold;margin-bottom:4px;color:#ff4b4b;">❌ {title}</div>
        <div style="color:#aaaaaa;">{content}</div>
    </div>
    """, unsafe_allow_html=True)


def success_card(title: str, content: str):
    """成功卡片"""
    st.markdown(f"""
    <div style="background:#1e1e2e;border-radius:8px;padding:12px 16px;margin-bottom:8px;border-left:3px solid #00c851;">
        <div style="font-weight:bold;margin-bottom:4px;color:#00c851;">✅ {title}</div>
        <div style="color:#aaaaaa;">{content}</div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# 空状态
# ═══════════════════════════════════════════════════════════════

def empty_state(message: str, icon: str = "📭"):
    """空状态提示"""
    st.markdown(f"""
    <div style="text-align:center;padding:40px;color:#aaaaaa;">
        <div style="font-size:48px;margin-bottom:16px;">{icon}</div>
        <div style="font-size:16px;">{message}</div>
    </div>
    """, unsafe_allow_html=True)
