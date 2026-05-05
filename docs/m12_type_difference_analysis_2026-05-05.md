# 盘前扫描 vs 盘中/盘后扫描的类型差异分析

**日期**: 2026-05-05  
**问题**: 为什么盘前扫描返回 `OpportunityObject`，而盘中/盘后扫描返回 `RetroOpportunity`？

---

## 一、类型差异的根本原因

### 1. 数据来源不同

**盘前扫描**（信号驱动）:
```
隔夜新闻 → M0采集 → M1解码 → M2存储 → M3判断 → OpportunityObject
```
- 数据源: **新闻/事件**
- 驱动方式: **主动信号搜集**
- 核心逻辑: **因果推理**（新闻 → 影响 → 机会）
- 输出: `OpportunityObject`（标准机会对象）

**盘中/盘后扫描**（价格驱动）:
```
价格异动 → 异动检测 → 反向溯源 → 趋势判断 → RetroOpportunity
```
- 数据源: **价格变动**
- 驱动方式: **被动异动追溯**
- 核心逻辑: **反向溯因**（价格 → 原因 → 机会）
- 输出: `RetroOpportunity`（补牢机会对象）

### 2. 信息结构不同

**OpportunityObject**（盘前）:
```python
class OpportunityObject:
    opportunity_id: str
    opportunity_title: str           # 机会标题
    why_now: str                     # 为什么现在
    target_instruments: List[str]    # 目标标的
    trade_direction: Direction       # 方向
    priority_level: PriorityLevel    # 优先级
    opportunity_score: OpportunityScore  # 评分
    risk_factors: List[str]          # 风险因素
    # 没有价格异动、趋势、溯因信息
```

**RetroOpportunity**（盘中/盘后）:
```python
class RetroOpportunity:
    anomaly: PriceAnomaly           # 价格异动（涨幅、sigma、ATR、量比）
    trend: TrendAssessment          # 趋势判断（EARLY/MIDDLE/LATE）
    causation: CausationResult      # 溯因结果（置信度、原因类型）
    opportunity: OpportunityObject  # 标准机会对象
```

**关键差异**:
- `OpportunityObject`: 只有机会信息，**没有价格异动数据**
- `RetroOpportunity`: 包含 `OpportunityObject` + **价格异动** + **趋势** + **溯因**

---

## 二、这个设计有什么好处？

### ✅ 好处1: 符合业务逻辑

**盘前扫描**:
- 目的: 开盘前准备交易计划
- 场景: 市场还未开盘，**没有价格异动**
- 输入: 隔夜新闻、情绪面
- 输出: 基于新闻的机会判断

**盘中/盘后扫描**:
- 目的: 捕获已发生的价格异动
- 场景: 市场已开盘，**价格已经变动**
- 输入: 实时价格、历史价格
- 输出: 基于价格异动的补牢机会

**结论**: 类型差异**反映了业务本质差异**

### ✅ 好处2: 信息完整性

**盘前扫描**:
```
新闻: "某公司获得重大合同"
  ↓
OpportunityObject:
  - title: "某公司业绩预期提升"
  - why_now: "重大合同签订"
  - direction: LONG
  - 没有价格异动（因为还未开盘）
```

**盘中扫描**:
```
价格: 某股票涨停
  ↓
RetroOpportunity:
  - anomaly: 涨幅9.8%, sigma=3.5, 量比=5.2
  - trend: EARLY（趋势早期）
  - causation: 置信度80%，原因=重大合同
  - opportunity: 标准机会对象
```

**结论**: 每种类型都包含**该场景下的完整信息**

### ✅ 好处3: 避免数据冗余

如果盘前扫描也返回 `RetroOpportunity`:
```python
# 问题：盘前扫描没有价格异动
RetroOpportunity(
    anomaly=None,  # ❌ 空值
    trend=None,    # ❌ 空值
    causation=None,  # ❌ 空值
    opportunity=OpportunityObject(...)
)
```

**结论**: 使用不同类型**避免了无意义的空值**

### ✅ 好处4: 类型安全

```python
def process_premarket_opportunity(opp: OpportunityObject):
    # 编译时保证：opp 没有 anomaly 属性
    # 不会误用不存在的数据
    pass

def process_retro_opportunity(retro: RetroOpportunity):
    # 编译时保证：retro 有 anomaly, trend, causation
    # 可以安全使用这些数据
    print(f"异动: {retro.anomaly.price_change_pct}%")
```

**结论**: 类型系统**防止误用**

---

## 三、有没有更好的设计？

### 方案A: 统一类型（不推荐）

```python
class UnifiedOpportunity:
    opportunity: OpportunityObject
    anomaly: Optional[PriceAnomaly] = None      # 盘前为None
    trend: Optional[TrendAssessment] = None     # 盘前为None
    causation: Optional[CausationResult] = None # 盘前为None
```

**缺点**:
- ❌ 大量 `Optional` 字段，容易出错
- ❌ 需要运行时检查 `if anomaly is not None`
- ❌ 类型安全性降低
- ❌ 语义不清晰（为什么有些字段是None？）

### 方案B: 继承关系（可行但复杂）

```python
class BaseOpportunity:
    opportunity: OpportunityObject

class PremarketOpportunity(BaseOpportunity):
    pass  # 只有 opportunity

class RetroOpportunity(BaseOpportunity):
    anomaly: PriceAnomaly
    trend: TrendAssessment
    causation: CausationResult
```

**优点**:
- ✅ 类型安全
- ✅ 避免空值

**缺点**:
- ⚠️ 增加复杂度
- ⚠️ 需要修改现有代码
- ⚠️ 收益不大（当前设计已经够用）

### 方案C: 保持现状（推荐）

**当前设计**:
- 盘前: `OpportunityObject`
- 盘中/盘后: `RetroOpportunity`

**优点**:
- ✅ 符合业务逻辑
- ✅ 信息完整性
- ✅ 避免数据冗余
- ✅ 类型安全
- ✅ 代码已经实现，无需大改

**缺点**:
- ⚠️ 持久化层需要处理两种类型（但这是合理的）

---

## 四、结论

### 为什么有类型差异？

**根本原因**: 
- 盘前扫描和盘中/盘后扫描是**两种不同的业务场景**
- 数据来源不同（新闻 vs 价格）
- 信息结构不同（无异动 vs 有异动）

### 这个设计有好处吗？

**✅ 有明确的好处**:
1. 符合业务逻辑（反映本质差异）
2. 信息完整性（每种类型包含该场景的完整信息）
3. 避免数据冗余（不需要无意义的空值）
4. 类型安全（编译时防止误用）

### 是否需要统一？

**❌ 不建议统一**:
- 当前设计合理，符合业务本质
- 统一类型会引入 `Optional` 字段，降低类型安全性
- 持久化层处理两种类型的成本很低（只需两个序列化方法）

### 对重构方案的影响

**✅ 影响可控**:
- 只需在 `M12ScanLogger` 中添加两个序列化方法
- 根据 `scan_type` 选择对应的方法
- 代码清晰，易于维护

```python
if scan_type == "premarket":
    opportunities = [self._serialize_premarket_opportunity(r) for r in results]
else:
    opportunities = [self._serialize_retro_opportunity(r) for r in results]
```

---

## 五、最终建议

### ✅ 保持类型差异，按修正后的方案实施

**理由**:
1. 类型差异有明确的业务价值
2. 统一类型会降低代码质量
3. 持久化层处理两种类型的成本很低
4. 修正后的方案已经解决了所有问题

### 实施方案

按照 [m12_refactor_risk_analysis_2026-05-05.md](docs/m12_refactor_risk_analysis_2026-05-05.md) 中的修正方案执行：

1. ✅ 创建支持两种类型的 `M12ScanLogger`
2. ✅ 根据 `scan_type` 选择序列化方法
3. ✅ 保持M7调度器的业务逻辑不变
4. ✅ 统一持久化位置和格式

**预计时间**: 2小时  
**风险等级**: 🟢 低  
**收益**: 架构清晰、数据完整、易于维护
