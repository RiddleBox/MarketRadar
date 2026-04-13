"""
core/data_loader.py — 历史市场数据加载器

可插拔的数据加载架构，支持多种数据源：
- AKShareLoader: akshare 开源数据（A股/港股/宏观）
- BaoStockLoader: baostock A股历史行情
- CSVLoader: 本地 CSV 文件

所有加载器实现 HistoricalDataLoader Protocol，可以互换。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, runtime_checkable

import pandas as pd
from typing import Protocol

logger = logging.getLogger(__name__)


# ============================================================
# Protocol 定义（接口规范）
# ============================================================

@runtime_checkable
class HistoricalDataLoader(Protocol):
    """
    历史数据加载器协议。

    所有具体实现都需要满足此接口。
    使用 Protocol 而非继承，保持实现的独立性和可替换性。
    """

    def get_ohlcv(
        self,
        instrument: str,
        start: datetime,
        end: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        """
        获取 OHLCV（开高低收量）历史数据。

        Args:
            instrument: 标的代码。A股如"600519"，港股如"00700"
            start: 开始日期
            end: 结束日期
            frequency: 频率，"1d"=日线, "1w"=周线, "1M"=月线

        Returns:
            DataFrame，至少包含列：['date', 'open', 'high', 'low', 'close', 'volume']
            index 为 date
        """
        ...

    def get_macro_data(
        self,
        indicator: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """
        获取宏观经济指标数据。

        Args:
            indicator: 指标名称，例："gdp_yoy"（GDP同比）, "cpi_yoy"（CPI同比）
            start: 开始日期
            end: 结束日期

        Returns:
            DataFrame，包含 ['date', 'value'] 列
        """
        ...


# ============================================================
# AKShare 实现
# ============================================================

class AKShareLoader:
    """
    基于 akshare 的数据加载器。

    覆盖：
    - A股日线/周线/月线（akshare.stock_zh_a_hist）
    - 港股行情（akshare.stock_hk_hist）
    - 中国宏观经济数据（akshare.macro_china_xxx）
    """

    # A股频率映射
    A_SHARE_FREQ_MAP = {
        "1d": "daily",
        "1w": "weekly",
        "1M": "monthly",
    }

    # 宏观指标映射（indicator名称 -> akshare函数名）
    MACRO_INDICATOR_MAP = {
        "gdp_yoy": "macro_china_gdp_yearly",
        "cpi_yoy": "macro_china_cpi_monthly",
        "ppi_yoy": "macro_china_ppi_monthly",
        "m2_yoy": "macro_china_money_supply",
        "pmi_manufacturing": "macro_china_pmi_yearly",
        "retail_sales_yoy": "macro_china_retail_price_index",
        "industrial_output_yoy": "macro_china_industrial_production_yoy",
    }

    def get_ohlcv(
        self,
        instrument: str,
        start: datetime,
        end: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        """
        获取股票 OHLCV 数据。
        自动根据代码前缀判断市场（A股/港股）。
        """
        try:
            import akshare as ak
        except ImportError:
            raise ImportError(
                "akshare is required. Install with: pip install akshare"
            )

        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        # 判断市场：港股代码通常是5位数字或包含"."
        if self._is_hk_stock(instrument):
            return self._get_hk_ohlcv(ak, instrument, start_str, end_str)
        else:
            return self._get_a_share_ohlcv(ak, instrument, start_str, end_str, frequency)

    def _is_hk_stock(self, instrument: str) -> bool:
        """判断是否为港股代码"""
        # 港股代码：5位数字（如"00700"）或包含".HK"
        clean = instrument.replace(".HK", "").replace(".hk", "")
        return len(clean) == 5 and clean.isdigit()

    def _get_a_share_ohlcv(
        self,
        ak: object,
        symbol: str,
        start: str,
        end: str,
        frequency: str,
    ) -> pd.DataFrame:
        """获取A股行情"""
        ak_period = self.A_SHARE_FREQ_MAP.get(frequency, "daily")
        logger.info(f"Fetching A-share OHLCV: {symbol}, {start}~{end}, period={ak_period}")

        df = ak.stock_zh_a_hist(  # type: ignore
            symbol=symbol,
            period=ak_period,
            start_date=start,
            end_date=end,
            adjust="qfq",  # 前复权
        )

        # 标准化列名
        column_map = {
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
            "振幅": "amplitude",
            "涨跌幅": "pct_change",
            "涨跌额": "price_change",
            "换手率": "turnover",
        }
        df = df.rename(columns=column_map)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

        logger.info(f"Loaded {len(df)} rows for {symbol}")
        return df

    def _get_hk_ohlcv(
        self,
        ak: object,
        symbol: str,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """获取港股行情"""
        # 统一去掉后缀
        clean_symbol = symbol.replace(".HK", "").replace(".hk", "").zfill(5)
        logger.info(f"Fetching HK OHLCV: {clean_symbol}, {start}~{end}")

        df = ak.stock_hk_hist(  # type: ignore
            symbol=clean_symbol,
            period="daily",
            start_date=start,
            end_date=end,
            adjust="qfq",
        )

        column_map = {
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
            "涨跌幅": "pct_change",
        }
        df = df.rename(columns=column_map)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

        logger.info(f"Loaded {len(df)} rows for {clean_symbol}")
        return df

    def get_macro_data(
        self,
        indicator: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """获取中国宏观经济数据"""
        try:
            import akshare as ak
        except ImportError:
            raise ImportError("akshare is required")

        if indicator not in self.MACRO_INDICATOR_MAP:
            raise ValueError(
                f"Unknown macro indicator: '{indicator}'. "
                f"Available: {list(self.MACRO_INDICATOR_MAP.keys())}"
            )

        func_name = self.MACRO_INDICATOR_MAP[indicator]
        logger.info(f"Fetching macro data: {indicator} via {func_name}")

        func = getattr(ak, func_name)
        df = func()

        # 标准化日期列
        date_col_candidates = ["date", "日期", "月份", "年份", "时间"]
        for col in date_col_candidates:
            if col in df.columns:
                df["date"] = pd.to_datetime(df[col])
                break

        if "date" not in df.columns:
            raise ValueError(f"Cannot find date column in macro data for {indicator}")

        # 过滤日期范围
        df = df[(df["date"] >= start) & (df["date"] <= end)]
        df = df.set_index("date").sort_index()

        return df


# ============================================================
# BaoStock 实现
# ============================================================

class BaoStockLoader:
    """
    基于 baostock 的数据加载器。

    主要用于 A股历史行情的批量下载，数据质量稳定。
    自动处理登录/登出生命周期。
    """

    FREQ_MAP = {
        "1d": "d",
        "1w": "w",
        "1M": "m",
        "30m": "30",
        "15m": "15",
        "5m": "5",
    }

    def _ensure_login(self, bs: object) -> None:
        """确保 baostock 已登录"""
        login_result = bs.login()  # type: ignore
        if login_result.error_code != "0":
            raise RuntimeError(
                f"BaoStock login failed: {login_result.error_msg}"
            )
        logger.debug("BaoStock logged in successfully")

    def _format_symbol(self, instrument: str) -> str:
        """
        将标的代码转换为 baostock 格式。
        baostock 格式：'sh.600519'（上海），'sz.000001'（深圳）
        """
        if "." in instrument:
            return instrument  # 已经是 baostock 格式

        code = instrument.strip()
        if code.startswith("6"):
            return f"sh.{code}"
        elif code.startswith(("0", "3")):
            return f"sz.{code}"
        elif code.startswith(("4", "8")):
            # 北交所
            return f"bj.{code}"
        else:
            return f"sh.{code}"

    def get_ohlcv(
        self,
        instrument: str,
        start: datetime,
        end: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        """获取 A股 OHLCV 数据"""
        try:
            import baostock as bs
        except ImportError:
            raise ImportError(
                "baostock is required. Install with: pip install baostock"
            )

        self._ensure_login(bs)

        try:
            symbol = self._format_symbol(instrument)
            freq = self.FREQ_MAP.get(frequency, "d")
            start_str = start.strftime("%Y-%m-%d")
            end_str = end.strftime("%Y-%m-%d")

            fields = "date,open,high,low,close,volume,amount,turn,pctChg"
            logger.info(f"BaoStock fetching: {symbol}, {start_str}~{end_str}, freq={freq}")

            rs = bs.query_history_k_data_plus(
                symbol,
                fields,
                start_date=start_str,
                end_date=end_str,
                frequency=freq,
                adjustflag="2",  # 前复权
            )

            data_list = []
            while rs.error_code == "0" and rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                logger.warning(f"No data returned for {symbol}")
                return pd.DataFrame()

            df = pd.DataFrame(data_list, columns=rs.fields)

            # 类型转换
            numeric_cols = ["open", "high", "low", "close", "volume", "amount", "turn", "pctChg"]
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()

            # 标准化列名
            df = df.rename(columns={"pctChg": "pct_change", "turn": "turnover"})

            logger.info(f"BaoStock loaded {len(df)} rows for {symbol}")
            return df

        finally:
            bs.logout()
            logger.debug("BaoStock logged out")

    def get_macro_data(
        self,
        indicator: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """
        BaoStock 宏观数据支持有限，建议使用 AKShareLoader 获取宏观数据。
        """
        logger.warning(
            "BaoStockLoader.get_macro_data is limited. "
            "Consider using AKShareLoader for macro data."
        )
        return pd.DataFrame()


# ============================================================
# CSV 本地文件实现
# ============================================================

class CSVLoader:
    """
    本地 CSV 文件数据加载器。

    文件名格式：{instrument}_{frequency}.csv
    例：600519_1d.csv, 00700_1d.csv

    CSV 文件格式要求（至少包含以下列）：
    date, open, high, low, close, volume

    适用场景：
    - 测试（不依赖网络）
    - 离线环境
    - 缓存已下载数据
    """

    def __init__(self, data_dir: Optional[str] = None):
        """
        Args:
            data_dir: CSV 文件目录，默认为 'data/csv_cache'
        """
        self.data_dir = Path(data_dir or "data/csv_cache")
        if not self.data_dir.exists():
            logger.info(f"Creating CSV data directory: {self.data_dir}")
            self.data_dir.mkdir(parents=True, exist_ok=True)

    def _build_filepath(self, instrument: str, frequency: str) -> Path:
        """构建 CSV 文件路径"""
        filename = f"{instrument}_{frequency}.csv"
        return self.data_dir / filename

    def get_ohlcv(
        self,
        instrument: str,
        start: datetime,
        end: datetime,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        """从本地 CSV 加载 OHLCV 数据"""
        filepath = self._build_filepath(instrument, frequency)

        if not filepath.exists():
            raise FileNotFoundError(
                f"CSV file not found: {filepath}. "
                f"Expected format: {instrument}_{frequency}.csv in {self.data_dir}"
            )

        logger.info(f"Loading CSV: {filepath}")
        df = pd.read_csv(filepath)

        # 自动检测日期列
        date_col = None
        for col in ["date", "Date", "datetime", "Datetime", "trade_date"]:
            if col in df.columns:
                date_col = col
                break

        if date_col is None:
            raise ValueError(
                f"Cannot find date column in {filepath}. "
                f"Expected one of: date, Date, datetime, trade_date"
            )

        df[date_col] = pd.to_datetime(df[date_col])
        df = df.set_index(date_col)
        df.index.name = "date"
        df = df.sort_index()

        # 过滤日期范围
        df = df[(df.index >= start) & (df.index <= end)]

        # 标准化列名（小写）
        df.columns = [col.lower() for col in df.columns]

        logger.info(f"Loaded {len(df)} rows from {filepath}")
        return df

    def get_macro_data(
        self,
        indicator: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """从本地 CSV 加载宏观数据"""
        filepath = self.data_dir / f"macro_{indicator}.csv"

        if not filepath.exists():
            raise FileNotFoundError(f"Macro data file not found: {filepath}")

        df = pd.read_csv(filepath)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        df = df[(df.index >= start) & (df.index <= end)]

        return df

    def save_ohlcv(self, df: pd.DataFrame, instrument: str, frequency: str) -> str:
        """
        将 DataFrame 保存为 CSV 文件。
        用于缓存从网络获取的数据。

        Returns:
            保存的文件路径
        """
        filepath = self._build_filepath(instrument, frequency)
        df.to_csv(filepath)
        logger.info(f"Saved {len(df)} rows to {filepath}")
        return str(filepath)


# ============================================================
# 工厂函数
# ============================================================

def create_loader(
    loader_type: str,
    **kwargs: Any,
) -> HistoricalDataLoader:
    """
    工厂函数：根据类型创建对应的数据加载器。

    Args:
        loader_type: "akshare" / "baostock" / "csv"
        **kwargs: 传递给具体加载器的初始化参数

    Returns:
        实现 HistoricalDataLoader Protocol 的加载器实例
    """
    loaders = {
        "akshare": AKShareLoader,
        "baostock": BaoStockLoader,
        "csv": CSVLoader,
    }

    if loader_type not in loaders:
        raise ValueError(
            f"Unknown loader type: '{loader_type}'. "
            f"Available: {list(loaders.keys())}"
        )

    loader = loaders[loader_type](**kwargs)
    logger.info(f"Created {loader_type} data loader")
    return loader
