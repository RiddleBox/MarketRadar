# M12 信号扫描架构重新思考

**日期**: 2026-05-05  
**问题**: 用户提出两个关键质疑

---

## 一、用户的两个质疑

### 质疑1: 职责过重的判断标准

**问题**:
> 为什么说 signal_pipeline 职责过重，而放到 M12 的盘中信号主动扫描就不会？

**我的错误**:
- ❌ 我说 signal_pipeline 职责过重是因为它做了 M0→M1→M2→M3→M4→M9
- ❌ 但我提议的 M12 盘中信号扫描也要做 M0→M1→M2→M3
- ❌ 这两者的职责范围其实差不多，我的批评标准不一致

**真相**:
```python
# signal_pipeline 的实际职责
_task_signal_pipeline():
    读取 data/incoming/ 文件
    → M1解码
    → M2存储
    → M3判断（包含历史信号查询）
    → M4行动设计
    → 保存到 data/opportunities/
    → 移动文件到 data/processed/

# 我提议的 M12 盘中信号扫描
_task_m12_intraday_signal_scan():
    M0拉取新闻（实时）
    → M1解码
    → M2存储
    → M3判断
    → 保存到 data/m12_scans/
```

**对比**:
- signal_pipeline: M1→M2→M3→M4（4个模块）
- M12盘中信号扫描: M0→M1→M2→M3（4个模块）
- **职责范围相当，我的批评不成立**

---

### 质疑2: 显式/隐式信号扫描的完整性

**问题**:
> 主动扫描是一个复杂的逻辑，既包括显式信号扫描流程和隐式信号扫描流程，用 M12 的盘中主动信号扫描会覆盖之前的完整信号扫描链条吗？是否分开会更好？

**关键发现**:
- ✅ 系统中存在 `m1_5_implicit_reasoner` 模块（隐式推理器）
- ✅ 系统中存在 `m3_judgment/implicit_signal_adapter.py`（隐式信号适配器）
- ✅ 显式/隐式信号是架构的核心设计（见 Architecture_Realignment_20260424.md）

**我的疏忽**:
- ❌ 我完全忽略了显式/隐式信号的区分
- ❌ 我提议的 M12 盘中信号扫描只考虑了显式信号（新闻→解码）
- ❌ 我没有检查 signal_pipeline 是否包含隐式推理逻辑

---

## 二、重新审视 signal_pipeline

### 当前 signal_pipeline 的完整流程

```python
# scheduler.py:470-554
def _task_signal_pipeline(self, run_id: str = "") -> dict:
    """
    M0收集→M1解码→M2存储→M3判断→M4行动，处理 data/incoming/ 新文件
    """
    # 1. 读取 data/incoming/ 新文件
    files = list(incoming_dir.glob("*.txt"))
    
    for f in files:
        # 2. M1 解码（显式信号）
        signals = decoder.decode(
            raw_text=raw_text,
            source_ref=f.name,
            source_type=SourceType("news"),
            batch_id=batch_id,
        )
        
        # 3. M2 存储
        store.save(signals)
        
        # 4. M3 判断（包含历史信号查询）
        hist = store.get_by_time_range(
            start=datetime.now() - timedelta(days=90),
            end=datetime.now(),
            markets=[Market.A_SHARE, Market.HK],
            min_intensity=5,
        )
        opportunities = engine.judge(
            signals=signals, 
            historical_signals=hist or None,  # ⚠️ 关键：传入历史信号
            batch_id=batch_id
        )
        
        # 5. M4 行动设计
        for opp in opportunities:
            plan = designer.design(opp)
            # 保存到 data/opportunities/
        
        # 6. 移动文件到 data/processed/
        f.rename(processed_dir / f.name)
```

### 关键发现

**signal_pipeline 的特殊之处**:
1. ✅ 查询90天历史信号（`get_by_time_range`）
2. ✅ 将历史信号传入 M3 判断（`historical_signals=hist`）
3. ✅ 这可能触发隐式推理逻辑（M1.5）
4. ✅ 完成 M4 行动设计（生成交易计划）

**M12 盘前扫描的对比**:
```python
# scheduler.py:794-893
def _task_m12_premarket_scan(self, market: "Market", run_id: str = "") -> dict:
    # 1. M0 采集隔夜新闻
    news_items = news_provider.fetch(limit=50)
    
    # 2. M1 解码
    signals = decoder.decode(...)
    
    # 3. M2 存储
    store.save(all_signals)
    
    # 4. M3 判断
    opportunities = engine.judge(
        signals=all_signals[:10],  # ⚠️ 只传入当前信号
        batch_id=batch_id,         # ⚠️ 没有传入历史信号
    )
    
    # 5. 保存到 data/premarket_opportunities/
    # ⚠️ 没有 M4 行动设计
```

**差异**:
- signal_pipeline: 传入历史信号 → 可能触发隐式推理
- M12 盘前扫描: 不传入历史信号 → 只做显式信号判断

---

## 三、显式/隐式信号架构

### 需要检查的关键问题

1. **M3 判断引擎是否包含隐式推理？**
   - 检查 `m3_judgment/judgment_engine.py`
   - 检查是否调用 `m1_5_implicit_reasoner`

2. **隐式信号适配器的作用？**
   - 检查 `m3_judgment/implicit_signal_adapter.py`
   - 确认如何将隐式推理结果转换为信号

3. **signal_pipeline 是否是唯一触发隐式推理的入口？**
   - 如果是，那么它的职责就不是"过重"，而是"必要"
   - 如果不是，那么需要确认其他入口在哪里

---

## 四、重新评估架构设计

### 假设1: signal_pipeline 包含完整的显式+隐式推理

**如果成立**:
```
signal_pipeline 的职责：
  1. 显式信号解码（M1）
  2. 历史信号查询（M2）
  3. 隐式信号推理（M1.5，通过M3触发）
  4. 机会判断（M3）
  5. 行动设计（M4）
```

**那么**:
- ✅ signal_pipeline 的职责是合理的（完整的信号处理链）
- ✅ 不应该拆分或简化
- ❌ 我之前的批评是错误的

**问题在于**:
- ❌ 间隔过长（30分钟）
- ❌ 无时间窗口（全天运行）
- ❌ 与 M12 架构不协调

### 假设2: M12 盘前/盘中扫描只做显式信号

**如果成立**:
```
M12 扫描的职责：
  1. 快速机会发现（显式信号）
  2. 不做深度推理（隐式信号）
  3. 不做行动设计（M4）
```

**那么**:
- ✅ M12 和 signal_pipeline 是互补的，不是重复的
- ✅ M12: 快速响应（10分钟）+ 显式信号
- ✅ signal_pipeline: 深度分析（30分钟）+ 显式+隐式信号

---

## 五、正确的架构理解

### 可能的正确架构

```
盘中信号处理的两条轨道：

轨道1: 快速机会发现（M12）
  - 频率: 每10分钟
  - 范围: 显式信号（新闻→解码→判断）
  - 目标: 快速响应突发事件
  - 输出: OpportunityObject（机会对象）
  - 不做: 隐式推理、行动设计

轨道2: 深度信号分析（signal_pipeline）
  - 频率: 每30分钟
  - 范围: 显式+隐式信号（历史关联、趋势推理）
  - 目标: 发现隐藏机会、生成交易计划
  - 输出: OpportunityObject + ActionPlan
  - 包含: M1.5隐式推理、M4行动设计
```

**如果这是正确的架构**:
- ✅ 两条轨道各有分工，不冲突
- ✅ M12 负责"快"，signal_pipeline 负责"深"
- ✅ 不需要新增盘中信号扫描（已经有了）

**需要优化的地方**:
- ⚠️ signal_pipeline 应该添加时间窗口（仅交易时段）
- ⚠️ M12 盘前扫描应该考虑是否需要隐式推理
- ⚠️ 两条轨道的协同机制（如何避免重复）

---

## 六、待确认的问题

### 必须回答的问题

1. **M3 判断引擎是否包含隐式推理逻辑？**
   - 如果包含：何时触发？（传入历史信号时？）
   - 如果不包含：M1.5 模块如何被调用？

2. **signal_pipeline 是否是唯一触发隐式推理的入口？**
   - 如果是：那么它的职责是合理的
   - 如果不是：其他入口在哪里？

3. **M12 盘前/盘中扫描是否应该包含隐式推理？**
   - 如果应该：需要修改 M12 的实现
   - 如果不应该：需要明确 M12 和 signal_pipeline 的分工

4. **显式/隐式信号的架构设计文档在哪里？**
   - 检查 `docs/Architecture_Realignment_20260424.md`
   - 检查 `docs/M1.5_vs_M3_Analysis.md`
   - 检查 `docs/Reasoning_vs_Judgment_Analysis.md`

---

## 七、下一步行动

### 立即行动

1. ✅ 读取 `m3_judgment/judgment_engine.py`，确认是否包含隐式推理
2. ✅ 读取 `m1_5_implicit_reasoner/inferencer.py`，确认如何被调用
3. ✅ 读取 `docs/Architecture_Realignment_20260424.md`，理解显式/隐式架构
4. ✅ 读取 `docs/M1.5_vs_M3_Analysis.md`，理解 M1.5 和 M3 的关系

### 暂停重构

**在确认以下问题之前，不应该开始重构**:
- ❌ 不确定 signal_pipeline 的职责是否合理
- ❌ 不确定 M12 和 signal_pipeline 的关系
- ❌ 不确定是否需要新增盘中信号扫描
- ❌ 不确定显式/隐式信号的架构设计

---

## 八、我的错误总结

### 错误1: 标准不一致
- 批评 signal_pipeline 职责过重（M1→M2→M3→M4）
- 但提议的 M12 盘中扫描也要做 M0→M1→M2→M3
- 职责范围相当，批评不成立

### 错误2: 忽略隐式推理
- 完全忽略了 M1.5 隐式推理模块
- 没有检查 signal_pipeline 是否包含隐式推理
- 没有理解显式/隐式信号的架构设计

### 错误3: 过早提出方案
- 在没有充分理解现有架构的情况下
- 就提出了"新增盘中信号扫描"的方案
- 可能导致重复建设或破坏现有设计

---

## 九、用户的洞察

**用户的两个问题都击中了要害**:

1. **职责过重的判断标准不一致**
   - 揭示了我的逻辑矛盾
   - 迫使我重新审视 signal_pipeline 的合理性

2. **显式/隐式信号的完整性**
   - 揭示了我对架构的理解不足
   - 提醒我检查完整的信号处理链条

**这两个问题说明**:
- ✅ 用户对系统架构有深刻理解
- ✅ 我需要更谨慎地分析现有设计
- ✅ 在提出方案之前，必须先理解现状

---

## 十、结论

### 当前状态

**暂停重构，先回答以下问题**:
1. M3 是否包含隐式推理？如何触发？
2. signal_pipeline 和 M12 的分工是什么？
3. 是否需要新增盘中信号扫描？

**下一步**:
- 读取架构文档和关键代码
- 理解显式/隐式信号的设计
- 重新评估重构方案的必要性和范围
