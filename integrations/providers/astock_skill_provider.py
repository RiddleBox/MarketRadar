"""
A-stock data SKILL Provider

基于 A-stock data SKILL 的数据提供者实现，提供：
- 新闻：akshare 个股新闻 + 财联社快讯 + 东财全球资讯
- 行情：腾讯财经 API（实时PE/PB/市值）
- 研报：东财研报 API
- 情绪：暂不支持（返回空字典）
- 基本面：mootdx 财务快照 + akshare 个股信息

数据源优先级（按SKILL文档）：
1. mootdx (TCP) - K线+财务快照+F10
2. 腾讯财经 (HTTP) - 实时PE/PB/市值
3. akshare (Python) - 研报+新闻+公告
"""

from typing import List, Dict, Optional
from datetime import datetime
from integrations.data_provider_interface import DataProvider
import logging
import urllib.request
import time

logger = logging.getLogger(__name__)


class AStockSkillProvider(DataProvider):
    """A-stock data SKILL 数据提供者"""

    def __init__(self):
        self._capabilities = ['news', 'quote', 'research', 'fundamentals']
        self._check_dependencies()

    def _check_dependencies(self):
        """检查依赖项是否可用"""
        try:
            import akshare
            self._akshare_available = True
        except ImportError:
            logger.warning("akshare 不可用，新闻和研报功能将受限")
            self._akshare_available = False

        try:
            from mootdx.quotes import Quotes
            self._mootdx_available = True
        except ImportError:
            logger.warning("mootdx 不可用，基本面功能将受限")
            self._mootdx_available = False

    def get_capabilities(self) -> List[str]:
        """返回支持的能力列表"""
        return self._capabilities

    def get_news(self, symbol: str = None, limit: int = 10,
                 start_date: Optional[datetime] = None) -> List[Dict]:
        """
        获取新闻

        Args:
            symbol: 股票代码（如 '000001'），None表示获取宏观新闻
            limit: 返回数量
            start_date: 起始日期（暂不支持过滤）

        Returns:
            新闻列表
        """
        if not self._akshare_available:
            logger.error("akshare 不可用，无法获取新闻")
            return []

        try:
            import akshare as ak
            import pandas as pd

            all_news = []

            if symbol:
                # 个股新闻（显式信号）
                try:
                    # Python 3.14兼容性：akshare的正则表达式bug workaround
                    # 临时禁用pandas的pyarrow引擎
                    import pandas as pd
                    original_engine = pd.options.mode.string_storage
                    try:
                        pd.options.mode.string_storage = "python"
                        df = ak.stock_news_em(symbol=symbol)
                    finally:
                        pd.options.mode.string_storage = original_engine

                    if not df.empty:
                        for _, row in df.head(limit).iterrows():
                            all_news.append({
                                "title": row.get("新闻标题", ""),
                                "content": row.get("新闻内容", ""),
                                "source": row.get("文章来源", "东方财富"),
                                "published_at": str(row.get("发布时间", "")),
                                "url": row.get("新闻链接", ""),
                                "provider": "astock_skill",
                                "type": "explicit"
                            })
                        logger.info(f"✅ 获取到 {len(all_news)} 条个股新闻: {symbol}")
                except Exception as e:
                    logger.warning(f"获取个股新闻失败 {symbol}: {e}")

            else:
                # 宏观新闻（隐式推理信号）
                # 1. 财联社快讯
                try:
                    df_cls = ak.stock_info_global_cls()
                    if not df_cls.empty:
                        for _, row in df_cls.head(limit // 2).iterrows():
                            all_news.append({
                                "title": row.get("标题", ""),
                                "content": row.get("内容", ""),
                                "source": "财联社",
                                "published_at": str(row.get("发布时间", "")),
                                "url": "",
                                "provider": "astock_skill",
                                "type": "macro"
                            })
                    logger.info(f"✅ 获取到 {len(all_news)} 条财联社快讯")
                except Exception as e:
                    logger.warning(f"获取财联社快讯失败: {e}")

                # 2. 东财全球资讯
                try:
                    df_em = ak.stock_info_global_em()
                    if not df_em.empty:
                        for _, row in df_em.head(limit // 2).iterrows():
                            all_news.append({
                                "title": row.get("标题", ""),
                                "content": row.get("摘要", ""),
                                "source": "东方财富",
                                "published_at": str(row.get("发布时间", "")),
                                "url": row.get("链接", ""),
                                "provider": "astock_skill",
                                "type": "macro"
                            })
                    logger.info(f"✅ 获取到 {len(all_news)} 条东财全球资讯")
                except Exception as e:
                    logger.warning(f"获取东财全球资讯失败: {e}")

            # 按发布时间排序
            all_news.sort(key=lambda x: x.get('published_at', ''), reverse=True)
            return all_news[:limit]

        except Exception as e:
            logger.error(f"获取新闻失败: {e}")
            return []

    def get_quote(self, symbol: str) -> Dict:
        """
        获取实时行情（腾讯财经 API）

        Args:
            symbol: 股票代码（6位）

        Returns:
            行情数据
        """
        try:
            # 市场前缀判断
            if symbol.startswith(("6", "9")):
                prefix = "sh"
            elif symbol.startswith("8"):
                prefix = "bj"
            else:
                prefix = "sz"

            # 腾讯财经 API
            url = f"https://qt.gtimg.cn/q={prefix}{symbol}"
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            resp = urllib.request.urlopen(req, timeout=10)
            data = resp.read().decode("gbk")

            # 解析数据
            vals = data.split('"')[1].split("~")
            if len(vals) < 50:
                logger.error(f"腾讯API返回数据不完整: {symbol}")
                return {}

            result = {
                "symbol": f"{symbol}.{prefix.upper()}",
                "name": vals[1],
                "price": float(vals[3]) if vals[3] else 0.0,
                "change_pct": float(vals[32]) if vals[32] else 0.0,
                "volume": int(float(vals[36]) * 100) if vals[36] else 0,  # 手转股
                "turnover": float(vals[37]) * 10000 if vals[37] else 0.0,  # 万元转元
                "turnover_rate": float(vals[38]) if vals[38] else 0.0,
                "pe_ttm": float(vals[39]) if vals[39] else 0.0,
                "pb": float(vals[46]) if vals[46] else 0.0,
                "market_cap": float(vals[44]) * 100000000 if vals[44] else 0.0,  # 亿转元
                "circulating_cap": float(vals[45]) * 100000000 if vals[45] else 0.0,
                "high": float(vals[33]) if vals[33] else 0.0,
                "low": float(vals[34]) if vals[34] else 0.0,
                "open": float(vals[5]) if vals[5] else 0.0,
                "close_prev": float(vals[4]) if vals[4] else 0.0,
                "provider": "astock_skill"
            }

            logger.info(f"✅ 获取到 {symbol} 行情: 价格={result['price']}, PE={result['pe_ttm']}, PB={result['pb']}")
            return result

        except Exception as e:
            logger.error(f"获取行情失败 {symbol}: {e}")
            return {}

    def get_research_reports(self, symbol: str, limit: int = 5) -> List[Dict]:
        """
        获取研报（东财研报 API）

        Args:
            symbol: 股票代码
            limit: 返回数量

        Returns:
            研报列表
        """
        if not self._akshare_available:
            logger.error("akshare 不可用，无法获取研报")
            return []

        try:
            import requests

            REPORT_API = "https://reportapi.eastmoney.com/report/list"
            UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

            session = requests.Session()
            session.headers.update({
                "User-Agent": UA,
                "Referer": "https://data.eastmoney.com/"
            })

            all_reports = []
            max_pages = (limit // 100) + 1

            for page in range(1, max_pages + 1):
                params = {
                    "industryCode": "*", "pageSize": "100", "industry": "*",
                    "rating": "*", "ratingChange": "*",
                    "beginTime": "2000-01-01", "endTime": "2030-01-01",
                    "pageNo": str(page), "fields": "", "qType": "0",
                    "orgCode": "", "code": symbol, "rcode": "",
                    "p": str(page), "pageNum": str(page), "pageNumber": str(page),
                }

                r = session.get(REPORT_API, params=params, timeout=30)
                d = r.json()
                rows = d.get("data") or []

                if not rows:
                    break

                for row in rows:
                    all_reports.append({
                        "title": row.get("title", ""),
                        "institution": row.get("orgSName", ""),
                        "rating": row.get("emRatingName", ""),
                        "published_at": (row.get("publishDate", "") or "")[:10],
                        "industry": row.get("indvInduName", ""),
                        "eps_cur": row.get("predictThisYearEps"),
                        "eps_next": row.get("predictNextYearEps"),
                        "info_code": row.get("infoCode", ""),
                        "provider": "astock_skill"
                    })

                if len(all_reports) >= limit:
                    break

                if page >= (d.get("TotalPage", 1) or 1):
                    break

                time.sleep(0.3)

            logger.info(f"✅ 获取到 {len(all_reports)} 条研报: {symbol}")
            return all_reports[:limit]

        except Exception as e:
            logger.error(f"获取研报失败 {symbol}: {e}")
            return []

    def get_sentiment(self, symbol: str) -> Dict:
        """
        获取情绪指标（暂不支持）

        Args:
            symbol: 股票代码

        Returns:
            空字典（SKILL未提供情绪数据）
        """
        logger.warning(f"A-stock SKILL 暂不支持情绪指标: {symbol}")
        return {}

    def get_fundamentals(self, symbol: str) -> Dict:
        """
        获取基本面数据（mootdx + akshare）

        Args:
            symbol: 股票代码

        Returns:
            基本面数据
        """
        result = {
            "symbol": symbol,
            "provider": "astock_skill"
        }

        # 1. mootdx 财务快照
        if self._mootdx_available:
            try:
                from mootdx.quotes import Quotes
                client = Quotes.factory(market='std')
                fin = client.finance(symbol=symbol)

                if fin:
                    result.update({
                        "eps": fin.get("eps"),
                        "bvps": fin.get("bvps"),
                        "roe": fin.get("roe"),
                        "net_profit": fin.get("profit"),
                        "revenue": fin.get("income"),
                        "total_shares": fin.get("zongguben"),
                        "circulating_shares": fin.get("liutongguben"),
                    })
                    logger.info(f"✅ 从 mootdx 获取到 {symbol} 财务数据")
            except Exception as e:
                logger.warning(f"mootdx 获取财务数据失败 {symbol}: {e}")

        # 2. akshare 个股基本信息
        if self._akshare_available:
            try:
                import akshare as ak
                df = ak.stock_individual_info_em(symbol=symbol)

                if not df.empty:
                    info_dict = dict(zip(df["item"], df["value"]))
                    result.update({
                        "name": info_dict.get("股票简称"),
                        "industry": info_dict.get("行业"),
                        "list_date": info_dict.get("上市时间"),
                        "total_market_cap": float(info_dict.get("总市值", 0)),
                        "circulating_market_cap": float(info_dict.get("流通市值", 0)),
                    })
                    logger.info(f"✅ 从 akshare 获取到 {symbol} 基本信息")
            except Exception as e:
                logger.warning(f"akshare 获取基本信息失败 {symbol}: {e}")

        return result if len(result) > 2 else {}

    def health_check(self) -> bool:
        """
        健康检查

        Returns:
            True: 数据源可用
            False: 数据源不可用
        """
        try:
            # 测试腾讯API（最稳定的数据源）
            test_symbol = "000001"
            quote = self.get_quote(test_symbol)

            if quote and quote.get("price", 0) > 0:
                logger.info("✅ A-stock SKILL 健康检查通过")
                return True
            else:
                logger.warning("❌ A-stock SKILL 健康检查失败：无法获取行情数据")
                return False

        except Exception as e:
            logger.error(f"❌ A-stock SKILL 健康检查失败: {e}")
            return False
