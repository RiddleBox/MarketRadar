# Phase 3.5: 架构修正计划

> **创建时间**: 2026-04-27  
> **优先级**: P0 (必须在Phase 4之前完成)  
> **目标**: 修正Phase 3的架构捷径，补全M3/M4流程

---

## 🔍 问题诊断

### 当前架构问题

**Phase 3实现的捷径**：
```
M0 (新闻采集)
  ↓
M1.5 (隐性信号推理)
  ↓
SignalToPaperTrader (直接转换) ← 问题在这里！
  ↓
M9 (模拟盘)
```

**违反的设计原则**：

1. **跳过M3机会判断**
   - `SignalToPaperTrader` 只做置信度过滤（>0.65）
   - 没有M3的推理型判断（"这是不是真的机会？"）
   - 没有因果链验证
   - 没有历史案例检索

2. **跳过M4行动设计**
   - 止损止盈是硬编码的（短期±5%/10%，中期±8%/15%，长期±12%/25%）
   - 仓位计算简化（0.65-0.75→2%, 0.75-0.85→3%, 0.85+→5%）
   - 没有Kelly公式
   - 没有风险预算管理
   - 没有分阶段行动计划

3. **数据流断裂**
   - M1.5信号没有存储到M2
   - M3/M4无法访问历史隐性信号
   - 无法做跨时间的信号聚合判断

---

## 🎯 正确架构

### 应该是这样的

```
M0 (新闻采集)
  ↓
M1.5 (隐性信号推理)
  ↓
M2 (存储隐性信号) ← 补充：需要扩展M2支持ImplicitSignal
  ↓
M3 (机会判断) ← 补充：需要适配ImplicitSignal输入
  ↓  输出: List[OpportunityObject]
  │
  ├─→ 空列表 → 不交易（信号不构成机会）
  │
  └─→ 有机会 → M4 (行动设计)
                ↓  输出: ActionPlan
               M9 (模拟盘执行)
```

### 关键改进点

1. **M2扩展** - 存储隐性信号
2. **M3适配** - 接受ImplicitSignal作为输入
3. **M4复用** - 使用现有的ActionDesigner
4. **数据追溯** - 完整的 Signal → Opportunity → Plan → Position 链路

---

## 📋 实施计划

### 阶段1: M2扩展 - 存储隐性信号 (1天)

#### 1.1 扩展SignalStore

**文件**: `m2_storage/signal_store.py`

**新增功能**:
```python
class SignalStore:
    def save_implicit_signal(self, signal: ImplicitSignal) -> bool:
        """存储隐性信号"""
        
    def query_implicit_signals(
        self,
        start_time: datetime,
        end_time: datetime,
        industry_sector: Optional[str] = None,
        signal_type: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> List[ImplicitSignal]:
        """查询隐性信号"""
```

**存储格式**:
```json
// data/implicit_signals/YYYY-MM-DD.json
{
  "signal_id": "imp_abc123",
  "signal_type": "policy_driven",
  "source_event": "中沙签署新能源合作",
  "industry_sector": "光伏",
  "opportunity_description": "沙特订单预期带动光伏出口",
  "target_symbols": ["601012.SH", "600438.SH"],
  "prior_confidence": 0.72,
  "posterior_confidence": 0.75,
  "reasoning_chain": {...},
  "expected_impact_timeframe": "mid_term",
  "generated_at": "2026-04-27T10:00:00"
}
```

**验收标准**:
- [ ] 隐性信号可以存储和查询
- [ ] 支持按时间/板块/类型/置信度过滤
- [ ] 与现有MarketSignal存储隔离（不同文件）

---

### 阶段2: M3适配 - 接受隐性信号 (2天)

#### 2.1 创建ImplicitSignal → MarketSignal转换器

**文件**: `m3_judgment/implicit_signal_adapter.py` (新建)

**职责**: 将ImplicitSignal转换为M3可以理解的MarketSignal格式

```python
class ImplicitSignalAdapter:
    """隐性信号适配器"""
    
    @staticmethod
    def to_market_signal(implicit_signal: ImplicitSignal) -> MarketSignal:
        """
        将ImplicitSignal转换为MarketSignal
        
        映射规则:
        - signal_type → signal_type
        - opportunity_description → description
        - target_symbols → affected_instruments
        - prior_confidence → confidence
        - reasoning_chain → 提取为tags
        """
        return MarketSignal(
            signal_id=implicit_signal.signal_id,
            signal_type=implicit_signal.signal_type,
            description=implicit_signal.opportunity_description,
            direction=Direction.BULLISH,  # 隐性信号通常是利好
            affected_instruments=implicit_signal.target_symbols,
            confidence=implicit_signal.prior_confidence,
            event_time=implicit_signal.generated_at,
            tags=[
                f"sector:{implicit_signal.industry_sector}",
                f"timeframe:{implicit_signal.expected_impact_timeframe}",
                f"source:{implicit_signal.source_event[:50]}",
            ],
            metadata={
                "reasoning_chain": implicit_signal.reasoning_chain.dict(),
                "posterior_confidence": implicit_signal.posterior_confidence,
            }
        )
```

#### 2.2 扩展JudgmentEngine

**文件**: `m3_judgment/judgment_engine.py`

**新增方法**:
```python
class JudgmentEngine:
    def judge_implicit_signals(
        self,
        implicit_signals: List[ImplicitSignal],
        batch_id: Optional[str] = None,
    ) -> List[OpportunityObject]:
        """
        判断隐性信号是否构成机会
        
        流程:
        1. 转换为MarketSignal格式
        2. 从M2查询相关历史信号（同板块、同类型）
        3. 调用现有的judge()方法
        4. 返回OpportunityObject列表
        """
        # 1. 转换格式
        market_signals = [
            ImplicitSignalAdapter.to_market_signal(sig)
            for sig in implicit_signals
        ]
        
        # 2. 查询历史信号（增强上下文）
        historical_signals = []
        for sig in implicit_signals:
            hist = self.signal_store.query_implicit_signals(
                start_time=datetime.now() - timedelta(days=90),
                end_time=datetime.now(),
                industry_sector=sig.industry_sector,
                signal_type=sig.signal_type,
                min_confidence=0.6,
            )
            # 转换为MarketSignal
            historical_signals.extend([
                ImplicitSignalAdapter.to_market_signal(h) for h in hist
            ])
        
        # 3. 调用现有判断逻辑
        return self.judge(
            signals=market_signals,
            historical_signals=historical_signals,
            batch_id=batch_id,
        )
```

**验收标准**:
- [ ] ImplicitSignal可以被M3处理
- [ ] M3能够查询历史隐性信号作为上下文
- [ ] 输出OpportunityObject包含原始signal_id追溯

---

### 阶段3: 重构live_signal_monitor.py (1天)

#### 3.1 补全完整流程

**文件**: `live_signal_monitor.py`

**修改前**:
```python
# 2. 处理新闻，生成信号
signals, signal_objects = self.process_news(news_items)

# 3. 执行模拟交易（如果启用）
if self.signal_trader and signal_objects:
    trade_results = self.signal_trader.process_signals_batch(
        signal_objects, current_prices
    )
```

**修改后**:
```python
# 2. 处理新闻，生成隐性信号 (M1.5)
signals_data, implicit_signals = self.process_news(news_items)

# 3. 存储隐性信号到M2
for sig in implicit_signals:
    self.signal_store.save_implicit_signal(sig)

# 4. M3机会判断
opportunities = self.judgment_engine.judge_implicit_signals(
    implicit_signals=implicit_signals,
    batch_id=f"live_{date}",
)

if not opportunities:
    print("[M3判断] 当前信号不构成交易机会，跳过")
    return

print(f"[M3判断] 识别到 {len(opportunities)} 个投资机会")

# 5. M4行动设计
action_plans = []
for opp in opportunities:
    plan = self.action_designer.design(opp)
    action_plans.append(plan)
    print(f"[M4设计] {opp.opportunity_id}: {plan.plan_summary[:50]}...")

# 6. M9模拟盘执行（如果启用）
if self.paper_trader and action_plans:
    for plan in action_plans:
        # 获取价格
        current_prices = self._get_prices_for_plan(plan)
        
        # 执行交易
        positions = self.paper_trader.open_from_plan(
            plan=plan,
            signal_ids=plan.metadata.get("source_signal_ids", []),
            opportunity_id=plan.opportunity_id,
            entry_price=current_prices.get(plan.primary_instruments[0], 0),
        )
        
        print(f"[M9执行] 创建 {len(positions)} 个持仓")
```

#### 3.2 初始化组件

**修改 `__init__` 方法**:
```python
def __init__(self, output_dir: str = "live_validation", enable_paper_trading: bool = False):
    # ... 现有初始化 ...
    
    # 新增: M2 SignalStore
    from m2_storage.signal_store import SignalStore
    self.signal_store = SignalStore()
    
    # 新增: M3 JudgmentEngine
    from m3_judgment.judgment_engine import JudgmentEngine
    self.judgment_engine = JudgmentEngine(
        llm_client=self.llm_client,
        signal_store=self.signal_store,
    )
    
    # 新增: M4 ActionDesigner
    from m4_action.action_designer import ActionDesigner
    self.action_designer = ActionDesigner(
        llm_client=self.llm_client,
    )
    
    # 修改: M9不再使用SignalToPaperTrader
    if enable_paper_trading:
        from m9_paper_trader import PaperTrader
        self.paper_trader = PaperTrader(initial_capital=1_000_000)
    else:
        self.paper_trader = None
```

**验收标准**:
- [ ] 完整的M0→M1.5→M2→M3→M4→M9流程
- [ ] M3能够过滤掉低质量信号
- [ ] M4生成的ActionPlan包含动态止损止盈
- [ ] 保留完整的追溯链路

---

### 阶段4: 废弃SignalToPaperTrader (0.5天)

#### 4.1 标记为废弃

**文件**: `signal_to_paper_trader.py`

**添加废弃警告**:
```python
"""
⚠️ DEPRECATED - 此模块已废弃

原因: Phase 3的架构捷径，跳过了M3/M4流程

替代方案:
  M1.5 → M2 → M3 → M4 → M9 (完整流程)

保留原因: 
  - 用于对比测试（捷径 vs 完整流程）
  - Phase 3的历史记录

请勿在新代码中使用此模块。
"""
import warnings

warnings.warn(
    "SignalToPaperTrader is deprecated. Use M3 JudgmentEngine + M4 ActionDesigner instead.",
    DeprecationWarning,
    stacklevel=2,
)
```

#### 4.2 保留用于对比测试

**用途**: 在Phase 3.5完成后，可以对比两种方式的效果：

| 维度 | 捷径方式 (Phase 3) | 完整流程 (Phase 3.5) |
|------|-------------------|---------------------|
| 信号过滤 | 置信度>0.65 | M3推理型判断 |
| 止损止盈 | 硬编码 | M4动态计算 |
| 仓位管理 | 简单映射 | Kelly公式/风险预算 |
| 历史上下文 | 无 | M2历史信号检索 |

---

## 📊 对比验证方案

### 并行运行7天

**方案A (捷径)**: 
```bash
python live_signal_monitor.py --mode=shortcut --enable-trading
```

**方案B (完整)**:
```bash
python live_signal_monitor.py --mode=full --enable-trading
```

### 对比指标

| 指标 | 方案A | 方案B | 预期差异 |
|------|-------|-------|---------|
| 信号数量 | 基准 | -30% | M3过滤掉低质量信号 |
| 交易次数 | 基准 | -40% | M3判断更严格 |
| 胜率 | 基准 | +15% | 信号质量提升 |
| 平均收益 | 基准 | +20% | M4动态止损止盈 |
| 最大回撤 | 基准 | -25% | M4风险管理 |
| 夏普比率 | 基准 | +30% | 整体风控提升 |

---

## 🗓️ 时间表

| 阶段 | 任务 | 预计工期 | 依赖 |
|------|------|----------|------|
| 1 | M2扩展 - 存储隐性信号 | 1天 | - |
| 2 | M3适配 - 接受隐性信号 | 2天 | 阶段1 |
| 3 | 重构live_signal_monitor | 1天 | 阶段2 |
| 4 | 废弃SignalToPaperTrader | 0.5天 | 阶段3 |
| - | **总计** | **4.5天** | - |

---

## ✅ 验收标准

### 功能验收

- [ ] M2可以存储和查询隐性信号
- [ ] M3可以处理隐性信号并输出OpportunityObject
- [ ] M4可以为OpportunityObject设计ActionPlan
- [ ] live_signal_monitor完整执行M0→M1.5→M2→M3→M4→M9流程
- [ ] 保留完整的追溯链路（Signal ID → Opportunity ID → Plan ID → Position ID）

### 质量验收

- [ ] M3能够过滤掉至少30%的低质量信号
- [ ] M4生成的止损止盈参数不是硬编码
- [ ] M4使用Kelly公式或风险预算计算仓位
- [ ] 所有模块有单元测试覆盖

### 性能验收

- [ ] 完整流程耗时 < 5秒/信号
- [ ] M3判断准确率 > 70%（通过7天回测验证）
- [ ] M4设计的ActionPlan夏普比率 > 捷径方式

---

## 🚀 后续工作

完成Phase 3.5后，才能开始Phase 4 (M12交易引擎)：

```
Phase 3.5 (架构修正)
  ↓
Phase 4 (M12交易引擎)
  ├─ M12.1 实时行情监控
  ├─ M12.2 动态止盈止损
  ├─ M12.3 择时优化 (集成M10/M11)
  └─ M12.4 仓位动态调整
```

**关键**: M12必须建立在正确的M3/M4基础上，否则会继承Phase 3的架构债务。

---

## 📝 风险与缓解

### 风险1: M3判断过于严格，导致交易机会过少

**缓解**: 
- 调整M3的置信度阈值
- 保留"观察级"机会（不交易但记录）
- 对比捷径方式的信号覆盖率

### 风险2: M4设计的止损过紧，频繁止损

**缓解**:
- 回测验证M4参数
- 引入"止损缓冲区"（价格在止损附近震荡时不立即触发）
- 对比捷径方式的止损表现

### 风险3: 完整流程耗时过长，影响实时性

**缓解**:
- M3/M4使用更快的LLM模型（Haiku）
- 批量处理信号
- 异步执行非关键路径

---

## 📚 参考文档

- [Architecture_Realignment_20260424.md](Architecture_Realignment_20260424.md) - 架构对齐报告
- [Module_Design_Audit_20260424.md](Module_Design_Audit_20260424.md) - 模块设计核对
- [Phase3_M9_Integration_Report.md](Phase3_M9_Integration_Report.md) - Phase 3实现报告
- [m3_judgment/PRINCIPLES.md](../m3_judgment/PRINCIPLES.md) - M3设计原则
- [m4_action/PRINCIPLES.md](../m4_action/PRINCIPLES.md) - M4设计原则
