# M2 Signal Store — 第一性原理文档

> **信号的价值不因时间流逝而消失。一个三个月前的信号，可能是今天机会论点的关键一环。**

---

## 存在意义

M1 每次运行都产生信号，但市场机会的形成往往是跨时间的积累过程。

如果每次 pipeline 运行都只看"当批"信号，就会错过两类重要模式：
1. **渐进确认型**：同一个变化趋势在多个批次中逐渐增强（如产业政策逐步落地）
2. **多因共振型**：来自不同时间段、不同维度的信号共同构成一个机会论点

M2 的存在，是为了让系统有"记忆"——当前批次的判断可以站在历史积累的信号肩膀上。

**2026-04-18 架构矫正**：M2 不仅是"信号仓库"，更是"推理支撑层"。它存储三类数据：
1. **信号记录**：已发生的事实变化（来自M1）
2. **因果图谱**：信号A → 通常导致事件B（概率+时间窗口，来自历史统计）
3. **历史案例**：信号组合 → 演化过程 → 结果（来自M6复盘）

---

## 第一性原理

### 原则一：信号是不可变的事实记录

一旦写入 Signal Store，信号的原始内容不应被修改。

原因：信号记录的是"某时刻已发生的客观变化"，这是历史事实。如果事后发现信号有误（如信息来源不可靠），应新增一条"修正信号"，而不是覆盖原始记录。

### 原则二：event_time 是时间基准，不是 collected_time

`event_time`（事件发生时间）和 `collected_time`（收集时间）是两个独立字段。

回测时，严格使用 `event_time` 对齐历史数据。使用 `collected_time` 会导致数据泄露（例如：一个 1 月 1 日发生的事件，可能在 1 月 10 日才被收集，但回测时不应该"知道"1 月 1 日发生了这件事）。

### 原则三：高效检索，拒绝全表扫描

Signal Store 的规模会随时间线性增长。检索接口必须支持：
- 按时间范围（回测场景）
- 按市场标识（市场过滤）
- 按信号类型（精准召回）
- 按强度分数（过滤低质量信号）

不允许全表加载后在内存中过滤——这会在信号量达到数千条后成为性能瓶颈。

### 原则四：因果图谱是推理的基础（新增）

M3 的推理能力依赖于 M2 提供的因果图谱。因果图谱记录：
- **前置信号模式**：["央行行长讲话提到降准", "财政提前发债", "经济数据低于预期"]
- **后续事件**：{"event": "央行降准", "probability": 0.80, "avg_lead_time_days": 14}
- **支撑案例**：[case_id_1, case_id_2, case_id_3]

因果图谱来源：
1. **人工标注**：基于领域知识手工构建（初期）
2. **历史统计**：从M6复盘数据中自动提取（中期）
3. **LLM辅助**：用LLM分析历史案例，生成候选模式（长期）

### 原则五：历史案例是判断的证据（新增）

M3 在判断机会时，需要回答"历史上类似信号组合如何演化"。M2 存储的历史案例提供这个证据：
- **信号序列**：时间顺序的信号列表
- **演化过程**：市场如何反应、政策如何落地
- **结果**：事件是否发生、市场涨跌幅
- **经验教训**：判断对错的关键因素

案例来源：
1. **M6复盘**：每次交易后，M6生成CaseRecord写入M2
2. **手工补充**：重要历史事件的人工标注

---

## 与其他模块的关系

- **上游 M1**：每批解码完成后，通过 `save()` 写入 Signal Store
- **上游 M6**：复盘后，通过 `save_case_record()` 写入历史案例
- **下游 M3**：判断前，通过以下接口获取推理支撑：
  - `get_by_time_range()` 检索历史相关信号
  - `query_causal_patterns()` 查询匹配的因果模式
  - `query_similar_cases()` 检索历史相似案例
- **下游 M7**：回测时通过 `get_by_time_range(start, end)` 加载指定时间段的信号

---

## 核心接口（扩展）

### 信号存储（现有）
```python
def save(self, signals: List[MarketSignal]) -> None
def get_by_time_range(self, start: datetime, end: datetime) -> List[MarketSignal]
def get_by_signal_ids(self, signal_ids: List[str]) -> List[MarketSignal]
```

### 因果图谱（新增）
```python
def save_causal_pattern(self, pattern: CausalPattern) -> None
    """
    存储因果模式
    
    Args:
        pattern: CausalPattern对象，包含：
            - precursor_signals: 前置信号特征（模糊匹配）
            - consequent_event: 后续事件描述
            - probability: 历史发生概率
            - avg_lead_time_days: 平均提前天数
            - supporting_cases: 支撑案例ID列表
    """

def query_causal_patterns(self, current_signals: List[MarketSignal]) -> List[CausalPattern]
    """
    基于当前信号，查询匹配的因果模式
    
    匹配逻辑：
    1. 提取current_signals的关键特征（类型、方向、强度）
    2. 与因果图谱中的precursor_signals做相似度匹配
    3. 返回相似度>阈值的因果模式，按概率排序
    
    Returns:
        匹配的因果模式列表，每个包含：
        - 可能发生的事件
        - 概率
        - 时间窗口
        - 支撑案例
    """
```

### 历史案例（新增）
```python
def save_case_record(self, case: CaseRecord) -> None
    """
    存储历史案例
    
    Args:
        case: CaseRecord对象，包含：
            - signal_sequence: 信号序列（时间顺序）
            - evolution: 演化过程描述
            - outcome: 结果（事件是否发生、市场反应）
            - lessons: 经验教训
    """

def query_similar_cases(self, current_signals: List[MarketSignal]) -> List[CaseRecord]
    """
    基于当前信号组合，检索历史相似案例
    
    匹配逻辑：
    1. 提取current_signals的特征向量
    2. 与历史案例的signal_sequence做相似度匹配
    3. 返回Top-K相似案例
    
    Returns:
        相似案例列表，按相似度排序
    """
```

---

## 数据结构定义（新增）

```python
@dataclass
class CausalPattern:
    """因果模式：信号A → 事件B"""
    pattern_id: str
    precursor_signals: List[str]  # 前置信号特征描述
    consequent_event: str  # 后续事件描述
    probability: float  # 历史发生概率 (0-1)
    avg_lead_time_days: int  # 平均提前天数
    std_lead_time_days: int  # 时间窗口标准差
    supporting_cases: List[str]  # 支撑案例ID
    last_updated: datetime
    confidence: float  # 模式置信度 (0-1)，基于样本量

@dataclass
class CaseRecord:
    """历史案例：信号组合 → 演化 → 结果"""
    case_id: str
    date_range: tuple[datetime, datetime]
    market: str  # A_SHARE, HK, etc.
    signal_sequence: List[MarketSignal]  # 信号序列（时间顺序）
    evolution: str  # 演化过程描述
    outcome: dict  # 结果，包含：
        # - event_occurred: bool
        # - market_reaction: float (涨跌幅)
        # - time_to_event: int (天数)
    lessons: str  # 经验教训
    tags: List[str]  # 标签（如"降准", "政策宽松"）
    created_at: datetime
```

---

## 实施路径

### Phase 1：信号存储（已完成）
- ✅ SQLite 存储
- ✅ 时间范围检索
- ✅ 去重机制

### Phase 2：因果图谱（待实施）
- 🔲 定义 CausalPattern 数据结构
- 🔲 实现 save_causal_pattern() 和 query_causal_patterns()
- 🔲 手工标注初始因果图谱（10-20个常见模式）
- 🔲 从M6复盘数据中自动提取因果模式

### Phase 3：历史案例库（待实施）
- 🔲 定义 CaseRecord 数据结构
- 🔲 实现 save_case_record() 和 query_similar_cases()
- 🔲 M6复盘后自动写入案例
- 🔲 手工补充重要历史事件（2023-2024年关键案例）

### Phase 4：向量检索（长期）
- 🔲 用向量数据库替代关键词匹配
- 🔲 提升因果模式和案例检索的准确率
