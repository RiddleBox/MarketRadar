# Task 4：最小回测执行器 v1

## 1. 目标

在 Task 4 第一阶段已经完成 schema 与 mapper 骨架后，本阶段补一个最小可执行回测器，验证：

- `BacktestTask` 不只是静态对象
- 机会对象已经可以落到简单历史实验
- 后续回测系统可以在此基础上继续增强

---

## 2. 当前范围

当前执行器：
- 文件：`backtest/minimal_backtest_engine.py`
- 类：`MinimalBacktestEngine`

本阶段刻意保持简单：
- 输入仅使用日线 close 序列
- 以首根 close 作为入场价
- 支持按 `holding_period_grid` 做多组实验
- 支持基于模板百分比的止损 / 止盈
- 输出单次运行结果与汇总结果

---

## 3. 输入输出

### 输入
- `BacktestTask`
- `instrument`
- `closes: List[float]`

### 输出
- `BacktestSummary`
  - 包含多个 `BacktestRunResult`

---

## 4. 当前简化假设

### 已支持
- 多持有期扫描：`T+1 / T+3 / T+5 / T+10`
- 百分比止损 / 止盈
- 简单成本模型：
  - fee = `0.06%`
  - slippage = `0.05%`
- 最大回撤计算
- 多空方向收益计算

### 尚未支持
- 开高低收 OHLC
- 盘中触发顺序
- 分阶段真实成交
- T+1 / T+2 交易制度差异
- 涨跌停 / 合约乘数 / 最小成交单位
- 多标的横向扫描

这些都应放到后续迭代，而不是在本阶段一次做满。

---

## 5. 与系统边界的关系

- 该执行器不重新判断机会
- 该执行器不重新设计行动计划
- 它只负责消费 `BacktestTask` 并输出实验结果

也就是说，它是 Task 4 的“验证器”，不是新的裁决模块。

---

## 6. 下一步建议

后续可按顺序增强：
1. 接入本地 CSV / akshare 数据源
2. 增加 `BacktestTask` 到多标的批量运行
3. 将 `phase_template` 纳入真实分阶段模拟
4. 将结果回流到 M6 复盘
