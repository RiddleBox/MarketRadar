# PROJECT_CONTEXT.md — MarketRadar 开工必读

> **文档类型**：项目状态总览 + 开工上下文
> **最后更新**：2026-04-13（初始版本）
> **当前阶段**：项目骨架建立，Phase 1 开发中

---

## 一句话当前状态

> 项目骨架已建立（所有模块目录 + PRINCIPLES.md + 核心代码框架），尚未接入真实 LLM API 进行端到端验证。

---

## 模块状态总览

| 模块 | 目录 | 状态 | 说明 |
|------|------|------|------|
| M1 信号解码 | `m1_decoder/` | 🟡 代码框架完成 | decoder.py + prompt_templates.py 已写，待真实 LLM 验证 |
| M2 信号存储 | `m2_storage/` | 🟡 代码框架完成 | SQLite 存储，待集成测试 |
| M3 机会判断 | `m3_judgment/` | 🟡 代码框架完成 | Step A/B 框架，待真实 LLM 验证 |
| M4 行动设计 | `m4_action/` | 🟡 代码框架完成 | 含止损/止盈/仓位逻辑，待验证 |
| M5 持仓管理 | `m5_position/` | 🟡 代码框架完成 | 持久化 + 止损检查，待集成测试 |
| M6 复盘归因 | `m6_retrospective/` | 🟡 代码框架完成 | LLM 驱动归因，待验证 |
| M7 回测引擎 | `m7_backtester/` | 🟡 代码框架完成 | 前向隔离逻辑，待接入真实数据 |
| M8 知识库 | `m8_knowledge/` | 🟡 代码框架完成 | JSON 存储，待填充初始知识文档 |
| Pipeline | `pipeline/` | 🟡 CLI 已写 | run_pipeline.py + run_backtest.py + dashboard.py |
| 测试 | `tests/` | 🟡 框架完成 | test_schemas.py + test_m1.py，待 LLM mock 验证 |

**状态图例**：⏳ 待开始 | 🟡 进行中 | ✅ 完成 | ❌ 有问题

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
- **M1+M2**：结构化信号，跨批次积累
- **M3**：系统性判断，有合法的"不构成机会"出口
- **M4+M5**：行动和判断绑定，止损在入场前确定
- **M6+M7**：复盘和回测，让判断力持续迭代

### 核心约束（永远不能违反）
1. 机会必须有信号溯源
2. 回测必须前向隔离（event_time 是时间基准）
3. 止损在入场前确定，持仓期间不随情绪修改
4. M3 的空列表输出是健康行为，不是系统错误

---

## 各模块文档索引

| 模块 | PRINCIPLES.md | 核心代码 |
|------|--------------|---------|
| M1 | [m1_decoder/PRINCIPLES.md](m1_decoder/PRINCIPLES.md) | [decoder.py](m1_decoder/decoder.py) |
| M2 | [m2_storage/PRINCIPLES.md](m2_storage/PRINCIPLES.md) | [signal_store.py](m2_storage/signal_store.py) |
| M3 | [m3_judgment/PRINCIPLES.md](m3_judgment/PRINCIPLES.md) | [judgment_engine.py](m3_judgment/judgment_engine.py) |
| M4 | [m4_action/PRINCIPLES.md](m4_action/PRINCIPLES.md) | [action_designer.py](m4_action/action_designer.py) |
| M5 | [m5_position/PRINCIPLES.md](m5_position/PRINCIPLES.md) | [position_manager.py](m5_position/position_manager.py) |
| M6 | [m6_retrospective/PRINCIPLES.md](m6_retrospective/PRINCIPLES.md) | [retrospective.py](m6_retrospective/retrospective.py) |
| M7 | [m7_backtester/PRINCIPLES.md](m7_backtester/PRINCIPLES.md) | [backtester.py](m7_backtester/backtester.py) |
| M8 | [m8_knowledge/PRINCIPLES.md](m8_knowledge/PRINCIPLES.md) | [knowledge_base.py](m8_knowledge/knowledge_base.py) |

---

## 当前最高优先级（Phase 1）

| # | 任务 | 状态 |
|---|------|------|
| P0-1 | 配置 .env，验证 LLM API 连通性 | ⏳ |
| P0-2 | 运行 `pytest tests/` 确认 Schema 和 Mock 测试通过 | ⏳ |
| P0-3 | 用一段真实文本跑 M1，验证信号解码质量 | ⏳ |
| P0-4 | M1→M2→M3 端到端联调，验证机会判断输出 | ⏳ |
| P0-5 | M4 行动设计联调，验证止损/止盈生成质量 | ⏳ |

---

## 关键配置文件

- LLM 配置：[config/llm_config.yaml](config/llm_config.yaml)
- 信号分类：[config/signal_taxonomy.yaml](config/signal_taxonomy.yaml)
- 市场配置：[config/market_config.yaml](config/market_config.yaml)
- 环境变量：`.env`（从 `.env.example` 复制后填写）

---

## 架构设计文档

详见工作区：`C:\Users\Administrator\.openclaw\workspace\MarketRadar_Architecture_v1.md`
