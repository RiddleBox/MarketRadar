"""
m7_scheduler/cli.py — 调度器 CLI

用法：
  python -m m7_scheduler.cli start              # 启动（前台阻塞）
  python -m m7_scheduler.cli start --background # 启动（写 PID 文件后退出，后台运行）
  python -m m7_scheduler.cli status             # 查看任务状态
  python -m m7_scheduler.cli run <task>         # 手动触发一次任务
  python -m m7_scheduler.cli stop               # 停止后台进程

可用任务名：
  signal_pipeline  — 扫描 data/incoming/ → M1→M2→M3→M4
  price_update     — M9 模拟仓价格 tick
  daily_review     — M6 收盘复盘
  news_collect     — M0 AKShare 新闻拉取
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

PID_FILE = ROOT / "data" / "scheduler.pid"
STATE_FILE = ROOT / "data" / "scheduler_state.json"

console = Console()


@click.group()
def cli():
    """M7 调度器 CLI"""
    pass


@cli.command()
@click.option("--background", "-b", is_flag=True, help="后台运行（写 PID 后此进程退出）")
@click.option("--tick", default=30, help="调度 tick 间隔（秒），默认 30")
@click.option("--config", default=None, help="任务配置 JSON 文件（可覆盖 interval/enabled）")
@click.option("--signal-interval", default=30, help="signal_pipeline 间隔（分钟）")
@click.option("--price-interval", default=10, help="price_update 间隔（分钟）")
@click.option("--news-interval", default=15, help="news_collect 间隔（分钟）")
@click.option("--no-news", is_flag=True, help="禁用新闻自动拉取")
def start(background, tick, config, signal_interval, price_interval, news_interval, no_news):
    """启动调度器"""
    from m7_scheduler.scheduler import Scheduler

    # 读取可选配置文件
    task_config = {}
    if config:
        try:
            task_config = json.loads(Path(config).read_text(encoding="utf-8"))
        except Exception as e:
            console.print(f"[red]配置文件读取失败: {e}[/red]")
            sys.exit(1)

    # CLI 参数覆盖
    task_config.setdefault("signal_pipeline", {})["interval_minutes"] = signal_interval
    task_config.setdefault("price_update", {})["interval_minutes"] = price_interval
    task_config.setdefault("news_collect", {})["interval_minutes"] = news_interval
    if no_news:
        task_config.setdefault("news_collect", {})["enabled"] = False

    if background:
        # fork 出子进程（Windows 用 subprocess 模拟）
        import subprocess
        args = [sys.executable, "-m", "m7_scheduler.cli", "start",
                f"--tick={tick}",
                f"--signal-interval={signal_interval}",
                f"--price-interval={price_interval}",
                f"--news-interval={news_interval}"]
        if no_news:
            args.append("--no-news")
        proc = subprocess.Popen(
            args,
            cwd=str(ROOT),
            stdout=open(ROOT / "data" / "logs" / "scheduler.log", "a"),
            stderr=subprocess.STDOUT,
            creationflags=0x00000008 if sys.platform == "win32" else 0,  # DETACHED_PROCESS
        )
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(proc.pid))
        console.print(Panel(
            f"[green]调度器已在后台启动[/green]\n"
            f"PID: {proc.pid}\n"
            f"日志: {ROOT}/data/logs/scheduler.log\n"
            f"状态: python -m m7_scheduler.cli status",
            title="M7 Scheduler",
            box=box.ROUNDED,
        ))
        return

    # 前台运行
    scheduler = Scheduler(tick_interval_seconds=tick)
    scheduler.register_default_tasks(config=task_config)

    console.print(Panel(
        f"[bold cyan]M7 调度器启动[/bold cyan]\n"
        f"任务数: {len(scheduler.tasks)} | tick: {tick}s\n"
        f"[dim]Ctrl+C 停止[/dim]",
        box=box.ROUNDED,
    ))

    _print_task_table(scheduler)

    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    try:
        scheduler.start(background=False)
    except KeyboardInterrupt:
        console.print("\n[yellow]调度器已停止[/yellow]")
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()


@cli.command()
def status():
    """查看任务状态"""
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            _print_status(state)
            return
        except Exception:
            pass

    # state 文件不存在，检查进程
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            console.print(f"[yellow]调度器进程 {pid} 正在运行，但状态文件不可读[/yellow]")
        except OSError:
            console.print("[red]调度器进程已退出（PID 文件残留）[/red]")
            PID_FILE.unlink()
    else:
        console.print("[dim]调度器未运行[/dim]")


@cli.command()
@click.argument("task_name")
@click.option("--verbose", "-v", is_flag=True)
def run(task_name, verbose):
    """手动触发一次任务"""
    from m7_scheduler.scheduler import Scheduler
    import logging
    if verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    scheduler = Scheduler()
    scheduler.register_default_tasks()

    if task_name not in scheduler.tasks:
        console.print(f"[red]未知任务: {task_name}[/red]")
        console.print(f"可用任务: {', '.join(scheduler.tasks.keys())}")
        sys.exit(1)

    console.print(f"[cyan]▶ 触发任务: {task_name}[/cyan]")
    result = scheduler.run_now(task_name)

    status_color = "green" if result.get("status") == "ok" else "red"
    console.print(f"[{status_color}]任务完成: {result.get('status')}[/{status_color}]")
    if result.get("error"):
        console.print(f"[red]错误: {result['error']}[/red]")
    else:
        r = result.get("result", {})
        for k, v in r.items():
            console.print(f"  {k}: {v}")


@cli.command()
def stop():
    """停止后台调度器进程"""
    if not PID_FILE.exists():
        console.print("[dim]调度器未在后台运行（无 PID 文件）[/dim]")
        return
    pid = int(PID_FILE.read_text().strip())
    try:
        if sys.platform == "win32":
            import subprocess
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=True, capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink()
        console.print(f"[green]已停止进程 {pid}[/green]")
    except (ProcessLookupError, subprocess.CalledProcessError):
        console.print(f"[yellow]进程 {pid} 已不存在[/yellow]")
        PID_FILE.unlink()


# ─────────────────────────────────────────────────────────────
# 输出辅助
# ─────────────────────────────────────────────────────────────

def _print_task_table(scheduler):
    table = Table(title="已注册任务", box=box.SIMPLE_HEAVY)
    table.add_column("任务名", style="cyan")
    table.add_column("间隔", justify="right")
    table.add_column("时段")
    table.add_column("状态")
    table.add_column("描述")
    for name, t in scheduler.tasks.items():
        status_str = "[green]启用[/green]" if t.enabled else "[dim]禁用[/dim]"
        window = f"{t.time_window[0]}~{t.time_window[1]}" if t.time_window else "全天"
        table.add_row(name, f"{t.interval_minutes}min", window, status_str, t.description[:40])
    console.print(table)


def _print_status(state: dict):
    running = state.get("running", False)
    status_str = "[green]运行中[/green]" if running else "[red]已停止[/red]"
    console.print(f"\n调度器状态: {status_str}")

    tasks = state.get("tasks", {})
    if tasks:
        table = Table(title="任务状态", box=box.SIMPLE_HEAVY)
        table.add_column("任务名", style="cyan")
        table.add_column("启用")
        table.add_column("间隔")
        table.add_column("运行次数", justify="right")
        table.add_column("错误次数", justify="right")
        table.add_column("上次运行")
        table.add_column("上次结果")
        for name, t in tasks.items():
            enabled = "[green]✓[/green]" if t.get("enabled") else "[dim]✗[/dim]"
            last_run = t.get("last_run", "-")
            if last_run and last_run != "-":
                from datetime import datetime
                try:
                    dt = datetime.fromisoformat(last_run)
                    ago = (datetime.now() - dt).seconds // 60
                    last_run = f"{dt.strftime('%H:%M:%S')} ({ago}min前)"
                except Exception:
                    pass
            last_status = t.get("last_status") or "-"
            status_color = "green" if last_status == "ok" else "red" if last_status == "error" else "dim"
            table.add_row(
                name, enabled,
                f"{t.get('interval_minutes', '?')}min",
                str(t.get("run_count", 0)),
                str(t.get("error_count", 0)),
                last_run or "-",
                f"[{status_color}]{last_status}[/{status_color}]",
            )
        console.print(table)

    # 最近运行记录
    recent = state.get("recent_runs", [])[-8:]
    if recent:
        console.print("\n最近运行记录:")
        for r in reversed(recent):
            color = "green" if r.get("status") == "ok" else "red"
            t = r.get("at", "")[:19]
            console.print(
                f"  [{color}]●[/{color}] [{t}] {r.get('task','?'):20} "
                f"{r.get('status','?'):8} {r.get('duration_s', 0):.1f}s"
            )


if __name__ == "__main__":
    cli()
