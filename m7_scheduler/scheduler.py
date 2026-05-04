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

# 导入 Market 枚举（用于任务注册）
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.schemas import Market

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
        """判断任务是否到执行时间
        
        对于盘前/盘后任务（time_window 起止相同），判断逻辑：
        - 当前时间在窗口内
        - 且今天还未执行过（last_run 不是今天）
        """
        if not self.enabled:
            return False
        
        # 判断时间窗口
        if self.time_window:
            start_h, start_m = map(int, self.time_window[0].split(":"))
            end_h, end_m = map(int, self.time_window[1].split(":"))
            t = now.time()
            from datetime import time as dtime
            
            # 盘前/盘后任务：time_window 起止相同，表示单次触发
            if start_h == end_h and start_m == end_m:
                # 单次触发逻辑：当前时间在目标时间后 5 分钟内，且今天还未执行
                target_time = dtime(start_h, start_m)
                time_diff_minutes = (t.hour * 60 + t.minute) - (target_time.hour * 60 + target_time.minute)
                
                # 当前时间在目标时间后 0-5 分钟内
                if not (0 <= time_diff_minutes <= 5):
                    return False
                
                # 检查今天是否已执行
                if self.last_run is not None:
                    if self.last_run.date() == now.date():
                        return False  # 今天已执行，跳过
                
                return True
            
            # 周期性任务：判断是否在时间窗口内
            if not (dtime(start_h, start_m) <= t <= dtime(end_h, end_m)):
                return False
        
        # 判断间隔
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

        self.register(ScheduledTask(
            name="sentiment_collect",
            fn=self._task_sentiment_collect,
            description="M10情绪采集：恐贪指数+北向资金+热搜+微博 → 写入 SQLite + 注入 M2",
            run_at_start=True,
            time_window=("09:00", "22:00"),   # 交易日+盘后均采集
            **_c("sentiment_collect", 30),      # 每 30 分钟一次
        ))

        # M12 分轨制：A股/港股/美股各自独立扫描
        self.register(ScheduledTask(
            name="m12_a_share_scan",
            fn=lambda run_id: self._task_m12_market_scan(Market.A_SHARE, run_id),
            description="M12 A股轨道：全景价格扫描→异动检测→反向溯源→趋势判断→机会生成",
            run_at_start=False,
            time_window=("09:30", "15:00"),   # A股交易时段
            **_c("m12_a_share_scan", 10),      # 每 10 分钟一次
        ))

        self.register(ScheduledTask(
            name="m12_hk_scan",
            fn=lambda run_id: self._task_m12_market_scan(Market.HK, run_id),
            description="M12 港股轨道：全景价格扫描→异动检测→反向溯源→趋势判断→机会生成",
            run_at_start=False,
            time_window=("09:30", "16:00"),   # 港股交易时段
            **_c("m12_hk_scan", 10),           # 每 10 分钟一次
        ))

        self.register(ScheduledTask(
            name="m12_us_scan",
            fn=lambda run_id: self._task_m12_market_scan(Market.US, run_id),
            description="M12 美股轨道：全景价格扫描→异动检测→反向溯源→趋势判断→机会生成",
            run_at_start=False,
            time_window=("21:30", "04:00"),   # 美股交易时段（跨日）
            **_c("m12_us_scan", 10),           # 每 10 分钟一次
        ))

        # M12 盘前扫描：开盘前30分钟，主动信号收集
        self.register(ScheduledTask(
            name="m12_premarket_a_share",
            fn=lambda run_id: self._task_m12_premarket_scan(Market.A_SHARE, run_id),
            description="M12 A股盘前扫描：隔夜信号收集+情绪面分析→开盘交易依据",
            run_at_start=False,
            time_window=("09:00", "09:00"),   # 开盘前30分钟，每天一次
            **_c("m12_premarket_a_share", 1440),  # 每天一次
        ))

        self.register(ScheduledTask(
            name="m12_premarket_hk",
            fn=lambda run_id: self._task_m12_premarket_scan(Market.HK, run_id),
            description="M12 港股盘前扫描：隔夜信号收集+情绪面分析→开盘交易依据",
            run_at_start=False,
            time_window=("09:00", "09:00"),   # 开盘前30分钟，每天一次
            **_c("m12_premarket_hk", 1440),       # 每天一次
        ))

        self.register(ScheduledTask(
            name="m12_premarket_us",
            fn=lambda run_id: self._task_m12_premarket_scan(Market.US, run_id),
            description="M12 美股盘前扫描：隔夜信号收集+情绪面分析→开盘交易依据",
            run_at_start=False,
            time_window=("21:00", "21:00"),   # 开盘前30分钟，每天一次
            **_c("m12_premarket_us", 1440),       # 每天一次
        ))

        # M12 盘后扫描：全量价格扫描+扩展监控池
        self.register(ScheduledTask(
            name="m12_postmarket_a_share",
            fn=lambda run_id: self._task_m12_postmarket_scan(Market.A_SHARE, run_id),
            description="M12 A股盘后扫描：全量价格扫描→异动发现→扩展监控池",
            run_at_start=False,
            time_window=("15:30", "15:30"),   # 收盘后，每天一次
            **_c("m12_postmarket_a_share", 1440),  # 每天一次
        ))

        self.register(ScheduledTask(
            name="m12_postmarket_hk",
            fn=lambda run_id: self._task_m12_postmarket_scan(Market.HK, run_id),
            description="M12 港股盘后扫描：全量价格扫描→异动发现→扩展监控池",
            run_at_start=False,
            time_window=("16:30", "16:30"),   # 收盘后，每天一次
            **_c("m12_postmarket_hk", 1440),       # 每天一次
        ))

        self.register(ScheduledTask(
            name="m12_postmarket_us",
            fn=lambda run_id: self._task_m12_postmarket_scan(Market.US, run_id),
            description="M12 美股盘后扫描：全量价格扫描→异动发现→扩展监控池",
            run_at_start=False,
            time_window=("05:00", "05:00"),   # 收盘后（北京时间次日凌晨5点），每天一次
            **_c("m12_postmarket_us", 1440),       # 每天一次
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
        from m7_scheduler.trading_calendar import is_trading_day
        from core.schemas import Market  # 在方法内部重新导入，确保可用
        
        while not self._stop_event.is_set():
            now = datetime.now()
            with self._lock:
                due_tasks = []
                for t in self.tasks.values():
                    if not t.is_due(now):
                        continue
                    
                    # 检查是否需要交易日判断（M12 相关任务）
                    if t.name.startswith("m12_"):
                        # 从任务名提取市场
                        if "_a_share" in t.name:
                            market = Market.A_SHARE
                        elif "_hk" in t.name:
                            market = Market.HK
                        elif "_us" in t.name:
                            market = Market.US
                        else:
                            market = None
                        
                        # 如果是交易相关任务，检查是否为交易日
                        if market and not is_trading_day(market, now.date()):
                            logger.info(f"[M7] 跳过任务 {t.name}：今日非交易日")
                            continue
                    
                    due_tasks.append(t)
            
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
            provider = AKShareNewsProvider()
            items = provider.fetch(source="all", limit=30)
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

    def _task_sentiment_collect(self, run_id: str = "") -> dict:
        """
        M10 情绪采集任务：
          1. SentimentProvider 从 AKShare 拉取 4 维数据
          2. 合成恐贪指数（FearGreed 0~100）
          3. 保存快照到 SQLite（data/sentiment/sentiment_history.db）
          4. 生成 SentimentSignal 注入 M2（可供 M3 机会判断参考）

        失败容忍：单个数据源失败不阻断整体，errors 记录到 result。
        """
        import sys
        sys.path.insert(0, str(ROOT))
        try:
            from m10_sentiment.sentiment_engine import SentimentEngine
            batch_id = f"sched_sent_{run_id or datetime.now().strftime('%Y%m%d_%H%M%S')}"
            engine = SentimentEngine()
            signal = engine.run_and_inject(batch_id=batch_id)
            result = {
                "fear_greed": round(signal.fear_greed_index, 1),
                "label": signal.sentiment_label,
                "direction": signal.signal_direction,
                "intensity": signal.intensity_score,
                "batch_id": batch_id,
                "errors": [],
            }
            logger.info(
                f"[M7/sentiment_collect] FG={signal.fear_greed_index:.1f} "
                f"({signal.sentiment_label}) {signal.signal_direction}"
            )
            return result
        except Exception as e:
            logger.error(f"[M7/sentiment_collect] 失败: {e}")
            return {"error": str(e)}

    def _task_m12_market_scan(self, market: "Market", run_id: str = "") -> dict:
        """
        M12 单市场盘中异动扫描任务（分轨制）：
          1. 全景价格扫描（单个市场）
          2. 异动检测（ATR/σ倍数+量比）
          3. 反向溯源（M0→M1→M2）
          4. M3判断（推理引擎）
          5. 趋势判断（EARLY/MIDDLE/LATE）
          6. 机会生成（RetroOpportunity）

        涨停股标记观察池，不生成入场机会。
        """
        import sys
        sys.path.insert(0, str(ROOT))
        try:
            from m12_opportunity_catcher.catcher_engine import OpportunityCatcherEngine
            from core.schemas import Market
            from m9_paper_trader.baostock_feed import BaostockFeed
            from m9_paper_trader.price_feed import YFinanceFeed

            engine = OpportunityCatcherEngine()
            batch_id = f"sched_m12_{market.value}_{run_id or datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 选择价格源
            if market == Market.A_SHARE:
                price_feed = BaostockFeed()
            else:
                price_feed = YFinanceFeed()

            # 执行盘中扫描
            retro_opps = engine.run_intraday_scan(
                market=market,
                price_feed=price_feed,
            )

            # 保存机会到文件（供dashboard读取）
            if retro_opps:
                retro_dir = ROOT / "data" / "retro_opportunities"
                retro_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                retro_file = retro_dir / f"{market.value.lower()}_{timestamp}.json"

                retro_data = []
                for retro in retro_opps:
                    retro_data.append({
                        "instrument": retro.anomaly.instrument,
                        "market": retro.anomaly.market.value,
                        "price_change_pct": retro.anomaly.price_change_pct,
                        "trend_stage": retro.trend.stage.value,
                        "causation_confidence": retro.causation.confidence,
                        "remaining_upside_pct": retro.trend.remaining_upside_pct,
                        "opportunity_id": retro.opportunity.opportunity_id,
                        "priority": retro.opportunity.priority_level.value,
                        "entry_constraint": retro.opportunity.entry_constraint.reason if retro.opportunity.entry_constraint else None,
                    })

                retro_file.write_text(
                    json.dumps(retro_data, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )

                logger.info(
                    f"[M7/m12_{market.value.lower()}_scan] 保存 {len(retro_opps)} 个机会到 {retro_file.name}"
                )

            result = {
                "market": market.value,
                "opportunities": len(retro_opps),
                "instruments": [r.anomaly.instrument for r in retro_opps[:5]],
                "batch_id": batch_id,
            }

            logger.info(
                f"[M7/m12_{market.value.lower()}_scan] 完成：{len(retro_opps)} 个机会"
            )

            return result

        except Exception as e:
            logger.error(f"[M7/m12_{market.value.lower()}_scan] 失败: {e}")
            return {"error": str(e), "market": market.value}

    def _task_m12_premarket_scan(self, market: "Market", run_id: str = "") -> dict:
        """
        M12 盘前扫描任务（开盘前30分钟）：
          1. 检查是否交易日（排除节假日）
          2. 主动信号收集（隔夜新闻、情绪面）
          3. M1解码 → M2存储 → M3判断
          4. 生成开盘交易依据

        目标：为开盘提供交易计划，减少盘中延迟。
        """
        import sys
        sys.path.insert(0, str(ROOT))
        try:
            from m7_scheduler.trading_calendar import is_trading_day
            from core.schemas import Market

            # 检查是否交易日
            if not is_trading_day(market):
                logger.info(f"[M7/m12_premarket_{market.value.lower()}] 今日休市，跳过盘前扫描")
                return {"skipped": True, "reason": "non_trading_day", "market": market.value}

            batch_id = f"premarket_{market.value}_{run_id or datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Step 1: 采集隔夜新闻
            from m0_collector.providers.akshare_news import AkshareNewsProvider
            news_provider = AkshareNewsProvider()
            news_items = news_provider.fetch(limit=50)
            logger.info(f"[M7/m12_premarket_{market.value.lower()}] 采集 {len(news_items)} 条隔夜新闻")

            # Step 2: M1解码 → M2存储
            from m1_decoder.decoder import SignalDecoder
            from m2_storage.signal_store import SignalStore
            from core.llm_client import LLMClient
            from core.schemas import SourceType

            llm_client = LLMClient()
            decoder = SignalDecoder(llm_client=llm_client)
            store = SignalStore()

            all_signals = []
            for item in news_items[:20]:  # 限制处理数量
                try:
                    signals = decoder.decode(
                        raw_text=item.content,
                        source_ref=item.source_url or "premarket",
                        source_type=SourceType.NEWS,
                        batch_id=batch_id,
                    )
                    all_signals.extend(signals)
                except Exception as e:
                    logger.debug(f"[M7/m12_premarket] 解码失败: {e}")
                    continue

            if all_signals:
                store.save(all_signals)
                logger.info(f"[M7/m12_premarket_{market.value.lower()}] 解码 {len(all_signals)} 条信号")

            # Step 3: M3判断
            from m3_judgment.judgment_engine import JudgmentEngine
            engine = JudgmentEngine(llm_client=llm_client)
            opportunities = engine.judge(
                signals=all_signals[:10],  # 限制判断数量
                batch_id=batch_id,
            )

            # 保存盘前机会
            if opportunities:
                premarket_dir = ROOT / "data" / "premarket_opportunities"
                premarket_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                premarket_file = premarket_dir / f"{market.value.lower()}_{timestamp}.json"

                opp_data = []
                for opp in opportunities:
                    opp_data.append({
                        "opportunity_id": opp.opportunity_id,
                        "title": opp.opportunity_title,
                        "priority": opp.priority_level.value,
                        "direction": opp.trade_direction.value,
                        "instruments": opp.target_instruments,
                        "score": opp.opportunity_score.overall_score if opp.opportunity_score else 0,
                    })

                premarket_file.write_text(
                    json.dumps(opp_data, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )

                logger.info(
                    f"[M7/m12_premarket_{market.value.lower()}] 保存 {len(opportunities)} 个盘前机会到 {premarket_file.name}"
                )

            result = {
                "market": market.value,
                "news_count": len(news_items),
                "signals": len(all_signals),
                "opportunities": len(opportunities),
                "batch_id": batch_id,
            }

            logger.info(
                f"[M7/m12_premarket_{market.value.lower()}] 完成：{len(news_items)}新闻 → {len(all_signals)}信号 → {len(opportunities)}机会"
            )

            return result

        except Exception as e:
            logger.error(f"[M7/m12_premarket_{market.value.lower()}] 失败: {e}")
            return {"error": str(e), "market": market.value}

    def _task_m12_postmarket_scan(self, market: "Market", run_id: str = "") -> dict:
        """
        M12 盘后扫描任务（收盘后）：
          1. 检查是否交易日（排除节假日）
          2. 全量价格扫描（覆盖更大范围）
          3. 异动发现 → 反向溯源 → 趋势判断
          4. 扩展监控池（将有价值的未纳入标的加入次日扫描）

        目标：发现被遗漏的异动标的，动态扩展监控范围。
        """
        import sys
        sys.path.insert(0, str(ROOT))
        try:
            from m7_scheduler.trading_calendar import is_trading_day
            from core.schemas import Market
            from m12_opportunity_catcher.catcher_engine import OpportunityCatcherEngine
            from m9_paper_trader.baostock_feed import BaostockFeed
            from m9_paper_trader.price_feed import YFinanceFeed

            # 检查是否交易日
            if not is_trading_day(market):
                logger.info(f"[M7/m12_postmarket_{market.value.lower()}] 今日休市，跳过盘后扫描")
                return {"skipped": True, "reason": "non_trading_day", "market": market.value}

            batch_id = f"postmarket_{market.value}_{run_id or datetime.now().strftime('%Y%m%d_%H%M%S')}"

            engine = OpportunityCatcherEngine()

            # 选择价格源
            if market == Market.A_SHARE:
                price_feed = BaostockFeed()
            else:
                price_feed = YFinanceFeed()

            # 执行盘后全量扫描（stock_list=None表示全市场）
            retro_opps = engine.run_daily_scan(
                market=market,
                price_feed=price_feed,
                stock_list=None,  # 全量扫描
            )

            # 保存盘后机会
            if retro_opps:
                postmarket_dir = ROOT / "data" / "postmarket_opportunities"
                postmarket_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                postmarket_file = postmarket_dir / f"{market.value.lower()}_{timestamp}.json"

                retro_data = []
                for retro in retro_opps:
                    retro_data.append({
                        "instrument": retro.anomaly.instrument,
                        "market": retro.anomaly.market.value,
                        "price_change_pct": retro.anomaly.price_change_pct,
                        "trend_stage": retro.trend.stage.value,
                        "causation_confidence": retro.causation.confidence,
                        "remaining_upside_pct": retro.trend.remaining_upside_pct,
                        "opportunity_id": retro.opportunity.opportunity_id,
                        "priority": retro.opportunity.priority_level.value,
                    })

                postmarket_file.write_text(
                    json.dumps(retro_data, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8",
                )

                logger.info(
                    f"[M7/m12_postmarket_{market.value.lower()}] 保存 {len(retro_opps)} 个盘后机会到 {postmarket_file.name}"
                )

                # TODO: 扩展监控池逻辑（将高价值标的加入次日扫描范围）
                # 可以写入 data/watch_pool/{market}.json

            result = {
                "market": market.value,
                "opportunities": len(retro_opps),
                "instruments": [r.anomaly.instrument for r in retro_opps[:10]],
                "batch_id": batch_id,
            }

            logger.info(
                f"[M7/m12_postmarket_{market.value.lower()}] 完成：{len(retro_opps)} 个盘后机会"
            )

            return result

        except Exception as e:
            logger.error(f"[M7/m12_postmarket_{market.value.lower()}] 失败: {e}")
            return {"error": str(e), "market": market.value}
