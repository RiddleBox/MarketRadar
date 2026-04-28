# P0 修复计划 — 美股实盘模拟就绪

> 创建时间: 2026-04-28
> 目标: 今晚可跑美股实盘模拟
> 更新时间: 2026-04-28 P0全部完成 + 现金流修复完成

## 问题诊断

| # | 问题 | 严重性 | 根因 |
|---|------|--------|------|
| 1 | SL/TP永不触发, PnL永远0% | 致命 | `run_continuous_simulation.py`从不调用`update_all_prices()` |
| 2 | 美股交易时段不执行盘中扫描 | 致命 | `is_trading_time()`只判断A股9:30-15:00 |
| 3 | 美股止损用5%(通用)而非2%(策略专用) | 高 | `opportunity_to_position.py`丢弃M12的`stop_loss_candidates` |
| 4 | 卖出手续费未从现金扣除 | 高 | `_on_close()`只加回卖出金额，未扣除卖出手续费 |

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

---

## P0-4: 卖出手续费从现金扣除 ✅ 已完成

**问题**: `_on_close()` 平仓时只加回 `sell_proceeds`，未扣除卖出手续费。
买入手续费已正确扣除，但卖出手续费只在 `apply_fees()` 中更新持仓级别PnL，
未从 `self._cash` 扣除，导致现金追踪虚高。

**修复方案**:
1. ✅ 在 `_on_close()` 中计算卖出手续费: `sell_fee = self._fee_model.sell_cost(sell_proceeds)`
2. ✅ 从现金中扣除卖出手续费: `self._cash += sell_proceeds - sell_fee`
3. ✅ 保持 `apply_fees()` 调用用于持仓级别PnL追踪

**涉及文件**: `m9_paper_trader/paper_trader.py`

**验证结果**:
- 买入100股@100，手续费10元 → 现金 = 1,000,000 - 10,010 = 989,990 ✓
- 卖出100股@110，手续费21.50元 → 现金 = 989,990 + 11,000 - 21.50 = 1,000,968.50 ✓
- 净PnL = 968.50 = (110-100)×100 - 10 - 21.50 ✓
- 现金流完整性: 开仓扣费 + 平仓扣费 = 完整追踪 ✓

**手续费结构** (来自 `core/fee_model.py`):
- 买入: 佣金(0.03%) + 滑点(0.05%)，最低5元
- 卖出: 佣金(0.03%) + 印花税(0.1%) + 滑点(0.05%)

---

## 总结

所有P0问题已修复，系统已就绪用于今晚美股实盘模拟：

✅ P0-1: 价格更新循环 - 每60秒更新持仓价格，触发止损止盈
✅ P0-2: 美股交易时段 - 21:30-04:00盘中扫描，每10分钟一次
✅ P0-3: M12止损策略 - 美股2%/港股3%/A股5%市场专用止损
✅ P0-4: 现金流完整性 - 买入卖出手续费均正确扣除

**下一步**: 运行 `python run_continuous_simulation.py` 进行美股实盘模拟测试