# Phase 3: 信息不对称优势实现计划

> **核心目标**: 从非财经信息中提取隐含信号，实现二阶/三阶推理
> **关键洞察**: 隐性信号需要可追溯 + 二次验证
> **时间**: 2026-04-24 开始

---

## 🎯 架构设计（最终版）

### 数据流
```
原始文章（非财经）
  ↓ M0采集
原始数据
  ↓ M1解码
显性信号（一阶信息）
  ↓ M1.5推理（新增）
隐性信号（二阶/三阶信息）+ 初步置信度 + 推理链
  ↓ M2存储
所有信号（显性+隐性，可追溯）
  ↓ M3验证+判断
验证后的信号（基于历史案例调整置信度）→ 投资机会
```

### 关键设计决策
1. **M1.5职责**: 发散推理 + 初步置信度（基于推理链强度）
2. **M2职责**: 存储所有信号（包括低置信度的隐性信号）
3. **M3职责**: 验证隐性信号（基于历史案例）+ 判断机会

---

## 📋 实施计划

### 1. M0扩展数据源（P0）

#### 目标
从财经新闻扩展到非财经信息源，获取信息不对称优势

#### 数据源分类

##### ✅ 已有数据源
- **财经**: AKShare（A股新闻）、Finnhub（港股/美股新闻）
- **国际**: Finnhub（市场新闻）

##### ➕ 新增数据源

###### 政策类（P0）
| 数据源 | 类型 | 价值 | 实现方式 |
|--------|------|------|---------|
| 新华社 | RSS/API | 政策风向、外交动态 | RSS或爬虫 |
| 发改委 | 官网 | 产业政策、投资方向 | 爬虫 |
| 外交部 | 官网 | 外交访问、国际合作 | 爬虫 |

**示例**:
```
原始信息: "外交部：中沙签署新能源合作备忘录"
显性信号: Signal(type="外交合作", sector="新能源")
隐性信号: 
  - Signal(type="订单预期", affected=["隆基绿能"], confidence=0.6)
  - Signal(type="供应链受益", affected=["通威股份"], confidence=0.5)
```

###### 技术类（P1）
| 数据源 | 类型 | 价值 | 实现方式 |
|--------|------|------|---------|
| 36氪 | RSS/API | 技术突破、创业动态 | RSS |
| 虎嗅 | RSS | 行业分析、趋势洞察 | RSS |
| 学术期刊 | API | 前沿技术、科研突破 | arXiv API |

**示例**:
```
原始信息: "清华团队钙钛矿电池效率突破25%"
显性信号: Signal(type="技术突破", sector="光伏")
隐性信号:
  - Signal(type="技术替代风险", affected=["传统硅料企业"], confidence=0.4)
  - Signal(type="新材料需求", affected=["钙钛矿材料商"], confidence=0.7)
```

###### 社会类（P2）
| 数据源 | 类型 | 价值 | 实现方式 |
|--------|------|------|---------|
| 微博热搜 | API | 社会情绪、消费趋势 | 微博API |
| 小红书 | 爬虫 | 消费偏好、品牌口碑 | 爬虫 |

**示例**:
```
原始信息: "微博热搜：#年轻人开始养生#"
显性信号: Signal(type="消费趋势", sector="健康")
隐性信号:
  - Signal(type="需求增长", affected=["保健品公司"], confidence=0.6)
  - Signal(type="品类扩张", affected=["健身器材"], confidence=0.5)
```

#### 实施步骤
1. **本周**: 实现新华社Provider（RSS）
2. **下周**: 实现发改委/外交部Provider（爬虫）
3. **2周后**: 实现36氪/虎嗅Provider（RSS）
4. **3周后**: 实现微博/小红书Provider（API/爬虫）

---

### 2. 新增M1.5模块（P0）

#### 目标
从显性信号推理隐性信号，实现二阶/三阶推理

#### 核心组件

##### 2.1 隐性信号推理器
```python
class ImplicitSignalInferencer:
    """隐性信号推理器"""
    
    def __init__(self, 
                 industry_graph: IndustryGraph,
                 llm_client: LLMClient):
        self.industry_graph = industry_graph
        self.llm_client = llm_client
    
    def infer(self, explicit_signal: Signal) -> List[Signal]:
        """
        从显性信号推理隐性信号
        
        返回: 隐性信号列表（带初步置信度和推理链）
        """
        # 1. 查询产业链图谱
        related_entities = self.industry_graph.query(explicit_signal)
        
        # 2. LLM多阶推理
        reasoning_result = self._llm_multi_stage_reasoning(
            explicit_signal, 
            related_entities
        )
        
        # 3. 生成隐性信号
        implicit_signals = []
        for reasoning_chain in reasoning_result.chains:
            signal = Signal(
                type=reasoning_chain.signal_type,
                affected=reasoning_chain.affected_entities,
                confidence=self._evaluate_chain_strength(reasoning_chain),
                metadata={
                    "reasoning_chain": reasoning_chain.steps,
                    "source_signal": explicit_signal.id,
                    "is_implicit": True
                }
            )
            implicit_signals.append(signal)
        
        return implicit_signals
    
    def _llm_multi_stage_reasoning(self, 
                                   signal: Signal, 
                                   context: Dict) -> ReasoningResult:
        """LLM多阶推理"""
        prompt = f"""
        显性信号: {signal.to_dict()}
        产业链上下文: {context}
        
        请进行多阶推理，找出所有可能的隐含信号：
        
        L1推理（直接影响）:
        - 这个事件直接影响哪些行业/公司？
        - 影响的性质是什么（利好/利空）？
        - 影响的时间窗口是多久？
        
        L2推理（间接影响）:
        - L1的影响会传导到哪些上下游？
        - 会产生哪些替代效应？
        - 会引发哪些连锁反应？
        
        L3推理（深层影响）:
        - L2的影响会改变哪些行业格局？
        - 会催生哪些新的需求/供给？
        - 会淘汰哪些旧的模式/技术？
        
        对每个推理链，请评估：
        1. 推理的确定性（高/中/低）
        2. 影响的时间窗口（短期/中期/长期）
        3. 影响的强度（强/中/弱）
        """
        
        response = self.llm_client.chat(prompt)
        return self._parse_reasoning_result(response)
    
    def _evaluate_chain_strength(self, chain: ReasoningChain) -> float:
        """评估推理链强度"""
        # 推理链的置信度 = 每一步的置信度的乘积
        confidence = 1.0
        for step in chain.steps:
            confidence *= step.certainty
        
        # 考虑推理层级（L1 > L2 > L3）
        level_discount = {
            "L1": 1.0,
            "L2": 0.8,
            "L3": 0.6
        }
        confidence *= level_discount.get(chain.level, 0.5)
        
        return confidence
```

##### 2.2 推理链数据结构
```python
@dataclass
class ReasoningStep:
    """推理步骤"""
    description: str  # "沙特需要光伏技术"
    certainty: float  # 0.9（高确定性）
    evidence: str  # "新能源合作备忘录"

@dataclass
class ReasoningChain:
    """推理链"""
    level: str  # "L1", "L2", "L3"
    steps: List[ReasoningStep]
    signal_type: str  # "订单预期"
    affected_entities: List[str]  # ["隆基绿能", "通威股份"]
    time_window: str  # "3-6个月"
    impact_strength: str  # "强"
```

#### 实施步骤
1. **本周**: 实现ImplicitSignalInferencer基础框架
2. **本周**: 实现LLM多阶推理Prompt
3. **下周**: 实现推理链强度评估算法
4. **下周**: 集成到M1.5模块

---

### 3. M2增强知识库（P0）

#### 目标
为M1.5推理和M3验证提供知识支持

#### 知识库分类

##### ✅ 已有知识库
- **因果图谱**: 10个因果模式（政策→行业、技术→产业等）

##### ➕ 新增知识库

###### 3.1 产业链图谱（P0）
```python
class IndustryGraph:
    """产业链图谱"""
    
    def __init__(self):
        self.graph = nx.DiGraph()
    
    def add_relationship(self, 
                        entity1: str, 
                        entity2: str, 
                        rel_type: str):
        """
        添加产业链关系
        
        rel_type:
        - upstream: 上游供应商
        - downstream: 下游客户
        - substitute: 替代品
        - complement: 互补品
        """
        self.graph.add_edge(entity1, entity2, type=rel_type)
    
    def query(self, signal: Signal) -> Dict:
        """查询相关实体"""
        affected = signal.affected or []
        
        result = {
            "upstream": [],
            "downstream": [],
            "substitutes": [],
            "complements": []
        }
        
        for entity in affected:
            if entity in self.graph:
                for neighbor in self.graph.neighbors(entity):
                    rel_type = self.graph[entity][neighbor]["type"]
                    result[rel_type].append(neighbor)
        
        return result
```

**数据来源**:
- 手动构建（核心产业链）
- 从财报/研报中提取（自动化）
- 从知识图谱API获取（如OpenKG）

**示例数据**:
```python
# 光伏产业链
industry_graph.add_relationship("通威股份", "隆基绿能", "upstream")  # 硅料→硅片
industry_graph.add_relationship("隆基绿能", "阳光电源", "upstream")  # 硅片→逆变器
industry_graph.add_relationship("隆基绿能", "晶澳科技", "substitute")  # 竞争对手
industry_graph.add_relationship("隆基绿能", "储能设备", "complement")  # 互补品
```

###### 3.2 事件→标的映射（P1）
```python
class EventTargetMapping:
    """事件→标的映射"""
    
    def __init__(self):
        self.mappings = {}
    
    def add_mapping(self, 
                   event_type: str, 
                   keywords: List[str], 
                   targets: List[str]):
        """
        添加映射规则
        
        示例:
        event_type="外交合作"
        keywords=["新能源", "光伏"]
        targets=["隆基绿能", "通威股份", "阳光电源"]
        """
        self.mappings[event_type] = {
            "keywords": keywords,
            "targets": targets
        }
    
    def query(self, signal: Signal) -> List[str]:
        """查询相关标的"""
        event_type = signal.type
        content = signal.content
        
        if event_type not in self.mappings:
            return []
        
        mapping = self.mappings[event_type]
        
        # 检查关键词匹配
        for keyword in mapping["keywords"]:
            if keyword in content:
                return mapping["targets"]
        
        return []
```

#### 实施步骤
1. **本周**: 设计产业链图谱Schema
2. **本周**: 手动构建核心产业链（光伏、新能源车、半导体）
3. **下周**: 实现IndustryGraph类
4. **下周**: 实现EventTargetMapping类
5. **2周后**: 从财报/研报中自动提取产业链关系

---

### 4. M3升级推理（P1）

#### 目标
验证隐性信号 + 多阶因果推理 + 时间窗口评估

#### 核心功能

##### 4.1 隐性信号验证
```python
class OpportunityJudge:
    def _verify_implicit_signals(self, signals: List[Signal]) -> List[Signal]:
        """基于历史案例验证隐性信号"""
        verified_signals = []
        
        for signal in signals:
            if not signal.metadata.get("is_implicit"):
                # 显性信号直接通过
                verified_signals.append(signal)
                continue
            
            # 查询历史案例
            similar_cases = self.case_library.query(signal)
            
            if not similar_cases:
                # 没有历史案例，使用初步置信度
                verified_signals.append(signal)
                continue
            
            # 计算历史成功率
            success_rate = self._calculate_success_rate(similar_cases)
            
            # 贝叶斯更新
            prior = signal.confidence  # 先验（来自M1.5）
            likelihood = success_rate  # 似然（来自历史案例）
            posterior = prior * likelihood  # 后验
            
            # 更新置信度
            signal.confidence = posterior
            
            # 只保留高置信度信号
            if posterior > 0.5:
                verified_signals.append(signal)
        
        return verified_signals
    
    def _calculate_success_rate(self, cases: List[Case]) -> float:
        """计算历史案例成功率"""
        if not cases:
            return 0.5  # 默认50%
        
        success_count = sum(1 for case in cases if case.success)
        return success_count / len(cases)
```

##### 4.2 多阶因果推理
```python
def _multi_stage_causal_reasoning(self, signals: List[Signal]) -> CausalChain:
    """多阶因果推理"""
    # L1: 直接因果
    l1_effects = self._infer_direct_effects(signals)
    
    # L2: 间接因果
    l2_effects = self._infer_indirect_effects(l1_effects)
    
    # L3: 深层因果
    l3_effects = self._infer_deep_effects(l2_effects)
    
    return CausalChain(
        l1=l1_effects,
        l2=l2_effects,
        l3=l3_effects
    )
```

##### 4.3 时间窗口评估
```python
def _evaluate_time_window(self, opportunity: Opportunity) -> TimeWindow:
    """评估时间窗口"""
    # 基于信号类型评估
    signal_types = [s.type for s in opportunity.signals]
    
    if "政策" in signal_types:
        # 政策信号：3-6个月
        return TimeWindow(start=3, end=6, unit="month")
    
    elif "订单预期" in signal_types:
        # 订单信号：1-3个月
        return TimeWindow(start=1, end=3, unit="month")
    
    elif "技术突破" in signal_types:
        # 技术信号：6-12个月
        return TimeWindow(start=6, end=12, unit="month")
    
    else:
        # 默认：3个月
        return TimeWindow(start=0, end=3, unit="month")
```

##### 4.4 确定性打分
```python
def _calculate_confidence(self, signals: List[Signal]) -> float:
    """计算机会确定性"""
    # 1. 信号数量（更多信号 = 更高确定性）
    signal_count_score = min(len(signals) / 5, 1.0)
    
    # 2. 信号置信度（平均）
    avg_confidence = sum(s.confidence for s in signals) / len(signals)
    
    # 3. 信号共振（多个信号指向同一标的）
    target_counts = {}
    for signal in signals:
        for target in signal.affected:
            target_counts[target] = target_counts.get(target, 0) + 1
    
    max_resonance = max(target_counts.values()) if target_counts else 1
    resonance_score = min(max_resonance / 3, 1.0)
    
    # 4. 综合评分
    confidence = (
        signal_count_score * 0.3 +
        avg_confidence * 0.4 +
        resonance_score * 0.3
    )
    
    return confidence
```

#### 实施步骤
1. **下周**: 实现隐性信号验证
2. **2周后**: 实现多阶因果推理
3. **2周后**: 实现时间窗口评估
4. **3周后**: 实现确定性打分

---

## 📊 完整示例

### 输入：非财经信息
```
原始文章: "外交部：中沙两国签署新能源领域合作备忘录"
来源: 新华社
时间: 2026-04-24
```

### M0采集
```python
RawArticle(
    title="中沙签署新能源合作备忘录",
    content="...",
    source="新华社",
    published_at="2026-04-24"
)
```

### M1解码（显性信号）
```python
Signal(
    type="外交合作",
    sector="新能源",
    content="中沙签署新能源合作备忘录",
    confidence=0.9,  # 高确定性（官方消息）
    metadata={"is_implicit": False}
)
```

### M1.5推理（隐性信号）
```python
# L1推理：直接影响
Signal(
    type="订单预期",
    affected=["隆基绿能", "通威股份"],
    confidence=0.6,  # 中等（备忘录→合同的不确定性）
    metadata={
        "is_implicit": True,
        "reasoning_chain": [
            ReasoningStep("沙特需要光伏技术", certainty=0.9),
            ReasoningStep("国内企业可能获得订单", certainty=0.7)
        ],
        "level": "L1",
        "time_window": "3-6个月"
    }
)

# L2推理：间接影响
Signal(
    type="供应链受益",
    affected=["通威股份", "TCL中环"],
    confidence=0.5,  # 中等（依赖L1）
    metadata={
        "is_implicit": True,
        "reasoning_chain": [
            ReasoningStep("隆基获得订单", certainty=0.7),
            ReasoningStep("上游硅料需求增加", certainty=0.8)
        ],
        "level": "L2",
        "time_window": "6-9个月"
    }
)

# L3推理：深层影响
Signal(
    type="行业格局变化",
    affected=["光伏行业"],
    confidence=0.3,  # 低（长期不确定性）
    metadata={
        "is_implicit": True,
        "reasoning_chain": [
            ReasoningStep("中东市场打开", certainty=0.6),
            ReasoningStep("国内企业国际化加速", certainty=0.5)
        ],
        "level": "L3",
        "time_window": "12-24个月"
    }
)
```

### M2存储
```python
# 存储所有信号（显性+隐性）
signal_store.save(explicit_signal)
signal_store.save(implicit_signal_l1)
signal_store.save(implicit_signal_l2)
signal_store.save(implicit_signal_l3)  # 即使置信度低也存储
```

### M3验证+判断
```python
# 1. 验证隐性信号
verified_signals = judge._verify_implicit_signals([
    explicit_signal,
    implicit_signal_l1,
    implicit_signal_l2,
    implicit_signal_l3
])

# 查询历史案例：
# - 2023年中沙合作 → 6个月后隆基获得订单（成功）
# - 2022年中印合作 → 未获得订单（失败）
# 成功率 = 1/2 = 0.5

# 更新置信度：
# implicit_signal_l1.confidence = 0.6 * 0.5 = 0.3（降低）
# implicit_signal_l2.confidence = 0.5 * 0.5 = 0.25（过滤）
# implicit_signal_l3.confidence = 0.3 * 0.5 = 0.15（过滤）

# 2. 综合信号，判断机会
opportunity = judge._judge_opportunity(verified_signals)

# 结果：信号不足，未形成机会
# 原因：隐性信号置信度被历史案例降低
```

### 输出
```python
# 本次未形成机会
# 但所有信号已存入M2，可追溯

# 如果未来出现新的信号：
# - "隆基绿能公告：与沙特签署10亿美元订单"
# 则M3会重新评估，可能形成机会
```

---

## 🎯 成功标准

### 定量指标
1. **数据源覆盖**: 至少5个非财经数据源
2. **隐性信号生成率**: 每个显性信号平均生成2-3个隐性信号
3. **推理链深度**: 支持L1/L2/L3三阶推理
4. **验证准确率**: 隐性信号验证后的准确率 > 60%

### 定性指标
1. **信息不对称优势**: 能从非财经信息中提前发现机会
2. **可追溯性**: 所有隐性信号可追溯到推理链和显性信号
3. **可解释性**: 用户能理解推理过程和置信度来源

---

## 📅 时间表

### Week 1（本周）✅ 已完成
- [x] M0: 实现新华社Provider
- [x] M1.5: 实现ImplicitSignalInferencer框架
- [x] M1.5: 设计LLM多阶推理Prompt
- [x] M2: 设计产业链图谱Schema
- [x] M2: 手动构建核心产业链（光伏、新能源车）

### Week 2（下周）
- [ ] M0: 实现发改委/外交部Provider
- [ ] M1.5: 实现推理链强度评估
- [ ] M1.5: 集成到完整流程
- [ ] M2: 实现IndustryGraph类
- [ ] M3: 实现隐性信号验证

### Week 3（2周后）
- [ ] M0: 实现36氪/虎嗅Provider
- [ ] M2: 从财报/研报中自动提取产业链
- [ ] M3: 实现多阶因果推理
- [ ] M3: 实现时间窗口评估

### Week 4（3周后）
- [ ] M0: 实现微博/小红书Provider
- [ ] M3: 实现确定性打分
- [ ] 端到端测试
- [ ] 文档和示例

---

## 🚀 下一步

**立即开始**: 
1. M0: 实现新华社Provider（RSS）
2. M1.5: 设计ImplicitSignalInferencer接口
3. M2: 设计产业链图谱Schema

**需要确认**:
1. LLM多阶推理的Prompt设计
2. 产业链图谱的数据来源
3. 历史案例库的构建方式
