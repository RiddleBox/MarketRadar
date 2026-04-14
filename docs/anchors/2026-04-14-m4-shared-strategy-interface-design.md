# 2026-04-14 M4 共享策略接口层（最小设计稿）

## 背景

当前仓库中已经存在两类与“行动设计/策略”相关的结构：

1. **M4 行动设计层**
   - 文件：`m4_action/action_designer.py`
   - 职责：`OpportunityObject -> ActionPlan`
   - 当前形态：更接近单一默认风格的计划生成器

2. **backtest 策略原型层**
   - 文件：`backtest/strategies.py`
   - 文件：`backtest/strategy_backtest.py`
   - 职责：定义可参数化策略，并在验证链中比较策略表现
   - 当前形态：主要存在于验证链，不直接进入主链

此前已确认：
- 短期不要求 M4 立刻支持多策略正式输出
- 短期允许策略继续留在 backtest 做验证
- 但长期如果策略永远只存在于 backtest，主链与验证链会持续割裂

因此需要一个折中层：

> **共享策略接口层**

用于让主链和验证链逐步共享“策略语义”，但暂不强迫主链立刻多策略化。

---

## 设计目标

### 目标 1：统一策略语义，而不是立刻统一执行逻辑

当前阶段的主要目标不是让 M4 一次输出多个计划，
而是先定义一个**可共享的策略描述对象**，使：

- M4 可以知道“当前默认行动计划对应的是哪类策略语义”
- backtest 可以继续使用策略参数做验证
- 未来 M5 / M6 / M9 / sim 可以感知 strategy identity

### 目标 2：保持 M4 主链最小侵入

当前主链优先级是稳态，不应因为策略层抽象而引入大量行为变化。

因此共享接口层的第一步应满足：
- 不改变 `ActionDesigner.design()` 的默认调用方式
- 不要求 M4 立刻输出多个 `ActionPlan`
- 不要求 backtest 立即完全重写

### 目标 3：为后续验证反哺主链留口

未来如果 backtest / ablation 证明某类策略在特定机会类型上更优，
共享策略接口层应允许系统逐步做到：
- 给 plan 打 strategy label
- 对 plan 做 strategy-aware 复盘
- 在 sim 中比较不同 strategy plan

---

## 非目标（当前明确不做）

### 非目标 1：当前不把 M4 改成多策略总控

不做：
- 同一机会返回多个正式 `ActionPlan`
- 在主链运行时进行策略选择器/策略排名
- 让 M4 负责策略最优解搜索

### 非目标 2：当前不要求 backtest 与 M4 完全代码合并

不做：
- 立刻把 `backtest/strategies.py` 全量迁入 `m4_action/`
- 为了统一目录结构而打断验证链现有工作

### 非目标 3：当前不改变 ActionPlan 契约

不做：
- 在当前阶段直接大改 `ActionPlan` Pydantic schema
- 让下游 M5 / M7 / 现有测试一起承压

---

## 建议的最小接口形态

当前建议先引入一个最小共享对象，例如：

- `StrategySpec`
- 或 `StrategyProfile`

其语义应偏“策略身份 + 风格约束 + 参数摘要”，而不是完整执行引擎。

### 最小字段建议

```python
class StrategySpec:
    name: str
    description: str
    style: str                  # 如 macro_momentum / policy_breakout / combo_filter
    allowed_signal_types: list[str]
    allowed_directions: list[str]
    allowed_markets: list[str] | None
    allowed_horizons: list[str] | None
    entry_timing: str
    risk_profile: dict
    exit_profile: dict
```

说明：
- 这不是为了替代 `ActionPlan`
- 也不是为了替代 backtest 内部的完整策略参数对象
- 而是作为一个**跨层共享的最小公共语义对象**

---

## 与现有模块的关系

### 1. 与 M4 的关系

M4 短期内仍然：
- 输入：`OpportunityObject`
- 输出：`ActionPlan`

但未来可以增加非常轻量的一步：
- 在 M4 内部指定“当前默认使用的策略语义”
- 或在内部维护默认 strategy registry

即：
- 先共享“策略 identity”
- 后续再考虑共享“策略实现”

### 2. 与 backtest 的关系

backtest 当前仍可继续保留现有：
- `Strategy`
- `StrategyBacktester`

但可逐步映射到统一 strategy identity：
- `MacroMomentum`
- `PolicyBreakout`
- `ComboFilter`

也就是说，backtest 先继续工作，
只是未来不再独占“策略语义定义权”。

### 3. 与 M5 / M6 / sim 的关系

一旦 plan / position / review 能感知 strategy identity，未来可支持：
- 哪类机会使用了什么策略
- 哪类策略在什么机会上胜率更高
- 是机会判断错误，还是策略选择错误

这对闭环系统很关键。

---

## 建议的分阶段实施方式

### Phase A（当前建议）

只做设计收口，不改主链行为：
- 落一份设计文档（本文）
- 明确共享接口层目标和非目标
- 后续若实施，只做最小 schema / registry 引入

### Phase B（下一步可做）

引入最小 registry / schema：
- 新建共享策略定义文件
- 先放少量策略 identity
- 不要求 M4 输出多计划

### Phase C（更后续）

让 M4 可以显式关联默认 strategy spec：
- 仍默认只输出一个 `ActionPlan`
- 但这个 plan 有明确策略身份来源

### Phase D（未来，非当前任务）

若验证充分，可再考虑：
- M4 多策略输出
- 策略选择器
- sim / retrospective strategy-aware 对比

---

## 风险与边界

### 风险 1：过早抽象

如果现在策略类型还很少，抽接口可能看起来收益不明显。

缓解方式：
- 只做最小共享对象
- 不做过度抽象

### 风险 2：误导为“主链立刻多策略化”

这是当前最大沟通风险。

必须持续强调：
- **共享策略接口层 ≠ 立即多策略主链输出**

### 风险 3：影响现有 ActionPlan 稳态

若为了策略接口层直接大改 `ActionPlan`，会扩大影响面。

缓解方式：
- 当前不改 `ActionPlan` 契约
- 优先做 registry / identity 层

---

## 当前建议结论

当前对 M4 策略层的最小推进建议是：

1. **短期：策略继续留在 backtest 做验证**
2. **近期：引入共享策略接口层（最小 identity / spec / registry）**
3. **暂不要求：M4 立即多策略正式输出**
4. **当前不建议：为统一而进行大规模目录迁移或契约改写**

一句话总结：

> 先统一“策略语义”，再决定是否统一“策略执行”；先让主链和验证链说同一种话，再决定是否让它们走同一条执行路径。
