"""
m9_paper_trader/eastmoney_feed.py — 东方财富实时行情 Feed

直接调用东方财富 HTTP API，绕过 AKShare 中间层，解决代理环境下的连接问题。

数据源：
  - A股实时行情：http://82.push2.eastmoney.com/api/qt/clist/get
  - A股分钟K线：http://push2his.eastmoney.com/api/qt/stock/kline/get
  - 港股实时行情：http://82.push2.eastmoney.com/api/qt/clist/get (港股列表)
  
优势：
  - 免费、无需 API Key
  - 3-5秒延迟（非Level-2）
  - 支持批量查询（一次请求拿全市场）
  - 绕过代理问题

劣势：
  - 仅限A股和部分港股
  - 非交易时段返回上一交易日收盘价
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import requests

from m9_paper_trader.price_feed import PriceFeed, PriceSnapshot

logger = logging.getLogger(__name__)

_A_SHARE_FIELDS = "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152"
_HK_SHARE_FIELDS = "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152"


class EastMoneyFeed(PriceFeed):
    """东方财富实时行情 Feed — A股 + 港股"""

    A_SHARE_LIST_URL = "https://82.push2.eastmoney.com/api/qt/clist/get"
    A_SHARE_DETAIL_URL = "https://push2.eastmoney.com/api/qt/stock/get"
    A_SHARE_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    HK_SHARE_LIST_URL = "https://82.push2.eastmoney.com/api/qt/clist/get"

    MARKET_A_SH = 1   # 上交所
    MARKET_A_SZ = 0   # 深交所

    MARKET_MAP = {
        "SH": 1,
        "SZ": 0,
    }

    def __init__(self, timeout: int = 10):
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://quote.eastmoney.com/",
        })
        self._realtime_cache: Dict[str, PriceSnapshot] = {}
        self._realtime_cache_time: Optional[datetime] = None
        self._cache_ttl_sec = 30
        self._batch_cache: Dict[str, PriceSnapshot] = {}

    def get_price(self, instrument: str, dt: Optional[date] = None) -> Optional[PriceSnapshot]:
        if dt is not None:
            return self._get_daily(instrument, dt)

        cache_key = instrument
        now = datetime.now()
        if self._realtime_cache_time and (now - self._realtime_cache_time).total_seconds() < self._cache_ttl_sec:
            if cache_key in self._realtime_cache:
                return self._realtime_cache[cache_key]

        if cache_key in self._batch_cache:
            return self._batch_cache[cache_key]

        snap = self._fetch_single(instrument)
        if snap:
            self._realtime_cache[cache_key] = snap
            self._realtime_cache_time = now
        return snap

    def get_prices_batch(self, instruments: List[str]) -> Dict[str, PriceSnapshot]:
        a_shares = [i for i in instruments if i.endswith((".SH", ".SZ"))]
        hk_shares = [i for i in instruments if i.endswith(".HK")]

        result: Dict[str, PriceSnapshot] = {}

        if a_shares:
            self._fetch_a_share_batch(a_shares, result)

        for i in hk_shares:
            snap = self._fetch_single(i)
            if snap:
                result[i] = snap

        self._batch_cache.update(result)
        return result

    def _fetch_a_share_batch(self, instruments: List[str], result: Dict[str, PriceSnapshot]):
        for page in range(1, 10):
            try:
                params = {
                    "pn": str(page),
                    "pz": "200",
                    "po": "1",
                    "np": "1",
                    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                    "fltt": "2",
                    "invt": "2",
                    "fid": "f3",
                    "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
                    "fields": _A_SHARE_FIELDS,
                }
                resp = self._session.get(
                    self.A_SHARE_LIST_URL,
                    params=params,
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                data = resp.json()

                if not data or "data" not in data or data["data"] is None:
                    break

                diff_items = data["data"].get("diff", [])
                if not diff_items:
                    break

                code_map = {}
                for inst in instruments:
                    code, suffix = inst.split(".")
                    code_map[code] = inst

                for item in diff_items:
                    code = str(item.get("f12", ""))
                    if code in code_map:
                        inst = code_map[code]
                        snap = self._parse_a_share_item(item, inst)
                        if snap:
                            result[inst] = snap

                if len(code_map) == 0 or all(i in result for i in instruments):
                    break

            except Exception as e:
                logger.warning(f"[EastMoneyFeed] A-share batch page {page} failed: {e}")
                break

    def _parse_a_share_item(self, item: dict, instrument: str) -> Optional[PriceSnapshot]:
        try:
            price_raw = item.get("f2", 0)
            if price_raw is None or float(price_raw) <= 0:
                return None
            price = float(price_raw) / 100
            prev_close_raw = item.get("f18", 0)
            prev_close = float(prev_close_raw) / 100 if prev_close_raw and float(prev_close_raw) > 0 else None
            change_pct_raw = item.get("f3", 0)
            change_pct = float(change_pct_raw) / 100 if change_pct_raw is not None else None
            open_raw = item.get("f17", 0)
            open_price = float(open_raw) / 100 if open_raw and float(open_raw) > 0 else price
            high_raw = item.get("f15", 0)
            high = float(high_raw) / 100 if high_raw and float(high_raw) > 0 else price
            low_raw = item.get("f16", 0)
            low = float(low_raw) / 100 if low_raw and float(low_raw) > 0 else price
            volume = float(item.get("f5", 0))
            amount = float(item.get("f6", 0))

            return PriceSnapshot(
                instrument=instrument,
                price=price,
                open_price=open_price,
                high=high,
                low=low,
                volume=volume,
                amount=amount,
                timestamp=datetime.now(),
                source="eastmoney_realtime_a",
                prev_close=prev_close,
                change_pct=change_pct,
            )
        except (ValueError, TypeError) as e:
            logger.warning(f"[EastMoneyFeed] parse A-share failed {instrument}: {e}")
            return None

    def _fetch_single(self, instrument: str) -> Optional[PriceSnapshot]:
        if instrument.endswith((".SH", ".SZ")):
            return self._fetch_a_share_single(instrument)
        if instrument.endswith(".HK"):
            return self._fetch_hk_single(instrument)
        return None

    def _fetch_a_share_single(self, instrument: str) -> Optional[PriceSnapshot]:
        code, suffix = instrument.split(".")
        market = self.MARKET_MAP.get(suffix, 1)
        secid = f"{market}.{code}"

        try:
            params = {
                "secid": secid,
                "fields": "f43,f44,f45,f46,f47,f48,f50,f51,f52,f55,f57,f58,f60,f116,f117,f162,f170,f171",
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            }
            resp = self._session.get(
                self.A_SHARE_DETAIL_URL,
                params=params,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data or "data" not in data or data["data"] is None:
                return None

            d = data["data"]
            price_raw = d.get("f43", 0)
            if price_raw is None or float(price_raw) <= 0:
                return None
            price = float(price_raw) / 100
            prev_close_raw = d.get("f60", 0)
            prev_close = float(prev_close_raw) / 100 if prev_close_raw and float(prev_close_raw) > 0 else None
            open_raw = d.get("f46", 0)
            open_price = float(open_raw) / 100 if open_raw and float(open_raw) > 0 else price
            high_raw = d.get("f44", 0)
            high = float(high_raw) / 100 if high_raw and float(high_raw) > 0 else price
            low_raw = d.get("f45", 0)
            low = float(low_raw) / 100 if low_raw and float(low_raw) > 0 else price
            volume = float(d.get("f47", 0))
            amount = float(d.get("f48", 0))
            change_pct_raw = d.get("f170", 0)
            change_pct = float(change_pct_raw) / 100 if change_pct_raw is not None else None

            return PriceSnapshot(
                instrument=instrument,
                price=price,
                open_price=open_price,
                high=high,
                low=low,
                volume=volume,
                amount=amount,
                timestamp=datetime.now(),
                source="eastmoney_realtime_a",
                prev_close=prev_close,
                change_pct=change_pct,
            )
        except Exception as e:
            logger.warning(f"[EastMoneyFeed] A-share single {instrument} failed: {e}")
            return None

    def _fetch_hk_single(self, instrument: str) -> Optional[PriceSnapshot]:
        code = instrument.split(".")[0]
        secid = f"116.{code}"

        try:
            params = {
                "secid": secid,
                "fields": "f43,f44,f45,f46,f47,f48,f50,f51,f52,f55,f57,f58,f60,f116,f117,f170,f171",
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            }
            resp = self._session.get(
                self.A_SHARE_DETAIL_URL,
                params=params,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data or "data" not in data or data["data"] is None:
                return None

            d = data["data"]
            price_raw = d.get("f43", 0)
            if price_raw is None or float(price_raw) <= 0:
                return None
            price = float(price_raw) / 1000
            prev_close_raw = d.get("f60", 0)
            prev_close = float(prev_close_raw) / 1000 if prev_close_raw and float(prev_close_raw) > 0 else None
            open_raw = d.get("f46", 0)
            open_price = float(open_raw) / 1000 if open_raw and float(open_raw) > 0 else price
            high_raw = d.get("f44", 0)
            high = float(high_raw) / 1000 if high_raw and float(high_raw) > 0 else price
            low_raw = d.get("f45", 0)
            low = float(low_raw) / 1000 if low_raw and float(low_raw) > 0 else price
            volume = float(d.get("f47", 0))
            amount = float(d.get("f48", 0))
            change_pct_raw = d.get("f170", 0)
            change_pct = float(change_pct_raw) / 100 if change_pct_raw is not None else None

            return PriceSnapshot(
                instrument=instrument,
                price=price,
                open_price=open_price,
                high=high,
                low=low,
                volume=volume,
                amount=amount,
                timestamp=datetime.now(),
                source="eastmoney_realtime_hk",
                prev_close=prev_close,
                change_pct=change_pct,
            )
        except Exception as e:
            logger.warning(f"[EastMoneyFeed] HK single {instrument} failed: {e}")
            return None

    def _get_daily(self, instrument: str, dt: date) -> Optional[PriceSnapshot]:
        if instrument.endswith((".SH", ".SZ")):
            return self._get_a_share_kline(instrument, dt)
        if instrument.endswith(".HK"):
            return self._get_hk_kline(instrument, dt)
        return None

    def _get_a_share_kline(self, instrument: str, dt: date) -> Optional[PriceSnapshot]:
        code, suffix = instrument.split(".")
        market = self.MARKET_MAP.get(suffix, 1)
        secid = f"{market}.{code}"

        try:
            end_date = dt + timedelta(days=5)
            params = {
                "secid": secid,
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57",
                "klt": "101",
                "fqt": "1",
                "beg": (dt - timedelta(days=10)).strftime("%Y%m%d"),
                "end": end_date.strftime("%Y%m%d"),
            }
            resp = self._session.get(
                self.A_SHARE_KLINE_URL,
                params=params,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data or "data" not in data or data["klines"] not in data["data"]:
                return None

            klines = data["data"]["klines"]
            if not klines:
                return None

            target_str = dt.strftime("%Y-%m-%d")
            target_kline = None
            prev_kline = None

            for kline in klines:
                parts = kline.split(",")
                if len(parts) < 7:
                    continue
                kline_date = parts[0]
                if kline_date == target_str:
                    target_kline = parts
                    break
                prev_kline = parts

            if target_kline is None:
                target_kline = klines[-1].split(",") if klines else None
                if target_kline is None:
                    return None

            close = float(target_kline[2])
            open_p = float(target_kline[1])
            high = float(target_kline[3])
            low = float(target_kline[4])
            volume = float(target_kline[5])
            amount = float(target_kline[6])

            prev_close = float(prev_kline[2]) if prev_kline and len(prev_kline) > 2 else None
            change_pct = None
            if prev_close and prev_close > 0:
                change_pct = round((close - prev_close) / prev_close * 100, 2)

            return PriceSnapshot(
                instrument=instrument,
                price=close,
                open_price=open_p,
                high=high,
                low=low,
                volume=volume,
                amount=amount,
                timestamp=datetime.combine(dt, datetime.min.time()),
                source="eastmoney_kline_a",
                prev_close=prev_close,
                change_pct=change_pct,
            )
        except Exception as e:
            logger.warning(f"[EastMoneyFeed] A-share kline {instrument} {dt} failed: {e}")
            return None

    def _get_hk_kline(self, instrument: str, dt: date) -> Optional[PriceSnapshot]:
        code = instrument.split(".")[0]
        secid = f"116.{code}"

        try:
            params = {
                "secid": secid,
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57",
                "klt": "101",
                "fqt": "1",
                "beg": (dt - timedelta(days=10)).strftime("%Y%m%d"),
                "end": (dt + timedelta(days=5)).strftime("%Y%m%d"),
            }
            resp = self._session.get(
                self.A_SHARE_KLINE_URL,
                params=params,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data or "data" not in data or "klines" not in data["data"]:
                return None

            klines = data["data"]["klines"]
            if not klines:
                return None

            target_str = dt.strftime("%Y-%m-%d")
            target_kline = None
            prev_kline = None

            for kline in klines:
                parts = kline.split(",")
                if len(parts) < 7:
                    continue
                if parts[0] == target_str:
                    target_kline = parts
                    break
                prev_kline = parts

            if target_kline is None:
                target_kline = klines[-1].split(",") if klines else None
                if target_kline is None:
                    return None

            close = float(target_kline[2])
            prev_close = float(prev_kline[2]) if prev_kline and len(prev_kline) > 2 else None

            return PriceSnapshot(
                instrument=instrument,
                price=close,
                open_price=float(target_kline[1]),
                high=float(target_kline[3]),
                low=float(target_kline[4]),
                volume=float(target_kline[5]),
                amount=float(target_kline[6]),
                timestamp=datetime.combine(dt, datetime.min.time()),
                source="eastmoney_kline_hk",
                prev_close=prev_close,
                change_pct=round((close - prev_close) / prev_close * 100, 2) if prev_close and prev_close > 0 else None,
            )
        except Exception as e:
            logger.warning(f"[EastMoneyFeed] HK kline {instrument} {dt} failed: {e}")
            return None

    def get_daily_prices(
        self,
        instrument: str,
        days: int = 20,
        end_date: Optional[date] = None,
    ) -> Optional[dict]:
        """批量获取历史日线数据，返回 {dates, prices, volumes}"""
        if end_date is None:
            end_date = date.today()

        if instrument.endswith((".SH", ".SZ")):
            return self._get_a_share_kline_batch(instrument, days, end_date)
        if instrument.endswith(".HK"):
            return self._get_hk_kline_batch(instrument, days, end_date)
        return None

    def _get_a_share_kline_batch(self, instrument: str, days: int, end_date: date) -> Optional[dict]:
        code, suffix = instrument.split(".")
        market = self.MARKET_MAP.get(suffix, 1)
        secid = f"{market}.{code}"
        start_date = end_date - timedelta(days=int(days * 2))

        try:
            params = {
                "secid": secid,
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57",
                "klt": "101",
                "fqt": "1",
                "beg": start_date.strftime("%Y%m%d"),
                "end": end_date.strftime("%Y%m%d"),
            }
            resp = self._session.get(
                self.A_SHARE_KLINE_URL,
                params=params,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data or "data" not in data or "klines" not in data["data"]:
                return None

            klines = data["data"]["klines"]
            if not klines:
                return None

            import numpy as np
            dates = []
            prices = []
            volumes = []
            for kline in klines:
                parts = kline.split(",")
                if len(parts) < 7:
                    continue
                try:
                    dates.append(date.fromisoformat(parts[0]))
                    prices.append(float(parts[2]))
                    volumes.append(float(parts[5]))
                except (ValueError, IndexError):
                    continue

            if len(prices) < 5:
                return None

            return {
                "dates": dates,
                "prices": np.array(prices),
                "volumes": np.array(volumes, dtype=float),
            }
        except Exception as e:
            logger.warning(f"[EastMoneyFeed] A-share kline batch {instrument} failed: {e}")
            return None

    def _get_hk_kline_batch(self, instrument: str, days: int, end_date: date) -> Optional[dict]:
        code = instrument.split(".")[0]
        secid = f"116.{code}"
        start_date = end_date - timedelta(days=int(days * 2))

        try:
            params = {
                "secid": secid,
                "fields1": "f1,f2,f3,f4,f5,f6",
                "fields2": "f51,f52,f53,f54,f55,f56,f57",
                "klt": "101",
                "fqt": "1",
                "beg": start_date.strftime("%Y%m%d"),
                "end": end_date.strftime("%Y%m%d"),
            }
            resp = self._session.get(
                self.A_SHARE_KLINE_URL,
                params=params,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if not data or "data" not in data or "klines" not in data["data"]:
                return None

            klines = data["data"]["klines"]
            if not klines:
                return None

            import numpy as np
            dates = []
            prices = []
            volumes = []
            for kline in klines:
                parts = kline.split(",")
                if len(parts) < 7:
                    continue
                try:
                    dates.append(date.fromisoformat(parts[0]))
                    prices.append(float(parts[2]))
                    volumes.append(float(parts[5]))
                except (ValueError, IndexError):
                    continue

            if len(prices) < 5:
                return None

            return {
                "dates": dates,
                "prices": np.array(prices),
                "volumes": np.array(volumes, dtype=float),
            }
        except Exception as e:
            logger.warning(f"[EastMoneyFeed] HK kline batch {instrument} failed: {e}")
            return None