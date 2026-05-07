"""
MarketRadar Dashboard V2 - 信号剖面页面
深入分析信号的决策链路和处理过程
"""
import sys
from pathlib import Path
import json

import streamlit as st

# 添加项目根目录到路径
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from dashboard_v2.utils.data_loader import load_signals_recent, load_signal_by_id
from dashboard_v2.components.metrics import signal_direction_badge, empty_state

# ═══════════════════════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="信号剖面 - MarketRadar V2",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 信号剖面分析")
st.caption("深入了解系统如何处理和判断每个信号")

# ═══════════════════════════════════════════════════════════════
# 加载信号列表
# ═══════════════════════════════════════════════════════════════

signals = load_signals_recent(days=7)

if not signals:
    empty_state("最近7天暂无信号记录", "📭")
    st.stop()

# ═══════════════════════════════════════════════════════════════
# 信号选择器
# ═══════════════════════════════════════════════════════════════

st.subheader("📋 选择信号")

# 创建信号选项列表
signal_options = {}
for sig in signals[:50]:  # 最多显示50条
    sig_id = sig.get("signal_id", "")
    sig_type = sig.get("signal_type", "未知")

    # 使用 event_time，如果没有则使用 collected_time
    event_time = sig.get("event_time") or sig.get("collected_time") or ""
    if event_time:
        event_time = str(event_time)[:19]  # 截取到秒

    # 使用 description 作为预览，如果没有则使用 signal_label
    content_preview = sig.get("description") or sig.get("signal_label") or sig.get("content") or ""
    content_preview = str(content_preview)[:50]

    label = f"[{sig_type}] {event_time} - {content_preview}..."
    signal_options[label] = sig_id

selected_label = st.selectbox(
    "选择要分析的信号",
    options=list(signal_options.keys()),
    help="显示最近7天的信号，最多50条"
)

selected_signal_id = signal_options[selected_label]

# 加载选中信号的完整信息
selected_signal = next((s for s in signals if s.get("signal_id") == selected_signal_id), None)

if not selected_signal:
    st.error("无法加载信号详情")
    st.stop()

st.divider()

# ═══════════════════════════════════════════════════════════════
# 信号源信息
# ═══════════════════════════════════════════════════════════════

st.subheader("📄 信号源")

with st.container():
    col_src1, col_src2 = st.columns([2, 1])

    with col_src1:
        # 信号内容
        content = selected_signal.get("content", "")
        with st.expander("查看完整内容", expanded=True):
            st.text_area(
                "信号原文",
                value=content,
                height=150,
                disabled=True,
                label_visibility="collapsed"
            )

    with col_src2:
        # 元数据
        st.markdown("**基本信息**")
        st.text(f"类型: {selected_signal.get('signal_type', '未知')}")
        st.text(f"来源: {selected_signal.get('source_type', '未知')}")
        st.text(f"时间: {selected_signal.get('created_at', '')[:19]}")

        # 方向
        direction = selected_signal.get("direction", "NEUTRAL")
        direction_html = signal_direction_badge(direction)
        st.markdown(f"方向: {direction_html}", unsafe_allow_html=True)

st.divider()

# ═══════════════════════════════════════════════════════════════
# 影响标的
# ═══════════════════════════════════════════════════════════════

st.subheader("🎯 影响标的")

instruments = selected_signal.get("instruments", [])
if instruments:
    # 显示为标签
    cols = st.columns(min(len(instruments), 5))
    for idx, inst in enumerate(instruments[:5]):
        with cols[idx]:
            st.markdown(f"""
            <div style="background:#1e1e2e;border-radius:8px;padding:12px;text-align:center;">
                <div style="font-weight:bold;font-size:16px;">{inst}</div>
            </div>
            """, unsafe_allow_html=True)

    if len(instruments) > 5:
        st.caption(f"还有 {len(instruments) - 5} 个标的...")
else:
    st.info("未识别到具体标的")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 决策链路图
# ═══════════════════════════════════════════════════════════════

st.subheader("🧠 决策链路")

st.markdown("""
<div style="background:#1e1e2e;border-radius:8px;padding:20px;margin-bottom:20px;">
    <div style="text-align:center;font-size:14px;color:#aaaaaa;">
        M0 收集 → M1 解码 → M2 存储 → M10 情绪 → M3 判断 → M4 策略 → 行动建议
    </div>
</div>
""", unsafe_allow_html=True)

# ── M1 解码模块 ──
with st.expander("📖 M1 解码模块", expanded=True):
    st.markdown("**提取的结构化信息**")

    col_m1_1, col_m1_2 = st.columns(2)

    with col_m1_1:
        st.markdown("##### 信号类型")
        st.text(selected_signal.get("signal_type", "未识别"))

        st.markdown("##### 时间范围")
        time_horizon = selected_signal.get("time_horizon", {})
        if isinstance(time_horizon, dict):
            st.text(f"开始: {time_horizon.get('start', '未知')}")
            st.text(f"结束: {time_horizon.get('end', '未知')}")
        else:
            st.text("未识别")

    with col_m1_2:
        st.markdown("##### 置信度")
        confidence = selected_signal.get("confidence", 0)
        st.progress(confidence / 10 if confidence <= 10 else confidence / 100)
        st.caption(f"评分: {confidence}/10" if confidence <= 10 else f"评分: {confidence}%")

        st.markdown("##### 影响范围")
        st.text(f"标的数: {len(instruments)}")
        st.text(f"市场: {', '.join(selected_signal.get('markets', []))}")

# ── M10 情绪模块 ──
with st.expander("🧠 M10 情绪分析模块"):
    st.markdown("**市场情绪评估**")

    # 尝试从信号中提取情绪相关信息
    metadata = selected_signal.get("metadata", {})
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except:
            metadata = {}

    sentiment_data = metadata.get("sentiment", {})

    if sentiment_data:
        col_sent1, col_sent2 = st.columns(2)

        with col_sent1:
            st.markdown("##### 情绪指标")
            fear_greed = sentiment_data.get("fear_greed", 50)
            st.metric("恐贪指数", f"{fear_greed}/100")

            sentiment_label = sentiment_data.get("label", "中性")
            st.text(f"市场情绪: {sentiment_label}")

        with col_sent2:
            st.markdown("##### 贡献度")
            contribution = sentiment_data.get("contribution", 50)
            st.progress(contribution / 100)
            st.caption(f"{contribution}%")

            st.markdown("**结论**")
            st.info(sentiment_data.get("conclusion", "情绪面中性"))
    else:
        st.info("该信号未关联情绪分析数据")

# ── M3 判断模块 ──
with st.expander("⚖️ M3 判断模块"):
    st.markdown("**信号质量评估**")

    col_m3_1, col_m3_2 = st.columns(2)

    with col_m3_1:
        st.markdown("##### 质量评分")
        quality = selected_signal.get("quality_score", 5)
        st.progress(quality / 10)
        st.caption(f"{quality}/10")

        st.markdown("##### 优先级")
        priority = selected_signal.get("priority", "medium")
        priority_map = {"high": "🔴 高", "medium": "🟡 中", "low": "🟢 低"}
        st.text(priority_map.get(priority, priority))

    with col_m3_2:
        st.markdown("##### 可信度")
        credibility = selected_signal.get("credibility", 50)
        st.progress(credibility / 100)
        st.caption(f"{credibility}%")

        st.markdown("##### 时效性")
        urgency = selected_signal.get("urgency", "normal")
        urgency_map = {"urgent": "🔴 紧急", "normal": "🟡 正常", "low": "🟢 低"}
        st.text(urgency_map.get(urgency, urgency))

# ── M4 策略模块 ──
with st.expander("📋 M4 策略模块"):
    st.markdown("**行动策略设计**")

    # 尝试加载关联的决策记录
    action_plan = metadata.get("action_plan", {})

    if action_plan:
        st.markdown("##### 策略类型")
        strategy_type = action_plan.get("strategy_type", "未指定")
        st.text(strategy_type)

        st.markdown("##### 策略参数")
        params = action_plan.get("parameters", {})
        if params:
            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                st.text(f"止损: {params.get('stop_loss', '-')}")
            with col_p2:
                st.text(f"止盈: {params.get('take_profit', '-')}")
            with col_p3:
                st.text(f"持仓周期: {params.get('holding_period', '-')}")

        st.markdown("##### 建议仓位")
        position_size = action_plan.get("position_size", "未指定")
        st.text(position_size)
    else:
        st.info("该信号未生成具体行动策略")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 后续行动
# ═══════════════════════════════════════════════════════════════

st.subheader("🎬 后续行动")

# 显示针对每个标的的建议
if instruments:
    for inst in instruments[:5]:  # 最多显示5个
        with st.container():
            col_act1, col_act2, col_act3, col_act4 = st.columns([2, 2, 2, 1])

            with col_act1:
                st.text(f"标的: {inst}")

            with col_act2:
                # 这里应该从决策记录中读取，暂时显示占位
                st.text("建议: 观察")

            with col_act3:
                st.text("仓位: -")

            with col_act4:
                st.text("状态: 等待")

            st.markdown("---")
else:
    st.info("无具体标的行动建议")

# ═══════════════════════════════════════════════════════════════
# 原始数据查看
# ═══════════════════════════════════════════════════════════════

with st.expander("🔧 查看原始数据（调试用）"):
    st.json(selected_signal)
