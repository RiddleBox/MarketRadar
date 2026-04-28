"""
m9_paper_trader/futu_feed.py — 富途OpenD实时行情 Feed

需要先启动 OpenD 命令行版：
  1. 下载：https://www.futunn.com/download/OpenD
  2. 启动：OpenD --ip 127.0.0.1 --port 33333
  3. 用富途牛牛APP扫码授权
  
数据源：
  - A股+港股：秒级推流（Subscribed）
  - 美股：15分钟延迟（免费版）
  
优势：免费（需开户）、实时推流、A股港股美股全覆盖
劣势：需要本地运行OpenD、免费版美股有延迟
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from m9_paper_trader.price_feed import PriceFeed, PriceSnapshot

logger = logging.getLogger(__name__)


class FutuFeed(PriceFeed):
    """富途OpenD实时行情 Feed — A股+港股+美股"""

    def __init__(self, host: str = "127.0.0.1", port: int = 33333):
        self._host = host
        self._port = port
        self._quote_ctx = None
        self._connected = False
        self._realtime_cache: Dict[str, PriceSnapshot] = {}
        self._realtime_cache_time: Optional[datetime] = None
        self._cache_ttl_sec = 10
        self._connect()

    def _connect(self):
        try:
            from futu import OpenQuoteContext
            self._quote_ctx = OpenQuoteContext(host=self._host, port=self._port)
            ret = self._quote_ctx.start()
            if ret == 0 or ret is None:
                self._connected = True
                logger.info(f"[FutuFeed] connected to {self._host}:{self._port}")
            else:
                logger.warning(f"[FutuFeed] start returned: {ret}")
                self._connected = True
        except ImportError:
            logger.error("[FutuFeed] futu-api not installed: pip install futu-api")
            self._connected = False
        except Exception as e:
            logger.warning(f"[FutuFeed] connect failed: {e}")
            self._connected = False

    def _ensure_connection(self) -> bool:
        if self._connected and self._quote_ctx is not None:
            return True
        self._connect()
        return self._connected

    @staticmethod
    def _to_futu_code(instrument: str) -> str:
        """MarketRadar -> Futu code format
        600519.SH -> SH.600519
        000001.SZ -> SZ.000001
        0700.HK  -> HK.0700
        AAPL.US  -> US.AAPL
        """
        if "." not in instrument:
            return instrument
        code, suffix = instrument.split(".")
        suffix = suffix.upper()
        if suffix in ("SH", "SZ"):
            return f"{suffix}.{code}"
        elif suffix == "HK":
            return f"HK.{code}"
        elif suffix == "US":
            return f"US.{code}"
        return instrument

    @staticmethod
    def _from_futu_code(futu_code: str) -> str:
        """Futu code -> MarketRadar format"""
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

    @staticmethod
    def _futu_market_code(instrument: str) -> Optional[int]:
        """Market code for Futu subscription"""
        code, suffix = instrument.split(".") if "." in instrument else (instrument, "")
        suffix = suffix.upper()
        if suffix == "HK":
            return 1
        elif suffix == "US":
            return 2
        elif suffix in ("SH", "SZ"):
            return 3 if suffix == "SH" else 4
        return None

    def get_price(self, instrument: str, dt: Optional[date] = None) -> Optional[PriceSnapshot]:
        if dt is not None:
            return self._get_daily(instrument, dt)

        now = datetime.now()
        if self._realtime_cache_time and (now - self._realtime_cache_time).total_seconds() < self._cache_ttl_sec:
            if instrument in self._realtime_cache:
                return self._realtime_cache[instrument]

        snap = self._fetch_realtime(instrument)
        if snap:
            self._realtime_cache[instrument] = snap
            self._realtime_cache_time = now
        return snap

    def _fetch_realtime(self, instrument: str) -> Optional[PriceSnapshot]:
        if not self._ensure_connection():
            return None

        from futu import RET_ERROR

        futu_code = self._to_futu_code(instrument)
        try:
            ret, df = self._quote_ctx.get_market_snapshot([futu_code])
            if ret == RET_ERROR or df is None or df.empty:
                return None

            row = df.iloc[0]
            price = float(row.get("cur_price", 0))
            if price <= 0:
                return None

            prev_close = float(row.get("prev_close_price", 0))
            open_price = float(row.get("open_price", 0))
            high = float(row.get("high_price", 0))
            low = float(row.get("low_price", 0))
            volume = float(row.get("volume", 0))
            turnover = float(row.get("turnover", 0))
            change_pct = float(row.get("change_rate", 0))

            return PriceSnapshot(
                instrument=instrument,
                price=price,
                open_price=open_price if open_price > 0 else price,
                high=high if high > 0 else price,
                low=low if low > 0 else price,
                volume=volume,
                amount=turnover,
                timestamp=datetime.now(),
                source="futu_realtime",
                prev_close=prev_close if prev_close > 0 else None,
                change_pct=change_pct if change_pct != 0 else None,
            )
        except Exception as e:
            logger.warning(f"[FutuFeed] realtime {instrument} failed: {e}")
            return None

    def _get_daily(self, instrument: str, dt: date) -> Optional[PriceSnapshot]:
        if not self._ensure_connection():
            return None

        from futu import RET_ERROR, KLType, AuType

        futu_code = self._to_futu_code(instrument)

        try:
            start_date = (dt - timedelta(days=10)).strftime("%Y-%m-%d")
            end_date = (dt + timedelta(days=5)).strftime("%Y-%m-%d")

            ret, df, _ = self._quote_ctx.request_history_kline(
                code=futu_code,
                start=start_date,
                end=end_date,
                ktype=KLType.K_DAY,
                autype=AuType.QFQ,
            )

            if ret == RET_ERROR or df is None or df.empty:
                return None

            target_str = dt.strftime("%Y-%m-%d")
            target_row = df[df["time_key"].str.startswith(target_str)]

            if target_row.empty:
                target_row = df.tail(1)

            if target_row.empty:
                return None

            row = target_row.iloc[0]
            close_price = float(row.get("close", 0))
            if close_price <= 0:
                return None

            prev_close = None
            change_pct = None

            row_date_str = str(row.get("time_key", ""))[:10]
            prev_rows = df[df["time_key"] < row_date_str]
            if not prev_rows.empty:
                prev_close = float(prev_rows.iloc[-1].get("close", 0))
                if prev_close > 0:
                    change_pct = round((close_price - prev_close) / prev_close * 100, 2)

            return PriceSnapshot(
                instrument=instrument,
                price=close_price,
                open_price=float(row.get("open", 0)),
                high=float(row.get("high", 0)),
                low=float(row.get("low", 0)),
                volume=float(row.get("volume", 0)),
                amount=float(row.get("turnover", 0)),
                timestamp=datetime.combine(dt, datetime.min.time()),
                source="futu_daily",
                prev_close=prev_close if prev_close and prev_close > 0 else None,
                change_pct=change_pct,
            )
        except Exception as e:
            logger.warning(f"[FutuFeed] daily {instrument} {dt} failed: {e}")
            return None

    def get_daily_prices(
        self,
        instrument: str,
        days: int = 20,
        end_date: Optional[date] = None,
    ) -> Optional[dict]:
        if not self._ensure_connection():
            return None

        from futu import RET_ERROR, KLType, AuType

        if end_date is None:
            end_date = date.today()

        futu_code = self._to_futu_code(instrument)
        start_date = (end_date - timedelta(days=int(days * 2))).strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        try:
            ret, df, _ = self._quote_ctx.request_history_kline(
                code=futu_code,
                start=start_date,
                end=end_date_str,
                ktype=KLType.K_DAY,
                autype=AuType.QFQ,
            )

            if ret == RET_ERROR or df is None or df.empty:
                return None

            import numpy as np

            prices = df["close"].values.astype(float)
            volumes = df["volume"].values.astype(float)
            dates = [date.fromisoformat(str(t)[:10]) for t in df["time_key"].values]

            if len(prices) < 5:
                return None

            return {
                "dates": dates,
                "prices": np.array(prices),
                "volumes": np.array(volumes, dtype=float),
            }
        except Exception as e:
            logger.warning(f"[FutuFeed] get_daily_prices {instrument} failed: {e}")
            return None

    def get_prices_batch(self, instruments: List[str]) -> Dict[str, PriceSnapshot]:
        if not self._ensure_connection():
            return {}

        from futu import RET_ERROR

        futu_codes = [self._to_futu_code(i) for i in instruments]
        result: Dict[str, PriceSnapshot] = {}

        try:
            ret, df = self._quote_ctx.get_market_snapshot(futu_codes)
            if ret == RET_ERROR or df is None or df.empty:
                return {}

            for _, row in df.iterrows():
                code = str(row.get("code", ""))
                instrument = self._from_futu_code(code)
                price = float(row.get("cur_price", 0))
                if price <= 0:
                    continue

                prev_close = float(row.get("prev_close_price", 0))
                result[instrument] = PriceSnapshot(
                    instrument=instrument,
                    price=price,
                    open_price=float(row.get("open_price", 0)),
                    high=float(row.get("high_price", 0)),
                    low=float(row.get("low_price", 0)),
                    volume=float(row.get("volume", 0)),
                    amount=float(row.get("turnover", 0)),
                    timestamp=datetime.now(),
                    source="futu_realtime",
                    prev_close=prev_close if prev_close > 0 else None,
                    change_pct=float(row.get("change_rate", 0)),
                )
        except Exception as e:
            logger.warning(f"[FutuFeed] batch failed: {e}")

        return result

    def close(self):
        if self._quote_ctx:
            try:
                self._quote_ctx.close()
            except Exception:
                pass
            self._connected = False

    def __del__(self):
        self.close()