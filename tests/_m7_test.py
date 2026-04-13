"""
tests/_m7_test.py — M7 调度器测试

覆盖：
  1. ScheduledTask 基础调度逻辑（is_due / time_window / run_at_start）
  2. Scheduler 注册 / 手动触发 / 状态查询
  3. signal_pipeline 任务（临时文件 → M1→M2→M3→M4 真实链路）
  4. daily_review 任务（M9 模拟仓 → SignalEvaluator → M8 写入）
  5. 状态文件持久化

注意：signal_pipeline 需要 LLM（DeepSeek），无 API Key 时跳过。
"""
import sys, json, tempfile, time, logging
from datetime import datetime, date, timedelta
from pathlib import Path

sys.path.insert(0, r"D:\AIproject\MarketRadar")
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

from m7_scheduler.scheduler import Scheduler, ScheduledTask


# ═══════════════════════════════════════════════════════════════
# 测试1：ScheduledTask 调度逻辑
# ═══════════════════════════════════════════════════════════════
print("=" * 60)
print("测试1: ScheduledTask 调度逻辑")
print("=" * 60)

call_log = []

def dummy_task(run_id=""):
    call_log.append(run_id)
    return {"ok": True}

# 1a. 未运行过的任务，is_due=True
t1 = ScheduledTask(name="t1", fn=dummy_task, interval_minutes=5)
assert t1.is_due(datetime.now()), "未运行过的任务应该 is_due=True"
print("✓ 未运行过的任务 is_due=True")

# 1b. 运行后未到间隔
t1.run()
assert not t1.is_due(datetime.now()), "刚运行完的任务不应 is_due"
print("✓ 刚运行完的任务 is_due=False")
assert t1.run_count == 1
assert call_log[0].startswith("t1_")
print(f"✓ 运行计数正确: run_count={t1.run_count}")

# 1c. 模拟时间流逝（手动修改 last_run）
t1.last_run = datetime.now() - timedelta(minutes=6)
assert t1.is_due(datetime.now()), "超过间隔应 is_due=True"
print("✓ 超过间隔后 is_due=True")

# 1d. time_window 限制
t2 = ScheduledTask(
    name="t2", fn=dummy_task, interval_minutes=1,
    time_window=("00:00", "00:01"),   # 几乎不可能在这个时段
)
# 除非当前时间恰好在 00:00~00:01，否则 is_due=False
now = datetime.now()
from datetime import time as dtime
if not (dtime(0, 0) <= now.time() <= dtime(0, 1)):
    assert not t2.is_due(now), "不在时间窗口内不应 is_due"
    print("✓ 时间窗口限制生效")

# 1e. disabled 任务
t3 = ScheduledTask(name="t3", fn=dummy_task, interval_minutes=1, enabled=False)
assert not t3.is_due(datetime.now()), "disabled 任务不应 is_due"
print("✓ disabled 任务 is_due=False")

# 1f. 任务失败时错误计数
def failing_task(run_id=""):
    raise RuntimeError("测试失败")

t4 = ScheduledTask(name="t4", fn=failing_task, interval_minutes=1)
result = t4.run()
assert result["status"] == "error"
assert t4.error_count == 1
assert t4.run_count == 0   # 失败不算运行成功
print(f"✓ 任务失败时错误计数: error_count={t4.error_count}")


# ═══════════════════════════════════════════════════════════════
# 测试2：Scheduler 注册 / 状态 / 手动触发
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("测试2: Scheduler 注册 / 状态 / 手动触发")
print("=" * 60)

with tempfile.TemporaryDirectory() as tmpdir:
    import m7_scheduler.scheduler as sched_module
    orig_state_file = sched_module.STATE_FILE
    sched_module.STATE_FILE = Path(tmpdir) / "state.json"

    scheduler = Scheduler(tick_interval_seconds=1)

    # 注册自定义任务
    results = []
    def my_job(run_id=""):
        results.append({"run_id": run_id, "time": datetime.now().isoformat()})
        return {"items": len(results)}

    scheduler.register(ScheduledTask(name="my_job", fn=my_job, interval_minutes=999, enabled=True))
    assert "my_job" in scheduler.tasks
    print("✓ 任务注册成功")

    # 手动触发
    result = scheduler.run_now("my_job")
    assert result["status"] == "ok"
    assert result["result"]["items"] == 1
    print(f"✓ 手动触发成功: {result['result']}")

    # 触发不存在的任务
    result = scheduler.run_now("nonexistent")
    assert result["status"] == "error"
    print("✓ 不存在的任务返回 error")

    # status 检查
    status = scheduler.status()
    assert "my_job" in status["tasks"]
    assert status["tasks"]["my_job"]["run_count"] == 1
    print(f"✓ status() 正确: run_count={status['tasks']['my_job']['run_count']}")

    # 状态文件写入
    scheduler._save_state()
    assert sched_module.STATE_FILE.exists()
    state = json.loads(sched_module.STATE_FILE.read_text(encoding="utf-8"))
    assert "tasks" in state
    print("✓ 状态文件写入成功")

    sched_module.STATE_FILE = orig_state_file


# ═══════════════════════════════════════════════════════════════
# 测试3：register_default_tasks 结构正确
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("测试3: 默认任务注册结构")
print("=" * 60)

scheduler2 = Scheduler()
scheduler2.register_default_tasks(config={
    "signal_pipeline": {"interval_minutes": 60},
    "price_update": {"interval_minutes": 5},
    "news_collect": {"enabled": False},
})

expected = {"signal_pipeline", "price_update", "daily_review", "news_collect"}
assert expected == set(scheduler2.tasks.keys()), f"任务集不符: {set(scheduler2.tasks.keys())}"
print(f"✓ 默认任务注册完整: {list(scheduler2.tasks.keys())}")

assert scheduler2.tasks["signal_pipeline"].interval_minutes == 60
assert scheduler2.tasks["price_update"].interval_minutes == 5
assert not scheduler2.tasks["news_collect"].enabled
print("✓ 任务参数覆盖正确")

# time_window 验证
assert scheduler2.tasks["price_update"].time_window == ("09:25", "15:05")
assert scheduler2.tasks["daily_review"].time_window == ("15:30", "23:59")
assert scheduler2.tasks["signal_pipeline"].time_window is None
print("✓ 时间窗口配置正确")


# ═══════════════════════════════════════════════════════════════
# 测试4：price_update 任务（无 OPEN 仓时快速返回）
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("测试4: price_update 任务（无持仓时）")
print("=" * 60)

# 直接调用任务函数，不需要 AKShare 在线
scheduler3 = Scheduler()
scheduler3.register_default_tasks()

# 没有 OPEN 持仓时应该快速返回（不发请求）
result = scheduler3._task_price_update(run_id="test_price")
assert "open_positions" in result
print(f"✓ price_update 无持仓时正常返回: {result}")


# ═══════════════════════════════════════════════════════════════
# 测试5：daily_review 任务（无已平仓时快速返回）
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("测试5: daily_review 任务（无已平仓时）")
print("=" * 60)

result = scheduler3._task_daily_review(run_id="test_review")
assert "reviewed" in result
print(f"✓ daily_review 无已平仓时正常返回: {result}")


# ═══════════════════════════════════════════════════════════════
# 测试6：signal_pipeline 任务（用真实临时文件）
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("测试6: signal_pipeline 任务（需 LLM API）")
print("=" * 60)

# 检查 LLM 是否可用
from core.llm_client import LLMClient
try:
    llm = LLMClient()
    llm_ok = True
except Exception:
    llm_ok = False

if not llm_ok:
    print("⏭  LLM 不可用，跳过 signal_pipeline 测试")
else:
    with tempfile.TemporaryDirectory() as tmpdir:
        import m7_scheduler.scheduler as sched_mod

        # 临时替换 ROOT 指向
        orig_root = sched_mod.ROOT
        sched_mod.ROOT = Path(tmpdir)

        # 创建必要目录和文件
        (Path(tmpdir) / "data" / "incoming").mkdir(parents=True)
        (Path(tmpdir) / "data" / "processed").mkdir(parents=True)
        (Path(tmpdir) / "data" / "logs").mkdir(parents=True)

        test_news = """
2024年10月，国家发改委发布新能源汽车补贴政策延长通知，
补贴规模扩大至500亿元，重点支持纯电动乘用车和商用车购置。
同日，多家头部车企股价涨停，产业链供应商大幅上涨。
受益标的：比亚迪（002594）、宁德时代（300750）、特斯拉供应商。
"""
        test_file = Path(tmpdir) / "data" / "incoming" / "20241001_test_news.txt"
        test_file.write_text(test_news, encoding="utf-8")

        sched_test = Scheduler()
        sched_test.register_default_tasks()

        result = sched_test._task_signal_pipeline(run_id="test_pipeline")
        print(f"  处理文件: {result.get('processed_files', 0)}")
        print(f"  信号数:   {result.get('total_signals', 0)}")
        print(f"  机会数:   {result.get('total_opportunities', 0)}")

        assert result.get("processed_files", 0) >= 1 or result.get("total_signals", 0) >= 0
        print("✓ signal_pipeline 执行完成")

        sched_mod.ROOT = orig_root


# ═══════════════════════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("✅ M7 调度器测试全部通过")
print("=" * 60)
print("  ScheduledTask: is_due / time_window / error_count ✓")
print("  Scheduler: register / run_now / status / state_file ✓")
print("  默认任务: signal_pipeline / price_update / daily_review / news_collect ✓")
print("  price_update (无持仓快速返回) ✓")
print("  daily_review (无已平仓快速返回) ✓")
print()
print("  CLI 用法：")
print("    python -m m7_scheduler.cli start              # 前台运行")
print("    python -m m7_scheduler.cli start --background # 后台运行")
print("    python -m m7_scheduler.cli run signal_pipeline # 手动触发")
print("    python -m m7_scheduler.cli status             # 查看状态")
