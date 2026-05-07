"""
MarketRadar Dashboard V2 - 情绪面页面
市场情绪可视化分析
"""
import sys
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# 添加项目根目录到路径
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from dashboard_v2.utils.data_loader import (
    load_sentiment_latest,
    load_sentiment_history,
    load_sentiment_trend,
)
from dashboard_v2.components.metrics import empty_state

# ═══════════════════════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="情绪面 - MarketRadar V2",
    page_icon="🧠",
    layout="wide",
)

st.title("🧠 市场情绪分析")
st.caption("📊 当前仅支持 A 股市场情绪分析（基于北向资金、东财评分、百度热搜、微博情绪）")

# ═══════════════════════════════════════════════════════════════
# 加载数据
# ═══════════════════════════════════════════════════════════════

latest_sentiment = load_sentiment_latest()
sentiment_history = load_sentiment_history(n=48)  # 最近48条
sentiment_trend = load_sentiment_trend(n=20)

# ═══════════════════════════════════════════════════════════════
# 立即采集按钮
# ═══════════════════════════════════════════════════════════════

col_btn1, col_btn2 = st.columns([1, 4])

with col_btn1:
    if st.button("🔄 立即采集", type="primary", use_container_width=True):
        import subprocess
        with st.spinner("正在采集市场情绪..."):
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "m7_scheduler.cli", "run", "sentiment_collect"],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    timeout=180,  # 增加到3分钟
                )
                if result.returncode == 0:
                    st.success("✅ 情绪采集完成")
                    st.rerun()
                else:
                    st.error(f"采集失败: {result.stderr}")
            except subprocess.TimeoutExpired:
                st.warning("⚠️ 采集超时（3分钟），任务可能仍在后台运行，请稍后刷新页面查看")
            except Exception as e:
                st.error(f"执行出错: {e}")

with col_btn2:
    if latest_sentiment:
        last_update = (latest_sentiment.get("timestamp") or "")[:19]
        st.caption(f"最后更新: {last_update}")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 当前情绪指标
# ═══════════════════════════════════════════════════════════════

st.subheader("📊 当前情绪")

if not latest_sentiment:
    empty_state("暂无情绪数据，请点击「立即采集」", "🧠")
else:
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        fear_greed = latest_sentiment.get("fear_greed_index", 50)
        st.metric("恐贪指数", f"{fear_greed}/100")

    with col2:
        label = latest_sentiment.get("sentiment_label", "中性")
        st.metric("市场情绪", label)

    with col3:
        direction = latest_sentiment.get("direction", "NEUTRAL")
        direction_map = {"BULLISH": "🟢 看多", "BEARISH": "🔴 看空", "NEUTRAL": "⚪ 中性"}
        st.metric("方向", direction_map.get(direction, direction))

    with col4:
        intensity = latest_sentiment.get("intensity", 5)
        st.metric("强度", f"{intensity}/10")

    # 恐贪指数仪表盘
    st.markdown("##### 恐贪指数仪表盘")

    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=fear_greed,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "恐贪指数"},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, 25], 'color': "#ff4b4b"},
                {'range': [25, 45], 'color': "#ffbb33"},
                {'range': [45, 55], 'color': "#aaaaaa"},
                {'range': [55, 75], 'color': "#33b5e5"},
                {'range': [75, 100], 'color': "#00c851"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': fear_greed
            }
        }
    ))

    fig_gauge.update_layout(
        height=300,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    st.plotly_chart(fig_gauge, use_container_width=True)

st.divider()

# ═══════════════════════════════════════════════════════════════
# 情绪趋势图
# ═══════════════════════════════════════════════════════════════

st.subheader("📈 情绪趋势")

if sentiment_history:
    df_history = pd.DataFrame(sentiment_history)

    # 确保有时间戳列
    if "timestamp" in df_history.columns:
        df_history["timestamp"] = pd.to_datetime(df_history["timestamp"])
        df_history = df_history.sort_values("timestamp")

        # 绘制恐贪指数趋势
        fig_trend = go.Figure()

        fig_trend.add_trace(go.Scatter(
            x=df_history["timestamp"],
            y=df_history.get("fear_greed_index", [50] * len(df_history)),
            mode='lines+markers',
            name='恐贪指数',
            line=dict(color='#33b5e5', width=2),
            marker=dict(size=6)
        ))

        # 添加参考线
        fig_trend.add_hline(y=50, line_dash="dash", line_color="gray", annotation_text="中性")
        fig_trend.add_hline(y=75, line_dash="dot", line_color="green", annotation_text="贪婪")
        fig_trend.add_hline(y=25, line_dash="dot", line_color="red", annotation_text="恐惧")

        fig_trend.update_layout(
            title="恐贪指数历史趋势",
            xaxis_title="时间",
            yaxis_title="指数值",
            height=400,
            hovermode='x unified',
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(30,30,46,0.5)",
        )

        st.plotly_chart(fig_trend, use_container_width=True)

        # 强度趋势
        if "intensity" in df_history.columns:
            fig_intensity = px.line(
                df_history,
                x="timestamp",
                y="intensity",
                title="情绪强度趋势",
                markers=True
            )

            fig_intensity.update_layout(
                height=300,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(30,30,46,0.5)",
            )

            st.plotly_chart(fig_intensity, use_container_width=True)
    else:
        st.warning("历史数据缺少时间戳信息")
else:
    st.info("暂无历史数据")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 北向资金流向
# ═══════════════════════════════════════════════════════════════

st.subheader("💰 北向资金流向")

if latest_sentiment and "northbound_flow" in latest_sentiment:
    northbound = latest_sentiment.get("northbound_flow", {})

    if isinstance(northbound, dict):
        col_nb1, col_nb2, col_nb3 = st.columns(3)

        with col_nb1:
            net_flow = northbound.get("net_inflow", 0)
            st.metric("净流入", f"¥{net_flow:.2f}亿")

        with col_nb2:
            sh_flow = northbound.get("shanghai", 0)
            st.metric("沪股通", f"¥{sh_flow:.2f}亿")

        with col_nb3:
            sz_flow = northbound.get("shenzhen", 0)
            st.metric("深股通", f"¥{sz_flow:.2f}亿")

        # 流向可视化
        if net_flow != 0:
            fig_flow = go.Figure(go.Indicator(
                mode="number+delta",
                value=net_flow,
                title={'text': "北向资金净流入（亿元）"},
                delta={'reference': 0, 'relative': False},
                domain={'x': [0, 1], 'y': [0, 1]}
            ))

            fig_flow.update_layout(
                height=200,
                paper_bgcolor="rgba(0,0,0,0)",
            )

            st.plotly_chart(fig_flow, use_container_width=True)
    else:
        st.info("北向资金数据格式异常")
else:
    st.info("暂无北向资金数据")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 板块情绪
# ═══════════════════════════════════════════════════════════════

st.subheader("📊 板块情绪")

if latest_sentiment and "sector_sentiment" in latest_sentiment:
    sector_data = latest_sentiment.get("sector_sentiment", {})

    if isinstance(sector_data, dict) and sector_data:
        # 转换为DataFrame
        df_sector = pd.DataFrame([
            {"板块": k, "情绪值": v}
            for k, v in sector_data.items()
        ])

        # 排序
        df_sector = df_sector.sort_values("情绪值", ascending=False)

        # 绘制柱状图
        fig_sector = px.bar(
            df_sector,
            x="板块",
            y="情绪值",
            title="各板块情绪分布",
            color="情绪值",
            color_continuous_scale=["red", "yellow", "green"]
        )

        fig_sector.update_layout(
            height=400,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(30,30,46,0.5)",
        )

        st.plotly_chart(fig_sector, use_container_width=True)
    else:
        st.info("暂无板块情绪数据")
else:
    st.info("暂无板块情绪数据")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 统计信息
# ═══════════════════════════════════════════════════════════════

if sentiment_trend:
    st.subheader("📈 统计信息")

    col_stat1, col_stat2, col_stat3 = st.columns(3)

    with col_stat1:
        avg_fear_greed = sentiment_trend.get("avg_fear_greed", 50)
        st.metric("平均恐贪指数", f"{avg_fear_greed:.1f}")

    with col_stat2:
        bullish_pct = sentiment_trend.get("bullish_percentage", 0)
        st.metric("看多占比", f"{bullish_pct:.1f}%")

    with col_stat3:
        bearish_pct = sentiment_trend.get("bearish_percentage", 0)
        st.metric("看空占比", f"{bearish_pct:.1f}%")
