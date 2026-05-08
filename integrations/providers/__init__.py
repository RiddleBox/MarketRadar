"""
Data Providers Package

包含所有数据提供者的实现：
- AStockSkillProvider: A-stock data SKILL（行情+新闻+研报+基本面）
- RSSProvider: RSS新闻源（宏观新闻）
"""

from integrations.providers.astock_skill_provider import AStockSkillProvider
from integrations.providers.rss_provider import RSSProvider

__all__ = ['AStockSkillProvider', 'RSSProvider']
