# PROJECT_CONTEXT.md — MarketRadar 开工必读

> **文档类型**：项目状态总览 + 开工上下文
> **最后更新**：2026-05-19
> **当前阶段**：M12 Track 2 v2.1 P0+P1 已落地 + 美股模拟实盘就绪；端到端验证已通过（NVDA +5.2% 全链路跑通 M0→M12→M3→M4→M9）

---

## 一句话当前状态

> 全链路自动化运行中。M12 Track 2 v2.1 P0+P1 已落地，端到端验证通过：NVDA +5.2% 异动 → 多源证据采集（Finnhub 10 + Yahoo 10 + DDG 15, 去重后 32 篇, 5 信号解码）→ M3 判断（RESEARCH/BULLISH/score 7.0）→ M4 行动设计 → M9 模拟开仓。美股市场已启用，FutuOpenD 行情源就绪，`max_anomalies` 限流阀门已加入 `CatcherEngine`，默认盘中 3 个/盘后 5 个异动走 LLM 管线（价格扫描全量不花 token）。

---

## 模块状态总览

| 模块 | 目录 | 状态 | 说明 |
|------|------|------|------|
| M0 收集器 | `m0_collector/` | ✅ 代码完成 | 多 provider + dedup（SQLite）+ normalizer + CLI，统一新闻采集 |
| M1 解码 | `m1_decoder/` | ✅ 代码完成 | LLM 解码 + retry，已验证 |
| M1.5 隐式推理 | `m1_5_implicit_reasoner/` | ✅ 代码完成 | 隐式信号推理，已集成主流水线 |
| M2 存储 | `m2_storage/` | ✅ 代码完成 | SQLite 存储 + 因果图谱 + 历史案例，支撑推理引擎 |
| M3 判断 | `m3_judgment/` | ✅ 代码完成 | Step A/B + 推理引擎 + 因果链推理 + 历史案例检索，M13 信息辅助架构已修复 |
| M4 行动设计 | `m4_action/` | ✅ 结构化条件已添加 | 策略接口 + Kelly/RiskBudget 仓位 + 品类模板 + **结构化 EntryCondition（新）** + 文本→条件正则提取 fallback |
| M5 持仓管理 | `m5_position/` | ✅ 代码完成，已联调 | M4→M5 桥接完成 |
| M6 复盘归因 | `m6_retrospective/` | ✅ 代码完成 | M6→M8 写入修复 |
| M7 调度器 | `m7_scheduler/` | ✅ 17 任务已注册 | 三市场分轨调度 + 交易日历 + OpenD 进程管理 |
| M7 回测引擎 | `m7_backtester/` | ✅ 已增强 | FeeModel+OHLC+丰富统计 |
| M8 知识库 | `m8_knowledge/` | ✅ 完成（Phase 1） | JSON + keyword search，行业知识库已扩展 |
| M9 模拟交易 | `m9_paper_trader/` | ✅ 三市场数据源已联调 | FutuFeed(YFinance/EastMoneyFeed) + 组合持久化 SQLite + 双轨防重复 |
| M10 情绪感知 | `m10_sentiment/` | ✅ 代码完成 | FG 指数 + 北向资金 + 热搜 + 微博 → SQLite + 注入 M2 |
| M11 模拟 Agent | `m11_agent_sim/` | ✅ 完成（Phase 1） | 5 agents 串行拓扑，概率校准 |
| M12 机会捕获 | `m12_opportunity_catcher/` | ✅ 三市场分轨 + v2.1 P0+P1 | 价格扫描 + 异动检测 + 反向溯源 + 趋势判断 + 机会生成 + 行业过滤；**v2.1**: Yahoo RSS + Finnhub key-aware + DDG 动态搜索(R1+R2) + 10s DPM 超时 + 跨源去重 + SOURCES 结构化日志(decoded/fallback计数) |
| M13 深度调研 | `m13_research/` | ✅ 架构已修复 + v2 设计 | 快速/标准/深度三级调研；v2 新增 `search_movement_evidence()` 设计（P1/P2 目标，非 P0 依赖）；M13 提供信息 → M3 做判断 |
| **PlanEvaluator** | `pipeline/plan_evaluator.py` | **✅ NEW** | 开盘检查计划储备：加载 ActionPlan → 结构化条件评估 → 开仓执行 |
| Pipeline | `pipeline/` | ✅ 全链路已联调 | CLI + 回测 + Dashboard V2 |
| Dashboard | `dashboard_v2/` | ✅ 6 tabs | Home + Signal 配置 + 组合 + 异动 + 决策 + 行动设计 |

---

## 模块分层定位

```
实时扫描链：   M12（异动检测+多源证据采集）→ M1/M1.5 → M2 (因果图谱) → M3 (推理判断) → M4 (行动设计) → M9 (模拟交易)
采集链：       M0 → M1 → M2
盘后链：       M6 (复盘) → M8 (知识)
检查链（新）：  PlanEvaluator (开盘读 ActionPlan → 条件评估 → 开仓)
并行输入：     M10（独立采集→注入 M2）
支撑：         M7 调度器 / M13 深度调研
验证：         M11 / backtest / ablation
展示：         Dashboard V2
```

**硬约束**：M13 仅提供信息辅助，不做判断（判断由 M3 完成）。M10/M11 不在充分验证前升格为主链必经节点。

---

## 第一性原理总纲

### 为什么这个系统存在？

二级市场的本质是**在不确定性中识别结构性预期差**。

大多数市场参与者的判断失败，不是因为信息不够，而是因为：
1. 信息没有结构化——新闻、数据、公告混在一起，无法系统比较
2. 信号没有跨时间积累——单次判断丢失了历史上下文
3. 判断和行动脱节——"有机会"和"怎么做"是分开的，止损是临时决定的
4. 结果没有被归因——每次交易后没有系统性复盘，判断力无法迭代
5. **入场缺少纪律**——计划制定后没有自动检查机制，依赖人工判断是否满足条件

MarketRadar 解决这五个问题：
- **M0**：忠实采集外部信息，去重，标准化
- **M1**：提取"已发生的事实变化"，不做预测和主观判断
- **M1.5**：隐式信号推理——从语气/措辞变化中提取未明说的信号
- **M2**：存储信号 + 因果图谱 + 历史案例，支撑跨时间推理
- **M3**：推理引擎，基于信号组合+因果模式+历史案例做机会判断
- **M12**：盘中实时价格扫描 + 异动检测 + 反向溯源，发现技术面机会
- **M4+M5**：行动和判断绑定，止损在入场前确定
- **PlanEvaluator**（新）：开盘自动评估计划条件，满足则执行开仓
- **M6+M8**：复盘归因+知识沉淀，让判断力持续迭代
- **M7**：调度器+回测引擎，编排工作流+验证策略

### 核心约束（永远不能违反）
1. 机会必须有信号溯源
2. 回测必须前向隔离（event_time 是时间基准）
3. 止损在入场前确定，持仓期间不随情绪修改
4. M3 的空列表输出是健康行为，不是系统错误
5. **入场条件必须是机器可评估的**（结构化 EntryCondition），否则计划标记为 unevaluable

---

## 各模块文档索引

| 模块 | PRINCIPLES.md | 核心代码 |
|------|--------------|---------|
| M0 | [m0_collector/PRINCIPLES.md](m0_collector/PRINCIPLES.md) | [cli.py](m0_collector/cli.py) |
| M1 | [m1_decoder/PRINCIPLES.md](m1_decoder/PRINCIPLES.md) | [decoder.py](m1_decoder/decoder.py) |
| M2 | [m2_storage/PRINCIPLES.md](m2_storage/PRINCIPLES.md) | [signal_store.py](m2_storage/signal_store.py) |
| M3 | [m3_judgment/PRINCIPLES.md](m3_judgment/PRINCIPLES.md) | [judgment_engine.py](m3_judgment/judgment_engine.py) |
| M4 | [m4_action/PRINCIPLES.md](m4_action/PRINCIPLES.md) | [action_designer.py](m4_action/action_designer.py) |
| M5 | [m5_position/PRINCIPLES.md](m5_position/PRINCIPLES.md) | [position_manager.py](m5_position/position_manager.py) |
| M6 | [m6_retrospective/PRINCIPLES.md](m6_retrospective/PRINCIPLES.md) | [retrospective.py](m6_retrospective/retrospective.py) |
| M7 | [m7_backtester/PRINCIPLES.md](m7_backtester/PRINCIPLES.md) | [backtester.py](m7_backtester/backtester.py) |
| M8 | [m8_knowledge/PRINCIPLES.md](m8_knowledge/PRINCIPLES.md) | [knowledge_base.py](m8_knowledge/knowledge_base.py) |
| M12 | — | [catcher_engine.py](m12_opportunity_catcher/catcher_engine.py)，[backward_causation.py](m12_opportunity_catcher/backward_causation.py) |
| M13 | [DESIGN.md](m13_research/DESIGN.md) | [research_agent.py](m13_research/research_agent.py) |
| PlanEvaluator | — | [plan_evaluator.py](pipeline/plan_evaluator.py) |

---

## 最近完成（2026-04-19 ~ 2026-05-19）

### M12 Track 2 v2.1 P0 — 美股/港股异动溯源修复（最新）
- **Yahoo Finance per-ticker RSS**: `_fetch_yahoo_ticker_rss()` — 美股/港股 ticker 新闻无 key 兜底
- **Finnhub company_news key-aware**: 有 `FINNHUB_API_KEY` 时优先调用（内容更丰富），无 key 时静默降级到 Yahoo RSS
- **HK symbol format 修正**: `_resolve_remote_symbol()` 统一追加 `.HK` 后缀，Yahoo RSS 和 Finnhub 均使用
- **DataProviderManager 10s 超时保护**: US/HK 无对应 A 股 provider 时不再无限阻塞
- **跨源文章去重**: `_dedup_articles()` 按标题前 80 字符去重，防止同一文章被 Finnhub + Yahoo RSS + DPM 三重解码
- **Finnhub 数据源优先**: Finnhub（更丰富内容）先于 Yahoo RSS（免费降级），与设计规约一致
- **SOURCES 结构化日志**: 单行 `SOURCES {symbol}: total=N deduped=N final=N | Finhub=N:OK | YahooRSS=N:OK | DPM=N:OK`
- **不新增 shared schema**: P0 不引入 `MovementContext`/`EvidenceBundle`/`CauseHypothesis`
- **不依赖 M13**: P0 在 M12 `_collect_and_decode_news()` 内直接接 Yahoo/Finnhub
- **详细设计文档**: `docs/M12_TRACK2_ITERATION_PLAN_2026-05-18.md`、`STANDARD_PIPELINE.md` v2.1、`m12_opportunity_catcher/DESIGN.md` §12、`m13_research/DESIGN.md` §12

### M12 Track 2 P1 — DuckDuckGo 动态搜索（2026-05-19）
- **`_build_search_queries()`**: 两轮查询构造 — R1 ticker direct (2-3 条), R2 sector/theme (2-4 条, 仅 R1 弱时触发)
- **`_search_ddg()`**: DuckDuckGo 文本搜索适配器，使用 `ddgs` 包(fallback `duckduckgo-search`)，无需 API key
- **搜索缓存**: 模块级 `_SEARCH_CACHE` dict, 30 分钟 TTL, 避免重复请求
- **R1/R2 轮次控制**: `ddg_search_rounds` 参数(默认 2, 0=禁用, 1=仅 R1)
- **Finnhub/Yahoo RSS 不再被 DPM 门控**: US/HK ticker 定向新闻始终执行，跨源去重处理重复
- **SOURCES 日志增强**: 新增 `decoded=` 和 `fallback=` 计数, 单行可看全链路结果
- **fallback 日志修正**: "M1 unavailable" → "M1 decoded 0 signals from N articles"
- **`.env` 管理**: Finnhub key 从硬编码迁移到 `.env` + `load_dotenv()`，所有入口统一
- **`.env.example`**: 新增 FINNHUB_API_KEY / NEWSAPI_KEY / BING_SEARCH_API_KEY 注释
- **`Data_Provider_Architecture.md`**: 新增 ticker RSS + 动态搜索 provider 章节

### 结构化入场条件 & 开盘检查（最新）
- **EntryConditionType/EntryCondition schema**：8 种条件类型（PRICE_ABOVE/BELOW/BETWEEN, VOLUME_ABOVE/ABOVE_MA, PRICE_ABOVE/BELOW_MA, TIME_SINCE_CREATED）
- **ActionPhase.entry_conditions**：新字段 `List[EntryCondition]`（默认空列表，向后兼容）
- **ActionPlan.entry_condition_summary**：新字段 `str`（默认 ""，向后兼容）
- **M4 LLM 提示词更新**：要求 LLM 输出结构化 entry_conditions，附条件类型文档
- **M4 文本→条件正则提取 fallback**：`_extract_conditions_from_text()` — 从中文文本提取价格/成交量条件
- **M4 _default_action_detail 兜底**：LLM 失败时默认生成 `PRICE_ABOVE(0)` 条件
- **M4 _build_action_plan phase 循环**：LLM 未产出结构化条件时自动 fallback 到正则提取
- **PlanEvaluator**：全新 `pipeline/plan_evaluator.py` — 三步骤：load_saved_plans() → evaluate_plan() → execute_eligible_plans()
- **Scheduler m4_open_check 任务**：A 股 (09:30)、港股 (09:30)、美股 (21:30) 开盘检查
- **迁移脚本**：`scripts/migrate_action_plans.py` — 批量迁移 50/73 存量计划至结构化条件（自动备份）
- **备份**：`data/action_plans_backup/20260515_203004/`

### M12 三市场分轨扫描
- A 股/港股/美股独立分轨扫描（不同间隔、不同时段）
- 盘中扫描：A 股 10min (09:30-15:00)，港股 10min (09:30-16:00)，美股 10min (21:30-04:00)
- 盘前扫描（收集隔夜信号）和盘后扫描（全量扫描）各市场独立
- 价格扫描 + 异动检测 + 反向溯源 + 趋势判断 + 机会生成全链路

### M13 深度调研架构修正
- M13 职责改为"提供信息"→ M3 做最终判断
- M13 的 major_negatives 显式传递给 M3 的 warnings 和 counter_evidence
- 自动建仓阈值降低，M13 置信度调整软化

### M9 模拟交易增强
- 三市场数据源：FutuFeed（主）+ EastMoneyFeed（A 股备选）+ YFinance（美股备选）
- 组合持久化 SQLite（持仓/成交记录跨重启保留）
- 双轨防重复（M12 和 M4 不同路径开同一标的时去重）
- 交易费用扣减（平仓时扣除卖出手续费）

### Dashboard V2
- 6 个 tab：Home、Signal 配置、组合查看、异动监控、决策日志、行动设计
- 系统级一键关闭按钮
- OpenD 进程管理状态集成
- M12 扫描监控面板
- 机会详情视图 + M4 行动计划展示

### 端到端验证通过（2026-05-19）

NVDA +5.2% 异动完整经过了所有模块：

| 阶段 | 输入 | 输出 | LLM 调用 |
|---|---|---|---|
| M0 采集 | NVDA ticker | Finnhub=10, Yahoo=10, DDG=15 | 0 |
| M1 解码 | 35 articles → dedup 33 | 5 signals decoded | ~5 |
| M2 存储 | 5 signals | saved to M2 | 0 |
| M3 判断 | 5 signals | 1 OPPORTUNITY: RESEARCH/BULLISH/score 7.0 | ~2 |
| Trend | anomaly + causation + M3 | MIDDLE / CONTINUING / 4.2% upside | 0 |
| M4→M9 | RetroOpportunity | ActionPlan → PaperTrade | ~1 |

**成本控制**：1 个异动约 8 次 LLM 调用（~4 min），价格扫描零 token。`max_anomalies` 限流默认盘中 3 / 盘后 5。

### 美股模拟实盘就绪（2026-05-19）

| 改动 | 文件 | 说明 |
|---|---|---|
| 美股市场启用 | `config/market_config.yaml` | US active=true, data_sources=futu→yfinance→csv_local |
| max_anomalies 限流 | `catcher_engine.py` | `run_daily_scan(max_anomalies=5)` / `run_intraday_scan(max_anomalies=3)`, 默认 0=不限 |
| 限流传导 | `run_continuous_simulation.py` | `_scan_single_market` 透传 max_anomalies |
| HK YAML 修复 | `config/market_config.yaml` | data_sources 缩进修正 |
| US 股票池 | `stock_universe.py` | Futu API 全量(上千只) + fallback 55 只热门股（.US 后缀） |

运行方式（**无新脚本，沿用已有入口**）：
```bash
python run_continuous_simulation.py   # 美股时段自动扫描，max_anomalies 默认 3
```
- M1→M2→M3→M4→M9 全链路集成测试
- M10/M11 追踪测试
- 完整系统测试总结报告
- 100% E2E 验证通过

### 调度器增强
- 17 个已注册任务（3 市场 M12 扫描 × 3 类型 + 信号流水线 + 价格更新 + 复盘 + 新闻 + 情绪 + M4 开盘检查 × 3）
- 交易日历集成：非交易日跳过
- OpenD 进程管理器（跨平台配置）
- 统一数据源配置管理
- 状态持久化

---

## 架构要点速查

### 入场条件评估流程
```
市场开盘
  │
  ▼
load_saved_plans(market)  ──  加载不过期、匹配市场的 ActionPlan
  │
  ▼
evaluate_plan(plan, feed)  ──  评估 Phase 1 entry_conditions
  │                             每个条件 → _evaluate_single_condition()
  │                             条件不满足 → eligible=False → 等待下次检查
  ▼
execute_eligible_plans(plans, trader, feed)  ──  调用 trader.open_from_plan()
  │
  ▼
开仓成功（仓位进入 M9 管理）
```

### 条件类型速查
| 类型 | 字段 | 说明 |
|------|------|------|
| PRICE_ABOVE | value | 价格 > value |
| PRICE_BELOW | value | 价格 < value |
| PRICE_BETWEEN | value, value_high | low ≤ price ≤ high |
| VOLUME_ABOVE | value | 成交量 > value |
| VOLUME_ABOVE_MA | value, period | 成交量 > 均量 × value（需历史数据） |
| PRICE_ABOVE_MA | value, period | 价格 > 均线（MA20 用昨收近似） |
| PRICE_BELOW_MA | value, period | 价格 < 均线 |
| TIME_SINCE_CREATED | value | 创建距今 > value 天 |

### M12 扫描流水线（v2.1）

```
价格扫描 → 异动检测(anomaly_detector)
  → 反向溯源(backward_causation)
      ├── DataProviderManager (A股为主, 10s超时)
      ├── Finnhub company_news (US/HK, key-aware)
      ├── Yahoo per-ticker RSS (US/HK, free fallback)
      ├── DuckDuckGo R1 ticker direct (US/HK, fee-free)
      ├── DuckDuckGo R2 sector/theme (弱证据时补充)
      ├── AKShare (A股降级)
      └── M1 decode → fallback weak signal
  → 跨源去重 → SOURCES结构化日志
  → M2 信号存储 → M3 判断
```

---

## 当前最高优先级

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 1 | 全链路自动运行 | ✅ | M0→M12→M1.5→M2→M3→M4→M9 周期性运行 |
| 2 | 开盘检查计划储备 | ✅ | 见 plan_evaluator + m4_open_check 任务 |
| 3 | M12 三市场分轨 | ✅ | A/港股/美股独立扫描 |
| 4 | Dashboard V2 | ✅ | 6 tabs + 系统控制 |
| 5 | M12 Track 2 v2.1 P0 | ✅ | Yahoo RSS + Finnhub + 10s 超时 + 去重 + 日志 |
| 6 | M12 Track 2 v2.1 P1 | ✅ | DDG 动态搜索(R1+R2) + Finnhub/Yahoo 不被 DPM 门控 + .env 管理 |
| 7 | M13→M3 架构分离 | ✅ | M13 提供信息，M3 做判断 |
| 8 | **端到端验证** | ✅ 已通过 | NVDA +5.2% 异动全链路：证据采集→M3→M4→M9，M3 输出 RESEARCH/BULLISH/score 7.0 |
| 9 | **美股模拟实盘就绪** | ✅ | US active=true + FutuFeed 行情 + max_anomalies 限流 + run_continuous_simulation.py 统一入口 |
| 10 | **P2 CauseHypothesis + MovementContext** | ⏳ | P1 日志稳定后引入本地 dataclass |
| 11 | 实盘交易评估 | ⏳ 待评估 | 观察模拟盘 M3 转化率后再决定 |

---

## 关键配置文件

- LLM 配置：[config/llm_config.yaml](config/llm_config.yaml)
- 信号分类：[config/signal_taxonomy.yaml](config/signal_taxonomy.yaml)
- 市场配置：[config/market_config.yaml](config/market_config.yaml)
- 风险参数：[config/risk_config.yaml](config/risk_config.yaml)
- 执行参数：[config/execution_config.yaml](config/execution_config.yaml)
- 机会规则：[config/opportunity_rules.yaml](config/opportunity_rules.yaml)
- 环境变量：`.env`（从 `.env.example` 复制后填写）

---

## 关键文档索引

| 文档 | 说明 |
|------|------|
| [STANDARD_PIPELINE.md](STANDARD_PIPELINE.md) | 标准流程文档（主线A信号驱动 + 主线B v1/v2 价格驱动） |
| [docs/M12_TRACK2_ITERATION_PLAN_2026-05-18.md](docs/M12_TRACK2_ITERATION_PLAN_2026-05-18.md) | M12 Track 2 v2.1 迭代计划（P0/P1/P2 分层） |
| [m12_opportunity_catcher/DESIGN.md](m12_opportunity_catcher/DESIGN.md) | M12 设计文档（含 §12 v2 迭代设计） |
| [m13_research/DESIGN.md](m13_research/DESIGN.md) | M13 设计文档（含 §12 search_movement_evidence 目标） |
| [docs/Data_Provider_Architecture.md](docs/Data_Provider_Architecture.md) | 数据提供者架构设计 |
| [docs/MarketRadar_Iteration_Plan_v2.md](docs/MarketRadar_Iteration_Plan_v2.md) | 迭代计划 |
| [docs/MarketRadar_Roadmap_v1.md](docs/MarketRadar_Roadmap_v1.md) | 整体演进路线图 |
| [docs/MarketRadar_Execution_Plan_v1.md](docs/MarketRadar_Execution_Plan_v1.md) | 执行计划 |
| [docs/anchors/2026-04-14-architecture-plan-and-change-disposition-anchor.md](docs/anchors/2026-04-14-architecture-plan-and-change-disposition-anchor.md) | 架构校准锚点 |
| [MEMORY.md](MEMORY.md) | 项目记忆 & 环境注意事项 |
