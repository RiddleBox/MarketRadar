# Market separation and price source plan (2026-04-14)

## 已确认现状
### 1. 系统已有按市场分开处理的设计倾向
- `config/market_config.yaml` 已按市场配置交易时间、指数、数据源优先级
- `m10_sentiment/sentiment_engine.py` 当前明确以 `A_SHARE` 为主（`affected_markets=["A_SHARE"]`）
- `backtest/strategies.py` 也已经有 `allowed_markets`

因此，Reality backtest 的价格层与数据处理规则也应继续坚持：
> **按 market 分开，不做所有市场共用一套粗糙规则。**

## 原则
### 原则 1：价格源按市场分流
建议最小分流：
- `A_SHARE`
  - 首选：CSV/cache
  - 次选：baostock
  - 兜底：akshare
- `HK`
  - 首选：CSV/cache
  - 次选：akshare
- `US`
  - 首选：CSV/cache
  - 次选：后续再接（当前不强推）

### 原则 2：instrument normalize 也按市场分流
同一中文名/指数名在不同市场可能映射不同代理品种，
所以 alias / proxy map 不应写成完全无 market 语境的全局黑盒。

### 原则 3：回测优先依赖本地价格沉淀
高精度回测最终应优先依赖：
- `data/price_cache/*.json`
- 或本地标准化 CSV

在线源（akshare / baostock / 未来的 tushare/2share）应主要作为：
- 首次回填
- 缺口补数
- 日常更新

## 关于 2share / tushare
当前仓库中未发现现成接入代码。

若用户提到“2share 免费源”，大概率是在说：
- `tushare`（常见中文口误/别称），或
- 其他第三方免费封装源

### 当前建议
短期不直接把它塞进主回测链，而是：
1. 先把价格层接口整理成多源 fallback
2. 再评估是否增加 `tushare` / `2share` loader
3. 新源接入时必须按 market 明确支持范围，不要全市场一把梭

## 下一步落点
1. 核 `core.data_loader` 的 loader 结构是否适合接入 market-aware fallback
2. 检查 `market_config.yaml` 中各 market 的 source priority
3. 在 Reality backtest Phase 1 里补 market-aware instrument / source summary
4. 如需新增 `tushare/2share`，先作为独立 loader 验证，不直接污染现有主链
