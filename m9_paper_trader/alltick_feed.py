"""
AllTick 实时行情 Feed

API Key: 1230baa6b4df511826b43549873eecfa-c-app
到期时间: 7天后
"""
import requests
import logging
from datetime import datetime, date
from typing import Optional
from m9_paper_trader.price_feed import PriceFeed, PriceSnapshot

logger = logging.getLogger(__name__)


class AllTickFeed(PriceFeed):
    """AllTick 实时行情（170ms延迟）"""
    
    BASE_URL = "https://quote.tradeswitcher.com/quote-stock-b-api"
    
    def __init__(self, api_key: str = "1230baa6b4df511826b43549873eecfa-c-app"):
        self.api_key = api_key
        self._cache = {}
        self._cache_ttl = 3  # 3秒缓存
    
    def get_price(self, instrument: str, dt: Optional[date] = None) -> Optional[PriceSnapshot]:
        if dt is not None:
            return None  # AllTick 只提供实时数据
        
        return self._get_realtime(instrument)
    
    def _get_realtime(self, instrument: str) -> Optional[PriceSnapshot]:
        """获取实时行情"""
        try:
            # 转换代码格式
            symbol_code = self._convert_symbol(instrument)
            if not symbol_code:
                return None
            
            url = f"{self.BASE_URL}/api/quote/realtime"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "symbol_list": [symbol_code]
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=5)
            
            if response.status_code != 200:
                logger.warning(f"[AllTickFeed] HTTP {response.status_code}: {response.text[:100]}")
                return None
            
            data = response.json()
            
            if not data.get("data") or len(data["data"]) == 0:
                return None
            
            quote = data["data"][0]
            
            return PriceSnapshot(
                instrument=instrument,
                price=float(quote.get("latest_price", 0)),
                open_price=float(quote.get("open", 0)),
                high=float(quote.get("high", 0)),
                low=float(quote.get("low", 0)),
                volume=float(quote.get("volume", 0)),
                amount=float(quote.get("amount", 0)),
                timestamp=datetime.now(),
                source="alltick_realtime",
                prev_close=float(quote.get("pre_close", 0)),
                change_pct=float(quote.get("change_rate", 0)) * 100,
            )
        
        except Exception as e:
            logger.warning(f"[AllTickFeed] failed {instrument}: {e}")
            return None
    
    def _convert_symbol(self, instrument: str) -> Optional[str]:
        """转换为 AllTick 代码格式
        
        MarketRadar: 600519.SH -> AllTick: 600519.SS
        MarketRadar: 000858.SZ -> AllTick: 000858.SZ
        MarketRadar: 0700.HK -> AllTick: 0700.HK
        MarketRadar: AAPL.US -> AllTick: AAPL.US
        """
        if '.' not in instrument:
            return None
        
        code, suffix = instrument.split('.')
        suffix = suffix.upper()
        
        if suffix == 'SH':
            return f"{code}.SS"  # 上交所
        elif suffix == 'SZ':
            return f"{code}.SZ"  # 深交所
        elif suffix == 'HK':
            return f"{code}.HK"  # 港股
        elif suffix == 'US':
            return f"{code}.US"  # 美股
        else:
            return instrument
