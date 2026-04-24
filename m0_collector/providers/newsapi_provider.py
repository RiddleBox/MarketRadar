"""
NewsAPI Provider - 港股/美股新闻数据源
支持: 美股、港股、全球市场新闻
免费额度: 100次/天
官网: https://newsapi.org/
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional
import requests
from m0_collector.providers.base import ProviderAdapter
from m0_collector.models import RawArticle


class NewsAPIProvider(ProviderAdapter):
    """NewsAPI新闻提供者"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化NewsAPI提供者

        Args:
            api_key: NewsAPI密钥，如果不提供则从环境变量NEWSAPI_KEY读取
        """
        self.api_key = api_key or os.getenv('NEWSAPI_KEY')
        if not self.api_key:
            raise ValueError("需要提供NewsAPI密钥，请设置环境变量NEWSAPI_KEY或传入api_key参数")

        self.base_url = "https://newsapi.org/v2"
        self.session = requests.Session()
        self.session.headers.update({
            'X-Api-Key': self.api_key,
            'User-Agent': 'MarketRadar/1.0'
        })

    @property
    def provider_id(self) -> str:
        return "newsapi"

    @property
    def display_name(self) -> str:
        return "NewsAPI"

    def fetch(self,
              query: str = "stock OR market OR trading",
              language: str = "en",
              from_date: Optional[datetime] = None,
              to_date: Optional[datetime] = None,
              page_size: int = 20) -> List[RawArticle]:
        """
        获取新闻数据

        Args:
            query: 搜索关键词（支持AND/OR/NOT逻辑）
            language: 语言代码（en/zh）
            from_date: 开始日期
            to_date: 结束日期
            page_size: 每页数量（最大100）

        Returns:
            新闻文章列表
        """
        # 默认获取最近24小时的新闻
        if not from_date:
            from_date = datetime.now() - timedelta(days=1)
        if not to_date:
            to_date = datetime.now()

        params = {
            'q': query,
            'language': language,
            'from': from_date.strftime('%Y-%m-%d'),
            'to': to_date.strftime('%Y-%m-%d'),
            'sortBy': 'publishedAt',
            'pageSize': min(page_size, 100)
        }

        try:
            response = self.session.get(
                f"{self.base_url}/everything",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if data.get('status') != 'ok':
                print(f"NewsAPI返回错误: {data.get('message', 'Unknown error')}")
                return []

            articles = []
            for item in data.get('articles', []):
                # 跳过被删除的文章
                if item.get('title') == '[Removed]':
                    continue

                # 解析发布时间
                pub_date = None
                if item.get('publishedAt'):
                    try:
                        pub_date = datetime.fromisoformat(
                            item['publishedAt'].replace('Z', '+00:00')
                        )
                    except:
                        pass

                # 组合标题和描述作为内容
                content = item.get('title', '')
                if item.get('description'):
                    content += '\n\n' + item['description']
                if item.get('content'):
                    # NewsAPI的content字段通常被截断，但仍然有用
                    content += '\n\n' + item['content']

                article = RawArticle(
                    title=item.get('title', ''),
                    content=content,
                    raw_published_at=item.get('publishedAt', ''),
                    source_name=item.get('source', {}).get('name', 'Unknown'),
                    source_url=item.get('url', ''),
                    provider_id=self.provider_id,
                    language=language
                )
                articles.append(article)

            return articles

        except requests.exceptions.RequestException as e:
            print(f"NewsAPI请求失败: {e}")
            return []

    def fetch_us_stock_news(self, page_size: int = 20) -> List[RawArticle]:
        """获取美股新闻"""
        query = '(stock OR market OR trading OR NYSE OR NASDAQ) AND (USA OR US OR America)'
        return self.fetch(query=query, language='en', page_size=page_size)

    def fetch_hk_stock_news(self, page_size: int = 20) -> List[RawArticle]:
        """获取港股新闻"""
        query = '(stock OR market OR trading OR HKEX) AND (Hong Kong OR HK)'
        return self.fetch(query=query, language='en', page_size=page_size)

    def fetch_china_stock_news(self, page_size: int = 20) -> List[RawArticle]:
        """获取中国股市新闻（英文）"""
        query = '(stock OR market OR trading OR Shanghai OR Shenzhen) AND China'
        return self.fetch(query=query, language='en', page_size=page_size)


def fetch_newsapi_articles(market: str = "us", api_key: Optional[str] = None, page_size: int = 20) -> List[RawArticle]:
    """
    便捷函数：获取指定市场的新闻

    Args:
        market: 市场类型 ("us", "hk", "cn")
        api_key: API密钥
        page_size: 数量

    Returns:
        新闻列表
    """
    provider = NewsAPIProvider(api_key=api_key)

    if market.lower() == "us":
        return provider.fetch_us_stock_news(page_size=page_size)
    elif market.lower() == "hk":
        return provider.fetch_hk_stock_news(page_size=page_size)
    elif market.lower() == "cn":
        return provider.fetch_china_stock_news(page_size=page_size)
    else:
        raise ValueError(f"不支持的市场类型: {market}，请使用 'us', 'hk', 或 'cn'")


if __name__ == "__main__":
    # 测试代码
    print("测试NewsAPI Provider...")

    # 需要设置环境变量 NEWSAPI_KEY
    # 或者直接传入: provider = NewsAPIProvider(api_key="your_key_here")

    try:
        # 测试美股新闻
        print("\n=== 美股新闻 ===")
        us_articles = fetch_newsapi_articles(market="us", page_size=5)
        print(f"获取到 {len(us_articles)} 篇美股新闻")
        for i, article in enumerate(us_articles[:3], 1):
            print(f"\n{i}. {article.title}")
            print(f"   来源: {article.source}")
            print(f"   时间: {article.published_at}")
            print(f"   链接: {article.url}")

        # 测试港股新闻
        print("\n=== 港股新闻 ===")
        hk_articles = fetch_newsapi_articles(market="hk", page_size=5)
        print(f"获取到 {len(hk_articles)} 篇港股新闻")
        for i, article in enumerate(hk_articles[:3], 1):
            print(f"\n{i}. {article.title}")
            print(f"   来源: {article.source}")
            print(f"   时间: {article.published_at}")

    except ValueError as e:
        print(f"\n错误: {e}")
        print("请设置环境变量: set NEWSAPI_KEY=your_api_key_here")
