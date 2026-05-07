"""
MarketRadar Dashboard V2 - 调度器页面
详细的调度器管理和任务监控
"""
import sys
from pathlib import Path

import streamlit as st
import pandas as pd

# 添加项目根目录到路径
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from dashboard_v2.utils.data_loader import load_scheduler_state
from dashboard_v2.components.metrics import status_badge, empty_state

# ═══════════════════════════════════════════════════════════════
# 页面配置
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="调度器 - MarketRadar V2",
    page_icon="⚙️",
    layout="wide",
)

st.title("⚙️ 调度器管理")

# ═══════════════════════════════════════════════════════════════
# 加载数据
# ═══════════════════════════════════════════════════════════════

sched_state = load_scheduler_state()
is_running = sched_state.get("running", False)
tasks = sched_state.get("tasks", {})
recent_runs = sched_state.get("recent_runs", [])

# ═══════════════════════════════════════════════════════════════
# 调度器状态
# ═══════════════════════════════════════════════════════════════

st.subheader("📊 调度器状态")

col_status1, col_status2, col_status3, col_status4 = st.columns(4)

with col_status1:
    status_text = "🟢 运行中" if is_running else "🔴 已停止"
    st.metric("状态", status_text)

with col_status2:
    enabled_count = sum(1 for t in tasks.values() if t.get("enabled"))
    st.metric("已启用任务", f"{enabled_count}/{len(tasks)}")

with col_status3:
    total_runs = sum(t.get("run_count", 0) for t in tasks.values())
    st.metric("总运行次数", total_runs)

with col_status4:
    total_errors = sum(t.get("error_count", 0) for t in tasks.values())
    st.metric("总错误次数", total_errors)

st.divider()

# ═══════════════════════════════════════════════════════════════
# 任务列表
# ═══════════════════════════════════════════════════════════════

st.subheader("📋 任务列表")

if not tasks:
    empty_state("暂无任务信息", "📭")
else:
    # 转换为DataFrame
    task_rows = []
    for name, task in tasks.items():
        last_run = task.get("last_run", "")
        if last_run:
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(last_run)
                mins_ago = int((datetime.now() - dt).total_seconds() / 60)
                last_run_str = f"{dt.strftime('%H:%M')} ({mins_ago}分钟前)"
            except:
                last_run_str = last_run[:16]
        else:
            last_run_str = "从未运行"

        task_rows.append({
            "任务名": name,
            "描述": task.get("description", "")[:40],
            "间隔": f"{task.get('interval_minutes', '?')}分钟",
            "时间窗口": str(task.get("time_window") or "全天"),
            "启用": "✅" if task.get("enabled") else "❌",
            "运行次数": task.get("run_count", 0),
            "错误次数": task.get("error_count", 0),
            "上次运行": last_run_str,
            "上次结果": task.get("last_status", "-"),
        })

    df_tasks = pd.DataFrame(task_rows)

    # 显示表格
    st.dataframe(
        df_tasks,
        use_container_width=True,
        hide_index=True,
        column_config={
            "上次结果": st.column_config.TextColumn(
                "上次结果",
                help="ok=成功, error=失败",
            )
        }
    )

    # 任务详情
    st.markdown("---")
    st.markdown("##### 任务详情")

    selected_task = st.selectbox(
        "选择任务查看详情",
        options=list(tasks.keys()),
        format_func=lambda x: f"{x} - {tasks[x].get('description', '')[:30]}"
    )

    if selected_task:
        task_detail = tasks[selected_task]

        col_detail1, col_detail2 = st.columns(2)

        with col_detail1:
            st.markdown("**基本信息**")
            st.text(f"任务名: {selected_task}")
            st.text(f"描述: {task_detail.get('description', '')}")
            st.text(f"间隔: {task_detail.get('interval_minutes')}分钟")
            st.text(f"时间窗口: {task_detail.get('time_window') or '全天'}")
            st.text(f"启用状态: {'✅ 启用' if task_detail.get('enabled') else '❌ 禁用'}")

        with col_detail2:
            st.markdown("**运行统计**")
            st.text(f"运行次数: {task_detail.get('run_count', 0)}")
            st.text(f"错误次数: {task_detail.get('error_count', 0)}")

            # 安全处理 last_run
            last_run = task_detail.get('last_run') or '从未'
            if last_run != '从未' and len(last_run) > 19:
                last_run = last_run[:19]
            st.text(f"上次运行: {last_run}")

            st.text(f"上次结果: {task_detail.get('last_status', '-')}")

            # 成功率
            run_count = task_detail.get('run_count', 0)
            error_count = task_detail.get('error_count', 0)
            if run_count > 0:
                success_rate = (run_count - error_count) / run_count * 100
                st.text(f"成功率: {success_rate:.1f}%")

        # 手动触发按钮
        st.markdown("---")
        if st.button(f"▶ 手动触发 {selected_task}", type="primary"):
            import subprocess
            with st.spinner(f"正在执行 {selected_task}..."):
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "m7_scheduler.cli", "run", selected_task],
                        cwd=str(ROOT),
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    if result.returncode == 0:
                        st.success(f"✅ {selected_task} 执行完成")
                        st.rerun()
                    else:
                        st.error(f"执行失败: {result.stderr}")
                except subprocess.TimeoutExpired:
                    st.warning("执行超时（5分钟）")
                except Exception as e:
                    st.error(f"执行出错: {e}")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 最近运行记录
# ═══════════════════════════════════════════════════════════════

st.subheader("📈 最近运行记录")

if recent_runs:
    # 显示最近20条
    for run in reversed(recent_runs[-20:]):
        status = run.get("status", "unknown")
        color = "#00c851" if status == "ok" else "#ff4b4b"
        task_name = run.get("task", "未知任务")
        timestamp = run.get("at", "")[:19]
        duration = run.get("duration_s", 0)
        result = run.get("result", {})

        with st.expander(f"{timestamp} - {task_name} - {status}"):
            col_run1, col_run2 = st.columns(2)

            with col_run1:
                st.markdown(
                    f'<span style="color:{color}">●</span> **状态**: `{status}`',
                    unsafe_allow_html=True
                )
                st.text(f"任务: {task_name}")
                st.text(f"时间: {timestamp}")
                st.text(f"耗时: {duration:.2f}秒")

            with col_run2:
                st.markdown("**执行结果**")

                # 如果有错误，显示详细错误信息
                if status == "error" and result:
                    error_msg = result.get("error", "未知错误")
                    error_type = result.get("error_type", "")
                    suggestion = result.get("suggestion", "")

                    st.error(f"**错误**: {error_msg}")

                    if error_type:
                        st.text(f"类型: {error_type}")

                    if suggestion:
                        st.warning(f"💡 **建议**: {suggestion}")

                    # 特殊处理 OpenD 连接失败
                    if error_type == "OpenD_Connection_Failed":
                        st.markdown("---")
                        st.markdown("**解决方案**:")
                        st.markdown("1. 前往 [主页](/) 启动 FutuOpenD")
                        st.markdown("2. 确认 OpenD 状态为 🟢 运行中")
                        st.markdown("3. 重新触发该任务")

                elif result:
                    for k, v in result.items():
                        if k not in ["error", "error_type", "suggestion"]:
                            st.text(f"{k}: {v}")
                else:
                    st.text("无详细结果")
else:
    st.info("暂无运行记录")

st.divider()

# ═══════════════════════════════════════════════════════════════
# 日志查看
# ═══════════════════════════════════════════════════════════════

st.subheader("📜 调度器日志")

log_file = ROOT / "data" / "logs" / "scheduler.log"

if log_file.exists():
    log_lines = st.slider("显示行数", 10, 200, 50)

    if st.button("🔄 刷新日志"):
        st.rerun()

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            recent_lines = lines[-log_lines:]

        log_content = "".join(recent_lines)

        st.text_area(
            "最近日志",
            value=log_content,
            height=400,
            disabled=True,
            label_visibility="collapsed"
        )
    except Exception as e:
        st.error(f"读取日志失败: {e}")
else:
    st.warning("日志文件不存在")
