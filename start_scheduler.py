import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['TERM'] = 'xterm'
os.environ['FINNHUB_API_KEY'] = 'd7lhlbhr01qm7o0bsj30d7lhlbhr01qm7o0bsj3g'

import logging
log_file = os.path.join('data', 'logs', 'scheduler_daemon.log')
os.makedirs(os.path.dirname(log_file), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(log_file, encoding='utf-8')]
)
logger = logging.getLogger(__name__)

from m7_scheduler.scheduler import Scheduler

while True:
    try:
        logger.info("[start_scheduler] 启动调度器...")
        s = Scheduler(tick_interval_seconds=30)
        s.register_default_tasks()
        s.start(background=False)
    except KeyboardInterrupt:
        logger.info("[start_scheduler] 收到中断信号，退出")
        break
    except Exception as e:
        logger.error(f"[start_scheduler] 调度器异常退出: {e}，30秒后重启")
        time.sleep(30)
        continue
    break
