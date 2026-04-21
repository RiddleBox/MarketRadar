# M11 ContrarianAgent 设计文档

> **版本**: v1.0  
> **日期**: 2026-04-21  
> **作者**: 信标 (Beacon)  
> **状态**: 已实现，待校准验证

---

## 背景

### 问题描述

M11 Agent 模拟在历史事件校准中表现不佳：
- **方向准确率**: 50%（规则）/ 37%（LLM，2% 阈值）
- **Brier Score**: 0.69（接近随机猜测 0.67）
- **极值召回率**: 33.3%（目标 60%）
- **综合评分**: 23.0/100（目标 70+）

### 核心问题

Agent 过度乐观，在情绪高涨时无法识别"利好出尽"风险：
- **9-30 牛市情绪爆发**：预测上涨，实际下跌
- **11-08 万亿国债**：预测上涨，实际下跌
- **12-12 经济工作会议**：预测上涨，实际下跌

---

## 设计方案

### 第一性原理

**真实市场中存在反向交易者**，他们在情绪极值时做反向判断：
- 情绪过热 + 利好信号 → 看空（利好已被市场提前消化）
- 情绪极度恐惧 + 利空信号 → 看多（恐慌过度，超跌反弹）

M11 的定位是"模拟市场参与者行为"，增加 `ContrarianAgent` 符合这一定位。

---

## 实现细节

### 1. ContrarianAgent 类

**文件**: `m11_agent_sim/agents/contrarian_agent.py`

**核心逻辑**：
```python
# 情绪过热场景（利好出尽）
if fear_greed_index > 80 and bullish_signals > bearish_signals:
    direction = "BEARISH"
    confidence = 0.35 ~ 0.85（基于过热程度）
    reasoning = "情绪过热，利好已被市场提前消化，追高风险大"

# 情绪极度恐惧场景（超跌反弹）
elif fear_greed_index < 20 and bearish_signals > bullish_signals:
    direction = "BULLISH"
    confidence = 0.35 ~ 0.85（基于恐惧程度）
    reasoning = "情绪极度恐惧，恐慌过度，超跌反弹概率高"

# 正常情绪区间（跟随上游共识）
else:
    direction = 跟随上游共识
    confidence = 0.15（低置信，避免干扰主流判断）
```

**数据来源**：
- `M10.sentiment.fear_greed_index`（恐贪指数）
- `M2.signals.policy`（政策信号）
- `M2.signals.official_announcement`（官方公告）

---

### 2. 动态权重机制

**文件**: `m11_agent_sim/agent_network.py`

**权重调整逻辑**：
```python
# 正常情况
ContrarianAgent.weight = 0.05（低权重，避免干扰主流判断）

# 情绪极值时（fear_greed_index > 80 或 < 20）
ContrarianAgent.weight = 0.25（提升至与其他 Agent 平权）
其他 Agent 权重按比例缩减，保持总权重 = 1.0
```

**判断函数**：
```python
@staticmethod
def should_boost_weight(market_input: MarketInput) -> bool:
    fg_index = market_input.sentiment.fear_greed_index
    return fg_index > 80 or fg_index < 20
```

---

### 3. Agent 序列

**修改前**：
```
0. PolicySensitiveAgent（政策分析师，权重 0.20）
1. NorthboundFollowerAgent（北向跟随者，权重 0.20）
2. TechnicalAgent（技术分析师，权重 0.15）
3. SentimentRetailAgent（情绪散户，权重 0.20）
4. FundamentalAgent（基本面分析师，权重 0.25）
```

**修改后**：
```
0. PolicySensitiveAgent（政策分析师，权重 0.20）
1. NorthboundFollowerAgent（北向跟随者，权重 0.20）
2. TechnicalAgent（技术分析师，权重 0.15）
3. SentimentRetailAgent（情绪散户，权重 0.20）
4. FundamentalAgent（基本面分析师，权重 0.20）← 从 0.25 降至 0.20
5. ContrarianAgent（反向交易员，权重 0.05 → 0.25 动态）← 新增
```

---

## 预期效果

### 目标指标

| 指标 | 当前值 | 目标值 | 改进方向 |
|------|--------|--------|---------|
| Brier Score | 0.69 | < 0.30 | 降低概率校准误差 |
| 极值召回率 | 33.3% | 60%+ | 提升极值事件识别能力 |
| 方向准确率 | 50% | 70%+ | 提升整体方向判断 |
| 综合评分 | 23.0 | 70+ | 全面提升 |

### 关键场景验证

| 事件 | 当前预测 | 实际方向 | 预期改进 |
|------|---------|---------|---------|
| 9-30 牛市情绪爆发 | BULLISH | BEARISH | ContrarianAgent 识别情绪过热 → BEARISH |
| 11-08 万亿国债 | BULLISH | BEARISH | ContrarianAgent 识别利好出尽 → BEARISH |
| 12-12 经济工作会议 | BULLISH | BEARISH | ContrarianAgent 识别情绪过热 → BEARISH |

---

## 验证步骤

### 1. 环境准备

```bash
cd /mnt/d/AIProjects/MarketRadar
# 确保 Python 环境已安装依赖
pip install -r requirements.txt
```

### 2. 运行校准

```bash
python scripts/calibrate_m11_v2.py
```

### 3. 检查输出

校准脚本会输出：
- **Brier Score**（概率校准误差）
- **极值召回率**（±5% 以上波动的识别能力）
- **情绪强度相关性**（模拟情绪 vs 实际波动的相关性）
- **综合评分**（加权总分）

### 4. 对比分析

对比修改前后的指标变化：
- Brier Score 是否下降？
- 极值召回率是否提升？
- 9-30、11-08、12-12 三个关键事件的方向是否修正？

---

## 风险与限制

### 已知限制

1. **历史情绪数据估算**：当前使用价格代理估算历史情绪，不是真实 M10 数据
2. **单一标的**：校准仅使用 510300.SH（沪深 300 ETF）
3. **LLM 成本**：完整校准需要约 300 次 API 调用（约 20 分钟）

### 潜在风险

1. **过度拟合**：如果只针对 9-30、11-08、12-12 三个事件优化，可能无法泛化
2. **权重冲突**：ContrarianAgent 权重提升时，可能压制其他 Agent 的有效信号
3. **情绪阈值敏感**：80/20 阈值是经验值，可能需要根据校准结果调整

---

## 后续优化方向

### 短期（如果效果不够）

1. **调整情绪阈值**：从 80/20 调整为 85/15 或 75/25
2. **增加信号类型判断**：只在政策类信号时触发反向逻辑
3. **引入历史兑现率**：政策类信号的历史兑现率作为反向判断依据

### 长期（如果效果显著）

1. **学习权重矩阵**：从历史数据学习 Agent 间的影响权重
2. **引入 M10 真实数据**：替换价格代理估算的情绪数据
3. **扩展到港股/美股**：验证 ContrarianAgent 在其他市场的有效性

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-04-21 | 初始设计，实现 ContrarianAgent + 动态权重机制 |

---

## 参考文档

- [M11 PRINCIPLES.md](../m11_agent_sim/PRINCIPLES.md)
- [M10 PRINCIPLES.md](../m10_sentiment/PRINCIPLES.md)
- [M3 PRINCIPLES.md](../m3_judgment/PRINCIPLES.md)
- [校准脚本 v2](../scripts/calibrate_m11_v2.py)
