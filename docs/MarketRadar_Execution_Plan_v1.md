# MarketRadar 具体执行计划 v1

## 1. 目标

本计划用于把当前已经打通的 `M1 -> M3 -> M4` 原型链路，继续推进为一个可验证、可复盘、可持续迭代的系统。

执行原则：
- 每一阶段都必须有明确产出物
- 每个模块优化都尽量能被测试验证
- 优先解决影响全局质量的核心问题，而不是局部锦上添花

---

## 2. 当前基线

当前已完成：
- 统一 LLM 配置：`config/llm_config.yaml`
- 统一 LLM 调用入口：`core/llm_client.py`
- 工蜂AI接入完成
- DeepSeek 真实可用验证完成
- DeepSeek 下 `M1 -> M3 -> M4` 主链路跑通
- M3 已完成一轮 schema/枚举容错增强

当前建议的联调默认 provider：
- `deepseek`

---

## 3. 分阶段任务规划

# Phase 1：联调与基础稳定性收敛

## P1-1. 固化当前联调默认 provider
目标：避免后续测试继续被工蜂AI 429 限流干扰。

任务：
- 将当前联调脚本统一切到 `deepseek`
- 保留 `gongfeng` / `xfyun` / `openai` 的 fallback 能力
- 补充 provider 使用说明文档

产出物：
- 稳定可复现的联调脚本
- provider 使用约定文档

验收标准：
- `M1 -> M3 -> M4` 可稳定在 DeepSeek 下复现

---

## P1-2. 清理/统一测试脚本
目标：减少“脚本字段已过时、输出口径不一致”的问题。

任务：
- 统一 `test_pipeline.py`
- 清理重复或废弃测试脚本
- 统一命名规范：`test_*`, `run_*`
- 区分 smoke / provider test / module test / e2e test

产出物：
- 干净的测试脚本集合
- README 中补充测试入口说明

验收标准：
- 任意测试脚本都能明确说明用途、输入、预期输出

---

## P1-3. 完善 LLMClient provider 切换逻辑
目标：让 fallback 真正可控、可解释。

任务：
- 修复 gongfeng 429 后自动 fallback 的执行路径
- 为 provider 增加更明确的 debug 日志
- 增加 provider 健康检查工具函数
- 区分认证失败 / 限流 / 超时 / 解析失败

产出物：
- 更稳的 `core/llm_client.py`
- provider health check 脚本

验收标准：
- 工蜂AI限流时，能明确看到实际切换到哪个 provider
- fallback 行为与日志一致

---

# Phase 2：M3 机会判断升级

## P2-1. 构建显式机会评分框架
目标：让 M3 不再只是“是/否判断”，而是可解释的综合评分。

建议评分维度：
- catalyst_strength
- timeliness
- market_confirmation
- tradability
- risk_clarity
- consensus_gap
- signal_consistency

任务：
- 设计 `opportunity_score` schema
- 在 M3 输出中加入分维度评分
- 保留 LLM 原始判断，同时增加规则约束

产出物：
- 评分版 `OpportunityObject` 扩展字段
- 对应 prompt / parser / validation 更新

验收标准：
- 每个机会都能解释为什么是 `watch / research / position / urgent`

---

## P2-2. 增加 invalidation / kill switch 机制
目标：把“为什么成立”与“何时失效”同时结构化。

任务：
- 增加 `invalidation_conditions`
- 增加 `must_watch_indicators`
- 增加 `kill_switch_signals`

产出物：
- M3 输出字段扩展
- 与 M4 / M5 的联动接口定义

验收标准：
- 每个 position/urgent 级机会都具备失效条件

---

## P2-3. 历史上下文增强
目标：让 M3 能区分“陈旧旧闻”与“真正新机会”。

任务：
- 接入历史相似事件检索
- 增加时间衰减规则
- 增加同主题连续事件合并机制

产出物：
- 历史辅助判断接口
- 机会聚合规则草案

验收标准：
- 同类旧事件不会轻易误判为新机会
- 连续催化能提高机会评分

---

# Phase 3：参数系统完善

## P3-1. 建立统一参数配置体系
状态：已完成第一阶段（参数文件落地 + M4 第一轮接入）

目标：避免风控、执行、机会阈值散落在代码中。

建议拆分配置：
- `config/risk_config.yaml`
- `config/execution_config.yaml`
- `config/opportunity_rules.yaml`

任务：
- 梳理现有硬编码参数
- 分层迁移到配置文件
- 增加配置读取与默认值校验

产出物：
- 参数配置文件
- 参数说明文档

验收标准：
- M3/M4/回测/模拟盘共享同一套参数语义

---

## P3-2. 参数分层设计
状态：已完成第一阶段（风险/执行/机会规则三层落地，后续继续扩展）

建议层级：
1. 全局风险参数
2. 机会级参数
3. 标的级参数
4. 执行级参数

任务：
- 定义每层参数字段
- 设计继承与覆盖关系
- 与 M4 行动设计器对接

验收标准：
- 不同机会类型能加载不同模板参数

---

# Phase 4：M4 行动设计升级

## P4-1. 品类化动作模板
状态：已完成第一阶段（M4 已支持按 instrument_type 选择 phase template）

目标：不同品类输出不同执行方案。

任务：
- 区分 ETF / 股票 / 期货 / 债券 / 指数
- 定义各自默认止损/止盈/分批建仓逻辑
- 按 `priority_level` 与 `instrument_type` 组合控制模板

产出物：
- 模板化 `ActionDesigner`
- 更细化的 action schema

验收标准：
- 相同机会换不同标的类型，生成计划应有明显差异

---

## P4-2. 计划有效期与复核机制增强
任务：
- 增加 review cadence
- 增加 plan refresh 条件
- 增加“入场失败后的替代方案”

验收标准：
- 行动计划不再是一次性静态文本，而是可复核的计划对象

---

# Phase 5：情绪讨论 Agent 扩展

## P5-1. 明确角色定位
目标：情绪 agent 作为 M3 的辅助修正因子，而不是独立拍板器。

任务：
- 定义情绪 agent 输入源
- 定义输出 schema：
  - sentiment_direction
  - sentiment_strength
  - attention_heat
  - crowding_risk
  - narrative_consensus
  - opposing_views

验收标准：
- 情绪输出可被 M3 调用，而不是只生成一段文本

---

## P5-2. 叙事图谱增强
目标：不只看情绪方向，还看市场叙事是否扩散、拥挤、分裂。

任务：
- 聚合多来源观点
- 提取主叙事/反叙事
- 建立主题-观点-热度映射

---

# Phase 6：回测系统升级

## P6-1. OpportunityObject 驱动回测
状态：已完成第一阶段（BacktestTask / mapper / 最小回测执行器已落地）

目标：让回测与机会对象直接对齐。

任务：
- 用 `OpportunityObject` 生成标准回测任务
- 支持不同持有期、止损止盈、分批建仓的参数扫描
- 输出收益/回撤/胜率/盈亏比分布

验收标准：
- 任意机会对象都能映射成可回测任务

---

## P6-2. 事件型回测模板
目标：优先验证政策/宏观宽松类机会。

任务：
- 建立政策宽松事件回测模板
- 评估 T+1/T+3/T+5/T+10 表现
- 对 ETF / 指数 / 期货 做横向对比

---

# Phase 7：模拟盘系统升级

## P7-1. 机会对象与模拟仓位绑定
状态：已完成第一阶段（SimulatedExecutionSpec / mapper / 最小模拟执行器已落地）

任务：
- 每一笔模拟仓必须绑定 `opportunity_id`
- 记录入场逻辑、执行计划、退出理由、盈亏归因

验收标准：
- 任意模拟仓位都可追溯来源机会

---

## P7-2. 模拟执行真实化
任务：
- 引入滑点、手续费、流动性约束、最小成交单位
- 支持无法成交、跳空、价格缺口等情况

验收标准：
- 模拟盘表现比当前“理想成交模型”更贴近现实

---

## P7-3. 与 M6 复盘闭环
任务：
- 自动输出复盘材料
- 归因判断问题出在 M3 / M4 / 参数 / 市场 regime

---

# Phase 8：走向实用性工具

## P8-1. 建立组合级风控
任务：
- 最大总仓位
- 主题暴露上限
- 单市场暴露上限
- 高相关性机会去重

## P8-2. 建立盘前/盘中工作流
任务：
- 盘前：机会扫描、优先级排序、行动计划生成
- 盘中：持仓状态检查、失效条件触发、提醒/调整建议
- 盘后：复盘与归因

## P8-3. 建立人机协作模式
目标：把系统打造成交易研究助手，而不是黑箱自动交易器。

任务：
- 所有关键动作保留人工确认点
- 提供清晰解释而非只给结论
- 保留审计日志

---

## 4. 建议执行顺序

建议严格按以下顺序推进：

1. P1 联调稳定性收敛
2. P2 M3 评分化与机会引擎增强
3. P3 参数系统配置化
4. P4 M4 行动设计参数化
5. P6 回测系统升级
6. P7 模拟盘系统升级
7. P5 情绪讨论 agent 扩展
8. P8 实用性工具化

说明：
- 情绪 agent 很重要，但优先级不应高于 M3/M4/参数/回测/模拟盘这些基础设施
- 否则系统容易变得“更会讲故事”，但不更可用

---

## 5. 建议下一步立即开工任务

### Task 1
将 DeepSeek 固化为当前联调默认 provider，并整理统一测试入口。

### Task 2
为 M3 设计评分版输出 schema，并完成字段定义。

### Task 3
梳理现有硬编码参数，设计参数配置文件结构。

### Task 4
定义 OpportunityObject 到回测任务的映射接口。

### Task 5
定义模拟仓位与 opportunity/action_plan 的绑定结构。

---

## 7. 当前迭代锚点（截至 Task 3 收口）

### 已完成锚点
- DeepSeek 已作为当前联调默认 provider
- M3 评分卡与失效条件已落地，并明确为解释层输出
- 参数系统已形成三份配置文件：
  - `config/risk_config.yaml`
  - `config/execution_config.yaml`
  - `config/opportunity_rules.yaml`
- M4 已接入参数系统，并支持按 `instrument_type` 选择 phase template

### 进入 Task 4 前的边界提醒
- 参数系统是共享语义层，不是新的裁决层
- 回测/模拟盘后续应优先复用 Task 3 参数，不应再私造一套平行参数体系

### 截至 Task 4 收口的新增锚点
- 回测主线已形成：`OpportunityObject -> BacktestTask -> BacktestSummary`
- 模拟执行主线已形成：`ActionPlan -> SimulatedExecutionSpec -> SimulatedExecutionResult`
- 当前两条链均为“最小可执行验证器”，下一步应优先补数据接入层与真实市场约束

---

## 6. 阶段验收口径

每一轮迭代建议都满足：
- 有明确代码改动
- 有文档更新
- 有测试脚本
- 有可复现的验证结果
- 有 git commit 与 push

这样后续推进时，系统会越来越像一个真正可维护的交易研究平台，而不是一堆散落的试验脚本。
