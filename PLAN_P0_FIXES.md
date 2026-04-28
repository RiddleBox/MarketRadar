# P0 修复计划 — 美股实盘模拟就绪

> 创建时间: 2026-04-28
> 目标: 今晚可跑美股实盘模拟

## 问题诊断

| # | 问题 | 严重性 | 根因 |
|---|------|--------|------|
| 1 | SL/TP永不触发, PnL永远0% | 致命 | `run_continuous_simulation.py`从不调用`update_all_prices()` |
| 2 | 美股交易时段不执行盘中扫描 | 致命 | `is_trading_time()`只判断A股9:30-15:00 |
| 3 | 美股止损用5%(通用)而非2%(策略专用) | 高 | `opportunity_to_position.py`丢弃M12的`stop_loss_candidates` |

## P0-1: 添加价格更新循环

**问题**: `run_continuous_simulation.py` 主循环从不调用 `PaperTrader.update_all_prices()`。
已开仓的持仓PnL永远为0%，止损止盈永远不触发，权益曲线不更新。

**修复方案**:
1. 将 `PaperTrader` 实例提升为模块级变量（当前`opportunities_to_positions()`每次新建临时实例）
2. 在 `while RUNNING` 主循环中每60秒调用 `trader.update_all_prices(feed)`
3. 仅在有OPEN持仓时拉价格（节省API调用）
4. 开仓成功后立即触发一次价格更新

**涉及文件**: `run_continuous_simulation.py`

**验证标准**: 
- 开仓后PnL随价格变动更新
- 止损/止盈条件满足时自动平仓
- 无持仓时不调用价格API

---

## P0-2: 扩展交易时段判断 + 美股盘中扫描

**问题**: `is_trading_time()` 只判断A股时段(9:30-15:00)。
美股定义(21:30-04:00)已写但从未使用。

**修复方案**:
1. 新增 `is_us_trading_time()` 函数，处理跨日判断(21:30到次日04:00)
2. 主循环增加美股盘中扫描分支，每30分钟一次
3. 周末(六日)跳过扫描
4. 日志标注当前是A股还是美股交易时段

**涉及文件**: `run_continuous_simulation.py`

**验证标准**:
- 21:30-04:00(北京)期间触发美股盘中扫描
- 9:30-15:00(北京)期间触发A股盘中扫描
- 周六日不扫描
- 非交易时段有明确日志

---

## P0-3: 传递M12止损策略到M4

**问题**: `opportunity_to_position.py` 用 `obj = opp.opportunity` 取内层
`OpportunityObject` 传给M4，M4生成通用止损。`RetroOpportunity.stop_loss_candidates`
（美股:2%/4%/1xATR）完全被丢弃。

**修复方案**:
1. `_process_single_opportunity()` 中,当 `orig` 是 `RetroOpportunity` 时取其 `stop_loss_candidates[0]`
2. M4生成ActionPlan后,用M12的止损策略覆盖 `plan.stop_loss`
3. M12无止损策略时保留M4结果作为兜底
4. 同理处理 `take_profit`（如有）

**涉及文件**: `pipeline/opportunity_to_position.py`

**验证标准**:
- 美股开仓止损≈2%而非5%
- A股开仓止损≈5%(保持原有策略)
- 港股开仓止损≈3%
- 纯M3机会（无RetroOpportunity）保持M4默认值

---

## 执行顺序

1. 落档本计划 + 提交当前版本
2. 修P0-1 → 验证 → 更新进度 → 提交
3. 修P0-2 → 验证 → 更新进度 → 提交
4. 修P0-3 → 验证 → 更新进度 → 提交

## P1 后续（本周）

4. M6复盘触发 — 持仓平仓时自动复盘
5. M8→M3知识检索 — 让M3利用历史教训
6. M9开仓扣现金 — 权益追踪准确性

## P2 后续优化

7. M0完整管线集成（当前只用了2/10数据源）
8. M4分阶段建仓
9. SQLite WAL模式