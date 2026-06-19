# M17 Ten-Bagger Research — 进度记录

> 创建日期: 2026-06-06
> 当前阶段: Step 1 样本收集
> 当前状态: OpenD partial 已产出，低成本 free fallback provider 已接入

---

## 进度更新规则

M17 后续每推进一个步骤，都必须更新本文件。

每次更新至少记录:

```text
日期
阶段
完成内容
输出文件
验证结果
已知风险
下一步
```

如果发生以下变化，必须写入 Decision Log:

```text
样本定义变化
价格口径变化
数据源变化
字段变化
episode 合并规则变化
模型目标变化
```

---

## 总体阶段进度

| 阶段 | 名称 | 状态 | 说明 |
|---|---|---|---|
| Step 1 | 样本收集 | In Planning | 先做美股 POC，输出 all_tenbaggers.csv 和 episodes.csv |
| Step 2 | 特征提取 | Not Started | 等 Step 1 样本库稳定后开始 |
| Step 3 | 规则/模型建立 | Not Started | 等 Step 2 特征完成后开始 |

---

## Step 1 样本收集任务

| 序号 | 任务 | 状态 | 输出 |
|---|---|---|---|
| 1.1 | 确认样本定义和价格口径 | Completed | `PRINCIPLES.md`, `DESIGN.md` |
| 1.2 | 设计数据源接口 | Completed | `data_providers.py` |
| 1.3 | 获取美股 ticker universe | Core Implemented | `ticker_universe.py` |
| 1.4 | 拉取历史价格数据 | POC Working Via OpenD | `pipeline.py`, `run_small_poc.py`, `data_providers.py` |
| 1.5 | 扫描 90 自然日 1000% 窗口 | Core Implemented | `sample_discovery.py` |
| 1.6 | 合并重叠窗口为 episode | Core Implemented | `sample_discovery.py` |
| 1.7 | Spot check 已知样本 | POC Completed | `sample_collection_report.md` |
| 1.8 | 标记 POC 数据风险 | Completed | `sample_collection_report.md` |

---

## Step 2 特征提取任务

| 序号 | 任务 | 状态 | 输出 |
|---|---|---|---|
| 2.1 | Case File 模板落地 | Not Started | `cases/{ticker}_{year}_{episode_id}/case.md` |
| 2.2 | 价格路径构建 | Not Started | `price_path.csv` |
| 2.3 | 事件事实提取 | Not Started | `events.csv` |
| 2.4 | 资金字段提取 | Not Started | `market_structure.csv` |
| 2.5 | 市场结构字段提取 | Not Started | `market_structure.csv` |
| 2.6 | Layer 1/2/3 事实拆解 | Not Started | `case.md` |
| 2.7 | 特征表汇总 | Not Started | `episode_features.csv` |

---

## Step 3 规则/模型建立任务

| 序号 | 任务 | 状态 | 输出 |
|---|---|---|---|
| 3.1 | 构建 100% / 200% / 300% 对照组 | Not Started | 待定 |
| 3.2 | Continuation Probability Model | Not Started | `models/continuation_probability_model.*` |
| 3.3 | 机制归纳 | Not Started | `tenbagger_mechanism_report.md` |
| 3.4 | 可复制性评估 | Not Started | `tenbagger_mechanism_report.md` |
| 3.5 | 无监督聚类 | Not Started | `models/clustering_*` |
| 3.6 | Actionable Signals Report | Not Started | `actionable_signals_report.md` |
| 3.7 | 反哺 M12/M13/M3 说明 | Not Started | `m12_m13_m3_feedback_notes.md` |

---

## Decision Log

| 日期 | 决策 | 说明 |
|---|---|---|
| 2026-06-06 | 使用 M17 编号 | M14/M15/M16 已在旧文档中分别规划给实盘对接、风控、监控告警 |
| 2026-06-06 | 第一版只做美股 | 优先 NASDAQ / NYSE / AMEX，架构保留后续市场扩展能力 |
| 2026-06-06 | POC 接受低成本数据 | POC 结果必须标记 preliminary，不作为最终概率结论 |
| 2026-06-06 | 90 天定义为自然日 | start_date 为交易日，end_date 使用 start_date + 90 自然日 |
| 2026-06-06 | end_date 非交易日时取之后第一个交易日 | 保留至少 90 自然日后的收盘价含义 |
| 2026-06-06 | 研究流程固定为三步 | 样本收集 -> 特征提取 -> 规则/模型建立 |
| 2026-06-06 | 价格双轨记录 | raw close 和 adjusted close 同时记录，同时计算 raw_return_90d 与 adjusted_return_90d |
| 2026-06-06 | POC 数据源并行 | yfinance 和 Stooq 并行，Futu OpenD 与 Tushare Pro 作为候选补充 |
| 2026-06-06 | episode 合并规则 | 同一 ticker 的 qualifying windows 如果 start_date 间隔 < 90 自然日，则合并 |
| 2026-06-06 | 对照组留到 Step 3 | 100% / 200% / 300% 对照组在完整样本和特征基础上按模型需求构建 |
| 2026-06-06 | Simple-first 执行策略 | 先用简单完整流程跑通 Step 1；Tushare Pro 等 POC 有效后再迭代接入 |
| 2026-06-06 | Step 1 核心算法先行 | 先实现不依赖外网的样本扫描和 episode 合并，再接真实 provider |
| 2026-06-18 | 低成本源优先级 | 参考 Vibe-Trading/FinceptTerminal 后，M17 新增 free provider，顺序为 yfinance -> AKShare |
| 2026-06-18 | 非 OpenD 全量扫描复用 universe snapshot | OpenD quota 耗尽时，非 OpenD provider 不重新请求 OpenD universe，直接复用已保存的 opend_us.csv |

---

## Open Questions

| 问题 | 状态 | 备注 |
|---|---|---|
| yfinance 与 Stooq 的主从关系 | Open | 已确认并行，待确认是否 yfinance 主拉取、Stooq 复核，还是完全同权 |
| raw/adjusted 单侧命中的处理 | Open | 建议纳入候选并标记 needs_manual_review |
| Futu OpenD 本机可用性和行情权限 | Open | 需要后续实际检测 |
| Tushare Pro token 和权限 | Deferred | POC 有效后再考虑接入 |

---

## 当前下一步

```text
1. 接入真实 ticker universe 来源。
2. 接入 yfinance/Stooq 的实际批量拉取流程和缓存。
3. 生成 all_tenbaggers.csv 和 episodes.csv。
4. 对 GME / AMC / HKD 等已知样本做 spot check。
5. 输出 sample_collection_report.md。
```

---

## 2026-06-06 Update

阶段:

```text
Step 1 样本收集
```

完成内容:

```text
1. 新增 M17 Python package。
2. 新增 QualifyingWindow 和 Episode 数据结构。
3. 实现 normalize_price_frame()，支持 provider-specific price frame 标准化。
4. 实现 scan_qualifying_windows()，按 90 自然日和下一个交易日规则扫描 1000% 窗口。
5. 实现 raw close / adjusted close 双轨 return 计算。
6. 实现 qualification_basis 和 needs_manual_review 标记。
7. 实现 merge_windows_into_episodes()，同 ticker 且 start_date 间隔 < 90 自然日合并。
8. 新增 yfinance / Stooq POC provider 接口。
9. 新增合成数据测试。
```

输出文件:

```text
m17_tenbagger_research/__init__.py
m17_tenbagger_research/schemas.py
m17_tenbagger_research/sample_discovery.py
m17_tenbagger_research/data_providers.py
tests/test_m17_sample_discovery.py
```

验证结果:

```text
python -m pytest tests/test_m17_sample_discovery.py -q
4 passed in 1.82s
```

已知风险:

```text
1. 尚未接入真实 ticker universe。
2. 尚未批量拉取 yfinance/Stooq 数据。
3. 尚未生成实际 all_tenbaggers.csv。
4. 当前 provider 只是 POC 接口，未处理限频、重试、缓存和 source conflict。
```

下一步:

```text
实现 Step 1 的真实数据输入和输出:
ticker universe -> daily prices -> all_tenbaggers.csv -> episodes.csv -> sample_collection_report.md
```

---

## 2026-06-06 Update 2

阶段:

```text
Step 1 样本收集
```

当前推进:

```text
进入 1.3 获取美股 ticker universe。
```

执行策略:

```text
先实现离线可测试的 ticker universe 标准化和流水线骨架。
后续再接 Nasdaq Trader / yfinance / Stooq 等真实数据源。
```

完成内容:

```text
1. 新增 TickerInfo 数据结构。
2. 新增 normalize_ticker_universe()，支持 symbol/company/exchange 字段别名。
3. 支持按 NASDAQ / NYSE / AMEX 等交易所过滤。
4. 新增 metadata_by_ticker()，为样本扫描提供 company_name 和 exchange。
5. 新增 CollectionConfig 和 CollectionResult。
6. 新增 collect_samples()，串联 ticker universe -> provider -> sample discovery -> episode merge。
7. 新增 write_collection_outputs()，输出 all_tenbaggers.csv 和 episodes.csv。
8. 新增离线 fake provider 测试 provider 调用和失败记录。
```

输出文件:

```text
m17_tenbagger_research/ticker_universe.py
m17_tenbagger_research/pipeline.py
tests/test_m17_ticker_universe_and_pipeline.py
```

验证结果:

```text
python -m pytest tests/test_m17_sample_discovery.py tests/test_m17_ticker_universe_and_pipeline.py -q
6 passed in 1.41s
```

已知风险:

```text
1. 尚未接入真实 Nasdaq Trader ticker universe。
2. 尚未实现 yfinance/Stooq 批量拉取缓存、限频、重试。
3. 尚未生成真实 all_tenbaggers.csv。
4. 真实数据源之间的 source_conflict 还未处理。
```

下一步:

```text
实现最小真实 POC:
用小规模 ticker universe 拉取 yfinance/Stooq 日线，生成样本 CSV，并对已知标的做 spot check。
```

---

## 2026-06-06 Update 3

阶段:

```text
Step 1 样本收集
```

当前推进:

```text
进入最小真实 POC。
```

执行策略:

```text
先只跑小规模 ticker universe，不做全市场扫描。
增加本地价格缓存和 sample_collection_report.md，确保每次 POC 可复查。
```

完成内容:

```text
1. 新增 fetch_prices_with_cache()，支持本地价格缓存。
2. 空价格数据会记录为失败，不再误判为没有样本。
3. 空价格数据不会写入缓存。
4. 新增 write_collection_outputs() 的报告和失败列表输出。
5. 新增 sample_collection_report.md 生成逻辑。
6. 新增 failed_tickers.csv 生成逻辑。
7. 新增 run_small_poc.py，可对指定 ticker 运行 yfinance/Stooq 小样本 POC。
8. 空 all_tenbaggers.csv 和 episodes.csv 也会写入表头，便于下游读取。
```

输出文件:

```text
m17_tenbagger_research/run_small_poc.py
data/tenbagger_research/poc/yfinance/samples/all_tenbaggers.csv
data/tenbagger_research/poc/yfinance/episodes/episodes.csv
data/tenbagger_research/poc/yfinance/reports/sample_collection_report.md
data/tenbagger_research/poc/yfinance/reports/failed_tickers.csv
data/tenbagger_research/poc/stooq/samples/all_tenbaggers.csv
data/tenbagger_research/poc/stooq/episodes/episodes.csv
data/tenbagger_research/poc/stooq/reports/sample_collection_report.md
data/tenbagger_research/poc/stooq/reports/failed_tickers.csv
```

验证结果:

```text
python -m pytest tests/test_m17_sample_discovery.py tests/test_m17_ticker_universe_and_pipeline.py -q
9 passed in 1.38s
```

真实 POC 结果:

```text
python -m m17_tenbagger_research.run_small_poc --provider yfinance --output-dir data/tenbagger_research/poc --no-cache GME AMC HKD

provider=yfinance
tickers=3
windows=0
episodes=0
failed=3
```

失败原因:

```text
yfinance: Yahoo 当前返回 YFRateLimitError，最终记录为 no price data returned。
Stooq: 当前返回浏览器 JavaScript 验证页，不是 OHLC CSV，记录为 Stooq did not return OHLC CSV data。
```

已知风险:

```text
1. 小样本真实数据尚未成功获取。
2. GME / AMC / HKD spot check 因 provider access 未完成。
3. yfinance 可能需要等待限频解除、降低请求频率，或使用已有本地缓存。
4. Stooq 可能无法在当前环境直接使用 CSV 下载，需要换源或改用浏览器/其他数据源。
```

下一步候选:

```text
1. 等 yfinance 限频解除后重跑小样本 POC。
2. 检测本机 Futu OpenD 是否可用，并尝试用 OpenD 拉小样本日 K。
3. 增加从本地 CSV 读取价格数据的 provider，允许手工导入 GME/AMC/HKD 历史价格先跑通真实样本。
4. 若 simple POC 仍被免费源阻挡，再评估接入 Tushare Pro。
```

---

## 2026-06-06 Update 4

阶段:

```text
Step 1 样本收集
```

当前推进:

```text
进入 Futu OpenD 小样本 POC。
```

执行策略:

```text
先检测本机 OpenD / futu-api 可用性，再尝试用 OpenD provider 拉取 GME / AMC / HKD 日 K。
OpenD 仅作为 POC 补充源，不替代后续研究级数据源。
```

完成内容:

```text
1. 确认 futu-api 已安装。
2. 确认 OpenD 手动启动后 API 可响应。
3. 新增 FutuOpenDProvider。
4. 支持将 GME / GME.US / US.GME 统一转换为 US.GME。
5. 支持 request_history_kline 分页，避免单次 1000 条限制漏掉关键年份。
6. 同时拉取 AuType.NONE 和 AuType.QFQ，形成 raw_close / adjusted_close 双轨记录。
7. run_small_poc.py 支持 --provider opend 和 --opend-timeout。
```

验证结果:

```text
python -m pytest tests/test_m17_sample_discovery.py tests/test_m17_ticker_universe_and_pipeline.py -q
11 passed in 1.63s
```

OpenD 数据范围检查:

```text
GME 2015-01-02 ~ 2026-03-31
2827 daily rows
```

OpenD 小样本 POC:

```text
python -m m17_tenbagger_research.run_small_poc --provider opend --output-dir data/tenbagger_research/poc --no-cache --opend-timeout 180 GME AMC HKD

provider=opend
tickers=3
windows=16
episodes=1
failed=0
```

输出文件:

```text
data/tenbagger_research/poc/opend/samples/all_tenbaggers.csv
data/tenbagger_research/poc/opend/episodes/episodes.csv
data/tenbagger_research/poc/opend/reports/sample_collection_report.md
data/tenbagger_research/poc/opend/reports/failed_tickers.csv
```

Spot check:

```text
GME_001 命中。
first_qualifying_start_date = 2020-10-28
first_qualifying_end_date = 2021-01-26
best_90d_start_date = 2020-10-29
best_90d_end_date = 2021-01-27
best_90d_return = 28.625745950554133
num_qualifying_windows = 16
```

说明:

```text
AMC 和 HKD 在当前 OpenD / 90 自然日 / 收盘价口径下未命中。
这不代表它们不是历史异常行情，只表示本轮 Step 1 口径没有发现 90 自然日收盘价 >= 1000% 的 qualifying window。
```

已知风险:

```text
1. OpenD 当前只是 POC 数据源，不保证 survivorship-bias-free。
2. OpenD 对退市、改名、并购、破产标的覆盖仍需验证。
3. 目前仅跑了 3 个 ticker 的小样本。
4. 后续全市场扫描需要处理 OpenD 频率、缓存、分页性能和失败重试。
```

下一步:

```text
1. 用 OpenD 获取小规模 US ticker universe。
2. 先跑 50~200 个 ticker 的 micro-batch POC。
3. 检查缓存、失败率、运行耗时和样本命中质量。
4. 再决定是否扩大到全市场或引入 Tushare Pro。
```

---

## 2026-06-06 Update 5

阶段:

```text
Step 1 样本收集
```

当前推进:

```text
进入 OpenD US ticker universe + micro-batch POC。
```

执行策略:

```text
先通过 OpenD 获取 US_NASDAQ / US_NYSE / US_AMEX 股票列表。
然后限制 ticker 数量跑 50~200 个 ticker 的 micro-batch。
本阶段目标是验证速度、失败率、缓存行为和输出质量，不追求全市场完整覆盖。
```

完成内容:

```text
1. 新增 fetch_opend_us_universe()。
2. OpenD US universe 支持 US_NASDAQ / US_NYSE / US_AMEX 过滤。
3. 初步过滤数字 ticker、优先股、unit、warrant、right 等特殊代码。
4. run_small_poc.py 支持 --universe opend-us。
5. run_small_poc.py 支持 --limit N。
6. pipeline 支持 --request-delay，避免 OpenD 历史 K 线限频。
```

验证结果:

```text
python -m pytest tests/test_m17_sample_discovery.py tests/test_m17_ticker_universe_and_pipeline.py -q
13 passed in 2.83s
```

Universe 检查:

```text
OpenD 原始 US 主板候选: 7074
初步 common-stock 过滤后: 6457
```

Micro-batch 1:

```text
python -m m17_tenbagger_research.run_small_poc --provider opend --universe opend-us --limit 50 --output-dir data/tenbagger_research/poc/opend_micro --opend-timeout 180

tickers=50
windows=1
episodes=1
failed=25
```

问题:

```text
OpenD 历史 K 线限频: 每 30 秒最多 60 次。
由于 M17 对每个 ticker 同时拉 raw 和 adjusted，两次请求/ticker，未节流时容易触发限频。
```

Micro-batch 2:

```text
python -m m17_tenbagger_research.run_small_poc --provider opend --universe opend-us --limit 50 --output-dir data/tenbagger_research/poc/opend_micro_delay --opend-timeout 180 --request-delay 1.1

tickers=50
windows=113
episodes=6
failed=5
```

命中 episodes:

```text
AACG_001: best_return=11.380952380952381, windows=1
ABEO_002: best_return=28.33579335793358, windows=62
ABTC_003: best_return=17.43817787418655, windows=15
ABTC_004: best_return=16.18487394957983, windows=3
ABTS_005: best_return=15.341948310139166, windows=3
ABVX_006: best_return=13.16996699669967, windows=29
```

失败原因:

```text
AACO / AACP / AACPR / AADX / AAS: OpenD history kline returned no rows
```

输出文件:

```text
data/tenbagger_research/poc/opend_micro_delay/opend/samples/all_tenbaggers.csv
data/tenbagger_research/poc/opend_micro_delay/opend/episodes/episodes.csv
data/tenbagger_research/poc/opend_micro_delay/opend/reports/sample_collection_report.md
data/tenbagger_research/poc/opend_micro_delay/opend/reports/failed_tickers.csv
```

已知风险:

```text
1. OpenD universe 仍包含部分特殊证券或无历史 K 线标的。
2. common-stock 过滤需要继续精细化。
3. 全市场扫描必须节流或批量分片，否则会触发 OpenD 限频。
4. 当前扫描是 POC，不代表正式研究级完整样本库。
```

下一步:

```text
1. 进一步清洗 OpenD US universe。
2. 固化 micro-batch 参数: --request-delay 1.1 或更保守。
3. 跑 200 ticker POC，观察失败率、耗时和样本质量。
4. 决定是否开始全市场分批扫描。
```

---

## 2026-06-06 Update 6

阶段:

```text
Step 1 样本收集
```

当前推进:

```text
进入 OpenD 200 ticker POC。
```

执行策略:

```text
使用 OpenD、opend-us universe、limit=200、request-delay=1.1。
观察失败率、耗时、样本命中质量，以及是否继续触发 OpenD 限频。
```

完成内容:

```text
1. 完成 OpenD 200 ticker POC。
2. 增强 sample_collection_report.md，增加 qualification quality。
3. 报告现在记录 both/raw/adjusted 命中分布和 needs_manual_review 数量。
```

验证结果:

```text
python -m pytest tests/test_m17_sample_discovery.py tests/test_m17_ticker_universe_and_pipeline.py -q
13 passed in 2.37s
```

OpenD 200 ticker POC:

```text
python -m m17_tenbagger_research.run_small_poc --provider opend --universe opend-us --limit 200 --output-dir data/tenbagger_research/poc/opend_200_delay --opend-timeout 180 --request-delay 1.1

tickers=200
windows=1432
episodes=39
failed=11
```

Qualification quality:

```text
both: 170
raw: 1262
adjusted: 0
needs_manual_review: 1262
```

Top observed episodes by best_90d_return:

```text
AEC_025: best_return=131.14634146341464
AGMH_036: best_return=96.62711864406779
AEHL_027: best_return=57.31619047619048
AEMD_029: best_return=50.6109785202864
AGPU_037: best_return=53.4827586208984
AGEN_032: best_return=33.92490472988119
ADV_021: best_return=31.050833624810537
ABEO_002: best_return=28.33579335793358
```

失败原因:

```text
11 个 ticker 返回 OpenD history kline returned no rows。
未再观察到 OpenD 每 30 秒 60 次的频率限制错误。
```

关键发现:

```text
1. --request-delay 1.1 可以显著降低 OpenD 限频失败。
2. 200 ticker POC 能稳定产出样本和报告。
3. raw-only 命中占多数，说明很多候选可能受 reverse split / corporate action / 复权差异影响。
4. 后续正式样本库必须区分 both-qualified 与 raw-only candidate。
5. both-qualified 更接近“大趋势真实上涨”的优先样本；raw-only 需要人工或 corporate action 复核。
```

输出文件:

```text
data/tenbagger_research/poc/opend_200_delay/opend/samples/all_tenbaggers.csv
data/tenbagger_research/poc/opend_200_delay/opend/episodes/episodes.csv
data/tenbagger_research/poc/opend_200_delay/opend/reports/sample_collection_report.md
data/tenbagger_research/poc/opend_200_delay/opend/reports/failed_tickers.csv
```

下一步:

```text
1. 在 sample 输出中增加 quality tier，例如 BOTH_QUALIFIED / RAW_ONLY_REVIEW / ADJUSTED_ONLY_REVIEW。
2. 先用 both-qualified 作为 high-confidence POC 样本。
3. 对 raw-only episode 做 reverse split / corporate action 复核。
4. 跑 500 ticker POC 或直接开始分批扫描，但必须保留 quality tier。
```

---

## 2026-06-06 Update 7

阶段:

```text
Step 1 样本收集
```

完成内容:

```text
1. 新增 quality_tier 字段。
2. BOTH_QUALIFIED: raw 和 adjusted 同时 >= 1000%。
3. RAW_ONLY_REVIEW: 只有 raw >= 1000%，需要复核 corporate action。
4. ADJUSTED_ONLY_REVIEW: 只有 adjusted >= 1000%，需要复核复权口径。
5. sample_collection_report.md 输出 quality_tier 分布。
```

验证结果:

```text
python -m pytest tests/test_m17_sample_discovery.py tests/test_m17_ticker_universe_and_pipeline.py -q
13 passed in 2.75s
```

200 ticker POC quality summary:

```text
BOTH_QUALIFIED: 170 windows
RAW_ONLY_REVIEW: 1262 windows
ADJUSTED_ONLY_REVIEW: 0 windows
```

关键例子:

```text
ACON 2025-01-29 -> 2025-04-29
raw:      0.0275 -> 6.7000, return = +242.636x
adjusted: 248.7375 -> 6.7000, return = -97.3064%
quality_tier = RAW_ONLY_REVIEW

ACET 2020-06-19 -> 2020-09-17
raw:      0.1345 -> 16.1100, return = +118.777x
adjusted: 15.0640 -> 257.7600, return = +16.111x
quality_tier = BOTH_QUALIFIED
```

结论:

```text
raw-only 差异不是 10 倍 vs 8 倍。
多数 raw-only 是 raw 看似 10 倍/几十倍/上百倍，但 adjusted 后实际下跌或小涨。
这些样本必须单独复核，不能混入 high-confidence ten-bagger 样本库。
```

---

## 2026-06-10 Update 8

阶段:

```text
Step 1 样本收集
```

当前推进:

```text
进入 OpenD full-universe 分批扫描。
```

完成内容:

```text
1. 新增 run_full_batch.py，支持全 universe 分批扫描。
2. 支持 batch 独立输出:
   data/tenbagger_research/full/opend/batches/batch_XXXX/
3. 支持共享价格缓存:
   data/tenbagger_research/full/opend/prices/opend/
4. 支持 universe snapshot:
   data/tenbagger_research/full/opend/universe/opend_us.csv
5. 支持 merge-only，把有效 batch 合并为最终样本文件。
6. 增加 OpenD quota fail-fast:
   遇到历史 K 线额度不足时停止继续扫描，不再把后续整批 quota failure 当作有效完成。
7. merge-only 会跳过额度耗尽后的无效 batch。
8. 续跑时会识别 quota-failed batch，不会因为旧 _DONE.json 误跳过。
```

验证结果:

```text
python -m pytest tests/test_m17_sample_discovery.py tests/test_m17_ticker_universe_and_pipeline.py -q
13 passed in 2.17s
```

全量扫描状态:

```text
OpenD universe tickers: 6456
已写入 batch dirs: 7
有效 batch: 2
quota-exhausted / invalid batch: 5
有效覆盖 ticker: 400
当前有效 windows: 2078
当前有效 episodes: 59
当前有效 failed tickers: 134
```

Qualification quality:

```text
BOTH_QUALIFIED: 180 windows
RAW_ONLY_REVIEW: 1870 windows
ADJUSTED_ONLY_REVIEW: 28 windows
Needs manual review: 1898 windows
```

输出文件:

```text
data/tenbagger_research/full/opend/samples/all_tenbaggers.csv
data/tenbagger_research/full/opend/episodes/episodes.csv
data/tenbagger_research/full/opend/reports/failed_tickers.csv
data/tenbagger_research/full/opend/reports/full_collection_status.md
data/tenbagger_research/full/opend/reports/sample_collection_report.md
```

阻塞原因:

```text
OpenD 返回:
历史K线额度不足，请求失败。额度会滚动释放，直至30天后全部释放。

这表示当前不是限频等待几分钟能恢复，而是历史 K 线额度被打满。
继续用 OpenD 强跑会继续产生 quota failure，不能完成全 universe。
```

当前结论:

```text
Step 1 的正式 full-universe runner 已完成。
Step 1 的全量样本收集已启动，但被 OpenD 历史 K 额度限制中断。
当前可用成果是 400 ticker 的有效阶段性样本库，不是最终全美股样本库。
```

下一步:

```text
1. 等 OpenD 历史 K 额度释放后，从 batch 3 开始续跑:
   python -m m17_tenbagger_research.run_full_batch --output-dir data/tenbagger_research/full/opend --start-batch 3
2. 或接入新的历史价格源，避免 OpenD 30 天额度限制。
3. 后续最终样本库必须继续保持 BOTH_QUALIFIED / RAW_ONLY_REVIEW / ADJUSTED_ONLY_REVIEW 分层。
```

---

## 2026-06-18 Update 9

阶段:

```text
Step 1 样本收集
```

当前推进:

```text
接入低成本数据源，绕开 OpenD 历史 K 线额度耗尽阻塞。
```

完成内容:

```text
1. 新增 AkShareProvider。
2. 新增 FreeFallbackProvider，顺序为 yfinance -> AKShare。
3. AKShare 美股路径支持 stock_us_hist，并兼容 stock_us_daily 全历史接口。
4. pipeline 缓存新增 .meta.json sidecar，记录 provider/source。
5. collect_samples() 会把实际命中的底层源写入 sample data_source。
6. run_small_poc.py 支持 free / yfinance / akshare / stooq / opend。
7. run_full_batch.py 支持 opend / free / yfinance / akshare。
8. 非 OpenD full-batch 会复用已保存的 OpenD universe snapshot，不再依赖 OpenD 取 universe。
```

输出文件:

```text
m17_tenbagger_research/data_providers.py
m17_tenbagger_research/pipeline.py
m17_tenbagger_research/run_small_poc.py
m17_tenbagger_research/run_full_batch.py
tests/test_m17_ticker_universe_and_pipeline.py
data/tenbagger_research/poc/free_probe/free/
data/tenbagger_research/full/free_probe/
```

验证结果:

```text
python -m py_compile m17_tenbagger_research\data_providers.py m17_tenbagger_research\pipeline.py m17_tenbagger_research\run_small_poc.py m17_tenbagger_research\run_full_batch.py

python -m pytest tests\test_m17_sample_discovery.py tests\test_m17_ticker_universe_and_pipeline.py -q
16 passed in 2.69s
```

真实 free provider 探针:

```text
python -m m17_tenbagger_research.run_small_poc --provider free --output-dir data\tenbagger_research\poc\free_probe --no-cache GME AMC HKD

provider=free
tickers=3
windows=16
episodes=1
failed=1
```

探针结论:

```text
1. yfinance 当前仍返回 YFRateLimitError。
2. free provider 成功 fallback 到 AKShare。
3. GME 命中 16 个 windows，1 个 episode，data_source=akshare。
4. HKD 在 yfinance 与 AKShare 下均未返回价格。
5. AKShare stock_us_daily 只提供单 close 序列，因此 GME 当前为 RAW_ONLY_REVIEW，不是 BOTH_QUALIFIED。
```

full-batch 入口探针:

```text
python -m m17_tenbagger_research.run_full_batch --provider free --output-dir data\tenbagger_research\full\free_probe --limit 3 --batch-size 3 --max-batches 1 --request-delay 0.1 --no-cache

provider=free
universe_tickers=3
windows=0
episodes=0
failed=1
```

已知风险:

```text
1. AKShare 免费源不是 survivorship-bias-free。
2. AKShare US daily 当前缺少 adjusted_close 双轨，输出多为 RAW_ONLY_REVIEW。
3. yfinance 当前环境被限流，短期不能作为稳定主源。
4. HKD 等部分标的可能仍缺失，需要后续补充源或本地导入。
```

下一步:

```text
1. 用 provider=free 跑 50-200 ticker micro-batch，输出到 data/tenbagger_research/full/free。
2. 汇总 yfinance/akshare 成功率、失败标的和样本 quality_tier。
3. 对 AKShare-only 样本补 raw/adjusted 口径复核策略。
4. 再决定是否扩大到 full universe。
```

---

## 2026-06-18 Update 10

阶段:

```text
Step 1 样本收集
```

当前推进:

```text
free provider 从探针推进到 500 ticker micro-batch。
```

完成内容:

```text
1. 优化 FreeFallbackProvider:
   yfinance 连续失败后，本轮 provider instance 自动跳过 yfinance。
2. 优化 AkShareProvider:
   stock_us_hist 连续失败后，直接降级到 stock_us_daily，避免每个 ticker 等待代理超时。
3. 新增两条离线测试覆盖上述降级逻辑。
4. 完成 provider=free 的 batch 1-5，每批 100 ticker。
```

验证结果:

```text
python -m py_compile m17_tenbagger_research\data_providers.py

python -m pytest tests\test_m17_sample_discovery.py tests\test_m17_ticker_universe_and_pipeline.py -q
18 passed in 3.86s
```

free micro-batch 输出:

```text
output_dir = data/tenbagger_research/full/free
completed batches = 1-5
covered tickers = 500
windows = 324
episodes = 31
failed tickers = 227
```

质量分布:

```text
akshare + RAW_ONLY_REVIEW: 324 windows
BOTH_QUALIFIED: 0
ADJUSTED_ONLY_REVIEW: 0
Needs manual review: 324
```

速度观察:

```text
batch 2 before AKShare stock_us_hist downgrade: about 557 seconds
batch 3 after downgrade: about 250 seconds
batch 4 after downgrade: about 234 seconds
batch 5 after downgrade: about 221 seconds
```

Top observed free-provider episodes by best_90d_return:

```text
AFG_005: 2865.0
AKTS_011: 601.1505
APAM_018: 398.0
AM_014: 319.75
AM_013: 303.0
AFG_006: 279.0
APAM_016: 193.0
AB_002: 170.8
AGM.A_008: 166.6667
ARCC_021: 110.0
```

已知风险:

```text
1. 当前 free provider 的有效样本全部来自 AKShare。
2. 当前 AKShare 美股 daily 路径缺 adjusted_close 双轨，所有命中均为 RAW_ONLY_REVIEW。
3. free 输出适合作为低成本候选样本层，不应直接替代 OpenD BOTH_QUALIFIED 层。
4. 部分早期 batch 仍记录旧逻辑下的 stock_us_hist 不可归一化失败，可后续 --force 重跑 batch 1-3 修正。
```

下一步:

```text
1. 从 batch 6 继续:
   python -m m17_tenbagger_research.run_full_batch --provider free --output-dir data/tenbagger_research/full/free --batch-size 100 --start-batch 6 --max-batches 1 --request-delay 0.2
2. 跑到 1000 ticker 后再做一次阶段汇总。
3. 设计 AKShare-only 样本的 raw/adjusted 复核策略。
```

---

## 2026-06-19 Update 11

阶段:

```text
Step 1 样本收集
```

当前推进:

```text
free provider 从 500 ticker 推进到 1000 ticker。
```

完成内容:

```text
1. 完成 provider=free 的 batch 6-10，每批 100 ticker。
2. 当前 completed batches: batch_0001 ~ batch_0010。
3. 运行 merge-only 验证，最终输出可由 batch 重建。
```

验证结果:

```text
python -m m17_tenbagger_research.run_full_batch --provider free --output-dir data\tenbagger_research\full\free --merge-only

provider=free
universe_tickers=6456
windows=794
episodes=89
failed=443
output_dir=data\tenbagger_research\full\free
```

free micro-batch 累计输出:

```text
output_dir = data/tenbagger_research/full/free
completed batches = 1-10
covered tickers = 1000
windows = 794
episodes = 89
failed tickers = 443
```

质量分布:

```text
akshare + RAW_ONLY_REVIEW: 794 windows
BOTH_QUALIFIED: 0
ADJUSTED_ONLY_REVIEW: 0
Needs manual review: 794
```

Top observed free-provider episodes by best_90d_return:

```text
BBAR_047: 7952.0
AFG_005: 2865.0
BBVA_051: 1382.3529
BCC_055: 847.0
BMA_075: 671.3063
AKTS_011: 601.1505
AVGO_036: 550.75
BSBR_083: 419.5263
APAM_018: 398.0
AM_014: 319.75
```

已知风险:

```text
1. 当前 free provider 的有效样本仍全部来自 AKShare。
2. 当前 AKShare 美股 daily 路径缺 adjusted_close 双轨，所有命中均为 RAW_ONLY_REVIEW。
3. 部分极高 return 可能是 corporate action / 复权 / 数据口径问题，必须后续复核。
4. free 输出是低成本候选样本层，不是高置信正式样本层。
```

下一步:

```text
1. 从 batch 11 继续:
   python -m m17_tenbagger_research.run_full_batch --provider free --output-dir data\tenbagger_research\full\free --batch-size 100 --start-batch 11 --max-batches 1 --request-delay 0.2
2. 跑到 2000 ticker 后再做下一次阶段汇总。
3. 设计 AKShare-only 样本的 raw/adjusted 复核策略。
```

---

## 2026-06-19 Update 12

阶段:

```text
Step 1 样本收集
```

当前推进:

```text
free provider 从 1000 ticker 推进到 1400 ticker。
```

完成内容:

```text
1. 完成 provider=free 的 batch 11-14，每批 100 ticker。
2. batch 15 未完成，未计入当前 merged outputs。
3. 停止一个已停滞的 run_full_batch 残留进程。
4. 运行 merge-only，只合并带 _DONE.json 的完成批次。
```

验证结果:

```text
python -m m17_tenbagger_research.run_full_batch --provider free --output-dir data\tenbagger_research\full\free --merge-only

provider=free
universe_tickers=6456
windows=1138
episodes=149
failed=583
output_dir=data\tenbagger_research\full\free
```

free micro-batch 累计输出:

```text
output_dir = data/tenbagger_research/full/free
completed batches = 1-14
covered tickers = 1400
windows = 1138
episodes = 149
failed tickers = 583
```

质量分布:

```text
akshare + RAW_ONLY_REVIEW: 1138 windows
BOTH_QUALIFIED: 0
ADJUSTED_ONLY_REVIEW: 0
Needs manual review: 1138
```

Top observed free-provider episodes by best_90d_return:

```text
BBAR_047: 7952.0
CIB_119: 4019.0
AFG_005: 2865.0
BBVA_051: 1382.3529
CCOI_108: 1108.0
BCC_055: 847.0
CNQ_143: 733.4894
BMA_075: 671.3063
AKTS_011: 601.1505
BTU_090: 583.5
```

低成本样本 vs 高置信样本:

```text
低成本样本是数据获取成本低的候选层，当前主要来自 AKShare free path。
它适合扩大覆盖、发现候选、建立待复核清单，但当前缺 adjusted_close 双轨确认。

高置信样本不是按数据源价格定义，而是按证据质量定义。
当前 M17 的高置信层应优先使用 BOTH_QUALIFIED，即 raw_close 和 adjusted_close 口径同时达到 90 自然日 >= 1000%。

因此低成本和高置信不是天然互斥。
如果低成本源能提供可信 raw/adjusted 双轨，且两条口径都命中，也可以进入高置信层。
但当前 AKShare-only 输出全部是 RAW_ONLY_REVIEW，只能作为候选样本层。
```

已知风险:

```text
1. 当前 free provider 的有效样本仍全部来自 AKShare。
2. AKShare 美股 daily 路径当前缺 adjusted_close 双轨，所有命中均为 RAW_ONLY_REVIEW。
3. 极高 return 可能来自 corporate action / 复权 / 数据口径问题，必须后续复核。
4. batch 15 未完成，下一次应从 batch 15 开始。
```

下一步:

```text
1. 从 batch 15 继续:
   python -m m17_tenbagger_research.run_full_batch --provider free --output-dir data\tenbagger_research\full\free --batch-size 100 --start-batch 15 --max-batches 1 --request-delay 0.2
2. 跑到 2000 ticker 后再做下一次阶段汇总。
3. 设计 AKShare-only 样本的 raw/adjusted 复核策略。
```

---

## 2026-06-19 Update 13

阶段:

```text
Step 1 样本收集
```

当前推进:

```text
本次会话尝试推进 batch 15，未能完成；记录网络阻塞情况并保留原有 1400 ticker 覆盖。
```

完成内容:

```text
1. 运行 M17 测试套件，18 项全部通过。
2. 运行 merge-only，确认 batches 1-14 的有效输出未被破坏。
3. 两次尝试推进 batch 15:
   a. provider=free, batch-size=100, start-batch=15: yfinance.download() 在限流环境下没有 timeout，整批阻塞 26 分钟无任何 cache 写入。
   b. provider=akshare, batch-size=100, start-batch=15: AKShare 在 COLAU..COMP 切片附近间歇性挂起，约 8-10 分钟仅缓存 2 个 ticker (COLB / COLM)。
4. 用 timeout 包裹的独立探针确认 AKShare stock_us_daily / stock_us_hist 在隔离环境下响应良好 (1-6s/ticker)，问题是批量运行中的间歇性挂起，不是全网络故障。
5. 两次尝试都没有创建 batch_0015 目录，没有产生任何无效 batch 残留。
6. 当前 free-provider 累计输出保持: 1400 tickers, 1138 windows, 149 episodes, 583 failed tickers。
```

验证结果:

```text
python -m pytest tests/test_m17_sample_discovery.py tests/test_m17_ticker_universe_and_pipeline.py -q
18 passed in 3.98s

python -m m17_tenbagger_research.run_full_batch --provider free --output-dir data/tenbagger_research/full/free --merge-only
provider=free
universe_tickers=6456
windows=1138
episodes=149
failed=583
output_dir=data\tenbagger_research\full\free
```

已知风险:

```text
1. yfinance.download() 没有 timeout，限流环境下会阻塞整个 batch 无法继续。
   provider=free 在 yfinance 阻塞期间无法 fallback 到 AKShare，因为 fallback 只在异常或空数据时触发，挂起不会触发。
2. AKShare 美股接口当前出现间歇性 ProxyError / 挂起，单次重试可以恢复但批量长跑容易卡住。
3. batch 15 切片 (COLAU..) 含较多新上市/SPAC/.WI 衍生证券，stock_us_daily 失败率较高，stock_us_hist 必须连续 3 次失败后才会被 disable。
4. 当前 free 输出仍全部为 akshare + RAW_ONLY_REVIEW，没有 BOTH_QUALIFIED 高置信样本。
```

下一步:

```text
1. 网络条件改善后再继续 batch 15:
   python -m m17_tenbagger_research.run_full_batch --provider akshare --output-dir data/tenbagger_research/full/free --batch-size 100 --start-batch 15 --max-batches 1 --request-delay 0.2
   建议运行前先用脚本探针确认 COLAU/COLB/COLL/COLM/COMP/CON.WI 在 stock_us_hist/stock_us_daily 下都能在 10s 内返回。
2. 在 m17_tenbagger_research/data_providers.py 给 YFinanceProvider 加一个硬超时
   (yf.download(..., timeout=30) 或 concurrent.futures 包裹)，让 provider=free 在 yfinance 挂起时也能 fallback 到 AKShare。
3. 跑到 2000 ticker 后再做一次阶段汇总。
4. 设计 AKShare-only 样本的 raw/adjusted 复核策略。
```
