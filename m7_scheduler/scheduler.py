"""
m7_scheduler/scheduler.py — MarketRadar 任务调度器

负责把各模块串联成自动运行的管道：

  【信号管道】每 N 分钟
    M0 收集新闻 → M1 解码 → M2 存储 → M3 判断 → M4 行动设计

  【价格更新】盘中每 10 分钟
    M9 模拟仓 tick 更新（检查止损止盈）

  【每日复盘】收盘后
    M6 对已平仓/超时持仓做复盘归因 → 写入 M8 知识库

设计原则：
  - 调度本身不持有业务状态，只负责触发各模块
  - 每次任务有独立的 run_id，日志可追溯
  - 任务失败不影响下一次调度（continue on error）
  - 支持手动触发（bypass 调度周期，直接运行一次）
"""
from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
LOG_DIR = ROOT / "data" / "logs"
STATE_FILE = ROOT / "data" / "scheduler_state.json"
LOG_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# 任务定义
# ─────────────────────────────────────────────────────────────

class ScheduledTask:
    """单个调度任务"""

    def __init__(
        self,
        name: str,
        fn: Callable,
        interval_minutes: int,
        enabled: bool = True,
        run_at_start: bool = False,
        description: str = "",
        time_window: Optional[tuple] = None,   # ("09:30", "15:00") 仅在此时段内运行
    ):
        self.name = name
        self.fn = fn
        self.interval_minutes = interval_minutes
        self.enabled = enabled
        self.run_at_start = run_at_start
        self.description = description
        self.time_window = time_window          # None = 全天

        self.last_run: Optional[datetime] = None
        self.last_result: Optional[dict] = None
        self.run_count: int = 0
        self.error_count: int = 0

    def is_due(self, now: datetime) -> bool:
        """判断任务是否到执行时间"""
        if not self.enabled:
            return False
        if self.time_window:
            start_h, start_m = map(int, self.time_window[0].split(":"))
            end_h, end_m = map(int, self.time_window[1].split(":"))
            t = now.time()
            from datetime import time as dtime
            if not (dtime(start_h, start_m) <= t <= dtime(end_h, end_m)):
                return False
        if self.last_run is None:
            return True
        return (now - self.last_run).total_seconds() >= self.interval_minutes * 60

    def run(self) -> dict:
        """执行任务，返回结果 dict"""
        run_id = f"{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        start = datetime.now()
        logger.info(f"[M7] ▶ 任务开始: {self.name} ({run_id})")
        try:
            result = self.fn(run_id=run_id)
            duration = (datetime.now() - start).total_seconds()
            self.run_count += 1
            self.last_run = datetime.now()
            self.last_result = {
                "run_id": run_id,
                "status": "ok",
                "duration_s": round(duration, 2),
                "result": result or {},
            }
            logger.info(f"[M7] ✓ 任务完成: {self.name} ({duration:.1f}s)")
            return self.last_result
        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.error_count += 1
            self.last_run = datetime.now()
            self.last_result = {
                "run_id": run_id,
                "status": "error",
                "error": str(e),
                "duration_s": round(duration, 2),
            }
            logger.error(f"[M7] ✗ 任务失败: {self.name} | {e}")
            return self.last_result

    def status_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "interval_minutes": self.interval_minutes,
            "time_window": self.time_window,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "last_status": self.last_result.get("status") if self.last_result else None,
        }


# ─────────────────────────────────────────────────────────────
# 调度器主体
# ─────────────────────────────────────────────────────────────

class Scheduler:
    """
    MarketRadar 任务调度器。

    用法：
      scheduler = Scheduler()
      scheduler.start()       # 后台线程，非阻塞
      scheduler.run_now("signal_pipeline")   # 手动触发
      scheduler.stop()
    """

    def __init__(self, tick_interval_seconds: int = 30):
        self.tick_interval = tick_interval_seconds
        self.tasks: Dict[str, ScheduledTask] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._run_log: List[dict] = []     # 最近 200 条运行记录

    # ── 任务注册 ─────────────────────────────────────────────

    def register(self, task: ScheduledTask):
        """注册一个调度任务"""
        with self._lock:
            self.tasks[task.name] = task
        logger.info(f"[M7] 注册任务: {task.name} (每 {task.interval_minutes} 分钟)")

    def register_default_tasks(self, config: Optional[dict] = None):
        """
        注册 MarketRadar 默认任务集。

        config 可覆盖各任务的 enabled / interval_minutes：
          {
            "signal_pipeline": {"enabled": True, "interval_minutes": 30},
            "price_update":    {"enabled": True, "interval_minutes": 10},
            "daily_review":    {"enabled": True, "interval_minutes": 1440},
          }
        """
        cfg = config or {}

        def _c(name, default_interval, **kwargs):
            """从 config 读取覆盖参数"""
            c = cfg.get(name, {})
            return {
                "interval_minutes": c.get("interval_minutes", default_interval),
                "enabled": c.get("enabled", kwargs.get("enabled", True)),
                **{k: v for k, v in kwargs.items() if k not in ("enabled",)},
            }

        self.register(ScheduledTask(
            name="signal_pipeline",
            fn=self._task_signal_pipeline,
            description="M0收集→M1解码→M2存储→M3判断→M4行动，处理 data/incoming/ 新文件",
            run_at_start=True,
            **_c("signal_pipeline", 30),
        ))

        self.register(ScheduledTask(
            name="price_update",
            fn=self._task_price_update,
            description="M9模拟仓价格更新（盘中检查止损止盈）",
            time_window=("09:25", "15:05"),    # 仅 A股交易时段
            **_c("price_update", 10),
        ))

        self.register(ScheduledTask(
            name="daily_review",
            fn=self._task_daily_review,
            description="M6收盘复盘归因→M8写回教训",
            time_window=("15:30", "23:59"),    # 收盘后运行
            **_c("daily_review", 1440),        # 每天一次
        ))

        self.register(ScheduledTask(
            name="news_collect",
            fn=self._task_news_collect,
            description="M0 AKShare新闻拉取（东方财富/财联社）",
            run_at_start=False,
            **_c("news_collect", 15),
        ))

    # ── 启停 ─────────────────────────────────────────────────

    def start(self, background: bool = True):
        """启动调度器"""
        if self._thread and self._thread.is_alive():
            logger.warning("[M7] 调度器已在运行")
            return
        self._stop_event.clear()

        # 处理 run_at_start
        for task in self.tasks.values():
            if task.run_at_start and task.enabled:
                result = task.run()
                self._append_log(task.name, result)

        if background:
            self._thread = threading.Thread(
                target=self._loop, daemon=True, name="M7-Scheduler"
            )
            self._thread.start()
            logger.info(f"[M7] 调度器已启动（后台线程，tick={self.tick_interval}s）")
        else:
            logger.info("[M7] 调度器前台运行（阻塞）")
            self._loop()

    def stop(self):
        """停止调度器"""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("[M7] 调度器已停止")

    def run_now(self, task_name: str) -> dict:
        """手动触发指定任务（忽略调度时间）"""
        task = self.tasks.get(task_name)
        if not task:
            return {"status": "error", "error": f"任务不存在: {task_name}"}
        result = task.run()
        self._append_log(task_name, result)
        return result

    def status(self) -> dict:
        """返回所有任务状态"""
        return {
            "running": self._thread is not None and self._thread.is_alive(),
            "tick_interval_s": self.tick_interval,
            "tasks": {name: t.status_dict() for name, t in self.tasks.items()},
            "recent_runs": self._run_log[-20:],
        }

    # ── 内部调度循环 ─────────────────────────────────────────

    def _loop(self):
        while not self._stop_event.is_set():
            now = datetime.now()
            with self._lock:
                due_tasks = [t for t in self.tasks.values() if t.is_due(now)]
            for task in due_tasks:
                result = task.run()
                self._append_log(task.name, result)
                self._save_state()
            self._stop_event.wait(timeout=self.tick_interval)

    def _append_log(self, task_name: str, result: dict):
        entry = {"task": task_name, "at": datetime.now().isoformat(), **result}
        self._run_log.append(entry)
        if len(self._run_log) > 200:
            self._run_log = self._run_log[-200:]

    def _save_state(self):
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(
                json.dumps(self.status(), ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass

    # ── 任务实现 ─────────────────────────────────────────────

    def _task_signal_pipeline(self, run_id: str = "") -> dict:
        """
        信号管道：扫描 data/incoming/ 新文件 → M1→M2→M3→M4
        """
        incoming_dir = ROOT / "data" / "incoming"
        processed_dir = ROOT / "data" / "processed"
        incoming_dir.mkdir(parents=True, exist_ok=True)
        processed_dir.mkdir(parents=True, exist_ok=True)

        files = sorted(incoming_dir.glob("*.txt"))
        if not files:
            logger.info("[M7/signal_pipeline] 无新文件")
            return {"new_files": 0}

        import sys
        sys.path.insert(0, str(ROOT))
        from core.schemas import Market, SourceType
        from core.llm_client import LLMClient
        from m1_decoder.decoder import SignalDecoder
        from m2_storage.signal_store import SignalStore
        from m3_judgment.judgment_engine import JudgmentEngine
        from m4_action.action_designer import ActionDesigner

        llm_client = LLMClient()
        decoder = SignalDecoder(llm_client=llm_client)
        store = SignalStore()
        engine = JudgmentEngine(llm_client=llm_client)
        designer = ActionDesigner(llm_client=llm_client)

        total_signals = 0
        total_opps = 0
        total_plans = 0
        processed_files = []

        for f in files:
            try:
                raw_text = f.read_text(encoding="utf-8")
                batch_id = f"sched_{run_id}_{f.stem}"

                # M1 解码
                signals = decoder.decode(
                    raw_text=raw_text,
                    source_ref=f.name,
                    source_type=SourceType("news"),
                    batch_id=batch_id,
                )
                if not signals:
                    f.rename(processed_dir / f.name)
                    continue

                # M2 存储
                store.save(signals)
                total_signals += len(signals)

                # M3 判断
                from datetime import timedelta
                hist = store.get_by_time_range(
                    start=datetime.now() - timedelta(days=90),
                    end=datetime.now(),
                    markets=[Market.A_SHARE, Market.HK],
                    min_intensity=5,
                )
                cur_ids = {s.signal_id for s in signals}
                hist = [s for s in hist if s.signal_id not in cur_ids]

                opportunities = engine.judge(signals=signals, historical_signals=hist or None, batch_id=batch_id)
                total_opps += len(opportunities)

                # M4 行动设计
                opp_dir = ROOT / "data" / "opportunities"
                opp_dir.mkdir(parents=True, exist_ok=True)
                for opp in opportunities:
                    plan = designer.design(opp)
                    total_plans += 1
                    # 保存机会 JSON
                    opp_file = opp_dir / f"{opp.opportunity_id}.json"
                    opp_file.write_text(
                        json.dumps(opp.model_dump(mode="json"), ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8",
                    )

                # 处理完成后移动文件
                f.rename(processed_dir / f.name)
                processed_files.append(f.name)
                logger.info(f"[M7/signal_pipeline] {f.name}: {len(signals)}信号 {len(opportunities)}机会")

            except Exception as e:
                logger.error(f"[M7/signal_pipeline] 处理文件失败 {f.name}: {e}")
                continue

        return {
            "processed_files": len(processed_files),
            "total_signals": total_signals,
            "total_opportunities": total_opps,
            "total_plans": total_plans,
            "files": processed_files,
        }

    def _task_price_update(self, run_id: str = "") -> dict:
        """
        M9 模拟仓价格更新：从 AKShare 拉当日最新实时价，
        对所有 OPEN 状态的 PaperPosition 做 tick 更新（检查止损止盈）。
        无网络时降级为日线收盘价（backtest HistoryPriceFeed）。
        """
        import sys
        sys.path.insert(0, str(ROOT))
        from m9_paper_trader.paper_trader import PaperTrader
        from m9_paper_trader.price_feed import AKShareRealtimeFeed

        trader = PaperTrader()
        open_positions = trader.list_open()
        if not open_positions:
            return {"open_positions": 0, "updated": 0, "closed": 0}

        feed = AKShareRealtimeFeed()
        result = trader.update_all_prices(feed)
        updated = result.get("updated", 0)
        closed_ids = result.get("closed", [])

        if closed_ids:
            for pid in closed_ids:
                pos = trader.get(pid)
                if pos:
                    logger.info(
                        f"[M7/price_update] 触发平仓: {pos.instrument} "
                        f"reason={pos.close_reason} pnl={pos.realized_pnl_pct:.2%}"
                    )

        logger.info(f"[M7/price_update] 更新 {updated} 仓，平仓 {len(closed_ids)} 仓")
        return {"open_positions": len(open_positions), "updated": updated, "closed": len(closed_ids)}

    def _task_daily_review(self, run_id: str = "") -> dict:
        """
        M6 收盘复盘：对已平仓的 PaperPosition 做归因分析并写回 M8 知识库。
        PaperPosition 转换为 M6 兴趣的指标字典，记录彝证和教训。
        """
        import sys
        sys.path.insert(0, str(ROOT))
        from m9_paper_trader.paper_trader import PaperTrader
        from m9_paper_trader.evaluator import SignalEvaluator
        from m8_knowledge.knowledge_base import KnowledgeBase

        trader = PaperTrader()
        closed = trader.list_closed()

        if not closed:
            logger.info("[M7/daily_review] 无已平仓持仓，跳过复盘")
            return {"reviewed": 0}

        # 用 SignalEvaluator 做统计分析
        evaluator = SignalEvaluator()
        pos_dicts = []
        for p in closed:
            pos_dicts.append({
                "paper_position_id": p.paper_position_id,
                "instrument": p.instrument,
                "market": p.market,
                "direction": p.direction,
                "signal_type": p.signal_type,
                "signal_intensity": p.signal_intensity,
                "signal_confidence": p.signal_confidence,
                "time_horizon": p.time_horizon,
                "entry_price": p.entry_price,
                "status": p.status,
                "realized_pnl_pct": p.realized_pnl_pct,
                "max_favorable_excursion": p.max_favorable_excursion,
                "max_adverse_excursion": p.max_adverse_excursion,
            })

        eval_report = evaluator.evaluate(pos_dicts, min_closed=max(3, len(pos_dicts) // 2))
        grade = eval_report.get("signal_efficacy_grade", {}).get("grade", "N/A")
        win_rate = eval_report.get("overall", {}).get("win_rate", 0)

        lesson = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "run_id": run_id,
            "total_closed": len(closed),
            "signal_grade": grade,
            "win_rate": win_rate,
            "recommendations": eval_report.get("recommendations", []),
            "by_signal_type": eval_report.get("by_signal_type", {}),
        }

        # 将复盘结果写入 M8
        kb = KnowledgeBase()
        lesson_content = json.dumps(lesson, ensure_ascii=False, indent=2)
        try:
            kb.add_document(
                content=lesson_content,
                metadata={"type": "daily_review", "date": lesson["date"], "grade": grade},
            )
        except Exception as e:
            logger.warning(f"[M7/daily_review] M8 写入失败: {e}")

        logger.info(f"[M7/daily_review] 复盘 {len(closed)} 条，评级 {grade}，胜率 {win_rate:.1f}%")
        return {"reviewed": len(closed), "grade": grade, "win_rate": win_rate}

    def _task_news_collect(self, run_id: str = "") -> dict:
        """
        M0 AKShare 新闻拉取，写入 data/incoming/ 供 signal_pipeline 消费。
        """
        import sys
        sys.path.insert(0, str(ROOT))
        try:
            from m0_collector.providers.akshare_provider import AKShareNewsProvider
            provider = AKShareNewsProvider(source="all", max_items=30)
            items = provider.fetch()
            written = 0
            incoming_dir = ROOT / "data" / "incoming"
            incoming_dir.mkdir(parents=True, exist_ok=True)
            for item in items:
                fname = incoming_dir / item.filename()
                if not fname.exists():
                    fname.write_text(item.content, encoding="utf-8")
                    written += 1
            logger.info(f"[M7/news_collect] 拉取 {len(items)} 条新闻，写入 {written} 个新文件")
            return {"fetched": len(items), "written": written}
        except Exception as e:
            logger.error(f"[M7/news_collect] 失败: {e}")
            return {"error": str(e)}
