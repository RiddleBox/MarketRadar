# 多源新闻采集 + 系统监控实施方案

**创建时间**: 2026-05-07  
**优先级**: P0 - 立即执行

---

## 目标

1. **启用 RSS 新闻源** - 作为 AKShare 的替代和补充
2. **添加系统监控** - 防止核心模块静默失败
3. **验证完整链路** - 确保新闻 → 信号 → 机会流程正常

---

## 第一部分: 启用 RSS 新闻源

### 1.1 添加 RSS 采集任务到调度器

**文件**: `m7_scheduler/scheduler.py`

**位置**: 在 `_task_news_collect` 后添加新方法

```python
def _task_rss_news_collect(self, run_id: str = "") -> dict:
    """
    M0 RSS 新闻拉取，写入 data/incoming/ 供 signal_pipeline 消费。
    
    RSS 源包括:
    - 财联社
    - 东方财富
    - 新浪财经
    - 华尔街见闻
    """
    import sys
    sys.path.insert(0, str(ROOT))
    try:
        from m0_collector.providers.rss import RssProvider
        
        provider = RssProvider(timeout=15, max_per_feed=20)
        items = provider.fetch(limit=50)  # 总共最多50条
        
        written = 0
        incoming_dir = ROOT / "data" / "incoming"
        incoming_dir.mkdir(parents=True, exist_ok=True)
        
        for item in items:
            fname = incoming_dir / item.filename()
            if not fname.exists():
                fname.write_text(item.content, encoding="utf-8")
                written += 1
        
        logger.info(f"[M7/rss_news_collect] 拉取 {len(items)} 条新闻，写入 {written} 个新文件")
        return {
            "fetched": len(items),
            "written": written,
            "status": "success"
        }
        
    except ImportError as e:
        error_msg = f"导入失败: {e} - 请运行: pip install feedparser beautifulsoup4"
        logger.error(f"[M7/rss_news_collect] {error_msg}")
        return {
            "error": error_msg,
            "status": "failed",
            "fetched": 0,
            "written": 0
        }
        
    except Exception as e:
        error_msg = f"执行失败: {e}"
        logger.error(f"[M7/rss_news_collect] {error_msg}", exc_info=True)
        return {
            "error": error_msg,
            "status": "failed",
            "fetched": 0,
            "written": 0
        }
```

### 1.2 注册 RSS 任务

**文件**: `m7_scheduler/scheduler.py`

**位置**: 在 `__init__` 方法中注册任务

```python
# 在 news_collect 任务后添加
self.register_task(
    name="rss_news_collect",
    fn=self._task_rss_news_collect,
    interval_minutes=task_config.get("rss_news_collect", {}).get("interval_minutes", 20),
    enabled=task_config.get("rss_news_collect", {}).get("enabled", True),
    description="M0 RSS新闻拉取（财联社/东方财富/新浪/华尔街见闻）",
    time_window=None,  # 全天运行
)
```

### 1.3 CLI 支持

**文件**: `m7_scheduler/cli.py`

**添加选项**:
```python
@click.option("--rss-interval", default=20, help="rss_news_collect 间隔（分钟）")
```

**在 start 命令中配置**:
```python
task_config.setdefault("rss_news_collect", {})["interval_minutes"] = rss_interval
if no_news:
    task_config.setdefault("rss_news_collect", {})["enabled"] = False
```

---

## 第二部分: 系统监控功能

### 2.1 任务健康检查

**文件**: `m7_scheduler/scheduler.py`

**添加方法**:
```python
def _check_task_health(self, task_name: str, result: dict) -> tuple[bool, str]:
    """
    检查任务是否真正成功
    
    Returns:
        (is_healthy, reason)
    """
    # 检查 error 字段
    if "error" in result:
        return False, f"返回错误: {result['error']}"
    
    # 检查 status 字段
    if "status" in result and result["status"] != "success":
        return False, f"状态异常: {result['status']}"
    
    # 针对特定任务的健康检查
    if task_name in ["news_collect", "rss_news_collect"]:
        # 新闻采集任务应该至少写入1个文件
        written = result.get("written", 0)
        fetched = result.get("fetched", 0)
        
        if fetched == 0:
            return False, "未获取到任何新闻"
        
        if written == 0:
            return False, f"获取了 {fetched} 条新闻但未写入任何文件（可能全部重复）"
    
    elif task_name == "sentiment_collect":
        # 情绪采集应该有有效的恐贪指数
        fear_greed = result.get("fear_greed")
        if fear_greed is None or not (0 <= fear_greed <= 100):
            return False, f"恐贪指数异常: {fear_greed}"
    
    elif task_name in ["m12_a_share_scan", "m12_hk_scan", "m12_us_scan"]:
        # M12 扫描应该至少扫描了一些股票
        scanned = result.get("scanned", 0)
        if scanned == 0:
            return False, "未扫描任何股票"
    
    return True, "OK"
```

### 2.2 任务执行记录增强

**修改 `_run_task` 方法**:
```python
def _run_task(self, task: ScheduledTask, run_id: str):
    """执行单个任务"""
    start = time.time()
    try:
        result = task.fn(run_id=run_id)
        duration = time.time() - start
        
        # 健康检查
        is_healthy, health_reason = self._check_task_health(task.name, result)
        
        if is_healthy:
            status = "ok"
            task.last_result = result
        else:
            status = "warning"
            task.error_count += 1
            logger.warning(
                f"[M7] 任务 {task.name} 健康检查失败: {health_reason} | "
                f"result={result}"
            )
        
        # 记录到历史
        self._record_run(task.name, status, duration, result, health_reason)
        
    except Exception as e:
        duration = time.time() - start
        status = "error"
        task.error_count += 1
        logger.error(f"[M7] 任务 {task.name} 执行失败: {e}", exc_info=True)
        self._record_run(task.name, status, duration, {"error": str(e)}, str(e))
```

### 2.3 监控数据持久化

**添加字段到 scheduler_state.json**:
```json
{
  "running": true,
  "tasks": {
    "news_collect": {
      "health_status": "warning",
      "health_reason": "未获取到任何新闻",
      "consecutive_failures": 3,
      "last_success_time": "2026-05-07T10:00:00"
    }
  },
  "recent_runs": [
    {
      "task": "news_collect",
      "status": "warning",
      "health_reason": "未获取到任何新闻",
      "at": "2026-05-07T15:30:00",
      "duration_s": 2.5,
      "result": {"fetched": 0, "written": 0}
    }
  ]
}
```

### 2.4 Dashboard 监控页面

**文件**: `dashboard_v2/pages/7_📊_监控.py` (新建)

**功能**:
1. **任务健康状态**
   - 绿色: 正常运行
   - 黄色: 有警告（如未写入文件）
   - 红色: 执行失败

2. **关键指标**
   - 新闻采集成功率
   - 信号生成数量趋势
   - 机会发现数量趋势
   - 任务执行时长

3. **告警列表**
   - 连续失败的任务
   - 长时间未成功的任务
   - 异常的任务执行时长

---

## 第三部分: 验证完整链路

### 3.1 端到端测试脚本

**文件**: `test_news_signal_pipeline.py` (新建)

```python
"""
测试完整的新闻信号处理链路

流程:
1. RSS 采集新闻 → data/incoming/
2. M1 解码新闻 → 提取关键信息
3. M1.5 隐式推理 → 推断隐含信息
4. M2 存储信号 → signal_store.db
5. M3 判断机会 → opportunities/
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

def test_rss_collection():
    """测试 RSS 新闻采集"""
    print("=" * 60)
    print("步骤 1: 测试 RSS 新闻采集")
    print("=" * 60)
    
    from m0_collector.providers.rss import RssProvider
    
    provider = RssProvider(timeout=15, max_per_feed=5)
    articles = provider.fetch(limit=10)
    
    print(f"✅ 采集到 {len(articles)} 条新闻")
    
    if articles:
        print(f"\n示例新闻:")
        for i, article in enumerate(articles[:3], 1):
            print(f"\n{i}. {article.title}")
            print(f"   来源: {article.source_name}")
            print(f"   内容: {article.content[:100]}...")
    
    return len(articles) > 0

def test_signal_generation():
    """测试信号生成"""
    print("\n" + "=" * 60)
    print("步骤 2: 测试信号生成")
    print("=" * 60)
    
    from m2_storage.signal_store import SignalStore
    from collections import Counter
    
    store = SignalStore()
    
    # 获取最近1小时的信号
    signals_before = store.get_by_time_range(
        start=datetime.now() - timedelta(hours=1),
        end=datetime.now()
    )
    
    print(f"处理前: {len(signals_before)} 条信号")
    
    # 触发信号处理
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "m7_scheduler.cli", "run", "signal_pipeline"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300
    )
    
    if result.returncode != 0:
        print(f"❌ 信号处理失败: {result.stderr}")
        return False
    
    # 获取处理后的信号
    signals_after = store.get_by_time_range(
        start=datetime.now() - timedelta(hours=1),
        end=datetime.now()
    )
    
    new_signals = len(signals_after) - len(signals_before)
    print(f"处理后: {len(signals_after)} 条信号 (+{new_signals})")
    
    # 统计信号类型
    signal_types = Counter([str(s.signal_type) for s in signals_after])
    print(f"\n信号类型分布:")
    for sig_type, count in signal_types.most_common():
        print(f"  {sig_type}: {count}")
    
    return new_signals > 0

def test_opportunity_generation():
    """测试机会生成"""
    print("\n" + "=" * 60)
    print("步骤 3: 测试机会生成")
    print("=" * 60)
    
    # 运行机会判断诊断
    import subprocess
    result = subprocess.run(
        [sys.executable, "test_signal_judgment.py"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60
    )
    
    print(result.stdout)
    
    if result.returncode != 0:
        print(f"❌ 机会判断失败: {result.stderr}")
        return False
    
    # 检查是否生成了机会
    opp_dir = ROOT / "data" / "opportunities"
    opp_files = list(opp_dir.glob("test_opportunity_*.json"))
    
    print(f"\n生成的测试机会文件: {len(opp_files)}")
    
    return len(opp_files) > 0

def main():
    print("MarketRadar 新闻信号处理链路测试")
    print("=" * 60)
    print()
    
    results = {}
    
    # 测试 RSS 采集
    results["rss_collection"] = test_rss_collection()
    
    # 测试信号生成
    results["signal_generation"] = test_signal_generation()
    
    # 测试机会生成
    results["opportunity_generation"] = test_opportunity_generation()
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n🎉 所有测试通过！新闻信号处理链路正常工作。")
    else:
        print("\n⚠️ 部分测试失败，请检查日志。")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
```

---

## 实施步骤

### 立即执行 (30分钟)

1. **安装依赖**
   ```bash
   pip install feedparser beautifulsoup4
   ```

2. **添加 RSS 采集任务到调度器**
   - 修改 `m7_scheduler/scheduler.py`
   - 添加 `_task_rss_news_collect` 方法
   - 注册任务

3. **测试 RSS 采集**
   ```bash
   python -m m7_scheduler.cli run rss_news_collect
   ls data/incoming/
   ```

4. **启动调度器**
   ```bash
   python -m m7_scheduler.cli stop
   python -m m7_scheduler.cli start --background
   ```

### 短期优化 (1-2小时)

5. **添加任务健康检查**
   - 实现 `_check_task_health` 方法
   - 修改 `_run_task` 方法
   - 增强状态记录

6. **创建端到端测试脚本**
   - 创建 `test_news_signal_pipeline.py`
   - 运行测试验证完整链路

7. **创建监控 Dashboard 页面**
   - 创建 `dashboard_v2/pages/7_📊_监控.py`
   - 显示任务健康状态
   - 显示关键指标

---

## 预期结果

### 成功标准

1. **RSS 新闻采集正常**
   - `data/incoming/` 目录每20分钟有新文件
   - 文件内容为财经新闻

2. **信号类型多样化**
   - 不再只有 `SENTIMENT` 类型
   - 出现 `EVENT_DRIVEN` 等其他类型

3. **机会能够生成**
   - `test_signal_judgment.py` 能生成机会
   - `data/opportunities/` 目录有新文件

4. **监控可见**
   - Dashboard 显示任务健康状态
   - 能识别失败的任务

---

**文档结束**
