"""
MarketRadar Dashboard V2 - 机会页面
查看M12扫描发现的交易机会
"""
import sys
from pathlib import Path

import streamlit as st

# 添加项目根目录到路径
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from dashboard_v2.utils.data_loader import load_opportunities
from dashboard_v2.components.metrics import priority_badge, signal_direction_badge, empty_state

# ═══════════════════════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="机会 - MarketRadar V2",
    page_icon="🎯",
    layout="wide",
)

st.title("🎯 交易机会")

# ═══════════════════════════════════════════════════════════════
# 加载数据
# ═══════════════════════════════════════════════════════════════

opportunities = load_opportunities()

# ═══════════════════════════════════════════════════════════════
# 筛选器
# ═══════════════════════════════════════════════════════════════

st.subheader("🔍 筛选条件")

col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    filter_priority = st.multiselect(
        "优先级",
        ["urgent", "position", "research", "watch"],
        default=["urgent", "position", "research"],
        format_func=lambda x: {"urgent": "紧急", "position": "持仓", "research": "研究", "watch": "观察"}[x]
    )

with col_f2:
    all_markets = sorted({m for o in opportunities for m in o.get("target_markets", [])})
    filter_markets = st.multiselect(
        "市场",
        all_markets or ["A_SHARE", "HK", "US"],
        default=all_markets or ["A_SHARE"]
    )

with col_f3:
    filter_direction = st.multiselect(
        "方向",
        ["BULLISH", "BEARISH", "NEUTRAL"],
        default=["BULLISH", "BEARISH"],
        format_func=lambda x: {"BULLISH": "看多", "BEARISH": "看空", "NEUTRAL": "中性"}[x]
    )

# 应用筛选
filtered_opps = [
    o for o in opportunities
    if o.get("priority_level", "watch") in filter_priority
    and any(m in filter_markets for m in o.get("target_markets", []))
    and o.get("trade_direction", "NEUTRAL") in filter_direction
]

# 排序：优先级 > 信号数量
priority_order = {"urgent": 0, "position": 1, "research": 2, "watch": 3}
filtered_opps.sort(key=lambda o: (
    priority_order.get(o.get("priority_level", "watch"), 4),
    -(o.get("signal_count") or len(o.get("related_signals", []))),
))

st.caption(f"显示 {len(filtered_opps)} / {len(opportunities)} 个机会")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 机会列表
# ═══════════════════════════════════════════════════════════════

if not filtered_opps:
    empty_state("暂无符合条件的机会", "🎯")
else:
    for opp in filtered_opps:
        priority = opp.get("priority_level", "watch")
        direction = opp.get("trade_direction", "NEUTRAL")
        title = opp.get("opportunity_title", "未命名机会")
        markets = " | ".join(opp.get("target_markets", []))
        instruments = opp.get("target_instruments", [])
        created_at = (opp.get("created_at") or "")[:19]

        # 卡片标题
        priority_html = priority_badge(priority)
        direction_html = signal_direction_badge(direction)

        with st.expander(
            f"**{title}** | {markets} | {created_at}",
            expanded=(priority in ["urgent", "position"])
        ):
            # 显示优先级和方向
            st.markdown(f"{priority_html} &nbsp; {direction_html}", unsafe_allow_html=True)

            col_left, col_right = st.columns([2, 1])

            with col_left:
                st.markdown("##### 📌 机会论点")
                thesis = opp.get("opportunity_thesis", "")
                st.write(thesis if thesis else "_暂无论点_")

                st.markdown("##### ⚡ 为什么是现在")
                why_now = opp.get("why_now", "")
                st.write(why_now if why_now else "_暂无说明_")

                # 关键假设
                assumptions = opp.get("key_assumptions", [])
                if assumptions:
                    st.markdown("##### 🔑 关键假设")
                    for assumption in assumptions[:3]:
                        st.write(f"• {assumption}")

                # 反驳证据
                counter = opp.get("counter_evidence", [])
                if counter:
                    st.markdown("##### ⚠️ 反驳证据")
                    for evidence in counter[:2]:
                        st.write(f"• {evidence}")

            with col_right:
                st.markdown("##### 📊 关键指标")

                # 时效性
                window = opp.get("opportunity_window", {})
                horizon = window.get("horizon", "未知") if isinstance(window, dict) else "未知"
                st.text(f"时效: {horizon}")

                # 信号数量
                signal_count = len(opp.get("related_signals", []))
                st.text(f"信号数: {signal_count}")

                # 风险回报
                risk_reward = opp.get("risk_reward_profile", "未知")
                st.text(f"风险回报: {risk_reward}")

                # 相关品种
                if instruments:
                    st.markdown("##### 🏷️ 相关品种")
                    st.write("、".join(instruments[:5]))

                # 操作按钮
                st.markdown("---")
                st.markdown("##### 🎬 操作")

                if st.button("📊 查看详情", key=f"detail_{opp.get('opportunity_id', '')}"):
                    st.info("详情页面待实现")

                if st.button("🔍 查看信号", key=f"signals_{opp.get('opportunity_id', '')}"):
                    st.info("信号查看功能待实现")

                if st.button("💼 开仓", key=f"open_{opp.get('opportunity_id', '')}", type="primary"):
                    st.warning("开仓功能待实现")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 统计信息
# ═══════════════════════════════════════════════════════════════

if opportunities:
    st.subheader("📈 机会统计")

    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)

    with col_stat1:
        urgent_count = sum(1 for o in opportunities if o.get("priority_level") == "urgent")
        st.metric("紧急机会", urgent_count)

    with col_stat2:
        bullish_count = sum(1 for o in opportunities if o.get("trade_direction") == "BULLISH")
        st.metric("看多机会", bullish_count)

    with col_stat3:
        bearish_count = sum(1 for o in opportunities if o.get("trade_direction") == "BEARISH")
        st.metric("看空机会", bearish_count)

    with col_stat4:
        avg_signals = sum(len(o.get("related_signals", [])) for o in opportunities) / len(opportunities)
        st.metric("平均信号数", f"{avg_signals:.1f}")
