"""
MarketRadar Dashboard V2 - 持仓页面
查看当前持仓、盈亏情况、实时价格
"""
import sys
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd

# 添加项目根目录到路径
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from dashboard_v2.utils.data_loader import load_positions_open, load_positions_closed
from dashboard_v2.components.metrics import metric_card

# ═══════════════════════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="持仓 - MarketRadar V2",
    page_icon="💼",
    layout="wide",
)

st.title("💼 持仓管理")

# ═══════════════════════════════════════════════════════════════
# 加载数据
# ═══════════════════════════════════════════════════════════════

positions_open = load_positions_open()
positions_closed = load_positions_closed()

# ═══════════════════════════════════════════════════════════════
# 总览指标
# ═══════════════════════════════════════════════════════════════

st.subheader("📊 持仓总览")

# 计算总览数据
total_positions = len(positions_open)
total_cost = sum(p.get("entry_price", 0) * p.get("quantity", 0) for p in positions_open)
total_value = sum(p.get("current_price", p.get("entry_price", 0)) * p.get("quantity", 0) for p in positions_open)
total_pnl = total_value - total_cost
total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("持仓数量", total_positions)

with col2:
    st.metric("总成本", f"¥{total_cost:,.2f}")

with col3:
    st.metric("当前市值", f"¥{total_value:,.2f}")

with col4:
    pnl_color = "🟢" if total_pnl >= 0 else "🔴"
    st.metric(
        "总盈亏",
        f"¥{total_pnl:,.2f}",
        f"{pnl_color} {total_pnl_pct:+.2f}%"
    )

st.divider()

# ═══════════════════════════════════════════════════════════════
# 持仓列表
# ═══════════════════════════════════════════════════════════════

st.subheader("📋 当前持仓")

if not positions_open:
    st.info("暂无持仓")
else:
    # 转换为DataFrame便于展示
    df_positions = pd.DataFrame(positions_open)

    # 计算衍生字段 - 使用 fillna 处理缺失值
    # 确保必需的列存在
    if "entry_price" not in df_positions.columns:
        st.error("持仓数据缺少 entry_price 字段，请检查数据库")
        st.stop()

    if "current_price" not in df_positions.columns:
        df_positions["current_price"] = df_positions["entry_price"]
    else:
        df_positions["current_price"] = df_positions["current_price"].fillna(df_positions["entry_price"])

    df_positions["市值"] = df_positions["quantity"] * df_positions["current_price"]
    df_positions["成本"] = df_positions["quantity"] * df_positions["entry_price"]
    df_positions["盈亏"] = df_positions["市值"] - df_positions["成本"]
    df_positions["盈亏率%"] = (df_positions["盈亏"] / df_positions["成本"] * 100).round(2)

    # 选择展示列
    display_cols = {
        "instrument": "代码",
        "market": "市场",
        "quantity": "数量",
        "entry_price": "成本价",
        "current_price": "现价",
        "市值": "市值",
        "盈亏": "盈亏",
        "盈亏率%": "盈亏率%",
        "entry_time": "开仓时间",
    }

    # 处理列名映射
    available_cols = [col for col in display_cols.keys() if col in df_positions.columns or col in ["市值", "成本", "盈亏", "盈亏率%"]]
    df_display = df_positions[available_cols].copy()
    df_display.columns = [display_cols[col] for col in available_cols]

    # 格式化数值列
    if "成本价" in df_display.columns:
        df_display["成本价"] = df_display["成本价"].apply(lambda x: f"¥{x:.2f}")
    if "现价" in df_display.columns:
        df_display["现价"] = df_display["现价"].apply(lambda x: f"¥{x:.2f}" if pd.notna(x) else "-")
    if "市值" in df_display.columns:
        df_display["市值"] = df_display["市值"].apply(lambda x: f"¥{x:,.2f}")
    if "盈亏" in df_display.columns:
        df_display["盈亏"] = df_display["盈亏"].apply(lambda x: f"¥{x:+,.2f}")
    if "盈亏率%" in df_display.columns:
        df_display["盈亏率%"] = df_display["盈亏率%"].apply(lambda x: f"{x:+.2f}%")
    if "开仓时间" in df_display.columns:
        df_display["开仓时间"] = pd.to_datetime(df_display["开仓时间"]).dt.strftime("%Y-%m-%d %H:%M")

    # 显示表格
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
    )

    # ── 持仓详情卡片 ──
    st.subheader("📌 持仓详情")

    for pos in positions_open:
        instrument = pos.get("instrument", "未知")
        quantity = pos.get("quantity", 0)
        entry_price = pos.get("entry_price", 0)
        current_price = pos.get("current_price", entry_price)
        stop_loss_price = pos.get("stop_loss_price")
        take_profit_price = pos.get("take_profit_price")
        direction = pos.get("direction", "BULLISH")

        cost = quantity * entry_price
        value = quantity * current_price
        pnl = value - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0

        entry_time = pos.get("entry_time", "")
        if entry_time:
            try:
                entry_time = datetime.fromisoformat(entry_time).strftime("%Y-%m-%d %H:%M")
            except:
                entry_time = str(entry_time)[:16]

        # 计算距离止损/止盈的百分比
        if direction == "BULLISH":
            stop_distance_pct = ((current_price - stop_loss_price) / current_price * 100) if stop_loss_price else None
            profit_distance_pct = ((take_profit_price - current_price) / current_price * 100) if take_profit_price else None
        else:
            stop_distance_pct = ((stop_loss_price - current_price) / current_price * 100) if stop_loss_price else None
            profit_distance_pct = ((current_price - take_profit_price) / current_price * 100) if take_profit_price else None

        # 触发预警
        trigger_warning = ""
        if stop_distance_pct is not None and stop_distance_pct < 2:
            trigger_warning = "⚠️ 接近止损"
        elif profit_distance_pct is not None and profit_distance_pct < 2:
            trigger_warning = "🎯 接近止盈"

        with st.expander(f"**{instrument}** | {pnl_pct:+.2f}% {trigger_warning}"):
            col_a, col_b, col_c = st.columns(3)

            with col_a:
                st.markdown("##### 持仓信息")
                st.text(f"标的: {instrument}")
                st.text(f"方向: {'做多' if direction == 'BULLISH' else '做空'}")
                st.text(f"数量: {quantity}")
                st.text(f"成本价: ¥{entry_price:.2f}")
                st.text(f"现价: ¥{current_price:.2f}")
                st.text(f"开仓时间: {entry_time}")

            with col_b:
                st.markdown("##### 盈亏情况")
                st.text(f"成本: ¥{cost:,.2f}")
                st.text(f"市值: ¥{value:,.2f}")
                pnl_emoji = "🟢" if pnl >= 0 else "🔴"
                st.text(f"盈亏: {pnl_emoji} ¥{pnl:+,.2f}")
                st.text(f"盈亏率: {pnl_emoji} {pnl_pct:+.2f}%")

            with col_c:
                st.markdown("##### 风控信息")
                if stop_loss_price:
                    st.text(f"止损价: ¥{stop_loss_price:.2f}")
                    if stop_distance_pct is not None:
                        st.text(f"距止损: {stop_distance_pct:+.2f}%")
                else:
                    st.text("止损价: 未设置")

                if take_profit_price:
                    st.text(f"止盈价: ¥{take_profit_price:.2f}")
                    if profit_distance_pct is not None:
                        st.text(f"距止盈: {profit_distance_pct:+.2f}%")
                else:
                    st.text("止盈价: 未设置")

            # 操作按钮
            col_op1, col_op2, col_op3 = st.columns(3)
            with col_op1:
                if st.button(f"📊 查看K线", key=f"chart_{instrument}"):
                    st.info("K线图功能待实现")
            with col_op2:
                if st.button(f"🔍 查看信号", key=f"signal_{instrument}"):
                    st.info("信号查看功能待实现")
            with col_op3:
                if st.button(f"❌ 平仓", key=f"close_{instrument}", type="secondary"):
                    st.warning("平仓功能待实现")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 历史持仓
# ═══════════════════════════════════════════════════════════════

st.subheader("📜 历史持仓")

with st.expander(f"查看已平仓记录 ({len(positions_closed)} 条)"):
    if not positions_closed:
        st.info("暂无历史持仓")
    else:
        df_closed = pd.DataFrame(positions_closed)

        # 计算盈亏
        if "quantity" in df_closed.columns and "cost_basis" in df_closed.columns and "close_price" in df_closed.columns:
            df_closed["成本"] = df_closed["quantity"] * df_closed["cost_basis"]
            df_closed["收入"] = df_closed["quantity"] * df_closed["close_price"]
            df_closed["盈亏"] = df_closed["收入"] - df_closed["成本"]
            df_closed["盈亏率%"] = (df_closed["盈亏"] / df_closed["成本"] * 100).round(2)

        # 选择展示列
        closed_display_cols = {
            "symbol": "代码",
            "name": "名称",
            "quantity": "数量",
            "cost_basis": "成本价",
            "close_price": "平仓价",
            "盈亏": "盈亏",
            "盈亏率%": "盈亏率%",
            "opened_at": "开仓时间",
            "closed_at": "平仓时间",
        }

        available_closed_cols = [col for col in closed_display_cols.keys() if col in df_closed.columns or col in ["成本", "收入", "盈亏", "盈亏率%"]]
        df_closed_display = df_closed[available_closed_cols].copy()
        df_closed_display.columns = [closed_display_cols[col] for col in available_closed_cols]

        # 格式化
        if "成本价" in df_closed_display.columns:
            df_closed_display["成本价"] = df_closed_display["成本价"].apply(lambda x: f"¥{x:.2f}")
        if "平仓价" in df_closed_display.columns:
            df_closed_display["平仓价"] = df_closed_display["平仓价"].apply(lambda x: f"¥{x:.2f}")
        if "盈亏" in df_closed_display.columns:
            df_closed_display["盈亏"] = df_closed_display["盈亏"].apply(lambda x: f"¥{x:+,.2f}")
        if "盈亏率%" in df_closed_display.columns:
            df_closed_display["盈亏率%"] = df_closed_display["盈亏率%"].apply(lambda x: f"{x:+.2f}%")
        if "开仓时间" in df_closed_display.columns:
            df_closed_display["开仓时间"] = pd.to_datetime(df_closed_display["开仓时间"]).dt.strftime("%Y-%m-%d")
        if "平仓时间" in df_closed_display.columns:
            df_closed_display["平仓时间"] = pd.to_datetime(df_closed_display["平仓时间"]).dt.strftime("%Y-%m-%d")

        st.dataframe(
            df_closed_display,
            use_container_width=True,
            hide_index=True,
        )

        # 历史统计
        if "盈亏" in df_closed.columns:
            total_closed_pnl = df_closed["盈亏"].sum()
            win_count = (df_closed["盈亏"] > 0).sum()
            loss_count = (df_closed["盈亏"] < 0).sum()
            win_rate = (win_count / len(df_closed) * 100) if len(df_closed) > 0 else 0

            st.markdown("---")
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            with col_stat1:
                st.metric("总盈亏", f"¥{total_closed_pnl:+,.2f}")
            with col_stat2:
                st.metric("盈利次数", win_count)
            with col_stat3:
                st.metric("亏损次数", loss_count)
            with col_stat4:
                st.metric("胜率", f"{win_rate:.1f}%")
