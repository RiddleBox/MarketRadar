"""
pipeline/dashboard.py — MarketRadar Streamlit Dashboard

启动：
  cd D:/AIproject/MarketRadar
  streamlit run pipeline/dashboard.py

数据源（真实接口）：
  - 信号    : M2 SignalStore（SQLite）
  - 机会    : data/opportunities/*.json
  - 持仓    : M9 PaperTrader（真实模拟仓）
  - 调度器  : M7 Scheduler 状态文件
  - 价格    : M9 AKShareRealtimeFeed（盘中实时）
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
# 数据加载（带缓存）— 全部接真实接口
# ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=15)
def load_paper_positions() -> list[dict]:
    """M9 PaperTrader — 全部持仓（OPEN + CLOSED）"""
    try:
        from m9_paper_trader.paper_trader import PaperTrader
        trader = PaperTrader()
        return [p.__dict__ for p in trader.list_all()]
    except Exception as e:
        return []


@st.cache_data(ttl=15)
def load_paper_positions_open() -> list[dict]:
    try:
        from m9_paper_trader.paper_trader import PaperTrader
        trader = PaperTrader()
        return [p.__dict__ for p in trader.list_open()]
    except Exception:
        return []


@st.cache_data(ttl=15)
def load_paper_positions_closed() -> list[dict]:
    try:
        from m9_paper_trader.paper_trader import PaperTrader
        trader = PaperTrader()
        return [p.__dict__ for p in trader.list_closed()]
    except Exception:
        return []


@st.cache_data(ttl=30)
def load_opportunities() -> list:
    opp_dir = ROOT / "data" / "opportunities"
    if not opp_dir.exists():
        return []
    opps = []
    for f in sorted(opp_dir.glob("*.json"), reverse=True)[:20]:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                opps.extend(data)
            elif isinstance(data, dict):
                opps.append(data)
        except Exception:
            pass
    seen, unique = set(), []
    for o in opps:
        oid = o.get("opportunity_id", "")
        if oid and oid not in seen:
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
        store = SignalStore()
        sigs = store.get_by_time_range(
            start=datetime.now() - timedelta(days=days),
            end=datetime.now(),
        )
        return [s.model_dump(mode="json") for s in sigs]
    except Exception:
        return []


@st.cache_data(ttl=20)
def load_scheduler_state() -> dict:
    """M7 调度器状态文件"""
    state_file = ROOT / "data" / "scheduler_state.json"
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


@st.cache_data(ttl=60)
def load_latest_price(instrument: str) -> float | None:
    """M9 AKShareRealtimeFeed 拉最新价"""
    try:
        from m9_paper_trader.price_feed import AKShareRealtimeFeed
        feed = AKShareRealtimeFeed()
        snap = feed.get_price(instrument)
        return snap.price if snap else None
    except Exception:
        return None


@st.cache_data(ttl=60)
def load_sentiment_history(n: int = 48) -> list[dict]:
    """M10 SentimentStore — 最近 n 条情绪快照"""
    try:
        from m10_sentiment.sentiment_store import SentimentStore
        store = SentimentStore()
        return store.latest(n)
    except Exception:
        return []


@st.cache_data(ttl=60)
def load_sentiment_trend(n: int = 20) -> dict:
    """M10 SentimentStore — 趋势统计"""
    try:
        from m10_sentiment.sentiment_store import SentimentStore
        store = SentimentStore()
        return store.trend(n)
    except Exception:
        return {}


@st.cache_data(ttl=60)
def load_sentiment_stats() -> dict:
    """M10 SentimentStore — 全期统计"""
    try:
        from m10_sentiment.sentiment_store import SentimentStore
        store = SentimentStore()
        return store.stats()
    except Exception:
        return {}


def clear_cache():
    st.cache_data.clear()


# ─────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────

PRIORITY_ICON  = {"urgent": "🔴", "position": "🟢", "research": "🟡", "watch": "⚪"}
PRIORITY_ORDER = {"urgent": 0, "position": 1, "research": 2, "watch": 3}
DIR_ICON       = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "⚪"}
DIR_LABEL      = {"BULLISH": "看多", "BEARISH": "看空", "NEUTRAL": "中性"}

SIGNAL_TYPE_CN = {
    "macro": "宏观", "policy": "政策", "technical": "技术",
    "capital_flow": "资金流", "industry": "行业", "event_driven": "事件",
    "sentiment": "情绪", "fundamental": "基本面",
}


def pnl_color(pnl: float) -> str:
    return "#00c851" if pnl >= 0 else "#ff4b4b"


def pnl_str(pnl: float | None, pct: bool = True) -> str:
    if pnl is None:
        return "—"
    v = pnl * 100 if pct else pnl
    c = pnl_color(pnl)
    sign = "+" if pnl >= 0 else ""
    return f'<span style="color:{c}">{sign}{v:.2f}{"%" if pct else ""}</span>'


def fmt_dt(s, fmt: str = "%m-%d %H:%M") -> str:
    if not s:
        return "—"
    try:
        if isinstance(s, datetime):
            return s.strftime(fmt)
        return datetime.fromisoformat(str(s)[:19]).strftime(fmt)
    except Exception:
        return str(s)[:10]


def fmt_price(p: float | None) -> str:
    return f"{p:.3f}" if p else "—"


# ─────────────────────────────────────────────────────────────
# 快速分析（侧边栏触发 M0→M1→M2→M3→M4）
# ─────────────────────────────────────────────────────────────

def _run_analysis(text: str, markets: list):
    from core.llm_client import LLMClient
    from m1_decoder.decoder import SignalDecoder
    from m2_storage.signal_store import SignalStore
    from m3_judgment.judgment_engine import JudgmentEngine
    from m4_action.action_designer import ActionDesigner
    from core.schemas import Market, SourceType

    incoming_dir = ROOT / "data" / "incoming"
    incoming_dir.mkdir(parents=True, exist_ok=True)
    batch_id = f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    market_enums = [Market(m) for m in markets]

    prog = st.sidebar.progress(0, text="初始化...")
    try:
        prog.progress(10, "M1 解码信号...")
        llm = LLMClient()
        decoder = SignalDecoder(llm_client=llm)
        # 直接解码文本（不走 M0 文件）
        signals = decoder.decode(
            raw_text=text,
            source_ref="dashboard_input",
            source_type=SourceType("manual_input"),
            batch_id=batch_id,
        )
        if not signals:
            st.sidebar.warning("未提取到信号")
            prog.empty()
            return

        prog.progress(40, f"M2 存储 {len(signals)} 条信号...")
        store = SignalStore()
        store.save(signals)

        prog.progress(60, "M3 判断机会...")
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

        prog.progress(85, "M4 行动设计...")
        designer = ActionDesigner(llm_client=llm)
        for opp in opps_new:
            designer.design(opp)

        opp_dir = ROOT / "data" / "opportunities"
        opp_dir.mkdir(parents=True, exist_ok=True)
        if opps_new:
            (opp_dir / f"{batch_id}_opportunities.json").write_text(
                json.dumps([o.model_dump(mode="json") for o in opps_new],
                           ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )

        prog.progress(100, "完成！")
        st.sidebar.success(f"✅ {len(signals)} 条信号 → {len(opps_new)} 个机会")
        clear_cache()
        st.rerun()

    except Exception as e:
        st.sidebar.error(f"分析出错: {e}")
        prog.empty()


# ─────────────────────────────────────────────────────────────
# 侧边栏
# ─────────────────────────────────────────────────────────────

with st.sidebar:
    st.image("https://img.icons8.com/ios-filled/50/00c851/radar.png", width=40)
    st.title("MarketRadar")
    st.caption("客观信号驱动的市场机会发现系统")
    st.divider()

    stats      = load_signal_stats()
    open_pos   = load_paper_positions_open()
    closed_pos = load_paper_positions_closed()
    opps       = load_opportunities()
    urgent_opps = [o for o in opps if o.get("priority_level") in ("urgent", "position")]

    c1, c2 = st.columns(2)
    with c1:
        st.metric("📶 信号总数", stats.get("total", 0))
        st.metric("💼 模拟持仓", len(open_pos))
    with c2:
        st.metric("🎯 机会总数", len(opps))
        st.metric("⚡ 高优先级", len(urgent_opps))

    if urgent_opps:
        st.error(f"⚡ {len(urgent_opps)} 个高优先级机会待处理")

    # 浮盈概览
    if open_pos:
        total_pnl = sum(p.get("unrealized_pnl_pct", 0) or 0 for p in open_pos)
        avg_pnl = total_pnl / len(open_pos)
        color = pnl_color(avg_pnl)
        st.markdown(
            f'模拟仓平均浮盈：<span style="color:{color};font-weight:bold">'
            f'{"+".rstrip("+")+("+" if avg_pnl>=0 else "")}{avg_pnl*100:.2f}%</span>',
            unsafe_allow_html=True,
        )

    st.divider()

    st.subheader("🚀 快速分析")
    input_text = st.text_area(
        "粘贴新闻 / 公告 / 研报摘要",
        height=120,
        placeholder="直接粘贴文本，自动提取信号并判断机会...",
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
    if st.button("🔄 刷新数据", use_container_width=True):
        clear_cache()
        st.rerun()
    st.caption(f"更新: {datetime.now().strftime('%H:%M:%S')}")


# ─────────────────────────────────────────────────────────────
# 主页 Tabs
# ─────────────────────────────────────────────────────────────

tab_opp, tab_signals, tab_paper, tab_sentiment, tab_system, tab_control = st.tabs([
    "🎯 机会", "📶 信号", "📊 模拟盘", "🧠 情绪面", "⚙️ 系统", "🎛️ 工作流"
])


# ═══════════════════════════════════════════════════════════════
# TAB 1: 机会
# ═══════════════════════════════════════════════════════════════

with tab_opp:
    st.header("🎯 机会列表")

    if not opps:
        st.info("暂无机会记录。在左侧输入文本运行分析，或配置 M7 调度器自动收集。")
    else:
        col_f1, col_f2, col_f3 = st.columns([2, 2, 3])
        with col_f1:
            filter_priority = st.multiselect(
                "优先级", ["urgent", "position", "research", "watch"],
                default=["urgent", "position", "research", "watch"],
            )
        with col_f2:
            all_markets = sorted({m for o in opps for m in o.get("target_markets", [])})
            filter_markets = st.multiselect("市场", all_markets or ["A_SHARE", "HK"],
                                             default=all_markets or ["A_SHARE", "HK"])
        with col_f3:
            filter_dir = st.multiselect("方向", ["BULLISH", "BEARISH", "NEUTRAL"],
                                         default=["BULLISH", "BEARISH", "NEUTRAL"])

        filtered = [
            o for o in opps
            if o.get("priority_level", "watch") in filter_priority
            and any(m in filter_markets for m in o.get("target_markets", []))
            and o.get("trade_direction", "NEUTRAL") in filter_dir
        ]
        filtered.sort(key=lambda o: (
            PRIORITY_ORDER.get(o.get("priority_level", "watch"), 4),
            -(o.get("signal_count") or len(o.get("related_signals", []))),
        ))

        st.caption(f"显示 {len(filtered)} / {len(opps)} 个机会")

        for opp in filtered:
            priority  = opp.get("priority_level", "watch")
            direction = opp.get("trade_direction", "NEUTRAL")
            markets   = " | ".join(opp.get("target_markets", []))
            instruments = opp.get("target_instruments", [])
            created   = fmt_dt(opp.get("created_at"))
            window    = opp.get("opportunity_window", {})
            horizon   = window.get("horizon", "") if isinstance(window, dict) else ""
            p_icon    = PRIORITY_ICON.get(priority, "⚪")
            d_icon    = DIR_ICON.get(direction, "⚪")

            with st.expander(
                f"{p_icon} **{opp.get('opportunity_title','未命名')}** "
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
                    st.markdown("**📊 关键指标**")
                    st.markdown(f"- 优先级：{p_icon} `{priority}`")
                    st.markdown(f"- 时效：`{horizon}`")
                    st.markdown(f"- 信号数：`{len(opp.get('related_signals', []))}`")
                    st.markdown(f"- 风险回报：{opp.get('risk_reward_profile', '—')}")
                    if instruments:
                        st.markdown("**🏷️ 相关品种**")
                        st.write("、".join(instruments[:5]))
                    if opp.get("counter_evidence"):
                        st.markdown("**⚠️ 反驳证据**")
                        for e in opp["counter_evidence"][:2]:
                            st.write(f"• {e}")

                    # ── 快速开模拟仓 ──
                    st.markdown("---")
                    st.markdown("**🏦 快速开模拟仓**")
                    opp_id = opp.get("opportunity_id", "")
                    inst_default = instruments[0] if instruments else ""
                    ep_key   = f"ep_{opp_id}"
                    sl_key   = f"sl_{opp_id}"
                    tp_key   = f"tp_{opp_id}"
                    qty_key  = f"qty_{opp_id}"
                    open_key = f"open_{opp_id}"

                    col_ep, col_sl = st.columns(2)
                    with col_ep:
                        ep = st.number_input("入场价", key=ep_key, value=0.0,
                                             min_value=0.0, step=0.01, format="%.3f")
                    with col_sl:
                        sl = st.number_input("止损价", key=sl_key, value=0.0,
                                             min_value=0.0, step=0.01, format="%.3f")
                    col_tp, col_qty = st.columns(2)
                    with col_tp:
                        tp = st.number_input("止盈价(可选)", key=tp_key, value=0.0,
                                             min_value=0.0, step=0.01, format="%.3f")
                    with col_qty:
                        qty = st.number_input("数量(份/手)", key=qty_key, value=10000.0,
                                              min_value=1.0, step=100.0)
                    inst_in = st.text_input("品种代码", key=f"inst_{opp_id}",
                                            value=inst_default,
                                            placeholder="如 510300.SH")

                    if st.button("📂 开仓", key=open_key):
                        if ep <= 0 or sl <= 0 or not inst_in:
                            st.error("请填写入场价、止损价和品种代码")
                        else:
                            try:
                                from m9_paper_trader.paper_trader import PaperTrader
                                trader = PaperTrader()
                                pos = trader.open_manual(
                                    instrument=inst_in,
                                    market=opp.get("target_markets", ["A_SHARE"])[0],
                                    direction=direction,
                                    entry_price=ep,
                                    stop_loss_price=sl,
                                    take_profit_price=tp if tp > 0 else None,
                                    quantity=qty,
                                    opportunity_id=opp_id,
                                )
                                st.success(f"✅ 已开仓 {inst_in}，ID: {pos.paper_position_id}")
                                clear_cache()
                            except Exception as e:
                                st.error(f"开仓失败: {e}")


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
        sig_types = st.multiselect("类型", type_opts, default=type_opts, key="sig_type",
                                   format_func=lambda x: SIGNAL_TYPE_CN.get(x, x))
    with col_dir:
        sig_dirs = st.multiselect("方向", ["BULLISH", "BEARISH", "NEUTRAL"],
                                  default=["BULLISH", "BEARISH", "NEUTRAL"], key="sig_dir")

    signals = load_signals_recent(days=days_back)
    filtered_sigs = [
        s for s in signals
        if any(m in sig_markets for m in s.get("affected_markets", []))
        and s.get("signal_type") in sig_types
        and s.get("signal_direction") in sig_dirs
    ]
    filtered_sigs.sort(key=lambda s: s.get("intensity_score", 0), reverse=True)

    st.caption(f"显示 {len(filtered_sigs)} / {len(signals)} 条信号（过去 {days_back} 天）")

    if not filtered_sigs:
        st.info("暂无符合条件的信号。从侧边栏输入文本分析，或配置 M7 自动采集。")
    else:
        m1, m2, m3, m4 = st.columns(4)
        bull = sum(1 for s in filtered_sigs if s.get("signal_direction") == "BULLISH")
        bear = sum(1 for s in filtered_sigs if s.get("signal_direction") == "BEARISH")
        avg_int  = sum(s.get("intensity_score", 0) for s in filtered_sigs) / len(filtered_sigs)
        avg_conf = sum(s.get("confidence_score", 0) for s in filtered_sigs) / len(filtered_sigs)
        m1.metric("看多信号", bull)
        m2.metric("看空信号", bear)
        m3.metric("平均强度", f"{avg_int:.1f}/10")
        m4.metric("平均置信", f"{avg_conf:.1f}/10")

        st.divider()

        import pandas as pd
        rows = []
        for s in filtered_sigs:
            rows.append({
                "时间":   fmt_dt(s.get("event_time")),
                "类型":   SIGNAL_TYPE_CN.get(s.get("signal_type", ""), s.get("signal_type", "")),
                "方向":   DIR_ICON.get(s.get("signal_direction"), "⚪") + " " + DIR_LABEL.get(s.get("signal_direction"), ""),
                "标签":   s.get("signal_label", ""),
                "市场":   "/".join(s.get("affected_markets", [])),
                "强度":   s.get("intensity_score", 0),
                "置信":   s.get("confidence_score", 0),
                "时效":   s.get("timeliness_score", 0),
                "批次":   s.get("batch_id", "")[-12:],
            })
        df = pd.DataFrame(rows)
        st.dataframe(
            df, use_container_width=True, hide_index=True,
            column_config={
                "强度": st.column_config.ProgressColumn("强度", min_value=0, max_value=10, format="%d"),
                "置信": st.column_config.ProgressColumn("置信", min_value=0, max_value=10, format="%d"),
                "时效": st.column_config.ProgressColumn("时效", min_value=0, max_value=10, format="%d"),
            },
        )

        with st.expander("查看信号详情"):
            sel_label = st.selectbox("选择信号", [s.get("signal_label", "") for s in filtered_sigs])
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
                        st.markdown(f"- 影响：{', '.join(lf.get('affects', []))}")
                    insts = sel_sig.get("affected_instruments", [])
                    if insts:
                        st.markdown(f"**相关品种：** {', '.join(insts)}")


# ═══════════════════════════════════════════════════════════════
# TAB 3: 模拟盘（M9 PaperTrader）
# ═══════════════════════════════════════════════════════════════

with tab_paper:
    st.header("📊 模拟盘")

    all_pos    = load_paper_positions()
    open_p     = [p for p in all_pos if p.get("status") == "OPEN"]
    closed_p   = [p for p in all_pos if p.get("status") != "OPEN"]

    # ── 顶部汇总 ──
    r1c1, r1c2, r1c3, r1c4, r1c5 = st.columns(5)
    wins = [p for p in closed_p if (p.get("realized_pnl_pct") or 0) > 0]
    losses = [p for p in closed_p if (p.get("realized_pnl_pct") or 0) <= 0]
    win_rate = len(wins) / len(closed_p) * 100 if closed_p else 0
    avg_win  = sum(p.get("realized_pnl_pct", 0) for p in wins)   / len(wins)   if wins   else 0
    avg_loss = sum(p.get("realized_pnl_pct", 0) for p in losses) / len(losses) if losses else 0
    unrealized_total = sum(p.get("unrealized_pnl_pct", 0) or 0 for p in open_p)

    r1c1.metric("📂 持仓中", len(open_p))
    r1c2.metric("📋 已平仓", len(closed_p))
    r1c3.metric("🏆 胜率", f"{win_rate:.1f}%")
    r1c4.metric("💰 平均盈利", f"{avg_win*100:+.2f}%" if wins else "—")
    r1c5.metric("📉 平均亏损", f"{avg_loss*100:+.2f}%" if losses else "—")

    st.divider()

    # ── 手动开仓 ──
    with st.expander("➕ 手动开仓", expanded=False):
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            m_inst = st.text_input("品种代码", placeholder="510300.SH", key="m_inst")
            m_mkt  = st.selectbox("市场", ["A_SHARE", "HK", "US"], key="m_mkt")
        with mc2:
            m_dir = st.selectbox("方向", ["BULLISH", "BEARISH"], key="m_dir")
            m_ep  = st.number_input("入场价", min_value=0.0, step=0.01, format="%.3f", key="m_ep")
        with mc3:
            m_sl  = st.number_input("止损价", min_value=0.0, step=0.01, format="%.3f", key="m_sl")
            m_tp  = st.number_input("止盈价(可选)", min_value=0.0, step=0.01, format="%.3f", key="m_tp")
        m_qty = st.number_input("数量(份/手)", min_value=1.0, value=10000.0, step=100.0, key="m_qty")

        if st.button("📂 开仓", key="manual_open_btn", type="primary"):
            if not m_inst or m_ep <= 0 or m_sl <= 0:
                st.error("请填写品种代码、入场价和止损价")
            else:
                try:
                    from m9_paper_trader.paper_trader import PaperTrader
                    trader = PaperTrader()
                    pos = trader.open_manual(
                        instrument=m_inst, market=m_mkt, direction=m_dir,
                        entry_price=m_ep, stop_loss_price=m_sl,
                        take_profit_price=m_tp if m_tp > 0 else None,
                        quantity=m_qty,
                    )
                    st.success(f"✅ 已开仓 {m_inst}，ID: `{pos.paper_position_id}`")
                    clear_cache()
                    st.rerun()
                except Exception as e:
                    st.error(f"开仓失败: {e}")

    # ── 活跃持仓 ──
    st.subheader(f"📌 持仓中（{len(open_p)}）")
    if not open_p:
        st.info("暂无持仓。可在机会 Tab 或上方「手动开仓」创建模拟仓位。")
    else:
        import pandas as pd

        # 批量刷新价格按钮
        col_refresh, col_expire = st.columns([1, 3])
        with col_refresh:
            if st.button("🔄 刷新所有价格（AKShare）", key="refresh_prices"):
                try:
                    from m9_paper_trader.paper_trader import PaperTrader
                    from m9_paper_trader.price_feed import AKShareRealtimeFeed
                    trader = PaperTrader()
                    result = trader.update_all_prices(AKShareRealtimeFeed())
                    updated = result.get("updated", 0)
                    closed_ids = result.get("closed", [])
                    msg = f"✅ 更新 {updated} 仓"
                    if closed_ids:
                        msg += f"，触发平仓 {len(closed_ids)} 仓"
                    st.success(msg)
                    clear_cache()
                    st.rerun()
                except Exception as e:
                    st.error(f"更新失败: {e}")
        with col_expire:
            if st.button("🗑 清理超期持仓（>90天）", key="expire_old"):
                try:
                    from m9_paper_trader.paper_trader import PaperTrader
                    trader = PaperTrader()
                    expired = trader.expire_old(max_days=90)
                    st.success(f"已清理 {len(expired)} 个超期持仓")
                    clear_cache()
                    st.rerun()
                except Exception as e:
                    st.error(f"清理失败: {e}")

        # 持仓表格 + 个别操作
        for pos in open_p:
            pnl = pos.get("unrealized_pnl_pct") or 0
            pnl_c = pnl_color(pnl)
            sign = "▲" if pnl >= 0 else "▼"
            col_info, col_action = st.columns([5, 1])
            with col_info:
                entry  = pos.get("entry_price", 0)
                curr   = pos.get("current_price", entry)
                sl     = pos.get("stop_loss_price", 0)
                tp     = pos.get("take_profit_price")
                mfe    = pos.get("max_favorable_excursion", 0) * 100
                mae    = pos.get("max_adverse_excursion", 0) * 100
                st.markdown(
                    f'**{pos.get("instrument","?")}** &nbsp;'
                    f'{DIR_ICON.get(pos.get("direction",""),"⚪")} '
                    f'{DIR_LABEL.get(pos.get("direction",""),"?")} &nbsp;｜&nbsp;'
                    f'入场 `{fmt_price(entry)}` → 当前 `{fmt_price(curr)}` &nbsp;'
                    f'<span style="color:{pnl_c};font-weight:bold">{sign} {abs(pnl)*100:.2f}%</span> &nbsp;｜&nbsp;'
                    f'止损 `{fmt_price(sl)}` 止盈 `{fmt_price(tp)}` &nbsp;｜&nbsp;'
                    f'MFE `+{mfe:.2f}%` MAE `-{mae:.2f}%` &nbsp;'
                    f'<span style="color:#888;font-size:12px">{fmt_dt(pos.get("entry_time"))}</span>',
                    unsafe_allow_html=True,
                )
            with col_action:
                close_key = f"close_{pos.get('paper_position_id','')}"
                curr_price_key = f"cprice_{pos.get('paper_position_id','')}"
                cp = st.number_input("平仓价", key=curr_price_key, value=float(curr or 0),
                                     min_value=0.0, step=0.001, format="%.3f",
                                     label_visibility="collapsed")
                if st.button("✖ 平仓", key=close_key):
                    try:
                        from m9_paper_trader.paper_trader import PaperTrader
                        trader = PaperTrader()
                        ok = trader.close_manual(pos["paper_position_id"], cp)
                        if ok:
                            st.success(f"已平仓 {pos.get('instrument')}")
                            clear_cache()
                            st.rerun()
                        else:
                            st.error("平仓失败")
                    except Exception as e:
                        st.error(f"平仓出错: {e}")

    # ── 历史持仓 ──
    st.divider()
    st.subheader(f"📋 历史持仓（{len(closed_p)}）")
    if not closed_p:
        st.info("暂无历史持仓记录。")
    else:
        import pandas as pd
        rows_c = []
        for p in sorted(closed_p, key=lambda x: x.get("exit_time") or "", reverse=True)[:30]:
            rpnl = p.get("realized_pnl_pct") or 0
            rows_c.append({
                "品种":     p.get("instrument", ""),
                "方向":     DIR_ICON.get(p.get("direction", ""), "⚪") + " " + DIR_LABEL.get(p.get("direction", ""), ""),
                "入场价":   fmt_price(p.get("entry_price")),
                "出场价":   fmt_price(p.get("exit_price")),
                "盈亏%":    rpnl * 100,
                "平仓原因": p.get("status") or "—",
                "MFE%":     (p.get("max_favorable_excursion") or 0) * 100,
                "MAE%":     (p.get("max_adverse_excursion") or 0) * 100,
                "开仓":     fmt_dt(p.get("entry_time")),
                "平仓":     fmt_dt(p.get("exit_time")),
            })
        df_c = pd.DataFrame(rows_c)
        st.dataframe(
            df_c, use_container_width=True, hide_index=True,
            column_config={
                "盈亏%": st.column_config.NumberColumn("盈亏%", format="%+.2f%%"),
                "MFE%":  st.column_config.NumberColumn("MFE%",  format="+%.2f%%"),
                "MAE%":  st.column_config.NumberColumn("MAE%",  format="-%.2f%%"),
            },
        )

        # 盈亏分布图
        if len(rows_c) >= 3:
            import pandas as pd
            pnl_data = pd.DataFrame({"盈亏%": [r["盈亏%"] for r in rows_c]})
            st.bar_chart(pnl_data, y="盈亏%", height=200)


# ═══════════════════════════════════════════════════════════════
# TAB 4: 情绪面（M10 SentimentEngine 恐贪指数 + 历史趋势）
# ═══════════════════════════════════════════════════════════════

with tab_sentiment:
    st.header("🧠 情绪面仪表盘")

    # ── 实时采集按鈕 ────────────────────────────────────────────
    s_col1, s_col2, s_col3 = st.columns([2, 2, 6])
    with s_col1:
        if st.button("🔄 立即采集", key="sentiment_run", use_container_width=True):
            with st.spinner("正在采集情绪数据..."):
                try:
                    from m10_sentiment.sentiment_engine import SentimentEngine
                    from datetime import datetime
                    engine = SentimentEngine()
                    sig = engine.run_and_inject(
                        batch_id=f"dash_{datetime.now().strftime('%H%M%S')}",
                    )
                    st.success(f"恐贪指数: {sig.fear_greed_index:.1f} ({sig.sentiment_label}) — 已入库")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"采集失败: {e}")
    with s_col2:
        if st.button("🔁 刷新显示", key="sentiment_refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    st.divider()

    hist = load_sentiment_history(48)
    trend = load_sentiment_trend(20)
    stats = load_sentiment_stats()

    if not hist:
        st.info("💭 暂无情绪历史数据，点击》立即采集《生成第一条快照")
        st.stop()

    latest = hist[0]
    fg = latest.get("fear_greed", 50.0)
    label = latest.get("label", "--")
    direction = latest.get("direction", "NEUTRAL")
    ts = latest.get("ts", "")[:16]

    # ── 恐贪指数主展示区 ─────────────────────────────────────────
    m1, m2, m3, m4 = st.columns(4)

    # 恐贪指数使用进度条展示
    fg_pct = fg / 100
    if fg >= 80:
        fg_color = "#ff4b4b"    # 极度贪婪 — 警告色
        fg_emoji = "🔴"
    elif fg >= 60:
        fg_color = "#ffaa00"    # 贪婪
        fg_emoji = "🟡"
    elif fg >= 40:
        fg_color = "#aaaaaa"    # 中性
        fg_emoji = "⚪"
    elif fg >= 20:
        fg_color = "#00ccff"    # 恐惧
        fg_emoji = "🔵"
    else:
        fg_color = "#0044ff"    # 极度恐惧 — 反转机会色
        fg_emoji = "🔵"

    # 方向颜色
    dir_color = "#00c851" if direction == "BULLISH" else (
        "#ff4b4b" if direction == "BEARISH" else "#aaaaaa"
    )
    dir_text = {
        "BULLISH": "↑ 倚多",
        "BEARISH": "↓ 假空",
        "NEUTRAL": "— 中性",
    }.get(direction, direction)

    with m1:
        st.metric(
            label=f"{fg_emoji} 恐贪指数",
            value=f"{fg:.1f}",
            delta=f"{fg - hist[1]['fear_greed']:.1f}" if len(hist) > 1 else None,
        )
        st.caption(f"{label}  |  {ts}")
        st.progress(fg_pct)

    with m2:
        nd = latest.get("northbound", 0.0)
        nd_delta = nd - hist[1].get("northbound", 0.0) if len(hist) > 1 else None
        st.metric(
            label="🌏 北向资金",
            value=f"{nd:+.1f}亿",
            delta=f"{nd_delta:+.1f}" if nd_delta is not None else None,
        )
        st.caption("南向资金断面" if nd > 0 else "外资流出")

    with m3:
        adr = latest.get("adr", 0.0) * 100
        st.metric(
            label="📈 涨跌家数比",
            value=f"{adr:.1f}%",
            delta=None,
        )
        st.caption(f"{'> 50% 市场偵健' if adr > 50 else '< 50% 偏弱迎'}") 

    with m4:
        st.metric(
            label="🦭 情绪方向",
            value=dir_text,
        )
        is_rising = trend.get("is_rising")
        slope = trend.get("slope", 0)
        if is_rising is not None:
            arrow_up = "\u2191"
            arrow_down = "\u2193"
            st.caption(f"{arrow_up} 情绪上升中" if is_rising else f"{arrow_down} 情绪下降中  (斜率{slope:+.2f})")

    st.divider()

    # ── 恐贪指数解读 + 信号指导 ─────────────────────────────
    st.subheader("📊 情绪解读与操作建议")

    # 根据 FG 值给出操作解读
    if fg >= 80:
        advice_text = "🚨 极度贪婪 — 市场冠居情绪颜峰，历史上属于高风险区间"
        advice_detail = """
**操作建议**
- ✅ 考虑分批减仓，采用移动止盈保护已有收益
- ✅ 新开仓要求更强的基本面支撑（不追资添仓）
- ⚠️ "Buy the rumor, sell the news" — 语气筑顶时小利好随时可能引发轻仓
- ⚠️ 监测北向资金是否翻转为净流出
        """
    elif fg >= 60:
        advice_text = "🟡 贪婪 — 市场选择偵康，但要防范主力采笹应局"
        advice_detail = """
**操作建议**
- ✅ 市场热度高但未到顶部，可少量添仓跟进
- ✅ 优先选择具有基本面支山的标的
- ⚠️ 误信号厯能增加，不轻弹全仓入
        """
    elif fg >= 40:
        advice_text = "⚪ 中性 — 市场情绪平衡，逸有分昔观察横盘机会"
        advice_detail = """
**操作建议**
- ✅ 等待情绪确方向后再加入
- ✅ 逸有娇眼收集基本面优缺且尚未被挖掘的标的
- ✅ 重点关注北向资金和强弱轮动信号
        """
    elif fg >= 20:
        advice_text = "🔵 恐惧 — 市场情绪低迷，反向指标开始上升"
        advice_detail = """
**操作建议**
- ✅ 反转窗口开始出现，安全边际少量布局
- ✅ 优先看大盘追辟过多的蓝筹指数 ETF
- ⚠️ 情绪还未到谷底，不要现在全仓入
- 💡 结合宏观政策信号 + 恐贪指数共振，信号质量大幅提升
        """
    else:
        advice_text = "🔵 极度恐惧 — 历史上是最好的买入机会区间"
        advice_detail = """
**操作建议**
- 🔥 共同恐惧 — Warren Buffett: "Be fearful when others are greedy, be greedy when others are fearful"
- ✅ 等待 1~2 个交易日确认底部信号（大涌量阳线或政策出台）再入
- ✅ 分批买入，第一批对应 ETF（非个股）伦风险
- ⚠️ 不要试图猫丸底，第一批可以不完美
        """
    st.info(advice_text)
    with st.expander("💡 详细操作建议", expanded=(fg >= 80 or fg <= 20)):
        st.markdown(advice_detail)

    st.divider()

    # ── 历史趋势图 ───────────────────────────────────────────
    st.subheader("📈 情绪历史趋势")

    if len(hist) >= 2:
        # 构建图表数据
        import pandas as pd
        df_sent = pd.DataFrame([
            {
                "time": r["ts"][:16],
                "恐贪指数": r["fear_greed"],
                "北向资金": r.get("northbound", 0),
            }
            for r in reversed(hist)  # 时间正序
        ])
        df_sent["time"] = pd.to_datetime(df_sent["time"])
        df_sent = df_sent.set_index("time")

        # 恐贪指数折线图
        st.line_chart(df_sent["恐贪指数"], height=200, use_container_width=True)

        # 北向资金柱状图
        st.bar_chart(df_sent["北向资金"], height=150, use_container_width=True)
    else:
        st.caption("记录不足，多采集几次后显示趋势图")

    st.divider()

    # ── 历史快照列表 ───────────────────────────────────────
    st.subheader("🕒 历史快照")
    hist_cols = st.columns([2, 2, 2, 2, 4])
    hist_cols[0].markdown("**时间**")
    hist_cols[1].markdown("**恐贪指数**")
    hist_cols[2].markdown("**北向资金**")
    hist_cols[3].markdown("**方向**")
    hist_cols[4].markdown("**标签**")

    for row in hist[:20]:
        fg_v = row.get("fear_greed", 50)
        d = row.get("direction", "NEUTRAL")
        d_mark = "↑" if d == "BULLISH" else ("↓" if d == "BEARISH" else "—")
        nd_v = row.get("northbound", 0)
        cc = hist_cols
        with st.container():
            cols_row = st.columns([2, 2, 2, 2, 4])
            cols_row[0].caption(row.get("ts", "")[:16])
            # 恐贪指数加颜色
            fg_style = "🔴" if fg_v >= 80 else ("🟡" if fg_v >= 60 else ("⚪" if fg_v >= 40 else ("🔵" if fg_v >= 20 else "🔵")))
            cols_row[1].caption(f"{fg_style} {fg_v:.1f}")
            cols_row[2].caption(f"{nd_v:+.1f}亿")
            cols_row[3].caption(d_mark)
            cols_row[4].caption(row.get("label", ""))

    # ── 全期统计 ──────────────────────────────────────────
    if stats:
        st.divider()
        st.subheader("📊 全期统计")
        st_cols = st.columns(4)
        st_cols[0].metric("总快照数", stats.get("total_snapshots", 0))
        st_cols[1].metric("均值", f"{stats.get('avg_fear_greed', 50):.1f}")
        st_cols[2].metric("最高", f"{stats.get('max_fear_greed', 0):.1f}")
        st_cols[3].metric("最低", f"{stats.get('min_fear_greed', 100):.1f}")


# ═══════════════════════════════════════════════════════════════
# TAB 5: 系统（M7 调度器 + 数据文件）
# ═══════════════════════════════════════════════════════════════

with tab_system:
    st.header("⚙️ 系统状态")

    # ── M7 调度器状态 ──
    sched_state = load_scheduler_state()
    st.subheader("🕐 M7 调度器")

    if not sched_state:
        st.warning("调度器未运行。启动命令：`python -m m7_scheduler.cli start`")
        col_cmd1, col_cmd2 = st.columns(2)
        with col_cmd1:
            st.code("python -m m7_scheduler.cli start", language="bash")
        with col_cmd2:
            st.code("python -m m7_scheduler.cli start --background", language="bash")
    else:
        running = sched_state.get("running", False)
        status_icon = "🟢" if running else "🔴"
        st.markdown(f"{status_icon} 调度器状态：{'**运行中**' if running else '**已停止**'}")

        tasks = sched_state.get("tasks", {})
        if tasks:
            import pandas as pd
            task_rows = []
            for name, t in tasks.items():
                last_run = t.get("last_run")
                if last_run:
                    try:
                        dt = datetime.fromisoformat(last_run)
                        mins_ago = int((datetime.now() - dt).total_seconds() / 60)
                        last_run_str = f"{dt.strftime('%H:%M')}（{mins_ago}分前）"
                    except Exception:
                        last_run_str = last_run[:16]
                else:
                    last_run_str = "从未"
                last_status = t.get("last_status") or "—"
                task_rows.append({
                    "任务":     name,
                    "间隔":     f"{t.get('interval_minutes','?')}min",
                    "时间窗口": str(t.get("time_window") or "全天"),
                    "启用":     "✅" if t.get("enabled") else "❌",
                    "运行次数": t.get("run_count", 0),
                    "错误次数": t.get("error_count", 0),
                    "上次运行": last_run_str,
                    "上次结果": last_status,
                })
            st.dataframe(pd.DataFrame(task_rows), use_container_width=True, hide_index=True)

        # 最近运行记录
        recent = sched_state.get("recent_runs", [])[-10:]
        if recent:
            with st.expander("最近运行记录"):
                for r in reversed(recent):
                    color = "#00c851" if r.get("status") == "ok" else "#ff4b4b"
                    t_str = str(r.get("at", ""))[:19]
                    st.markdown(
                        f'<span style="color:{color}">●</span> '
                        f'`{t_str}` &nbsp; **{r.get("task","?")}** &nbsp; '
                        f'`{r.get("status","?")}` &nbsp; '
                        f'{r.get("duration_s",0):.1f}s',
                        unsafe_allow_html=True,
                    )

    st.divider()

    # ── 信号统计图表 ──
    st.subheader("📈 信号统计")
    c_left, c_right = st.columns(2)
    with c_left:
        by_type = stats.get("by_signal_type", {})
        if by_type:
            import pandas as pd
            df_type = pd.DataFrame(
                [{"类型": SIGNAL_TYPE_CN.get(k, k), "数量": v} for k, v in by_type.items()]
            ).sort_values("数量", ascending=False)
            st.caption("信号类型分布")
            st.bar_chart(df_type.set_index("类型"))
        else:
            st.info("暂无信号数据")
    with c_right:
        batches = stats.get("recent_batches", {})
        if batches:
            import pandas as pd
            df_b = pd.DataFrame(
                [{"批次": k[-12:], "信号数": v} for k, v in list(batches.items())[-10:]]
            )
            st.caption("最近批次信号量")
            st.bar_chart(df_b.set_index("批次"))
        else:
            st.info("暂无批次数据")

    st.divider()

    # ── 数据文件状态 ──
    st.subheader("📁 数据文件")
    fc1, fc2, fc3, fc4 = st.columns(4)

    with fc1:
        inc_dir = ROOT / "data" / "incoming"
        proc_dir = ROOT / "data" / "processed"
        inc_files = list(inc_dir.glob("*.txt")) if inc_dir.exists() else []
        proc_files = list(proc_dir.glob("*.txt")) if proc_dir.exists() else []
        st.metric("待处理文件", len(inc_files))
        st.caption(f"已处理: {len(proc_files)}")
        for f in sorted(inc_files, reverse=True)[:3]:
            st.text(f"  {f.name[:30]}")

    with fc2:
        opp_dir = ROOT / "data" / "opportunities"
        opp_files = list(opp_dir.glob("*.json")) if opp_dir.exists() else []
        st.metric("机会文件", len(opp_files))

    with fc3:
        db_path = ROOT / "data" / "signals" / "signal_store.db"
        if db_path.exists():
            size_kb = db_path.stat().st_size / 1024
            st.metric("SignalStore", f"{size_kb:.1f} KB")
            st.caption(f"总信号: {stats.get('total', 0)} 条")
        else:
            st.metric("SignalStore", "未初始化")

    with fc4:
        cache_dir = ROOT / "data" / "price_cache"
        cache_files = list(cache_dir.glob("*.json")) if cache_dir.exists() else []
        cache_kb = sum(f.stat().st_size for f in cache_files) / 1024
        st.metric("价格缓存", f"{len(cache_files)} 文件")
        st.caption(f"共 {cache_kb:.1f} KB")

    st.divider()

    # ── 使用说明 ──
    st.subheader("📖 快速命令")
    st.markdown("""
```bash
# 调度器（全自动模式）
python -m m7_scheduler.cli start --background   # 后台启动
python -m m7_scheduler.cli status               # 查看状态
python -m m7_scheduler.cli run signal_pipeline  # 手动触发一次
python -m m7_scheduler.cli run news_collect     # 立即抓取新闻
python -m m7_scheduler.cli stop                 # 停止

# 手动分析
python pipeline/run_pipeline.py --input my_news.txt
python pipeline/ingest.py --dir data/incoming/

# 回测
python -m backtest.backtest_engine --help
```
""")


# ═══════════════════════════════════════════════════════════════
# TAB 6: 工作流 + 确认 + 审计
# ═══════════════════════════════════════════════════════════════

with tab_control:
    st.header("🎛️ 工作流控制中心")

    # ── 当前阶段指示 ──────────────────────────────────────────
    try:
        from pipeline.workflows import WorkflowPhase, resolve_phase, get_phase_steps, run_workflow
        current_phase = resolve_phase("A_SHARE")
        phase_labels = {
            WorkflowPhase.PRE_MARKET: ("🟡 盘前", "准备阶段，采集隔夜信号和情绪快照"),
            WorkflowPhase.INTRADAY: ("🟢 盘中", "交易时段，实时监控和信号处理"),
            WorkflowPhase.POST_MARKET: ("🔴 盘后", "复盘阶段，归因分析和风控检查"),
            WorkflowPhase.CLOSED: ("⚫ 休市", "非交易时段"),
        }
        label, desc = phase_labels.get(current_phase, ("❓", "未知"))
        col_ph1, col_ph2 = st.columns([1, 3])
        with col_ph1:
            st.metric("当前阶段", label)
        with col_ph2:
            st.info(desc)

        # ── 工作流执行 ──────────────────────────────────────────
        st.subheader("阶段工作流")
        phase_names = {
            WorkflowPhase.PRE_MARKET: "盘前工作流",
            WorkflowPhase.INTRADAY: "盘中工作流",
            WorkflowPhase.POST_MARKET: "盘后工作流",
        }

        steps = get_phase_steps(current_phase)
        if steps:
            step_cols = st.columns(min(len(steps), 4))
            for i, step in enumerate(steps):
                with step_cols[i % len(step_cols)]:
                    st.markdown(f"**{step.step_id}** {step.name}")
                    deps = ", ".join(step.depends_on) if step.depends_on else "无依赖"
                    st.caption(f"依赖: {deps}")

        wf_col1, wf_col2, wf_col3 = st.columns(3)
        with wf_col1:
            if st.button("▶ 执行盘前工作流", use_container_width=True):
                with st.spinner("执行盘前工作流..."):
                    result = run_workflow(WorkflowPhase.PRE_MARKET)
                    st.success(f"完成 {result.steps_completed}/{result.steps_total} 步")
        with wf_col2:
            if st.button("▶ 执行盘中工作流", use_container_width=True):
                with st.spinner("执行盘中工作流..."):
                    result = run_workflow(WorkflowPhase.INTRADAY)
                    st.success(f"完成 {result.steps_completed}/{result.steps_total} 步")
        with wf_col3:
            if st.button("▶ 执行盘后工作流", use_container_width=True):
                with st.spinner("执行盘后工作流..."):
                    result = run_workflow(WorkflowPhase.POST_MARKET)
                    st.success(f"完成 {result.steps_completed}/{result.steps_total} 步")
    except Exception as e:
        st.warning(f"工作流模块加载失败: {e}")

    st.divider()

    # ── 确认中心 ──────────────────────────────────────────────
    st.subheader("🔐 确认中心")
    try:
        from pipeline.confirmation_store import ConfirmationStore
        from pipeline.confirmation import ConfirmationStatus

        cfm_store = ConfirmationStore()
        pending = cfm_store.get_pending()

        if not pending:
            st.success("无待确认请求")
        else:
            for req in pending:
                risk_badge = {"low": "🟢", "medium": "🟡", "high": "🔴", "critical": "⛔"}.get(
                    req.get("risk_level", "medium"), "🟡"
                )
                with st.expander(
                    f'{risk_badge} {req["action_type"]} — {req["description"][:60]}',
                    expanded=True,
                ):
                    st.write(f"**创建时间**: {req['created_at']}")
                    if req.get("parameters_json"):
                        try:
                            import json
                            params = json.loads(req["parameters_json"])
                            st.json(params)
                        except Exception:
                            pass
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ 批准", key=f"approve_{req['request_id']}"):
                            cfm_store.approve(req["request_id"], reviewed_by="dashboard_user")
                            from pipeline.audit import audit
                            from pipeline.audit_log import ActionType, Actor, AuditResult
                            audit(
                                action_type=ActionType.CONFIRMATION_APPROVE,
                                actor=Actor.USER,
                                target_id=req["request_id"],
                                description=f"批准: {req['action_type']}",
                                result=AuditResult.SUCCESS,
                            )
                            st.success("已批准")
                            st.rerun()
                    with c2:
                        if st.button("❌ 拒绝", key=f"reject_{req['request_id']}"):
                            note = "dashboard拒绝"
                            cfm_store.reject(req["request_id"], reviewed_by="dashboard_user", note=note)
                            from pipeline.audit import audit
                            from pipeline.audit_log import ActionType, Actor, AuditResult
                            audit(
                                action_type=ActionType.CONFIRMATION_REJECT,
                                actor=Actor.USER,
                                target_id=req["request_id"],
                                description=f"拒绝: {req['action_type']}",
                                result=AuditResult.SUCCESS,
                            )
                            st.warning("已拒绝")
                            st.rerun()

        history = cfm_store.list_history(limit=10)
        if history:
            with st.expander("最近确认历史"):
                import pandas as pd
                hist_df = pd.DataFrame(history)
                display_cols = [c for c in ["created_at", "action_type", "status", "reviewed_by"] if c in hist_df.columns]
                st.dataframe(hist_df[display_cols], use_container_width=True, hide_index=True)
    except Exception as e:
        st.warning(f"确认中心加载失败: {e}")

    st.divider()

    # ── 审计日志 ──────────────────────────────────────────────
    st.subheader("📋 审计日志")
    try:
        from pipeline.audit_store import AuditStore
        audit_store = AuditStore()

        col_a1, col_a2 = st.columns([1, 3])
        with col_a1:
            audit_filter = st.selectbox(
                "动作类型", ["全部"] + [t.value for t in ActionType],
                key="audit_filter",
            )
        with col_a2:
            audit_days = st.slider("查看天数", 1, 30, 7, key="audit_days")

        from datetime import timedelta as _td
        filter_type = None if audit_filter == "全部" else audit_filter
        entries = audit_store.query(
            action_type=filter_type,
            start=datetime.now() - _td(days=audit_days),
            limit=100,
        )

        if entries:
            import pandas as pd
            audit_df = pd.DataFrame(entries)
            display_cols = [c for c in ["timestamp", "action_type", "actor", "description", "result"]
                          if c in audit_df.columns]
            st.dataframe(audit_df[display_cols], use_container_width=True, hide_index=True)

            stats = audit_store.get_stats(days=audit_days)
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                st.metric("总操作数", stats["total_entries"])
            with col_s2:
                st.metric("失败数", stats["failure_count"])
            with col_s3:
                st.metric("成功率", f'{(1 - stats["failure_count"]/max(stats["total_entries"],1)):.0%}')
        else:
            st.info("无审计记录")
    except Exception as e:
        st.warning(f"审计日志加载失败: {e}")
