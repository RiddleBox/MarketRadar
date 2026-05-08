# M13 深度调研模块设计方案

## 📋 模块定位

**名称**: M13 Research Agent（深度调研代理）  
**编号**: M13（按现有模块顺延，M12之后）  
**位置**: 横跨两个轨道的验证模块  
**触发场景**:
1. **M1轨道**: M1.5推理后 → M2情绪分析前（补充信息）
2. **M12轨道**: 反向溯源后 → 趋势判断前（验证信息）
3. **M3判断**: 生成机会后 → M4行动设计前（最终验证）

## 🎯 核心功能

### 1. 定向信息搜索
当发现一个机会（如"平安银行 000001"）时，自动搜索：

```python
def deep_research(symbol: str, opportunity_context: str) -> ResearchReport:
    """
    深度调研单个标的
    
    Args:
        symbol: 股票代码
        opportunity_context: 机会上下文（如"价格异动+5%"或"新闻提及产能扩张"）
    
    Returns:
        ResearchReport: 包含研报、新闻、财报、验证结论
    """
    
    # 1. 搜索研报（最近3个月）
    reports = data_manager.get_research_reports(symbol, limit=10)
    
    # 2. 搜索相关新闻（最近1周）
    news = data_manager.get_news(symbol, limit=20)
    
    # 3. 获取基本面数据
    fundamentals = data_manager.get_fundamentals(symbol)
    quote = data_manager.get_quote(symbol)
    
    # 4. NL语义搜索（如果有iwencai）
    # 根据opportunity_context构造搜索query
    if "产能扩张" in opportunity_context:
        semantic_results = iwencai_search(f"{symbol} 产能 扩产 投资", channel="report")
    
    # 5. LLM综合分析
    verification = llm_verify(
        opportunity=opportunity_context,
        reports=reports,
        news=news,
        fundamentals=fundamentals
    )
    
    return ResearchReport(
        symbol=symbol,
        reports=reports,
        news=news,
        fundamentals=fundamentals,
        verification=verification,
        confidence_boost=verification.confidence_delta  # 提升或降低置信度
    )
```

### 2. 集成到现有流程

#### M1轨道集成（新增）
```python
# m1_5_implicit_reasoning/implicit_reasoner.py

def reason_implicit_signals(self, macro_news: List[NewsSignal]) -> List[ImplicitSignal]:
    # 现有推理逻辑...
    # 输出：["平安银行可能受益于降息", "万科可能受益于降息"]
    
    # 🆕 对推理出的标的进行深度调研
    for signal in implicit_signals:
        if signal.confidence > 0.5:  # 推理置信度够高时
            research = self.m13_research_agent.deep_research(
                symbol=signal.instrument,
                opportunity_context=f"宏观事件: {macro_news.title}\n推理: {signal.reasoning}"
            )
            
            # 根据调研结果调整置信度
            signal.confidence *= research.confidence_multiplier
            signal.reasoning += f"\n\n【调研验证】{research.summary}"
            
            # 如果调研发现重大利空，可能降低置信度甚至过滤掉
            if research.has_major_negative:
                signal.confidence *= 0.5
```

**M1轨道的调研重点**：
- 验证推理逻辑是否成立
- 发现可能的反向因素
- 评估影响的时间跨度和强度

#### M12轨道集成
```python
# m12_opportunity_catcher/catcher_engine.py

def _build_opportunity(self, anomaly, causation, trend, strategy):
    # 现有逻辑...
    
    # 🆕 深度调研
    if causation.confidence < 0.7:  # 置信度不够高时
        research = self.m13_research_agent.deep_research(
            symbol=anomaly.instrument,
            opportunity_context=f"价格异动{anomaly.price_change_pct}%"
        )
        
        # 根据调研结果调整置信度
        causation.confidence += research.confidence_boost
        
        # 添加调研结果到机会描述
        opportunity.research_summary = research.summary
```

#### M3轨道集成
```python
# m3_opportunity/opportunity_engine.py

def judge_opportunity(self, signals: List[MarketSignal]) -> Opportunity:
    # 现有LLM判断逻辑...
    
    # 🆕 如果判断为"可能有机会"，进行深度调研
    if opportunity.confidence > 0.5:
        research = self.m13_research_agent.deep_research(
            symbol=opportunity.instrument,
            opportunity_context=opportunity.reasoning
        )
        
        # 更新置信度和理由
        opportunity.confidence += research.confidence_boost
        opportunity.reasoning += f"\n\n【调研验证】\n{research.summary}"
```

### 3. 数据提供者扩展

需要在 `AStockSkillProvider` 中添加：

```python
class AStockSkillProvider(DataProvider):
    
    # 🆕 NL语义搜索
    def semantic_search(self, query: str, channel: str = "report", 
                       limit: int = 20) -> List[Dict]:
        """
        NL语义搜索（需要iwencai API Key）
        
        Args:
            query: 自然语言查询，如"人形机器人 减速器 2026"
            channel: report/news/announcement
            limit: 返回数量
        """
        if not self._iwencai_available:
            return []
        
        return iwencai_search(query, channel, limit)
    
    # 🆕 批量获取多只股票的数据
    def batch_get_quotes(self, symbols: List[str]) -> Dict[str, Dict]:
        """批量获取行情（腾讯API支持批量）"""
        pass
```

## 📊 数据流示意

### M1轨道示例
```
【新闻】央行降息25bp
  ↓ M1解码
理解：货币政策宽松
  ↓ M1.5推理
推理出：平安银行可能受益（置信度0.6）
  ↓
🔍 触发深度调研:
    ├─ 搜索研报: "平安银行 净息差 零售转型"
    ├─ 查询财报: Q1净息差2.5%，环比+5bp
    ├─ 搜索新闻: "平安银行零售贷款增长15%"
    └─ 语义搜索: "银行股 降息影响 2026"
  ↓
LLM综合分析:
    "短期净息差承压，但零售转型顺利，
     贷款增长强劲，降息长期利好，
     置信度调整至0.75"
  ↓
进入M2情绪分析（带有调研背景）
```

### M12轨道示例
```
M12发现异动: 平安银行 +5.2%
    ↓
反向溯源: 找到2条相关新闻
    ↓
置信度: 0.4 (不够高)
    ↓
🔍 触发深度调研:
    ├─ 搜索研报: 找到5篇最近研报
    ├─ 搜索新闻: 找到12条相关新闻
    ├─ 查询财报: ROE 12%, EPS增长15%
    └─ 语义搜索: "平安银行 零售转型 2026"
    ↓
LLM综合分析:
    "研报普遍看好零售转型，Q1业绩超预期，
     今日异动可能与业绩预告相关，
     建议关注，置信度提升至0.75"
    ↓
生成高置信度机会 → M4行动设计
```

## 🔧 实现优先级

### Phase 1: 基础功能（1-2小时）
1. 创建 `m13_research/research_agent.py`
2. 实现基础的定向搜索（研报+新闻+基本面）
3. 简单的文本拼接作为调研报告

### Phase 2: LLM增强（2-3小时）
1. 使用LLM分析调研结果
2. 生成结构化的验证结论
3. 计算置信度提升/降低

### Phase 3: 语义搜索（需要iwencai API Key）
1. 集成iwencai NL搜索
2. 根据机会上下文自动构造搜索query
3. 主题关联分析

### Phase 4: 集成到M1.5/M12/M3
1. 在M1.5 implicit_reasoner中添加调研环节
2. 在M12 catcher_engine中添加调研环节
3. 在M3 opportunity_engine中添加验证环节
4. 调整置信度阈值

## 📝 配置示例

```yaml
# config/research_agent.yaml
research_agent:
  enabled: true
  
  # 触发条件
  triggers:
    m12_confidence_threshold: 0.6  # M12置信度低于此值时触发
    m3_confidence_threshold: 0.5   # M3置信度高于此值时触发
  
  # 搜索范围
  search_scope:
    reports_limit: 10
    reports_days: 90  # 最近90天
    news_limit: 20
    news_days: 7      # 最近7天
  
  # LLM配置
  llm:
    model: "gpt-4"
    temperature: 0.3
    max_tokens: 2000
```

## 🎯 预期效果

**Before**:
- M12发现异动 → 只有2条新闻 → 置信度0.4 → 放弃

**After**:
- M12发现异动 → 深度调研 → 找到5篇研报+12条新闻+财报数据 → LLM综合分析 → 置信度0.75 → 生成机会

**价值**:
1. **提高机会质量**: 有充分信息支撑的机会更可靠
2. **减少误判**: 通过多维验证过滤噪音
3. **增强可解释性**: 调研报告让决策过程透明
4. **充分利用SKILL**: 发挥A-stock SKILL的全部能力

---

**是否需要我开始实现这个模块？**
