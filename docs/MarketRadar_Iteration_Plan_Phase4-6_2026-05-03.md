# MarketRadar 迭代计划 Phase 4-6

**制定日期**: 2026-05-03  
**制定者**: cloud-server  
**目标**: 从基本就绪（73%）升级到生产就绪（95%）

---

## 总体时间线

| Phase | 目标 | 优先级 | 预计耗时 | 完成后得分 |
|-------|------|--------|----------|-----------|
| Phase 4 | 关键模块补全 | P0 | 2-3 周 | 85% |
| Phase 5 | 架构优化 | P1 | 2-3 周 | 90% |
| Phase 6 | 生产增强 | P2 | 3-4 周 | 95% |
| **总计** | - | - | **7-10 周** | **95%** |

---

## Phase 4: 关键模块补全（P0 - 紧急）

**目标**: 补全关键缺失模块，解决核心架构缺陷  
**优先级**: P0（紧急）  
**预计耗时**: 2-3 周  
**完成后得分**: 85%

### 任务清单

#### 4.1 实现 M13 信号输出接口（3天）

**任务描述**: 标准化交易信号输出接口  
**优先级**: P0  
**预计耗时**: 3 天

**实现内容**:
```python
# m13_signal_output/signal.py
class TradingSignal:
    symbol: str          # 股票代码
    direction: str       # LONG/SHORT
    size: float          # 仓位（%）
    entry_price: float   # 入场价
    stop_loss: float     # 止损价
    take_profit: float   # 止盈价
    reason: str          # 信号原因
    confidence: float    # 置信度
    time_horizon: str    # 时间窗口
    created_at: datetime # 创建时间

# m13_signal_output/exporter.py
class SignalExporter:
    def export_to_file(self, signal: TradingSignal, path: str)
    def export_to_api(self, signal: TradingSignal, endpoint: str)
    def export_to_mq(self, signal: TradingSignal, queue: str)
```

**验收标准**:
- [ ] TradingSignal 数据结构定义完成
- [ ] 支持文件输出（JSON/CSV）
- [ ] 支持 API 输出（HTTP POST）
- [ ] 支持消息队列输出（可选）
- [ ] 单元测试覆盖 90%+

---

#### 4.2 实现 M15 风控模块（5天）

**任务描述**: 完整的风控规则引擎  
**优先级**: P0  
**预计耗时**: 5 天

**实现内容**:
```python
# m15_risk_control/rules.py
class RiskControlRules:
    max_single_position: float = 0.10  # 单笔最大仓位 10%
    max_total_position: float = 0.80   # 总持仓最大 80%
    max_daily_trades: int = 10         # 单日最大交易次数
    max_consecutive_losses: int = 3    # 最大连续亏损次数
    daily_loss_limit: float = 0.05     # 单日最大亏损 5%

# m15_risk_control/engine.py
class RiskControlEngine:
    def check_position_limit(self, position: Position) -> bool
    def check_total_exposure(self, portfolio: Portfolio) -> bool
    def check_daily_trades(self, trades: List[Trade]) -> bool
    def check_consecutive_losses(self, trades: List[Trade]) -> bool
    def trigger_circuit_breaker(self, reason: str) -> None
```

**验收标准**:
- [ ] 单笔仓位限制实现
- [ ] 总持仓限制实现
- [ ] 单日交易次数限制实现
- [ ] 连续亏损熔断实现
- [ ] 单日亏损限制实现
- [ ] 熔断机制实现
- [ ] 单元测试覆盖 90%+

---

#### 4.3 M3 推理引擎评分化（3天）

**任务描述**: 为推理引擎添加置信度评分  
**优先级**: P0  
**预计耗时**: 3 天

**实现内容**:
```python
# m3_reasoning_engine/scoring.py
class ConfidenceScorer:
    def score_pattern_match(self, pattern: CausalPattern, signals: List[Signal]) -> float
    def score_case_similarity(self, case: HistoricalCase, signals: List[Signal]) -> float
    def score_signal_strength(self, signals: List[Signal]) -> float
    def score_time_window_accuracy(self, pattern: CausalPattern) -> float
    
    def calculate_overall_confidence(self, breakdown: dict) -> float:
        # 加权平均
        return (
            breakdown["pattern_match"] * 0.35 +
            breakdown["case_similarity"] * 0.30 +
            breakdown["signal_strength"] * 0.25 +
            breakdown["time_window_accuracy"] * 0.10
        )

# m3_reasoning_engine/judgment.py
class OpportunityJudgment:
    is_opportunity: bool
    confidence_score: float  # 新增
    confidence_breakdown: dict  # 新增
```

**验收标准**:
- [ ] 因果模式匹配度评分实现
- [ ] 历史案例相似度评分实现
- [ ] 信号强度评分实现
- [ ] 时间窗口准确性评分实现
- [ ] 综合置信度计算实现
- [ ] OpportunityJudgment 数据结构更新
- [ ] 单元测试覆盖 90%+

---

#### 4.4 M5 持仓生命周期管理（3天）

**任务描述**: 实现持仓状态机和失效条件监控  
**优先级**: P0  
**预计耗时**: 3 天

**实现内容**:
```python
# m5_position/lifecycle.py
class PositionLifecycle:
    OPEN = "open"              # 开仓
    MONITORING = "monitoring"  # 监控中
    INVALIDATED = "invalidated"  # 已失效
    CLOSED = "closed"          # 已平仓

class InvalidationCondition:
    time_window_expired: bool  # 时间窗口过期
    premise_changed: bool      # 前提条件变化
    stop_loss_triggered: bool  # 止损触发

# m5_position/monitor.py
class PositionMonitor:
    def check_time_window(self, position: Position) -> bool
    def check_premise_conditions(self, position: Position) -> bool
    def check_stop_loss(self, position: Position) -> bool
    def invalidate_position(self, position: Position, reason: str) -> None
```

**验收标准**:
- [ ] 持仓状态机实现
- [ ] 时间窗口过期检查实现
- [ ] 前提条件变化检查实现
- [ ] 止损触发检查实现
- [ ] 失效持仓自动平仓实现
- [ ] 单元测试覆盖 90%+

---

### Phase 4 完成标准

- [ ] M13 信号输出接口实现并测试通过
- [ ] M15 风控模块实现并测试通过
- [ ] M3 推理引擎评分化完成并测试通过
- [ ] M5 持仓生命周期管理完成并测试通过
- [ ] 所有模块集成到主系统
- [ ] 端到端测试通过
- [ ] 文档更新完成

---

## Phase 5: 架构优化（P1 - 重要）

**目标**: 优化架构设计，提升系统稳定性  
**优先级**: P1（重要）  
**预计耗时**: 2-3 周  
**完成后得分**: 90%

### 任务清单

#### 5.1 M4 行动设计参数化（3天）

**任务描述**: 外置参数配置，支持灵活调整  
**优先级**: P1  
**预计耗时**: 3 天

**实现内容**:
```yaml
# config/action_params.yaml
ETF:
  stop_loss_pct: 0.05
  take_profit_pct: 0.15
  max_position_pct: 0.10
  kelly_fraction: 0.5

STOCK:
  stop_loss_pct: 0.08
  take_profit_pct: 0.20
  max_position_pct: 0.05
  kelly_fraction: 0.3

FUTURES:
  stop_loss_pct: 0.03
  take_profit_pct: 0.10
  max_position_pct: 0.02
  kelly_fraction: 0.2
```

**验收标准**:
- [ ] 参数配置文件实现
- [ ] 不同品类参数模板实现
- [ ] 参数热加载实现
- [ ] A/B 测试支持
- [ ] 单元测试覆盖 90%+

---

#### 5.2 M7 调度器状态持久化（2天）

**任务描述**: 持久化调度器状态，避免重启丢失  
**优先级**: P1  
**预计耗时**: 2 天

**实现内容**:
```python
# m7_scheduler/state.py
class SchedulerState:
    tasks: Dict[str, TaskState]
    
    def save(self, path: str) -> None
    def load(self, path: str) -> None

class TaskState:
    name: str
    last_run: datetime
    run_count: int
    error_count: int
    last_error: Optional[str]
```

**验收标准**:
- [ ] 状态持久化实现（JSON）
- [ ] 重启后状态恢复实现
- [ ] 任务执行历史记录实现
- [ ] 单元测试覆盖 90%+

---

#### 5.3 数据源降级策略（3天）

**任务描述**: 实现数据源降级，避免单点故障  
**优先级**: P1  
**预计耗时**: 3 天

**实现内容**:
```python
# core/data_source/fallback.py
class DataSourceFallback:
    primary: PriceFeed      # AKShare
    secondary: PriceFeed    # YFinance
    tertiary: PriceFeed     # HistoricalData
    
    def get_price(self, symbol: str) -> float:
        for source in [self.primary, self.secondary, self.tertiary]:
            try:
                return source.get_price(symbol)
            except Exception as e:
                logger.warning(f"数据源 {source} 失败: {e}")
        raise DataSourceUnavailable("所有数据源均不可用")
```

**验收标准**:
- [ ] 数据源降级策略实现
- [ ] 主数据源故障自动切换实现
- [ ] 数据源健康检查实现
- [ ] 单元测试覆盖 90%+

---

#### 5.4 实现 M16 监控告警（3天）

**任务描述**: 异常监控和通知机制  
**优先级**: P1  
**预计耗时**: 3 天

**实现内容**:
```python
# m16_monitoring/alerts.py
class AlertManager:
    def alert_data_source_failure(self, source: str, error: str) -> None
    def alert_inference_failure(self, error: str) -> None
    def alert_position_risk(self, position: Position, reason: str) -> None
    def send_feishu(self, message: str) -> None
    def send_wechat(self, message: str) -> None
```

**验收标准**:
- [ ] 数据源异常告警实现
- [ ] 推理引擎异常告警实现
- [ ] 持仓异常告警实现
- [ ] 飞书通知实现
- [ ] 微信通知实现（可选）
- [ ] 单元测试覆盖 90%+

---

### Phase 5 完成标准

- [ ] M4 参数化完成并测试通过
- [ ] M7 状态持久化完成并测试通过
- [ ] 数据源降级策略完成并测试通过
- [ ] M16 监控告警完成并测试通过
- [ ] 所有模块集成到主系统
- [ ] 端到端测试通过
- [ ] 文档更新完成

---

## Phase 6: 生产增强（P2 - 优化）

**目标**: 性能优化、可观测性增强、实盘对接  
**优先级**: P2（优化）  
**预计耗时**: 3-4 周  
**完成后得分**: 95%

### 任务清单

#### 6.1 实现 M14 实盘对接层（7天）

**任务描述**: 与券商 API（QMT/富途）对接  
**优先级**: P2  
**预计耗时**: 7 天

**实现内容**:
```python
# m14_broker_integration/qmt_adapter.py
class QMTAdapter:
    def place_order(self, signal: TradingSignal) -> Order
    def cancel_order(self, order_id: str) -> bool
    def query_position(self, symbol: str) -> Position
    def query_account(self) -> Account

# m14_broker_integration/futu_adapter.py
class FutuAdapter:
    def place_order(self, signal: TradingSignal) -> Order
    def cancel_order(self, order_id: str) -> bool
    def query_position(self, symbol: str) -> Position
    def query_account(self) -> Account
```

**验收标准**:
- [ ] QMT API 适配器实现
- [ ] 富途 API 适配器实现
- [ ] 统一交易接口实现
- [ ] 下单/撤单/查询功能实现
- [ ] 单元测试覆盖 90%+

---

#### 6.2 性能优化（5天）

**任务描述**: 索引、缓存、并行优化  
**优先级**: P2  
**预计耗时**: 5 天

**优化内容**:
- M2 信号存储：添加索引优化查询性能
- M3 推理引擎：缓存因果模式匹配结果
- M12 盘中扫描：并行扫描多个市场
- M0 信号采集：并行采集多个数据源

**验收标准**:
- [ ] M0 采集时间 <30s
- [ ] M1 解码时间 <10s
- [ ] M3 推理时间 <5s
- [ ] M12 扫描时间 <2min

---

#### 6.3 可观测性增强（5天）

**任务描述**: 日志、监控、告警增强  
**优先级**: P2  
**预计耗时**: 5 天

**实现内容**:
- 统一日志格式（JSON）
- 添加 trace_id
- 实现 Prometheus 指标
- 监控 Dashboard

**验收标准**:
- [ ] 结构化日志实现
- [ ] Prometheus 指标实现
- [ ] 监控 Dashboard 实现
- [ ] 关键指标监控实现

---

#### 6.4 文档完善（3天）

**任务描述**: API 文档、运维手册  
**优先级**: P2  
**预计耗时**: 3 天

**文档清单**:
- API 文档（M13/M14/M15/M16）
- 运维手册（部署/监控/故障排查）
- 用户手册（使用指南/最佳实践）

**验收标准**:
- [ ] API 文档完成
- [ ] 运维手册完成
- [ ] 用户手册完成

---

### Phase 6 完成标准

- [ ] M14 实盘对接层完成并测试通过
- [ ] 性能优化完成并达到目标
- [ ] 可观测性增强完成
- [ ] 文档完善完成
- [ ] 所有模块集成到主系统
- [ ] 端到端测试通过
- [ ] 生产就绪度达到 95%

---

## 总结

**总体目标**: 从基本就绪（73%）升级到生产就绪（95%）

**关键里程碑**:
- Phase 4 完成：85%（关键模块补全）
- Phase 5 完成：90%（架构优化）
- Phase 6 完成：95%（生产增强）

**预计时间线**: 7-10 周

**下一步行动**:
1. 将 Phase 4 任务拆解为独立的 task 文件
2. 放入 `openclaw-tasks/tasks/pending/`
3. 按优先级排序
4. 开始执行 Phase 4

---

**制定完成时间**: 2026-05-03 22:35  
**下一步**: 拆解任务并创建 task 文件
