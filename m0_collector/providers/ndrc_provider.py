"""
发改委 Provider - 产业政策和投资方向数据源
支持: 产业政策、投资导向、规划文件
官网: https://www.ndrc.gov.cn/
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Optional
from m0_collector.providers.base import ProviderAdapter
from m0_collector.models import RawArticle


class NDRCProvider(ProviderAdapter):
    """发改委新闻提供者"""

    def __init__(self):
        """初始化发改委提供者"""
        self.base_url = "https://www.ndrc.gov.cn"

        # 发改委新闻栏目
        self.channels = {
            "policy": "/fggz/",  # 发改工作
            "planning": "/fggz/fggh/",  # 发改规划
            "investment": "/fggz/tzgg/",  # 投资管理
            "industry": "/fggz/cyfz/",  # 产业发展
        }

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    @property
    def provider_id(self) -> str:
        return "ndrc"

    @property
    def display_name(self) -> str:
        return "国家发改委"

    def fetch(self,
              category: str = "policy",
              limit: Optional[int] = None,
              **kwargs) -> List[RawArticle]:
        """
        获取发改委新闻

        Args:
            category: 新闻类别 (policy, planning, investment, industry)
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

            # 查找新闻列表（根据发改委网站结构）
            articles = []

            # 发改委网站通常使用<ul class="list_01">或类似结构
            news_list = soup.find_all('li', limit=limit or 20)

            for item in news_list:
                try:
                    # 提取标题和链接
                    link_tag = item.find('a')
                    if not link_tag:
                        continue

                    title = link_tag.get_text(strip=True)
                    href = link_tag.get('href', '')

                    # 构建完整URL
                    if href.startswith('http'):
                        article_url = href
                    elif href.startswith('/'):
                        article_url = f"{self.base_url}{href}"
                    else:
                        article_url = f"{self.base_url}/{href}"

                    # 提取日期
                    date_tag = item.find('span', class_='date') or item.find('span')
                    pub_date_str = date_tag.get_text(strip=True) if date_tag else ''

                    # 创建文章对象（不获取正文，避免过多请求）
                    article = RawArticle(
                        title=title,
                        content='',  # 列表页不包含正文
                        raw_published_at=pub_date_str,
                        source_name="国家发改委",
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
            print(f"发改委网站请求失败: {e}")
            return []
        except Exception as e:
            print(f"发改委数据获取失败: {e}")
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

            # 查找正文容器（根据发改委网站结构）
            content_div = (
                soup.find('div', class_='TRS_Editor') or
                soup.find('div', id='content') or
                soup.find('div', class_='content')
            )

            if content_div:
                # 提取文本，去除HTML标签
                paragraphs = content_div.find_all('p')
                content = '\n'.join(p.get_text(strip=True) for p in paragraphs)
                return content

            return ''

        except Exception as e:
            print(f"获取文章正文失败: {e}")
            return ''

    def fetch_policy_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取政策新闻"""
        return self.fetch(category="policy", limit=limit)

    def fetch_planning_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取规划新闻"""
        return self.fetch(category="planning", limit=limit)

    def fetch_investment_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取投资新闻"""
        return self.fetch(category="investment", limit=limit)

    def fetch_industry_news(self, limit: Optional[int] = None) -> List[RawArticle]:
        """获取产业新闻"""
        return self.fetch(category="industry", limit=limit)


# 便捷函数
def fetch_ndrc_news(category: str = "policy", limit: int = 10) -> List[RawArticle]:
    """
    便捷函数：获取发改委新闻

    Args:
        category: 新闻类别 (policy, planning, investment, industry)
        limit: 限制返回数量

    Returns:
        新闻文章列表
    """
    provider = NDRCProvider()
    return provider.fetch(category=category, limit=limit)
