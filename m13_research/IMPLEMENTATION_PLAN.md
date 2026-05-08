# M13 深度调研 — 实施计划

> **创建日期**: 2026-05-07
> **状态**: 设计完成，准备实施

---

## 实施步骤

| 步骤 | 任务 | 依赖 | 预计 | 状态 |
|------|------|------|------|------|
| 0 | 设计文档落档 | 无 | 1h | ✅ 完成 |
| 1 | core/schemas.py 新增M13数据模型 | 无 | 30min | ⏳ 待开始 |
| 2 | research_agent.py 核心调研引擎 | 步骤1 | 2h | ⏳ 待开始 |
| 3 | llm_analyzer.py LLM分析模块 | 步骤1 | 1.5h | ⏳ 待开始 |
| 4 | cache_manager.py 缓存管理 | 步骤1 | 1h | ⏳ 待开始 |
| 5 | 扩展DataProviderManager支持语义搜索 | integrations已有 | 1h | ⏳ 待开始 |
| 6 | M1.5集成：推理后快速验证 | 步骤2,3 | 30min | ⏳ 待开始 |
| 7 | M12集成：溯源后标准调研 | 步骤2,3 | 30min | ⏳ 待开始 |
| 8 | M3集成：判断后深度验证 | 步骤2,3 | 30min | ⏳ 待开始 |
| 9 | 单元测试 + 集成测试 | 步骤2-8 | 1h | ⏳ 待开始 |
| 10 | Dashboard监控页面 | 步骤2-8 | 1h | ⏳ 待开始 |

**总预计时间**: 10小时

---

## 依赖关系图

```
步骤0 (设计文档) ──────────────────────────────── ✅ 完成
     │
步骤1 (schemas) ────────────────────────────────── 可独立完成
     │
     ├─ 步骤2 (research_agent) ←── 步骤1
     │       │
     ├─ 步骤3 (llm_analyzer) ←── 步骤1
     │       │
     ├─ 步骤4 (cache_manager) ←── 步骤1
     │       │
     └─ 步骤5 (DataProvider扩展) ←── integrations已有
             │
     ┌───────┴───────┐
     │               │
步骤6 (M1.5集成) 步骤7 (M12集成) 步骤8 (M3集成)
     │               │               │
     └───────┬───────┴───────────────┘
             │
     步骤9 (测试) ←── 步骤2-8
             │
     步骤10 (Dashboard) ←── 步骤2-8
```

---

## 详细实施计划

### 步骤1: 数据模型定义（30分钟）

**文件**: `core/schemas.py`

**新增数据结构**:

```python
@dataclass
class ResearchReport:
    """调研报告"""
    symbol: str
    research_level: str              # quick/standard/deep
    triggered_by: str                # m1_5/m12/m3
    
    # 原始数据
    reports: List[Dict] = field(default_factory=list)
    news: List[Dict] = field(default_factory=list)
    fundamentals: Dict = field(default_factory=dict)
    quote: Dict = field(default_factory=dict)
    semantic_results: List[Dict] = field(default_factory=list)
    
    # LLM分析结果
    summary: str = ""
    key_findings: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    confidence_assessment: str = ""
    
    # 置信度调整
    confidence_multiplier: float = 1.0
    confidence_delta: float = 0.0
    has_major_negative: bool = False
    
    # 元数据
    research_time: datetime = field(default_factory=datetime.now)
    data_sources: List[str] = field(default_factory=list)
    cache_hit: bool = False
    timeout: bool = False
    partial_result: bool = False

@dataclass
class ResearchContext:
    """调研上下文"""
    symbol: str
    opportunity_context: str
    research_level: str              # quick/standard/deep
    triggered_by: str                # m1_5/m12/m3
    timeout_seconds: int
```

**验收标准**:
- [ ] 数据类定义完整
- [ ] 类型注解正确
- [ ] 默认值合理
- [ ] 导入测试通过

---

### 步骤2: 核心调研引擎（2小时）

**文件**: `m13_research/research_agent.py`

**核心类**:

```python
class ResearchAgent:
    """深度调研代理"""
    
    def __init__(self, data_manager, llm_analyzer, cache_manager):
        self.data_manager = data_manager
        self.llm_analyzer = llm_analyzer
        self.cache_manager = cache_manager
    
    def quick_research(self, symbol: str, context: str) -> ResearchReport:
        """Level 1: 快速验证（< 30秒）"""
        pass
    
    def standard_research(self, symbol: str, context: str) -> ResearchReport:
        """Level 2: 标准调研（1-2分钟）"""
        pass
    
    def deep_research(self, symbol: str, context: str) -> ResearchReport:
        """Level 3: 深度调研（3-5分钟）"""
        pass
    
    def _collect_data(self, symbol: str, level: str) -> Dict:
        """收集原始数据"""
        pass
    
    def _check_cache(self, symbol: str, level: str) -> Optional[ResearchReport]:
        """检查缓存"""
        pass
    
    def _save_cache(self, report: ResearchReport):
        """保存缓存"""
        pass
```

**实现要点**:
- 三个Level的调研流程
- 超时控制（使用threading.Timer或asyncio.timeout）
- 数据源失败容错
- 缓存检查和保存
- 并发控制（最多10个并发）

**验收标准**:
- [ ] 三个Level方法实现完整
- [ ] 超时控制正常工作
- [ ] 数据源失败不影响整体
- [ ] 缓存机制正常工作
- [ ] 单元测试通过

---

### 步骤3: LLM分析模块（1.5小时）

**文件**: `m13_research/llm_analyzer.py`

**核心类**:

```python
class LLMAnalyzer:
    """LLM分析器"""
    
    def __init__(self, llm_client):
        self.llm_client = llm_client
    
    def quick_verify(self, context: str, reports: List[str], 
                    fundamentals: Dict) -> Dict:
        """快速验证分析"""
        prompt = self._build_quick_prompt(context, reports, fundamentals)
        result = self.llm_client.chat(prompt, temperature=0.3)
        return self._parse_quick_result(result)
    
    def standard_analyze(self, context: str, reports: List[Dict],
                        news: List[Dict], fundamentals: Dict) -> Dict:
        """标准分析"""
        prompt = self._build_standard_prompt(context, reports, news, fundamentals)
        result = self.llm_client.chat(prompt, temperature=0.3)
        return self._parse_standard_result(result)
    
    def deep_analyze(self, context: str, reports: List[Dict],
                    news: List[Dict], fundamentals: Dict,
                    semantic_results: List[Dict]) -> Dict:
        """深度分析"""
        prompt = self._build_deep_prompt(context, reports, news, 
                                         fundamentals, semantic_results)
        result = self.llm_client.chat(prompt, temperature=0.3)
        return self._parse_deep_result(result)
    
    def _build_quick_prompt(self, ...) -> str:
        """构建快速验证Prompt"""
        pass
    
    def _build_standard_prompt(self, ...) -> str:
        """构建标准分析Prompt"""
        pass
    
    def _build_deep_prompt(self, ...) -> str:
        """构建深度分析Prompt"""
        pass
```

**实现要点**:
- 三个Level的Prompt模板
- JSON格式输出解析
- LLM超时处理
- 结果验证和容错

**验收标准**:
- [ ] 三个Prompt模板完整
- [ ] JSON解析正确
- [ ] LLM超时不阻塞
- [ ] 单元测试通过

---

### 步骤4: 缓存管理（1小时）

**文件**: `m13_research/cache_manager.py`

**核心类**:

```python
class CacheManager:
    """缓存管理器"""
    
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get(self, symbol: str, level: str) -> Optional[ResearchReport]:
        """获取缓存"""
        cache_key = self._build_key(symbol, level)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
        
        # 检查是否过期
        if self._is_expired(cache_file, level):
            cache_file.unlink()
            return None
        
        # 读取缓存
        data = json.loads(cache_file.read_text(encoding='utf-8'))
        return ResearchReport(**data)
    
    def set(self, report: ResearchReport):
        """保存缓存"""
        cache_key = self._build_key(report.symbol, report.research_level)
        cache_file = self.cache_dir / f"{cache_key}.json"
        
        data = asdict(report)
        cache_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding='utf-8'
        )
    
    def invalidate(self, symbol: str):
        """清除指定标的的所有缓存"""
        for level in ['quick', 'standard', 'deep']:
            cache_key = self._build_key(symbol, level)
            cache_file = self.cache_dir / f"{cache_key}.json"
            if cache_file.exists():
                cache_file.unlink()
    
    def _build_key(self, symbol: str, level: str) -> str:
        """构建缓存键"""
        date = datetime.now().strftime("%Y%m%d")
        return f"research_{symbol}_{level}_{date}"
    
    def _is_expired(self, cache_file: Path, level: str) -> bool:
        """检查是否过期"""
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        age = datetime.now() - mtime
        
        # Level 1: 6小时, Level 2: 12小时, Level 3: 24小时
        ttl = {'quick': 6, 'standard': 12, 'deep': 24}
        return age.total_seconds() > ttl[level] * 3600
```

**验收标准**:
- [ ] 缓存读写正常
- [ ] 过期检查正确
- [ ] 缓存清除正常
- [ ] 单元测试通过

---

### 步骤5: DataProvider扩展（1小时）

**文件**: `integrations/providers/astock_skill_provider.py`

**新增方法**:

```python
class AStockSkillProvider(DataProvider):
    
    def semantic_search(self, query: str, channel: str = "report", 
                       limit: int = 20) -> List[Dict]:
        """
        NL语义搜索（需要iwencai API Key）
        
        Args:
            query: 自然语言查询，如"人形机器人 减速器 2026"
            channel: report/news/announcement
            limit: 返回数量
        
        Returns:
            搜索结果列表
        """
        if not self._iwencai_available:
            logger.warning("iwencai不可用，语义搜索功能受限")
            return []
        
        try:
            # 调用iwencai API
            results = iwencai_search(query, channel, limit)
            
            # 格式化结果
            formatted = []
            for r in results:
                formatted.append({
                    "title": r.get("title", ""),
                    "content": r.get("content", ""),
                    "published_at": r.get("publish_date", ""),
                    "source": r.get("extra", {}).get("organization", ""),
                    "url": r.get("url", ""),
                    "score": r.get("score", 0),
                    "provider": "astock_skill"
                })
            
            return formatted
            
        except Exception as e:
            logger.error(f"语义搜索失败: {e}")
            return []
```

**验收标准**:
- [ ] 方法签名正确
- [ ] iwencai集成正常（如果有API Key）
- [ ] 无API Key时降级处理
- [ ] 单元测试通过

---

### 步骤6-8: 模块集成（各30分钟）

#### 步骤6: M1.5集成

**文件**: `m1_5_implicit_reasoner/implicit_reasoner.py`

```python
class ImplicitReasoner:
    
    def __init__(self, ..., m13_agent: ResearchAgent = None):
        ...
        self.m13_agent = m13_agent
    
    def reason_implicit_signals(self, macro_news):
        signals = self._reason(macro_news)
        
        # 对高置信度推理进行快速验证
        if self.m13_agent:
            for signal in signals:
                if signal.confidence > 0.5:
                    try:
                        research = self.m13_agent.quick_research(
                            symbol=signal.instrument,
                            context=f"宏观事件: {macro_news.title}\n推理: {signal.reasoning}"
                        )
                        signal.confidence *= research.confidence_multiplier
                        signal.research_summary = research.summary
                    except Exception as e:
                        logger.warning(f"M13调研失败: {e}")
        
        return signals
```

#### 步骤7: M12集成

**文件**: `m12_opportunity_catcher/catcher_engine.py`

```python
class OpportunityCatcherEngine:
    
    def __init__(self, ..., m13_agent: ResearchAgent = None):
        ...
        self.m13_agent = m13_agent
    
    def _build_opportunity(self, anomaly, causation, trend, strategy):
        # 如果溯源置信度不够，触发标准调研
        if self.m13_agent and causation.confidence < 0.7:
            try:
                research = self.m13_agent.standard_research(
                    symbol=anomaly.instrument,
                    context=f"价格异动{anomaly.price_change_pct}%"
                )
                causation.confidence += research.confidence_delta
                # 添加调研结果
            except Exception as e:
                logger.warning(f"M13调研失败: {e}")
        
        return opportunity
```

#### 步骤8: M3集成

**文件**: `m3_reasoning_engine/reasoning_engine.py`

```python
class ReasoningEngine:
    
    def __init__(self, ..., m13_agent: ResearchAgent = None):
        ...
        self.m13_agent = m13_agent
    
    def judge_opportunity(self, signals):
        opportunity = self._judge(signals)
        
        # 对生成的机会进行最终验证
        if self.m13_agent and opportunity.confidence > 0.5:
            try:
                research = self.m13_agent.deep_research(
                    symbol=opportunity.instrument,
                    context=opportunity.reasoning
                )
                opportunity.confidence += research.confidence_delta
                opportunity.research_summary = research.summary
                
                if research.has_major_negative:
                    opportunity.confidence *= 0.5
            except Exception as e:
                logger.warning(f"M13调研失败: {e}")
        
        return opportunity
```

**验收标准**:
- [ ] 集成代码不破坏原有逻辑
- [ ] M13失败不影响主流程
- [ ] 调研结果正确传递
- [ ] 集成测试通过

---

### 步骤9: 测试（1小时）

**单元测试**:
- `test_research_agent.py`: 测试三个Level的调研流程
- `test_llm_analyzer.py`: 测试LLM分析逻辑
- `test_cache_manager.py`: 测试缓存机制

**集成测试**:
- `test_m1_5_integration.py`: 测试M1.5集成
- `test_m12_integration.py`: 测试M12集成
- `test_m3_integration.py`: 测试M3集成

**端到端测试**:
- 模拟M1.5推理 → M13快速验证 → 验证置信度调整
- 模拟M12异动 → M13标准调研 → 验证信息补充
- 模拟M3判断 → M13深度验证 → 验证最终结果

**验收标准**:
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试全部通过
- [ ] 端到端测试全部通过

---

### 步骤10: Dashboard监控（1小时）

**文件**: `dashboard_v2/pages/M13_调研监控.py`

**监控内容**:
- 调研统计（今日/本周/本月）
- 调研耗时分布（按Level）
- 缓存命中率
- 数据源可用率
- 置信度调整分布
- 发现重大利空的案例

**验收标准**:
- [ ] Dashboard页面正常显示
- [ ] 数据统计正确
- [ ] 图表展示清晰

---

## 进展日志

### 2026-05-07 — 设计阶段

- [x] 模块目录创建
- [x] PRINCIPLES.md 第一性原理文档
- [x] DESIGN.md 设计文档
- [x] IMPLEMENTATION_PLAN.md 实施计划
- [ ] 开始实施步骤1

---

## 关键里程碑

- **M13-Alpha**: 核心调研引擎可运行，三个Level流程走通
- **M13-Beta**: LLM分析正常，缓存机制工作
- **M13-RC**: 集成到M1.5/M12/M3，端到端测试通过
- **M13-GA**: 运行1周，数据驱动验证调研效果

---

## 风险与应对

### 风险1: LLM分析超时

**影响**: 调研流程阻塞

**应对**:
- 设置严格超时（Level 1: 15s, Level 2: 40s, Level 3: 80s）
- 超时返回原始数据，不做分析
- 降级策略：使用简单规则替代LLM

### 风险2: 数据源不稳定

**影响**: 调研结果不完整

**应对**:
- 多源容错，单个源失败不影响整体
- 返回partial_result标记
- 监控数据源可用率

### 风险3: 调研成本过高

**影响**: API调用和LLM Token消耗大

**应对**:
- 严格控制触发条件
- 缓存机制减少重复调研
- 监控成本指标，及时调整

### 风险4: 集成破坏原有逻辑

**影响**: M1.5/M12/M3功能异常

**应对**:
- M13失败不影响主流程
- 充分的集成测试
- 灰度发布，先在部分标的测试

---

## 后续优化方向

1. **智能触发**: 根据历史数据学习最佳触发时机
2. **个性化调研**: 根据标的特点调整调研策略
3. **实时更新**: 监听新闻流，自动失效相关缓存
4. **调研报告归档**: 保存历史调研报告供复盘
5. **A/B测试**: 对比有无调研的决策质量差异
