"""
MarketRadar Dashboard V2 - M12扫描监控页面
展示M12价格扫描的详细结果和历史
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import json

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 添加项目根目录到路径
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from dashboard_v2.components.metrics import status_badge, empty_state

# ═══════════════════════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="M12扫描监控 - MarketRadar V2",
    page_icon="📊",
    layout="wide",
)

st.title("📊 M12价格扫描监控")

# ═══════════════════════════════════════════════════════════════
# 数据加载
# ═══════════════════════════════════════════════════════════════

@st.cache_data(ttl=30)
def load_scan_results():
    """加载M12扫描结果历史"""
    scan_file = ROOT / "data" / "m12_scan_results.json"
    if not scan_file.exists():
        return []

    try:
        with open(scan_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # 按时间倒序排列
            return sorted(data, key=lambda x: x.get('timestamp', ''), reverse=True)
    except Exception as e:
        st.error(f"加载扫描结果失败: {e}")
        return []

@st.cache_data(ttl=30)
def load_scheduler_state():
    """加载调度器状态"""
    state_file = ROOT / "data" / "scheduler_state.json"
    if not state_file.exists():
        return {}

    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

scan_results = load_scan_results()
sched_state = load_scheduler_state()

# ═══════════════════════════════════════════════════════════════
# 顶部指标卡片
# ═══════════════════════════════════════════════════════════════

st.subheader("📈 扫描概览")

col1, col2, col3, col4 = st.columns(4)

# 统计最近24小时的扫描次数
now = datetime.now()
recent_scans = [s for s in scan_results if (now - datetime.fromisoformat(s['timestamp'])).total_seconds() < 86400]

with col1:
    st.metric("24小时扫描次数", len(recent_scans))

with col2:
    total_opps = sum(s.get('total_opportunities', 0) for s in recent_scans)
    st.metric("24小时发现机会", total_opps)

with col3:
    # 获取M12任务状态
    tasks = sched_state.get('tasks', {})
    m12_tasks = {k: v for k, v in tasks.items() if k.startswith('m12_') and '_scan' in k}
    enabled_count = sum(1 for t in m12_tasks.values() if t.get('enabled'))
    st.metric("启用的扫描任务", f"{enabled_count}/{len(m12_tasks)}")

with col4:
    if scan_results:
        last_scan = datetime.fromisoformat(scan_results[0]['timestamp'])
        mins_ago = int((now - last_scan).total_seconds() / 60)
        st.metric("上次扫描", f"{mins_ago}分钟前")
    else:
        st.metric("上次扫描", "无数据")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 市场选择器
# ═══════════════════════════════════════════════════════════════

st.subheader("🔍 扫描历史")

market_filter = st.selectbox(
    "选择市场",
    ["全部", "A股", "港股", "美股"],
    key="market_filter"
)

# 过滤数据
filtered_results = scan_results
if market_filter != "全部":
    market_map = {"A股": "a_share", "港股": "hk", "美股": "us"}
    market_key = market_map.get(market_filter)
    filtered_results = [
        s for s in scan_results
        if s.get('a_share', 0) > 0 if market_key == 'a_share' else
           s.get('hk', 0) > 0 if market_key == 'hk' else
           s.get('us', 0) > 0 if market_key == 'us' else True
    ]

# ═══════════════════════════════════════════════════════════════
# 扫描趋势图表
# ═══════════════════════════════════════════════════════════════

if filtered_results:
    st.subheader("📊 机会发现趋势")

    # 准备数据（最近50次扫描）
    recent_data = filtered_results[:50]
    recent_data.reverse()  # 时间正序

    timestamps = [datetime.fromisoformat(s['timestamp']) for s in recent_data]
    total_opps = [s.get('total_opportunities', 0) for s in recent_data]

    # 如果有市场细分数据
    if market_filter == "全部" and any('a_share' in s for s in recent_data):
        a_share_opps = [s.get('a_share', 0) for s in recent_data]
        hk_opps = [s.get('hk', 0) for s in recent_data]
        us_opps = [s.get('us', 0) for s in recent_data]

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=timestamps, y=a_share_opps, name='A股', mode='lines+markers', line=dict(color='#FF6B6B')))
        fig.add_trace(go.Scatter(x=timestamps, y=hk_opps, name='港股', mode='lines+markers', line=dict(color='#4ECDC4')))
        fig.add_trace(go.Scatter(x=timestamps, y=us_opps, name='美股', mode='lines+markers', line=dict(color='#95E1D3')))
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=timestamps, y=total_opps, name='机会数量', mode='lines+markers', line=dict(color='#667EEA')))

    fig.update_layout(
        xaxis_title="时间",
        yaxis_title="机会数量",
        hovermode='x unified',
        height=400,
        margin=dict(l=0, r=0, t=20, b=0)
    )

    st.plotly_chart(fig, use_container_width=True)

# ═══════════════════════════════════════════════════════════════
# 扫描历史表格
# ═══════════════════════════════════════════════════════════════

st.subheader("📋 扫描记录")

if not filtered_results:
    empty_state("暂无扫描记录", "📭")
else:
    # 转换为DataFrame
    rows = []
    for scan in filtered_results[:100]:  # 显示最近100条
        timestamp = datetime.fromisoformat(scan['timestamp'])

        # 市场细分
        markets = []
        if scan.get('a_share', 0) > 0:
            markets.append(f"A股({scan['a_share']})")
        if scan.get('hk', 0) > 0:
            markets.append(f"港股({scan['hk']})")
        if scan.get('us', 0) > 0:
            markets.append(f"美股({scan['us']})")

        market_str = ", ".join(markets) if markets else "-"

        rows.append({
            "时间": timestamp.strftime("%m-%d %H:%M"),
            "总机会": scan.get('total_opportunities', 0),
            "市场分布": market_str,
            "距今": f"{int((now - timestamp).total_seconds() / 60)}分钟前"
        })

    df = pd.DataFrame(rows)

    # 使用颜色标记机会数量
    def highlight_opportunities(val):
        if val > 5:
            return 'background-color: #C3F0CA'
        elif val > 0:
            return 'background-color: #FFF4C4'
        return ''

    styled_df = df.style.applymap(highlight_opportunities, subset=['总机会'])

    st.dataframe(styled_df, use_container_width=True, height=400)

st.divider()

# ═══════════════════════════════════════════════════════════════
# M12任务状态
# ═══════════════════════════════════════════════════════════════

st.subheader("⚙️ M12任务状态")

if not m12_tasks:
    empty_state("无M12任务信息", "📭")
else:
    task_rows = []
    for name, task in m12_tasks.items():
        # 解析市场
        if '_a_share' in name:
            market = "A股"
        elif '_hk' in name:
            market = "港股"
        elif '_us' in name:
            market = "美股"
        else:
            market = "-"

        # 解析任务类型
        if 'premarket' in name:
            task_type = "盘前"
        elif 'postmarket' in name:
            task_type = "盘后"
        else:
            task_type = "盘中"

        # 上次运行时间
        last_run = task.get('last_run', '')
        if last_run:
            try:
                dt = datetime.fromisoformat(last_run)
                mins_ago = int((now - dt).total_seconds() / 60)
                last_run_str = f"{dt.strftime('%H:%M')} ({mins_ago}分钟前)"
            except:
                last_run_str = last_run[:16]
        else:
            last_run_str = "从未运行"

        task_rows.append({
            "任务名": name,
            "市场": market,
            "类型": task_type,
            "间隔": f"{task.get('interval_minutes', '?')}分钟",
            "时间窗口": str(task.get('time_window') or "全天"),
            "启用": "✅" if task.get('enabled') else "❌",
            "运行次数": task.get('run_count', 0),
            "上次运行": last_run_str,
        })

    df_tasks = pd.DataFrame(task_rows)
    st.dataframe(df_tasks, use_container_width=True, height=400)

# ═══════════════════════════════════════════════════════════════
# 页脚说明
# ═══════════════════════════════════════════════════════════════

st.divider()
st.caption("💡 M12扫描监控：实时追踪价格异动扫描任务的执行情况和发现的机会")
