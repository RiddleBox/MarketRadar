# 美股相关功能问题诊断

> **日期**: 2026-05-08  
> **问题**: 美股盘前扫描、盘中扫描结果展示、新闻RSS订阅

---

## 问题1: 美股盘前扫描未生效 ⚠️

### 现状
- **任务名**: `m12_premarket_us`
- **时间窗口**: `["21:00", "21:00"]` (单次触发)
- **last_run**: `null` (从未执行)
- **手动测试结果**: ✅ 可以执行，但有错误

### 测试输出
```
> 手动触发: m12_premarket_us
ERROR:m0_collector.providers.akshare_news:[M0] AKShare 新闻采集失败: Invalid regular expression: invalid escape sequence: \u
手动触发完成: ok
  market: US
  news_count: 0
  signals: 0
  opportunities: 0
  batch_id: premarket_US_m12_premarket_us_20260508_224900_421e2f
```

### 问题分析
1. **AKShare错误**: Python 3.14兼容性问题（正则表达式转义）
2. **新闻采集失败**: 导致news_count=0，无法生成信号
3. **时间窗口**: 21:00单次触发，如果当时scheduler未运行则会错过

### 解决方案
- [ ] 修复AKShare正则表达式错误（或禁用AKShare，使用RSS）
- [ ] 确保21:00时scheduler正在运行
- [ ] 验证RSS美股新闻源是否正常工作

---

## 问题2: 美股盘中扫描结果无处查看 ⚠️

### 现状
- **扫描任务**: `m12_us_scan` 正常运行
- **结果存储**: `data/m12_scan_results.json` (仅统计数据)
- **Dashboard**: 无专门页面展示M12扫描结果

### 当前数据结构
```json
{
  "timestamp": "2026-04-29T12:22:18.962929",
  "total_opportunities": 0,
  "a_share": 0,
  "hk": 0,
  "us": 0
}
```

### 问题分析
1. **m12_scan_results.json**: 只记录统计数据，不记录具体扫描详情
2. **Dashboard缺失**: 没有页面展示M12的扫描过程和发现
3. **信息丢失**: 扫描了哪些股票、发现了什么异动、为什么没生成机会等信息无法查看

### 解决方案
- [ ] 扩展`m12_scan_results.json`，记录详细扫描信息：
  - 扫描的股票列表
  - 发现的异动（即使未达到机会阈值）
  - 价格变化、成交量等关键指标
  - 未生成机会的原因
- [ ] 在Dashboard添加"M12扫描监控"页面：
  - 展示最近扫描历史
  - 按市场（A股/港股/美股）分类
  - 显示异动股票列表
  - 可视化价格/成交量变化

---

## 问题3: 美股新闻RSS订阅 ✅ 已配置

### 现状
**配置文件**: `config/data_providers.yaml`

**已配置的美股新闻源**:
```yaml
- name: "Reuters Business"
  url: "https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best"
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

### 验证需求
- [ ] 测试这些RSS源是否可访问
- [ ] 检查unified_news_collect是否正确拉取美股新闻
- [ ] 验证美股新闻是否进入M1解码流程

---

## 优先级建议

### 高优先级
1. **修复AKShare错误** - 影响盘前扫描
2. **添加M12扫描监控页面** - 提升可观测性

### 中优先级
3. **验证RSS美股新闻** - 确保数据源正常
4. **优化m12_scan_results.json** - 记录更多细节

### 低优先级
5. **盘前扫描时间窗口优化** - 考虑容错机制

---

## 下一步行动

1. 测试RSS美股新闻源是否正常工作
2. 修复AKShare正则表达式错误
3. 设计并实现"M12扫描监控"Dashboard页面
4. 扩展m12_scan_results.json数据结构
