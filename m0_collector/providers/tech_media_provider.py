"""
36氪 Provider - 科技创业和行业分析数据源
支持: 技术突破、创业动态、行业趋势
官网: https://36kr.com/
"""

import feedparser
from datetime import datetime
from typing import List, Optional
from m0_collector.providers.base import ProviderAdapter
from m0_collector.models import RawArticle


class Kr36Provider(ProviderAdapter):
    """36氪新闻提供者"""

    def __init__(self):
        """初始化36氪提供者"""
        # 36氪RSS源
        self.rss_feeds = {
            "tech": "https://36kr.com/feed",
            "latest": "https://36kr.com/feed-latest",
        }

        # 备用：直接使用通用RSS
        self.backup_feed = "https://36kr.com/feed"

    @property
    def provider_id(self) -> str:
        return "36kr"

    @property
    def display_name(self) -> str:
        return "36氪"

    def fetch(self,
              category: str = "tech",
              limit: Optional[int] = None,
              **kwargs) -> List[RawArticle]:
        """
        获取36氪新闻

        Args:
            category: 新闻类别 (tech, latest)
            limit: 限制返回数量

        Returns:
            新闻文章列表
        """
        # 获取RSS源地址
        rss_url = self.rss_feeds.get(category, self.backup_feed)

        try:
            # 解析RSS
            feed = feedparser.parse(rss_url)

            # 检查是否成功
            if feed.bozo:
                print(f"RSS解析失败: {feed.bozo_exception}")
                # 尝试备用源
                if rss_url != self.backup_feed:
                    print(f"尝试备用源: {self.backup_feed}")
                    feed = feedparser.parse(self.backup_feed)
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

                # 提取标签/分类
                tags = []
                if hasattr(entry, 'tags'):
                    tags = [tag.term for tag in entry.tags]

                article = RawArticle(
                    title=entry.title if hasattr(entry, 'title') else '',
                    content=content,
                    raw_published_at=pub_date_str,
                    source_name="36氪",
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
            print(f"36氪RSS获取失败: {e}")
            return []

    def fetch_tech_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取科技新闻"""
        return self.fetch(category="tech", limit=limit)

    def fetch_latest_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取最新新闻"""
        return self.fetch(category="latest", limit=limit)


class HuxiuProvider(ProviderAdapter):
    """虎嗅新闻提供者"""

    def __init__(self):
        """初始化虎嗅提供者"""
        # 虎嗅RSS源
        self.rss_feeds = {
            "tech": "https://www.huxiu.com/rss/0.xml",
            "finance": "https://www.huxiu.com/rss/1.xml",
        }

    @property
    def provider_id(self) -> str:
        return "huxiu"

    @property
    def display_name(self) -> str:
        return "虎嗅"

    def fetch(self,
              category: str = "tech",
              limit: Optional[int] = None,
              **kwargs) -> List[RawArticle]:
        """
        获取虎嗅新闻

        Args:
            category: 新闻类别 (tech, finance)
            limit: 限制返回数量

        Returns:
            新闻文章列表
        """
        rss_url = self.rss_feeds.get(category)
        if not rss_url:
            print(f"未知的类别: {category}")
            return []

        try:
            # 解析RSS
            feed = feedparser.parse(rss_url)

            if feed.bozo:
                print(f"RSS解析失败: {feed.bozo_exception}")
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
                    source_name="虎嗅",
                    source_url=link,
                    provider_id=self.provider_id,
                    language='zh'
                )
                articles.append(article)

                if limit and len(articles) >= limit:
                    break

            return articles

        except Exception as e:
            print(f"虎嗅RSS获取失败: {e}")
            return []

    def fetch_tech_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取科技新闻"""
        return self.fetch(category="tech", limit=limit)

    def fetch_finance_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取财经新闻"""
        return self.fetch(category="finance", limit=limit)


# 便捷函数
def fetch_36kr_news(category: str = "tech", limit: int = 10) -> List[RawArticle]:
    """
    便捷函数：获取36氪新闻

    Args:
        category: 新闻类别 (tech, latest)
        limit: 限制返回数量

    Returns:
        新闻文章列表
    """
    provider = Kr36Provider()
    return provider.fetch(category=category, limit=limit)


def fetch_huxiu_news(category: str = "tech", limit: int = 10) -> List[RawArticle]:
    """
    便捷函数：获取虎嗅新闻

    Args:
        category: 新闻类别 (tech, finance)
        limit: 限制返回数量

    Returns:
        新闻文章列表
    """
    provider = HuxiuProvider()
    return provider.fetch(category=category, limit=limit)
