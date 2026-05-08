"""
MarketRadar Dashboard V2 - M13调研页面
查看M13调研统计、缓存状态、手动触发调研
"""
import sys
from pathlib import Path

import streamlit as st

# 添加项目根目录到路径
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from dashboard_v2.utils.data_loader import (
    load_m13_stats,
    load_m13_cache_stats,
    load_m13_recent_research,
)
from dashboard_v2.components.metrics import empty_state

# ═══════════════════════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="调研 - MarketRadar V2",
    page_icon="🔬",
    layout="wide",
)

st.title("🔬 M13 调研中心")

# ═══════════════════════════════════════════════════════════════
# 加载数据
# ═══════════════════════════════════════════════════════════════

stats = load_m13_stats()
cache_stats = load_m13_cache_stats()
recent_research = load_m13_recent_research(limit=20)

# ═══════════════════════════════════════════════════════════════
# 统计卡片
# ═══════════════════════════════════════════════════════════════

st.subheader("📊 调研统计")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("总调研数", stats.get("total_research", 0))

with col2:
    by_level = stats.get("by_level", {})
    quick_count = by_level.get("QUICK", 0)
    st.metric("快速验证", quick_count)

with col3:
    standard_count = by_level.get("STANDARD", 0)
    st.metric("标准调研", standard_count)

with col4:
    deep_count = by_level.get("DEEP", 0)
    st.metric("深度调研", deep_count)

st.divider()

# ═══════════════════════════════════════════════════════════════
# 缓存状态
# ═══════════════════════════════════════════════════════════════

st.subheader("💾 缓存状态")

col_c1, col_c2, col_c3, col_c4 = st.columns(4)

with col_c1:
    st.metric("总缓存数", cache_stats.get("total", 0))

with col_c2:
    valid = cache_stats.get("valid", 0)
    st.metric("有效缓存", valid, delta=None)

with col_c3:
    expired = cache_stats.get("expired", 0)
    st.metric("过期缓存", expired, delta=None if expired == 0 else f"-{expired}")

with col_c4:
    total = cache_stats.get("total", 0)
    hit_rate = (valid / total * 100) if total > 0 else 0
    st.metric("缓存命中率", f"{hit_rate:.1f}%")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 手动调研
# ═══════════════════════════════════════════════════════════════

st.subheader("🎯 手动调研")

with st.form("manual_research_form"):
    col_f1, col_f2 = st.columns(2)

    with col_f1:
        symbol = st.text_input(
            "股票代码",
            placeholder="例如: 000001",
            help="输入6位A股代码"
        )

    with col_f2:
        level = st.selectbox(
            "调研深度",
            ["QUICK", "STANDARD", "DEEP"],
            format_func=lambda x: {
                "QUICK": "快速验证 (30秒)",
                "STANDARD": "标准调研 (2分钟)",
                "DEEP": "深度调研 (5分钟)"
            }[x]
        )

    context = st.text_area(
        "背景信息",
        placeholder="例如: 公司发布Q1财报，营收同比增长30%",
        help="提供调研背景，帮助LLM更好地分析"
    )

    submitted = st.form_submit_button("🚀 开始调研", type="primary")

    if submitted:
        if not symbol:
            st.error("请输入股票代码")
        elif len(symbol) != 6 or not symbol.isdigit():
            st.error("请输入有效的6位A股代码")
        else:
            with st.spinner(f"正在执行 {level} 调研..."):
                try:
                    # 初始化M13组件
                    from integrations.init_data_providers import initialize_data_providers
                    from m13_research.research_agent import ResearchAgent
                    from m13_research.llm_analyzer import LLMAnalyzer
                    from m13_research.cache_manager import CacheManager
                    from m13_research.data_manager_adapter import get_m13_data_manager
                    from core.llm_client import LLMClient

                    initialize_data_providers()
                    data_manager = get_m13_data_manager()
                    llm_client = LLMClient()
                    llm_analyzer = LLMAnalyzer(llm_client)
                    cache_manager = CacheManager(ROOT / "data" / "research_cache")

                    agent = ResearchAgent(
                        data_manager=data_manager,
                        llm_analyzer=llm_analyzer,
                        cache_manager=cache_manager
                    )

                    # 执行调研
                    if level == "QUICK":
                        research = agent.quick_research(symbol, context or "手动调研")
                    elif level == "STANDARD":
                        research = agent.standard_research(symbol, context or "手动调研")
                    else:
                        research = agent.deep_research(symbol, context or "手动调研")

                    # 显示结果
                    st.success("✅ 调研完成！")

                    col_r1, col_r2 = st.columns(2)

                    with col_r1:
                        st.markdown("##### 📊 置信度调整")
                        st.metric("乘数", f"{research.confidence_multiplier:.2f}x")
                        st.metric("增量", f"{research.confidence_delta:+.2f}")
                        if research.has_major_negative:
                            st.error("⚠️ 发现重大利空")

                    with col_r2:
                        st.markdown("##### 📚 数据来源")
                        st.text(f"新闻: {len(research.news)}条")
                        st.text(f"研报: {len(research.reports)}篇")
                        st.text(f"缓存: {'命中' if research.cache_hit else '未命中'}")

                    st.markdown("##### 📝 调研摘要")
                    st.write(research.summary)

                    if research.key_findings:
                        st.markdown("##### 🔍 关键发现")
                        for i, finding in enumerate(research.key_findings, 1):
                            st.write(f"{i}. {finding}")

                    if research.risk_factors:
                        st.markdown("##### ⚠️ 风险因素")
                        for i, risk in enumerate(research.risk_factors, 1):
                            st.write(f"{i}. {risk}")

                except Exception as e:
                    st.error(f"调研失败: {e}")
                    import traceback
                    st.code(traceback.format_exc())

st.divider()

# ═══════════════════════════════════════════════════════════════
# 最近调研记录
# ═══════════════════════════════════════════════════════════════

st.subheader("📜 最近调研记录")

if not recent_research:
    empty_state("暂无调研记录", "🔬")
else:
    # 筛选器
    col_filter1, col_filter2 = st.columns(2)

    with col_filter1:
        filter_level = st.multiselect(
            "调研深度",
            ["QUICK", "STANDARD", "DEEP"],
            default=["QUICK", "STANDARD", "DEEP"],
            format_func=lambda x: {"QUICK": "快速", "STANDARD": "标准", "DEEP": "深度"}[x]
        )

    with col_filter2:
        filter_confidence = st.selectbox(
            "置信度调整",
            ["全部", "正面 (>0)", "负面 (<0)", "中性 (=0)"],
        )

    # 应用筛选
    filtered = recent_research
    if filter_level:
        filtered = [r for r in filtered if r.get("level", "") in filter_level]

    if filter_confidence == "正面 (>0)":
        filtered = [r for r in filtered if r.get("confidence_delta", 0) > 0]
    elif filter_confidence == "负面 (<0)":
        filtered = [r for r in filtered if r.get("confidence_delta", 0) < 0]
    elif filter_confidence == "中性 (=0)":
        filtered = [r for r in filtered if r.get("confidence_delta", 0) == 0]

    st.caption(f"显示 {len(filtered)} / {len(recent_research)} 条记录")

    # 显示记录
    for record in filtered[:10]:
        symbol = record.get("symbol", "")
        level = record.get("level", "")
        cached_at = record.get("cached_at", "")[:19]
        delta = record.get("confidence_delta", 0)
        findings = record.get("key_findings", [])

        level_emoji = {"QUICK": "⚡", "STANDARD": "📊", "DEEP": "🔍"}.get(level, "📝")
        delta_color = "green" if delta > 0 else "red" if delta < 0 else "gray"

        with st.expander(f"{level_emoji} **{symbol}** | {level} | {cached_at}"):
            col_d1, col_d2 = st.columns([1, 2])

            with col_d1:
                st.markdown(f"**置信度调整:** :{delta_color}[{delta:+.2f}]")

            with col_d2:
                if findings:
                    st.markdown("**关键发现:**")
                    for finding in findings[:3]:
                        st.write(f"• {finding}")
                else:
                    st.write("_无关键发现_")
