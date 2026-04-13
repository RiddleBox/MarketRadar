# Task 5：多标的最小回测对比 v1

## 1. 目标

当 `OpportunityObject` 给出多个候选标的时，回测不应只挑一个跑。

本阶段补上最小多标的对比能力，让系统可以：
- 自动加载多个候选标的价格序列
- 逐个运行最小回测
- 输出统一排序结果

---

## 2. 当前实现

### 数据层
`data/price_loader.py`
新增：
- `load_closes_for_instruments(instruments, frequency)`

### 回测层
`backtest/minimal_backtest_engine.py`
新增：
- `compare_instruments(task, price_map)`

### schema
`core/schemas.py`
新增：
- `InstrumentBacktestComparison`

---

## 3. 当前输出

对比结果会输出：
- `best_instrument`
- `ranked_results`
- `summaries`

这样后续可以继续扩展到：
- 多标的排序
- 多标的归因
- 将最佳标的回流给模拟盘 / M6

---

## 4. 当前边界

这仍然只是最小验证器：
- 只做逐标的独立回测
- 不做组合优化
- 不做相关性去重
- 不做资金竞争与分配

这些属于后续更高一层的组合风控 / 投资组合管理问题。
