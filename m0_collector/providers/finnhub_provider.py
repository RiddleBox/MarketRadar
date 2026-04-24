"""
Finnhub Provider - 全球股市新闻数据源
支持: 美股、港股、A股等全球市场
免费额度: 60次/分钟
官网: https://finnhub.io/
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional
import requests
from m0_collector.providers.base import ProviderAdapter
from m0_collector.models import RawArticle


class FinnhubProvider(ProviderAdapter):
    """Finnhub新闻提供者"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化Finnhub提供者

        Args:
            api_key: Finnhub API密钥，如果不提供则从环境变量FINNHUB_API_KEY读取
        """
        self.api_key = api_key or os.getenv('FINNHUB_API_KEY')
        if not self.api_key:
            raise ValueError("需要提供Finnhub API密钥，请设置环境变量FINNHUB_API_KEY或传入api_key参数")

        self.base_url = "https://finnhub.io/api/v1"
        self.session = requests.Session()

    @property
    def provider_id(self) -> str:
        return "finnhub"

    @property
    def display_name(self) -> str:
        return "Finnhub"

    def fetch(self,
              category: str = "general",
              min_id: int = 0,
              limit: Optional[int] = None,
              **kwargs) -> List[RawArticle]:
        """
        获取市场新闻

        Args:
            category: 新闻类别 (general, forex, crypto, merger)
            min_id: 最小新闻ID（用于分页）
            limit: 限制返回数量

        Returns:
            新闻文章列表
        """
        params = {
            'category': category,
            'token': self.api_key
        }
        if min_id > 0:
            params['minId'] = min_id

        try:
            response = self.session.get(
                f"{self.base_url}/news",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            articles = []
            for item in data:
                # 解析Unix时间戳转为ISO字符串
                pub_date_str = ''
                if item.get('datetime'):
                    try:
                        pub_date = datetime.fromtimestamp(item['datetime'])
                        pub_date_str = pub_date.isoformat()
                    except:
                        pass

                article = RawArticle(
                    title=item.get('headline', ''),
                    content=item.get('summary', ''),
                    raw_published_at=pub_date_str,
                    source_name=item.get('source', 'Unknown'),
                    source_url=item.get('url', ''),
                    provider_id=self.provider_id,
                    language='en'
                )
                articles.append(article)

                # 应用limit限制
                if limit and len(articles) >= limit:
                    break

            return articles

        except requests.exceptions.RequestException as e:
            print(f"Finnhub请求失败: {e}")
            return []

    def fetch_company_news(self,
                          symbol: str,
                          from_date: Optional[datetime] = None,
                          to_date: Optional[datetime] = None,
                          limit: Optional[int] = None) -> List[RawArticle]:
        """
        获取特定公司的新闻

        Args:
            symbol: 股票代码（如 AAPL, 0700.HK）
            from_date: 开始日期
            to_date: 结束日期
            limit: 限制返回数量

        Returns:
            新闻文章列表
        """
        # 默认获取最近7天的新闻
        if not from_date:
            from_date = datetime.now() - timedelta(days=7)
        if not to_date:
            to_date = datetime.now()

        params = {
            'symbol': symbol,
            'from': from_date.strftime('%Y-%m-%d'),
            'to': to_date.strftime('%Y-%m-%d'),
            'token': self.api_key
        }

        try:
            response = self.session.get(
                f"{self.base_url}/company-news",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            articles = []
            for item in data:
                # 解析Unix时间戳转为ISO字符串
                pub_date_str = ''
                if item.get('datetime'):
                    try:
                        pub_date = datetime.fromtimestamp(item['datetime'])
                        pub_date_str = pub_date.isoformat()
                    except:
                        pass

                article = RawArticle(
                    title=item.get('headline', ''),
                    content=item.get('summary', ''),
                    raw_published_at=pub_date_str,
                    source_name=item.get('source', 'Unknown'),
                    source_url=item.get('url', ''),
                    provider_id=self.provider_id,
                    language='en'
                )
                articles.append(article)

                # 应用limit限制
                if limit and len(articles) >= limit:
                    break

            return articles

        except requests.exceptions.RequestException as e:
            print(f"Finnhub请求失败: {e}")
            return []

    def fetch_market_news(self, category: str = "general", limit: Optional[int] = None) -> List[RawArticle]:
        """获取市场新闻（通用）"""
        return self.fetch(category=category, limit=limit)

    def fetch_us_stock_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取美股市场新闻"""
        return self.fetch(category="general", limit=limit)

    def fetch_forex_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取外汇新闻"""
        return self.fetch(category="forex", limit=limit)

    def fetch_crypto_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取加密货币新闻"""
        return self.fetch(category="crypto", limit=limit)

    def fetch_merger_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取并购新闻"""
        return self.fetch(category="merger", limit=limit)
