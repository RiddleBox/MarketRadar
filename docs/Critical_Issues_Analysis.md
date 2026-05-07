# MarketRadar 关键问题分析与解决方案

**创建日期**: 2026-05-07  
**优先级**: 🔴 P0 - 必须立即解决

---

## 问题总览

| # | 问题 | 严重程度 | 状态 |
|---|------|----------|------|
| 1 | 机会判断：三个市场均未发现机会 | 🔴 严重 | 待验证 |
| 2 | 信号剖面：页面显示错误（字段名不匹配） | 🔴 严重 | 已定位 |
| 3 | 情绪面：过于宏观，缺少个股/板块级别分析 | 🟡 中等 | 待设计 |
| 4 | 信号源：需要外部插件提供额外信息 | 🟢 增强 | 待讨论 |

---

## 问题 1: 机会判断失效

### 现象

- 系统显示信号总数增加（264条总数，最近7天128条）
- 但三个市场（A股/港股/美股）均未发现机会
- 无法判断是判断标准过严还是功能异常

### 可能原因

#### 1.1 M3 判断引擎阈值过严

**检查方法**:
```python
# 查看 M3 判断配置
cat config/judgment_config.yaml

# 检查最近的判断日志
grep "M3.*judgment" data/logs/scheduler.log | tail -20
```

**可能的问题**:
- `min_confidence_score` 设置过高（如 >0.8）
- `min_intensity_score` 设置过高
- `priority_level` 计算逻辑过于保守

#### 1.2 信号类型不匹配

**检查方法**:
```python
from m2_storage.signal_store import SignalStore
from datetime import datetime, timedelta

store = SignalStore()
signals = store.get_by_time_range(
    start=datetime.now() - timedelta(days=7),
    end=datetime.now()
)

# 统计信号类型分布
from collections import Counter
signal_types = Counter([s.signal_type for s in signals])
print("信号类型分布:", signal_types)

# 统计信号方向分布
signal_directions = Counter([s.signal_direction for s in signals])
print("信号方向分布:", signal_directions)
```

**可能的问题**:
- 大部分信号是 `sentiment` 类型，但 M3 只处理 `event_driven` 类型
- 大部分信号方向是 `NEUTRAL`，被 M3 过滤掉

#### 1.3 M12 扫描未触发

**检查方法**:
```bash
# 查看最近的 M12 扫描记录
grep "m12.*scan" data/logs/scheduler.log | tail -20

# 检查机会文件
ls -lh data/opportunities/

# 查看最新的机会文件
cat data/opportunities/opportunities_*.json | tail -1 | jq .
```

**可能的问题**:
- M12 扫描任务未执行
- 扫描执行了但未发现异动
- 异动检测参数过严

### 解决方案

#### 方案 A: 降低判断阈值（快速验证）

**文件**: `config/judgment_config.yaml`

```yaml
# 临时降低阈值用于测试
thresholds:
  min_confidence_score: 0.3  # 从 0.6 降低到 0.3
  min_intensity_score: 0.3   # 从 0.5 降低到 0.3
  min_timeliness_score: 0.3  # 从 0.5 降低到 0.3
```

**执行**:
```bash
# 重启调度器
python -m m7_scheduler.cli stop
python -m m7_scheduler.cli start --background

# 手动触发信号处理
python -m m7_scheduler.cli run signal_pipeline

# 检查是否生成机会
ls -lh data/opportunities/
```

#### 方案 B: 添加调试日志

**文件**: `m3_judgment/judgment_engine.py`

在 `judge()` 方法中添加详细日志：

```python
def judge(self, signal: MarketSignal) -> OpportunityObject:
    logger.info(f"[M3] 开始判断信号 | signal_id={signal.signal_id} type={signal.signal_type}")
    
    # 记录评分
    logger.info(f"[M3] 信号评分 | confidence={signal.confidence_score} "
                f"intensity={signal.intensity_score} timeliness={signal.timeliness_score}")
    
    # 记录优先级判断
    priority = self._calculate_priority(signal)
    logger.info(f"[M3] 优先级判断 | priority={priority}")
    
    # 记录是否通过阈值
    if priority == PriorityLevel.WATCH:
        logger.warning(f"[M3] 信号未达到阈值 | signal_id={signal.signal_id} "
                      f"被降级为 WATCH")
    
    # ... 继续原有逻辑
```

#### 方案 C: 手动测试单个信号

**创建测试脚本**: `test_signal_judgment.py`

```python
"""测试单个信号的判断流程"""
from m2_storage.signal_store import SignalStore
from m3_judgment.judgment_engine import JudgmentEngine
from datetime import datetime, timedelta

# 加载最近的信号
store = SignalStore()
signals = store.get_by_time_range(
    start=datetime.now() - timedelta(days=7),
    end=datetime.now()
)

if not signals:
    print("没有找到信号")
    exit(1)

# 选择第一个信号进行测试
test_signal = signals[0]
print(f"测试信号: {test_signal.signal_id}")
print(f"类型: {test_signal.signal_type}")
print(f"方向: {test_signal.signal_direction}")
print(f"置信度: {test_signal.confidence_score}")
print(f"强度: {test_signal.intensity_score}")
print()

# 执行判断
engine = JudgmentEngine()
try:
    opportunity = engine.judge(test_signal)
    print(f"✅ 判断成功")
    print(f"机会ID: {opportunity.opportunity_id}")
    print(f"优先级: {opportunity.priority_level}")
    print(f"标题: {opportunity.opportunity_title}")
except Exception as e:
    print(f"❌ 判断失败: {e}")
    import traceback
    traceback.print_exc()
```

**执行**:
```bash
python test_signal_judgment.py
```

### 验证步骤

1. **检查信号数据** ✅ (已完成 - 264条信号存在)
2. **检查 M3 配置** (待执行)
3. **检查 M12 扫描日志** (待执行)
4. **手动测试信号判断** (待执行)
5. **降低阈值重新测试** (待执行)

---

## 问题 2: 信号剖面页面显示错误

### 现象

- Dashboard 显示信号总数增加
- 但"信号剖面"页面看不到任何信号
- 实际数据库中有 128 条最近7天的信号

### 根本原因

**字段名不匹配**:
- Dashboard 代码使用 `created_at` 字段
- 实际信号对象使用 `event_time` 和 `collected_time` 字段

### 信号对象实际字段

```python
{
  "signal_id": "sent_4d8e86ffa6e5",
  "signal_type": "sentiment",
  "signal_label": "市场情绪: 中性（恐指贪婪 51）",
  "description": "...",
  "evidence_text": "...",
  "affected_markets": ["A_SHARE"],
  "affected_instruments": ["..."],
  "signal_direction": "NEUTRAL",
  "event_time": "2026-05-07T10:30:00",      # ← 事件发生时间
  "collected_time": "2026-05-07T10:35:22",  # ← 信号采集时间
  "time_horizon": "short_term",
  "intensity_score": 0.5,
  "confidence_score": 0.6,
  "timeliness_score": 0.8,
  "source_type": "sentiment_provider",
  "source_ref": "...",
  "logic_frame": {...},
  "batch_id": "..."
}
```

### 解决方案

#### 修复 1: 信号剖面页面

**文件**: `dashboard_v2/pages/3_🔍_信号剖面.py`

**修改**:
```python
# 第 52 行 - 修改字段名
# 原代码:
created_at = (sig.get("created_at") or "")[:19]

# 修改为:
event_time = (sig.get("event_time") or sig.get("collected_time") or "")[:19]

# 第 55 行 - 修改显示
# 原代码:
label = f"[{sig_type}] {created_at} - {content_preview}..."

# 修改为:
label = f"[{sig_type}] {event_time} - {content_preview}..."
```

**完整修复**:
```python
# 创建信号选项列表
signal_options = {}
for sig in signals[:50]:  # 最多显示50条
    sig_id = sig.get("signal_id", "")
    sig_type = sig.get("signal_type", "未知")
    
    # 使用 event_time，如果没有则使用 collected_time
    event_time = sig.get("event_time") or sig.get("collected_time") or ""
    if event_time:
        event_time = event_time[:19]  # 截取到秒
    
    # 使用 description 作为预览，如果没有则使用 signal_label
    content_preview = sig.get("description") or sig.get("signal_label") or ""
    content_preview = content_preview[:50]

    label = f"[{sig_type}] {event_time} - {content_preview}..."
    signal_options[label] = sig_id
```

#### 修复 2: 其他使用 created_at 的地方

**搜索所有使用 created_at 的文件**:
```bash
grep -r "created_at" dashboard_v2/
```

**需要修改的文件**:
- `dashboard_v2/pages/3_🔍_信号剖面.py` (已识别)
- 其他可能使用该字段的页面

### 验证步骤

1. 修复字段名
2. 重启 Dashboard
3. 打开"信号剖面"页面
4. 确认可以看到信号列表
5. 选择信号查看详情

---

## 问题 3: 情绪面过于宏观

### 现象

- 当前情绪面只显示整个市场的情绪指标
- 缺少板块级别的情绪分析
- 缺少个股级别的情绪分析

### 当前情绪数据结构

```python
{
  "timestamp": "2026-05-07T10:30:00",
  "fear_greed_index": 51,           # 市场级别
  "sentiment_label": "中性",
  "direction": "NEUTRAL",
  "northbound_flow": {               # 市场级别
    "net_inflow": 1234567890
  },
  "sector_sentiment": {              # 板块级别（简化版）
    "格力电器": 85.3,
    "贵州茅台": 78.2
  }
}
```

### 问题分析

1. **板块情绪不准确**: 当前使用百度热搜股票作为板块情绪代理，不够准确
2. **缺少真实板块数据**: 没有按行业/概念板块聚合情绪
3. **缺少个股情绪**: 无法查看特定股票的情绪历史

### 解决方案

#### 方案 A: 增强情绪采集（短期）

**修改**: `m10_sentiment/sentiment_engine.py`

**新增功能**:
1. 采集板块资金流向（东方财富板块资金流）
2. 采集板块涨跌幅排行
3. 采集个股情绪指标（换手率、量比、资金流向）

**数据结构**:
```python
{
  "market_sentiment": {
    "fear_greed_index": 51,
    "direction": "NEUTRAL"
  },
  "sector_sentiment": {
    "电力设备": {
      "sentiment_score": 75.3,
      "net_inflow": 1234567890,
      "avg_change_pct": 2.5,
      "hot_stocks": ["宁德时代", "比亚迪"]
    },
    "白酒": {
      "sentiment_score": 68.2,
      "net_inflow": 987654321,
      "avg_change_pct": 1.2,
      "hot_stocks": ["贵州茅台", "五粮液"]
    }
  },
  "stock_sentiment": {
    "000651.SZ": {
      "name": "格力电器",
      "sentiment_score": 82.5,
      "turnover_rate": 3.2,
      "volume_ratio": 1.8,
      "net_inflow": 123456789
    }
  }
}
```

#### 方案 B: Dashboard 增加板块/个股视图（中期）

**新增页面**: `dashboard_v2/pages/4_🧠_情绪面.py`

**新增功能**:
1. **市场总览** (现有)
2. **板块情绪排行** (新增)
   - 表格显示各板块情绪得分
   - 资金流向、涨跌幅
   - 点击查看板块详情
3. **个股情绪查询** (新增)
   - 输入股票代码
   - 显示个股情绪历史曲线
   - 显示情绪指标明细

#### 方案 C: 情绪与机会关联（长期）

**目标**: 在机会判断时考虑情绪因素

**实现**:
1. M3 判断时查询标的的情绪得分
2. 情绪得分作为加权因子影响优先级
3. 高情绪 + 强信号 = 更高优先级

### 实施优先级

1. **P0 - 立即**: 修复信号剖面页面（问题2）
2. **P1 - 本周**: 验证机会判断问题（问题1）
3. **P2 - 下周**: 增强情绪采集（问题3 方案A）
4. **P3 - 未来**: Dashboard 板块视图（问题3 方案B）

---

## 问题 4: 外部信息源插件

### 需求

- 使用外部 skill 提供额外信息源
- 作为补充信号输入系统

### 技术方案

#### 方案 A: MCP Server 集成

**优势**:
- Claude Code 原生支持 MCP
- 可以调用外部 API、数据库
- 标准化的工具接口

**实现**:
1. 创建 MCP Server: `mcp_servers/market_data_server.py`
2. 提供工具:
   - `get_stock_news`: 获取个股新闻
   - `get_sector_analysis`: 获取板块分析
   - `get_macro_indicators`: 获取宏观指标
3. 在 M0 收集器中调用 MCP 工具

#### 方案 B: 自定义 Provider

**实现**:
1. 创建新的 Provider: `m0_collector/providers/external_skill_provider.py`
2. 实现 `collect()` 方法调用外部 skill
3. 返回标准化的 `RawSignal` 对象

**示例**:
```python
class ExternalSkillProvider(BaseProvider):
    def collect(self) -> List[RawSignal]:
        # 调用外部 skill API
        response = requests.post(
            "http://external-skill-api/analyze",
            json={"market": "A_SHARE", "date": "2026-05-07"}
        )
        
        # 转换为 RawSignal
        signals = []
        for item in response.json():
            signal = RawSignal(
                content=item["content"],
                source_type="external_skill",
                source_ref=item["ref"],
                collected_time=datetime.now()
            )
            signals.append(signal)
        
        return signals
```

### 建议

- **短期**: 使用方案 B（自定义 Provider），快速集成
- **长期**: 迁移到方案 A（MCP Server），标准化架构

---

## 行动计划

### 立即行动（今天）

1. **修复信号剖面页面** (30分钟)
   - 修改字段名 `created_at` → `event_time`
   - 测试验证

2. **验证机会判断问题** (1小时)
   - 执行前置条件检查清单 2.1
   - 运行 `test_signal_judgment.py`
   - 查看 M3 判断日志

3. **降低阈值测试** (30分钟)
   - 临时降低 `judgment_config.yaml` 阈值
   - 重新处理信号
   - 观察是否生成机会

### 明天行动

4. **深入诊断机会判断** (2小时)
   - 如果降低阈值有效，调整合理阈值
   - 如果降低阈值无效，检查 M3 代码逻辑
   - 添加详细调试日志

5. **设计情绪增强方案** (1小时)
   - 确定数据源（东方财富/同花顺）
   - 设计数据结构
   - 评估实施工作量

### 本周行动

6. **实施情绪增强** (1-2天)
   - 实现板块情绪采集
   - 实现个股情绪采集
   - Dashboard 增加板块视图

7. **外部插件集成** (1天)
   - 设计 Provider 接口
   - 实现示例 Provider
   - 测试端到端流程

---

## 总结

### 关键发现

1. ✅ **信号数据正常**: 264条信号，最近7天128条
2. ❌ **Dashboard 字段错误**: 使用了不存在的 `created_at` 字段
3. ❓ **机会判断待验证**: 可能是阈值过严或逻辑问题
4. 💡 **情绪面需增强**: 需要板块和个股级别的情绪分析

### 优先级排序

1. **P0 - 修复信号剖面** (立即)
2. **P0 - 验证机会判断** (今天)
3. **P1 - 增强情绪采集** (本周)
4. **P2 - 外部插件集成** (本周)
5. **P3 - 桌面应用开发** (下周，前提是以上问题解决)

### 建议

**暂缓桌面应用开发**，先解决核心功能问题：
- 如果系统无法生成机会，桌面应用的进度显示也没有意义
- 先确保数据流通畅，再优化用户体验

**分步验证**:
1. 今天修复信号剖面，验证机会判断
2. 明天根据验证结果决定下一步
3. 如果机会判断正常，继续桌面应用开发
4. 如果机会判断有问题，优先修复核心逻辑

---

**文档结束**
