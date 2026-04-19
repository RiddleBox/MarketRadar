"""
m11_agent_sim/event_catalog.py — 历史事件目录

从种子价格数据自动生成 HistoricalEvent 列表，供校准器使用。
支持：
  1. 手动标注的重大事件（政策、黑天鹅等）
  2. 自动从价格数据生成交易日快照（覆盖日常行情）
  3. 合并两者产出 50+ 校准案例
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from .schemas import (
    Direction,
    HistoricalEvent,
    MarketInput,
    PriceContext,
    SentimentContext,
    SignalContext,
)
from .sentiment_provider import SentimentProvider, DecorrelatedSentimentProvider

logger = logging.getLogger(__name__)

_sentiment_provider: SentimentProvider = DecorrelatedSentimentProvider()


def set_sentiment_provider(provider: SentimentProvider):
    """设置全局情绪数据源（可替换为 M10 真实数据等）"""
    global _sentiment_provider
    _sentiment_provider = provider


def get_sentiment_provider() -> SentimentProvider:
    return _sentiment_provider


ANNOTATED_EVENTS = [
    {"date": "2024-07-22", "desc": "三中全会召开，改革预期升温", "signal_dir": "BULLISH", "intensity": 6.0},
    {"date": "2024-08-05", "desc": "全球恐慌抛售，日股熔断传导A股", "signal_dir": "BEARISH", "intensity": 7.5},
    {"date": "2024-09-24", "desc": "央行降准50bp+降息，历史性宽松组合", "signal_dir": "BULLISH", "intensity": 9.5},
    {"date": "2024-09-30", "desc": "牛市情绪爆发，两市成交破万亿", "signal_dir": "BULLISH", "intensity": 9.0},
    {"date": "2024-10-08", "desc": "国庆后首日高开低走，游资出货", "signal_dir": "BEARISH", "intensity": 7.0},
    {"date": "2024-10-09", "desc": "大跌后反弹，政策底与市场底博弈", "signal_dir": "BULLISH", "intensity": 6.0},
    {"date": "2024-11-08", "desc": "人大常委会审批化债方案，规模超预期", "signal_dir": "BULLISH", "intensity": 7.0},
    {"date": "2024-12-09", "desc": "中央经济工作会议前夕，政策预期升温", "signal_dir": "BULLISH", "intensity": 6.5},
    {"date": "2024-12-13", "desc": "中央经济工作会议定调积极，市场反应平淡", "signal_dir": "NEUTRAL", "intensity": 5.0},
    {"date": "2025-01-06", "desc": "年初资金面紧张，小盘股杀跌", "signal_dir": "BEARISH", "intensity": 5.5},
    {"date": "2025-01-20", "desc": "特朗普就职前不确定性上升", "signal_dir": "BEARISH", "intensity": 5.0},
    {"date": "2025-01-27", "desc": "DeepSeek发布V3模型，科技板块异动", "signal_dir": "BULLISH", "intensity": 8.0},
    {"date": "2025-02-17", "desc": "DeepSeek AI突破持续发酵，科技股领涨", "signal_dir": "BULLISH", "intensity": 8.0},
    {"date": "2025-03-05", "desc": "两会开幕，GDP目标5%，财政力度符合预期", "signal_dir": "NEUTRAL", "intensity": 5.5},
    {"date": "2025-03-11", "desc": "两会闭幕，政策面温和，市场回调", "signal_dir": "BEARISH", "intensity": 5.0},
    {"date": "2025-04-07", "desc": "美国关税冲击，外资大幅流出", "signal_dir": "BEARISH", "intensity": 8.5},
]


def load_event_catalog(min_events: int = 50, instrument: str = "510300.SH") -> List[HistoricalEvent]:
    """加载历史事件目录，至少产出 min_events 个案例。"""
    events = []

    annotated_dates = set()
    for ann in ANNOTATED_EVENTS:
        annotated_dates.add(ann["date"])
        event = _build_annotated_event(ann, instrument)
        if event:
            events.append(event)

    if len(events) >= min_events:
        return events

    auto_events = generate_auto_events(
        instrument=instrument,
        exclude_dates=annotated_dates,
        max_events=min_events - len(events) + 10,
    )
    events.extend(auto_events)

    events.sort(key=lambda e: e.date)
    logger.info(f"[EventCatalog] 共加载 {len(events)} 个历史事件（{len(ANNOTATED_EVENTS)} 标注 + {len(events)-len(ANNOTATED_EVENTS)} 自动生成）")
    return events[:max(min_events, len(events))]


def _build_annotated_event(ann: dict, instrument: str) -> Optional[HistoricalEvent]:
    date_str = ann["date"]
    signal_dir = ann.get("signal_dir", "NEUTRAL")
    intensity = ann.get("intensity", 5.0)

    price = _load_price_from_seed(instrument, date_str)
    sentiment = _sentiment_provider.get_sentiment(date_str, signal_dir, price.price_5d_chg_pct)

    market_input = MarketInput(
        timestamp=datetime.fromisoformat(date_str),
        market="A_SHARE",
        event_description=ann["desc"],
        price=price,
        sentiment=sentiment,
        signals=SignalContext(
            bullish_count=1 if signal_dir == "BULLISH" else 0,
            bearish_count=1 if signal_dir == "BEARISH" else 0,
            neutral_count=1 if signal_dir == "NEUTRAL" else 0,
            dominant_signal_type="macro" if "政策" in ann["desc"] or "央行" in ann["desc"] else "event_driven",
            avg_intensity=round(intensity),
            avg_confidence=6,
            recent_signals=[{"signal_type": "macro", "description": ann["desc"][:40], "direction": signal_dir}],
        ),
        recent_extreme_move=_compute_recent_extreme(instrument, date_str),
        days_since_extreme=_compute_days_since_extreme(instrument, date_str),
    )

    actual_5d = _compute_5d_return(instrument, date_str)
    actual_direction: Direction = (
        "BULLISH" if actual_5d > 0.03 else "BEARISH" if actual_5d < -0.03 else "NEUTRAL"
    )

    return HistoricalEvent(
        event_id=f"ev_{date_str.replace('-', '')}",
        date=date_str,
        description=ann["desc"],
        market_input=market_input,
        actual_direction=actual_direction,
        actual_5d_return=actual_5d,
        actual_is_extreme=abs(actual_5d) > 0.08,
    )


def generate_auto_events(
    instrument: str = "510300.SH",
    exclude_dates: Optional[set] = None,
    max_events: int = 50,
) -> List[HistoricalEvent]:
    """从种子价格数据自动生成交易日快照事件。

    策略：选择有显著价格变动的交易日（5日涨幅绝对值 > 2%），
    无显著变动时等间隔采样。
    """
    exclude_dates = exclude_dates or set()
    try:
        from backtest.seed_data import SEED_510300
        seed = SEED_510300
    except ImportError:
        logger.warning("[EventCatalog] 无法加载种子价格数据")
        return []

    dates_sorted = sorted(seed.keys())
    all_events = []

    for date_str in dates_sorted:
        if date_str in exclude_dates:
            continue

        ret5 = _compute_5d_return(instrument, date_str)
        if ret5 is None:
            continue

        if abs(ret5) < 0.02 and len(all_events) % 5 != 0:
            continue

        price = _load_price_from_seed(instrument, date_str)
        if price.current_price == 0:
            continue

        # Auto events: use backward price direction but with NEUTRAL range
        # Most auto events are daily snapshots with weak signals → NEUTRAL sentiment
        direction: Direction = "BULLISH" if ret5 > 0 else "BEARISH" if ret5 < 0 else "NEUTRAL"
        # For auto events with |ret5| < 3%, the signal direction is weak → use NEUTRAL
        signal_for_sentiment = direction if abs(ret5) >= 0.03 else "NEUTRAL"
        sentiment = _sentiment_provider.get_sentiment(date_str, signal_for_sentiment, price.price_5d_chg_pct)

        chg_desc = f"5日涨跌幅{ret5:+.1%}" if abs(ret5) >= 0.03 else "窄幅震荡"
        event_desc = f"沪深300ETF {chg_desc}" if abs(ret5) >= 0.03 else f"沪深300ETF 日常行情"

        market_input = MarketInput(
            timestamp=datetime.fromisoformat(date_str),
            market="A_SHARE",
            event_description=event_desc,
            price=price,
            sentiment=sentiment,
            signals=SignalContext(
                bullish_count=1 if direction == "BULLISH" else 0,
                bearish_count=1 if direction == "BEARISH" else 0,
                neutral_count=1 if direction == "NEUTRAL" else 0,
                dominant_signal_type="market_data",
                avg_intensity=min(10, max(1, int(abs(ret5) * 80))),
                avg_confidence=4,
                recent_signals=[{"signal_type": "market_data", "description": event_desc[:40]}],
            ),
            recent_extreme_move=_compute_recent_extreme(instrument, date_str),
            days_since_extreme=_compute_days_since_extreme(instrument, date_str),
        )

        actual_direction: Direction = (
            "BULLISH" if ret5 > 0.03 else "BEARISH" if ret5 < -0.03 else "NEUTRAL"
        )

        all_events.append(HistoricalEvent(
            event_id=f"auto_{date_str.replace('-', '')}",
            date=date_str,
            description=event_desc,
            market_input=market_input,
            actual_direction=actual_direction,
            actual_5d_return=ret5,
            actual_is_extreme=abs(ret5) > 0.08,
        ))

        if len(all_events) >= max_events:
            break

    return all_events


def _load_price_from_seed(instrument: str, date_str: str) -> PriceContext:
    try:
        from backtest.seed_data import SEED_510300, SEED_588000
        seed = SEED_510300 if "510300" in instrument else SEED_588000
    except ImportError:
        return PriceContext()

    if date_str not in seed:
        return PriceContext()

    row = seed[date_str]
    close = row["close"]
    volume = row.get("volume", 0)

    dates_sorted = sorted(seed.keys())
    idx = dates_sorted.index(date_str)

    ma5_prices = [seed[d]["close"] for d in dates_sorted[max(0, idx-4):idx+1]]
    ma20_prices = [seed[d]["close"] for d in dates_sorted[max(0, idx-19):idx+1]]
    ma5 = sum(ma5_prices) / len(ma5_prices) if ma5_prices else close
    ma20 = sum(ma20_prices) / len(ma20_prices) if ma20_prices else close

    ret5 = 0.0
    if idx >= 5:
        prev5 = seed[dates_sorted[idx-5]]["close"]
        ret5 = (close - prev5) / prev5 if prev5 else 0.0
    ret20 = 0.0
    if idx >= 20:
        prev20 = seed[dates_sorted[idx-20]]["close"]
        ret20 = (close - prev20) / prev20 if prev20 else 0.0

    avg_vol_5 = 1
    if idx >= 5:
        vols = [seed[dates_sorted[idx-i]]["volume"] for i in range(1, 6)]
        avg_vol_5 = sum(vols) / len(vols) if vols else 1
    volume_ratio = volume / avg_vol_5 if avg_vol_5 > 0 else 1.0

    return PriceContext(
        instrument=instrument,
        current_price=close,
        price_5d_chg_pct=ret5,
        price_20d_chg_pct=ret20,
        ma5=ma5,
        ma20=ma20,
        above_ma5=close > ma5,
        above_ma20=close > ma20,
        volume_ratio=volume_ratio,
    )


def _compute_5d_return(instrument: str, date_str: str) -> float:
    try:
        from backtest.seed_data import SEED_510300, SEED_588000
        seed = SEED_510300 if "510300" in instrument else SEED_588000
    except ImportError:
        return 0.0

    if date_str not in seed:
        return 0.0

    dates_sorted = sorted(seed.keys())
    idx = dates_sorted.index(date_str)

    entry_price = seed[date_str]["close"]

    for d in range(5, 15):
        if idx + d < len(dates_sorted):
            exit_date = dates_sorted[idx + d]
            exit_price = seed[exit_date]["close"]
            return (exit_price - entry_price) / entry_price if entry_price else 0.0

    return 0.0


def _compute_recent_extreme(instrument: str, date_str: str) -> float:
    """Compute the largest single-day return in the past 5 trading days."""
    try:
        from backtest.seed_data import SEED_510300, SEED_588000
        seed = SEED_510300 if "510300" in instrument else SEED_588000
    except ImportError:
        return 0.0

    if date_str not in seed:
        return 0.0

    dates_sorted = sorted(seed.keys())
    idx = dates_sorted.index(date_str)

    max_move = 0.0
    for d in range(1, 6):
        if idx - d >= 0:
            prev_date = dates_sorted[idx - d]
            curr_date = dates_sorted[idx - d + 1]
            prev_close = seed[prev_date]["close"]
            curr_close = seed[curr_date]["close"]
            if prev_close > 0:
                chg = (curr_close - prev_close) / prev_close
                if abs(chg) > abs(max_move):
                    max_move = chg
    return max_move


def _compute_days_since_extreme(instrument: str, date_str: str, threshold: float = 0.04) -> int:
    """Count trading days since last single-day move exceeding threshold."""
    try:
        from backtest.seed_data import SEED_510300, SEED_588000
        seed = SEED_510300 if "510300" in instrument else SEED_588000
    except ImportError:
        return 0

    if date_str not in seed:
        return 0

    dates_sorted = sorted(seed.keys())
    idx = dates_sorted.index(date_str)

    for d in range(1, min(21, idx + 1)):
        prev_date = dates_sorted[idx - d]
        curr_date = dates_sorted[idx - d + 1]
        prev_close = seed[prev_date]["close"]
        curr_close = seed[curr_date]["close"]
        if prev_close > 0:
            chg = abs((curr_close - prev_close) / prev_close)
            if chg >= threshold:
                return d
    return 99


def _estimate_sentiment(date_str: str, signal_dir: str, price_5d_chg: float = 0.0) -> SentimentContext:
    """基于价格数据估算情绪上下文。

    使用 price_5d_chg 作为情绪代理：
    - 5日涨幅大 → 市场偏贪婪
    - 5日跌幅大 → 市场偏恐惧
    - 量比高 → 情绪强度高
    """
    fg = 50.0 + price_5d_chg * 200
    fg = max(10.0, min(95.0, fg))

    if fg <= 20:
        label = "极度恐惧"
    elif fg <= 40:
        label = "恐惧"
    elif fg <= 60:
        label = "中性"
    elif fg <= 80:
        label = "贪婪"
    else:
        label = "极度贪婪"

    northbound = price_5d_chg * 500
    northbound = max(-150.0, min(150.0, northbound))
    adr = 0.5 + price_5d_chg * 2
    adr = max(0.15, min(0.90, adr))
    weibo = max(-1.0, min(1.0, price_5d_chg * 5))

    return SentimentContext(
        fear_greed_index=round(fg, 1),
        sentiment_label=label,
        northbound_flow=round(northbound, 1),
        advance_decline_ratio=round(adr, 3),
        weibo_sentiment=round(weibo, 2),
    )
