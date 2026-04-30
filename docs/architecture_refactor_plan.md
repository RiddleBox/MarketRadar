# MarketRadar 持续运行架构改造计划

**创建时间**: 2026-04-30  
**状态**: 进行中  
**目标**: 解决M9持仓状态不持久化、轨道1消息去重、双轨协同三大核心问题

---

## 一、现状确认 ✅

### 已实现的双轨架构

#### 轨道1：主动信号搜集（新闻驱动）
- **入口**: `live_signal_monitor.py`
- **流程**: M0采集新闻 → M1.5推理 → M2存储 → M3判断 → M4行动 → M9交易
- **运行频率**: 支持 `--continuous` 模式，可配置间隔（默认24小时）
- **状态**: ✅ 已实现，但缺少消息去重机制

#### 轨道2：异动信号追溯（价格驱动）
- **入口**: `run_continuous_simulation.py`
- **流程**:
  - `run_intraday_scan()` - 盘中高频扫描（10分钟）：异动检测 → 反向溯源 → M3判断 → 趋势判断 → M9交易
  - `run_daily_scan()` - 盘后全面扫描（4小时）：全市场扫描
- **运行频率**:
  - A股：9:30-15:00，每10分钟
  - 港股：9:30-16:00，每10分钟
  - 美股：21:30-04:00，每10分钟
  - 盘后：所有市场闭市时，每4小时
- **状态**: ✅ 已实现完整的持续运行逻辑

#### 持仓管理
- **价格更新**: 每60秒更新一次持仓价格
- **止盈止损**: 自动触发平仓
- **状态持久化**: ❌ **缺失** - M9 PaperTrader 的持仓状态只在内存中

---

## 二、核心问题诊断

### 问题1：M9 持仓状态不持久化 🔴 最高优先级
- **现象**: `run_continuous_simulation.py` 进程退出后，所有持仓记录丢失
- **影响**: 无法跨进程追踪持仓、无法复盘、无法生成资金曲线
- **根本原因**: `PaperTrader` 的 `self.positions` 和 `self.account` 只在内存中

### 问题2：轨道1缺少消息去重 🟡 中优先级
- **现象**: `live_signal_monitor.py` 每次运行都会重复采集相同新闻
- **影响**: 重复生成信号、浪费LLM额度、M2数据库冗余
- **根本原因**: 没有记录已处理的新闻ID

### 问题3：两条轨道独立运行，无法协同 🟢 低优先级
- **现象**:
  - 轨道1（新闻）和轨道2（异动）各自运行，互不感知
  - 同一个机会可能被两条轨道重复开仓
- **影响**: 仓位管理混乱、风控失效

---

## 三、改造方案

### Phase 1：M9 持仓状态持久化 🔴

**目标**: 让 `PaperTrader` 的持仓和资金状态可以跨进程恢复

#### 新增文件

**`m9_paper_trader/portfolio_db.py`**
```python
class PortfolioDB:
    """持仓数据库（SQLite）"""
    
    def save_position(self, position: Position) -> None:
        """保存持仓"""
    
    def load_open_positions(self) -> List[Position]:
        """加载所有未平仓持仓"""
    
    def update_position(self, position_id: str, **kwargs) -> None:
        """更新持仓（价格、状态等）"""
    
    def save_account(self, cash: float, total_value: float) -> None:
        """保存账户状态"""
    
    def load_account(self) -> Tuple[float, float]:
        """加载账户状态"""
    
    def log_trade(self, action: str, position: Position, reason: str) -> None:
        """记录交易日志"""
```

#### 数据库表结构

```sql
-- positions 表
CREATE TABLE positions (
  position_id TEXT PRIMARY KEY,
  instrument TEXT,
  direction TEXT,
  entry_price REAL,
  quantity INTEGER,
  entry_time TEXT,
  stop_loss_price REAL,
  take_profit_price REAL,
  current_price REAL,
  status TEXT,  -- open/closed
  close_price REAL,
  close_time TEXT,
  pnl REAL,
  opportunity_id TEXT,
  branch_id TEXT
);

-- account 表
CREATE TABLE account (
  id INTEGER PRIMARY KEY CHECK (id = 1),  -- 单行表
  cash REAL,
  total_value REAL,
  update_time TEXT
);

-- trade_log 表
CREATE TABLE trade_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp TEXT,
  action TEXT,  -- open/close
  position_id TEXT,
  instrument TEXT,
  price REAL,
  quantity INTEGER,
  reason TEXT
);
```

#### 修改现有文件

**`m9_paper_trader/paper_trader.py`**
```python
class PaperTrader:
    def __init__(self, initial_capital=1_000_000, db_path="data/portfolio.db"):
        self.db = PortfolioDB(db_path)
        
        # 启动时恢复状态
        self.positions = self.db.load_open_positions()
        self.cash, self.total_value = self.db.load_account()
        
        # 如果是首次启动，初始化账户
        if self.cash == 0:
            self.cash = initial_capital
            self.total_value = initial_capital
            self.db.save_account(self.cash, self.total_value)
    
    def open_position(self, plan: ActionPlan) -> Position:
        position = ...  # 现有逻辑
        self.db.save_position(position)  # 新增：保存到数据库
        self.db.log_trade("open", position, plan.reasoning)
        return position
    
    def close_position(self, position_id: str, reason: str) -> None:
        ...  # 现有逻辑
        self.db.update_position(position_id, status="closed", ...)
        self.db.log_trade("close", position, reason)
    
    def update_all_prices(self, feed) -> dict:
        result = ...  # 现有逻辑
        # 新增：批量更新数据库
        for position in self.positions:
            self.db.update_position(position.position_id, current_price=position.current_price)
        return result
```

---

### Phase 2：轨道1消息去重 🟡

**目标**: 避免重复处理相同新闻

#### 新增文件

**`m0_collector/deduplicator.py`**
```python
class NewsDeduplicator:
    """新闻去重器（基于SQLite）"""
    
    def __init__(self, db_path="data/news_cache.db"):
        self.db_path = db_path
        self._init_db()
    
    def is_processed(self, news_id: str) -> bool:
        """检查新闻是否已处理"""
    
    def mark_processed(self, news_id: str, title: str, source: str) -> None:
        """标记新闻已处理"""
    
    def cleanup_old(self, days=7) -> None:
        """清理7天前的记录"""
```

#### 修改现有文件

**`live_signal_monitor.py`**
```python
class LiveSignalMonitor:
    def __init__(self, ...):
        ...
        self.deduplicator = NewsDeduplicator()
    
    def collect_news(self, date: str = None) -> list:
        all_news = []
        for provider_name, provider in self.providers.items():
            news_items = provider.fetch()
            
            # 新增：去重过滤
            for item in news_items:
                news_id = f"{item.source_name}_{item.title}"
                if not self.deduplicator.is_processed(news_id):
                    all_news.append(item)
                    self.deduplicator.mark_processed(news_id, item.title, item.source_name)
        
        return all_news
```

---

### Phase 3：双轨协同 🟢

**目标**: 避免两条轨道重复开仓同一标的

#### 修改现有文件

**`m9_paper_trader/paper_trader.py`**
```python
class PaperTrader:
    def open_position(self, plan: ActionPlan) -> Position:
        # 新增：检查是否已有相同标的的持仓
        existing = [p for p in self.positions 
                   if p.instrument == plan.instrument 
                   and p.direction == plan.direction 
                   and p.status == "open"]
        
        if existing:
            logger.warning(f"标的 {plan.instrument} 已有持仓，跳过重复开仓")
            return None
        
        # 原有逻辑...
```

---

## 四、实施步骤

### Step 1：M9 持仓持久化（预计2-3小时）
1. ✅ 落档计划文档
2. ⏳ 创建 `m9_paper_trader/portfolio_db.py`（1小时）
3. ⏳ 修改 `m9_paper_trader/paper_trader.py`（1小时）
4. ⏳ 测试验证：启动 → 开仓 → 停止 → 重启 → 验证持仓恢复（30分钟）

### Step 2：轨道1消息去重（预计1小时）
1. ⏳ 创建 `m0_collector/deduplicator.py`（30分钟）
2. ⏳ 修改 `live_signal_monitor.py`（30分钟）

### Step 3：双轨协同（预计1小时，可选）
1. ⏳ 修改 `PaperTrader.open_position()` 增加重复检查（30分钟）
2. ⏳ 测试验证（30分钟）

---

## 五、验收标准

### Phase 1 验收
- [ ] `run_continuous_simulation.py` 启动后开仓
- [ ] 手动停止进程（Ctrl+C）
- [ ] 重新启动 `run_continuous_simulation.py`
- [ ] 验证持仓、资金、交易日志完整恢复

### Phase 2 验收
- [ ] `live_signal_monitor.py` 首次运行，采集N条新闻
- [ ] 立即再次运行，验证0条新闻被处理（全部去重）
- [ ] 7天后验证旧记录自动清理

### Phase 3 验收
- [ ] 轨道1开仓标的A
- [ ] 轨道2尝试开仓标的A
- [ ] 验证轨道2跳过重复开仓，日志记录警告信息

---

## 六、风险与注意事项

1. **数据库锁竞争**: SQLite在高并发写入时可能出现锁等待，需要设置合理的timeout
2. **数据迁移**: 如果已有运行中的实例，需要手动导出现有持仓数据
3. **向后兼容**: 修改 `PaperTrader.__init__()` 时保持参数向后兼容
4. **测试覆盖**: 重点测试进程异常退出（kill -9）后的数据完整性

---

**最后更新**: 2026-04-30 19:38
