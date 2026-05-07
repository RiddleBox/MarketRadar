# 新闻采集功能状态与解决方案

## 当前状态（2026-05-07）

### 核心问题
系统264条信号**全部为市场情绪快照**，**完全缺失新闻推理信号**，导致：
- M3判断引擎无法生成机会（缺少具体事件触发）
- 系统只能做宏观市场分析，无法捕捉个股机会
- 整个信号处理链路（M0→M1→M2→M3→M4）实际上处于半瘫痪状态

### 根因分析
1. **调度器导入路径错误**（已修复）
   - 错误：`from m0_collector.providers.akshare_provider import AKShareNewsProvider`
   - 正确：`from m0_collector.providers.akshare_news import AKShareNewsProvider`
   - 影响：新闻采集任务从未成功执行

2. **AKShare库兼容性问题**（无法修复）
   - Python 3.14 + pyarrow 正则表达式不兼容
   - 测试的所有接口均失败：
     - `stock_news_em()` - 东方财富新闻
     - `stock_comment_em()` - 千股千评
     - `stock_hot_rank_em()` - 热门股票
     - `stock_hot_keyword_em()` - 热门关键词
   - 错误信息：`re.error: global flags not at the start of the expression`

3. **RSS源全部失效**（需要替代方案）
   - 测试的4个RSS源全部解析失败：
     - 财联社：`https://www.cls.cn/rss`
     - 东方财富：`https://feed.eastmoney.com/news/cat_179.rss`
     - 新浪财经：`https://finance.sina.com.cn/rss/news.xml`
     - 华尔街见闻：`https://wallstreetcn.com/rss`
   - 错误原因：XML格式错误或源已失效

---

## 解决方案

### 方案1：降级Python版本（推荐）⭐
**优点：**
- 一劳永逸解决AKShare兼容性问题
- AKShare是最稳定的A股数据源
- 无需寻找替代数据源

**缺点：**
- 需要重新配置Python环境
- 可能影响其他依赖库

**实施步骤：**
```bash
# 1. 创建Python 3.11虚拟环境
conda create -n marketradar_py311 python=3.11
conda activate marketradar_py311

# 2. 重新安装依赖
pip install -r requirements.txt

# 3. 测试AKShare
python -c "import akshare as ak; print(ak.stock_news_em(symbol='000001').head())"
```

### 方案2：使用网页爬虫（备选）
**目标网站：**
- 东方财富：`https://finance.eastmoney.com/`
- 同花顺：`https://news.10jqka.com.cn/`
- 金融界：`http://stock.jrj.com.cn/`

**优点：**
- 不依赖第三方库
- 数据源稳定

**缺点：**
- 需要维护爬虫代码
- 可能被反爬虫机制阻止
- 需要处理网页结构变化

**实施步骤：**
```python
# 创建 m0_collector/providers/web_scraper.py
# 使用 requests + BeautifulSoup
# 参考现有的 rss.py 结构
```

### 方案3：手动新闻输入（临时）
**当前已支持：**
- Dashboard V2 → 手动输入页面
- 可以手动添加新闻事件
- 立即进入信号处理流程

**适用场景：**
- 测试系统完整性
- 验证信号处理链路
- 紧急情况下的临时方案

**使用方法：**
```bash
# 启动Dashboard V2
python -m streamlit run dashboard_v2/Home.py

# 访问"手动输入"页面
# 输入新闻标题、内容、相关股票
```

### 方案4：付费API（长期）
**推荐服务：**
- Tushare Pro（国内A股数据）
- Alpha Vantage（全球市场）
- Financial Modeling Prep（美股）

**优点：**
- 数据质量高
- 稳定可靠
- 有官方支持

**缺点：**
- 需要付费
- 有API调用限制

---

## 推荐行动路径

### 立即执行（今天）
1. **降级到Python 3.11**
   - 创建新的虚拟环境
   - 重新安装依赖
   - 测试AKShare功能

2. **验证新闻采集**
   ```bash
   # 测试新闻采集
   python -c "from m0_collector.providers.akshare_news import AKShareNewsProvider; p = AKShareNewsProvider(); print(len(p.fetch(limit=10)))"
   ```

3. **运行完整信号处理链路**
   ```bash
   # 启动调度器
   python -m m7_scheduler.cli start
   
   # 等待10分钟，观察新闻采集任务
   # 检查信号数据库
   python test_signal_judgment.py
   ```

### 短期优化（本周）
1. **添加系统监控**
   - 健康检查：每个模块是否正常运行
   - 告警机制：关键任务失败时通知
   - 数据质量监控：信号数量、类型分布

2. **完善Dashboard V2**
   - 添加新闻采集状态显示
   - 显示最近采集的新闻
   - 显示信号处理统计

3. **测试完整流程**
   - M0新闻采集 → M1解码 → M2存储 → M3判断 → M4行动设计
   - 验证每个环节的输出
   - 修复发现的问题

### 长期规划（下月）
1. **多源新闻采集**
   - AKShare（主要）
   - 网页爬虫（备用）
   - 付费API（高质量）

2. **智能去重和过滤**
   - 新闻相似度检测
   - 垃圾信息过滤
   - 重要性评分

3. **实时监控系统**
   - 桌面应用开发
   - 实时进度显示
   - 系统健康监控

---

## 技术细节

### 当前调度器配置
```python
# m7_scheduler/scheduler.py
def _task_akshare_news_collect(self):
    """采集 AKShare 新闻"""
    from m0_collector.providers.akshare_news import AKShareNewsProvider
    provider = AKShareNewsProvider()
    articles = provider.fetch(limit=50)
    # ... 处理逻辑

# 注册任务（10分钟间隔）
self.register_task("akshare_news_collect", self._task_akshare_news_collect, interval_minutes=10)
```

### 信号数据统计
```sql
-- 总信号数
SELECT COUNT(*) FROM signals;  -- 264

-- 最近7天信号
SELECT COUNT(*) FROM signals 
WHERE event_time >= datetime('now', '-7 days');  -- 128

-- 信号类型分布
SELECT signal_type, COUNT(*) FROM signals GROUP BY signal_type;
-- sentiment: 264
-- news: 0  ⚠️ 问题所在
```

### 依赖版本
```
Python: 3.14 (当前) → 3.11 (推荐)
akshare: 1.15.14
pyarrow: 18.1.0
feedparser: 6.0.11
```

---

## 相关文档
- [系统状态总结](System_Status_Summary.md)
- [多源新闻监控计划](Multi_Source_News_Monitoring_Plan.md)
- [桌面应用实施计划](Desktop_App_Implementation_Plan.md)
- [用户指南](USER_GUIDE.md)

---

## 更新日志
- 2026-05-07: 初始版本，定位新闻采集失败根因
- 2026-05-07: 添加4种解决方案和推荐行动路径
