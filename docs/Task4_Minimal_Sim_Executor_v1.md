# Task 4：最小模拟执行器 v1

## 1. 目标

在最小回测执行器之后，补上 Task 4 的另一条腿：
让 `SimulatedExecutionSpec` 可以被一个简单执行器消费，产出结构化模拟执行结果。

---

## 2. 当前实现

文件：`simulation/minimal_execution_engine.py`

类：`MinimalExecutionEngine`

能力范围：
- 消费 `SimulatedExecutionSpec`
- 基于 `entry_phases` 生成模拟成交记录
- 基于百分比止损 / 止盈决定退出
- 输出 realized pnl / max drawdown / review_triggered

---

## 3. 输入输出

### 输入
- `SimulatedExecutionSpec`
- `prices: List[float]`
- `initial_capital`

### 输出
- `SimulatedExecutionResult`
  - 包含多个 `SimulatedFill`

---

## 4. 当前简化假设

### 已支持
- 分阶段 entry fill 记录
- 固定手续费 bps
- 固定滑点 bps
- 百分比止损 / 止盈
- 简单持有至序列结束 / 触发止盈止损退出

### 尚未支持
- 真实挂单/撤单
- 部分成交
- 流动性不足导致的无法成交
- 盘中撮合顺序
- T+1 卖出限制
- 多标的切换与替代方案

---

## 5. 模块边界

- 该执行器不重新设计行动计划
- 该执行器不重新判断机会
- 该执行器仅负责把 `ActionPlan -> SimulatedExecutionSpec` 的输出真正跑起来

所以它属于 Task 4 的执行验证层，而不是新的决策模块。

---

## 6. 下一步建议

后续增强顺序建议：
1. 增加订单状态机（submitted / partial / filled / canceled）
2. 引入 T+1 / 涨跌停 / 最小成交单位
3. 增加替代方案与 review trigger 的真实触发逻辑
4. 将模拟执行结果回流到 M6 复盘
