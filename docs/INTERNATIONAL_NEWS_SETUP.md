# 国际新闻源配置指南

MarketRadar现已支持港股和美股新闻采集！

## 支持的数据源

### 1. NewsAPI（推荐用于港股/美股）
- **官网**: https://newsapi.org/
- **免费额度**: 100次/天
- **覆盖市场**: 全球新闻（英文为主）
- **优势**: 新闻源广泛，更新及时

### 2. Finnhub
- **官网**: https://finnhub.io/
- **免费额度**: 60次/分钟
- **覆盖市场**: 美股、港股、全球市场
- **优势**: 支持按公司代码查询，数据质量高

### 3. AKShare（已配置）
- **免费**: 无需API Key
- **覆盖市场**: 主要是A股
- **优势**: 中文新闻，无需注册

## 快速开始

### 步骤1: 注册API Key

**NewsAPI**:
1. 访问 https://newsapi.org/register
2. 填写邮箱注册（免费）
3. 获取API Key

**Finnhub**:
1. 访问 https://finnhub.io/register
2. 注册账号（免费）
3. 在Dashboard获取API Key

### 步骤2: 配置环境变量

**Windows (CMD)**:
```cmd
set NEWSAPI_KEY=your_newsapi_key_here
set FINNHUB_API_KEY=your_finnhub_key_here
```

**Windows (PowerShell)**:
```powershell
$env:NEWSAPI_KEY="your_newsapi_key_here"
$env:FINNHUB_API_KEY="your_finnhub_key_here"
```

**永久配置** (推荐):
1. 右键"此电脑" → 属性 → 高级系统设置 → 环境变量
2. 在"用户变量"中新建:
   - 变量名: `NEWSAPI_KEY`，变量值: 你的API Key
   - 变量名: `FINNHUB_API_KEY`，变量值: 你的API Key

### 步骤3: 测试数据源

```bash
python test_international_news.py
```

## 使用示例

### 1. 在Python代码中使用

```python
from m0_collector.providers.newsapi_provider import NewsAPIProvider
from m0_collector.providers.finnhub_provider import FinnhubProvider

# NewsAPI - 搜索港股新闻
newsapi = NewsAPIProvider()
articles = newsapi.fetch(query="Hong Kong stock", language="en", page_size=10)

# Finnhub - 获取腾讯新闻
finnhub = FinnhubProvider()
articles = finnhub.fetch_company_news(symbol="0700.HK")

# Finnhub - 获取苹果新闻
articles = finnhub.fetch_company_news(symbol="AAPL")
```

### 2. 集成到日常流程

修改 `run_daily_pipeline.py`，添加国际新闻源：

```python
from m0_collector.providers.newsapi_provider import NewsAPIProvider
from m0_collector.providers.finnhub_provider import FinnhubProvider

# 采集港股新闻
newsapi = NewsAPIProvider()
hk_articles = newsapi.fetch(query="Hong Kong stock OR HKEX", language="en")

# 采集美股新闻
us_articles = newsapi.fetch(query="NYSE OR NASDAQ OR Wall Street", language="en")

# 采集特定公司新闻
finnhub = FinnhubProvider()
aapl_articles = finnhub.fetch_company_news(symbol="AAPL")
```

## 数据源对比

| 数据源 | A股 | 港股 | 美股 | 免费额度 | 语言 | 需要注册 |
|--------|-----|------|------|----------|------|----------|
| AKShare | ✅ | ⚠️ | ❌ | 无限制 | 中文 | ❌ |
| NewsAPI | ⚠️ | ✅ | ✅ | 100次/天 | 英文 | ✅ |
| Finnhub | ⚠️ | ✅ | ✅ | 60次/分钟 | 英文 | ✅ |

## 推荐配置

**日常监控**:
- **A股**: AKShare（主力）
- **港股**: NewsAPI + Finnhub（互补）
- **美股**: NewsAPI + Finnhub（互补）

**采集频率建议**:
- 盘前: 每天09:00采集隔夜新闻
- 盘中: 每2小时采集一次（注意API限额）
- 盘后: 每天16:00采集当日新闻

## 注意事项

1. **API限额**: 
   - NewsAPI免费版每天100次，建议只在盘前/盘后采集
   - Finnhub免费版每分钟60次，可以更频繁使用

2. **新闻语言**:
   - 国际新闻源主要是英文
   - M1解码器支持英文新闻（Claude API）
   - 可以考虑添加翻译步骤

3. **成本控制**:
   - 优先使用免费的AKShare
   - NewsAPI/Finnhub作为补充
   - 避免重复采集相同新闻

## 故障排查

**问题1: "需要提供API密钥"**
- 检查环境变量是否设置正确
- 重启终端/IDE使环境变量生效

**问题2: "API请求失败"**
- 检查网络连接
- 确认API Key是否有效
- 检查是否超过免费额度

**问题3: "获取到0篇文章"**
- 检查搜索关键词是否合适
- 尝试更换时间范围
- 查看API返回的错误信息

## 下一步

- [ ] 配置Windows定时任务，实现每日自动采集
- [ ] 添加新闻翻译功能（英文→中文）
- [ ] 优化关键词搜索策略
- [ ] 监控API使用量，避免超限
