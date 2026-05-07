# 新闻信号缺失问题 - 根本原因分析

**发现时间**: 2026-05-07  
**严重程度**: 🔴 P0 - 核心功能失效

---

## 问题现象

1. **信号剖面页面只显示情绪信号**
   - 最近7天128条信号，全部是 `SignalType.SENTIMENT`
   - 来源全部是 `SourceType.SOCIAL_MEDIA`
   - **没有任何新闻推理信号**

2. **调度器显示新闻采集任务正常**
   - `news_collect` 任务已启用
   - 运行7次，状态显示 "ok"
   - 但实际上没有产生任何输出

3. **incoming 目录为空**
   - `data/incoming/` 目录存在但完全为空
   - 说明新闻采集任务从未成功写入文件

---

## 根本原因

### 导入路径错误

**文件**: `m7_scheduler/scheduler.py:668`

**错误代码**:
```python
from m0_collector.providers.akshare_provider import AKShareNewsProvider
```

**问题**:
1. 文件名应该是 `akshare_news.py`，不是 `akshare_provider.py`
2. 类名应该是 `AkshareNewsProvider`（小写k），不是 `AKShareNewsProvider`

**实际文件结构**:
```
m0_collector/providers/
├── akshare_news.py          # ← 实际文件名
│   └── class AkshareNewsProvider  # ← 实际类名
├── akshare_provider.py      # ← 这是另一个文件（股票数据）
└── ...
```

### 错误被静默吞掉

**问题代码**:
```python
def _task_news_collect(self, run_id: str = "") -> dict:
    try:
        from m0_collector.providers.akshare_provider import AKShareNewsProvider
        # ... 采集逻辑
        return {"fetched": len(items), "written": written}
    except Exception as e:
        logger.error(f"[M7/news_collect] 失败: {e}")
        return {"error": str(e)}  # ← 返回错误但任务状态仍为 "ok"
```

**问题**:
- `ImportError` 被 catch 住
- 只记录到日志，但任务状态仍然是 "ok"
- 调度器认为任务成功，继续定期执行
- 用户看不到任何异常提示

---

## 影响范围

### 直接影响

1. **新闻信号完全缺失**
   - M0 新闻采集失效
   - M1 解码器无输入
   - M1.5 隐式推理无法运行
   - M3 判断引擎只能处理情绪信号

2. **机会发现能力严重受限**
   - 只能依赖 M12 价格扫描发现机会
   - 无法从新闻事件中发现机会
   - 错过政策、财报、行业变化等重要信号

3. **系统设计初衷未实现**
   - 系统设计的核心是"新闻 → 显式推理 → 隐式推理 → 机会判断"
   - 目前只有"情绪快照 → 机会判断"这一条简化路径
   - 大部分模块（M0/M1/M1.5）实际上没有运行

### 间接影响

1. **无法验证 M1/M1.5 功能**
   - 显式解码器未被测试
   - 隐式推理器未被测试
   - 可能存在其他隐藏 bug

2. **机会判断阈值可能不准确**
   - 当前阈值可能是针对新闻信号设计的
   - 情绪信号的评分体系可能不同
   - 导致无法生成机会

---

## 修复方案

### 方案 A: 修复导入路径（立即）

**文件**: `m7_scheduler/scheduler.py`

**修改**:
```python
# 第 668 行
# 原代码:
from m0_collector.providers.akshare_provider import AKShareNewsProvider

# 修改为:
from m0_collector.providers.akshare_news import AkshareNewsProvider

# 第 669 行
# 原代码:
provider = AKShareNewsProvider()

# 修改为:
provider = AkshareNewsProvider()
```

### 方案 B: 改进错误处理（重要）

**问题**: 当前错误被静默吞掉，用户无感知

**改进**:
```python
def _task_news_collect(self, run_id: str = "") -> dict:
    try:
        from m0_collector.providers.akshare_news import AkshareNewsProvider
        provider = AkshareNewsProvider()
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
        return {"fetched": len(items), "written": written, "status": "success"}
        
    except ImportError as e:
        error_msg = f"导入失败: {e}"
        logger.error(f"[M7/news_collect] {error_msg}")
        return {"error": error_msg, "status": "failed", "fetched": 0, "written": 0}
        
    except Exception as e:
        error_msg = f"执行失败: {e}"
        logger.error(f"[M7/news_collect] {error_msg}", exc_info=True)
        return {"error": error_msg, "status": "failed", "fetched": 0, "written": 0}
```

**改进点**:
1. 区分 `ImportError` 和其他异常
2. 返回明确的 `status` 字段
3. 记录完整的异常堆栈 (`exc_info=True`)

### 方案 C: 添加任务健康检查（长期）

**目标**: 让调度器能识别"假成功"的任务

**实现**:
```python
def _check_task_health(self, task_name: str, result: dict) -> bool:
    """检查任务是否真正成功"""
    
    # 如果返回结果包含 error 字段，认为失败
    if "error" in result:
        return False
    
    # 如果返回结果包含 status 字段，检查状态
    if "status" in result and result["status"] != "success":
        return False
    
    # 针对特定任务的健康检查
    if task_name == "news_collect":
        # 新闻采集任务应该至少写入1个文件
        if result.get("written", 0) == 0:
            logger.warning(f"[M7] {task_name} 未写入任何文件，可能存在问题")
            return False
    
    return True
```

---

## 验证步骤

### 1. 修复代码

```bash
# 编辑 m7_scheduler/scheduler.py
# 修改第 668-669 行的导入路径
```

### 2. 重启调度器

```bash
python -m m7_scheduler.cli stop
python -m m7_scheduler.cli start --background
```

### 3. 手动触发新闻采集

```bash
python -m m7_scheduler.cli run news_collect
```

### 4. 检查结果

```bash
# 检查 incoming 目录
ls -lh data/incoming/

# 应该看到新闻文件，格式如: news_20260507_153022_abc123.txt

# 检查日志
grep "news_collect" data/logs/scheduler.log | tail -5
```

### 5. 触发信号处理

```bash
# 处理新闻文件
python -m m7_scheduler.cli run signal_pipeline

# 检查信号数据库
python -c "
from m2_storage.signal_store import SignalStore
from datetime import datetime, timedelta
from collections import Counter

store = SignalStore()
signals = store.get_by_time_range(
    start=datetime.now() - timedelta(hours=1),
    end=datetime.now()
)

signal_types = Counter([str(s.signal_type) for s in signals])
print('最近1小时信号类型:')
for sig_type, count in signal_types.items():
    print(f'  {sig_type}: {count}')
"
```

**预期结果**:
- `data/incoming/` 目录有新闻文件
- 信号数据库中出现 `SignalType.EVENT_DRIVEN` 或其他非情绪类信号
- 日志显示 M1 解码和 M1.5 推理执行

---

## 后续行动

### 立即（今天）

1. **修复导入路径** (10分钟)
2. **重启调度器并验证** (10分钟)
3. **观察1小时，确认新闻信号正常生成** (1小时)

### 短期（明天）

4. **改进错误处理** (30分钟)
5. **添加任务健康检查** (1小时)
6. **重新运行机会判断诊断** (30分钟)
   - 现在有新闻信号后，重新测试 `test_signal_judgment.py`
   - 查看是否能生成机会

### 中期（本周）

7. **验证完整信号处理链路**
   - M0 采集 → M1 解码 → M1.5 推理 → M2 存储 → M3 判断 → M4 行动
   - 确保每个环节都正常工作

8. **调整判断阈值**
   - 基于新闻信号的评分分布
   - 重新校准 `judgment_config.yaml`

---

## 经验教训

### 1. 错误处理不应该吞掉异常

**问题**:
```python
except Exception as e:
    logger.error(f"失败: {e}")
    return {"error": str(e)}  # ← 任务状态仍为 "ok"
```

**改进**:
- 返回明确的失败状态
- 区分不同类型的异常
- 记录完整的异常堆栈

### 2. 任务状态应该反映真实情况

**问题**:
- 调度器只看任务是否抛出异常
- 不检查任务的实际输出
- 导致"假成功"无法被发现

**改进**:
- 添加任务健康检查
- 验证任务的实际输出
- 对关键任务设置告警

### 3. 应该有端到端的集成测试

**问题**:
- 各个模块单独测试可能通过
- 但集成后可能因为配置错误而失败
- 缺少端到端的验证

**改进**:
- 添加集成测试脚本
- 定期运行完整流程验证
- 监控关键指标（如信号类型分布）

---

## 总结

### 核心问题

**新闻采集任务因导入路径错误而一直失败，但错误被静默吞掉，导致系统核心功能（新闻推理）完全失效。**

### 影响

- ❌ M0/M1/M1.5 模块实际未运行
- ❌ 只有情绪信号，没有新闻信号
- ❌ 无法从新闻事件中发现机会
- ❌ 系统设计初衷未实现

### 修复优先级

1. **P0 - 立即**: 修复导入路径
2. **P0 - 今天**: 验证新闻信号生成
3. **P1 - 明天**: 改进错误处理
4. **P1 - 本周**: 验证完整链路

### 下一步

**立即修复导入路径，重启调度器，观察新闻信号是否正常生成。**

---

**文档结束**
