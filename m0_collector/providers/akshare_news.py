"""
m0_collector/providers/akshare_news.py — AKShare 新闻数据源

使用 AKShare 的 stock_news_em() 接口获取东方财富新闻。
作为 RSS 源的备用数据源。
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from m0_collector.providers.base import ProviderAdapter
from m0_collector.models import RawArticle

logger = logging.getLogger(__name__)


class AkshareNewsProvider(ProviderAdapter):
    """AKShare 新闻数据源 (东方财富)"""

    def __init__(self, symbol: str = "全部"):
        self.symbol = symbol

    @property
    def provider_id(self) -> str:
        return "akshare_news"

    @property
    def display_name(self) -> str:
        return "AKShare 新闻 (东方财富)"

    def fetch(self, limit: int = 20, **kwargs) -> List[RawArticle]:
        """
        获取新闻列表

        Args:
            limit: 最多返回条数

        Returns:
            List[RawArticle]
        """
        symbol = kwargs.get('symbol', self.symbol)

        try:
            import akshare as ak

            logger.info(f"[M0] AKShare 新闻采集: symbol={symbol}, limit={limit}")
            
            # 调用 AKShare API
            df = ak.stock_news_em(symbol=symbol)
            
            if df.empty:
                logger.warning(f"[M0] AKShare 返回空数据")
                return []
            
            # 限制条数
            df = df.head(limit)

            articles = []
            for _, row in df.iterrows():
                try:
                    # 提取字段
                    title = str(row.get("新闻标题", ""))
                    content = str(row.get("新闻内容", ""))
                    pub_time = row.get("发布时间", "")
                    source = str(row.get("文章来源", "东方财富"))
                    link = str(row.get("新闻链接", ""))

                    # 构造文章
                    article = RawArticle(
                        title=title,
                        content=content or title,
                        raw_published_at=str(pub_time) if pub_time else "",
                        source_name=source,
                        source_url=link or f"https://finance.eastmoney.com/",
                        provider_id=self.provider_id,
                        language="zh",
                    )

                    articles.append(article)
                    
                except Exception as e:
                    logger.warning(f"[M0] 解析新闻失败: {e}")
                    continue

            logger.info(f"[M0] AKShare 新闻采集成功: {len(articles)} 条")
            return articles
            
        except ImportError:
            logger.error("[M0] AKShare 未安装,请运行: pip install akshare")
            return []
        except Exception as e:
            logger.error(f"[M0] AKShare 新闻采集失败: {e}")
            return []

    def is_available(self) -> bool:
        """检查数据源是否可用"""
        try:
            import akshare as ak
            # 尝试获取1条数据测试
            df = ak.stock_news_em(symbol="全部")
            return not df.empty
        except:
            return False


# 便捷函数
def fetch_akshare_news(symbol: str = "全部", limit: int = 20) -> List[RawArticle]:
    """便捷函数: 获取 AKShare 新闻"""
    provider = AkshareNewsProvider(symbol=symbol)
    return provider.fetch(limit=limit)


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    provider = AkshareNewsProvider(symbol="全部")

    print(f"数据源可用: {provider.is_available()}")

    articles = provider.fetch(limit=5)

    print(f"\n获取到 {len(articles)} 条新闻:")
    for i, article in enumerate(articles, 1):
        print(f"\n{i}. {article.title}")
        print(f"   来源: {article.source_name}")
        print(f"   时间: {article.raw_published_at}")
        print(f"   内容: {article.content[:100]}...")
