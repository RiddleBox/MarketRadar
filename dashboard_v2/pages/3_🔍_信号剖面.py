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
# 信号筛选和选择器
# ═══════════════════════════════════════════════════════════════

st.subheader("📋 选择信号")

# 信号类型筛选
col_filter1, col_filter2 = st.columns([2, 1])

with col_filter1:
    # 获取所有信号类型
    all_types = sorted(set(sig.get("signal_type", "未知") for sig in signals))

    signal_type_filter = st.multiselect(
        "信号类型筛选",
        options=all_types,
        default=[t for t in all_types if t != "sentiment"],  # 默认排除情绪信号
        help="选择要显示的信号类型（默认排除情绪信号以便查看其他类型）"
    )

with col_filter2:
    max_signals = st.number_input(
        "显示数量",
        min_value=10,
        max_value=200,
        value=50,
        step=10,
        help="最多显示的信号数量"
    )

# 应用筛选
filtered_signals = [
    sig for sig in signals
    if sig.get("signal_type", "未知") in signal_type_filter
]

st.caption(f"筛选后: {len(filtered_signals)} 条信号 / 总计: {len(signals)} 条")

if not filtered_signals:
    st.warning("没有符合筛选条件的信号，请调整筛选条件")
    st.stop()

# 创建信号选项列表
signal_options = {}
for sig in filtered_signals[:max_signals]:
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
    help=f"显示筛选后的信号，最多{max_signals}条"
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
        # 信号内容 - 使用 evidence_text 或 description
        evidence_text = selected_signal.get("evidence_text", "")
        description = selected_signal.get("description", "")

        with st.expander("📰 原始证据文本", expanded=True):
            st.text_area(
                "证据原文",
                value=evidence_text if evidence_text else description,
                height=150,
                disabled=True,
                label_visibility="collapsed"
            )

    with col_src2:
        # 元数据
        st.markdown("**基本信息**")
        st.text(f"类型: {selected_signal.get('signal_type', '未知')}")
        st.text(f"来源: {selected_signal.get('source_type', '未知')}")
        st.text(f"来源文件: {selected_signal.get('source_ref', '未知')}")

        event_time = selected_signal.get("event_time", "")
        if event_time:
            st.text(f"事件时间: {str(event_time)[:19]}")

        collected_time = selected_signal.get("collected_time", "")
        if collected_time:
            st.text(f"采集时间: {str(collected_time)[:19]}")

        # 方向
        direction = selected_signal.get("signal_direction", "NEUTRAL")
        direction_colors = {
            "BULLISH": "🟢",
            "BEARISH": "🔴",
            "NEUTRAL": "⚪",
        }
        direction_emoji = direction_colors.get(direction, "⚪")
        st.text(f"方向: {direction_emoji} {direction}")

st.divider()

# ═══════════════════════════════════════════════════════════════
# M1 解码信息
# ═══════════════════════════════════════════════════════════════

st.subheader("🧠 M1 解码分析")

col_m1_1, col_m1_2 = st.columns(2)

with col_m1_1:
    st.markdown("##### 📊 信号评分")

    intensity = selected_signal.get("intensity_score", 0)
    confidence = selected_signal.get("confidence_score", 0)
    timeliness = selected_signal.get("timeliness_score", 0)

    st.metric("强度评分", f"{intensity}/10")
    st.metric("置信度评分", f"{confidence}/10")
    st.metric("时效性评分", f"{timeliness}/10")

with col_m1_2:
    st.markdown("##### 🔗 逻辑框架")

    logic_frame = selected_signal.get("logic_frame", {})
    if logic_frame:
        what_changed = logic_frame.get("what_changed", "未知")
        change_direction = logic_frame.get("change_direction", "未知")
        affects = logic_frame.get("affects", [])

        st.text(f"变化内容:")
        st.caption(what_changed)

        st.text(f"变化方向: {change_direction}")

        if affects:
            st.text(f"影响范围:")
            for affect in affects[:3]:
                st.caption(f"  • {affect}")
    else:
        st.info("无逻辑框架信息")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 信号标签和描述
# ═══════════════════════════════════════════════════════════════

st.subheader("📝 信号解读")

signal_label = selected_signal.get("signal_label", "")
signal_description = selected_signal.get("description", "")

col_label1, col_label2 = st.columns([1, 2])

with col_label1:
    st.markdown("**信号标签**")
    st.info(signal_label)

with col_label2:
    st.markdown("**详细描述**")
    st.write(signal_description)

st.divider()

# ═══════════════════════════════════════════════════════════════
# 影响标的
# ═══════════════════════════════════════════════════════════════

st.subheader("🎯 影响标的")

# 使用 affected_instruments 字段
instruments = selected_signal.get("affected_instruments", [])
affected_markets = selected_signal.get("affected_markets", [])

col_target1, col_target2 = st.columns([2, 1])

with col_target1:
    if instruments:
        st.markdown("**具体标的**")
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

with col_target2:
    if affected_markets:
        st.markdown("**影响市场**")
        for market in affected_markets:
            market_emoji = {"A_SHARE": "🇨🇳", "HK": "🇭🇰", "US": "🇺🇸"}.get(market, "🌍")
            st.caption(f"{market_emoji} {market}")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 决策链路
# ═══════════════════════════════════════════════════════════════

st.subheader("🔗 信号处理链路")

# 显示处理流程
st.markdown("""
<div style="background:#1e1e2e;border-radius:8px;padding:20px;margin-bottom:20px;">
    <div style="text-align:center;font-size:14px;color:#aaaaaa;">
        📰 M0 收集 → 🧠 M1 解码 → 💾 M2 存储 → ⚖️ M3 判断 → 🎯 M4 行动设计
    </div>
</div>
""", unsafe_allow_html=True)

col_chain1, col_chain2, col_chain3 = st.columns(3)

with col_chain1:
    st.markdown("##### ✅ M0 收集")
    st.caption(f"来源: {selected_signal.get('source_type', '未知')}")
    st.caption(f"文件: {selected_signal.get('source_ref', '未知')}")

with col_chain2:
    st.markdown("##### ✅ M1 解码")
    st.caption(f"信号类型: {selected_signal.get('signal_type', '未知')}")
    st.caption(f"时间范围: {selected_signal.get('time_horizon', '未知')}")

with col_chain3:
    st.markdown("##### ✅ M2 存储")
    st.caption(f"批次ID: {selected_signal.get('batch_id', '未知')[:30]}...")
    st.caption(f"信号ID: {selected_signal.get('signal_id', '未知')}")

# 查找关联的机会
import json
from pathlib import Path

signal_id = selected_signal.get("signal_id", "")
related_opportunities = []

opp_dir = Path(ROOT) / "data" / "opportunities"
if opp_dir.exists():
    for opp_file in opp_dir.glob("opp_*.json"):
        try:
            opp_data = json.loads(opp_file.read_text(encoding="utf-8"))
            if signal_id in opp_data.get("related_signals", []):
                related_opportunities.append({
                    "id": opp_data.get("opportunity_id", ""),
                    "title": opp_data.get("opportunity_title", ""),
                    "priority": opp_data.get("priority_level", ""),
                    "score": opp_data.get("opportunity_score", {}).get("overall_score", 0),
                })
        except:
            pass

st.divider()

# M3 判断结果
st.markdown("##### ⚖️ M3 判断结果")

if related_opportunities:
    st.success(f"✅ 该信号参与生成了 {len(related_opportunities)} 个投资机会")

    for opp in related_opportunities[:3]:
        with st.expander(f"🎯 {opp['title']}", expanded=False):
            col_opp1, col_opp2, col_opp3 = st.columns(3)

            with col_opp1:
                st.metric("优先级", opp['priority'].upper())

            with col_opp2:
                st.metric("综合评分", f"{opp['score']:.1f}/10")

            with col_opp3:
                st.metric("机会ID", opp['id'][:12] + "...")

    if len(related_opportunities) > 3:
        st.caption(f"还有 {len(related_opportunities) - 3} 个机会...")
else:
    st.info("该信号未生成投资机会（可能被M3判断为不构成机会，或信号强度不足）")
    st.markdown("**行动策略设计**")

    # 尝试加载关联的决策记录
    signal_metadata = selected_signal.get("metadata", {})
    action_plan = signal_metadata.get("action_plan", {})

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
