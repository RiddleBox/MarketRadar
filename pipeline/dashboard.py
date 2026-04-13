"""
pipeline/dashboard.py — MarketRadar Streamlit Dashboard

启动：
  streamlit run pipeline/dashboard.py
  
或：
  cd D:/AIproject/MarketRadar
  streamlit run pipeline/dashboard.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

# 添加项目根目录到路径
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="MarketRadar",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ──────────────────────────────────────────────
# 数据加载函数
# ──────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_positions():
    pos_file = ROOT / "data" / "positions" / "positions.json"
    if not pos_file.exists():
        return []
    try:
        return json.loads(pos_file.read_text(encoding="utf-8"))
    except Exception:
        return []


@st.cache_data(ttl=30)
def load_opportunities():
    opp_dir = ROOT / "data" / "opportunities"
    if not opp_dir.exists():
        return []
    opps = []
    for f in sorted(opp_dir.glob("*.json"), reverse=True)[:5]:  # 最近5批
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                opps.extend(data)
        except Exception:
            pass
    return opps


@st.cache_data(ttl=60)
def load_signal_stats():
    try:
        from m2_storage.signal_store import SignalStore
        store = SignalStore()
        return store.stats()
    except Exception as e:
        return {"error": str(e)}


@st.cache_data(ttl=30)
def load_logs():
    log_dir = ROOT / "data" / "logs"
    if not log_dir.exists():
        return []
    logs = []
    for f in sorted(log_dir.glob("*.jsonl"), reverse=True)[:2]:
        try:
            for line in f.read_text(encoding="utf-8").strip().split("\n")[-20:]:
                if line.strip():
                    logs.append(json.loads(line))
        except Exception:
            pass
    return logs[-20:]


# ──────────────────────────────────────────────
# 侧边栏
# ──────────────────────────────────────────────

with st.sidebar:
    st.title("📡 MarketRadar")
    st.caption("客观信号驱动的市场机会发现系统")
    st.divider()

    # 系统状态
    st.subheader("系统状态")
    stats = load_signal_stats()
    if "error" not in stats:
        st.metric("信号总数", stats.get("total", 0))
    else:
        st.warning(f"Signal Store 不可用: {stats['error']}")

    positions = load_positions()
    active_pos = [p for p in positions if p.get("status") == "ACTIVE"]
    st.metric("活跃持仓", len(active_pos))

    opps = load_opportunities()
    urgent_opps = [o for o in opps if o.get("priority_level") == "urgent"]
    if urgent_opps:
        st.error(f"⚡ {len(urgent_opps)} 个 urgent 机会需要关注")

    st.divider()

    # 运行 Pipeline
    st.subheader("运行 Pipeline")
    input_text = st.text_area("输入原始文本（新闻/财报/公告）", height=120, placeholder="粘贴需要分析的文本...")
    markets_sel = st.multiselect("目标市场", ["A_SHARE", "HK", "US"], default=["A_SHARE", "HK"])
    source_type_sel = st.selectbox("来源类型", ["news", "report", "announcement"])

    if st.button("🚀 运行分析", type="primary", use_container_width=True):
        if input_text.strip():
            # 保存临时输入文件
            tmp_file = ROOT / "data" / "incoming" / f"dashboard_input_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            tmp_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_file.write_text(input_text, encoding="utf-8")

            markets_str = ",".join(markets_sel)
            with st.spinner("分析中..."):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "pipeline" / "run_pipeline.py"),
                        "--input", str(tmp_file),
                        "--market", markets_str,
                        "--source-type", source_type_sel,
                    ],
                    capture_output=True, text=True, cwd=str(ROOT),
                )
            if result.returncode == 0:
                st.success("✅ 分析完成！")
                st.cache_data.clear()
            else:
                st.error(f"运行失败:\n{result.stderr[-500:]}")
        else:
            st.warning("请输入文本")

    st.divider()
    if st.button("🔄 刷新数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


# ──────────────────────────────────────────────
# 主区域
# ──────────────────────────────────────────────

st.title("📡 MarketRadar Dashboard")
st.caption(f"最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ── 1. 当前持仓 ──────────────────────────────
st.header("💼 当前持仓")

if not active_pos:
    st.info("暂无活跃持仓")
else:
    import pandas as pd

    rows = []
    for p in active_pos:
        pnl = p.get("unrealized_pnl", 0) or 0
        pnl_str = f"{pnl*100:+.2f}%"
        pnl_color = "🟢" if pnl >= 0 else "🔴"
        rows.append({
            "持仓ID": p.get("position_id", ""),
            "品种": p.get("instrument", ""),
            "方向": p.get("direction", ""),
            "入场价": p.get("entry_price", ""),
            "当前价": p.get("current_price", ""),
            "浮盈": f"{pnl_color} {pnl_str}",
            "止损价": p.get("stop_loss_price", ""),
            "入场时间": p.get("entry_time", "")[:10] if p.get("entry_time") else "",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ── 2. 最近机会 ──────────────────────────────
st.header("🎯 最近机会")

if not opps:
    st.info("暂无机会记录")
else:
    priority_order = {"urgent": 0, "position": 1, "research": 2, "watch": 3}
    opps_sorted = sorted(opps, key=lambda o: (priority_order.get(o.get("priority_level", "watch"), 4), o.get("created_at", "")))

    col_count = min(len(opps_sorted), 3)
    cols = st.columns(col_count) if col_count > 0 else [st]

    priority_colors = {
        "urgent": "🔴", "position": "🟢", "research": "🟡", "watch": "⚪"
    }

    for i, opp in enumerate(opps_sorted[:6]):
        with cols[i % col_count]:
            priority = opp.get("priority_level", "watch")
            color = priority_colors.get(priority, "⚪")
            markets = ", ".join(opp.get("target_markets", []))
            created = opp.get("created_at", "")[:10] if opp.get("created_at") else ""

            st.markdown(f"""
**{color} {opp.get('opportunity_title', '未命名')}**

_{opp.get('opportunity_thesis', '')[:100]}..._

🏷️ `{priority}` | 📍 {markets} | 📅 {created}
""")
            with st.expander("详情"):
                st.write("**为什么是现在：**", opp.get("why_now", ""))
                st.write("**风险回报：**", opp.get("risk_reward_profile", ""))
                if opp.get("key_assumptions"):
                    st.write("**关键假设：**")
                    for a in opp["key_assumptions"]:
                        st.write(f"- {a}")

# ── 3. 信号统计 ──────────────────────────────
st.header("📊 信号统计")

col1, col2 = st.columns(2)

with col1:
    st.subheader("按信号类型")
    if "by_signal_type" in stats and stats["by_signal_type"]:
        try:
            import pandas as pd
            df = pd.DataFrame.from_dict(
                stats["by_signal_type"], orient="index", columns=["数量"]
            )
            st.bar_chart(df)
        except Exception:
            st.json(stats.get("by_signal_type", {}))
    else:
        st.info("暂无信号数据")

with col2:
    st.subheader("近期批次")
    if "recent_batches" in stats and stats["recent_batches"]:
        try:
            import pandas as pd
            df = pd.DataFrame.from_dict(
                stats["recent_batches"], orient="index", columns=["信号数"]
            )
            st.bar_chart(df)
        except Exception:
            st.json(stats.get("recent_batches", {}))
    else:
        st.info("暂无批次数据")

# ── 4. 系统日志 ──────────────────────────────
st.header("📋 系统日志")

logs = load_logs()
if not logs:
    st.info("暂无日志记录")
else:
    for entry in reversed(logs[-20:]):
        ts = entry.get("time", "")[:19] if entry.get("time") else ""
        level = entry.get("level", "INFO")
        msg = entry.get("message", str(entry))
        icon = {"ERROR": "🔴", "WARNING": "🟡", "INFO": "🔵"}.get(level, "⚪")
        st.text(f"{icon} [{ts}] {msg}")

# ── 底部：数据库状态 ──────────────────────────
with st.expander("🔧 系统信息"):
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("总持仓（含已关闭）", len(positions))
    with col_b:
        closed = [p for p in positions if p.get("status") == "CLOSED"]
        wins = [p for p in closed if (p.get("realized_pnl") or 0) > 0]
        wr = f"{len(wins)/len(closed)*100:.1f}%" if closed else "N/A"
        st.metric("历史胜率", wr)
    with col_c:
        total_pnl = sum((p.get("realized_pnl") or 0) for p in closed)
        st.metric("历史总盈亏", f"{total_pnl*100:.2f}%")
