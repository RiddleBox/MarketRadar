"""
M13 Data Manager Adapter
将DataProviderManager适配为M13 ResearchAgent期望的接口
"""

from typing import List, Dict, Optional
from datetime import datetime, timedelta
from integrations.data_provider_manager import get_global_data_manager
import logging

logger = logging.getLogger(__name__)


class M13DataManagerAdapter:
    """
    M13数据管理器适配器

    将DataProviderManager的接口适配为M13 ResearchAgent期望的接口
    """

    def __init__(self):
        self.provider_manager = get_global_data_manager()

    def get_research_reports(self, symbol: str, days: int = 30, limit: int = 10) -> List[Dict]:
        """
        获取研报（目前返回空，因为DataProvider还没实现研报接口）

        TODO: 等A-stock SKILL支持研报搜索后实现
        """
        logger.warning(f"[M13Adapter] get_research_reports not implemented yet, returning empty")
        return []

    def get_news(self, symbol: str = None, days: int = 30, limit: int = 20) -> List[Dict]:
        """
        获取新闻

        Args:
            symbol: 股票代码（None = 宏观新闻）
            days: 最近N天
            limit: 数量限制

        Returns:
            新闻列表
        """
        try:
            start_date = datetime.now() - timedelta(days=days)
            news = []

            # 如果指定了symbol，先尝试获取个股新闻（但不阻塞）
            if symbol:
                try:
                    news = self.provider_manager.get_news(
                        symbol=symbol,
                        limit=limit,
                        start_date=start_date,
                        aggregate=True
                    )
                    logger.info(f"[M13Adapter] 获取个股新闻: {symbol} - {len(news)}条")
                except Exception as e:
                    logger.warning(f"[M13Adapter] 个股新闻获取失败: {symbol} - {e}")
                    news = []

            # 如果个股新闻不足或没有symbol，补充宏观新闻
            if len(news) < limit // 2:
                try:
                    macro_news = self.provider_manager.get_news(
                        symbol=None,  # 宏观新闻
                        limit=limit,
                        start_date=start_date,
                        aggregate=True
                    )
                    logger.info(f"[M13Adapter] 补充宏观新闻: {len(macro_news)}条")
                    news.extend(macro_news)
                except Exception as e:
                    logger.warning(f"[M13Adapter] 宏观新闻获取失败: {e}")

            # 去重并限制数量
            if news:
                seen = set()
                unique_news = []
                for item in news:
                    key = (item.get('title', ''), item.get('published_at', ''))
                    if key not in seen:
                        seen.add(key)
                        unique_news.append(item)
                news = unique_news[:limit]

            logger.info(f"[M13Adapter] 最终返回新闻: {len(news)}条")
            return news
        except Exception as e:
            logger.error(f"[M13Adapter] 获取新闻失败: {e}")
            return []

    def get_fundamentals(self, symbol: str) -> Dict:
        """
        获取基本面数据（目前返回空，因为DataProvider还没实现）

        TODO: 等数据源支持后实现
        """
        logger.warning(f"[M13Adapter] get_fundamentals not implemented yet, returning empty")
        return {}

    def get_quote(self, symbol: str) -> Dict:
        """
        获取实时行情（目前返回空，因为DataProvider还没实现）

        TODO: 等数据源支持后实现
        """
        logger.warning(f"[M13Adapter] get_quote not implemented yet, returning empty")
        return {}

    def semantic_search(self, query: str, limit: int = 5) -> List[Dict]:
        """
        语义搜索（目前返回空，因为DataProvider还没实现）

        TODO: 等向量数据库集成后实现
        """
        logger.warning(f"[M13Adapter] semantic_search not implemented yet, returning empty")
        return []


def get_m13_data_manager():
    """获取M13数据管理器适配器实例"""
    return M13DataManagerAdapter()
