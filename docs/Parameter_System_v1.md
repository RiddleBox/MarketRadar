# Parameter System v1

## 1. 目标

将原先散落在代码中的风险预算、止损止盈、计划有效期、分阶段建仓模板等参数，统一沉淀到配置文件中，形成跨模块共享的参数系统。

当前目标不是一次性做成完整风控引擎，而是先完成第一轮“参数外置化”，让 M4、回测、模拟盘后续可在同一语义下继续演进。

---

## 2. 配置文件

### 2.1 `config/risk_config.yaml`
负责定义：
- 全局风险上限
- 按优先级划分的风险预算
- 按品类划分的默认止损/止盈与仓位上限

### 2.2 `config/execution_config.yaml`
负责定义：
- 行动计划有效期
- 分阶段建仓模板
- 默认 review trigger
- 默认止损止盈执行参数

### 2.3 `config/opportunity_rules.yaml`
负责定义：
- M3 评分卡的使用边界
- 后续模块消费约定
- opportunity priority 语义说明

---

## 3. 当前已接入的模块

### M4 Action Designer
当前已从配置文件读取：
- `priority_risk_budget_pct`
- `plan_validity_days`
- `instrument_risk_overrides`
- `phase_templates`
- `default_review_triggers`
- `fallback_stop_loss`
- `fallback_take_profit`

这意味着：
- M4 不再只依赖硬编码常量
- 不同优先级与品类的默认参数可以通过 YAML 调整

---

## 4. 边界说明

参数系统的职责是：
- 提供统一、可维护、可复用的约束与模板
- 让 M4 / 回测 / 模拟盘共享同一套语义

参数系统当前**不负责**：
- 推翻 M3 的机会判断
- 动态盘中风险控制
- 多账户资金分配
- 组合优化

---

## 5. 下一步

后续可继续推进：
1. 让回测系统直接消费相同参数
2. 让模拟盘系统使用同一套仓位/止损/有效期定义
3. 为不同机会类型增加更细化模板
4. 增加参数校验与 schema
