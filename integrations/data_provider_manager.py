"""
数据提供者管理器

负责注册、管理多个数据提供者，支持：
- 多源聚合（合并多个数据源的结果）
- 自动降级（某个源失败时切换到备用源）
- 优先级管理（按优先级选择数据源）
- 健康检查（监控各数据源状态）
"""

from typing import List, Dict, Optional
from integrations.data_provider_interface import DataProvider
from datetime import datetime
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
                 aggregate: bool = True,
                 start_date: Optional[datetime] = None) -> List[Dict]:
        """
        获取新闻（支持多源聚合）

        Args:
            symbol: 股票代码（None = 获取宏观新闻）
            limit: 数量限制
            providers: 指定提供者列表（None = 使用所有可用提供者）
            aggregate: 是否聚合多源（True = 合并去重，False = 只用第一个成功的）
            start_date: 起始日期

        Returns:
            新闻列表，按发布时间倒序排列
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
                        news = provider.get_news(symbol, limit, start_date)
                        if news:
                            logger.info(f"✅ 从 {provider_name} 获取到 {len(news)} 条新闻")
                            return news
                    except Exception as e:
                        logger.warning(f"Provider {provider_name} failed, trying next: {e}")
                        continue
            logger.warning(f"所有新闻提供者均失败")
            return []

        # 聚合模式：从多个提供者获取新闻
        for provider_name in providers:
            provider = self._providers.get(provider_name)
            if provider and 'news' in provider.get_capabilities():
                try:
                    news = provider.get_news(symbol, limit, start_date)
                    if news:
                        logger.info(f"✅ 从 {provider_name} 获取到 {len(news)} 条新闻")
                        all_news.extend(news)
                except Exception as e:
                    logger.warning(f"Provider {provider_name} failed: {e}")
                    continue

        if not all_news:
            logger.warning(f"所有新闻提供者均未返回数据")
            return []

        # 去重 + 排序
        seen = set()
        unique_news = []
        for item in all_news:
            key = (item.get('title', ''), item.get('published_at', ''))
            if key not in seen:
                seen.add(key)
                unique_news.append(item)

        unique_news.sort(key=lambda x: x.get('published_at', ''), reverse=True)
        logger.info(f"📊 聚合后共 {len(unique_news)} 条唯一新闻")
        return unique_news[:limit]

    def get_quote(self, symbol: str, provider: Optional[str] = None) -> Dict:
        """
        获取行情（支持降级）

        Args:
            symbol: 股票代码
            provider: 指定提供者（None = 按优先级尝试）

        Returns:
            行情数据，失败返回空字典
        """
        if provider:
            # 使用指定提供者
            p = self._providers.get(provider)
            if p and 'quote' in p.get_capabilities():
                try:
                    result = p.get_quote(symbol)
                    if result:
                        logger.info(f"✅ 从 {provider} 获取到 {symbol} 行情")
                        return result
                except Exception as e:
                    logger.error(f"Provider {provider} get_quote failed: {e}")

        # 按优先级降级尝试
        for _, provider_name in self._priority.get('quote', []):
            provider = self._providers.get(provider_name)
            if provider and 'quote' in provider.get_capabilities():
                try:
                    result = provider.get_quote(symbol)
                    if result:
                        logger.info(f"✅ 从 {provider_name} 获取到 {symbol} 行情")
                        return result
                except Exception as e:
                    logger.warning(f"Provider {provider_name} failed, trying next: {e}")
                    continue

        logger.error(f"❌ 所有行情提供者均失败: {symbol}")
        return {}

    def get_research_reports(self, symbol: str, limit: int = 5,
                             provider: Optional[str] = None) -> List[Dict]:
        """
        获取研报（支持降级）

        Args:
            symbol: 股票代码
            limit: 数量限制
            provider: 指定提供者（None = 按优先级尝试）

        Returns:
            研报列表
        """
        if provider:
            p = self._providers.get(provider)
            if p and 'research' in p.get_capabilities():
                try:
                    result = p.get_research_reports(symbol, limit)
                    if result:
                        logger.info(f"✅ 从 {provider} 获取到 {len(result)} 条研报")
                        return result
                except Exception as e:
                    logger.error(f"Provider {provider} get_research_reports failed: {e}")

        for _, provider_name in self._priority.get('research', []):
            provider = self._providers.get(provider_name)
            if provider and 'research' in provider.get_capabilities():
                try:
                    result = provider.get_research_reports(symbol, limit)
                    if result:
                        logger.info(f"✅ 从 {provider_name} 获取到 {len(result)} 条研报")
                        return result
                except Exception as e:
                    logger.warning(f"Provider {provider_name} failed, trying next: {e}")
                    continue

        logger.warning(f"所有研报提供者均失败: {symbol}")
        return []

    def get_sentiment(self, symbol: str, provider: Optional[str] = None) -> Dict:
        """
        获取情绪指标（支持降级）

        Args:
            symbol: 股票代码
            provider: 指定提供者（None = 按优先级尝试）

        Returns:
            情绪数据，失败返回空字典
        """
        if provider:
            p = self._providers.get(provider)
            if p and 'sentiment' in p.get_capabilities():
                try:
                    result = p.get_sentiment(symbol)
                    if result:
                        logger.info(f"✅ 从 {provider} 获取到 {symbol} 情绪数据")
                        return result
                except Exception as e:
                    logger.error(f"Provider {provider} get_sentiment failed: {e}")

        for _, provider_name in self._priority.get('sentiment', []):
            provider = self._providers.get(provider_name)
            if provider and 'sentiment' in provider.get_capabilities():
                try:
                    result = provider.get_sentiment(symbol)
                    if result:
                        logger.info(f"✅ 从 {provider_name} 获取到 {symbol} 情绪数据")
                        return result
                except Exception as e:
                    logger.warning(f"Provider {provider_name} failed, trying next: {e}")
                    continue

        logger.warning(f"所有情绪提供者均失败: {symbol}")
        return {}

    def get_fundamentals(self, symbol: str, provider: Optional[str] = None) -> Dict:
        """
        获取基本面（支持降级）

        Args:
            symbol: 股票代码
            provider: 指定提供者（None = 按优先级尝试）

        Returns:
            基本面数据，失败返回空字典
        """
        if provider:
            p = self._providers.get(provider)
            if p and 'fundamentals' in p.get_capabilities():
                try:
                    result = p.get_fundamentals(symbol)
                    if result:
                        logger.info(f"✅ 从 {provider} 获取到 {symbol} 基本面数据")
                        return result
                except Exception as e:
                    logger.error(f"Provider {provider} get_fundamentals failed: {e}")

        for _, provider_name in self._priority.get('fundamentals', []):
            provider = self._providers.get(provider_name)
            if provider and 'fundamentals' in provider.get_capabilities():
                try:
                    result = provider.get_fundamentals(symbol)
                    if result:
                        logger.info(f"✅ 从 {provider_name} 获取到 {symbol} 基本面数据")
                        return result
                except Exception as e:
                    logger.warning(f"Provider {provider_name} failed, trying next: {e}")
                    continue

        logger.warning(f"所有基本面提供者均失败: {symbol}")
        return {}

    def health_check(self) -> Dict[str, bool]:
        """
        检查所有提供者健康状态

        Returns:
            {
                'astock_skill': True,
                'rss': False,
                ...
            }
        """
        result = {}
        for name, provider in self._providers.items():
            try:
                is_healthy = provider.health_check()
                result[name] = is_healthy
                status = "✅" if is_healthy else "❌"
                logger.info(f"{status} {name}: {'正常' if is_healthy else '异常'}")
            except Exception as e:
                result[name] = False
                logger.error(f"❌ {name} 健康检查失败: {e}")

        return result

    def list_capabilities(self) -> Dict[str, List[str]]:
        """
        列出所有能力及其提供者

        Returns:
            {
                'news': ['astock_skill', 'rss'],
                'quote': ['astock_skill'],
                ...
            }
        """
        result = {}
        for capability, providers in self._priority.items():
            result[capability] = [name for _, name in providers]
        return result

    def get_provider_info(self) -> Dict[str, Dict]:
        """
        获取所有提供者的详细信息

        Returns:
            {
                'astock_skill': {
                    'capabilities': ['news', 'quote', 'research', 'fundamentals'],
                    'priority': {'news': 100, 'quote': 100, ...},
                    'healthy': True
                },
                ...
            }
        """
        result = {}
        for name, provider in self._providers.items():
            capabilities = provider.get_capabilities()
            priority_map = {}
            for cap in capabilities:
                for pri, pname in self._priority.get(cap, []):
                    if pname == name:
                        priority_map[cap] = pri
                        break

            result[name] = {
                'capabilities': capabilities,
                'priority': priority_map,
                'healthy': provider.health_check()
            }

        return result


# 全局单例
_global_manager = None


def get_global_data_manager() -> DataProviderManager:
    """获取全局数据管理器（单例模式）"""
    global _global_manager
    if _global_manager is None:
        _global_manager = DataProviderManager()
    return _global_manager
