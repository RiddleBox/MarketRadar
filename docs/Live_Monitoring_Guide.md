# 实盘信号监控系统使用指南

## 概述

实盘信号监控系统每天自动采集真实新闻，使用M1.5推理隐性信号，通过M3验证置信度，并生成每日报告。

## 快速开始

### 1. 单次运行（今天）

**Windows:**
```bash
run_live_monitoring.bat
```

**Linux/Mac:**
```bash
bash run_live_monitoring.sh
```

### 2. 指定日期运行

```bash
python live_signal_monitor.py --date 2024-04-20
```

### 3. 持续监控模式（每24小时运行一次）

```bash
python live_signal_monitor.py --continuous
```

### 4. 自定义监控间隔（每6小时）

```bash
python live_signal_monitor.py --continuous --interval 6
```

## 系统架构

```
[数据采集] → [M1.5推理] → [M3验证] → [报告生成]
    ↓            ↓            ↓           ↓
新华社        隐性信号      贝叶斯      JSON报告
发改委        推理链        置信度      统计摘要
36氪          因果关系      历史案例    高置信信号
```

## 数据源

| 数据源 | 类型 | 覆盖领域 | 状态 |
|--------|------|----------|------|
| 新华社 | RSS | 政治、外交、财经 | ✅ 正常 |
| 发改委 | 爬虫 | 产业政策、投资 | ⚠️ 部分可用 |
| 36氪 | RSS | 科技、创业 | ✅ 正常 |

## 输出报告

### 报告位置
```
live_validation/
├── report_2024-04-20.json
├── report_2024-04-21.json
└── report_2024-04-22.json
```

### 报告结构
```json
{
  "metadata": {
    "generated_at": "2024-04-20T18:30:00",
    "date": "2024-04-20"
  },
  "statistics": {
    "news_count": 25,
    "signal_count": 8,
    "high_confidence_signals": 3,
    "signal_types": {
      "policy_driven": 5,
      "diplomatic_event": 2,
      "tech_breakthrough": 1
    },
    "industry_sectors": {
      "半导体设备": 3,
      "光伏中游": 2,
      "生物医药": 1
    }
  },
  "signals": [
    {
      "signal_id": "implicit_abc123",
      "signal_type": "policy_driven",
      "source": "发改委",
      "title": "关于支持集成电路产业发展的若干政策",
      "industry_sector": "半导体设备",
      "opportunity_description": "政策支持带动半导体设备采购增长",
      "target_symbols": ["688012.SH", "002371.SZ"],
      "prior_confidence": 0.784,
      "posterior_confidence": 0.784,
      "confidence_change": 0.0,
      "reasoning_chain": {
        "source_event": "国家发布半导体产业支持政策",
        "target_opportunity": "半导体设备厂商受益",
        "causal_links": [
          {
            "from_concept": "政策支持",
            "to_concept": "研发投入增加",
            "relation_type": "policy_drives",
            "confidence": 0.9,
            "reasoning": "税收减免和融资支持直接降低企业研发成本"
          }
        ]
      },
      "expected_impact_timeframe": "mid_term"
    }
  ]
}
```

## 信号质量指标

### 置信度分级
- **高置信度 (≥0.7)**: 强烈推荐关注，历史验证成功率高
- **中置信度 (0.5-0.7)**: 值得关注，需结合其他信息
- **低置信度 (<0.5)**: 仅供参考，不确定性较高

### 时间框架
- **immediate**: 立即影响（1周内）
- **short_term**: 短期影响（1-3个月）
- **mid_term**: 中期影响（3-6个月）
- **long_term**: 长期影响（6个月以上）

## 验证流程

### 第1天：信号生成
1. 采集当天新闻
2. M1.5推理隐性信号
3. M3验证置信度
4. 记录信号详情

### 第2-7天：持续跟踪
1. 每天采集新闻
2. 生成新信号
3. 累积信号数据

### 第8天：验证分析
1. 回顾7天信号
2. 对比市场表现
3. 评估信号准确性
4. 更新历史案例库

## 验证指标

### 准确性指标
- **信号命中率**: 高置信度信号中，实际发生的比例
- **时效性**: 信号生成到事件发生的时间差
- **可操作性**: 信号是否提供明确的投资标的

### 质量指标
- **推理链完整性**: 因果链条是否清晰
- **置信度校准**: 预测置信度与实际结果的匹配度
- **标的准确性**: 推荐标的是否真正受益

## 常见问题

### Q1: 为什么有些新闻没有生成信号？
**A**: 可能原因：
- 新闻内容不包含投资机会
- LLM判断信息不足以推理
- 推理链置信度过低被过滤

### Q2: 如何提高信号质量？
**A**: 改进方向：
- 扩充产业链图谱（更多产业节点）
- 增加历史案例（提高验证准确性）
- 优化推理提示词（更精准的推理）

### Q3: 持续监控会消耗多少API费用？
**A**: 估算（基于DeepSeek定价）：
- 每条新闻推理：~2000 tokens
- 每天25条新闻：~50,000 tokens
- DeepSeek价格：~0.14元/百万tokens
- 每天成本：~0.007元（不到1分钱）

### Q4: 如何停止持续监控？
**A**: 按 `Ctrl+C` 中断程序

### Q5: 报告中的置信度变化为什么是0？
**A**: 可能原因：
- 历史案例库中没有相似案例
- 贝叶斯更新后置信度未变化
- 需要扩充历史案例库

## 下一步计划

### Week 1: 数据收集
- [x] 部署监控系统
- [ ] 运行7天，收集信号
- [ ] 记录每日统计

### Week 2: 验证分析
- [ ] 分析信号准确性
- [ ] 识别改进点
- [ ] 更新历史案例库

### Week 3: 系统优化
- [ ] 优化推理提示词
- [ ] 扩充产业链数据
- [ ] 调整置信度阈值

### Week 4: M9集成
- [ ] 将高置信度信号传递给M9
- [ ] M9模拟盘执行交易
- [ ] 观察交易结果

## 技术支持

遇到问题请查看：
- 日志文件：`live_validation/report_*.json`
- 错误信息：终端输出
- 配置文件：`config/llm_config.local.yaml`

## 更新日志

### 2024-04-24
- ✅ 初始版本发布
- ✅ 支持新华社、发改委、36氪数据源
- ✅ 集成DeepSeek API
- ✅ M1.5推理 + M3验证
- ✅ 每日报告生成
