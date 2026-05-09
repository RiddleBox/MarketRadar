"""
MarketRadar Dashboard V2 - 主页
控制中心 + 快速总览
"""
import sys
from pathlib import Path

import streamlit as st

# 添加项目根目录到路径
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dashboard_v2.utils.data_loader import (
    get_summary_stats,
    load_scheduler_state,
    clear_all_cache,
)
from dashboard_v2.components.metrics import (
    metric_card,
    status_badge,
    info_card,
    action_button,
)

# 导入 OpenD 管理器
try:
    from integrations.opend_manager import get_opend_manager
    OPEND_AVAILABLE = True
except ImportError:
    OPEND_AVAILABLE = False

# ═══════════════════════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="MarketRadar V2",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stMetric { background: #1e1e2e; padding: 12px; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# 侧边栏
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.image("https://img.icons8.com/ios-filled/50/00c851/radar.png", width=40)
    st.title("MarketRadar V2")
    st.caption("模块化市场机会发现系统")
    st.divider()

    if st.button("🔄 刷新数据", use_container_width=True):
        clear_all_cache()
        st.rerun()

    st.divider()

    # 系统关闭按钮
    st.caption("⚠️ 系统控制")

    if st.button("🛑 关闭所有服务", type="secondary", use_container_width=True, help="停止调度器、OpenD和Dashboard"):
        import subprocess
        import os
        import signal

        with st.spinner("正在关闭所有服务..."):
            # 1. 停止调度器
            try:
                subprocess.run(
                    [sys.executable, "-m", "m7_scheduler.cli", "stop"],
                    cwd=str(ROOT),
                    capture_output=True,
                    timeout=10
                )
                st.success("✅ 调度器已停止")
            except Exception as e:
                st.warning(f"调度器停止失败: {e}")

            # 2. 停止 OpenD
            if OPEND_AVAILABLE:
                try:
                    opend_mgr = get_opend_manager()
                    result = opend_mgr.stop()
                    if result["success"]:
                        st.success("✅ OpenD 已停止")
                    else:
                        st.warning(f"OpenD 停止失败: {result['message']}")
                except Exception as e:
                    st.warning(f"OpenD 停止失败: {e}")

            # 3. 关闭其他可能的 Streamlit 进程（8501, 8502端口）
            try:
                if sys.platform == "win32":
                    # Windows: 查找并关闭占用8501和8502端口的进程
                    for port in [8501, 8502]:
                        result = subprocess.run(
                            f'netstat -ano | findstr :{port}',
                            shell=True,
                            capture_output=True,
                            text=True
                        )
                        if result.stdout:
                            # 提取PID并终止
                            lines = result.stdout.strip().split('\n')
                            for line in lines:
                                parts = line.split()
                                if len(parts) >= 5:
                                    pid = parts[-1]
                                    try:
                                        subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
                                        st.success(f"✅ 已关闭端口 {port} 的进程 (PID: {pid})")
                                    except:
                                        pass
                else:
                    # Linux/Mac: 使用 lsof 查找并关闭
                    for port in [8501, 8502]:
                        result = subprocess.run(
                            f'lsof -ti:{port}',
                            shell=True,
                            capture_output=True,
                            text=True
                        )
                        if result.stdout:
                            pids = result.stdout.strip().split('\n')
                            for pid in pids:
                                try:
                                    subprocess.run(f'kill -9 {pid}', shell=True, capture_output=True)
                                    st.success(f"✅ 已关闭端口 {port} 的进程 (PID: {pid})")
                                except:
                                    pass
            except Exception as e:
                st.warning(f"清理端口进程时出错: {e}")

            st.success("🎉 所有服务已关闭")
            st.info("Dashboard 将在 2 秒后自动退出...")

            # 4. 最后关闭当前 Dashboard
            import time
            time.sleep(2)
            os.kill(os.getpid(), signal.SIGTERM)

    st.caption("💡 使用左侧导航切换功能页面")

# ═══════════════════════════════════════════════════════════════
# 主页内容
# ═══════════════════════════════════════════════════════════════

st.title("📡 MarketRadar 控制中心")

# ── 总览指标 ──
st.subheader("📊 系统总览")
stats = get_summary_stats()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("💼 持仓数", stats["positions_count"])
with col2:
    st.metric("🎯 机会数", stats["opportunities_count"])
with col3:
    st.metric("📶 信号总数", stats["signals_count"])
with col4:
    scheduler_status = "🟢 运行中" if stats["scheduler_running"] else "🔴 已停止"
    st.metric("⚙️ 调度器", scheduler_status)

# ── 信号类型分布 ──
st.markdown("##### 📊 信号类型分布（最近7天）")

from dashboard_v2.utils.data_loader import load_signal_stats
signal_stats = load_signal_stats()
by_type = signal_stats.get("by_signal_type", {})

if by_type:
    col_sig1, col_sig2, col_sig3, col_sig4, col_sig5, col_sig6 = st.columns(6)

    type_labels = {
        "sentiment": ("情绪", "💭"),
        "macro": ("宏观", "🌍"),
        "event_driven": ("事件", "⚡"),
        "industry": ("行业", "🏭"),
        "policy": ("政策", "📜"),
        "technical": ("技术", "📈"),
    }

    cols = [col_sig1, col_sig2, col_sig3, col_sig4, col_sig5, col_sig6]
    for idx, (sig_type, count) in enumerate(sorted(by_type.items(), key=lambda x: -x[1])):
        if idx < 6:
            label, emoji = type_labels.get(sig_type, (sig_type, "📊"))
            with cols[idx]:
                st.metric(f"{emoji} {label}", count)

st.divider()

# ── OpenD 控制 ──
st.subheader("🔌 FutuOpenD 行情网关")

if OPEND_AVAILABLE:
    opend_mgr = get_opend_manager(force_reload=True)  # 强制重新加载配置
    opend_status = opend_mgr.status()
    opend_running = opend_status["running"]
    opend_pid = opend_status.get("pid")

    col_opend1, col_opend2, col_opend3, col_opend4 = st.columns(4)

    with col_opend1:
        status_text = "🟢 运行中" if opend_running else "🔴 已停止"
        st.metric("OpenD 状态", status_text)

    with col_opend2:
        if opend_running and opend_pid:
            st.metric("进程 PID", opend_pid)
        else:
            st.metric("进程 PID", "-")

    with col_opend3:
        st.metric("端口", opend_status["port"])

    with col_opend4:
        st.metric("地址", opend_status["host"])

    # OpenD 控制按钮
    col_opend_ctrl1, col_opend_ctrl2, col_opend_ctrl3 = st.columns(3)

    with col_opend_ctrl1:
        if st.button("🚀 启动 OpenD", disabled=opend_running, use_container_width=True):
            with st.spinner("正在启动 OpenD..."):
                result = opend_mgr.start(wait=True)
                if result["success"]:
                    st.success(result["message"])
                    st.rerun()
                else:
                    st.error(result["message"])

    with col_opend_ctrl2:
        if st.button("⏸️ 停止 OpenD", disabled=not opend_running, use_container_width=True):
            with st.spinner("正在停止 OpenD..."):
                result = opend_mgr.stop()
                if result["success"]:
                    st.success(result["message"])
                    st.rerun()
                else:
                    st.error(result["message"])

    with col_opend_ctrl3:
        if st.button("🔄 重启 OpenD", use_container_width=True):
            with st.spinner("正在重启 OpenD..."):
                result = opend_mgr.restart()
                if result["success"]:
                    st.success(result["message"])
                    st.rerun()
                else:
                    st.error(result["message"])

    # 显示 OpenD 状态提示
    if not opend_running:
        st.warning("⚠️ OpenD 未运行，M12 市场扫描任务将无法执行（依赖实时行情数据）")
    else:
        st.info(f"✅ OpenD 运行中 | 可执行 A股/港股/美股 实时行情扫描")

else:
    st.error("❌ OpenD 管理器不可用，请检查 integrations/opend_manager.py")

st.divider()

# ── 调度器控制 ──
st.subheader("⚙️ 调度器控制")

sched_state = load_scheduler_state()
is_running = sched_state.get("running", False)

col_ctrl1, col_ctrl2, col_ctrl3 = st.columns(3)

with col_ctrl1:
    if st.button("🚀 启动调度器", disabled=is_running, use_container_width=True):
        import subprocess
        try:
            # Start scheduler in background with proper log redirection
            log_file = ROOT / "data" / "logs" / "scheduler.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)

            subprocess.Popen(
                [sys.executable, "-m", "m7_scheduler.cli", "start", "--background"],
                cwd=str(ROOT),
                stdout=open(log_file, "a", encoding="utf-8"),
                stderr=subprocess.STDOUT,
                creationflags=0x00000008 if sys.platform == "win32" else 0,  # DETACHED_PROCESS on Windows
            )
            st.success("调度器启动命令已发送，请等待3-5秒后刷新")
        except Exception as e:
            st.error(f"启动失败: {e}")

with col_ctrl2:
    if st.button("⏸️ 停止调度器", disabled=not is_running, use_container_width=True):
        import subprocess
        try:
            subprocess.run(
                [sys.executable, "-m", "m7_scheduler.cli", "stop"],
                cwd=str(ROOT),
                capture_output=True,
            )
            st.success("调度器已停止")
            st.rerun()
        except Exception as e:
            st.error(f"停止失败: {e}")

with col_ctrl3:
    if st.button("🔄 重启调度器", use_container_width=True):
        import subprocess
        try:
            subprocess.run([sys.executable, "-m", "m7_scheduler.cli", "stop"], cwd=str(ROOT), capture_output=True)
            import time
            time.sleep(2)

            log_file = ROOT / "data" / "logs" / "scheduler.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)

            subprocess.Popen(
                [sys.executable, "-m", "m7_scheduler.cli", "start", "--background"],
                cwd=str(ROOT),
                stdout=open(log_file, "a", encoding="utf-8"),
                stderr=subprocess.STDOUT,
                creationflags=0x00000008 if sys.platform == "win32" else 0,
            )
            st.success("调度器重启命令已发送，请等待3-5秒后刷新")
        except Exception as e:
            st.error(f"重启失败: {e}")

# 显示调度器任务状态
if is_running:
    tasks = sched_state.get("tasks", {})
    enabled_count = sum(1 for t in tasks.values() if t.get("enabled"))
    st.info(f"✅ 调度器运行中 | 已启用任务: {enabled_count}/{len(tasks)}")
else:
    st.warning("⚠️ 调度器未运行")

st.divider()

# ── 手动触发任务 ──
st.subheader("🎯 手动触发任务")

col_trigger1, col_trigger2 = st.columns(2)

with col_trigger1:
    st.markdown("##### 📊 M12 市场扫描")
    st.caption("主动发现价格异动机会")

    scan_market = st.selectbox(
        "选择市场",
        ["A股 (A-Share)", "港股 (HK)", "美股 (US)"],
        key="scan_market"
    )

    scan_type = st.radio(
        "扫描类型",
        ["盘中扫描 (监控池)", "盘前扫描 (隔夜信号)", "盘后扫描 (全市场)"],
        key="scan_type"
    )

    if st.button("▶ 执行 M12 扫描", type="primary", use_container_width=True):
        import subprocess

        market_map = {
            "A股 (A-Share)": "a_share",
            "港股 (HK)": "hk",
            "美股 (US)": "us"
        }
        market_code = market_map[scan_market]

        task_map = {
            "盘中扫描 (监控池)": f"m12_{market_code}_scan",
            "盘前扫描 (隔夜信号)": f"m12_premarket_{market_code}",
            "盘后扫描 (全市场)": f"m12_postmarket_{market_code}"
        }
        task_name = task_map[scan_type]

        with st.spinner(f"正在执行 {scan_type}..."):
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "m7_scheduler.cli", "run", task_name],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    timeout=600,  # 增加到 10 分钟
                )
                if result.returncode == 0:
                    st.success(f"✅ {scan_type} 完成")
                    st.info("请切换到「🎯 机会」页面查看扫描结果")
                else:
                    st.error(f"执行失败: {result.stderr}")
            except subprocess.TimeoutExpired:
                st.warning("执行超时（10分钟），任务可能仍在后台运行，请前往「⚙️ 调度器」页面查看执行记录")
            except Exception as e:
                st.error(f"执行出错: {e}")

with col_trigger2:
    st.markdown("##### 📶 信号处理链")
    st.caption("处理用户提供的信号文件")

    incoming_dir = ROOT / "data" / "incoming"
    incoming_files = list(incoming_dir.glob("*")) if incoming_dir.exists() else []

    st.metric("待处理文件", len(incoming_files))

    if incoming_files:
        with st.expander("查看待处理文件"):
            for f in incoming_files[:10]:
                st.text(f"  • {f.name}")

    if st.button("▶ 执行信号处理", type="primary", use_container_width=True, disabled=len(incoming_files) == 0):
        import subprocess
        with st.spinner("正在处理信号..."):
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "m7_scheduler.cli", "run", "signal_pipeline"],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode == 0:
                    st.success("✅ 信号处理完成")
                    st.info("请切换到「📶 信号」页面查看处理结果")
                else:
                    st.error(f"执行失败: {result.stderr}")
            except subprocess.TimeoutExpired:
                st.warning("执行超时（5分钟），任务可能仍在后台运行")
            except Exception as e:
                st.error(f"执行出错: {e}")

st.divider()

# ── 功能说明 ──
st.subheader("📖 功能说明")

col_doc1, col_doc2 = st.columns(2)

with col_doc1:
    info_card(
        "M12 扫描 vs 信号处理",
        """
        • M12扫描: 主动扫描市场价格 → 异动检测 → 反向溯因 → 趋势判断 → 机会生成
        • 信号处理: 处理用户信号文件 → M0收集 → M1解码 → M2存储 → M3判断 → M4行动计划
        """
    )

with col_doc2:
    info_card(
        "页面导航",
        """
        • 💼 持仓: 查看当前持仓和盈亏情况
        • 🎯 机会: 查看M12扫描发现的机会
        • 🔍 信号剖面: 深入分析信号决策链路
        • 🧠 情绪面: 市场情绪可视化分析
        • ⚙️ 调度器: 详细的调度器管理
        """
    )

st.divider()

# ── 最近活动 ──
st.subheader("📈 最近活动")

recent_runs = sched_state.get("recent_runs", [])[-10:]
if recent_runs:
    for run in reversed(recent_runs):
        status = run.get("status", "unknown")
        color = "#00c851" if status == "ok" else "#ff4b4b"
        task_name = run.get("task", "未知任务")
        timestamp = (run.get("at") or "")[:19]
        duration = run.get("duration_s", 0)

        st.markdown(
            f'<span style="color:{color}">●</span> '
            f'`{timestamp}` &nbsp; **{task_name}** &nbsp; '
            f'`{status}` &nbsp; {duration:.1f}s',
            unsafe_allow_html=True,
        )
else:
    st.info("暂无最近活动记录")
