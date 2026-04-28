# M12 机会补牢 — 实施计划

> **创建日期**: 2026-04-28
> **状态**: M12-RC 完成，可试运行

---

## 实施步骤

| 步骤 | 任务 | 依赖 | 预计 | 状态 |
|------|------|------|------|------|
| 0 | 设计文档落档 | 无 | 30min | ✅ 完成 |
| 1 | Bug修：M1.5管道接入run_daily_pipeline | 无 | 30min | ✅ 完成 |
| 2 | core/schemas.py 新增M12数据模型 | 无 | 30min | ✅ 完成 |
| 3 | anomaly_detector.py 异动检测核心 | 步骤2 | 2h | ✅ 完成 |
| 4 | backward_causation.py 反向溯源 | 步骤3+M0/M1可调用 | 2h | ✅ 完成 |
| 5 | trend_stage.py 趋势阶段判断 | 步骤4+M3可调用 | 1.5h | ✅ 完成 |
| 6 | market_strategies.py 三市场策略 | 步骤2 | 1h | ✅ 完成 |
| 7 | catcher_engine.py 主引擎编排 | 步骤3-6 | 1h | ✅ 完成 |
| 8 | run_daily_pipeline.py + live_signal_monitor.py 集成 | 步骤7 | 30min | ✅ 完成 |
| 9 | Dashboard补牢机会tab + M6埋点准备 | 步骤7 | 1h | ✅ 完成 |

## 依赖关系图

```
步骤1 (Bug修) ──────────────────────────────── 可独立完成
步骤2 (schemas) ────────────────────────────── 可独立完成
     │
步骤3 (anomaly_detector) ←── 步骤2
     │
步骤4 (backward_causation) ←── 步骤3 + M0/M1
     │
步骤5 (trend_stage) ←── 步骤4 + M3
     │
步骤6 (market_strategies) ←── 步骤2
     │
步骤7 (catcher_engine) ←── 步骤3,4,5,6
     │
步骤8 (pipeline集成) ←── 步骤7
     │
步骤9 (dashboard) ←── 步骤7
```

---

## 进展日志

### 2026-04-28 — 设计阶段

- [x] 模块目录创建
- [x] PRINCIPLES.md 第一性原理文档
- [x] DESIGN.md 设计文档
- [x] IMPLEMENTATION_PLAN.md 实施计划
- [x] 开始实施步骤1

### 2026-04-28 — 步骤1-7 完成

- [x] Bug修：M1.5管道接入 run_daily_pipeline（step_m1_5_implicit + 合并到premarket流程）
- [x] core/schemas.py 新增所有M12数据模型
- [x] anomaly_detector.py 异动检测核心（ATR+σ+量比双重条件，盘后+盘中两种模式）
- [x] backward_causation.py 反向溯源（M0定向采集+信号匹配+置信度评估）
- [x] trend_stage.py 趋势阶段判断（early/middle/late三阶段+原因持续性+剩余空间估算）
- [x] market_strategies.py 三市场差异化策略（A股/港股/美股）
- [x] catcher_engine.py 主引擎编排（daily_scan+intraday_scan+完整流程）
- [x] 全部模块导入测试通过

### 2026-04-28 — 步骤8-9 完成 + Bug修复

- [x] 步骤8: pipeline集成到 run_daily_pipeline.py（postmarket + intraday）
- [x] 步骤9: Dashboard补牢机会tab（扫描配置+结果展示+汇总表）
- [x] 全模块端到端导入测试通过
- [x] Bug修复：BaostockFeed缓存不区分日期（历史查询返回相同数据）
- [x] Bug修复：BaostockFeed新增批量接口 get_daily_prices（减少重复login/logout）
- [x] Bug修复：AnomalyDetector._check_instrument len(tuple)<lookback_days（tuple长度总是2）
- [x] Bug修复：BackwardCausation MarketSignal缺少 time_horizon/logic_frame 字段
- [x] Bug修复：OpportunityScore缺少8个必填字段（catalyst_strength等）
- [x] Bug修复：OpportunityObject缺少 uncertainty_map/next_validation_questions/time_window.end
- [x] Bug修复：日期加法导致月份溢出（day+7）
- [x] **M12 全流程端到端验证通过**：A股盘后扫描成功检测异动并生成RetroOpportunity

---

## 关键里程碑

- **M12-Alpha**: 异动检测可运行，A股盘后扫描能发现异动股票
- **M12-Beta**: 反向溯源+趋势判断可运行，完整流程走通
- **M12-RC**: 集成到主pipeline，Dashboard可展示补牢机会 ✅ 完成
- **M12-GA**: 模拟盘运行2周，数据驱动验证止损策略选择