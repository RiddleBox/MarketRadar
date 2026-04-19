# MarketRadar 迭代推进计划 v2

> **文档类型**：项目计划（基于 v1 执行计划 + 架构锚点校准 + 当前实际状态迭代）
> **归档日期**：2026-04-18
> **替代文档**：MarketRadar_Execution_Plan_v1.md（本文档吸收其有效内容并按实际状态修正）

---

## 一、当前实际状态（2026-04-17）

### 1.1 阶段判定

项目已完成**阶段 A（研究原型）**，正处于**阶段 B（验证增强）**早期。

关键事实：
- 主链路 `M0 → M1 → M2 → M3 → M4` 全部代码已实现（非骨架），约 10,000+ 行
- 多 provider LLM 接入（工蜂OAuth / DeepSeek / OpenAI-compatible）已完成，带 fallback 链
- 消融实验已跑通：Full 策略胜率 100%，均盈亏 +9.81%
- 参数系统三层配置已落地（risk / execution / opportunity_rules）
- 回测两条映射链已建立（OpportunityObject→BacktestTask, ActionPlan→SimulatedExecutionSpec）
- Streamlit Dashboard 已有 5 个 tab
- 正式测试 30/30 通过（schemas / m3_judgment / m3_parse_repair / m4_strategy / strategy_registry）

### 1.2 当前阻塞性问题

| # | 问题 | 影响 | 来源 |
|---|------|------|------|
| B1 | 9 个 WIP 测试文件全部不可用 | 无回归保护网 | tests/ |
| B2 | M6 测试因 schema 演进（opportunity_score 字段）失败 | 闭环后段无法验证 | tests/_m6_test.py |
| B3 | _integration_test 仍引用已删除的 sentiment_resonance | 旧逻辑残留 | tests/_integration_test.py |
| B4 | M7 scheduler 测试断言过时（缺少 sentiment_collect） | 调度层无法验证 | tests/_m7_test.py |
| B5 | LLM OAuth 认证在非工蜂内网环境不可用 | 端到端联调受限 | core/llm_client.py |

### 1.3 各模块第一性原理定位摘要

以下定位来自各模块 PRINCIPLES.md，是后续所有迭代的不可违反边界：

| 模块 | 第一性原理定位 | 禁止越界行为 |
|------|---------------|-------------|
| M0 | 忠实记录，不提前解读 | 不做判断、不评估重要性 |
| M1 | 翻译已发生的变化为结构化信号 | 不预测、不判断是否构成机会、不合并多事件 |
| M2 | 跨时间信号记忆层 | 不修改已写入信号、event_time 为时间基准 |
| M3 | 唯一被允许做判断的模块 | 判断必须建立在信号证据之上、空列表是合法输出 |
| M4 | 把机会转化为可执行可退出的行动结构 | 不改变M3判断、止损比止盈更重要 |
| M5 | 用规则替代情绪执行持仓纪律 | 持仓期间不做新决策、不接受情绪输入修改规则 |
| M6 | 区分运气和判断，让系统可学习 | 归因必须有具体证据、失败比成功更有价值 |
| M7 | 验证判断框架，不优化参数 | 严格前向隔离、分层统计、盈亏比比胜率更重要 |
| M8 | 为M3/M4提供可溯源证据 | 不做预测、不存实时新闻、精准优于召回 |

### 1.4 模块分层定位（架构锚点）

此定位源自 `2026-04-14-architecture-plan-and-change-disposition-anchor.md`，后续迭代必须遵守：

```
主生产判断链：  M1 → M2 → M3 → M4
输入前端：     M0
闭环后段：     M5 / M6
支撑层：       M8 / M9（价格更新/模拟执行支撑）
并行输入层：   M10（情绪感知，独立采集→注入M2→M3按标准signal消费）
验证链：       M11 / backtest / ablation（不在未充分验证前升格为主链）
编排层：       M7 Scheduler
```

**硬约束**：
- 验证链有效 ≠ 应立即进入主链
- M10 当前是并行输入层，不是 M3 的强制后处理增强器
- M11 不应在未充分验证前成为主生产判断链必经节点
- 共享策略接口层 ≠ 立即多策略主链输出

---

## 二、迭代推进计划

### 总策略

> 先收口主链稳态 → 再补闭环后段 → 再增强验证链 → 最后考虑主链扩容准入

每一轮迭代的验收口径：
- 有明确代码改动
- 有测试覆盖
- 有可复现的验证结果
- 有 git commit

---

### Iteration 1：测试基础设施修复与回归保护网建设 ✅ 已完成（2026-04-17）

**目标**：让所有正式模块拥有可运行的单元测试，建立回归保护。

**依据**：M6 复盘归因的第一性原理——"归因必须有具体证据"——测试就是系统行为的证据基础。没有测试的代码是不可复盘的代码。

| 任务 | 说明 | 验收标准 | 状态 |
|------|------|---------|------|
| 1.1 修复 _m6_test.py | 补 opportunity_score 等新增必需字段 | OpportunityObject 构造通过 | ✅ |
| 1.2 修复 _m7_test.py | 更新 scheduler 默认任务集断言（含 sentiment_collect） | scheduler 测试通过 | ✅ |
| 1.3 删除 _integration_test.py | sentiment_resonance 已回退，其测试同步删除 | 无残留引用 | ✅ |
| 1.4 修复 _sentiment_test.py | 移除 Python 3.10+ only 参数 | 测试通过 | ✅ |
| 1.5 修复 _backtest_test.py | 更新过时断言（价格变动预期） | 测试通过 | ✅ |
| 1.6 _batch_ingest_test.py → scripts/ | 需要 LLM 的端到端脚本，非单元测试 | 移出 tests/ | ✅ |
| 1.7 修复 _m0_test.py | 适配实际 API（DedupIndex / ManualProvider / Normalizer） | 测试通过 | ✅ |
| 1.8 所有 _前缀测试重写为正式 pytest 测试 | test_m0/m2/m5/m6/m7/m8/m11/sentiment/backtest | 全部可被 pytest 发现 | ✅ |
| 1.9 补充 M2 / M5 / M8 最小单元测试 | 原先无任何正式测试 | 每模块至少 2 个测试用例 | ✅ |
| 1.10 清理根目录临时测试文件 | 9 个 test_*.py 移入 scripts/ | 根目录无 test_*.py | ✅ |
| 1.11 修复 M6 _make_minimal_opportunity | 补 opportunity_score 必需字段 | M6 批量复盘不再 crash | ✅ |
| 1.12 清理 docs/anchors 过量调试文档 | 16→4 个，保留架构锚点和关键状态 | 无冗余 | ✅ |

**最终结果**：119 tests passed, 0 failed

---

### Iteration 2：主链稳态收敛 ✅ 已完成（2026-04-17）

**目标**：让 M1→M2→M3→M4 在至少一个 provider 下可稳定、可复现地端到端跑通。

**依据**：M3 的第一性原理——"判断必须建立在信号证据之上"——如果主链本身不稳定（JSON 解析失败、provider 切换不可控），则判断证据链断裂。

| 任务 | 说明 | 验收标准 | 状态 |
|------|------|---------|------|
| 2.1 LLM 本地配置机制 | 支持 llm_config.local.yaml 覆盖默认配置，密钥不入 Git | .gitignore 已包含 | ✅ |
| 2.2 DeepSeek provider 配置 | 用户提供的 key 已写入 llm_config.local.yaml | inspect_llm_runtime 显示 credential_ready=true | ✅ |
| 2.3 M0→M1→M2→M3→M4 端到端联调 | 含完整断言 | smoke test PASSED | ✅ |
| 2.4 主链 smoke test 入口正规化 | scripts/run_smoke.py 替代根目录 test_pipeline.py | 一个命令可跑通主链 | ✅ |
| 2.5 LLM provider fallback 可观测性 | 切换时写明从哪个 provider 切到哪个 | 日志可追踪 | ✅ |
| 2.6 环境变量警告降级 | 未设置的 env var 从 warning 降为 debug | 不干扰正常输出 | ✅ |
| 2.7 M3 Step B JSON 解析稳定性 | 当前 DeepSeek 下 3 次端到端均 0 次 parse failure | 待更多样本验证 | ⚠️ 需持续观察 |

---

### Iteration 3：闭环后段补齐（M5 / M6） ✅ 已完成（2026-04-17）

**目标**：让系统从"判断+行动设计"延伸到"持仓跟踪+复盘归因"，形成最小闭环。

**依据**：M5 的核心——"建仓前所有决策必须已经做好"，M6 的核心——"区分运气和判断"——没有 M5/M6，系统只会判断不会复盘，判断力无法迭代。

| 任务 | 说明 | 验收标准 | 状态 |
|------|------|---------|------|
| 3.1 ActionPlan 补充 direction/market 字段 | M5 开仓需要这两个字段 | schema + test 通过 | ✅ |
| 3.2 PositionSizing 补充数值字段 | suggested_allocation_pct / max_allocation_pct | 可计算仓位数量 | ✅ |
| 3.3 M4 ActionDesigner 更新 | 设置 direction/market/numeric sizing | watch plan + action plan 均输出 | ✅ |
| 3.4 pipeline/position_bridge.py | M4→M5 桥接函数，ActionPlan→Position | 可从 plan 开立持仓 | ✅ |
| 3.5 M6 timedelta import 修复 | _make_minimal_opportunity 使用 timedelta 但未导入 | 不再 NameError | ✅ |
| 3.6 M6→M8 API 修复 | add_entry→add_document | 复盘教训可写入知识库 | ✅ |
| 3.7 M5 持仓管理单元测试 | test_m5.py | 3 个测试用例 | ✅ |
| 3.8 M4→M5→M6 闭环联调测试 | test_m4_m5_m6.py | schema/bridge/retro 测试 | ✅ |
| 3.9 M1→M6 全闭环端到端验证 | scripts/run_full_loop.py | 脚本通过 | ✅ |

**最终结果**：126 tests passed; full loop M1→M6 verified

---

### Iteration 4：回测与数据层增强 ✅ 已完成（2026-04-17）

**目标**：让回测系统从"最小验证器"升级为"可产出有统计意义结论"的工具。

**依据**：M7 的第一性原理——"回测的目的是验证判断框架，不是优化参数"——当前引擎缺少手续费/滑点、分层统计不够深、数据层存在合成占位数据。

| 任务 | 说明 | 验收标准 | 状态 |
|------|------|---------|------|
| 4.1 FeeModel 手续费/滑点模型 | 佣金万三+印花税千一+滑点万五，默认往返成本 | 盈亏自动扣减费用 | ✅ |
| 4.2 by_signal_type 丰富化 | 增加 profit_factor / avg_holding_days / best / worst | 分层统计可深度对比 | ✅ |
| 4.3 by_direction 分层统计 | BULLISH vs BEARISH 独立统计 | 报告含方向分组 | ✅ |
| 4.4 BacktestReport.fee_cost_pct | 报告中显示往返交易成本 | 透明 | ✅ |
| 4.5 csv_cache 合成数据清理 | 删除占位数据，用 seed+price_cache 生成真实 OHLCV CSV | CSV 含 open/high/low/close/volume | ✅ |
| 4.6 PriceLoader 弃用标记 | 添加 DeprecationWarning，文档指向 HistoryPriceFeed | 不再误用 | ✅ |
| 4.7 回测增强测试 | test_backtest.py 覆盖 FeeModel / OHLC / 分层统计 | 131 passed | ✅ |

**最终结果**：131 tests passed (51+28+52 分批); 回测引擎含手续费模型+丰富统计

---

### Iteration 5：M3 评分框架完善 ✅ 已完成（2026-04-17）

**目标**：让 M3 的判断从"有/无机会"升级为"可解释的综合评分"。

**依据**：M3 PRINCIPLES 明确要求回答五个核心问题（为什么价格会变/为什么是现在/如果错了为什么/胜率赔率/下一步验证什么）。评分框架是这五个问题的结构化表达，不是额外装饰。

| 任务 | 说明 | 验收标准 | 状态 |
|------|------|---------|------|
| 5.1 评分维度定义 | catalyst_strength / timeliness / tradability / risk_clarity / signal_consistency | schema 字段落地 | ✅ |
| 5.2 M3 prompt 更新 | 引导 LLM 按评分维度输出 + 每个维度1-10分含义定义 | 评分输出可解析 | ✅ |
| 5.3 失效条件结构化 | invalidation_conditions / kill_switch_signals 验证 + 空条件补充默认 + 去重 | 每个 position/urgent 机会有失效条件 | ✅ |
| 5.4 评分与 priority_level 映射 | _calibrate_priority() + 9 个测试用例覆盖边界 | 可解释为什么是 watch/research/position/urgent | ✅ |
| 5.5 历史上下文增强 | M3 可检索 M2 历史相似信号，区分旧闻与新闻 | 同主题旧事件不误判为新机会 | ⏳ 移至后续迭代 |

---

### Iteration 6：M4 参数化行动设计完善 ✅ 已完成（2026-04-17）

**目标**：让 M4 的行动计划完全由参数系统驱动，而非硬编码。

**依据**：M4 的第一性原理——"仓位是风险的函数不是信心的函数"——仓位必须由止损距离和风险预算计算，不应是 LLM 的"感觉"。

| 任务 | 说明 | 验收标准 | 状态 |
|------|------|---------|------|
| 6.1 仓位计算规则化 | compute_kelly_position (1/4 Kelly) + compute_position_from_risk_budget (风险预算/止损距离) | M4 输出的 position_sizing 有计算依据 | ✅ |
| 6.2 品类模板差异化 | ETF/STOCK/FUTURES 各自的止损止盈/分阶段逻辑不同（execution_config.yaml） | 不同 instrument_type 输出明显差异 | ✅ |
| 6.3 _build_action_plan 参数化集成 | 替换硬编码 risk_budget → 用 compute_position_from_risk_budget + Kelly 参考 | sizing_rationale 含止损距离/风险预算/Kelly 参考 | ✅ |
| 6.4 plan refresh / review cadence | 行动计划不是一次性静态文本 | 有有效期和复核机制 | ✅ 已有 valid_until + review_triggers |
| 6.5 M4→M7 参数共享验证 | M4 与回测使用同一套参数 | 参数语义一致 | ⏳ 移至后续迭代 |

---

### Iteration 7：模拟盘系统

**目标**：建立近真实执行环境的验证体系。

**依据**：M5 的第一性原理——"止损是纪律不是建议"——模拟盘是验证纪律执行的第一道关卡。

分两个 Sub-iteration：7A（核心增强）和 7B（数据源+期货+资金曲线）。

#### Iteration 7A：模拟盘核心增强 ✅ 已完成（2026-04-17）

| 任务 | 说明 | 验收标准 | 状态 |
|------|------|---------|------|
| 7A.1 FeeModel 共享 | 从 backtest_engine 移到 core/fee_model.py，M7/M9 共用 | backtest 和 M9 费率一致 | ✅ |
| 7A.2 订单状态机 | PaperOrder + OrderStatus(4 状态) | 开仓有订单记录 | ✅ |
| 7A.3 MarketRules | core/market_rules.py，T+1/涨跌停/最小手数/交易时段/订单校验 | A股T+1卖出被拒、涨跌停价格正确 | ✅ |
| 7A.4 RiskMonitor | 日亏损限制/最大回撤/单仓上限 | 触发阈值时自动停止开仓 | ✅ |
| 7A.5 M6 自动复盘 | 平仓后 on_position_closed 回调 | 回调可触发 RetrospectiveEngine | ✅ |
| 7A.6 修复 open_from_plan | entry_price 改为必传参数 | 不再出现 entry_price=0 | ✅ |
| 7A.7 交易日志审计 | trade_log.json 记录每笔开仓/平仓 | 审计可追溯 | ✅ |
| 7A.8 手续费扣除 | 平仓时 apply_fees() 扣除佣金+印花税+滑点 | realized_pnl_after_fees < realized_pnl_pct | ✅ |

**最终结果**：37 new tests passed (102 total core+7A); 0 regressions

#### Iteration 7B：数据源升级+期货+资金曲线 ✅ 已完成（2026-04-17）

| 任务 | 说明 | 验收标准 | 状态 |
|------|------|---------|------|
| 7B.1 TushareFeed | TuShare Pro 接入（涨跌停价/交易日历/分钟线/期货日线） | token 可用时提供分钟级行情 | ✅ |
| 7B.2 期货合约/保证金 | MarketRules._FUTURES_SPECS + futures_margin/notional + open_futures() | IF/IC/T 可模拟交易 | ✅ |
| 7B.3 资金曲线 | EquityCurveTracker 每日净值+回撤+收益 | 可产出 equity curve JSON | ✅ |
| 7B.4 交易日历集成 | TushareFeed.get_trade_calendar/is_trading_day/next_trading_day + JSON缓存 | T+1 准确到交易日 | ✅ |
| 7B.5 CompositeFeed | 多源 fallback 链（tushare→akshare→csv） | 主源失败自动 fallback | ✅ |
| 7B.6 PriceSnapshot 增强 | limit_up/limit_down/prev_close/change_pct 字段 | 涨跌停价可从 TuShare 获取 | ✅ |

**最终结果**：22 new tests passed (110 total for Iter 5-7B); 0 regressions

---

### Iteration 8：并行输入层与验证链建设 ✅ 已完成（2026-04-18）

**目标**：M10 标准化、M11 验证结果积累，按证据决定是否准入主链。

**依据**：架构锚点——"验证链有效 ≠ 应立即进入主链"，准入由证据决定。

| 任务 | 说明 | 验收标准 | 状态 |
|------|------|---------|------|
| 8.1 M10 标准情绪 signal 注入 M2 | 情绪信号作为普通 signal 供 M3 消费 | M2 中可见情绪类型信号 | ✅ |
| 8.2 M11 验证结果积累 | 至少 50 个历史案例的校准数据 | 输出稳定性可量化 | ✅ |
| 8.3 M10/M11 准入评估 | 按证据评估：是否稳定、失败是否阻断主链、角色是什么 | 形成准入评估报告 | ✅ |
| 8.4 组合级风控 | 最大总仓位 / 主题暴露上限 / 高相关性去重 | 多机会并发时风控生效 | ✅ |

---

### Iteration 9：人机协作与实用性工具化 ✅ 已完成（2026-04-18）

**目标**：从"研究原型"升级为"交易研究助手"。

**依据**：Roadmap 最终愿景——"可解释、可验证、可迭代的市场机会操作系统"。

| 任务 | 说明 | 验收标准 | 状态 |
|------|------|---------|------|
| 9.1 盘前/盘中/盘后工作流 | 机会扫描→优先级排序→持仓检查→复盘归因 | 工作流可端到端演示 | ✅ |
| 9.2 所有关键动作保留人工确认点 | 不做黑箱自动交易 | 每个执行动作需确认 | ✅ |
| 9.3 Dashboard 完善 | 完整的操作与审计界面 | 可日常使用 | ✅ |
| 9.4 审计日志 | 所有判断/行动/执行/复盘完整可追溯 | 任意机会可查全链路历史 | ✅ |

---

### Iteration 10：M11 LLM 模式校准 ✅ 已完成（2026-04-18）

**目标**：用 LLM 替代规则模式重新校准 M11，评估是否达到准入标准。

**依据**：M11 PRINCIPLES P3 — "校准证据驱动准入"，方向命中率需 ≥ 70%。

| 任务 | 说明 | 验收标准 | 状态 |
|------|------|---------|------|
| 10.1 LLM 校准脚本 | `scripts/run_llm_calibration.py` | 支持 DeepSeek/gongfeng/auto provider | ✅ |
| 10.2 LLM 客户端集成 | LLMAdapter → AgentNetwork → BaseMarketAgent | LLM 模式可用且可降级到规则 | ✅ |
| 10.3 LLM 校准运行 | 60 事件 DeepSeek 校准 | 方向命中率、综合得分、分类统计 | ✅ |
| 10.4 M11 PRINCIPLES.md | 补充缺失的第一性原理文档 | 文档存在且包含 6 条核心原则 | ✅ |
| 10.5 校准报告与准入更新 | 更新准入评估文档 | 报告落档、准入评估更新 | ✅ |
| 10.6 GBK 兼容修复 | calibrator.py 日志中 ✓✗❌ 替换为 OK/MISS/FAIL | Windows 下无编码错误 | ✅ |

**最终结果**：

| 模式 | Direction Accuracy | Composite | Pass |
|------|-------------------|-----------|------|
| Rule-based (3%) | 50.00% | 29.5 | No |
| Rule-based (2%) | 21.67% | 11.6 | No |
| LLM DeepSeek (2%) | **36.67%** | **22.4** | No |

**M11 维持不准入主链**。LLM 模式比规则模式有显著改善（+15pp），但仍远低于 70% 阈值。核心瓶颈：系统性看多偏差、NEUTRAL 识别不足、缺乏历史上下文。

---

## 三、执行顺序与优先级

```
Iteration 1（测试修复）     ← 最高优先级，无测试则无安全迭代
Iteration 2（主链稳态）     ← 紧随其后，主链不稳则一切不可靠
Iteration 3（M5/M6 闭环）  ← 形成最小完整闭环
Iteration 4（回测增强）     ← 让验证有统计意义
Iteration 5（M3 评分化）    ← 让判断可解释
Iteration 6（M4 参数化）    ← 让行动可验证
Iteration 7（模拟盘）       ← 近真实环境验证
Iteration 8（M10/M11）     ← 按证据准入
Iteration 9（工具化）       ← 最终可用性
Iteration 10（M11 LLM 校准）← LLM 模式校准，改善但仍未达 70%
```

**关键路径**：1 → 2 → 3 → 4 → 5/6 → 7 → 8 → 9 → 10

Iteration 5 和 6 可并行推进。Iteration 8 不阻塞 Iteration 9。

---

## 四、验收总口径

项目从"研究原型"升级为"成熟可应用工具"的里程碑标准：

| 维度 | 标准 | 当前 |
|------|------|------|
| 主链稳定性 | 连续 20 次端到端运行无失败 | ⚠️ M3 JSON 解析偶发失败（DeepSeek下已大幅改善） |
| 测试覆盖 | 所有正式模块有单元测试且通过 | ✅ 102+ tests passed |
| 闭环完整性 | M1→M6 全链路可演示 | ✅ full loop verified |
| 回测有效性 | > 30 笔回测样本、分层统计 | ⚠️ FeeModel+OHLC已增强，样本量待扩展 |
| 判断可解释 | 每个机会有评分与失效条件 | ✅ M3评分校准+失效条件验证完成 |
| 参数一致性 | M3/M4/回测/模拟盘共享参数语义 | ✅ FeeModel共享+MarketRules集中管理 |
| 模拟盘真实度 | 含滑点/手续费/市场制度 | ✅ 7A完成（FeeModel+MarketRules+RiskMonitor） |
| 人机协作 | 关键动作有人工确认 | ❌ 未建设（Iter 9） |

---

## 五、此计划与 v1 执行计划的关系

| v1 阶段 | v1 状态 | v2 处置 |
|---------|--------|--------|
| P1 联调稳定性 | 部分完成 | → Iteration 2 收口 |
| P2 M3 评分化 | 评分卡字段已加，框架未完成 | → Iteration 5 完善 |
| P3 参数系统 | 三层配置已落地 | → Iteration 6 继续 M4 深度参数化 |
| P4 M4 行动设计 | 品类模板+策略接口已落地 | → Iteration 6 继续 |
| P5 情绪Agent | M10/M11 已实现但未准入主链 | → Iteration 8 按证据评估 |
| P6 回测升级 | 最小执行器已落地 | → Iteration 4 增强 |
| P7 模拟盘 | 最小执行器已落地 | → Iteration 7 增强 |
| P8 实用性 | 未开始 | → Iteration 9 |

**v1 缺失项（v2 新增）**：
- 测试基础设施修复（v1 未覆盖，是最大风险）
- M5/M6 闭环补齐（v1 低估了闭环后段重要性）
- 回测数据层增强（v1 仅提到但未规划细节）

---

## 六、给后续执行的硬约束

1. **不要把实验链有效性自动等同于主链准入资格**
2. **不要在未验证前恢复 M3 主链中的情绪共振增强**
3. **不要默认推动 M11 成为主链必经节点**
4. **不要把"共享策略接口层"误解为"立即多策略主链输出"**
5. **每个 Iteration 完成后必须更新本文档的进度状态**
6. **任何模块改动必须先看该模块的 PRINCIPLES.md**
7. **参数不足时优先补参数系统，不在执行器内部塞临时常量**
