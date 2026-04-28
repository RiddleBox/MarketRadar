# M12 机会补牢 — 设计文档

> **模块代号**: M12 (Opportunity Catcher)
> **创建日期**: 2026-04-28
> **状态**: 设计阶段

---

## 一、模块定位

### 一句话描述

**价格是最终验证** — 当市场已用真金白银投票时，反向溯源找原因，判断趋势能否延续，决定是否仍可补上车。

### 与现有模块的关系

```
现有管线（信号驱动，正向推理）：
  M0(新闻) → M1(解码) → M2(存储) → M3(判断) → M4(行动)

并行管线（价格驱动，反向溯源）：
  [M12 异动检测] → [M12 反向溯源(M0定向采集+M1解码)]
                                ↓
                    M2(存储) → M3(评判持续性) → M4(行动，更紧止损)
                                ↓
                    M9(多策略模拟对比)
```

M12 不替代任何模块，而是一个**新触发层**：以价格异动为入口，编排已有模块完成反向推理。

### 模块边界

| 职责 | 所属模块 | 说明 |
|------|---------|------|
| 异动检测 | M12 | 核心职责：发现统计显著的价格异动 |
| 反向溯源 | M12 | 核心职责：找异动的原因 |
| 趋势阶段判断 | M12 | 核心职责：判断异动处于 early/middle/late |
| 止损策略推荐 | M12 | 推荐候选止损策略，M4最终决策 |
| 止损策略选定 | M4 | M4根据风险预算+市场规则做最终决策 |
| 交易执行规则 | core/market_rules | T+1/涨跌停/最小手数 |
| 胜率统计/复盘 | M6 | 按origin/anomaly_type/market交叉统计 |
| 策略参数回测 | M7 | 验证历史异动收益 |

---

## 二、第一性原理

### 10条不可违反的原则

1. **价格是最终验证** — 市场已用真金白银投票的信息比分析更可信
2. **溯因必须有证据** — 每次补牢必须连到明确原因，无因追高=赌博
3. **止损比入场更重要** — 补牢入场偏晚，止损必须更紧
4. **趋势阶段是核心判断** — early可补，middle谨慎，late放弃
5. **市场规则不可违反** — T+1/涨跌停/最小手数由 core/market_rules 统一管理
6. **不是追高** — 异动已消耗大部分空间时，选择不入场
7. **多策略平行验证** — 推荐止损策略候选列表，M4最终决策
8. **信号溯源** — 每笔补牢持仓标注 `origin="opportunity_catcher"`
9. **与M3协作不替代** — 趋势持续性判断复用M3，不自建判断逻辑
10. **埋点标签供复盘** — M6可按 anomaly_type × market × trend_stage 交叉统计胜率

### 关键约束

- M12 输出的 `OpportunityObject` 的 `origin` 字段必须为 `"opportunity_catcher"`
- 涨停股不入场，标记为 `watch` 并附 `EntryConstraint(reason="limit_up")`
- 空结果 `[]` 是合法输出 — 没有可补牢的机会 = 不入场
- M12 不直接开仓，必须经过 M4→M9 流程

---

## 三、市场差异化策略

| | A股 | 港股 | 美股 |
|---|---|---|---|
| 盘中扫描 | ✅ 每30分钟，涨停标记观察 | ✅ 每30分钟 | ✅ 每30分钟（北京时间夜间） |
| 盘后扫描 | ✅ 15:30全量 | ✅ 16:30 | ✅ 次日早晨 |
| 数据源 | Baostock日线 | YFinance | YFinance |
| T+N | T+1 | T+0 | T+0 |
| 止损候选 | 5%/ATR×2/次日低开3% | 3%/ATR×1.5/分时破位 | 2%/ATR×1/VWAP破位 |
| 入场 | 盘后发现→次日开盘 | 异动确认→立即 | 异动确认→立即 |
| 涨停处理 | 标记观察池，不入场 | N/A | N/A |

### A股两轮处理机制

**盘中（9:30-15:00）**：
- 快速异动检测（涨幅>5%且量比>2）
- 涨停股？标记"无法入场"，加入观察池
- 未涨停但有异动？快速溯源（30分钟内完成）
- 趋势判断early？次日开盘挂单（T+1入场）

**盘后（15:30）**：
- 全量异动扫描（所有A股）
- 对盘中已标记的异动做更深入分析
- 发现盘中遗漏的N日累计异动
- 所有判断结果入库，次日执行

---

## 四、数据模型

### 新增枚举

```python
class SignalType:
    ANOMALOUS_ACTIVITY = "anomalous_activity"  # 价格异动

class SourceType:
    MARKET_MONITOR = "market_monitor"  # 行情监控

class TrendStage(str, Enum):
    EARLY = "early"      # 趋势早期：可补
    MIDDLE = "middle"    # 趋势中期：谨慎
    LATE = "late"        # 趋势晚期：放弃
```

### 新增数据结构

```python
class PriceAnomaly(BaseModel):
    """价格异动事件"""
    anomaly_id: str
    instrument: str
    market: Market
    anomaly_type: str          # daily_surge / n_day_breakout / volume_surge
    anomaly_date: date
    price_change_pct: float
    atr_multiple: float
    sigma_multiple: float
    volume_ratio: float
    baseline_price: float
    anomaly_price: float

class CausationResult(BaseModel):
    """反向溯源结果"""
    anomaly: PriceAnomaly
    causes: List[MarketSignal]
    unexplained_ratio: float   # 无法解释的涨幅比例 0-1
    confidence: float          # 溯源置信度

class TrendAssessment(BaseModel):
    """趋势阶段判断"""
    anomaly: PriceAnomaly
    stage: TrendStage
    remaining_upside_pct: float
    catalyst_persistence: str  # continuing / one_time / uncertain
    similar_cases: List[str]

class EntryConstraint(BaseModel):
    """入场约束"""
    reason: str                # "limit_up" / "t_staged" / "insufficient_data"
    expected_entry_time: Optional[datetime]
    monitoring_fields: dict

class RetroOpportunity(BaseModel):
    """补牢机会（M12最终输出）"""
    opportunity: OpportunityObject
    anomaly: PriceAnomaly
    causation: CausationResult
    trend: TrendAssessment
    origin: str = "opportunity_catcher"
    stop_loss_candidates: List[StopLossConfig]  # M12推荐，M4最终决策
    # 埋点标签
    anomaly_type: str
    market: Market
    trend_stage: TrendStage
    causation_type: str
    causation_confidence: float
    volume_ratio: float
    atr_multiple: float
    sigma_multiple: float
```

### OpportunityObject 扩展

```python
class OpportunityObject(BaseModel):
    # ... 已有字段 ...
    origin: str = "m3_judgment"  # 新增：来源标记
    entry_constraint: Optional[EntryConstraint] = None  # 新增：入场约束
```

---

## 五、异动检测算法

```
每日盘后扫描（A股15:30，港股16:30，美股次日早晨）：

对全市场股票：

1. 计算统计基线：
   - 20日收益率均值 μ 和标准差 σ
   - 14日ATR（平均真实波幅）
   - 20日成交量均值

2. 异动判定（双重条件）：
   条件A: N日涨幅 > 2σ        （统计显著性）
   条件B: 日涨幅 > 2×ATR      （波动率自适应）
   条件C: 成交量 > 1.5×均量   （量价配合）

   通过条件: A AND B AND C

3. 过滤噪音：
   - 排除ST/*ST
   - 排除上市<60天的次新股
   - 排除涨跌停（无法入场，标记观察池）
   - 排除单日事件型冲高回落

盘中扫描（每30分钟）：
   快速检测当日涨幅>5%且量比>2的股票
   涨停股标记观察池
```

---

## 六、反向溯源流程

```
对每个异动股票：

1. M0定向采集：
   - A股: AkshareNewsProvider(symbol=stock_code)
   - 港股: FinnhubProvider.fetch_company_news(symbol)
   - 美股: FinnhubProvider.fetch_company_news(symbol)
   - 补充: RSS搜索(stock_name keyword)

2. M1解码：对采集到的新闻运行 SignalDecoder

3. M10情绪：获取当前恐贪指数
   - 极度恐惧 + BULLISH异动 = 反转信号

4. 溯源置信度：
   - 完全解释(cause_match > 80%): confidence = 0.8
   - 部分解释(50-80%): confidence = 0.5
   - 无法解释(< 50%): confidence = 0.2，放弃
```

---

## 七、趋势阶段判断

```
判断为 EARLY（可补）：
  - 涨幅在统计异动的第1-2天
  - 溯源原因具有持续性（政策利好、产业趋势）
  - M3判断BULLISH且置信度>0.7
  - 历史案例平均后续空间>5%
  - 恐贪指数不处于极端贪婪

判断为 MIDDLE（谨慎）：
  - 涨幅在异动第3-5天
  - 原因部分可持续
  - 预期剩余空间 3-5%

判断为 LATE（放弃）：
  - 涨幅>5天连续上涨
  - 原因为一次性事件
  - 预期剩余空间<3%
  - 或恐贪指数极端贪婪
```

---

## 八、文件结构

```
m12_opportunity_catcher/
├── __init__.py
├── PRINCIPLES.md              — 第一性原理文档
├── DESIGN.md                  — 本设计文档
├── IMPLEMENTATION_PLAN.md     — 实施计划
├── anomaly_detector.py        — 异动检测
├── backward_causation.py      — 反向溯源
├── trend_stage.py             — 趋势阶段判断
├── catcher_engine.py          — 主引擎编排
└── market_strategies.py       — 市场差异化策略配置
```

---

## 九、与现有模块的集成点

| 集成点 | 模块 | 方式 |
|--------|------|------|
| 定向新闻采集 | M0 | 复用 AkshareNewsProvider(symbol=code) / FinnhubProvider.fetch_company_news() |
| 信号解码 | M1 | 复用 SignalDecoder.decode() |
| 信号存储 | M2 | 异动信号存入 SignalStore，origin标记为 market_monitor |
| 因果图谱检索 | M2 | 复用 query_causal_patterns() |
| 案例检索 | M2 | 复用 query_similar_cases() |
| 持续性判断 | M3 | 复用 JudgmentEngine.judge() |
| 行动设计 | M4 | M4根据RetroOpportunity选择止损策略 |
| 市场规则 | core/market_rules | T+1/涨跌停/最小手数 |
| 模拟交易 | M9 | 多策略平行模拟对比 |
| 情绪面 | M10 | 恐贪指数作为趋势判断输入 |
| 复盘归因 | M6 | 按 origin/anomaly_type/market/trend_stage 交叉统计 |
| 价格数据 | M9/price_feed | Baostock(A股日线) + YFinance(港股/美股) |
| 日常编排 | run_daily_pipeline | 盘后流程新增M12步骤 |
| 可视化 | pipeline/dashboard | 新增补牢机会tab |

---

## 十、不在本模块范围内的事项

- M4止损策略最终决策（M4职责）
- M6复盘归因逻辑（M6按origin字段统计）
- M7回测框架（M7职责）
- M1.5→M3管道Bug修（单独修复）

---

## 十一、实现追踪（对照本设计文档的落实情况）

> 追踪日期：2026-04-28
> 以下记录当前实现状态与设计目标的对齐情况。

### 数据流实现对照

| 设计目标 | 当前实现状态 | 备注 |
|----------|-------------|------|
| M12异动检测 (AnomalyDetector) | ✅ 已实现 | ATR×2 + 2σ + 1.5×量比 |
| M12反向溯源 (BackwardCausation) | ✅ 已实现 | 编排M0定向采集→M1解码→M2查询 |
| M0定向采集 | ✅ 已实现 | AKShare(A股)/Finnhub(港股美股) |
| M1 LLM解码 | ✅ 已实现 | SignalDecoder自动初始化；LLM不可用时降级到简化信号 |
| M2存储 | ✅ 已实现 | BackwardCausation._save_signals_to_store()写回M2 |
| M3判断 (JudgmentEngine) | ✅ 已实现 | CatcherEngine自动初始化JudgmentEngine，有因信号送M3 judge |
| M3认为不是机会时放弃 | ✅ 已实现 | m3_results为空列表时return None |
| M3不可用时降级 | ✅ 已实现 | _build_opportunity()作为降级路径，log标注"M12 fallback" |
| 趋势阶段判断 (TrendAssessor) | ✅ 已实现 | early/middle/late三阶段 |
| LATE阶段放弃 | ✅ 已实现 | |
| 无因放弃 | ✅ 已实现 | confidence=0.0 或 causation_type=="unexplained" |
| 止损策略推荐 | ✅ 已实现 | MarketAnomalyStrategy提供候选列表 |
| M12→M4→M9桥接 | ✅ 已实现 | pipeline/opportunity_to_position.py |
| M12→M4止损委托 | ✅ 已实现 | stop_loss_candidates传给M4 |
| 决策日志系统 | ✅ 已实现 | pipeline/decision_log.py 全链路5步记录+每日结构化报告 |
| Dashboard补牢tab决策链路 | ✅ 已实现 | 每个异动expander内显示5步决策链+结果 |
| Dashboard决策追踪tab | ✅ 已实现 | 每日报告概览+筛选+汇总表 |

### 架构决策记录

**决策1：M12置信度评估 → 改为有因/无因二分**
- 设计文档不包含_confidence打分，当前实现已改为binary:
  - 有因 = confidence=1.0 → 信号送M3量化
  - 无因 = confidence=0.0 → 放弃
- 理由：置信度打分是M3的职责，M12不应越俎代庖

**决策2：M3为主路径，_build_opportunity为降级路径**
- 默认自动初始化JudgmentEngine（M3）和SignalStore（M2）
- LLM不可用（超时/额度不足）时降级到硬编码规则
- 降级路径_build_opportunity()标注为fallback，log明确提示

**决策3：溯源信号写回M2**
- BackwardCausation._save_signals_to_store()将M0采集+M1解码的信号写回SignalStore
- 后续M3 judge可查询这些历史信号做判断

### 待完善项

| 项目 | 状态 | 说明 |
|------|------|------|
| M9多策略平行模拟对比 | ❌ 未实现 | 设计文档要求多止损候选平行模拟，当前M4只选一个策略 |
| 盘中A股涨停→观察池标记 | ✅ 已实现 | is_limit_up时标记EntryConstraint |
| 港股/美股盘中扫描 | ✅ 已实现 | market_strategies.py有差异化配置 |
| M10情绪面作为趋势判断输入 | ⚠️ 部分实现 | TrendAssessor接收sentiment_data但未深度集成 |
| M6按origin/anomaly_type/market交叉统计 | ❌ 未实现 | M6复盘接口存在但未接入M12标签 |
| 涨停股隔日开盘挂单 | ❌ 未实现 | EntryConstraint有expected_entry_time但未接入M9 |
| 决策追踪Dashboard | ✅ 已实现 | 新增决策追踪tab + 补牢tab显示决策链路 |
| 决策日志系统 | ✅ 已实现 | pipeline/decision_log.py 全链路记录+每日报告 |
- 新数据模型定义以外的schemas变更