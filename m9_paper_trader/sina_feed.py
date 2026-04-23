"""
新浪财经实时行情 Feed

优点：
  - 真正实时（无延迟）
  - 无需API Key
  - 稳定性较好

缺点：
  - 非官方API
  - 可能随时失效
"""
import requests
import logging
from datetime import datetime
from typing import Optional
from m9_paper_trader.price_feed import PriceFeed, PriceSnapshot

logger = logging.getLogger(__name__)


class SinaFeed(PriceFeed):
    """新浪财经实时行情"""
    
    def __init__(self):
        self._cache = {}
        self._cache_ttl = 3  # 3秒缓存
    
    def get_price(self, instrument: str, dt: Optional[date] = None) -> Optional[PriceSnapshot]:
        if dt is not None:
            return None  # 新浪只提供实时数据
        
        return self._get_realtime(instrument)
    
    def _get_realtime(self, instrument: str) -> Optional[PriceSnapshot]:
        """获取实时行情"""
        try:
            # 转换代码格式：600519.SH -> sh600519
            sina_code = self._convert_to_sina(instrument)
            if not sina_code:
                return None
            
            url = f"http://hq.sinajs.cn/list={sina_code}"
            response = requests.get(url, timeout=3)
            
            if response.status_code != 200:
                return None
            
            # 解析返回数据
            # var hq_str_sh600519="贵州茅台,1680.50,1675.00,1682.30,..."
            content = response.text
            if "\"\"" in content:
                logger.warning(f"[SinaFeed] no data for {instrument}")
                return None
            
            data_str = content.split('"')[1]
            fields = data_str.split(',')
            
            if len(fields) < 32:
                return None
            
            return PriceSnapshot(
                instrument=instrument,
                price=float(fields[3]),      # 当前价
                open_price=float(fields[1]), # 今开
                high=float(fields[4]),       # 最高
                low=float(fields[5]),        # 最低
                volume=float(fields[8]),     # 成交量（手）
                amount=float(fields[9]),     # 成交额（元）
                timestamp=datetime.now(),
                source="sina_realtime",
                prev_close=float(fields[2]), # 昨收
                change_pct=((float(fields[3]) - float(fields[2])) / float(fields[2]) * 100) if float(fields[2]) > 0 else 0,
            )
        
        except Exception as e:
            logger.warning(f"[SinaFeed] failed {instrument}: {e}")
            return None
    
    def _convert_to_sina(self, instrument: str) -> Optional[str]:
        """转换为新浪代码格式
        
        MarketRadar: 600519.SH -> 新浪: sh600519
        MarketRadar: 000858.SZ -> 新浪: sz000858
        MarketRadar: 0700.HK -> 新浪: hk00700
        """
        if '.' not in instrument:
            return None
        
        code, suffix = instrument.split('.')
        suffix = suffix.upper()
        
        if suffix == 'SH':
            return f"sh{code}"
        elif suffix == 'SZ':
            return f"sz{code}"
        elif suffix == 'HK':
            return f"hk{code}"
        else:
            return None
