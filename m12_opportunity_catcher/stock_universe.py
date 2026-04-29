"""
股票池管理 - 动态获取全市场标的列表

数据源：
  - A股：Futu API (沪深全部股票，约5000只)
  - 港股：Futu API (港股主板+创业板)
  - 美股：Futu API (美股全部股票) 或预定义列表(标普500/纳斯达克100)

缓存策略：
  - 每日更新一次（盘前）
  - 缓存到本地文件 data/stock_universe.json

过滤策略：
  - 行业过滤：只关注科技类高新产业（游戏、互联网、AI等）
  - 价格过滤：可配置（默认不过滤）
  - 成交量过滤：日均成交量 > 10万股
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.schemas import Market
from m12_opportunity_catcher.industry_filter import get_industry_filter

logger = logging.getLogger(__name__)


class StockUniverse:
    """股票池管理器 - 动态获取全市场标的"""

    def __init__(
        self,
        cache_dir: str = "data",
        min_volume: int = 100000,
        min_price_us: float = 0.0,
        enable_industry_filter: bool = False
    ):
        """
        Args:
            cache_dir: 缓存目录
            min_volume: 最小成交量（当日或5日平均）
            min_price_us: 美股最低价格（0表示不过滤）
            enable_industry_filter: 是否启用行业过滤（仅科技股），默认False捕捉全市场
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "stock_universe.json"
        self._cache: Dict[str, List[str]] = {}
        self._cache_date: Optional[date] = None
        self._load_cache()
        self.industry_filter = get_industry_filter()
        self.min_volume = min_volume
        self.min_price_us = min_price_us
        self.enable_industry_filter = enable_industry_filter

    def _load_cache(self):
        """从本地文件加载缓存"""
        if not self.cache_file.exists():
            return

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._cache = data.get("stocks", {})
                cache_date_str = data.get("date")
                if cache_date_str:
                    self._cache_date = date.fromisoformat(cache_date_str)
        except Exception as e:
            logger.warning(f"[StockUniverse] load cache failed: {e}")

    def _save_cache(self):
        """保存缓存到本地文件"""
        try:
            data = {
                "date": self._cache_date.isoformat() if self._cache_date else None,
                "stocks": self._cache,
                "updated_at": datetime.now().isoformat(),
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"[StockUniverse] save cache failed: {e}")

    def get_stock_list(self, market: Market, force_refresh: bool = False) -> List[str]:
        """
        获取指定市场的股票列表

        Args:
            market: 目标市场
            force_refresh: 强制刷新（忽略缓存）

        Returns:
            股票代码列表
        """
        market_key = market.value

        # 检查缓存是否有效
        if not force_refresh and self._cache_date == date.today() and market_key in self._cache:
            logger.info(f"[StockUniverse] using cached {market_key}: {len(self._cache[market_key])} stocks")
            return self._cache[market_key]

        # 刷新股票列表
        logger.info(f"[StockUniverse] fetching {market_key} stock list...")
        stock_list = self._fetch_stock_list(market)

        if stock_list:
            self._cache[market_key] = stock_list
            self._cache_date = date.today()
            self._save_cache()
            logger.info(f"[StockUniverse] fetched {market_key}: {len(stock_list)} stocks")
        else:
            logger.warning(f"[StockUniverse] fetch {market_key} failed, using fallback")
            stock_list = self._get_fallback_list(market)

        return stock_list

    def _fetch_stock_list(self, market: Market) -> List[str]:
        """从Futu API获取股票列表，并应用行业和成交量过滤"""
        try:
            from futu import OpenQuoteContext, Market as FutuMarket, SecurityType, RET_OK

            quote_ctx = OpenQuoteContext(host='127.0.0.1', port=11111)

            # 映射市场
            futu_market_map = {
                Market.A_SHARE: FutuMarket.SH,  # 先获取沪市
                Market.HK: FutuMarket.HK,
                Market.US: FutuMarket.US,
            }

            if market not in futu_market_map:
                quote_ctx.close()
                return []

            stock_list = []
            stock_info_list = []  # [(code, name), ...]

            if market == Market.A_SHARE:
                # A股需要分别获取沪市和深市
                for futu_market in [FutuMarket.SH, FutuMarket.SZ]:
                    ret, df = quote_ctx.get_stock_basicinfo(
                        market=futu_market,
                        stock_type=SecurityType.STOCK
                    )
                    if ret == RET_OK and df is not None and not df.empty:
                        # 过滤：排除停牌、退市、ST股票
                        df = df[
                            (df['suspension'] != 'True') &
                            (df['delisting'] == False) &
                            (~df['name'].str.contains('ST', na=False))
                        ]
                        for _, row in df.iterrows():
                            code = self._from_futu_code(row['code'])
                            name = row['name']
                            stock_info_list.append((code, name))
                    else:
                        logger.warning(f"[StockUniverse] get_stock_basicinfo failed: ret={ret}")
            else:
                futu_market = futu_market_map[market]
                ret, df = quote_ctx.get_stock_basicinfo(
                    market=futu_market,
                    stock_type=SecurityType.STOCK
                )
                if ret == RET_OK and df is not None and not df.empty:
                    # 过滤停牌、退市和OTC市场（美股）
                    df = df[
                        (df['suspension'] != 'True') &
                        (df['delisting'] == False)
                    ]
                    if market == Market.US:
                        # 过滤OTC市场（US_PINK），只保留主板市场
                        df = df[df['exchange_type'].isin(['US_NASDAQ', 'US_NYSE', 'US_AMEX'])]

                    for _, row in df.iterrows():
                        code = self._from_futu_code(row['code'])
                        name = row['name']
                        stock_info_list.append((code, name))
                else:
                    logger.warning(f"[StockUniverse] get_stock_basicinfo failed: ret={ret}")

            logger.info(f"[StockUniverse] fetched {len(stock_info_list)} stocks before filtering")

            # 应用行业过滤（如果启用）
            if self.enable_industry_filter:
                tech_stocks = self.industry_filter.filter_stock_list(stock_info_list)
                logger.info(f"[StockUniverse] after industry filter: {len(tech_stocks)} stocks")
            else:
                # 不过滤行业，直接提取股票代码
                tech_stocks = [code for code, name in stock_info_list]
                logger.info(f"[StockUniverse] industry filter disabled, keeping all {len(tech_stocks)} stocks")

            # 应用成交量和价格过滤（批量获取快照）
            filtered_stocks = self._filter_by_volume_and_price(quote_ctx, tech_stocks, market)
            logger.info(f"[StockUniverse] after volume/price filter: {len(filtered_stocks)} stocks")

            quote_ctx.close()
            return filtered_stocks

        except ImportError:
            logger.error("[StockUniverse] futu-api not installed")
            return []
        except Exception as e:
            logger.warning(f"[StockUniverse] fetch from Futu failed: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _filter_by_volume_and_price(
        self,
        quote_ctx,
        stocks: List[str],
        market: Market,
        min_volume: int = 100000,  # 最小成交量10万股
        min_price_us: float = 20.0  # 美股最低价格$20
    ) -> List[str]:
        """
        根据成交量和价格过滤股票

        Args:
            quote_ctx: Futu API连接
            stocks: 股票代码列表
            market: 市场
            min_volume: 最小成交量（当日累计成交量 OR 5日平均成交量，满足其一即可）
            min_price_us: 美股最低价格

        Returns:
            过滤后的股票列表
        """
        from futu import RET_OK, KLType
        import time

        filtered = []
        batch_size = 200  # 每批查询200只

        logger.info(f"[StockUniverse] filtering {len(stocks)} stocks by volume/price...")

        for i in range(0, len(stocks), batch_size):
            batch = stocks[i:i+batch_size]
            futu_codes = [self._to_futu_code(s) for s in batch]

            try:
                # 批量请求快照
                ret, df = quote_ctx.get_market_snapshot(futu_codes)
                if ret != RET_OK or df is None or df.empty:
                    logger.warning(f"[StockUniverse] batch {i//batch_size} snapshot failed: ret={ret}")
                    time.sleep(0.5)  # 失败后等待0.5秒再继续
                    continue

                # 处理所有返回的股票
                for _, row in df.iterrows():
                    code = self._from_futu_code(row['code'])
                    price = float(row.get('last_price', 0))
                    volume_today = float(row.get('volume', 0))

                    # 价格过滤（仅美股）
                    if market == Market.US and price < min_price_us:
                        continue

                    # 成交量过滤：当日累计成交量 OR 5日平均成交量 >= 10万
                    if volume_today >= min_volume:
                        filtered.append(code)
                    else:
                        # 检查5日平均成交量
                        futu_code = self._to_futu_code(code)
                        ret_kl, df_kl, _ = quote_ctx.request_history_kline(
                            futu_code, None, None, KLType.K_DAY, 5
                        )
                        if ret_kl == RET_OK and df_kl is not None and not df_kl.empty:
                            if df_kl['volume'].mean() >= min_volume:
                                filtered.append(code)

            except Exception as e:
                logger.warning(f"[StockUniverse] batch {i//batch_size} failed: {e}")
                time.sleep(0.5)  # 异常后等待0.5秒再继续
                continue

            # 每批之间间隔0.5秒，避免API频率限制
            if i + batch_size < len(stocks):
                time.sleep(0.5)

            if (i // batch_size) % 5 == 0:
                logger.info(f"[StockUniverse] processed {min(i + batch_size, len(stocks))}/{len(stocks)}, filtered: {len(filtered)}")

        logger.info(f"[StockUniverse] filtered result: {len(filtered)} stocks")

        return filtered

    @staticmethod
    def _to_futu_code(instrument: str) -> str:
        """MarketRadar -> Futu code format"""
        if "." not in instrument:
            return instrument
        # 使用 rsplit 从右边分割，只分割一次，处理 BRK.B.US 这种情况
        parts = instrument.rsplit(".", 1)
        if len(parts) != 2:
            return instrument
        code, suffix = parts
        suffix = suffix.upper()
        if suffix in ("SH", "SZ"):
            return f"{suffix}.{code}"
        elif suffix == "HK":
            return f"HK.{int(code):05d}"
        elif suffix == "US":
            return f"US.{code}"
        return instrument

    @staticmethod
    def _from_futu_code(futu_code: str) -> str:
        """Futu格式 -> MarketRadar格式
        SH.600519 -> 600519.SH
        SZ.000001 -> 000001.SZ
        HK.00700 -> 0700.HK
        US.AAPL -> AAPL.US
        """
        if "." not in futu_code:
            return futu_code
        prefix, code = futu_code.split(".", 1)
        prefix = prefix.upper()
        if prefix in ("SH", "SZ"):
            return f"{code}.{prefix}"
        elif prefix == "HK":
            return f"{int(code):04d}.HK"
        elif prefix == "US":
            return f"{code}.US"
        return futu_code

    def _get_fallback_list(self, market: Market) -> List[str]:
        """获取备用股票列表（当API失败时）"""
        if market == Market.A_SHARE:
            # A股：沪深300成分股
            return [
                "000001.SZ", "000002.SZ", "000063.SZ", "000333.SZ",
                "000338.SZ", "000425.SZ", "000568.SZ", "000625.SZ",
                "000651.SZ", "000725.SZ", "000776.SZ", "000858.SZ",
                "600000.SH", "600009.SH", "600010.SH", "600016.SH",
                "600019.SH", "600025.SH", "600028.SH", "600029.SH",
                "600030.SH", "600031.SH", "600036.SH", "600048.SH",
                "600050.SH", "600104.SH", "600519.SH", "600585.SH",
                "600887.SH", "601012.SH", "601088.SH", "601111.SH",
                "601166.SH", "601211.SH", "601225.SH", "601288.SH",
                "601318.SH", "601336.SH", "601398.SH", "601601.SH",
                "601628.SH", "601688.SH", "601728.SH", "601766.SH",
                "601857.SH", "601888.SH", "601899.SH", "601919.SH",
                "601985.SH", "601988.SH", "603259.SH",
            ]
        elif market == Market.HK:
            return [
                "00700.HK", "00005.HK", "00941.HK", "01299.HK",
                "02318.HK", "02382.HK", "03988.HK", "09988.HK",
            ]
        elif market == Market.US:
            # 美股：纳斯达克100 + 标普500头部
            return [
                "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
                "JPM", "V", "UNH", "MA", "HD", "PG", "JNJ", "BAC", "ABBV", "CVX",
                "LLY", "AVGO", "MRK", "KO", "PEP", "COST", "WMT", "ADBE", "MCD",
                "CSCO", "ACN", "TMO", "ABT", "DHR", "VZ", "NKE", "NFLX", "CRM",
                "INTC", "TXN", "CMCSA", "AMD", "QCOM", "PM", "UNP", "NEE", "HON",
                "RTX", "ORCL", "INTU", "LOW", "UPS", "IBM", "AMGN", "BA", "CAT",
            ]
        return []


# 全局单例
_stock_universe = None


def get_stock_universe() -> StockUniverse:
    """获取全局股票池管理器单例"""
    global _stock_universe
    if _stock_universe is None:
        _stock_universe = StockUniverse()
    return _stock_universe
