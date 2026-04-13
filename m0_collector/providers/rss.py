"""
m0_collector/providers/rss.py — RSS 财经新闻 Provider

支持的免费 RSS 源（无需登录/API Key）：
  - 财联社快讯：https://www.cls.cn/rss
  - 东方财富财经：https://feed.eastmoney.com/news/cat_179.rss
  - 新浪财经：https://finance.sina.com.cn/rss/news.xml
  - 华尔街见闻：https://wallstreetcn.com/rss

配置在 m0_collector/config.yaml 中，可自由增删。
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse

from m0_collector.models import RawArticle
from m0_collector.providers.base import ProviderAdapter

logger = logging.getLogger(__name__)

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


# 默认 RSS 源列表（无需 API Key，公开可访问）
DEFAULT_RSS_FEEDS = [
    {
        "name": "财联社",
        "url": "https://www.cls.cn/rss",
        "language": "zh",
    },
    {
        "name": "东方财富",
        "url": "https://feed.eastmoney.com/news/cat_179.rss",
        "language": "zh",
    },
    {
        "name": "新浪财经",
        "url": "https://finance.sina.com.cn/rss/news.xml",
        "language": "zh",
    },
    {
        "name": "华尔街见闻",
        "url": "https://wallstreetcn.com/rss",
        "language": "zh",
    },
]


class RssProvider(ProviderAdapter):
    """RSS 财经新闻 Provider

    从多个 RSS 源抓取最新财经新闻，返回 RawArticle 列表。
    """

    def __init__(self, feeds: Optional[List[dict]] = None, timeout: int = 15, max_per_feed: int = 50):
        """
        Args:
            feeds: RSS 源配置列表，每项包含 name/url/language
                   None 表示使用 DEFAULT_RSS_FEEDS
            timeout: 每个源的请求超时秒数
            max_per_feed: 每个源最多取多少条
        """
        if not HAS_FEEDPARSER:
            raise ImportError("feedparser 未安装，请运行: pip install feedparser")
        self.feeds = feeds or DEFAULT_RSS_FEEDS
        self.timeout = timeout
        self.max_per_feed = max_per_feed

    @property
    def provider_id(self) -> str:
        return "rss"

    @property
    def display_name(self) -> str:
        return "RSS 财经新闻"

    def fetch(self, limit: Optional[int] = None, **kwargs) -> List[RawArticle]:
        """
        从所有配置的 RSS 源抓取新闻。

        Args:
            limit: 总条数上限（None = 不限）

        Returns:
            RawArticle 列表，单个源失败不影响其他源
        """
        articles: List[RawArticle] = []

        for feed_cfg in self.feeds:
            feed_name = feed_cfg.get("name", "未知")
            feed_url = feed_cfg.get("url", "")
            language = feed_cfg.get("language", "zh")

            if not feed_url:
                continue

            try:
                logger.info(f"[RSS] 抓取 {feed_name}: {feed_url}")
                fetched = self._fetch_single_feed(feed_url, feed_name, language)
                articles.extend(fetched[:self.max_per_feed])
                logger.info(f"[RSS] {feed_name}: 获取 {len(fetched)} 条")
                time.sleep(0.5)  # 礼貌延迟，避免被封
            except Exception as e:
                logger.warning(f"[RSS] {feed_name} 抓取失败: {e}")
                continue

        if limit is not None:
            articles = articles[:limit]

        logger.info(f"[RSS] 共获取 {len(articles)} 条文章")
        return articles

    def _fetch_single_feed(self, url: str, source_name: str, language: str) -> List[RawArticle]:
        """抓取单个 RSS 源"""
        feed = feedparser.parse(url, request_headers={"User-Agent": "MarketRadar/1.0"})

        if feed.bozo and not feed.entries:
            raise ValueError(f"RSS 解析失败: {feed.bozo_exception}")

        articles = []
        for entry in feed.entries:
            try:
                title = entry.get("title", "").strip()
                if not title:
                    continue

                # 内容提取（优先 content，其次 summary）
                content = ""
                if hasattr(entry, "content") and entry.content:
                    content = entry.content[0].get("value", "")
                elif hasattr(entry, "summary"):
                    content = entry.summary or ""

                content = self._clean_html(content) or title

                # 发布时间
                published = ""
                if hasattr(entry, "published"):
                    published = entry.published
                elif hasattr(entry, "updated"):
                    published = entry.updated

                # 链接
                link = entry.get("link", "") or url

                articles.append(RawArticle(
                    title=title,
                    content=content,
                    raw_published_at=published,
                    source_name=source_name,
                    source_url=link,
                    provider_id=self.provider_id,
                    language=language,
                ))
            except Exception as e:
                logger.debug(f"[RSS] 跳过条目: {e}")
                continue

        return articles

    def _clean_html(self, html: str) -> str:
        """清洗 HTML，提取纯文本"""
        if not html:
            return ""
        if HAS_BS4:
            try:
                soup = BeautifulSoup(html, "html.parser")
                return soup.get_text(separator="\n", strip=True)
            except Exception:
                pass
        # 降级：用正则去除标签
        text = re.sub(r"<[^>]+>", "", html)
        text = re.sub(r"&nbsp;", " ", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
