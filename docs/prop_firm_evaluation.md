# Prop Firm 可行性评估与 Iteration 7 设计分析

> **文档类型**：模拟盘系统设计分析 + Prop Firm 适配评估
> **创建日期**：2026-04-17
> **关联迭代**：Iteration 7（模拟盘系统）

---

## 一、Track 2（SimulatedExecutionSpec）来源与弃用分析

### 1.1 创建时间线

| 时间 | 提交 | 事件 |
|------|------|------|
| 2026-04-13 11:36 | `3f68a3a` | M9 PaperTrader 创建（Track 1） |
| 2026-04-13 20:52 | `4f89cd2` | Execution Plan v1 写入，定义 Task 4 |
| 2026-04-13 22:15 | `58395c4` | Task 4 schema + mapper 创建 |
| 2026-04-13 22:35 | `4035198` | Minimal backtest engine 添加 |
| 2026-04-13 22:42 | `481e346` | Minimal simulation execution engine 添加 |
| 2026-04-13 22:55 | `82ee477` | Task 4 闭合文档提交 |

### 1.2 设计意图

Track 2 在一天内 4 次提交快速创建，目的是 **接口先行**：

- Task4 文档明确：目的是"先建立统一接口，后续回测、模拟盘、M6 复盘系统都基于同一对象语义演进"
- `MinimalExecutionEngine` 自称"最小验证器"——验证 SimulatedExecutionSpec 可被端到端消费
- 模拟路径应：不重新设计行动计划、不重新判断机会、忠实模拟执行阶段/滑点/费用/流动性约束、输出结构化结果供 M6 复盘

### 1.3 Track 1 胜出原因

1. M9 PaperTrader 比 Track 2 早 11 小时提交，且当天就被 Dashboard/Scheduler/回测引擎 20+ 处引用
2. Track 2 是 schema-first 的最小验证代码，没有持久化、没有定时更新、没有 UI 集成
3. 锚点文档要求"统一到 Track 2 体系"，但后续迭代优先级（1→2→3→4→5/6）使没人回去补全 Track 2
4. backtest 侧（BacktestTask）被更积极开发（FeeModel、OHLC、多标的），而 simulation 侧零进展

### 1.4 Track 对比

| 维度 | Track 1 (M9 PaperTrader) | Track 2 (SimulatedExecutionSpec) |
|------|--------------------------|----------------------------------|
| 位置 | `m9_paper_trader/` | `core/task4_mappers.py` + `simulation/` |
| 数据模型 | `PaperPosition` (plain class) | Pydantic 模型 |
| 生产引用 | 20+ 处 | 0 处 |
| 执行模型 | 有状态持久化 JSON + 实时价格 | 无状态同步函数 + mock 价格序列 |
| 参数来源 | 内部默认 | risk_config.yaml + execution_config.yaml |
| 锚点要求 | Phase 5 闭环后段 | Iter 7 继续沿此对象链扩展 |

### 1.5 统一策略决策

**选择：Track 1 增强 + Track 2 桥接**

- 废弃 PaperPosition 成本太高（20+ 引用需逐个修改）
- 增强 PaperTrader：加订单状态机、FeeModel、MarketRules
- 平仓时转换为 SimulatedExecutionResult 供 M6 消费
- `build_sim_execution_spec()` 保留为 ActionPlan→模拟盘的参数映射入口

---

## 二、适用场景分析

### 2.1 品种适用性

| 品种 | 流动性 | 滑点 | 个人适用度 | 当前覆盖 | Prop Firm 常见 |
|------|--------|------|-----------|---------|---------------|
| A股 ETF（510300等） | 极好 | 极小 | 最佳 | 已有 | 较少 |
| A股大盘股 | 好 | 小 | 适合 | 部分 | 较少 |
| 股指期货（IF/IC/IM） | 极好 | 极小 | 适合（杠杆高） | 配置有/数据缺 | **最常见** |
| 国债期货（T/TF） | 好 | 小 | 适合 | 未覆盖 | 常见 |
| 港股 ETF/大盘 | 好 | 小 | 适合 | AKShare 基础 | 较少 |
| 外汇 | 极好 | 极小 | 需外盘 | 未覆盖 | **最常见** |
| 商品期货（Au/Cu） | 好 | 小 | 适合 | 未覆盖 | 常见 |

### 2.2 个人交易特征对系统设计的影响

- 仓量小 → 不需要部分成交（PARTTRADED），简化 4 状态即可
- 品种以 ETF/期货为主 → 滑点模型可用固定比例，无需复杂市价冲击模型
- 流动性好的标的 → 不需要流动性约束检查
- 但 T+1 和涨跌停规则 → MarketRules 必须准确实现

---

## 三、数据源——核心问题分析

### 3.1 当前数据源

项目当前使用 AKShare 作为主要数据源（`m9_paper_trader/price_feed.py`）：

- `AKShareRealtimeFeed`：实时行情（A股 `stock_zh_a_spot_em()`，港股 `stock_hk_spot_em()`），1 分钟缓存
- `AKShareRealtimeFeed._get_daily()`：历史日线（ETF `fund_etf_hist_em()`，A股 `stock_zh_a_hist()`）
- `CSVPriceFeed`：离线测试用
- `BaoStock`：在 `market_config.yaml` 中配置为备用

### 3.2 数据源对比

| 数据源 | 费用 | 数据质量 | 实时性 | 稳定性 | A股 | 期货 | 港股 |
|--------|------|---------|--------|--------|-----|------|------|
| **AKShare** | 免费 | 中（东方财富爬虫） | 延迟1-3分钟 | 经常被反爬限流 | 有 | 部分 | 基础 |
| **BaoStock** | 免费 | 中（证券宝） | 日线级别 | 稳定 | 日线 | 日线 | 无 |
| **TuShare Pro** | 500元/年起（积分制） | 高 | 分钟级/实时 | 很稳定 | 完整 | 完整 | 完整 |
| **迅投研 xtquant** | 免费绑定券商 | 极高 | Tick级 | 极稳定 | 完整 | 完整 | 完整 |
| **RQData** | 机构定价 | 极高 | 分钟级 | 极稳定 | 完整 | 完整 | 无 |

### 3.3 推荐方案

**分阶段数据源策略**：

1. **Iter 7 开发验证阶段**：继续用 AKShare + BaoStock，零成本，日线回测够用
2. **模拟盘正式运行阶段**：注册 TuShare Pro（最低 500元/年，2000积分），获得：
   - 分钟级行情（滞后1分钟）
   - 期货分钟线 + 合约信息
   - **涨跌停价格**（`stk_limit` 接口——模拟盘验证涨跌停必需）
   - **交易日历**（`trade_cal` 接口——T+1 判断必需）
   - 每日指标/资金流向等
3. **Prop Firm 考核阶段**：如果需要实时 Tick 级数据，使用迅投研 xtquant（免费但需绑定券商账户）

### 3.4 TuShare 的关键接口

| 接口 | 用途 | 积分要求 |
|------|------|---------|
| `stk_limit` | 每日涨跌停价格 | ≥120 |
| `trade_cal` | 交易日历 | ≥120 |
| `stk_mins` | 分钟行情 | ≥2000 |
| `fut_daily` | 期货日线 | ≥120 |
| `fut_mins` | 期货分钟线 | ≥2000 |
| `fut_basic` | 期货合约信息 | ≥120 |

### 3.5 数据源架构

```
PriceFeed (抽象基类)
  ├── AKShareRealtimeFeed  (免费，当前默认)
  ├── BaoStockDailyFeed     (免费，日线备用)
  ├── TushareFeed           (付费，分钟级，涨跌停/交易日历)
  ├── CSVPriceFeed          (离线测试)
  └── make_price_feed()     (工厂函数，按配置选择)
```

---

## 四、设计模式决策

### 4.1 借鉴 vnpy paperaccount 的设计模式

**vnpy/vnpy_paperaccount**（MIT 协议，24 stars）的核心设计：

- **订单驱动撮合**：`cross_order()` 根据订单类型（MARKET/LIMIT/STOP）和 Tick 数据判断成交
- **订单状态机**：SUBMITTING → NOTTRADED → PARTTRADED → ALLTRADED / CANCELLED / REJECTED
- **滑点模型**：`trade_slippage` 参数，市价单在 ask/bid 上加减滑点
- **持仓冻结**：平仓时冻结对应仓位，防超卖
- **定时计算**：`EVENT_TIMER` 定时重算 PnL

**借鉴点与调整**：

| vnpy 设计 | MarketRadar 采用 | 调整理由 |
|-----------|-----------------|---------|
| 6 状态订单 | 简化 4 状态（SUBMITTED/FILLED/CANCELLED/REJECTED） | 个人小仓量不需部分成交 |
| 事件驱动架构 | 不引入（保持当前直接调用模式） | MarketRadar 不用事件驱动，引入 vnpy 的 EventEngine 代价太大 |
| 滑点模型 | 采用（固定比例滑点） | 简化但非零 |
| 持仓冻结 | 采用 | T+1 卖出限制 + 仓位检查 |
| Tick 驱动撮合 | 简化为价格快照驱动 | 无 Tick 级数据源（当前 AKShare 只有快照） |

### 4.2 各设计点决策

| 设计点 | 决策 | 理由 |
|--------|------|------|
| Track 统一 | Track 1 增强 + Track 2 桥接 | 废弃 PaperPosition 成本太高 |
| 订单状态 | 简化 4 状态 | 小仓量不需 PARTTRADED |
| FeeModel | 移到 core/ 共享 | backtest 和 M9 共用一份费率 |
| MarketRules | 新增独立类读 market_config.yaml | T+1/涨跌停/最小手数集中管理 |
| M6 触发 | 同步回调 | 仓位平仓时立即调用 RetrospectiveEngine |
| 实时风控 | 新增 RiskMonitor | prop firm 需日亏损/最大回撤检查 |

---

## 五、Prop Firm 可行性评估

### 5.1 典型 Prop Firm 考核标准

| 考核维度 | FTMO | MFF | MyForexFunds | 常见范围 |
|----------|------|-----|--------------|---------|
| 最大回撤 | 10% | 10% | 10% | 8-12% |
| 日亏损限制 | 5% | 5% | 4-5% | 4-6% |
| 盈利目标 | 10% | 10% | 8-10% | 8-12% |
| 考核天数 | 30-60 | 30 | 30-60 | 30-60 |
| 品种限制 | 期货/外汇/股指 | 期货/外汇 | 外汇/金属 | 以衍生品为主 |
| 禁止马丁格尔 | 是 | 是 | 是 | 通用 |
| 最小交易天数 | 4天 | 5天 | 5天 | 4-10天 |
| 一致性要求 | 策略逻辑稳定 | 同 | 同 | 通用 |

### 5.2 MarketRadar 现状与差距

| 考核维度 | MarketRadar 现状 | 差距 | 优先级 |
|----------|-----------------|------|--------|
| **最大回撤** | M7 回测有 max_drawdown | 模拟盘无实时风控 | **Iter 7A** |
| **日亏损限制** | config 有 max_daily_drawdown_pct | 模拟盘无实时检查 | **Iter 7A** |
| **盈利目标** | 系统设计覆盖 | 需资金曲线追踪 | Iter 7B |
| **交易天数** | Scheduler 已有 | 需交易日历校验 | Iter 7B |
| **品种限制** | A 股 ETF 为主 | 需适配期货 | Iter 7B |
| **禁止马丁格尔** | M4 PRINCIPLES 禁止 | 架构级保障 | ✅ 已有 |
| **一致性** | M6 复盘 + M3 评分 | 需交易日志审计 | Iter 7A |
| **资金曲线** | 无 | 需每日净值记录 | Iter 7B |

### 5.3 Iteration 7A/7B 分工

**7A（模拟盘核心增强）**：
1. 订单状态机（4 状态）
2. FeeModel 共享（core/fee_model.py）
3. MarketRules 类（T+1/涨跌停/最小手数）
4. 实时风控（日亏损限制/最大回撤/仓位上限）
5. M6 自动复盘触发
6. 修复 open_from_plan entry_price=0 bug
7. 交易日志审计（结构化 trade log）

**7B（数据源升级+期货+资金曲线）**：
1. TuShare Feed 接入
2. 期货合约/保证金支持
3. 资金曲线（equity curve）每日记录
4. 交易日历集成
5. Prop Firm 考核仪表盘

### 5.4 Prop Firm 适配的关键架构要求

1. **实时风控层**：模拟盘需在每次 update_price() 时检查日累计亏损/最大回撤，触发阈值时自动停止新开仓
2. **交易日志**：每笔交易需记录开仓/平仓/止损/止盈的完整时间、价格、费用、原因
3. **资金曲线**：每日收盘后记录 total_equity = cash + sum(unrealized_pnl)，生成净值曲线
4. **一致性证明**：M3 的评分卡 + M4 的参数化仓位 + M6 的归因报告构成完整的"判断-行动-归因"审计链

### 5.5 风险提示

- **本系统不构成投资建议**：MarketRadar 是市场机会操作系统，其模拟盘结果不代表实盘表现
- **Prop Firm 考核有随机性**：即使系统逻辑正确，短期考核窗口的随机波动可能导致考核失败
- **期货杠杆风险**：prop firm 考核常涉及高杠杆期货品种，保证金计算必须精确
- **合规约束**：模拟盘到实盘的迁移需遵守相关法规和 prop firm 规则

---

## 六、开源项目调研记录

### 6.1 vnpy/vnpy_paperaccount

- **地址**：https://github.com/vnpy/vnpy_paperaccount
- **Stars**：24
- **协议**：MIT
- **核心价值**：
  - 完整订单状态机（SUBMITTING/NOTTRADED/PARTTRADED/ALLTRADED/CANCELLED/REJECTED）
  - 订单驱动撮合（MARKET/LIMIT/STOP 三种订单类型）
  - 滑点模型（`trade_slippage` 参数）
  - 持仓冻结（平仓时冻结仓位防超卖）
  - 定时 PnL 计算
- **不适合直接引入的原因**：
  - 深度耦合 vnpy MainEngine/EventEngine/Gateway 体系
  - 需要 vnpy 的 `OrderData`/`TickData`/`ContractData` 等基础类型
  - 剥离成本 > 自建成本
- **借鉴部分**：订单状态定义、撮合逻辑设计模式、持仓冻结概念

### 6.2 vnpy/vnpy (核心框架)

- **地址**：https://github.com/vnpy/vnpy
- **Stars**：39.5k
- **协议**：MIT
- **关键设计参考**：
  - `ContractData`：min_volume/pricetick/size 字段——期货合约规格
  - `TickData`：limit_up/limit_down 字段——涨跌停价格
  - `OrderData`：完整订单生命周期
  - `PositionData`：frozen/volume/yd_volume 字段——T+1 仓位区分

### 6.3 backtrader

- **结论**：纯回测框架，无独立 paper trading 层，不适用

### 6.4 AKShare

- **地址**：https://github.com/akfamily/akshare
- **Stars**：18.3k
- **当前项目使用**：作为主要数据源
- **局限**：反爬限流、无涨跌停价格接口、无交易日历、实时数据延迟 1-3 分钟

### 6.5 TuShare Pro

- **地址**：https://tushare.pro
- **费用**：500元/年起（2000积分）
- **关键接口**：stk_limit(涨跌停价格)、trade_cal(交易日历)、stk_mins(分钟线)、fut_daily/fut_mins(期货行情)
- **推荐**：作为模拟盘正式运行阶段的数据源升级方案

---

## 七、当前项目 M9 模块现状

### 7.1 M9 PaperTrader 已实现功能

| 功能 | 状态 | 说明 |
|------|------|------|
| PaperPosition 数据模型 | 有 | plain class，dict 序列化 |
| PaperTrader 管理器 | 有 | open_from_plan / open_manual / update_all_prices / list_open / list_closed |
| AKShareRealtimeFeed | 有 | 实时 + 日线 + 1 分钟缓存 |
| CSVPriceFeed | 有 | 离线测试 |
| SignalEvaluator | 有 | 信号效能评估 + 报告 |
| CLI | 有 | status/open/update/close/evaluate/expire |
| Dashboard 集成 | 有 | Tab 3 全功能 |
| Scheduler 集成 | 有 | price_update + daily_review |
| MAE/MFE 追踪 | 有 | 最大不利/有利偏移 |
| 止损/止盈自动触发 | 有 | update_price() 时自动平仓 |

### 7.2 M9 PaperTrader 缺失功能

| 功能 | Iter 7 任务 | 说明 |
|------|-------------|------|
| 订单状态机 | 7A.2 | 当前无 Order 概念，仓位"直接开" |
| 手续费/滑点 | 7A.1 | PaperPosition 的 PnL 不扣任何成本 |
| T+1 限制 | 7A.3 | 当日买入可立即卖出 |
| 涨跌停检查 | 7A.3 | 无 |
| 最小手数 | 7A.3 | 无 |
| 日亏损限制 | 7A.4 | 无实时风控 |
| 最大回撤检查 | 7A.4 | 无实时风控 |
| M6 自动复盘 | 7A.5 | 只有 Scheduler 的 daily_review，非平仓即触发 |
| open_from_plan bug | 7A.6 | entry_price=0 未自动填充 |
| 交易日志审计 | 7A.7 | 无结构化 trade log |

### 7.3 Scheduler 的 M9 相关 bug

`m7_scheduler/scheduler.py` 第 429 行引用 `pos.close_reason`，但 `PaperPosition` 无此属性（应为 `pos.status`），运行时会 AttributeError。

### 7.4 两套并行系统的关键分歧

| 维度 | M9 Track (在用) | Task4 Track (死代码) |
|------|----------------|---------------------|
| 数据模型 | PaperPosition (plain class) | SimulatedExecutionSpec (Pydantic) |
| 参数来源 | 内部默认 | risk_config.yaml + execution_config.yaml |
| 生产引用 | 20+ 处 | 0 处 |
| 锚点要求 | — | "模拟盘继续围绕 SimulatedExecutionSpec/Result" |

**统一方案**：M9 增强为运行时引擎，平仓时桥接输出 SimulatedExecutionResult。
