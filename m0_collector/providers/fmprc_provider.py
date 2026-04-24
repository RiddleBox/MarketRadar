"""
外交部 Provider - 外交动态和国际合作数据源
支持: 外交访问、国际合作、双边关系
官网: https://www.fmprc.gov.cn/
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Optional
from m0_collector.providers.base import ProviderAdapter
from m0_collector.models import RawArticle


class FMPRCProvider(ProviderAdapter):
    """外交部新闻提供者"""

    def __init__(self):
        """初始化外交部提供者"""
        self.base_url = "https://www.fmprc.gov.cn"

        # 外交部新闻栏目
        self.channels = {
            "news": "/web/wjdt_674879/",  # 外交动态
            "spokesperson": "/web/fyrbt_673021/",  # 发言人表态
            "bilateral": "/web/gjhdq_676201/",  # 国家和地区
        }

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    @property
    def provider_id(self) -> str:
        return "fmprc"

    @property
    def display_name(self) -> str:
        return "外交部"

    def fetch(self,
              category: str = "news",
              limit: Optional[int] = None,
              **kwargs) -> List[RawArticle]:
        """
        获取外交部新闻

        Args:
            category: 新闻类别 (news, spokesperson, bilateral)
            limit: 限制返回数量

        Returns:
            新闻文章列表
        """
        channel_path = self.channels.get(category)
        if not channel_path:
            print(f"未知的类别: {category}")
            return []

        try:
            # 构建URL
            url = f"{self.base_url}{channel_path}"

            # 发送请求
            response = requests.get(url, headers=self.headers, timeout=10)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                print(f"请求失败: {response.status_code}")
                return []

            # 解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            articles = []

            # 外交部网站通常使用特定的列表结构
            news_items = soup.find_all('li', limit=limit or 20)

            for item in news_items:
                try:
                    # 提取标题和链接
                    link_tag = item.find('a')
                    if not link_tag:
                        continue

                    title = link_tag.get_text(strip=True)
                    href = link_tag.get('href', '')

                    # 过滤无效链接
                    if not href or href == '#':
                        continue

                    # 构建完整URL
                    if href.startswith('http'):
                        article_url = href
                    elif href.startswith('/'):
                        article_url = f"{self.base_url}{href}"
                    else:
                        article_url = f"{self.base_url}/{href}"

                    # 提取日期
                    date_text = ''
                    date_tag = item.find('span', class_='date') or item.find('span')
                    if date_tag:
                        date_text = date_tag.get_text(strip=True)

                    # 创建文章对象
                    article = RawArticle(
                        title=title,
                        content='',  # 列表页不包含正文
                        raw_published_at=date_text,
                        source_name="外交部",
                        source_url=article_url,
                        provider_id=self.provider_id,
                        language='zh'
                    )
                    articles.append(article)

                    if limit and len(articles) >= limit:
                        break

                except Exception as e:
                    print(f"解析新闻项失败: {e}")
                    continue

            return articles

        except requests.RequestException as e:
            print(f"外交部网站请求失败: {e}")
            return []
        except Exception as e:
            print(f"外交部数据获取失败: {e}")
            return []

    def fetch_article_content(self, url: str) -> str:
        """
        获取文章正文

        Args:
            url: 文章URL

        Returns:
            文章正文
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.encoding = 'utf-8'

            if response.status_code != 200:
                return ''

            soup = BeautifulSoup(response.text, 'html.parser')

            # 查找正文容器
            content_div = (
                soup.find('div', class_='content') or
                soup.find('div', id='News_Body_Txt') or
                soup.find('div', class_='article-content')
            )

            if content_div:
                paragraphs = content_div.find_all('p')
                content = '\n'.join(p.get_text(strip=True) for p in paragraphs)
                return content

            return ''

        except Exception as e:
            print(f"获取文章正文失败: {e}")
            return ''

    def fetch_diplomatic_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取外交动态"""
        return self.fetch(category="news", limit=limit)

    def fetch_spokesperson_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取发言人表态"""
        return self.fetch(category="spokesperson", limit=limit)

    def fetch_bilateral_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取双边关系新闻"""
        return self.fetch(category="bilateral", limit=limit)


# 便捷函数
def fetch_fmprc_news(category: str = "news", limit: int = 10) -> List[RawArticle]:
    """
    便捷函数：获取外交部新闻

    Args:
        category: 新闻类别 (news, spokesperson, bilateral)
        limit: 限制返回数量

    Returns:
        新闻文章列表
    """
    provider = FMPRCProvider()
    return provider.fetch(category=category, limit=limit)
