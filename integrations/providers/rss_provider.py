"""
RSS 新闻源 Provider

提供宏观财经新闻（隐式推理信号），支持：
- 多个RSS源聚合
- 自动去重
- 时间过滤

配置的RSS源（来自 config/data_providers.yaml）：
- 财新网: http://www.caixin.com/rss/rss_finance.xml
- 第一财经: https://www.yicai.com/rss/news.xml
- 36氪: https://36kr.com/feed
- 虎嗅: https://www.huxiu.com/rss/0.xml
"""

from typing import List, Dict, Optional
from datetime import datetime
from integrations.data_provider_interface import DataProvider
import logging
import feedparser
import time

logger = logging.getLogger(__name__)


class RSSProvider(DataProvider):
    """RSS 新闻源数据提供者"""

    def __init__(self, feeds: List[Dict] = None):
        """
        初始化RSS Provider

        Args:
            feeds: RSS源配置列表
                [
                    {"name": "财新网", "url": "http://...", "type": "macro"},
                    ...
                ]
        """
        self._capabilities = ['news']
        self._feeds = feeds or []
        logger.info(f"RSS Provider 初始化，配置了 {len(self._feeds)} 个RSS源")

    def get_capabilities(self) -> List[str]:
        """返回支持的能力列表"""
        return self._capabilities

    def get_news(self, symbol: str = None, limit: int = 10,
                 start_date: Optional[datetime] = None) -> List[Dict]:
        """
        获取新闻（仅支持宏观新闻）

        Args:
            symbol: 股票代码（RSS不支持个股新闻，传入会返回空列表）
            limit: 返回数量
            start_date: 起始日期

        Returns:
            新闻列表
        """
        if symbol:
            logger.warning("RSS Provider 不支持个股新闻，仅支持宏观新闻")
            return []

        if not self._feeds:
            logger.warning("未配置RSS源")
            return []

        all_news = []

        for feed_config in self._feeds:
            feed_name = feed_config.get("name", "未知")
            feed_url = feed_config.get("url", "")
            feed_type = feed_config.get("type", "macro")

            if not feed_url:
                continue

            try:
                logger.info(f"正在拉取RSS源: {feed_name} ({feed_url})")
                feed = feedparser.parse(feed_url)

                if feed.bozo:
                    logger.warning(f"RSS解析警告 {feed_name}: {feed.bozo_exception}")

                for entry in feed.entries[:limit]:
                    # 解析发布时间
                    published_at = ""
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        published_at = time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            entry.published_parsed
                        )
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        published_at = time.strftime(
                            "%Y-%m-%d %H:%M:%S",
                            entry.updated_parsed
                        )

                    # 时间过滤
                    if start_date and published_at:
                        try:
                            pub_dt = datetime.strptime(published_at, "%Y-%m-%d %H:%M:%S")
                            if pub_dt < start_date:
                                continue
                        except:
                            pass

                    # 提取内容
                    content = ""
                    if hasattr(entry, 'summary'):
                        content = entry.summary
                    elif hasattr(entry, 'description'):
                        content = entry.description
                    elif hasattr(entry, 'content'):
                        content = entry.content[0].value if entry.content else ""

                    all_news.append({
                        "title": entry.get("title", ""),
                        "content": content,
                        "source": feed_name,
                        "published_at": published_at,
                        "url": entry.get("link", ""),
                        "provider": "rss",
                        "type": feed_type
                    })

                logger.info(f"✅ 从 {feed_name} 获取到 {len(feed.entries)} 条新闻")

            except Exception as e:
                logger.error(f"拉取RSS源失败 {feed_name}: {e}")
                continue

        # 去重（按标题+发布时间）
        seen = set()
        unique_news = []
        for item in all_news:
            key = (item.get('title', ''), item.get('published_at', ''))
            if key not in seen:
                seen.add(key)
                unique_news.append(item)

        # 按发布时间排序
        unique_news.sort(key=lambda x: x.get('published_at', ''), reverse=True)

        logger.info(f"📊 RSS聚合后共 {len(unique_news)} 条唯一新闻")
        return unique_news[:limit]

    def get_quote(self, symbol: str) -> Dict:
        """RSS不支持行情数据"""
        return {}

    def get_research_reports(self, symbol: str, limit: int = 5) -> List[Dict]:
        """RSS不支持研报数据"""
        return []

    def get_sentiment(self, symbol: str) -> Dict:
        """RSS不支持情绪数据"""
        return {}

    def get_fundamentals(self, symbol: str) -> Dict:
        """RSS不支持基本面数据"""
        return {}

    def health_check(self) -> bool:
        """
        健康检查

        Returns:
            True: 至少有一个RSS源可用
            False: 所有RSS源均不可用
        """
        if not self._feeds:
            logger.warning("未配置RSS源")
            return False

        for feed_config in self._feeds:
            feed_name = feed_config.get("name", "未知")
            feed_url = feed_config.get("url", "")

            if not feed_url:
                continue

            try:
                feed = feedparser.parse(feed_url)
                if feed.entries:
                    logger.info(f"✅ RSS源 {feed_name} 可用")
                    return True
            except Exception as e:
                logger.warning(f"RSS源 {feed_name} 不可用: {e}")
                continue

        logger.error("❌ 所有RSS源均不可用")
        return False
