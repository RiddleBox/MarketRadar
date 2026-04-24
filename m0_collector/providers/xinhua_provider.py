"""
新华社 Provider - 政策和外交新闻数据源
支持: 政策风向、外交动态、国家战略
官网: http://www.news.cn/
"""

import feedparser
from datetime import datetime
from typing import List, Optional
from m0_collector.providers.base import ProviderAdapter
from m0_collector.models import RawArticle


class XinhuaProvider(ProviderAdapter):
    """新华社新闻提供者"""

    def __init__(self):
        """初始化新华社提供者"""
        # 新华社RSS源（常见的RSS地址格式）
        self.rss_feeds = {
            "politics": "http://www.news.cn/politics/news_politics.xml",
            "world": "http://www.news.cn/world/news_world.xml",
            "finance": "http://www.news.cn/fortune/news_fortune.xml",
            "tech": "http://www.news.cn/tech/news_tech.xml",
        }

        # 备用RSS源（如果官方RSS不可用）
        self.backup_feeds = {
            "politics": "http://www.xinhuanet.com/politics/news_politics.xml",
            "world": "http://www.xinhuanet.com/world/news_world.xml",
        }

    @property
    def provider_id(self) -> str:
        return "xinhua"

    @property
    def display_name(self) -> str:
        return "新华社"

    def fetch(self,
              category: str = "politics",
              limit: Optional[int] = None,
              **kwargs) -> List[RawArticle]:
        """
        获取新华社新闻

        Args:
            category: 新闻类别 (politics, world, finance, tech)
            limit: 限制返回数量

        Returns:
            新闻文章列表
        """
        # 获取RSS源地址
        rss_url = self.rss_feeds.get(category)
        if not rss_url:
            print(f"未知的类别: {category}")
            return []

        try:
            # 解析RSS
            feed = feedparser.parse(rss_url)

            # 检查是否成功
            if feed.bozo:
                print(f"RSS解析失败: {feed.bozo_exception}")
                # 尝试备用源
                backup_url = self.backup_feeds.get(category)
                if backup_url:
                    print(f"尝试备用源: {backup_url}")
                    feed = feedparser.parse(backup_url)
                    if feed.bozo:
                        return []

            articles = []
            for entry in feed.entries:
                # 解析发布时间
                pub_date_str = ''
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    try:
                        pub_date = datetime(*entry.published_parsed[:6])
                        pub_date_str = pub_date.isoformat()
                    except:
                        pass
                elif hasattr(entry, 'published'):
                    pub_date_str = entry.published

                # 提取内容
                content = ''
                if hasattr(entry, 'summary'):
                    content = entry.summary
                elif hasattr(entry, 'description'):
                    content = entry.description

                # 提取链接
                link = entry.link if hasattr(entry, 'link') else ''

                article = RawArticle(
                    title=entry.title if hasattr(entry, 'title') else '',
                    content=content,
                    raw_published_at=pub_date_str,
                    source_name="新华社",
                    source_url=link,
                    provider_id=self.provider_id,
                    language='zh'
                )
                articles.append(article)

                # 应用limit限制
                if limit and len(articles) >= limit:
                    break

            return articles

        except Exception as e:
            print(f"新华社RSS获取失败: {e}")
            return []

    def fetch_politics_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取政治新闻"""
        return self.fetch(category="politics", limit=limit)

    def fetch_world_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取国际新闻"""
        return self.fetch(category="world", limit=limit)

    def fetch_finance_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取财经新闻"""
        return self.fetch(category="finance", limit=limit)

    def fetch_tech_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取科技新闻"""
        return self.fetch(category="tech", limit=limit)


# 便捷函数
def fetch_xinhua_news(category: str = "politics", limit: int = 10) -> List[RawArticle]:
    """
    便捷函数：获取新华社新闻

    Args:
        category: 新闻类别 (politics, world, finance, tech)
        limit: 限制返回数量

    Returns:
        新闻文章列表
    """
    provider = XinhuaProvider()
    return provider.fetch(category=category, limit=limit)
