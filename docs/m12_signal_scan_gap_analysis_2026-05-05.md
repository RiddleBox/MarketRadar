# M12 盘中主动信号扫描缺失分析

**日期**: 2026-05-05  
**问题**: 盘中除了价格异动驱动的扫描外，是否有主动的信号扫描（M0→M1→M2→M3）？

---

## 一、当前架构现状

### 1. 已有的扫描任务

#### ✅ 盘前主动信号扫描（已实现）
```python
# scheduler.py:296-300
name="m12_premarket_a_share"
description="M12 A股盘前扫描：隔夜信号收集+情绪面分析→开盘交易依据"
time_window=("09:00", "09:25")  # 开盘前30分钟
```

**流程**:
```
隔夜新闻 → M0采集 → M1解码 → M2存储 → M3判断 → OpportunityObject
```

#### ✅ 盘中价格异动扫描（已实现）
```python
# scheduler.py:268-293
name="m12_a_share_scan"  # A股轨道
name="m12_hk_scan"       # 港股轨道
name="m12_us_scan"       # 美股轨道
time_window=("09:30", "15:00")  # 交易时段
interval_minutes=10              # 每10分钟
```

**流程**:
```
价格异动 → 异动检测 → 反向溯源 → 趋势判断 → RetroOpportunity
```

#### ✅ 独立的新闻采集任务（已实现）
```python
# scheduler.py:251-256
name="news_collect"
description="M0 AKShare新闻拉取（东方财富/财联社）"
interval_minutes=15  # 每15分钟
time_window=None     # ⚠️ 全天运行，无时间窗口限制
```

**流程**:
```
M0拉取新闻 → 写入 data/incoming/ → 等待 signal_pipeline 消费
```

#### ✅ 信号处理管道（已实现）
```python
# scheduler.py:226-232
name="signal_pipeline"
description="M0收集→M1解码→M2存储→M3判断→M4行动，处理 data/incoming/ 新文件"
interval_minutes=30  # 每30分钟
time_window=None     # ⚠️ 全天运行，无时间窗口限制
```

**流程**:
```
读取 data/incoming/ → M1解码 → M2存储 → M3判断 → M4行动
```

---

## 二、问题诊断

### ❌ 缺失：盘中主动信号扫描的**实时性**

#### 问题1: 新闻采集与信号处理的时间差

**当前流程**:
```
09:30 - news_collect 拉取新闻 → 写入 data/incoming/
10:00 - signal_pipeline 处理（30分钟后）
```

**问题**:
- `news_collect` 每15分钟拉取一次新闻
- `signal_pipeline` 每30分钟处理一次
- **最坏情况延迟**: 30分钟（新闻刚写入，错过上一轮处理）
- **平均延迟**: 15分钟

**影响**:
- 盘中突发新闻（如：重大合同、业绩预告、监管公告）无法及时响应
- 错过最佳入场时机（新闻发布后5-10分钟内）

#### 问题2: 信号处理管道的职责混乱

**当前 `signal_pipeline` 的问题**:
```python
# scheduler.py:550-620
def _task_signal_pipeline(self, run_id: str = "") -> dict:
    """
    M0收集→M1解码→M2存储→M3判断→M4行动，处理 data/incoming/ 新文件
    """
    # 1. 读取 data/incoming/ 新文件
    # 2. M1解码
    # 3. M2存储
    # 4. M3判断
    # 5. M4行动设计
    # 6. M9执行（如果是模拟盘）
```

**问题**:
- ❌ 职责过重：从M0到M9全流程
- ❌ 无时间窗口限制：全天运行（包括休市时段）
- ❌ 间隔过长：30分钟（盘中需要更高频）
- ❌ 与M12盘中扫描**完全独立**，无协同

#### 问题3: 盘中主动信号扫描的缺失

**用户期望的架构**:
```
盘中应该有两条平行轨道：

轨道1（价格驱动）:
  价格异动 → M12异动检测 → 反向溯源 → RetroOpportunity
  ✅ 已实现（m12_a_share_scan）

轨道2（信号驱动）:
  实时新闻 → M0采集 → M1解码 → M2存储 → M3判断 → OpportunityObject
  ❌ 缺失（或实时性不足）
```

**当前架构的问题**:
- `news_collect` + `signal_pipeline` 理论上实现了轨道2
- 但**时间延迟过大**（15-30分钟）
- 且**无时间窗口限制**（休市时段也在运行，浪费资源）

---

## 三、架构对比

### 当前架构（有缺陷）

```
盘前（09:00-09:25）:
  ✅ m12_premarket_scan: 隔夜新闻 → M0→M1→M2→M3 → OpportunityObject

盘中（09:30-15:00）:
  ✅ m12_a_share_scan: 价格异动 → M12 → RetroOpportunity（每10分钟）
  ⚠️ news_collect: 拉取新闻 → data/incoming/（每15分钟）
  ⚠️ signal_pipeline: 处理新闻 → M1→M2→M3→M4→M9（每30分钟）
  
  问题：
  - news_collect 和 signal_pipeline 时间不同步
  - signal_pipeline 间隔过长（30分钟）
  - 无法及时响应盘中突发新闻
```

### 理想架构（应该实现）

```
盘前（09:00-09:25）:
  ✅ m12_premarket_scan: 隔夜新闻 → M0→M1→M2→M3 → OpportunityObject

盘中（09:30-15:00）:
  ✅ m12_a_share_scan: 价格异动 → M12 → RetroOpportunity（每10分钟）
  
  ❌ 缺失：m12_intraday_signal_scan（应该新增）
     实时新闻 → M0→M1→M2→M3 → OpportunityObject（每10-15分钟）
     
  或者：
  ✅ 优化现有的 news_collect + signal_pipeline
     - 缩短 signal_pipeline 间隔（30分钟 → 10分钟）
     - 添加时间窗口限制（仅交易时段运行）
     - 与 M12 盘中扫描协同
```

---

## 四、根本问题

### 设计理念不一致

**M12 盘前/盘中扫描**（新设计）:
- ✅ 职责清晰：只负责机会发现
- ✅ 时间窗口明确：仅交易时段运行
- ✅ 间隔合理：10分钟（盘中）
- ✅ 分轨制：A股/港股/美股独立

**signal_pipeline**（旧设计）:
- ❌ 职责过重：M0→M1→M2→M3→M4→M9全流程
- ❌ 无时间窗口：全天运行
- ❌ 间隔过长：30分钟
- ❌ 无市场区分：所有市场混在一起

### 历史遗留问题

**推测**:
1. `signal_pipeline` 是早期设计，负责完整的信号处理流程
2. 后来引入 M12 模块，专注于价格异动扫描
3. 但**忘记了**将盘中主动信号扫描也纳入 M12 体系
4. 导致两套系统并存，职责不清

---

## 五、解决方案

### 方案A: 新增 M12 盘中主动信号扫描任务（推荐）

**优点**:
- ✅ 与现有 M12 架构一致
- ✅ 职责清晰（只负责机会发现）
- ✅ 时间窗口明确（仅交易时段）
- ✅ 可与价格异动扫描协同

**实现**:
```python
# 新增任务
self.register(ScheduledTask(
    name="m12_intraday_signal_scan",
    fn=self._task_m12_intraday_signal_scan,
    description="M12 盘中主动信号扫描：实时新闻→M0→M1→M2→M3→OpportunityObject",
    time_window=("09:30", "15:00"),  # 仅交易时段
    interval_minutes=10,              # 与价格异动扫描同频
))

def _task_m12_intraday_signal_scan(self, run_id: str = "") -> dict:
    """
    M12 盘中主动信号扫描：
      1. M0拉取最新新闻（最近10分钟）
      2. M1解码 → M2存储
      3. M3判断 → OpportunityObject
      4. 持久化到 data/m12_scans/
    
    与价格异动扫描平行运行，互为补充。
    """
    # 实现逻辑
    pass
```

### 方案B: 优化现有 signal_pipeline（次选）

**优点**:
- ✅ 无需新增任务
- ✅ 复用现有代码

**缺点**:
- ❌ 职责仍然过重（M0→M9全流程）
- ❌ 与 M12 架构不一致

**实现**:
```python
# 修改现有任务
self.register(ScheduledTask(
    name="signal_pipeline",
    fn=self._task_signal_pipeline,
    description="M0收集→M1解码→M2存储→M3判断→M4行动",
    time_window=("09:30", "15:00"),  # 添加时间窗口
    interval_minutes=10,              # 缩短间隔（30→10）
))
```

---

## 六、推荐方案

### ✅ 方案A: 新增 M12 盘中主动信号扫描

**理由**:
1. 与现有 M12 架构一致（盘前/盘中价格/盘中信号/盘后）
2. 职责清晰（只负责机会发现，不负责执行）
3. 可与价格异动扫描协同（两条平行轨道）
4. 时间窗口明确（仅交易时段，节省资源）

**实施步骤**:
1. 新增 `_task_m12_intraday_signal_scan` 方法
2. 复用 M12 盘前扫描的逻辑（M0→M1→M2→M3）
3. 使用统一的持久化层（`M12ScanLogger`）
4. 与价格异动扫描使用相同的间隔（10分钟）

**与重构方案的关系**:
- ✅ 可以在重构时一并实现
- ✅ 使用统一的持久化层
- ✅ 完善 M12 模块的功能完整性

---

## 七、结论

### 问题确认

**用户的质疑是正确的**:
- ✅ 盘中确实应该有两条平行轨道（价格驱动 + 信号驱动）
- ❌ 当前架构中，信号驱动轨道的实时性不足（15-30分钟延迟）
- ❌ `signal_pipeline` 职责过重，与 M12 架构不一致

### 建议

**在 M12 重构时一并解决**:
1. ✅ 新增 M12 盘中主动信号扫描任务
2. ✅ 使用统一的持久化层
3. ✅ 与价格异动扫描协同（10分钟间隔）
4. ⚠️ 保留 `signal_pipeline` 作为兜底（处理历史数据）

**预计增加工作量**: 30-40分钟  
**总重构时间**: 2.5小时（原2小时 + 新增0.5小时）

---

## 八、待确认问题

1. **是否在本次重构中一并实现盘中主动信号扫描？**
2. **signal_pipeline 是否保留？**（建议保留但降低优先级）
3. **盘中信号扫描的间隔是否与价格异动扫描一致？**（建议10分钟）
4. **是否需要为港股/美股也添加盘中信号扫描？**（建议是）
