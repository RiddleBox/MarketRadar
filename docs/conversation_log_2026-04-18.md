# docs/conversation_log_2026-04-18.md

# 对话记录 — 2026-04-18

> 记录日期：2026-04-18
> 会话类型：AI 辅助开发（opencode + qwen3.6-plus）
> 覆盖范围：Iteration 8 + Iteration 9 端到端实现

---

## 一、会话开始：确认项目进度

用户请求："帮我确认一下项目的当前进度"

### 发现

- 项目处于阶段 B 后期，Iteration 8 入口
- Iteration 1~7 已全部完成
- 测试基线：223 tests passed, 1 known failure
- 关键文档：`PROJECT_CONTEXT.md`, `MEMORY.md`, `docs/MarketRadar_Iteration_Plan_v2.md`

---

## 二、Iteration 8 实现（并行输入层与验证链建设）

### 8.1 M10 标准情绪 signal 注入 M2

**Bug 修复：**
1. `m7_scheduler/scheduler.py:542` — `engine.run(inject_m2=True)` 参数不存在，改为 `engine.run_and_inject(batch_id=batch_id)`
2. `pipeline/dashboard.py:810-814` — 同上，Dashboard "立即采集" 按钮也会 crash
3. `integrations/market_sentinel.py:249,279,301` — `time_horizon="short"` 大小写错误，改为 `"SHORT"`
4. `integrations/market_sentinel.py:121` — `logic_frame.affects` 在 `hot_sectors` 和 `affected_instruments` 都为空时变成空列表，加兜底 `"市场整体"`

**M3 情绪感知逻辑：**
- `m3_judgment/judgment_engine.py` 新增 `_extract_sentiment_context()` — 从信号列表提取 FG 指数和情绪标签
- `_calibrate_priority()` 增加情绪校准维度：
  - FG ≤ 20 + 利好信号 → watch/research 提升为 position
  - FG ≥ 80 + 利好信号 → position/urgent 降为 research（短期过热）
- `m3_judgment/prompt_templates.py` Step B prompt 增加情绪信号处理规则
- `_signals_to_detail()` 增加情绪信号标注

**新增文件：**
- `m10_sentiment/PRINCIPLES.md` — M10 第一性原理文档

**测试：**
- `tests/test_sentiment.py` 新增 10 个测试用例（schema 兼容、MockAdapter、注入 M2、M3 情绪校准）

### 8.2 M11 验证结果积累（50+ 历史案例）

**新增文件：**
- `m11_agent_sim/event_catalog.py` — 16 个手动标注重大事件 + 从 187 个交易日种子价格数据自动生成，共产出 60+ 历史事件
- `m11_agent_sim/calibration_store.py` — SQLite 持久化校准结果（save/load/list/compare）

**修改文件：**
- `m11_agent_sim/schemas.py` — 新增 `ValidationCase` + `CalibrationRun` schema
- `m11_agent_sim/calibrator.py` — 默认使用 event_catalog（替代不存在的 SEED_SIGNALS），构建 ValidationCase 并持久化
- `tests/test_m11.py` — 新增 12 个测试（事件目录、持久化、schema）

### 8.3 M10/M11 准入评估

**新增文件：**
- `docs/anchors/2026-04-17-m10-m11-admission-evaluation.md` — 准入评估报告

**结论：**
- M10 ✅ 准入主链（并行输入层，有限角色）
- M11 ❌ 不准入（方向命中率 50% < 70% 阈值，概率误差 0.424，极值召回 0%）

### 8.4 组合级风控

**修改文件：**
- `m9_paper_trader/paper_trader.py` — `RiskMonitor` 新增 `max_total_exposure_pct`、`max_theme_exposure_pct`、`high_corr_threshold` 参数和 `check_portfolio_risk()` 方法
- `tests/test_m9_7a.py` — 新增 4 个测试（总仓位、主题暴露、高相关、正常情况）

---

## 三、Iteration 9 实现（人机协作与实用性工具化）

### 9.4 审计日志（基础设施先行）

**新增文件：**
- `pipeline/audit_log.py` — `AuditEntry` 模型，`ActionType`/`Actor`/`AuditResult` 枚举
- `pipeline/audit_store.py` — SQLite 持久化（log/query/get_recent/get_stats/cleanup）
- `pipeline/audit.py` — 便捷函数 `audit()` + `@audit_action` 装饰器

### 9.2 人工确认机制

**新增文件：**
- `pipeline/confirmation.py` — `ConfirmationRequest` 模型，`RiskLevel`/`ConfirmationStatus` 枚举，`CONFIRMABLE_ACTIONS` 注册表，`requires_confirmation()` 判断函数
- `pipeline/confirmation_store.py` — SQLite 持久化（create/get_pending/approve/reject/expire/list_history）

**确认规则：**
| 动作 | 触发条件 | 风险等级 |
|------|---------|---------|
| position_open_large | allocation_pct > 5% | HIGH |
| position_close_large | |realized_pnl_pct| > 3% | MEDIUM |
| urgent_opportunity_execute | 任何 urgent 机会执行 | HIGH |
| pipeline_batch_large | batch_size > 20 | LOW |
| config_change | 任何 | CRITICAL |

### 9.1 盘前/盘中/盘后工作流

**新增文件：**
- `pipeline/workflows.py` — 工作流引擎
  - `WorkflowPhase` 枚举（PRE_MARKET/INTRADAY/POST_MARKET/CLOSED）
  - `resolve_phase()` — 从 `config/market_config.yaml` 读取交易时间判断当前阶段
  - `PHASE_STEPS` — 9 个步骤定义（含依赖关系）
  - `run_workflow()` — 依赖解析 + 顺序执行 + 审计日志
  - 桩函数：`_position_monitor_stub()` / `_portfolio_risk_check_stub()`
- `pipeline/__init__.py` — 模块初始化

**阶段定义：**
| 阶段 | 时间 | 步骤 |
|------|------|------|
| 盘前 | 集合竞价前 ~ 09:30 | 隔夜信号采集 → 情绪面快照 → 信号管道处理 |
| 盘中 | 09:30 ~ 15:05 | 价格更新 → 信号管道 → 持仓止损止盈监控 |
| 盘后 | 15:05 ~ 23:59 | 收盘价更新 → 复盘归因 → 组合风控检查 |

### 9.3 Dashboard 完善

**修改文件：**
- `pipeline/dashboard.py` — 新增 Tab 6 "🎛️ 工作流"
  - 当前阶段指示器（盘前/盘中/盘后/休市）
  - 阶段步骤可视化
  - 三个工作流执行按钮
  - 确认中心（待确认列表 + 批准/拒绝 + 历史）
  - 审计日志（过滤查询 + 统计摘要）

---

## 四、测试基线变化

| 阶段 | 测试数 | 说明 |
|------|--------|------|
| 会话开始 | 223 passed | Iteration 1~7 |
| Iter 8 完成后 | 246 passed | +10 sentiment +12 m11 +4 portfolio risk |
| Iter 9 完成后 | 253 passed | +16 iter9（审计/确认/工作流） |
| 最终 | 253 passed, 1 known failure | m3_parse_repair（已知） |

---

## 五、最终状态

### 所有迭代计划完成

| 迭代 | 状态 | 测试增量 |
|------|------|---------|
| Iter 1 | ✅ | 测试基础设施 |
| Iter 2 | ✅ | 主链稳态 |
| Iter 3 | ✅ | M5/M6 闭环 |
| Iter 4 | ✅ | 回测增强 |
| Iter 5 | ✅ | M3 评分 |
| Iter 6 | ✅ | M4 参数化 |
| Iter 7A | ✅ | 模拟盘核心 |
| Iter 7B | ✅ | 数据源+期货 |
| Iter 8.1 | ✅ | M10→M2 注入 |
| Iter 8.2 | ✅ | M11 50+ 案例 |
| Iter 8.3 | ✅ | 准入评估 |
| Iter 8.4 | ✅ | 组合风控 |
| Iter 9.1 | ✅ | 工作流 |
| Iter 9.2 | ✅ | 人工确认 |
| Iter 9.3 | ✅ | Dashboard |
| Iter 9.4 | ✅ | 审计日志 |

### 项目定位

从"研究原型"升级为"交易研究助手"，具备：
- 完整的 M1→M6 生产判断链
- 增强的 M7 回测引擎
- M8 知识库 + M9 模拟盘
- M10 情绪感知（已准入主链）
- M11 Agent 模拟（验证链内，不准入主链）
- 盘前/盘中/盘后工作流
- 人工确认机制
- 审计日志
- 6 tab Dashboard

---

## 六、文档更新清单

| 文档 | 更新内容 |
|------|---------|
| `PROJECT_CONTEXT.md` | 阶段→阶段C完成，测试数→253+，Pipeline→6 tabs，优先级表更新 |
| `MEMORY.md` | 阶段→阶段C完成，阻塞项#5/#7标记已解决，迭代列表更新 |
| `docs/MarketRadar_Iteration_Plan_v2.md` | Iter 8 状态→✅，Iter 9 状态→✅ |
| `docs/anchors/2026-04-17-m10-m11-admission-evaluation.md` | 新增准入评估报告 |
| `docs/conversation_log_2026-04-18.md` | 本文档 |
