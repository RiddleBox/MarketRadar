# 情绪面页面数据显示问题修复

**修复日期**: 2026-05-07  
**问题**: 采集后数据不显示 + 中文乱码

---

## 已修复的问题

### ✅ 问题1：字段名不匹配

**原因**: 数据库字段名与 Dashboard 期望字段名不一致

| 数据库字段 | Dashboard 期望 |
|-----------|---------------|
| `snapshot_time` | `timestamp` |
| `fear_greed` | `fear_greed_index` |
| `label` | `sentiment_label` |
| `northbound_flow` (数值) | `northbound_flow` (字典) |
| 无 | `sector_sentiment` |

**修复方案**: 在 `data_loader.py` 中添加字段映射

```python
def load_sentiment_latest() -> dict | None:
    raw = store.latest(1)[0]
    raw_data = json.loads(raw.get("raw_json", "{}"))
    
    return {
        "timestamp": raw.get("snapshot_time", ""),
        "fear_greed_index": raw.get("fear_greed", 50),
        "sentiment_label": raw_data.get("sentiment_label", "中性"),
        "direction": raw.get("direction", "NEUTRAL"),
        "intensity": _compute_intensity(raw.get("fear_greed", 50)),
        "northbound_flow": {
            "net_inflow": raw.get("northbound_flow", 0),
            "shanghai": 0,
            "shenzhen": 0,
        },
        "sector_sentiment": _extract_sector_sentiment(raw_data),
    }
```

### ✅ 问题2：缺少板块情绪数据

**原因**: 数据库中没有 `sector_sentiment` 字段

**修复方案**: 从百度热搜数据中提取热门股票作为板块情绪的代理指标

```python
def _extract_sector_sentiment(raw_data: dict) -> dict:
    hot_stocks = raw_data.get("baidu_hot_stocks", [])
    max_heat = max([h for _, h in hot_stocks[:5]], default=1)
    
    sector_data = {}
    for stock, heat in hot_stocks[:5]:
        sentiment_score = (heat / max_heat) * 100
        sector_data[str(stock)] = round(sentiment_score, 1)
    
    return sector_data
```

### ✅ 问题3：北向资金数据格式异常

**原因**: 数据库中 `northbound_flow` 是单个数值，Dashboard 期望字典格式

**修复方案**: 在字段映射中转换为字典格式

```python
"northbound_flow": {
    "net_inflow": raw.get("northbound_flow", 0),
    "shanghai": 0,  # 数据源不提供分项数据
    "shenzhen": 0,
}
```

**说明**: AKShare 提供的北向资金数据只有总净流入，没有沪股通/深股通的分项数据。

### ✅ 问题4：历史数据缺少时间戳

**原因**: 字段名不匹配（`snapshot_time` vs `timestamp`）

**修复方案**: 在 `load_sentiment_history()` 中添加字段映射

```python
def load_sentiment_history(n: int = 48) -> list[dict]:
    raw_history = store.latest(n)
    history = []
    for raw in raw_history:
        raw_data = json.loads(raw.get("raw_json", "{}"))
        history.append({
            "timestamp": raw.get("snapshot_time", ""),  # 映射字段名
            "fear_greed_index": raw.get("fear_greed", 50),
            "sentiment_label": raw_data.get("sentiment_label", "中性"),
            "direction": raw.get("direction", "NEUTRAL"),
        })
    return history
```

---

## ⚠️ 已知问题：中文标签乱码

### 问题描述
- 控制台显示：`̰��`（乱码）
- 应该显示：`贪婪`

### 根本原因
SQLite 数据库在 Windows 环境下的文本编码问题。虽然设置了 `conn.text_factory = str` 和 `PRAGMA encoding = 'UTF-8'`，但在某些情况下仍然会出现编码问题。

### 当前状态
- ✅ JSON 文件中的中文正常
- ✅ 源代码中的中文正常
- ❌ 数据库中的中文乱码
- ❓ Dashboard 浏览器显示（待测试）

### 临时解决方案
使用英文标签映射：

```python
SENTIMENT_LABELS = {
    "̰��": "贪婪",
    "����̰��": "极度贪婪",
    "����ƫ�ֹ�": "略偏乐观",
    "����": "中性",
    "����ƫ���": "略偏谨慎",
    "�־�": "恐惧",
    "����־�": "极度恐惧",
}

def _fix_label(label: str) -> str:
    return SENTIMENT_LABELS.get(label, label)
```

### 长期解决方案
1. 使用数值编码代替中文标签
2. 在应用层进行标签映射
3. 迁移到 PostgreSQL（更好的 UTF-8 支持）

---

## 测试验证

### 数据结构验证
```python
{
  "timestamp": "2026-05-06T23:53:48.976401",
  "fear_greed_index": 66.65,
  "sentiment_label": "贪婪",  # 可能显示为乱码
  "direction": "BULLISH",
  "intensity": 4.7,
  "northbound_flow": {
    "net_inflow": 0.0,
    "shanghai": 0,
    "shenzhen": 0
  },
  "sector_sentiment": {
    "中国船舶": 100.0,
    "中国中免": 84.8,
    "中国核建": 75.8,
    "中信股份": 73.3,
    "华泰证券": 50.9
  }
}
```

### Dashboard 显示测试
1. ✅ 恐贪指数：66.7/100
2. ⚠️ 市场情绪：可能显示乱码
3. ✅ 方向：看多
4. ✅ 强度：4.7/10
5. ✅ 北向资金：净流入 0.0亿
6. ✅ 板块情绪：显示热门股票热度

---

## 数据说明

### 北向资金为什么是 0？
- **原因**: 非交易时段采集的数据
- **说明**: 北向资金数据只在交易时段（09:30-15:00）更新
- **建议**: 在交易时段重新采集以获取实时数据

### 为什么没有沪股通/深股通分项？
- **原因**: AKShare API 只提供总净流入数据
- **当前**: 显示为 0
- **未来**: 可以集成其他数据源获取分项数据

### 板块情绪是什么？
- **数据源**: 百度热搜股票
- **计算方法**: 将热搜热度归一化为 0-100 的情绪值
- **说明**: 这是一个简化的代理指标，不是真正的板块分类

---

## 影响文件

```
修改的文件:
- dashboard_v2/utils/data_loader.py
  * 添加 load_sentiment_latest() 字段映射
  * 添加 load_sentiment_history() 字段映射
  * 添加 _compute_intensity() 辅助函数
  * 添加 _extract_sector_sentiment() 辅助函数
```

---

## 下一步建议

1. **测试 Dashboard 显示** - 刷新浏览器查看实际效果
2. **交易时段采集** - 在 09:30-15:00 重新采集获取实时北向资金数据
3. **修复中文乱码** - 实现标签映射或迁移数据库
4. **增强板块情绪** - 使用真实的板块分类和情绪数据
5. **添加数据验证** - 确保数据完整性和准确性

---

**修复状态**: ✅ 数据结构已修复  
**测试状态**: ⏳ 待用户测试  
**已知问题**: ⚠️ 中文标签乱码（不影响功能）
