"""
数据提供者抽象接口

定义统一的数据获取接口，所有外部数据源（SKILL、AKShare、RSS等）
必须实现此接口，确保核心模块不依赖具体实现。
"""

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
            能力列表，可选值：
            - 'news': 新闻
            - 'quote': 实时行情
            - 'research': 研报
            - 'sentiment': 情绪指标
            - 'fundamentals': 基本面数据

        Example:
            ['news', 'quote', 'research']
        """
        pass

    @abstractmethod
    def get_news(self, symbol: str = None, limit: int = 10,
                 start_date: Optional[datetime] = None) -> List[Dict]:
        """
        获取新闻

        Args:
            symbol: 股票代码（如 '000001'），None表示获取宏观新闻
            limit: 返回数量
            start_date: 起始日期

        Returns:
            新闻列表，每条新闻包含：
            [
                {
                    "title": "新闻标题",
                    "content": "新闻内容",
                    "source": "来源",
                    "published_at": "2026-05-07 10:00:00",
                    "url": "https://...",
                    "provider": "astock_skill",  # 数据提供者标识
                    "type": "explicit"  # explicit=显式（个股新闻）, macro=宏观新闻
                }
            ]
        """
        pass

    @abstractmethod
    def get_quote(self, symbol: str) -> Dict:
        """
        获取实时行情

        Args:
            symbol: 股票代码

        Returns:
            行情数据：
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

            如果获取失败或不支持，返回空字典 {}
        """
        pass

    @abstractmethod
    def get_research_reports(self, symbol: str, limit: int = 5) -> List[Dict]:
        """
        获取研报

        Args:
            symbol: 股票代码
            limit: 返回数量

        Returns:
            研报列表：
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

        Args:
            symbol: 股票代码

        Returns:
            情绪数据：
            {
                "symbol": "000001.SZ",
                "sentiment_score": 0.75,  # 0-1之间
                "hot_rank": 10,  # 热度排名
                "provider": "astock_skill"
            }

            如果获取失败或不支持，返回空字典 {}
        """
        pass

    @abstractmethod
    def get_fundamentals(self, symbol: str) -> Dict:
        """
        获取基本面数据

        Args:
            symbol: 股票代码

        Returns:
            基本面数据：
            {
                "symbol": "000001.SZ",
                "revenue": 123456789.0,  # 营收
                "net_profit": 12345678.0,  # 净利润
                "eps": 1.23,  # 每股收益
                "roe": 12.34,  # 净资产收益率
                "debt_ratio": 0.45,  # 资产负债率
                "report_date": "2026-03-31",
                "provider": "astock_skill"
            }

            如果获取失败或不支持，返回空字典 {}
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        健康检查

        Returns:
            True: 数据源可用
            False: 数据源不可用
        """
        pass
