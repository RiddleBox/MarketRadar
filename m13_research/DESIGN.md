# M13 深度调研 — 设计文档

> **模块代号**: M13 (Research Agent)
> **创建日期**: 2026-05-07
> **状态**: 设计阶段

---

## 一、模块定位

### 一句话描述

**信息补全是决策基础** — 当发现潜在机会时，主动搜索验证信息，用多维数据提升判断质量。

### 与现有模块的关系

```
M1轨道（新闻驱动）：
  M0(采集) → M1(解码) → M1.5(推理) → [M13调研验证] → M2(存储) → M3(判断) → [M13最终验证] → M4(行动)

M12轨道（价格驱动）：
  M12(异动检测) → M12(反向溯源) → [M13调研补充] → M12(趋势判断) → M3(判断) → [M13最终验证] → M4(行动)
```

M13是**横跨两个轨道的验证层**，在关键决策点主动补全信息。

### 模块边界

| 职责 | 所属模块 | 说明 |
|------|---------|------|
| 定向信息搜索 | M13 | 核心职责：按股票代码搜索研报/新闻/财报 |
| 语义搜索 | M13 | 核心职责：基于上下文的NL主题搜索 |
| 信息结构化 | M13 | 核心职责：整理为结构化报告 |
| LLM综合分析 | M13 | 核心职责：分析调研结果，评估置信度 |
| 机会判断 | M3 | M3根据调研结果做最终判断 |
| 趋势判断 | M12 | M12根据调研结果判断趋势 |
| 行动决策 | M4 | M4根据调研结果决定仓位和止损 |
| 被动采集 | M0 | M0负责定时采集，M13负责主动搜索 |

---

## 二、第一性原理

### 10条不可违反的原则

1. **信息必须可验证** — 所有调研结果必须有明确来源
2. **调研不替代判断** — M13只负责信息收集，不做最终决策
3. **成本意识** — 只在关键决策点触发，不浪费资源
4. **时效性优先** — 必须在决策窗口内返回结果
5. **置信度透明** — 必须包含置信度评估
6. **反向证据优先** — 主动寻找利空因素，避免确认偏误
7. **多源交叉验证** — 单一来源不可靠
8. **结构化输出** — 便于LLM和人类理解
9. **缓存机制** — 避免重复调研
10. **失败容错** — 单个数据源失败不影响整体

### 关键约束

- 调研超时（Level 1: 30s, Level 2: 2min, Level 3: 5min）→ 降级返回部分结果
- 同一标的24小时内已调研 → 使用缓存
- 调研队列满（>10个并发）→ 降级跳过
- 数据源全部失败 → 返回"信息不足"标记，不阻塞流程

---

## 三、触发策略

### 触发条件矩阵

| 触发点 | 条件 | 调研深度 | 超时 | 目的 |
|--------|------|---------|------|------|
| M1.5推理后 | 置信度 > 0.5 | Level 1 (快速) | 30s | 验证推理逻辑 |
| M12溯源后 | 置信度 < 0.7 | Level 2 (标准) | 2min | 补充信息 |
| M3判断后 | 置信度 > 0.5 | Level 3 (深度) | 5min | 最终验证 |

### 不触发条件

- 置信度 < 0.3 → 直接放弃
- 置信度 > 0.9 → 信息已充分
- 24小时内已调研 → 使用缓存
- 调研队列已满 → 降级跳过

---

## 四、数据模型

### 核心数据结构

```python
@dataclass
class ResearchReport:
    """调研报告"""
    # 基本信息
    symbol: str
    research_level: str              # quick/standard/deep
    triggered_by: str                # m1_5/m12/m3
    
    # 原始数据
    reports: List[Dict]              # 研报列表
    news: List[Dict]                 # 新闻列表
    fundamentals: Dict               # 基本面数据
    quote: Dict                      # 行情数据
    semantic_results: List[Dict]     # 语义搜索结果
    
    # LLM分析结果
    summary: str                     # 调研摘要（200字内）
    key_findings: List[str]          # 关键发现（3-5条）
    risk_factors: List[str]          # 风险因素（2-3条）
    confidence_assessment: str       # 置信度评估说明
    
    # 置信度调整
    confidence_multiplier: float     # 置信度乘数（0.5-2.0）
    confidence_delta: float          # 置信度增量（-0.3 ~ +0.3）
    has_major_negative: bool         # 是否发现重大利空
    
    # 元数据
    research_time: datetime
    data_sources: List[str]
    cache_hit: bool
    timeout: bool                    # 是否超时
    partial_result: bool             # 是否部分结果

@dataclass
class ResearchContext:
    """调研上下文"""
    symbol: str
    opportunity_context: str         # 机会描述
    research_level: str
    triggered_by: str
    timeout_seconds: int
```

---

## 五、调研流程

### Level 1: 快速验证（< 30秒）

```python
def quick_research(symbol: str, context: str) -> ResearchReport:
    """
    快速验证流程（M1.5推理后）
    
    目标：快速判断推理是否合理
    """
    # 1. 搜索最近5篇研报标题（5s）
    reports = data_manager.get_research_reports(symbol, limit=5)
    
    # 2. 查询最新财报关键指标（5s）
    fundamentals = data_manager.get_fundamentals(symbol)
    quote = data_manager.get_quote(symbol)
    
    # 3. LLM快速分析（15s）
    analysis = llm_quick_verify(
        context=context,
        reports=[r['title'] for r in reports],
        fundamentals=fundamentals
    )
    
    # 4. 返回结果
    return ResearchReport(
        research_level="quick",
        summary=analysis.summary,
        confidence_multiplier=analysis.multiplier
    )
```

### Level 2: 标准调研（1-2分钟）

```python
def standard_research(symbol: str, context: str) -> ResearchReport:
    """
    标准调研流程（M12反向溯源后）
    
    目标：补充信息，提升置信度
    """
    # 1. 搜索研报（30s）
    reports = data_manager.get_research_reports(symbol, limit=10)
    
    # 2. 搜索新闻（30s）
    news = data_manager.get_news(symbol, limit=20)
    
    # 3. 查询财报（10s）
    fundamentals = data_manager.get_fundamentals(symbol)
    quote = data_manager.get_quote(symbol)
    
    # 4. LLM综合分析（40s）
    analysis = llm_standard_analyze(
        context=context,
        reports=reports,
        news=news,
        fundamentals=fundamentals
    )
    
    # 5. 返回结果
    return ResearchReport(
        research_level="standard",
        summary=analysis.summary,
        key_findings=analysis.findings,
        risk_factors=analysis.risks,
        confidence_delta=analysis.delta
    )
```

### Level 3: 深度调研（3-5分钟）

```python
def deep_research(symbol: str, context: str) -> ResearchReport:
    """
    深度调研流程（M3判断后）
    
    目标：最终验证，确保决策质量
    """
    # 1. 搜索研报（60s）
    reports = data_manager.get_research_reports(symbol, limit=20)
    
    # 2. 搜索新闻（60s）
    news = data_manager.get_news(symbol, limit=30)
    
    # 3. 查询财报（20s）
    fundamentals = data_manager.get_fundamentals(symbol)
    quote = data_manager.get_quote(symbol)
    
    # 4. 语义搜索（60s）
    semantic_query = construct_semantic_query(context, symbol)
    semantic_results = data_manager.semantic_search(
        query=semantic_query,
        channel="report",
        limit=20
    )
    
    # 5. LLM深度分析（80s）
    analysis = llm_deep_analyze(
        context=context,
        reports=reports,
        news=news,
        fundamentals=fundamentals,
        semantic_results=semantic_results
    )
    
    # 6. 返回结果
    return ResearchReport(
        research_level="deep",
        summary=analysis.summary,
        key_findings=analysis.findings,
        risk_factors=analysis.risks,
        confidence_assessment=analysis.assessment,
        confidence_delta=analysis.delta,
        has_major_negative=analysis.has_major_negative
    )
```

---

## 六、LLM分析策略

### 快速验证Prompt

```
你是一个专业的投资分析师。请快速验证以下推理是否合理：

【推理】
{context}

【研报标题】
{report_titles}

【基本面】
PE: {pe}, PB: {pb}, ROE: {roe}

请在30秒内回答：
1. 推理逻辑是否成立？（是/否/部分成立）
2. 是否有明显反向证据？（是/否）
3. 置信度调整建议（0.5-2.0倍）

输出格式：JSON
```

### 标准分析Prompt

```
你是一个专业的投资分析师。请综合分析以下信息：

【机会描述】
{context}

【研报摘要】（最近10篇）
{reports_summary}

【相关新闻】（最近20条）
{news_summary}

【基本面数据】
{fundamentals}

请分析：
1. 关键发现（3-5条，每条50字内）
2. 风险因素（2-3条，每条50字内）
3. 置信度调整（-0.3 ~ +0.3）
4. 综合摘要（200字内）

输出格式：JSON
```

### 深度分析Prompt

```
你是一个资深投资分析师。请对以下机会进行最终验证：

【机会描述】
{context}

【研报分析】（最近20篇）
{reports_analysis}

【新闻分析】（最近30条）
{news_analysis}

【基本面数据】
{fundamentals}

【行业趋势】（语义搜索结果）
{semantic_results}

请深度分析：
1. 关键发现（5条，每条100字内）
2. 风险因素（3条，每条100字内）
3. 是否发现重大利空？（是/否）
4. 置信度评估说明（200字）
5. 置信度调整（-0.3 ~ +0.3）
6. 综合摘要（300字内）

输出格式：JSON
```

---

## 七、缓存策略

### 缓存键设计

```python
cache_key = f"research:{symbol}:{research_level}:{date}"
```

### 缓存规则

- **Level 1 (快速)**: 缓存6小时
- **Level 2 (标准)**: 缓存12小时
- **Level 3 (深度)**: 缓存24小时

### 缓存失效条件

- 该标的有新的重大新闻（M0采集到）
- 价格异动超过5%（M12检测到）
- 手动清除缓存

---

## 八、性能优化

### 并发控制

- 最大并发调研数：10个
- 超过限制时：降级跳过或排队等待
- 优先级：Level 3 > Level 2 > Level 1

### 超时处理

- Level 1: 30s超时 → 返回"信息不足"
- Level 2: 2min超时 → 返回部分结果
- Level 3: 5min超时 → 返回部分结果

### 降级策略

```
数据源失败 → 降级到其他数据源
全部数据源失败 → 返回"信息不足"标记
LLM超时 → 返回原始数据，不做分析
```

---

## 九、集成点

### M1.5集成

```python
# m1_5_implicit_reasoner/implicit_reasoner.py

def reason_implicit_signals(self, macro_news):
    signals = self._reason(macro_news)
    
    # 对高置信度推理进行快速验证
    for signal in signals:
        if signal.confidence > 0.5:
            research = self.m13_agent.quick_research(
                symbol=signal.instrument,
                context=f"宏观事件: {macro_news.title}\n推理: {signal.reasoning}"
            )
            signal.confidence *= research.confidence_multiplier
            signal.reasoning += f"\n【调研】{research.summary}"
    
    return signals
```

### M12集成

```python
# m12_opportunity_catcher/catcher_engine.py

def _build_opportunity(self, anomaly, causation, trend):
    # 如果溯源置信度不够，触发标准调研
    if causation.confidence < 0.7:
        research = self.m13_agent.standard_research(
            symbol=anomaly.instrument,
            context=f"价格异动{anomaly.price_change_pct}%"
        )
        causation.confidence += research.confidence_delta
        # 添加调研结果到机会描述
    
    return opportunity
```

### M3集成

```python
# m3_reasoning_engine/reasoning_engine.py

def judge_opportunity(self, signals):
    opportunity = self._judge(signals)
    
    # 对生成的机会进行最终验证
    if opportunity.confidence > 0.5:
        research = self.m13_agent.deep_research(
            symbol=opportunity.instrument,
            context=opportunity.reasoning
        )
        opportunity.confidence += research.confidence_delta
        opportunity.reasoning += f"\n\n【最终验证】\n{research.summary}"
        
        if research.has_major_negative:
            opportunity.confidence *= 0.5
    
    return opportunity
```

---

## 十、监控指标

### 性能指标

- 调研平均耗时（按Level分）
- 调研成功率
- 缓存命中率
- 数据源可用率

### 质量指标

- 置信度调整分布
- 发现重大利空的比例
- 调研后机会转化率
- 调研后持仓胜率

### 成本指标

- API调用次数
- LLM Token消耗
- 调研触发频率

---

## 十一、关键决策

### 为什么分三个Level？

- 不同决策点对信息完整性要求不同
- 平衡调研深度和时效性
- 避免过度调研浪费资源

### 为什么不在M0采集时就调研？

- M0是被动采集，不知道哪些标的重要
- 调研成本高，不能对所有标的都调研
- 只在发现潜在机会时才触发

### 为什么不直接集成到M3？

- M13是横跨多个模块的通用能力
- M1.5、M12、M3都需要调研
- 独立模块便于复用和维护

### 为什么需要缓存？

- 同一标的短期内基本面不会大变
- 避免重复调研浪费资源
- 提升响应速度

---

## 十二、v2 补充：为 M12 提供异动证据搜索（2026-05-18）

> 背景：M12 价格异动轨道需要的是“这个股票为什么刚刚动了”的快速证据搜索，不一定是完整研报/财报调研。现有 `quick_research()`、`standard_research()`、`deep_research()` 偏验证和补全，不能完全覆盖异动发生当下的因果搜索需求。
>
> v2.1 修订：`search_movement_evidence()` 是 P1/P2 的目标能力，不是 P0 的前置依赖。P0 先由 M12 直接接入 Yahoo ticker RSS 和 Finnhub key-aware fallback，等动态搜索、缓存、ranking、去重需要跨模块复用时，再迁移到 M13。

### 12.1 新增能力定位

M13 在 Track 2 v2 的完整形态中新增轻量能力：

```text
MovementContext
  -> search_movement_evidence()
  -> EvidenceBundle
```

该能力服务于 M12 的“反向溯源前置证据获取”，重点是快、准、可降级、可追踪查询过程。该能力应在 P1/P2 实现，不阻塞 P0。

### 12.2 与现有研究接口的区别

| 接口 | 触发点 | 目标 | 输出 |
|------|--------|------|------|
| `quick_research()` | M1.5 推理后 | 验证推理是否有明显反向证据 | `ResearchReport` |
| `standard_research()` | 初步原因已存在后 | 补充新闻/研报/基本面，提高判断质量 | `ResearchReport` |
| `deep_research()` | M3 生成机会后 | 最终验证机会质量与风险 | `ResearchReport` |
| `search_movement_evidence()` | M12 异动刚发生后 | 寻找解释该异动的候选证据 | `EvidenceBundle` |

### 12.3 建议接口

```python
def search_movement_evidence(
    context: MovementContext,
    max_items: int = 12,
    timeout_seconds: int = 20,
) -> EvidenceBundle:
    """为 M12 价格异动搜索候选解释证据。

    返回内容必须包含：
    - normalized EvidenceItem 列表
    - searched_queries
    - providers_used
    - providers_failed
    - timeout / partial_result
    """
```

### 12.4 搜索层级

| 层级 | 数据源 | 默认策略 |
|------|--------|----------|
| Tier 0 | M2 recent signals | 读取同市场/同主题近期信号作为背景 |
| Tier 1 | Finnhub company_news | 有 key 时优先，用于 US/HK ticker 新闻 |
| Tier 1 | Yahoo Finance per-ticker RSS | 无 key 兜底，覆盖 US ticker headline |
| Tier 1 | AStockSkill/EastMoney | A股 ticker 新闻 |
| Tier 2 | DuckDuckGo/Bing/NewsAPI | 动态查询 `why moving`、`jumps`、行业主题 |
| Tier 3 | 行业图谱/主题词表 | 扩展供应链、同业、板块、宏观关键词 |

P0 说明：

- Tier 1 的 Yahoo/Finnhub 先在 M12 内部实现，避免把尚未成型的搜索能力绕到 M13。
- M13 从 P1 开始接管通用搜索、缓存、排序和去重。
- `standard_research()` 仍可在已有初步原因后用于补充验证，但不承担 P0 异动溯源入口。

### 12.5 输出要求

`EvidenceBundle` 必须便于 M12 复盘：

- 保留每条证据的原始来源、URL、发布时间、抓取时间。
- 记录每个查询词，即使无结果。
- 记录失败 provider 和失败原因。
- 不直接判断“是否机会”，只给 M12/M1/M1.5/M3 使用。
- 超时返回部分结果，不阻塞 M12 主流程。

### 12.6 边界约束

M13 不做以下事情：

- 不决定 `causation_type`。
- 不决定是否进入 M3。
- 不突破 M12 的 `max_allowed_priority`。
- 不直接生成 `OpportunityObject`。

M13 可以做以下事情：

- 对证据做初步 relevance/freshness/credibility 打分。
- 缓存 ticker/query 级搜索结果。
- 为 M12 提供 normalized evidence。
- 在后续 `standard_research()` 中补充基本面、研报和反向证据。

详细 Track 2 v2 方案见 `docs/M12_TRACK2_ITERATION_PLAN_2026-05-18.md`。
