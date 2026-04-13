# Task 4：回测 / 模拟盘接口设计 v1

## 1. 目标

在进入真实回测与模拟执行之前，先把两条关键映射关系定义清楚：

1. `OpportunityObject -> BacktestTask`
2. `ActionPlan -> SimulatedExecutionSpec`

目的不是马上做完整执行引擎，而是先建立统一接口，确保后续回测系统、模拟盘系统、M6 复盘都基于同一套对象语义演进。

---

## 2. 设计原则

### 原则 A：回测不是重做一次 M3
回测系统接收的是已经形成的 `OpportunityObject`，其职责是：
- 将机会映射为可检验的历史实验任务
- 评估该机会在不同执行参数下的表现
- 输出收益/回撤/胜率/盈亏比分布

它不负责重新判断“这是不是机会”。

### 原则 B：模拟盘不是重做一次 M4
模拟盘接收的是已经形成的 `ActionPlan`，其职责是：
- 忠实模拟建仓 / 加仓 / 减仓 / 止损 / 止盈的执行过程
- 引入滑点、手续费、最小成交单位、流动性约束等现实摩擦
- 记录执行结果供 M6 复盘

它不负责重新设计行动计划。

### 原则 C：优先复用 Task 3 参数系统
回测和模拟盘优先复用：
- `config/risk_config.yaml`
- `config/execution_config.yaml`
- `config/opportunity_rules.yaml`

如果参数不够，应补充参数系统，而不是在回测/模拟盘内部临时发明另一套字段。

---

## 3. OpportunityObject -> BacktestTask

### 3.1 输入对象
输入：`OpportunityObject`

关键消费字段：
- `opportunity_id`
- `opportunity_title`
- `target_markets`
- `target_instruments`
- `trade_direction`
- `instrument_types`
- `opportunity_window`
- `priority_level`
- `opportunity_score`
- `invalidation_conditions`
- `must_watch_indicators`
- `kill_switch_signals`

### 3.2 输出对象建议：`BacktestTask`
建议字段：
- `task_id`
- `opportunity_id`
- `task_type`：event / trend / regime / basket
- `market`
- `instrument_candidates`
- `instrument_type`
- `direction`
- `event_start`
- `event_end`
- `entry_rules`
- `exit_rules`
- `holding_period_grid`
- `risk_budget_pct`
- `stop_loss_template`
- `take_profit_template`
- `phase_template`
- `evaluation_metrics`
- `metadata`

### 3.3 映射逻辑建议

#### 市场与标的
- `target_markets[0]` -> `market`
- `target_instruments` -> `instrument_candidates`
- `instrument_types[0]` -> `instrument_type`

#### 时间窗口
- `opportunity_window.start` -> `event_start`
- `opportunity_window.end` -> `event_end`

#### 风险参数
- 从 `risk_config.yaml` 读取 `priority_risk_budget_pct`
- 从 `instrument_risk_overrides` 读取默认止损 / 止盈

#### 执行模板
- 从 `execution_config.yaml` 读取：
  - `phase_templates`
  - `plan_validity_days`
  - `fallback_stop_loss`
  - `fallback_take_profit`

#### 评分卡用途
`opportunity_score` 仅用于：
- 分桶统计
- 结果解释
- 后续检验“高分机会是否真的更有效”

不用于：
- 覆盖或否决 `OpportunityObject`

---

## 4. ActionPlan -> SimulatedExecutionSpec

### 4.1 输入对象
输入：`ActionPlan`

关键消费字段：
- `plan_id`
- `opportunity_id`
- `plan_summary`
- `primary_instruments`
- `instrument_type`
- `stop_loss`
- `take_profit`
- `position_sizing`
- `phases`
- `valid_until`
- `review_triggers`
- `opportunity_priority`

### 4.2 输出对象建议：`SimulatedExecutionSpec`
建议字段：
- `spec_id`
- `plan_id`
- `opportunity_id`
- `market`
- `instrument`
- `direction`
- `entry_phases`
- `stop_loss_rule`
- `take_profit_rule`
- `max_position_pct`
- `order_constraints`
- `slippage_model`
- `fee_model`
- `liquidity_constraints`
- `expiry_time`
- `review_triggers`
- `metadata`

### 4.3 映射逻辑建议

#### 仓位与风险
- `position_sizing` -> `max_position_pct` / `allocation_hint`
- `risk_config.yaml` 的 `max_single_position_pct` 作为模拟上限约束

#### 分阶段执行
- `phases` -> `entry_phases`
- 每个 `ActionPhase` 直接映射为模拟执行阶段

#### 止损止盈
- `stop_loss` -> `stop_loss_rule`
- `take_profit` -> `take_profit_rule`

#### 计划有效期
- `valid_until` -> `expiry_time`
- `review_triggers` 原样保留

---

## 5. 与 M6 的闭环关系

### BacktestTask -> M6
回测结果应回流给 M6，用于回答：
- 这类机会 historically 是否有效？
- 哪类参数组合表现更稳？
- 高分机会是否真的带来更好结果？

### SimulatedExecutionSpec -> M6
模拟执行结果应回流给 M6，用于回答：
- 是机会判断有问题，还是执行计划有问题？
- 是止损过紧，还是入场节奏不对？
- review trigger 是否起到了作用？

---

## 6. 建议的代码落地方向

### 第一阶段
先在 `core/schemas.py` 中新增两个 schema：
- `BacktestTask`
- `SimulatedExecutionSpec`

### 第二阶段
新增映射函数：
- `build_backtest_task(opportunity: OpportunityObject) -> BacktestTask`
- `build_sim_execution_spec(opportunity: OpportunityObject, action_plan: ActionPlan) -> SimulatedExecutionSpec`

### 第三阶段
补一份 smoke test：
- 给定固定 `OpportunityObject`
- 给定固定 `ActionPlan`
- 验证映射结果字段完整且参数来源正确

---

## 7. 当前建议

Task 4 的第一步，不是立刻做复杂执行逻辑。
而是先把 schema 和映射函数骨架搭起来。

这样后续无论接回测、模拟盘还是 M6，都有统一入口可用。
