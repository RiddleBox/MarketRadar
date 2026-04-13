# Task 4 收口总结与后续迭代锚点

## 1. Task 4 目标回顾

Task 4 的核心目标，是在 Task 3 已形成统一参数系统的基础上，把：

- `OpportunityObject`
- `ActionPlan`

继续向下映射为：

- 可回测任务
- 可模拟执行规格

并验证这两条链不只是静态 schema，而是真的能被最小执行器跑起来。

---

## 2. 本轮已完成内容

### 2.1 接口设计文档已落地
已新增：
- `docs/Task4_Backtest_and_Sim_Interfaces_v1.md`

该文档明确了：
- `OpportunityObject -> BacktestTask`
- `ActionPlan -> SimulatedExecutionSpec`
- 参数系统的复用边界
- 与 M6 的闭环关系

### 2.2 Task 4 核心 schema 已落地
`core/schemas.py` 已新增：
- `BacktestTask`
- `SimulatedExecutionSpec`
- `BacktestRunResult`
- `BacktestSummary`
- `SimulatedFill`
- `SimulatedExecutionResult`

### 2.3 mapper 骨架已落地
已新增：
- `core/task4_mappers.py`

当前已实现：
- `build_backtest_task(opportunity)`
- `build_sim_execution_spec(opportunity, action_plan)`

### 2.4 最小回测执行器已落地
已新增：
- `backtest/minimal_backtest_engine.py`
- `docs/Task4_Minimal_Backtest_Executor_v1.md`
- `test_minimal_backtest_engine.py`

### 2.5 最小模拟执行器已落地
已新增：
- `simulation/minimal_execution_engine.py`
- `docs/Task4_Minimal_Sim_Executor_v1.md`
- `test_minimal_execution_engine.py`

### 2.6 联调入口已可复用
`run_test_pipeline_force_deepseek.py` 已暴露：
- `run_pipeline()`

后续测试和执行器 smoke test 已可直接复用，不再需要重复拼装 M1/M3/M4 流程。

---

## 3. Task 4 当前完成度判断

### 已达成
Task 4 的第一阶段目标已经完成：
- 两条映射链都已建立
- 两类最小执行器都已跑通
- 回测链与模拟链均已有结构化结果对象
- 参数系统已经贯穿到 Task 4

### 当前仍是“最小可执行”，不是“可用于生产”
当前版本仍然是骨架 + 最小验证器，主要作用是：
- 保证对象边界正确
- 保证参数流向正确
- 保证后续增强有稳定入口

而不是：
- 完整真实回测系统
- 完整真实模拟盘系统

---

## 4. 当前明确存在的限制

### 4.1 回测执行器限制
- 仅使用 close 序列
- 不支持 OHLC
- 不支持盘中触发顺序
- 不支持多标的批量运行
- 不支持真实 market-specific 交易约束

### 4.2 模拟执行器限制
- 不支持订单状态机
- 不支持部分成交 / 无法成交
- 不支持 T+1 / 涨跌停 / 最小成交单位
- review trigger 仍是简化触发逻辑

### 4.3 数据层限制
- 当前 smoke test 仍使用 mock 序列
- 尚未接入本地 CSV / akshare / baostock 的统一价格载入层

---

## 5. 后续优化方向（作为迭代锚点）

### 5.1 数据接入层
优先补：
- 标准 price loader
- 支持 `market_config.yaml` 中的数据源优先级
- 优先从本地 CSV 跑，再逐步接 akshare / baostock

### 5.2 回测系统增强
- 支持多标的批量回测
- 支持 OHLC 与盘中触发顺序
- 将 `phase_template` 纳入分阶段回测
- 增加参数扫描结果聚合

### 5.3 模拟盘系统增强
- 订单生命周期状态机
- 部分成交 / 无法成交 / 流动性约束
- 市场制度差异（T+1 / T+2 / 涨跌停）
- review trigger / alternative plan 的真实执行逻辑

### 5.4 与 M6 闭环
- 回测结果自动生成复盘视图
- 模拟执行结果自动归因到 M3 / M4 / 参数 / 市场 regime
- 为高分/低分机会建立分层效果检验

---

## 6. 进入下一阶段前的固定锚点

### 锚点 A：Task 4 的第一阶段已经完成，不要再无限在最小执行器上补细节
后续应进入“数据接入层 + 真实约束增强”，而不是继续在 mock price 上做过多装饰。

### 锚点 B：所有增强都应沿着统一对象体系扩展
- 回测继续围绕 `BacktestTask / BacktestSummary`
- 模拟盘继续围绕 `SimulatedExecutionSpec / SimulatedExecutionResult`

不要另起一套旁路对象。

### 锚点 C：参数不足时，优先补 Task 3 参数系统
而不是在执行器内部偷偷塞一堆临时常量。

---

## 7. 建议的下一步

Task 5 / 下一阶段更适合优先做：
1. 建一个最小 price loader
2. 让回测执行器优先接本地 CSV 数据
3. 让模拟执行器开始识别市场制度差异
4. 再考虑更复杂的订单状态机与 M6 回流

这样推进，会比继续停留在 mock 价格世界里更有价值。
