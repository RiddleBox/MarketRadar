# M17 Ten-Bagger Research — 设计文档

> 模块代号: M17
> 模块名称: Ten-Bagger Research
> 创建日期: 2026-06-06
> 状态: 规划阶段

---

## 1. 项目背景

M17 是 MarketRadar 的离线研究模块。

项目关注 2015-01-01 到 2025-12-31 期间，美股市场中任意连续 90 个自然日收盘价涨幅达到或超过 1000% 的股票 episode。

核心研究问题:

```text
历史上 90 自然日 10 倍股主要由哪些机制驱动?

当股票已经上涨 100% / 200% / 300% 后，
它继续成为 10 倍股的概率是多少?

上涨过程中哪些信号最能区分:
未来继续上涨 vs 未来见顶回落?
```

---

## 2. 总体研究流程

M17 只采用三阶段主线:

```text
Step 1: 样本收集
Step 2: 特征提取
Step 3: 规则/模型建立
```

### Step 1: 样本收集

目标:

```text
找出所有满足 90 自然日收盘价涨幅 >= 1000% 的美股 episode。
```

核心输出:

```text
data/tenbagger_research/samples/all_tenbaggers.csv
data/tenbagger_research/episodes/episodes.csv
data/tenbagger_research/reports/sample_collection_report.md
```

本阶段只回答:

```text
哪些股票在哪些 90 自然日窗口中真的涨了 10 倍?
```

本阶段不做:

```text
事件解释
机制分类
可复制性判断
交易规则
```

### Step 2: 特征提取

目标:

```text
对每个 episode 提取价格路径、成交量路径、波动率、回撤、事件、资金和市场结构事实。
```

核心输出:

```text
data/tenbagger_research/cases/{ticker}_{year}_{episode_id}/case.md
data/tenbagger_research/cases/{ticker}_{year}_{episode_id}/price_path.csv
data/tenbagger_research/cases/{ticker}_{year}_{episode_id}/events.csv
data/tenbagger_research/cases/{ticker}_{year}_{episode_id}/market_structure.csv
data/tenbagger_research/features/episode_features.csv
```

本阶段只提取事实，不提前分类。

### Step 3: 规则/模型建立

目标:

```text
基于样本和特征，归纳上涨机制、延续概率、可复制性标签和行动信号。
```

核心输出:

```text
data/tenbagger_research/models/continuation_probability_model.*
data/tenbagger_research/reports/tenbagger_mechanism_report.md
data/tenbagger_research/reports/actionable_signals_report.md
data/tenbagger_research/reports/m12_m13_m3_feedback_notes.md
```

本阶段才允许执行:

```text
机制归纳
HIGH / MEDIUM / LOW 可复制性评估
Continuation probability model
无监督聚类
可操作信号总结
```

---

## 3. Step 1 样本收集设计

### 3.1 市场范围

第一版:

```text
NASDAQ
NYSE
AMEX
```

后续扩展:

```text
OTC
港股
A股
韩国市场
```

设计要求:

```text
数据源、ticker universe、交易日历、交易所字段必须可扩展。
```

### 3.2 时间范围

```text
2015-01-01
~
2025-12-31
```

为了处理 90 自然日窗口，价格数据实际拉取范围应覆盖:

```text
2015-01-01
~
2026-03-31
```

这样 2025-12-31 附近的 start_date 仍然可以找到 90 天后的 end_date。

### 3.3 样本定义

对于任意 start_date:

```text
start_date 必须是交易日。
target_end_date = start_date + 90 natural days。
```

如果 `target_end_date` 是交易日:

```text
end_date = target_end_date
```

如果 `target_end_date` 不是交易日:

```text
end_date = target_end_date 之后第一个交易日
```

计算:

```text
return_90d = end_close / start_close - 1
```

纳入条件:

```text
return_90d >= 10.0
```

即:

```text
90 自然日涨幅 >= 1000%
```

### 3.4 价格口径

已确认:

```text
1. raw close 和 adjusted close 双轨记录。
2. 同时计算 raw_return_90d 和 adjusted_return_90d。
3. 保留 qualification_basis 字段，记录命中来自 raw、adjusted 或 both。
4. 如果 raw 和 adjusted 结果不一致，标记 needs_manual_review。
5. M17 追求的是大趋势样本库，不把单一价格口径下的严格 1000% 当作唯一事实。
6. 每个命中样本必须保留 corporate action 备注，后续人工或规则复核拆股/并股/异常复权。
```

### 3.5 POC 数据源

POC 阶段可使用低成本数据源:

```text
Nasdaq Trader symbol directory
SEC company_tickers
yfinance
Stooq
Futu OpenD
Tushare Pro
```

POC 目标:

```text
验证样本扫描流程，而不是产出最终研究结论。
```

POC 风险:

```text
survivorship bias
退市标的缺失
改名标的缺失
并购/破产标的缺失
异常 corporate action 处理不完整
免费源限频、字段不一致、复权规则不同
```

POC 输出必须标记:

```text
preliminary = true
data_quality = POC
```

POC 默认策略:

```text
1. yfinance 和 Stooq 并行拉取。
2. 两个数据源都记录 source 字段。
3. 如果两个数据源的价格路径差异过大，标记 source_conflict。
4. 第一轮先跑简单完整流程，不接入 Tushare Pro。
5. Futu OpenD 作为可选 provider，适合在本机 OpenD 可用且行情权限满足时补充 K 线。
6. Tushare Pro 作为后续增强 provider，等 POC 流程验证有效后再接入。
```

注意:

```text
Futu OpenD 和 Tushare Pro 都不能默认视为 survivorship-bias-free 数据源。
它们可以提高覆盖和交叉验证能力，但正式研究仍需单独处理退市和历史 ticker universe。
```

Simple-first 执行原则:

```text
先用 yfinance / Stooq / 合成测试数据跑通完整 Step 1。
如果样本扫描、episode 合并和报告结构有效，再迭代接入 Tushare Pro。
```

### 3.6 正式数据源要求

正式研究需要尽量支持:

```text
delisted securities
corporate actions
symbol changes
exchange changes
reverse splits
delisting returns
```

候选研究级数据源:

```text
CRSP
EODHD delisted coverage
Polygon
Nasdaq Data Link / Sharadar
其他支持 survivorship-bias-free 的美股历史数据库
```

### 3.7 Episode 合并

同一股票可能出现多个重叠的 qualifying windows。

不能把每个重叠窗口都当成独立样本。

需要合并为 episode:

```text
ticker + episode_id
```

建议 episode 字段:

```text
ticker
episode_id
company_name
exchange
first_qualifying_start_date
first_qualifying_end_date
best_90d_start_date
best_90d_end_date
best_90d_return
peak_date
peak_return_from_first_start
episode_start_date
episode_end_date
num_qualifying_windows
data_quality
preliminary
notes
```

episode 合并规则待确认。

POC 默认规则:

```text
同一 ticker 的 qualifying windows 如果 start_date 间隔 < 90 自然日，则合并为同一 episode。
```

### 3.8 all_tenbaggers.csv 字段

第一版字段:

```text
ticker
company_name
exchange
start_date
end_date
start_price
end_price
return_90d
raw_start_price
raw_end_price
raw_return_90d
adjusted_start_price
adjusted_end_price
adjusted_return_90d
qualification_basis
needs_manual_review
market_cap_at_start
industry
episode_id
data_source
data_quality
preliminary
price_basis
notes
```

字段说明:

```text
market_cap_at_start 和 industry 在 POC 阶段允许为空。
正式研究阶段必须尽量补全。
```

### 3.9 样本收集验证

Step 1 完成前，至少要做:

```text
1. Spot check 已知样本，例如 GME、AMC、HKD 等是否能被扫描到。
2. 检查样本是否包含明显由拆股/并股造成的虚假 10 倍。
3. 检查同一 ticker 重叠窗口是否被合并为合理 episode。
4. 输出 sample_collection_report.md，说明数据源、覆盖范围、缺失风险和 preliminary 标记。
```

---

## 4. Step 2 特征提取设计

Step 2 只在 Step 1 样本库稳定后执行。

### 4.1 Case File 目录

每个 episode 生成:

```text
data/tenbagger_research/cases/{ticker}_{year}_{episode_id}/
  case.md
  price_path.csv
  events.csv
  market_structure.csv
  sources.json
```

### 4.2 case.md 模板

```markdown
# Company

# Price Action

# Timeline

# Major Events

# News

# Financial State

# Market Structure

# Possible Drivers

# One-Year Outcome
```

### 4.3 事件事实字段

初始事件字段:

```text
FDA
Clinical Trial
Merger
Acquisition
Bankruptcy
Restructuring
AI
Crypto
EV
IPO
SPAC
Index Inclusion
Earnings
Regulatory Approval
```

允许新增字段。

### 4.4 资金字段

```text
Short Interest
Days To Cover
Borrow Fee
Institution Ownership
Retail Activity
Options Volume
Gamma Exposure
```

### 4.5 市场结构字段

```text
Market Cap
Float
Float Turnover
Insider Ownership
Institution Ownership
Share Dilution
Reverse Split History
```

### 4.6 上涨路径字段

每个 episode 构建:

```text
Day 0
Day 10
Day 20
...
Day 90
```

记录:

```text
Price
Volume
Volatility
Drawdown
Market Cap
Short Interest
```

同时保留完整日频路径。

---

## 5. Step 3 规则/模型建立设计

Step 3 只能在样本收集和特征提取完成后执行。

### 5.1 Continuation Probability Model

必须回答:

```text
当股票上涨 100% 后，后续继续达到 1000% 的概率是多少?
当股票上涨 200% 后，后续继续达到 1000% 的概率是多少?
当股票上涨 300% 后，后续继续达到 1000% 的概率是多少?
```

重要约束:

```text
不能只用成功样本。
必须构建对照组:
所有曾上涨 100% / 200% / 300% 但未达到 1000% 的 episode。
```

否则概率会系统性虚高。

已确认:

```text
100% / 200% / 300% 对照组留到 Step 3。
Step 1 只收集 90 自然日 1000% 样本，不提前扩展对照组。
```

### 5.2 机制分层

每个样本最终要拆成:

```text
Layer 1: 表面原因
Layer 2: 资金原因
Layer 3: 结构原因
```

### 5.3 可复制性评估

每个机制最终标记:

```text
HIGH
MEDIUM
LOW
```

标准:

```text
HIGH: 机制多次重复出现。
MEDIUM: 有重复迹象，但依赖一定环境。
LOW: 依赖特殊人为因素、异常交易或难以复制的结构。
```

### 5.4 无监督聚类

仅在所有 Case File 和 features 完成后执行。

输入:

```text
Price Path
Volume Path
Volatility Path
Drawdown Path
Market Structure
Event Features
```

候选方法:

```text
HDBSCAN
KMeans
Gaussian Mixture
```

目标:

```text
让数据自动形成类别，而不是先用媒体叙事分类。
```

---

## 6. 与 MarketRadar 其他模块关系

M17 不接入实时交易链路。

未来可反哺:

```text
M12: 价格异动后的趋势阶段和延续性判断
M13: Case File 调研模板、证据补全字段、反向证据规则
M3: 机会判断中的延续概率和机制评分
```

M17 不做:

```text
实时扫描
机会生成
仓位决策
止损决策
实盘下单
```

---

## 7. 目录规划

```text
m17_tenbagger_research/
  PRINCIPLES.md
  DESIGN.md
  PROGRESS.md

  sample_discovery.py
  episode_builder.py
  price_path_builder.py
  case_file_builder.py
  feature_builder.py
  continuation_model.py
  clustering.py
  report_builder.py
  schemas.py
  config.py

data/tenbagger_research/
  raw/
  prices/
  samples/
  episodes/
  cases/
  features/
  models/
  reports/
```

代码文件只在对应阶段开始时创建。

当前阶段只创建规划文档。
