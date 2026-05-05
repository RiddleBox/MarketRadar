# M12重构方案风险检查与问题分析

**日期**: 2026-05-05  
**检查范围**: 重构方案的潜在风险、隐藏问题、兼容性

---

## 一、发现的关键问题

### 🔴 问题1: 盘前扫描返回类型不同

**问题描述**:
```python
# 盘中/盘后扫描返回: List[RetroOpportunity]
retro_opps = engine.run_intraday_scan(...)
retro_opps = engine.run_daily_scan(...)

# 盘前扫描返回: List[OpportunityObject]
opportunities = engine.judge(...)  # M3判断引擎
```

**数据结构差异**:
```python
# RetroOpportunity (盘中/盘后)
class RetroOpportunity:
    anomaly: PriceAnomaly          # 价格异动
    trend: TrendAssessment         # 趋势判断
    causation: CausationResult     # 溯因结果
    opportunity: OpportunityObject # 机会对象

# OpportunityObject (盘前)
class OpportunityObject:
    opportunity_id: str
    opportunity_title: str
    priority_level: PriorityLevel
    trade_direction: Direction
    target_instruments: List[str]
    opportunity_score: OpportunityScore
    # ... 没有 anomaly, trend, causation
```

**影响**:
- ❌ `M12ScanLogger._serialize_opportunity()` 无法处理 `OpportunityObject`
- ❌ 会导致 `AttributeError: 'OpportunityObject' object has no attribute 'anomaly'`

**解决方案**:
```python
class M12ScanLogger:
    def log_scan(self, scan_type, market, results, ...):
        # 根据扫描类型选择序列化方法
        if scan_type == "premarket":
            opportunities = [self._serialize_premarket_opportunity(r) for r in results]
        else:
            opportunities = [self._serialize_retro_opportunity(r) for r in results]
    
    def _serialize_retro_opportunity(self, retro: RetroOpportunity) -> dict:
        """序列化 RetroOpportunity（盘中/盘后）"""
        return {
            "instrument": retro.anomaly.instrument,
            "anomaly_type": retro.anomaly.anomaly_type,
            "price_change_pct": retro.anomaly.price_change_pct,
            "trend_stage": retro.trend.stage.value,
            "causation_confidence": retro.causation.confidence,
            "opportunity_id": retro.opportunity.opportunity_id,
            # ...
        }
    
    def _serialize_premarket_opportunity(self, opp: OpportunityObject) -> dict:
        """序列化 OpportunityObject（盘前）"""
        return {
            "opportunity_id": opp.opportunity_id,
            "title": opp.opportunity_title,
            "priority": opp.priority_level.value,
            "direction": opp.trade_direction.value,
            "instruments": opp.target_instruments,
            "score": opp.opportunity_score.overall_score if opp.opportunity_score else 0,
            # 盘前扫描没有异动、趋势、溯因信息
        }
```

---

### 🟡 问题2: Dashboard文件位置

**问题描述**:
- 重构方案中提到修改 `dashboard_app.py`
- 实际文件是 `pipeline/dashboard.py`

**解决方案**:
- 修改正确的文件路径：`pipeline/dashboard.py`

---

### 🟡 问题3: 旧数据迁移

**问题描述**:
- 旧的持久化位置：
  - `data/retro_opportunities/` (可能不存在)
  - `data/premarket_opportunities/` (可能不存在)
  - `data/postmarket_opportunities/` (可能不存在)
  - `data/m12_scan_results.json` (存在)

**风险**:
- 如果这些目录存在历史数据，直接废弃会丢失

**解决方案**:
```bash
# 检查是否存在历史数据
if [ -d "data/retro_opportunities" ] && [ "$(ls -A data/retro_opportunities)" ]; then
    echo "发现历史数据，迁移中..."
    mv data/retro_opportunities data/_backup_retro_opportunities_$(date +%Y%m%d)
fi

# 同样处理其他目录
```

---

### 🟢 问题4: M12ScanLogger的类型提示

**问题描述**:
```python
def log_scan(
    self,
    results: List[RetroOpportunity],  # 类型提示不准确
    ...
):
```

**风险**:
- 盘前扫描传入的是 `List[OpportunityObject]`
- 类型检查会报错

**解决方案**:
```python
from typing import Union

def log_scan(
    self,
    results: Union[List[RetroOpportunity], List[OpportunityObject]],
    ...
):
```

---

### 🟢 问题5: Dashboard的Tab5结构

**问题描述**:
- 当前Dashboard的Tab5可能已经有自己的结构
- 直接替换可能破坏现有功能

**解决方案**:
- 先读取现有的Tab5代码
- 保留现有功能，只修改数据读取部分

---

## 二、兼容性检查

### 1. 向后兼容性

| 组件 | 兼容性 | 说明 |
|------|--------|------|
| M7调度器 | ✅ 兼容 | 只改持久化，不改逻辑 |
| M9模拟盘 | ✅ 兼容 | 不依赖M12扫描结果 |
| M3判断引擎 | ✅ 兼容 | 不受影响 |
| M4行动设计 | ✅ 兼容 | 不受影响 |
| Dashboard | ⚠️ 需适配 | 需要读取新的持久化位置 |

### 2. 数据格式兼容性

**旧格式** (m12_scan_results.json):
```json
{
  "timestamp": "2026-04-28T11:17:36",
  "total_opportunities": 2
}
```

**新格式** (data/m12_scans/intraday/a_share_20260505_093000.json):
```json
{
  "scan_id": "intraday_A_SHARE_20260505_093000",
  "timestamp": "2026-05-05T09:30:00",
  "scan_type": "intraday",
  "market": "A_SHARE",
  "source": "m7_scheduler",
  "total_opportunities": 2,
  "opportunities": [...],
  "metadata": {...}
}
```

**兼容性**: ❌ 不兼容，需要迁移工具

---

## 三、性能影响评估

### 1. 磁盘空间

**旧方案**:
```
m12_scan_results.json: 3.5KB (39条记录，只记录总数)
```

**新方案**:
```
每次扫描: ~5-50KB (取决于异动数量)
每天扫描次数: 
  - 盘中: 3市场 × 10分钟 × 交易时长 ≈ 150次/天
  - 盘前: 3市场 × 1次 = 3次/天
  - 盘后: 3市场 × 1次 = 3次/天
  - 总计: ~156次/天

每天磁盘占用: 156 × 10KB ≈ 1.5MB/天
每月磁盘占用: 1.5MB × 30 ≈ 45MB/月
```

**结论**: ✅ 可接受（45MB/月）

### 2. 写入性能

**旧方案**:
```python
# 追加到单个文件
existing.append(record)
json.dump(existing, f)  # 每次写入整个文件
```

**新方案**:
```python
# 写入独立文件
filepath.write_text(json.dumps(record))  # 只写入当前记录
```

**结论**: ✅ 新方案性能更好（不需要读取整个文件）

### 3. 读取性能

**旧方案**:
```python
# 读取整个文件
records = json.load(open("m12_scan_results.json"))
```

**新方案**:
```python
# 只读取最近N个文件
files = sorted(scan_dir.glob("*.json"))[-limit:]
```

**结论**: ✅ 新方案性能更好（按需读取）

---

## 四、风险等级评估

### 高风险项 🔴

1. **盘前扫描类型不匹配**
   - 风险: 运行时崩溃
   - 影响: 盘前扫描任务失败
   - 缓解: 修改 `M12ScanLogger` 支持两种类型

### 中风险项 🟡

2. **历史数据丢失**
   - 风险: 旧数据被覆盖
   - 影响: 无法回溯历史
   - 缓解: 先备份再迁移

3. **Dashboard功能破坏**
   - 风险: 现有Tab5功能丢失
   - 影响: 用户体验下降
   - 缓解: 先读取现有代码，保留功能

### 低风险项 🟢

4. **类型提示不准确**
   - 风险: IDE警告
   - 影响: 不影响运行
   - 缓解: 使用 `Union` 类型

5. **文件路径错误**
   - 风险: 找不到文件
   - 影响: 修改失败
   - 缓解: 先确认文件位置

---

## 五、修正后的实施方案

### Step 1: 创建统一持久化层（修正版）

**文件**: `m12_opportunity_catcher/scan_logger.py`

```python
"""M12扫描结果统一持久化层"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Union
from core.schemas import Market, RetroOpportunity, OpportunityObject

class M12ScanLogger:
    """M12扫描结果统一记录器"""
    
    def __init__(self, base_dir: str = "data/m12_scans"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建子目录
        (self.base_dir / "intraday").mkdir(exist_ok=True)
        (self.base_dir / "premarket").mkdir(exist_ok=True)
        (self.base_dir / "postmarket").mkdir(exist_ok=True)
    
    def log_scan(
        self,
        scan_type: str,  # "intraday" | "premarket" | "postmarket"
        market: Market,
        results: Union[List[RetroOpportunity], List[OpportunityObject]],  # 修正：支持两种类型
        source: str = "m7_scheduler",
        metadata: Optional[dict] = None,
    ) -> Path:
        """
        记录扫描结果（始终记录，即使0异动）
        
        Args:
            scan_type: 扫描类型
            market: 市场
            results: 扫描结果列表（RetroOpportunity 或 OpportunityObject）
            source: 来源（m7_scheduler/simulation/dashboard）
            metadata: 元数据（数据源、扫描时长等）
        
        Returns:
            保存的文件路径
        """
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        
        # 构建文件路径
        scan_dir = self.base_dir / scan_type
        filename = f"{market.value.lower()}_{timestamp_str}.json"
        filepath = scan_dir / filename
        
        # 根据扫描类型选择序列化方法
        if scan_type == "premarket":
            opportunities = [self._serialize_premarket_opportunity(r) for r in results]
        else:
            opportunities = [self._serialize_retro_opportunity(r) for r in results]
        
        # 构建记录
        record = {
            "scan_id": f"{scan_type}_{market.value}_{timestamp_str}",
            "timestamp": timestamp.isoformat(),
            "scan_type": scan_type,
            "market": market.value,
            "source": source,
            "total_opportunities": len(results),
            "opportunities": opportunities,
            "metadata": metadata or {},
        }
        
        # 保存到文件
        filepath.write_text(
            json.dumps(record, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8"
        )
        
        return filepath
    
    def _serialize_retro_opportunity(self, retro: RetroOpportunity) -> dict:
        """序列化 RetroOpportunity（盘中/盘后）"""
        return {
            "instrument": retro.anomaly.instrument,
            "market": retro.anomaly.market.value,
            "anomaly_type": retro.anomaly.anomaly_type,
            "price_change_pct": retro.anomaly.price_change_pct,
            "sigma_multiple": retro.anomaly.sigma_multiple,
            "atr_multiple": retro.anomaly.atr_multiple,
            "volume_ratio": retro.anomaly.volume_ratio,
            "trend_stage": retro.trend.stage.value,
            "remaining_upside_pct": retro.trend.remaining_upside_pct,
            "causation_confidence": retro.causation.confidence,
            "causation_reason": retro.causation.reason_type.value if retro.causation.reason_type else None,
            "opportunity_id": retro.opportunity.opportunity_id,
            "priority": retro.opportunity.priority_level.value,
            "direction": retro.opportunity.trade_direction.value,
            "entry_constraint": retro.opportunity.entry_constraint.reason if retro.opportunity.entry_constraint else None,
        }
    
    def _serialize_premarket_opportunity(self, opp: OpportunityObject) -> dict:
        """序列化 OpportunityObject（盘前）"""
        return {
            "opportunity_id": opp.opportunity_id,
            "title": opp.opportunity_title,
            "priority": opp.priority_level.value,
            "direction": opp.trade_direction.value,
            "instruments": opp.target_instruments,
            "score": opp.opportunity_score.overall_score if opp.opportunity_score else 0,
            "why_now": opp.why_now if hasattr(opp, 'why_now') else None,
            "risk_factors": opp.risk_factors if hasattr(opp, 'risk_factors') else [],
        }
    
    def load_recent_scans(
        self,
        scan_type: str,
        market: Optional[Market] = None,
        limit: int = 10
    ) -> List[dict]:
        """
        加载最近的扫描记录
        
        Args:
            scan_type: 扫描类型
            market: 市场（None表示所有市场）
            limit: 返回数量
        
        Returns:
            扫描记录列表（按时间倒序）
        """
        scan_dir = self.base_dir / scan_type
        if not scan_dir.exists():
            return []
        
        # 获取所有文件
        pattern = f"{market.value.lower()}_*.json" if market else "*.json"
        files = sorted(scan_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        
        # 读取文件
        records = []
        for filepath in files[:limit]:
            try:
                record = json.loads(filepath.read_text(encoding="utf-8"))
                records.append(record)
            except Exception:
                continue
        
        return records
```

### Step 2: 数据迁移脚本

**新建文件**: `scripts/migrate_m12_data.py`

```python
"""迁移旧的M12扫描数据到新格式"""
import json
import shutil
from pathlib import Path
from datetime import datetime

def migrate():
    """迁移数据"""
    backup_dir = Path("data/_backup_m12_old_format_20260505")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. 备份旧数据
    old_dirs = [
        "data/retro_opportunities",
        "data/premarket_opportunities",
        "data/postmarket_opportunities",
    ]
    
    for old_dir in old_dirs:
        old_path = Path(old_dir)
        if old_path.exists() and any(old_path.iterdir()):
            print(f"备份 {old_dir}...")
            shutil.copytree(old_path, backup_dir / old_path.name, dirs_exist_ok=True)
    
    # 2. 备份 m12_scan_results.json
    old_results = Path("data/m12_scan_results.json")
    if old_results.exists():
        print(f"备份 {old_results}...")
        shutil.copy(old_results, backup_dir / "m12_scan_results.json")
    
    print(f"\n备份完成！备份位置: {backup_dir}")
    print("旧数据已保留，可以安全进行重构。")

if __name__ == "__main__":
    migrate()
```

### Step 3: 修正后的实施顺序

1. ✅ **先备份数据**（运行迁移脚本）
2. ✅ **创建 scan_logger.py**（修正版，支持两种类型）
3. ✅ **修改 M7调度器**（使用统一持久化）
4. ✅ **读取现有 Dashboard 代码**（确认Tab5结构）
5. ✅ **更新 Dashboard**（保留现有功能）
6. ✅ **废弃旧脚本**（重命名为.bak）
7. ✅ **测试验证**

---

## 六、测试计划

### 1. 单元测试

```python
# tests/test_m12_scan_logger.py
def test_log_retro_opportunity():
    """测试记录 RetroOpportunity"""
    logger = M12ScanLogger(base_dir="test_data")
    # ... 测试逻辑

def test_log_premarket_opportunity():
    """测试记录 OpportunityObject"""
    logger = M12ScanLogger(base_dir="test_data")
    # ... 测试逻辑

def test_load_recent_scans():
    """测试加载历史记录"""
    # ... 测试逻辑
```

### 2. 集成测试

```bash
# 1. 启动M7调度器
python -m m7_scheduler.scheduler --background

# 2. 等待一次扫描完成（10分钟）
sleep 600

# 3. 检查新的持久化位置
ls -la data/m12_scans/intraday/

# 4. 检查Dashboard是否正常显示
# 访问 http://localhost:8501

# 5. 检查日志是否有错误
tail -100 logs/simulation_10min.log | grep ERROR
```

---

## 七、回滚方案

如果重构失败，回滚步骤：

```bash
# 1. 停止M7调度器
pkill -f "m7_scheduler"

# 2. 恢复旧脚本
mv _deprecated_run_continuous_simulation.py.bak run_continuous_simulation.py
mv _deprecated_run_full_scan.py.bak run_full_scan.py

# 3. 恢复旧数据
cp data/_backup_m12_old_format_20260505/m12_scan_results.json data/

# 4. 删除新的持久化层
rm -rf data/m12_scans/
rm m12_opportunity_catcher/scan_logger.py

# 5. 恢复M7调度器代码
git checkout m7_scheduler/scheduler.py

# 6. 重启旧脚本
python run_continuous_simulation.py
```

---

## 八、总结

### 发现的关键问题

1. 🔴 **盘前扫描类型不匹配** - 已修正
2. 🟡 **Dashboard文件路径错误** - 已修正
3. 🟡 **历史数据迁移** - 已添加迁移脚本
4. 🟢 **类型提示不准确** - 已修正
5. 🟢 **文件路径确认** - 已确认

### 修正后的风险评估

| 风险项 | 原风险 | 修正后风险 | 缓解措施 |
|--------|--------|-----------|---------|
| 类型不匹配 | 🔴 高 | 🟢 低 | 支持两种类型 |
| 数据丢失 | 🟡 中 | 🟢 低 | 先备份再迁移 |
| Dashboard破坏 | 🟡 中 | 🟢 低 | 先读取现有代码 |
| 性能影响 | 🟢 低 | 🟢 低 | 新方案性能更好 |

### 实施建议

✅ **方案可行**，但需要按修正后的步骤执行：
1. 先运行数据迁移脚本（备份）
2. 使用修正版的 `scan_logger.py`（支持两种类型）
3. 先读取现有Dashboard代码（确认结构）
4. 逐步实施，每步验证
5. 准备好回滚方案

**预计时间**: 2小时（增加了备份和验证时间）
**风险等级**: 🟢 低（已缓解所有高风险项）
