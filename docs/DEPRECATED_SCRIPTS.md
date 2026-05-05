# 已废弃脚本说明

## 废弃时间
2026-05-05

## 废弃原因
M12扫描功能已统一到M7调度器，独立脚本造成入口分散、数据不一致、职责不清。

## 废弃脚本列表

### 1. run_continuous_simulation.py
**原功能**: 独立运行盘中/盘后扫描，写入`m12_scan_results.json`

**废弃原因**:
- 与M7调度器功能重复
- 持久化位置不规范（根目录data/）
- 4小时盘后扫描无实际意义
- 无时间窗口限制，休市时段空扫描

**替代方案**: 使用M7调度器的M12任务
- 盘中扫描: `_task_m12_market_scan()` (10分钟间隔)
- 盘后扫描: `_task_m12_postmarket_scan()` (每日一次)

### 2. run_full_scan.py
**原功能**: 手动触发全量扫描

**废弃原因**:
- 与M7调度器的盘前/盘后扫描功能重复
- 持久化格式不一致
- 缺少市场分轨逻辑

**替代方案**: 使用M7调度器的盘前/盘后任务
- 盘前扫描: `_task_m12_premarket_scan()` (每日08:30/20:30)
- 盘后扫描: `_task_m12_postmarket_scan()` (每日15:30/16:30/05:00)

## 数据迁移

旧数据已备份至: `data/backups/m12_migration_20260505_150042/`

新数据位置:
```
data/m12_scans/
├── intraday/      # 盘中扫描 (10分钟间隔)
├── premarket/     # 盘前扫描 (每日一次)
└── postmarket/    # 盘后扫描 (每日一次)
```

## 如何使用新架构

### 启动M7调度器
```bash
python -m m7_scheduler.scheduler
```

### 查看扫描结果
```python
from pathlib import Path
import json

# 读取最新盘中扫描
intraday_files = sorted(Path("data/m12_scans/intraday").glob("*.json"))
if intraday_files:
    with open(intraday_files[-1]) as f:
        latest_scan = json.load(f)
        print(f"发现 {latest_scan['summary']['total_opportunities']} 个异动")
```

### Dashboard集成
Dashboard已更新为读取新目录结构，无需手动操作。

## 回滚方案

如需回滚到旧架构:
```bash
# 1. 恢复备份数据
cp data/backups/m12_migration_20260505_150042/* data/

# 2. 使用旧脚本
python run_continuous_simulation.py

# 3. 恢复scheduler.py (git checkout)
git checkout HEAD~1 m7_scheduler/scheduler.py
```

## 相关文档
- [M12重构计划](m12_refactor_plan_unified_2026-05-05.md)
- [风险分析](m12_refactor_risk_analysis_2026-05-05.md)
- [架构决策](m12_refactor_final_answer_2026-05-05.md)
