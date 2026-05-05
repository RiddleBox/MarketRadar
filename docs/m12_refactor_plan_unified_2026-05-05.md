# M12入口统一与持久化重构方案（修正版）

**日期**: 2026-05-05  
**最后更新**: 2026-05-05 14:30  
**目标**: 统一M12持久化 + 优化signal_pipeline配置  
**原则**: 实盘与模拟盘共用同一套架构，区别仅在执行层

---

## 📋 重构范围调整说明

### 原方案问题

**删除的内容**:
- ❌ 不新增 M12 盘中主动信号扫描（与 signal_pipeline 重复）

**原因**:
1. signal_pipeline 已实现完整的显式+隐式信号处理链
2. signal_pipeline 支持隐式推理（通过传入90天历史信号）
3. 新增 M12 盘中信号扫描会导致功能重复且不支持隐式推理（功能退化）

### 修正后的方案

**保留**:
1. ✅ 统一 M12 价格异动扫描的持久化层
2. ✅ 废弃独立脚本（run_continuous_simulation.py, run_full_scan.py）
3. ✅ 更新 Dashboard 读取逻辑

**新增**:
4. ✅ 优化 signal_pipeline 配置
   - 添加时间窗口：`time_window=("09:00", "22:00")`（避免休市时段运行）
   - 缩短间隔：`interval_minutes=15`（从30分钟改为15分钟，提高响应速度）

### 架构理解

**两条平行轨道（互补，非重复）**:

```
轨道1: signal_pipeline（深度分析）
  职责: 完整的显式+隐式信号处理
  频率: 15分钟（修正后）
  时间窗口: 09:00-22:00（新增）
  流程: M1解码 → M2存储 → 查询历史信号(90天) → M3判断(隐式推理) → M4行动设计
  特点: 慢但深，发现隐藏机会（二阶/三阶信息）
  示例: "中沙签署新能源合作" → 推理出光伏产业链受益

轨道2: M12 扫描（快速响应）
  职责: 快速机会发现（仅显式信号）
  频率: 10分钟
  时间窗口: 交易时段（已有）
  流程: M0采集/价格异动 → M1解码 → M2存储 → M3判断(无历史信号)
  特点: 快但浅，抢时间窗口
  示例: "某公司业绩预增" → 直接生成机会
```

**两者互补**:
- signal_pipeline: 发现别人看不到的机会（隐式推理）
- M12: 快速捕获显式机会（时效性）

---

## 一、目标架构

```
M7调度器任务:
  ├─ M12 盘中扫描（10分钟）
  │   ├─ m12_a_share_scan
  │   ├─ m12_hk_scan
  │   └─ m12_us_scan
  ├─ M12 盘前扫描（每天一次）
  │   ├─ m12_premarket_a_share
  │   ├─ m12_premarket_hk
  │   └─ m12_premarket_us
  ├─ M12 盘后扫描（每天一次）
  │   ├─ m12_postmarket_a_share
  │   ├─ m12_postmarket_hk
  │   └─ m12_postmarket_us
  └─ signal_pipeline（15分钟，09:00-22:00）← 新增优化

统一持久化:
  data/m12_scans/
    ├─ intraday/
    │   ├─ a_share_20260505_093000.json
    │   ├─ hk_20260505_100000.json
    │   └─ us_20260505_220000.json
    ├─ premarket/
    │   ├─ a_share_20260505_090000.json
    │   ├─ hk_20260505_090000.json
    │   └─ us_20260505_210000.json
    └─ postmarket/
        ├─ a_share_20260505_153000.json
        ├─ hk_20260505_163000.json
        └─ us_20260505_050000.json

废弃:
  ❌ run_continuous_simulation.py
  ❌ run_full_scan.py
  ❌ data/m12_scan_results.json
```

---

## 二、重构步骤

### Step 0: 数据备份（10分钟）

运行数据迁移脚本，备份旧数据：

```bash
python scripts/migrate_m12_data.py
```

### Step 1: 创建统一持久化层（30分钟）

创建 `m12_opportunity_catcher/scan_logger.py`

### Step 2: 修改M7调度器（30分钟）

修改 `m7_scheduler/scheduler.py`：
1. 导入 M12ScanLogger
2. 修改盘中/盘前/盘后扫描任务使用统一持久化
3. 删除旧的持久化逻辑

### Step 3: 优化signal_pipeline配置（10分钟）

修改 `m7_scheduler/scheduler.py` 中的 signal_pipeline 任务配置：
- 间隔从30分钟改为15分钟
- 添加时间窗口 09:00-22:00

### Step 4: 更新Dashboard（20分钟）

修改 `pipeline/dashboard.py`，使用 M12ScanLogger 读取新的持久化位置

### Step 5: 废弃旧脚本（10分钟）

重命名旧脚本为 `.bak` 后缀，创建说明文档

---

## 三、时间估算

| 步骤 | 工作量 | 风险 |
|------|--------|------|
| Step 0: 数据备份 | 10分钟 | 无 |
| Step 1: 统一持久化层 | 30分钟 | 低 |
| Step 2: 修改M7调度器 | 30分钟 | 低 |
| Step 3: 优化signal_pipeline | 10分钟 | 低 |
| Step 4: 更新Dashboard | 20分钟 | 低 |
| Step 5: 废弃旧脚本 | 10分钟 | 无 |
| **总计** | **2小时** | **低** |

---

## 四、实施顺序

1. ✅ Step 0: 数据备份
2. ✅ Step 1: 创建统一持久化层
3. ✅ Step 2: 修改M7调度器
4. ✅ Step 3: 优化signal_pipeline
5. ✅ Step 4: 更新Dashboard
6. ✅ Step 5: 废弃旧脚本
7. ✅ 测试验证

---

## 五、重构后的优势

### 1. 架构清晰

```
之前:
  M7调度器 ──┐
  run_continuous_simulation ──┼──> 多个持久化位置
  run_full_scan ──┘
  Dashboard ──┘

之后:
  M7调度器 ──> 统一持久化层 ──> data/m12_scans/
  Dashboard ──┘
```

### 2. 数据完整

- 所有扫描始终记录（包括0异动）
- 详细信息：异动、趋势、溯因、机会

### 3. 信号处理优化

- signal_pipeline 响应速度提升（30分钟 → 15分钟）
- 避免休市时段运行（节省资源）
- 与M12扫描互补（深度分析 + 快速响应）

### 4. 实盘就绪

```
模拟盘:
  M7调度器 → M12扫描 → M3判断 → M4策略 → M9 PaperTrader

实盘:
  M7调度器 → M12扫描 → M3判断 → M4策略 → M9 RealTrader
  
区别: 只需替换 M9 的实现类
```

---

## 六、参考文档

- [风险分析](m12_refactor_risk_analysis_2026-05-05.md)
- [类型差异分析](m12_type_difference_analysis_2026-05-05.md)
- [信号扫描缺口分析](m12_signal_scan_gap_analysis_2026-05-05.md)
- [最终回答](m12_refactor_final_answer_2026-05-05.md)
