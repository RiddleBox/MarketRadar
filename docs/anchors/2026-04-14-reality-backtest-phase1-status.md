# Reality backtest Phase 1 status (2026-04-14)

## 已验证打通
### 1. 真实机会样本 -> 策略回测事件
- `backtest/strategy_backtest.py` 已可从 `data/opportunities/*.json` 加载真实 M3 风格机会样本
- 当前统计：
  - opportunity files: 21
  - loaded events: 33

### 2. Phase 1 runner 已可执行
- 新增：`backtest/reality_backtest_phase1.py`
- 会输出：`data/backtest/reality_phase1_report.json`

## 当前主 blocker
不是事件链，而是**价格链**：

### 价格缓存覆盖已开始改善，但仍明显不足
- 初始状态：`data/price_cache/` 仅 1 个缓存文件
- 经过 warmup + instrument normalize 后：已提升到 4 个缓存文件
- 当前已确认缓存样本：
  - `510300_SH.json`
  - `512480_SH.json`
  - `00981_HK.json`
  - `01347_HK.json`

### 在线拉取仍不稳定
本轮运行中，AKShare 仍有多只标的拉取失败，例如：
- `159755.SZ`
- `300750.SZ`
- `588000.SH`

错误形态：
- `RemoteDisconnected('Remote end closed connection without response')`

## 当前回测结果含义
本轮 Phase 1 runner 输出中：
- `PolicyBreakout.total_cases = 19`
- `ComboFilter.total_cases = 14`
- 已从 **completed = 0** 推进到 **completed = 1**
- 当前唯一完成样本来自 `ComboFilter`
- 结果：
  - `win_rate = 100%`（但仅 1 笔）
  - `avg_pnl_pct = 1.57`
  - `max_drawdown_pct = -0.19`

因此当前结论更新为：
> **现实机会样本接入已打通，价格缓存覆盖开始形成，但仍不足以支撑有统计意义的高精回测。**

## 已做的小修
### instrument normalize
已在 `load_events_from_opportunities()` 中增加常见标的标准化，例如：
- `沪深300ETF` -> `510300.SH`
- `科创50ETF` -> `588000.SH`
- `半导体ETF（512480）` -> `512480.SH`
- `锂电池ETF（159755）` -> `159755.SZ`

这一步解决了“中文标的名无法直接走 price feed”的问题，但还不能替代价格缓存本身。

## 下一步建议（最高优先级）
### 价格缓存预热器 / 回填器
目标：
- 扫描真实事件样本涉及的 instruments
- 批量预热 `data/price_cache/*.json`
- 将 Reality Phase 1 从“全是 NO_DATA”推进到“开始出现 completed trades”

建议优先做：
1. 提取 `data/opportunities/` 中所有 instruments
2. 去重后批量通过 `HistoryPriceFeed` 预拉缓存
3. 记录哪些标的成功、哪些失败
4. 再重新跑 `backtest.reality_backtest_phase1`
