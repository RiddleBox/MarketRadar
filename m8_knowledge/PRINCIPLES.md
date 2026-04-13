# M8 Knowledge Base — 第一性原理文档

> **知识库不是问答系统，是判断的证据基础。它存在的意义是降低下游决策的不确定性，而不是提供答案。**

---

## 存在意义

M3 在判断机会时，需要回答一个问题："历史上，类似的信号组合，最终如何演化？"

没有知识库，M3 只能依赖 LLM 的参数知识（截止到训练日期，且可能有幻觉）。有了知识库，M3 可以检索真实的、经过审核的历史案例和分析框架。

**M8 的定位**：为 M3/M4 提供可溯源的证据，降低判断的不确定性。

---

## 什么值得存入知识库

### ✅ 应该存入
| 内容类型 | 说明 | 示例 |
|---------|------|------|
| `case_record` | 历史上已兑现的机会案例（含信号、过程、结果） | "2023年底AI算力板块行情复盘" |
| `analytical_framework` | 估值框架、行业分析方法论 | "半导体周期判断框架" |
| `market_structure` | 市场结构特征（A股情绪特征、港股外资逻辑等） | "A股主板情绪驱动特征研究" |
| `policy_context` | 重要政策文件和历史政策效果 | "2015年以来A股市场干预政策梳理" |
| `sector_dynamics` | 行业供需结构、竞争格局基础知识 | "新能源车行业价值链分析" |

### ❌ 不应该存入
- 实时新闻（那是 M1 的输入）
- 价格预测（知识库不做预测）
- 未经验证的分析（质量不可控）
- 过度细节的数据（知识库提供框架，不提供数据表格）

---

## 内容分类标准（四维标签）

```
market:    [A_SHARE, HK, US, CROSS_MARKET]
category:  [valuation, macro, industry, event, technical, policy, market_structure]
content_type: [case_record, analytical_framework, market_structure, policy_context, sector_dynamics]
tags:      [半导体, 新能源, 利率, 货币政策, ...]（自由标签）
```

---

## 检索设计原则

1. **精准优于召回**：宁可返回 3 条高质量结果，也不要返回 10 条噪音
2. **元数据过滤先于语义检索**：先按 market / category / content_type 筛选，再在子集内做语义检索
3. **信任度字段**：每条文档有 `trust_level`（1-5），M3 检索时可设最低信任度阈值
