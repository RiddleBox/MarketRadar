"""
m9_paper_trader/price_feed.py -- 价格数据源

支持：
  1. AKShare 实时行情（A股/港股）
  2. AKShare 历史日线（回填用）
  3. TuShare Pro（分钟线/涨跌停价/交易日历/期货）
  4. CSV 静态文件（离线测试用）

统一返回 PriceSnapshot 对象，与具体数据源解耦。
"""
from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent / "data" / "price_cache"


@dataclass
class PriceSnapshot:
    """单标的价格快照"""
    instrument: str
    price: float
    open_price: float
    high: float
    low: float
    volume: float
    amount: float
    timestamp: datetime
    source: str
    limit_up: Optional[float] = None
    limit_down: Optional[float] = None
    prev_close: Optional[float] = None
    change_pct: Optional[float] = None


class PriceFeed:
    """价格数据源基类 / 工厂"""

    def get_price(self, instrument: str, dt: Optional[date] = None) -> Optional[PriceSnapshot]:
        raise NotImplementedError

    def get_limit_prices(self, instrument: str, dt: Optional[date] = None) -> Optional[dict]:
        """获取涨跌停价格。Returns {'limit_up': float, 'limit_down': float} or None."""
        snap = self.get_price(instrument, dt)
        if snap and snap.limit_up is not None:
            return {"limit_up": snap.limit_up, "limit_down": snap.limit_down}
        return None


# ─────────────────────────────────────────────────────────────
# AKShare 实时行情
# ─────────────────────────────────────────────────────────────

class AKShareRealtimeFeed(PriceFeed):

    def __init__(self):
        self._cache: Dict[str, PriceSnapshot] = {}
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_sec = 60

    def get_price(self, instrument: str, dt: Optional[date] = None) -> Optional[PriceSnapshot]:
        if dt is not None:
            return self._get_daily(instrument, dt)
        return self._get_realtime(instrument)

    def _get_realtime(self, instrument: str) -> Optional[PriceSnapshot]:
        try:
            import akshare as ak
            now = datetime.now()

            code = instrument.split(".")[0]
            suffix = instrument.split(".")[-1].upper() if "." in instrument else ""

            if suffix in ("HK",):
                df = ak.stock_hk_spot_em()
                row = df[df["\u4ee3\u7801"] == code]
                if row.empty:
                    return None
                row = row.iloc[0]
                return PriceSnapshot(
                    instrument=instrument,
                    price=float(row.get("\u6700\u65b0\u4ef7", 0)),
                    open_price=float(row.get("\u4eca\u5f00", 0)),
                    high=float(row.get("\u6700\u9ad8", 0)),
                    low=float(row.get("\u6700\u4f4e", 0)),
                    volume=float(row.get("\u6210\u4ea4\u91cf", 0)),
                    amount=float(row.get("\u6210\u4ea4\u989d", 0)),
                    timestamp=now,
                    source="akshare_realtime_hk",
                )
            else:
                df = ak.stock_zh_a_spot_em()
                row = df[df["\u4ee3\u7801"] == code]
                if row.empty:
                    return None
                row = row.iloc[0]
                return PriceSnapshot(
                    instrument=instrument,
                    price=float(row.get("\u6700\u65b0\u4ef7", 0)),
                    open_price=float(row.get("\u4eca\u5f00", 0)),
                    high=float(row.get("\u6700\u9ad8", 0)),
                    low=float(row.get("\u6700\u4f4e", 0)),
                    volume=float(row.get("\u6210\u4ea4\u91cf", 0)),
                    amount=float(row.get("\u6210\u4ea4\u989d", 0)),
                    timestamp=now,
                    source="akshare_realtime_a",
                )
        except Exception as e:
            logger.warning(f"[PriceFeed] realtime failed {instrument}: {e}")
            return None

    def _get_daily(self, instrument: str, dt: date) -> Optional[PriceSnapshot]:
        try:
            import akshare as ak
            code = instrument.split(".")[0]
            suffix = instrument.split(".")[-1].upper() if "." in instrument else ""
            dt_str = dt.strftime("%Y%m%d")

            if suffix in ("HK",):
                df = ak.stock_hk_daily(symbol=code, adjust="qfq")
            elif code.startswith(("51", "15", "16")):
                df = ak.fund_etf_hist_em(symbol=code, adjust="qfq")
                df = df.rename(columns={
                    "\u65e5\u671f": "date", "\u6536\u76d8": "close", "\u5f00\u76d8": "open",
                    "\u6700\u9ad8": "high", "\u6700\u4f4e": "low",
                    "\u6210\u4ea4\u91cf": "volume", "\u6210\u4ea4\u989d": "amount"})
            else:
                df = ak.stock_zh_a_hist(symbol=code, adjust="qfq",
                                        start_date=dt_str, end_date=dt_str)

            if df is None or df.empty:
                return None

            row = df.iloc[-1]
            return PriceSnapshot(
                instrument=instrument,
                price=float(row.get("\u6536\u76d8", row.get("close", 0))),
                open_price=float(row.get("\u5f00\u76d8", row.get("open", 0))),
                high=float(row.get("\u6700\u9ad8", row.get("high", 0))),
                low=float(row.get("\u6700\u4f4e", row.get("low", 0))),
                volume=float(row.get("\u6210\u4ea4\u91cf", row.get("volume", 0))),
                amount=float(row.get("\u6210\u4ea4\u989d", row.get("amount", 0))),
                timestamp=datetime.combine(dt, datetime.min.time()),
                source="akshare_daily",
            )
        except Exception as e:
            logger.warning(f"[PriceFeed] daily failed {instrument} {dt}: {e}")
            return None


# ─────────────────────────────────────────────────────────────
# yfinance (Yahoo Finance)
# ─────────────────────────────────────────────────────────────

class YFinanceFeed(PriceFeed):
    """yfinance 数据源（Yahoo Finance）。

    优势：全球股票（港股/美股/A股）、免费、无需 API Key。
    劣势：实时行情有 15 分钟延迟（免费版）。
    """

    def __init__(self):
        self._cache: Dict[str, PriceSnapshot] = {}
        self._cache_ttl_sec = 60

    def get_price(self, instrument: str, dt: Optional[date] = None) -> Optional[PriceSnapshot]:
        if dt is not None:
            return self._get_daily(instrument, dt)
        return self._get_realtime(instrument)

    def _get_realtime(self, instrument: str) -> Optional[PriceSnapshot]:
        """获取实时行情（15 分钟延迟）"""
        try:
            import yfinance as yf
            
            # 转换股票代码格式
            symbol = self._convert_symbol(instrument)
            if not symbol:
                return None
            
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # 检查数据有效性
            if not info or "currentPrice" not in info:
                logger.warning(f"[YFinanceFeed] no data for {instrument} ({symbol})")
                return None
            
            now = datetime.now()
            
            return PriceSnapshot(
                instrument=instrument,
                price=float(info.get("currentPrice", 0)),
                open_price=float(info.get("open", 0)),
                high=float(info.get("dayHigh", 0)),
                low=float(info.get("dayLow", 0)),
                volume=float(info.get("volume", 0)),
                amount=0.0,  # yfinance 不提供成交额
                timestamp=now,
                source="yfinance_realtime",
                prev_close=float(info.get("previousClose", 0)),
                change_pct=float(info.get("regularMarketChangePercent", 0)),
            )
        except ImportError:
            logger.error("[YFinanceFeed] yfinance not installed: pip install yfinance")
            return None
        except Exception as e:
            logger.warning(f"[YFinanceFeed] realtime failed {instrument}: {e}")
            return None

    def _get_daily(self, instrument: str, dt: date) -> Optional[PriceSnapshot]:
        """获取历史日线数据"""
        try:
            import yfinance as yf
            
            # 转换股票代码格式
            symbol = self._convert_symbol(instrument)
            if not symbol:
                return None
            
            ticker = yf.Ticker(symbol)
            
            # 获取指定日期的数据（前后各取 1 天，确保能取到数据）
            start = dt - timedelta(days=1)
            end = dt + timedelta(days=1)
            hist = ticker.history(start=start.isoformat(), end=end.isoformat())
            
            if hist is None or hist.empty:
                return None
            
            # 找到最接近目标日期的数据
            hist.index = hist.index.tz_localize(None)  # 移除时区信息
            target_rows = hist[hist.index.date == dt]
            
            if target_rows.empty:
                # 如果目标日期没有数据，取最接近的日期
                logger.warning(f"[YFinanceFeed] no data for {dt}, using closest date")
                row = hist.iloc[-1]
            else:
                row = target_rows.iloc[0]
            
            return PriceSnapshot(
                instrument=instrument,
                price=float(row["Close"]),
                open_price=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                volume=float(row["Volume"]),
                amount=0.0,  # yfinance 不提供成交额
                timestamp=datetime.combine(dt, datetime.min.time()),
                source="yfinance_daily",
            )
        except ImportError:
            logger.error("[YFinanceFeed] yfinance not installed: pip install yfinance")
            return None
        except Exception as e:
            logger.warning(f"[YFinanceFeed] daily failed {instrument} {dt}: {e}")
            return None

    def _convert_symbol(self, instrument: str) -> Optional[str]:
        """转换股票代码格式：MarketRadar 格式 → yfinance 格式
        
        MarketRadar 格式：
        - A股：600519.SH, 000858.SZ
        - 港股：0700.HK, 09988.HK
        - 美股：AAPL.US, TSLA.US
        
        yfinance 格式：
        - A股：600519.SS (上交所), 000858.SZ (深交所)
        - 港股：0700.HK, 9988.HK (去掉前导 0)
        - 美股：AAPL, TSLA (不需要后缀)
        """
        if "." not in instrument:
            return instrument  # 已经是正确格式
        
        code, suffix = instrument.split(".")
        suffix = suffix.upper()
        
        if suffix == "SH":
            # 上交所：SH → SS
            return f"{code}.SS"
        elif suffix == "SZ":
            # 深交所：保持 SZ
            return f"{code}.SZ"
        elif suffix == "HK":
            # 港股：去掉前导 0
            code_int = int(code)
            return f"{code_int}.HK"
        elif suffix == "US":
            # 美股：去掉后缀
            return code
        else:
            # 其他市场：保持原样
            return instrument


# ─────────────────────────────────────────────────────────────
# TuShare Pro
# ─────────────────────────────────────────────────────────────

class TushareFeed(PriceFeed):
    """TuShare Pro 数据源。

    优势：涨跌停价格(stk_limit)、交易日历(trade_cal)、分钟线、期货行情。
    需要 token（500元/年起，2000积分）。
    """

    def __init__(self, token: str = ""):
        self._token = token
        self._pro = None
        self._cal_cache: Optional[Set[date]] = None
        self._cal_cache_file = CACHE_DIR / "trade_calendar.json"
        self._limit_cache: Dict[str, dict] = {}
        self._init_pro()

    def _init_pro(self):
        if not self._token:
            try:
                import os
                self._token = os.environ.get("TUSHARE_TOKEN", "")
            except Exception:
                pass
        if self._token:
            try:
                import tushare as ts
                ts.set_token(self._token)
                self._pro = ts.pro_api()
                logger.info("[TushareFeed] initialized")
            except Exception as e:
                logger.warning(f"[TushareFeed] init failed: {e}")
                self._pro = None
        else:
            logger.info("[TushareFeed] no token, disabled")

    @property
    def available(self) -> bool:
        return self._pro is not None

    # ── 交易日历 ─────────────────────────────────────────────

    def get_trade_calendar(self, start_date: str = "20200101",
                           end_date: str = "20261231") -> Set[date]:
        if self._cal_cache is not None:
            return self._cal_cache
        if self._cal_cache_file.exists():
            try:
                data = json.loads(self._cal_cache_file.read_text(encoding="utf-8"))
                self._cal_cache = {date.fromisoformat(d) for d in data}
                return self._cal_cache
            except Exception:
                pass
        if not self.available:
            return set()
        try:
            df = self._pro.trade_cal(exchange="SSE", start_date=start_date,
                                     end_date=end_date, is_open="1")
            dates = set()
            for _, row in df.iterrows():
                cal_date = row["cal_date"]
                dates.add(date(int(cal_date[:4]), int(cal_date[4:6]), int(cal_date[6:8])))
            self._cal_cache = dates
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            self._cal_cache_file.write_text(
                json.dumps(sorted(d.isoformat() for d in dates), indent=2),
                encoding="utf-8",
            )
            logger.info(f"[TushareFeed] calendar cached {len(dates)} trading days")
            return dates
        except Exception as e:
            logger.warning(f"[TushareFeed] trade_cal failed: {e}")
            return set()

    def is_trading_day(self, dt: Optional[date] = None) -> bool:
        dt = dt or date.today()
        cal = self.get_trade_calendar()
        if not cal:
            return dt.weekday() < 5
        return dt in cal

    def next_trading_day(self, dt: date) -> Optional[date]:
        cal = self.get_trade_calendar()
        if not cal:
            nxt = dt + timedelta(days=1)
            while nxt.weekday() >= 5:
                nxt += timedelta(days=1)
            return nxt
        future = sorted(d for d in cal if d > dt)
        return future[0] if future else None

    # ── 涨跌停价格 ─────────────────────────────────────────────

    def get_limit_prices(self, instrument: str, dt: Optional[date] = None) -> Optional[dict]:
        dt = dt or date.today()
        key = f"{instrument}_{dt.isoformat()}"
        if key in self._limit_cache:
            return self._limit_cache[key]
        if not self.available:
            return None
        try:
            code = instrument.split(".")[0]
            ts_code = self._to_ts_code(instrument)
            df = self._pro.stk_limit(ts_code=ts_code, trade_date=dt.strftime("%Y%m%d"))
            if df is not None and not df.empty:
                row = df.iloc[0]
                result = {
                    "limit_up": float(row.get("up_limit", 0)),
                    "limit_down": float(row.get("down_limit", 0)),
                }
                self._limit_cache[key] = result
                return result
        except Exception as e:
            logger.warning(f"[TushareFeed] stk_limit failed {instrument}: {e}")
        return None

    # ── 行情 ──────────────────────────────────────────────────

    def get_price(self, instrument: str, dt: Optional[date] = None) -> Optional[PriceSnapshot]:
        if dt is not None:
            return self._get_daily(instrument, dt)
        return self._get_realtime_daily(instrument)

    def _get_daily(self, instrument: str, dt: date) -> Optional[PriceSnapshot]:
        if not self.available:
            return None
        try:
            ts_code = self._to_ts_code(instrument)
            dt_str = dt.strftime("%Y%m%d")
            code = instrument.split(".")[0]
            if code.startswith(("IF", "IC", "IM", "IH", "TF", "T")):
                return self._get_futures_daily(instrument, dt)
            df = self._pro.daily(ts_code=ts_code, start_date=dt_str, end_date=dt_str)
            if df is None or df.empty:
                return None
            row = df.iloc[0]
            limits = self.get_limit_prices(instrument, dt)
            return PriceSnapshot(
                instrument=instrument,
                price=float(row.get("close", 0)),
                open_price=float(row.get("open", 0)),
                high=float(row.get("high", 0)),
                low=float(row.get("low", 0)),
                volume=float(row.get("vol", 0)),
                amount=float(row.get("amount", 0)) * 1000,
                timestamp=datetime.combine(dt, datetime.min.time()),
                source="tushare_daily",
                limit_up=limits["limit_up"] if limits else None,
                limit_down=limits["limit_down"] if limits else None,
                prev_close=float(row.get("pre_close", 0)),
                change_pct=float(row.get("pct_chg", 0)),
            )
        except Exception as e:
            logger.warning(f"[TushareFeed] daily failed {instrument} {dt}: {e}")
            return None

    def _get_realtime_daily(self, instrument: str) -> Optional[PriceSnapshot]:
        return self._get_daily(instrument, date.today())

    def _get_futures_daily(self, instrument: str, dt: date) -> Optional[PriceSnapshot]:
        if not self.available:
            return None
        try:
            ts_code = self._to_ts_code(instrument)
            dt_str = dt.strftime("%Y%m%d")
            df = self._pro.fut_daily(ts_code=ts_code, start_date=dt_str, end_date=dt_str)
            if df is None or df.empty:
                return None
            row = df.iloc[0]
            return PriceSnapshot(
                instrument=instrument,
                price=float(row.get("close", 0)),
                open_price=float(row.get("open", 0)),
                high=float(row.get("high", 0)),
                low=float(row.get("low", 0)),
                volume=float(row.get("vol", 0)),
                amount=float(row.get("amount", 0)),
                timestamp=datetime.combine(dt, datetime.min.time()),
                source="tushare_futures",
            )
        except Exception as e:
            logger.warning(f"[TushareFeed] futures daily failed {instrument}: {e}")
            return None

    @staticmethod
    def _to_ts_code(instrument: str) -> str:
        code = instrument.split(".")[0]
        suffix = instrument.split(".")[-1].upper() if "." in instrument else ""
        if suffix == "SH":
            return f"{code}.SH"
        if suffix == "SZ":
            return f"{code}.SZ"
        if suffix == "HK":
            return f"{code}.HK"
        if code.startswith(("51", "60", "68", "00", "30", "IF", "IC", "IM", "IH")):
            if code.startswith(("51", "60", "68")):
                return f"{code}.SH"
            return f"{code}.SZ"
        return instrument


# ─────────────────────────────────────────────────────────────
# CSV 静态文件
# ─────────────────────────────────────────────────────────────

class CSVPriceFeed(PriceFeed):

    def __init__(self, csv_path: str):
        self._data: Dict[tuple, PriceSnapshot] = {}
        self._load(csv_path)

    def _load(self, path: str):
        try:
            with open(path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    dt = date.fromisoformat(row["date"])
                    inst = row["instrument"]
                    self._data[(inst, dt)] = PriceSnapshot(
                        instrument=inst,
                        price=float(row.get("close", 0)),
                        open_price=float(row.get("open", 0)),
                        high=float(row.get("high", 0)),
                        low=float(row.get("low", 0)),
                        volume=float(row.get("volume", 0)),
                        amount=float(row.get("amount", 0)),
                        timestamp=datetime.combine(dt, datetime.min.time()),
                        source="csv",
                    )
            logger.info(f"[CSVPriceFeed] loaded {len(self._data)} records")
        except Exception as e:
            logger.error(f"[CSVPriceFeed] load failed: {e}")

    def get_price(self, instrument: str, dt: Optional[date] = None) -> Optional[PriceSnapshot]:
        if dt is None:
            dt = date.today()
        return self._data.get((instrument, dt))


# ─────────────────────────────────────────────────────────────
# Composite Feed (fallback chain)
# ─────────────────────────────────────────────────────────────

class CompositeFeed(PriceFeed):
    """多数据源 fallback 链：tushare -> akshare -> csv_local"""

    def __init__(self, feeds: List[PriceFeed]):
        self._feeds = feeds

    def get_price(self, instrument: str, dt: Optional[date] = None) -> Optional[PriceSnapshot]:
        for feed in self._feeds:
            result = feed.get_price(instrument, dt)
            if result and result.price > 0:
                return result
        return None

    def get_limit_prices(self, instrument: str, dt: Optional[date] = None) -> Optional[dict]:
        for feed in self._feeds:
            if hasattr(feed, "get_limit_prices"):
                result = feed.get_limit_prices(instrument, dt)
                if result:
                    return result
        return None

    def is_trading_day(self, dt: Optional[date] = None) -> bool:
        for feed in self._feeds:
            if hasattr(feed, "is_trading_day"):
                return feed.is_trading_day(dt)
        dt = dt or date.today()
        return dt.weekday() < 5

    def next_trading_day(self, dt: date) -> Optional[date]:
        for feed in self._feeds:
            if hasattr(feed, "next_trading_day"):
                result = feed.next_trading_day(dt)
                if result:
                    return result
        nxt = dt + timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += timedelta(days=1)
        return nxt


# ─────────────────────────────────────────────────────────────
# Equity Curve Tracker
# ─────────────────────────────────────────────────────────────

class EquityCurveTracker:
    """每日资金曲线记录器"""

    def __init__(self, save_path: Optional[Path] = None):
        self._save_path = save_path or Path(__file__).parent.parent / "data" / "equity_curve.json"
        self._curve: List[dict] = []
        self._load()

    def record(self, dt: date, equity: float, cash: float, unrealized_pnl: float,
               open_count: int, closed_today: int, daily_pnl: float = 0.0):
        entry = {
            "date": dt.isoformat(),
            "equity": round(equity, 2),
            "cash": round(cash, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "open_count": open_count,
            "closed_today": closed_today,
            "daily_pnl": round(daily_pnl, 2),
            "drawdown_pct": 0.0,
            "peak_equity": round(equity, 2),
        }
        if self._curve:
            prev = self._curve[-1]
            peak = max(prev.get("peak_equity", equity), equity)
            entry["peak_equity"] = round(peak, 2)
            if peak > 0:
                entry["drawdown_pct"] = round((peak - equity) / peak * 100, 4)
        self._curve.append(entry)
        self._save()

    def latest(self) -> Optional[dict]:
        return self._curve[-1] if self._curve else None

    def get_curve(self, start_date: Optional[date] = None) -> List[dict]:
        if start_date is None:
            return list(self._curve)
        return [e for e in self._curve if date.fromisoformat(e["date"]) >= start_date]

    def max_drawdown_pct(self) -> float:
        if not self._curve:
            return 0.0
        return max(e.get("drawdown_pct", 0) for e in self._curve)

    def total_return_pct(self) -> float:
        if len(self._curve) < 2:
            return 0.0
        start = self._curve[0]["equity"]
        end = self._curve[-1]["equity"]
        if start <= 0:
            return 0.0
        return (end - start) / start * 100

    def _save(self):
        self._save_path.parent.mkdir(parents=True, exist_ok=True)
        self._save_path.write_text(
            json.dumps(self._curve[-365:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load(self):
        if self._save_path.exists():
            try:
                self._curve = json.loads(self._save_path.read_text(encoding="utf-8"))
            except Exception:
                self._curve = []


# ─────────────────────────────────────────────────────────────
# 工厂函数
# ─────────────────────────────────────────────────────────────

def make_price_feed(mode: str = "akshare", csv_path: str = "",
                    tushare_token: str = "",
                    alltick_key: str = "",
                    itick_key: str = "") -> PriceFeed:
    if mode == "csv":
        return CSVPriceFeed(csv_path)
    if mode == "tushare":
        return TushareFeed(token=tushare_token)
    if mode == "yfinance":
        return YFinanceFeed()
    if mode == "alltick":
        from m9_paper_trader.alltick_feed import AllTickFeed
        return AllTickFeed(api_key=alltick_key)
    if mode == "itick":
        from m9_paper_trader.itick_feed import ITickFeed
        return ITickFeed(api_key=itick_key)
    if mode == "composite":
        feeds = []
        
        # 优先级 1: iTick（实时，免费7天）
        if itick_key:
            from m9_paper_trader.itick_feed import ITickFeed
            feeds.append(ITickFeed(api_key=itick_key))
        
        # 优先级 2: AllTick（实时，免费7天）
        if alltick_key:
            from m9_paper_trader.alltick_feed import AllTickFeed
            feeds.append(AllTickFeed(api_key=alltick_key))
        
        # 优先级 3: TuShare（实时，需付费）
        tf = TushareFeed(token=tushare_token)
        if tf.available:
            feeds.append(tf)
        
        # 优先级 4: AKShare（3-5分钟延迟，免费）
        feeds.append(AKShareRealtimeFeed())
        
        # 优先级 5: YFinance（15分钟延迟，免费）
        feeds.append(YFinanceFeed())
        
        return CompositeFeed(feeds)
    return AKShareRealtimeFeed()
