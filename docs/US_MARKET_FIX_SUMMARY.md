# 美股功能修复总结

> **日期**: 2026-05-09  
> **修复内容**: 美股盘前扫描、M12扫描监控Dashboard、数据提供者架构优化

---

## 问题回顾

用户提出了3个关于美股功能的问题：

1. **美股盘前扫描未生效** - 硬编码使用AKShare，遇到Python 3.14兼容性问题
2. **美股盘中扫描结果无处查看** - 缺少Dashboard页面展示M12扫描详情
3. **美股新闻RSS订阅** - 已配置但需要验证是否正常工作

---

## 修复内容

### 1. 美股盘前扫描架构重构 ✅

**问题**：
- 盘前扫描硬编码使用 `AkshareNewsProvider`
- 无法利用已配置的美股RSS新闻源（Reuters, MarketWatch, CNBC等）
- AKShare在Python 3.14下有正则表达式兼容性问题

**解决方案**：
- 重构 `_task_m12_premarket_scan` 使用 `UnifiedNewsCollector`
- 支持多数据源聚合（RSS + astock_skill）
- 从 `data/incoming/*.txt` 读取新闻文件
- 使用与 `pipeline/ingest.py` 相同的处理逻辑

**修改文件**：
- `m7_scheduler/scheduler.py` (lines 1020-1130)

**测试结果**：
```
✅ 采集新闻：20条（多源聚合）
✅ M1解码：20个信号
✅ M3判断：0个机会（正常，未达阈值）
✅ 使用统一数据提供者架构
```

### 2. M12扫描监控Dashboard ✅

**新增页面**：`dashboard_v2/pages/8_📊_M12扫描.py`

**功能特性**：
- **扫描概览**：24小时扫描次数、发现机会数、任务状态
- **机会发现趋势图**：可视化展示扫描历史和机会数量变化
- **市场筛选**：支持按A股/港股/美股筛选
- **扫描记录表格**：显示最近100次扫描的详细信息
- **M12任务状态**：展示所有M12扫描任务的运行状态

**数据源**：
- `data/m12_scan_results.json` - 扫描历史统计
- `data/scheduler_state.json` - 调度器任务状态

### 3. 美股新闻RSS验证 ✅

**已配置的美股新闻源**（`config/data_providers.yaml`）：
```yaml
- name: "Reuters Business"
  url: "https://www.reutersagency.com/feed/..."
  type: "us_market"

- name: "MarketWatch"
  url: "https://feeds.marketwatch.com/marketwatch/topstories/"
  type: "us_market"

- name: "Seeking Alpha"
  url: "https://seekingalpha.com/feed.xml"
  type: "us_market"

- name: "Yahoo Finance"
  url: "https://finance.yahoo.com/news/rssindex"
  type: "us_market"

- name: "CNBC"
  url: "https://www.cnbc.com/id/100003114/device/rss/rss.html"
  type: "us_market"
```

**验证结果**：
- ✅ RSS提供者正常工作
- ✅ 成功采集美股新闻（如CNBC的Akamai AI基建新闻）
- ⚠️ 部分RSS源有格式问题（mismatched tag），但不影响整体功能

---

## 架构改进

### .txt vs .json 文件格式

**设计理由**：
- `data/incoming/` 使用 `.txt` 格式存储新闻
- 元数据以HTML注释形式嵌入：`<!-- source: ... | url: ... -->`
- M1解码器只需要文本内容，不需要解析JSON结构
- 简单、可读、易于人工审查

**处理流程**：
```
UnifiedNewsCollector → incoming/*.txt → M1解码 → M2存储
                        ↓
                   使用文件名作为source_ref
```

### 数据提供者架构

**优势**：
- 多源聚合：同时使用astock_skill和RSS
- 自动去重：避免重复采集
- 容错性：单个源失败不影响其他源
- 可扩展：易于添加新的数据提供者

---

## M3修复验证

**最新生成的机会文件已包含正确的股票代码**：

A股机会示例：
```json
{
  "title": "金融板块业绩分化机会",
  "priority": "research",
  "instruments": [
    "000776.SZ",
    "600036.SH",
    "601166.SH",
    "601398.SH",
    "600048.SH"
  ]
}
```

美股盘前机会示例：
```json
{
  "title": "AI基建需求爆发",
  "priority": "research",
  "instruments": [
    "NVDA",
    "AKAM",
    "IREN"
  ]
}
```

**不再是ETF名称或板块名称！** ✅

---

## 遗留问题

### 1. RSS源格式问题 ⚠️

部分RSS源有XML格式问题：
- 财新网：`<unknown>:15:2: mismatched tag`
- 第一财经：`<unknown>:2:500: not well-formed (invalid token)`
- Reuters Business：`<unknown>:38:160: mismatched tag`

**影响**：不影响整体功能，但这些源的新闻可能无法采集

**建议**：
- 检查RSS源URL是否正确
- 考虑添加更健壮的XML解析容错机制
- 或者禁用有问题的源

### 2. 优先级仍为research ⚠️

新生成的机会优先级仍为"research"，未达到"position"或"urgent"

**原因**：
- 机会评分未达到阈值（需要 overall_score >= 8 且 confidence >= 0.8）
- 当前机会的评分在6.6-7.4之间

**建议**：
- 观察更多机会生成，看是否有高分机会
- 如果持续无position级别机会，可能需要调整评分逻辑或阈值

---

## 测试验证

### 盘前扫描测试
```bash
python -m m7_scheduler.cli run m12_premarket_us
```

**结果**：
- ✅ 采集20条新闻
- ✅ 解码20个信号
- ✅ 判断0个机会（正常）
- ✅ 无错误

### Dashboard访问
```bash
streamlit run dashboard_v2/Home.py --server.port 8502
```

**新增页面**：
- 📊 M12扫描 - 展示扫描历史和任务状态

---

## 相关文件

**修改**：
- `m7_scheduler/scheduler.py` - 盘前扫描架构重构
- `pipeline/dashboard_OLD_DEPRECATED.py` - 旧Dashboard标记为废弃
- `pipeline/README_DASHBOARD.md` - Dashboard使用说明

**新增**：
- `dashboard_v2/pages/8_📊_M12扫描.py` - M12扫描监控页面
- `docs/US_MARKET_ISSUES.md` - 问题诊断文档
- `docs/US_MARKET_FIX_SUMMARY.md` - 本文档

---

## 下一步建议

1. **监控RSS源健康度** - 定期检查哪些源正常工作
2. **优化M3评分逻辑** - 如果需要更多position级别机会
3. **扩展M12扫描结果** - 记录更多扫描细节（异动股票、价格变化等）
4. **添加实时通知** - 当发现高分机会时推送通知

---

**修复完成** ✅
