# MarketRadar 标准流程文档

## 一、系统架构总览

```
数据采集 ──→ 信号提取 ──→ 存储 ──→ 判断 ──→ 行动设计 ──→ 模拟盘 ──→ 复盘归因 ──→ 知识库
  M0          M1          M2       M3         M4            M9          M6          M8
                                    ↑                          ↑
               情绪面 ──→ M10 ────┘                          │
               补牢机会 ──→ M12 ──→ M4 ──────────────────────┘
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

### 主线B：补牢驱动（价格驱动，反向溯源）

> **核心原则**: M12只是触发层，判断全部交给M0→M1→M2→M3。
> M12负责检测异动和收集证据，M3负责所有判断。
> 两条主线共用同一条M0→M1→M2→M3管线，只是触发方式不同。

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
| M12 | 价格数据+M2信号 | List[RetroOpportunity] | `data/m12_scan_results.json` |

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