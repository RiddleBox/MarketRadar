# P0 修复计划 — 美股实盘模拟就绪

> 创建时间: 2026-04-28
> 目标: 今晚可跑美股实盘模拟
> 更新时间: 2026-04-28 P0全部完成

## 问题诊断

| # | 问题 | 严重性 | 根因 |
|---|------|--------|------|
| 1 | SL/TP永不触发, PnL永远0% | 致命 | `run_continuous_simulation.py`从不调用`update_all_prices()` |
| 2 | 美股交易时段不执行盘中扫描 | 致命 | `is_trading_time()`只判断A股9:30-15:00 |
| 3 | 美股止损用5%(通用)而非2%(策略专用) | 高 | `opportunity_to_position.py`丢弃M12的`stop_loss_candidates` |

## P0-1: 添加价格更新循环 ✅ 已完成

**问题**: `run_continuous_simulation.py` 主循环从不调用 `PaperTrader.update_all_prices()`。
已开仓的持仓PnL永远为0%，止损止盈永远不触发，权益曲线不更新。

**修复方案**:
1. ✅ 将 `PaperTrader` 实例提升为模块级变量 `_trader`
2. ✅ 每60秒调用 `update_open_positions()` 更新所有OPEN持仓价格
3. ✅ 仅在有OPEN持仓时拉价格（节省API调用）
4. ✅ 自动选择数据源：Futu > YFinance，按持仓市场智能选择
5. ✅ 日志记录止损/止盈触发

**涉及文件**: `run_continuous_simulation.py`, `pipeline/opportunity_to_position.py`

**验证结果**:
- 交易时段逻辑跨午夜正确（21:30-04:00 通过 `_is_in_range`）
- PaperTrader共享实例正确传入 `opportunities_to_positions(trader=_trader)`
- 价格更新函数根据持仓市场自动选择数据源

---

## P0-2: 扩展交易时段判断 + 美股盘中扫描 ✅ 已完成

**问题**: `is_trading_time()` 只判断A股时段(9:30-15:00)。
美股定义(21:30-04:00)已写但从未使用。

**修复方案**:
1. ✅ 新增 `is_us_trading()` 函数，处理跨日判断(21:30到次日04:00)
2. ✅ 主循环增加美股盘中扫描分支，每30分钟一次
3. ✅ 周末(六日)跳过所有扫描
4. ✅ 日志标注 A股/美股 交易时段

**涉及文件**: `run_continuous_simulation.py`

**验证结果**:
- 22:00 在US时段内 ✓
- 02:00 在US时段内 ✓
- 12:00 不在任何交易时段 ✓
- 21:29 不在US时段内 ✓
- 04:01 不在US时段内 ✓

---

## P0-3: 传递M12止损策略到M4 ✅ 已完成

**问题**: `opportunity_to_position.py` 用 `obj = opp.opportunity` 取内层
`OpportunityObject` 传给M4，M4生成通用止损。`RetroOpportunity.stop_loss_candidates`
（美股:2%/4%/1xATR）完全被丢弃。

**修复方案**:
1. ✅ `_process_single_opportunity()` 中,当 `orig` 是 `RetroOpportunity` 时取其 `stop_loss_candidates[0]`
2. ✅ M4生成ActionPlan后,用M12的止损策略覆盖 `plan.stop_loss`
3. ✅ M12无止损策略时保留M4结果作为兜底
4. ✅ TP为0时，设为2x SL值

**涉及文件**: `pipeline/opportunity_to_position.py`

**验证结果**:
- 美股开仓止损 2%（原5%）✓
- 港股开仓止损 3%（原5%）✓
- A股开仓止损 5%（保持不变）✓
- 纯M3机会（无RetroOpportunity）保持M4默认值 ✓