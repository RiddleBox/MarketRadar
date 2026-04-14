# Reality-data backtest foundation plan (2026-04-14)

## 目标
尽快完成最小但可持续扩展的“现实数据高精度回测”基础建设，验证：
1. M3 判断是否能识别真实可兑现机会
2. M4 默认策略语义是否与历史兑现路径一致
3. backtest 指标是否足够反映“准确性”和“有效性”

## 当前现状
已具备：
- `m3_judgment/`：可从信号生成 `OpportunityObject`
- `m4_action/strategy_registry.py`：共享策略语义层（轻绑定）
- `backtest/strategies.py`：3 个基础策略参数原型
- `backtest/strategy_backtest.py`：策略级回测框架
- `backtest/history_price.py`：价格读取三层机制（seed / price_cache / akshare）
- `pipeline/run_backtest.py`：已有回测 pipeline 入口

当前主要缺口：
1. **机会样本不够真实、规模不够**
   - 目前仍偏 seed / 手工历史样本
2. **价格精度与标的映射仍较粗**
   - 需要更稳定的真实历史行情载入与缓存
3. **事件 -> 交易标的 的映射还不够系统**
   - 如“央行宽松”到底默认回测 510300 / 券商ETF / 银行ETF / 期指，需要统一规则
4. **评估维度仍偏收益，不够覆盖判断准确性**
   - 还需要 precision / hit rate / lead time / false positive cost

## 最短落地路径（建议按顺序）

### Phase 1：先把“现实价格回测”跑顺
目标：不再主要依赖 seed，而是优先使用真实历史价格。

最小动作：
- 核 `backtest/history_price.py` 的 cache/akshare 读取链路
- 统一 instrument -> 市场代码映射规范（A股 ETF / 港股 ETF / 指数）
- 固化 `data/price_cache/` 的缓存格式与回填流程
- 用 20~50 个已知历史事件做第一轮现实价格回测

交付标准：
- 不依赖手写 seed，也能稳定对一批历史机会回放收益曲线

### Phase 2：构建“现实机会样本集”
目标：让回测验证对象从“手工故事样本”转向“真实采集样本”。

最小动作：
- 从 `data/incoming/`、历史新闻、历史 signals 中抽取真实事件
- 形成一份可复跑的数据集（建议 jsonl / json）
- 每条样本至少包含：
  - event_time
  - source_ref
  - signal_label / signal_type
  - affected_markets
  - affected_instruments
  - outcome_label（后验标注，可逐步补）

交付标准：
- 有一份可被 M3 / backtest 反复消费的现实样本库

### Phase 3：建立“判断准确性”指标，而不只看收益
目标：验证“判断对不对”，不是只看“是否赚钱”。

最小指标集合：
- hit_rate：构成机会后，窗口内是否出现预期方向有效行情
- false_positive_cost：误报机会后的平均最大回撤 / 平均亏损
- lead_time_advantage：信号出现到行情启动的提前量
- direction_accuracy：方向判断正确率
- strategy_alignment：M4 默认策略语义与历史最佳策略是否一致

交付标准：
- 报表里同时有收益指标与判断指标

### Phase 4：再做“高精度”
只有 Phase 1~3 跑顺之后，再做：
- 更细粒度价格（分钟级 / 开收盘切片）
- 更精确标的篮子
- 分 market / signal_type / strategy 的分层统计
- walk-forward / 时间切片验证，避免过拟合

## 当前建议
短期优先级应是：
1. M3 Step B 稳态修复（已推进）
2. Phase 1：现实价格回测跑顺
3. Phase 2：现实机会样本集
4. Phase 3：判断准确性指标

不要一开始就追求“超复杂高精回测平台”，否则会拖慢验证闭环。

## 下一步可直接开做的事项
1. 检查并加固 `backtest/history_price.py` / `pipeline/run_backtest.py` 的现实数据链路
2. 选一批已知历史事件（20~50 条）做现实价格回测样本
3. 给 backtest 报表补 `hit_rate / direction_accuracy / false_positive_cost`
