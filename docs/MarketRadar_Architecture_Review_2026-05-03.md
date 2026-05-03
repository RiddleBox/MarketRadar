# MarketRadar 架构评估报告

**评估日期**: 2026-05-03  
**评估者**: cloud-server  
**代码版本**: MarketRadar cf10118c

---

## 执行摘要

MarketRadar 采用模块化架构，M0-M12 职责清晰，推理引擎是核心竞争力。架构改造三阶段（持久化、去重、协同）已完成，系统可持续运行。

当前主要架构缺陷：M3 缺少评分化、M4 缺少参数化、M5 缺少生命周期管理、数据源缺少降级策略。

---

## 一、架构优势

### 1.1 模块化设计 ✅
- **职责清晰**: M0-M12 各司其职，易于理解和维护
- **低耦合**: 模块间通过标准化数据结构（Signal/Opportunity）通信
- **易扩展**: 新增模块不影响现有模块

### 1.2 推理引擎核心竞争力 ✅
- **因果链推理**: 基于因果图谱推理未来事件
- **历史案例检索**: 从历史数据中学习
- **验证结果**: 100% 事件预测准确率

### 1.3 持久化机制 ✅
- **M9 持仓持久化**: SQLite 存储，重启后恢复
- **M2 信号存储**: SQLite 存储，支持历史查询
- **M8 知识库**: 结构化知识沉淀

### 1.4 去重机制 ✅
- **M0 消息去重**: URL + 标题哈希去重
- **M2 信号去重**: 避免重复处理

### 1.5 双轨协同 ✅
- **主动信号线**: 30 分钟扫描
- **异动信号线**: 5-10 分钟高频扫描
- **协同机制**: 避免重复开仓

---

## 二、架构缺陷

### 2.1 M3 推理引擎缺少评分化（P0）

**问题描述**:
- 当前输出"是/否"判断，缺少置信度评分
- 无法区分高置信度机会和低置信度机会

**影响**:
- 无法优先处理高置信度机会
- 无法基于置信度调整仓位

**建议方案**:
```python
class OpportunityJudgment:
    is_opportunity: bool
    confidence_score: float  # 0-1，新增
    confidence_breakdown: dict  # 评分细节
    # confidence_breakdown = {
    #     "pattern_match": 0.9,      # 因果模式匹配度
    #     "case_similarity": 0.85,   # 历史案例相似度
    #     "signal_strength": 0.8,    # 信号强度
    #     "time_window_accuracy": 0.75  # 时间窗口准确性
    # }
```

### 2.2 M4 行动设计缺少参数化（P1）

**问题描述**:
- 止损/止盈/仓位建议硬编码在代码中
- 无法灵活调整策略参数

**影响**:
- 无法 A/B 测试不同参数组合
- 无法针对不同品类使用不同参数

**建议方案**:
```yaml
# config/action_params.yaml
ETF:
  stop_loss_pct: 0.05
  take_profit_pct: 0.15
  max_position_pct: 0.10

STOCK:
  stop_loss_pct: 0.08
  take_profit_pct: 0.20
  max_position_pct: 0.05
```

### 2.3 M5 持仓管理缺少生命周期管理（P0）

**问题描述**:
- 只有基础持仓跟踪，缺少失效条件监控
- 持仓可能在失效条件触发后仍然持有

**影响**:
- 无法及时平仓失效持仓
- 增加亏损风险

**建议方案**:
```python
class PositionLifecycle:
    OPEN = "open"              # 开仓
    MONITORING = "monitoring"  # 监控中
    INVALIDATED = "invalidated"  # 已失效
    CLOSED = "closed"          # 已平仓

# 失效条件
class InvalidationCondition:
    time_window_expired: bool  # 时间窗口过期
    premise_changed: bool      # 前提条件变化
    stop_loss_triggered: bool  # 止损触发
```

### 2.4 数据源缺少降级策略（P1）

**问题描述**:
- AKShare/YFinance 故障时系统停止工作
- 单点故障风险

**影响**:
- 数据源故障导致系统不可用
- 无法保证 7×24 持续运行

**建议方案**:
```python
class DataSourceFallback:
    primary: AKShareFeed
    secondary: YFinanceFeed
    tertiary: HistoricalDataFeed
    
    def get_price(self, symbol):
        try:
            return self.primary.get_price(symbol)
        except:
            try:
                return self.secondary.get_price(symbol)
            except:
                return self.tertiary.get_price(symbol)
```

### 2.5 M7 调度器缺少状态持久化（P1）

**问题描述**:
- 重启后丢失 `last_run` 状态
- 可能导致任务重复执行或遗漏

**影响**:
- 系统重启后任务调度不准确

**建议方案**:
```python
# scheduler_state.json
{
  "tasks": {
    "signal_pipeline": {
      "last_run": "2026-05-03T09:00:00",
      "run_count": 42,
      "error_count": 0
    }
  }
}
```

---

## 三、技术债务清单

| 债务项 | 优先级 | 影响 | 预计修复时间 |
|--------|--------|------|-------------|
| M3 评分化 | P0 | 无法区分机会质量 | 3 天 |
| M5 生命周期管理 | P0 | 失效持仓无法及时平仓 | 3 天 |
| M4 参数化 | P1 | 无法灵活调整策略 | 3 天 |
| 数据源降级 | P1 | 单点故障风险 | 3 天 |
| M7 状态持久化 | P1 | 重启后状态丢失 | 2 天 |
| M12 跨日时间窗口 | P1 | 美股交易时段跨日问题 | 2 天 |
| M2 跨批次检索 | P2 | 历史信号查询不便 | 2 天 |
| M10 情绪热度 | P2 | 情绪分析不够细化 | 3 天 |

---

## 四、扩展性评估

### 4.1 新增市场 ✅
- 当前支持：A股、港股、美股
- 扩展方式：添加 Market 枚举 + 交易日历
- 难度：低

### 4.2 新增策略 ✅
- 当前支持：政策驱动型、事件驱动型
- 扩展方式：添加因果模式 + 历史案例
- 难度：中

### 4.3 新增数据源 ⚠️
- 当前支持：AKShare、YFinance
- 扩展方式：实现 PriceFeed 接口
- 难度：中
- 问题：缺少降级策略

### 4.4 新增模块 ✅
- 模块化设计，易于扩展
- 难度：低

---

## 五、结论

**架构优势**:
- 模块化设计清晰
- 推理引擎核心竞争力
- 持久化、去重、协同机制完善

**架构缺陷**:
- M3 缺少评分化（P0）
- M5 缺少生命周期管理（P0）
- M4 缺少参数化（P1）
- 数据源缺少降级策略（P1）

**技术债务**:
- 8 项技术债务，预计修复时间 21 天

**扩展性**:
- 新增市场/策略/模块：易于扩展
- 新增数据源：需要降级策略支持

---

**评估完成时间**: 2026-05-03 22:25  
**下一步**: 生产就绪度评估
