# M3 机会评分 Schema v1

## 1. 目标

把 M3 从“是否构成机会”的单点判断，升级为“可解释、可评分、可验证”的机会引擎。

本版扩展的核心思路：
- 保留 `OpportunityObject` 作为统一中枢对象
- 增加 `opportunity_score` 评分卡
- 增加 `invalidation_conditions` / `must_watch_indicators` / `kill_switch_signals`
- 为后续 M4、回测、模拟盘、复盘提供统一输入

---

## 2. 新增字段

### 2.1 opportunity_score
类型：`OpportunityScore`

包含以下维度：
- `catalyst_strength`：催化强度
- `timeliness`：时效性
- `market_confirmation`：市场确认度
- `tradability`：可交易性
- `risk_clarity`：风险边界清晰度
- `consensus_gap`：预期差大小
- `signal_consistency`：信号一致性
- `overall_score`：综合得分（0-10）
- `confidence_score`：机会判断置信度（0-1）
- `execution_readiness`：执行就绪度（0-1）

### 2.2 invalidation_conditions
机会失效条件。用于说明“什么发生时，这个机会应被重新评估或终止”。

### 2.3 must_watch_indicators
必须持续跟踪的验证指标。用于盘中/盘后跟踪、模拟盘监控与复盘。

### 2.4 kill_switch_signals
一旦出现即应快速放弃该机会的危险信号。用于执行层快速防御。

---

## 3. 评分维度定义

### catalyst_strength
衡量催化剂本身的力度与级别。

参考：
- 1-3：弱催化，小级别边际变化
- 4-6：中等催化，有一定影响但未必改变市场主线
- 7-8：强催化，对风险偏好或盈利预期有明显影响
- 9-10：系统性催化，可能触发大级别重估

### timeliness
衡量信号是否具备“现在就值得看”的时效性。

### market_confirmation
衡量市场是否已经出现量价、资金流或跨市场联动确认。

### tradability
衡量机会是否容易落实为实际可执行的仓位。

### risk_clarity
衡量止损逻辑、失效条件、风险边界是否足够清晰。

### consensus_gap
衡量市场预期差。越是未被充分 price-in，分值越高。

### signal_consistency
衡量多条信号是否共同指向同一方向与同一叙事。

### overall_score
综合得分，建议作为后续优先级映射、回测分桶、模拟盘筛选的重要依据。

### confidence_score
对机会成立本身的信心。

### execution_readiness
对“当前是否适合进入执行动作”的准备度评分。

---

## 4. 与后续模块的衔接

### 对 M4
- `opportunity_score.overall_score` 可用于影响计划激进程度
- `execution_readiness` 可影响建仓节奏
- `risk_clarity` 可影响止损模板选择

### 对回测系统
- 用于机会分桶评估
- 用于回测样本质量分层
- 用于检验“高分机会是否显著优于低分机会”

### 对模拟盘系统
- 用于控制是否允许进入模拟仓
- 用于控制初始仓位上限
- 用于监控机会是否仍处于可执行区间

### 对复盘系统
- 用于检验评分维度是否具有预测力
- 用于识别哪类评分维度经常高估/低估

---

## 5. 当前实现策略

当前先采用“LLM 原始输出优先 + 本地兜底回填”的方式：
- 如果 LLM 已输出评分字段，优先使用
- 如果未输出，则根据信号强度/时效/数量等做默认估算

这是过渡方案。
后续应逐步把评分逻辑做成：
- LLM 判断 + 规则校正 + 参数配置

---

## 6. 下一步

下一步建议：
1. 更新 M3 prompt，让模型显式输出评分卡
2. 设计 `priority_level` 与 `overall_score` / `execution_readiness` 的映射规则
3. 让 M4 根据评分卡调整动作模板
4. 让回测与模拟盘消费这些新字段
