"""
iTick 实时行情 Feed

API Key: 3f9318ac81e449bcb3ccfcf05aaf54910d89268520354dccba95c1c272cd06d6
到期时间: 7天后
"""
import requests
import logging
from datetime import datetime, date
from typing import Optional
from m9_paper_trader.price_feed import PriceFeed, PriceSnapshot

logger = logging.getLogger(__name__)


class ITickFeed(PriceFeed):
    """iTick 实时行情"""
    
    BASE_URL = "https://api.itick.org"
    
    def __init__(self, api_key: str = "3f9318ac81e449bcb3ccfcf05aaf54910d89268520354dccba95c1c272cd06d6"):
        self.api_key = api_key
        self._cache = {}
        self._cache_ttl = 3  # 3秒缓存
    
    def get_price(self, instrument: str, dt: Optional[date] = None) -> Optional[PriceSnapshot]:
        if dt is not None:
            return None  # iTick 只提供实时数据
        
        return self._get_realtime(instrument)
    
    def _get_realtime(self, instrument: str) -> Optional[PriceSnapshot]:
        """获取实时行情"""
        try:
            # 转换代码格式
            region, code = self._convert_symbol(instrument)
            if not region or not code:
                return None
            
            url = f"{self.BASE_URL}/stock/quote"
            params = {
                "region": region,
                "code": code,
                "token": self.api_key,
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code != 200:
                logger.warning(f"[ITickFeed] HTTP {response.status_code}: {response.text[:100]}")
                return None
            
            data = response.json()
            
            if data.get("code") != 0:
                logger.warning(f"[ITickFeed] API error: {data.get('msg')}")
                return None
            
            quote = data.get("data", {})
            
            return PriceSnapshot(
                instrument=instrument,
                price=float(quote.get("ld", 0)),      # latest price
                open_price=float(quote.get("o", 0)),  # open
                high=float(quote.get("h", 0)),        # high
                low=float(quote.get("l", 0)),         # low
                volume=float(quote.get("v", 0)),      # volume
                amount=float(quote.get("a", 0)),      # amount
                timestamp=datetime.now(),
                source="itick_realtime",
                prev_close=float(quote.get("pc", 0)), # prev close
                change_pct=float(quote.get("chp", 0)), # change percent
            )
        
        except Exception as e:
            logger.warning(f"[ITickFeed] failed {instrument}: {e}")
            return None
    
    def _convert_symbol(self, instrument: str) -> tuple:
        """转换为 iTick 代码格式
        
        MarketRadar: 600519.SH -> iTick: region=SH, code=600519
        MarketRadar: 000858.SZ -> iTick: region=SZ, code=000858
        MarketRadar: 0700.HK -> iTick: region=HK, code=0700
        MarketRadar: AAPL.US -> iTick: region=US, code=AAPL
        """
        if '.' not in instrument:
            return None, None
        
        code, suffix = instrument.split('.')
        suffix = suffix.upper()
        
        if suffix in ('SH', 'SZ', 'HK', 'US'):
            return suffix, code
        else:
            return None, None
