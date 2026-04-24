# 历史案例库构建指南

> **任务**: 从2023-2024历史数据提取100+案例
> **状态**: 待实现
> **预计工时**: 6-8小时

---

## 案例库目标

构建一个包含100+历史案例的数据库,用于M3推理引擎的案例检索,提升判断准确率。

---

## 案例结构

```python
from core.schemas import CaseRecord

CaseRecord(
    case_id="case_2024_02_05_rrr_cut",
    title="2024年2月5日央行降准",
    signal_sequence=[
        "2024-01-24: 央行行长讲话'适时降准'",
        "2024-01-20: 财政部提前发债",
        "2024-01-10: 8月CPI 0.6%通缩压力"
    ],
    evolution_process="信号出现后12-14天落地,市场提前3天开始反应",
    outcome="2024-02-05降准0.5个百分点,上证指数当日上涨2.5%",
    lessons_learned="三个前置信号指向宽松政策,历史上类似组合后2周内降准概率80%",
    tags=["货币政策", "降准", "宽松"],
    market=Market.A_SHARE,
    start_date=date(2024, 1, 10),
    end_date=date(2024, 2, 5),
    created_at=datetime.now()
)
```

---

## 案例来源

### 1. 货币政策案例 (20个)

**2023-2024重大事件**:
- 2024-09-24: 央行降准+降息组合拳
- 2024-07-22: LPR下调
- 2024-02-05: 降准0.5个百分点
- 2023-09-15: 降准0.25个百分点
- 2023-06-13: MLF降息
- 2023-03-17: 降准0.25个百分点

**案例模板**:
```python
{
    "case_id": "case_2024_09_24_policy_combo",
    "title": "2024年9月24日央行降准降息组合拳",
    "signal_sequence": [
        "2024-09-10: 政治局会议提到'加大宏观政策调控力度'",
        "2024-09-05: 8月CPI 0.6%,PPI -1.8%,通缩压力",
        "2024-08-30: 北向资金连续5日净流出,累计150亿"
    ],
    "evolution_process": "政治局会议后14天落地,市场提前2天开始反应",
    "outcome": "降准0.5个百分点+LPR下调25bp,上证指数3日累计上涨8.5%",
    "lessons_learned": "政治局会议+通缩压力+资金外流,三重信号触发政策组合拳",
    "tags": ["货币政策", "降准", "降息", "组合拳"]
}
```

---

### 2. 行业政策案例 (20个)

**2023-2024重大事件**:
- 2024-05-15: 新能源汽车补贴延续
- 2024-03-20: 地产政策放松(一线城市限购松绑)
- 2023-11-10: 医药集采(第九批)
- 2023-08-25: 科技产业政策(新质生产力)
- 2023-06-30: 消费刺激政策(家电以旧换新)

**案例模板**:
```python
{
    "case_id": "case_2024_03_20_property_easing",
    "title": "2024年3月20日地产政策放松",
    "signal_sequence": [
        "2024-03-10: 住建部提到'支持刚性和改善性住房需求'",
        "2024-03-05: 2月房地产销售面积同比下降25%",
        "2024-03-15: 上海宣布放松限购"
    ],
    "evolution_process": "政策表态后10天,一线城市陆续跟进",
    "outcome": "地产板块3日累计上涨12%,万科A涨停",
    "lessons_learned": "政策表态+数据差+一线城市先行,地产板块短期爆发",
    "tags": ["行业政策", "地产", "限购松绑"]
}
```

---

### 3. 个股事件案例 (20个)

**2023-2024重大事件**:
- 2024-08-15: 宁德时代业绩预增80%
- 2024-06-20: 比亚迪新车型发布(销量超预期)
- 2023-12-10: 茅台股东增持
- 2023-10-25: 中芯国际技术突破
- 2023-09-05: 美的集团回购注销

**案例模板**:
```python
{
    "case_id": "case_2024_08_15_catl_earnings",
    "title": "2024年8月15日宁德时代业绩预增",
    "signal_sequence": [
        "2024-08-15: 公告业绩预增80%",
        "2024-08-10: 新能源汽车销量数据超预期",
        "2024-08-05: 机构集中调研(15家)"
    ],
    "evolution_process": "公告当日涨停,次日继续上涨5%",
    "outcome": "3日累计上涨18%,带动新能源板块上涨",
    "lessons_learned": "业绩预增+行业景气+机构调研,三重利好叠加",
    "tags": ["个股事件", "业绩预增", "新能源"]
}
```

---

### 4. 技术面案例 (20个)

**2023-2024重大事件**:
- 2024-10-08: 上证指数突破3000点
- 2024-07-15: 创业板指突破前高
- 2023-11-20: 沪深300 MACD金叉
- 2023-09-25: 北证50放量突破
- 2023-08-10: 科创50均线多头排列

**案例模板**:
```python
{
    "case_id": "case_2024_10_08_breakout_3000",
    "title": "2024年10月8日上证指数突破3000点",
    "signal_sequence": [
        "2024-10-08: 突破3000点阻力位",
        "2024-10-08: 成交量放大至1.2万亿(>20日均量2倍)",
        "2024-10-07: 北向资金净流入80亿"
    ],
    "evolution_process": "突破当日涨3.5%,次日继续上涨2%",
    "outcome": "3日累计上涨7%,确立上涨趋势",
    "lessons_learned": "放量突破关键位+资金流入,技术面确认",
    "tags": ["技术面", "突破", "放量"]
}
```

---

### 5. 资金面案例 (20个)

**2023-2024重大事件**:
- 2024-09-20: 北向资金单日净流入200亿
- 2024-06-30: 融资余额突破1.8万亿
- 2023-12-15: 沪深300ETF单日申购50亿
- 2023-10-10: 茅台大宗交易溢价成交
- 2023-08-20: 外资增持A股核心资产

**案例模板**:
```python
{
    "case_id": "case_2024_09_20_northbound_surge",
    "title": "2024年9月20日北向资金单日净流入200亿",
    "signal_sequence": [
        "2024-09-20: 北向资金净流入200亿(创年内新高)",
        "2024-09-19: 央行释放宽松信号",
        "2024-09-18: 恐贪指数从30升至45"
    ],
    "evolution_process": "资金流入当日上涨2%,次3日累计上涨5%",
    "outcome": "外资抢筹,市场情绪转暖",
    "lessons_learned": "政策预期+资金流入+情绪改善,三重催化",
    "tags": ["资金面", "北向资金", "外资"]
}
```

---

## 实现步骤

### 1. 创建案例收集脚本

```bash
# 创建脚本
touch scripts/build_case_library.py
```

### 2. 编写案例数据

```python
#!/usr/bin/env python3
"""
构建历史案例库

从2023-2024历史数据提取100+案例
"""
from datetime import date, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.schemas import CaseRecord, Market
from m2_storage.signal_store import SignalStore


def create_monetary_policy_cases():
    """货币政策案例 (20个)"""
    cases = [
        CaseRecord(
            case_id="case_2024_09_24_policy_combo",
            title="2024年9月24日央行降准降息组合拳",
            signal_sequence=[
                "2024-09-10: 政治局会议提到'加大宏观政策调控力度'",
                "2024-09-05: 8月CPI 0.6%,PPI -1.8%,通缩压力",
                "2024-08-30: 北向资金连续5日净流出,累计150亿"
            ],
            evolution_process="政治局会议后14天落地,市场提前2天开始反应",
            outcome="降准0.5个百分点+LPR下调25bp,上证指数3日累计上涨8.5%",
            lessons_learned="政治局会议+通缩压力+资金外流,三重信号触发政策组合拳",
            tags=["货币政策", "降准", "降息", "组合拳"],
            market=Market.A_SHARE,
            start_date=date(2024, 8, 30),
            end_date=date(2024, 9, 24),
        ),
        # ... 添加其他19个案例
    ]
    return cases


def main():
    """主函数"""
    print("=" * 60)
    print("构建历史案例库")
    print("=" * 60)
    print()

    # 创建案例
    all_cases = []
    all_cases.extend(create_monetary_policy_cases())
    # all_cases.extend(create_industry_policy_cases())
    # all_cases.extend(create_stock_event_cases())
    # all_cases.extend(create_technical_cases())
    # all_cases.extend(create_capital_flow_cases())

    print(f"创建 {len(all_cases)} 个案例")
    print()

    # 保存到M2
    store = SignalStore()
    saved_count = 0

    for case in all_cases:
        if store.save_case_record(case):
            saved_count += 1
            print(f"[OK] {case.case_id}: {case.title}")
        else:
            print(f"[FAIL] {case.case_id}: 保存失败")

    print()
    print("=" * 60)
    print(f"完成：{saved_count}/{len(all_cases)} 个案例已保存")
    print("=" * 60)


if __name__ == "__main__":
    main()
```

### 3. 运行脚本

```bash
cd /mnt/d/AIProjects/MarketRadar
python3 scripts/build_case_library.py
```

### 4. 验证案例库

```python
from m2_storage.signal_store import SignalStore

store = SignalStore()
all_cases = store.query_case_records()
print(f"总计: {len(all_cases)} 个案例")

# 按标签统计
tags_count = {}
for case in all_cases:
    for tag in case.tags:
        tags_count[tag] = tags_count.get(tag, 0) + 1

for tag, count in sorted(tags_count.items(), key=lambda x: x[1], reverse=True):
    print(f"  {tag}: {count} 个")
```

---

## 数据来源

1. **公开数据**:
   - 东方财富网历史新闻
   - 同花顺公告数据
   - Wind资讯历史数据

2. **技术指标**:
   - AKShare历史K线数据
   - TuShare技术指标数据

3. **资金数据**:
   - 北向资金历史数据
   - 融资融券历史数据
   - ETF申赎数据

---

## 注意事项

1. **时间准确性**: 信号序列的时间要准确,用于计算lead_time
2. **因果关系**: 确保信号和结果之间有明确的因果关系
3. **可验证性**: 案例要基于真实历史数据,可验证
4. **教训提炼**: lessons_learned要有价值,能指导未来判断
5. **标签规范**: 使用统一的标签体系,便于检索

---

## 下一步

完成案例库构建后,测试M3推理引擎的案例检索功能,验证准确率提升效果。
