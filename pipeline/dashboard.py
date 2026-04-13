"""
pipeline/dashboard.py — MarketRadar Streamlit Dashboard

启动：
  cd D:/AIproject/MarketRadar
  streamlit run pipeline/dashboard.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="MarketRadar",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# CSS 注入
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
.priority-urgent   { color: #ff4b4b; font-weight: bold; }
.priority-position { color: #00c851; font-weight: bold; }
.priority-research { color: #ffbb33; font-weight: bold; }
.priority-watch    { color: #aaaaaa; }
.signal-bullish    { color: #00c851; }
.signal-bearish    { color: #ff4b4b; }
.signal-neutral    { color: #aaaaaa; }
.metric-up         { color: #00c851; }
.metric-down       { color: #ff4b4b; }
.card {
    background: #1e1e2e;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 8px;
    border-left: 3px solid #444;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# 数据加载（带缓存）
# ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_positions() -> list:
    pos_file = ROOT / "data" / "positions" / "positions.json"
    if not pos_file.exists():
        return []
    try:
        return json.loads(pos_file.read_text(encoding="utf-8"))
    except Exception:
        return []


@st.cache_data(ttl=30)
def load_opportunities() -> list:
    opp_dir = ROOT / "data" / "opportunities"
    if not opp_dir.exists():
        return []
    opps = []
    for f in sorted(opp_dir.glob("*.json"), reverse=True)[:10]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                opps.extend(data)
        except Exception:
            pass
    # 去重（按 opportunity_id）
    seen = set()
    unique = []
    for o in opps:
        oid = o.get("opportunity_id", "")
        if oid not in seen:
            seen.add(oid)
            unique.append(o)
    return unique


@st.cache_data(ttl=30)
def load_signal_stats() -> dict:
    try:
        from m2_storage.signal_store import SignalStore
        return SignalStore().stats()
    except Exception as e:
        return {"error": str(e), "total": 0}


@st.cache_data(ttl=30)
def load_signals_recent(days: int = 7) -> list:
    try:
        from m2_storage.signal_store import SignalStore
        from core.schemas import Market
        store = SignalStore()
        sigs = store.get_by_time_range(
            start=datetime.now() - timedelta(days=days),
            end=datetime.now(),
        )
        return [s.model_dump(mode="json") for s in sigs]
    except Exception:
        return []


def clear_cache():
    st.cache_data.clear()


# ─────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────

PRIORITY_ICON = {"urgent": "🔴", "position": "🟢", "research": "🟡", "watch": "⚪"}
PRIORITY_ORDER = {"urgent": 0, "position": 1, "research": 2, "watch": 3}
DIR_ICON = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "⚪"}
DIR_LABEL = {"BULLISH": "看多", "BEARISH": "看空", "NEUTRAL": "中性"}

SIGNAL_TYPE_CN = {
    "macro": "宏观",
    "policy": "政策",
    "technical": "技术",
    "capital_flow": "资金流",
    "industry": "行业",
    "event_driven": "事件",
    "sentiment": "情绪",
    "fundamental": "基本面",
}


def pnl_str(pnl: float | None) -> str:
    if pnl is None:
        return "—"
    color = "#00c851" if pnl >= 0 else "#ff4b4b"
    sign = "+" if pnl >= 0 else ""
    return f'<span style="color:{color}">{sign}{pnl*100:.2f}%</span>'


def fmt_dt(s: str | None, fmt: str = "%m-%d %H:%M") -> str:
    if not s:
        return "—"
    try:
        return datetime.fromisoformat(s[:19]).strftime(fmt)
    except Exception:
        return s[:10]


# ─────────────────────────────────────────────────────────────
# 侧边栏
# ─────────────────────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/ios-filled/50/00c851/radar.png", width=40)
    st.title("MarketRadar")
    st.caption("客观信号驱动的市场机会发现系统")
    st.divider()

    # ── 核心指标 ──
    stats = load_signal_stats()
    positions = load_positions()
    opps = load_opportunities()
    active_pos = [p for p in positions if p.get("status") == "ACTIVE"]
    urgent_opps = [o for o in opps if o.get("priority_level") in ("urgent", "position")]

    c1, c2 = st.columns(2)
    with c1:
        st.metric("📶 信号总数", stats.get("total", 0))
        st.metric("💼 活跃持仓", len(active_pos))
    with c2:
        st.metric("🎯 机会总数", len(opps))
        st.metric("⚡ 高优先级", len(urgent_opps))

    if urgent_opps:
        st.error(f"⚡ {len(urgent_opps)} 个高优先级机会待处理")

    st.divider()

    # ── 快速分析入口（M0→M1→M2→M3→M4）──
    st.subheader("🚀 快速分析")
    input_text = st.text_area(
        "粘贴新闻 / 公告 / 财报摘要",
        height=140,
        placeholder="直接粘贴文本，系统会自动提取信号并判断机会...",
        key="quick_input",
    )
    markets_sel = st.multiselect(
        "目标市场", ["A_SHARE", "HK", "US"], default=["A_SHARE", "HK"]
    )
    run_btn = st.button("▶ 运行完整分析", type="primary", use_container_width=True)

    if run_btn:
        if not input_text.strip():
            st.warning("请输入文本")
        else:
            _run_analysis(input_text, markets_sel)

    st.divider()
    if st.button("🔄 刷新", use_container_width=True):
        clear_cache()
        st.rerun()

    st.caption(f"更新: {datetime.now().strftime('%H:%M:%S')}")


# ─────────────────────────────────────────────────────────────
# 快速分析（侧边栏调用，需在侧边栏代码之前定义）
# ─────────────────────────────────────────────────────────────

def _run_analysis(text: str, markets: list):
    """从侧边栏触发完整分析链路"""
    import os
    from m0_collector.providers.manual import ManualProvider
    from m0_collector.dedup import DedupIndex
    from m0_collector.normalizer import Normalizer
    from core.llm_client import LLMClient
    from m1_decoder.decoder import SignalDecoder
    from m2_storage.signal_store import SignalStore
    from m3_judgment.judgment_engine import JudgmentEngine
    from m4_action.action_designer import ActionDesigner
    from core.schemas import Market

    incoming_dir = ROOT / "data" / "incoming"
    incoming_dir.mkdir(parents=True, exist_ok=True)

    batch_id = f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    market_enums = [Market(m) for m in markets]

    progress = st.sidebar.progress(0, text="初始化...")

    try:
        # M0: 收集
        progress.progress(10, "M0 收集...")
        provider = ManualProvider(source_name="Dashboard 输入")
        articles = provider.fetch(text=text)
        dedup = DedupIndex(ROOT / "m0_collector" / "manifest" / "dedup_index.json")
        normalizer = Normalizer(dedup_index=dedup)
        items, _, _ = normalizer.normalize(articles, force_reimport=True)
        if not items:
            st.sidebar.error("文本标准化失败")
            progress.empty()
            return
        fp = incoming_dir / items[0].filename()
        fp.write_text(items[0].to_text(), encoding="utf-8")
        dedup.save()

        # M1: 解码
        progress.progress(30, "M1 解码信号...")
        llm = LLMClient()
        decoder = SignalDecoder(llm_client=llm)
        signals = decoder.decode_file(fp, markets=market_enums, batch_id=batch_id)
        if not signals:
            st.sidebar.warning("未提取到信号")
            progress.empty()
            return

        # M2: 存储
        progress.progress(55, "M2 存储...")
        store = SignalStore()
        store.save(signals)

        # M3: 判断
        progress.progress(70, "M3 判断机会...")
        hist = store.get_by_time_range(
            start=datetime.now() - timedelta(days=90),
            end=datetime.now(),
            markets=market_enums,
            min_intensity=5,
        )
        curr_ids = {s.signal_id for s in signals}
        hist = [s for s in hist if s.signal_id not in curr_ids]
        opps_new = JudgmentEngine(llm_client=llm).judge(
            signals=signals, historical_signals=hist or None, batch_id=batch_id
        )

        # M4: 行动计划
        progress.progress(88, "M4 行动设计...")
        designer = ActionDesigner(llm_client=llm)
        plans = [designer.design(o) for o in opps_new]

        # 保存机会
        opp_dir = ROOT / "data" / "opportunities"
        opp_dir.mkdir(parents=True, exist_ok=True)
        out = opp_dir / f"{batch_id}_opportunities.json"
        out.write_text(
            json.dumps([o.model_dump(mode="json") for o in opps_new], ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        progress.progress(100, "完成！")
        st.sidebar.success(
            f"✅ {len(signals)} 条信号 → {len(opps_new)} 个机会"
        )
        clear_cache()
        st.rerun()

    except Exception as e:
        st.sidebar.error(f"分析出错: {e}")
        progress.empty()


# ─────────────────────────────────────────────────────────────
# 页面导航
# ─────────────────────────────────────────────────────────────

tab_opp, tab_signals, tab_position, tab_system = st.tabs([
    "🎯 机会", "📶 信号", "💼 持仓", "⚙️ 系统"
])


# ═══════════════════════════════════════════════════════════════
# TAB 1: 机会
# ═══════════════════════════════════════════════════════════════

with tab_opp:
    st.header("🎯 机会列表")

    if not opps:
        st.info("暂无机会记录。在左侧输入文本运行分析，或使用 pipeline/ingest.py 批量导入。")
    else:
        # 过滤控件
        col_f1, col_f2, col_f3 = st.columns([2, 2, 3])
        with col_f1:
            filter_priority = st.multiselect(
                "优先级", ["urgent", "position", "research", "watch"],
                default=["urgent", "position", "research", "watch"],
                key="opp_priority_filter",
            )
        with col_f2:
            all_markets = sorted({m for o in opps for m in o.get("target_markets", [])})
            filter_markets = st.multiselect("市场", all_markets, default=all_markets, key="opp_market_filter")
        with col_f3:
            filter_dir = st.multiselect(
                "方向", ["BULLISH", "BEARISH", "NEUTRAL"],
                default=["BULLISH", "BEARISH", "NEUTRAL"],
                key="opp_dir_filter",
            )

        filtered = [
            o for o in opps
            if o.get("priority_level", "watch") in filter_priority
            and any(m in filter_markets for m in o.get("target_markets", []))
            and o.get("trade_direction", "NEUTRAL") in filter_dir
        ]
        filtered = sorted(filtered, key=lambda o: (
            PRIORITY_ORDER.get(o.get("priority_level", "watch"), 4),
            -(o.get("signal_count") or len(o.get("related_signals", []))),
        ))

        st.caption(f"显示 {len(filtered)} / {len(opps)} 个机会")

        for opp in filtered:
            priority = opp.get("priority_level", "watch")
            direction = opp.get("trade_direction", "NEUTRAL")
            markets = " | ".join(opp.get("target_markets", []))
            instruments = opp.get("target_instruments", [])
            related = opp.get("related_signals", [])
            created = fmt_dt(opp.get("created_at"))
            window = opp.get("opportunity_window", {})
            horizon = window.get("horizon", "") if isinstance(window, dict) else ""

            p_icon = PRIORITY_ICON.get(priority, "⚪")
            d_icon = DIR_ICON.get(direction, "⚪")

            with st.expander(
                f"{p_icon} **{opp.get('opportunity_title', '未命名')}** "
                f"｜ {d_icon} {DIR_LABEL.get(direction, direction)} "
                f"｜ {markets} ｜ {created}",
                expanded=(priority in ("urgent", "position")),
            ):
                c_left, c_right = st.columns([3, 2])

                with c_left:
                    st.markdown("**📌 机会论点**")
                    st.write(opp.get("opportunity_thesis", ""))

                    st.markdown("**⚡ 为什么是现在**")
                    st.write(opp.get("why_now", ""))

                    if opp.get("key_assumptions"):
                        st.markdown("**🔑 关键假设**")
                        for a in opp["key_assumptions"][:3]:
                            st.write(f"• {a}")

                with c_right:
                    # 关键指标
                    st.markdown("**📊 关键指标**")
                    st.markdown(f"- 优先级：{p_icon} `{priority}`")
                    st.markdown(f"- 时效：`{horizon}`")
                    st.markdown(f"- 信号数：`{len(related)}`")
                    st.markdown(f"- 风险回报：{opp.get('risk_reward_profile', '—')}")

                    if instruments:
                        st.markdown("**🏷️ 相关品种**")
                        st.write("、".join(instruments[:5]))

                    if opp.get("counter_evidence"):
                        st.markdown("**⚠️ 反驳证据**")
                        for e in opp["counter_evidence"][:2]:
                            st.write(f"• {e}")

                    if opp.get("next_validation_questions"):
                        st.markdown("**❓ 待验证**")
                        for q in opp["next_validation_questions"][:2]:
                            st.write(f"• {q}")


# ═══════════════════════════════════════════════════════════════
# TAB 2: 信号
# ═══════════════════════════════════════════════════════════════

with tab_signals:
    st.header("📶 信号库")

    col_days, col_mkt, col_type, col_dir = st.columns([1, 2, 2, 2])
    with col_days:
        days_back = st.selectbox("时间范围", [1, 3, 7, 30, 90], index=2, key="sig_days")
    with col_mkt:
        sig_markets = st.multiselect("市场", ["A_SHARE", "HK", "US", "CRYPTO", "GLOBAL"],
                                     default=["A_SHARE", "HK"], key="sig_mkt")
    with col_type:
        type_opts = list(SIGNAL_TYPE_CN.keys())
        sig_types = st.multiselect("类型", type_opts,
                                   default=type_opts, key="sig_type",
                                   format_func=lambda x: SIGNAL_TYPE_CN.get(x, x))
    with col_dir:
        sig_dirs = st.multiselect("方向", ["BULLISH", "BEARISH", "NEUTRAL"],
                                  default=["BULLISH", "BEARISH", "NEUTRAL"], key="sig_dir")

    signals = load_signals_recent(days=days_back)

    # 过滤
    filtered_sigs = [
        s for s in signals
        if any(m in sig_markets for m in s.get("affected_markets", []))
        and s.get("signal_type") in sig_types
        and s.get("signal_direction") in sig_dirs
    ]
    filtered_sigs.sort(key=lambda s: s.get("intensity_score", 0), reverse=True)

    st.caption(f"显示 {len(filtered_sigs)} / {len(signals)} 条信号")

    if not filtered_sigs:
        st.info("暂无符合条件的信号")
    else:
        # 汇总 metrics
        m1, m2, m3, m4 = st.columns(4)
        bull = sum(1 for s in filtered_sigs if s.get("signal_direction") == "BULLISH")
        bear = sum(1 for s in filtered_sigs if s.get("signal_direction") == "BEARISH")
        avg_int = sum(s.get("intensity_score", 0) for s in filtered_sigs) / len(filtered_sigs)
        avg_conf = sum(s.get("confidence_score", 0) for s in filtered_sigs) / len(filtered_sigs)
        m1.metric("看多信号", bull)
        m2.metric("看空信号", bear)
        m3.metric("平均强度", f"{avg_int:.1f}/10")
        m4.metric("平均置信", f"{avg_conf:.1f}/10")

        st.divider()

        # 信号表格
        import pandas as pd
        rows = []
        for s in filtered_sigs:
            rows.append({
                "时间": fmt_dt(s.get("event_time")),
                "类型": SIGNAL_TYPE_CN.get(s.get("signal_type", ""), s.get("signal_type", "")),
                "方向": DIR_ICON.get(s.get("signal_direction"), "⚪") + " " + DIR_LABEL.get(s.get("signal_direction"), ""),
                "标签": s.get("signal_label", ""),
                "市场": "/".join(s.get("affected_markets", [])),
                "强度": s.get("intensity_score", 0),
                "置信": s.get("confidence_score", 0),
                "时效": s.get("timeliness_score", 0),
                "批次": s.get("batch_id", "")[-12:],
            })
        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "强度": st.column_config.ProgressColumn("强度", min_value=0, max_value=10, format="%d"),
                "置信": st.column_config.ProgressColumn("置信", min_value=0, max_value=10, format="%d"),
                "时效": st.column_config.ProgressColumn("时效", min_value=0, max_value=10, format="%d"),
            },
        )

        # 详情展开
        with st.expander("查看信号详情"):
            sel_label = st.selectbox(
                "选择信号", [s.get("signal_label", "") for s in filtered_sigs]
            )
            sel_sig = next((s for s in filtered_sigs if s.get("signal_label") == sel_label), None)
            if sel_sig:
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.markdown(f"**ID:** `{sel_sig.get('signal_id', '')}`")
                    st.markdown(f"**描述:** {sel_sig.get('description', '')}")
                    st.markdown(f"**证据原文:** _{sel_sig.get('evidence_text', '')[:300]}_")
                with col_d2:
                    lf = sel_sig.get("logic_frame", {})
                    if lf:
                        st.markdown("**逻辑框架：**")
                        st.markdown(f"- 变化：{lf.get('what_changed', '')}")
                        st.markdown(f"- 方向：{lf.get('change_direction', '')}")
                        st.markdown(f"- 影响：{', '.join(lf.get('affects', []))}")
                    insts = sel_sig.get("affected_instruments", [])
                    if insts:
                        st.markdown(f"**相关品种：** {', '.join(insts)}")


# ═══════════════════════════════════════════════════════════════
# TAB 3: 持仓
# ═══════════════════════════════════════════════════════════════

with tab_position:
    st.header("💼 持仓管理")

    positions = load_positions()
    active = [p for p in positions if p.get("status") == "ACTIVE"]
    closed = [p for p in positions if p.get("status") == "CLOSED"]

    # 汇总指标
    cm1, cm2, cm3, cm4 = st.columns(4)
    total_unrealized = sum((p.get("unrealized_pnl") or 0) for p in active)
    total_realized = sum((p.get("realized_pnl") or 0) for p in closed)
    wins = [p for p in closed if (p.get("realized_pnl") or 0) > 0]
    wr = f"{len(wins)/len(closed)*100:.1f}%" if closed else "N/A"

    cm1.metric("活跃持仓", len(active))
    cm2.metric("已关闭持仓", len(closed))
    cm3.metric("浮动盈亏", f"{total_unrealized*100:+.2f}%")
    cm4.metric("历史胜率", wr)

    st.divider()

    # 活跃持仓
    st.subheader("📌 活跃持仓")
    if not active:
        st.info("暂无活跃持仓")
    else:
        import pandas as pd
        rows = []
        for p in active:
            pnl = p.get("unrealized_pnl") or 0
            entry = p.get("entry_price") or 0
            sl = p.get("stop_loss_price") or 0
            tp = p.get("take_profit_price") or 0
            curr = p.get("current_price") or entry
            rows.append({
                "品种": p.get("instrument", ""),
                "方向": DIR_ICON.get(p.get("direction", ""), "⚪"),
                "入场价": entry,
                "当前价": curr,
                "浮盈": f"{'▲' if pnl >= 0 else '▼'} {pnl*100:+.2f}%",
                "止损": f"{sl:.3f}" if sl else "—",
                "止盈": f"{tp:.3f}" if tp else "—",
                "仓位(元)": p.get("total_cost") or "—",
                "开仓时间": fmt_dt(p.get("entry_time")),
            })
        df_pos = pd.DataFrame(rows)
        st.dataframe(df_pos, use_container_width=True, hide_index=True)

    # 历史持仓
    if closed:
        st.subheader("📋 历史持仓")
        rows_c = []
        for p in sorted(closed, key=lambda x: x.get("exit_time", ""), reverse=True)[:20]:
            rpnl = p.get("realized_pnl") or 0
            rows_c.append({
                "品种": p.get("instrument", ""),
                "方向": DIR_ICON.get(p.get("direction", ""), "⚪"),
                "入场价": p.get("entry_price") or 0,
                "出场价": p.get("exit_price") or 0,
                "盈亏": f"{'▲' if rpnl >= 0 else '▼'} {rpnl*100:+.2f}%",
                "平仓原因": p.get("exit_reason", "—"),
                "开仓": fmt_dt(p.get("entry_time")),
                "平仓": fmt_dt(p.get("exit_time")),
            })
        st.dataframe(pd.DataFrame(rows_c), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════
# TAB 4: 系统
# ═══════════════════════════════════════════════════════════════

with tab_system:
    st.header("⚙️ 系统状态")

    # 信号统计图表
    c_left, c_right = st.columns(2)
    with c_left:
        st.subheader("信号类型分布")
        by_type = stats.get("by_signal_type", {})
        if by_type:
            import pandas as pd
            df_type = pd.DataFrame(
                [{"类型": SIGNAL_TYPE_CN.get(k, k), "数量": v} for k, v in by_type.items()]
            ).sort_values("数量", ascending=False)
            st.bar_chart(df_type.set_index("类型"))
        else:
            st.info("暂无数据")

    with c_right:
        st.subheader("批次信号数量")
        batches = stats.get("recent_batches", {})
        if batches:
            import pandas as pd
            df_batch = pd.DataFrame(
                [{"批次": k[-12:], "信号数": v} for k, v in batches.items()]
            )
            st.bar_chart(df_batch.set_index("批次"))
        else:
            st.info("暂无数据")

    st.divider()

    # 文件状态
    st.subheader("📁 数据文件状态")
    fc1, fc2, fc3 = st.columns(3)

    with fc1:
        incoming_dir = ROOT / "data" / "incoming"
        files = list(incoming_dir.glob("*.txt")) if incoming_dir.exists() else []
        st.metric("incoming/ 文件数", len(files))
        if files:
            st.caption("最近文件:")
            for f in sorted(files, reverse=True)[:3]:
                st.text(f"  {f.name}")

    with fc2:
        opp_dir = ROOT / "data" / "opportunities"
        opp_files = list(opp_dir.glob("*.json")) if opp_dir.exists() else []
        st.metric("机会文件数", len(opp_files))

    with fc3:
        db_path = ROOT / "data" / "signals" / "signal_store.db"
        if db_path.exists():
            size_kb = db_path.stat().st_size / 1024
            st.metric("Signal Store 大小", f"{size_kb:.1f} KB")
            st.caption(f"总信号: {stats.get('total', 0)} 条")
        else:
            st.metric("Signal Store", "未初始化")

    st.divider()

    # 使用说明
    st.subheader("📖 使用说明")
    st.markdown("""
**完整工作流程：**

```
M0 收集  →  M1 解码  →  M2 存储  →  M3 判断  →  M4 行动设计  →  M5 持仓管理
```

**快速开始：**
1. 在左侧「快速分析」粘贴新闻文本，点击「运行完整分析」
2. 或者用命令行批量处理：
   ```bash
   # 手动导入文件
   python -m m0_collector.cli --source manual --file my_news.txt --then-ingest --then-judge
   
   # RSS 抓取（需安装 feedparser）
   python -m m0_collector.cli --source rss --then-ingest --market A_SHARE,HK
   
   # 批量处理 data/incoming/ 目录
   python pipeline/ingest.py --dir data/incoming/ --then-judge
   ```

**模块说明：**
| 模块 | 职责 |
|------|------|
| M0 收集器 | RSS/手动导入新闻 → data/incoming/ |
| M1 解码器 | 文本 → 结构化信号（LLM） |
| M2 存储 | 信号持久化（SQLite，跨批次） |
| M3 判断引擎 | 信号群 → 机会对象（LLM） |
| M4 行动设计师 | 机会 → 止损/止盈/仓位方案（LLM） |
| M5 持仓管理 | 开仓/跟踪/平仓（纯规则） |
""")
