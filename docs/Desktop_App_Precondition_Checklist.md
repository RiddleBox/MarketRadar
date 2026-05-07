# MarketRadar 桌面应用 - 前置条件检查清单

**检查日期**: 待填写  
**检查人**: 待填写  
**状态**: 🔴 未开始 / 🟡 进行中 / 🟢 已完成

---

## 检查目的

在开始桌面应用开发前，需要确保现有功能稳定可靠，避免在不稳定的基础上构建新功能。

---

## 1. 调度器功能检查

### 1.1 启动功能

**测试步骤**:
```bash
# 1. 确保调度器未运行
python -m m7_scheduler.cli stop

# 2. 启动调度器
python -m m7_scheduler.cli start --background

# 3. 等待 3-5 秒

# 4. 检查状态
python -m m7_scheduler.cli status
```

**预期结果**:
- ✅ 启动命令无错误输出
- ✅ 状态显示 "Scheduler is running"
- ✅ PID 文件存在: `data/scheduler.pid`
- ✅ 日志文件正常写入: `data/logs/scheduler.log`

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
```

---

### 1.2 停止功能

**测试步骤**:
```bash
# 1. 停止调度器
python -m m7_scheduler.cli stop

# 2. 检查状态
python -m m7_scheduler.cli status
```

**预期结果**:
- ✅ 停止命令无错误输出
- ✅ 状态显示 "Scheduler is not running"
- ✅ PID 文件被删除
- ✅ 进程确实已终止

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
```

---

### 1.3 重启功能

**测试步骤**:
```bash
# 1. 启动调度器
python -m m7_scheduler.cli start --background

# 2. 记录 PID
python -m m7_scheduler.cli status

# 3. 重启
python -m m7_scheduler.cli stop
python -m m7_scheduler.cli start --background

# 4. 检查新 PID
python -m m7_scheduler.cli status
```

**预期结果**:
- ✅ 重启后 PID 改变
- ✅ 调度器正常运行
- ✅ 任务状态保持

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
```

---

### 1.4 稳定性测试

**测试步骤**:
```bash
# 1. 启动调度器
python -m m7_scheduler.cli start --background

# 2. 运行 10 分钟

# 3. 检查日志是否有错误
tail -n 100 data/logs/scheduler.log

# 4. 检查状态
python -m m7_scheduler.cli status
```

**预期结果**:
- ✅ 运行 10 分钟无崩溃
- ✅ 日志无 ERROR 级别错误
- ✅ 内存占用稳定
- ✅ CPU 占用正常

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
```

---

## 2. M12 扫描任务检查

### 2.1 A股扫描

**测试步骤**:
```bash
# 1. 确保调度器运行
python -m m7_scheduler.cli status

# 2. 手动触发 A股扫描
python -m m7_scheduler.cli run m12_a_share_scan

# 3. 等待完成（可能需要 5-10 分钟）

# 4. 检查结果
ls -lh data/opportunities/
```

**预期结果**:
- ✅ 扫描命令正常执行
- ✅ 无 Python 异常
- ✅ 生成机会文件: `opportunities_YYYYMMDD_HHMMSS.json`
- ✅ 机会文件格式正确（JSON 可解析）
- ✅ 日志记录完整

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
扫描耗时: _____ 秒
发现机会数: _____ 个
```

---

### 2.2 港股扫描

**测试步骤**:
```bash
python -m m7_scheduler.cli run m12_hk_scan
```

**预期结果**:
- ✅ 扫描正常完成
- ✅ 生成机会文件

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
[ ] 跳过 - 原因: 无港股数据源
```

---

### 2.3 美股扫描

**测试步骤**:
```bash
python -m m7_scheduler.cli run m12_us_scan
```

**预期结果**:
- ✅ 扫描正常完成
- ✅ 生成机会文件

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
[ ] 跳过 - 原因: 无美股数据源
```

---

### 2.4 扫描日志检查

**测试步骤**:
```bash
# 查看最近的扫描日志
grep "m12.*scan" data/logs/scheduler.log | tail -n 50
```

**预期结果**:
- ✅ 日志包含扫描开始信息
- ✅ 日志包含扫描进度信息
- ✅ 日志包含扫描完成信息
- ✅ 日志包含发现的机会数量
- ✅ 无 ERROR 或 CRITICAL 级别错误

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
```

---

## 3. OpenD 集成检查

### 3.1 OpenD 管理器导入

**测试步骤**:
```python
# 在 Python REPL 中执行
from integrations.opend_manager import get_opend_manager

opend_mgr = get_opend_manager()
print(opend_mgr)
```

**预期结果**:
- ✅ 导入无错误
- ✅ 对象创建成功

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
```

---

### 3.2 OpenD 状态查询

**测试步骤**:
```python
from integrations.opend_manager import get_opend_manager

opend_mgr = get_opend_manager()
status = opend_mgr.status()
print(status)
```

**预期结果**:
- ✅ 返回字典包含 `running`, `pid`, `host`, `port` 字段
- ✅ `running` 为布尔值
- ✅ 如果运行中，`pid` 为整数

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
状态: _______________
```

---

### 3.3 OpenD 启动功能

**测试步骤**:
```python
from integrations.opend_manager import get_opend_manager

opend_mgr = get_opend_manager()

# 确保已停止
opend_mgr.stop()

# 启动
result = opend_mgr.start(wait=True)
print(result)

# 检查状态
status = opend_mgr.status()
print(status)
```

**预期结果**:
- ✅ `result["success"]` 为 `True`
- ✅ 状态显示 `running: True`
- ✅ PID 文件存在: `logs/opend.pid`
- ✅ OpenD 进程确实在运行

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
[ ] 跳过 - 原因: 未配置 OpenD 路径
```

---

### 3.4 OpenD 停止功能

**测试步骤**:
```python
from integrations.opend_manager import get_opend_manager

opend_mgr = get_opend_manager()
result = opend_mgr.stop()
print(result)

status = opend_mgr.status()
print(status)
```

**预期结果**:
- ✅ `result["success"]` 为 `True`
- ✅ 状态显示 `running: False`
- ✅ PID 文件被删除
- ✅ OpenD 进程确实已终止

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
```

---

## 4. 数据持久化检查

### 4.1 持仓数据

**测试步骤**:
```python
from m9_paper_trader.paper_trader import PaperTrader

trader = PaperTrader()
positions = trader.list_open()
print(f"持仓数: {len(positions)}")

if positions:
    pos = positions[0]
    print(f"标的: {pos.instrument}")
    print(f"止损价: {pos.stop_loss_price}")
    print(f"止盈价: {pos.take_profit_price}")
```

**预期结果**:
- ✅ 导入无错误
- ✅ 可以加载持仓数据
- ✅ 持仓对象包含 `stop_loss_price` 和 `take_profit_price` 字段
- ✅ 数据类型正确

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
持仓数: _____
```

---

### 4.2 机会数据

**测试步骤**:
```python
import json
from pathlib import Path

opp_dir = Path("data/opportunities")
opp_files = list(opp_dir.glob("opportunities_*.json"))
print(f"机会文件数: {len(opp_files)}")

if opp_files:
    latest = sorted(opp_files)[-1]
    data = json.loads(latest.read_text(encoding="utf-8"))
    print(f"最新文件: {latest.name}")
    print(f"机会数: {len(data) if isinstance(data, list) else 1}")
    
    opp = data[0] if isinstance(data, list) else data
    print(f"字段: {list(opp.keys())}")
```

**预期结果**:
- ✅ 机会文件存在
- ✅ JSON 格式正确
- ✅ 包含必要字段: `opportunity_id`, `instrument`, `opportunity_title`

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
机会文件数: _____
```

---

### 4.3 信号数据

**测试步骤**:
```python
from m2_storage.signal_store import SignalStore
from datetime import datetime, timedelta

store = SignalStore()
stats = store.stats()
print(f"信号总数: {stats['total']}")

# 获取最近 7 天的信号
signals = store.get_by_time_range(
    start=datetime.now() - timedelta(days=7),
    end=datetime.now()
)
print(f"最近 7 天信号数: {len(signals)}")
```

**预期结果**:
- ✅ 导入无错误
- ✅ 可以查询信号统计
- ✅ 可以按时间范围查询

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
信号总数: _____
```

---

## 5. Dashboard V2 检查

### 5.1 Dashboard 启动

**测试步骤**:
```bash
streamlit run dashboard_v2/Home.py
```

**预期结果**:
- ✅ 无 Python 错误
- ✅ 浏览器自动打开 http://localhost:8501
- ✅ 主页正常显示
- ✅ 系统总览数据正确

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
```

---

### 5.2 持仓页面

**测试步骤**:
1. 打开 Dashboard
2. 点击左侧 "💼 持仓" 页面
3. 检查持仓列表
4. 展开持仓详情

**预期结果**:
- ✅ 持仓列表正常显示
- ✅ 止损价、止盈价正确显示
- ✅ 距离百分比计算正确
- ✅ 触发预警正常工作

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
```

---

### 5.3 机会页面

**测试步骤**:
1. 点击 "🎯 机会" 页面
2. 检查机会列表

**预期结果**:
- ✅ 机会列表正常显示
- ✅ 筛选功能正常
- ✅ 详情展开正常

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
```

---

### 5.4 调度器控制

**测试步骤**:
1. 在 Dashboard 主页
2. 点击 "🚀 启动调度器"
3. 等待 3-5 秒，刷新页面
4. 点击 "⏸️ 停止调度器"

**预期结果**:
- ✅ 启动按钮正常工作
- ✅ 状态指示灯更新
- ✅ 停止按钮正常工作

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
```

---

## 6. 性能检查

### 6.1 内存占用

**测试步骤**:
```bash
# 启动调度器
python -m m7_scheduler.cli start --background

# 等待 5 分钟

# 检查内存占用 (Windows)
tasklist /FI "IMAGENAME eq python.exe" /FO TABLE

# 或 (Linux)
ps aux | grep python
```

**预期结果**:
- ✅ 内存占用 < 500MB
- ✅ 内存占用稳定，无持续增长

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
内存占用: _____ MB
```

---

### 6.2 CPU 占用

**测试步骤**:
观察调度器空闲时的 CPU 占用

**预期结果**:
- ✅ 空闲时 CPU < 5%
- ✅ 扫描时 CPU < 50%

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
空闲 CPU: _____ %
扫描 CPU: _____ %
```

---

### 6.3 响应速度

**测试步骤**:
1. 启动 Dashboard
2. 切换不同页面
3. 刷新数据

**预期结果**:
- ✅ 页面切换 < 1 秒
- ✅ 数据刷新 < 2 秒
- ✅ 无明显卡顿

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
```

---

## 7. 错误处理检查

### 7.1 调度器异常停止

**测试步骤**:
```bash
# 1. 启动调度器
python -m m7_scheduler.cli start --background

# 2. 获取 PID
python -m m7_scheduler.cli status

# 3. 强制杀死进程 (Windows)
taskkill /PID <pid> /F

# 4. 检查状态
python -m m7_scheduler.cli status

# 5. 尝试重新启动
python -m m7_scheduler.cli start --background
```

**预期结果**:
- ✅ 状态检查能识别进程已死
- ✅ 可以正常重新启动
- ✅ 无残留 PID 文件问题

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
```

---

### 7.2 数据文件损坏

**测试步骤**:
```bash
# 1. 备份数据文件
cp data/portfolio.db data/portfolio.db.bak

# 2. 损坏文件
echo "corrupted" > data/portfolio.db

# 3. 尝试加载持仓
python -c "from m9_paper_trader.paper_trader import PaperTrader; PaperTrader().list_open()"

# 4. 恢复文件
mv data/portfolio.db.bak data/portfolio.db
```

**预期结果**:
- ✅ 有明确的错误提示
- ✅ 不会崩溃
- ✅ 恢复后正常工作

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
```

---

## 8. 配置文件检查

### 8.1 OpenD 配置

**测试步骤**:
```bash
cat config/opend_config.yaml
```

**预期结果**:
- ✅ 文件存在
- ✅ YAML 格式正确
- ✅ 包含必要字段: `executable`, `host`, `port`
- ✅ 路径配置正确

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
```

---

### 8.2 数据源配置

**测试步骤**:
```bash
cat config/data_sources.yaml
```

**预期结果**:
- ✅ 文件存在
- ✅ YAML 格式正确
- ✅ 包含主数据源和备用数据源配置

**实际结果**:
```
[ ] 通过
[ ] 失败 - 原因: _______________
```

---

## 检查总结

### 通过情况统计

- 调度器功能: ___/4 通过
- M12 扫描任务: ___/4 通过
- OpenD 集成: ___/4 通过
- 数据持久化: ___/3 通过
- Dashboard V2: ___/4 通过
- 性能检查: ___/3 通过
- 错误处理: ___/2 通过
- 配置文件: ___/2 通过

**总计**: ___/26 通过

### 关键问题列表

1. _______________
2. _______________
3. _______________

### 是否可以开始开发？

```
[ ] ✅ 是 - 所有关键功能正常
[ ] ⚠️ 有条件 - 需要先修复以下问题: _______________
[ ] ❌ 否 - 存在严重问题，需要先解决
```

### 下一步行动

1. _______________
2. _______________
3. _______________

---

**检查完成日期**: _______________  
**签名**: _______________
