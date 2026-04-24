# 因果图谱扩充指南

> **任务**: 从10个货币政策模式扩展到50+模式
> **状态**: 待实现
> **预计工时**: 4-6小时

---

## 扩充计划

### 1. 行业政策模式 (10个)

```python
# 新能源补贴
CausalPattern(
    pattern_id="pattern_new_energy_subsidy_001",
    precursor_signals=[
        "政策表态：发改委或工信部提到'新能源汽车补贴延续'",
        "行业数据：新能源汽车销量增速放缓",
    ],
    consequent_event="新能源板块上涨",
    probability=0.70,
    avg_lead_time_days=5,
)

# 地产政策放松
CausalPattern(
    pattern_id="pattern_property_policy_easing_001",
    precursor_signals=[
        "政策表态：住建部提到'支持刚性和改善性住房需求'",
        "一线城市放松限购",
    ],
    consequent_event="地产板块上涨",
    probability=0.65,
    avg_lead_time_days=3,
)

# 医药集采
CausalPattern(
    pattern_id="pattern_pharma_vbp_001",
    precursor_signals=[
        "政策公告：医保局发布集采名单",
        "涉及品种：高毛利药品或耗材",
    ],
    consequent_event="相关医药股下跌",
    probability=0.80,
    avg_lead_time_days=1,
)

# 科技产业政策
CausalPattern(
    pattern_id="pattern_tech_policy_support_001",
    precursor_signals=[
        "政策表态：国务院提到'加快发展新质生产力'",
        "资金支持：设立专项基金或税收优惠",
    ],
    consequent_event="科技板块上涨",
    probability=0.60,
    avg_lead_time_days=7,
)

# 消费刺激政策
CausalPattern(
    pattern_id="pattern_consumption_stimulus_001",
    precursor_signals=[
        "政策表态：商务部提到'促进消费'或'消费券'",
        "经济数据：社会消费品零售总额增速低于预期",
    ],
    consequent_event="消费板块上涨",
    probability=0.55,
    avg_lead_time_days=5,
)
```

**其他5个**: 环保政策、军工订单、基建投资、出口退税、数字经济

---

### 2. 个股事件模式 (10个)

```python
# 业绩预增
CausalPattern(
    pattern_id="pattern_earnings_preannounce_001",
    precursor_signals=[
        "公司公告：业绩预增50%以上",
        "行业景气：所属行业处于上行周期",
    ],
    consequent_event="股价上涨",
    probability=0.75,
    avg_lead_time_days=1,
)

# 重组并购
CausalPattern(
    pattern_id="pattern_ma_announcement_001",
    precursor_signals=[
        "公司公告：重大资产重组或并购",
        "标的质量：被并购方盈利能力强",
    ],
    consequent_event="股价上涨",
    probability=0.70,
    avg_lead_time_days=1,
)

# 股东增持
CausalPattern(
    pattern_id="pattern_insider_buying_001",
    precursor_signals=[
        "公司公告：大股东或高管增持",
        "增持规模：占总股本1%以上",
    ],
    consequent_event="股价上涨",
    probability=0.60,
    avg_lead_time_days=2,
)

# 高管变动
CausalPattern(
    pattern_id="pattern_management_change_001",
    precursor_signals=[
        "公司公告：董事长或总经理变更",
        "新任背景：来自行业龙头或有成功经验",
    ],
    consequent_event="股价上涨",
    probability=0.50,
    avg_lead_time_days=3,
)

# 产品发布
CausalPattern(
    pattern_id="pattern_product_launch_001",
    precursor_signals=[
        "公司公告：重大新产品发布",
        "市场反馈：预订量或销量超预期",
    ],
    consequent_event="股价上涨",
    probability=0.65,
    avg_lead_time_days=2,
)
```

**其他5个**: 分红预案、股权激励、订单中标、研发突破、违规处罚

---

### 3. 技术面模式 (10个)

```python
# 突破关键位
CausalPattern(
    pattern_id="pattern_breakout_resistance_001",
    precursor_signals=[
        "技术形态：突破前期高点或重要阻力位",
        "成交量：放量突破（成交量>5日均量1.5倍）",
    ],
    consequent_event="继续上涨",
    probability=0.60,
    avg_lead_time_days=3,
)

# 成交量放大
CausalPattern(
    pattern_id="pattern_volume_surge_001",
    precursor_signals=[
        "成交量：单日成交量>20日均量2倍",
        "价格：上涨>3%",
    ],
    consequent_event="短期继续上涨",
    probability=0.55,
    avg_lead_time_days=2,
)

# MACD金叉
CausalPattern(
    pattern_id="pattern_macd_golden_cross_001",
    precursor_signals=[
        "技术指标：MACD DIF上穿DEA",
        "位置：零轴附近或零轴上方",
    ],
    consequent_event="上涨趋势确立",
    probability=0.50,
    avg_lead_time_days=5,
)

# 均线多头排列
CausalPattern(
    pattern_id="pattern_ma_bullish_alignment_001",
    precursor_signals=[
        "均线形态：5日>10日>20日>60日",
        "趋势：均线向上发散",
    ],
    consequent_event="持续上涨",
    probability=0.65,
    avg_lead_time_days=10,
)

# 缩量回调
CausalPattern(
    pattern_id="pattern_pullback_low_volume_001",
    precursor_signals=[
        "价格：回调3-5%",
        "成交量：缩量（<5日均量0.7倍）",
    ],
    consequent_event="回调结束，继续上涨",
    probability=0.55,
    avg_lead_time_days=3,
)
```

**其他5个**: 跌破支撑、背离信号、形态突破、波段高点、超跌反弹

---

### 4. 资金面模式 (10个)

```python
# 北向资金流入
CausalPattern(
    pattern_id="pattern_northbound_inflow_001",
    precursor_signals=[
        "资金流向：北向资金连续3日净流入，累计>50亿",
        "市场表现：上证指数企稳或上涨",
    ],
    consequent_event="市场上涨",
    probability=0.70,
    avg_lead_time_days=2,
)

# 融资余额增加
CausalPattern(
    pattern_id="pattern_margin_balance_increase_001",
    precursor_signals=[
        "融资余额：连续5日增加，累计增幅>2%",
        "市场情绪：恐贪指数>50",
    ],
    consequent_event="市场上涨",
    probability=0.60,
    avg_lead_time_days=3,
)

# 大宗交易
CausalPattern(
    pattern_id="pattern_block_trade_001",
    precursor_signals=[
        "大宗交易：单日成交额>流通市值1%",
        "折价率：折价<5%（接近市价）",
    ],
    consequent_event="股价上涨",
    probability=0.55,
    avg_lead_time_days=5,
)

# ETF申购
CausalPattern(
    pattern_id="pattern_etf_creation_001",
    precursor_signals=[
        "ETF份额：单日增加>2%",
        "标的：宽基指数ETF（如沪深300、中证500）",
    ],
    consequent_event="相关指数上涨",
    probability=0.50,
    avg_lead_time_days=2,
)

# 机构调研
CausalPattern(
    pattern_id="pattern_institutional_research_001",
    precursor_signals=[
        "调研记录：10家以上机构集中调研",
        "公司质量：行业龙头或成长股",
    ],
    consequent_event="股价上涨",
    probability=0.60,
    avg_lead_time_days=7,
)
```

**其他5个**: 减持预告、定增完成、回购注销、股权质押、资金流出

---

## 实现步骤

### 1. 创建扩展脚本

```bash
# 复制初始化脚本
cp scripts/init_causal_graph.py scripts/expand_causal_graph.py

# 编辑添加新模式
nano scripts/expand_causal_graph.py
```

### 2. 运行扩展脚本

```bash
cd /mnt/d/AIProjects/MarketRadar
python3 scripts/expand_causal_graph.py
```

### 3. 验证扩展结果

```python
from m2_storage.signal_store import SignalStore

store = SignalStore()
all_patterns = store.query_causal_patterns()
print(f"总计: {len(all_patterns)} 个模式")

# 按类别统计
categories = {}
for p in all_patterns:
    category = p.pattern_id.split('_')[1]  # 提取类别
    categories[category] = categories.get(category, 0) + 1

for cat, count in categories.items():
    print(f"  {cat}: {count} 个")
```

---

## 注意事项

1. **概率校准**: 新模式的概率需要基于历史数据验证,初始值可以保守估计
2. **时间窗口**: avg_lead_time_days 要符合实际市场反应速度
3. **前置信号**: 要具体、可观测、可量化
4. **supporting_cases**: 初期可以为空,后续通过M6复盘补充
5. **confidence**: 新模式置信度建议设为0.5,待验证后提升

---

## 下一步

完成因果图谱扩充后,继续任务6:构建历史案例库
