"""
tests/test_m7.py — M7 调度器测试

覆盖：
  1. ScheduledTask 基础调度逻辑
  2. Scheduler 注册 / 手动触发 / 状态查询
  3. 默认任务注册结构
  4. price_update 任务（无持仓快速返回）
  5. daily_review 任务（无已平仓快速返回）
"""
import json, tempfile
from datetime import datetime, timedelta, time as dtime
from pathlib import Path

from m7_scheduler.scheduler import Scheduler, ScheduledTask


class TestScheduledTask:
    def test_initial_is_due(self):
        call_log = []
        def dummy_task(run_id=""):
            call_log.append(run_id)
            return {"ok": True}

        t1 = ScheduledTask(name="t1", fn=dummy_task, interval_minutes=5)
        assert t1.is_due(datetime.now())

    def test_not_due_after_run(self):
        call_log = []
        def dummy_task(run_id=""):
            call_log.append(run_id)
            return {"ok": True}

        t1 = ScheduledTask(name="t1", fn=dummy_task, interval_minutes=5)
        t1.run()
        assert not t1.is_due(datetime.now())
        assert t1.run_count == 1

    def test_due_after_interval(self):
        def dummy_task(run_id=""):
            return {"ok": True}

        t1 = ScheduledTask(name="t1", fn=dummy_task, interval_minutes=5)
        t1.run()
        t1.last_run = datetime.now() - timedelta(minutes=6)
        assert t1.is_due(datetime.now())

    def test_time_window(self):
        def dummy_task(run_id=""):
            return {"ok": True}

        t2 = ScheduledTask(
            name="t2", fn=dummy_task, interval_minutes=1,
            time_window=("00:00", "00:01"),
        )
        now = datetime.now()
        if not (dtime(0, 0) <= now.time() <= dtime(0, 1)):
            assert not t2.is_due(now)

    def test_disabled_task(self):
        def dummy_task(run_id=""):
            return {"ok": True}

        t3 = ScheduledTask(name="t3", fn=dummy_task, interval_minutes=1, enabled=False)
        assert not t3.is_due(datetime.now())

    def test_error_count_on_failure(self):
        def failing_task(run_id=""):
            raise RuntimeError("测试失败")

        t4 = ScheduledTask(name="t4", fn=failing_task, interval_minutes=1)
        result = t4.run()
        assert result["status"] == "error"
        assert t4.error_count == 1
        assert t4.run_count == 0


class TestScheduler:
    def test_register_and_run_now(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            import m7_scheduler.scheduler as sched_module
            orig_state_file = sched_module.STATE_FILE
            sched_module.STATE_FILE = Path(tmpdir) / "state.json"

            try:
                results = []
                def my_job(run_id=""):
                    results.append({"run_id": run_id})
                    return {"items": len(results)}

                scheduler = Scheduler(tick_interval_seconds=1)
                scheduler.register(ScheduledTask(name="my_job", fn=my_job, interval_minutes=999, enabled=True))

                result = scheduler.run_now("my_job")
                assert result["status"] == "ok"
                assert result["result"]["items"] == 1

                result_err = scheduler.run_now("nonexistent")
                assert result_err["status"] == "error"
            finally:
                sched_module.STATE_FILE = orig_state_file

    def test_default_tasks_registration(self):
        scheduler2 = Scheduler()
        scheduler2.register_default_tasks(config={
            "signal_pipeline": {"interval_minutes": 60},
            "price_update": {"interval_minutes": 5},
            "news_collect": {"enabled": False},
        })

        expected = {"signal_pipeline", "price_update", "daily_review", "news_collect", "sentiment_collect"}
        actual = set(scheduler2.tasks.keys())
        assert expected == actual, f"任务集不符: {actual}"

        assert scheduler2.tasks["signal_pipeline"].interval_minutes == 60
        assert scheduler2.tasks["price_update"].interval_minutes == 5
        assert not scheduler2.tasks["news_collect"].enabled

    def test_time_windows(self):
        scheduler = Scheduler()
        scheduler.register_default_tasks()
        assert scheduler.tasks["price_update"].time_window == ("09:25", "15:05")
        assert scheduler.tasks["daily_review"].time_window == ("15:30", "23:59")
        assert scheduler.tasks["signal_pipeline"].time_window is None

    def test_price_update_no_positions(self):
        scheduler3 = Scheduler()
        scheduler3.register_default_tasks()
        result = scheduler3._task_price_update(run_id="test_price")
        assert "open_positions" in result

    def test_daily_review_no_closed(self):
        scheduler = Scheduler()
        scheduler.register_default_tasks()
        result = scheduler._task_daily_review(run_id="test_review")
        assert "reviewed" in result
