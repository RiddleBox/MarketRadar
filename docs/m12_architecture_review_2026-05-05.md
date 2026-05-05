# M12扫描入口与持久化架构评估

**日期**: 2026-05-05  
**评估范围**: M12扫描的入口收束性、持久化规范性

---

## 一、当前入口分析

### M12扫描的调用入口（8个）

| 文件 | 类型 | 用途 | 持久化 |
|------|------|------|--------|
| **m7_scheduler/scheduler.py** | 生产调度器 | M7调度器的M12任务 | ✅ 有（retro/premarket/postmarket） |
| **run_continuous_simulation.py** | 独立脚本 | 持续模拟运行 | ✅ 有（m12_scan_results.json） |
| **run_full_scan.py** | 独立脚本 | 手动全量扫描 | ✅ 有（m12_scan_results.json） |
| **run_daily_pipeline.py** | 独立脚本 | 每日管道运行 | ❓ 未知 |
| **pipeline/dashboard.py** | Dashboard | 手动触发扫描 | ❌ 无（仅展示） |
| **test_a_share_scan.py** | 测试脚本 | A股扫描测试 | ❌ 无 |
| **m12_opportunity_catcher/catcher_engine.py** | 核心引擎 | 被其他模块调用 | N/A |
| **m12_opportunity_catcher/__init__.py** | 模块导出 | 导出接口 | N/A |

### 入口收束性问题 🔴

**问题**: 存在**3个独立的运行入口**，各自持久化到不同位置

```
生产环境:
  M7调度器 → data/retro_opportunities/*.json
              data/premarket_opportunities/*.json
              data/postmarket_opportunities/*.json

模拟环境:
  run_continuous_simulation.py → data/m12_scan_results.json
  run_full_scan.py → data/m12_scan_results.json

Dashboard:
  手动触发 → 无持久化（仅session_state）
```

**风险**:
1. **数据分散**: 生产数据和模拟数据存储在不同位置
2. **格式不一致**: `m12_scan_results.json` 只记录总数，`retro_opportunities/*.json` 记录详细对象
3. **职责不清**: 不清楚哪个是"官方"入口
4. **维护困难**: 修改持久化逻辑需要改3个地方

---

## 二、持久化现状分析

### M7调度器的持久化（标准）

```python
# m7_scheduler/scheduler.py:748-775
if retro_opps:
    retro_dir = ROOT / "data" / "retro_opportunities"
    retro_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    retro_file = retro_dir / f"{market.value.lower()}_{timestamp}.json"
    
    retro_data = []
    for retro in retro_opps:
        retro_data.append({
            "instrument": retro.anomaly.instrument,
            "market": retro.anomaly.market.value,
            "price_change_pct": retro.anomaly.price_change_pct,
            "trend_stage": retro.trend.stage.value,
            "causation_confidence": retro.causation.confidence,
            "remaining_upside_pct": retro.trend.remaining_upside_pct,
            "opportunity_id": retro.opportunity.opportunity_id,
            "priority": retro.opportunity.priority_level.value,
            "entry_constraint": retro.opportunity.entry_constraint.reason,
        })
    
    retro_file.write_text(json.dumps(retro_data, ...))
```

**特点**:
- ✅ 按市场分文件: `a_share_YYYYMMDD_HHMMSS.json`
- ✅ 记录详细对象: 包含异动、趋势、溯因、机会等完整信息
- ✅ 时间戳命名: 可追溯历史
- ✅ 三种扫描分开: retro（盘中）、premarket（盘前）、postmarket（盘后）

### run_continuous_simulation.py 的持久化（非标准）

```python
# run_continuous_simulation.py:585-607
def _save_results(total_count):
    results_file = "data/m12_scan_results.json"
    record = {
        "timestamp": datetime.now().isoformat(),
        "total_opportunities": total_count,
    }
    existing.append(record)
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, ...)
```

**特点**:
- ❌ 单一文件: 所有扫描记录追加到同一个文件
- ❌ 只记录总数: 丢失了详细的异动信息
- ❌ 不区分市场: 无法知道是哪个市场的扫描
- ❌ 不区分类型: 无法区分盘中/盘后扫描

### Dashboard 的持久化（无）

```python
# pipeline/dashboard.py
# 扫描结果存储在 st.session_state
# 刷新页面后丢失
```

**特点**:
- ❌ 无持久化: 仅存在于会话中
- ❌ 无法回溯: 无法查看历史扫描结果

---

## 三、持久化规范性评估

### 当前问题

| 问题 | 严重性 | 影响 |
|------|--------|------|
| **多入口写入同一文件** | 🔴 高 | `m12_scan_results.json` 被两个脚本写入，可能冲突 |
| **格式不统一** | 🔴 高 | M7调度器和模拟脚本的格式完全不同 |
| **盘中扫描无持久化** | 🟡 中 | M7调度器的盘中扫描结果只在有异动时保存 |
| **Dashboard无持久化** | 🟡 中 | 手动扫描结果无法追溯 |
| **数据分散** | 🟡 中 | 生产数据和模拟数据分开存储 |
| **缺少元数据** | 🟢 低 | 缺少扫描类型、市场、数据源等元数据 |

### 规范性对比

| 维度 | M7调度器 | run_continuous_simulation | run_full_scan | Dashboard |
|------|---------|--------------------------|---------------|-----------|
| 文件命名 | ✅ 时间戳+市场 | ❌ 固定文件名 | ❌ 固定文件名 | ❌ 无文件 |
| 数据完整性 | ✅ 详细对象 | ❌ 只有总数 | ✅ 分市场统计 | ✅ 完整对象 |
| 可追溯性 | ✅ 独立文件 | ⚠️ 追加记录 | ⚠️ 追加记录 | ❌ 无 |
| 区分扫描类型 | ✅ 三种目录 | ❌ 混在一起 | ❌ 不区分 | ❌ 不区分 |
| 区分市场 | ✅ 文件名 | ❌ 无 | ✅ 字段 | ✅ 对象 |

---

## 四、建议的架构改进

### 方案A: 统一入口（推荐）

**目标**: 所有M12扫描通过M7调度器统一管理

```
唯一入口: M7调度器
  ├─ m12_a_share_scan (盘中)
  ├─ m12_hk_scan (盘中)
  ├─ m12_us_scan (盘中)
  ├─ m12_premarket_* (盘前)
  └─ m12_postmarket_* (盘后)

持久化:
  data/m12_scans/
    ├─ intraday/
    │   ├─ a_share_20260505_093000.json
    │   ├─ hk_20260505_100000.json
    │   └─ us_20260505_220000.json
    ├─ premarket/
    │   └─ a_share_20260505_090000.json
    └─ postmarket/
        └─ a_share_20260505_153000.json

废弃:
  - run_continuous_simulation.py (功能合并到M7)
  - run_full_scan.py (改为调用M7 API)
  - m12_scan_results.json (迁移到新格式)
```

**优点**:
- ✅ 单一入口，职责清晰
- ✅ 统一持久化格式
- ✅ 便于监控和管理
- ✅ 避免数据冲突

**缺点**:
- ⚠️ 需要重构现有脚本
- ⚠️ 迁移历史数据

### 方案B: 分层架构（折中）

**目标**: 保留多入口，但统一持久化层

```
入口层:
  - M7调度器 (生产)
  - run_continuous_simulation.py (模拟)
  - Dashboard (手动)

持久化层 (统一):
  M12ScanLogger (新增)
    ├─ log_scan(scan_type, market, results)
    └─ 统一写入 data/m12_scans/

格式:
  {
    "scan_id": "uuid",
    "timestamp": "2026-05-05T10:30:00",
    "scan_type": "intraday|premarket|postmarket",
    "market": "A_SHARE|HK|US",
    "source": "m7_scheduler|simulation|dashboard",
    "total_opportunities": 3,
    "opportunities": [...],  // 详细对象
    "metadata": {
      "data_source": "FutuFeed",
      "scan_duration_ms": 1234,
      "stock_count": 5002
    }
  }
```

**优点**:
- ✅ 保留现有入口
- ✅ 统一持久化格式
- ✅ 易于扩展
- ✅ 向后兼容

**缺点**:
- ⚠️ 仍有多入口维护成本
- ⚠️ 需要新增持久化层

### 方案C: 现状优化（最小改动）

**目标**: 保持现状，但规范化持久化

**改进点**:
1. **run_continuous_simulation.py**:
   - 改为写入 `data/m12_scans/simulation_YYYYMMDD.json`
   - 记录详细对象，不只是总数
   - 区分盘中/盘后扫描

2. **run_full_scan.py**:
   - 改为写入 `data/m12_scans/manual_YYYYMMDD_HHMMSS.json`
   - 保持详细记录

3. **Dashboard**:
   - 手动扫描结果写入 `data/m12_scans/dashboard_YYYYMMDD_HHMMSS.json`

4. **M7调度器**:
   - 保持现有格式，但统一目录到 `data/m12_scans/`

**优点**:
- ✅ 改动最小
- ✅ 快速实施

**缺点**:
- ❌ 仍有多入口
- ❌ 格式仍不完全统一

---

## 五、盘中扫描持久化问题

### 当前状态

```python
# M7调度器的盘中扫描
if retro_opps:  # ← 只有发现异动时才保存
    retro_file.write_text(...)
```

**问题**: 
- ❌ 0异动的扫描**不记录**
- ❌ 无法区分"未扫描"和"扫描了但0异动"
- ❌ 无法统计扫描频率和成功率

### 建议改进

**始终记录扫描结果**，即使0异动：

```python
# 改进后
scan_result = {
    "scan_id": uuid.uuid4().hex,
    "timestamp": datetime.now().isoformat(),
    "scan_type": "intraday",
    "market": market.value,
    "total_opportunities": len(retro_opps),
    "opportunities": [r.to_dict() for r in retro_opps],
    "metadata": {
        "stock_scanned": len(stock_list),
        "scan_duration_ms": duration,
        "data_source": price_feed.__class__.__name__,
    }
}

# 始终保存
scan_file = f"data/m12_scans/intraday/{market.value.lower()}_{timestamp}.json"
scan_file.write_text(json.dumps(scan_result, ...))
```

**优点**:
- ✅ 完整的扫描历史
- ✅ 可统计扫描频率
- ✅ 可分析0异动的原因（数据源失败 vs 真的无异动）

---

## 六、推荐方案

### 短期（1周内）: 方案C - 现状优化

1. **统一目录结构**:
   ```
   data/m12_scans/
     ├─ scheduler/     # M7调度器
     ├─ simulation/    # run_continuous_simulation
     ├─ manual/        # run_full_scan
     └─ dashboard/     # Dashboard手动扫描
   ```

2. **规范化格式**:
   - 所有扫描记录包含: scan_type, market, source, opportunities
   - 始终记录，即使0异动

3. **废弃 m12_scan_results.json**:
   - 迁移历史数据到新格式
   - 更新 Dashboard 读取逻辑

### 中期（1个月内）: 方案B - 分层架构

1. **新增 M12ScanLogger**:
   ```python
   # m12_opportunity_catcher/scan_logger.py
   class M12ScanLogger:
       def log_scan(self, scan_type, market, results, source, metadata):
           # 统一持久化逻辑
   ```

2. **所有入口调用统一接口**:
   ```python
   logger = M12ScanLogger()
   logger.log_scan(
       scan_type="intraday",
       market=Market.A_SHARE,
       results=retro_opps,
       source="m7_scheduler",
       metadata={...}
   )
   ```

### 长期（3个月内）: 方案A - 统一入口

1. **废弃独立脚本**:
   - run_continuous_simulation → M7调度器
   - run_full_scan → M7 CLI命令

2. **统一管理界面**:
   - Dashboard 通过 M7 API 触发扫描
   - 所有扫描通过 M7 调度器

---

## 七、总结

### 当前问题

1. 🔴 **入口分散**: 3个独立入口，职责不清
2. 🔴 **格式不统一**: M7调度器 vs 模拟脚本格式不同
3. 🟡 **盘中扫描无完整记录**: 0异动不记录
4. 🟡 **数据分散**: 生产和模拟数据分开存储

### 建议优先级

**P0 (立即)**:
- 统一目录结构到 `data/m12_scans/`
- 盘中扫描始终记录（包括0异动）

**P1 (本周)**:
- 规范化所有持久化格式
- 废弃 `m12_scan_results.json`

**P2 (本月)**:
- 实现统一持久化层 `M12ScanLogger`
- 所有入口调用统一接口

**P3 (长期)**:
- 评估是否需要统一入口
- 废弃冗余脚本

### 对实盘影响

- ✅ **不影响**: 这些都是架构优化，不影响核心交易逻辑
- ⚠️ **需注意**: 迁移时保持向后兼容，避免丢失历史数据
