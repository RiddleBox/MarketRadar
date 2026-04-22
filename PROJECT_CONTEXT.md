# PROJECT_CONTEXT.md — MarketRadar 开工必读

> **文档类型**：项目状态总览 + 开工上下文
> **最后更新**：2026-04-19
> **当前阶段**：阶段 C（工具化）完成，M2/M3推理引擎已实现
> **迭代计划**：[MarketRadar_Iteration_Plan_v2.md](docs/MarketRadar_Iteration_Plan_v2.md)

---

## 一句话当前状态

> Iteration 1~9 全部完成；253+ tests passed；M10 准入主链，M11 不准入；盘前/盘中/盘后工作流 + 人工确认 + 审计日志 + Dashboard 6 tab 已上线。M2/M3推理引擎已实现，支持因果链推理和历史案例检索，100%准确率验证通过。项目从"研究原型"升级为"交易研究助手"。

---

## 模块状态总览

| 模块 | 目录 | 状态 | 说明 |
|------|------|------|------|
| M0 收集器 | `m0_collector/` | ✅ 代码完成 | 4 providers + dedup + normalizer + CLI |
| M1 信号解码 | `m1_decoder/` | ✅ 代码完成 | LLM 解码 + retry，已验证 |
| M2 信号存储 | `m2_storage/` | ✅ 代码完成 | SQLite 存储 + 因果图谱 + 历史案例，支撑推理引擎 |
| M3 机会判断 | `m3_judgment/` | ✅ 代码完成，推理引擎已实现 | Step A/B + 推理引擎 + 因果链推理 + 历史案例检索，100%准确率验证通过 |
| M4 行动设计 | `m4_action/` | ✅ 代码完成，参数化仓位已实现 | 策略接口 + Kelly/RiskBudget仓位 + 品类模板差异化 |
| M5 持仓管理 | `m5_position/` | ✅ 代码完成，已联调 | M4→M5 桥接完成，position_bridge 可开仓 |
| M6 复盘归因 | `m6_retrospective/` | ✅ 代码完成，已联调 | M6→M8 写入修复，全闭环 M1→M6 验证通过 |
| M7 回测引擎 | `m7_backtester/` | ✅ 已增强 | FeeModel+OHLC+丰富统计，csv_cache 已清理 |
| M7 调度器 | `m7_scheduler/` | ✅ 代码完成 | 5 任务调度 + 状态持久化 |
| M8 知识库 | `m8_knowledge/` | ✅ 代码完成（Phase 1） | JSON + keyword search，Phase 2 向量待做 |
| M10 情绪感知 | `m10_sentiment/` | ✅ 代码完成 | FG 指数 + SQLite 历史，独立采集→注入 M2 |
| M11 Agent 模拟 | `m11_agent_sim/` | ✅ 代码完成（Phase 1） | 5 agents 串行拓扑，图谱拓扑骨架 |
| Pipeline | `pipeline/` | ✅ 代码完成 | CLI + 回测 + Dashboard（6 tabs） |
| 测试 | `tests/` | ✅ 核心测试通过 | 253+ tests passed, 1 known failure (m3_parse_repair) |

**状态图例**：⏳ 待开始 | 🟡 进行中 | ⚠️ 有风险 | ✅ 完成 | ❌ 有问题

---

## 模块分层定位

```
主生产判断链：  M1 → M2 → M3 → M4
输入前端：     M0
闭环后段：     M5 / M6
支撑层：       M8 / M9
并行输入层：   M10（独立采集→注入M2→M3按标准signal消费）
验证链：       M11 / backtest / ablation
编排层：       M7 Scheduler
```

**硬约束**：验证链有效 ≠ 应进入主链；M10/M11 不在未充分验证前升格为主链必经节点。

---

## 第一性原理总纲

### 为什么这个系统存在？

二级市场的本质是**在不确定性中识别结构性预期差**。

大多数市场参与者的判断失败，不是因为信息不够，而是因为：
1. 信息没有结构化——新闻、数据、公告混在一起，无法系统比较
2. 信号没有跨时间积累——单次判断丢失了历史上下文
3. 判断和行动脱节——"有机会"和"怎么做"是分开的，止损是临时决定的
4. 结果没有被归因——每次交易后没有系统性复盘，判断力无法迭代

MarketRadar 试图解决这四个问题：
- **M0**：忠实采集外部信息，去重，标准化
- **M1**：提取"已发生的事实变化"，不做预测和主观判断
- **M2**：存储信号 + 因果图谱 + 历史案例，支撑跨时间推理
- **M3**：推理引擎，基于信号组合+因果模式+历史案例做机会判断
- **M4+M5**：行动和判断绑定，止损在入场前确定
- **M6+M8**：复盘归因+知识沉淀，让判断力持续迭代
- **M7**：调度器+回测引擎，编排工作流+验证策略

### 核心约束（永远不能违反）
1. 机会必须有信号溯源
2. 回测必须前向隔离（event_time 是时间基准）
3. 止损在入场前确定，持仓期间不随情绪修改
4. M3 的空列表输出是健康行为，不是系统错误

### 关键架构原则（2026-04-18 矫正）

**M1 的边界**：
- ✅ 提取"已发生的事实变化"
- ❌ 不做预测、不做主观判断、不合并多个独立事件

**M2 的职责**（数据层）：
- ✅ 存储信号（跨时间积累）
- ✅ 存储因果图谱（信号A → 通常导致事件B，概率+时间窗口）
- ✅ 存储历史案例（信号组合 → 演化过程 → 结果）
- ❌ 不做推理判断（推理是M3的职责）

**M3 的职责**（推理层）：
- ✅ 信号关联分析（识别哪些信号逻辑相关）
- ✅ 因果链推理（基于M2的因果图谱，推断未来事件概率）
- ✅ 历史案例检索（从M2查询相似案例，作为判断依据）
- ✅ 机会判断（回答五个核心问题：什么变了、对谁有利、为什么是现在、风险是什么、如何证伪）
- 🎯 **核心能力**：不是"反应型判断"（看到降准公告才判断），而是"推理型判断"（看到3个线索推断降准概率80%，提前布局）

**M8 的职责**（知识层）：
- ✅ 存储分析框架、行业知识、政策背景
- ✅ 为M3提供领域知识支撑
- ❌ 不存储实时信号（那是M2的职责）

---

## 各模块文档索引

| 模块 | PRINCIPLES.md | 核心代码 |
|------|--------------|---------|
| M0 | [m0_collector/PRINCIPLES.md](m0_collector/PRINCIPLES.md) | [cli.py](m0_collector/cli.py) |
| M1 | [m1_decoder/PRINCIPLES.md](m1_decoder/PRINCIPLES.md) | [decoder.py](m1_decoder/decoder.py) |
| M2 | [m2_storage/PRINCIPLES.md](m2_storage/PRINCIPLES.md) | [signal_store.py](m2_storage/signal_store.py) |
| M3 | [m3_judgment/PRINCIPLES.md](m3_judgment/PRINCIPLES.md) | [judgment_engine.py](m3_judgment/judgment_engine.py) |
| M4 | [m4_action/PRINCIPLES.md](m4_action/PRINCIPLES.md) | [action_designer.py](m4_action/action_designer.py) |
| M5 | [m5_position/PRINCIPLES.md](m5_position/PRINCIPLES.md) | [position_manager.py](m5_position/position_manager.py) |
| M6 | [m6_retrospective/PRINCIPLES.md](m6_retrospective/PRINCIPLES.md) | [retrospective.py](m6_retrospective/retrospective.py) |
| M7 | [m7_backtester/PRINCIPLES.md](m7_backtester/PRINCIPLES.md) | [backtester.py](m7_backtester/backtester.py) |
| M8 | [m8_knowledge/PRINCIPLES.md](m8_knowledge/PRINCIPLES.md) | [knowledge_base.py](m8_knowledge/knowledge_base.py) |

---

## 最近完成（2026-04-19）

**M2/M3推理引擎扩展**：
- M2新增因果图谱存储（CausalPattern）和历史案例存储（CaseRecord）
- M3新增推理引擎：_infer_future_events()（因果链推理）+ _retrieve_similar_cases()（案例检索）
- 初始化10个货币政策因果模式（降准/降息/政策宽松等场景）
- 回测验证：4个2023-2024历史案例，事件预测准确率100%，时间窗口准确率75%
- 核心能力升级：从"反应型判断"（看到降准公告才判断）→"推理型判断"（识别前置信号组合，提前14天预测降准概率80%）

---

## 当前最高优先级（后续迭代）

| # | 任务 | 状态 |
|---|------|------|
| 9.1 | 盘前/盘中/盘后工作流 | ✅ |
| 9.2 | 所有关键动作保留人工确认点 | ✅ |
| 9.3 | Dashboard 完善 | ✅ |
| 9.4 | 审计日志 | ✅ |
| 10.1 | M2/M3推理引擎扩展 | ✅ |

详细计划见：[docs/MarketRadar_Iteration_Plan_v2.md](docs/MarketRadar_Iteration_Plan_v2.md)

---

## 关键配置文件

- LLM 配置：[config/llm_config.yaml](config/llm_config.yaml)
- 信号分类：[config/signal_taxonomy.yaml](config/signal_taxonomy.yaml)
- 市场配置：[config/market_config.yaml](config/market_config.yaml)
- 风险参数：[config/risk_config.yaml](config/risk_config.yaml)
- 执行参数：[config/execution_config.yaml](config/execution_config.yaml)
- 机会规则：[config/opportunity_rules.yaml](config/opportunity_rules.yaml)
- 环境变量：`.env`（从 `.env.example` 复制后填写）

---

## 关键文档索引

| 文档 | 说明 |
|------|------|
| [docs/MarketRadar_Iteration_Plan_v2.md](docs/MarketRadar_Iteration_Plan_v2.md) | 当前迭代计划（v2，2026-04-17） |
| [docs/MarketRadar_Roadmap_v1.md](docs/MarketRadar_Roadmap_v1.md) | 整体演进路线图 |
| [docs/MarketRadar_Execution_Plan_v1.md](docs/MarketRadar_Execution_Plan_v1.md) | 旧执行计划（已被 v2 替代） |
| [docs/anchors/2026-04-14-architecture-plan-and-change-disposition-anchor.md](docs/anchors/2026-04-14-architecture-plan-and-change-disposition-anchor.md) | 架构校准锚点（仍然有效） |
| [MEMORY.md](MEMORY.md) | 项目记忆 & 环境注意事项 |
