"""
Baostock 实时行情 Feed

优点：
  - 免费无需 API Key
  - A股数据稳定
  - 已在模拟盘中验证通过

缺点：
  - 仅支持A股
  - 返回的是日线收盘价（非实时）
"""
import baostock as bs
import logging
from datetime import datetime, date, timedelta
from typing import Optional
from m9_paper_trader.price_feed import PriceFeed, PriceSnapshot

logger = logging.getLogger(__name__)


class BaostockFeed(PriceFeed):
    """Baostock A股行情"""

    def __init__(self):
        self._cache = {}
        self._cache_time = None
        self._cache_ttl_sec = 300  # 5分钟缓存

    def get_price(self, instrument: str, dt: Optional[date] = None) -> Optional[PriceSnapshot]:
        now = datetime.now()

        # 检查缓存
        if self._cache_time and (now - self._cache_time).total_seconds() < self._cache_ttl_sec:
            if instrument in self._cache:
                return self._cache[instrument]

        if dt is None:
            dt = now.date()

        try:
            # 转换代码格式：600519.SH -> sh.600519
            bs_code = self._convert_to_baostock(instrument)
            if not bs_code:
                return None

            lg = bs.login()
            try:
                end_date = dt.strftime('%Y-%m-%d')
                start_date = (dt - timedelta(days=10)).strftime('%Y-%m-%d')

                df = bs.query_history_k_data_plus(
                    bs_code,
                    'date,open,high,low,close,volume',
                    start_date=start_date,
                    end_date=end_date
                )
                data = df.get_data()

                if data is None or data.empty:
                    return None

                row = data.iloc[-1]
                close_price = float(row['close'])

                snapshot = PriceSnapshot(
                    instrument=instrument,
                    price=close_price,
                    open_price=float(row.get('open', close_price)),
                    high=float(row.get('high', close_price)),
                    low=float(row.get('low', close_price)),
                    volume=float(row.get('volume', 0)),
                    amount=0.0,
                    timestamp=now,
                    source="baostock_daily",
                )

                self._cache[instrument] = snapshot
                self._cache_time = now
                return snapshot

            finally:
                bs.logout()

        except Exception as e:
            logger.warning(f"[BaostockFeed] failed {instrument}: {e}")
            return None

    def _convert_to_baostock(self, instrument: str) -> Optional[str]:
        """转换为 Baostock 代码格式"""
        if '.' not in instrument:
            return None

        code, suffix = instrument.split('.')
        suffix = suffix.upper()

        if suffix == 'SH':
            return f"sh.{code}"
        elif suffix == 'SZ':
            return f"sz.{code}"
        else:
            return None
