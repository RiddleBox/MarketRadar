# 数据提供者架构设计文档

**创建时间**: 2026-05-07  
**版本**: v1.0  
**状态**: 实施中

---

## 📋 设计目标

将外部数据源（A股数据SKILL、AKShare、RSS等）设计为**可插拔的数据提供者**，通过统一接口为各模块提供数据，保持核心推理链条的独立性和可测试性。

### 核心原则

1. **依赖倒置** - 核心模块依赖抽象接口，不依赖具体实现
2. **单一职责** - 数据提供者只负责数据获取，不参与推理逻辑
3. **开闭原则** - 对扩展开放（添加新数据源），对修改关闭（不影响现有模块）
4. **可插拔** - 支持动态注册/移除数据提供者
5. **可降级** - 多数据源自动降级，提高可用性

---

## 🏗️ 架构设计

### 三层架构

```
┌─────────────────────────────────────────────────────────┐
│              Layer 1: 核心业务模块（不变）                 │
│  M0 → M1 → M2 → M3 → M4 → M5 → M9                       │
│  (推理链条保持独立，通过接口调用数据)                       │
└─────────────────────────────────────────────────────────┘
                          ↓ 调用
┌─────────────────────────────────────────────────────────┐
│         Layer 2: 数据提供者管理层（新增）                  │
│                                                           │
│  DataProviderManager                                     │
│  - 多源聚合                                               │
│  - 自动降级                                               │
│  - 去重排序                                               │
│  - 健康检查                                               │
└─────────────────────────────────────────────────────────┘
                          ↓ 实现
┌─────────────────────────────────────────────────────────┐
│         Layer 3: 具体数据提供者（可插拔）                  │
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ AStock SKILL │  │   AKShare    │  │  RSS Feeds   │  │
│  │  Provider    │  │   Provider   │  │   Provider   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 💻 接口定义

### DataProvider 抽象基类

```python
# integrations/data_provider_interface.py
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime

class DataProvider(ABC):
    """数据提供者抽象接口"""
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        返回支持的能力列表
        
        Returns:
            ['news', 'quote', 'research', 'sentiment', 'fundamentals']
        """
        pass
    
    @abstractmethod
    def get_news(self, symbol: str, limit: int = 10, 
                 start_date: Optional[datetime] = None) -> List[Dict]:
        """
        获取新闻
        
        Args:
            symbol: 股票代码（如 '000001'）
            limit: 返回数量
            start_date: 起始日期
        
        Returns:
            [
                {
                    "title": "新闻标题",
                    "content": "新闻内容",
                    "source": "来源",
                    "published_at": "2026-05-07 10:00:00",
                    "url": "https://...",
                    "provider": "astock_skill"
                }
            ]
        """
        pass
    
    @abstractmethod
    def get_quote(self, symbol: str) -> Dict:
        """
        获取实时行情
        
        Returns:
            {
                "symbol": "000001.SZ",
                "price": 12.34,
                "change_pct": 1.23,
                "volume": 123456789,
                "pe": 5.67,
                "pb": 0.89,
                "market_cap": 123456789012.0,
                "provider": "astock_skill"
            }
        """
        pass
    
    @abstractmethod
    def get_research_reports(self, symbol: str, limit: int = 5) -> List[Dict]:
        """
        获取研报
        
        Returns:
            [
                {
                    "title": "研报标题",
                    "institution": "机构名称",
                    "rating": "买入",
                    "published_at": "2026-05-07",
                    "provider": "astock_skill"
                }
            ]
        """
        pass
    
    @abstractmethod
    def get_sentiment(self, symbol: str) -> Dict:
        """
        获取情绪指标
        
        Returns:
            {
                "symbol": "000001.SZ",
                "sentiment_score": 0.75,
                "hot_rank": 10,
                "provider": "astock_skill"
            }
        """
        pass
    
    @abstractmethod
    def get_fundamentals(self, symbol: str) -> Dict:
        """
        获取基本面数据
        
        Returns:
            {
                "symbol": "000001.SZ",
                "eps": 1.23,
                "roe": 12.34,
                "debt_ratio": 0.45,
                "report_date": "2026-03-31",
                "provider": "astock_skill"
            }
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """健康检查"""
        pass
```

---

## 🔌 数据提供者实现

### 1. A股数据 SKILL Provider

```python
# integrations/astock_skill_provider.py
from integrations.data_provider_interface import DataProvider
from integrations import astock_skill
import logging

logger = logging.getLogger(__name__)

class AStockSkillProvider(DataProvider):
    """A股数据 SKILL 的数据提供者实现"""
    
    def __init__(self):
        self._capabilities = ['news', 'quote', 'research', 'fundamentals']
    
    def get_capabilities(self) -> List[str]:
        return self._capabilities
    
    def get_news(self, symbol: str, limit: int = 10, 
                 start_date: Optional[datetime] = None) -> List[Dict]:
        try:
            raw_news = astock_skill.get_stock_news(symbol, limit)
            
            return [
                {
                    "title": item.get("新闻标题", ""),
                    "content": item.get("新闻内容", ""),
                    "source": item.get("文章来源", ""),
                    "published_at": item.get("发布时间", ""),
                    "url": item.get("新闻链接", ""),
                    "provider": "astock_skill"
                }
                for item in raw_news
            ]
        except Exception as e:
            logger.error(f"AStockSkill get_news failed: {e}")
            return []
    
    def get_quote(self, symbol: str) -> Dict:
        try:
            raw_quote = astock_skill.tencent_quote(symbol)
            if not raw_quote:
                return {}
            
            return {
                "symbol": raw_quote["symbol"],
                "price": raw_quote["price"],
                "change_pct": raw_quote["change_pct"],
                "volume": raw_quote["volume"],
                "pe": raw_quote.get("pe_ttm"),
                "pb": raw_quote.get("pb"),
                "market_cap": raw_quote.get("market_cap"),
                "provider": "astock_skill"
            }
        except Exception as e:
            logger.error(f"AStockSkill get_quote failed: {e}")
            return {}
    
    def get_research_reports(self, symbol: str, limit: int = 5) -> List[Dict]:
        try:
            raw_reports = astock_skill.eastmoney_reports(symbol, limit)
            
            return [
                {
                    "title": r.get("研报标题", ""),
                    "institution": r.get("机构名称", ""),
                    "rating": r.get("评级", ""),
                    "published_at": r.get("发布日期", ""),
                    "provider": "astock_skill"
                }
                for r in raw_reports
            ]
        except Exception as e:
            logger.error(f"AStockSkill get_research_reports failed: {e}")
            return []
    
    def get_sentiment(self, symbol: str) -> Dict:
        # SKILL 不支持情绪
        return {}
    
    def get_fundamentals(self, symbol: str) -> Dict:
        try:
            raw_data = astock_skill.get_financial_snapshot(symbol)
            if not raw_data:
                return {}
            
            return {
                "symbol": raw_data["symbol"],
                "revenue": raw_data.get("revenue"),
                "net_profit": raw_data.get("net_profit"),
                "roe": raw_data.get("roe"),
                "debt_ratio": raw_data.get("debt_ratio"),
                "report_date": raw_data.get("report_date"),
                "provider": "astock_skill"
            }
        except Exception as e:
            logger.error(f"AStockSkill get_fundamentals failed: {e}")
            return {}
    
    def health_check(self) -> bool:
        try:
            result = astock_skill.tencent_quote("000001")
            return result is not None
        except:
            return False
```

### 2. RSS Provider

```python
# integrations/rss_provider.py
from integrations.data_provider_interface import DataProvider
from m0_collector.providers.rss import RssProvider as RssCollector

class RSSProvider(DataProvider):
    """RSS 新闻源的数据提供者实现"""
    
    def __init__(self):
        self._capabilities = ['news']
        self.collector = RssCollector()
    
    def get_capabilities(self) -> List[str]:
        return self._capabilities
    
    def get_news(self, symbol: str = None, limit: int = 10, 
                 start_date: Optional[datetime] = None) -> List[Dict]:
        """
        RSS 源返回宏观新闻，不针对特定股票
        """
        try:
            articles = self.collector.fetch(limit=limit)
            
            return [
                {
                    "title": article.title,
                    "content": article.content,
                    "source": article.source_name,
                    "published_at": article.raw_published_at,
                    "url": article.source_url,
                    "provider": "rss",
                    "type": "macro"  # 标记为宏观新闻
                }
                for article in articles
            ]
        except Exception as e:
            logger.error(f"RSS get_news failed: {e}")
            return []
    
    def get_quote(self, symbol: str) -> Dict:
        return {}  # RSS 不支持行情
    
    def get_research_reports(self, symbol: str, limit: int = 5) -> List[Dict]:
        return []  # RSS 不支持研报
    
    def get_sentiment(self, symbol: str) -> Dict:
        return {}  # RSS 不支持情绪
    
    def get_fundamentals(self, symbol: str) -> Dict:
        return {}  # RSS 不支持基本面
    
    def health_check(self) -> bool:
        try:
            articles = self.collector.fetch(limit=1)
            return len(articles) > 0
        except:
            return False
```

---

## 🎛️ 数据提供者管理器

```python
# integrations/data_provider_manager.py
from typing import List, Dict, Optional
from integrations.data_provider_interface import DataProvider
import logging

logger = logging.getLogger(__name__)

class DataProviderManager:
    """数据提供者管理器 - 支持多源聚合和降级"""
    
    def __init__(self):
        self._providers: Dict[str, DataProvider] = {}
        self._priority: Dict[str, List[tuple]] = {}  # capability → [(priority, name)]
    
    def register_provider(self, name: str, provider: DataProvider, 
                         priority: int = 100):
        """
        注册数据提供者
        
        Args:
            name: 提供者名称（如 'astock_skill'）
            provider: DataProvider 实例
            priority: 优先级（数字越大优先级越高）
        """
        self._providers[name] = provider
        
        # 根据能力和优先级排序
        for capability in provider.get_capabilities():
            if capability not in self._priority:
                self._priority[capability] = []
            self._priority[capability].append((priority, name))
            self._priority[capability].sort(reverse=True)  # 高优先级在前
        
        logger.info(f"✅ 注册数据提供者: {name}, 能力: {provider.get_capabilities()}, 优先级: {priority}")
    
    def get_news(self, symbol: str = None, limit: int = 10, 
                 providers: Optional[List[str]] = None,
                 aggregate: bool = True) -> List[Dict]:
        """
        获取新闻（支持多源聚合）
        
        Args:
            symbol: 股票代码（None = 获取宏观新闻）
            limit: 数量限制
            providers: 指定提供者列表（None = 使用所有可用提供者）
            aggregate: 是否聚合多源（True = 合并去重，False = 只用第一个成功的）
        """
        all_news = []
        
        # 确定使用哪些提供者
        if providers is None:
            providers = [name for _, name in self._priority.get('news', [])]
        
        if not aggregate:
            # 降级模式：只用第一个成功的
            for provider_name in providers:
                provider = self._providers.get(provider_name)
                if provider and 'news' in provider.get_capabilities():
                    try:
                        news = provider.get_news(symbol, limit)
                        if news:
                            return news
                    except Exception as e:
                        logger.warning(f"Provider {provider_name} failed, trying next: {e}")
                        continue
            return []
        
        # 聚合模式：从多个提供者获取新闻
        for provider_name in providers:
            provider = self._providers.get(provider_name)
            if provider and 'news' in provider.get_capabilities():
                try:
                    news = provider.get_news(symbol, limit)
                    all_news.extend(news)
                except Exception as e:
                    logger.warning(f"Provider {provider_name} failed: {e}")
                    continue
        
        # 去重 + 排序
        seen = set()
        unique_news = []
        for item in all_news:
            key = (item['title'], item.get('published_at', ''))
            if key not in seen:
                seen.add(key)
                unique_news.append(item)
        
        unique_news.sort(key=lambda x: x.get('published_at', ''), reverse=True)
        return unique_news[:limit]
    
    def get_quote(self, symbol: str, provider: Optional[str] = None) -> Dict:
        """
        获取行情（支持降级）
        
        Args:
            symbol: 股票代码
            provider: 指定提供者（None = 按优先级尝试）
        """
        if provider:
            # 使用指定提供者
            p = self._providers.get(provider)
            if p and 'quote' in p.get_capabilities():
                return p.get_quote(symbol)
        
        # 按优先级降级尝试
        for _, provider_name in self._priority.get('quote', []):
            provider = self._providers.get(provider_name)
            if provider and 'quote' in provider.get_capabilities():
                try:
                    result = provider.get_quote(symbol)
                    if result:
                        return result
                except Exception as e:
                    logger.warning(f"Provider {provider_name} failed, trying next: {e}")
                    continue
        
        logger.error(f"All quote providers failed for {symbol}")
        return {}
    
    def get_research_reports(self, symbol: str, limit: int = 5,
                            provider: Optional[str] = None) -> List[Dict]:
        """获取研报（支持降级）"""
        if provider:
            p = self._providers.get(provider)
            if p and 'research' in p.get_capabilities():
                return p.get_research_reports(symbol, limit)
        
        for _, provider_name in self._priority.get('research', []):
            provider = self._providers.get(provider_name)
            if provider and 'research' in provider.get_capabilities():
                try:
                    result = provider.get_research_reports(symbol, limit)
                    if result:
                        return result
                except Exception as e:
                    logger.warning(f"Provider {provider_name} failed, trying next: {e}")
                    continue
        
        return []
    
    def get_fundamentals(self, symbol: str, provider: Optional[str] = None) -> Dict:
        """获取基本面（支持降级）"""
        if provider:
            p = self._providers.get(provider)
            if p and 'fundamentals' in p.get_capabilities():
                return p.get_fundamentals(symbol)
        
        for _, provider_name in self._priority.get('fundamentals', []):
            provider = self._providers.get(provider_name)
            if provider and 'fundamentals' in provider.get_capabilities():
                try:
                    result = provider.get_fundamentals(symbol)
                    if result:
                        return result
                except Exception as e:
                    logger.warning(f"Provider {provider_name} failed, trying next: {e}")
                    continue
        
        return {}
    
    def health_check(self) -> Dict[str, bool]:
        """检查所有提供者健康状态"""
        return {
            name: provider.health_check()
            for name, provider in self._providers.items()
        }
    
    def list_capabilities(self) -> Dict[str, List[str]]:
        """列出所有能力及其提供者"""
        result = {}
        for capability, providers in self._priority.items():
            result[capability] = [name for _, name in providers]
        return result


# 全局单例
_global_manager = None

def get_global_data_manager() -> DataProviderManager:
    """获取全局数据管理器"""
    global _global_manager
    if _global_manager is None:
        _global_manager = DataProviderManager()
    return _global_manager
```

---

## ⚙️ 配置文件

```yaml
# config/data_providers.yaml
providers:
  astock_skill:
    enabled: true
    priority: 100
    description: "A股数据SKILL - 提供个股新闻/行情/研报/基本面"
    capabilities:
      - news
      - quote
      - research
      - fundamentals
    config:
      timeout: 5
      retry: 3
  
  rss:
    enabled: true
    priority: 60
    description: "RSS新闻源 - 提供宏观财经新闻"
    capabilities:
      - news
    config:
      feeds:
        - name: "财新网"
          url: "http://www.caixin.com/rss/rss_finance.xml"
          type: "macro"
        - name: "第一财经"
          url: "https://www.yicai.com/rss/news.xml"
          type: "industry"
  
  akshare:
    enabled: false  # Python 3.14 不兼容，暂时禁用
    priority: 80
    description: "AKShare - A股数据接口"
    capabilities:
      - news

# 各模块的数据源偏好
modules:
  m0_collector:
    news:
      providers: ['astock_skill', 'rss']  # 聚合多源
      aggregate: true
  
  m2_sentiment:
    quote:
      provider: 'astock_skill'  # 优先 SKILL
  
  m3_opportunity:
    fundamentals:
      provider: 'astock_skill'
    research:
      provider: 'astock_skill'
```

---

## 🚀 初始化和使用

### 1. 系统启动时初始化

```python
# m7_scheduler/scheduler.py 或 main.py
from integrations.data_provider_manager import get_global_data_manager
from integrations.astock_skill_provider import AStockSkillProvider
from integrations.rss_provider import RSSProvider
import yaml

def initialize_data_providers():
    """初始化数据提供者"""
    manager = get_global_data_manager()
    
    # 读取配置
    with open('config/data_providers.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 注册 A股数据 SKILL
    if config['providers']['astock_skill']['enabled']:
        provider = AStockSkillProvider()
        priority = config['providers']['astock_skill']['priority']
        manager.register_provider('astock_skill', provider, priority)
    
    # 注册 RSS
    if config['providers']['rss']['enabled']:
        provider = RSSProvider()
        priority = config['providers']['rss']['priority']
        manager.register_provider('rss', provider, priority)
    
    # 健康检查
    health = manager.health_check()
    logger.info(f"📊 数据提供者健康状态: {health}")
    
    # 列出能力
    capabilities = manager.list_capabilities()
    logger.info(f"📋 可用能力: {capabilities}")

# 在系统启动时调用
initialize_data_providers()
```

### 2. 各模块调用示例

```python
# M0 采集器
from integrations.data_provider_manager import get_global_data_manager

class M0Collector:
    def __init__(self):
        self.data_manager = get_global_data_manager()
    
    def collect_news_for_symbol(self, symbol: str):
        """采集个股新闻"""
        # 自动聚合 SKILL + RSS 的新闻
        news_list = self.data_manager.get_news(symbol, limit=20, aggregate=True)
        
        for news in news_list:
            # 写入 data/incoming/
            self._write_to_incoming(news)
    
    def collect_macro_news(self):
        """采集宏观新闻"""
        # 只从 RSS 获取宏观新闻
        news_list = self.data_manager.get_news(symbol=None, limit=50, providers=['rss'])
        
        for news in news_list:
            self._write_to_incoming(news)


# M3 机会判断
from integrations.data_provider_manager import get_global_data_manager

class M3OpportunityJudge:
    def __init__(self):
        self.data_manager = get_global_data_manager()
    
    def judge_opportunity(self, signal: MarketSignal):
        # 获取基本面数据辅助判断
        fundamentals = self.data_manager.get_fundamentals(signal.symbol)
        
        # 获取最新行情
        quote = self.data_manager.get_quote(signal.symbol)
        
        # 获取研报参考
        reports = self.data_manager.get_research_reports(signal.symbol, limit=3)
        
        # ... 机会判断逻辑
```

---

## ✅ 实施步骤

### 第一阶段：基础架构（1小时）

1. ✅ 创建 `integrations/data_provider_interface.py`
2. ✅ 创建 `integrations/data_provider_manager.py`
3. ✅ 创建 `config/data_providers.yaml`

### 第二阶段：SKILL 集成（1小时）

4. ✅ 提取 SKILL 核心函数到 `integrations/astock_skill.py`
5. ✅ 创建 `integrations/astock_skill_provider.py`
6. ✅ 测试 SKILL Provider

### 第三阶段：RSS 集成（30分钟）

7. ✅ 创建 `integrations/rss_provider.py`
8. ✅ 测试 RSS Provider

### 第四阶段：系统集成（1小时）

9. ✅ 在系统启动时初始化数据提供者
10. ✅ 修改 M0 采集器使用数据管理器
11. ✅ 修改 M3 判断引擎使用数据管理器

### 第五阶段：测试验证（30分钟）

12. ✅ 端到端测试
13. ✅ 健康检查测试
14. ✅ 降级测试

---

## 📊 预期效果

### 数据源状态

```
数据提供者健康状态:
  astock_skill: ✅ 正常
  rss: ✅ 正常
  akshare: ❌ 禁用

可用能力:
  news: ['astock_skill', 'rss']
  quote: ['astock_skill']
  research: ['astock_skill']
  fundamentals: ['astock_skill']
```

### 信号类型分布

```
总信号数: 500
├── 显式信号 (SKILL): 200 (40%)
│   ├── 个股新闻: 150
│   ├── 研报: 30
│   └── 公告: 20
│
└── 隐式信号 (RSS): 300 (60%)
    ├── 宏观经济: 100
    ├── 行业动态: 120
    └── 政策变化: 80
```

---

## 🎯 优势总结

1. **模块边界清晰** - 核心逻辑不依赖具体数据源
2. **可插拔** - 随时添加/移除数据提供者
3. **可测试** - 可以 Mock DataProvider 进行单元测试
4. **可降级** - 某个源失败自动切换
5. **可聚合** - 多源数据自动去重合并
6. **可配置** - 通过 YAML 控制数据源优先级
7. **可扩展** - 添加新数据源只需实现接口

---

**文档结束**
