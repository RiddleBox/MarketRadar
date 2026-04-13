# 情绪面（M10 Sentiment）设计文档

## 1. 模块定位

M10 是 MarketRadar 的情绪面感知层，与基本面（M1 解码的宏观政策信号）并列，提供"**市场当下的心理温度**"。

核心问题：
> **现在市场参与者整体在"贪婪"还是"恐惧"？这是顺势进还是逆向布局？**

---

## 2. 架构图

```
AKShare（4个维度）
  ├─ stock_hsgt_fund_flow_summary_em  → 北向/南向资金净流入（聪明钱流向）
  ├─ stock_comment_em                 → 全市场个股综合评分分布（主力/机构参与度）
  ├─ stock_hot_search_baidu           → 百度热搜热度（社会关注度）
  └─ stock_js_weibo_report            → 微博情绪 rate（散户情绪）
          │
    SentimentProvider.fetch()
          │ SentimentSnapshot（原始快照）
          ↓
    SentimentEngine.run()
          ├─ fear_greed_score()       → FearGreed 指数（0~100）
          ├─ SentimentSignalData      → 注入 M2 SignalStore（供 M3 使用）
          └─ SentimentStore.save()    → SQLite 历史（data/sentiment/sentiment_history.db）
                                         + JSON 快照文件（data/sentiment/snapshot_*.json）
```

---

## 3. 恐贪指数算法

### 3.1 公式

```
FearGreed = weighted_avg(
    advance_decline_score * 0.35,   // 涨跌比
    northbound_score      * 0.30,   // 北向资金
    composite_score       * 0.25,   // 个股综合评分
    weibo_score           * 0.10,   // 微博情绪
)
```

**归一化到 [0, 100]**：缺失维度自动排除，按实际可用权重重新计算加权均值。

### 3.2 各维度计算细节

| 维度 | 原始值 | 转 0~100 方式 | 权重 | 数据来源 |
|------|--------|--------------|------|----------|
| 涨跌比 | up/(up+down) ∈ [0,1] | × 100 | 35% | stock_comment_em 涨/跌数量 |
| 北向资金 | ±亿元，约 ±200 亿范围 | 50 + (flow/200)×50，截断 ±200 | 30% | stock_hsgt_fund_flow_summary_em |
| 综合评分均值 | 0~100（东财综合得分） | 直接使用 | 25% | stock_comment_em 综合得分列 |
| 微博情绪 | rate ∈ [-1, 1] | 50 + rate×50 | 10% | stock_js_weibo_report |

### 3.3 权重设计依据

- **涨跌比 35%**：最直接的市场宽度指标，价格已经"投票"了，难以人为干扰
- **北向资金 30%**：A 股历史证明外资流向对短期走势有领先性，聪明钱权重高
- **综合评分 25%**：东财综合评分包含主力净买入、机构持股、资金流向，有复合性
- **微博情绪 10%**：散户情绪有反向指标价值（极值时最有用），权重低防止噪音

---

## 4. 情绪区间划分与信号含义

| 区间 | 标签 | 含义 | 操作建议 |
|------|------|------|----------|
| 80~100 | 极度贪婪 🔴 | 历史高风险区间，市场情绪顶部 | 考虑减仓，移动止盈，不追资添仓 |
| 60~79  | 贪婪 🟡 | 市场热度高，但未到顶 | 谨慎加仓，优先基本面强的标的 |
| 40~59  | 中性 ⚪ | 情绪平衡，等待方向 | 观察，关注北向资金和政策信号 |
| 20~39  | 恐惧 🔵 | 情绪低迷，反向指标开始上升 | 少量布局，优先 ETF 分散风险 |
| 0~19   | 极度恐惧 🔵 | 历史最佳买入区间 | 分批买入，等待底部确认信号 |

### 4.1 极值信号的特殊逻辑

当 FG ≥ 80 或 FG ≤ 20 时：
- `is_extreme = True`
- `intensity_score` 自动提升至 8~10（正比于偏离中线的程度）
- 在 M3 机会判断中，极值情绪信号与宏观政策信号形成**共振**时，置信度大幅提升

**极度恐惧 + 宏观利好政策信号** = 历史上最强的买入信号组合（如 2024-09-24 降准降息叠加情绪恐慌底部）

---

## 5. 信号注入 M2 的格式

`SentimentSignalData.to_market_signal_dict()` 转换规则：

```python
{
    "signal_id":       f"sent_{uuid[:12]}",
    "signal_type":     "sentiment",             # MarketSignal.signal_type 枚举
    "source_type":     "social_media",          # SourceType 枚举
    "time_horizon":    "SHORT",                 # 情绪信号默认短期（1~5 天有效）
    "intensity_score": int(round(fg_to_intensity)),  # 1~10 整数
    "confidence_score": int(round(confidence)),      # 数据源完整度越高越高
    "signal_direction": "BULLISH"|"BEARISH"|"NEUTRAL",
    "description":     f"市场情绪: {label}，FearGreed={fg:.1f}",
    "logic_frame":     {
        "what_changed": f"情绪面: {label}",
        "change_direction": direction,
        "affects": hot_sectors,
    }
}
```

### 5.1 信号强度计算 `_compute_intensity(fg)`

```python
def _compute_intensity(fg: float) -> float:
    """FG → 强度 1~10
    
    设计逻辑：
    - 极值（≤20 或 ≥80）时强度最高（8~10），信号最有价值
    - 中性（40~60）时强度最低（1~3），基本无交易信号价值
    - 强度正比于偏离中性 50 的程度
    """
    deviation = abs(fg - 50)    # 0~50
    # 偏离 ≥ 30（即 FG ≤ 20 或 ≥ 80）时强度 = 8~10
    # 偏离 = 0（FG = 50）时强度 = 1
    intensity = 1.0 + (deviation / 50) * 9.0
    return min(10.0, max(1.0, intensity))
```

### 5.2 置信度计算 `_compute_confidence(snapshot)`

数据源完整度 → 置信度：
- 4 个维度全部成功：confidence = 10
- 3 个成功：confidence = 8
- 2 个成功：confidence = 5
- 1 个成功：confidence = 2
- 0 个：不生成信号

---

## 6. Dashboard 情绪 Tab 设计

### 6.1 UI 结构

```
[立即采集] [刷新显示]

────────────────────────────────────────────────────────
[恐贪指数 x.x] [北向资金 ±xx亿] [涨跌家数比 xx%] [情绪方向 ↑多]
  progress bar

────────────────────────────────────────────────────────
情绪解读与操作建议（根据当前 FG 区间给出）

────────────────────────────────────────────────────────
历史趋势折线图（恐贪指数，最近 48 条）
北向资金柱状图

────────────────────────────────────────────────────────
历史快照列表（最近 20 条）

全期统计（总快照数、均值、最高、最低）
```

### 6.2 颜色方案

| 区间 | 颜色 | 含义 |
|------|------|------|
| ≥ 80 | `#ff4b4b`（红）| 危险，警告 |
| 60~79 | `#ffaa00`（橙黄）| 偏高，谨慎 |
| 40~59 | `#aaaaaa`（灰）| 中性 |
| 20~39 | `#00ccff`（淡蓝）| 偏低，关注 |
| < 20  | `#0044ff`（深蓝）| 极度恐惧，机会 |

---

## 7. M7 调度器集成

### 7.1 任务配置

```python
ScheduledTask(
    name="sentiment_collect",
    interval_minutes=30,        # 每 30 分钟一次
    time_window=("09:00", "22:00"),  # 交易日 + 盘后均采集
    run_at_start=True,          # 启动时立即采集一次
)
```

### 7.2 采集频率设计依据

- **盘中（09:30~15:00）**：北向资金每分钟更新，但情绪本身不需要那么高频
- **30 分钟间隔**：能捕捉盘中情绪转折，不造成 AKShare 请求过于频繁
- **盘后（15:00~22:00）**：机构持续交易 ETF、外盘联动，情绪仍有变化
- **22:00 后停止**：美股开盘情绪与 A 股次日情绪关系复杂，暂不纳入

---

## 8. 与其他模块的交互关系

```
M10 SentimentSignal（注入 M2）
         ↓
    M3 JudgmentEngine
         ↓ 情绪共振逻辑（待实现）
    
当前机会判断中，M3 可查询最新情绪信号：
  - FG < 20 + macro BULLISH → confidence + 20%
  - FG > 80 + macro BULLISH → confidence - 15%（语气顶部，谨慎追）
  - FG > 80 + macro BEARISH → confidence + 10%（顶部反转）
```

> 注意：当前版本 M3 尚未实现情绪共振逻辑，M10 信号作为参考存储在 M2 中，
> 未来在 M3 的 `judge()` 方法中加入情绪权重调整即可。

---

## 9. 局限性与风险

1. **AKShare 数据延迟**：东财数据通常延迟 5~15 分钟，非实时
2. **微博数据不稳定**：`stock_js_weibo_report` 接口偶尔失败，已做容错
3. **北向资金归零问题**：非交易时段 API 返回 0，需注意 FG 失真
4. **单日局限**：AKShare 接口只返回当日数据，无历史情绪可回测
5. **A股专属**：当前设计仅适用于 A 股，港股另有港交所数据源（未集成）

---

## 10. 后续扩展方向

- [ ] M3 情绪共振逻辑（情绪极值 × 宏观政策信号 → 强复合信号）
- [ ] 情绪策略回测（用历史新闻 + 重建情绪快照验证效果）
- [ ] 港股情绪接入（恒指期权 PCR + 南向资金）
- [ ] **多 Agent 市场情绪模拟**（见 M11 MultiAgentSim 设计文档）
- [ ] 情绪预测模型（LSTM 基于历史情绪序列预测次日 FG）
