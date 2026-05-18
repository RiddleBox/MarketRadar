# MarketRadar 标准流程文档

> 本文档保留历史设计脉络。2026-05-18 起，主线B（M12价格驱动）新增 v2 迭代方案；旧主线B不删除，作为 v1 历史链路与问题定位依据。

## 一、系统架构总览

```
数据采集 ──→ 信号提取 ──→ 存储 ──→ 判断 ──→ 行动设计 ──→ 模拟盘 ──→ 复盘归因 ──→ 知识库
  M0          M1          M2       M3         M4            M9          M6          M8
                                    ↑                          ↑
               情绪面 ──→ M10 ────┘                          │
               调研/搜索 ─→ M13 ──→ M1.5/M12/M3              │
               补牢机会 ──→ M12 ──→ M3/M4 ───────────────────┘
               模拟代理 ──→ M11 ──→ (未接入主链)              │
               调度器 ──→ M7 ──→ 编排所有模块 ───────────────┘
```

## 二、标准流水线（两条主线）

### 主线A：信号驱动（主动预判）

```
M0 新闻采集
  ↓ (RSS/AKShare/手动)
M1 信号解码
  ↓ (LLM提取MarketSignal)
M2 信号存储
  ↓ (SQLite, 支持因果模式+案例库查询)
M3 机会判断
  ↓ (LLM判断 + 情绪校准 → 输出OpportunityObject)
  ↓  ┌─── M10 情绪信号 ──→ 注入M2 ──→ 被M3消费
M4 行动设计
  ↓ (LLM设计ActionPlan: 止损/止盈/仓位/分批)
M9 模拟开仓
  ↓ (PaperTrader.open_from_plan(plan))
M9 持仓监控
  ↓ (定时更新价格, 自动止损止盈)
M6 复盘归因
  ↓ (LLM分析平仓原因, 质量打分)
M8 知识更新
  (教训写入知识库, 反哺M3未来判断)
```

### 主线B v1（历史设计）：补牢驱动（价格驱动，反向溯源）

> **核心原则**: M12只是触发层，判断全部交给M0→M1→M2→M3。
> M12负责检测异动和收集证据，M3负责所有判断。
> 两条主线共用同一条M0→M1→M2→M3管线，只是触发方式不同。
>
> **历史问题**: v1 默认把“异动原因”压缩为“能被 M1 解码为 MarketSignal 的新闻”。这对 A 股个股新闻有效，但对美股/港股不够：原因可能来自板块、产业链、宏观政策、社交情绪、期权流或纯价格/量能结构，而不一定存在于 ticker 新闻页面。

```
M12 异动检测 (AnomalyDetector) → PriceAnomaly[]
  ↓ 涨停股标记观察池，不入场
  ↓
M12 反向溯源 (BackwardCausation) — 只找原因，不做判断
  ↓ Step 1: M2 SignalStore 查已有相关信号
  ↓ Step 2: M0 定向采集新闻 → M1 LLM解码为结构化信号
  ↓ Step 3: 原因分类（有因/无因）
  ↓ ★ 无因 = 放弃（溯因必须有证据）
  ↓ 有因 → 信号列表
  ↓
M3 judge — 与主线A完全相同的判断逻辑
  ↓ signals → M3 判断是否构成机会
  ↓ 返回 OpportunityObject（含priority/confidence/direction/score）
  ↓ ★ M3返回空列表 = 不构成机会 → 放弃
  ↓
M12 趋势判断 (TrendAssessor) — 基于价格数据+M3结果
  ↓ EARLY (可补) / MIDDLE (谨慎) / LATE (放弃)
  ↓ LATE = 放弃
  ↓
M4 行动设计 — 选择止损策略，更紧止损补偿入场偏晚
  ↓ priority=WATCH → 仅观察不开仓
  ↓
M9 模拟开仓 (多策略可平行对比)
  ↓
M6 复盘归因 — 按origin/anomaly_type/market/trend_stage交叉统计
  ↓
M8 知识更新
```

### 主线B v2（当前迭代目标）：异动解释驱动（Movement Explanation）

> **核心原则**: 价格异动先进入“原因解释”层，不再要求每个原因都必须先变成 `MarketSignal`。M12 负责构造异动上下文和因果假设，M13 负责主动搜索/调研能力，M1/M1.5 负责显式和隐式信息理解，M3 仍负责最终机会判断。

```
M12 异动检测 (AnomalyDetector)
  ↓ PriceAnomaly
M12 构造 MovementContext
  ↓ ticker/market/涨跌幅/量比/ATR/σ/行业/主题/时间窗
M12 调用证据获取层
  ↓ P0: M12直接获取 ticker news（Yahoo ticker RSS / Finnhub / A股个股新闻）
  ↓ P1/P2: M13 search_movement_evidence()（新增目标）
  ↓ M2 近期信号查询（宏观/板块/历史相关信号）
  ↓ M10 情绪上下文（可选，只辅助校准）
  ↓
Candidate Event Builder
  ↓ 去重、排序、打分、保留查询词和失败源
  ↓
M1 显式解码
  ↓ 对明确新闻/公告/财报类证据提取 MarketSignal
  ↓
M1.5 隐式推理
  ↓ 判断板块、产业链、宏观、同业消息是否能解释该标的异动
  ↓
M12 CausalReasoner
  ↓ 输出 CauseHypothesis + CausationResult
  ↓ 有因/部分有因 → 进入 M3
  ↓ 无新闻但强价格/量能 → 受限 watch/research，不得直接 position/urgent
  ↓ 无证据且无强价格结构 → unexplained，放弃
  ↓
M3 judge
  ↓ MarketSignal + CauseHypothesis + MovementContext
  ↓ 是否构成 OpportunityObject
  ↓
M12 TrendAssessor
  ↓ early / middle / late
  ↓
M4 行动设计
  ↓
M9 模拟开仓
  ↓
M6/M8 复盘归因与知识更新
```

#### v2 新增核心对象

| 对象 | 归属 | 作用 |
|------|------|------|
| `MovementContext` | M12 | 描述异动本身：标的、市场、涨跌幅、量比、ATR/σ、行业、主题、时间窗 |
| `EvidenceItem` | M12/M13 | 统一表示新闻、搜索结果、M2信号、情绪、研报、基本面、未来期权/社媒证据 |
| `EvidenceBundle` | M13→M12 | 一次证据搜索的结果包，含查询词、数据源、失败原因、超时标记 |
| `CauseHypothesis` | M12 | 表达可能原因，即使它不能被 M1 解码为标准 MarketSignal |
| `CausalReasoningResult` | M12 | 连接新因果假设与旧 CausationResult/M3 输入 |

#### v2 默认证据源

| 优先级 | 数据源 | 用途 | Key要求 |
|--------|--------|------|---------|
| P0 | Yahoo Finance per-ticker RSS | 美股/港股 ticker 新闻兜底 | 无 |
| P0 | Finnhub company_news | 标的专属新闻主源 | `FINNHUB_API_KEY` |
| P0 | AStockSkill/EastMoney | A股个股新闻 | 无 |
| P1 | DuckDuckGo/Bing/NewsAPI | 动态搜索 `why moving`、板块、产业链、宏观关键词 | DuckDuckGo无；Bing/NewsAPI需key |
| P2 | 行业图谱/主题词表 | 产业链、同业、主题扩展 | 无 |
| P3 | 期权/社媒/flow | 解释 meme、squeeze、momentum 类异动 | 待接入 |

#### v2 与 M13 的边界

M13 提供搜索/调研能力，不替 M12 做因果门控，也不替 M3 判断机会。完整 v2 目标需要新增一个轻量入口：

```python
search_movement_evidence(context: MovementContext, max_items: int, timeout_seconds: int) -> EvidenceBundle
```

这个入口不同于现有 `standard_research()`：它服务于“异动原因解释”，要求快、可降级、保留查询日志；`standard_research()` 仍用于已有初步原因后的补充验证。

P0 不强依赖 M13。P0 先在 M12 当前 `_collect_and_decode_news()` 链路中直接补 Yahoo ticker RSS 和 Finnhub key 检测，复用现有 M1 解码与 `_fallback_simple_signals()`。等 P1/P2 引入动态搜索、缓存、排序、去重后，再把通用搜索能力迁移到 M13。

### 辅助线：情绪面

```
M10 情绪引擎
  ↓ (每30分钟, 09:00-22:00)
  ↓ → 注入M2为signal_type="sentiment"的MarketSignal
  ↓ → 被M3消费校准优先级
```

## 三、数据流与存储

| 模块 | 输入 | 输出 | 存储 |
|------|------|------|------|
| M0 | RSS/AKShare/手动 | CollectedItem文本文件 | `data/incoming/` |
| M1 | 文本+source_ref | List[MarketSignal] | →M2 |
| M2 | MarketSignal/CausalPattern/CaseRecord | 查询接口 | `data/signals/signal_store.db` |
| M3 | 信号+因果模式+案例 | List[OpportunityObject] | →M4 |
| M4 | OpportunityObject | ActionPlan | `data/opportunities/*.json` |
| M5 | ActionPlan+价格 | Position | `data/positions/positions.json` |
| M6 | OpportunityObject+Position+结局 | 复盘报告 | `data/retrospectives/retro_*.json` |
| M8 | 文档+元数据 | 查询结果 | `m8_knowledge/data/knowledge_base.json` |
| M9 | ActionPlan/手动 | PaperPosition生命周期 | `data/paper_positions.json`, `data/paper_trade_log.json` |
| M10 | AKShare数据 | SentimentSignalData | `data/sentiment/` |
| M11 | MarketInput | SentimentDistribution | `data/m11/` (未接入主链) |
| M12 v1 | 价格数据+M2信号 | List[RetroOpportunity] | `data/m12_scan_results.json` |
| M12 v2 | PriceAnomaly+MovementContext+EvidenceBundle | CauseHypothesis/CausalReasoningResult/RetroOpportunity | `data/m12_scan_results.json` + 决策日志 |
| M13 | 标的/上下文/搜索查询 | ResearchReport/EvidenceBundle | `data/research_cache/` |

## 四、交易时段调度

### 盘前 (08:30-09:25)
- M10 情绪数据采集
- M0 新闻批量采集

### 盘中 (09:30-15:00)
- M9 价格更新（每10分钟）
- M12 盘中扫描（每30分钟）
- M0 新闻采集（每15分钟）
- M10 情绪采集（每30分钟）

### 盘后 (15:00以后)
- M12 盘后全量扫描
- M0→M1→M2→M3→M4 信号流水线
- M9 开仓（M4输出ActionPlan）
- M6 复盘归因（当日平仓）
- M8 知识库更新

## 五、数据源优先级

| 市场 | 首选 | 备选1 | 备选2 |
|------|------|-------|-------|
| A股 | FutuFeed (实时) | EastMoneyFeed (3-5秒延迟) | BaostockFeed (日线T+1) |
| 港股 | FutuFeed (实时) | YFinanceFeed (日线) | - |
| 美股 | FutuFeed (实时) | YFinanceFeed (日线) | - |

### 证据源优先级（M12 v2）

| 市场 | P0 直接证据 | P1 动态搜索 | P2 扩展 |
|------|-------------|-------------|---------|
| A股 | AStockSkill/EastMoney 个股新闻 | 百度/通用搜索（可选） | 行业图谱、M2历史信号 |
| 港股 | Finnhub/Yahoo ticker RSS | DuckDuckGo/Bing/NewsAPI | 港股板块、南向资金、行业图谱 |
| 美股 | Finnhub/Yahoo ticker RSS | DuckDuckGo/Bing/NewsAPI | 产业链、同业、主题、未来期权/社媒 |

## 六、已修复的断点

### 断点1: M12→M4→M9 (已修复)
M12扫描出的补牢机会（RetroOpportunity）之前只打印不做操作。现在：
- RetroOpportunity.opportunity 传给 M4.design() 生成 ActionPlan
- ActionPlan 传给 M9 open_from_plan() 自动开模拟仓

### 断点2: M3→M4→M9 (已修复)
M7调度器的signal_pipeline只运行到M4输出，不自动开仓。现在：
- M4 ActionPlan 输出后，自动检查 priority != WATCH 的机会
- 优先级 >= RESEARCH 的机会自动传入 M9 开仓

### 断点3: 数据截断 (已修复)
- paper_trade_log.json 之前只保留最近500条，现在保留全部用于复盘
- equity_curve.json 保留365天

### 断点4: M8→M3 (待实现)
M8知识库当前是只写的，M3不查询M8。未来需：
- M3.judge() 增加 M8 知识库检索，获取相关分析框架和历史教训

### 断点5: M6→M2因果模式 (待实现)
M6复盘结论不自动回写M2因果模式库。未来需：
- M6复盘产出的因果结论自动结构化为CausalPattern写入M2

### 断点6: M12美股/港股定向溯源缺失 (v2迭代中)
当前美股盘中扫描可以发现异动，但经常在反向溯源阶段全部变成 `unexplained`：
- A股新闻源能按代码查新闻，美股/港股 ticker 新闻源不完整
- 通用 RSS 是订阅 feed，不等于异动触发的定向搜索
- `MarketSignal` 不是所有异动原因的唯一表达
- 现有 M13 在 M12 中主要位于 fallback 分支，无法在“无因放弃”前补证据

v2 修复方向：
- 新增 Yahoo per-ticker RSS 和 Finnhub company_news 作为美股/港股 P0 证据源
- P0 先在 M12 内部直接补证据源，不强制依赖 M13
- P0 复用现有 M1 解码和 `_fallback_simple_signals()`，不新增共享 schema
- P1/P2 再新增 `CauseHypothesis`，允许非标准 MarketSignal 的原因进入 M3 上下文
- 对无新闻但强价格/量能结构的异动使用受限允许，最高 `research/watch`
- 将查询词、证据数、数据源失败原因写入决策日志

## 七、关键配置

- FutuOpenD地址: 127.0.0.1:11111
- LLM: DeepSeek (deepseek-chat)
- 数据源检测: detect_a_share_feed() 自动选择最优数据源
- 模拟盘风控: 最大单仓8%, 最大总敞口30%, 最大日回撤5%, 最大总回撤10%

## 八、复盘流程

复盘分为三个层次：

### 1. 每日复盘（自动，盘后15:30）
- M6 RetrospectiveEngine 分析当日平仓
- 信号质量/判断质量/时机质量 各1-5分
- 关键教训写入M8知识库

### 2. 周度复盘（手动触发）
```bash
python run_daily_pipeline.py --mode postmarket
```

### 3. 月度评估（手动触发）
```bash
python -m m9_paper_trader.evaluator
```
- 胜率/盈亏比/夏普/MAE/MFE分析
- 信号类型/强度/置信度分层评估

## 九、文档变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-04-28 | v1 | 建立标准流程文档，定义信号驱动主线A与补牢驱动主线B |
| 2026-05-18 | v2 draft | 保留主线B v1历史设计，新增主线B v2“异动解释驱动”方案 |
| 2026-05-18 | v2.1 draft | 收缩 P0：M12 直接补 Yahoo/Finnhub + 现有 fallback signal；M13 搜索入口和 CauseHypothesis 推迟到 P1/P2 |

2026-05-18 的变更不删除旧内容，原因是 v1 仍然解释了当前实现为何会在“无因”处截断。v2 的详细落地方案见 [docs/M12_TRACK2_ITERATION_PLAN_2026-05-18.md](docs/M12_TRACK2_ITERATION_PLAN_2026-05-18.md)。
